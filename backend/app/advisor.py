"""Conversational needs discovery.

A small state machine asks only for what it still needs (business type, city, team size, sites, GSTIN),
lets the owner answer in free text or by tapping chips, confirms needs, then hands the profile to the
deterministic recommender. An LLM, when configured, improves understanding and phrasing; it never
changes products or prices.

After the bundle is shown, a question is never an order: "can I skip CCTV?" or "12 or 24 months?" gets an answer
with the exact saving or cost and a button to make the change, and every change can be undone. Every item comes
with a plain-language card (what it is, why it is there, what happens without it, ₹ a day), and the owner can
switch between three levels: Basic, Recommended and Complete.
"""
import copy
import json
import os
import re

from . import assistant, cards, guard, knowledge, pains, privacy, ranker, store
from .data import gstin_registry, udyam_by_name
from .extract import clean_llm_facts, extract
from .i18n import LANGS, need_label, t
from .ids import mask, validate_gstin
from .recommender import (CONN_DOWNGRADE, CONNECTIVITY, NEEDS, Profile, _NEED_OF, default_needs, infer_segment, typical_needs,
                          recommend, resolve_location)

_PID_OF = {need: pid for pid, need in _NEED_OF.items()}
from .data import products

SLOT_ORDER = ["business_type", "city", "employees", "sites", "gstin"]
# words that answer nothing about the business ("status", "help", "ok"): never taken as the kind of business
_NOT_A_BUSINESS = re.compile(r"^\W*(?:status|order|track|reschedule|problem|help|menu|start|hi+|hello|hey|namaste|"
                             r"ok(?:ay)?|yes|no|thanks?|thank you|stop|test|what|why|how)\b", re.I)

BUSINESS_CHIPS = [
    ("Kirana / retail shop", "Kirana store"), ("Salon / boutique", "Salon"), ("Pharmacy", "Pharmacy"),
    ("Clinic / lab", "Dental clinic"), ("CA / law / office", "CA firm"), ("Coaching centre", "Coaching centre"),
    ("Restaurant / hotel chain", "Restaurant chain"), ("Retail chain (3+ stores)", "Apparel retail chain"),
    ("Factory / workshop", "Auto-parts unit"),
]
EMPLOYEE_CHIPS = [("1–5", 3), ("6–20", 12), ("21–50", 35), ("51–150", 90), ("150+", 160)]
SITE_CHIPS = [("1", 1), ("2", 2), ("3–5", 4), ("6–10", 8), ("10+", 12)]
CITY_CHIPS = ["Delhi", "Mumbai", "Bengaluru", "Pune", "Jaipur", "Lucknow", "Nagpur", "Indore"]


def _profile(s: dict) -> Profile:
    d = dict(s["profile"])
    d["needs"] = set(d.get("needs", []))
    d["explicit_needs"] = set(d.get("explicit_needs", []))
    d["asked_needs"] = set(d.get("asked_needs", []))
    return Profile(**d)


def _profile_dict(p: Profile) -> dict:
    d = copy.deepcopy(dict(p.__dict__))
    d["needs"] = sorted(p.needs)
    d["explicit_needs"] = sorted(p.explicit_needs)
    d["asked_needs"] = sorted(p.asked_needs)
    return d


def _save_profile(s: dict, p: Profile) -> None:
    s["profile"] = _profile_dict(p)


def _city_from_address(addr: str) -> str:
    m = re.search(r",\s*([A-Za-z .]+),\s*[A-Za-z .]+\s*-\s*\d{6}", addr or "")
    return m.group(1).strip() if m else ""


def _gstin_lookup(raw: str) -> dict:
    v = validate_gstin(raw)
    if not v["valid"]:
        return {"ok": False, "kind": "invalid", "reason": v["reason"], "gstin": v["gstin"]}
    rec = gstin_registry().get(v["gstin"])
    if not rec:
        return {"ok": False, "kind": "not_found", "gstin": v["gstin"]}
    udyam = next((u for u in udyam_by_name().get(rec["trade_name"].lower(), []) if u["state"] == rec["state"]), None)
    return {"ok": True, "gstin": v["gstin"], "record": rec, "udyam": udyam}


def _first_number(text: str) -> int | None:
    from .extract import _DEVANAGARI, _WORDS
    low = text.translate(_DEVANAGARI).lower()
    m = re.search(r"\d+", low)
    if m:
        return int(m.group(0))
    if re.search(r"\b(?:single|only|just|sirf|bas)\b", low) and not re.search(r"\d", low):
        for w in re.findall(r"[\w\u0900-\u097f]+", low):
            if w in _WORDS:
                return _WORDS[w]
        return 1
    return next((_WORDS[w] for w in re.findall(r"[\w\u0900-\u097f]+", low) if w in _WORDS), None)


def _chips(slot: str, lang: str) -> list[dict]:
    if slot == "business_type":
        return [{"label": l, "slot": slot, "value": v} for l, v in BUSINESS_CHIPS]
    if slot == "employees":
        return [{"label": l, "slot": slot, "value": v} for l, v in EMPLOYEE_CHIPS]
    if slot == "sites":
        return [{"label": l, "slot": slot, "value": v} for l, v in SITE_CHIPS]
    if slot == "city":
        return [{"label": c, "slot": slot, "value": c} for c in CITY_CHIPS]
    if slot == "gstin":
        return [{"label": t(lang, "chip_no_gstin"), "slot": "gstin", "value": "none"}]
    if slot == "gstin_confirm":
        return [{"label": t(lang, "chip_gstin_yes"), "slot": slot, "value": "yes"},
                {"label": t(lang, "chip_gstin_no"), "slot": slot, "value": "no"}]
    if slot == "current":
        return [{"label": t(lang, f"chip_cur_{v}"), "slot": slot, "value": v} for v in CURRENT_CHOICES]
    return []


CURRENT_CHOICES = ["hotspot", "home", "business", "leased", "none"]
# What the owner uses for internet today, from free text (the categories match current_internet in smb_leads.csv).
_CURRENT = [
    ("none", r"\bnothing\b|\bnone\b|no (?:internet|wi-?fi|connection|broadband)|not yet|kuch nahi|kuchh nahi|"
             r"कुछ नहीं|काही नाही|எதுவும் இல்லை"),
    ("hotspot", r"hotspot|(?:phone|mobile) (?:data|internet|net)|my phone|फोन का|फ़ोन का|हॉटस्पॉट|मोबाइल डेटा|"
                r"मोबाइल का नेट|மொபைல் டேட்டா"),
    ("leased", r"leased|dedicated (?:line|internet)|\bill\b|लीज़्ड|लीज्ड"),
    ("home", r"\bhome\b|\bghar\b|घर|घरचा|வீட்டு"),
    ("business", r"broadband|fib(?:re|er)|wi-?fi|\bjio\b|airtel|hathway|excitel|bsnl|local (?:isp|cable)|cable|"
                 r"ब्रॉडबैंड|वाईफाई|वाई-फाई|फाइबर|ப்ராட்பேண்ட்"),
]
_CURRENT_CONTEXT = r"\b(?:use|using|used|have|has|currently|right now|today|at the moment|abhi|chal raha|chalta)\b|अभी|चल रहा"


def current_from_text(text: str, strict: bool = True) -> str | None:
    """The owner's current internet, if the message says it. strict: only when they say they use or have it."""
    low = text.lower()
    if strict and not re.search(_CURRENT_CONTEXT, low):
        return None
    return next((kind for kind, pat in _CURRENT if re.search(pat, low)), None)


def start(lang: str = "en", source: str = "web", channel: str = "app") -> dict:
    lang = lang if lang in LANGS else "en"
    s = {"id": store.new_id("ses"), "lang": lang, "source": source, "channel": channel, "stage": "chat",
         "profile": {}, "history": [], "created": store.now(), "status": "advisor_started",
         "pending_slot": "business_type", "misses": 0}
    _save_profile(s, Profile())
    reply = {"messages": [t(lang, "greet")], "chips": _chips("business_type", lang), "input": "text"}
    s["history"].append({"role": "assistant", "text": reply["messages"][0]})
    store.put("session", s["id"], s)
    store.audit("advisor", "session_started", s["id"], f"lang={lang} source={source}")
    return {"session_id": s["id"], **reply, "stage": "chat"}


def _apply(p: Profile, facts: dict, lang: str, notes: list[str], s: dict | None = None) -> None:
    for k in ("business_type", "employees", "sites", "current_spend", "budget", "fibre_available", "current_internet"):
        if k in facts:
            setattr(p, k, facts[k])
    if "city" in facts:
        p.city, p.city_tier, p.state = facts["city"], None, ""
        resolve_location(p)
    if facts.get("needs"):
        p.explicit_needs |= set(facts["needs"])
        p.asked_needs |= set(facts["needs"])
        if p.needs_confirmed:
            p.needs |= set(facts["needs"])
    if facts.get("counts"):
        p.counts.update(facts["counts"])
    heard = [k for k in dict.fromkeys(facts.get("pains") or []) if k not in p.pains]
    p.pains += heard
    if heard and s is not None and s.get("stage", "chat") == "chat":  # told before the checklist: show she was heard
        notes.append(t(lang, "pain_heard", pains=", ".join(f"“{t(lang, f'pain_{k}')}”" for k in heard[:3])))
    if facts.get("has_gstin") is True and not facts.get("gstin") and p.has_gstin is None:
        p.has_gstin = True
    if facts.get("has_gstin") is False and not facts.get("gstin"):
        if p.has_gstin is not False:  # say it once, not again when the AI repeats a fact it already had
            notes.append(t(lang, "no_gstin_ok"))
        p.has_gstin, p.gstin, p.gstin_verified = False, "", None
    if facts.get("gstin"):
        res = _gstin_lookup(facts["gstin"])
        if res["ok"] and s is not None and s.get("stage") != "done":
            # Show what the registry says and let the owner confirm it is theirs before using it.
            rec = res["record"]
            s["gstin_check"] = res["gstin"]
            city = _city_from_address(rec["principal_place_of_business"]) or rec["state"]
            notes.append(t(lang, "gstin_confirm", name=rec["trade_name"], city=city, status=rec["status"]))
        elif res["ok"]:
            _use_gstin(p, res, lang, notes)
        elif res["kind"] == "invalid":
            notes.append(t(lang, "gstin_invalid", reason=res["reason"]))
        else:
            notes.append(t(lang, "gstin_not_found"))


def _use_gstin(p: Profile, res: dict, lang: str, notes: list[str], confirmed: bool = False) -> None:
    rec = res["record"]
    p.has_gstin, p.gstin = True, res["gstin"]
    p.gstin_verified = rec["status"] == "Active"
    p.business_name = rec["trade_name"]
    reg_city = _city_from_address(rec["principal_place_of_business"])
    if reg_city:  # the registry address is authoritative over what was typed earlier
        p.city, p.city_tier, p.state = reg_city, None, ""
        resolve_location(p)
    p.state = rec["state"]
    if res["udyam"] and not p.business_type:
        p.business_type = res["udyam"]["nic_description"]
    notes.append(t(lang, "gstin_confirmed") if confirmed else
                 t(lang, "gstin_found", name=rec["trade_name"], city=p.city or rec["state"], status=rec["status"]))
    if not p.gstin_verified:
        notes.append(t(lang, "gstin_inactive", status=rec["status"].lower()))


def _gstin_answer(s: dict, p: Profile, yes: bool, lang: str) -> dict:
    """The owner confirmed (or rejected) the business the GST registry returned for their GSTIN."""
    gstin = s.pop("gstin_check", None)
    if yes and gstin:
        msgs: list[str] = []
        _use_gstin(p, _gstin_lookup(gstin), lang, msgs, confirmed=True)
        s["pending_slot"] = None
        return _continue(s, p, msgs, lang)
    p.has_gstin, p.gstin, p.gstin_verified = None, "", None
    s["pending_slot"] = "gstin"
    return {"messages": [t(lang, "gstin_wrong")], "chips": _chips("gstin", lang)}


def _next_slot(p: Profile) -> str | None:
    missing = p.missing()
    return next((s for s in SLOT_ORDER if s in missing), None)


def _question(slot: str, lang: str) -> str:
    return t(lang, f"ask_{slot}")


def _needs_payload(p: Profile, lang: str) -> dict:
    p.segment = infer_segment(p)
    pre = default_needs(p)
    if p.has_gstin is False:  # don't pre-tick services that need a GSTIN the owner doesn't have
        pre = {n for n in pre if not all(products()[pid].requires_gstin for pid, need in _NEED_OF.items() if need == n)}
    pre |= p.explicit_needs
    order = sorted(NEEDS, key=lambda n: (n not in pre, NEEDS.index(n)))
    return {"needs": [{"key": n, "label": need_label(lang, n), "selected": n in pre} for n in order]}


def _pain_chips(p: Profile, lang: str) -> list[dict]:
    """Two or three questions about the business, as taps: a salesperson asks about problems, not products."""
    keys = pains.to_ask(infer_segment(p), p.business_type, p.pains)
    chips = [{"label": t(lang, f"pain_{k}"), "slot": "pain", "value": k} for k in keys]
    return chips + [{"label": t(lang, "chip_pain_none"), "slot": "pain", "value": "none"}] if chips else []


def _pain_answer(s: dict, p: Profile, key: str, lang: str) -> dict:
    """The owner tapped a problem: tick what fixes it, say so, and ask the next one."""
    if s["stage"] != "needs":
        return _continue(s, p, [], lang)
    if key in pains.PAINS and key not in p.pains:
        p.pains.append(key)
        fix = pains.needs_for([key])
        p.explicit_needs |= set(fix)
        p.asked_needs |= set(fix)
        return {"messages": [t(lang, "pain_got", fix=assistant.names(lang, fix))], "chips": _pain_chips(p, lang),
                **_needs_payload(p, lang)}
    return {"messages": [t(lang, "pain_none")], "chips": [], **_needs_payload(p, lang)}


def _reason_text(lang: str, reason: str) -> str:
    if reason.startswith("alt_for:"):
        return t(lang, "r_alt_for", name=products()[reason.split(":")[1]].name)
    return t(lang, f"r_{reason}")


def _localise(rec: dict, lang: str, p: Profile | None = None) -> dict:
    for line in rec["quote"]["lines"] + rec.get("suggested", []):
        line["reason_text"] = _reason_text(lang, line["reason"])
        cards.enrich(line, lang, rec["segment"], p.asked_needs if p else set(), p.explicit_needs if p else set(),
                     p.business_type if p else "")
    for b in rec["blocked"]:
        b["name"] = products()[b["id"]].name
        b["plain"] = cards.plain(lang, b["id"])
        b["why_text"] = t(lang, f"why_{b['why']}")
        b["alternative_name"] = products()[b["alternative"]].name if b.get("alternative") else None
    return rec


def _sig(rec: dict) -> str:
    q = rec["quote"]
    return ";".join(f"{l['id']}x{l['qty']}" for l in q["lines"]) + f"@{q['term_months']}"


# ---------- three levels: Basic, Recommended, Complete ----------

def _level_profiles(p: Profile) -> dict[str, Profile]:
    """Basic keeps the internet line, one phone line and only what the owner asked for. Complete keeps every service
    businesses like this one usually take, without holding any back as an add-on."""
    in_bundle = {_NEED_OF.get(l["id"]) for l in recommend(copy.deepcopy(p))["quote"]["lines"] if l["reason"] != "addon"
                 and not l["reason"].startswith("alt_for:")}
    keep = {n for n in p.asked_needs if n in in_bundle}  # never a service the recommendation itself doesn't have
    basic = copy.deepcopy(p)
    basic.needs_confirmed, basic.needs, basic.explicit_needs, basic.asked_needs = True, set(keep), set(keep), set(keep)
    if "mobile_lines" not in p.counts:
        basic.counts["mobile_lines"] = 1
    complete = copy.deepcopy(p)
    complete.full = True
    complete.needs |= default_needs(p) | typical_needs(p)
    return {"basic": basic, "recommended": copy.deepcopy(p), "complete": complete}


def _compute_levels(s: dict, p: Profile) -> None:
    levels, seen = {}, {}
    for key, q in _level_profiles(p).items():
        r = recommend(copy.deepcopy(q))
        sig = _sig(r)
        if key != "recommended" and sig == seen.get("recommended"):
            continue  # same as the recommendation: don't offer it twice
        seen[key] = sig
        levels[key] = {"profile": _profile_dict(q), "monthly": r["quote"]["monthly"], "count": len(r["quote"]["lines"]),
                       "sig": sig}
    s["levels"] = levels if len(levels) > 1 else {}


def _level_cards(s: dict, rec: dict, lang: str) -> list[dict]:
    sig = _sig(rec)
    return [{"key": k, "label": t(lang, f"opt_{k}"), "monthly": v["monthly"], "count": v["count"], "current": v["sig"] == sig}
            for k, v in (s.get("levels") or {}).items()]


def _cap(x: str | None) -> str | None:
    return x[:1].upper() + x[1:] if x and x[:1].islower() else x


def _why_bundle(s: dict, p: Profile, rec: dict) -> list[dict]:
    """The four steps behind this bundle, in the owner's language: what we understood from her, what the catalogue
    rules checked, how similar Accel customers ranked the services, and which level she is on."""
    lang, q = s["lang"], rec["quote"]
    heard = [x for x in (
        _cap(_local(lang, "bt", p.business_type) or rec["segment_name"]),
        _local(lang, "city", p.city),
        t(lang, "why_people", n=p.employees) if p.employees else None,
        t(lang, "why_n_sites", n=p.sites) if p.sites and p.sites > 1 else None,
        t(lang, f"chip_cur_{p.current_internet}") if p.current_internet in CURRENT_CHOICES else None,
        t(lang, "why_gst_ok") if p.gstin_verified else (t(lang, "why_no_gst") if p.has_gstin is False else None),
    ) if x]
    if p.pains:
        heard.append(t(lang, "why_said", pains=", ".join(f"“{t(lang, f'pain_{k}')}”" for k in p.pains[:3])))
    asked = sorted(p.asked_needs | p.explicit_needs)
    if asked:
        heard.append(t(lang, "why_wants", needs=", ".join(need_label(lang, n) for n in asked[:4])))
    checked = len(products())
    blocked = len(rec.get("blocked") or [])
    sim = ranker.similar(rec["segment"], p.business_type)
    who = (_local(lang, "bt", sim["label"]) if sim["kind"] == "type" else rec["segment_name"])
    level = next((o["label"] for o in rec.get("options") or [] if o.get("current")), None)
    return [
        {"title": t(lang, "why_step_heard"), "text": " · ".join(heard)},
        {"title": t(lang, "why_step_rules"),
         "text": t(lang, "why_rules_blocked" if blocked else "why_rules", n=checked, k=blocked, kept=len(q["lines"]))},
        {"title": t(lang, "why_step_ranked"),
         "text": t(lang, "why_ranked_type" if sim["kind"] == "type" else "why_ranked_seg", who=who, n=sim["n"], m=sim["segment_n"])},
        {"title": t(lang, "why_step_level"),
         "text": t(lang, "why_level", level=level, basic=t(lang, "opt_basic"), complete=t(lang, "opt_complete")) if level else t(lang, "why_level_one")},
    ]


def _local(lang: str, kind: str, value: str | None) -> str | None:
    """A business type or city from our lists in the owner's language ("Pune" -> "पुणे"); anything else as typed."""
    if not value:
        return value
    key = f"{kind}_" + re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    out = t(lang, key)
    return value if out == key else out


def _explain(p: Profile, rec: dict, lang: str, levels: dict | None = None) -> list[str]:
    """The bundle in the owner's own terms: what it costs, how it answers what they told us, and the other levels.
    Written from the locale files, so it needs no AI call and reads the same on WhatsApp."""
    q = rec["quote"]
    business = p.business_name or _local(lang, "bt", p.business_type) or rec["segment_name"]
    msgs = [t(lang, "summary", business=business, city=_local(lang, "city", p.city) or t(lang, "your_city"),
              employees=p.employees or 1,
              count=len(q["lines"]), monthly=f"{q['monthly']:,}", days=q["activation_days"])
            .replace("with 1 people", "with 1 person")]
    yours = []
    if p.current_internet in CURRENT_CHOICES:
        yours.append(t(lang, f"cur_{p.current_internet}"))
    if p.current_spend:
        yours.append(t(lang, "cur_spend", spend=_money(p.current_spend), monthly=_money(q["monthly"]), count=len(q["lines"])))
    asked = [l["plain"] for l in q["lines"] if l.get("asked")]
    if asked:
        yours.append(t(lang, "asked_in", names=", ".join(asked)))
    if yours:
        msgs.append(" ".join(yours))
    for b in rec["blocked"][:2]:
        msgs.append(t(lang, "blocked_line", name=b["plain"], why=b["why_text"]))
    levels = levels or {}
    if "basic" in levels and "complete" in levels:
        msgs.append(t(lang, "options_line", basic=_money(levels["basic"]["monthly"]),
                      complete=_money(levels["complete"]["monthly"])))
    elif "basic" in levels:
        msgs.append(t(lang, "options_line_basic", basic=_money(levels["basic"]["monthly"])))
    elif "complete" in levels:
        msgs.append(t(lang, "options_line_complete", complete=_money(levels["complete"]["monthly"])))
    msgs.append(t(lang, "ready"))
    return msgs


def _recommend(s: dict, p: Profile) -> dict:
    rec = _localise(recommend(p), s["lang"], p)
    s["stage"], s["status"] = "done", "quote_viewed"
    s["recommendation"] = rec
    _save_profile(s, p)
    lean = s.pop("lean", False) and (not p.budget or rec["quote"]["monthly"] > p.budget)
    if not lean:
        _compute_levels(s, p)
    msgs = _explain(p, rec, s["lang"], s.get("levels"))
    if lean:
        # the owner asked for a low price before seeing the bundle: apply the same cuts as "make it cheaper"
        snapshot, before = copy.deepcopy(s["profile"]), _fingerprint(rec)
        msgs[-1:-1] = _cheaper(s, p, p.budget, s["lang"])
        if _fingerprint(s["recommendation"]) != before:
            s["undo"] = snapshot
        _compute_levels(s, p)
        rec = s["recommendation"]
    rec["options"] = _level_cards(s, rec, s["lang"])
    rec["why"] = _why_bundle(s, p, rec)
    _save_profile(s, p)
    store.audit("advisor", "bundle_recommended", s["id"], f"segment={rec['segment']} monthly={rec['quote']['monthly']}")
    return {"messages": msgs, "chips": [], "recommendation": rec}


def _public_profile(p: Profile) -> dict:
    return {"business_name": p.business_name, "business_type": p.business_type, "segment": p.segment,
            "city": p.city, "state": p.state, "city_tier": p.city_tier, "employees": p.employees, "sites": p.sites,
            "has_gstin": p.has_gstin, "gstin_masked": mask(p.gstin), "gstin_verified": p.gstin_verified,
            "contract_months": p.contract_months}


# ---------- follow-up turns: questions and changes at any step ----------

_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?([6-9]\d{9})(?!\d)")
_YES = re.compile(r"^\s*(?:yes|yeah|yup|haan|han|ha|हाँ|हां|होय|हो|ஆம்)(?=$|[\s!.,?])", re.I)
_NO = re.compile(r"^\s*(?:no|nope|nahi|nahin|नहीं|नही|नाही|இல்லை)(?=$|[\s!.,?])", re.I)
# answers to "do you have a GST number?" that mean "not for now"
_NOT_YET = re.compile(r"\bnot yet\b|\bappl(?:ied|ying)\b|\bpending\b|\bawaited\b|in process|under process|abhi nahi|aaya nahi|"
                      r"nahi (?:hai|aaya|mila)|don'?t have|do not have|नहीं है|नहीं आया|नाही|નથી|নেই|ਨਹੀਂ|లేదు|ಇಲ್ಲ|ഇല്ല", re.I)
_LATER = re.compile(r"\blater\b|\bbaad (?:mein|me|mai)\b|\bnot now\b|don'?t remember|yaad nahi|\bskip\b|बाद में|नंतर", re.I)


def _rerun(s: dict, p: Profile) -> dict:
    rec = _localise(recommend(p), s["lang"], p)
    rec["options"] = _level_cards(s, rec, s["lang"])
    rec["why"] = _why_bundle(s, p, rec)
    s["recommendation"] = rec
    return rec


def _monthly(p: Profile) -> int:
    return recommend(copy.deepcopy(p))["quote"]["monthly"]


def _money(n: int) -> str:
    return f"{n:,}"


def _cheaper(s: dict, p: Profile, budget: int | None, lang: str) -> list[str]:
    """Bring the bundle down to the owner's budget (or about 20% lower) with the least harmful changes first:
    24-month pricing, then fewer mobile lines, then a lighter internet plan, then add-ons the owner never asked for
    (dearest first). Services the owner asked for or kept ticked in the checklist are never taken away. Each step
    goes through the rules engine, so the result is always a valid bundle."""
    rec = s["recommendation"]
    old = cur = rec["quote"]["monthly"]
    target = budget or int(old * 0.8)
    if budget and old <= budget:
        return [t(lang, "no_change", new=_money(old))]
    changes: list[str] = []

    base_ids = {l["id"] for l in rec["quote"]["lines"]}

    def no_new_items(q: Profile) -> None:
        """A cheaper bundle must not quietly gain products (e.g. a swapped-in alternative that now fits)."""
        for _ in range(3):
            new = [l for l in recommend(copy.deepcopy(q))["quote"]["lines"] if l["id"] not in base_ids]
            if not new:
                return
            for l in new:
                src = l["reason"].split(":")[1] if l["reason"].startswith("alt_for:") else l["id"]
                need = _NEED_OF.get(src) or _NEED_OF.get(l["id"])
                q.needs_confirmed = True
                q.needs.discard(need)
                q.explicit_needs.discard(need)

    def attempt(mutate, label):
        nonlocal cur
        if cur <= target:
            return
        trial = copy.deepcopy(p)
        mutate(trial)
        no_new_items(trial)
        new = _monthly(trial)
        if new < cur:
            mutate(p)
            no_new_items(p)
            cur = new
            changes.append(label)

    # 24 months is cheaper too, but it changes the commitment: it is offered with its price, never switched silently
    # trim quantities and the internet plan before taking away a service the owner picked
    mobile = next((l for l in rec["quote"]["lines"] if l["id"] in ("P07", "P08")), None)
    if mobile and mobile["qty"] > 1 and "mobile_lines" not in p.counts:
        attempt(lambda q: q.counts.__setitem__("mobile_lines", 1), t(lang, "ch_lines", n=1))
    conn = next((l["id"] for l in rec["quote"]["lines"] if l["id"] in CONNECTIVITY), None)
    while conn in CONN_DOWNGRADE and cur > target:
        nxt = CONN_DOWNGRADE[conn]
        before = len(changes)
        attempt(lambda q, nxt=nxt: setattr(q, "conn_cap", nxt), t(lang, "ch_conn", name=_product_name(nxt)))
        if len(changes) == before:
            break
        conn = nxt
    optional, seen = [], set()
    for line in sorted(rec["quote"]["lines"], key=lambda l: -l["monthly"]):
        need = _NEED_OF.get(line["id"])
        if need and need not in p.asked_needs and need not in p.explicit_needs and need not in seen:
            seen.add(need)
            optional.append((need, line["name"]))
    for need, name in optional:
        def drop(q, need=need):
            q.needs_confirmed = True
            q.needs.discard(need)
            q.explicit_needs.discard(need)
        attempt(drop, t(lang, "ch_drop", name=name))

    new_rec = _rerun(s, p)
    q24 = new_rec["term_compare"]["monthly"] if p.contract_months < 24 else None
    if not changes:  # nothing left to trim without taking away what she picked: show her the ways down instead
        return [t(lang, "cheaper_floor_pick"), _ways_down(s, p, lang, trim=False)[0]]
    msgs = [t(lang, "cheaper_done", changes=", ".join(changes), new=_money(new_rec["quote"]["monthly"]), old=_money(old))]
    if budget and new_rec["quote"]["monthly"] > budget:
        kept = ", ".join(l["name"] for l in new_rec["quote"]["lines"])
        msgs.append(t(lang, "budget_short", kept=kept, new=_money(new_rec["quote"]["monthly"])))
    if q24 and (not budget or new_rec["quote"]["monthly"] > budget):
        msgs.append(t(lang, "cheaper_24", monthly=_money(q24)))
    return msgs


def _product_name(pid: str) -> str:
    return products()[pid].name


def _blocked_news(before: dict, after: dict, lang: str) -> list[str]:
    old = {b["id"] for b in before.get("blocked", [])}
    return [t(lang, "blocked_line", name=b.get("plain") or b["name"], why=b["why_text"]) for b in after.get("blocked", [])
            if b["id"] not in old]


def _change(s: dict, p: Profile, u: dict, facts: dict, lang: str) -> list[str]:
    """Apply a change asked for after the bundle was shown. Returns the messages describing it."""
    rec = s["recommendation"]
    old = rec["quote"]["monthly"]
    snapshot = copy.deepcopy(s["profile"])
    action, msgs = u["action"], []
    in_bundle = {_NEED_OF.get(l["id"]) for l in rec["quote"]["lines"]}

    if action == "undo":
        if not s.get("undo"):
            return [t(lang, "no_change", new=_money(old))]
        s["profile"], s["undo"] = s["undo"], None
        restored = _profile(s)
        p.__dict__.update(restored.__dict__)
        new = _rerun(s, p)
        return [t(lang, "undo_done", new=_money(new["quote"]["monthly"]))]

    if action == "keep":
        return [t(lang, "kept", new=_money(old))]

    if action == "option":
        key = u.get("option") or ""
        level = (s.get("levels") or {}).get(key)
        if not level:
            return [t(lang, "no_change", new=_money(old))]
        if level["sig"] == _sig(rec):
            return [t(lang, "option_same", name=t(lang, f"opt_{key}"))]
        s["profile"] = copy.deepcopy(level["profile"])
        p.__dict__.update(_profile(s).__dict__)
        new = _rerun(s, p)
        msgs.append(t(lang, "option_set", name=t(lang, f"opt_{key}"), new=_money(new["quote"]["monthly"]), old=_money(old)))
        msgs += _blocked_news(rec, new, lang)
    elif action == "cheaper":
        msgs = _cheaper(s, p, u.get("budget"), lang)
    elif action == "add":
        wanted = [n for n in u.get("add_needs") or facts.get("needs") or [] if n in NEEDS]
        have = [n for n in wanted if n in p.needs and n in in_bundle]
        new_needs = [n for n in wanted if n not in have]
        if have:
            msgs.append(t(lang, "already_have", names=assistant.names(lang, have)))
        if new_needs:
            p.needs_confirmed = True
            p.needs |= set(new_needs)
            p.explicit_needs |= set(new_needs)
            p.asked_needs |= set(new_needs)
            for k, v in (facts.get("counts") or {}).items():
                p.counts[k] = v
            new = _rerun(s, p)
            msgs.append(t(lang, "added", names=assistant.names(lang, new_needs), new=_money(new["quote"]["monthly"]),
                          old=_money(old)))
            msgs += _blocked_news(rec, new, lang)
    elif action == "remove":
        targets = u.get("remove_needs") or []
        if "internet" in targets and len(targets) == 1:
            return [t(lang, "keep_internet")]
        removed, missing = [], []
        for n in targets:
            if n == "mobile":
                if any(l["id"] in ("P07", "P08") for l in rec["quote"]["lines"]):
                    p.counts["mobile_lines"] = 0
                    removed.append(_product_name(next(l["id"] for l in rec["quote"]["lines"] if l["id"] in ("P07", "P08"))))
                else:
                    missing.append("mobile")
            elif n in NEEDS:
                p.needs_confirmed = True
                p.needs.discard(n)
                p.explicit_needs.discard(n)
                p.asked_needs.discard(n)
                (removed if n in in_bundle else missing).append(need_label(lang, n))
        if removed:
            new = _rerun(s, p)
            msgs.append(t(lang, "removed", names=", ".join(removed), new=_money(new["quote"]["monthly"]), old=_money(old)))
        if missing:
            msgs.append(t(lang, "not_in_bundle", names=", ".join(missing)))
    elif action == "site_plan":
        msgs += _site_plan(s, p, u.get("small_sites"), lang, old)
    elif action == "term":
        term = u.get("term_months") or 24
        if term == p.contract_months:
            msgs.append(t(lang, "term_same", term=term))
        else:
            p.contract_months = term
            new = _rerun(s, p)
            msgs.append(t(lang, "term_set", term=term, new=_money(new["quote"]["monthly"]), old=_money(old)))

    hard = {k: v for k, v in facts.items() if k in ("business_type", "employees", "sites", "city", "gstin", "has_gstin",
                                                    "fibre_available", "current_spend", "counts")}
    if action in ("none", "proceed") and hard:
        notes: list[str] = []
        _apply(p, hard, lang, notes)
        if hard.get("counts"):
            p.counts.update(hard["counts"])
        if any(k in hard for k in ("business_type", "employees", "sites")):
            p.segment = ""
        _compute_levels(s, p)
        new = _rerun(s, p)
        msgs += notes
        msgs.append(t(lang, "updated", new=_money(new["quote"]["monthly"]), old=_money(old))
                    if new["quote"]["monthly"] != old else t(lang, "no_change", new=_money(old)))
        msgs += _blocked_news(rec, new, lang)
    if _fingerprint(s["recommendation"]) != _fingerprint(rec):
        s["undo"] = snapshot
        store.audit("advisor", f"bundle_changed:{action}", s["id"],
                    f"monthly {old} -> {s['recommendation']['quote']['monthly']}")
    return msgs


def _fingerprint(rec: dict) -> tuple:
    q = rec["quote"]
    return q["monthly"], q["term_months"], tuple((l["id"], l["qty"]) for l in q["lines"])


def _done_chips(s: dict, lang: str, offer: list[str] | None = None) -> list[dict]:
    rec = s.get("recommendation") or {}
    q = rec.get("quote") or {}
    chips = [{"label": t(lang, "chip_go"), "slot": "refine", "value": "proceed"}]
    chips += [{"label": t(lang, "chip_add", name=need_label(lang, n)), "slot": "refine", "value": f"add:{n}"}
              for n in offer or []]
    chips.append({"label": t(lang, "chip_cheaper"), "slot": "refine", "value": "cheaper"})
    if q.get("term_months", 24) < 24 and rec.get("term_compare"):
        chips.append({"label": t(lang, "chip_24", monthly=_money(rec["term_compare"]["monthly"])), "slot": "refine",
                      "value": "term:24"})
    if s.get("undo"):
        chips.append({"label": t(lang, "chip_undo"), "slot": "refine", "value": "undo"})
    for line in rec.get("suggested", [])[:2]:
        need = _NEED_OF.get(line["id"])
        if need and need not in (offer or []):
            chips.append({"label": t(lang, "chip_add", name=need_label(lang, need)), "slot": "refine", "value": f"add:{need}"})
    sig = _sig(rec) if rec.get("quote") else ""
    for key, level in (s.get("levels") or {}).items():
        if key != "recommended" and level["sig"] != sig:
            chips.append({"label": t(lang, "chip_level", name=t(lang, f"opt_{key}"), monthly=_money(level["monthly"])),
                          "slot": "refine", "value": f"option:{key}"})
    chips += [{"label": t(lang, "chip_docs"), "slot": "refine", "value": "ask:q_docs"},
              {"label": t(lang, "chip_call"), "slot": "refine", "value": "callback"},
              {"label": t(lang, "chip_restart"), "slot": "refine", "value": "restart"}]
    return chips


def _lines_for(rec: dict, thing: str) -> list[dict]:
    lines = rec["quote"]["lines"]
    if thing == "mobile":
        return [l for l in lines if l["id"] in ("P07", "P08")]
    if thing == "internet":
        return [l for l in lines if l["id"] in CONNECTIVITY]
    return [l for l in lines if _NEED_OF.get(l["id"]) == thing]


def _without(p: Profile, thing: str) -> Profile:
    q = copy.deepcopy(p)
    if thing == "mobile":
        q.counts["mobile_lines"] = 0
    else:
        q.needs_confirmed = True
        q.needs.discard(thing)
        q.explicit_needs.discard(thing)
        q.asked_needs.discard(thing)
    return q


def _with(p: Profile, need: str) -> Profile:
    q = copy.deepcopy(p)
    q.needs_confirmed = True
    q.needs.add(need)
    q.explicit_needs.add(need)
    return q


def _chip(label: str, value: str) -> dict:
    return {"label": label, "slot": "refine", "value": value}


def _ask_skip(s: dict, p: Profile, things: list[str], lang: str, sources: list) -> tuple[list[str], list[dict] | None]:
    """'Can I skip X?' / 'do I need X?': what X does here, what happens without it, the exact saving, and buttons."""
    rec = s["recommendation"]
    old = rec["quote"]["monthly"]
    thing = next((x for x in things if x != "internet"), things[0] if things else None)
    if not thing:
        return [t(lang, "skip_which")], None
    if thing == "internet":
        sources.append("eligibility#products-that-need-an-internet-line")
        return [t(lang, "skip_internet")], [_chip(t(lang, "chip_cheaper"), "cheaper"), _chip(t(lang, "chip_keep"), "keep")]
    lines = _lines_for(rec, thing)
    if not lines:  # not in the bundle: say so, explain it, and offer it with its price
        pid = "P07" if thing == "mobile" else _PID_OF.get(thing)
        if not pid:
            return [t(lang, "skip_which")], None
        sources.append(f"product#{pid}")
        msgs = [t(lang, "skip_not_in_bundle", plain=cards.plain(lang, pid))]
        if thing == "mobile":
            return msgs, None
        trial = recommend(_with(p, thing))
        add = trial["quote"]["monthly"] - old
        blocked = next((b for b in trial["blocked"] if b["id"] == pid), None)
        if blocked:  # not possible for this business yet: say why, once
            return [t(lang, "blocked_line", name=cards.plain(lang, pid), why=t(lang, f"why_{blocked['why']}"))], None
        if add <= 0:
            return msgs, None
        msgs.append(t(lang, "need_offer", plain=cards.plain(lang, pid), does=t(lang, f"does_{pid}"), add=_money(add),
                      day=cards.per_day(add)))
        return msgs, [_chip(t(lang, "chip_add_cost", add=_money(add)), f"add:{thing}"),
                      _chip(t(lang, "chip_no_thanks"), "keep")]
    line = lines[0]
    sources.append(f"product#{line['id']}")
    save = old - recommend(_without(p, thing))["quote"]["monthly"]
    msgs = [t(lang, "skip_answer", plain=line["plain"], reason=line["reason_text"], skip=line["skip"], save=_money(save),
              day=cards.per_day(save))]
    if thing in p.asked_needs:
        msgs.append(t(lang, "skip_you_asked"))
    return msgs, [_chip(t(lang, "chip_remove_save", save=_money(save)), f"remove:{thing}"), _chip(t(lang, "chip_keep"), "keep")]


def _ask_term(s: dict, p: Profile, text: str, lang: str, sources: list) -> tuple[list[str], list[dict]]:
    """'12 or 24 months?': both prices, the monthly and total saving, and what the commitment means."""
    rec = s["recommendation"]
    q, other = rec["quote"], rec["term_compare"]
    sources.append("buying#12-or-24-months")
    if q["term_months"] >= 24:
        msgs = [t(lang, "term_answer_24", m24=_money(q["monthly"]), m12=_money(other["monthly"]))]
        chips = [_chip(t(lang, "chip_term12"), "term:12"), _chip(t(lang, "chip_keep"), "keep")]
    else:
        save = q["monthly"] - other["monthly"]
        msgs = [t(lang, "term_answer_12", m12=_money(q["monthly"]), m24=_money(other["monthly"]), save=_money(save),
                  total=_money(save * 24))]
        chips = [_chip(t(lang, "chip_24", monthly=_money(other["monthly"])), "term:24"), _chip(t(lang, "chip_stay12"), "keep")]
        fixed = [l["plain"] for l in q["lines"] if products()[l["id"]].min_contract >= 24]
        if fixed:
            msgs.append(t(lang, "term_fixed", names=", ".join(fixed)))
    if re.search(r"cancel|exit|leave|lock-?in|break|छोड़|बंद कर|रद्द", text.lower()):
        msgs.append(t(lang, "term_exit"))
    return msgs, chips


def _money_answer(s: dict, p: Profile, lang: str, sources: list) -> list[str]:
    rec = s.get("recommendation")
    if not rec:
        return [t(lang, "faq_price_pending")]
    q, other = rec["quote"], rec["term_compare"]
    sources.append("buying#how-prices-work")
    msgs = [t(lang, "money_setup" if q["setup"] else "money_nosetup", monthly=_money(q["monthly"]), gst=_money(q["gst"]),
              with_gst=_money(q["monthly_with_gst"]), setup=_money(q["setup"]), first=_money(q["first_bill"]),
              alt=_money(other["monthly"]), alt_term=other["term"])]
    if p.has_gstin and p.gstin_verified is not False:
        msgs.append(t(lang, "money_itc"))
    return msgs


def _safety_answer(s: dict, p: Profile, text: str, lang: str, sources: list) -> tuple[list[str], list[str]]:
    """'Is my data safe?': the owner's own files (backup, antivirus) and the documents they give us (DPDP)."""
    rec = s.get("recommendation")
    sources.append("privacy#purpose-and-minimisation")
    if not rec:
        return [t(lang, "faq_privacy")], []
    ids = {l["id"] for l in rec["quote"]["lines"]}
    term = rec["quote"]["term_months"]
    files = [t(lang, "safe_files_have") if "P17" in ids else t(lang, "safe_files_offer", price=_money(cards.price_for("P17", term))),
             t(lang, "safe_av_have") if "P20" in ids else t(lang, "safe_av_offer", price=_money(cards.price_for("P20", term)))]
    sources += ["product#P17", "product#P20"]
    kyc = t(lang, "safe_kyc")
    documents_first = re.search(r"document|kyc|aadha+r|\bpan\b|photo|consent|dpdp|दस्तावेज|आधार|कागज", text.lower())
    msgs = [kyc, " ".join(files)] if documents_first else [" ".join(files), kyc]
    return msgs, [n for n, pid in (("backup", "P17"), ("security", "P20")) if pid not in ids]


def _down_answer(s: dict, p: Profile, lang: str, sources: list) -> tuple[list[str], list[str]]:
    rec = s.get("recommendation")
    ids = {l["id"] for l in rec["quote"]["lines"]} if rec else set()
    term = rec["quote"]["term_months"] if rec else 12
    sources += ["product#P09", "install#help-and-tickets"]
    msgs = [t(lang, "down_have") if "P09" in ids else
            t(lang, "down_offer", price=_money(cards.price_for("P09", term)), setup=_money(products()["P09"].setup_fee))]
    for pid, sla in (("P05", "99.5%"), ("P06", "99.9%")):
        if pid in ids:
            msgs.append(t(lang, "down_sla", name=cards.plain(lang, pid), sla=sla))
    msgs.append(t(lang, "down_help"))
    return msgs, ([] if "P09" in ids or not rec else ["failover"])


# ---------- the moments that decide a sale ----------

def _next_step(s: dict, lang: str) -> str:
    """Every selling answer ends with what to do next, so the owner is never left wondering."""
    q = (s.get("recommendation") or {}).get("quote") or {}
    return t(lang, "next_step", days=q.get("activation_days", 5))


def _level(s: dict, key: str) -> dict | None:
    lv = (s.get("levels") or {}).get(key)
    return lv if lv and lv["sig"] != _sig(s["recommendation"]) else None


def _obj_price(s: dict, p: Profile, lang: str) -> tuple[list[str], list[dict]]:
    """"Too expensive": no silent change. Put the price in daily terms, then give her the ways down with their prices."""
    rec = s["recommendation"]
    q = rec["quote"]
    msgs = [t(lang, "obj_price", monthly=_money(q["monthly"]), day=cards.per_day(q["monthly"]), count=len(q["lines"]))]
    ways, chips = _ways_down(s, p, lang, trim=True)
    msgs.append(ways)
    store.audit("advisor", "objection_price", s["id"], f"monthly={q['monthly']}")
    return msgs, chips + [_chip(t(lang, "chip_keep_go"), "proceed"), _chip(t(lang, "chip_call"), "callback")]


def _ways_down(s: dict, p: Profile, lang: str, trim: bool) -> tuple[str, list[dict]]:
    """Every way to a lower price, each with its exact price, as a list and as buttons."""
    rec = s["recommendation"]
    q = rec["quote"]
    ways, chips = [], []
    basic = _level(s, "basic")
    if basic and (basic["monthly"] >= q["monthly"] or basic["count"] >= len(q["lines"])):
        basic = None  # same services, only lighter: that is the trim below, not "just the essentials"
    if basic:
        ways.append(t(lang, "way_basic", monthly=_money(basic["monthly"]), count=basic["count"]))
        chips.append(_chip(t(lang, "chip_level", name=t(lang, "opt_basic"), monthly=_money(basic["monthly"])), "option:basic"))
    if trim:
        s2, p2 = copy.deepcopy(s), copy.deepcopy(p)
        _cheaper(s2, p2, None, lang)
        new = s2["recommendation"]["quote"]["monthly"]
        if new < q["monthly"] and (not basic or new != basic["monthly"]):
            ways.append(t(lang, "way_trim", monthly=_money(new)))
            chips.append(_chip(t(lang, "chip_trim", monthly=_money(new)), "cheaper"))
    if q["term_months"] < 24 and rec["term_compare"]["monthly"] < q["monthly"]:
        ways.append(t(lang, "way_24", monthly=_money(rec["term_compare"]["monthly"])))
        chips.append(_chip(t(lang, "chip_24", monthly=_money(rec["term_compare"]["monthly"])), "term:24"))
    ways.append(t(lang, "way_budget"))
    return "\n".join("• " + w for w in ways), chips


def _continue_link(s: dict) -> str | None:
    base = os.getenv("APP_URL", "").rstrip("/")
    return f"{base}/#/continue/{s['id']}" if base else None


def _obj_think(s: dict, p: Profile, lang: str) -> tuple[list[str], list[dict]]:
    """"Let me think about it": keep the bundle, make coming back easy, and ask what is holding her back."""
    q = s["recommendation"]["quote"]
    msgs = [t(lang, "obj_think", count=len(q["lines"]), monthly=_money(q["monthly"]), days=q["activation_days"])]
    if s.get("channel") == "whatsapp":
        msgs.append(t(lang, "obj_think_wa"))
    elif _continue_link(s):
        msgs.append(t(lang, "obj_think_link", link=_continue_link(s)))
    msgs.append(t(lang, "obj_holding"))
    store.audit("advisor", "objection_think", s["id"])
    return msgs, [_chip(t(lang, "chip_why_price"), "ask:obj_price"), _chip(t(lang, "chip_why_someone"), "ask:obj_someone"),
                  _chip(t(lang, "chip_why_unsure"), "ask:q_recommend"), _chip(t(lang, "chip_why_compare"), "ask:q_competitor"),
                  _chip(t(lang, "chip_call"), "callback")]


def _obj_someone(s: dict, p: Profile, lang: str) -> tuple[list[str], list[dict]]:
    """"I'll ask my partner": give her a summary she can forward, and offer to talk to both of them."""
    rec = s["recommendation"]
    q = rec["quote"]
    business = p.business_name or _local(lang, "bt", p.business_type) or rec["segment_name"]
    items = ", ".join(l["plain"] for l in q["lines"][:6])
    summary = t(lang, "share_summary", business=business, items=items, monthly=_money(q["monthly"]),
                with_gst=_money(q["monthly_with_gst"]), days=q["activation_days"])
    store.audit("advisor", "objection_someone", s["id"])
    return [t(lang, "obj_someone"), summary, t(lang, "obj_someone_call")], \
        [_chip(t(lang, "chip_call_both"), "callback"), _chip(t(lang, "chip_go"), "proceed"), _chip(t(lang, "chip_why_price"), "ask:obj_price")]


def _recommend_answer(s: dict, p: Profile, lang: str) -> tuple[list[str], list[dict]]:
    """"Which one do you recommend, and why?": a straight answer, the reasons in her terms, and the other levels."""
    rec = s["recommendation"]
    q = rec["quote"]
    levels = s.get("levels") or {}
    sig = _sig(rec)
    on = next((k for k, v in levels.items() if v["sig"] == sig), "recommended")
    best = levels.get("recommended") or {"monthly": q["monthly"], "count": len(q["lines"])}
    business = _local(lang, "bt", p.business_type) or rec["segment_name"]
    msgs = [t(lang, "rec_answer", level=t(lang, "opt_recommended"), count=best["count"], monthly=_money(best["monthly"]),
              business=business)]
    reasons = []
    if p.pains:
        reasons.append(t(lang, "rec_pain", pains=", ".join(f"“{t(lang, f'pain_{k}')}”" for k in p.pains[:2])))
    asked = [l["plain"] for l in q["lines"] if l.get("asked")]
    if asked:
        reasons.append(t(lang, "rec_asked", names=", ".join(asked[:3])))
    popular = sorted((l for l in q["lines"] if l.get("take_up") and l["id"] not in CONNECTIVITY + ("P07", "P08")
                      and not l.get("asked")), key=lambda l: -l["take_up"])
    if popular:
        l = popular[0]
        reasons.append(t(lang, "rec_takeup", n=l["take_up"], plain=l["plain"]) if l["take_up"] < 10 else
                       t(lang, "rec_takeup_all", plain=l["plain"]))
    conn = next((l for l in q["lines"] if l["id"] in CONNECTIVITY), None)
    if conn:
        reasons.append(conn["reason_text"])
    msgs.append("\n".join("• " + _cap(r) for r in reasons[:3]))
    basic, complete = levels.get("basic"), levels.get("complete")
    if basic and complete:
        msgs.append(t(lang, "rec_levels", basic=_money(basic["monthly"]), complete=_money(complete["monthly"])))
    if on != "recommended" and "recommended" in levels:
        msgs.append(t(lang, "rec_you_are_on", level=t(lang, f"opt_{on}")))
    msgs.append(_next_step(s, lang))
    chips = [_chip(t(lang, "chip_go"), "proceed")]
    if on != "recommended" and "recommended" in levels:
        chips.insert(0, _chip(t(lang, "chip_level", name=t(lang, "opt_recommended"), monthly=_money(best["monthly"])), "option:recommended"))
    chips += [_chip(t(lang, "chip_level", name=t(lang, f"opt_{k}"), monthly=_money(v["monthly"])), f"option:{k}")
              for k, v in levels.items() if k not in ("recommended", on)]
    return msgs, chips + [_chip(t(lang, "chip_why_price"), "ask:obj_price")]


def _competitor(s: dict, p: Profile, text: str, lang: str, sources: list) -> tuple[list[str], list[dict]]:
    """"Jio gives me 399": no running down other companies. Say what a business line and one bill give her, from the
    catalogue, then the cheapest real option."""
    rec = s["recommendation"]
    q = rec["quote"]
    conn = next((l for l in q["lines"] if l["id"] in CONNECTIVITY), None)
    sources += [f"product#{conn['id']}"] if conn else []
    gets = []
    if conn:
        gets.append(f"{conn['plain']}: {conn['does']}")
    gets.append(t(lang, "comp_one_bill", count=len(q["lines"])) + (" " + t(lang, "comp_itc") if p.has_gstin and p.gstin_verified else ""))
    gets.append(t(lang, "comp_help", days=q["activation_days"]))
    msgs = [t(lang, "competitor", monthly=_money(q["monthly"])), "\n".join("• " + g for g in gets)]
    basic = _level(s, "basic")
    chips = [_chip(t(lang, "chip_cheaper"), "cheaper")]
    if basic and basic["monthly"] < q["monthly"]:
        msgs.append(t(lang, "options_line_basic", basic=_money(basic["monthly"])))  # Basic still carries her problems: never call it "just a line and a phone"
        chips.insert(0, _chip(t(lang, "chip_level", name=t(lang, "opt_basic"), monthly=_money(basic["monthly"])), "option:basic"))
    else:
        msgs.append(t(lang, "comp_cheaper"))
    msgs.append(_next_step(s, lang))
    store.audit("advisor", "objection_competitor", s["id"])
    return msgs, chips + [_chip(t(lang, "chip_go"), "proceed"), _chip(t(lang, "chip_call"), "callback")]


def _outlets(rec: dict, lang: str) -> str:
    """What each outlet gets, from the per-site lines of the quote."""
    q = rec["quote"]
    conns = [l for l in q["lines"] if l["id"] in CONNECTIVITY]
    per_site = [l["plain"] for l in q["lines"] if l["unit"] == "per site" and l["id"] not in CONNECTIVITY]
    if len(conns) > 1:
        out = t(lang, "sites_split", big=conns[0]["qty"], big_line=conns[0]["plain"], small=conns[1]["qty"],
                small_line=conns[1]["plain"])
    else:
        out = t(lang, "sites_same", n=conns[0]["qty"] if conns else 1, line=conns[0]["plain"] if conns else "")
    return out + (" " + t(lang, "sites_each", each=", ".join(per_site)) if per_site else "")


def _sites_answer(s: dict, p: Profile, n_small: int | None, lang: str) -> tuple[list[str], list[dict]]:
    """"Can each outlet have a different setup?": yes. Say what each gets, and offer a lighter setup for small ones."""
    rec = s["recommendation"]
    q = rec["quote"]
    if (p.sites or 1) < 2 or rec["segment"] != "multi":
        return [t(lang, "sites_one")], None
    msgs = [t(lang, "sites_yes", n=p.sites), _outlets(rec, lang)]
    chips = []
    if n_small and n_small != p.small_sites and n_small < p.sites:
        trial = copy.deepcopy(p)
        trial.small_sites = n_small
        new = recommend(trial)["quote"]["monthly"]
        if new < q["monthly"]:
            msgs.append(t(lang, "sites_small_offer", n=n_small, new=_money(new), old=_money(q["monthly"])))
            chips.append(_chip(t(lang, "chip_small_sites", n=n_small, monthly=_money(new)), f"small:{n_small}"))
    elif not p.small_sites:
        msgs.append(t(lang, "sites_ask_small"))
        chips += [_chip(t(lang, "chip_small_n", n=k), f"small:{k}") for k in (1, 2) if k < p.sites]
    msgs.append(t(lang, "faq_time_sites", sites=p.sites, days=q["activation_days"],
                  slow=max(q["lines"], key=lambda l: l["install_days"])["plain"]))
    return msgs, chips + [_chip(t(lang, "chip_go"), "proceed")]


def _site_plan(s: dict, p: Profile, n: int | None, lang: str, old: int) -> list[str]:
    if (p.sites or 1) < 2 or infer_segment(p) != "multi":
        return [t(lang, "sites_one")]
    p.small_sites = max(0, min(n or 0, p.sites - 1))
    _compute_levels(s, p)
    new = _rerun(s, p)
    return [t(lang, "sites_set" if p.small_sites else "sites_all_same", n=p.small_sites, sites=p.sites,
              new=_money(new["quote"]["monthly"]), old=_money(old)), _outlets(new, lang)]


def _ask_answer(intent: str, s: dict, p: Profile, u: dict, text: str, lang: str,
                sources: list) -> tuple[list[str], list[dict] | None]:
    """Answers the app writes itself, with exact numbers, for questions about the bundle. Never changes it."""
    if not s.get("recommendation"):
        return _rules_answer(intent if intent in ("q_privacy", "q_total", "q_discount", "q_promise") else "question",
                             text, s, lang, sources)
    if intent == "q_discount":  # no discounts, said plainly, then every real way to pay less with its exact price
        ways, chips = _ways_down(s, p, lang, trim=True)
        return [t(lang, "guard_discount"), ways], chips + [_chip(t(lang, "chip_keep_go"), "proceed"),
                                                             _chip(t(lang, "chip_call"), "callback")]
    if intent == "q_promise":  # no promises beyond the plan; what is true instead
        msgs = [t(lang, "guard_promise", days=s["recommendation"]["quote"]["activation_days"])]
        offer: list[str] = []
        if "failover" in (u.get("offer") or []):
            more, offer = _down_answer(s, p, lang, sources)
            msgs += more
        return msgs, _done_chips(s, lang, offer=offer)
    if intent == "ask_skip":
        return _ask_skip(s, p, u.get("about") or [], lang, sources)
    if intent == "ask_term":
        return _ask_term(s, p, text, lang, sources)
    if intent == "q_total":
        return _money_answer(s, p, lang, sources), None
    if intent == "q_privacy":
        msgs, offer = _safety_answer(s, p, text, lang, sources)
        return msgs, _done_chips(s, lang, offer=offer)
    if intent == "q_down":
        msgs, offer = _down_answer(s, p, lang, sources)
        return msgs, _done_chips(s, lang, offer=offer)
    if intent == "q_competitor":
        return _competitor(s, p, text, lang, sources)
    if intent == "obj_price":
        return _obj_price(s, p, lang)
    if intent == "obj_think":
        return _obj_think(s, p, lang)
    if intent == "obj_someone":
        return _obj_someone(s, p, lang)
    if intent in ("q_recommend", "q_unsure"):
        return _recommend_answer(s, p, lang)
    if intent == "q_sites":
        return _sites_answer(s, p, u.get("small_sites"), lang)
    return [], None


def _rules_answer(intent: str | None, text: str, s: dict, lang: str, sources: list | None = None,
                  ) -> tuple[list[str], list[dict] | None]:
    """Answers without the LLM. Returns the messages and, when the answer comes with its own buttons, the chips."""
    rec = s.get("recommendation")
    sources = sources if sources is not None else []
    sources += knowledge.RULE_SOURCES.get(intent or "", [])
    p = _profile(s)
    if intent in ("q_discount", "q_promise"):
        return [t(lang, f"guard_{intent[2:]}" if rec else f"guard_{intent[2:]}_early", days=rec["quote"]["activation_days"] if rec else 0)], None
    if intent == "q_docs":
        return [t(lang, "faq_kyc")], None
    if intent == "q_gst":  # name what they asked about first: "Can I get WhatsApp without GST?" deserves a straight answer
        named = [pid for need in assistant.needs_in(text) for pid, n in _NEED_OF.items() if n == need and products()[pid].requires_gstin]
        return [t(lang, "blocked_line", name=cards.plain(lang, pid), why=t(lang, "why_gstin")) for pid in named[:2]] + [t(lang, "faq_gst")], None
    if intent == "q_privacy":
        return _safety_answer(s, p, text, lang, sources)[0], None
    if intent == "q_time":
        if rec and (p.sites or 1) > 1:
            q = rec["quote"]
            return [t(lang, "faq_time_sites", sites=p.sites, days=q["activation_days"],
                      slow=max(q["lines"], key=lambda l: l["install_days"])["plain"])], None
        return ([t(lang, "faq_time", days=rec["quote"]["activation_days"])] if rec else [t(lang, "faq_time_generic")]), None
    if intent in ("q_price", "q_total", "q_competitor"):
        return _money_answer(s, p, lang, sources), None
    if intent == "q_down":
        return _down_answer(s, p, lang, sources)[0], None
    if intent in ("question", "ask_skip", "ask_term"):
        low = text.lower()
        if rec and re.search(r"\bwhy\b|kyu|क्यों|का\s|ஏன்", low):
            hits = [l for l in rec["quote"]["lines"] if l["name"].lower().split(" ")[1 if l["name"].startswith("Biz") else 0] in low
                    or _NEED_OF.get(l["id"]) in assistant.needs_in(text)]
            if hits:
                sources += [f"product#{l['id']}" for l in hits[:2]]
                return [t(lang, "why_item", plain=l["plain"], reason=l["reason_text"], does=l["does"])
                        + (" " + (t(lang, "take_up_all") if l["take_up"] >= 10 else t(lang, "take_up", n=l["take_up"]))
                           if l.get("take_up") else "") for l in hits[:2]], None
        found = assistant.describe_products(text, lang, rec)
        sources += [cid for _, cid in found if cid]
        return [msg for msg, _ in found], None
    if intent == "greet" and s["stage"] == "done":
        return [t(lang, "welcome_back")], None
    return [], None


def _restart(s: dict) -> dict:
    lang = s["lang"]
    s.update({"stage": "chat", "status": "advisor_started", "pending_slot": "business_type", "misses": 0,
              "recommendation": None, "undo": None, "history": []})
    _save_profile(s, Profile())
    store.audit("advisor", "restarted", s["id"])
    return {"messages": [t(lang, "greet")], "chips": _chips("business_type", lang), "reset": True}


_SALES = ("obj_price", "obj_think", "obj_someone", "q_recommend", "q_unsure", "q_sites")
_OWN_BUSINESS = re.compile(
    r"\b(?:i|we)\s+(?:run|own|have|operate|manage|am|are|do|also|actually|started|opened)\b|\b(?:i'm|we're)\b|\bactually\b|"
    r"\b(?:my|our)\s+(?:business|shop|store|company|firm|work)\b|\bnot an?\b|\b(?:mera|meri|mere|hamara|hamari|hum|main)\b|"
    r"मेरा|मेरी|मेरे|हमारा|हमारी|हम\s|मैं\s|माझ|आमच|என்|எங்கள்|నా\s|మా\s|ನನ್ನ|ನಮ್ಮ|എന്റെ|ഞങ്ങളുടെ|আমার|আমাদের|મારો|મારી|અમારો|ਮੇਰਾ|ਮੇਰੀ|ਸਾਡਾ", re.I)


def _same_business(stage: str, p: Profile, text: str, facts: dict) -> dict:
    """A passing word is not a change of business. Once the bundle is built, "print the quote" or "the salon next
    door" changes nothing unless the owner is talking about their own business."""
    if facts.get("business_type") and stage == "done" and not _OWN_BUSINESS.search(text):
        facts.pop("business_type")
    return facts


def _guarded(s: dict, p: Profile, kind: str, text: str) -> dict:
    """A message the safety layer stopped: answer from fixed text, change nothing, and carry on where we were."""
    lang = s["lang"] if s.get("lang_pinned") else assistant.turn_lang(text, s["lang"])
    store.audit("advisor", f"guard:{kind}", s["id"])
    if kind == "misuse":  # a person should look at this lead before anything is sold
        s["risk"] = sorted(set(s.get("risk") or []) | {"misuse"})
    msgs = [t(lang, f"guard_{kind}")]
    call = [_chip(t(lang, "chip_call"), "callback")]
    if s["stage"] == "done":
        return {"messages": msgs, "chips": (call if kind == "abuse" else []) + [c for c in _done_chips(s, lang) if c["value"] != "callback"]}
    if s["stage"] == "needs":
        return {"messages": msgs, "chips": _pain_chips(p, lang), **_needs_payload(p, lang)}
    out = _continue(s, p, msgs, lang)
    if kind == "abuse":
        out["chips"] = call + list(out.get("chips") or [])
    return out


def _too_big(s: dict, hit: tuple[str, int], lang: str) -> dict:
    """A business beyond small-business plans, or a typo: don't price it, offer the enterprise team."""
    store.audit("advisor", "guard:scale", s["id"], f"{hit[0]}={hit[1]}")
    s["awaiting_phone"] = True
    return {"messages": [t(lang, "guard_scale", n=f"{hit[1]:,}"), t(lang, "callback_ask")],
            "chips": _done_chips(s, lang) if s["stage"] == "done" else []}


def _understand(s: dict, p: Profile, text: str) -> tuple[dict, dict]:
    """One LLM call when configured (facts + action + answer), always backed by the keyword rules."""
    stage = s["stage"]
    kind = guard.screen(text)
    if kind in guard.POLICY:  # "give me 50% off", "guarantee 100% uptime": answered by the app, never by the model
        store.audit("advisor", f"guard:{kind}", s["id"])
        return ({"action": "none", "add_needs": [], "remove_needs": [], "term_months": None, "budget": None, "reply": "",
                 "intent": f"q_{kind}", "about": [], "offer": assistant.needs_in(text) if kind == "promise" else []}, {})
    rules = assistant.rules_understand(text, stage)
    rule_facts = _same_business(stage, p, text, extract(text, smart={}))
    if s.get("pending_slot") == "current" or stage in ("chat", "needs"):
        cur = current_from_text(text, strict=s.get("pending_slot") != "current")
        if not cur and stage in ("chat", "needs") and not p.current_internet and len(text.split()) <= 5 and not re.search(r"\d", text) \
                and s.get("pending_slot") not in ("business_type", "city") \
                and not (s.get("pending_slot") == "gstin" and (_NOT_YET.search(text) or _LATER.search(text))):
            cur = current_from_text(text, strict=False)  # "mobile hotspot" answered out of turn: keep it
        if cur:
            rule_facts["current_internet"] = cur
    if p.sites and p.sites > 1 and rule_facts.get("sites") == 1 and s.get("pending_slot") != "sites":
        rule_facts.pop("sites")  # "leased line at one site" is not "we have one site"
    smart = None
    if assistant.worth_asking_llm(text, stage, s.get("pending_slot"), rules, rule_facts):
        smart = assistant.llm_understand(text, s["lang"], stage, s.get("pending_slot"), _public_profile(p),
                                         s.get("recommendation"), s["history"][:-1], intent=rules["intent"], session=s)
    if smart and rules["intent"] in _SALES and smart["action"] in ("none", "cheaper", "term", "proceed", "add", "remove"):
        smart = {**smart, "action": "none", "question": rules["intent"], "add_needs": [], "remove_needs": []}
    if smart:
        u = smart
        if u["action"] == "cheaper" and not u.get("budget"):
            u["budget"] = rules["budget"]
        if u["action"] == "term" and not u.get("term_months"):
            u["term_months"] = rules["term_months"]
        if rules["intent"] in ("ask_skip", "ask_term") and u["action"] in ("remove", "term", "add", "cheaper"):
            u["action"], u["add_needs"], u["remove_needs"] = "none", [], []  # a question is never an order
        if u["action"] == "none" and not u["reply"] and not u.get("question") and rules["action"] != "none":
            u = {**rules, "reply": ""}  # the LLM missed an obvious request the rules caught
        question = u.get("question") or (rules["intent"] if rules["intent"] in assistant.ASKS else None)
        if question and u["action"] == "none":
            u["intent"] = question
            u["about"] = u.get("about") or rules.get("about") or []
            if stage == "done":
                u["reply"], u["sources"] = "", []  # the app answers these itself, with exact numbers
        else:
            u["intent"] = None if u["reply"] else rules["intent"]
        if u["action"] == "add" and assistant.asks_only(text):  # "do you have X?" answers and offers X, never adds it
            u["offer"] = u["add_needs"]
            u["action"], u["add_needs"] = "none", []
        u.setdefault("option", rules.get("option"))
        u.setdefault("small_sites", rules.get("small_sites"))
        facts = _same_business(stage, p, text, extract(text, smart=clean_llm_facts(smart.get("facts") or {})))
        if facts.get("gstin") and facts["gstin"].upper() not in re.sub(r"[\s-]", "", text.upper()):
            facts.pop("gstin")  # the AI repeated the GSTIN from the profile: looking it up again would loop on "is this you?"
        if "current_internet" in rule_facts:
            facts["current_internet"] = rule_facts["current_internet"]
    else:
        u = rules
        facts = rule_facts
    if u.get("intent") == "question" and not u.get("offer"):
        u["offer"] = assistant.needs_in(text)
    if u["action"] != "none" or u.get("reply") or u.get("intent") in ("question", "q_docs", "q_gst", "q_time",
                                                                      "q_privacy", "q_price") + assistant.ASKS:
        if u["action"] not in ("add",):
            facts.pop("needs", None)  # "what is CCTV?" is not a request for CCTV
    return u, facts


def message(session_id: str, text: str = "", slot: str | None = None, value=None, needs: list | None = None,
            display: str | None = None) -> dict:
    s = store.get("session", session_id)
    if not s:
        raise KeyError("session not found")
    lang = s["lang"]
    p = _profile(s)
    notes: list[str] = []
    text = (text or "").strip()
    shown = text or (display or "").strip()
    if not text and len(shown) > 300:  # a long list of tapped services: keep the start, say how many more
        parts = [x.strip() for x in shown.split(",") if x.strip()]
        head = []
        while parts and len(", ".join(head + parts[:1])) <= 220:
            head.append(parts.pop(0))
        shown = ", ".join(head) + (f" … +{len(parts)}" if parts else "") if head else shown[:300] + "…"
    shown, aadhaar = privacy.hide_aadhaar(shown)  # the number is used for nothing and stored nowhere
    if shown:
        s["history"].append({"role": "user", "text": shown[:500]})
    extra: dict = {}

    if needs is not None:  # needs confirmed from the checklist
        chosen = {n for n in needs if n in NEEDS}
        p.needs, p.explicit_needs, p.needs_confirmed = set(chosen) | p.asked_needs, set(chosen) | p.asked_needs, True
        out = _recommend(s, p)
        out["chips"] = _done_chips(s, lang)
    elif slot == "pain":
        out = _pain_answer(s, p, str(value), lang)
    elif slot == "refine" and str(value).startswith("small:"):
        n = str(value).partition(":")[2]
        out = _turn(s, p, {"action": "site_plan", "small_sites": int(n) if n.isdigit() else 0, "add_needs": [],
                           "remove_needs": [], "term_months": None, "budget": None, "reply": "", "intent": None,
                           "about": []}, {}, "")
    elif slot == "refine":
        kind, _, arg = str(value).partition(":")
        out = _turn(s, p, {"action": kind if kind in assistant.ACTIONS else "none",
                           "add_needs": [arg] if kind == "add" else [], "remove_needs": [arg] if kind == "remove" and arg else [],
                           "term_months": int(arg) if kind == "term" and arg.isdigit() else None,
                           "budget": None, "reply": "", "intent": arg if kind == "ask" else None,
                           "option": arg if kind == "option" else None, "about": []}, {}, "")
    elif slot == "gstin_confirm":
        out = _gstin_answer(s, p, str(value) == "yes", lang)
    elif slot and value is not None:
        big = None
        if slot == "current" and str(value) in CURRENT_CHOICES:
            p.current_internet = str(value)
        elif slot == "gstin" and value == "skip":
            pass
        elif slot == "gstin" and value == "none":
            _apply(p, {"has_gstin": False}, lang, notes)
        elif slot in ("employees", "sites"):
            n = int(value) if str(value).isdigit() else 0  # a button sends a number; anything else is ignored
            big = guard.too_big({slot: n})
            if n > 0 and not big:
                setattr(p, slot, n)
        elif slot == "city":
            _apply(p, {"city": str(value)[:60]}, lang, notes)
        elif slot == "business_type":
            p.business_type = str(value)[:60]
        out = _too_big(s, big, lang) if big else _continue(s, p, notes, lang)
    elif text and guard.screen(text) in guard.BLOCK:  # steering, abuse, misuse, other people's data, off-topic
        out = _guarded(s, p, guard.screen(text), text)
    elif text and (asked := assistant.language_request(text)):  # "talk in English", "Hindi mai baat karo": switch, stay
        told = {k for k in extract(text, smart={}) if k in ("business_type", "city", "employees", "sites", "gstin")}
        if told:  # "I run a pharmacy in Pune, talk in English": switch, and keep what she told us
            s["lang"], s["lang_pinned"] = asked, True
            u, facts = _understand(s, p, text)
            out = _turn(s, p, u, facts, text)
            out["messages"] = [t(asked, "lang_switched")] + out["messages"]
        else:
            out = _switch_language(s, p, asked)
    elif text and s["stage"] == "needs" and assistant.confused(text):  # "What?" at the checklist: explain, don't repeat
        out = {"messages": [t(lang, "unsure_needs")], "chips": _pain_chips(p, lang), **_needs_payload(p, lang)}
    elif text and s["stage"] == "needs" and assistant.wants_all(text):  # "I want all of them": tick every service
        chosen = {n["key"] for n in _needs_payload(p, lang)["needs"]}
        p.needs, p.explicit_needs, p.needs_confirmed = chosen | p.asked_needs, chosen | p.asked_needs, True
        out = _recommend(s, p)
        out["chips"] = _done_chips(s, lang)
    elif text:
        u, facts = _understand(s, p, text)
        out = _turn(s, p, u, facts, text)
    else:
        out = _continue(s, p, notes, lang)

    if out.get("reset"):
        p = _profile(s)
    else:
        _save_profile(s, p)
    if aadhaar:
        store.audit("advisor", "aadhaar_hidden_in_chat", s["id"])
        out["messages"] = [t(s["lang"], "aadhaar_hidden")] + list(out["messages"])
    sources = s.pop("_sources", None) or []
    if sources:
        out["sources"] = sources
    for i, m in enumerate(out["messages"]):
        s["history"].append({"role": "assistant", "text": m, **({"sources": sources} if i == 0 and sources else {})})
    s["last"] = {"chips": out.get("chips", []), "needs": out.get("needs")}
    store.put("session", s["id"], s)
    if s["stage"] == "done" and s.get("recommendation") and "recommendation" not in out:
        out["recommendation"] = s["recommendation"]
    return {"session_id": s["id"], "stage": s["stage"], "lang": s["lang"], "profile": _public_profile(p), **extra, **out}


def _switch_language(s: dict, p: Profile, lang: str) -> dict:
    """The owner asked for another language: switch, keep it for the rest of the chat, and repeat where we were."""
    s["lang"], s["lang_pinned"] = lang, True
    store.audit("advisor", "language_requested", s["id"], lang)
    msgs = [t(lang, "lang_switched")]
    if s["stage"] == "done" and s.get("recommendation"):
        return {"messages": msgs + [t(lang, "help_done")], "chips": _done_chips(s, lang),
                "recommendation": _localise(s["recommendation"], lang, p)}
    if s["stage"] == "needs":
        return {"messages": msgs + [t(lang, "ask_needs")], "chips": _pain_chips(p, lang), **_needs_payload(p, lang)}
    if s.get("pending_slot") == "gstin_confirm" and s.get("gstin_check"):
        return {"messages": msgs, "chips": _chips("gstin_confirm", lang)}
    if s.get("pending_slot") == "current":
        return {"messages": msgs + [t(lang, "ask_current")], "chips": _chips("current", lang)}
    return _continue(s, p, msgs, lang)


def _plausible(slot: str, text: str) -> bool:
    """Is this reply really a business type or a city, rather than talk about the chat ("talk in English")?"""
    if slot == "city":
        return 2 <= len(text) <= 40 and not re.search(r"\d", text) and len(text.split()) <= 4 and not assistant.is_meta(text)
    if slot == "business_type":
        if not (3 <= len(text) <= 60) or _NOT_A_BUSINESS.search(text) or "?" in text:
            return False
        return not assistant.is_meta(text) or bool(assistant._LANG_BUSINESS.search(text))
    return True


def _turn(s: dict, p: Profile, u: dict, facts: dict, text: str) -> dict:
    lang, stage = assistant.turn_lang(text, s["lang"]), s["stage"]
    if s.get("lang_pinned"):
        lang = s["lang"]  # she asked for this language: don't flip because one reply came in another script
    if text and lang != s["lang"]:  # the owner wrote in another language: carry on in theirs
        s["lang"] = lang
        store.audit("advisor", "language_switched", s["id"], lang)
    action = u.get("action", "none")
    msgs: list[str] = []

    phone = _PHONE.search(text.replace(" ", "")) if text else None
    if phone and (s.get("awaiting_phone") or action == "callback"):
        num = phone.group(1)
        s["callback"] = {"phone": num, "at": store.now()}
        s["awaiting_phone"] = False
        store.audit("advisor", "callback_requested", s["id"], f"phone=******{num[-4:]}")
        msgs.append(t(lang, "callback_ok", phone="******" + num[-4:]))
        return _continue(s, p, msgs, lang) if stage != "done" else {"messages": msgs, "chips": _done_chips(s, lang)}
    if (hit := guard.too_big(facts)):  # "1000000 staff": never priced, handed to a person
        return _too_big(s, hit, lang)

    if action == "restart":
        return _restart(s)
    if action == "track":
        return {"messages": [t(lang, "go_track")], "chips": [], "go": "tracker"}
    if action == "callback":
        s["awaiting_phone"] = True
        msgs = ([u["reply"]] if u.get("reply") else []) + [t(lang, "callback_ask")]
        return {"messages": msgs, "chips": []}

    sources: list[str] = []
    chips = None
    intent = u.get("intent")
    if stage != "done" and s.get("pending_slot") == "current" and intent == "q_competitor" and action == "none":
        intent = u["intent"] = None  # "we use Jio hotspot" answers "what do you use today?", it isn't a comparison
    if intent in assistant.ASKS and action == "none" and stage == "done":
        answer, chips = _ask_answer(intent, s, p, u, text, lang, sources)
        msgs += answer
    elif u.get("reply"):
        msgs.append(u["reply"])
        sources = list(u.get("sources") or [])
    elif action == "none" or (action == "proceed" and stage != "done"):
        answer, chips = _rules_answer(intent, text, s, lang, sources)
        msgs += answer
    s["_sources"] = [{"id": c, "title": knowledge.by_id(c)["title"]} for c in dict.fromkeys(sources) if knowledge.by_id(c)]

    if stage == "done":
        before = _fingerprint(s["recommendation"])
        for k in facts.get("pains") or []:
            if k not in p.pains:
                p.pains.append(k)
        if intent not in assistant.ASKS or action != "none":
            msgs += _change(s, p, u, facts, lang)
        if _fingerprint(s["recommendation"]) != before and action not in ("proceed", "undo"):
            msgs.append(_next_step(s, lang))
        out = {"messages": msgs, "chips": chips if chips is not None else
               _done_chips(s, lang, offer=[n for n in u.get("offer") or [] if n not in p.needs])}
        if action == "proceed":
            out["messages"].append(t(lang, "go_quote"))
            out["go"] = "quote"
        if not out["messages"]:
            out["messages"] = [t(lang, "help_done")]
        return out

    # still collecting details (chat) or confirming needs
    if intent == "q_unsure":  # "I don't know what I need": that's our job; at the checklist, ask about problems instead
        if stage == "needs":
            return {"messages": [t(lang, "unsure_needs")], "chips": _pain_chips(p, lang), **_needs_payload(p, lang)}
        msgs.append(t(lang, "unsure_chat"))
    elif intent in ("obj_think", "obj_someone"):
        msgs.append(t(lang, "think_early"))
    if action == "cheaper" or u.get("budget") or intent == "obj_price":  # price matters: keep the bundle lean
        if u.get("budget"):
            p.budget = u["budget"]
        s["lean"] = True
        msgs.append(t(lang, "noted_budget", budget=_money(p.budget)) if p.budget else t(lang, "noted_lean"))
    answered = bool(msgs)
    pending = s.get("pending_slot")
    if pending == "gstin_confirm" and text and not facts.get("gstin") and (_YES.search(text) or _NO.search(text)):
        return _gstin_answer(s, p, bool(_YES.search(text)), lang)
    if pending == "gstin" and text and _LATER.search(text):  # "I'll give the number later": don't ask for it again now
        s["asked_gstin_number"] = True
        if p.has_gstin is None and "has_gstin" not in facts:
            facts = {**facts, "has_gstin": False}
    chatter = u.get("intent") in ("greet", "question") or bool(u.get("reply"))
    if not facts and text and not answered and not chatter:
        if pending == "gstin" and (_NO.search(text) or _NOT_YET.search(text)):
            facts = {"has_gstin": False}
        elif pending == "gstin" and _YES.search(text):
            return {"messages": [t(lang, "ask_gstin_type")], "chips": _chips("gstin", lang)}
        elif pending in ("employees", "sites"):
            n = _first_number(text)
            if n and (hit := guard.too_big({pending: n})):
                return _too_big(s, hit, lang)
            if n:
                facts = {pending: n}
        elif pending == "current":
            facts = {"current_internet": "business"} if 2 <= len(text) <= 60 else {}  # "Jio", "ACT", a provider name
        elif pending == "city" and _plausible("city", text):
            facts = {"city": text.title()}
        elif pending == "business_type" and _plausible("business_type", text):
            facts = {"business_type": text.capitalize()}
    if pending in ("business_type", "city") and pending in facts and text and not _plausible(pending, text) \
            and not _plausible(pending, str(facts[pending])):
        facts.pop(pending)  # the AI copied a non-answer ("Englishe karna chahta hu") into the profile: ask again
    if pending == "current" and text and "current_internet" in facts:
        m = re.search(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]{2,6})", text.lower())
        if m and "current_spend" not in facts and 100 <= int(m.group(1).replace(",", "")) <= 200000:
            facts["current_spend"] = int(m.group(1).replace(",", ""))
    if facts:
        _apply(p, facts, lang, msgs, s)
        s["misses"] = 0
        if not msgs and pending in SLOT_ORDER and pending in p.missing() and pending not in facts:
            msgs.append(t(lang, "noted"))  # an answer to something else: keep it, thank her, ask again
    elif text and not answered and not chatter:
        s["misses"] = s.get("misses", 0) + 1
        if pending == "gstin" and s["misses"] >= 2:  # never ask a third time: carry on without one, it can be added later
            _apply(p, {"has_gstin": False}, lang, msgs, s)
            s["misses"] = 0
    if s.get("gstin_check") and stage != "done":  # "is this your business?" comes before anything else
        s["pending_slot"] = "gstin_confirm"
        return {"messages": msgs, "chips": _chips("gstin_confirm", lang)}
    if stage == "needs" and ((set(facts) - {"current_internet", "current_spend"}) or action == "proceed"):
        out = _recommend(s, p)
        out["messages"] = msgs + out["messages"]
        out["chips"] = _done_chips(s, lang)
        return out
    if stage == "needs":
        return {"messages": msgs or [t(lang, "ask_needs")], "chips": _pain_chips(p, lang), **_needs_payload(p, lang)}
    return _continue(s, p, msgs, lang, missed=bool(text) and not facts and not answered and not chatter)


def _continue(s: dict, p: Profile, msgs: list[str], lang: str, missed: bool = False) -> dict:
    """Ask the next missing detail, or move on to the needs checklist."""
    if s["stage"] == "done":
        return {"messages": msgs, "chips": _done_chips(s, lang)}
    nxt = _next_slot(p)
    if not nxt and p.has_gstin and not p.gstin and not s.get("asked_gstin_number"):
        # GST-registered but no number yet: ask once, since the GSTIN fills in and verifies everything instantly
        s["asked_gstin_number"], s["pending_slot"] = True, "gstin"
        return {"messages": msgs + [t(lang, "ask_gstin_type")],
                "chips": [{"label": t(lang, "chip_skip"), "slot": "gstin", "value": "skip"}]}
    if nxt:
        q = _question(nxt, lang)
        if missed and s.get("misses"):
            q = t(lang, "didnt_get", question=q)
        s["pending_slot"] = nxt
        stuck = [_chip(t(lang, "chip_call"), "callback")] if missed and s.get("misses", 0) >= 2 else []  # offer a person
        return {"messages": msgs + [q], "chips": _chips(nxt, lang) + stuck}
    if not p.current_internet and not s.get("asked_current") and s["stage"] == "chat":
        # what they use today: the brief asks for it, and it shapes how the bundle is explained
        s["asked_current"], s["pending_slot"] = True, "current"
        return {"messages": msgs + [t(lang, "ask_current")], "chips": _chips("current", lang)}
    if s["stage"] == "chat":
        s["stage"], s["status"], s["pending_slot"] = "needs", "needs_assessed", None
    chips = _pain_chips(p, lang)
    return {"messages": msgs + [t(lang, "ask_needs")] + ([t(lang, "pain_ask")] if chips else []), "chips": chips,
            **_needs_payload(p, lang)}


def resume(session_id: str) -> dict:
    """Everything the app needs to redraw the chat after going back or reloading the page."""
    s = store.get("session", session_id)
    if not s:
        raise KeyError("session not found")
    p = _profile(s)
    last = s.get("last") or {}
    out = {"session_id": s["id"], "lang": s["lang"], "stage": s["stage"], "history": s["history"],
           "profile": _public_profile(p), "chips": last.get("chips") or (_chips(s.get("pending_slot"), s["lang"])
                                                                        if s["stage"] == "chat" else [])}
    if s["stage"] == "needs":
        out["needs"] = last.get("needs") or _needs_payload(p, s["lang"])["needs"]
    if s["stage"] == "done" and s.get("recommendation"):
        out["recommendation"] = s["recommendation"]
        out["chips"] = _done_chips(s, s["lang"])
    return out


def set_language(session_id: str, lang: str) -> dict:
    s = store.get("session", session_id)
    if not s or lang not in LANGS:
        raise KeyError("bad session or language")
    s["lang"], s["lang_pinned"] = lang, False  # chosen in the menu: replies may still follow what she types
    store.put("session", s["id"], s)
    return {"ok": True}
