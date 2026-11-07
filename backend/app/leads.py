"""Lead propensity model and the partner/field-sales call list.

A logistic regression trained on the quarter of leads (smb_leads.csv) using only what is known when a
lead arrives. Coefficients are kept so every score comes with its top reasons, which a sales partner
can act on.
"""
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from . import store
from .data import SEGMENTS, leads

CATEGORICAL = ["lead_source", "segment", "preferred_language", "current_internet", "annual_turnover_band"]
NUMERIC = ["city_tier", "log_employees", "num_sites", "has_gstin", "has_udyam", "log_spend", "n_interest"]
FRIENDLY = {
    "has_gstin": "has a GSTIN", "has_udyam": "has Udyam registration", "log_spend": "current telecom spend",
    "log_employees": "team size", "num_sites": "number of sites", "n_interest": "products asked about",
    "city_tier": "city tier",
}

PARTNERS = [
    {"id": "PT01", "name": "Shree Telecom Solutions", "cities": ["Pune", "Mumbai", "Nashik", "Nagpur"], "languages": ["Marathi", "Hindi", "English"]},
    {"id": "PT02", "name": "Dakshin Digital", "cities": ["Chennai", "Coimbatore", "Bengaluru", "Mysuru", "Kochi"], "languages": ["Tamil", "Kannada", "Malayalam", "English"]},
    {"id": "PT03", "name": "Ganga Connect", "cities": ["Delhi", "Lucknow", "Patna", "Jaipur", "Indore", "Bhopal", "Ludhiana"], "languages": ["Hindi", "Punjabi", "English"]},
    {"id": "PT04", "name": "Sabarmati Networks", "cities": ["Ahmedabad", "Surat", "Vadodara"], "languages": ["Gujarati", "Hindi", "English"]},
    {"id": "PT05", "name": "Purvi Telecom", "cities": ["Kolkata", "Visakhapatnam", "Hyderabad"], "languages": ["Bengali", "Telugu", "Hindi", "English"]},
]


def _features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    for c in CATEGORICAL:
        x[c] = df[c].fillna("Unknown").astype(str)
    x["city_tier"] = df["city_tier"].fillna(2)
    x["log_employees"] = np.log1p(df["employee_count"].fillna(1))
    x["num_sites"] = df["num_sites"].fillna(1).clip(upper=12)
    x["has_gstin"] = (df["has_gstin"] == "Y").astype(int)
    x["has_udyam"] = (df["has_udyam"] == "Y").astype(int)
    x["log_spend"] = np.log1p(df["monthly_telecom_spend_inr"].fillna(0))
    x["n_interest"] = df["products_of_interest"].fillna("").str.count(";") + df["products_of_interest"].notna()
    return pd.get_dummies(x, columns=CATEGORICAL, dtype=float)


@lru_cache
def model() -> dict:
    df = leads()
    X = _features(df)
    y = (df["outcome"] == "Activated").astype(int).values
    mu, sd = X.mean(), X.std().replace(0, 1)
    Xs = (X - mu) / sd
    clf = LogisticRegression(max_iter=2000, C=0.5)
    oof = cross_val_predict(clf, Xs, y, cv=StratifiedKFold(5, shuffle=True, random_state=7), method="predict_proba")[:, 1]
    clf.fit(Xs, y)
    order = np.argsort(-oof)
    top_decile = order[: len(order) // 10]
    return {"clf": clf, "cols": list(X.columns), "mu": mu, "sd": sd, "auc": round(float(roc_auc_score(y, oof)), 3),
            "base_rate": round(float(y.mean()), 3),
            "top_decile_rate": round(float(y[top_decile].mean()), 3),
            "coef": dict(zip(X.columns, clf.coef_[0]))}


def _driver_name(col: str, value: float | None = None) -> str:
    if col in ("has_gstin", "has_udyam") and value == 0:
        return "no GSTIN" if col == "has_gstin" else "no Udyam registration"
    for c in CATEGORICAL:
        if col.startswith(c + "_"):
            return f"{c.replace('_', ' ')}: {col[len(c) + 1:]}"
    return FRIENDLY.get(col, col)


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    m = model()
    X = _features(df).reindex(columns=m["cols"], fill_value=0.0)
    Xs = (X - m["mu"]) / m["sd"]
    p = m["clf"].predict_proba(Xs)[:, 1]
    contrib = Xs.values * m["clf"].coef_[0]
    dummy = np.array([any(c.startswith(k + "_") for k in CATEGORICAL) for c in m["cols"]])
    drivers = []
    for row, xrow in zip(contrib, X.values):
        row = np.where(dummy & (xrow == 0), 0.0, row)  # explain only with facts true for this lead
        idx = np.argsort(-np.abs(row))[:3]
        drivers.append([{"factor": _driver_name(m["cols"][i], xrow[i]), "effect": "up" if row[i] > 0 else "down"}
                        for i in idx])
    out = df.copy()
    out["score"] = np.round(p * 100).astype(int)  # calibrated chance of activation, in %
    out["drivers"] = drivers
    return out


def next_best_action(r: dict) -> str:
    if r.get("has_gstin") != "Y":
        return "Help them get a GSTIN (free, about a week). It unlocks WhatsApp/SMS and lifts activation 5x."
    stage = r.get("stage_reached", "")
    reason = r.get("drop_reason") or ""
    if "Installation delayed" in reason or "not feasible" in reason:
        return "Install was the blocker: offer 5G AirFiber now (2-day setup) and move to fibre later."
    if "Price" in reason or "cheaper" in reason:
        return "Price objection: show the 24-month price and the 'replaces N vendors' saving."
    if stage == "Quote accepted":
        return "KYC stalled: offer DigiLocker or a doorstep pickup and e-sign on the same visit."
    if stage == "Needs assessed":
        return "Quote not accepted: send the one-page bundle quote and the 24-month price."
    if r.get("segment") in (SEGMENTS["mfg"], SEGMENTS["multi"]):
        return "Complex site: book a field survey for leased line / SD-WAN."
    if r.get("preferred_language") not in ("English", "Hindi"):
        return f"Call in {r.get('preferred_language')} through the local partner."
    return "Call within 24 hours and share the advisor link on WhatsApp."


def partner_for(city: str, language: str) -> dict | None:
    for p in PARTNERS:
        if city in p["cities"] and (not language or language in p["languages"]):
            return p
    return next((p for p in PARTNERS if city in p["cities"]), None)


def call_list(limit: int = 40) -> list[dict]:
    """Open opportunities from the last quarter: leads that showed intent but dropped for reasons a
    partner can fix (not 'wrong number' or 'locked in')."""
    df = leads()
    fixable = df[(df.outcome == "Dropped") & df.stage_reached.isin(["Needs assessed", "Quote accepted", "KYC complete"])
                 & ~df.drop_reason.isin(["Customer cancelled before install", "Competitor offered cheaper plan"])]
    scored = score_frame(fixable).sort_values("score", ascending=False).head(limit)
    out = []
    for r in scored.to_dict("records"):
        partner = partner_for(r["city"], r["preferred_language"])
        out.append({"lead_id": r["lead_id"], "business": r["business_name"], "type": r["business_type"],
                    "segment": r["segment"], "city": r["city"], "language": r["preferred_language"],
                    "stage": r["stage_reached"], "drop_reason": r["drop_reason"], "score": int(r["score"]),
                    "drivers": r["drivers"], "action": next_best_action(r), "source": "Q1 pipeline",
                    "partner": partner["name"] if partner else "Field sales"})
    return out


def live_leads() -> list[dict]:
    """Advisor sessions that did not reach an order: the leads the bot could not close."""
    out = []
    for s in store.list_("session", 300):
        if s.get("status") == "order_placed":
            continue
        p = s.get("profile", {})
        if not p.get("business_type") and not p.get("city"):
            continue
        row = pd.DataFrame([{
            "lead_source": "Website form", "segment": SEGMENTS.get(p.get("segment") or "micro", SEGMENTS["micro"]),
            "preferred_language": {"hi": "Hindi", "mr": "Marathi", "ta": "Tamil"}.get(s.get("lang"), "English"),
            "current_internet": p.get("current_internet") or "Mobile hotspot", "annual_turnover_band": "< 40 lakh",
            "city_tier": p.get("city_tier") or 2, "employee_count": p.get("employees") or 1,
            "num_sites": p.get("sites") or 1, "has_gstin": "Y" if p.get("has_gstin") else "N", "has_udyam": "N",
            "monthly_telecom_spend_inr": p.get("current_spend") or 0, "products_of_interest": None}])
        sc = score_frame(row).iloc[0]
        rec = (s.get("recommendation") or {}).get("quote", {})
        partner = partner_for(p.get("city", ""), row.preferred_language[0])
        out.append({"lead_id": s["id"], "business": p.get("business_name") or p.get("business_type"),
                    "type": p.get("business_type"), "segment": row.segment[0], "city": p.get("city"),
                    "language": row.preferred_language[0], "stage": s.get("status", "").replace("_", " "),
                    "drop_reason": "Left during " + s.get("status", "advisor").replace("_", " "),
                    "score": int(sc.score), "drivers": sc.drivers, "monthly": rec.get("monthly"),
                    "action": next_best_action({"has_gstin": "Y" if p.get("has_gstin") else "N",
                                                "stage_reached": "Needs assessed" if s.get("status") == "quote_viewed" else "",
                                                "segment": row.segment[0],
                                                "preferred_language": row.preferred_language[0]}),
                    "source": "Live advisor", "partner": partner["name"] if partner else "Field sales",
                    "updated": s.get("created")})
        if s.get("callback"):
            out[-1]["drop_reason"] = "Asked for a call back"
            out[-1]["action"] = f"Call back now on ******{s['callback']['phone'][-4:]} (owner asked, chat saved)"
            out[-1]["callback"] = True
    return sorted(out, key=lambda r: (not r.get("callback"), -r["score"]))


def model_card() -> dict:
    m = model()
    top = sorted(m["coef"].items(), key=lambda kv: -abs(kv[1]))[:8]
    return {"auc": m["auc"], "base_rate": m["base_rate"], "top_decile_rate": m["top_decile_rate"],
            "lift": round(m["top_decile_rate"] / m["base_rate"], 1),
            "top_factors": [{"factor": _driver_name(k), "weight": round(float(v), 2)} for k, v in top],
            "training_rows": int(len(leads()))}
