# Accel Saathi · Project Udyam Digital

[![tests](https://github.com/sujalbhatu/accel-saathi/actions/workflows/tests.yml/badge.svg)](https://github.com/sujalbhatu/accel-saathi/actions/workflows/tests.yml)

A small business owner finds the right telecom bundle, buys it and tracks activation in one sitting, on a phone, in their own language. Built for Airtel Sync 2026 (Digital Track, Project Udyam Digital) by team TouristGuide, NIT Jamshedpur.

| Journey step | What happens |
| --- | --- |
| **Advisor** | The owner describes the business in any of 10 Indian languages (typed or spoken). It asks only what is missing, pre-fills from the GSTIN, and recommends a bundle with a plain-language reason for every item. The owner can ask anything at any step (documents, install time, what a product does) and change the bundle in chat: "make it cheaper", "my budget is 2000", "add CCTV", "remove WhatsApp", "24 months", "undo", "talk to a person". |
| **Quote and checkout** | One monthly price with GST, setup fee and go-live date. Add-ons toggle on and off, 12 or 24 months, and every change is re-checked against catalogue rules. |
| **Smart KYC** | Consent first, then DigiLocker pull, Aadhaar OTP e-KYC, or photo upload with offline OCR. Each document is cross-checked against the GST and Udyam registries and against the other documents. Every problem is explained in one sentence. |
| **Tracker** | A live timeline, an ETA for each service, self-service slot booking, WhatsApp-style updates and tickets, so the owner never has to call support. |
| **Partner console** (`/#/console`) | Leads the advisor could not close, ranked by a lead-scoring model, with the next best action and the local partner who speaks the owner's language. Also shows the live funnel, orders and a masked audit log. |

## Run it on your laptop

You need Python 3.11 or newer. Node is only needed if you change the frontend.

```bash
cp .env.example .env        # then paste your LLM key into .env (optional)
./start.sh                  # Windows: start.bat
```

Then open http://localhost:8000. The partner console is at http://localhost:8000/#/console.

The app works without an LLM key. The advisor then runs on its built-in rules and English, Hindi, Marathi and Tamil templates. With a key, it understands free text better and writes friendlier explanations. Any OpenAI-compatible provider works (Gemini, Groq, xAI, OpenAI); see `.env.example`.

To work on the frontend:

```bash
cd frontend && npm install && npm run dev   # http://localhost:5173, proxies /api to :8000
npm run build                                # writes frontend/dist, which the backend serves
```

## Deploy

`Dockerfile` builds everything into one container on port 7860. It runs as-is on Hugging Face Spaces (Docker), Render, Railway or Cloud Run. Set `LLM_API_KEY` as a secret on the host, never in the repo.

## How it is built

```
frontend/  React + Vite mobile web app (customer journey + partner console)
backend/app/
  recommender.py  deterministic bundle engine: eligibility, dependencies, pricing, install timeline
  extract.py      free text -> business profile (rules for all 10 languages + optional LLM)
  lexicon.py      the services and kinds of business named in the nine Indian scripts, for the rules
  advisor.py      conversation state machine and in-chat bundle changes; LLM never chooses products or prices
  assistant.py    understands any message (one LLM call + keyword rules), answers questions
  knowledge.py    what the advisor answers from, and the hybrid search over it (no model needed)
  guard.py        safety layer: screens each message before the model, caps absurd sizes, checks every model reply
  ocr.py          offline OCR (RapidOCR/ONNX): watermark removal, de-rotation, two-pass digit reading
  kyc.py          document parsing and 20+ checks (GSTIN checksum, registry status, names, state, address, dates)
  ids.py          GSTIN checksum and Udyam format rules, masking
  orders.py       orders, tracker stages, notifications, slots, tickets
  leads.py        lead-scoring model (logistic regression) and next best action
  store.py        SQLite store and audit log (swap for Postgres in production)
  main.py         FastAPI routes; interactive API docs at /api/docs
backend/data/     hackathon data pack (synthetic)
```

**Design choices that matter**

- **Answers are grounded and guarded.** The LLM answers only from the catalogue and the owner's current quote. Its reply is treated as untrusted: one that quotes a price or percentage not in the catalogue or the quote, offers a discount or a waiver, makes a promise, carries a link or an identifier, runs down a competitor or leaks its instructions is dropped, logged, and replaced by the app's own answer. Every bundle change runs through the rules engine.
- **Hostile messages never reach the model.** Attempts to steer the AI, requests for other customers' data, signs of misuse (bulk SIMs for OTP schemes, someone else's GSTIN), abuse and unrelated asks get a fixed answer in the owner's language and change nothing. Asks for a discount or a guarantee are answered by the app with the real options and exact prices. A business beyond small-business plans (or a typo such as "1000000 staff") is handed to a person instead of being priced. An Aadhaar number typed into the chat is masked before it is stored.
- **Search that is measured, not assumed.** Answers come from 47 knowledge chunks (the KYC, privacy, pricing, installation and eligibility notes plus one sheet per catalogue product, built from the catalogue file). The search needs no model and no paid service: stemmed BM25 and character 3-grams (which survive typos) merged by reciprocal rank fusion, over chunks indexed with the ways owners ask and the problems each product solves, with the question widened by the services and topics it names in any of the 10 languages. On 26 questions written after the search was built and never tuned on, the right source is in the top four (what the model is given) for 96%, against 50% for the BM25 search it replaced; first place is right for 58% against 31%. On the 77-question set it was tuned on: 100% and 90%. `python -m tests.eval.run_rag_eval` prints all three sets for all three methods and fails the build if they slip.
- **The LLM never picks products.** It helps understand the owner; a rules engine enforces every catalogue rule (city tier, minimum team size and sites, GSTIN required, product dependencies). Every quote is therefore valid and explainable, and the advisor keeps working if the LLM is slow or down.
- **GSTIN first.** Leads with a GSTIN activate at 9.6% against 2.0% without one, so the advisor asks for it early and fills in the rest from the registry.
- **Privacy by design (DPDP Act 2023).** No document is processed before consent. Images are discarded after extraction, keeping only a SHA-256 fingerprint. Identifiers are masked in the UI, the API and the audit log. Owners can erase their data before ordering.
- **Offline OCR.** No document leaves the server for a third-party OCR API.

## Tests

```bash
cd backend
python -m tests.run_kyc_pack           # Smart KYC over all 12 specimen applicants
python -m tests.run_advisor_scenarios  # 30 owners in 5 languages + 7 chat changes, checked against the catalogue
python -m tests.run_advisor_scenarios --llm   # the same with the LLM from .env, as in a live demo
python -m tests.run_judge_scenarios     # 50 owners nobody tuned for: typos, Hinglish, spoken run-ons, all 10 languages
python -m tests.run_security_checks    # only the built front end is ever served as a file
python -m tests.run_red_team           # 500+ checks: 50 attacks in the chat, a model that misbehaves, API abuse
python -m tests.run_red_team --llm     # the same attacks against the LLM from .env
```

Layout check: the whole buying journey in each of the 10 languages on a small phone, a tablet and a laptop (300 screens). It fails on any text that spills out of its box, any sideways scroll and any script error.

```bash
# with the app running on port 8000 and Playwright installed (npm i -D playwright)
node frontend/tests/layout_check.cjs http://127.0.0.1:8000
```

**Judge-style scenarios.** `run_judge_scenarios` types the way people really type ("only me n 1 helper", "fifteen people one office", "GST applied but not received yet") and answers every follow-up question by typing. The expected bundle is worked out from the catalogue file by the suite's own rules, not by the app's code. It checks seven things per owner: the profile is understood, nothing already said is asked again, everything asked for is ticked, each ask is in the bundle or explained as not available, every line is valid and priced right, sizes match (one line per site, 4 cameras means 4), and the answer is in the owner's script. Honest numbers, rules only: the first set of 30 scored 13 clean on its first run; after fixing what it found, a second set of 20 written afterwards scored 12 clean on its first run; both sets pass in full now and run in CI. Among the faults it found: a GST question that repeated forever on "not yet, applied only", "fifteen people one office" read as 15 offices (a quote of ₹95,737 a month), two branches given one internet line, and service names not understood in six of the ten languages without the model.

Expected results: K01 cancelled GSTIN, K04 blurred GST certificate, K05 missing Udyam certificate, K06 altered GSTIN (check digit fails), K07 legal name differs from the registry, K11 address proof older than 90 days. K05, K10 and K11 are asked for a signatory authorisation letter. K02, K03, K08, K09 and K12 pass.

All data is synthetic and the operator "Accel Telecom" is fictional, as in the case study.
