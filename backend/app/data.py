"""Loads the hackathon data pack once and exposes typed lookups (catalogue, registries, cities)."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TODAY = pd.Timestamp("2026-07-15")  # "today" fixed by the data README for all date checks

SEGMENTS = {
    "micro": "Micro retail & services",
    "prof": "Professional offices",
    "multi": "Small multi-site businesses",
    "mfg": "Small manufacturers",
}
SEGMENT_KEY = {v: k for k, v in SEGMENTS.items()}


@dataclass(frozen=True)
class Product:
    id: str
    category: str
    name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup_fee: int
    min_contract: int
    tiers: frozenset
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: tuple
    install_days: int
    segments: frozenset


@lru_cache
def products() -> dict[str, Product]:
    df = pd.read_csv(DATA_DIR / "product_catalogue.csv", dtype=str).fillna("")
    out = {}
    for r in df.itertuples():
        out[r.product_id] = Product(
            id=r.product_id,
            category=r.category,
            name=r.product_name,
            description=r.description,
            unit=r.unit,
            price_min=int(r.price_min_inr_per_month),
            price_max=int(r.price_max_inr_per_month),
            setup_fee=int(r.one_time_setup_inr),
            min_contract=int(r.min_contract_months),
            tiers=frozenset(int(t) for t in r.available_city_tiers.split(";") if t),
            min_employees=int(r.min_employees),
            min_sites=int(r.min_sites),
            requires_gstin=r.requires_gstin == "Y",
            requires_one_of=tuple(p for p in r.requires_one_of.split("|") if p),
            install_days=int(r.typical_install_days),
            segments=frozenset(s for s in r.target_segments.split(";") if s),
        )
    return out


@lru_cache
def gstin_registry() -> dict[str, dict]:
    df = pd.read_csv(DATA_DIR / "mock_gstin_registry.csv", dtype=str).fillna("")
    return {r["gstin"]: r for r in df.to_dict("records")}


@lru_cache
def udyam_registry() -> dict[str, dict]:
    df = pd.read_csv(DATA_DIR / "mock_udyam_registry.csv", dtype=str).fillna("")
    return {r["udyam_number"]: r for r in df.to_dict("records")}


@lru_cache
def leads() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "smb_leads.csv")


@lru_cache
def city_tiers() -> dict[str, int]:
    d = leads()
    return {c: int(t) for c, t in d.groupby("city").city_tier.first().items()}


@lru_cache
def city_states() -> dict[str, str]:
    d = leads()
    return {c: s for c, s in d.groupby("city").state.first().items()}


@lru_cache
def business_types() -> dict[str, str]:
    """business_type -> segment key, learned from the leads file."""
    d = leads()
    return {bt: SEGMENT_KEY[seg] for bt, seg in d.groupby("business_type").segment.agg(lambda s: s.mode()[0]).items()}


@lru_cache
def udyam_by_name() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in udyam_registry().values():
        out.setdefault(r["enterprise_name"].lower(), []).append(r)
    return out


@lru_cache
def gstin_by_trade_name() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in gstin_registry().values():
        out.setdefault(r["trade_name"].lower(), []).append(r)
    return out
