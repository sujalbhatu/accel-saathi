"""Back-test of the recommendation on Accel's 368 activated customers (leave-one-out, see app/backtest.py).

    python -m tests.run_ranking_eval

Passes when the learned ranking beats both the hand-written rules and "recommend the most popular services" on
precision and on the F1 score, with bundles of the same size that follow the same catalogue rules.
"""
import os
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY", "DATA_KEY"):
    os.environ[key] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "eval.db"))

from app import backtest  # noqa: E402

NAMES = {"learned": "Learned from similar customers (this advisor)", "hand": "Hand-written rules by business type",
         "segment": "Most popular in the customer's segment", "popular": "Most popular across all customers"}


def main():
    r = backtest.run()
    print(f"Leave-one-out back-test on {r['customers']} activated customers: does the Recommended bundle match what each"
          " customer actually bought?\n")
    print(f"{'method':50s} precision  recall    F1")
    for m in ("learned", "hand", "segment", "popular"):
        x = r[m]
        print(f"{NAMES[m]:50s} {x['precision']:8.0%} {x['recall']:7.0%} {x['f1']:6.2f}")
    checks = [
        ("the learned ranking beats the hand-written rules (precision and F1)",
         r["learned"]["precision"] > r["hand"]["precision"] and r["learned"]["f1"] > r["hand"]["f1"]),
        ("the learned ranking beats 'most popular' (precision and F1)",
         r["learned"]["precision"] > r["popular"]["precision"] and r["learned"]["f1"] > r["popular"]["f1"]),
        ("about two in three recommended services are ones real customers bought", r["learned"]["precision"] >= 0.6),
    ]
    print()
    for label, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {label}")
    print(f"\n{sum(ok for _, ok in checks)}/{len(checks)} ranking checks passed")
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main()
