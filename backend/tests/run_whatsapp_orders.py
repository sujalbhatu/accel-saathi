"""WhatsApp order suite: an update at every tracker stage, and STATUS / RESCHEDULE / PROBLEM replies, through the
real API and webhook handler.

    python -m tests.run_whatsapp_orders

Runs without WhatsApp or AI keys (it blanks them, so a laptop .env with real keys never sends anything); the live
sending path is checked with Meta's API replaced by a stand-in that answers like Meta does.
"""
import hashlib
import hmac
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

for key in ("LLM_API_KEY", "GROQ_API_KEY", "WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET",
            "WA_TEMPLATE_ORDER_UPDATE", "APP_URL"):
    os.environ[key] = ""  # set but empty: load_dotenv never overrides it
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "wa_orders.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app import advisor, orders, store, whatsapp  # noqa: E402
from app.i18n import t  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
RESULTS: list[tuple[bool, str]] = []
PHONE, WA = "9876543210", "919876543210"  # the number given at checkout, and the same number as WhatsApp sends it
CHAT = "910000000001"  # the in-app WhatsApp screen the owner started on
STRANGER, NEWBIE = "919811111111", "910000000002"


def check(ok, label: str, detail: str = "") -> bool:
    RESULTS.append((bool(ok), label))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"   {detail}"))
    return bool(ok)


def payload(wa: str, text: str | None = None, reply: tuple | None = None, kind: str = "button_reply",
            msg_id: str | None = None, number_id: str | None = None) -> dict:
    payload.n = getattr(payload, "n", 0) + 1
    msg = {"from": wa, "id": msg_id or f"wamid.test{payload.n}"}
    if text is not None:
        msg.update(type="text", text={"body": text})
    else:
        msg.update(type="interactive", interactive={"type": kind, kind: {"id": reply[0], "title": reply[1]}})
    value = {"messages": [msg]}
    if number_id:
        value["metadata"] = {"phone_number_id": number_id}
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": value}]}]}


def wa(wa_id: str, text: str | None = None, reply: tuple | None = None, kind: str = "button_reply") -> list[dict]:
    """A message from a phone, as Meta's webhook delivers it (demo mode: the replies come back in the response)."""
    r = client.post("/api/whatsapp/webhook", json=payload(wa_id, text, reply, kind))
    assert r.status_code == 200, r.text
    return r.json()["sent"]


def demo(wa_id: str, text: str) -> list[dict]:
    """A message typed in the in-app WhatsApp screen."""
    r = client.post("/api/whatsapp/demo", json=payload(wa_id, text))
    assert r.status_code == 200, r.text
    return r.json()["sent"]


def body(m: dict) -> str:
    if m["type"] == "text":
        return m["text"]["body"]
    return m["interactive"]["body"]["text"]


def all_text(msgs: list[dict]) -> str:
    return "\n".join(body(m) for m in msgs)


def buttons(m: dict) -> list[str]:
    return [b["reply"]["id"] for b in m.get("interactive", {}).get("action", {}).get("buttons", [])]


def rows(m: dict) -> list[dict]:
    return [r for sec in m.get("interactive", {}).get("action", {}).get("sections", []) for r in sec["rows"]]


def order_now(oid: str) -> dict:
    return client.get(f"/api/orders/{oid}").json()


def place_order(chat_wa: str, phone: str, opening: str) -> dict:
    """An owner starts on WhatsApp, continues in the app (same session), passes KYC and orders."""
    demo(chat_wa, opening)
    sid = store.get("wa_link", chat_wa)["session_id"]
    r = advisor.message(sid, slot="current", value="hotspot")
    for _ in range(4):
        if r.get("recommendation"):
            break
        if r.get("needs"):
            r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]])
        else:
            slot = (r.get("chips") or [{}])[0].get("slot")
            r = advisor.message(sid, slot=slot, value=(r["chips"][0]["value"]))
    assert r.get("recommendation"), r["messages"]
    store.put("kyc", sid, {"session_id": sid, "consent": {"at": store.now()}, "docs": {},
                           "result": {"decision": "approved", "checks": []}})
    lines = r["recommendation"]["quote"]["lines"]
    res = client.post("/api/orders", json={
        "session_id": sid, "selection": [{"id": l["id"], "qty": l["qty"]} for l in lines], "contract_months": 12,
        "contact_name": "Sunita Sharma", "phone": phone, "whatsapp_updates": True, "esign_otp": "123456"})
    assert res.status_code == 200, res.text
    return res.json()


def main():
    print("Demo screen and signatures:")
    r = client.post("/api/whatsapp/demo", json=payload("919876500000", "hi"))
    check(r.status_code == 400, "the in-app WhatsApp screen can't pose as a real number", r.text)
    os.environ["WA_APP_SECRET"] = "test-secret"
    raw = json.dumps(payload(NEWBIE, "hi")).encode()
    r = client.post("/api/whatsapp/webhook", content=raw, headers={"content-type": "application/json"})
    check(r.status_code == 401, "with an app secret set, an unsigned webhook is refused", str(r.status_code))
    sig = "sha256=" + hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
    r = client.post("/api/whatsapp/webhook", content=raw,
                    headers={"content-type": "application/json", "x-hub-signature-256": sig})
    check(r.status_code == 200, "a webhook signed with the app secret is accepted", str(r.status_code))
    r = client.post("/api/whatsapp/demo", json=payload(NEWBIE, "hello"))
    check(r.status_code == 200, "the in-app screen still works when the app secret is set", r.text[:100])
    os.environ["WA_APP_SECRET"] = ""

    print("\nOrder placed from a chat that started on WhatsApp:")
    o = place_order(CHAT, PHONE, "I run a pharmacy in Jaipur with 4 people, one shop, no GST")
    oid = o["id"]
    check(o["stage"] == "esigned", "order starts e-signed", o["stage"])
    check(PHONE not in json.dumps(o) and o["contact"]["phone_masked"].endswith("3210"),
          "the order never shows the full phone number", o["contact"])
    check((store.get("order_contact", oid) or {}).get("wa") == WA, "updates go to the number given at checkout")
    check(oid in whatsapp._my_orders(WA) and oid in whatsapp._my_orders(CHAT),
          "both the checkout number and the chat it was bought from can ask about it")
    n0 = o["notifications"][0]
    check(oid in o["notifications"][-1]["text"] and n0.get("delivery") == "demo",
          "'order received' first; the latest update is marked as a WhatsApp preview without keys", n0)
    check(len(o["notifications"]) == 3 and sum("delivery" in n for n in o["notifications"]) == 1,
          "placed, KYC and e-sign show in the tracker, but WhatsApp gets one message, not three", o["notifications"])
    check(all(st["label"] == t("en", f"st_{st['key']}") for st in o["steps"]), "tracker steps come from the locale")
    check(all(it.get("plain") for it in o["items"]), "tracker items carry plain names")
    day = datetime.now(orders.IST).date() + timedelta(days=2)
    day += timedelta(days=1) if day.weekday() == 6 else timedelta(0)
    check(len(o["slots"]) == 6 and not any(x.startswith("Sun") for x in o["slots"])
          and o["slots"][0].startswith(f"{day:%a} {day.day} {day:%b},"),
          "six installation slots from the day after tomorrow, no Sundays", o["slots"])

    print("\nSTATUS:")
    m = wa(WA, "STATUS")
    check(len(m) == 1 and oid in body(m[0]) and buttons(m[0]) == [f"ord:status:{oid}", f"ord:resched:{oid}",
                                                                    f"ord:problem:{oid}"],
          "STATUS gives the order, its stage and three buttons", m)
    m = wa(WA, "where is my connection? kab tak lagega")
    check(m and oid in body(m[0]), "'where is my connection' is a status question", all_text(m)[:120])
    m = demo(CHAT, "status")
    check(m and oid in body(m[0]), "the in-app WhatsApp chat it was bought from gets the status too")
    m = wa(WA, "स्टेटस बताओ")
    check(m and oid in body(m[0]), "Hindi 'स्टेटस' works", all_text(m)[:80])
    m = wa(WA, "staus")
    check(m and oid in body(m[0]), "a typo like 'staus' still gets the status", all_text(m)[:80])
    m = wa(WA, "track my order")
    check(m and oid in body(m[0]), "'track my order' answers with the status")
    m = wa(WA, reply=(f"ord:status:{oid}", "Order status"))
    check(m and oid in body(m[0]), "the Order status button works")

    print("\nOther numbers learn nothing:")
    m = wa(STRANGER, "status")
    check(all_text(m) == t("en", "wa_no_order"), "'status' from a number with no orders says there is none",
          all_text(m)[:120])
    m = wa(STRANGER, "what is the status of fibre in my area, I run a shop")
    check(oid not in all_text(m) and t("en", "wa_no_order") not in all_text(m),
          "a longer message with 'status' from a new owner goes to the advisor", all_text(m)[:120])
    m = wa(STRANGER, f"what about {oid}?")
    check(all_text(m) == t("en", "wa_no_order"), "someone else's order number gets 'no order for this number'",
          all_text(m)[:120])
    m = wa(STRANGER, reply=(f"ord:status:{oid}", "Order status"))
    check(all_text(m) == t("en", "wa_no_order"), "someone else's order button gets the same", all_text(m)[:120])
    m = wa(STRANGER, reply=(f"ord:slot:{oid}:1", "Mon"), kind="list_reply")
    check(order_now(oid)["slot"] is None and all_text(m) == t("en", "wa_no_order"),
          "someone else can't move the slot")
    m = demo(NEWBIE, "my current internet is not working well, I need a new connection for my shop")
    check(t("en", "wa_no_order") not in all_text(m) and m, "a new owner's 'not working' goes to the advisor",
          all_text(m)[:120])
    m = demo(NEWBIE, "help")
    check(t("en", "wa_no_order") not in all_text(m) and m, "'help' from a new owner goes to the advisor")

    print("\nRESCHEDULE:")
    m = wa(WA, "I want to reschedule")
    slots = orders.next_slots()
    check(len(m) == 1 and [r["id"] for r in rows(m[0])] == [f"ord:slot:{oid}:{i}" for i in range(len(slots))]
          and all(len(r["title"]) <= 24 for r in rows(m[0])), "RESCHEDULE lists the same slots as the app", m)
    m = wa(WA, reply=(f"ord:slot:{oid}:1", slots[1][:24]), kind="list_reply")
    o = order_now(oid)
    check(o["slot"] == slots[1] and o["stage"] == "scheduled" and slots[1] in all_text(m),
          "picking a slot books it and moves the order to scheduled", (o["slot"], o["stage"], all_text(m)))
    check(slots[1] in o["notifications"][0]["text"] and o["notifications"][0].get("delivery") == "demo",
          "the tracker shows the booking, sent to WhatsApp", o["notifications"][0])
    m = wa(WA, "can I change the time to another day")
    m = wa(WA, reply=(f"ord:slot:{oid}:0", slots[0][:24]), kind="list_reply")
    o = order_now(oid)
    check(o["slot"] == slots[0] and o["notifications"][0]["text"] == t("en", "stm_rescheduled", slot=slots[0]),
          "a second change says 'moved to'", o["notifications"][0]["text"])

    print("\nPROBLEM:")
    m = wa(WA, "internet not working since morning")
    o = order_now(oid)
    check(len(o["tickets"]) == 1 and "T001" in all_text(m), "a problem described in one message is logged at once",
          all_text(m))
    m = wa(WA, "PROBLEM")
    check(all_text(m) == t("en", "wa_problem_ask"), "PROBLEM alone asks what is wrong")
    m = wa(WA, "router light is red")
    o = order_now(oid)
    check(len(o["tickets"]) == 2 and o["tickets"][-1]["text"] == "router light is red" and "T002" in all_text(m),
          "the next message is the description", o["tickets"])
    m = wa(WA, reply=(f"ord:problem:{oid}", "Report a problem"))
    m = wa(WA, "status")
    o = order_now(oid)
    check(len(o["tickets"]) == 2 and oid in all_text(m), "a short 'status' after PROBLEM is a status question")
    m = wa(WA, "thanks, we also want CCTV cameras later")
    o = order_now(oid)
    check(len(o["tickets"]) == 2, "after that, chat goes back to the advisor, not into a ticket", o["tickets"])
    wa(WA, "problem")
    link = store.get("wa_link", WA)
    link["awaiting_since"] = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    store.put("wa_link", WA, link)
    wa(WA, "we are thinking of adding a second branch next year")
    check(len(order_now(oid)["tickets"]) == 2, "a PROBLEM left unanswered for 30 minutes expires")

    print("\nAn update at every stage:")
    sent_before = sum("delivery" in n for n in order_now(oid)["notifications"])
    for _ in range(12):
        o = client.post(f"/api/orders/{oid}/advance").json()
        if o["stage"] == "activated":
            break
    texts = [n["text"] for n in o["notifications"]]
    check(o["stage"] == "activated" and all(it["status"] == "live" for it in o["items"]),
          "the order reaches 'all services live'", o["stage"])
    check(not any("stm_" in x or "{" in x for x in texts), "every update is real text, no raw keys", texts[:3])
    check(sum("delivery" in n for n in o["notifications"]) - sent_before >= len(o["items"]) + 1,
          "each stage and each service going live is sent to WhatsApp", len(texts))
    check(o["slots"] == [] and "wamid" not in json.dumps(o), "no slots after installation; no message ids shown")
    m = wa(WA, "reschedule")
    check(all_text(m) == t("en", "wa_resched_late"), "RESCHEDULE after installation explains why not",
          all_text(m))
    m = wa(WA, reply=(f"ord:slot:{oid}:3", "x"), kind="list_reply")
    check(order_now(oid)["slot"] == slots[0] and all_text(m) == t("en", "wa_resched_late"),
          "an old slot button can't move a finished installation")

    print("\nDuplicates and delivery receipts:")
    p = payload(WA, "STATUS", msg_id="wamid.same")
    first, again = client.post("/api/whatsapp/webhook", json=p).json(), client.post("/api/whatsapp/webhook", json=p).json()
    check(first["sent"] and again["sent"] == [], "a webhook Meta re-sends is answered once")
    order = store.get("order", oid)
    order["notifications"][0]["wamid"] = "wamid.UPD1"
    store.put("order", oid, order)
    store.put("wa_message", "wamid.UPD1", {"order": oid})
    for status in ("delivered", "read", "delivered"):
        client.post("/api/whatsapp/webhook", json={"entry": [{"changes": [{"value": {
            "statuses": [{"id": "wamid.UPD1", "status": status}]}}]}]})
    check(order_now(oid)["notifications"][0]["delivery"] == "read",
          "the tracker shows 'read' from Meta's receipts, even when they arrive out of order")

    print("\nLive sending (Meta's API replaced by a stand-in):")
    calls, answers = [], []

    def fake_post(b):
        calls.append(b)
        return answers.pop(0) if answers else {"ok": True, "code": None, "id": f"wamid.live{len(calls)}"}

    real_post = whatsapp._post
    whatsapp._post = fake_post
    os.environ.update(WA_ACCESS_TOKEN="x", WA_PHONE_NUMBER_ID="PN1")
    try:
        o2 = place_order("910000000003", "9123456780", "Salon in Indore, 6 people, one shop, no GST")
        sent_to = [c["to"] for c in calls]
        check(sent_to == ["919123456780"] and o2["notifications"][0].get("delivery") == "sent",
              "live: 'order received' goes to the checkout number on WhatsApp", sent_to)
        check(store.get("wa_message", "wamid.live1") == {"order": o2["id"]}, "live: Meta's message id is kept")
        n = len(calls)
        demo("910000000003", "status")
        check(len(calls) == n, "live: the in-app screen still never sends to Meta")
        r = client.post("/api/whatsapp/webhook", json=payload("919123456780", "STATUS", number_id="PN1"))
        check(r.json() == {"ok": True} and len(calls) == n + 1 and o2["id"] in body(calls[-1]),
              "live: Meta gets an immediate 200 and the reply goes out through the API", r.json())
        r = client.post("/api/whatsapp/webhook", json=payload("919123456780", "STATUS", number_id="OTHER"))
        check(len(calls) == n + 1, "live: messages for another number on the account are ignored")
        answers[:] = [{"ok": False, "code": 131047}]
        os.environ["WA_TEMPLATE_ORDER_UPDATE"] = "order_update"
        o3 = client.post(f"/api/orders/{o2['id']}/advance").json()
        check(o3["notifications"][0].get("delivery") == "template" and calls[-1]["type"] == "template",
              "live: outside the 24-hour window the approved template is used", calls[-1].get("type"))
        answers[:] = [{"ok": False, "code": 131030}]
        os.environ["WA_TEMPLATE_ORDER_UPDATE"] = ""
        o3 = client.post(f"/api/orders/{o2['id']}/advance").json()
        check(o3["notifications"][0].get("delivery") == "test_only",
              "live: a phone the test number can't reach is labelled as such")
        answers[:] = [{"ok": False, "code": 100}]
        o3 = client.post(f"/api/orders/{o2['id']}/advance").json()
        check(o3["notifications"][0].get("delivery") == "failed" and o3["stage"],
              "live: a failed send still moves the order on and shows in the tracker")
    finally:
        whatsapp._post = real_post
        os.environ.update(WA_ACCESS_TOKEN="", WA_PHONE_NUMBER_ID="", WA_TEMPLATE_ORDER_UPDATE="")

    print("\nErasure:")
    demo("910000000009", "hi")
    sid = store.get("wa_link", "910000000009")["session_id"]
    r = client.post(f"/api/privacy/erase/{sid}")
    check(r.status_code == 200 and not store.get("wa_link", "910000000009") and not store.get("wa_session", sid),
          "erasing a chat also forgets which WhatsApp number it came from")

    print("\nOne reminder for an unfinished bundle:")

    def bundle_chat(wa_id: str) -> tuple[str, datetime]:
        demo(wa_id, "I run a pharmacy in Pune with 4 people, one shop, we have GST")
        sid = store.get("wa_link", wa_id)["session_id"]
        r = advisor.message(sid, slot="current", value="hotspot")
        for _ in range(6):
            if r.get("recommendation"):
                break
            r = advisor.message(sid, needs=[n["key"] for n in r["needs"] if n["selected"]]) if r.get("needs") \
                else advisor.message(sid, slot=r["chips"][0].get("slot"), value=r["chips"][0]["value"])
        link = store.get("wa_link", wa_id)
        store.put("wa_link", wa_id, {**link, "card": [r["recommendation"]["quote"]["monthly"], 12, []]})
        return sid, datetime.fromisoformat(link["last_in"])

    NUDGE = "910000000077"
    sid, last = bundle_chat(NUDGE)
    url = "https://app.example/"
    check(not whatsapp.send_nudges(url, last + timedelta(hours=1), demo=True), "no reminder while the owner may still be deciding")
    sent = whatsapp.send_nudges(url, last + timedelta(hours=4), demo=True)
    check(len(sent) == 1 and sent[0]["to"] == NUDGE and f"{url}#/continue/{sid}" in body(sent[0]),
          "after 3 quiet hours: one reminder with a link to finish", [body(m) for m in sent])
    check(not whatsapp.send_nudges(url, last + timedelta(hours=6), demo=True), "never a second reminder")
    LATE = "910000000078"
    _, last2 = bundle_chat(LATE)
    check(not whatsapp.send_nudges(url, last2 + timedelta(hours=25), demo=True),
          "none after WhatsApp's 24-hour service window has closed")
    demo(NUDGE, "hi")  # writing again opens a new window, but she was already reminded once for this bundle
    check(not whatsapp.send_nudges(url, datetime.now(timezone.utc) + timedelta(hours=4), demo=True) or
          store.get("wa_link", NUDGE).get("nudged"), "a reminded chat stays reminded")

    passed = sum(ok for ok, _ in RESULTS)
    print(f"\n{passed}/{len(RESULTS)} WhatsApp order checks passed")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
