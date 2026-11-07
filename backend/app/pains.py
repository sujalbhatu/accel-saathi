"""Problems an owner can tell us about, and the services that fix them (the catalogue's metadata on the demand side).

A good salesperson asks about the business, not about products: "do payments fail at rush hour?", "any theft?".
Each problem here is tagged with the needs (and so the catalogue services) that solve it. The advisor asks two or
three of them as taps when the owner is choosing services, and also picks them out of anything the owner types, in
English, Hinglish and the Indian languages, with or without the AI model (the model is told the same list). A
service that solves a problem the owner told us about is pre-ticked, ranked first and never trimmed for price, and
the "why this bundle" panel says so in her words.
"""
import re

# key -> (needs it maps to, pattern in the owner's words)
PAINS: dict[str, tuple[list[str], str]] = {
    "pay_fail": (["payments", "failover"],
                 r"(?:upi|payments?|card|qr|swip\w*|billing)\b.{0,30}(?:fail|stuck|declin|not (?:go|work)|slow|hang|atak|nahi ja)|"
                 r"rush hour|peak hours?|पेमेंट.{0,20}(?:फेल|अटक|नहीं जा)|यूपीआई.{0,20}(?:फेल|अटक)|भीड़ में"),
    "theft": (["cctv"], r"theft|thief|thieves|stolen|steal|shoplift|pilfer|chori|चोरी|चोर|திருட்டு|ಕಳ್ಳತನ|దొంగతనం|"
                        r"മോഷണ|ચોરી|ਚੋਰੀ|চুরি"),
    "wifi_ask": (["guest_wifi"], r"(?:customers?|clients?|guests?|students?|patients?)\b.{0,20}(?:ask|want|need)\w*.{0,15}wi-?fi|"
                                 r"wi-?fi.{0,15}(?:for|to) (?:customers?|clients?|guests?|students?|patients?)|"
                                 r"ग्राहक.{0,20}वाई-?फाई"),
    "records": (["backup", "security"],
                r"(?:records?|data|files?|bills?|accounts?|reports?)\b.{0,30}(?:one|single|old|only one) (?:pc|computer|laptop|system)|"
                r"lost (?:my |our |all )?(?:data|files|records)|(?:pc|computer|laptop|system) (?:crash|died|broke)|"
                r"\bvirus|ransomware|हिसाब.{0,20}(?:एक|पुराने) (?:कंप्यूटर|लैपटॉप)|डेटा (?:चला गया|उड़ गया|खो)"),
    "missed_calls": (["calls"], r"miss(?:ed|ing)? (?:customer )?calls?|calls? (?:get |are |go )?(?:missed|unanswered)|"
                                r"phone (?:is )?always busy|कॉल (?:छूट|मिस)|फोन (?:बिज़ी|व्यस्त)"),
    "repeat": (["whatsapp"], r"repeat customers?|customers? (?:don'?t|do not|never) come back|bring (?:customers|them) back|"
                             r"orders? on whats ?app|promote (?:my |our )?offers?|ग्राहक वापस"),
    "net_down": (["failover"], r"(?:internet|\bnet\b|connection|wi-?fi|broadband)\b.{0,20}(?:keeps? (?:going|dropping)|"
                               r"goes down (?:often|a lot|daily)|drops?|cuts? (?:out|off)|unreliable|band ho jata|chala jata)|"
                               r"नेट (?:बार-बार|बार बार|अक्सर) (?:बंद|चला)|इंटरनेट (?:बार-बार|बार बार|अक्सर)"),
    "branches": (["central_mgmt", "cctv"], r"(?:can'?t|cannot|hard to|no way to) (?:see|check|watch|manage|control)\b.{0,25}"
                                           r"(?:branch|outlet|store|site|shop)|from one (?:screen|place|phone)|"
                                           r"सारी (?:ब्रांच|दुकानें).{0,20}(?:एक जगह|देख)"),
}

# which problems to ask about, by kind of business (two or three taps, the most telling first)
_ASK = [
    (("salon", "boutique", "optician", "gym", "coaching", "pre-school"), ["wifi_ask", "repeat", "pay_fail"]),
    (("dental", "physio", "diagnostic", "clinic"), ["records", "missed_calls", "net_down"]),
    (("ca firm", "law", "insurance", "architecture", "real estate", "travel"), ["records", "missed_calls", "net_down"]),
    (("unit", "press", "workshop", "manufactur", "factory"), ["records", "theft", "net_down"]),
]
_ASK_BY_SEGMENT = {"micro": ["pay_fail", "theft", "repeat"], "prof": ["records", "missed_calls", "net_down"],
                   "multi": ["pay_fail", "branches", "theft"], "mfg": ["records", "theft", "net_down"]}


def found(text: str) -> list[str]:
    low = (text or "").lower()
    return [k for k, (_, pat) in PAINS.items() if re.search(pat, low)]


def needs_for(keys: list[str]) -> list[str]:
    out: list[str] = []
    for k in keys:
        out += [n for n in PAINS.get(k, ([], ""))[0] if n not in out]
    return out


def to_ask(segment: str, business_type: str, told: list[str] | None = None) -> list[str]:
    bt = (business_type or "").lower()
    keys = next((ks for words, ks in _ASK if any(w in bt for w in words)), _ASK_BY_SEGMENT.get(segment, _ASK_BY_SEGMENT["micro"]))
    return [k for k in keys if k not in (told or [])]
