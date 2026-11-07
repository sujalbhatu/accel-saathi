"""Tokens, calls and rupees per conversation, from the passive call log (LLM_CALL_LOG=<file> while running a suite).

    LLM_CALL_LOG=calls.jsonl python -m tests.run_advisor_scenarios --llm
    python -m tests.eval.cost_report calls.jsonl [conversations]

Prices are public pay-as-you-go list prices in US$ per million tokens, as used below (state them when quoting a cost):
the free plans we run on cost nothing, so this is what the same traffic would cost on paid plans.
"""
import json
import statistics
import sys
from collections import defaultdict

PRICES = {  # (input, output) US$ per 1M tokens
    "openai/gpt-oss-120b": (0.15, 0.60),       # Groq list price
    "gemini-3.5-flash-lite": (0.30, 2.50),     # the app's own LLM_PRICE_IN / LLM_PRICE_OUT defaults
    "gemini-3.1-flash-lite": (0.30, 2.50),
}
USD_INR = 88


def main():
    calls = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8") if line.strip()]
    by_session = defaultdict(list)
    for c in calls:
        by_session[c.get("session") or "?"].append(c)
    convs = int(sys.argv[2]) if len(sys.argv) > 2 else len(by_session)
    usd = sum(c["tokens_in"] * PRICES.get(c["model"], (0.30, 2.50))[0] / 1e6 +
              c["tokens_out"] * PRICES.get(c["model"], (0.30, 2.50))[1] / 1e6 for c in calls)
    tin, tout = sum(c["tokens_in"] for c in calls), sum(c["tokens_out"] for c in calls)
    out = {"calls": len(calls), "conversations": convs, "calls_per_conversation": round(len(calls) / convs, 2),
           "tokens_in_per_call_median": statistics.median(c["tokens_in"] for c in calls),
           "tokens_out_per_call_median": statistics.median(c["tokens_out"] for c in calls),
           "tokens_per_conversation": round((tin + tout) / convs),
           "inr_per_conversation": round(usd * USD_INR / convs, 3),
           "inr_per_1000_conversations": round(usd * USD_INR / convs * 1000),
           "latency_ms_p50": statistics.median(c["ms"] for c in calls),
           "by_model": {m: sum(1 for c in calls if c["model"] == m) for m in sorted({c["model"] for c in calls})},
           "prices_usd_per_million": PRICES, "usd_inr": USD_INR}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
