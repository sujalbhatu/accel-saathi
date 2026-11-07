"""Encryption at source and tokenisation, as a regulated telco needs.

At rest: every stored document (sessions, KYC records, orders, consents) is sealed with AES-256-GCM before it reaches
the database, so a copied database file shows nothing readable. Records keyed by a phone number (the WhatsApp links,
a partner's 30-day protection) are keyed by a keyed hash (HMAC-SHA256) of the number instead, so the number never
appears even as a key. The key comes from DATA_KEY (32 bytes, base64) — in production from a key vault / HSM; if it
is not set, a random key is created once next to the database with owner-only permissions.

In transit to outside services: before any text goes to an AI model over the public internet, phone numbers, GSTIN,
PAN, Aadhaar, Udyam numbers, e-mail addresses and the owner's own business and contact names are swapped for tokens
such as [PHONE_1]. The model answers with the tokens and they are swapped back here, so the model never sees them.
"""
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

log = logging.getLogger("privacy")
PREFIX = "enc:v1:"


@lru_cache
def _key() -> bytes:
    env = os.getenv("DATA_KEY", "").strip()
    if env:
        key = base64.urlsafe_b64decode(env + "=" * (-len(env) % 4))
        if len(key) != 32:
            raise ValueError("DATA_KEY must be 32 bytes, base64-encoded")
        return key
    from .store import DB_PATH  # the key file lives next to the database it protects
    path = Path(DB_PATH).parent / "data.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
        log.warning("DATA_KEY not set: created %s (use a key vault in production)", path)
    return base64.urlsafe_b64decode(path.read_text().strip())


def seal(text: str) -> str:
    nonce = secrets.token_bytes(12)
    ct = AESGCM(_key()).encrypt(nonce, text.encode(), b"udyam-doc")
    return PREFIX + base64.b64encode(nonce + ct).decode()


def unseal(stored: str) -> str:
    if not stored.startswith(PREFIX):  # written before encryption was switched on
        return stored
    raw = base64.b64decode(stored[len(PREFIX):])
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], b"udyam-doc").decode()


def seal_json(body: dict) -> str:
    return seal(json.dumps(body, ensure_ascii=False))


def unseal_json(stored: str) -> dict:
    return json.loads(unseal(stored))


def token(kind: str, value: str) -> str:
    """A stable, non-reversible stand-in for a personal key (same input, same token; useless without the key)."""
    return "tok_" + hmac.new(_key(), f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()[:32]


# ---------- tokenising text sent to outside AI models ----------

_PATTERNS = [
    ("GSTIN", re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]\b", re.I)),
    ("UDYAM", re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", re.I)),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("AADHAAR", re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")),
]


def tokenize(texts: list[str], names: list[str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Swap personal data in all texts for tokens, the same token for the same value across texts."""
    mapping: dict[str, str] = {}
    seen: dict[tuple[str, str], str] = {}
    counts: dict[str, int] = {}

    def sub(kind: str, value: str) -> str:
        key = (kind, value.lower())
        if key not in seen:
            counts[kind] = counts.get(kind, 0) + 1
            tok = f"[{kind}_{counts[kind]}]"
            seen[key], mapping[tok] = tok, value
        return seen[key]

    out = []
    for text in texts:
        for kind, rx in _PATTERNS:
            text = rx.sub(lambda m, k=kind: sub(k, m.group(0)), text)
        for name in sorted({n.strip() for n in names or [] if n and len(n.strip()) >= 4}, key=len, reverse=True):
            text = re.sub(re.escape(name), lambda m: sub("NAME", m.group(0)), text, flags=re.I)
        out.append(text)
    return out, mapping


def detokenize(text: str, mapping: dict[str, str]) -> str:
    for tok, value in mapping.items():
        text = text.replace(tok, value)
    return text
