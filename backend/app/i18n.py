"""Advisor copy in every supported language, loaded from locales/<code>.json.

English is the source. Other languages are produced with scripts/translate_locales.py and reviewed; any missing
string falls back to English, so a half-translated language never breaks the chat. Without an LLM key the advisor
speaks only from these strings, so every flow works offline.
"""
import json
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).with_name("locales")
# Order shown in the app: by share of leads in smb_leads.csv (Hindi 43%, English 23%, Marathi 10%, ...).
ORDER = ["en", "hi", "mr", "kn", "gu", "te", "ta", "bn", "pa", "ml"]


@lru_cache
def _load() -> dict:
    out = {}
    for f in sorted(_DIR.glob("*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


LANGS = {code: _load()[code]["name"] for code in ORDER if code in _load()}
T = {code: d.get("strings", {}) for code, d in _load().items()}
NEED_LABELS = {code: d.get("needs", {}) for code, d in _load().items()}


def t(lang: str, key: str, **kw) -> str:
    table = T.get(lang) or T["en"]
    template = table.get(key) or T["en"].get(key, key)
    try:
        return template.format(**kw)
    except (KeyError, IndexError):
        return T["en"].get(key, key).format(**kw) if key in T["en"] else template


def need_label(lang: str, need: str) -> str:
    return (NEED_LABELS.get(lang) or {}).get(need) or NEED_LABELS["en"].get(need, need)
