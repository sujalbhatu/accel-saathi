"""Plain-language item cards: what each service is, what it does for this owner, what happens without it, what it
costs a day, and how many similar businesses on Accel have it.

The words come from the locale files (written once, reviewed, in all ten languages), and the take-up numbers from
the activated customers in smb_leads.csv, so a card costs no AI call and reads the same in the app and on WhatsApp.
"""
from collections import Counter
from functools import lru_cache

from . import ranker
from .data import SEGMENT_KEY, leads, products
from .i18n import t
from .recommender import _NEED_OF, CONNECTIVITY, unit_price


@lru_cache
def take_up() -> dict[str, dict[str, int]]:
    """For each segment, in how many of 10 activated customers' bundles each product appears (rounded)."""
    df = leads()
    act = df[df["outcome"] == "Activated"]
    out: dict[str, dict[str, int]] = {}
    for seg_name, g in act.groupby("segment"):
        seg = SEGMENT_KEY.get(seg_name)
        if not seg or not len(g):
            continue
        c = Counter(pid for b in g["bundle_products"].dropna() for pid in {i.split("x")[0] for i in b.split(";")})
        out[seg] = {pid: round(n * 10 / len(g)) for pid, n in c.items()}
    return out


def per_day(monthly: int) -> int:
    return max(1, round(monthly / 30))


def unit_text(lang: str, pid: str) -> str:
    unit = products()[pid].unit.replace("per ", "").strip().lower()
    return t(lang, f"unit_{unit}")


def plain(lang: str, pid: str) -> str:
    return t(lang, f"plain_{pid}")


def price_for(pid: str, term: int) -> int:
    prod = products()[pid]
    return unit_price(prod, max(term, prod.min_contract))


def enrich(line: dict, lang: str, segment: str, asked: set, ticked: set | None = None, business_type: str = "") -> dict:
    """Add the card fields to a priced quote line (in place) and return it. "why" is about this owner: they asked
    for it, kept it ticked, it is sized for their team, or it stands in for something they can't have yet."""
    pid = line["id"]
    line["plain"] = plain(lang, pid)
    line["does"] = t(lang, f"does_{pid}")
    line["skip"] = t(lang, f"skip_{pid}")
    line["per_day"] = per_day(line["monthly"])
    line["take_up"] = ranker.take_up(segment, business_type, pid)
    need = _NEED_OF.get(pid)
    line["asked"] = bool(need and need in asked)
    reason = line.get("reason", "")
    if reason.startswith("alt_for:") or reason == "dependency_added":
        line["why"] = line.get("reason_text") or ""
    elif line["asked"]:
        line["why"] = t(lang, "why_asked")
    elif reason == "addon":
        line["why"] = t(lang, "r_addon")
    elif need and need in (ticked or set()):
        line["why"] = t(lang, "why_ticked")
    elif pid in CONNECTIVITY or pid in ("P07", "P08"):
        line["why"] = line.get("reason_text") or ""
    else:
        line["why"] = t(lang, "why_typical")
    return line


def info(lang: str, pid: str, term: int, in_bundle: bool) -> str:
    """One answer to "what is X?" for any catalogue product."""
    if in_bundle:
        return t(lang, "item_info_have", plain=plain(lang, pid), does=t(lang, f"does_{pid}"))
    return t(lang, "item_info", plain=plain(lang, pid), does=t(lang, f"does_{pid}"), price=f"{price_for(pid, term):,}",
             unit=unit_text(lang, pid))
