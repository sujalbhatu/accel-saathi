"""WhatsApp front end for the same advisor, in the WhatsApp Business Cloud API format.

Meta calls POST /api/whatsapp/webhook with each incoming message. We find (or start) the owner's advisor session by
their number, run the message through the same advisor as the app, and answer with WhatsApp messages: text, up to
3 reply buttons, and a list for longer menus. With WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID set, replies are sent
through the Graph API; without them (the demo), the messages that would be sent are returned in the response.
The owner can continue in the app at any point with their conversation intact, because both use one session.

After an order is placed, every tracker update is also sent to the owner's WhatsApp (send_update), and the owner
can reply STATUS, RESCHEDULE or PROBLEM (in English, Hindi, Marathi or Tamil words) to get the order status, move the
installation slot, or log a ticket, all without a call. Updates are free-form text inside WhatsApp's 24-hour
window; outside it, an approved utility template (WA_TEMPLATE_ORDER_UPDATE) is used when one is configured.
"""
import difflib
import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timezone

import httpx

from . import advisor, orders, store
from .i18n import t

log = logging.getLogger("whatsapp")
GRAPH = "https://graph.facebook.com/v21.0"


def _session_for(wa_id: str, lang: str = "en") -> str:
    link = store.get("wa_link", wa_id)
    if link and store.get("session", link["session_id"]):
        return link["session_id"]
    sid = advisor.start(lang, source="whatsapp", channel="whatsapp")["session_id"]
    store.put("wa_link", wa_id, {"session_id": sid, "created": store.now()})
    store.put("wa_session", sid, {"wa": wa_id})  # so an order placed from this chat gets its updates here
    s = store.get("session", sid)
    s["wa_id_masked"] = "******" + wa_id[-4:]
    store.put("session", sid, s)
    return sid


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def to_whatsapp(wa_id: str, reply: dict, lang: str, app_url: str, show_bundle: bool = True) -> list[dict]:
    """Advisor reply -> WhatsApp Cloud API message bodies. The bundle card goes out only when the bundle is new
    or changed, so a question after the recommendation gets an answer, not the same card again."""
    msgs = list(reply["messages"])
    if msgs and reply.get("sources"):
        msgs[0] += "\n\n📄 " + " · ".join(src["title"].replace("Product sheet: ", "") for src in reply["sources"])
    out = [{"messaging_product": "whatsapp", "to": wa_id, "type": "text", "text": {"body": m}} for m in msgs]
    rec = reply.get("recommendation")
    if rec and reply.get("stage") == "done" and show_bundle:
        q = rec["quote"]
        lines = "\n".join(f"• {l.get('plain') or l['name']}{' × ' + str(l['qty']) if l['qty'] > 1 else ''}: ₹{l['monthly']:,}"
                          for l in q["lines"])
        levels = rec.get("options") or []
        if len(levels) > 1:  # Basic / Recommended / Complete, the current one marked
            lines += "\n\n" + " · ".join(f"{'✓ ' if o['current'] else ''}{o['label']} ₹{o['monthly']:,}" for o in levels)
        out.append({"messaging_product": "whatsapp", "to": wa_id, "type": "interactive", "interactive": {
            "type": "cta_url", "body": {"text": f"{lines}\n\n" + t(lang, "wa_bundle_foot", monthly=f"₹{q['monthly']:,}",
                                                                          setup=f"₹{q['setup']:,}", days=q["activation_days"])},
            "action": {"name": "cta_url", "parameters": {"display_text": _clip(t(lang, "wa_see_price"), 20),
                                                         "url": f"{app_url}#/continue/{reply['session_id']}"}}}})
    if reply.get("needs"):
        out.append({"messaging_product": "whatsapp", "to": wa_id, "type": "interactive", "interactive": {
            "type": "button", "body": {"text": "✔ " + "\n✔ ".join(n["label"] for n in reply["needs"] if n["selected"])},
            "action": {"buttons": [{"type": "reply", "reply": {"id": "needs:ok", "title": _clip(t(lang, "wa_continue"), 20)}},
                                   {"type": "reply", "reply": {"id": "needs:edit", "title": _clip(t(lang, "wa_change"), 20)}}]}}})
    chips = reply.get("chips") or []
    if chips:
        ids = [f"chip:{c['slot']}:{c['value']}" for c in chips]
        if len(chips) <= 3:
            action = {"buttons": [{"type": "reply", "reply": {"id": i, "title": _clip(c["label"], 20)}}
                                  for i, c in zip(ids, chips)]}
            kind = "button"
        else:
            action = {"button": _clip(t(lang, "wa_options"), 20), "sections": [{"title": _clip(t(lang, "wa_choose"), 24), "rows": [
                {"id": i, "title": _clip(c["label"], 24)} for i, c in zip(ids, chips[:10])]}]}
            kind = "list"
        out.append({"messaging_product": "whatsapp", "to": wa_id, "type": "interactive",
                    "interactive": {"type": kind, "body": {"text": "👇"}, "action": action}})
    return out


# ---------- orders on WhatsApp: updates out, STATUS / RESCHEDULE / PROBLEM in ----------

_ORDER_ID = re.compile(r"\bAB[A-Z0-9]{8}\b")
_ORDER_ASK = {
    "status": r"\bstatus\b|where is my (?:order|connection)|track (?:my |the |our )?(?:order|connection|installation)|"
              r"order (?:kaha|kahan|kab)|kab tak|kab lagega|स्टेटस|ऑर्डर कहाँ|ऑर्डर कहां|मेरा ऑर्डर|ऑर्डर ट्रैक|कब तक|"
              r"कब लगेगा|माझी ऑर्डर|ஆர்டர் நிலை|\bநிலை\b",
    "reschedule": r"reschedul|change (?:the )?(?:slot|time|date|day)|another (?:slot|time|day)|different (?:slot|time|day)|"
                  r"slot badal|time badal|दूसरा समय|समय बदल|तारीख बदल|वेळ बदल|நேரத்தை மாற்ற",
    "problem": r"\bproblem\b|\bissue\b|not working|complain|kharab|band hai|nahi chal|दिक्कत|समस्या|खराब|बंद है|"
               r"काम नहीं|அடிக்கடி|வேலை செய்யவில்லை|பிரச்சனை",
}
KEYWORDS = {"status": "STATUS", "reschedule": "RESCHEDULE", "problem": "PROBLEM"}


def _text(wa_id: str, body: str) -> dict:
    return {"messaging_product": "whatsapp", "to": wa_id, "type": "text", "text": {"body": body}}


def _buttons(wa_id: str, body: str, buttons: list[tuple[str, str]]) -> dict:
    return {"messaging_product": "whatsapp", "to": wa_id, "type": "interactive", "interactive": {
        "type": "button", "body": {"text": body},
        "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": _clip(title, 20)}} for i, title in buttons[:3]]}}}


def _order_menu(wa_id: str, order: dict, body: str) -> dict:
    lang, oid = order.get("lang", "en"), order["id"]
    return _buttons(wa_id, body, [(f"ord:status:{oid}", t(lang, "chip_status")), (f"ord:resched:{oid}", t(lang, "chip_resched")),
                                  (f"ord:problem:{oid}", t(lang, "chip_problem"))])


def _status(wa_id: str, order: dict) -> list[dict]:
    lang = order.get("lang", "en")
    v = orders.view(order)
    body = t(lang, "wa_status", id=order["id"], stage=next(st["label"] for st in v["steps"] if st["current"]),
             eta=order["expected_activation"])
    if order.get("slot"):
        body += " " + t(lang, "wa_status_slot", slot=order["slot"])
    latest = (order.get("notifications") or [{}])[0].get("text")
    return [_order_menu(wa_id, order, body + (f"\n\n{latest}" if latest else ""))]


def _slots(wa_id: str, order: dict) -> list[dict]:
    lang = order.get("lang", "en")
    rows = [{"id": f"ord:slot:{order['id']}:{i}", "title": _clip(slot, 24)} for i, slot in enumerate(orders.next_slots())]
    return [{"messaging_product": "whatsapp", "to": wa_id, "type": "interactive", "interactive": {
        "type": "list", "body": {"text": t(lang, "wa_pick_slot")},
        "action": {"button": _clip(t(lang, "chip_slots"), 20), "sections": [{"title": order["id"], "rows": rows}]}}}]


def _my_orders(wa_id: str) -> list[str]:
    return (store.get("wa_orders", wa_id) or {}).get("ids", [])


TICKET_WAIT = 30 * 60  # after PROBLEM, the next message (within 30 minutes) is taken as the description


def _waiting_for(link: dict) -> str | None:
    w = link.get("awaiting_ticket")
    if not w:
        return None
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(link.get("awaiting_since", ""))).total_seconds()
    except ValueError:
        return None
    return w if age < TICKET_WAIT else None


def _ticket(wa_id: str, order_id: str, text: str, link: dict) -> list[dict]:
    order = orders.raise_ticket(order_id, text)
    store.put("wa_link", wa_id, {**link, "awaiting_ticket": None})
    return [_text(wa_id, t(order.get("lang", "en"), "wa_ticket_done", tid=order["tickets"][-1]["id"], id=order["id"]))]


def order_turn(wa_id: str, text: str, link: dict, lang: str = "en") -> list[dict] | None:
    """A typed message about an order: STATUS, RESCHEDULE, PROBLEM (or the same in Indian languages), an order
    number, or the description after PROBLEM. Returns the replies, or None when the message is for the advisor.
    Only the numbers an order is linked to get an answer about it; anyone else learns nothing about the order."""
    low, words = text.lower(), len(text.split())
    ask = next((k for k, pat in _ORDER_ASK.items() if re.search(pat, low)), None)
    if not ask and words <= 2:  # a typo of a reply keyword ("staus", "reshedule", "probelm")
        near = difflib.get_close_matches(re.sub(r"[^a-z]", "", low), list(KEYWORDS), n=1, cutoff=0.75)
        ask = near[0] if near else None
    mine = _my_orders(wa_id)
    waiting = _waiting_for(link)
    if waiting in mine:
        if not ask or words > 3:  # the description (a short "status" or "reschedule" is a new request instead)
            return _ticket(wa_id, waiting, text, link)
        if ask != "problem":
            store.put("wa_link", wa_id, {**link, "awaiting_ticket": None})
    named = _ORDER_ID.search(text.upper())
    if named:
        if named.group(0) not in mine or not store.get("order", named.group(0)):
            return [_text(wa_id, t(lang, "wa_no_order"))]
        order = store.get("order", named.group(0))
    elif ask and mine:
        order = store.get("order", mine[0])
        if not order:
            return None
    elif ask in ("status", "reschedule") and words <= 4:  # "STATUS" from a number with no order: say so plainly
        return [_text(wa_id, t(lang, "wa_no_order"))]
    else:  # no order on this number: "my internet has a problem" is a new owner talking to the advisor
        return None
    if ask == "problem" and words >= 4 and not named:  # "internet not working since morning": log it right away
        return _ticket(wa_id, order["id"], text, link)
    return _order_action(wa_id, order, ask or "status", link)


def _order_action(wa_id: str, order: dict, ask: str, link: dict, arg: str = "") -> list[dict]:
    lang = order.get("lang", "en")
    if ask == "status":
        return _status(wa_id, order)
    if ask in ("reschedule", "resched", "slot") and order["stage"] not in orders.CAN_BOOK:
        return [_text(wa_id, t(lang, "wa_resched_late"))]
    if ask in ("reschedule", "resched"):
        return _slots(wa_id, order)
    if ask == "slot":
        options = orders.next_slots()
        slot = options[int(arg)] if arg.isdigit() and int(arg) < len(options) else options[0]
        orders.book_slot(order["id"], slot)
        return [_text(wa_id, t(lang, "wa_slot_done", slot=slot))]
    if ask == "problem":
        store.put("wa_link", wa_id, {**link, "awaiting_ticket": order["id"],
                                     "awaiting_since": datetime.now(timezone.utc).isoformat()})
        return [_text(wa_id, t(lang, "wa_problem_ask"))]
    return _status(wa_id, order)


def send_update(order_id: str, text: str, lang: str = "en") -> dict:
    """Send one tracker update to the owner's WhatsApp. Returns {"delivery": "sent" | "template" | "demo" (no
    WhatsApp keys set) | "no_number" | "test_only" (a number the test sender can't reach) | "failed", "wamid": Meta's
    message id when sent}. Never raises: an update that can't be sent still shows in the tracker."""
    to = (store.get("order_contact", order_id) or {}).get("wa", "")
    if not to:
        return {"delivery": "no_number"}
    if not live():
        return {"delivery": "demo"}
    body = t(lang, "wa_update", id=order_id, text=text, **{k: KEYWORDS[k] for k in KEYWORDS})
    res = _post(_text(to, body))
    if res["ok"]:
        return {"delivery": "sent", "wamid": res.get("id")}
    template = os.getenv("WA_TEMPLATE_ORDER_UPDATE")
    if template and res.get("code") in (131047, 131026, 470):  # outside the 24-hour window: use the approved template
        msg = {"messaging_product": "whatsapp", "to": to, "type": "template", "template": {
            "name": template, "language": {"code": os.getenv("WA_TEMPLATE_LANG", "en")},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": order_id},
                                                           {"type": "text", "text": " ".join(text.split())[:900]}]}]}}
        res = _post(msg)
        if res["ok"]:
            return {"delivery": "template", "wamid": res.get("id")}
    if res.get("code") == 131030:  # Meta's free test number only reaches the (up to 5) phones registered with it
        return {"delivery": "test_only"}
    return {"delivery": "failed"}


def handle(payload: dict, app_url: str, demo: bool = False) -> dict:
    """Process a Cloud API webhook payload. Returns the messages sent (or, in the demo, that would be sent).
    demo=True is the in-app WhatsApp screen: same advisor and order replies, but nothing goes to Meta."""
    sent = []
    deliver = (lambda b: b) if demo else _send
    own = os.getenv("WA_PHONE_NUMBER_ID")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            number = (value.get("metadata") or {}).get("phone_number_id")
            if not demo and own and number and number != own:  # another number on the same business account
                continue
            for st in value.get("statuses", []):  # sent / delivered / read receipts for our order updates
                if st.get("id") and st.get("status"):
                    orders.set_delivery(st["id"], st["status"])
            for msg in value.get("messages", []):
                wa_id = msg.get("from", "")
                if not wa_id:
                    continue
                if msg.get("id"):  # Meta re-sends a webhook it thinks we missed: answer each message once
                    if store.get("wa_seen", msg["id"]):
                        continue
                    store.put("wa_seen", msg["id"], {"at": store.now()})
                sid = _session_for(wa_id)
                s = store.get("session", sid)
                link = {**(store.get("wa_link", wa_id) or {}), "wa": wa_id, "last_in": store.now()}
                store.put("wa_link", wa_id, link)  # opens WhatsApp's 24-hour service window for one reminder
                kind = msg.get("type")
                if kind == "button":  # a quick-reply button on a template message: treat its label as text
                    kind, msg = "text", {**msg, "text": {"body": (msg.get("button") or {}).get("text", "")}}
                it = msg.get("interactive") or {}
                choice = (it.get("button_reply") or it.get("list_reply") or {})
                cid, title = choice.get("id", ""), choice.get("title", "")
                handled = None
                if kind == "text":
                    handled = order_turn(wa_id, msg["text"]["body"][:1000], link, s["lang"])
                elif cid.startswith("ord:"):
                    _, ask, rest = cid.split(":", 2)
                    oid, _, arg = rest.partition(":")
                    order = store.get("order", oid)
                    handled = _order_action(wa_id, order, ask, link, arg) if order and oid in _my_orders(wa_id) \
                        else [_text(wa_id, t(s["lang"], "wa_no_order"))]
                if handled is not None:
                    sent += [deliver(b) for b in handled]
                    store.audit("whatsapp", "order_message", sid, f"from=******{wa_id[-4:]}")
                    continue
                if kind == "text":
                    reply = advisor.message(sid, text=msg["text"]["body"][:1000])
                    if reply.get("go") == "tracker":  # "track my order" in the advisor: answer with the status here
                        mine = _my_orders(wa_id)
                        order = store.get("order", mine[0]) if mine else None
                        bodies = _status(wa_id, order) if order else [_text(wa_id, t(s["lang"], "wa_no_order"))]
                        sent += [deliver(b) for b in bodies]
                        continue
                elif kind == "interactive":
                    if cid == "needs:ok":
                        last = (s.get("last") or {}).get("needs") or []
                        reply = advisor.message(sid, needs=[n["key"] for n in last if n["selected"]], display=title)
                    elif cid == "needs:edit":
                        reply = {"session_id": sid, "messages": [t(s["lang"], "wa_change_needs")], "chips": []}
                    elif cid.startswith("chip:"):
                        _, slot, value = cid.split(":", 2)
                        reply = advisor.message(sid, slot=slot, value=value, display=title)
                    else:
                        reply = advisor.message(sid, text=title or "help")
                else:  # voice notes, images: ask for text in the owner's language
                    reply = {"session_id": sid, "messages": [t(s["lang"], "help_done")], "chips": []}
                s = store.get("session", sid)  # the advisor may have switched language
                rec = reply.get("recommendation")
                card = [rec["quote"]["monthly"], rec["quote"]["term_months"],
                        [[l["id"], l["qty"]] for l in rec["quote"]["lines"]]] if rec else None
                link = store.get("wa_link", wa_id)
                show = bool(card) and (card != link.get("card") or reply.get("go") == "quote")  # "go ahead": the link again
                if show or reply.get("reset"):
                    store.put("wa_link", wa_id, {**link, "card": card if show else None})
                bodies = to_whatsapp(wa_id, reply, s["lang"], app_url, show_bundle=show)
                sent += [deliver(b) for b in bodies]
                store.audit("whatsapp", "message_handled", sid, f"from=******{wa_id[-4:]} type={kind}")
    return {"ok": True, "sent": sent, "live": live() and not demo}


# ---------- one reminder for a bundle left unfinished ----------

NUDGE_AFTER_H, WINDOW_H = 3, 23  # remind after 3 quiet hours, only inside WhatsApp's 24-hour service window


def _hours_since(ts: str, now: datetime) -> float:
    return (now - datetime.fromisoformat(ts)).total_seconds() / 3600


def send_nudges(app_url: str, now: datetime | None = None, demo: bool = False) -> list[dict]:
    """For each WhatsApp chat that got a priced bundle but no order, and has been quiet for 3 hours, send ONE
    reminder with a link to finish in the app. Only inside the 24-hour window the owner opened by writing to us,
    never twice, never after an order. Returns the messages sent (or, in the demo, that would be sent)."""
    now = now or datetime.now(timezone.utc)
    deliver = (lambda b: b) if demo else _send
    out = []
    for link in store.list_("wa_link", 1000):
        wa, sid = link.get("wa"), link.get("session_id")
        if not (wa and sid and link.get("card") and link.get("last_in")) or link.get("nudged"):
            continue
        if not demo and wa.startswith("910"):  # the in-app WhatsApp demo's made-up numbers: nothing to send
            continue
        quiet = _hours_since(link["last_in"], now)
        if not NUDGE_AFTER_H <= quiet <= WINDOW_H:
            continue
        s = store.get("session", sid)
        if not s or s.get("order_id") or _my_orders(wa):
            continue
        rec, lang = s.get("recommendation") or {}, s.get("lang", "en")
        q = rec.get("quote") or {}
        if not q.get("monthly"):
            continue
        body = t(lang, "wa_nudge", count=len(q.get("lines", [])), monthly=f"{q['monthly']:,}",
                 link=f"{app_url}#/continue/{sid}")
        out.append(deliver(_text(wa, body)))
        store.put("wa_link", wa, {**link, "nudged": now.isoformat(timespec="seconds")})
        store.audit("whatsapp", "reminder_sent", sid, f"to=******{wa[-4:]} quiet_hours={quiet:.1f}")
    return out


def live() -> bool:
    return bool(os.getenv("WA_ACCESS_TOKEN") and os.getenv("WA_PHONE_NUMBER_ID"))


def _post(body: dict) -> dict:
    """POST one message to the Cloud API. Returns {"ok": bool, "code": Meta error code or HTTP status, "id":
    Meta's message id}."""
    try:
        r = httpx.post(f"{GRAPH}/{os.environ['WA_PHONE_NUMBER_ID']}/messages", json=body, timeout=8,
                       headers={"Authorization": f"Bearer {os.environ['WA_ACCESS_TOKEN']}"})
    except httpx.HTTPError as e:
        log.warning("WhatsApp send failed: %s", type(e).__name__)
        return {"ok": False, "code": None}
    if r.status_code < 300:
        try:
            return {"ok": True, "code": None, "id": (r.json().get("messages") or [{}])[0].get("id")}
        except (ValueError, AttributeError, IndexError):
            return {"ok": True, "code": None}
    try:
        code = r.json().get("error", {}).get("code")
    except ValueError:
        code = None
    log.warning("WhatsApp send failed: HTTP %s code %s", r.status_code, code)
    return {"ok": False, "code": code or r.status_code}


def _send(body: dict) -> dict:
    if live():
        _post(body)
    return body


def signature_ok(raw: bytes, header: str | None) -> bool:
    """Meta signs every webhook with the app secret. In the demo (no secret configured) the check is skipped."""
    secret = os.getenv("WA_APP_SECRET")
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return bool(header) and hmac.compare_digest(expected, header)


def verify(mode: str, token: str, challenge: str) -> str | None:
    """Meta's webhook verification handshake."""
    expected = os.getenv("WA_VERIFY_TOKEN")
    return challenge if expected and mode == "subscribe" and token == expected else None

