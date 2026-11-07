"""The same journey in all 10 languages, with the AI off (rules mode), so the "10 languages" claim is checked, not assumed.

    cd backend && python -m tests.run_language_checks

For each language: every string exists with the same {placeholders} as English; a pharmacy owner goes from her GSTIN to
a bundle by taps alone; every price is the catalogue's; the advisor's replies are written in that language's script
(not English left behind); and the selling taps (too expensive, another company, Basic, which documents) answer in that language too.
"""
import json
import os
import re
import sys
import tempfile

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "lang.db"))
os.environ.pop("LLM_API_KEY", None)
os.environ.pop("GROQ_API_KEY", None)
sys.argv = sys.argv[:1]  # the scenario suite reads its own flags on import

from app import advisor  # noqa: E402
from tests.run_advisor_scenarios import catalogue_checks  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOC = os.path.join(HERE, "..", "app", "locales")
SCRIPTS = {  # Unicode block of each language's script
    "en": r"[A-Za-z]", "hi": r"[ऀ-ॿ]", "mr": r"[ऀ-ॿ]", "bn": r"[ঀ-৿]",
    "pa": r"[਀-੿]", "gu": r"[઀-૿]", "ta": r"[஀-௿]", "te": r"[ఀ-౿]",
    "kn": r"[ಀ-೿]", "ml": r"[ഀ-ൿ]",
}
# words that stay as they are in every language: names, brands and codes
KEEP = re.compile(r"Coral Medicals|Jaipur|Accel(?: Saathi)?|GSTIN|GST|UPI|KYC|OTP|DigiLocker|Aadhaar|Udyam|WhatsApp|"
                  r"Active|Mbps|GB|CCTV|POS|Wi-?Fi|SIM|ID|IoT|SD-WAN|IVR|IP|4G|5G|Basic|Recommended|Complete", re.I)
PASS, FAIL = [], []


def check(lang, name, ok, detail=""):
    (PASS if ok else FAIL).append((lang, name))
    if not ok:
        print(f"  FAIL  [{lang}] {name}  {str(detail)[:160]}")


def native_share(text, lang):
    """Share of letters in the language's own script, after names and codes are taken out."""
    t = KEEP.sub(" ", text)
    letters = re.findall(r"[^\W\d_]", t)
    if not letters:
        return 1.0
    return sum(1 for c in letters if re.match(SCRIPTS[lang], c)) / len(letters)


def strings(lang):
    return json.load(open(os.path.join(LOC, f"{lang}.json"), encoding="utf-8"))["strings"]


def journey(lang):
    sid = advisor.start(lang)["session_id"]
    said = []
    r = advisor.message(sid, text="GSTIN 08EAHXC5550F1ZF")
    for _ in range(10):
        said += r["messages"]
        if r.get("recommendation"):
            break
        if r.get("needs"):
            keys = [n["key"] for n in r["needs"] if n["selected"]]
            r = advisor.message(sid, needs=keys)
            continue
        chips = r.get("chips") or []
        slot = chips[0].get("slot") if chips else None
        pick = {"gstin_confirm": "yes", "business_type": "Pharmacy", "employees": 3, "sites": 1, "current": "hotspot"}
        if slot not in pick:
            return sid, r, said, f"stuck at {slot}"
        r = advisor.message(sid, slot=slot, value=pick[slot])
    return sid, r, said, None


def main():
    en = strings("en")
    ph = {k: set(re.findall(r"\{(\w+)\}", v)) for k, v in en.items() if isinstance(v, str)}
    for lang in SCRIPTS:
        loc = strings(lang)
        missing = [k for k in en if k not in loc]
        check(lang, "every English string is translated", not missing, missing[:5])
        bad = [k for k, v in loc.items() if isinstance(v, str) and k in ph and set(re.findall(r"\{(\w+)\}", v)) != ph[k]]
        check(lang, "placeholders match English", not bad, bad[:5])

        sid, r, said, err = journey(lang)
        rec = r.get("recommendation")
        check(lang, "GSTIN to a bundle by taps alone", rec is not None and not err, err or r["messages"][-1:])
        if not rec:
            continue
        errs = catalogue_checks(rec, r["profile"])
        check(lang, "every price is the catalogue's", not errs, errs)
        low = [m for m in said if native_share(m, lang) < 0.6]
        check(lang, "every advisor reply is in the language's script", not low, low[:1])
        why = " ".join(str(v) for v in (rec.get("why") or {}).values()) if isinstance(rec.get("why"), dict) else str(rec.get("why") or "")
        check(lang, "\"why this bundle\" is in the language", native_share(why, lang) >= 0.6, why[:120])

        price = rec["quote"]["monthly"]
        r2 = advisor.message(sid, slot="refine", value="ask:obj_price")
        msgs = " ".join(r2.get("messages") or [])
        check(lang, "\"too expensive\" gets choices with prices, in the language, and nothing changes",
              "₹" in msgs and native_share(msgs, lang) >= 0.6 and r2["recommendation"]["quote"]["monthly"] == price,
              msgs[:140])
        rc = advisor.message(sid, slot="refine", value="ask:q_competitor")
        mc = " ".join(rc.get("messages") or [])
        check(lang, "\"another company is cheaper\" is answered in the language", mc and native_share(mc, lang) >= 0.6, mc[:140])
        r3 = advisor.message(sid, slot="refine", value="option:basic")
        q3 = r3.get("recommendation", {}).get("quote", {})
        check(lang, "Basic is one tap and still a valid catalogue bundle",
              q3.get("monthly", price) <= price and not catalogue_checks(r3["recommendation"], r3["profile"]), q3.get("monthly"))
        r4 = advisor.message(sid, slot="refine", value="ask:q_docs")
        m4 = " ".join(r4.get("messages") or [])
        check(lang, "\"which documents?\" is answered in the language", m4 and native_share(m4, lang) >= 0.6, m4[:140])

    langs = {l for l, _ in PASS + FAIL}
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} passed across {len(langs)} languages")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
