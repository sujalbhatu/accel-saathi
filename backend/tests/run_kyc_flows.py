"""KYC flows through the API: an owner without a GSTIN needs only the signatory's ID and a recent bill, and any
document can be removed and replaced.

    python -m tests.run_kyc_flows
"""
import os
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY", "WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET"):
    os.environ[key] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "kyc_flows.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import advisor  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
RESULTS = []


def check(ok, label, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"   {detail}"))


def owner(opening):
    sid = advisor.start("en")["session_id"]
    advisor.message(sid, text=opening)
    client.post("/api/kyc/consent", json={"session_id": sid, "accepted": True, "whatsapp_updates": True})
    return sid


def main():
    print("Owner without a GSTIN:")
    sid = owner("I run a kirana store in Jaipur with 3 people, one shop, no GST")
    k = client.get(f"/api/kyc/{sid}").json()
    check(k["required"] == ["signatory_id", "address_proof"], "asks only for the signatory's ID and a bill", k["required"])
    k = client.post("/api/kyc/sample", json={"session_id": sid, "applicant": "K01"}).json()  # has a cancelled GSTIN
    client.post("/api/kyc/ekyc", json={"session_id": sid, "name": "Ramesh Kumar", "otp": "123456"})
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    codes = {c["code"]: c["status"] for c in r["checks"]}
    check(r["decision"] != "rejected" and codes.get("gst_not_needed") == "warn" and "gstin_inactive" not in codes,
          "a GST certificate they didn't need is set aside, not a reason to refuse", r["checks"][:3])
    k = client.post("/api/kyc/remove", json={"session_id": sid, "doc_type": "gst_certificate"}).json()
    check("gst_certificate" not in k["docs"] and k["result"] is None, "Remove takes the certificate back")
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    check(r["decision"] in ("approved", "review") and not any(c["code"] == "gst_not_needed" for c in r["checks"]),
          "after removing it, verification passes", [c["message"] for c in r["checks"] if c["status"] != "pass"])
    client.post("/api/kyc/remove", json={"session_id": sid, "doc_type": "address_proof"})
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    check(r["decision"] == "rejected" and any(c["code"] == "missing_document" and c["doc"] == "address_proof"
                                              for c in r["checks"]), "the bill is still required")

    print("\nOwner with a GSTIN:")
    sid = owner("Dental clinic in Pune, 8 staff, one clinic, we have GST")
    k = client.get(f"/api/kyc/{sid}").json()
    check(len(k["required"]) == 4, "asks for all four documents", k["required"])
    client.post("/api/kyc/sample", json={"session_id": sid, "applicant": "K01"})
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    check(any(c["code"] == "gstin_inactive" and c["status"] == "fail" for c in r["checks"]),
          "a cancelled GSTIN is still refused for a GST business")
    client.post("/api/kyc/sample", json={"session_id": sid, "applicant": "K02"})
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    check(r["decision"] in ("approved", "review"), "a clean applicant passes", r["decision"])

    print("\nGST business with no Udyam registration (Coral Medicals, Jaipur):")
    sid = advisor.start("en")["session_id"]
    r = advisor.message(sid, text="Pharmacy in Jaipur, 4 people, GSTIN 08EAHXC5550F1ZF")
    advisor.message(sid, slot=r["chips"][0]["slot"], value=r["chips"][0]["value"])  # "yes, that's mine"
    client.post("/api/kyc/consent", json={"session_id": sid, "accepted": True})
    k = client.get(f"/api/kyc/{sid}").json()
    check("udyam_certificate" not in k["required"], "Udyam isn't asked for when the registry has none", k["required"])
    client.post(f"/api/kyc/digilocker/{sid}")
    client.post("/api/kyc/ekyc", json={"session_id": sid, "name": "Priya Chauhan", "otp": "123456"})
    r = client.post(f"/api/kyc/verify/{sid}").json()["result"]
    check(r["decision"] == "approved" and any(c["code"] == "udyam_not_needed" for c in r["checks"]),
          "DigiLocker plus Aadhaar OTP verifies it", [c["message"] for c in r["checks"] if c["status"] != "pass"])

    print(f"\n{sum(RESULTS)}/{len(RESULTS)} KYC flow checks passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    main()
