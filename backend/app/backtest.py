"""Does the recommendation match what real customers bought? A leave-one-out back-test on Accel's activated customers.

For each of the 368 activated customers in smb_leads.csv, everything the ranking learned is recomputed without that
customer, the advisor builds the Recommended bundle from what we would know at the first chat (business type,
segment, team size, sites, city, GST status, current internet), and the bundle is compared with what the customer
actually bought:
  precision = share of the services we recommended that the customer bought,
  recall    = share of the services the customer bought that we recommended.
Methods compared, each a valid bundle (one internet line, one mobile plan, catalogue rules) of the same size:
  learned  = this advisor: needs checked against what similar customers kept, ranked by take-up (ranker.py);
  hand     = the same engine with hand-written needs by business type and a fixed product order (our first version);
  popular  = the most-bought services across all customers;
  segment  = the most-bought services in the customer's segment.
"""
from collections import Counter
from contextlib import contextmanager

from . import ranker, recommender
from .data import SEGMENT_KEY, leads
from .recommender import CONNECTIVITY, Profile, _NEED_OF, check_eligibility, recommend

_CURRENT = {"Business broadband": "business", "Home broadband": "home", "Mobile hotspot": "hotspot",
            "Leased line": "leased", "Mixed per site": "business"}


def _profile(r) -> Profile:
    p = Profile(business_type=r["business_type"], segment=SEGMENT_KEY[r["segment"]], employees=int(r["employee_count"]),
                sites=int(r["num_sites"]), city=r["city"], city_tier=int(r["city_tier"]), has_gstin=r["has_gstin"] == "Y",
                gstin_verified=True if r["has_gstin"] == "Y" else None, current_internet=_CURRENT.get(r["current_internet"], ""))
    p.needs_confirmed = True
    return p


@contextmanager
def _without(r):
    """Forget one customer while we predict them."""
    s = ranker._stats()
    seg, bt, ps, w = SEGMENT_KEY[r["segment"]], str(r["business_type"]).lower(), ranker._products(r["bundle_products"]), ranker.weight(r)
    ranker.count(s, seg, bt, ps, w, -1)
    try:
        yield
    finally:
        ranker.count(s, seg, bt, ps, w, +1)


@contextmanager
def _fixed_order():
    learned = ranker.order
    ranker.order = lambda items, seg, bt, fallback: sorted(
        items, key=lambda it: {pid: i for i, pid in enumerate(fallback)}.get(it["id"], 99))
    try:
        yield
    finally:
        ranker.order = learned


def _bundle(p: Profile, needs: set) -> set[str]:
    p.needs = set(needs)
    return {l["id"] for l in recommend(p)["quote"]["lines"]}


def _popular(p: Profile, counts: Counter, k: int) -> set[str]:
    out: set[str] = set()
    for pid, _ in counts.most_common():
        if len(out) >= k:
            break
        if (pid in CONNECTIVITY and out & set(CONNECTIVITY)) or (pid in ("P07", "P08") and out & {"P07", "P08"}):
            continue
        if check_eligibility(pid, p, out | {"P01"}) is None:
            out.add(pid)
    return out


def run() -> dict:
    act = leads()
    act = act[act["outcome"] == "Activated"]
    sums = {m: [0.0, 0.0] for m in ("learned", "hand", "popular", "segment")}
    n = 0
    for _, r in act.iterrows():
        if r["segment"] not in SEGMENT_KEY:
            continue
        actual = ranker._products(r["bundle_products"])
        with _without(r):
            p = _profile(r)
            p.segment = recommender.infer_segment(p)
            got = {"learned": _bundle(_profile(r), recommender.default_needs(p))}
            with _fixed_order():
                got["hand"] = _bundle(_profile(r), recommender.typical_needs(p))
            s, k = ranker._stats(), len(got["learned"])
            everyone = Counter()
            for c in s["seg_bought"].values():
                everyone.update(c)
            got["popular"] = _popular(p, everyone, k)
            got["segment"] = _popular(p, s["seg_bought"][p.segment], k)
        for m, ours in got.items():
            hit = len(ours & actual)
            sums[m][0] += hit / len(ours) if ours else 0
            sums[m][1] += hit / len(actual) if actual else 0
        n += 1
    out = {}
    for m, (ps, rs) in sums.items():
        pr, rc = ps / n, rs / n
        out[m] = {"precision": round(pr, 3), "recall": round(rc, 3), "f1": round(2 * pr * rc / (pr + rc), 3) if pr + rc else 0}
    out["customers"] = n
    return out
