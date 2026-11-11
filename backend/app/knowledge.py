"""Knowledge base the advisor answers from, with retrieval and source ids.

Sources: the markdown files in knowledge/ (KYC, privacy, pricing, installation, eligibility), split by "##" section,
plus one sheet per catalogue product built from product_catalogue.csv, so product facts can never drift from the
data the rules engine uses. Each chunk has a stable id ("kyc#documents-needed", "product#P23") that the advisor
shows as the source of an answer.

Retrieval (find) is hybrid and needs no model, so it works when the AI is down and costs nothing per question:
  1. the question is widened with English words for what the rules understood in any of the 10 languages: the
     services it names (lexicon.py) and the topic it is about (documents, days, price, deleting data ...);
  2. two rankers score every chunk: BM25 on stemmed words, and character 3-grams, which survive typos ("camra",
     "instalation") and inflections;
  3. the two rankings are merged by reciprocal rank fusion, with a small lift for the sections the app itself cites
     for that kind of question.
Each chunk is indexed with more than its text: knowledge sections carry an "Asked as:" line of the ways owners put
the question, and product sheets carry the problems that product solves in the owner's words ("someone walked out
without paying" finds CCTV). Those extra words are for finding only; they are never shown and never sent to the AI.
search() is the plain BM25 it replaces, kept as the baseline that tests/eval measures find() against.
"""
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from . import lexicon
from .data import products

_DIR = Path(__file__).with_name("knowledge")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an and are as at be by can do does for from has have how i if in is it its my of on or our the their "
            "this to was we what when where which who why will with you your".split())


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# The problem each product solves, in the words an owner uses. Indexed with the product sheet, never shown.
_OWNER_WORDS = {
    "P01": "internet for a small shop, wifi, broadband, basic speed",
    "P02": "faster internet for an office with many devices, wifi, broadband",
    "P03": "fastest internet, gigabit, heavy uploads, faster than 300 Mbps",
    "P04": "wireless internet, no cable, no fibre in the area, quick to set up, plug and play",
    "P05": "dedicated line, guaranteed speed, never slows down, uptime for a factory or large office",
    "P06": "dedicated line, guaranteed speed, never slows down, uptime for a large factory",
    "P07": "SIM cards, mobile plan for staff, calls and data on phones",
    "P08": "SIM cards, mobile plan for staff who travel, calls and data on phones",
    "P09": "internet goes down, the net keeps dropping, standby line, stay online when the main line fails, automatic switch, outage",
    "P10": "manage all branches from one place, see every outlet's internet on one screen, link the sites together, head office control",
    "P11": "fixed address for remote access, view cameras from outside, host a server",
    "P12": "office phone lines, many customers calling at once, busy tone, missed calls, IVR menu, call recording, landline, ring",
    "P13": "a free number for customers to call, 1800 number, customer care line",
    "P14": "send text messages to all customers, bulk SMS, festival offers, reminders, alerts, promotions to phones",
    "P15": "chat with customers on WhatsApp, share a catalogue or product list, take orders, send offers and reminders, verified tick, broadcast",
    "P16": "company email on our own name, professional mail instead of gmail, office documents, video meetings, staff mailboxes",
    "P17": "losing files, a computer died or crashed, keep data safe, a copy of accounts and records, restore",
    "P18": "get found online, own site, a web page for my shop, domain name",
    "P19": "billing counter, card machine, swipe, UPI, QR, accept payments, invoices, stock, inventory, GST bills",
    "P20": "virus, ransomware, hacked, protect laptops and computers",
    "P21": "block attacks, protect the office network, control which sites staff open, intrusion",
    "P22": "customers ask for Wi-Fi, the password is shared with everyone, separate Wi-Fi for guests, keep visitors off the billing network",
    "P23": "theft, stolen, shoplifting, someone walked out without paying, proof, recording, watch the shop from my phone, security camera",
    "P24": "know when a machine stops, factory floor monitoring, downtime of machines, energy use, sensors",
    "P25": "where are my vehicles, delivery vans, trucks, drivers, live location",
}


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
            body = [l.strip() for l in lines[1:] if l.strip()]
            asks = " ".join(l[len("Asked as:"):] for l in body if l.startswith("Asked as:"))
            out.append({"id": f"{f.stem}#{_slug(title)}", "title": f"{doc_title}: {title}", "asks": asks,
                        "text": " ".join(l for l in body if not l.startswith("Asked as:"))})
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
        out.append({"id": f"product#{p.id}", "title": f"Product sheet: {p.name}", "asks": _OWNER_WORDS.get(p.id, ""),
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


def _stem(w: str) -> str:
    for suf in ("ies", "ing", "es", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[:-len(suf)] + ("y" if suf == "ies" else "")
    return w


def _grams(text: str) -> list[str]:
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2]
    return [f" {w} "[i:i + 3] for w in words for i in range(len(w))]


@lru_cache
def _index2():
    """Stemmed words (title counted twice) and character 3-grams for each chunk, over text plus the finding-only words."""
    full = [f"{c['title']} {c['title']} {c['text']} {c.get('asks', '')}" for c in chunks()]
    words = [[_stem(w) for w in _tokens(t)] for t in full]
    grams = [Counter(_grams(t)) for t in full]
    df = Counter(t for d in words for t in set(d))
    gdf = Counter(g for d in grams for g in d)
    return words, df, sum(len(d) for d in words) / max(1, len(words)), grams, gdf


# What a question is about, in Hinglish and the scripts -> the English words the documents use (the rules' intents
# cover English and part of Hindi only).
_TOPIC_WORDS = {"documents": "documents needed papers kyc", "days": "how long days installation time", "price": "price cost month",
                "erase": "erase delete data owner rights", "safe": "privacy data consent protected", "photos": "photos kept deleted documents", "visit": "technician slot visit",
                "term": "12 24 months contract cheaper", "no_gst": "without gstin products need", "status": "order status tracker",
                "help": "ticket complaint help support"}


def _ranks(scores: list[float]) -> dict[int, int]:
    order = sorted((i for i, x in enumerate(scores) if x > 0), key=lambda i: -scores[i])
    return {i: r for r, i in enumerate(order, 1)}


def find(text: str, intent: str | None = None, needs: list[str] | None = None, k: int = 4) -> list[dict]:
    """The k chunks that best answer the question, in any of the 10 languages. Returns [] when nothing matches."""
    words, df, avg, grams, gdf = _index2()
    plain = lexicon.plain(text).lower()
    topics = [t for t, pat in lexicon.TOPICS.items() if pat.search(plain)]
    query = " ".join([text, "" if needs else _INTENT_WORDS.get(intent or "", "")] + [_NEED_WORDS.get(n, n) for n in needs or []]
                     + [_TOPIC_WORDS[t] for t in topics])
    q = [_stem(w) for w in _tokens(query)]
    n, k1, b = len(words), 1.4, 0.75
    bm = []
    for d in words:
        tf = Counter(d)
        bm.append(sum(math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
                      for t in q if t in tf))
    qg = Counter(_grams(query))
    idf = {g: math.log(1 + n / gdf[g]) for g in qg if g in gdf}
    qn = math.sqrt(sum((c * idf.get(g, 0)) ** 2 for g, c in qg.items())) or 1.0
    cg = []
    for d in grams:
        dot = sum(c * idf[g] * d[g] * idf[g] for g, c in qg.items() if g in idf and g in d)
        dn = math.sqrt(sum((c * math.log(1 + n / gdf[g])) ** 2 for g, c in d.items())) or 1.0
        cg.append(dot / (qn * dn) if dot / (qn * dn) >= 0.08 else 0.0)  # a few shared letters are not a match
    r1, r2 = _ranks(bm), _ranks(cg)
    cited = set() if needs else set(RULE_SOURCES.get(intent or "", []))  # a question about a named service wants its sheet
    fused = {i: (1.0 / (60 + r1[i]) if i in r1 else 0.0) + (0.6 / (60 + r2[i]) if i in r2 else 0.0) for i in set(r1) | set(r2)}
    for i in fused:
        if chunks()[i]["id"] in cited:
            fused[i] += 0.5 / 61
    best = sorted(fused, key=lambda i: -fused[i])[:k]
    return [chunks()[i] for i in best]


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
