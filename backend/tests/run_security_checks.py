"""Security checks on the web server itself: only the built front end may be served as files.

    python -m tests.run_security_checks
"""
import os
import sys
import tempfile

os.environ["LLM_API_KEY"] = os.environ["GROQ_API_KEY"] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "security.db"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)
PASS = FAIL = 0


def check(ok: bool, name: str, detail: str = "") -> None:
    global PASS, FAIL
    PASS, FAIL = PASS + bool(ok), FAIL + (not ok)
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n        {detail}" if detail and not ok else ""))


# A request must never climb out of frontend/dist: the keys file, the database and the code live two folders up.
OUTSIDE = ["/..%2F..%2FREADME.md", "/%2e%2e/%2e%2e/README.md", "/..%2F..%2F.env", "/%2e%2e%2f%2e%2e%2f.gitignore",
           "/..%2F..%2Fbackend%2Fapp%2Fmain.py", "/..%2F..%2Fbackend%2Fruntime%2Fapp.db", "/assets/..%2F..%2F..%2FREADME.md",
           "/..%5C..%5CREADME.md", "/....//....//README.md", "/%2e%2e/%2e%2e/backend/data/smb_leads.csv"]
for u in OUTSIDE:
    r = c.get(u)
    leaked = r.status_code == 200 and "text/html" not in r.headers.get("content-type", "")
    check(not leaked, f"nothing outside the front end is served: {u}", f"{r.status_code} {r.headers.get('content-type')} {len(r.content)} bytes")

r = c.get("/")
check(r.status_code == 200 and "text/html" in r.headers["content-type"], "the app page itself is served")
r = c.get("/privacy.html")
check(r.status_code == 200 and "text/html" in r.headers["content-type"], "the privacy page is served")
check(c.get("/some/screen/in/the/app").status_code == 200, "an in-app address falls back to the app page")
check(c.get("/api/no-such-endpoint").status_code == 404, "an unknown API address is a 404, not the app page")

names = c.get("/api/kyc/samples").json()
some = next(iter(names.values()))[0] if isinstance(names, dict) and names else None
for bad in ["..%2F..%2F..%2Fapp", "K01_gst_certificate%2F..%2F..%2Fx", "..", "K01", "K01_gst_certificate.png", "%2e%2e%5c%2e%2e%5cx"]:
    r = c.get(f"/api/kyc/samples/{bad}")
    check(r.status_code == 404 or "image" not in r.headers.get("content-type", ""), f"specimen images: '{bad}' is refused", str(r.status_code))
check(c.get("/api/kyc/samples/K01_gst_certificate").headers.get("content-type") == "image/png", "specimen images: a real specimen is served")

h = c.get("/api/health").headers
check(h.get("x-content-type-options") == "nosniff" and h.get("x-frame-options") == "SAMEORIGIN" and h.get("referrer-policy") == "no-referrer",
      "every response carries the security headers")

print(f"{PASS}/{PASS + FAIL} security checks passed" if not FAIL else f"{FAIL} of {PASS + FAIL} security checks FAILED")
sys.exit(1 if FAIL else 0)
