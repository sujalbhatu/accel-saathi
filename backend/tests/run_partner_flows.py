"""Partner-assisted selling through the API: a partner starts the chat, the owner consents by a code on her own
phone, the sale is credited to the partner, and her verified number stays protected for 30 days.

    python -m tests.run_partner_flows
"""
import os
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY", "WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET"):
    os.environ[key] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "partner_flows.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import advisor, store  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
RESULTS = []
OWNER, OTHER = "9876511111", "9876522222"


def check(ok, label, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"   {detail}"))


def chat_to_quote(sid):
    r = advisor.message(sid, text="I run a pharmacy in Pune with 4 people, one shop, we have GST")
    r = advisor.message(sid, slot="current", value="hotspot")
    for _ in range(5):
        if r.get("recommendation"):
            break
        if r.get("needs"):
            r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]])
        else:
            r = advisor.message(sid, slot=r["chips"][0].get("slot"), value=r["chips"][0]["value"])
    assert r.get("recommendation"), r["messages"]
    return r["recommendation"]["quote"]


def order(sid, phone, consent=True):
    q = chat_to_quote(sid)
    k = store.get("kyc", sid) or {"session_id": sid, "consent": {"accepted": True, "at": store.now()}, "docs": {}}
    k["result"] = {"decision": "approved", "checks": []}
    store.put("kyc", sid, k)
    res = client.post("/api/orders", json={
        "session_id": sid, "selection": [{"id": l["id"], "qty": l["qty"]} for l in q["lines"]], "contract_months": 12,
        "contact_name": "Sunita Sharma", "phone": phone, "whatsapp_updates": True, "esign_otp": "123456"})
    assert res.status_code == 200, res.text
    return res.json(), q


def main():
    print("Assisted session:")
    check(client.post("/api/assist/start", json={"partner_id": "PT99"}).status_code == 404, "an unknown partner is refused")
    a = client.post("/api/assist/start", json={"partner_id": "pt01", "lang": "mr"}).json()
    sid = a["session_id"]
    check(a["partner"]["id"] == "PT01" and a["partner"]["mode"] == "assisted" and a["join_url"].endswith(f"#/continue/{sid}")
          and "/#/" in a["join_url"] and "//#" not in a["join_url"], "starts a chat credited to PT01, with a link to carry on", a)
    r = client.post("/api/kyc/consent", json={"session_id": sid, "accepted": True})
    check(r.status_code == 403, "the partner can't give consent for the owner", r.text)
    c = client.post("/api/assist/owner-code", json={"session_id": sid, "phone": OWNER}).json()
    check(c["delivery"] == "demo" and len(c.get("demo_code", "")) == 6 and c["phone_masked"].endswith("1111"),
          "a code goes to the owner's phone (shown on screen only in the demo)", c)
    bad = "000000" if c["demo_code"] != "000000" else "111111"
    r = client.post("/api/kyc/consent", json={"session_id": sid, "accepted": True, "owner_code": bad})
    check(r.status_code == 403, "a wrong code is refused")
    r = client.post("/api/kyc/consent", json={"session_id": sid, "accepted": True, "owner_code": c["demo_code"]})
    check(r.status_code == 200 and "assisted by PT01" in r.json()["consent"]["given_by"], "the owner's code records her consent",
          r.text[:200])
    check(client.get(f"/api/advisor/{sid}").json()["partner"]["owner_verified"], "the app shows the owner is verified")
    o, q = order(sid, OWNER)
    stored = store.get("order", o["id"])["partner"]
    check(stored["via"] == "assisted" and stored["commission"] == round(q["monthly"])
          and stored["first"] + stored["retained"] == stored["commission"], "the order is credited to PT01: one month's rental, in two halves", stored)
    check(o["partner"] == {"id": "PT01", "name": "Shree Telecom Solutions"}, "the owner's tracker names the partner, not the commission", o["partner"])

    print("\nCommission protection:")
    sid2 = advisor.start("en")["session_id"]
    o2, _ = order(sid2, OWNER)
    check(store.get("order", o2["id"])["partner"]["via"] == "protected", "she orders alone a week later: still PT01's sale")
    sid3 = advisor.start("en")["session_id"]
    o3, _ = order(sid3, OTHER)
    check(store.get("order", o3["id"])["partner"] is None, "another shop's order isn't credited to anyone")
    a4 = client.post("/api/assist/start", json={"partner_id": "PT03"}).json()
    client.post("/api/assist/owner-code", json={"session_id": a4["session_id"], "phone": OTHER})
    sid5 = advisor.start("en")["session_id"]
    o5, _ = order(sid5, OTHER)
    check(store.get("order", o5["id"])["partner"] is None, "a number typed in but never confirmed by its owner earns nothing")
    a6 = client.post("/api/assist/start", json={"partner_id": "PT02"}).json()
    code6 = client.post("/api/assist/owner-code", json={"session_id": a6["session_id"], "phone": OTHER}).json()["demo_code"]
    wrong = [f"{i:06d}" for i in range(7) if f"{i:06d}" != code6][:5]
    for w in wrong:
        client.post("/api/kyc/consent", json={"session_id": a6["session_id"], "accepted": True, "owner_code": w})
    r = client.post("/api/kyc/consent", json={"session_id": a6["session_id"], "accepted": True, "owner_code": code6})
    check(r.status_code == 403, "after 5 wrong tries even the right code stops working", r.status_code)

    print("\nReferral QR:")
    r = client.post("/api/advisor/start", json={"lang": "en", "ref": "PT04"}).json()
    check(r["partner"]["mode"] == "referral", "?ref=PT04 tags the chat to Sabarmati Networks", r.get("partner"))
    o7, _ = order(r["session_id"], "9876533333")
    check(store.get("order", o7["id"])["partner"]["via"] == "referral", "and the order is theirs")
    r = client.post("/api/advisor/start", json={"lang": "en", "ref": "XX"}).json()
    check("partner" not in r, "an unknown referral code is ignored")

    print("\nConsole:")
    rows = {p["id"]: p for p in client.get("/api/console/partners").json()}
    check(rows["PT01"]["orders"] == 2 and rows["PT01"]["protected_orders"] == 1 and rows["PT01"]["assisted"] == 1
          and rows["PT01"]["pending"] > 0 and rows["PT01"]["earned"] == 0, "PT01 shows 2 sales, 1 protected, commission pending", rows["PT01"])
    print(f"\n{sum(RESULTS)}/{len(RESULTS)} partner checks passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    main()
