"""Safety layer around the advisor.

screen(text)         What kind of message is this, before anything else reads it? An attempt to steer the AI, a demand
                     for a discount or a promise the catalogue doesn't make, a request for someone else's data, a sign
                     of misuse, abuse, or something unrelated to the business. These are answered from fixed text in
                     the owner's language: they never reach the model, and they never change the bundle or the profile.
too_big(facts)       A business beyond small-business plans (or a typo such as "1000000 staff"): handed to a person
                     instead of being priced.
reply_ok(reply, rec) May this model-written answer be shown? The model is treated as untrusted: an answer that quotes a
                     price or percentage that isn't in the catalogue or the quote, offers a discount or a waiver,
                     promises something, runs down a competitor, carries a link or an identifier, or leaks its
                     instructions is dropped, and the app answers from its own rules instead.

Everything here is plain pattern matching, so it costs nothing, behaves the same on every run and can be tested
without a model (tests/run_red_team.py).
"""
import re

from .data import products
from .recommender import unit_price

BLOCK = ("injection", "others_data", "misuse", "abuse", "offtopic")  # fixed answer; nothing else happens this turn
POLICY = ("discount", "promise")  # the app answers with the real options and exact prices; the bundle stays as it is

MAX_EMPLOYEES, MAX_SITES, MAX_COUNT = 500, 50, 300

_INJECTION = re.compile(
    r"(?:ignore|forget|disregard|override)\b.{0,40}\b(?:instructions?|rules?|prompts?|guidelines?|restrictions?|"
    r"polic(?:y|ies)|told|training|programming)"
    r"|(?:repeat|print|show|output|copy|write out)\b.{0,20}\b(?:everything|all|the (?:text|words|message)|what (?:is|was) written)\s+(?:above|before)"
    r"|(?:system|developer|hidden|initial|original|secret)\s+(?:prompt|message|instructions?|rules)"
    r"|(?:reveal|show|print|repeat|display|output|tell me|give me|what (?:is|are|were))\b.{0,20}\b(?:your|the)\s+"
    r"(?:prompt|instructions?|rules|guidelines|configuration|api key|keys?)\b"
    r"|you are now\b|from now on,? you|pretend (?:to be|you(?:'re| are))|act as (?:an? )?(?:different|unrestricted|new|admin|developer|dan)"
    r"|role-?play|jailbreak|\bdan mode\b|developer mode|debug mode|admin (?:mode|override|access)|do anything now|\bsudo\b"
    r"|</?(?:system|assistant|instructions?|prompt)>|\[/?(?:system|inst)\]|#{2,}\s*(?:system|instructions?)|new instructions?\s*:"
    r"|\bi(?: am|'m)\s+(?:the |an? |your )?(?:ceo|cto|founder|owner|director|manager|boss|admin(?:istrator)?|developer|engineer|"
    r"employee|staff)\b.{0,30}\baccel\b|\bi work (?:at|for|in|with) accel\b|\baccel (?:employee|staff|admin|head ?office|management)\b"
    r"|(?:set|change|update|make)\b.{0,25}\bprices?\b.{0,12}\bto\b\s*(?:₹|rs\.?|inr)?\s*\d"
    r"|pichh?le\b.{0,20}\b(?:nirdesh|instructions?)|niyam (?:bhool|bhul|tod)|apne rules? (?:bhool|bhul|tod|chhod)"
    r"|निर्देश(?:ों)?\s*(?:को\s*)?(?:भूल|अनदेखा|छोड़)|नियम\s*(?:भूल|तोड़)|सिस्टम\s*प्रॉम्प्ट", re.I | re.S)

_DISCOUNT = re.compile(
    r"\bdiscounts?\b|\d+\s*(?:%|percent|per cent)\s*(?:off|less|kam|discount|chhoot|chhut)|\boff\b.{0,12}\d+\s*%"
    r"|coupon|promo ?code|cash ?back|voucher|\bwaive(?:r|d)?\b|\bfor free\b|free of (?:cost|charge)"
    r"|\bfree\s+(?:installation|install|setup|set-up|months?|trial|router|device|sims?|service|upgrade)\b"
    r"|(?<!toll[- ])\bfree\s+(?:me|mein|mai)\b|\b(?:muft|moft|mufat)\b"
    r"|(?<!toll[- ])\bfree\b(?! (?:number|line|calling))(?:\s+\w+)?\s+(?:de ?do|dedo|kar ?do|chahiye|milega|doge)\b"
    r"|price match|match\b.{0,15}\bprice|\b(?:best|last|final|lowest possible)\s+(?:price|rate|offer|deal)\b|negotiat|bargain"
    r"|special\s+(?:price|rate|offer|deal)|\bany\s+offers?\b|\boffers?\s+(?:hai|chal|kya|running|available)"
    r"|छूट|डिस्काउंट|मुफ्त|मुफ़्त|फ्री\s*में|ऑफर|सवलत|मोफत|ડિસ્કાઉન્ટ|મફત|ছাড়|বিনামূল্যে|தள்ளுபடி|డిస్కౌంట్|తగ్గింపు|"
    r"ರಿಯಾಯಿತಿ|ಡಿಸ್ಕೌಂಟ್|കിഴിവ്|ഡിസ്കൗണ്ട്|ਛੋਟ|ਮੁਫ਼ਤ|ਡਿਸਕਾਊਂਟ", re.I)

_PROMISE = re.compile(
    r"guarant(?:ee|eed|y)|\bpromise\b|in writing|written\s+(?:commitment|assurance|guarantee)|\bassur(?:e|ance)\b|100\s*(?:%|percent)"
    r"|compensat|refund|money[- ]back"
    r"|\b(?:install\w*|activat\w*|connection|go live|live|setup|start\w*)\b.{0,30}\b(?:today|tonight|tomorrow|same day|right now|"
    r"immediately|within (?:an?|one|1|two|2) (?:hour|day)s?|in (?:an?|one|1|two|2) (?:hour|day)s?|aaj|kal)\b"
    r"|\b(?:today|tonight|tomorrow|same day|immediately|aaj|kal)\b.{0,30}\b(?:install\w*|activat\w*|connection|go live|laga\w*|chalu)\b"
    r"|गारंटी|गॅरंटी|वादा|लिखित|रिफंड|ગેરંટી|গ্যারান্টি|உத்தரவாதம்|హామీ|గ్యారంటీ|ಖಾತರಿ|ಗ್ಯಾರಂಟಿ|ഗ്യാരണ്ടി|ഉറപ്പ്|ਗਾਰੰਟੀ", re.I)

_OTHERS = re.compile(
    r"\b(?:other|another|someone else'?s?|somebody else'?s?|any|all|your|different)\s+(?:customers?|clients?|shops?|business(?:es)?|"
    r"owners?|users?|compan(?:y|ies))(?:'s?|s')?\s+(?:data|details?|info\w*|gstin|gst|numbers?|phones?|mobiles?|address(?:es)?|names?|"
    r"list|orders?|bills?|kyc|aadhaar|pan|documents?|records?)"
    r"|\b(?:gstin|gst number|phone numbers?|mobile numbers?|contact(?: details| numbers?)?|address(?:es)?|aadhaar|pan|kyc|orders?|bills?|"
    r"details?|data|names?)\s+of\s+(?:(?:your|the|other|another|all|any|some)\s+)*(?:customers?|clients?|shops?|pharmac(?:y|ies)|"
    r"business(?:es)?|owners?|competitors?|neighbou?rs?)"
    r"|(?:give|show|send|share|tell|sell|export|download|get|see|access|need|want)\b.{0,25}\b(?:your|accel'?s?|the|all)\s+"
    r"customers?\s+(?:list|database|data ?dump|records)|list\s+(?:of\s+)?(?:all\s+)?(?:your\s+)customers"
    r"|your\s+(?:customer\s+)?database|export\s+(?:all\s+)?(?:your|the)\s+(?:leads|customers)|\byour\s+leads?\s+(?:list|data)\b"
    r"|(?:dusre|doosre|baaki|baki)\s+(?:customers?|grahak\w*)|दूसरे\s+ग्राहक|अन्य\s+ग्राहक|बाकी\s+ग्राहक", re.I)

_MISUSE = re.compile(
    r"(?:send|sending|do|doing|for|run|running)\s+(?:\w+\s+){0,3}spam\b|\bspam\s+(?:sms|messages?|calls?|people|customers|numbers)"
    r"|(?:run|running|do|doing|for|start)\s+(?:a |an |my )?(?:\w+\s+)?scam\b|\bscam\s+(?:people|customers|scheme|calls?|messages?)"
    r"|lottery\s+(?:scheme|sms|messages?|winners?|prize|scam|calls?)|(?:won|win)\s+(?:a\s+)?(?:lottery|prize)\b|phish"
    r"|fake\s+(?:calls?|sms|messages?|numbers?|ids?|kyc|documents?|gstin|gst|aadhaar|pan|otp|bills?|certificates?)"
    r"|(?:otp|kyc)\s+(?:scheme|fraud)|bypass\s+(?:kyc|otp|verification|dlt)|without\s+(?:their\s+|customer\s+|any\s+)?(?:consent|permission|dlt)"
    r"|sim\s?box|bulk\s+sims?\b|\b\d{3,}\s*sims?(?:\s+cards?)?\b.{0,60}\b(?:otp|messages?|sms|calls?|market\w*|promot\w*)"
    r"|spoof|mask\s+(?:my|the|our)\s+(?:number|caller)|caller\s?id\s+(?:change|fake|spoof)"
    r"|(?:someone|somebody) else'?s\s+(?:gstin|gst|aadhaar|pan|id|documents?|name|kyc)"
    r"|(?:friend|neighbou?r|brother|uncle|cousin|relative)'?s?\s+(?:gstin|gst|aadhaar|pan|kyc|documents?)\b|not my\s+(?:gstin|aadhaar|pan)"
    r"|spy on|\btrack\s+(?:my\s+)?(?:wife|husband|girlfriend|boyfriend|spouse|ex)\b|hack\s+(?:into|someone|a\s|my\s+(?:competitor|neighbou?r))"
    r"|tap\s+(?:a\s+|the\s+|someone'?s\s+)?phone|call\s+(?:tapping|intercept)|unsolicited"
    r"|(?:buy|bought|purchased?)\s+(?:a\s+)?(?:phone\s+|mobile\s+)?(?:numbers?|contacts?)\s+(?:list|database|data)", re.I | re.S)

_ABUSE_WORDS = (r"stupid|idiots?|useless|dumb|morons?|fools?|bastards?|bloody|rubbish|worthless|pathetic|thie(?:f|ves)|cheat(?:er|ers|s)?|"
                r"liars?|frauds?|crooks?|bakwas|bekaar|bekar|bewakoof|bewkoof|bevkuf|pagal|gadha|gadhe|chor|kamina|kamine|ullu|nalayak|"
                r"ghatiya")
_ABUSE = re.compile(
    rf"\b(?:you|u|ur|you'?re|your|tum|tu|aap|ye|yeh|this|bloody|what an?|such an?)\b(?:\s+\w+){{0,3}}\s+(?:{_ABUSE_WORDS})\b"
    rf"|\b(?:{_ABUSE_WORDS})\s+(?:bots?|apps?|advisors?|assistant|ai|machine|compan(?:y|ies)|service|people|accel|saathi|log|ho|hai)\b"
    r"|\bshut up\b|\bfuck\w*|\bshit\w*|\bassholes?\b|\bbitch\w*|\bbullshit\b|\bcrap\b|\bwtf\b"
    r"|\bchutiy\w*|\bharam\w*|\bmadarchod\b|\bbh?enchod\b|\bbhosd\w*|\bsaal[ae]\b|\bkutt[ae]\b"
    r"|बकवास\s*(?:बॉट|ऐप|कंपनी|हो|है)|बेवकूफ|पागल|चोर\s*(?:कंपनी|हो|है)|गधा|कमीन|हरामी", re.I)

_OFFTOPIC = re.compile(
    r"\b(?:write|compose|tell|sing|recite|give)\b.{0,25}\b(?:poems?|poetry|shayari|jokes?|stor(?:y|ies)|songs?|essays?|rap|riddles?|"
    r"recipes?|limericks?|haiku)\b"
    r"|\b(?:write|compose)\b.{0,25}\b(?:code|program|script|homework|assignment|love letter)\b"
    r"|\bwho\s+(?:won|will win|is winning)\b|\b(?:prime minister|president|capital)\s+of\b|what'?s the weather|weather\s+(?:today|tomorrow|forecast)"
    r"|cricket score|\bipl\s+(?:score|winner|match)|\bbitcoin\b|\bcrypto\b|stock\s+(?:tips?|market tips?)|horoscope|rashifal"
    r"|\bi love you\b|\bmarry me\b|meaning of life|^\s*(?:what is\s+)?\d+\s*[+*x×/]\s*\d+\s*=?\s*\??\s*$"
    r"|कविता|शायरी|चुटकुला|कहानी\s+सुना|जोक\s+सुना|kavita|chutkula|joke\s+(?:sunao|suna)", re.I | re.S)

_ORDER = (("injection", _INJECTION), ("misuse", _MISUSE), ("others_data", _OTHERS), ("abuse", _ABUSE),
          ("discount", _DISCOUNT), ("promise", _PROMISE), ("offtopic", _OFFTOPIC))


def screen(text: str) -> str | None:
    """The first matching kind, most serious first, or None for an ordinary message."""
    if not text or not text.strip():
        return None
    for kind, pat in _ORDER:
        if pat.search(text):
            return kind
    return None


def too_big(facts: dict) -> tuple[str, int] | None:
    """(what, number) when the business is beyond small-business plans, e.g. ("employees", 1000000)."""
    e, n = facts.get("employees"), facts.get("sites")
    if isinstance(e, (int, float)) and e > MAX_EMPLOYEES:
        return "employees", int(e)
    if isinstance(n, (int, float)) and n > MAX_SITES:
        return "sites", int(n)
    for k, v in (facts.get("counts") or {}).items():
        if isinstance(v, (int, float)) and v > MAX_COUNT:
            return k, int(v)
    return None


# ---------- what the model may say ----------

_DIGITS = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯੦੧੨੩੪੫੬੭੮੯૦૧૨૩૪૫૬૭૮૯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯೦೧೨೩೪೫೬೭೮೯൦൧൨൩൪൫൬൭൮൯", "0123456789" * 8)
_MONEY_BEFORE = r"(?:₹|\brs\.?|\binr\b|rupees?|रुपये|रुपए|रु\.?|ரூ\.?|రూ\.?|ರೂ\.?|രൂ\.?|টাকা|રૂ\.?|ਰੁ\.?)"
_MONEY_AFTER = (r"(?:rupees?|rs\b|inr\b|/-|bucks|रुपये|रुपए|रुपया|ரூபாய்|రూపాయ\w*|ರೂಪಾಯಿ\w*|രൂപ|টাকা|રૂપિયા|ਰੁਪਏ|"
                r"(?:/|\s*per\s+|\s*a\s+|\s*every\s+)(?:month|mo|year)\b|\s*महीना|\s*प्रति\s*माह)")
_NUM = r"\d[\d,]*(?:\.\d+)?"
_NEG = (r"\b(?:no|not|n't|cannot|can't|cant|won't|wont|don't|dont|doesn't|never|unable|without|neither|nor|isn't|aren't|"
        r"nahi|nahin|nhi|mat)\b|नहीं|नही|नाही|इल्ला|இல்லை|முடியாது|లేదు|కాదు|ಇಲ್ಲ|ഇല്ല|না|নেই|નથી|ਨਹੀਂ")
_OFFER = (r"discount|cash ?back|coupon|promo ?code|voucher|waiv\w*|complimentary|on the house|free of (?:cost|charge)|for free|"
          r"free (?:installation|install|setup|months?|trial|router|device|sims?|upgrade)|price match|special (?:price|rate|offer|deal)|"
          r"छूट|डिस्काउंट|मुफ्त|मुफ़्त|मोफत|सवलत|ડિસ્કાઉન્ટ|મફત|ছাড়|বিনামূল্যে|தள்ளுபடி|இலவசமாக|ఉచితంగా|డిస్కౌంట్|ಉಚಿತವಾಗಿ|ರಿಯಾಯಿತಿ|"
          r"സൗജന്യമായി|കിഴിവ്|ਛੋਟ|ਮੁਫ਼ਤ")
_PLEDGE = (r"guarant\w*|\bpromis\w*|\bassur\w*|\bi (?:will|'ll) make sure|definitely will|for sure|refund\w*|money[- ]back|compensat\w*|"
           r"same[- ]day|by tomorrow|by today|within (?:an?|one|1|two|2|24|48) (?:hour|day)s?|गारंटी|वादा|रिफंड|ગેરંટી|গ্যারান্টি|"
           r"உத்தரவாதம்|హామీ|ಖಾತರಿ|ഗ്യാരണ്ടി|ਗਾਰੰਟੀ")
_VOW = r"\b(?:i|we)(?:\s+(?:can|will|do|hereby|personally|fully))?\s+(?:promise|guarantee|assure)\b"  # "I promise it will never go down"
_RIVALS = r"\bjio\b|\bvi\b|vodafone|\bidea\b|bsnl|act (?:fibernet|broadband)|hathway|excitel|tata (?:play|tele|sky)|you ?broadband|railwire|spectra|airtel"
_SLUR = (r"fraud|scam|cheat\w*|worst|terrible|useless|bad|poor|pathetic|unreliable|slow|rubbish|garbage|liars?|loot\w*|धोखा|बेकार|"
         r"खराब|घटिया")
_LEAK = (r"system prompt|my (?:instructions|prompt|guidelines|rules) (?:are|say|is)|i (?:was|am|have been) (?:told|instructed|programmed) to|"
         r"as an ai (?:language )?model|as a large language model|latest message from owner|conversation so far|return only a json|"
         r"knowledge \(retrieved|catalogue:|\"(?:facts|action|add_needs|remove_needs|about_needs|term_months)\"\s*:|api[_ ]?key|"
         r"\bopenai\b|\bgemini\b|\bgroq\b|\bllama\b|\bgpt\b|\bclaude\b|\banthropic\b")
_LINK = r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|xyz|info|biz|co\.in)\b|\S+@\S+\.\w+"
_ID = (r"(?<![A-Z0-9])\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Z0-9])|(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)|"
       r"(?<![A-Z])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])|(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)")
MAX_REPLY = 700


def _allowed_amounts(rec: dict | None) -> set[int]:
    ok: set[int] = set()
    for p in products().values():  # every price the app itself can show: the range, the setup fee, each contract length
        ok |= {p.price_min, p.price_max, p.setup_fee} | {unit_price(p, term) for term in (1, 12, 24, 36)}
    if rec:
        q = rec["quote"]
        ok |= {q["monthly"], q["gst"], q["monthly_with_gst"], q["setup"]}
        for l in q["lines"] + rec.get("suggested", []):
            ok |= {l.get("monthly", 0), l.get("unit_price", 0), l.get("setup", 0)}
        if rec.get("term_compare"):
            ok.add(rec["term_compare"]["monthly"])
    return ok


def _allowed_percents() -> set[str]:
    ok = {"18"}  # GST
    for p in products().values():  # service levels the catalogue itself states, such as 99.5%
        ok |= set(re.findall(r"(\d+(?:\.\d+)?)\s*%", p.description))
    return ok


def _sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?।])\s+|\n+", text) if x.strip()]


def _unnegated(pattern: str, text: str) -> bool:
    """True if the pattern appears in a sentence that doesn't refuse it ("I can't offer a discount" is fine)."""
    return any(re.search(pattern, x, re.I) and not re.search(_NEG, x, re.I) for x in _sentences(text))


def reply_problem(reply: str, rec: dict | None = None) -> str | None:
    """Why a model-written reply may not be shown, or None if it may."""
    if not reply or not reply.strip():
        return None
    text = reply.translate(_DIGITS)
    low = text.lower()
    if len(text) > MAX_REPLY:
        return "too long"
    if re.search(_LEAK, low):
        return "talks about its own instructions or the model behind it"
    if re.search(_LINK, low):
        return "carries a link or an email address"
    if re.search(_ID, text):
        return "carries an identifier or a phone number"
    allowed = _allowed_amounts(rec)
    if re.search(rf"{_MONEY_BEFORE}\s*{_NUM}\s*(?:k|lakh|lac|crore|cr)\b", low):
        return "quotes a rounded amount"
    pairs = re.findall(rf"{_MONEY_BEFORE}\s*({_NUM})(?:\s*(?:-|–|‑|—|to)\s*(?:₹|rs\.?\s*)?({_NUM}))?", low)
    amounts = [a for pair in pairs for a in pair if a]
    amounts += re.findall(rf"({_NUM})\s*{_MONEY_AFTER}", low)
    for a in amounts:
        n = a.replace(",", "")
        if "." in n and not n.endswith(".00") or int(float(n)) not in allowed:
            return f"quotes ₹{a}, which is not in the catalogue or the quote"
    ok_pct = _allowed_percents()
    for pct in re.findall(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent|प्रतिशत|फीसदी|टक्के|শতাংশ|சதவீதம்|శాతం|ಶೇಕಡಾ|ശതമാനം|ટકા|ਫ਼ੀਸਦੀ)", low):
        if pct not in ok_pct:
            return f"quotes {pct}%, which the catalogue does not state"
    if _unnegated(_OFFER, low):
        return "offers a discount, a waiver or something free"
    if _unnegated(_PLEDGE, low) or re.search(_VOW, low):
        return "makes a promise the catalogue does not make"
    if any(re.search(_RIVALS, x, re.I) and re.search(_SLUR, x, re.I) for x in _sentences(low)):
        return "runs down a competitor"
    return None


def reply_ok(reply: str, rec: dict | None = None) -> bool:
    return reply_problem(reply, rec) is None
