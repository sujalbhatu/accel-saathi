"""Search test for the advisor's knowledge base: does the right section reach the AI?

    python -m tests.run_retrieval_eval

66 hand-labelled owner questions in all 10 app languages (English, Hinglish, and the 9 Indian scripts). Each question
lists the knowledge-base sections that answer it. We measure, over the 47 chunks:

  hit@1   the first section sent is a right one
  hit@4   a right section is among the 4 sent to the AI (what the advisor actually uses)
  MRR     mean reciprocal rank of the first right section

for plain BM25 on the owner's words, and for BM25 on the words plus what the rules understood (knowledge.expand),
which is what the live advisor does. Passes when the live setup gets hit@4 >= 85% overall and beats plain BM25.
No AI and no network are used, so this runs in CI.
"""
import os
import sys
import tempfile

for key in ("LLM_API_KEY", "GROQ_API_KEY", "DATA_KEY"):
    os.environ[key] = ""
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "eval.db"))

from app import knowledge  # noqa: E402
from app.assistant import needs_in, rules_understand  # noqa: E402

DOCS = ["kyc#documents-needed", "kyc#fastest-way-digilocker-and-aadhaar-otp"]
TIME = ["install#how-long-it-takes", "install#after-ordering"]
PRIV = ["privacy#consent-first", "privacy#purpose-and-minimisation", "privacy#owner-s-rights", "privacy#ai-and-data"]
PRICE = ["buying#how-prices-work", "buying#12-or-24-months"]
GST = ["eligibility#gstin"]

# (language, question, sections that answer it)
QUESTIONS = [
    ("en", "What documents do I need for KYC?", DOCS),
    ("en", "Can I do KYC with DigiLocker?", ["kyc#fastest-way-digilocker-and-aadhaar-otp"]),
    ("en", "My PAN photo upload is blurry, what should I do?", ["kyc#uploading-photos", "kyc#if-a-check-fails"]),
    ("en", "What checks do you run on my GSTIN and PAN?", ["kyc#checks-we-run"]),
    ("en", "My KYC check failed, what now?", ["kyc#if-a-check-fails"]),
    ("en", "How long does installation take?", TIME),
    ("en", "How do I book the technician visit?", ["install#booking-the-technician"]),
    ("en", "There is no fibre at my shop, can I still get internet?", ["install#no-fibre-at-the-site", "product#P04"]),
    ("en", "Who do I call if the internet stops working after install?", ["install#help-and-tickets"]),
    ("en", "What happens after I place the order?", ["install#after-ordering", "buying#steps-to-order"]),
    ("en", "Is my data safe with you?", PRIV),
    ("en", "Do you use AI on my documents?", ["privacy#ai-and-data"]),
    ("en", "Can I ask you to delete my data?", ["privacy#owner-s-rights"]),
    ("en", "Why do you ask for my consent?", ["privacy#consent-first"]),
    ("en", "How are prices calculated, is GST extra?", PRICE),
    ("en", "Is 24 months cheaper than 12 months?", ["buying#12-or-24-months"]),
    ("en", "Can I change my bundle later?", ["buying#changing-the-bundle"]),
    ("en", "What are the steps to order?", ["buying#steps-to-order"]),
    ("en", "I don't have a GSTIN, can I still buy?", GST),
    ("en", "Is static IP available in a tier-3 town?", ["eligibility#city-tier", "product#P11"]),
    ("en", "Can a one-person shop get SD-WAN?", ["eligibility#team-size-and-locations", "product#P10"]),
    ("en", "Why does static IP need an internet line?", ["eligibility#products-that-need-an-internet-line", "product#P11"]),
    ("en", "How much is the cloud CCTV camera?", ["product#P23"]),
    ("en", "I want to accept UPI payments and print bills", ["product#P19"]),
    ("en", "Can my customers get guest wi-fi?", ["product#P22"]),
    ("en", "Do you have a backup internet if fibre goes down?", ["product#P09"]),
    ("en", "I need a toll-free number for my clinic", ["product#P13"]),
    ("en", "Send WhatsApp messages to my customers", ["product#P15"]),
    ("en", "I want a website for my shop", ["product#P18"]),
    ("en", "Antivirus for my billing computer", ["product#P20"]),
    ("en", "Track my delivery vans", ["product#P25"]),
    ("en", "Monitor the machines in my workshop", ["product#P24"]),
    ("en", "Business email for my staff", ["product#P16"]),
    ("hi", "kyc ke liye kaunse documents chahiye?", DOCS),
    ("hi", "installation me kitne din lagenge?", TIME),
    ("hi", "mera data safe hai kya?", PRIV),
    ("hi", "gst nahi hai to bhi le sakte hai?", GST),
    ("hi", "dukaan ke liye camera chahiye", ["product#P23"]),
    ("hi", "केवाईसी के लिए कौन से दस्तावेज़ चाहिए?", DOCS),
    ("hi", "इंस्टॉलेशन में कितने दिन लगेंगे?", TIME),
    ("hi", "दुकान में कैमरा लगवाना है", ["product#P23"]),
    ("hi", "यूपीआई पेमेंट और बिलिंग चाहिए", ["product#P19"]),
    ("bn", "কেওয়াইসির জন্য কী কী কাগজ লাগবে?", DOCS),
    ("bn", "দোকানে ক্যামেরা লাগাতে চাই", ["product#P23"]),
    ("bn", "আমার তথ্য কি নিরাপদ? privacy", PRIV),
    ("gu", "KYC માટે કયા દસ્તાવેજ જોઈએ?", DOCS),
    ("gu", "દુકાનમાં કેમેરા જોઈએ છે", ["product#P23"]),
    ("gu", "ઇન્સ્ટોલેશનમાં કેટલા દિવસ લાગશે?", TIME),
    ("kn", "KYC ಗೆ ಯಾವ ದಾಖಲೆಗಳು ಬೇಕು?", DOCS),
    ("kn", "ಅಂಗಡಿಗೆ ಕ್ಯಾಮೆರಾ ಬೇಕು", ["product#P23"]),
    ("kn", "ನನ್ನ ಗ್ರಾಹಕರಿಗೆ WhatsApp ಸಂದೇಶ ಕಳುಹಿಸಬೇಕು", ["product#P15"]),
    ("ml", "KYC ക്ക് എന്തൊക്കെ രേഖകൾ വേണം?", DOCS),
    ("ml", "കടയിൽ ക്യാമറ വേണം", ["product#P23"]),
    ("ml", "UPI പേയ്മെന്റും ബില്ലിംഗും വേണം", ["product#P19"]),
    ("mr", "KYC साठी कोणती कागदपत्रे लागतात?", DOCS),
    ("mr", "दुकानात कॅमेरा हवा आहे", ["product#P23"]),
    ("mr", "किंमत किती आहे? GST वेगळा का?", PRICE),
    ("pa", "KYC ਲਈ ਕਿਹੜੇ ਦਸਤਾਵੇਜ਼ ਚਾਹੀਦੇ ਹਨ?", DOCS),
    ("pa", "ਦੁਕਾਨ ਲਈ ਕੈਮਰਾ ਚਾਹੀਦਾ ਹੈ", ["product#P23"]),
    ("pa", "ਗਾਹਕਾਂ ਲਈ WiFi ਚਾਹੀਦਾ ਹੈ", ["product#P22"]),
    ("ta", "KYC க்கு என்ன ஆவணங்கள் வேண்டும்?", DOCS),
    ("ta", "கடைக்கு கேமரா வேண்டும்", ["product#P23"]),
    ("ta", "விலை எவ்வளவு? price", PRICE),
    ("te", "KYC కి ఏ పత్రాలు కావాలి?", DOCS),
    ("te", "షాప్ కి కెమెరా కావాలి", ["product#P23"]),
    ("te", "UPI పేమెంట్స్ మరియు బిల్లింగ్ కావాలి", ["product#P19"]),
]

# Written AFTER the keyword fixes that the questions above led to, and never tuned on: an honest check that the
# fixes generalise. Reported separately, not a pass/fail gate.
HELD_OUT = [
    ("bn", "ইনস্টলেশন কত দিনে হবে?", TIME),
    ("bn", "কাস্টমারদের জন্য WiFi চাই", ["product#P22"]),
    ("gu", "ગ્રાહકો માટે WiFi જોઈએ", ["product#P22"]),
    ("gu", "KYC માટે કાગળ શું જોઈએ?", DOCS),
    ("kn", "ಇನ್‌ಸ್ಟಾಲೇಶನ್ ಎಷ್ಟು ದಿನ ಆಗುತ್ತೆ?", TIME),
    ("ml", "ഇൻസ്റ്റലേഷന് എത്ര ദിവസം എടുക്കും?", TIME),
    ("ml", "എന്റെ ഡാറ്റ സുരക്ഷിതമാണോ?", PRIV),
    ("pa", "ਇੰਸਟਾਲੇਸ਼ਨ ਵਿੱਚ ਕਿੰਨੇ ਦਿਨ ਲੱਗਣਗੇ?", TIME),
    ("te", "ఇన్‌స్టాలేషన్ కి ఎన్ని రోజులు పడుతుంది?", TIME),
    ("te", "నా డేటా సురక్షితమేనా?", PRIV),
    ("ta", "என் டேட்டா பாதுகாப்பா?", PRIV),
    ("hi", "ग्राहकों के लिए वाईफाई चाहिए", ["product#P22"]),
    ("mr", "माझा डेटा सुरक्षित आहे का?", PRIV),
    ("en", "Is there a one-time setup fee or only monthly?", PRICE),
    ("en", "Do I need fibre for the leased line?", ["product#P05", "product#P06", "install#no-fibre-at-the-site"]),
    ("hi", "website banwani hai dukaan ki", ["product#P18"]),
]

K = 4


def rank_of(found: list[dict], gold: list[str]) -> int | None:
    for i, c in enumerate(found):
        if c["id"] in gold:
            return i + 1
    return None


def score(query_of, questions=None) -> dict:
    ranks, misses = [], []
    for lang, q, gold in questions or QUESTIONS:
        r = rank_of(knowledge.search(query_of(q), k=len(knowledge.chunks())), gold)
        ranks.append((lang, r))
        if not r or r > K:
            misses.append((lang, q, r))
    n = len(ranks)
    by_lang = {}
    for lang, r in ranks:
        a = by_lang.setdefault(lang, [0, 0])
        a[0] += 1
        a[1] += bool(r and r <= K)
    return {"hit1": sum(1 for _, r in ranks if r == 1) / n, "hitk": sum(1 for _, r in ranks if r and r <= K) / n,
            "mrr": sum(1 / r for _, r in ranks if r) / n, "misses": misses, "by_lang": by_lang}


def live_query(q: str) -> str:
    return knowledge.expand(q, rules_understand(q, "chat").get("intent"), needs_in(q))


def main():
    plain = score(lambda q: q)
    live = score(live_query)
    print(f"Search test: {len(QUESTIONS)} owner questions in {len({l for l, _, _ in QUESTIONS})} languages, "
          f"{len(knowledge.chunks())} knowledge chunks, top {K} sent to the AI.\n")
    print(f"{'method':46s} hit@1  hit@{K}   MRR")
    for name, r in (("BM25 on the owner's words", plain), ("BM25 + what the rules understood (live)", live)):
        print(f"{name:46s} {r['hit1']:5.0%} {r['hitk']:6.0%} {r['mrr']:5.2f}")
    print("\nhit@4 by language (live): " + ", ".join(f"{l} {h}/{n}" for l, (n, h) in live["by_lang"].items()))
    if live["misses"]:
        print("\nMissed by the live setup (rank of first right section):")
        for lang, q, r in live["misses"]:
            print(f"  [{lang}] {q}  -> {r or 'not found'}")
    hp, hl = score(lambda q: q, HELD_OUT), score(live_query, HELD_OUT)
    print(f"\nHeld-out ({len(HELD_OUT)} questions written after the fixes, not tuned on): hit@{K} plain "
          f"{hp['hitk']:.0%}, live {hl['hitk']:.0%}; MRR plain {hp['mrr']:.2f}, live {hl['mrr']:.2f}")
    for lang, q, r in hl["misses"]:
        print(f"  missed [{lang}] {q}  -> {r or 'not found'}")
    checks = [("live hit@4 >= 85%", live["hitk"] >= 0.85),
              ("live beats plain BM25 on hit@4", live["hitk"] > plain["hitk"]),
              ("live MRR >= plain MRR", live["mrr"] >= plain["mrr"])]
    print()
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main()
