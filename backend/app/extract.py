"""Turns what the owner types (English, Hindi, Hinglish, Marathi, Tamil) into profile fields.

Two layers: an LLM extractor when a key is configured, and a rules extractor that always runs.
Rules win for hard facts they can read exactly (numbers, GSTIN, city); the LLM fills the rest.
"""
import json
import re

from . import llm, pains
from .data import business_types, city_tiers
from .recommender import NEEDS

# Digits in every Indian script the app supports, read as 0-9 (Devanagari, Bengali, Gurmukhi, Gujarati, Tamil,
# Telugu, Kannada, Malayalam). The name is kept for the callers that import it.
_DEVANAGARI = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯੦੧੨੩੪੫੬੭੮੯૦૧૨૩૪૫૬૭૮૯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯೦೧೨೩೪೫೬೭೮೯൦൧൨൩൪൫൬൭൮൯",
                            "0123456789" * 8)
_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "ek": 1, "do": 2, "teen": 3, "char": 4,
          "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7, "aath": 8, "das": 10, "बीस": 20,
          "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "सात": 7, "आठ": 8, "दस": 10,
          # "one" to "five" in Tamil, Telugu, Kannada, Malayalam, Bengali, Gujarati, Punjabi, Marathi
          "ஒரு": 1, "ஒன்று": 1, "இரண்டு": 2, "மூன்று": 3, "நான்கு": 4, "ஐந்து": 5,
          "ఒక": 1, "ఒకటి": 1, "రెండు": 2, "మూడు": 3, "నాలుగు": 4, "ఐదు": 5,
          "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4, "ಐದು": 5,
          "ഒരു": 1, "ഒന്ന്": 1, "രണ്ട്": 2, "മൂന്ന്": 3, "നാല്": 4, "അഞ്ച്": 5,
          "এক": 1, "একটি": 1, "একটা": 1, "দুই": 2, "তিন": 3, "চার": 4, "পাঁচ": 5,
          "એક": 1, "બે": 2, "ત્રણ": 3, "ચાર": 4, "પાંચ": 5,
          "ਇੱਕ": 1, "ਦੋ": 2, "ਤਿੰਨ": 3, "ਚਾਰ": 4, "ਪੰਜ": 5,
          "दोन": 2, "पाच": 5}

_PEOPLE = (r"(?:employees?|staff|people|persons?|workers?|members?|trainers?|teachers?|doctors?|nurses?|agents?|"
           r"technicians?|engineers?|log|karmachari|कर्मचारी|लोग|लोक|पेर|பேர்|ஊழியர்|ಜನ|ಸಿಬ್ಬಂದಿ|જણ|લોકો|మంది|জন|ਲੋਕ|പേർ)")
_SITES = (r"(?:sites?|branch(?:es)?|stores?|outlets?|shops?|locations?|clinics?|centres?|centers?|restaurants?|"
          r"hotels?|gyms?|schools?|factories|factory|plants?|units?|offices?|workshops?|labs?|studios?|warehouses?|"
          r"godowns?|showrooms?|propert(?:y|ies)|dukaan|dukan|शाखा|ब्रांच|दुकान|दुकानें|ठिकाणे|கிளை|கடை|"
          r"क्लिनिक|ऑफिस|ऑफ़िस|कार्यालय|शोरूम|स्टोर|फैक्ट्री|फ़ैक्ट्री|कारखाना|सेंटर|लैब|होटल|रेस्टोरेंट|स्कूल|गोदाम|"
          r"जिम|आउटलेट|यूनिट|प्लांट|அலுவலகம்|கிளினிக்)")

# keyword -> canonical business_type from the leads data
_BUSINESS_KEYWORDS = [
    (r"kirana|grocery|general store|किराना|किराणा", "Kirana store"),
    (r"salon|parlou?r|beauty|सैलून|पार्लर", "Salon"),
    (r"pharmacy chain|medical stores", "Pharmacy chain"),
    (r"pharmacy|chemist|medical store|दवा|मेडिकल", "Pharmacy"),
    (r"bakery chain", "Bakery chain"),
    (r"bakery|bake house|बेकरी", "Bakery"),
    (r"sweet|mithai|मिठाई", "Sweet shop"),
    (r"boutique|tailor|बुटीक", "Boutique"),
    (r"hardware", "Hardware store"),
    (r"mobile (?:repair|shop|store|accessor)|phone (?:repair|shop)|mobile (?:ki |ka )?(?:dukan|dukaan)|"
     r"मोबाइल (?:की |का )?(?:दुकान|शॉप|स्टोर|रिपेयर)|मोबाइल रिपेयरिंग|मोबाईल (?:दुकान|शॉप)|மொபைல் கடை", "Mobile repair shop"),
    (r"optic|spectacle|चश्मा", "Optician"),
    (r"stationery|stationers|book ?shop", "Stationery shop"),
    (r"dental|dentist|दंत", "Dental clinic"),
    (r"physio", "Physiotherapy clinic"),
    (r"diagnostic|pathology|lab\b", "Diagnostic lab"),
    (r"\bca\b|chartered accountant|accountant|ca firm|tax consult", "CA firm"),
    (r"law|lawyer|advocate|legal|वकील", "Law office"),
    (r"coaching|tuition|classes|institute|कोचिंग", "Coaching centre"),
    (r"insurance", "Insurance agency"),
    (r"architect|interior", "Architecture studio"),
    (r"real estate|property|realty|broker", "Real estate agency"),
    (r"travel|tours", "Travel agency"),
    (r"restaurant|dhaba|cafe|caf[eé]|food court|रेस्टोरेंट|ढाबा", "Restaurant chain"),
    (r"hotel|lodge|guest ?house|stays|होटल", "Budget hotel group"),
    (r"gym|fitness", "Gym chain"),
    (r"pre-?school|play ?school|kindergarten", "Pre-school chain"),
    (r"apparel|garment|clothing|fashion|कपड़े", "Apparel retail chain"),
    (r"electronics", "Electronics retail chain"),
    (r"auto ?parts|automobile|auto component", "Auto-parts unit"),
    (r"textile|weaving|spinning|कपड़ा मिल", "Textile unit"),
    (r"food processing|masala|spices|पापड़", "Food processing unit"),
    (r"furniture|wood", "Furniture workshop"),
    (r"packaging|carton|corrugat", "Packaging unit"),
    (r"plastic|moulding|molding", "Plastic moulding unit"),
    (r"print", "Printing press"),
    (r"clinic|doctor|hospital|nursing|क्लिनिक|डॉक्टर|மருத்துவ", "Clinic"),
    (r"factory|manufactur|फ़ैक्टरी|फैक्टरी|कारखाना|தொழிற்சாலை", "Auto-parts unit"),
    (r"shop|store|दुकान|கடை", "Kirana store"),
]
_CHAIN_UPGRADE = {"Pharmacy": "Pharmacy chain", "Bakery": "Bakery chain", "Boutique": "Apparel retail chain"}

_NEED_KEYWORDS = {
    "payments": r"\bpos\b|billing|bill machine|upi|card payment|payments?|बिलिंग|पेमेंट",
    "whatsapp": r"whats ?app|व्हाट्सएप|वॉट्सऐप",
    "sms": r"\bsms\b|text message|reminders?",
    "cctv": r"cctv|camera|surveillance|कैमरा|कॅमेरा|கேமரா|ক্যামেরা|કેમેરા|ಕ್ಯಾಮೆರಾ|ക്യാമറ|ਕੈਮਰਾ|కెమెరా",
    "email": r"e-?mail|gmail|domain mail|ईमेल",
    "security": r"antivirus|virus|ransomware|cyber|security|सुरक्षा",
    "backup": r"\bbackup\b(?! (?:internet|line|connection))|cloud storage|storage|बैकअप",
    "website": r"website|online presence|वेबसाइट",
    "guest_wifi": r"guest wi-?fi|customer wi-?fi|wi-?fi for (?:customers|guests|students|members)|free wi-?fi|(?:ग्राहक|ਗਾਹਕ|গ্রাহক|ગ્રાહક|ಗ್ರಾಹಕ|ഉപഭോക്താ|వినియోగదారు|கஸ்டமர்|வாடிக்கையாளர)\S*(?:\s+\S+){0,2}\s+wi-?fi",
    "failover": r"downtime|backup internet|internet (?:goes|went) down|failover|always on|uptime|नेट बंद",
    "calls": r"\bivr\b|phone lines?|landline|call recording|telephony|calls? (?:to|from) customers|call cent",
    "tollfree": r"toll ?free|1800",
    "static_ip": r"static ip|remote access|fixed ip|server",
    "iot": r"machine|sensor|iot|energy monitor|मशीन",
    "fleet": r"vehicle|fleet|delivery (?:van|bike)s?|truck|gps|गाड़ी",
    "central_mgmt": r"one bill|central(?:ly)?|all (?:branches|sites|outlets|stores)|single dashboard|manage .*from one",
    "firewall": r"firewall",
}
_NO_GST = r"no gst|without gst|not registered|gst nahi|gst नहीं|जीएसटी नहीं|gstin नहीं|don'?t have (?:a )?gst"
_HAS_GST = (r"(?:have|has|with|got|are)\s+(?:a\s+|an\s+)?gst(?:in| number| registration)?\b|gst(?:in)?\s*(?:-|:)?\s*"
            r"(?:registered|yes|hai|है|number hai|आहे|ಇದೆ|છે|ఉంది|আছে|ਹੈ|உள்ளது)|gst registered")
_GSTIN = r"(?<![A-Z0-9])\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Z0-9])"
_UDYAM = r"UDYAM-[A-Z]{2}-\d{2}-\d{7}"

_HINDI_CITIES = {"दिल्ली": "Delhi", "मुंबई": "Mumbai", "पुणे": "Pune", "कोलकाता": "Kolkata", "चेन्नई": "Chennai",
                 "बेंगलुरु": "Bengaluru", "बैंगलोर": "Bengaluru", "हैदराबाद": "Hyderabad", "अहमदाबाद": "Ahmedabad",
                 "जयपुर": "Jaipur", "लखनऊ": "Lucknow", "पटना": "Patna", "इंदौर": "Indore", "भोपाल": "Bhopal",
                 "नागपुर": "Nagpur", "नाशिक": "Nashik", "नासिक": "Nashik", "सूरत": "Surat", "वडोदरा": "Vadodara",
                 "लुधियाना": "Ludhiana", "कोच्चि": "Kochi", "சென்னை": "Chennai", "கோயம்புத்தூர்": "Coimbatore",
                 "bangalore": "Bengaluru", "bombay": "Mumbai", "calcutta": "Kolkata", "madras": "Chennai",
                 "baroda": "Vadodara", "vizag": "Visakhapatnam", "mysore": "Mysuru", "cochin": "Kochi",
                 "new delhi": "Delhi", "gurgaon": "Delhi", "noida": "Delhi",
                 "पुण्यात": "Pune", "पुण्याला": "Pune", "मुंबईत": "Mumbai", "नागपुरात": "Nagpur", "नागपूर": "Nagpur",
                 "नाशिकला": "Nashik", "नाशिकमध्ये": "Nashik", "ಬೆಂಗಳೂರು": "Bengaluru", "ಮೈಸೂರು": "Mysuru",
                 "హైదరాబాద్": "Hyderabad", "విశాఖపట్నం": "Visakhapatnam", "কলকাতা": "Kolkata", "অমদাবাদ": "Ahmedabad",
                 "અમદાવાદ": "Ahmedabad", "સુરત": "Surat", "વડોદરા": "Vadodara", "ਲੁਧਿਆਣਾ": "Ludhiana",
                 "കൊച്ചി": "Kochi", "ചെന്നൈ": "Chennai", "பெங்களூர்": "Bengaluru", "ಚೆನ್ನೈ": "Chennai"}


def _num(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return _WORDS.get(s)


def rules_extract(text: str) -> dict:
    raw = text.translate(_DEVANAGARI)
    low = raw.lower()
    out: dict = {}
    num = r"(\d+|[a-z\u0900-\u0DFF]+)"  # digits, or a number word in Latin or any Indian script
    m = next((m for m in re.finditer(num + r"\s*\+?\s*" + _PEOPLE, low) if _num(m.group(1)) is not None), None)
    if m:
        out["employees"] = _num(m.group(1))
    elif re.search(r"\b(?:just me|only me|myself only|by myself|alone|akela|sirf main|अकेला|अकेले)\b", low):
        out["employees"] = 1
    m = re.search(r"(?:team of|staff of)\s*(\d+)|(\d+|[a-z]+) of us\b|\bwe are (\d+)\b(?! ?(?:years?|yrs|km|%|branches|sites))", low)
    if m and "employees" not in out:
        n = _num(next(g for g in m.groups() if g))
        if n:
            out["employees"] = n
    m = next((m for m in re.finditer(num + r"\s+(?:[a-z\u0900-\u097f-]+\s+){0,2}" + _SITES, low)
              if _num(m.group(1)) is not None), None)
    if m:
        out["sites"] = _num(m.group(1))
    elif re.search(r"(?:^|\s)(?:a|one|single|my|our|ek|एक|मेरी|मेरा|हमारी|माझे|माझी)\s+(?:\S+\s+)?" + _SITES, low):
        out["sites"] = 1
    for pat, bt in _BUSINESS_KEYWORDS:
        if re.search(pat, low):
            out["business_type"] = bt
            break
    if out.get("sites", 1) >= 3 and out.get("business_type") in _CHAIN_UPGRADE:
        out["business_type"] = _CHAIN_UPGRADE[out["business_type"]]
    named = [(m.start(), -len(city), city) for city in city_tiers()
             for m in [re.search(r"\b" + re.escape(city.lower()) + r"\b", low)] if m]
    if named:  # "4 restaurants in Pune and Mumbai": the first city named is home
        out["city"] = min(named)[2]
    else:
        for alias, city in _HINDI_CITIES.items():
            if alias in low or alias in raw:
                out["city"] = city
                break
    if "city" not in out:  # a town we don't list: "a shop in Jhansi" -> Jhansi (treated as tier 2)
        t = re.search(r"\b(?:in|at|from|near)\s+([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})?)\b", raw)
        if t and t.group(1).lower() not in ("gst", "india", "the", "my", "our", "one", "two", "hindi", "english",
                                            "marathi", "tamil", "kannada", "telugu", "gujarati", "bengali", "punjabi",
                                            "malayalam", "whatsapp", "total", "future"):
            out["city"] = t.group(1)
    g = re.search(_GSTIN, raw.upper())
    if g:
        out["gstin"] = g.group(0)
        out["has_gstin"] = True
    elif re.search(_NO_GST, low):
        out["has_gstin"] = False
    elif re.search(_HAS_GST, low):
        out["has_gstin"] = True
    u = re.search(_UDYAM, raw.upper())
    if u:
        out["udyam"] = u.group(0)
    needs = {k for k, pat in _NEED_KEYWORDS.items() if re.search(pat, low)}
    told = pains.found(text)
    if told:  # "we had a theft" -> CCTV; "UPI fails at rush hour" -> billing + backup internet
        out["pains"] = told
        needs |= set(pains.needs_for(told))
    if needs:
        out["needs"] = sorted(needs)
    m = re.search(r"(?:spend|paying|pay|bill(?: is)?|kharcha|खर्च)\D{0,20}(\d[\d,]{2,6})", low)
    if m:
        out["current_spend"] = int(m.group(1).replace(",", ""))
    m = re.search(r"budget\D{0,15}(\d[\d,]{2,6})", low)
    if m:
        out["budget"] = int(m.group(1).replace(",", ""))
    if re.search(r"no fib(?:re|er)|fib(?:re|er) (?:not|isn'?t) available|no cable", low):
        out["fibre_available"] = False
    for k, pat in (("cameras", r"(\d+)\s*(?:cctv )?cameras?"), ("mobile_lines", r"(\d+)\s*(?:sims?|mobile|phones?|lines)"),
                   ("vehicles", r"(\d+)\s*(?:vehicles?|vans?|trucks?|bikes?)"), ("machines", r"(\d+)\s*machines?"),
                   ("counters", r"(\d+)\s*(?:counters?|billing counters?)"), ("users", r"(\d+)\s*(?:email|users)")):
        m = re.search(pat, low)
        if m:
            out.setdefault("counts", {})[k] = int(m.group(1))
    return out


_SYSTEM = """You extract facts about an Indian small business from the owner's message (any language or Hinglish).
Return ONLY a JSON object with any of these keys you can fill with confidence, omit the rest:
business_type (pick the closest of: {types}), employees (int), sites (int), city (string, English name),
has_gstin (bool), gstin (string), current_spend (int, INR per month on telecom/internet),
budget (int, INR per month), fibre_available (bool), needs (list from: {needs}),
counts (object with any of mobile_lines, cameras, users, counters, vehicles, machines as ints).
Never guess numbers that were not stated."""


def llm_extract(text: str, context: dict) -> dict:
    prompt = _SYSTEM.format(types=", ".join(sorted(business_types())), needs=", ".join(NEEDS))
    data = llm.chat_json([
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Known so far: {json.dumps(context, ensure_ascii=False)}\nOwner says: {text}"},
    ])
    return clean_llm_facts(data) if data else {}


def clean_llm_facts(data: dict) -> dict:
    """Keep only well-typed facts from an LLM answer."""
    clean: dict = {}
    if data.get("business_type") in business_types():
        clean["business_type"] = data["business_type"]
    for k in ("employees", "sites", "current_spend", "budget"):
        if isinstance(data.get(k), (int, float)) and data[k] > 0:
            clean[k] = int(data[k])
    for k in ("has_gstin", "fibre_available"):
        if isinstance(data.get(k), bool):
            clean[k] = data[k]
    if isinstance(data.get("city"), str) and data["city"].strip():
        clean["city"] = data["city"].strip().title()
    if isinstance(data.get("gstin"), str):
        clean["gstin"] = data["gstin"].upper().replace(" ", "")
    if isinstance(data.get("needs"), list):
        clean["needs"] = [n for n in data["needs"] if n in NEEDS]
    if isinstance(data.get("counts"), dict):
        clean["counts"] = {k: int(v) for k, v in data["counts"].items() if isinstance(v, (int, float)) and v > 0}
    return clean


def extract(text: str, context: dict | None = None, smart: dict | None = None) -> dict:
    """Rules facts merged with LLM facts. Pass `smart` when the LLM has already been asked this turn."""
    rules = rules_extract(text)
    if smart is None:
        smart = llm_extract(text, context or {}) if llm.enabled() else {}
    merged = {**smart, **{k: v for k, v in rules.items() if k not in ("needs", "counts", "business_type")}}
    if "business_type" in rules and "business_type" not in smart:
        merged["business_type"] = rules["business_type"]
    merged["needs"] = sorted(set(smart.get("needs", [])) | set(rules.get("needs", [])))
    merged["counts"] = {**smart.get("counts", {}), **rules.get("counts", {})}
    return {k: v for k, v in merged.items() if v not in (None, [], {})}
