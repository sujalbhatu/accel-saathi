"""Measures the advisor's knowledge retrieval and its AI answers, instead of assuming they work.

    cd backend && python -m tests.eval.run_rag_eval              # retrieval only: no network, seconds
    cd backend && python -m tests.eval.run_rag_eval --answers    # + AI answers (uses the .env keys, ~85 calls)

Questions: tests/eval/rag_questions.jsonl, owner questions in English, Hinglish and 9 Indian scripts, each labelled
with the knowledge chunk(s) that answer it (ids from app.knowledge.chunks()); "out_of_scope" questions have none.

Retrieval, for two variants of the same BM25 index:
  bm25         the owner's words as typed
  bm25+expand  what the app really sends: the words plus English terms for the intent and needs the rules engine
               understood (knowledge.expand), which is how Hindi or Tamil questions reach English documents
Metrics: recall@1 and recall@4 (a correct chunk in the top 1 / top 4; the AI is given the top 4) and MRR@10.

Answers (--answers), the AI step only (assistant.llm_understand, as the advisor calls it for a free-form question),
all judged by deterministic checks, no LLM judge:
  answered          a non-empty reply came back (the price guard empties a reply that quotes an unknown price)
  right_language    the reply is in the question's script (Latin for English and Hinglish)
  cites_gold        a returned source id is one of the labelled chunks
  unsupported_nums  numbers with a unit in the reply (₹, Mbps, GB, days, months, TB) that appear nowhere in the
                    retrieved chunks, the catalogue or the question: a proxy for invented facts
  declined          out-of-scope questions: no price quoted and no product claimed as the answer
Writes tests/eval/results/rag_eval.json and .md.
"""
import json
import os
import re
import statistics
import sys
import tempfile
import time

ANSWERS = "--answers" in sys.argv
if not ANSWERS:
    for key in ("LLM_API_KEY", "GROQ_API_KEY"):
        os.environ[key] = ""
else:
    from pathlib import Path
    env = Path(__file__).resolve().parents[3] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            k, _, v = line.partition("=")
            if k.strip() and not line.lstrip().startswith("#") and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip().strip('"')
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "rag_eval.db"))
sys.argv = sys.argv[:1]

from app import assistant, knowledge, llm  # noqa: E402
from app.data import products  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")
SCRIPT = {"en": r"[A-Za-z]", "hinglish": r"[A-Za-z]", "hi": r"[ऀ-ॿ]", "mr": r"[ऀ-ॿ]", "bn": r"[ঀ-৿]", "pa": r"[਀-੿]",
          "gu": r"[઀-૿]", "ta": r"[஀-௿]", "te": r"[ఀ-౿]", "kn": r"[ಀ-೿]", "ml": r"[ഀ-ൿ]"}
APP_LANG = {"hinglish": "hi"}
NUM_UNIT = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+)|([\d,.]+)\s*(?:mbps|gbps|gb|tb|days?|months?|din|दिन|महीने)", re.I)


def load():
    with open(os.path.join(HERE, "rag_questions.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ranked(q, variant):
    text = q["q"]
    if variant == "bm25":
        return [c["id"] for c in knowledge.search(text, k=10)]
    intent = assistant.rules_understand(text, "done").get("intent")
    return [c["id"] for c in knowledge.search(knowledge.expand(text, intent, assistant.needs_in(text)), k=10)]


def score(rows):
    if not rows:
        return {}
    r1 = sum(1 for r in rows if r["rank"] == 1) / len(rows)
    r4 = sum(1 for r in rows if r["rank"] and r["rank"] <= 4) / len(rows)
    mrr = sum(1 / r["rank"] for r in rows if r["rank"]) / len(rows)
    return {"n": len(rows), "recall@1": round(r1, 3), "recall@4": round(r4, 3), "mrr@10": round(mrr, 3)}


def retrieval(qs):
    out = {}
    for variant in ("bm25", "bm25+expand"):
        rows = []
        for q in qs:
            if not q["gold"]:
                continue
            ids = ranked(q, variant)
            rank = next((i + 1 for i, c in enumerate(ids) if c in q["gold"]), None)
            rows.append({"id": q["id"], "type": q["type"], "lang": q["lang"], "rank": rank, "top4": ids[:4]})
        out[variant] = {"all": score(rows),
                        "by_type": {t: score([r for r in rows if r["type"] == t]) for t in sorted({r["type"] for r in rows})},
                        "by_lang": {g: score([r for r in rows if r["lang"] == g]) for g in sorted({r["lang"] for r in rows})},
                        "misses": [r for r in rows if not r["rank"] or r["rank"] > 4]}
    return out


def _known_numbers(text):
    return {re.sub(r"[,.]0*$", "", (a or b).replace(",", "")) for a, b in NUM_UNIT.findall(text)} | \
        {n.replace(",", "") for n in re.findall(r"\d[\d,]*", text)}


def answers(qs):
    catalogue = " ".join(f"{p.name} {p.description} {p.price_min} {p.price_max} {p.setup_fee} {p.min_contract} "
                         f"{p.install_days}" for p in products().values())
    recs = []
    for q in qs:
        lang = APP_LANG.get(q["lang"], q["lang"])
        intent = assistant.rules_understand(q["q"], "done").get("intent")
        found = knowledge.search(knowledge.expand(q["q"], intent, assistant.needs_in(q["q"])), k=4)
        session = {"id": f"eval_{q['id']}", "profile": {}}
        t0 = time.monotonic()
        u = assistant.llm_understand(q["q"], lang, "done", None, {"business_type": "Pharmacy", "city": "Jaipur"}, None,
                                     [], intent=intent, session=session)
        ms = (time.monotonic() - t0) * 1000
        reply = (u or {}).get("reply") or ""
        sources = (u or {}).get("sources") or []
        allowed = _known_numbers(" ".join(c["text"] for c in found) + " " + catalogue + " " + q["q"])
        said = {re.sub(r"[,.]0*$", "", (a or b).replace(",", "")) for a, b in NUM_UNIT.findall(reply)}
        unsupported = sorted(n for n in said if n and n not in allowed)
        letters = re.findall(r"[^\W\d_]", re.sub(r"Accel|Saathi|GSTIN|GST|KYC|UPI|OTP|DigiLocker|Aadhaar|Udyam|WhatsApp|"
                                                 r"CCTV|Wi-?Fi|Mbps|SIM|IVR|SD-WAN|POS|AI", " ", reply))
        native = sum(1 for c in letters if re.match(SCRIPT[q["lang"]], c)) / len(letters) if letters else 0
        rec = {"id": q["id"], "type": q["type"], "lang": q["lang"], "q": q["q"], "reply": reply, "sources": sources,
               "ms": round(ms), "ai_answered": u is not None, "answered": bool(reply),
               "right_language": bool(reply) and native >= 0.6, "unsupported_numbers": unsupported,
               "cites_gold": bool(set(sources) & set(q["gold"])) if q["gold"] else None,
               "sources_retrieved": all(s in [c["id"] for c in found] for s in sources)}
        if q["type"] == "out_of_scope":
            rec["declined"] = bool(reply) and not re.search(r"₹|\brs\.?\s*\d", reply, re.I) and not sources
        recs.append(rec)
        print(f"  {q['id']:6s} {round(ms):5d} ms  {'ok ' if rec['answered'] else '-- '} {reply[:90]!r}", flush=True)
        time.sleep(1.2)  # stay inside the free plan's per-minute limit
    inscope = [r for r in recs if r["type"] != "out_of_scope"]
    oos = [r for r in recs if r["type"] == "out_of_scope"]
    ans = [r for r in recs if r["answered"]]
    pct = lambda xs: round(sum(1 for x in xs if x) / len(xs), 3) if xs else None  # noqa: E731
    summary = {
        "questions": len(recs), "ai_calls_answered": pct([r["ai_answered"] for r in recs]),
        "answered": pct([r["answered"] for r in inscope]),
        "right_language": pct([r["right_language"] for r in ans]),
        "cites_gold_when_answered": pct([r["cites_gold"] for r in inscope if r["answered"]]),
        "sources_were_retrieved": pct([r["sources_retrieved"] for r in ans]),
        "replies_with_unsupported_number": pct([bool(r["unsupported_numbers"]) for r in ans]),
        "out_of_scope_declined": pct([r.get("declined") for r in oos]),
        "latency_ms_p50": round(statistics.median([r["ms"] for r in recs])) if recs else None,
        "latency_ms_p95": round(sorted(r["ms"] for r in recs)[int(0.95 * (len(recs) - 1))]) if recs else None,
    }
    return summary, recs


def main():
    qs = load()
    os.makedirs(OUT, exist_ok=True)
    result = {"questions": len(qs), "chunks": len(knowledge.chunks()), "retrieval": retrieval(qs)}
    for v, r in result["retrieval"].items():
        print(f"{v:12s} {r['all']}")
        for t, s in r["by_type"].items():
            print(f"    {t:13s} {s}")
    if ANSWERS:
        if not llm.enabled():
            sys.exit("--answers needs LLM_API_KEY or GROQ_API_KEY")
        print("answers (AI on):")
        result["answers"], result["answer_records"] = answers(qs)
        print(json.dumps(result["answers"], indent=1))
    with open(os.path.join(OUT, "rag_eval.json" if ANSWERS else "retrieval_eval.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
