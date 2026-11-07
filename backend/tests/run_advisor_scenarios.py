"""Advisor scenario suite: owners in 5 languages, driven end to end through the real advisor.

    python -m tests.run_advisor_scenarios          # rules only (deterministic), the default
    python -m tests.run_advisor_scenarios --llm    # with the LLM from .env, as in a live demo

Every bundle is checked against the catalogue (eligibility, GSTIN, city tier, team size, sites, dependencies,
prices inside the published range, GST at 18%, go-live = slowest product) and against what a good salesperson
would recommend for that owner. Follow-up turns check that the bundle changes correctly from chat, that a question
never changes it (it is answered, and the change is offered as a button), and that every button does what it says.
"""
import re
import argparse
import os
import sys
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument("--llm", action="store_true")
parser.add_argument("-v", "--verbose", action="store_true")
ARGS = parser.parse_args()
if ARGS.llm:  # the same keys the server uses (app.main loads .env; this suite imports the advisor directly)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
else:
    os.environ["LLM_API_KEY"] = os.environ["GROQ_API_KEY"] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "scenarios.db"))

from app import advisor  # noqa: E402
from app.data import gstin_registry, products  # noqa: E402
from app.recommender import CONNECTIVITY, check_eligibility, unit_price  # noqa: E402


def gstin(status: str, state: str | None = None) -> str:
    return next(g for g, r in gstin_registry().items() if r["status"] == status and (not state or r["state"] == state))


ACTIVE_KL, CANCELLED, SUSPENDED = gstin("Active", "Kerala"), gstin("Cancelled"), gstin("Suspended")
ACTIVE_MH, ACTIVE_KA = gstin("Active", "Maharashtra"), gstin("Active", "Karnataka")

# name, language, opening message, answers to follow-up questions, expectations, follow-up turns
S = [
    ("Kirana, tier 2, no GST", "en", "I run a kirana store in Jaipur with 3 people, one shop, no GST", {},
     {"has": ["P01", "P07"], "not": ["P15", "P14", "P03"], "max": 3500}),
    ("Pharmacy in Hindi", "hi", "मेरी लखनऊ में मेडिकल दुकान है, 4 लोग काम करते हैं, एक दुकान, GST नहीं है", {},
     {"has": ["P01", "P07"], "not": ["P15"]}),
    ("Salon in Hinglish", "en", "Indore mein mera salon hai, 6 log hai, ek hi shop, GST nahi hai", {},
     {"has": ["P01"], "not": ["P15", "P14"]}),
    ("Dental clinic with GSTIN", "en", f"Dental clinic, 8 staff, GSTIN {ACTIVE_KL}", {"sites": 1},
     {"has": ["P02"], "has_any": [["P16", "P20", "P17"]], "segment": "prof"}),
    ("CA firm Mumbai 25 staff", "en", "We are a CA firm in Mumbai with 25 employees, 1 office, we have GST", {},
     {"segment": "prof", "has_any": [["P02", "P03"]], "has": ["P16"]}),
    ("Law office tier 2", "en", "Law office in Bhopal, 22 people, one office, GST registered", {},
     {"not": ["P03"], "segment": "prof"}),
    ("Coaching centre Marathi", "mr", "माझे पुण्यात कोचिंग क्लासेस आहेत, 12 लोक, एक शाखा, GST नाही", {},
     {"has_any": [["P01", "P02"]], "not": ["P14"]}),
    ("Restaurant chain 5 outlets", "en", "Restaurant chain in Bengaluru with 5 outlets and 40 staff, GST registered", {},
     {"segment": "multi", "conn_qty": 5, "has": ["P09"]}),
    ("Retail chain 8 stores", "en", "Apparel retail chain, 8 stores in Pune, 60 employees, we have GSTIN", {},
     {"segment": "multi", "conn_qty": 8}),
    ("Factory with leased line", "en", "Auto parts factory in Ludhiana, 40 workers, 1 plant, GST registered", {},
     {"segment": "mfg", "has": ["P05"]}),
    ("Large plant 120 staff", "en", "Textile unit in Coimbatore, 120 workers, one plant, GST yes", {},
     {"segment": "mfg", "has": ["P06"]}),
    ("Small workshop no GST", "en", "Furniture workshop in Mysuru, 6 people, one workshop, no GST", {},
     {"not": ["P05", "P06", "P24"]}),
    ("No fibre at site", "en", "Kirana store in Kochi, 2 people, one shop, no GST, no fibre available here", {},
     {"has": ["P04"], "not": ["P01", "P02"]}),
    ("Cancelled GSTIN", "en", f"Travel agency, 5 staff, one office, GSTIN {CANCELLED}", {},
     {"not": ["P15", "P14", "P13", "P12", "P03"]}),
    ("Suspended GSTIN", "en", f"Real estate office, 4 people, 1 office, GSTIN {SUSPENDED}", {},
     {"not": ["P15", "P14", "P13", "P12"]}),
    ("Invalid GSTIN then none", "en", "Bakery in Nagpur, 4 people, one shop, GSTIN 27ABCDE1234F1Z9", {"gstin": "none"},
     {"has": ["P01"]}),
    ("Tamil boutique", "ta", "சென்னையில் என் பூட்டிக் கடை, 3 பேர், ஒரு கடை, GST இல்லை", {"business_type": "Boutique",
     "city": "Chennai", "employees": 3, "sites": 1, "gstin": "none"}, {"has": ["P01"]}),
    ("Hotel group wants toll-free", "en", "Budget hotel group with 3 hotels in Jaipur, 30 staff, GST registered, need a toll free number", {},
     {"segment": "multi", "has": ["P13"]}),
    ("Clinic wants WhatsApp no GST", "en", "Physiotherapy clinic in Lucknow, 5 staff, one clinic, no GST, we want WhatsApp for appointments", {},
     {"not": ["P15"], "blocked": ["P15"]}),
    ("Gym chain", "en", "Gym chain with 4 branches in Hyderabad, 30 trainers, GST registered", {},
     {"segment": "multi", "conn_qty": 4}),
    ("Pre-school chain", "en", "Pre-school chain, 3 centres in Ahmedabad, 25 staff, GST yes", {}, {"segment": "multi"}),
    ("Diagnostic lab cameras", "en", "Diagnostic lab in Kolkata with 15 staff, 1 lab, GST registered, need 6 cameras", {},
     {"has": ["P23"], "qty": {"P23": 6}}),
    ("Stationery tiny shop", "en", "Stationery shop in Indore, just me, single shop, no gst", {}, {"max": 3000}),
    ("Delivery fleet", "en", "Food processing unit in Indore, 30 workers, one unit, GST yes, 5 delivery vans to track", {},
     {"has": ["P25"]}),
    ("Optician answers by chips", "en", "optician", {"city": "Delhi", "employees": 3, "sites": 1, "gstin": "none"},
     {"has": ["P01"]}),
    ("GSTIN only, Maharashtra", "en", f"My GSTIN is {ACTIVE_MH}", {"employees": 6, "sites": 1, "business_type": "Pharmacy"},
     {"has_any": [["P01", "P02"]]}),
    ("GSTIN only, Karnataka", "en", f"{ACTIVE_KA}", {"employees": 12, "sites": 1, "business_type": "CA firm"},
     {"has_any": [["P01", "P02", "P03"]]}),
    ("Unknown small town", "en", "Mobile repair shop in Jhansi, 2 people, one shop, no GST", {},
     {"not": ["P03"], "has": ["P01"]}),
    ("Architecture studio with servers", "en", "Architecture studio in Pune, 18 people, one office, GST yes, we need remote access to our server", {},
     {"has": ["P11"]}),
    ("Electronics chain", "en", "Electronics retail chain with 6 stores in Chennai, 45 staff, GST registered", {},
     {"segment": "multi", "conn_qty": 6}),
    ("Hindi clinic with GSTIN", "hi", f"मेरा डेंटल क्लिनिक है, 9 लोग, एक क्लिनिक, GSTIN {ACTIVE_MH}", {},
     {"segment": "prof", "has_any": [["P01", "P02"]]}),
    ("Says current internet", "en", "Bakery in Indore, 5 people, one shop, no GST, we use a phone hotspot right now", {},
     {"has": ["P01"], "current": "hotspot"}),
    ("Current internet typed", "en", "Tailoring shop in Surat, 3 people, 1 shop, no GST", {"current": "jio fiber 799"},
     {"has": ["P01"], "current": "business", "spend": 799}),
    ("Coaching centre Hinglish", "en", "Patna mein coaching centre hai, 10 log, ek branch, GST nahi", {},
     {"not": ["P14", "P15"]}),
    ("Chartered accountant tier 1", "en", f"CA practice in Bengaluru, 14 staff, one office, GSTIN {ACTIVE_KA}", {},
     {"segment": "prof", "has": ["P16"]}),
]

FOLLOW_UPS = [  # applied to the first scenario's bundle, in order: (message, check)
    ("make it cheaper", lambda old, new: new["monthly"] <= old["monthly"] and new["term"] == old["term"]),  # never a silent 24 months
    ("add CCTV", lambda old, new: "P23" in new["ids"]),
    ("remove CCTV", lambda old, new: "P23" not in new["ids"]),
    ("24 months", lambda old, new: new["term"] == 24),
    ("my budget is 1500", lambda old, new: new["monthly"] <= 1500 or new["monthly"] == old["monthly"]),
    ("undo", lambda old, new: new["monthly"] != old["monthly"] or new["ids"] != old["ids"]),
    ("what documents do I need?", lambda old, new: new["ids"] == old["ids"]),
]


SAME = lambda old, new: new == old  # noqa: E731
# (message or ("tap", value), check on the bundle, words the answer must contain, chip value that must be offered)
QUESTIONS = [  # a pharmacy in Jaipur, no GSTIN: every question is answered and the bundle stays the same
    ("can I skip CCTV?", SAME, r"saves ₹[\d,]+ a month", "remove:cctv"),
    ("do I need mobile lines?", SAME, r"saves ₹", "remove:mobile"),
    ("CCTV zaruri hai kya?", SAME, r"₹", "remove:cctv"),
    ("is the billing tablet necessary?", SAME, r"saves ₹", "remove:payments"),
    ("what's the difference between 12 and 24 months?", SAME, r"₹[\d,]+/month.*₹[\d,]+/month", "term:24"),
    ("24 months?", SAME, r"two years", "term:24"),
    ("which is better, 12 or 24?", SAME, r"commit", "term:24"),
    ("how much is the first bill with GST?", SAME, r"first bill", None),
    ("is my customers' data safe?", SAME, r"consent", "add:backup"),
    ("what if the internet goes down?", SAME, r"backup internet", "add:failover"),
    ("Jio gives 100 Mbps for 699, why should I pay more?", SAME, r"one bill", "cheaper"),
    ("what is static IP?", SAME, r"fixed address", "add:static_ip"),
    ("do I need a website?", SAME, r"isn't in your bundle", "add:website"),
    ("can we do without internet?", SAME, r"base of your bundle", "cheaper"),
    ("what is mbps?", SAME, r"internet speed", None),
    (("tap", "keep"), SAME, r"nothing changed", None),
    (("tap", "remove:cctv"), lambda old, new: "P23" not in new["ids"] and new["monthly"] < old["monthly"], r"Removed", "undo"),
    (("tap", "undo"), lambda old, new: "P23" in new["ids"], r"previous bundle", None),
    (("tap", "term:24"), lambda old, new: new["term"] == 24 and new["monthly"] < old["monthly"], r"24 months", None),
    ("basic", lambda old, new: new["monthly"] < old["monthly"], r"Basic", "undo"),
    (("tap", "undo"), lambda old, new: new["monthly"] > old["monthly"], r"previous bundle", None),
    ("complete", lambda old, new: new["monthly"] > old["monthly"], r"Complete", None),
]


def state(rc):
    return {"monthly": rc["quote"]["monthly"], "term": rc["quote"]["term_months"],
            "ids": [l["id"] for l in rc["quote"]["lines"]]}


def catalogue_checks(rec: dict, profile: dict) -> list[str]:
    errs = []
    q = rec["quote"]
    ids = {l["id"] for l in q["lines"]}
    from app.recommender import Profile
    p = Profile(employees=profile.get("employees"), sites=profile.get("sites"), city_tier=profile.get("city_tier"),
                has_gstin=profile.get("has_gstin"), gstin_verified=profile.get("gstin_verified"))
    for l in q["lines"]:
        prod = products()[l["id"]]
        why = check_eligibility(l["id"], p, ids)
        if why:
            errs.append(f"{l['id']} not eligible ({why})")
        term = max(q["term_months"], prod.min_contract)
        if not prod.price_min <= l["unit_price"] <= prod.price_max:
            errs.append(f"{l['id']} unit price {l['unit_price']} outside {prod.price_min}-{prod.price_max}")
        if l["unit_price"] != unit_price(prod, term):
            errs.append(f"{l['id']} unit price not the catalogue price for {term} months")
        if l["monthly"] != l["unit_price"] * l["qty"]:
            errs.append(f"{l['id']} line total wrong")
    if q["monthly"] != sum(l["monthly"] for l in q["lines"]):
        errs.append("monthly total is not the sum of lines")
    if abs(q["gst"] - round(q["monthly"] * 0.18)) > 1:
        errs.append("GST is not 18%")
    if q["activation_days"] != max(products()[i].install_days for i in ids):
        errs.append("go-live is not the slowest product")
    if not ids & set(CONNECTIVITY):
        errs.append("no internet line")
    return errs


def run_one(name, lang, opening, answers, exp, verbose=False):
    sid = advisor.start(lang)["session_id"]
    r = advisor.message(sid, text=opening)
    for _ in range(8):
        if r.get("recommendation"):
            break
        if r.get("needs"):
            r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]])
            continue
        slot = (r.get("chips") or [{}])[0].get("slot")
        if slot == "gstin_confirm":  # "is this your business?" -> yes
            r = advisor.message(sid, slot=slot, value="yes")
            continue
        if slot == "current":
            v = answers.get("current", "hotspot")
            r = advisor.message(sid, slot=slot, value=v) if v in advisor.CURRENT_CHOICES else advisor.message(sid, text=v)
            continue
        if slot in answers:
            v = answers[slot]
            r = advisor.message(sid, slot=slot, value=v) if slot != "business_type" else advisor.message(sid, text=v)
        elif slot == "gstin":
            skip = any(c.get("value") == "skip" for c in r.get("chips") or [])
            r = advisor.message(sid, slot="gstin", value="skip" if skip else "none")
        else:
            return sid, None, [f"stuck at {slot or r.get('stage')}: {r['messages'][-1][:80]}"]
    rec = r.get("recommendation")
    if not rec:
        return sid, None, ["no recommendation"]
    errs = catalogue_checks(rec, r["profile"])
    ids = [l["id"] for l in rec["quote"]["lines"]]
    qty = {l["id"]: l["qty"] for l in rec["quote"]["lines"]}
    for pid in exp.get("has", []):
        if pid not in ids:
            errs.append(f"expected {pid} ({products()[pid].name})")
    for group in exp.get("has_any", []):
        if not set(group) & set(ids):
            errs.append(f"expected one of {group}")
    for pid in exp.get("not", []):
        if pid in ids:
            errs.append(f"should not include {pid} ({products()[pid].name})")
    if "segment" in exp and rec["segment"] != exp["segment"]:
        errs.append(f"segment {rec['segment']}, expected {exp['segment']}")
    if "conn_qty" in exp:
        conn = next((l for l in rec["quote"]["lines"] if l["id"] in CONNECTIVITY), None)
        if not conn or conn["qty"] != exp["conn_qty"]:
            errs.append(f"internet lines {conn and conn['qty']}, expected {exp['conn_qty']}")
    for pid, n in exp.get("qty", {}).items():
        if qty.get(pid) != n:
            errs.append(f"{pid} qty {qty.get(pid)}, expected {n}")
    if "max" in exp and rec["quote"]["monthly"] > exp["max"]:
        errs.append(f"₹{rec['quote']['monthly']} is above ₹{exp['max']} for this owner")
    for pid in exp.get("blocked", []):
        if pid not in [b["id"] for b in rec["blocked"]]:
            errs.append(f"{pid} should be explained as not available")
    prof = advisor._profile(advisor.store.get("session", sid))
    if "current" in exp and prof.current_internet != exp["current"]:
        errs.append(f"current internet {prof.current_internet!r}, expected {exp['current']!r}")
    if "spend" in exp and prof.current_spend != exp["spend"]:
        errs.append(f"current spend {prof.current_spend}, expected {exp['spend']}")
    for line in rec["quote"]["lines"]:
        if not (line.get("plain") and line.get("does") and line.get("skip") and line.get("per_day")):
            errs.append(f"{line['id']} has no plain-language card")
    if verbose:
        print(f"    {ids} ₹{rec['quote']['monthly']}")
    return sid, rec, errs


def main():
    passed, checks = 0, 0
    print(f"Advisor scenarios ({'LLM + rules' if ARGS.llm else 'rules only'})\n")
    first_sid = None
    for name, lang, opening, answers, exp in S:
        sid, rec, errs = run_one(name, lang, opening, answers, exp, ARGS.verbose)
        first_sid = first_sid or sid
        checks += 12 + sum(len(v) if isinstance(v, (list, dict)) else 1 for v in exp.values())
        ok = not errs
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  [{lang}] {name}" + ("" if ok else "\n      - " + "\n      - ".join(errs)))
    print("\nFollow-up changes from chat (first scenario):")
    f_pass = 0
    rec = advisor.resume(first_sid)["recommendation"]
    old = state(rec)
    for msg, check in FOLLOW_UPS:
        r = advisor.message(first_sid, text=msg)
        new = state(r["recommendation"])
        errs = catalogue_checks(r["recommendation"], r["profile"])
        ok = check(old, new) and not errs
        f_pass += ok
        print(f"{'PASS' if ok else 'FAIL'}  \"{msg}\": ₹{old['monthly']} -> ₹{new['monthly']}  {r['messages'][0][:70]}"
              + ("" if not errs else f"  {errs}"))
        old = new
    print("\nQuestions never change the bundle; buttons do exactly what they say (pharmacy, Jaipur):")
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a pharmacy in Jaipur with 4 people, one shop, no GST. We had a theft last month")
    r = advisor.message(sid, slot="current", value="hotspot")
    r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]])
    q_pass, old = 0, state(r["recommendation"])
    for step, check, words, chip in QUESTIONS:
        if isinstance(step, tuple):
            r, shown = advisor.message(sid, slot="refine", value=step[1]), f"[tap {step[1]}]"
        else:
            r, shown = advisor.message(sid, text=step), f"\"{step}\""
        new = state(r["recommendation"])
        said = " ".join(r["messages"])
        errs = catalogue_checks(r["recommendation"], r["profile"])
        if not check(old, new):
            errs.append(f"bundle {old} -> {new}")
        if words and not re.search(words, said):
            errs.append(f"answer lacks /{words}/")
        if chip and chip not in [c["value"] for c in r.get("chips") or []]:
            errs.append(f"no {chip} button")
        ok = not errs
        q_pass += ok
        print(f"{'PASS' if ok else 'FAIL'}  {shown}: {said[:90]}" + ("" if ok else f"\n      - " + "\n      - ".join(errs)))
        old = new
    print("\nSelling: objections, the next step, problems, out-of-turn answers, outlets:")
    s_pass, s_total = selling()
    total = len(S) + len(FOLLOW_UPS) + len(QUESTIONS) + s_total
    print(f"\n{passed + f_pass + q_pass + s_pass}/{total} passed ({passed}/{len(S)} scenarios, {f_pass}/{len(FOLLOW_UPS)} follow-ups, "
          f"{q_pass}/{len(QUESTIONS)} questions and buttons, {s_pass}/{s_total} selling), {checks}+ checks against the catalogue")
    sys.exit(0 if passed + f_pass + q_pass + s_pass == total else 1)


def _to_bundle(sid, r, pick=None):
    for _ in range(8):
        if r.get("recommendation") and r.get("stage") == "done":
            return r
        if r.get("needs"):
            r = advisor.message(sid, needs=pick if pick is not None else [n["key"] for n in r["needs"] if n["selected"]])
            continue
        slot = (r.get("chips") or [{}])[0].get("slot")
        if slot == "current":
            r = advisor.message(sid, slot="current", value="hotspot")
        elif slot == "gstin":
            skip = any(c.get("value") == "skip" for c in r.get("chips") or [])
            r = advisor.message(sid, slot="gstin", value="skip" if skip else "none")
        else:
            raise AssertionError(f"stuck at {slot}: {r['messages'][-1][:80]}")
    raise AssertionError("no bundle")


def selling():
    """The moments that decide a sale, as a judge would try them. A complaint or a hesitation never changes the bundle;
    each answer gives choices with prices and ends with the next step."""
    results = []

    def check(label, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"\n      - {detail}"))

    def values(r):
        return [c["value"] for c in r.get("chips") or []]

    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a kirana store in Jaipur with 3 staff, one shop, no GST")
    r = advisor.message(sid, slot="current", value="hotspot")
    check("the checklist asks about problems, not products", any(c["slot"] == "pain" for c in r.get("chips") or []),
          r.get("chips"))
    r = advisor.message(sid, slot="pain", value="theft")
    check("tapping \"theft\" ticks CCTV", any(n["key"] == "cctv" and n["selected"] for n in r["needs"]), r["needs"])
    r = _to_bundle(sid, r)
    base = state(r["recommendation"])
    check("the why panel quotes what she told us", "Theft" in " ".join(w["text"] for w in r["recommendation"]["why"]),
          r["recommendation"]["why"][0])
    check("every bundle offers the next step first", values(r)[:1] == ["proceed"], values(r))

    r = advisor.message(sid, text="this is too expensive for me")
    said = " ".join(r["messages"])
    check("\"too expensive\": nothing changes, it answers with ₹ a day and choices",
          state(r["recommendation"]) == base and "a day" in said and {"option:basic", "term:24"} <= set(values(r)),
          f"{said[:120]} {values(r)}")
    r = advisor.message(sid, text="my nephew set up Jio for 399, why should I pay you?")
    said = " ".join(r["messages"])
    check("a competitor's price: what a business line and one bill give, then the cheaper option and the next step",
          state(r["recommendation"]) == base and "one bill" in said and "Go ahead" in said and "cheaper" in values(r),
          said[:160])
    r = advisor.message(sid, text="let me think about it, I'll come back later")
    check("\"let me think\": bundle saved, asks what is holding her back",
          state(r["recommendation"]) == base and {"ask:obj_price", "ask:obj_someone", "callback"} <= set(values(r)),
          values(r))
    r = advisor.message(sid, slot="refine", value="ask:obj_someone")
    check("\"need to ask someone\": a summary she can forward, and a call for both",
          "GST" in r["messages"][1] and "₹" in r["messages"][1] and "callback" in values(r), r["messages"])
    r = advisor.message(sid, text="which one do you recommend and why?")
    said = " ".join(r["messages"])
    check("\"which one do you recommend?\": a straight answer with reasons",
          said.startswith("I'd go with Recommended") and "Theft" in said and values(r)[0] == "proceed", said[:200])
    r = advisor.message(sid, text="make it cheaper")
    check("\"make it cheaper\" never switches to 24 months on its own", state(r["recommendation"])["term"] == 12,
          state(r["recommendation"]))
    r = advisor.message(sid, slot="refine", value="proceed")
    check("Go ahead opens the price", r.get("go") == "quote", r.get("go"))

    sid = advisor.start("hi")["session_id"]
    r = _to_bundle(sid, advisor.message(sid, text="जयपुर में मेरी किराना दुकान है, 3 लोग, एक दुकान, GST नहीं है"))
    base = state(r["recommendation"])
    r = advisor.message(sid, text="बहुत महंगा है")
    check("Hindi \"बहुत महंगा है\": nothing changes, choices in Hindi",
          state(r["recommendation"]) == base and re.search(r"[\u0900-\u097f]", r["messages"][0]) and "term:24" in values(r),
          r["messages"][0][:100])

    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a pharmacy in Pune with 4 staff, one shop, no GST")
    r = advisor.message(sid, slot="current", value="hotspot")
    r = advisor.message(sid, text="I don't know what I need honestly")
    check("\"I don't know what I need\": it asks about problems", r.get("needs") and
          any(c["slot"] == "pain" for c in r.get("chips") or []), r["messages"])
    r = advisor.message(sid, text="UPI keeps failing at rush hour")
    check("a problem in her own words ticks what fixes it", r.get("stage") == "done" and
          {"P19", "P09"} <= set(state(r["recommendation"])["ids"]), r.get("stage"))

    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I have a small shop in Indore with 3 people")
    r = advisor.message(sid, text="mobile hotspot")
    check("an answer to another question is kept, not \"didn't catch that\"",
          "didn't catch" not in " ".join(r["messages"]) and advisor._profile(advisor.store.get("session", sid)).current_internet == "hotspot",
          r["messages"])
    sid = advisor.start("hi")["session_id"]
    r = advisor.message(sid, text="मोबाइल की दुकान है लखनऊ में")
    check("Hindi \"मोबाइल की दुकान\" is a mobile shop, not a kirana", r["profile"]["business_type"] == "Mobile repair shop",
          r["profile"]["business_type"])

    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="4 restaurants in Pune and Mumbai, about 40 staff, GST registered")
    r = advisor.message(sid, slot="gstin", value="skip")
    r = advisor.message(sid, text="leased line at one site and local ISPs at others")
    check("\"leased line at one site\" keeps 4 outlets; the first city named is home",
          r["profile"]["sites"] == 4 and r["profile"]["city"] == "Pune", r["profile"])
    r = _to_bundle(sid, r, pick=["payments", "cctv", "guest_wifi", "central_mgmt", "failover"])
    base = state(r["recommendation"])
    check("a 4-outlet chain gets a bundle (this used to fail)", r["messages"] and "P10" in base["ids"], r["messages"][:1])
    r = advisor.message(sid, text="can each outlet have a different setup? one is very small")
    check("\"each outlet different? one is small\": yes, per outlet, with a lighter option as a button",
          state(r["recommendation"]) == base and "small:1" in values(r) and "outlets" in r["messages"][1], r["messages"][:2])
    r = advisor.message(sid, slot="refine", value="small:1")
    conns = [l for l in r["recommendation"]["quote"]["lines"] if l["id"] in CONNECTIVITY]
    check("the small outlet gets a lighter line, the price drops, one bill",
          [(l["id"], l["qty"]) for l in conns] == [("P02", 3), ("P01", 1)] and state(r["recommendation"])["monthly"] < base["monthly"]
          and not catalogue_checks(r["recommendation"], r["profile"]), conns)
    r = advisor.message(sid, text="how long will all 4 take?")
    check("\"how long for all 4?\": per outlet, side by side", "All 4 outlets" in r["messages"][0], r["messages"][0])

    # found on the live site with the AI on: "फोन का हॉटस्पॉट" read as a question, and "no GSTIN" said twice
    rules = advisor.assistant.rules_understand("फोन का हॉटस्पॉट", "chat")
    check("Hindi \"फोन का हॉटस्पॉट\" is an answer, not a question (का means \"of\" in Hindi)", rules["intent"] is None, rules["intent"])
    p, notes = advisor.Profile(has_gstin=False), []
    advisor._apply(p, {"has_gstin": False}, "hi", notes)
    check("\"no GSTIN, that's fine\" is said once, not again when the AI repeats the fact", notes == [], notes)

    # problems told in the first line are heard back at once, and not again when the next answer repeats them
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a pharmacy in Jaipur, we are 4 people. UPI fails at rush hour and we had a theft last month.")
    r2 = advisor.message(sid, text="UPI fails at rush hour, 1 shop")
    check("problems in the first line are heard back once, before the next question",
          r["messages"][0].startswith("Noted:") and "UPI" in r["messages"][0] and "Theft" in r["messages"][0]
          and not any(m.startswith("Noted:") for m in r2["messages"]), (r["messages"], r2["messages"]))

    # found while checking the video flow: with the AI on, "yes, that's my shop" looped on "is this your business?"
    real_ask, real_worth = advisor.assistant.llm_understand, advisor.assistant.worth_asking_llm
    advisor.assistant.worth_asking_llm = lambda *a, **k: True
    advisor.assistant.llm_understand = lambda *a, **k: {
        "facts": {"gstin": "08EAHXC5550F1ZF", "business_type": "Pharmacy"}, "action": "none", "add_needs": [], "remove_needs": [],
        "term_months": None, "budget": None, "reply": "", "question": None, "about": [], "sources": []}
    try:
        sid = advisor.start("en")["session_id"]
        advisor.message(sid, text="I run a pharmacy in Jaipur, we are 4 people. GSTIN 08EAHXC5550F1ZF")
        r = advisor.message(sid, text="yes, that's my shop")
    finally:
        advisor.assistant.llm_understand, advisor.assistant.worth_asking_llm = real_ask, real_worth
    check("typed \"yes, that's my shop\" confirms the GSTIN even when the AI repeats the number", r["profile"].get("gstin_verified")
          and not any("Is this your business" in m for m in r["messages"]), r["messages"])

    # Basic with as many services as the bundle is not "just the essentials"
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a pharmacy in Jaipur, 4 of us. UPI fails at rush hour and we had a theft last month. GSTIN 08EAHXC5550F1ZF")
    r = advisor.message(sid, slot="gstin_confirm", value="yes")
    for x in ("1", "phone hotspot"):
        r = advisor.message(sid, text=x)
    r = _to_bundle(sid, r)
    r = advisor.message(sid, text="this is too expensive")
    n = len(r["recommendation"]["quote"]["lines"])
    sid = advisor.start("en")["session_id"]
    for x in ("I run a pharmacy in Jaipur, we are 4 people. GSTIN 08EAHXC5550F1ZF", "yes, that's my shop", "1",
              "UPI fails at rush hour and we had a theft last month", "phone hotspot"):
        r2 = advisor.message(sid, text=x)
    check("problems told at the internet question, then \"phone hotspot\": the hotspot is still kept",
          advisor.store.get("session", sid)["profile"].get("current_internet") == "hotspot", r2["messages"][:2])
    check("...and she still sees the checklist, not an early bundle", r2.get("stage") == "needs" and r2.get("needs"), r2.get("stage"))
    check("price objection never offers a 'Basic' with the same number of services", f"({n} services)" not in r["messages"][1]
          and "cheaper" in values(r), r["messages"][1:])
    return sum(results), len(results)


if __name__ == "__main__":
    main()
