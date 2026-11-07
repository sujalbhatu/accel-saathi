# Evaluation results, 7 Nov 2026

Reproduce: `cd backend && python -m tests.eval.run_rag_eval` (retrieval, offline) and `--answers` (AI answers, uses the
.env keys). Questions: `tests/eval/rag_questions.jsonl`, 83 owner questions (77 with a labelled answer chunk, 6 out of
scope) in English, Hinglish, Hindi, Marathi, Tamil, Bengali, Telugu, Gujarati, Kannada, Malayalam and Punjabi, over the
47 knowledge chunks.

## Retrieval (BM25 over 47 chunks; the AI is given the top 4)

| Variant | recall@1 | recall@4 | MRR@10 |
|---|---:|---:|---:|
| BM25 on the owner's words | 0.545 | 0.649 | 0.600 |
| BM25 + the rules engine's expansion, before the 7 Nov keyword fix | 0.688 | 0.844 | 0.761 |
| **BM25 + expansion, after it (what the app sends now)** | **0.766** | **0.935** | **0.845** |

By question type, recall@4 now (plain BM25 → app): FAQ 1.000 → 0.957, product 0.944 → 1.000,
paraphrase ("someone stole from my shop") 0.250 → 0.750, multilingual 0.292 → 0.958.

By language now (recall@1 / recall@4 / MRR): English 0.755 / 0.925 / 0.832, Hinglish 1 / 1 / 1, Hindi 0.833 / 1 / 0.917,
Marathi 0.5 / 1 / 0.75, Tamil 0.333 / 0.667 / 0.5, Bengali 0.5 / 1 / 0.75, Gujarati, Kannada, Malayalam, Punjabi and
Telugu 1 / 1 / 1. Before the keyword fix (commit 6439848: camera, documents and install-time words in Bengali,
Gujarati, Kannada, Malayalam, Punjabi and Telugu) those six languages scored 0, because the expansion read only English,
Hindi, Marathi and Tamil.

Caveats: these six languages have only 1–2 questions each here, so their numbers are indicative, not precise; and the
fix was written the same day as this set, so the independent check is `tests/run_retrieval_eval.py`, whose 16 held-out
questions (written after the fix) reach hit@4 75% vs 25% for plain BM25. Paraphrases and Tamil remain the weakest;
a multilingual embedding model (hybrid retrieval) is the next step.

## AI answers (the AI step only, deterministic checks, no LLM judge)

83 questions, AI on (Gemini Flash-Lite and Groq gpt-oss-120b, free plans):

| Metric | Value |
|---|---:|
| AI calls that returned an answer | 79.5% (the rest hit provider limits: Groq 429, Gemini 503; the app then answers by rules) |
| In-scope questions answered by the AI itself | 62.3% (the rest are routed to the app's own exact answers, by design, or hit a limit) |
| Reply in the question's language | 96.2% |
| Cites a correct (labelled) source, when it answers | 93.8% |
| Cited sources that were really retrieved | 94.3% |
| Replies with a number (₹, Mbps, GB, days...) found nowhere in the sources, catalogue or question | **0%** |
| Out-of-scope questions politely declined | 83.3% (5 of 6; one was left to the app's rules) |
| Latency p50 / p95 | 1.8 s / 4.0 s |

## Cost

From the passive call log (`LLM_CALL_LOG`), priced at public pay-as-you-go list prices: Groq gpt-oss-120b US$0.15 in /
0.60 out per million tokens, Gemini Flash-Lite US$0.30 / 2.50, US$1 = ₹88. We run on free plans, so actual spend is ₹0.

- A typical AI call: about 2,700–3,100 tokens in and 110–140 out.
- The 92-check advisor suite with the AI on made only 7 AI calls: the rules answer most turns themselves.
  Where a conversation used the AI: 1.17 calls, about 3,800 tokens, **about ₹0.11 per conversation**
  (₹108 per 1,000 conversations) at paid prices.
