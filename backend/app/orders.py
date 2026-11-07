"""Orders and the self-service tracker.

Every status change creates a notification in the owner's language and, when they agreed to WhatsApp updates,
sends it to their WhatsApp for real (whatsapp.send_update), so the owner never has to call to ask "where is my
connection?" (status chases predict churn in the leads data: 6% churn at 1 chase, 28% at 5). The owner can also
reply STATUS, RESCHEDULE or PROBLEM on WhatsApp (see whatsapp.py).

The phone number is kept apart from the order (store kind "order_contact"), only when the owner opted in to
WhatsApp updates, and is used for nothing else; every view of the order shows it masked.
"""
import re
from datetime import datetime, timedelta, timezone

from . import store
from .data import products
from .i18n import t
from .recommender import CONNECTIVITY

STAGES = [
    ("placed", "Order placed"),
    ("kyc_verified", "KYC verified"),
    ("esigned", "Agreement e-signed"),
    ("feasibility", "Site feasibility confirmed"),
    ("scheduled", "Installation scheduled"),
    ("installing", "Installation in progress"),
    ("activated", "All services live"),
]
STAGE_KEYS = [k for k, _ in STAGES]


def _today() -> datetime:
    return datetime.now(timezone.utc)


def _plan(lines: list[dict], start: datetime) -> list[dict]:
    conn_days = max([l["install_days"] for l in lines if l["id"] in CONNECTIVITY] or [0])
    items = []
    for l in lines:
        prod = products()[l["id"]]
        days = max(l["install_days"], conn_days if prod.requires_one_of else 0)
        items.append({"id": l["id"], "name": l["name"], "qty": l["qty"], "status": "pending",
                      "eta": (start + timedelta(days=days)).date().isoformat(), "install_days": days})
    return items


def wa_number(phone: str) -> str:
    """An Indian mobile number in WhatsApp's format (country code, no plus), or "" if it isn't one."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10 and digits[0] in "6789":
        return "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    return ""


def link_whatsapp(order_id: str, wa_id: str, chat_wa: str = "") -> None:
    """Remember which WhatsApp number gets this order's updates (wa_id, the number given at checkout) and which
    chats may ask about it (that number, plus the WhatsApp chat the order was bought from, if any)."""
    if wa_id:
        store.put("order_contact", order_id, {"wa": wa_id})
    for n in {wa_id, chat_wa} - {""}:
        ids = (store.get("wa_orders", n) or {}).get("ids", [])
        store.put("wa_orders", n, {"ids": [order_id] + [i for i in ids if i != order_id][:9]})


def create(session: dict, quote: dict, kyc: dict, contact: dict, esign_ok: bool) -> dict:
    now = _today()
    oid = "AB" + store.new_id("o").split("_")[1][:8].upper()
    lang = session.get("lang", "en")
    conn_line = next((l for l in quote["lines"] if l["id"] in CONNECTIVITY), None)
    conn = t(lang, f"plain_{conn_line['id']}") if conn_line else "your connection"
    chat_wa = (store.get("wa_session", session["id"]) or {}).get("wa", "")
    if contact.get("whatsapp_updates", True):
        link_whatsapp(oid, wa_number(contact.get("phone", "")) or wa_number(chat_wa), chat_wa)
    from . import partners
    partner = partners.credit(session, quote["monthly"], [n for n in (wa_number(contact.get("phone", "")), chat_wa) if n])
    order = {
        "id": oid, "session_id": session["id"], "created": now.isoformat(timespec="seconds"),
        "business": session["profile"].get("business_name") or session["profile"].get("business_type"),
        "city": session["profile"].get("city"), "lang": session.get("lang", "en"),
        "contact": {"name": contact.get("name", ""), "phone_masked": _mask_phone(contact.get("phone", "")),
                    "whatsapp_updates": bool(contact.get("whatsapp_updates", True))},
        "quote": quote, "connectivity": conn, "kyc_decision": kyc.get("decision"),
        "items": _plan(quote["lines"], now),
        "expected_activation": (now + timedelta(days=quote["activation_days"])).date().isoformat(),
        "stage": "placed", "history": [], "notifications": [], "slot": None, "tickets": [], "partner": partner,
    }
    _advance_to(order, "placed", send=False)
    _advance_to(order, "kyc_verified", send=False)
    if esign_ok:
        _advance_to(order, "esigned", send=False)
    _notify(order, t(lang, "stm_created", id=oid, conn=conn), show=False)  # one WhatsApp message, not three
    store.put("order", oid, order)
    store.audit("customer", "order_created", oid, f"monthly={quote['monthly']} items={len(quote['lines'])}")
    if partner:
        store.audit(f"partner:{partner['id']}", "commission_credited", oid, f"via={partner['via']} amount={partner['commission']}")
    return order


def _mask_phone(p: str) -> str:
    digits = "".join(c for c in p if c.isdigit())
    return ("•" * max(0, len(digits) - 4) + digits[-4:]) if digits else ""


def _notify(order: dict, text: str, show: bool = True, send: bool = True) -> None:
    """Add an update to the tracker (show) and send it to the owner's WhatsApp if they opted in (send). With show
    False the text goes out on WhatsApp only, and its delivery is shown on the latest tracker update instead."""
    wa = order["contact"]["whatsapp_updates"]
    note = {"at": _today().isoformat(timespec="seconds"), "channel": "WhatsApp" if wa else "SMS", "text": text}
    if send and wa:
        from . import whatsapp
        res = whatsapp.send_update(order["id"], text, order.get("lang", "en"))
        note["delivery"] = res["delivery"]
        if res.get("wamid"):  # Meta reports delivered / read for this message id; see set_delivery
            note["wamid"] = res["wamid"]
            store.put("wa_message", res["wamid"], {"order": order["id"]})
    if show:
        order["notifications"].insert(0, note)
    elif note.get("delivery") and order["notifications"]:
        order["notifications"][0].update({k: note[k] for k in ("delivery", "wamid") if k in note})


_DELIVERY_RANK = {"failed": 0, "demo": 0, "no_number": 0, "sent": 1, "template": 1, "delivered": 2, "read": 3}


def set_delivery(wamid: str, status: str) -> None:
    """A WhatsApp status webhook (sent, delivered, read, failed) for an update we sent: show it in the tracker."""
    ref = store.get("wa_message", wamid)
    order = store.get("order", ref["order"]) if ref else None
    if not order:
        return
    for n in order["notifications"]:
        if n.get("wamid") == wamid:
            if status == "failed" or _DELIVERY_RANK.get(status, 0) > _DELIVERY_RANK.get(n.get("delivery"), 0):
                n["delivery"] = status  # statuses can arrive out of order: never step back from read to delivered
                store.put("order", order["id"], order)
            return


def _advance_to(order: dict, stage: str, send: bool = True) -> None:
    order["stage"] = stage
    ts = _today().isoformat(timespec="seconds")
    lang = order.get("lang", "en")
    order["history"].append({"stage": stage, "label": dict(STAGES)[stage], "at": ts})
    msg = t(lang, f"stm_{stage}", id=order["id"], conn=order["connectivity"], slot=order.get("slot") or "",
            n=len(order["items"]))
    _notify(order, msg, send=send)
    if stage == "installing":
        for it in order["items"]:
            it["status"] = "installing"
    if stage == "activated":
        for it in order["items"]:
            it["status"] = "live"


def advance(order_id: str) -> dict:
    """Simulates the field/back-office update that moves an order on (demo control)."""
    order = store.get("order", order_id)
    if not order:
        raise KeyError(order_id)
    i = STAGE_KEYS.index(order["stage"])
    if order["stage"] == "installing":
        pending = [it for it in order["items"] if it["status"] != "live"]
        pending.sort(key=lambda it: it["install_days"])
        if pending:
            pending[0]["status"] = "live"
            lang = order.get("lang", "en")
            _notify(order, t(lang, "stm_item_live", name=t(lang, f"plain_{pending[0]['id']}")))
            if len(pending) > 1:
                store.put("order", order_id, order)
                return view(order)
        _advance_to(order, "activated")
    elif i < len(STAGE_KEYS) - 1:
        nxt = STAGE_KEYS[i + 1]
        if nxt == "scheduled" and not order.get("slot"):
            order["slot"] = next_slots(1)[0]
        _advance_to(order, nxt)
    store.put("order", order_id, order)
    return view(order)


def book_slot(order_id: str, slot: str) -> dict:
    order = store.get("order", order_id)
    if not order:
        raise KeyError(order_id)
    order["slot"] = slot[:60]
    if STAGE_KEYS.index(order["stage"]) < STAGE_KEYS.index("scheduled"):
        if order["stage"] != "feasibility":
            _advance_to(order, "feasibility", send=False)
        _advance_to(order, "scheduled")
    else:
        _notify(order, t(order.get("lang", "en"), "stm_rescheduled", slot=order["slot"]))
    store.put("order", order_id, order)
    store.audit("customer", "slot_booked", order_id, "")
    return view(order)


def raise_ticket(order_id: str, text: str) -> dict:
    order = store.get("order", order_id)
    if not order:
        raise KeyError(order_id)
    tid = f"T{len(order['tickets']) + 1:03d}"
    order["tickets"].append({"id": tid, "text": text[:300], "status": "open", "at": _today().isoformat(timespec="seconds")})
    _notify(order, t(order.get("lang", "en"), "stm_ticket", tid=tid))
    store.put("order", order_id, order)
    return view(order)


IST = timezone(timedelta(hours=5, minutes=30))


def next_slots(n: int = 6) -> list[str]:
    """Installation windows from the day after tomorrow, Sundays off, in Indian time. The tracker and WhatsApp
    offer exactly these, so a slot picked in either place means the same thing."""
    out, day = [], datetime.now(IST).date() + timedelta(days=2)
    while len(out) < n:
        if day.weekday() != 6:
            label = f"{day:%a} {day.day} {day:%b}"
            out += [f"{label}, 10am–1pm", f"{label}, 2pm–6pm"]
        day += timedelta(days=1)
    return out[:n]


CAN_BOOK = ("esigned", "feasibility", "scheduled")


def view(order: dict) -> dict:
    idx = STAGE_KEYS.index(order["stage"])
    lang = order.get("lang", "en")
    steps = [{"key": k, "label": t(lang, f"st_{k}"), "done": i <= idx, "current": i == idx,
              "at": next((h["at"] for h in order["history"] if h["stage"] == k), None)}
             for i, (k, label) in enumerate(STAGES)]
    items = [{**it, "plain": t(lang, f"plain_{it['id']}")} for it in order["items"]]
    notes = [{k: v for k, v in n.items() if k != "wamid"} for n in order["notifications"]]
    helper = {"id": order["partner"]["id"], "name": order["partner"]["name"]} if order.get("partner") else None
    return {**order, "partner": helper, "items": items, "notifications": notes, "steps": steps,
            "progress": round(100 * idx / (len(STAGES) - 1)),
            "slots": next_slots() if order["stage"] in CAN_BOOK else []}


def get(order_id: str) -> dict | None:
    o = store.get("order", order_id.strip().upper())
    return view(o) if o else None
