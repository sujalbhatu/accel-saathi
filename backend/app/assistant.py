"""Understands anything the owner types, at any step of the advisor.

With an LLM key, one call per turn reads the message together with the conversation, the profile and
the current bundle, and returns JSON: facts to record, an action (cheaper, add, remove, term, restart,
proceed, track, callback) and a short answer to any question. The advisor then applies the action
through the rules engine, so products and prices always come from the catalogue. A price guard drops
any answer that quotes a rupee amount that is not in the catalogue or the current quote.

Without a key (or when the LLM is slow or down), keyword rules in English, Hindi, Marathi and Tamil
cover the same actions and the common questions.

A question is never an order. "Can I skip CCTV?", "do I need backup?" or "what's the difference between 12 and 24
months?" are answered with what changes and what it costs, and the change is offered as a button; only a clear
request ("remove CCTV", "24 months") changes the bundle, and every change can be undone.
"""
import json
import logging
import re

from . import knowledge, llm, pains
from .data import business_types, products
from .extract import _NEED_KEYWORDS
from .i18n import LANGS, need_label, t
from .recommender import _NEED_OF as _PID_OF_NEED, CONNECTIVITY, NEEDS

log = logging.getLogger("assistant")

ACTIONS = ("none", "cheaper", "add", "remove", "term", "restart", "proceed", "track", "callback", "undo", "keep",
           "option", "site_plan")
# Questions the app answers itself with exact numbers from the rules engine (no AI needed for these), including the
# moments a salesperson must handle well: "too expensive", "let me think", "which one do you recommend?".
ASKS = ("ask_skip", "ask_term", "q_total", "q_down", "q_competitor", "q_privacy", "obj_price", "obj_think",
        "obj_someone", "q_recommend", "q_unsure", "q_sites")
_LLM_QUESTION = {"skip": "ask_skip", "term": "ask_term", "total": "q_total", "downtime": "q_down",
                 "competitor": "q_competitor", "safety": "q_privacy", "price": "obj_price", "think": "obj_think",
                 "recommend": "q_recommend", "unsure": "q_unsure", "outlets": "q_sites"}

# ---------- requests about the conversation itself (handled before anything else) ----------

# each language's name as owners type it: Latin, its own script, and Hindi transliterations
_LANG_NAMES = {
    # Indic names take \S* after them: case endings ("தமிழில்", "मराठीत") carry vowel signs that \w does not match
    "en": r"english\w*|angre[zj]i|इंग्लिश\S*|इंग्लीश\S*|अंग्रेज़ी\S*|अंग्रेजी\S*|ইংরেজি\S*|ઇંગ્લિશ\S*|ਅੰਗਰੇਜ਼ੀ\S*|ஆங்கில\S*|"
          r"ఇంగ్లీష్\S*|ಇಂಗ್ಲಿಷ್\S*|ഇംഗ്ലീഷ്\S*",
    "hi": r"hindi|हिंदी\S*|हिन्दी\S*|हिंदि\S*",
    "mr": r"marathi|मराठी\S*",
    "kn": r"kannada|ಕನ್ನಡ\S*",
    "gu": r"gujarati|ગુજરાતી\S*",
    "te": r"telugu|తెలుగు\S*",
    "ta": r"tamil|தமிழ\S*",
    "bn": r"bengali|bangla|বাংলা\S*",
    "pa": r"punjabi|panjabi|ਪੰਜਾਬੀ\S*",
    "ml": r"malayalam|മലയാള\S*",
}
_LANG_RE = {code: re.compile(rf"(?<!\w)(?:{pat})(?!\w)", re.I) for code, pat in _LANG_NAMES.items()}
# verbs that make a language name a request: talk, speak, reply, switch... in the scripts owners use
_LANG_VERB = re.compile(
    r"(?<!\w)(?:talk\w*|speak|speak\s*in|reply|respond|answer|continue|switch\w*|change|chat|write|type|language|"
    r"baat|bat|bolo|bol|boliye|bolna|karo|karna|kar\s*sakt\w*|chahta|chahti|chahiye|bhasha|samjh\w*|likh\w*|"
    r"बात|बोल\w*|भाषा|करना|करो|करें|चाहता|चाहती|चाहिए|टॉक|स्पीक|लिखो|"
    r"பேச\w*|మాట్లాడ\w*|ಮಾತನಾಡ\w*|ಮಾತಾಡ\w*|സംസാര\w*|কথা|বলুন|વાત|બોલ\w*|ਗੱਲ|ਬੋਲ\w*)(?!\w)", re.I)
# "English coaching centre", "Hindi books shop": a business, not a request
_LANG_BUSINESS = re.compile(r"\b(?:class\w*|course\w*|coaching|institute|academy|school|tuition|centre|center|shop|"
                            r"store|books?|newspaper|teacher|medium)\b", re.I)


def language_request(text: str) -> str | None:
    """The language code when the owner asks to change language ("talk in English", "Hindi mai baat karo"), else None."""
    t_ = (text or "").strip()
    if not t_ or len(t_.split()) > 20 or _LANG_BUSINESS.search(t_):
        return None
    named = [code for code, rx in _LANG_RE.items() if rx.search(t_)]
    if len(named) != 1:
        return None
    if re.search(r"(?<!\w)(?:customers?|staff|people|employees|workers?|they|log|grahak|ग्राहक|लोग)\s+(?:\S+\s+){0,2}"
                 r"(?:speak\w*|talk\w*|bol\w*|बोल\S*|understand\w*|samajh\w*)", t_, re.I):
        return None  # "my customers speak Hindi" describes the shop; it doesn't ask us to switch
    rest = _LANG_RE[named[0]].sub(" ", t_)
    rest = re.sub(r"(?<!\w)(?:in|mein|mai|me|mei|में|मे|please|pls|plz|only|sirf|ok(?:ay)?|now|ab|अब)(?!\w)|[^\w\s]", " ", rest,
                  flags=re.I)
    if not rest.strip() or _LANG_VERB.search(t_):
        return named[0] if named[0] in LANGS else None
    return None


# "What?", "I don't understand", "samjha nahi": the owner is lost, not answering
_CONFUSED = re.compile(
    r"^\W*(?:what+\W*|wha+t\s+(?:is|does)\s+(?:this|that|it)(?:\s+mean)?|huh|kya+|क्या|matlab|meaning|explain|"
    r"i\s+(?:do\s*n[o']?t|did\s*n[o']?t)\s+(?:understand|get\s+(?:it|this|that))|not\s+clear|confus\w*|"
    r"(?:mujhe\s+)?(?:samjha|samajh|samjh)\w*\s+(?:nahi|nahin|na)\w*|(?:nahi|nahin)\s+samjh\w*|"
    r"समझ\s*नहीं|समझा\s*नहीं|मतलब)"
    r"(?:\s+(?:aaya|aya|hua|hai|is|this|that|it|mean|bhai|ji|sir|please|आया|आ\s*रहा|हुआ|है|जी|भाई))*\W*$", re.I)


def confused(text: str) -> bool:
    return bool(_CONFUSED.match(text or ""))


# "I want all of them", "sab chahiye", "select everything": every offered service
_ALL = re.compile(r"(?<!\w)(?:all|everything|every\s+one|sab|sabhi|saare|sare|sab\s*kuch|सब|सभी|सारे|सबकुछ)(?!\w)", re.I)
_NOT_ALL = re.compile(r"(?<!\w)(?:not|don'?t|dont|no|nahi|nahin|nhi|na|नहीं|except|but|without|remove|only)(?!\w)", re.I)


def wants_all(text: str) -> bool:
    t_ = text or ""
    return len(t_.split()) <= 8 and bool(_ALL.search(t_)) and not _NOT_ALL.search(t_) and "?" not in t_


# words that make a reply about the conversation, not a business type or a city
_META = re.compile(
    r"(?<!\w)(?:talk\w*|speak\w*|language|english\w*|hindi|baat|bol(?:o|na|iye|te|ta)?|karna|karo|kar\s*sakt\w*|chahta|chahti|"
    r"chahiye|can\s+you|could\s+you|please|what|why|how|who|kya|kaise|kyun|help|understand|samjh\w*|repeat|sorry|"
    r"hello|hi|hey|thanks?|thank\s+you|बात|बोल\w*|भाषा|करना|चाहता|चाहती|क्या|कैसे|टॉक|इंग्लिश|हिंदी|समझ\w*)(?!\w)", re.I)


def is_meta(text: str) -> bool:
    """True when a reply talks about the chat (language, a question, a greeting) instead of answering it."""
    return "?" in (text or "") or bool(_META.search(text or "")) or bool(language_request(text))


_FAQ = """THE JOURNEY (always true): advisor -> quote (one monthly price before 18% GST, 12 or 24 months, add-ons can
be switched) -> consent -> Smart KYC (DigiLocker / Aadhaar OTP or photos) -> e-sign -> order -> tracker with WhatsApp
updates and self-booked installation slot. No office visit, no paper forms. A local partner can call back."""


def _catalogue_text(focus: set | None = None) -> str:
    rows = []
    for p in products().values():
        if focus is not None and p.id not in focus:
            rows.append(f"[product#{p.id}] {p.name}: {p.description}. Rs {p.price_min}-{p.price_max}/month {p.unit}")
            continue
        rule = []
        if p.tiers == frozenset({1}):
            rule.append("tier-1 cities only")
        if p.min_employees > 1:
            rule.append(f"{p.min_employees}+ staff")
        if p.min_sites > 1:
            rule.append(f"{p.min_sites}+ sites")
        if p.requires_gstin:
            rule.append("needs active GSTIN")
        if p.requires_one_of:
            rule.append("needs an internet line in the bundle")
        rows.append(f"[product#{p.id}] {p.name} [{p.category}]: {p.description}. Rs {p.price_min}-{p.price_max}/month {p.unit}, "
                    f"setup Rs {p.setup_fee}, min {p.min_contract} months, ~{p.install_days} days to install"
                    + (f"; {', '.join(rule)}" if rule else ""))
    return "\n".join(rows)


_SYSTEM = """You are the Accel Business advisor inside a mobile app that sells telecom bundles (internet, mobile, CCTV,
POS billing, WhatsApp, email, security and more) to Indian small businesses. Accel is a fictional operator.

Read the owner's LATEST message in context and return ONLY a JSON object with these keys:
"facts": object with any of business_type (closest of: {types}), employees (int), sites (int), city (English name),
  has_gstin (bool), gstin (string), current_spend (int, Rs/month), budget (int, Rs/month), fibre_available (bool),
  needs (list from: {needs}), counts (object: mobile_lines, cameras, users, counters, vehicles, machines as ints).
  Only facts stated in the latest message. Never guess numbers.
"action": one of none | cheaper | add | remove | term | restart | proceed | track | callback | undo
  cheaper = asks for a lower price or a cheaper option, or gives a budget below the current price. If the owner only
  says it is expensive or too much (a complaint, not a request), use action none and question "price".
  add / remove = wants a service added or taken out (put them in add_needs / remove_needs; use "mobile" for mobile lines).
  term = wants 12 or 24 months. restart = wants to start over. proceed = happy and wants to buy or continue.
  track = asks about an order already placed. callback = wants a human to call. undo = wants the previous bundle back.
  Use none when they only answer a question or ask something. A question like "do you have X?" or "what is X?"
  is NOT a request to add X: use none, answer it, and say they can add it; the app shows an Add button.
  A question about a change is NOT the change: "can I skip X?", "do I need X?", "is X necessary?", "what if I
  don't take X?" -> action none, question "skip". "What's the difference between 12 and 24 months?", "which term
  is better?", "is there a lock-in?" -> action none, question "term". Only a clear request changes the bundle.
"question": "" or one of skip | term | total | safety | downtime | competitor | price | think | recommend | unsure | outlets
  skip = asks whether they need or can drop a service; term = asks about 12 vs 24 months or the commitment;
  total = asks what they will pay in all, the first bill, or the price with GST; safety = asks whether their data,
  files or records are safe; downtime = asks what happens if the internet goes down; competitor = compares with
  another company's plan or price; price = says it is expensive without asking for a change; think = wants to think,
  come back later or ask someone first; recommend = asks which option you recommend or what they should take;
  unsure = says they don't know what they need; outlets = asks whether outlets or branches can have different setups.
  When "question" is set, leave "reply" empty: the app answers with exact numbers.
"about_needs": list of the services the question is about (same names as needs; "mobile", "internet" allowed).
"add_needs": list, "remove_needs": list, "term_months": 12, 24 or null, "budget": int or null,
"reply": your answer to any question in the message, 1-3 short sentences, plain text, no markdown, in the same
  language and script the owner used in the latest message (Hinglish stays Hinglish); if unclear, in {language}.
  Use ONLY the catalogue, the facts below and the current bundle. Never invent prices, discounts, offers, speeds or
  policies, and never promise anything not listed. If you don't know, say a specialist will confirm and offer a call.
  Never claim that a product was added, removed or changed, and never quote the new total; the app does that.
  Leave reply empty ("") when the message only gives information or only asks for a change.
  Never mention internal product codes such as P22; use product names.
  Do not ask the owner the next onboarding question; the app asks it.
  If the message is unrelated to the business or telecom, reply politely in one sentence and steer back.
"sources": ids in square brackets of the KNOWLEDGE or CATALOGUE entries your reply relies on (empty if no reply).
  Answer only from those entries and the context. If they don't cover the question, say so plainly and offer a
  call from a local partner.

{faq}

KNOWLEDGE (retrieved for this message):
{knowledge}

CATALOGUE:
{catalogue}"""


def _context(stage: str, pending: str | None, profile: dict, rec: dict | None) -> dict:
    ctx = {"stage": {"chat": "collecting business details", "needs": "owner is ticking needs",
                     "done": "bundle recommended"}.get(stage, stage),
           "question_waiting_for_answer": pending, "profile": profile}
    if rec:
        q = rec["quote"]
        ctx["current_bundle"] = {
            "lines": [{"product": l["name"], "qty": l["qty"], "monthly_rs": l["monthly"], "why": l.get("reason_text", "")}
                      for l in q["lines"]],
            "monthly_rs_before_gst": q["monthly"], "gst_rs": q["gst"], "setup_rs": q["setup"],
            "term_months": q["term_months"], "live_in_days": q["activation_days"],
            "other_term": rec.get("term_compare"),
            "not_possible": [{"product": b.get("name"), "why": b.get("why_text")} for b in rec.get("blocked", [])],
        }
    return ctx


_HINGLISH = r"\b(?:mujhe|mera|meri|hamara|hai|hain|kya|kaise|kitna|kitne|kaun|chahiye|karo|kar do|nahi|nahin|bhi|aur|lagenge|milega|sakta|sakte|batao|bataiye)\b"


_ENGLISH = r"\b(?:i|my|we|our|you|do|does|is|are|have|has|the|what|how|need|want|can|please|with|for|much|any)\b"


_SCRIPTS = [("ta", "\u0b80-\u0bff"), ("kn", "\u0c80-\u0cff"), ("te", "\u0c00-\u0c7f"), ("ml", "\u0d00-\u0d7f"),
            ("gu", "\u0a80-\u0aff"), ("pa", "\u0a00-\u0a7f"), ("bn", "\u0980-\u09ff")]


def turn_lang(text: str, lang: str) -> str:
    """The language to answer this message in: the owner's own, even if the app is set to another."""
    for code, block in _SCRIPTS:
        if re.search(f"[{block}]", text):
            return code if code in LANGS else lang
    if re.search(r"[\u0900-\u097f]", text):
        return lang if lang in ("hi", "mr") else "hi"
    if lang == "en" and len(re.findall(_HINGLISH, text.lower())) >= 2:
        return "hi"
    if lang != "en" and len(re.findall(_ENGLISH, text.lower())) >= 2 and not re.search(_HINGLISH, text.lower()):
        return "en"  # a full sentence in English: answer in English, even if the app is set to another language
    return lang


def worth_asking_llm(text: str, stage: str, pending: str | None, rules: dict, facts: dict) -> bool:
    """Save the LLM (and the free-tier quota) for messages the rules can't fully handle."""
    words = len(text.split())
    if rules.get("intent") in ASKS and words <= 14:
        return False  # a question the app answers itself, with exact numbers
    if rules["action"] in ("option", "keep"):
        return False
    if words <= 8 and re.search(r"what(?:'s| is| are| does)|meaning|matlab|kya (?:hai|hota)|क्या (?:है|होता)|मतलब", text.lower()) \
            and describe_products(text, "en"):
        return False  # "what is static IP?": the product card or glossary answers exactly, with an Add button
    if rules["action"] != "none" and words <= 6 and not re.search(_R["question"], text.lower()):
        return False  # "make it cheaper", "24 months", "undo", "ok"
    if re.fullmatch(r"\s*[\d,+]+\s*|\s*\S+\s*", text) and stage != "done":
        return False  # a bare number or one-word answer to the pending question
    answered = pending in facts or (pending == "gstin" and "has_gstin" in facts) or \
        (pending == "current" and "current_internet" in facts)
    if stage == "needs" and "current_internet" in facts and words <= 5 and "?" not in text:
        return False  # "phone hotspot" told late, on the checklist: the rules have it
    if stage == "chat" and pending and answered and rules["intent"] is None and "?" not in text:
        return False  # the rules already read the answer to the question we asked
    return True


def llm_understand(text: str, lang: str, stage: str, pending: str | None, profile: dict, rec: dict | None,
                   history: list[dict], intent: str | None = None, session: dict | None = None) -> dict | None:
    if not llm.available() or not llm.session_allowed(session):
        return None
    found = knowledge.search(knowledge.expand(text, intent, needs_in(text)), k=4)
    kb = "\n".join(f"[{c['id']}] {c['title']}: {c['text']}" for c in found) or "(nothing matched)"
    focus = {c["id"].split("#")[1] for c in found if c["id"].startswith("product#")}
    if rec:
        focus |= {l["id"] for l in rec["quote"]["lines"] + rec.get("suggested", [])}
    focus |= {pid for pid, need in _PID_OF_NEED.items() if need in needs_in(text)}
    system = _SYSTEM.format(types=", ".join(sorted(business_types())), needs=", ".join(NEEDS),
                            language=LANGS.get(lang, "English"), faq=_FAQ, knowledge=kb, catalogue=_catalogue_text(focus))
    convo = "\n".join(f"{m['role']}: {m['text'][:300]}" for m in history[-8:])
    user = (f"CONTEXT: {json.dumps(_context(stage, pending, profile, rec), ensure_ascii=False)}\n"
            f"CONVERSATION SO FAR:\n{convo}\n\nLATEST MESSAGE FROM OWNER: {text}")
    data = llm.chat_json([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=1500,
                         session=session, lang=lang)
    if not data:
        return None
    out = {"facts": data.get("facts") if isinstance(data.get("facts"), dict) else {},
           "action": data.get("action") if data.get("action") in ACTIONS else "none",
           "add_needs": [n for n in data.get("add_needs") or [] if n in NEEDS],
           "remove_needs": [n for n in data.get("remove_needs") or [] if n in NEEDS or n in ("mobile", "internet")],
           "term_months": data.get("term_months") if data.get("term_months") in (12, 24) else None,
           "budget": int(data["budget"]) if isinstance(data.get("budget"), (int, float)) and data["budget"] > 0 else None,
           "reply": (data.get("reply") or "").strip() if isinstance(data.get("reply"), str) else "",
           "question": _LLM_QUESTION.get(data.get("question") or ""),
           "about": [n for n in data.get("about_needs") or [] if n in NEEDS or n in ("mobile", "internet")],
           "sources": [c for c in data.get("sources") or [] if isinstance(c, str) and knowledge.by_id(c.strip("[]"))]}
    out["sources"] = [c.strip("[]") for c in out["sources"]][:3] if out["reply"] else []
    out["reply"] = re.sub(r"\s*\(?\bP\d{2}\b\)?", "", out["reply"]).strip()
    if out["reply"] and not price_guard(out["reply"], rec):
        log.warning("dropped an LLM answer that quoted a price not in the catalogue or quote")
        out["reply"], out["sources"] = "", []
    return out


# ---------- price guard ----------

def _allowed_amounts(rec: dict | None) -> set[int]:
    ok: set[int] = set()
    for p in products().values():
        ok |= {p.price_min, p.price_max, p.setup_fee}
    if rec:
        q = rec["quote"]
        ok |= {q["monthly"], q["gst"], q["monthly_with_gst"], q["setup"]}
        for l in q["lines"] + rec.get("suggested", []):
            ok |= {l.get("monthly", 0), l.get("unit_price", 0), l.get("setup", 0)}
        if rec.get("term_compare"):
            ok.add(rec["term_compare"]["monthly"])
    return ok


def price_guard(reply: str, rec: dict | None) -> bool:
    """True if every rupee amount in the reply exists in the catalogue or the current quote."""
    pairs = re.findall(r"(?:₹|\brs\.?|\binr|rupees?)\s*([\d,]+)(?:\s*(?:-|–|‑|—|to)\s*(?:₹|rs\.?\s*)?([\d,]+))?",
                       reply, flags=re.I)  # a range ("Rs 299-499") has its second amount checked too
    amounts = [a for pair in pairs for a in pair if a.replace(",", "")]
    allowed = _allowed_amounts(rec)
    return all(int(a.replace(",", "")) in allowed for a in amounts)


# ---------- rules fallback ----------

_R = {
    "restart": r"start (?:over|again)|restart|new chat|शुरू से|फिर से शुरू|पुन्हा सुरू|மீண்டும் தொடங்கு",
    "undo": r"^\s*(?:undo|go back to (?:the )?(?:previous|old|last)|पहले वाला|पिछला वाला|आधीचा)",
    "callback": r"call me|call back|callback|talk to (?:a |an )?(?:person|human|agent|someone|executive)|human|"
                r"बात करा|बात कर|कॉल कर|फोन कर|फ़ोन कर|कॉल करा|அழை",
    "track": r"\btrack\b|order status|where is my order|मेरा ऑर्डर|ऑर्डर कहाँ|ऑर्डर कहां|माझी ऑर्डर",
    "cheaper": r"cheap|less expensive|lower (?:the )?(?:price|cost|bill)|reduce|too (?:much|high|expensive|costly)|"
               r"expensive|costly|afford|discount|budget|sasta|sasti|saste|mehenga|mehnga|kam (?:kar|karo|price|daam|kijiye)|"
               r"सस्ता|सस्ती|सस्ते|महंगा|महँगा|ज़्यादा है|ज्यादा है|कम कर|कम करो|कम कीजिए|महाग|स्वस्त|कमी कर|"
               r"குறை|மலிவ|விலை அதிக",
    "remove": r"\bremove\b|\bdrop\b|\bdelete\b|\bwithout\b|don'?t (?:need|want)|do not (?:need|want)|no need|not needed|"
              r"\bskip\b|hata|nahi chahiye|nahin chahiye|नहीं चाहिए|नही चाहिए|हटा|नको|काढ|வேண்டாம்|நீக்கு|"
              r"(?:zaruri|zaroori|jaruri|jaroori) nahi|ज़रूरी नहीं|जरूरी नहीं|गरज नाही|தேவையில்லை",
    "add": r"\badd\b|\balso\b|\binclude\b|\bplus\b|\bneed\b|\bwant\b|chahiye|चाहिए|जोड़|जोड|हवे|हवा|पाहिजे|சேர்|வேண்டும்",
    "proceed": r"^\s*(?:ok(?:ay)?|yes|yeah|yup|sure|fine|good|great|perfect|haan|han|ha|theek hai|thik hai|done|proceed|"
               r"continue|buy|book|order|checkout|go ahead|let'?s go|chalo|हाँ|हां|ठीक है|चलो|बढ़िया|होय|हो|ठीक आहे|சரி|ஆம்)"
               r"(?=$|[\s!.,?])",
    "greet": r"^\s*(?:hi+|hello|hey|namaste|namaskar|नमस्ते|नमस्कार|வணக்கம்)(?=$|[\s!.,?])",
    "q_docs": r"document|kyc|paper|dastavez|kagaz|कागज|कागज़|दस्तावेज|कागदपत्र|ஆவண|কাগজ|ডকুমেন্ট|દસ્તાવેજ|ದಾಖಲೆ|രേഖ|ਦਸਤਾਵੇਜ਼|ਦਸਤਾਵੇਜ|పత్ర",
    "q_time": r"how long|how many days|how soon|when (?:will|can|do)|kitne din|kab tak|kab se|कितने दिन|कब तक|कब से|"
              r"किती दिवस|केव्हा|எத்தனை நாள்|எப்போது|কত দিন|કેટલા દિવસ|ಎಷ್ಟು ದಿನ|എത്ര ദിവസ|ਕਿੰਨੇ ਦਿਨ|ఎన్ని రోజు",
    "q_price": r"price|cost|how much|kitna|kitne ka|कितना|कितने का|कीमत|दाम|किंमत|किती|விலை|எவ்வளவு",
    "q_privacy": r"\bsafe\b|\bsafety\b|privacy|private\b|my data|our data|data (?:safe|secure|protect)|"
                 r"is (?:it|my|our|this) (?:\w+ )?secure|(?:patient|client|customer|business)(?:'s|s)? (?:data|records|files|details)|"
                 r"\bhack|ransomware|\bleak|dpdp|सुरक्षित|प्राइवेसी|डेटा सुरक्षा|தரவு பாதுகாப்பு|பாதுகாப்பான",
    "q_gst": r"(?:no|without|don'?t have|nahi|नहीं).{0,12}gst|gst.{0,12}(?:nahi|नहीं|not|why|kyu|क्यों|ज़रूरी|zaruri|needed|required)",
    "question": r"\?|\bwhat\b|\bwhy\b|\bhow\b|\bwhich\b|\bcan i\b|\bdo you\b|\bis it\b|\bkya\b|\bkyu|\bkaise\b|\bkaun|"
                r"\bshould\b|\bdo i\b|\bdo we\b|क्या|क्यों|कैसे|कौन|काय|कसे|என்ன|ஏன்|எப்படி",
    # "can I skip X?", "do I need X?", "is X necessary?": a question about removing, never the removal itself
    "ask_skip": r"\b(?:can|could|may|should|shall|must) (?:i|we) (?:skip|remove|drop|leave out|do without|not take|not have|"
                r"avoid|go without|cancel)\b|\bdo (?:i|we) (?:really |actually |even )?(?:need|require|have to (?:take|keep|buy))\b|"
                r"\b(?:is|are) (?:it|they|this|these|that|the [\w\-/ ]{2,30}?|[\w\-/]{2,20}(?: [\w\-/]{2,20})?) (?:really |actually |even )?"
                r"(?:necessary|needed|required|compulsory|mandatory|a must|important|essential|worth it)\b|"
                r"\bwhat (?:happens )?if (?:i|we) (?:don'?t|do not|skip|remove|drop|leave)\b|\bwithout (?:it|this|them)\b.*\?|"
                r"\b(?:need|needed|necessary|required)\s*\?",
    "ask_skip_soft": r"\b(?:zaruri|zaroori|jaruri|jaroori|avashyak)\b|\bke bina\b|hata (?:sakte|sakta|sakti|skte)|"
                     r"chhod (?:sakte|sakta|skte)|ज़रूरी|जरूरी|के बिना|हटा सकत|छोड़ सकत|आवश्यक|गरज आहे|शिवाय|काढू शकत|"
                     r"தேவையா|இல்லாமல்|அவசியமா",
    "ask_term": r"\b(?:difference|differ|compare|comparison|better|benefit|advantage|which (?:is|one|term|plan|option)|"
                r"lock-?in|commit(?:ment)?|cancel|leave early|exit)\b|farak|fark|फ़र्क|फर्क|अंतर|फरक|फायदा|फ़ायदा|"
                r"வித்தியாசம்|நன்மை|(?:12|twelve).{0,30}(?:24|twenty)|(?:24|twenty).{0,30}(?:12|twelve)",
    "term_words": r"contract|\bterm\b|lock-?in|commitment|कॉन्ट्रैक्ट|अनुबंध|ஒப்பந்த|\b12\b.{0,30}\b24\b|\b24\b.{0,30}\b12\b",
    "imperative": r"\b(?:switch|change|make|move|go|put|set|convert|shift)\b.{0,25}(?:12|24|one|two|1|2)\b|"
                  r"kar do|kardo|karo\b|kijiye|chahiye|please|pls|\bplz\b|कर दो|करो|कीजिए|चाहिए|करा\b|हवे",
    "q_total": r"first (?:month|bill|payment|invoice)|total (?:cost|amount|price|bill|payable|monthly)|in total|altogether|"
               r"all[- ]inclusive|all-in|(?:with|including|incl\.?|after|plus) gst|gst (?:included|ke saath|milake|mila ke)|"
               r"grand total|upfront|pay (?:now|first|today)|how much (?:will|do|would) (?:i|we) (?:pay|have to pay)|"
               r"pehle mahine|pehla bill|kul kitna|total kitna|sab mila ?ke|सब मिलाकर|कुल|पहले महीने|पहला बिल|"
               r"जीएसटी के साथ|पहिल्या महिन्य|एकूण|மொத்த|முதல் மாத",
    "q_down": r"(?:internet|\bnet\b|line|connection|wi-?fi|broadband|fib(?:re|er))\b.{0,25}(?:goes? down|go down|went down|is down|"
              r"stops?|fails?|breaks?|cuts?|outage|not working|band ho|chala ja|nahi chal|बंद)|downtime|outage|\buptime\b|"
              r"\bsla\b|नेट बंद|इंटरनेट बंद|इंटरनेट चला|नेट चला|इंटरनेट नहीं चल|இணையம் நின்ற|இணையம் இல்லை",
    "q_competitor": r"\b(?:jio|airtel|bsnl|hathway|excitel|tata play|act fibernet|act fiber|vodafone|vi (?:fiber|fibre|postpaid))\b|"
                    r"local (?:isp|cable|wala|operator|provider)|cable ?wala|competitor|other (?:company|companies|provider|"
                    r"providers|operator|operators)|another (?:company|provider|operator)|elsewhere|dusri company|"
                    r"doosri company|दूसरी कंपनी|दुसरी कंपनी|வேறு நிறுவன",
    "opt_basic": r"^\s*(?:basic|the basic(?: one| option| plan)?|basic (?:one|option|plan|please)|बेसिक|बेसिक वाला)\s*[.!]?\s*$",
    "opt_complete": r"^\s*(?:complete|the complete(?: one| option| plan)?|complete (?:one|option|plan|please)|everything|"
                    r"full (?:package|bundle|option)|कंप्लीट|सब कुछ|पूरा पैकेज)\s*[.!]?\s*$",
    "opt_recommended": r"^\s*(?:recommended|the recommended(?: one| option| plan)?|recommended (?:one|option|plan|please))\s*[.!]?\s*$",
    "keep": r"^\s*(?:keep(?: it| them| that| this)?|no,? thanks?|no thank you|leave it|rehne do|rahne do|rehene do|"
            r"रहने दो|असू द्या|இருக்கட்டும்)\s*[.!]?\s*$",
    "glossary": r"\bmbps\b|\bsla\b|\bdlt\b|\bivr\b|\bsoc\b|input tax credit|\bitc\b",
    # a complaint about the price, not a request to change it: answered with choices, nothing changes until she picks
    "obj_price": r"too (?:much|high|expensive|costly|pricey)|(?:is|it'?s|that'?s|very|quite|so|bit|bahut|bohot|kaafi) "
                 r"(?:expensive|costly|pricey|high)|^\W*(?:expensive|costly|too much)\W*$|can'?t afford|cannot afford|"
                 r"out of (?:my |our )?budget|mehe?nga|mahe?nga|महंगा|महँगा|बहुत ज़्यादा|बहुत ज्यादा|ज़्यादा है|ज्यादा है|"
                 r"(?:zyada|jyada|jada) hai|महाग|விலை அதிக|அதிக விலை",
    "price_ask": r"\b(?:make|reduce|lower|cut|bring)\b|cheaper|cheapest|sasta kar|sasti kar|kam kar|kam karo|सस्ता कर|"
                 r"सस्ता दो|कम कर|कम करो|कम कीजिए|discount|कमी कर|स्वस्त कर|குறை",
    "obj_think": r"(?:let me|i'?ll|i will|i need to|i want to|i have to|will|need to) think|think (?:about it|it over)|"
                 r"come back later|get back (?:to you )?later|call (?:you )?(?:back )?later|maybe later|not (?:right )?now|decide later|"
                 r"sochta|sochti|soch(?:ke| kar| ke)|सोचता|सोचती|सोच कर|सोचकर|सोच के|बाद में (?:बताता|बताती|देखते|आता|आती)|"
                 r"baad mein (?:batata|batati|dekhte|aata|aati)|विचार करून|யோசிக்க",
    "obj_someone": r"(?:ask|discuss (?:it )?with|check with|talk to|consult) (?:my |our )?(?:partner|wife|husband|brother|"
                   r"father|dad|son|daughter|family|accountant|ca\b|boss|owner|team)|(?:partner|wife|husband|papa|bhai|"
                   r"family|ghar)(?: se| mein| me)? (?:puchh?|pooch|baat)|घर (?:पर|में|वालों से) (?:पूछ|बात)|"
                   r"(?:पार्टनर|पत्नी|पति|भाई|पापा|परिवार) से (?:पूछ|बात)|पूछ (?:कर|के) (?:बताता|बताती|बताऊंगा)",
    "q_recommend": r"which (?:one|option|plan|level|bundle|package)s? (?:do you|would you|should i|should we|is (?:the )?best|"
                   r"is better|do i|to (?:take|choose|pick))|what (?:do|would) you (?:recommend|suggest)|which (?:do|would) "
                   r"you (?:recommend|suggest)|your (?:recommendation|suggestion|advice)|best (?:option|plan|one) for (?:me|us)|"
                   r"what should (?:i|we) (?:take|choose|buy|pick|go for)|kaun ?sa (?:lu|loon|lun|lena|le|best)|"
                   r"कौन ?सा (?:लूँ|लूं|लें|लेना|बेस्ट|सही)|आप क्या (?:सुझाव|सलाह|कहते)|क्या लेना चाहिए|kya lena chahiye",
    "q_unsure": r"(?:don'?t|do not|dont) (?:really )?know what (?:i|we) (?:need|want|should)|not sure what (?:i|we) "
                r"(?:need|want)|no idea what (?:i|we) need|you (?:decide|tell me what|suggest what)|i'?m confused|"
                r"pata nahi kya chahiye|kya chahiye pata nahi|पता नहीं क्या चाहिए|क्या चाहिए पता नहीं|समझ नहीं आ रहा|"
                r"आप ही बताइए|आप ही बताओ|aap hi batao",
    "q_sites": r"(?:each|every|different|separate|individual) (?:outlet|branch|store|site|shop|location|centre|center|"
               r"restaurant|hotel|clinic)s?|(?:outlet|branch|store|site|shop|location)s? (?:can|could) (?:have|get) "
               r"(?:a )?different|per (?:outlet|branch|store|site|location)|हर (?:ब्रांच|दुकान|आउटलेट|शाखा)|alag[ -]alag",
    "small_sites": r"(?:\b(?:\d+|one|two|three|four|a|ek|do|teen)\s+(?:of (?:them|the \w+)\s+|(?:outlet|branch|branche|store|"
                   r"site|shop|location|restaurant|centre|center)s?\s+)?(?:is|are)\s+(?:very |quite |really |a bit |pretty )?"
                   r"(?:small|tiny))|\bsmall(?:er)? (?:outlet|branch|store|site|shop|location|centre|center|kiosk)s?\b|"
                   r"छोटी (?:दुकान|ब्रांच)|छोटा (?:आउटलेट|स्टोर)",
}
_SMALL_WORDS = {"one": 1, "a": 1, "ek": 1, "two": 2, "do": 2, "three": 3, "teen": 3, "four": 4}


def small_sites(text: str) -> int | None:
    """"One outlet is very small" -> 1, "two of them are small" -> 2; None if the message says nothing about it."""
    low = text.lower()
    m = re.search(_R["small_sites"], low)
    if not m:
        return None
    n = re.search(r"\b(\d+|one|two|three|four|a|ek|do|teen)\s+(?:of |outlet|branch|store|site|shop|location|restaurant|centre|center|is|are)", m.group(0))
    if not n:
        return 1
    return int(n.group(1)) if n.group(1).isdigit() else _SMALL_WORDS.get(n.group(1), 1)
_GLOSSARY = {"mbps": r"\bmbps\b", "sla": r"\bsla\b", "dlt": r"\bdlt\b", "ivr": r"\bivr\b", "soc": r"\bsoc\b",
             "itc": r"input tax credit|\bitc\b"}
_MOBILE = r"mobile|\bsims?\b|postpaid|phone(?:s)? for (?:staff|team)|मोबाइल|सिम|மொபைல்"
_INTERNET = r"internet|broadband|fib(?:re|er)|wifi line|इंटरनेट|ब्रॉडबैंड|இணையம்"


def _budget(text: str) -> int | None:
    low = text.lower().replace(",", "")
    m = re.search(r"(?:under|below|within|less than|upto|up to|max(?:imum)?|budget(?: is| of)?|around|about|only|"
                  r"sirf|bas|₹|rs\.?|inr)\s*₹?\s*(\d+(?:\.\d+)?)\s*(k|thousand|hazar|हज़ार|हजार)?", low)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(k|thousand|hazar|हज़ार|हजार)?\s*(?:rs|₹|rupees?|रुपये|रुपए)?\s*"
                      r"(?:tak|तक|ke andar|के अंदर|se kam|से कम|पर्यंत|per month|a month|/month|महीना|महिना)", low)
    if not m:
        return None
    n = float(m.group(1)) * (1000 if m.group(2) else 1)
    return int(n) if 100 <= n <= 500000 else None


def _term(text: str) -> int | None:
    low = text.lower()
    if re.search(r"24\s*(?:months?|mahine|mahina|महीने|महिने|மாத)|2\s*(?:years?|yrs?|saal|साल|वर्ष)|two years?|do saal|दो साल", low):
        return 24
    if re.search(r"12\s*(?:months?|mahine|mahina|महीने|महिने|மாத)|1\s*(?:year|yr|saal|साल|वर्ष)|one year|ek saal|एक साल", low):
        return 12
    return None


def needs_in(text: str) -> list[str]:
    """Services a message names, or that solve a problem it describes ("we had a theft" -> CCTV)."""
    low = text.lower()
    return sorted({k for k, pat in _NEED_KEYWORDS.items() if re.search(pat, low)} | set(pains.needs_for(pains.found(text))))


def asks_only(text: str) -> bool:
    """A question about a service ("do you have CCTV?") rather than a request to change the bundle."""
    low = text.lower()
    return bool(re.search(_R["question"], low)) and not re.search(_R["remove"], low) and not re.search(
        r"\badd\b|\binclude\b|please (?:add|put)|daal do|jod do|जोड़ दो|जोड़ें|लगा दो|सेर்", low)


def about(text: str) -> list[str]:
    """The services a message talks about: need keys, plus "mobile" and "internet"."""
    low = text.lower()
    out = needs_in(text)
    if re.search(_MOBILE, low):
        out.append("mobile")
    if re.search(_INTERNET, low) and not out:
        out.append("internet")
    return out


def rules_understand(text: str, stage: str) -> dict:
    low = text.lower().strip()
    hit = {k: bool(re.search(p, low)) for k, p in _R.items()}
    needs, things = needs_in(text), about(text)
    out = {"facts": {}, "action": "none", "add_needs": [], "remove_needs": [], "term_months": _term(text),
           "budget": _budget(text), "reply": "", "intent": None, "about": things}
    asking = hit["question"] or low.endswith("?")
    complaint = hit["obj_price"] and not hit["price_ask"] and not out["budget"]
    # The moments that decide a sale: answered with choices (and a next step), nothing changes until she picks.
    if hit["obj_someone"]:
        out["intent"] = "obj_someone"
    elif hit["obj_think"]:
        out["intent"] = "obj_think"
    elif complaint and not hit["q_competitor"]:
        out["intent"] = "obj_price"
    elif hit["q_unsure"]:
        out["intent"] = "q_unsure"
    elif stage == "done" and hit["q_recommend"]:
        out["intent"] = "q_recommend"
    if stage == "done" and (hit["small_sites"] or hit["q_sites"]) and not out["intent"]:
        n = small_sites(text)
        if n is not None and not asking:
            out["action"], out["small_sites"] = "site_plan", n
        elif hit["q_sites"] or n is not None:
            out["intent"] = "q_sites"
            out["small_sites"] = n
    if out["intent"] or out["action"] != "none":
        if hit["restart"]:
            out["action"], out["intent"] = "restart", None
        elif hit["callback"]:
            out["action"], out["intent"] = "callback", None
        return out
    # Questions about a change come first: they are answered and the change is offered as a button.
    if stage == "done" and not (hit["q_docs"] or hit["q_gst"]):
        if things and (hit["ask_skip"] or (hit["ask_skip_soft"] and asking)):
            out["intent"] = "ask_skip"
        elif (out["term_months"] or hit["term_words"]) and (hit["ask_term"] or asking) and not hit["imperative"]:
            out["intent"] = "ask_term"
    if hit["restart"]:
        out["action"] = "restart"
    elif hit["undo"] and stage == "done":
        out["action"] = "undo"
    elif hit["callback"]:
        out["action"] = "callback"
    elif hit["track"] and stage != "chat":
        out["action"] = "track"
    elif out["intent"]:
        pass
    elif stage == "done" and (hit["opt_basic"] or hit["opt_complete"] or hit["opt_recommended"]):
        out["action"] = "option"
        out["option"] = "basic" if hit["opt_basic"] else "complete" if hit["opt_complete"] else "recommended"
    elif stage == "done" and hit["keep"]:
        out["action"] = "keep"
    elif stage == "done" and hit["remove"] and things:
        out["action"] = "remove"
        out["remove_needs"] = things
    elif hit["q_competitor"] and (hit["cheaper"] or hit["q_price"] or hit["question"] or re.search(r"\d", low)):
        out["intent"] = "q_competitor"  # answer, and offer "make it cheaper" as a button
    elif (stage == "done" and hit["cheaper"]) or (out["budget"] and not hit["question"]) or \
            (hit["cheaper"] and not hit["question"] and not re.search(r"budget\s+(?:hotel|lodge|stay|rooms?)", low)):
        out["action"] = "cheaper"
    elif stage == "done" and out["term_months"]:
        out["action"] = "term"
    elif stage == "done" and needs and not hit["question"]:
        out["action"] = "add"
        out["add_needs"] = needs
    elif stage == "done" and hit["proceed"]:
        out["action"] = "proceed"
    # questions the rules can answer
    if out["action"] == "none" and not out["intent"]:
        always = ("q_docs", "q_time", "q_total", "q_down", "q_competitor")
        for intent in ("q_docs", "q_gst", "q_total", "q_down", "q_competitor", "q_time", "q_privacy", "q_price"):
            if hit[intent] and (asking or intent in always):
                out["intent"] = intent
                break
        if not out["intent"] and asking:
            out["intent"] = "question"
        if not out["intent"] and hit["greet"]:
            out["intent"] = "greet"
    return out


def glossary(text: str, lang: str) -> list[str]:
    low = text.lower()
    return [t(lang, f"gloss_{k}") for k, pat in _GLOSSARY.items() if re.search(pat, low)]


def describe_products(text: str, lang: str, rec: dict | None = None) -> list[tuple[str, str]]:
    """Rules answer to "what is X?": the plain-language card of each product the question names (at most two),
    plus any jargon it uses. Returns (message, source id) pairs."""
    from . import cards
    low = text.lower()
    hits = []
    for p in products().values():
        short = p.name.lower().split(" ")[0:2]
        if p.name.lower() in low or (len(" ".join(short)) > 5 and " ".join(short) in low):
            hits.append(p.id)
    if not hits:
        need_to_pid = {need: pid for pid, need in _PID_OF_NEED.items()}
        hits = [need_to_pid[n] for n in needs_in(text) if n in need_to_pid]
        if not hits and re.search(_MOBILE, low):
            hits = ["P07"]
    lines = {l["id"]: l for l in (rec or {}).get("quote", {}).get("lines", [])}
    if "P07" in hits and "P08" in lines:
        hits[hits.index("P07")] = "P08"
    term = (rec or {}).get("quote", {}).get("term_months", 12)
    out = [(cards.info(lang, pid, term, pid in lines), f"product#{pid}") for pid in dict.fromkeys(hits)][:2]
    return out + [(g, "") for g in glossary(text, lang)][:2]


def names(lang: str, needs: list[str]) -> str:
    return ", ".join(need_label(lang, n) for n in needs)
