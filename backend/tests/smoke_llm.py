"""Live AI smoke test: a handful of messages (about 6 AI calls) through the real advisor, showing which model
answered each one. Run before a demo, not in a loop, so the free quotas stay for the judges.

    python -m tests.smoke_llm
"""
import os
import tempfile
import time

os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "smoke.db"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
from app import advisor, llm  # noqa: E402

print("route:", [f"{r['provider']}:{r['model']}" for r in llm._route("en")], "| other languages:",
      [f"{r['provider']}:{r['model']}" for r in llm._route("ta")][:2])
for lang, opening, follow in [
    ("en", "We are a small physiotherapy clinic in Pune, 6 of us, one clinic, no GST yet", "do you also do websites?"),
    ("hi", "मेरी जयपुर में दवाइयों की दुकान है, 4 लोग, एक दुकान, GST नहीं है", "क्या मुझे CCTV की ज़रूरत है?"),
    ("ta", "சென்னையில் என் பூட்டிக் கடை, 3 பேர், ஒரு கடை, GST இல்லை", "இணையம் நின்றால் என்ன ஆகும்?"),
]:
    sid = advisor.start(lang)["session_id"]
    t0 = time.monotonic()
    r = advisor.message(sid, text=opening)
    print(f"\n[{lang}] {opening}\n  -> {r['messages'][-1][:140]}  ({time.monotonic() - t0:.1f}s)")
    for _ in range(4):  # answer the remaining questions by tapping the first chip, then confirm the needs
        if r.get("recommendation"):
            break
        if r.get("needs"):
            r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]])
        elif r.get("chips"):
            c = r["chips"][0]
            r = advisor.message(sid, slot=c["slot"], value=c["value"])
    t0 = time.monotonic()
    r = advisor.message(sid, text=follow)
    print(f"  {follow}\n  -> {' | '.join(m[:160] for m in r['messages'])}  ({time.monotonic() - t0:.1f}s)")
print("\nAI usage this month:", llm.usage())
