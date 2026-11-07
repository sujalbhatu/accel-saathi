"""What a real owner did on 7 Nov, replayed, plus the four other ways it went wrong (AI off, rules mode).

    cd backend && python -m tests.run_chat_fixes

A. Asking for a language ("talk in English", "Hindi mai baat karo", in any of the 10) switches the chat and it stays.
B. A reply that talks about the chat is never saved as the business type or the city.
C. "What?" at the checklist explains it instead of repeating it.
D. "I want all of them" ticks every service.
E. Ticking every service and tapping Continue works (the tapped text used to be refused past 300 characters).
"""
import os
import re
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY"):
    os.environ[key] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "chat_fixes.db"))
sys.argv = sys.argv[:1]

from fastapi.testclient import TestClient  # noqa: E402

from app import advisor, assistant, store  # noqa: E402
from app.i18n import t  # noqa: E402
from app.main import app  # noqa: E402

PASS, FAIL = [], []
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def check(ok, label, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  ok    " if ok else "  FAIL  ") + label + ("" if ok else f"  {str(detail)[:200]}"))


def said(r):
    return " ".join(r["messages"])


def replay_sujal():
    print("A + B: the 7 Nov conversation, replayed")
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="Kya mai hindi mai baat kar sakta hu")
    check(r["lang"] == "hi" and t("hi", "lang_switched") in r["messages"], "asked for Hindi: the chat switches to Hindi", r)
    check(r["profile"]["business_type"] == "", "the request is not saved as the business type", r["profile"])
    r = advisor.message(sid, text="Englishe karna chahta hu")
    check(r["lang"] == "en" and t("en", "lang_switched") in r["messages"], "'Englishe karna chahta hu' switches to English", r)
    check(r["profile"]["business_type"] == "", "...and is not saved as the business type", r["profile"])
    check(not DEVANAGARI.search(said(r)), "the next question is in English", said(r))
    r = advisor.message(sid, text="तो टॉक इन इंग्लिश")
    check(r["lang"] == "en" and r["profile"]["city"] == "" and r["profile"]["business_type"] == "",
          "'तो टॉक इन इंग्लिश' keeps English and is saved as nothing", r["profile"])
    r = advisor.message(sid, text="हे आई वांटेड टू टॉक इन इंग्लिश")
    check(r["lang"] == "en" and not DEVANAGARI.search(said(r)), "asked again in Devanagari: still English, no Hindi question",
          said(r))
    r = advisor.message(sid, text="I run a pharmacy")
    check(r["profile"]["business_type"].lower() == "pharmacy" and r["lang"] == "en", "then her real answer is kept", r["profile"])
    r = advisor.message(sid, text="can you help me?")
    check(r["profile"]["city"] == "", "'can you help me?' is not saved as the city", r["profile"])
    r = advisor.message(sid, text="Jaipur")
    check(r["profile"]["city"] == "Jaipur", "'Jaipur' is", r["profile"])
    for slot, value in (("employees", 3), ("sites", 1)):
        r = advisor.message(sid, slot=slot, value=value, display=str(value))
    r = advisor.message(sid, text="No I don't have")
    r = advisor.message(sid, text="Phone hotspot")
    check(r["stage"] == "needs" and not DEVANAGARI.search(said(r)), "the whole chat stayed in English up to the checklist",
          said(r))
    return sid


def confused_and_all(sid):
    print("C + D: at the checklist")
    before = advisor.message(sid, text="What?")
    check(t("en", "unsure_needs") in before["messages"] and before["stage"] == "needs" and before.get("needs"),
          "'What?' explains the checklist and shows it again", before["messages"])
    check(t("en", "ask_needs") not in before["messages"], "...instead of repeating the same sentence", before["messages"])
    for q in ("I don't understand", "samjha nahi", "समझ नहीं आया"):
        check(assistant.confused(q), f"'{q}' is understood as confusion")
    for q in ("what is CCTV?", "Pharmacy", "all of them"):
        check(not assistant.confused(q), f"'{q}' is not")
    offered = {n["key"] for n in before["needs"]}
    r = advisor.message(sid, text="I want all of them")
    lines = {l["need"] for l in r["recommendation"]["quote"]["lines"] if l.get("need")} if r.get("recommendation") else set()
    s = store.get("session", sid)
    check(r["stage"] == "done" and set(s["profile"]["needs"]) >= offered, "'I want all of them' ticks every offered service",
          (r["stage"], sorted(offered - set(s["profile"]["needs"]))))
    check(len(r["recommendation"]["quote"]["lines"]) > 6, "...and the bundle has them all, not just 3",
          len(r["recommendation"]["quote"]["lines"]))
    del lines
    for q, want in (("sab chahiye", True), ("select everything", True), ("सब चाहिए", True), ("not all of them", False),
                    ("all except CCTV", False), ("do I need all of them?", False)):
        check(assistant.wants_all(q) == want, f"'{q}' {'means' if want else 'does not mean'} everything")


def language_requests():
    print("A: language requests in all 10 languages, and look-alikes that are not")
    asks = {"en": "please talk in English", "hi": "Hindi mai baat karo", "mr": "मराठीत बोला", "kn": "ಕನ್ನಡದಲ್ಲಿ ಮಾತನಾಡಿ",
            "gu": "ગુજરાતીમાં વાત કરો", "te": "తెలుగులో మాట్లాడండి", "ta": "தமிழில் பேசுங்கள்", "bn": "বাংলায় কথা বলুন",
            "pa": "ਪੰਜਾਬੀ ਵਿੱਚ ਗੱਲ ਕਰੋ", "ml": "മലയാളത്തിൽ സംസാരിക്കൂ"}
    for code, q in asks.items():
        check(assistant.language_request(q) == code, f"'{q}' -> {code}", assistant.language_request(q))
        sid = advisor.start("en" if code != "en" else "hi")["session_id"]
        r = advisor.message(sid, text=q)
        check(r["lang"] == code and r["messages"][0] == t(code, "lang_switched"), f"the chat switches to {code}", r["messages"])
    for q in ("Hindi", "English please", "can you talk in tamil"):
        check(assistant.language_request(q) is not None, f"'{q}' is a request")
    for q in ("I run an English coaching centre in Pune", "Hindi books shop", "English speaking course institute",
              "we sell Tamil sarees", "Pharmacy in Jaipur", "most of my customers speak Marathi"):
        check(assistant.language_request(q) is None, f"'{q}' is not a language request", assistant.language_request(q))
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run an English coaching centre in Pune")
    check(r["lang"] == "en" and r["profile"]["business_type"] != "" and r["profile"]["city"] == "Pune",
          "an English coaching centre is a business, not a request", r["profile"])
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="I run a pharmacy in Jaipur with 4 staff, please talk in Hindi")
    check(r["lang"] == "hi" and r["profile"]["city"] == "Jaipur" and r["profile"]["employees"] == 4,
          "facts and a language request in one line: switch to Hindi and keep the facts", r["profile"])
    r = advisor.message(sid, text="1")
    check(r["lang"] == "hi", "a bare number afterwards keeps Hindi", r["lang"])


def select_all_over_api():
    print("E: ticking every service over the API")
    c = TestClient(app)
    sid = c.post("/api/advisor/start", json={"lang": "hi"}).json()["session_id"]
    c.post("/api/advisor/message", json={"session_id": sid, "text": "GSTIN 08EAHXC5550F1ZF"})
    for _ in range(8):
        s = store.get("session", sid)
        if s["stage"] == "needs":
            break
        if s.get("pending_slot") == "gstin_confirm":
            c.post("/api/advisor/message", json={"session_id": sid, "slot": "gstin_confirm", "value": "yes"})
        elif s.get("pending_slot") == "current":
            c.post("/api/advisor/message", json={"session_id": sid, "slot": "current", "value": "hotspot"})
        elif s.get("pending_slot") in ("employees", "sites"):
            c.post("/api/advisor/message", json={"session_id": sid, "slot": s["pending_slot"], "value": 3 if s["pending_slot"] == "employees" else 1})
        else:
            c.post("/api/advisor/message", json={"session_id": sid, "text": "Pharmacy"})
    s = store.get("session", sid)
    check(s["stage"] == "needs", "reached the checklist", s["stage"])
    needs = advisor._needs_payload(advisor._profile(s), "hi")["needs"]
    display = ", ".join(n["label"] for n in needs) * 3  # longer than any real list
    r = c.post("/api/advisor/message", json={"session_id": sid, "needs": [n["key"] for n in needs], "display": display})
    check(r.status_code == 200 and r.json()["stage"] == "done", f"every service ticked ({len(display)} characters of labels): accepted",
          (r.status_code, r.text[:200]))
    last_user = [m for m in store.get("session", sid)["history"] if m["role"] == "user"][-1]["text"]
    check(len(last_user) <= 320 and "+" in last_user, "the chat history keeps a short version", last_user)


def main():
    sid = replay_sujal()
    confused_and_all(sid)
    language_requests()
    select_all_over_api()
    print(f"\n{len(PASS)}/{len(PASS) + len(FAIL)} chat-fix checks passed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
