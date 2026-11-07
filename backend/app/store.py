"""Tiny SQLite document store for sessions, orders, consents and the audit log.

Production would swap this for Postgres; the interface (put/get/list/audit) stays the same.
Only masked identifiers are ever written to the audit log. Every document is encrypted before it is written
(AES-256-GCM, see privacy.py), and records keyed by a phone number are keyed by a keyed hash of it instead.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import privacy

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent.parent / "runtime" / "app.db"))
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
# kinds whose id is a phone number: stored under a token, never the number itself
PERSONAL_IDS = {"wa_link", "wa_orders", "partner_touch"}


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, body TEXT, updated TEXT, PRIMARY KEY(kind, id))")
        _conn.execute("CREATE TABLE IF NOT EXISTS audit (ts TEXT, actor TEXT, action TEXT, ref TEXT, detail TEXT)")
        _conn.commit()
    return _conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _key(kind: str, id_: str) -> str:
    return privacy.token(kind, id_) if kind in PERSONAL_IDS else id_


def put(kind: str, id_: str, body: dict) -> dict:
    with _lock:
        _db().execute("REPLACE INTO docs VALUES (?,?,?,?)", (kind, _key(kind, id_), privacy.seal_json(body), now()))
        if kind in PERSONAL_IDS:  # drop any copy saved under the plain number before tokens were used
            _db().execute("DELETE FROM docs WHERE kind=? AND id=?", (kind, id_))
        _db().commit()
    return body


def get(kind: str, id_: str) -> dict | None:
    with _lock:
        row = _db().execute("SELECT body FROM docs WHERE kind=? AND id=?", (kind, _key(kind, id_))).fetchone()
        if not row and kind in PERSONAL_IDS:  # saved under the plain number by an older version: move it now
            row = _db().execute("SELECT body FROM docs WHERE kind=? AND id=?", (kind, id_)).fetchone()
            if row:
                body = privacy.unseal_json(row[0])
                _db().execute("REPLACE INTO docs VALUES (?,?,?,?)", (kind, _key(kind, id_), privacy.seal_json(body), now()))
                _db().execute("DELETE FROM docs WHERE kind=? AND id=?", (kind, id_))
                _db().commit()
                return body
    return privacy.unseal_json(row[0]) if row else None


def list_(kind: str, limit: int = 200) -> list[dict]:
    with _lock:
        rows = _db().execute("SELECT body FROM docs WHERE kind=? ORDER BY updated DESC LIMIT ?", (kind, limit)).fetchall()
    return [privacy.unseal_json(r[0]) for r in rows]


def delete(kind: str, id_: str) -> None:
    with _lock:
        _db().execute("DELETE FROM docs WHERE kind=? AND id IN (?,?)", (kind, _key(kind, id_), id_))
        _db().commit()


def encrypt_existing() -> int:
    """Seal every document still stored in plain text (run once after upgrading). Returns how many were sealed."""
    n = 0
    with _lock:
        for kind, id_, body in _db().execute("SELECT kind, id, body FROM docs").fetchall():
            if not body.startswith(privacy.PREFIX):
                _db().execute("UPDATE docs SET body=? WHERE kind=? AND id=?", (privacy.seal(body), kind, id_))
                n += 1
            if kind in PERSONAL_IDS and not id_.startswith("tok_"):
                _db().execute("UPDATE OR REPLACE docs SET id=? WHERE kind=? AND id=?", (privacy.token(kind, id_), kind, id_))
                n += 1
        _db().commit()
    return n


def audit(actor: str, action: str, ref: str, detail: str = "") -> None:
    with _lock:
        _db().execute("INSERT INTO audit VALUES (?,?,?,?,?)", (now(), actor, action, ref, detail))
        _db().commit()


def audit_log(ref: str | None = None, limit: int = 100) -> list[dict]:
    q, args = "SELECT ts, actor, action, ref, detail FROM audit", []
    if ref:
        q, args = q + " WHERE ref=?", [ref]
    with _lock:
        rows = _db().execute(q + " ORDER BY ts DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(zip(("ts", "actor", "action", "ref", "detail"), r)) for r in rows]
