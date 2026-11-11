"""Judge-style scenarios: 30 owners the advisor has never seen, typed the way people really type.

    python -m tests.run_judge_scenarios          # rules only (what the app does when the AI model is down)
    python -m tests.run_judge_scenarios --llm    # with the LLM from .env, as in a live demo
    python -m tests.run_judge_scenarios -v       # print every conversation

These are not the tidy sentences of run_advisor_scenarios. They have typos, SMS spelling, Hinglish, spoken-style
run-ons, numbers as words, facts that arrive over several turns, corrections, and every one of the 10 languages.
Each scenario states the truth about the owner (business, city, team, sites, GST, what they asked for). Every
follow-up question is answered by typing, never by tapping a button.

The expected result is not written by hand. It is worked out from the catalogue file by this suite's own rules
(city tier, minimum team, minimum sites, GSTIN, dependencies), not by the app's code, so the two can disagree:
  understood   the profile the app built matches the truth
  asked for    everything the owner asked for is ticked on the needs card
  served       each ask is in the bundle if the catalogue allows it for this owner; if not, it is left out AND
               explained, never silently dropped and never sold to someone who can't have it
  valid        every line is eligible, priced inside the published range, sums are right, GST is 18%
  sized        one internet line per site; counts the owner gave (4 cameras) are the counts on the bill
  language     the recommendation is written in the owner's script
  listened     the app never asks for something the owner had already said
"""
import argparse
import os
import re
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--llm", action="store_true")
parser.add_argument("-v", "--verbose", action="store_true")
ARGS = parser.parse_args()
if ARGS.llm:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
else:
    os.environ["LLM_API_KEY"] = os.environ["GROQ_API_KEY"] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "judge.db"))

from app import advisor  # noqa: E402
from app.data import city_tiers, products  # noqa: E402

FIBRE = ("P01", "P02", "P03")
LINES = ("P01", "P02", "P03", "P04", "P05", "P06")  # an internet line for the site
SERVES = {  # what the owner asks for -> the catalogue products that answer it (read off the catalogue, by hand)
    "payments": ("P19",), "whatsapp": ("P15",), "sms": ("P14",), "cctv": ("P23",), "email": ("P16",), "security": ("P20",),
    "backup": ("P17",), "website": ("P18",), "guest_wifi": ("P22",), "failover": ("P09",), "calls": ("P12",),
    "tollfree": ("P13",), "static_ip": ("P11",), "iot": ("P24",), "fleet": ("P25",), "central_mgmt": ("P10",),
    "firewall": ("P21",),
}
SCRIPT = {"hi": r"[ऀ-ॿ]", "mr": r"[ऀ-ॿ]", "bn": r"[ঀ-৿]", "pa": r"[਀-੿]",
          "gu": r"[઀-૿]", "ta": r"[஀-௿]", "te": r"[ఀ-౿]", "kn": r"[ಀ-೿]",
          "ml": r"[ഀ-ൿ]", "en": r"[A-Za-z]"}


def T(business, city, employees, sites, gst, asks=(), counts=None, lang="en", also=(), unsaid=()):
    """The truth about one owner. `also`: other business types that are a fair reading of what was typed.
    `employees` may be a (low, high) range when the owner gave one. `unsaid`: facts the opening message leaves out,
    which the app is right to ask for."""
    team = employees if isinstance(employees, tuple) else (employees, employees)
    return {"business": (business, *also), "city": city, "team": team, "employees": team[1], "sites": sites, "gst": gst,
            "asks": list(asks), "counts": counts or {}, "lang": lang, "unsaid": set(unsaid)}


# name, opening message, typed answers to follow-up questions (by what is being asked), the truth
S = [
    ("Typos and SMS spelling", "hi i hv a small mobile repairing shop in patna.. only me n 1 helper. no gst. need wifi n card machine",
     {}, T("Mobile repair shop", "Patna", 2, 1, False, ["payments"])),
    ("Hinglish, counts in the sentence", "bhai mera sweet shop hai surat me, 5 ladke kaam karte h, ek hi dukan, gst number hai, "
     "cctv lagwana h 4 camera aur whatsapp pe order lena h",
     {}, T("Sweet shop", "Surat", 5, 1, True, ["cctv", "whatsapp"], {"P23": 4}, lang="hi")),
    ("Spoken run-on, number as a word", "so basically we are an architecture firm we are in hyderabad around fifteen people one office "
     "yes gst registered we need good internet email for everyone and backup of our drawings",
     {}, T("Architecture studio", "Hyderabad", 15, 1, True, ["email", "backup"], {"P16": 15})),
    ("Hindi: the internet keeps dropping", "नाशिक में हमारी प्रिंटिंग प्रेस है, 12 कर्मचारी, एक ही यूनिट, जीएसटी है, इंटरनेट बार-बार बंद हो जाता है",
     {}, T("Printing press", "Nashik", 12, 1, True, ["failover"], lang="hi")),
    ("Bengali, Bengali digits", "কলকাতায় আমার একটা ডায়াগনস্টিক ল্যাব আছে, ১০ জন কর্মী, একটাই ল্যাব, জিএসটি আছে, রোগীদের রিপোর্ট এসএমএসে পাঠাতে চাই",
     {}, T("Diagnostic lab", "Kolkata", 10, 1, True, ["sms"], lang="bn")),
    ("Gujarati hardware shop", "અમદાવાદમાં મારી હાર્ડવેરની દુકાન છે, 3 માણસો, એક જ દુકાન, GST નથી, બિલિંગ મશીન જોઈએ છે",
     {}, T("Hardware store", "Ahmedabad", 3, 1, False, ["payments"], lang="gu")),
    ("Telugu clinic wants a website", "విశాఖపట్నంలో మా ఫిజియోథెరపీ క్లినిక్ ఉంది, 6 మంది సిబ్బంది, ఒకే క్లినిక్, GST లేదు, వెబ్‌సైట్ కావాలి",
     {}, T("Physiotherapy clinic", "Visakhapatnam", 6, 1, False, ["website"], lang="te")),
    ("Kannada stationery shop", "ಮೈಸೂರಿನಲ್ಲಿ ನನ್ನ ಸ್ಟೇಷನರಿ ಅಂಗಡಿ ಇದೆ, 2 ಜನ, ಒಂದೇ ಅಂಗಡಿ, GST ಇಲ್ಲ",
     {}, T("Stationery shop", "Mysuru", 2, 1, False, [], lang="kn")),
    ("Malayalam travel agency, toll-free", "കൊച്ചിയിൽ ഞങ്ങൾക്ക് ഒരു ട്രാവൽ ഏജൻസി ഉണ്ട്, 7 ജീവനക്കാർ, ഒരു ഓഫീസ്, GST ഉണ്ട്, ടോൾ ഫ്രീ നമ്പർ വേണം",
     {}, T("Travel agency", "Kochi", 7, 1, True, ["tollfree"], lang="ml")),
    ("Punjabi packaging unit, machines", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਸਾਡੀ ਪੈਕੇਜਿੰਗ ਯੂਨਿਟ ਹੈ, 30 ਕਾਮੇ, ਇੱਕ ਫੈਕਟਰੀ, GST ਹੈ, ਮਸ਼ੀਨਾਂ ਦੀ ਨਿਗਰਾਨੀ ਚਾਹੀਦੀ ਹੈ",
     {}, T("Packaging unit", "Ludhiana", 30, 1, True, ["iot"], lang="pa")),
    ("Marathi optician, guest Wi-Fi", "नागपूरमध्ये आमचे चष्म्याचे दुकान आहे, 4 कर्मचारी, एकच दुकान, GST आहे, ग्राहकांसाठी गेस्ट वायफाय हवे",
     {}, T("Optician", "Nagpur", 4, 1, True, ["guest_wifi"], lang="mr")),
    ("Tamil food factory", "கோயம்புத்தூரில் எங்கள் உணவு பதப்படுத்தும் தொழிற்சாலை உள்ளது, 45 பணியாளர்கள், ஒரு தொழிற்சாலை, GST உண்டு",
     {}, T("Food processing unit", "Coimbatore", 45, 1, True, [], lang="ta")),
    ("Facts arrive one at a time", "Hello",
     {"business_type": "we do insurance, LIC agency type", "city": "indore", "employees": "about 9 including me",
      "sites": "just the one office", "gstin": "no gst as of now"},
     T("Insurance agency", "Indore", 9, 1, False, unsaid=("business", "city", "employees", "sites", "gst"))),
    ("Gym chain, one dashboard", "gym chain, 4 branches across pune, around 35 trainers n staff, gstin yes. want one dashboard to manage "
     "all branch internet + 12 cctv cameras in total",
     {}, T("Gym chain", "Pune", 35, 4, True, ["central_mgmt", "cctv"], {"P23": 12})),
    ("Pre-schools, SMS to parents", "preschool chain 3 centres in Lucknow, 28 staff, GST registered, parents should get SMS updates",
     {}, T("Pre-school chain", "Lucknow", 28, 3, True, ["sms"])),
    ("Boutique wants WhatsApp, has no GST", "mera boutique hai delhi me, 3 log, ek shop, gst nahi hai, whatsapp api chahiye customers ko "
     "message karne ke liye",
     {}, T("Boutique", "Delhi", 3, 1, False, ["whatsapp"], lang="hi")),
    ("Bakery chain, orders stop when the net is down", "Bakery chain, 3 outlets in Chennai, 18 staff, GSTIN available. Need billing at "
     "every outlet and backup internet because online orders stop when the net is down",
     {}, T("Bakery chain", "Chennai", 18, 3, True, ["payments", "failover"])),
    ("Small plant wants machine monitoring", "plastic moulding unit, vadodara, 8 workers, 1 unit, gst registered. want to monitor 5 machines",
     {}, T("Plastic moulding unit", "Vadodara", 8, 1, True, ["iot"])),
    ("Law firm, head-count as a sum", "law firm 3 partners + 4 juniors, Bhopal, single office, GST yes, need static IP for court e-filing "
     "software and antivirus on laptops",
     {}, T("Law office", "Bhopal", 7, 1, True, ["static_ip", "security"])),
    ("Spoken Hindi in Latin letters, numbers as words", "haan ji mera kirana store hai bhopal mein do dukaan hai total chhe log hai gst nahi hai",
     {}, T("Kirana store", "Bhopal", 6, 2, False, lang="hi")),
    ("Two people in a co-working space", "We're a 2-person real estate agency working from a co-working space in Bengaluru. No GST.",
     {}, T("Real estate agency", "Bengaluru", 2, 1, False, unsaid=("sites",))),
    ("Salon, shared Wi-Fi password", "Salon with 2 branches in Kochi, 11 staff total, GSTIN registered. Clients complain our wifi password is "
     "shared with everyone. Also want appointment reminders on WhatsApp",
     {}, T("Salon", "Kochi", 11, 2, True, ["guest_wifi", "whatsapp"])),
    ("Hardware store with delivery tempos", "Hardware store Nashik, 6 staff, one shop, GST yes, we have 3 delivery tempos and want to track them",
     {}, T("Hardware store", "Nashik", 6, 1, True, ["fleet"], {"P25": 3})),
    ("A correction half-way", "Coaching centre in Patna, 20 teachers, no GST",
     {"sites": "sorry its 12 teachers not 20, and 2 branches"},
     T("Coaching centre", "Patna", 12, 2, False, unsaid=("sites",))),
    ("GST applied for, not received", "I'm opening a restaurant next month in Hyderabad, will have 5 staff, one outlet, GST applied but not received yet. "
     "Want a toll free number for orders",
     {"gstin": "not yet, applied only"}, T("Restaurant chain", "Hyderabad", 5, 1, False, ["tollfree"])),
    ("All capitals, telegram style", "TEXTILE UNIT SURAT 80 WORKERS 1 FACTORY GST YES NEED LEASED LINE AND FIREWALL",
     {}, T("Textile unit", "Surat", 80, 1, True, ["firewall"])),
    ("Five medical stores under one GSTIN", "5 medical stores in Jaipur under one GSTIN, 22 employees. Need all stores connected & billing "
     "in every store",
     {}, T("Pharmacy chain", "Jaipur", 22, 5, True, ["payments"], also=("Pharmacy",))),
    ("Dentist, team described not counted", "Dentist. Solo practice in Indore with a receptionist and an assistant. Not GST registered. "
     "Patient x-rays must not get lost.",
     {"employees": "3", "sites": "one"}, T("Dental clinic", "Indore", 3, 1, False, ["backup"], unsaid=("employees", "sites"))),
    ("Two hotels, guests need Wi-Fi", "Budget hotel, 2 properties in Jaipur, 16 staff, GST yes. guests need wifi",
     {}, T("Budget hotel group", "Jaipur", 16, 2, True, ["guest_wifi"])),
    ("A range for the team, Hinglish", "electronics showroom, 2 outlets in ahmedabad, 10-12 staff, gst hai, cctv chahiye 6 camera, "
     "aur staff ke liye email",
     {}, T("Electronics retail chain", "Ahmedabad", (10, 12), 2, True, ["cctv", "email"], {"P23": 6}, lang="hi")),
]


# A second set, written after the fixes the first set led to, to see how well those fixes carry to owners nobody
# tuned for. Its first-run score is recorded in the README.
S2 = [
    ("SMS spelling, seats for all", "we r a small ca firm in nagpur, 6 ppl, gst registered. need email ids for all of us and data backup",
     {}, T("CA firm", "Nagpur", 6, 1, True, ["email", "backup"], {"P16": 6}, unsaid=("sites",))),
    ("Hindi salon, Wi-Fi for customers", "मेरा जयपुर में सैलून है, 5 लोग काम करते हैं, एक ही दुकान है, जीएसटी नहीं है, ग्राहकों के लिए वाईफाई चाहिए",
     {}, T("Salon", "Jaipur", 5, 1, False, ["guest_wifi"], lang="hi")),
    ("Hinglish workshop with tempos", "hamara furniture ka workshop hai mysore me, 9 karigar hai, gst hai, 2 tempo hai delivery ke liye unko track karna hai",
     {}, T("Furniture workshop", "Mysuru", 9, 1, True, ["fleet"], {"P25": 2}, lang="hi", unsaid=("sites",))),
    ("Two labs, WhatsApp and toll-free", "Diagnostic centre with 2 labs in Vadodara. 14 employees. GSTIN yes. Want reports to go on WhatsApp and a "
     "toll free number for bookings.",
     {}, T("Diagnostic lab", "Vadodara", 14, 2, True, ["whatsapp", "tollfree"])),
    ("Two trades in one shop", "sweet shop + bakery, Lucknow, 7 workers, single outlet, no GST number. customers pay by UPI and it fails a lot",
     {}, T("Sweet shop", "Lucknow", 7, 1, False, ["payments"], also=("Bakery",))),
    ("Marathi hardware shop, cameras", "पुण्यात आमचे हार्डवेअरचे दुकान आहे, 5 कर्मचारी, एकच दुकान, GST आहे, सीसीटीव्ही कॅमेरे हवेत",
     {}, T("Hardware store", "Pune", 5, 1, True, ["cctv"], lang="mr")),
    ("Tamil pharmacy, WhatsApp", "சென்னையில் எங்கள் மருந்து கடை உள்ளது, 4 பேர், ஒரே கடை, GST உண்டு, வாட்ஸ்அப் வேண்டும்",
     {}, T("Pharmacy", "Chennai", 4, 1, True, ["whatsapp"], lang="ta")),
    ("Bengali coaching centre, two branches", "কলকাতায় আমাদের কোচিং সেন্টার, ৮ জন শিক্ষক, দুটো শাখা, জিএসটি নেই, ওয়েবসাইট চাই",
     {}, T("Coaching centre", "Kolkata", 8, 2, False, ["website"], lang="bn")),
    ("Gujarati textile factory, firewall", "સુરતમાં અમારી ટેક્સટાઇલ ફેક્ટરી છે, 60 કર્મચારીઓ, એક ફેક્ટરી, GST છે, ફાયરવોલ જોઈએ",
     {}, T("Textile unit", "Surat", 60, 1, True, ["firewall"], lang="gu")),
    ("Telugu restaurant, three branches", "హైదరాబాద్‌లో మా రెస్టారెంట్ ఉంది, 12 మంది సిబ్బంది, 3 బ్రాంచ్‌లు, GST ఉంది, బిల్లింగ్ కావాలి",
     {}, T("Restaurant chain", "Hyderabad", 12, 3, True, ["payments"], lang="te")),
    ("Kannada dental clinic, backup", "ಬೆಂಗಳೂರಿನಲ್ಲಿ ನಮ್ಮ ಡೆಂಟಲ್ ಕ್ಲಿನಿಕ್ ಇದೆ, 5 ಜನ, ಒಂದೇ ಕ್ಲಿನಿಕ್, GST ಇಲ್ಲ, ಬ್ಯಾಕಪ್ ಬೇಕು",
     {}, T("Dental clinic", "Bengaluru", 5, 1, False, ["backup"], lang="kn")),
    ("Malayalam bakery, cameras", "കൊച്ചിയിൽ ഞങ്ങളുടെ ബേക്കറി ഉണ്ട്, 6 ജോലിക്കാർ, ഒരു കട, GST ഇല്ല, സിസിടിവി വേണം",
     {}, T("Bakery", "Kochi", 6, 1, False, ["cctv"], lang="ml")),
    ("Punjabi mobile repair shop", "ਲੁਧਿਆਣਾ ਵਿੱਚ ਮੇਰੀ ਮੋਬਾਈਲ ਰਿਪੇਅਰ ਦੀ ਦੁਕਾਨ ਹੈ, 2 ਬੰਦੇ, ਇੱਕ ਦੁਕਾਨ, GST ਨਹੀਂ",
     {}, T("Mobile repair shop", "Ludhiana", 2, 1, False, lang="pa")),
    ("Almost nothing to start with", "need internet for my shop",
     {"business_type": "its a stationery and xerox shop", "city": "nashik", "employees": "me and my brother", "gstin": "no"},
     T("Stationery shop", "Nashik", 2, 1, False, unsaid=("business", "city", "employees", "gst"))),
    ("Factory, head-count in two parts", "Auto parts manufacturing, Pune MIDC, 55 on the shop floor plus 10 in office, GST registered, we need a "
     "leased line, firewall and monitoring for 8 CNC machines",
     {"employees": "65 in all", "sites": "one plant"},
     T("Auto-parts unit", "Pune", 65, 1, True, ["firewall", "iot"], {"P24": 8}, unsaid=("employees", "sites"))),
    ("Two optical shops, card machines", "optical store, 2 shops in Indore, 5 staff in total, GST no. need card machine in both shops",
     {}, T("Optician", "Indore", 5, 2, False, ["payments"])),
    ("Hinglish travel agency, SMS", "sir mera travel agency hai jaipur me 4 log hai ek office hai gst hai customers ko sms bhejna hai",
     {}, T("Travel agency", "Jaipur", 4, 1, True, ["sms"], lang="hi")),
    ("Thirty lawyers, one gig", "Law office Mumbai 30 lawyers one office GST yes need 1 gig internet, static ip and email for everyone",
     {}, T("Law office", "Mumbai", 30, 1, True, ["static_ip", "email"], {"P16": 30})),
    ("A question in the first message", "Hi, I have a boutique in Surat, 3 girls work with me, no GST yet. Can I get WhatsApp business?",
     {"employees": "4 with me", "sites": "1"}, T("Boutique", "Surat", (3, 4), 1, False, ["whatsapp"], unsaid=("employees", "sites"))),
    ("Pre-school, team in two parts", "pre school in Bhopal, 9 teachers and 2 helpers, 1 centre, GST not applicable for us. want cctv in the "
     "classrooms so parents feel safe",
     {}, T("Pre-school chain", "Bhopal", 11, 1, False, ["cctv"])),
]


# ---------- what the catalogue allows, worked out here and not by the app ----------
def allowed(pid: str, t: dict, _seen=()) -> str | None:
    """None if the catalogue lets this owner have the product, else the rule that stops it."""
    p = products()[pid]
    if city_tiers().get(t["city"], 2) not in p.tiers:
        return "city"
    if t["employees"] < p.min_employees:
        return "team size"
    if t["sites"] < p.min_sites:
        return "sites"
    if p.requires_gstin and not t["gst"]:
        return "GSTIN"
    if p.requires_one_of and pid not in _seen and all(allowed(x, t, (*_seen, pid)) for x in p.requires_one_of):
        return "needs a line it can't have"
    return None


def valid(rec: dict, t: dict) -> list[str]:
    errs, q = [], rec["quote"]
    ids = {l["id"] for l in q["lines"]}
    for l in q["lines"]:
        p = products()[l["id"]]
        why = allowed(l["id"], t)
        if why:
            errs.append(f"sold {l['id']} {p.name}, which the catalogue does not allow here ({why})")
        if p.requires_one_of and not ids & set(p.requires_one_of):
            errs.append(f"{l['id']} {p.name} is in the bundle without the line it depends on")
        if not p.price_min <= l["unit_price"] <= p.price_max:
            errs.append(f"{l['id']} priced ₹{l['unit_price']}, outside ₹{p.price_min}-{p.price_max}")
        if l["monthly"] != l["unit_price"] * l["qty"] or l["qty"] < 1:
            errs.append(f"{l['id']} line total is wrong")
    if q["monthly"] != sum(l["monthly"] for l in q["lines"]):
        errs.append("the monthly total is not the sum of the lines")
    if abs(q["gst"] - round(q["monthly"] * 0.18)) > 1:
        errs.append("GST is not 18%")
    if q["setup"] != sum(l.get("setup", 0) for l in q["lines"]):
        errs.append("the one-time total is not the sum of the lines")
    if q["activation_days"] != max(products()[i].install_days for i in ids):
        errs.append("go-live is not the slowest product")
    return errs


# ---------- one conversation, every answer typed ----------
FIELD = {"business_type": "business", "city": "city", "employees": "employees", "sites": "sites", "gstin": "gst"}


def talk(opening: str, answers: dict, t: dict, log: list):
    """Returns (session, last reply, needs card, what went wrong, the facts the app asked for)."""
    hinglish = t["lang"] != "en" and opening.isascii()  # Hindi typed in Latin letters: keep answering that way
    native = t["lang"] != "en" and not hinglish          # an owner typing in their script taps the two choice questions
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text=opening)
    log.append(("owner", opening))
    card, asked = None, []
    for _ in range(12):
        log.extend(("app", m) for m in r.get("messages") or [])
        if r.get("recommendation"):
            break
        if r.get("needs"):
            card = r["needs"]
            r = advisor.message(sid, needs=[n["key"] for n in card if n["selected"]])
            log.append(("owner", "[Continue]"))
            continue
        chips = r.get("chips") or [{}]
        slot = chips[0].get("slot")
        number_ask = slot == "gstin" and any(c.get("value") == "skip" for c in chips)  # "type your GSTIN": asked once by design
        if slot in FIELD and not number_ask:
            asked.append(FIELD[slot])
        tap = None
        if slot == "gstin_confirm":
            say = "yes"
        elif slot in answers:
            say = answers[slot]
        elif slot == "employees":
            say = str(t["employees"])
        elif slot == "sites":
            say = str(t["sites"])
        elif slot == "city":
            say = t["city"]
        elif slot == "business_type":
            say = t["business"][0]
        elif slot == "gstin" and number_ask and (native or hinglish):
            say, tap = "[Skip]" if native else "number baad mein dunga", ("skip" if native else None)
        elif slot == "gstin":
            say = ("haan hai, number baad mein dunga" if t["gst"] else "nahi hai") if hinglish else \
                ("yes we have GST, I will give the number later" if t["gst"] else "no GST")
            if native and not t["gst"]:
                say, tap = "[No GSTIN]", "none"
        elif slot == "current":
            say = "mobile hotspot se chalta hai" if hinglish else "we use a phone hotspot"
            if native:
                say, tap = "[Phone hotspot]", "hotspot"
        else:
            return sid, r, card, f"stuck at {slot or r.get('stage')}", asked
        log.append(("owner", say))
        r = advisor.message(sid, slot=slot, value=tap) if tap else advisor.message(sid, text=say)
    return sid, r, card, None if r.get("recommendation") else "never reached a bundle", asked


def judge(name, opening, answers, t) -> tuple[dict, list]:
    log: list = []
    sid, r, card, stuck, asked = talk(opening, answers, t, log)
    res = {k: [] for k in CHECKS}
    if stuck:
        for k in res:
            res[k].append(stuck)
        return res, log
    rec, prof = r["recommendation"], r["profile"]
    ids = {l["id"]: l for l in rec["quote"]["lines"]}

    if prof["business_type"] not in t["business"]:
        res["understood"].append(f"business {prof['business_type']!r}, typed as {t['business'][0]!r}")
    if (prof.get("city") or "").lower() != t["city"].lower():
        res["understood"].append(f"city {prof.get('city')!r}, not {t['city']!r}")
    if not t["team"][0] <= (prof.get("employees") or 0) <= t["team"][1]:
        res["understood"].append(f"team of {prof.get('employees')}, not {t['employees']}")
    if prof.get("sites") != t["sites"]:
        res["understood"].append(f"{prof.get('sites')} sites, not {t['sites']}")
    if bool(prof.get("has_gstin")) != t["gst"]:
        res["understood"].append(f"GST {'yes' if prof.get('has_gstin') else 'no'}, owner said {'yes' if t['gst'] else 'no'}")

    ticked = {n["key"] for n in card or [] if n["selected"]}
    blocked = {b["id"] for b in rec.get("blocked") or []}
    for ask in t["asks"]:
        pids = SERVES[ask]
        can = [pid for pid in pids if not allowed(pid, t)]
        if can and card is not None and ask not in ticked and not any(pid in ids for pid in pids):
            res["asked for"].append(f"{ask} was asked for but not ticked")
        if can and not any(pid in ids for pid in can):
            res["served"].append(f"{ask}: {can[0]} {products()[can[0]].name} is allowed for this owner but is not in the bundle")
        if not can and not any(pid in blocked for pid in pids):
            said = " ".join(log_text(log))
            if not any(products()[pid].name.split()[0].lower() in said.lower() for pid in pids):
                res["served"].append(f"{ask}: not available to this owner ({allowed(pids[0], t)}), and nobody told them")

    res["valid"] = valid(rec, t)

    line = next((ids[i] for i in LINES if i in ids), None)
    if not line:
        res["sized"].append("no internet line")
    elif line["qty"] != t["sites"]:
        res["sized"].append(f"{line['qty']} internet line(s) for {t['sites']} site(s)")
    for pid, n in t["counts"].items():
        if pid in ids and ids[pid]["qty"] != n and not allowed(pid, t):
            res["sized"].append(f"{products()[pid].name}: {ids[pid]['qty']} on the bill, owner said {n}")

    for what in dict.fromkeys(asked):
        if what not in t["unsaid"]:
            res["listened"].append(f"asked for the {what}, which the owner had already said")

    first = (r.get("messages") or [""])[0]
    if not re.search(SCRIPT[t["lang"]], first) or (t["lang"] != "en" and len(re.findall(SCRIPT[t["lang"]], first)) < 10):
        res["language"].append(f"answer not in the owner's script: {first[:70]}")
    return res, log


CHECKS = ("understood", "listened", "asked for", "served", "valid", "sized", "language")


def log_text(log):
    return [m for who, m in log if who == "app"]


def run(title: str, owners: list) -> bool:
    print(f"{title}\n")
    totals = {k: 0 for k in CHECKS}
    clean = 0
    for name, opening, answers, t in owners:
        try:
            res, log = judge(name, opening, answers, t)
        except Exception as e:  # noqa: BLE001
            res, log = {k: [f"crashed: {e!r}"] for k in totals}, []
        bad = {k: v for k, v in res.items() if v}
        for k in totals:
            totals[k] += not res[k]
        clean += not bad
        print(f"{'PASS' if not bad else 'FAIL'}  {name}")
        for k, v in bad.items():
            for x in v:
                print(f"        {k}: {x}")
        if ARGS.verbose or (bad and os.environ.get("JUDGE_LOG")):
            for who, m in log:
                print(f"          {who:>5}: {str(m)[:200]}")
    n = len(owners)
    print()
    for k, v in totals.items():
        print(f"  {k:<11} {v}/{n}")
    print(f"\n{clean}/{n} owners handled with nothing wrong\n")
    return clean == n


def main():
    mode = "LLM + rules" if ARGS.llm else "rules only"
    ok = run(f"Judge-style scenarios ({mode}): {len(S)} unseen owners, every answer typed", S)
    ok = run(f"Second set ({mode}): {len(S2)} more, written after the first set's fixes", S2) and ok
    print("PASS" if ok else "FAIL", f"{len(S) + len(S2)} owners")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
