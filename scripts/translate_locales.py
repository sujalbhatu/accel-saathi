"""Fill in every language from the English source strings with the configured LLM.

    python scripts/translate_locales.py            # translate only what is missing, in all languages
    python scripts/translate_locales.py --check    # show coverage, no API calls
    python scripts/translate_locales.py --only kn gu

Only missing keys are translated, so strings a person has reviewed are never overwritten. Every answer is checked:
the same keys, the same {placeholders}, the same list lengths, nothing empty. Anything that fails stays in English
(the app falls back per string) and is listed at the end. Uses LLM_API_KEY / LLM_BASE_URL / LLM_MODEL from .env.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
BACKEND = ROOT / "backend" / "app" / "locales"
FRONTEND = ROOT / "frontend" / "src" / "locales"

# code: (name in its own script, short label, speech-recognition locale, English name for the prompt)
LANGS = {
    "hi": ("हिन्दी", "हि", "hi-IN", "Hindi"), "mr": ("मराठी", "म", "mr-IN", "Marathi"),
    "kn": ("ಕನ್ನಡ", "ಕ", "kn-IN", "Kannada"), "gu": ("ગુજરાતી", "ગુ", "gu-IN", "Gujarati"),
    "te": ("తెలుగు", "తె", "te-IN", "Telugu"), "ta": ("தமிழ்", "த", "ta-IN", "Tamil"),
    "bn": ("বাংলা", "বা", "bn-IN", "Bengali"), "pa": ("ਪੰਜਾਬੀ", "ਪੰ", "pa-IN", "Punjabi (Gurmukhi script)"),
    "ml": ("മലയാളം", "മ", "ml-IN", "Malayalam"),
}

PROMPT = """You translate the text of a mobile app that helps Indian small business owners (shopkeepers, clinics,
small offices, small factories) buy internet, mobile and business services. Translate every value of the JSON
object into {language}.
- Use simple, everyday, spoken {language} that a shop owner understands, not formal or literary words.
- Keep these in English/Latin script exactly: Accel, Accel Business, GST, GSTIN, Udyam, UPI, WhatsApp, CCTV, Wi-Fi,
  KYC, DigiLocker, Aadhaar, OTP, PAN, IVR, SMS, IP, POS, SD-WAN, LLP, e-Sign, AI, Chrome, Edge, product names.
- Keep every {{placeholder}} in curly braces exactly as written, untranslated. Keep ₹, numbers and emoji.
- If a value is a list, return a list of the same length.
- Keep the same tone and length; no explanations.
Return ONLY a JSON object with exactly the same keys."""

_last_call = 0.0


def llm_json(payload: dict, language: str) -> dict | None:
    global _last_call
    base = os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").rstrip("/")
    model = os.getenv("LLM_MODEL", "gemini-3.5-flash")
    body = {"model": model, "temperature": 0.1, "max_tokens": 8000, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": PROMPT.format(language=language)},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]}
    gap = float(os.getenv("TRANSLATE_GAP_SECONDS", "7"))  # free tiers allow only a few requests a minute
    for attempt in range(6):
        wait = _last_call + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        try:
            r = httpx.post(f"{base}/chat/completions", json=body, timeout=90,
                           headers={"Authorization": f"Bearer {os.environ['LLM_API_KEY']}"})
        except httpx.HTTPError as e:
            print(f"    network error {type(e).__name__}, retrying")
            time.sleep(10)
            continue
        if r.status_code in (429, 500, 502, 503):
            print(f"    {r.status_code}, waiting 30s")
            time.sleep(30)
            continue
        if r.status_code >= 400:
            print(f"    HTTP {r.status_code}: {r.text[:200]}")
            return None
        text = r.json()["choices"][0]["message"]["content"] or ""
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print("    answer was not JSON, retrying")
    return None


def _placeholders(v) -> set:
    if isinstance(v, list):
        return set().union(*(_placeholders(x) for x in v)) if v else set()
    return set(re.findall(r"\{\w+\}", v))


def valid(src, out) -> bool:
    if isinstance(src, list):
        return isinstance(out, list) and len(out) == len(src) and all(isinstance(x, str) and x.strip() for x in out)
    return isinstance(out, str) and bool(out.strip()) and _placeholders(src) == _placeholders(out)


def translate(missing: dict, language: str, failed: list, where: str) -> dict:
    done: dict = {}
    keys = list(missing)
    for i in range(0, len(keys), 30):
        batch = {k: missing[k] for k in keys[i:i + 30]}
        out = llm_json(batch, language) or {}
        for k, src in batch.items():
            if valid(src, out.get(k)):
                done[k] = out[k]
            else:
                failed.append(f"{where}:{k}")
        print(f"    {where}: {len(done)}/{len(keys)}")
    return done


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    en_b, en_f = load(BACKEND / "en.json"), load(FRONTEND / "en.json")
    if not args.check and not os.getenv("LLM_API_KEY"):
        sys.exit("Set LLM_API_KEY in .env first.")
    failed: list[str] = []
    for code, (name, label, speech, english) in LANGS.items():
        if args.only and code not in args.only:
            continue
        b, f = load(BACKEND / f"{code}.json"), load(FRONTEND / f"{code}.json")
        b.setdefault("strings", {}), b.setdefault("needs", {}), f.setdefault("ui", {})
        b["name"] = name
        f.update({"name": name, "label": label, "speech": speech})
        miss = {
            "strings": {k: v for k, v in en_b["strings"].items() if k not in b["strings"]},
            "needs": {k: v for k, v in en_b["needs"].items() if k not in b["needs"]},
            "ui": {k: v for k, v in en_f["ui"].items() if k not in f["ui"]},
        }
        total = sum(len(v) for v in miss.values())
        print(f"{code} {english}: {total} strings missing")
        if args.check or not total:
            continue
        b["strings"].update(translate(miss["strings"], english, failed, f"{code}/advisor"))
        b["needs"].update(translate(miss["needs"], english, failed, f"{code}/needs"))
        f["ui"].update(translate(miss["ui"], english, failed, f"{code}/screens"))
        save(BACKEND / f"{code}.json", b)
        save(FRONTEND / f"{code}.json", f)
    if failed:
        print(f"\n{len(failed)} strings stayed in English (the app falls back to English for these):")
        print(", ".join(failed))


if __name__ == "__main__":
    main()
