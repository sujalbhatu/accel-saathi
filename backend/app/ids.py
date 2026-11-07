"""Identifier rules: GSTIN checksum, Udyam format, masking for logs and UI."""
import re

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

GST_STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}
UDYAM_STATE_CODES = {
    "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam", "BR": "Bihar", "CG": "Chhattisgarh",
    "DL": "Delhi", "GA": "Goa", "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh",
    "JK": "Jammu and Kashmir", "JH": "Jharkhand", "KR": "Karnataka", "KL": "Kerala", "MP": "Madhya Pradesh",
    "MH": "Maharashtra", "MN": "Manipur", "ML": "Meghalaya", "MZ": "Mizoram", "NL": "Nagaland",
    "OD": "Odisha", "PB": "Punjab", "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu",
    "TS": "Telangana", "TR": "Tripura", "UP": "Uttar Pradesh", "UK": "Uttarakhand", "WB": "West Bengal",
    "CH": "Chandigarh", "PY": "Puducherry", "LA": "Ladakh",
}

# GSTIN = 2-digit state + 10-char PAN (5 letters, 4 digits, 1 letter) + entity code + 'Z' + checksum.
# The README says the 4th PAN character is always 'X' in this dataset; we accept any letter there.
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
UDYAM_RE = re.compile(r"^UDYAM-([A-Z]{2})-(\d{2})-(\d{7})$")

# Characters OCR commonly confuses, used only where the GSTIN format demands the other type.
_TO_DIGIT = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}
_TO_LETTER = {v: k for k, v in {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7"}.items()}
_DIGIT_POS = {0, 1, 7, 8, 9, 10}
_LETTER_POS = {2, 3, 4, 5, 6, 11, 13}


def gstin_checksum(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _CHARS[(36 - total % 36) % 36]


def normalise_gstin(raw: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", (raw or "").upper())


def fix_gstin_ocr(raw: str) -> str:
    """Repair only type mismatches (a letter where the format needs a digit, or vice versa).
    Never swaps one digit for another, so a genuinely altered number still fails the checksum."""
    g = list(normalise_gstin(raw))
    if len(g) != 15:
        return "".join(g)
    for i, ch in enumerate(g):
        if i in _DIGIT_POS and not ch.isdigit():
            g[i] = _TO_DIGIT.get(ch, ch)
        elif i in _LETTER_POS and ch.isdigit():
            g[i] = _TO_LETTER.get(ch, ch)
    if g[13] == "2":
        g[13] = "Z"
    return "".join(g)


def validate_gstin(raw: str) -> dict:
    g = normalise_gstin(raw)
    if len(g) != 15:
        return {"gstin": g, "valid": False, "reason": "GSTIN must have 15 characters"}
    if not GSTIN_RE.match(g):
        return {"gstin": g, "valid": False, "reason": "GSTIN does not follow the official format"}
    if g[:2] not in GST_STATE_CODES:
        return {"gstin": g, "valid": False, "reason": f"State code {g[:2]} does not exist"}
    if gstin_checksum(g[:14]) != g[14]:
        return {"gstin": g, "valid": False, "reason": "Check digit does not match (number mistyped or altered)"}
    return {"gstin": g, "valid": True, "state": GST_STATE_CODES[g[:2]], "pan": g[2:12]}


def validate_udyam(raw: str) -> dict:
    u = re.sub(r"\s+", "", (raw or "").upper())
    m = UDYAM_RE.match(u)
    if not m:
        return {"udyam": u, "valid": False, "reason": "Udyam number must look like UDYAM-XX-00-0000000"}
    if m.group(1) not in UDYAM_STATE_CODES:
        return {"udyam": u, "valid": False, "reason": f"State code {m.group(1)} does not exist"}
    return {"udyam": u, "valid": True, "state": UDYAM_STATE_CODES[m.group(1)]}


def mask(value: str | None, keep_start: int = 2, keep_end: int = 3) -> str:
    """'27QHJXK0658U1ZL' -> '27••••••••••1ZL'. Used everywhere an identifier is displayed or logged."""
    if not value:
        return ""
    v = str(value)
    if len(v) <= keep_start + keep_end:
        return "•" * len(v)
    return v[:keep_start] + "•" * (len(v) - keep_start - keep_end) + v[-keep_end:]


def mask_name(name: str | None) -> str:
    if not name:
        return ""
    return " ".join(p[0] + "•" * (len(p) - 1) if len(p) > 1 else p for p in name.split())
