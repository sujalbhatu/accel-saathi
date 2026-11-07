"""Channel partners: assisted selling, referral links and commission protection.

A partner (a local telecom dealer) can sell in two ways:
  * assisted: the partner opens a session on their own tablet, sits with the owner and fills the chat; the owner
    gives KYC consent herself, by a one-time code sent to her own phone, and can continue on her phone by QR.
  * referral: the partner's QR at the shop counter opens the app with ?ref=PT01; the owner does it alone.

Commission protection: once the owner has confirmed her number by the code, that number stays credited to the
partner for 30 days. If she later orders on her own (a new app session, or WhatsApp), the sale is still the
partner's. Only a verified number counts, so a partner cannot claim a shop by typing its number.

Commission: one month's rental (before GST), half when every service is live, half after 6 months retained.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from . import store
from .leads import PARTNERS

TOUCH_DAYS = 30
CODE_MINUTES = 10
CODE_TRIES = 5
FIRST_SHARE, RETAINED_SHARE, RETAINED_MONTHS = 0.5, 0.5, 6


def get(pid: str | None) -> dict | None:
    pid = (pid or "").strip().upper()
    return next((p for p in PARTNERS if p["id"] == pid), None)


def public(p: dict) -> dict:
    return {"id": p["id"], "name": p["name"], "cities": p["cities"], "languages": p["languages"]}


def tag(session: dict, pid: str, mode: str) -> dict | None:
    """Mark a session as brought in by a partner (mode "assisted" or "referral"). Unknown ids are ignored."""
    p = get(pid)
    if not p:
        return None
    session["partner"] = {"id": p["id"], "name": p["name"], "mode": mode, "at": store.now()}
    store.audit(f"partner:{p['id']}", f"{mode}_session", session["id"], "")
    return session["partner"]


def _hash(sid: str, code: str) -> str:
    return hashlib.sha256(f"{sid}:{code}".encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def send_owner_code(sid: str, wa: str, lang: str = "en") -> dict:
    """Send a 6-digit code to the owner's own WhatsApp. Returns {"delivery", "phone_masked", "demo_code"?}.
    The code is shown on screen only when it could not be delivered (demo mode, or a number Meta's test sender
    can't reach), and the screen says so."""
    from . import whatsapp
    from .i18n import t
    code = f"{secrets.randbelow(10**6):06d}"
    store.put("owner_code", sid, {"wa": wa, "hash": _hash(sid, code), "tries": 0,
                                  "expires": (_now() + timedelta(minutes=CODE_MINUTES)).isoformat(timespec="seconds")})
    delivery = "demo"
    if whatsapp.live():
        res = whatsapp._post(whatsapp._text(wa, t(lang, "wa_owner_code", code=code, minutes=CODE_MINUTES)))
        delivery = "sent" if res["ok"] else ("test_only" if res.get("code") == 131030 else "failed")
    store.audit("system", "owner_code_sent", sid, f"to=••{wa[-4:]} delivery={delivery}")
    out = {"delivery": delivery, "phone_masked": "••••••" + wa[-4:]}
    if delivery != "sent":
        out["demo_code"] = code
    return out


def check_owner_code(sid: str, code: str) -> str | None:
    """The verified WhatsApp number if the code is right, else None. Five wrong tries or 10 minutes end a code."""
    rec = store.get("owner_code", sid)
    if not rec or rec["tries"] >= CODE_TRIES or datetime.fromisoformat(rec["expires"]) < _now():
        return None
    if not secrets.compare_digest(rec["hash"], _hash(sid, (code or "").strip())):
        rec["tries"] += 1
        store.put("owner_code", sid, rec)
        return None
    store.delete("owner_code", sid)
    return rec["wa"]


def protect(wa: str, partner: dict, sid: str) -> None:
    """Credit this verified number to the partner for the next 30 days (a newer touch by another partner wins)."""
    until = (_now() + timedelta(days=TOUCH_DAYS)).isoformat(timespec="seconds")
    store.put("partner_touch", wa, {"partner_id": partner["id"], "session_id": sid, "until": until})
    store.audit(f"partner:{partner['id']}", "commission_protected", sid, f"number=••{wa[-4:]} until={until[:10]}")


def _touch(wa: str) -> dict | None:
    rec = store.get("partner_touch", wa) if wa else None
    if rec and datetime.fromisoformat(rec["until"]) >= _now():
        return rec
    return None


def credit(session: dict, monthly: float, numbers: list[str]) -> dict | None:
    """Who gets the commission for an order: the session's own partner, else a partner whose 30-day protection
    covers one of the owner's numbers (checkout number, or the WhatsApp chat the order came from)."""
    tagged = session.get("partner")
    p, via = (get(tagged["id"]), tagged["mode"]) if tagged else (None, None)
    if not p:
        rec = next((r for r in (_touch(n) for n in numbers) if r), None)
        p, via = (get(rec["partner_id"]), "protected") if rec else (None, None)
    if not p:
        return None
    total = round(monthly)
    return {"id": p["id"], "name": p["name"], "via": via, "commission": total,
            "first": round(total * FIRST_SHARE), "retained": total - round(total * FIRST_SHARE),
            "retained_months": RETAINED_MONTHS}


def summary() -> list[dict]:
    """Per partner: sessions started, orders, and commission earned (services live) or pending."""
    rows = {p["id"]: {**public(p), "assisted": 0, "referral": 0, "orders": 0, "protected_orders": 0,
                      "earned": 0, "pending": 0, "recent": []} for p in PARTNERS}
    for s in store.list_("session", 1000):
        tagged = s.get("partner")
        if tagged and tagged["id"] in rows:
            rows[tagged["id"]][tagged["mode"]] = rows[tagged["id"]].get(tagged["mode"], 0) + 1
    for o in store.list_("order", 500):
        c = o.get("partner")
        if not c or c["id"] not in rows:
            continue
        r = rows[c["id"]]
        r["orders"] += 1
        r["protected_orders"] += c["via"] == "protected"
        live = o["stage"] == "activated"
        r["earned"] += c["first"] if live else 0
        r["pending"] += c["retained"] + (0 if live else c["first"])
        if len(r["recent"]) < 4:
            r["recent"].append({"id": o["id"], "business": o["business"], "via": c["via"], "commission": c["commission"],
                                "stage": o["stage"]})
    return list(rows.values())
