"""Run Smart KYC over every applicant in the specimen pack and print the decision and failed checks.
Usage: python -m tests.run_kyc_pack [--json out.json]"""
import glob
import json
import os
import sys
from collections import defaultdict

from app.kyc import extract_document, validate

DOCS = os.path.join(os.path.dirname(__file__), "..", "data", "kyc_documents")


def main():
    by_app = defaultdict(dict)
    for path in sorted(glob.glob(os.path.join(DOCS, "K*.png"))):
        name = os.path.basename(path)[:-4]
        app, declared = name.split("_", 1)
        by_app[app][declared] = extract_document(open(path, "rb").read(), declared)
    report = {}
    for app, docs in sorted(by_app.items()):
        res = validate(docs)
        report[app] = {"decision": res["decision"], "docs": {k: v["fields"] for k, v in docs.items()},
                       "sharpness": {k: v["sharpness"] for k, v in docs.items()},
                       "issues": [f"{c['status']}:{c['code']}: {c['message']}" for c in res["checks"] if c["status"] != "pass"]}
        print(app, res["decision"].upper())
        for i in report[app]["issues"]:
            print("   ", i)
    if "--json" in sys.argv:
        json.dump(report, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1, ensure_ascii=False)
    # the decision each specimen's planted problem calls for (deck annexure A4)
    expected = {"K01": "rejected", "K02": "approved", "K03": "approved", "K04": "rejected", "K05": "rejected",
                "K06": "rejected", "K07": "rejected", "K08": "approved", "K09": "approved", "K10": "review",
                "K11": "rejected", "K12": "approved"}
    right = [a for a, d in expected.items() if report.get(a, {}).get("decision") == d]
    print(f"{len(right)}/{len(expected)} KYC specimens judged as expected")
    return len(right) == len(expected)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
