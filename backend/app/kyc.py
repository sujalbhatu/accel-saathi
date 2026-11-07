"""Smart KYC: read four documents, cross-check them with each other and with the GST and Udyam
registries, and explain every problem in one plain sentence.

Privacy by design (DPDP Act 2023):
- nothing is processed before consent is recorded for this application and purpose;
- only the fields a check needs are kept; the image is discarded after extraction (we keep a hash);
- identifiers are masked in every API response and in the audit log.
"""
import hashlib
import re
from datetime import date
from difflib import SequenceMatcher

import pandas as pd

from . import store
from .data import TODAY, gstin_by_trade_name, gstin_registry, udyam_by_name, udyam_registry
from .ids import (GST_STATE_CODES, UDYAM_STATE_CODES, fix_gstin_ocr, mask, mask_name, normalise_gstin,
                  validate_gstin, validate_udyam)
from .ocr import decode, read_boxes, sharpness

DOC_TYPES = {
    "gst_certificate": "GST registration certificate",
    "udyam_certificate": "Udyam registration certificate",
    "signatory_id": "Authorised signatory ID",
    "address_proof": "Address proof (utility bill)",
}
REQUIRED = list(DOC_TYPES)
NO_GST_REQUIRED = ["signatory_id", "address_proof"]  # a business without GST: Udyam is optional, GST not needed


def required_for(has_gstin: bool | None, has_udyam: bool | None = None) -> list[str]:
    """Documents an owner must give. One who told the advisor they have no GSTIN needs only the signatory's ID
    (Aadhaar OTP is enough) and a recent bill for the address; demanding a GST certificate would block them.
    Udyam registration is voluntary: when the registry has none for this business, its certificate isn't asked for."""
    docs = NO_GST_REQUIRED if has_gstin is False else REQUIRED
    return [d for d in docs if not (d == "udyam_certificate" and has_udyam is False)]


def udyam_registered(gstin: str | None) -> bool | None:
    """Whether the business behind a GSTIN has a Udyam registration (same name, same state). None if unknown."""
    reg = gstin_registry().get(normalise_gstin(gstin or "")) if gstin else None
    if not reg:
        return None
    for name in {reg["trade_name"].lower(), reg["legal_name"].lower()}:
        if any(u["state"] == reg["state"] for u in udyam_by_name().get(name, [])):
            return True
    return False
ADDRESS_PROOF_MAX_AGE_DAYS = 90
MIN_SHARPNESS = 120.0

LABELS = {
    "gst_certificate": {"gstin": ["gstin"], "legal_name": ["legal name"], "trade_name": ["trade name"],
                        "constitution": ["constitution"], "address": ["address of principal", "place of business"],
                        "date": ["date of liability"], "reg_type": ["type of registration"]},
    "udyam_certificate": {"udyam": ["udyam reg. number", "udyam reg number"], "name": ["enterprise name"],
                          "activity": ["major activity"], "city": ["city"], "state": ["state"],
                          "date": ["date of registration"]},
    "signatory_id": {"name": ["name"], "designation": ["designation"], "business": ["for business"],
                     "id_no": ["id no."], "valid_till": ["valid till"]},
    "address_proof": {"consumer_no": ["consumer no."], "billed_to": ["billed to"], "address": ["supply address"],
                      "bill_date": ["bill date"], "units": ["units consumed"], "amount": ["amount due (inr)"]},
}
_TITLES = [("gst registration", "gst_certificate"), ("udyam", "udyam_certificate"), ("signatory", "signatory_id"),
           ("bill", "address_proof")]
_NOISE = ("specimen", "hackathon", "not a valid", "fictional", "format for", "ocr testing", "synthetic")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def similar(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def names_match(a: str, b: str) -> bool:
    """Strict name comparison that tolerates OCR noise but not a different business name.
    'Neha B (Prop. Shri Physio Clinic)' vs 'Neha B (Prop. Neelgiri Physio Clinic)' -> False."""
    pa, pb = re.search(r"\(prop\.?\s*(.+?)\)", a or "", re.I), re.search(r"\(prop\.?\s*(.+?)\)", b or "", re.I)
    if pa and pb and SequenceMatcher(None, _norm(pa.group(1)), _norm(pb.group(1))).ratio() < 0.88:
        return False
    na, nb = _norm(a), _norm(b)
    return bool(na and nb) and (na == nb or SequenceMatcher(None, na, nb).ratio() >= 0.9)


def _label_key(text: str, doc_type: str) -> str | None:
    t = _norm(text)
    best, score = None, 0.0
    for key, names in LABELS[doc_type].items():
        for n in names:
            s = SequenceMatcher(None, t, _norm(n)).ratio()
            if s > score:
                best, score = key, s
    return best if score >= 0.72 else None


def detect_type(boxes: list[dict]) -> str | None:
    head = " ".join(b["text"].lower() for b in boxes[:4])
    return next((dt for kw, dt in _TITLES if kw in head), None)


def parse(boxes: list[dict], doc_type: str) -> dict:
    """Pair each value with the label on its row. Values on a row with no label (a wrapped address)
    continue the previous field."""
    boxes = [b for b in boxes if not any(n in b["text"].lower() for n in _NOISE)]
    if not boxes:
        return {}
    xs = sorted(b["x"] for b in boxes)
    split = xs[0] + (xs[-1] - xs[0]) * 0.33
    labels = [(b, _label_key(b["text"], doc_type)) for b in boxes if b["x"] < split]
    labels = [(b, k) for b, k in labels if k]
    values = [b for b in boxes if b["x"] >= split]
    fields: dict[str, list] = {}
    for v in sorted(values, key=lambda b: b["y"]):
        above = [(b, k) for b, k in labels if b["y"] <= v["y"] + max(12, b["h"] * 0.6)]
        if not above:
            continue
        lab_box, key = max(above, key=lambda bk: bk[0]["y"])
        fields.setdefault(key, []).append(v)
    out = {}
    for k, parts in fields.items():
        joined = parts[0]["text"]
        for p in (b["text"] for b in parts[1:]):  # "West Be" + "ngal - 347550" -> "West Bengal - 347550"
            joined = joined + p if joined[-1:].isalpha() and p[:1].isalpha() and p[:1].islower() else joined + " " + p
        out[k] = joined.strip()
        readings = [b.get("alt") for b in parts if b.get("alt")] + [b["text"] for b in parts]
        if k == "gstin":
            out[k] = best_gstin(readings)
        elif k == "udyam":
            out[k] = best_udyam(readings) or out[k]
        elif k in ("date", "valid_till", "bill_date"):
            out[k] = best_date(readings) or out[k]
    return out


def best_gstin(readings: list[str]) -> str:
    """Pick the reading that passes format + checksum. OCR sometimes inserts a character, so for
    readings longer than 15 we also try dropping one or two. Digits are never swapped, so an
    altered GSTIN still fails."""
    from itertools import combinations
    norm = [fix_gstin_ocr(r) for r in readings if r]
    swaps = {"0": "O", "O": "0", "1": "I", "I": "1"}
    for g in norm:
        if validate_gstin(g)["valid"]:
            return g
        if len(g) == 15 and g[14] in swaps and validate_gstin(g[:14] + swaps[g[14]])["valid"]:
            return g[:14] + swaps[g[14]]
    for raw in readings:
        g = normalise_gstin(raw)
        if 15 < len(g) <= 17:
            found = {fix_gstin_ocr("".join(c for i, c in enumerate(g) if i not in drop))
                     for drop in combinations(range(len(g)), len(g) - 15)}
            valid = sorted(x for x in found if validate_gstin(x)["valid"])
            registered = [x for x in valid if x in gstin_registry()]
            if len(registered) == 1:
                return registered[0]
            others = [x for x in norm if len(x) == 15]
            if valid and others:
                dist = {x: min(sum(a != b for a, b in zip(x, o)) for o in others) for x in valid}
                best = min(dist.values())
                if list(dist.values()).count(best) == 1 and best <= 2:
                    return min(dist, key=dist.get)
    return next((g for g in norm if len(g) == 15), norm[0] if norm else "")


def best_udyam(readings: list[str]) -> str | None:
    for r in sorted(readings, key=lambda r: "-" not in r):
        m = re.search(r"UDYAM\W*([A-Z]{2,3})\W*([0-9O]{2})\W*([0-9O]{7})", r.upper())
        if m:
            st = m.group(1)
            st = st if st in UDYAM_STATE_CODES else (st[-2:] if st[-2:] in UDYAM_STATE_CODES else st[:2])
            return f"UDYAM-{st}-{m.group(2).replace('O', '0')}-{m.group(3).replace('O', '0')}"
    return None


def best_date(readings: list[str]) -> str | None:
    for r in readings:
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", r)
        if m:
            return m.group(0)
    for r in readings:
        d = re.sub(r"\D", "", r)
        if len(d) == 8:
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return None


def _date(s: str | None) -> pd.Timestamp | None:
    m = re.search(r"(\d{4})\D?(\d{2})\D?(\d{2})", s or "")
    if not m:
        return None
    try:
        return pd.Timestamp(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
    except ValueError:
        return None


def _pin(s: str | None) -> str | None:
    m = re.search(r"(\d{6})\s*$", re.sub(r"[^\d ]", " ", s or "").strip())
    return m.group(1) if m else None


def extract_document(image_bytes: bytes, declared_type: str | None = None) -> dict:
    img = decode(image_bytes)
    sharp = sharpness(img)
    boxes = read_boxes(img)
    doc_type = detect_type(boxes) or declared_type
    result = {"doc_type": doc_type, "sharpness": round(sharp, 1), "sha256": hashlib.sha256(image_bytes).hexdigest(),
              "fields": {}, "quality_ok": sharp >= MIN_SHARPNESS}
    if doc_type in LABELS:
        result["fields"] = parse(boxes, doc_type)
    if declared_type and doc_type and declared_type != doc_type:
        result["type_mismatch"] = True
    return result


# ---------- validation ----------

def _check(status: str, code: str, msg: str, doc: str | None = None) -> dict:
    return {"status": status, "code": code, "message": msg, "doc": doc}


def validate(docs: dict[str, dict], business_hint: dict | None = None) -> dict:
    """docs: doc_type -> extract_document() result. Returns checks with pass / warn / fail."""
    checks: list[dict] = []
    no_gst = (business_hint or {}).get("has_gstin") is False
    if no_gst and "gst_certificate" in docs:  # told the advisor "no GSTIN": this certificate plays no part
        checks.append(_check("warn", "gst_not_needed", "You told us you don't have a GSTIN, so this GST certificate "
                             "isn't needed and wasn't checked. Remove it, or share your GSTIN with the advisor to "
                             "buy GST-only services.", "gst_certificate"))
        docs = {k: v for k, v in docs.items() if k != "gst_certificate"}
    f = {k: v.get("fields", {}) for k, v in docs.items()}

    has_udyam = None if no_gst else udyam_registered((f.get("gst_certificate") or {}).get("gstin"))
    if has_udyam is False and "udyam_certificate" not in docs:
        checks.append(_check("pass", "udyam_not_needed", "No Udyam registration found for this business, so no Udyam "
                             "certificate is needed.", "udyam_certificate"))
    for dt in required_for(False if no_gst else None, has_udyam):
        if dt not in docs:
            checks.append(_check("fail", "missing_document", f"{DOC_TYPES[dt]} has not been uploaded.", dt))
        elif not docs[dt].get("quality_ok", True) or not f[dt]:
            checks.append(_check("fail", "unreadable", f"{DOC_TYPES[dt]} is too blurred to read. Please retake the "
                                 "photo in good light, holding the phone steady.", dt))
        elif docs[dt].get("type_mismatch"):
            checks.append(_check("fail", "wrong_document", f"The file uploaded as {DOC_TYPES[dt]} looks like a "
                                 "different document.", dt))

    gst = f.get("gst_certificate") or {}
    reg = None
    if gst.get("gstin"):
        v = validate_gstin(gst["gstin"])
        if not v["valid"]:
            near = _nearest_registered(gst)
            hint = f" The GST registry lists {mask(near['gstin'])} for {near['trade_name']}." if near else ""
            checks.append(_check("fail", "gstin_invalid", f"GSTIN {mask(v['gstin'])} on the certificate is not valid: "
                                 f"{v['reason'].lower()}. The certificate may be altered or mistyped.{hint}",
                                 "gst_certificate"))
        else:
            reg = gstin_registry().get(v["gstin"])
            if not reg:
                checks.append(_check("fail", "gstin_not_registered", f"GSTIN {mask(v['gstin'])} is not in the GST "
                                     "registry.", "gst_certificate"))
            elif reg["status"] != "Active":
                checks.append(_check("fail", "gstin_inactive", f"GSTIN {mask(v['gstin'])} is {reg['status'].upper()} "
                                     "in the GST registry, so it cannot be used to buy business services.",
                                     "gst_certificate"))
            else:
                checks.append(_check("pass", "gstin_active", f"GSTIN {mask(v['gstin'])} is valid and active.",
                                     "gst_certificate"))
            if reg:
                for fld, reg_fld, label in (("legal_name", "legal_name", "legal name"),
                                            ("trade_name", "trade_name", "trade name")):
                    if gst.get(fld) and not names_match(gst[fld], reg[reg_fld]):
                        checks.append(_check("fail", f"gst_{fld}_mismatch", f"The {label} on the certificate "
                                             f"(\"{gst[fld]}\") does not match the GST registry (\"{reg[reg_fld]}\").",
                                             "gst_certificate"))
                if gst.get("address") and _pin(gst["address"]) and _pin(gst["address"]) != _pin(
                        reg["principal_place_of_business"]):
                    checks.append(_check("warn", "gst_address_mismatch", "The address PIN code on the GST certificate "
                                         "differs from the registry.", "gst_certificate"))
                if GST_STATE_CODES.get(v["gstin"][:2]) != reg["state"]:
                    checks.append(_check("fail", "gst_state_mismatch", "The GSTIN state code does not match the "
                                         "registered state.", "gst_certificate"))

    udy = f.get("udyam_certificate") or {}
    if udy.get("udyam"):
        uv = validate_udyam(udy["udyam"])
        urec = udyam_registry().get(uv["udyam"]) if uv["valid"] else None
        if not uv["valid"]:
            checks.append(_check("fail", "udyam_invalid", uv["reason"] + ".", "udyam_certificate"))
        elif not urec:
            checks.append(_check("fail", "udyam_not_registered", f"Udyam number {mask(uv['udyam'], 9, 3)} is not in "
                                 "the Udyam registry.", "udyam_certificate"))
        else:
            checks.append(_check("pass", "udyam_found", f"Udyam {mask(uv['udyam'], 9, 3)} found: {urec['enterprise_type']}"
                                 f" enterprise, {urec['nic_description'].lower()}.", "udyam_certificate"))
            if udy.get("name") and not names_match(udy["name"], urec["enterprise_name"]):
                checks.append(_check("fail", "udyam_name_mismatch", f"Enterprise name on the Udyam certificate "
                                     f"(\"{udy['name']}\") does not match the registry.", "udyam_certificate"))
            if reg and urec["state"] != reg["state"]:
                checks.append(_check("fail", "udyam_state_mismatch", f"Udyam is registered in {urec['state']} but the "
                                     f"GSTIN is in {reg['state']}.", "udyam_certificate"))
            if reg and similar(urec["enterprise_name"], reg["trade_name"]) < 0.85 and similar(
                    urec["enterprise_name"], reg["legal_name"]) < 0.85:
                checks.append(_check("fail", "udyam_gst_name_mismatch", f"Udyam is for \"{urec['enterprise_name']}\" "
                                     f"but the GSTIN belongs to \"{reg['trade_name']}\".", "udyam_certificate"))
        if uv.get("valid") and UDYAM_STATE_CODES.get(uv["udyam"].split("-")[1]) and udy.get("state") and \
                similar(UDYAM_STATE_CODES[uv["udyam"].split("-")[1]], udy["state"]) < 0.8:
            checks.append(_check("warn", "udyam_state_code", "The state code in the Udyam number does not match "
                                 "the state printed on the certificate.", "udyam_certificate"))

    business = (reg or {}).get("trade_name") or gst.get("trade_name") or udy.get("name") or ""
    sig = f.get("signatory_id") or {}
    if sig:
        vt = _date(sig.get("valid_till"))
        if vt is not None and vt < TODAY:
            checks.append(_check("fail", "signatory_id_expired", f"The signatory ID expired on {vt.date()}.",
                                 "signatory_id"))
        elif vt is not None:
            checks.append(_check("pass", "signatory_id_valid", f"Signatory ID is valid till {vt.date()}.",
                                 "signatory_id"))
        if business and sig.get("business") and similar(sig["business"], business) < 0.85:
            checks.append(_check("fail", "signatory_business_mismatch", f"The signatory ID is issued for "
                                 f"\"{sig['business']}\", not \"{business}\".", "signatory_id"))
        legal = (reg or {}).get("legal_name") or gst.get("legal_name") or ""
        constitution = (reg or {}).get("constitution") or gst.get("constitution") or ""
        if constitution == "Proprietorship" and sig.get("name"):
            proprietor = legal.split("(")[0].strip()
            if proprietor and similar(sig["name"], proprietor) < 0.85:
                checks.append(_check("fail", "signatory_not_proprietor", f"For a proprietorship the signatory must be "
                                     f"the proprietor ({mask_name(proprietor)}), but the ID is for "
                                     f"{mask_name(sig['name'])}.", "signatory_id"))
            else:
                checks.append(_check("pass", "signatory_is_proprietor", "Signatory is the registered proprietor.",
                                     "signatory_id"))
        elif constitution and sig.get("name"):
            checks.append(_check("warn", "authorisation_letter", f"{constitution}: please also upload a board "
                                 "resolution or authorisation letter for the signatory.", "signatory_id"))

    addr = f.get("address_proof") or {}
    if addr and docs.get("address_proof", {}).get("source") == "gst_registry":
        checks.append(_check("pass", "address_from_gst", "Address verified from the GST registration "
                             "(principal place of business).", "address_proof"))
    elif addr:
        bd = _date(addr.get("bill_date"))
        if bd is not None:
            age = (TODAY - bd).days
            if age > ADDRESS_PROOF_MAX_AGE_DAYS:
                checks.append(_check("fail", "address_proof_old", f"The bill is dated {bd.date()}, {age} days old. "
                                     f"Address proof must be from the last {ADDRESS_PROOF_MAX_AGE_DAYS} days.",
                                     "address_proof"))
            elif age < 0:
                checks.append(_check("fail", "address_proof_future", "The bill date is in the future.", "address_proof"))
            else:
                checks.append(_check("pass", "address_proof_recent", f"Bill dated {bd.date()} ({age} days old).",
                                     "address_proof"))
        if business and addr.get("billed_to") and similar(addr["billed_to"], business) < 0.85 and similar(
                addr["billed_to"], (reg or {}).get("legal_name", "")) < 0.85:
            checks.append(_check("fail", "address_name_mismatch", f"The bill is in the name of \"{addr['billed_to']}\", "
                                 f"not \"{business}\".", "address_proof"))
        ref_addr = (reg or {}).get("principal_place_of_business") or gst.get("address")
        if ref_addr and addr.get("address"):
            pin_a, pin_r = _pin(addr["address"]), _pin(ref_addr)
            if pin_a and pin_r and pin_a != pin_r:
                checks.append(_check("fail", "address_mismatch", f"The bill's PIN code ({pin_a}) differs from the "
                                     f"registered business address ({pin_r}).", "address_proof"))
            elif similar(addr["address"].split(",")[0], ref_addr.split(",")[0]) < 0.8:
                checks.append(_check("warn", "address_line_mismatch", "The street address on the bill differs from "
                                     "the GST address.", "address_proof"))
            else:
                checks.append(_check("pass", "address_match", "Bill address matches the registered address.",
                                     "address_proof"))

    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    decision = "rejected" if fails else ("review" if warns else "approved")
    return {"decision": decision, "checks": sorted(checks, key=lambda c: {"fail": 0, "warn": 1, "pass": 2}[c["status"]]),
            "business": business, "gstin_masked": mask((reg or {}).get("gstin") or gst.get("gstin")),
            "fail_count": len(fails), "warn_count": len(warns)}


def _nearest_registered(gst: dict) -> dict | None:
    name = (gst.get("trade_name") or "").lower()
    cands = gstin_by_trade_name().get(name, [])
    if gst.get("legal_name"):
        cands = [c for c in cands if similar(c["legal_name"], gst["legal_name"]) >= 0.85] or cands
    return cands[0] if len(cands) == 1 else None


def masked_fields(doc_type: str, fields: dict) -> dict:
    """What the owner sees back: enough to confirm, never the full identifier."""
    out = dict(fields)
    for k in ("gstin", "udyam", "id_no", "consumer_no"):
        if out.get(k):
            out[k] = mask(out[k], 2 if k == "gstin" else 4, 3)
    return out
