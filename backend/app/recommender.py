"""Deterministic bundle engine.

The LLM never chooses products. It only helps understand the owner; this module picks the
bundle, enforces every catalogue rule (city tier, size, sites, GSTIN, dependencies) and prices it.
That keeps every quote valid and explainable, whatever the owner types.
"""
from dataclasses import dataclass, field
from math import ceil

from .data import SEGMENTS, Product, business_types, city_states, city_tiers, products
from . import ranker

NEEDS = [
    "payments", "whatsapp", "sms", "cctv", "email", "security", "backup", "website", "guest_wifi",
    "failover", "calls", "tollfree", "static_ip", "iot", "fleet", "central_mgmt", "firewall",
]

# What owners of each kind of business usually need. Shown as pre-ticked choices the owner can change.
_DEFAULT_NEEDS_BY_KEYWORD = [
    (("kirana", "sweet", "bakery", "stationery", "hardware"), {"payments", "whatsapp", "cctv"}),
    (("pharmacy",), {"payments", "whatsapp", "cctv"}),
    (("salon", "boutique", "optician", "mobile repair"), {"payments", "whatsapp", "guest_wifi", "cctv"}),
    (("dental", "physio", "diagnostic", "clinic"), {"email", "security", "backup", "failover", "whatsapp"}),
    (("ca firm", "law", "insurance", "architecture", "real estate", "travel"), {"email", "security", "backup"}),
    (("coaching", "pre-school"), {"email", "cctv", "guest_wifi", "sms"}),
    (("restaurant", "bakery chain", "apparel", "electronics", "pharmacy chain"),
     {"payments", "cctv", "failover", "central_mgmt", "guest_wifi"}),
    (("hotel",), {"payments", "cctv", "guest_wifi", "failover", "central_mgmt", "tollfree"}),
    (("gym",), {"payments", "cctv", "guest_wifi", "central_mgmt"}),
    (("unit", "press", "workshop", "manufactur", "factory"), {"email", "security", "cctv", "iot", "firewall"}),
]

ALTERNATIVES = {"P03": "P02", "P02": "P01", "P05": "P03", "P06": "P05", "P10": "P09", "P12": "P08", "P13": "P12", "P21": "P20",
                "P14": "P18", "P15": "P18"}
CONNECTIVITY = ("P01", "P02", "P03", "P04", "P05", "P06")
CONN_LADDER = {"P04": 0, "P01": 1, "P02": 2, "P03": 3, "P05": 4, "P06": 5}  # cheapest to dearest
CONN_DOWNGRADE = {"P03": "P02", "P02": "P01", "P06": "P05"}


@dataclass
class Profile:
    business_name: str = ""
    business_type: str = ""
    segment: str = ""             # micro | prof | multi | mfg
    employees: int | None = None
    sites: int | None = None
    city: str = ""
    state: str = ""
    city_tier: int | None = None
    has_gstin: bool | None = None
    gstin: str = ""
    gstin_verified: bool | None = None   # None = not checked yet, False = checked and not valid/active
    fibre_available: bool = True
    current_spend: int | None = None
    current_internet: str = ""
    needs: set = field(default_factory=set)
    explicit_needs: set = field(default_factory=set)  # needs the owner confirmed or asked for (never trimmed by budget)
    asked_needs: set = field(default_factory=set)  # needs the owner typed themselves (kept even when asked for cheaper)
    budget: int | None = None
    counts: dict = field(default_factory=dict)  # mobile_lines, cameras, users, devices, counters, vehicles, machines
    contract_months: int = 12
    needs_confirmed: bool = False  # the owner has confirmed the needs checklist, so no needs are implied any more
    pains: list = field(default_factory=list)  # problems the owner told us about (app/pains.py), in her order
    small_sites: int = 0  # of the sites, how many are small outlets that get a lighter setup
    conn_cap: str = ""  # cheapest-first cap on the internet line, set when the owner asks for a cheaper bundle
    full: bool = False  # the "Complete" option: keep every useful service in the bundle instead of suggesting some

    def missing(self) -> list[str]:
        out = []
        if not self.business_type and not self.segment:
            out.append("business_type")
        if self.employees is None:
            out.append("employees")
        if self.sites is None:
            out.append("sites")
        if not self.city and self.city_tier is None:
            out.append("city")
        if self.has_gstin is None:
            out.append("gstin")
        return out


def infer_segment(p: Profile) -> str:
    if p.segment:
        return p.segment
    bt = business_types().get(p.business_type)
    if (p.sites or 1) >= 3:
        return "multi"
    if bt:
        return bt
    t = p.business_type.lower()
    if any(k in t for k in ("unit", "factory", "manufactur", "press", "workshop", "plant")):
        return "mfg"
    if any(k in t for k in ("clinic", "ca ", "firm", "office", "agency", "coaching", "lab", "studio", "law")):
        return "prof"
    if (p.employees or 0) >= 8:
        return "prof"
    return "micro"


def resolve_location(p: Profile) -> None:
    if p.city:
        match = next((c for c in city_tiers() if c.lower() == p.city.lower()), None)
        if match:
            p.city = match
            p.city_tier = p.city_tier or city_tiers()[match]
            p.state = p.state or city_states()[match]
    if p.city_tier is None:
        p.city_tier = 2  # unknown town: assume tier 2, so we never promise a tier-1-only product


def typical_needs(p: Profile) -> set:
    """What an experienced salesperson would expect this kind of business to need (hand-written, by keyword)."""
    t = (p.business_type or "").lower()
    for keys, needs in _DEFAULT_NEEDS_BY_KEYWORD:
        if any(k in t for k in keys):
            return set(needs)
    return {"micro": {"payments", "whatsapp"}, "prof": {"email", "security"},
            "multi": {"payments", "cctv", "central_mgmt", "failover"},
            "mfg": {"email", "security", "cctv"}}[infer_segment(p)]


def default_needs(p: Profile) -> set:
    """The needs pre-ticked for this owner, checked against what similar Accel customers actually kept: a typical need
    stays only if enough of them kept it, and anything most of them kept is added (thresholds in ranker.py, chosen by
    the back-test). Problems the owner told us about are added on top by the advisor."""
    seg, typical = infer_segment(p), typical_needs(p)
    return {need for pid, need in _NEED_OF.items() if ranker.likely(seg, p.business_type, pid, need in typical)}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def default_counts(p: Profile) -> dict:
    seg, emp, sites = p.segment, p.employees or 1, p.sites or 1
    return {
        "mobile_lines": {"micro": _clamp(emp // 2, 1, 2), "prof": _clamp(round(emp / 5), 2, 6),
                         "multi": _clamp(sites // 2 + 1, 3, 10), "mfg": _clamp(emp // 20, 2, 8)}[seg],
        "users": {"micro": 1, "prof": _clamp(ceil(emp * 0.6), 2, 25),
                  "multi": _clamp(sites + 2, 3, 20), "mfg": _clamp(emp // 8, 3, 25)}[seg],
        "cameras": {"micro": 2, "prof": 2, "multi": max(2, round(sites * 1.5)), "mfg": 4 + emp // 50}[seg],
        "counters": sites if seg == "multi" else 1,
        "vehicles": 2,
        "machines": _clamp(emp // 10, 2, 15),
        "channels": _clamp(emp // 5, 2, 6),
    }


def unit_price(prod: Product, term: int) -> int:
    """Longer commitment = lower price inside the catalogue range. Always within [min, max]."""
    if term >= 24:
        return prod.price_min
    mid = (prod.price_min + prod.price_max) / 2
    return min(prod.price_max, max(prod.price_min, int(round(mid / 10) * 10 - 1)))


def check_eligibility(pid: str, p: Profile, chosen: set) -> str | None:
    """Return None if the product can be sold to this profile, else a reason key."""
    prod = products()[pid]
    if p.city_tier not in prod.tiers:
        return "tier"
    if (p.employees or 1) < prod.min_employees:
        return "employees"
    if (p.sites or 1) < prod.min_sites:
        return "sites"
    if prod.requires_gstin and not (p.has_gstin and p.gstin_verified is not False):
        return "gstin"
    if prod.requires_one_of and not (set(prod.requires_one_of) & chosen):
        return "dependency"
    return None


def _connectivity(p: Profile) -> tuple[str, str]:
    seg, emp, gst, tier = p.segment, p.employees or 1, bool(p.has_gstin), p.city_tier
    if seg == "mfg" and gst and emp >= 100:
        return "P06", "conn_mfg_heavy"
    if seg == "mfg" and gst and emp >= 10:
        return "P05", "conn_mfg"
    if not p.fibre_available:
        return "P04", "conn_no_fibre"
    if seg == "prof" and gst and tier == 1 and emp >= 20:
        return "P03", "conn_prof_large"
    if seg in ("prof", "multi", "mfg") and emp >= 5:
        return "P02", "conn_prof" if seg == "prof" else "conn_multi"
    return "P01", "conn_micro"


def best_connectivity(p: Profile) -> str | None:
    """The recommended line for this business, or the next best one it is eligible for."""
    pid = _connectivity(p)[0]
    while pid and check_eligibility(pid, p, set()) is not None:
        pid = ALTERNATIVES.get(pid)
    return pid


def build_items(p: Profile) -> list[dict]:
    """Pick products and quantities from needs. Returns [{id, qty, reason}] before eligibility checks."""
    c = {**default_counts(p), **{k: v for k, v in p.counts.items() if v is not None}}
    sites = p.sites or 1
    n = p.needs
    items: list[dict] = []

    def add(pid, qty, reason):
        if qty > 0 and not any(i["id"] == pid for i in items):
            items.append({"id": pid, "qty": int(qty), "reason": reason})

    conn, why = _connectivity(p)
    if p.conn_cap and CONN_LADDER.get(conn, 0) > CONN_LADDER.get(p.conn_cap, 0):
        conn, why = p.conn_cap, ("conn_micro" if p.conn_cap == "P01" else why)
    small = min(p.small_sites or 0, sites - 1) if p.segment == "multi" else 0
    if small and "cameras" not in p.counts:  # a small outlet needs one camera, not one and a half
        c["cameras"] = max(2, round((sites - small) * 1.5) + small)
    if small and conn in CONN_DOWNGRADE:  # the big outlets keep the line they need; the small ones get the next one down
        add(conn, sites - small, why)
        add(CONN_DOWNGRADE[conn], small, "conn_small_site")
    else:
        add(conn, sites if p.segment == "multi" else 1, why)
    if p.segment in ("micro",):
        add("P07", c["mobile_lines"], "mobile_micro")
    else:
        add("P08", c["mobile_lines"], "mobile_pro")
    if "payments" in n:
        add("P19", c["counters"], "pos")
    if "whatsapp" in n:
        add("P15", 1, "whatsapp")
    if "sms" in n:
        add("P14", 1, "sms")
    if "cctv" in n:
        add("P23", c["cameras"], "cctv")
    if "email" in n:
        add("P16", c["users"], "email")
    if "security" in n:
        add("P20", c.get("devices") or c["users"], "endpoint")
    if "backup" in n:
        add("P17", 1, "backup")
    if "website" in n:
        add("P18", 1, "website")
    if "guest_wifi" in n:
        add("P22", sites, "guest_wifi")
    implied = p.segment == "multi" and not p.needs_confirmed
    if "failover" in n or implied:
        add("P09", sites, "failover")
    if "central_mgmt" in n or implied:
        add("P10", sites, "sdwan")
    if "calls" in n:
        add("P12", c["channels"], "telephony")
    if "tollfree" in n:
        add("P13", 1, "tollfree")
    if conn in ("P01", "P02", "P03") and ("static_ip" in n or ("cctv" in n and p.segment in ("prof", "mfg"))):
        add("P11", 1, "static_ip")
    if "firewall" in n or (p.segment in ("mfg", "multi") and (p.employees or 0) >= 10 and "security" in n):
        add("P21", 1, "firewall")
    if "iot" in n:
        add("P24", c["machines"], "iot")
    if "fleet" in n:
        add("P25", c["vehicles"], "fleet")
    return items


def enforce_rules(items: list[dict], p: Profile) -> tuple[list[dict], list[dict], list[str]]:
    """Apply catalogue eligibility. Returns (kept, blocked, notes). Swaps in alternatives where they fit
    and adds a connectivity product if a dependent product needs one."""
    kept, blocked, notes = [], [], []
    pending = list(items)
    while pending:
        it = pending.pop(0)
        chosen = {i["id"] for i in kept} | {i["id"] for i in pending}
        why = check_eligibility(it["id"], p, chosen)
        if why is None:
            kept.append(it)
            continue
        if why == "dependency":
            dep = best_connectivity(p) if not (chosen & set(CONNECTIVITY)) else None
            if dep and dep in products()[it["id"]].requires_one_of:
                pending.insert(0, it)
                pending.insert(0, {"id": dep, "qty": 1, "reason": "dependency_added"})
                notes.append(f"added:{dep}:{it['id']}")
                continue
        alt = ALTERNATIVES.get(it["id"])
        while alt and check_eligibility(alt, p, chosen | {alt}) is not None:
            alt = ALTERNATIVES.get(alt)
        blocked.append({"id": it["id"], "why": why, "alternative": alt})
        if alt and not any(i["id"] == alt for i in kept + pending):
            pending.insert(0, {"id": alt, "qty": it["qty"], "reason": f"alt_for:{it['id']}"})
    return kept, blocked, notes


def price(items: list[dict], term: int) -> dict:
    lines, monthly, setup, max_install = [], 0, 0, 0
    conn_days = max([products()[i["id"]].install_days for i in items if i["id"] in CONNECTIVITY] or [0])
    for it in items:
        prod = products()[it["id"]]
        line_term = max(term, prod.min_contract)
        up = unit_price(prod, line_term)
        days = prod.install_days if not prod.requires_one_of else max(prod.install_days, conn_days)
        lines.append({
            "id": prod.id, "name": prod.name, "category": prod.category, "description": prod.description,
            "unit": prod.unit, "qty": it["qty"], "unit_price": up, "monthly": up * it["qty"],
            "setup": prod.setup_fee * it["qty"], "contract_months": line_term,
            "install_days": days, "reason": it.get("reason", "addon"),
            "price_range": [prod.price_min, prod.price_max],
        })
        monthly += up * it["qty"]
        setup += prod.setup_fee * it["qty"]
        max_install = max(max_install, days)
    gst = round(monthly * 0.18)
    setup_gst = round(setup * 0.18)  # the one-time setup carries GST too, so the first bill is higher
    return {"lines": lines, "monthly": monthly, "gst": gst, "monthly_with_gst": monthly + gst,
            "setup": setup, "setup_gst": setup_gst, "first_bill": monthly + gst + setup + setup_gst,
            "term_months": term, "activation_days": max_install}


# Order in which items earn a place in the core bundle, from what activated customers of each
# segment actually bought (share of activated bundles containing the product, smb_leads.csv).
_PRIORITY = {
    "micro": ["P01", "P04", "P07", "P19", "P15", "P22", "P23", "P18", "P14"],
    "prof": ["P01", "P02", "P03", "P04", "P16", "P08", "P20", "P17", "P09", "P12", "P11"],
    "multi": ["P01", "P02", "P08", "P09", "P19", "P23", "P10", "P22", "P13", "P15"],
    "mfg": ["P05", "P06", "P03", "P02", "P08", "P16", "P20", "P21", "P11", "P23", "P24"],
}
_DEFAULT_BUDGET = {"micro": 2500, "prof": 8000}
_NEED_OF = {"P19": "payments", "P15": "whatsapp", "P14": "sms", "P23": "cctv", "P16": "email", "P20": "security",
            "P17": "backup", "P18": "website", "P22": "guest_wifi", "P09": "failover", "P12": "calls",
            "P13": "tollfree", "P11": "static_ip", "P24": "iot", "P25": "fleet", "P10": "central_mgmt", "P21": "firewall"}


def split_core(kept: list[dict], p: Profile) -> tuple[list[dict], list[dict]]:
    """Keep the bundle inside what this kind of business typically pays; the rest become add-ons
    the owner can switch on. Connectivity, mobile lines and anything the owner asked for stay in."""
    budget = p.budget or _DEFAULT_BUDGET.get(p.segment)
    if p.full:
        return kept, []
    if p.current_spend and p.segment == "micro":
        budget = max(budget, int(p.current_spend * 1.3))
    if not budget:
        return kept, []
    ordered = ranker.order(kept, p.segment, p.business_type, _PRIORITY[p.segment])
    core, extra, total = [], [], 0
    for it in ordered:
        prod = products()[it["id"]]
        cost = unit_price(prod, max(p.contract_months, prod.min_contract)) * it["qty"]
        must = it["id"] in CONNECTIVITY or it["id"] in ("P07", "P08") or _NEED_OF.get(it["id"]) in p.explicit_needs
        depends_ok = not prod.requires_one_of or any(c["id"] in prod.requires_one_of for c in core)
        if must or (total + cost <= budget and depends_ok):
            core.append(it)
            total += cost
        else:
            extra.append(it)
    return core, extra


def recommend(p: Profile) -> dict:
    p.segment = infer_segment(p)
    resolve_location(p)
    if not p.needs and not p.needs_confirmed:
        p.needs = default_needs(p)
    p.needs |= p.explicit_needs
    items = build_items(p)
    kept, blocked, notes = enforce_rules(items, p)
    kept, suggested = split_core(kept, p)
    quote = price(kept, p.contract_months)
    alt_term = 24 if p.contract_months < 24 else 12
    alt_monthly = price(kept, alt_term)["monthly"]
    return {
        "segment": p.segment, "segment_name": SEGMENTS[p.segment], "city_tier": p.city_tier,
        "quote": quote, "blocked": blocked, "notes": notes,
        "term_compare": {"term": alt_term, "monthly": alt_monthly},
        "savings_vs_current": (p.current_spend - quote["monthly"]) if p.current_spend else None,
        "needs": sorted(p.needs),
        "suggested": price(suggested, p.contract_months)["lines"] if suggested else [],
    }


def requote(p: Profile, selection: list[dict]) -> dict:
    """Re-price after the owner toggles add-ons or quantities; every change is re-validated."""
    p.segment = infer_segment(p)
    resolve_location(p)
    items = [{"id": s["id"], "qty": max(1, int(s.get("qty", 1))), "reason": s.get("reason") or "addon"}
             for s in selection if s["id"] in products()]
    kept, blocked, notes = enforce_rules(items, p)
    return {"quote": price(kept, p.contract_months), "blocked": blocked, "notes": notes}


def addon_options(p: Profile, chosen: set) -> list[dict]:
    """Every catalogue product not in the bundle, with whether this business can add it and why not."""
    out = []
    has_line = bool(chosen & set(CONNECTIVITY))
    for pid, prod in products().items():
        if pid in chosen or (has_line and pid in CONNECTIVITY[:4]):  # don't offer a second broadband plan
            continue
        why = check_eligibility(pid, p, chosen)
        out.append({"id": pid, "name": prod.name, "category": prod.category, "description": prod.description,
                    "unit": prod.unit, "unit_price": unit_price(prod, max(p.contract_months, prod.min_contract)),
                    "setup": prod.setup_fee, "eligible": why is None, "why": why,
                    "fit": p.segment in prod.segments})
    for o in out:
        o["score"] = round(ranker.score(p.segment, p.business_type, o["id"]) * ranker.often_with(p.segment, chosen, o["id"]), 3)
        o["take_up"] = ranker.take_up(p.segment, p.business_type, o["id"])
    out.sort(key=lambda o: (not o["eligible"], not o["fit"], -o["score"], o["category"]))
    return out
