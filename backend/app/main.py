"""HTTP API for the Udyam Digital journey and the partner console. Serves the built frontend too."""
import json
import logging
import time
import threading
import os
import re
from pathlib import Path

import anyio
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.middleware.gzip import GZipMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from . import advisor, cards, kyc, leads, llm, orders, partners, store, whatsapp  # noqa: E402
from .data import DATA_DIR, TODAY, gstin_registry, leads as lead_data, products, udyam_by_name  # noqa: E402
from .i18n import LANGS, t  # noqa: E402
from .ids import mask  # noqa: E402
from .recommender import Profile, addon_options, requote  # noqa: E402

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


class _HideSecrets(logging.Filter):
    """The access log prints full URLs; Meta's webhook check carries the verify token in the query string."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(re.sub(r"(hub\.verify_token=)[^&\s]*", r"\1***", a) if isinstance(a, str) else a
                                for a in record.args)
        return True


logging.getLogger("uvicorn.access").addFilter(_HideSecrets())
app = FastAPI(title="Accel Saathi · Project Udyam Digital", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.on_event("startup")
def _seal_old_records() -> None:
    n = store.encrypt_existing()
    if n:
        logging.getLogger("store").warning("encrypted %s records written before encryption was on", n)



def _reminder_loop() -> None:
    while True:
        time.sleep(600)
        try:
            if whatsapp.live() and os.getenv("APP_URL"):
                whatsapp.send_nudges(os.environ["APP_URL"].rstrip("/") + "/")
        except Exception:  # a failed reminder must never stop the loop
            logging.getLogger("whatsapp").exception("reminder run failed")


@app.on_event("startup")
def _start_reminders() -> None:
    threading.Thread(target=_reminder_loop, daemon=True, name="wa-reminders").start()
app.add_middleware(GZipMiddleware, minimum_size=1000)

MAX_UPLOAD = 6 * 1024 * 1024
OCR_SLOTS = anyio.CapacityLimiter(1)
ALLOWED_IMAGE = {"image/png", "image/jpeg", "image/webp"}
CONSENT_VERSION = "2026-10-v1"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=(self), geolocation=()"
    return resp


@app.exception_handler(KeyError)
async def not_found(_: Request, exc: KeyError):
    return JSONResponse({"detail": f"Not found: {exc}"}, status_code=404)


def _session(sid: str) -> dict:
    s = store.get("session", sid)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


def _profile(s: dict, contract_months: int | None = None) -> Profile:
    p = advisor._profile(s)
    if contract_months:
        p.contract_months = 24 if contract_months >= 24 else 12
    return p


# ---------- meta ----------

@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {"llm": llm.enabled(), "llm_model": llm.MODEL if llm.enabled() else None, "languages": LANGS,
            "today": str(TODAY.date()), "consent_version": CONSENT_VERSION}


@app.get("/api/catalogue")
def catalogue():
    return [p.__dict__ | {"tiers": sorted(p.tiers), "segments": sorted(p.segments)} for p in products().values()]


@app.get("/api/lookup/gstin/{gstin}")
def lookup_gstin(gstin: str):
    """Mock GSTN lookup backed by mock_gstin_registry.csv."""
    res = advisor._gstin_lookup(gstin)
    if not res["ok"]:
        return {"found": False, "reason": res.get("reason") or "Not in GST registry", "kind": res["kind"]}
    r = res["record"]
    return {"found": True, "gstin_masked": mask(res["gstin"]), "legal_name": r["legal_name"], "trade_name": r["trade_name"],
            "constitution": r["constitution"], "state": r["state"], "status": r["status"],
            "registration_date": r["registration_date"],
            "udyam": {"enterprise_type": res["udyam"]["enterprise_type"], "activity": res["udyam"]["nic_description"]}
            if res["udyam"] else None}


# ---------- advisor ----------

class StartIn(BaseModel):
    lang: str = "en"
    source: str = "web"
    channel: str = "app"
    ref: str | None = Field(None, max_length=10)  # a partner's referral code from their shop QR (?ref=PT01)


class MessageIn(BaseModel):
    session_id: str
    text: str = Field("", max_length=1000)
    slot: str | None = None
    value: str | int | None = None
    needs: list[str] | None = None
    # what the owner tapped, kept in the chat history. Ticking every service (longer still in Hindi or Tamil) runs past
    # a few hundred characters, so the advisor shortens it when storing it instead of the whole request being refused
    display: str | None = Field(None, max_length=4000)


@app.post("/api/advisor/start")
def advisor_start(body: StartIn):
    out = advisor.start(body.lang, body.source, body.channel)
    if body.ref:
        s = store.get("session", out["session_id"])
        if partners.tag(s, body.ref, "referral"):
            store.put("session", s["id"], s)
            out["partner"] = _partner_view(s)
    return out


def _partner_view(s: dict) -> dict | None:
    p = s.get("partner")
    return {"id": p["id"], "name": p["name"], "mode": p["mode"], "owner_verified": bool(s.get("owner_verified"))} if p else None


@app.post("/api/advisor/message")
def advisor_message(body: MessageIn):
    _session(body.session_id)
    return advisor.message(body.session_id, body.text, body.slot, body.value, body.needs, body.display)


@app.get("/api/advisor/{sid}")
def advisor_resume(sid: str):
    """Redraw a conversation after the owner goes back from the quote or reloads the page."""
    s = _session(sid)
    return {**advisor.resume(sid), "partner": _partner_view(s)}


@app.post("/api/advisor/{sid}/language/{lang}")
def advisor_language(sid: str, lang: str):
    return advisor.set_language(sid, lang)


# ---------- WhatsApp (Cloud API webhook; the app's WhatsApp view talks to the same endpoint) ----------

@app.get("/api/whatsapp/webhook")
def whatsapp_verify(request: Request):
    q = request.query_params
    challenge = whatsapp.verify(q.get("hub.mode", ""), q.get("hub.verify_token", ""), q.get("hub.challenge", ""))
    if challenge is None:
        raise HTTPException(403, "Verification failed")
    return PlainTextResponse(challenge)


def _app_url(request: Request) -> str:
    """Where WhatsApp buttons send the owner: APP_URL when set (behind a proxy), else the address of this request."""
    return (os.getenv("APP_URL") or str(request.base_url)).rstrip("/") + "/"


@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    """Meta's webhook. Signed with the app secret when one is set. With live WhatsApp keys, Meta gets its 200 at
    once and the replies go out through the Graph API after (an AI answer can take seconds, and Meta re-sends
    webhooks that wait too long); without keys the replies come back in the response, as in the tests."""
    raw = await request.body()
    if not whatsapp.signature_ok(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "Bad signature")
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        raise HTTPException(400, "Body must be JSON")
    if whatsapp.live():
        background.add_task(whatsapp.handle, payload, _app_url(request))
        return {"ok": True}
    return whatsapp.handle(payload, _app_url(request))


DEMO_WA = re.compile(r"^910\d{9}$")  # "91" + 0: never a real Indian mobile, so the demo can't speak for one


@app.post("/api/whatsapp/demo")
def whatsapp_demo(payload: dict, request: Request):
    """The in-app WhatsApp screen: the same advisor and order replies as the real number, returned here and never
    sent to Meta. Senders must be demo numbers, so this can't be used to read a real customer's chat or orders."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if not DEMO_WA.match(str(msg.get("from", ""))):
                    raise HTTPException(400, "Demo chats use demo numbers (910 followed by 9 digits)")
    return whatsapp.handle(payload, _app_url(request), demo=True)


# ---------- quote ----------

class Selection(BaseModel):
    id: str
    qty: int = Field(1, ge=1, le=200)
    reason: str | None = None


class QuoteIn(BaseModel):
    session_id: str
    selection: list[Selection]
    contract_months: int = 12


@app.post("/api/quote")
def quote(body: QuoteIn):
    s = _session(body.session_id)
    p = _profile(s, body.contract_months)
    res = requote(p, [x.model_dump() for x in body.selection])
    res["quote"]["lines"] = advisor._localise({"quote": res["quote"], "blocked": res["blocked"], "segment": p.segment},
                                              s["lang"], p)["quote"]["lines"]
    res["addons"] = addon_options(p, {l["id"] for l in res["quote"]["lines"]})
    for a in res["addons"]:
        a["plain"], a["does"] = cards.plain(s["lang"], a["id"]), t(s["lang"], f"does_{a['id']}")
    alt = requote(_profile(s, 24 if p.contract_months < 24 else 12), [x.model_dump() for x in body.selection])
    res["term_compare"] = {"term": alt["quote"]["term_months"], "monthly": alt["quote"]["monthly"]}
    s["last_quote"] = {"selection": [x.model_dump() for x in body.selection], "contract_months": p.contract_months}
    store.put("session", s["id"], s)
    return res


# ---------- KYC ----------

class ConsentIn(BaseModel):
    session_id: str
    accepted: bool
    whatsapp_updates: bool = True
    marketing: bool = False
    owner_code: str | None = Field(None, pattern=r"^\d{6}$")  # assisted mode: the code sent to the owner's phone


def _kyc(sid: str) -> dict:
    return store.get("kyc", sid) or {"session_id": sid, "consent": None, "docs": {}, "result": None}


def _require_consent(k: dict):
    if not (k.get("consent") or {}).get("accepted"):
        raise HTTPException(403, "Consent is required before any document is processed")


def _doc_view(dt: str, d: dict) -> dict:
    return {"doc_type": dt, "label": kyc.DOC_TYPES.get(dt, dt), "source": d.get("source", "upload"),
            "quality_ok": d.get("quality_ok", True), "fields": kyc.masked_fields(dt, d.get("fields", {})),
            "uploaded_at": d.get("uploaded_at")}


def _has_gstin(sid: str | None) -> bool | None:
    return ((store.get("session", sid or "") or {}).get("profile") or {}).get("has_gstin")


def _kyc_view(k: dict) -> dict:
    s = store.get("session", k.get("session_id") or "") or {}
    gstin = ((k.get("docs", {}).get("gst_certificate") or {}).get("fields") or {}).get("gstin") or s.get("profile", {}).get("gstin")
    has_gstin = _has_gstin(k.get("session_id"))
    required = kyc.required_for(has_gstin, None if has_gstin is False else kyc.udyam_registered(gstin))
    return {"consent": k.get("consent"), "docs": {dt: _doc_view(dt, d) for dt, d in k.get("docs", {}).items()},
            "result": k.get("result"), "required": required,
            "all": list(kyc.DOC_TYPES), "labels": kyc.DOC_TYPES}


class RemoveDocIn(BaseModel):
    session_id: str
    doc_type: str


@app.post("/api/kyc/remove")
def kyc_remove(body: RemoveDocIn):
    """Take back one document (a wrong photo, or a certificate the owner doesn't need). Its fields are deleted."""
    _session(body.session_id)
    k = _kyc(body.session_id)
    if k["docs"].pop(body.doc_type, None) is not None:
        k["result"] = None
        store.put("kyc", body.session_id, k)
        store.audit("customer", "document_removed", body.session_id, body.doc_type)
    return _kyc_view(k)


@app.post("/api/kyc/consent")
def kyc_consent(body: ConsentIn):
    s = _session(body.session_id)
    k = _kyc(body.session_id)
    given_by = "owner"
    partner = s.get("partner")
    if body.accepted and partner and partner["mode"] == "assisted" and not s.get("owner_verified"):
        # the partner holds the device, so consent must come from the owner's own phone
        wa = partners.check_owner_code(s["id"], body.owner_code or "")
        if not wa:
            raise HTTPException(403, "Enter the code sent to the owner's phone (it is valid for 10 minutes)")
        s["owner_verified"] = {"wa_masked": "••••••" + wa[-4:], "at": store.now()}
        store.put("session", s["id"], s)
        partners.protect(wa, partner, s["id"])
    if partner and partner["mode"] == "assisted":
        given_by = f"owner by code to {s['owner_verified']['wa_masked']}, assisted by {partner['id']}" if body.accepted else "owner"
    k["consent"] = {"accepted": body.accepted, "version": CONSENT_VERSION, "at": store.now(), "given_by": given_by,
                    "purposes": ["kyc_verification"] + (["service_updates"] if body.whatsapp_updates else [])
                    + (["marketing"] if body.marketing else [])}
    store.put("kyc", body.session_id, k)
    store.audit("customer", "consent_given" if body.accepted else "consent_declined", body.session_id,
                ",".join(k["consent"]["purposes"]))
    return _kyc_view(k)


@app.post("/api/kyc/upload")
async def kyc_upload(session_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    _session(session_id)
    k = _kyc(session_id)
    _require_consent(k)
    if doc_type not in kyc.DOC_TYPES:
        raise HTTPException(400, "Unknown document type")
    if file.content_type not in ALLOWED_IMAGE:
        raise HTTPException(415, "Please upload a photo (JPG, PNG or WebP)")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Photo is larger than 6 MB")
    try:  # OCR takes a minute on a small server: run it off the event loop, one photo at a time, so chats go on
        res = await anyio.to_thread.run_sync(kyc.extract_document, data, doc_type, limiter=OCR_SLOTS)
    except ValueError:
        raise HTTPException(400, "Could not read this file as an image")
    del data  # the image is never stored; only extracted fields and a SHA-256 fingerprint are kept
    res["uploaded_at"], res["source"] = store.now(), "upload"
    k["docs"][doc_type] = res
    k["result"] = None
    store.put("kyc", session_id, k)
    store.audit("customer", "document_uploaded", session_id, f"{doc_type} sha256={res['sha256'][:12]}")
    return _kyc_view(k)


class SampleIn(BaseModel):
    session_id: str
    applicant: str = Field(pattern=r"^K\d{2}$")


@app.get("/api/kyc/samples")
def kyc_samples():
    out = {}
    for p in sorted((DATA_DIR / "kyc_documents").glob("K*.png")):
        app_id, dt = p.stem.split("_", 1)
        out.setdefault(app_id, []).append(dt)
    return out


@app.get("/api/kyc/samples/{name}")
def kyc_sample_image(name: str):
    p = DATA_DIR / "kyc_documents" / f"{name}.png"
    if not p.exists() or not p.stem.startswith("K"):
        raise HTTPException(404, "No such sample")
    return FileResponse(p)


@app.post("/api/kyc/sample")
def kyc_use_sample(body: SampleIn):
    """Demo helper: runs a specimen applicant's documents through the exact same upload pipeline."""
    _session(body.session_id)
    k = _kyc(body.session_id)
    _require_consent(k)
    k["docs"] = {}
    for p in sorted((DATA_DIR / "kyc_documents").glob(f"{body.applicant}_*.png")):
        dt = p.stem.split("_", 1)[1]
        res = kyc.extract_document(p.read_bytes(), dt)
        res["uploaded_at"], res["source"] = store.now(), f"specimen {body.applicant}"
        k["docs"][dt] = res
    k["result"] = None
    store.put("kyc", body.session_id, k)
    return _kyc_view(k)


@app.post("/api/kyc/digilocker/{sid}")
def kyc_digilocker(sid: str):
    """Mock DigiLocker / GSTN pull: verified data straight from the source, no photos needed."""
    s = _session(sid)
    k = _kyc(sid)
    _require_consent(k)
    gstin = s["profile"].get("gstin")
    rec = gstin_registry().get(gstin or "")
    if not rec:
        raise HTTPException(400, "Share a GSTIN in the advisor first to fetch documents from DigiLocker")
    udy = next((u for u in udyam_by_name().get(rec["trade_name"].lower(), []) if u["state"] == rec["state"]), None)
    now = store.now()
    k["docs"]["gst_certificate"] = {"source": "digilocker", "quality_ok": True, "uploaded_at": now, "fields": {
        "gstin": rec["gstin"], "legal_name": rec["legal_name"], "trade_name": rec["trade_name"],
        "constitution": rec["constitution"], "address": rec["principal_place_of_business"],
        "date": rec["registration_date"]}}
    if udy:
        k["docs"]["udyam_certificate"] = {"source": "digilocker", "quality_ok": True, "uploaded_at": now, "fields": {
            "udyam": udy["udyam_number"], "name": udy["enterprise_name"], "state": udy["state"], "city": udy["city"]}}
    k["docs"]["address_proof"] = {"source": "gst_registry", "quality_ok": True, "uploaded_at": now, "fields": {
        "billed_to": rec["trade_name"], "address": rec["principal_place_of_business"], "bill_date": str(TODAY.date())}}
    k["result"] = None
    store.put("kyc", sid, k)
    store.audit("system", "digilocker_fetch", sid, f"gstin={mask(gstin)}")
    return _kyc_view(k)


class EkycIn(BaseModel):
    session_id: str
    name: str = Field(min_length=2, max_length=80)
    otp: str = Field(pattern=r"^\d{6}$")


@app.post("/api/kyc/ekyc")
def kyc_ekyc(body: EkycIn):
    """Mock Aadhaar OTP e-KYC for the authorised signatory (any 6-digit OTP works in the demo)."""
    s = _session(body.session_id)
    k = _kyc(body.session_id)
    _require_consent(k)
    business = s["profile"].get("business_name") or ""
    k["docs"]["signatory_id"] = {"source": "aadhaar_ekyc", "quality_ok": True, "uploaded_at": store.now(), "fields": {
        "name": body.name.strip(), "business": business, "valid_till": "2099-12-31", "id_no": "EKYC-" + body.otp[-3:]}}
    k["result"] = None
    store.put("kyc", body.session_id, k)
    store.audit("customer", "ekyc_completed", body.session_id, "aadhaar_otp")
    return _kyc_view(k)


class AccelKycIn(BaseModel):
    session_id: str
    name: str = Field(min_length=2, max_length=80)
    mobile: str = Field(pattern=r"^[6-9]\d{9}$")
    otp: str = Field(pattern=r"^\d{6}$")


@app.post("/api/kyc/accel")
def kyc_accel(body: AccelKycIn):
    """Reuse the KYC Accel already holds for the owner's Accel mobile number (mock subscriber lookup; any 6-digit
    OTP works in the demo). 30% of leads already use Accel mobile, so they need no new ID document."""
    s = _session(body.session_id)
    k = _kyc(body.session_id)
    _require_consent(k)
    k["docs"]["signatory_id"] = {"source": "accel_kyc", "quality_ok": True, "uploaded_at": store.now(), "fields": {
        "name": body.name.strip(), "business": s["profile"].get("business_name") or "", "valid_till": "2099-12-31",
        "id_no": "ACCEL-" + body.mobile[-4:]}}
    k["result"] = None
    store.put("kyc", body.session_id, k)
    store.audit("customer", "accel_kyc_reused", body.session_id, f"mobile=••{body.mobile[-4:]}")
    return _kyc_view(k)


@app.post("/api/kyc/verify/{sid}")
def kyc_verify(sid: str):
    s = _session(sid)
    k = _kyc(sid)
    _require_consent(k)
    k["result"] = kyc.validate(k["docs"], {"has_gstin": s["profile"].get("has_gstin")})
    if k["result"]["decision"] in ("approved", "review"):
        s["status"] = "kyc_complete"
    else:
        s["status"] = "kyc_started"
    store.put("kyc", sid, k)
    store.put("session", sid, s)
    store.audit("system", f"kyc_{k['result']['decision']}", sid, f"fails={k['result']['fail_count']}")
    return _kyc_view(k)


@app.get("/api/kyc/{sid}")
def kyc_get(sid: str):
    return _kyc_view(_kyc(sid))


# ---------- partner-assisted selling ----------

class AssistIn(BaseModel):
    partner_id: str = Field(max_length=10)
    lang: str = "en"


@app.post("/api/assist/start")
def assist_start(body: AssistIn, request: Request):
    """A partner starts a chat on their own device for the owner sitting with them. The QR lets the owner carry on
    on her own phone at any point; consent and the order are still hers (see /api/assist/owner-code)."""
    if not partners.get(body.partner_id):
        raise HTTPException(404, "Unknown partner")
    out = advisor.start(body.lang, f"partner:{body.partner_id.upper()}", "assisted")
    s = store.get("session", out["session_id"])
    partners.tag(s, body.partner_id, "assisted")
    store.put("session", s["id"], s)
    return {**out, "partner": _partner_view(s), "join_url": f"{_app_url(request)}#/continue/{s['id']}"}


class OwnerCodeIn(BaseModel):
    session_id: str
    phone: str = Field(pattern=r"^[6-9]\d{9}$")


@app.post("/api/assist/owner-code")
def assist_owner_code(body: OwnerCodeIn):
    s = _session(body.session_id)
    if not (s.get("partner") or {}).get("mode") == "assisted":
        raise HTTPException(400, "Only an assisted session needs the owner's code")
    return partners.send_owner_code(s["id"], orders.wa_number(body.phone), s.get("lang", "en"))


@app.get("/api/partners")
def partner_list():
    return [partners.public(p) for p in leads.PARTNERS]


@app.get("/api/console/partners")
def console_partners():
    return partners.summary()


# ---------- orders ----------

class OrderIn(BaseModel):
    session_id: str
    selection: list[Selection]
    contract_months: int = 12
    contact_name: str = Field(min_length=2, max_length=80)
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
    whatsapp_updates: bool = True
    esign_otp: str = Field(pattern=r"^\d{6}$")


@app.post("/api/orders")
def create_order(body: OrderIn):
    s = _session(body.session_id)
    k = _kyc(body.session_id)
    if not k.get("result") or k["result"]["decision"] == "rejected":
        raise HTTPException(409, "KYC must be verified before placing the order")
    p = _profile(s, body.contract_months)
    q = requote(p, [x.model_dump() for x in body.selection])["quote"]
    if not q["lines"]:
        raise HTTPException(400, "Bundle is empty")
    order = orders.create(s, q, k["result"], {"name": body.contact_name, "phone": body.phone,
                                               "whatsapp_updates": body.whatsapp_updates}, esign_ok=True)
    s["status"], s["order_id"] = "order_placed", order["id"]
    store.put("session", s["id"], s)
    return orders.view(order)


@app.get("/api/orders/{oid}")
def get_order(oid: str):
    o = orders.get(oid)
    if not o:
        raise HTTPException(404, "No order with that number")
    return o


@app.post("/api/orders/{oid}/advance")
def advance_order(oid: str):
    return orders.advance(oid.upper())


class SlotIn(BaseModel):
    slot: str = Field(min_length=3, max_length=60)


@app.post("/api/orders/{oid}/slot")
def book_slot(oid: str, body: SlotIn):
    return orders.book_slot(oid.upper(), body.slot)


class TicketIn(BaseModel):
    text: str = Field(min_length=3, max_length=300)


@app.post("/api/orders/{oid}/ticket")
def ticket(oid: str, body: TicketIn):
    return orders.raise_ticket(oid.upper(), body.text)


# ---------- privacy ----------

@app.post("/api/privacy/erase/{sid}")
def erase(sid: str):
    """Right to erasure: removes the session and KYC data; keeps only a minimal audit entry."""
    s = store.get("session", sid)
    if s and s.get("order_id"):
        raise HTTPException(409, "Active connection: data is retained as required by the telecom licence; "
                                 "it will be erased when the connection ends")
    store.delete("session", sid)
    store.delete("kyc", sid)
    wa = (store.get("wa_session", sid) or {}).get("wa")
    if wa:  # the WhatsApp number that chat came from: forget the link both ways
        if (store.get("wa_link", wa) or {}).get("session_id") == sid:
            store.delete("wa_link", wa)
        store.delete("wa_session", sid)
    store.audit("customer", "data_erased", sid, "")
    return {"erased": True}


# ---------- partner / sales console ----------

@app.get("/api/console/leads")
def console_leads():
    return {"live": leads.live_leads(), "pipeline": leads.call_list(40)}


@app.get("/api/console/model")
def console_model():
    return leads.model_card()


@app.get("/api/console/overview")
def console_overview():
    d = lead_data()
    sessions = store.list_("session", 500)
    stages = ["advisor_started", "needs_assessed", "quote_viewed", "kyc_started", "kyc_complete", "order_placed"]
    rank = {s: i for i, s in enumerate(stages)}
    live = {st: sum(1 for s in sessions if rank.get(s.get("status"), 0) >= i) for i, st in enumerate(stages)}
    act = d[d.outcome == "Activated"]
    return {
        "baseline": {"leads": int(len(d)), "activated": int(len(act)), "conversion": round(len(act) / len(d), 3),
                     "days_to_activate": round(float(act.days_lead_to_activation.mean()), 1),
                     "follow_up_calls": round(float(act.customer_follow_up_calls.mean()), 1),
                     "cac": int(d.acquisition_cost_inr.sum() / len(act))},  # blended: all spend / activations
        "live_funnel": live,
        "orders": [{"id": o["id"], "business": o["business"], "city": o["city"], "stage": dict(orders.STAGES).get(o["stage"], o["stage"]),
                    "monthly": o["quote"]["monthly"], "created": o["created"]} for o in store.list_("order", 50)],
    }


@app.get("/api/console/audit")
def console_audit():
    return store.audit_log(limit=60)


# ---------- frontend ----------

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
