"""Ranking learned from Accel's own customers, not hand-set weights.

The advisor works in four steps:
  1. understand: the owner's words become a business profile (type, city, staff, sites, current internet, needs);
  2. check: catalogue rules decide what this business may have (eligibility, dependencies, quantities);
  3. rank: every eligible service is scored by what similar businesses actually bought and asked for;
  4. level: the ranked list is cut into Basic, Recommended and Complete by what such a business typically pays.

Step 3 uses the activated customers in smb_leads.csv. Most business types have only 5 to 20 activated customers,
so a type's own numbers are pulled towards its segment's (a Bayesian average with a prior of K customers):
a pharmacy's ranking follows pharmacies where there is enough evidence and small shops in general where there isn't.
A customer who left within six months counts half (churned_within_6_months), so the ranking follows what customers
kept, not just what was sold to them. A second signal is what owners of the same type asked for when they first
enquired (all 5,000 leads), because a service many owners ask for but few were sold points to a need the old journey
missed. The owner's own words come first: a service that solves a problem she told us about (app/pains.py) is
always in, whatever the ranking says.

K and the two thresholds below were chosen by a leave-one-out back-test on the 368 activated customers
(app/backtest.py, tests/run_ranking_eval.py): each customer's bundle is predicted from everyone else's.

Add-ons are ranked by co-occurrence: among similar customers who have the services already in the bundle, how much
more often they also have the add-on than customers in general (lift).
"""
from collections import Counter
from functools import lru_cache

from .data import SEGMENT_KEY, leads

K = 30  # prior strength, in customers
W_BOUGHT, W_ASKED = 0.75, 0.25
W_CHURNED = 0.5  # a customer who left within six months counts half
KEEP_TYPICAL = 0.30  # a usual need for this kind of business stays pre-ticked if this share of similar customers kept it
ADD_LEARNED = 0.35  # any service this share of similar customers kept is pre-ticked too


def _products(cell) -> set[str]:
    if not isinstance(cell, str):
        return set()
    return {i.split("x")[0] for i in cell.split(";") if i}


@lru_cache
def _stats() -> dict:
    df = leads()
    act = df[df["outcome"] == "Activated"]
    out = {"seg_n": Counter(), "seg_bought": {}, "type_n": Counter(), "type_bought": {}, "type_seg": {},
           "type_asked_n": Counter(), "type_asked": {}, "seg_asked_n": Counter(), "seg_asked": {}, "bundles": {},
           "seg_w": Counter(), "type_w": Counter()}
    for _, r in act.iterrows():
        seg, bt = SEGMENT_KEY.get(r["segment"]), str(r["business_type"]).lower()
        if seg:
            count(out, seg, bt, _products(r["bundle_products"]), weight(r), +1)
            out["type_seg"][bt] = seg
    for _, r in df.iterrows():
        seg, bt = SEGMENT_KEY.get(r["segment"]), str(r["business_type"]).lower()
        asked = {p for p in str(r["products_of_interest"]).split(";") if p.startswith("P")}
        if not seg:
            continue
        out["type_asked_n"][bt] += 1
        out["type_asked"].setdefault(bt, Counter()).update(asked)
        out["seg_asked_n"][seg] += 1
        out["seg_asked"].setdefault(seg, Counter()).update(asked)
    return out


def weight(row) -> float:
    return W_CHURNED if str(row.get("churned_within_6_months", "N")).upper() == "Y" else 1.0


def count(s: dict, seg: str, bt: str, ps: set, w: float, sign: int) -> None:
    """Add (sign +1) or take out (sign -1, for the leave-one-out back-test) one activated customer."""
    s["seg_n"][seg] += sign
    s["type_n"][bt] += sign
    s["seg_w"][seg] += sign * w
    s["type_w"][bt] += sign * w
    for pid in ps:
        s["seg_bought"].setdefault(seg, Counter())[pid] += sign * w
        s["type_bought"].setdefault(bt, Counter())[pid] += sign * w
    if sign > 0:
        s["bundles"].setdefault(seg, []).append(ps)
    else:
        s["bundles"][seg].remove(ps)


def _smoothed(type_count: float, type_n: float, seg_share: float) -> float:
    return (type_count + K * seg_share) / (type_n + K)


def bought_share(segment: str, business_type: str, pid: str) -> float:
    """Share of similar activated customers who have this service, a customer who left counting half (type pulled
    towards segment)."""
    s = _stats()
    seg_w = s["seg_w"].get(segment, 0)
    seg_share = s["seg_bought"].get(segment, Counter())[pid] / seg_w if seg_w > 0 else 0.0
    bt = (business_type or "").lower()
    if s["type_n"].get(bt) and s["type_seg"].get(bt) == segment:
        return _smoothed(s["type_bought"][bt][pid], s["type_w"][bt], seg_share)
    return seg_share


def asked_share(segment: str, business_type: str, pid: str) -> float:
    """Share of similar owners (all leads) who asked about this service when they enquired."""
    s = _stats()
    seg_n = s["seg_asked_n"].get(segment, 0)
    seg_share = s["seg_asked"].get(segment, Counter())[pid] / seg_n if seg_n else 0.0
    bt = (business_type or "").lower()
    if s["type_asked_n"].get(bt):
        return _smoothed(s["type_asked"][bt][pid], s["type_asked_n"][bt], seg_share)
    return seg_share


def score(segment: str, business_type: str, pid: str) -> float:
    return W_BOUGHT * bought_share(segment, business_type, pid) + W_ASKED * asked_share(segment, business_type, pid)


def order(items: list[dict], segment: str, business_type: str, fallback: list[str]) -> list[dict]:
    """Highest score first; the old fixed order only breaks ties."""
    rank = {pid: i for i, pid in enumerate(fallback)}
    return sorted(items, key=lambda it: (-round(score(segment, business_type, it["id"]), 3), rank.get(it["id"], 99)))


def likely(segment: str, business_type: str, pid: str, typical: bool) -> bool:
    """Pre-tick this service? A usual need for this kind of business needs KEEP_TYPICAL of similar customers to have
    kept it; anything else needs ADD_LEARNED."""
    return bought_share(segment, business_type, pid) >= (KEEP_TYPICAL if typical else ADD_LEARNED)


def take_up(segment: str, business_type: str, pid: str) -> int | None:
    """"n in 10 similar businesses have this", from the smoothed share; None when it rounds to 0."""
    n = round(bought_share(segment, business_type, pid) * 10)
    return n or None


def often_with(segment: str, chosen: set[str], pid: str) -> float:
    """Lift: how much more often customers who have the bundle's services also have this add-on, vs all customers
    of the segment. 1.0 means no link; only bundles sharing at least one service count."""
    bundles = _stats()["bundles"].get(segment, [])
    if not bundles or not chosen:
        return 1.0
    base = sum(pid in b for b in bundles) / len(bundles)
    near = [b for b in bundles if len(b & chosen) >= max(1, min(2, len(chosen)))]
    if not base or len(near) < 8:
        return 1.0
    return (sum(pid in b for b in near) / len(near)) / base


def similar(segment: str, business_type: str) -> dict:
    """Who "similar businesses" are for this owner: the type if it has activated customers, else the segment."""
    s = _stats()
    bt = (business_type or "").lower()
    if s["type_n"].get(bt, 0) >= 5 and s["type_seg"].get(bt) == segment:
        return {"kind": "type", "label": business_type, "n": s["type_n"][bt], "segment_n": s["seg_n"][segment]}
    return {"kind": "segment", "label": segment, "n": s["seg_n"].get(segment, 0), "segment_n": s["seg_n"].get(segment, 0)}
