"""Knowledge base the advisor answers from, with retrieval and source ids.

Sources: the markdown files in knowledge/ (KYC, privacy, pricing, installation, eligibility), split by "##" section,
plus one sheet per catalogue product built from product_catalogue.csv, so product facts can never drift from the
data the rules engine uses. Each chunk has a stable id ("kyc#documents-needed", "product#P23") that the advisor
shows as the source of an answer.

Retrieval is BM25 over the chunks, with the question expanded by what the rules understood (needs, intent), so a
question in Hindi or Tamil about "कैमरा" still finds the CCTV sheet. The knowledge base is small today, so the
advisor sends the top few chunks; the same interface scales to thousands of documents.
"""
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .data import products

_DIR = Path(__file__).with_name("knowledge")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an and are as at be by can do does for from has have how i if in is it its my of on or our the their "
            "this to was we what when where which who why will with you your".split())


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@lru_cache
def chunks() -> list[dict]:
    out = []
    for f in sorted(_DIR.glob("*.md")):
        doc_title = ""
        for block in re.split(r"\n(?=## )", f.read_text(encoding="utf-8")):
            lines = block.strip().splitlines()
            if lines and lines[0].startswith("# "):
                doc_title = lines[0][2:].strip()
                lines = lines[1:]
            if not lines or not lines[0].startswith("## "):
                continue
            title = lines[0][3:].strip()
            out.append({"id": f"{f.stem}#{_slug(title)}", "title": f"{doc_title}: {title}",
                        "text": " ".join(l.strip() for l in lines[1:] if l.strip())})
    for p in products().values():
        rules = []
        if p.tiers == frozenset({1}):
            rules.append("tier-1 cities only")
        if p.min_employees > 1:
            rules.append(f"needs {p.min_employees} or more staff")
        if p.min_sites > 1:
            rules.append(f"needs {p.min_sites} or more sites")
        if p.requires_gstin:
            rules.append("needs an active GSTIN")
        if p.requires_one_of:
            rules.append("needs an internet line in the same bundle")
        out.append({"id": f"product#{p.id}", "title": f"Product sheet: {p.name}",
                    "text": f"{p.name} ({p.category}): {p.description}. Price Rs {p.price_min} to Rs {p.price_max} a month "
                            f"{p.unit}; setup fee Rs {p.setup_fee}; minimum contract {p.min_contract} months; typical "
                            f"installation {p.install_days} days."
                            + (f" Eligibility: {', '.join(rules)}." if rules else " Available to every business.")})
    return out


@lru_cache
def _index():
    docs = [_tokens(c["title"] + " " + c["text"]) for c in chunks()]
    df = Counter(t for d in docs for t in set(d))
    avg = sum(len(d) for d in docs) / max(1, len(docs))
    return docs, df, avg


def search(query: str, k: int = 4) -> list[dict]:
    """BM25 top-k chunks for the query. Returns [] when nothing matches."""
    docs, df, avg = _index()
    q = _tokens(query)
    if not q:
        return []
    n, k1, b = len(docs), 1.4, 0.75
    scored = []
    for i, d in enumerate(docs):
        tf = Counter(d)
        score = 0.0
        for t in q:
            if t in tf:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        if score > 0:
            scored.append((score, i))
    scored.sort(reverse=True)
    return [chunks()[i] for _, i in scored[:k]]


_INTENT_WORDS = {"q_docs": "kyc documents needed digilocker", "q_time": "installation how long live days slot",
                 "q_privacy": "privacy consent data photos deleted", "q_price": "price gst setup months",
                 "q_gst": "gstin products need active gstin without"}
_NEED_WORDS = {"payments": "pos billing upi", "whatsapp": "whatsapp business api", "sms": "sms", "cctv": "cctv camera",
               "email": "email office", "security": "endpoint security antivirus", "backup": "cloud backup",
               "website": "website domain", "guest_wifi": "wi-fi guest network", "failover": "backup failover",
               "calls": "telephony sip ivr", "tollfree": "toll-free", "static_ip": "static ip", "iot": "machine iot",
               "fleet": "fleet tracker", "central_mgmt": "sd-wan", "firewall": "firewall"}


def expand(text: str, intent: str | None, needs: list[str]) -> str:
    """The question plus English words for what the rules understood, so any language can retrieve."""
    return " ".join([text, _INTENT_WORDS.get(intent or "", "")] + [_NEED_WORDS.get(n, n) for n in needs])


def by_id(cid: str) -> dict | None:
    return next((c for c in chunks() if c["id"] == cid), None)


# Sources for the answers the rules give without an LLM.
RULE_SOURCES = {"q_docs": ["kyc#documents-needed", "kyc#fastest-way-digilocker-and-aadhaar-otp"],
                "q_time": ["install#how-long-it-takes"], "q_privacy": ["privacy#purpose-and-minimisation"],
                "q_price": ["buying#how-prices-work"], "q_gst": ["eligibility#gstin"]}
