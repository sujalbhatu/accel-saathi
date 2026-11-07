"""Encryption at source and tokenisation: nothing personal is readable in the database file, phone numbers are never
used as keys, and an outside AI model only ever sees tokens.

    python -m tests.run_privacy_checks
"""
import os
import sqlite3
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY", "WA_ACCESS_TOKEN", "WA_PHONE_NUMBER_ID", "WA_APP_SECRET", "DATA_KEY"):
    os.environ[key] = ""
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "privacy.db")

from app import llm, privacy, ranker, store  # noqa: E402

RESULTS = []
PHONE, GSTIN, NAME = "9876512345", "08EAHXC5550F1ZF", "Coral Medicals"


def check(ok, label, detail=""):
    RESULTS.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"   {detail}"))


def raw_db() -> str:
    con = sqlite3.connect(store.DB_PATH)
    rows = con.execute("SELECT kind, id, body FROM docs").fetchall()
    con.close()
    return "\n".join(" ".join(r) for r in rows)


def main():
    print("Encryption at rest:")
    store.put("session", "ses_1", {"profile": {"business_name": NAME, "gstin": GSTIN}, "phone": PHONE})
    store.put("wa_link", PHONE, {"session_id": "ses_1"})
    dump = raw_db()
    check(PHONE not in dump and GSTIN not in dump and NAME not in dump, "the database file has no name, GSTIN or phone number")
    check(store.get("session", "ses_1")["profile"]["gstin"] == GSTIN, "the app still reads its own records")
    check(store.get("wa_link", PHONE) == {"session_id": "ses_1"}, "a record keyed by a phone number is found by that number")
    check(store.list_("session")[0]["phone"] == PHONE, "listing decrypts too")
    key_file = os.path.join(os.path.dirname(store.DB_PATH), "data.key")
    if os.name == "posix":  # Windows has no owner-only mode bits to check
        check(oct(os.stat(key_file).st_mode)[-3:] == "600", "the generated key file is readable by the owner only")
    else:
        check(os.path.exists(key_file), "the generated key file exists next to the database")

    print("\nUpgrade from plain records:")
    con = sqlite3.connect(store.DB_PATH)
    con.execute("INSERT INTO docs VALUES ('wa_link', '9876599999', '{\"session_id\": \"ses_old\"}', '2026-10-31')")
    con.execute("INSERT INTO docs VALUES ('order', 'AB1', '{\"phone\": \"9876588888\"}', '2026-10-31')")
    con.commit()
    con.close()
    check(store.get("wa_link", "9876599999") == {"session_id": "ses_old"}, "an old plain record is still found")
    n = store.encrypt_existing()
    dump = raw_db()
    check(n >= 1 and "9876599999" not in dump and "9876588888" not in dump, "old records are sealed and re-keyed on start-up", n)
    check(store.get("order", "AB1") == {"phone": "9876588888"}, "and still read back")
    store.delete("wa_link", PHONE)
    check(store.get("wa_link", PHONE) is None, "delete works on a tokenised key")

    print("\nTampering:")
    con = sqlite3.connect(store.DB_PATH)
    body = con.execute("SELECT body FROM docs WHERE kind='order' AND id='AB1'").fetchone()[0]
    con.execute("UPDATE docs SET body=? WHERE kind='order' AND id='AB1'", (body[:-6] + ("AAAA==" if not body.endswith("AAAA==") else "BBBB=="),))
    con.commit()
    con.close()
    try:
        store.get("order", "AB1")
        check(False, "an edited record is refused")
    except Exception:
        check(True, "an edited record is refused (GCM authentication)")

    print("\nTokenised before an outside AI model:")
    sent = {}

    class Resp:
        status_code, headers = 200, {}

        def json(self):
            return {"choices": [{"message": {"content": "Sure [NAME_1], we'll text [PHONE_1] about [GSTIN_1]."}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    llm._post = lambda r, body, timeout: sent.update(body) or Resp()
    llm._route = lambda lang=None: [{"provider": "test", "model": "m", "url": "x", "paid": False, "key": "k"}]
    llm._ready = lambda r: True
    llm.session_allowed = lambda s: True
    session = {"profile": {"business_name": NAME}}
    out = llm.chat([{"role": "user", "content": f"I am {NAME}, call {PHONE}, GSTIN {GSTIN}, PAN ABCDE1234F"}], session=session)
    prompt = sent["messages"][0]["content"]
    check(PHONE not in prompt and GSTIN not in prompt and NAME not in prompt and "ABCDE1234F" not in prompt,
          "the model receives tokens, not the name, phone, GSTIN or PAN", prompt)
    check(out == f"Sure {NAME}, we'll text {PHONE} about {GSTIN}.", "and the owner gets her real details back", out)
    t, m = privacy.tokenize(["100 Mbps for ₹699, 25 services, 4 people, 2026-11-03"])
    check(t[0] == "100 Mbps for ₹699, 25 services, 4 people, 2026-11-03" and not m, "prices, speeds and dates are left alone", t)

    print("\nRanking learned from the data:")
    sweets, shops = ranker.bought_share("micro", "Sweet shop", "P23"), ranker.bought_share("micro", "", "P23")
    check(sweets > shops + 0.05, f"sweet shops rank CCTV higher than small shops in general ({sweets:.2f} vs {shops:.2f})")
    salon, small = ranker.bought_share("micro", "Salon", "P15"), ranker.bought_share("micro", "", "P15")
    check(salon < small, f"salons rank verified WhatsApp lower than small shops in general ({salon:.2f} vs {small:.2f})")
    check(ranker.similar("micro", "Pharmacy")["kind"] == "type", "a pharmacy is compared with pharmacies")
    check(ranker.similar("micro", "Space station")["kind"] == "segment", "an unknown type falls back to its segment")

    print(f"\n{sum(RESULTS)}/{len(RESULTS)} privacy and ranking checks passed")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    main()
