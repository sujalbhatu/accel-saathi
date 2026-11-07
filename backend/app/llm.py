"""Thin client for any OpenAI-compatible chat API (Gemini, Groq, xAI, OpenAI, Azure...), with a fallback chain and
a hard spending cap.

Configured only through environment variables, so no key ever lives in code:
  LLM_API_KEY            enables the main provider; without any key the advisor runs on rules alone
  LLM_BASE_URL           default: Google Gemini's OpenAI-compatible endpoint
  LLM_MODEL              default: gemini-3.5-flash-lite
  LLM_FALLBACK_MODELS    comma list on the same provider, tried when a model is rate-limited or down
                         (Gemini default: gemini-3.1-flash-lite, which has its own quota)
  GROQ_API_KEY           optional second provider (free plan): about 1 s per answer where free Gemini takes several
  GROQ_MODEL             default: openai/gpt-oss-120b
  LLM_FAST_LANGS         languages that try Groq first, default "en,hi"; the others try Gemini first, since it
                         handles regional scripts better
  LLM_BUDGET_INR         hard cap on AI spend per calendar month, default 150. Spend is counted from the token usage
                         every reply reports, at LLM_PRICE_IN / LLM_PRICE_OUT (US$ per million tokens, defaults
                         0.30 / 2.50 for gemini-3.5-flash-lite) and USD_INR (default 88). 0 turns the cap off.
  LLM_DAILY_CALL_LIMIT   default 400 calls a day; LLM_SESSION_CALL_LIMIT default 30 calls per chat
Every call has a short time budget and returns None on any failure, so callers always fall back to rules.
Once a cap is reached the app keeps working on rules (and on Groq's free plan, which costs nothing).
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone

import httpx

from . import privacy

log = logging.getLogger("llm")

GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"
BASE_URL = os.getenv("LLM_BASE_URL", GEMINI).rstrip("/")
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "10"))
_GEMINI_FALLBACKS = "gemini-3.1-flash-lite"  # 2.5-flash-lite is retired (404)
FALLBACKS = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", _GEMINI_FALLBACKS if "generativelanguage" in BASE_URL
                                          else "").split(",") if m.strip() and m.strip() != MODEL]
GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FAST_LANGS = {code.strip() for code in os.getenv("LLM_FAST_LANGS", "en,hi").split(",") if code.strip()}


def _num(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


BUDGET_INR = _num("LLM_BUDGET_INR", 150)
PRICE_IN, PRICE_OUT, USD_INR = _num("LLM_PRICE_IN", 0.30), _num("LLM_PRICE_OUT", 2.50), _num("USD_INR", 88)
DAILY_LIMIT, SESSION_LIMIT = int(_num("LLM_DAILY_CALL_LIMIT", 400)), int(_num("LLM_SESSION_CALL_LIMIT", 30))

_lock = threading.Lock()
_cooldown: dict[str, float] = {}  # "provider" or "provider/model" -> monotonic time it may be used again
_no_reasoning: set[str] = set()  # models that rejected the reasoning_effort option


def _route(lang: str | None = None) -> list[dict]:
    """The providers and models to try, best first for this language."""
    main = [{"provider": "main", "url": BASE_URL, "key": os.environ["LLM_API_KEY"], "model": m, "paid": True}
            for m in [MODEL] + FALLBACKS] if os.getenv("LLM_API_KEY") else []
    groq = [{"provider": "groq", "url": GROQ_URL, "key": os.environ["GROQ_API_KEY"], "model": GROQ_MODEL,
             "paid": False}] if os.getenv("GROQ_API_KEY") else []
    return groq + main if lang in FAST_LANGS else main + groq


def enabled() -> bool:
    return bool(_route())


def _cool(name: str, seconds: float) -> None:
    _cooldown[name] = max(_cooldown.get(name, 0), time.monotonic() + seconds)


def _ready(r: dict) -> bool:
    now = time.monotonic()
    return now >= _cooldown.get(r["provider"], 0) and now >= _cooldown.get(f"{r['provider']}/{r['model']}", 0)


# ---------- spending: counted in the app database, so a restart never resets it ----------

def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def usage() -> dict:
    from . import store
    u = store.get("llm_usage", _month()) or {}
    return {"month": _month(), "inr": round(u.get("inr", 0.0), 2), "calls": u.get("calls", 0),
            "today": (u.get("days") or {}).get(_day(), 0), "budget_inr": BUDGET_INR, "daily_limit": DAILY_LIMIT,
            "by_model": u.get("by_model", {})}


def _paid_allowed() -> bool:
    u = usage()
    if BUDGET_INR and u["inr"] >= BUDGET_INR:
        return False
    return not DAILY_LIMIT or u["today"] < DAILY_LIMIT


CALL_LOG = os.getenv("LLM_CALL_LOG", "")  # optional: one JSON line per AI call, for the cost and latency evals


def _log_call(r: dict, tin: int, tout: int, ms: float, session: dict | None, lang: str | None) -> None:
    """Passive metering: writes what a call used and nothing else, so it can never change an answer."""
    if not CALL_LOG:
        return
    line = {"at": time.time(), "provider": r["provider"], "model": r["model"], "tokens_in": tin, "tokens_out": tout,
            "ms": round(ms), "session": (session or {}).get("id"), "lang": lang}
    with _lock, open(CALL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def _record(r: dict, data: dict, ms: float = 0.0, session: dict | None = None, lang: str | None = None) -> None:
    from . import store
    tok = data.get("usage") or {}
    tin = int(tok.get("prompt_tokens") or 0)
    tout = max(int(tok.get("total_tokens") or 0) - tin, int(tok.get("completion_tokens") or 0))  # includes thinking
    _log_call(r, tin, tout, ms, session, lang)
    inr = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6 * USD_INR if r["paid"] else 0.0
    with _lock:
        u = store.get("llm_usage", _month()) or {"inr": 0.0, "calls": 0, "tokens_in": 0, "tokens_out": 0, "days": {}}
        u["inr"] += inr
        u["calls"] += 1
        u["tokens_in"] += tin
        u["tokens_out"] += tout
        days, models = u.setdefault("days", {}), u.setdefault("by_model", {})  # older months lack these keys
        days[_day()] = days.get(_day(), 0) + 1
        models[r["model"]] = models.get(r["model"], 0) + 1
        store.put("llm_usage", _month(), u)
    if BUDGET_INR and u["inr"] >= BUDGET_INR:
        log.warning("AI budget of Rs %s reached for %s: paid calls stop until next month", BUDGET_INR, _month())


def session_allowed(session: dict | None) -> bool:
    """At most LLM_SESSION_CALL_LIMIT AI calls per chat, so one person can't run up the bill."""
    return not session or not SESSION_LIMIT or session.get("llm_calls", 0) < SESSION_LIMIT


def available() -> bool:
    paid_ok = None
    for r in _route():
        if not _ready(r):
            continue
        if r["paid"]:
            paid_ok = _paid_allowed() if paid_ok is None else paid_ok
            if not paid_ok:
                continue
        return True
    return False


def _post(r: dict, body: dict, timeout: float) -> httpx.Response:
    body = {**body, "model": r["model"]}
    if "generativelanguage" in r["url"] and r["model"] not in _no_reasoning:
        body["reasoning_effort"] = os.getenv("LLM_REASONING_EFFORT", "minimal")
    elif r["provider"] == "groq" and "gpt-oss" in r["model"]:
        body["reasoning_effort"] = "low"
    headers = {"Authorization": f"Bearer {r['key']}"}
    resp = httpx.post(f"{r['url']}/chat/completions", json=body, timeout=timeout, headers=headers)
    if resp.status_code == 400 and "reasoning_effort" in body:  # a model without that option: stop sending it
        _no_reasoning.add(r["model"])
        body.pop("reasoning_effort")
        resp = httpx.post(f"{r['url']}/chat/completions", json=body, timeout=timeout, headers=headers)
    return resp


def chat(messages: list[dict], json_mode: bool = False, max_tokens: int = 600, session: dict | None = None,
         lang: str | None = None) -> str | None:
    """One answer from the first model in the chain that is up, under quota and under budget. At most three models
    are tried per message, inside one time budget, so the owner never waits long."""
    if not session_allowed(session):
        return None
    # tokenise personal data before it leaves for an outside model; tokens are swapped back in the answer
    prof = (session or {}).get("profile") or {}
    texts, mapping = privacy.tokenize([m.get("content") or "" for m in messages],
                                      [prof.get("business_name") or "", prof.get("contact_name") or ""])
    messages = [{**m, "content": t} for m, t in zip(messages, texts)]
    body = {"messages": messages, "temperature": 0.2, "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    deadline, tried = time.monotonic() + TIMEOUT + 2, 0
    for r in _route(lang):
        left = deadline - time.monotonic()
        if tried >= 3 or left < 2:
            break
        if not _ready(r) or (r["paid"] and not _paid_allowed()):
            continue
        tried += 1
        t0 = time.monotonic()
        try:
            resp = _post(r, body, min(TIMEOUT, left))
        except httpx.TransportError as e:  # timeout, connection refused, DNS
            log.warning("LLM %s unreachable: %s", r["model"], type(e).__name__)
            _cool(f"{r['provider']}/{r['model']}", 30)
            continue
        code = resp.status_code
        if code == 200:
            try:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError):
                log.warning("LLM %s sent an unreadable answer", r["model"])
                continue
            try:
                _record(r, data, (time.monotonic() - t0) * 1000, session, lang)
            except Exception:  # counting spend must never cost the owner their answer
                log.exception("LLM usage not recorded")
            if session is not None:
                session["llm_calls"] = session.get("llm_calls", 0) + 1
                if mapping:
                    session["llm_tokenised"] = session.get("llm_tokenised", 0) + len(mapping)
            return privacy.detokenize(text, mapping)
        wait = resp.headers.get("retry-after", "")
        wait_s = float(wait) if wait.replace(".", "").isdigit() else 0
        if code == 402:  # prepaid credit used up: this provider is out until someone tops up
            _cool(r["provider"], 3600)
        elif code == 429:  # this model's quota (per minute or per day) is used up: try the next model
            _cool(f"{r['provider']}/{r['model']}", wait_s or 60)
        elif code in (401, 403):  # bad or revoked key
            _cool(r["provider"], 600)
        elif code == 404:  # model name not offered to this key
            _cool(f"{r['provider']}/{r['model']}", 24 * 3600)
        elif code >= 500:
            _cool(f"{r['provider']}/{r['model']}", wait_s or 30)
        log.warning("LLM %s answered HTTP %s", r["model"], code)
    return None


def chat_json(messages: list[dict], max_tokens: int = 600, session: dict | None = None,
              lang: str | None = None) -> dict | None:
    out = chat(messages, json_mode=True, max_tokens=max_tokens, session=session, lang=lang)
    if not out:
        return None
    out = out.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(out)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
