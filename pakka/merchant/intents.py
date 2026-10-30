"""Classify a merchant's reply into one fixed intent. This is the only place an LLM is used.

The LLM never picks an action: it only labels the reply, and anything outside the label set
becomes `unclear`. With no LLM configured, the keyword classifier runs fully offline.
"""
import logging
import os
import re
from collections import Counter
from typing import Literal

from pakka.pii import mask

from .models import ALL_INTENTS, DISTRESS

log = logging.getLogger(__name__)
LLM_USAGE: Counter = Counter()      # token usage reported by the provider, when it reports any

# Checked in this order. Hardship and dispute come first so "kal hospital jaana hai" is hardship.
# Hardship also covers the sensitive occasions in the recovery rules: bereavement, illness, calamity
# and weddings, so contact pauses and a person takes over.
KEYWORDS: list[tuple[str, list[str]]] = [
    ("hardship", ["bimar", "beemar", "bimaar", "hospital", "illness", "ill", "sick", "death", "maut",
                  "flood", "baadh", "dukaan band thi", "dukaan band hai", "dukaan band rahi", "dukan band thi",
                  "dukan band hai", "shop closed", "shop is closed", "shop was closed",
                  "bikri nahi", "nuksan", "nuksaan", "loss", "pareshani", "paise nahi", "paisa nahi", "cash nahi",
                  "manda", "tabiyat", "tabiyat kharab", "halat", "haalat", "no money", "business is down",
                  "accident", "no sales", "dhanda band",
                  "died", "passed away", "funeral", "death in the family", "guzar gaye", "guzar gayi",
                  "dehant", "antim sanskar", "shok", "shraddh",
                  "wedding", "marriage", "shaadi", "shadi", "vivah",
                  "cyclone", "toofan", "earthquake", "bhukamp", "fire", "aag lag", "calamity",
                  "बीमार", "अस्पताल", "दुकान बंद थी", "दुकान बंद है", "दुकान बंद रही", "दुकान बंद पड़ी", "बाढ़", "मौत",
                  "बिक्री नहीं", "नुकसान", "परेशानी", "पैसे नहीं", "पैसे ही नहीं", "पैसा नहीं", "नकद नहीं", "मंदा",
                  "मंदी", "तबीयत", "हालात", "बीमारी", "इलाज", "देहांत", "गुज़र", "गुजर", "अंतिम संस्कार",
                  "शादी", "विवाह", "तूफ़ान", "भूकंप", "आग"]),
    ("dispute", ["galat", "wrong", "kaat liya", "kat gaya", "kat gaye", "kat chuke", "deducted twice", "do baar",
                 "fraud", "extra kata", "extra charge", "liya hi nahi", "kyun kata", "kyu kata",
                 "गलत", "ग़लत", "दो बार", "काट लिया", "कट गए", "कट गया", "कट चुके", "अतिरिक्त", "किस बात",
                 "लिया ही नहीं", "बकाया क्यों", "क्यों कटे", "क्यों काटे"]),
    ("already_paid", ["already paid", "already pay", "pehle hi", "pahle hi", "pay kar diya", "bhar diya",
                      "de diya", "bhej diya", "bhej diye", "paid already", "payment done", "transaction id", "txn",
                      "screenshot", "chukta", "पहले ही", "भर दिया", "दे दिया", "भेज दिया", "भेज दिए",
                      "पेमेंट कर दी", "पेमेंट कर दिया", "ट्रांजैक्शन", "स्क्रीनशॉट", "चुकता"]),
    ("request_lower_deduction", ["kam kato", "kam kaato", "kam katna", "kam kaatna", "thoda kam",
                                 "lower", "reduce", "less deduction", "कम काट", "कम कटौती"]),
    ("request_reschedule", ["date badlo", "date badal", "reschedule", "aage badhao", "aage badha",
                            "extend", "more time", "tareekh", "तारीख", "आगे बढ़ा"]),
    ("request_callback", ["call karo", "call kar", "call me", "call back", "callback", "baat karni",
                          "baat karna", "phone karo", "phone kar lena", "कॉल", "बात करनी", "फ़ोन कर", "फोन कर"]),
    ("will_pay_later", ["kal", "tomorrow", "parso", "parson", "next week", "baad mein", "baad me", "later",
                        "hafte", "do din", "kuch din", "sunday", "monday", "salary",
                        "कल", "परसों", "बाद में", "हफ्ते", "हफ़्ते", "दो दिन", "कुछ दिन", "रविवार", "सोमवार",
                        "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "सैलरी"]),
    ("will_pay_today", ["abhi", "aaj", "today", "now", "pay kar raha", "paying", "right away", "qr",
                        "अभी", "आज"]),
]

# Fail safe: when unsure, Pakka routes to a person, never to a payment nudge.
# A reply becomes will_pay_* only with a time word AND a payment verb AND no negation.
# Negation together with a money or sales word is hardship. Anything else is unclear, which goes to a person.
PAY_VERBS = ["pay", "paying", "de dunga", "de doonga", "de dungi", "dunga", "doonga", "kar dunga", "karunga",
             "bhar", "bhej", "daal", "dal dunga", "chuka", "transfer", "send", "upi", "qr", "google pay", "phonepe",
             "दे दूंगा", "दे दूँगा", "दूंगा", "दूँगा", "दूगा", "दूंगी", "कर दूंगा", "कर दूँगा", "करूंगा", "करूँगा",
             "पेमेंट कर", "भेज", "डाल", "भर", "भरूंगा", "चुका", "upi", "qr"]
NEGATIONS = ["nahi", "nahin", "nhi", "nai", "not", "no", "cannot", "can't", "cant", "won't", "wont", "don't",
             "dont", "mat", "नहीं", "नही", "मत", "ना"]
MONEY_WORDS = ["paise", "paisa", "paison", "pese", "cash", "money", "bikri", "sale", "sales", "dhanda", "dhandha",
               "kamai", "income", "business", "grahak", "पैसे", "पैसा", "पैसों", "नकद", "कैश", "बिक्री", "धंधा",
               "धंधे", "कमाई", "ग्राहक", "बिक्री"]
PAY_INTENTS = {"will_pay_today", "will_pay_later"}

# "Can't pay today": a reply is request_skip_today only with BOTH
#   (1) a skip marker: "skip", "kal se" (from tomorrow), or a today-word together with a negation or "adjust"
#   (2) a deduct / take / adjust / skip marker (a tomorrow-word alone is not enough).
# Distress words are checked before this (so "bimar hoon, aaj nahi" stays hardship), and the
# "negation + money word -> hardship" rule comes after it.
SKIP_WORDS = ["skip", "chhod do", "chod do", "छोड़ दो"]
FROM_TOMORROW = ["kal se", "कल से", "from tomorrow"]
TODAY_WORDS = ["aaj", "today", "आज"]
ADJUST_WORDS = ["adjust", "एडजस्ट", "carry forward", "aage kar"]
# The second marker must be about the lender taking or adjusting it ("kaat lena", "take it", "adjust").
# A tomorrow-word alone isn't enough: "aaj nahi, kal kar dunga" means "I'll pay tomorrow", not a skip request.
LATER_MARKERS = ["kaat", "kat lena", "kat lo", "katna", "deduct", "take it", "le lena", "le lo", "काट",
                 "कटौती"] + ADJUST_WORDS + SKIP_WORDS

LABELS = {
    "will_pay_today": "will pay today or right now",
    "will_pay_later": "will pay on a later day (tomorrow, next week)",
    "request_lower_deduction": "asks for a smaller daily deduction",
    "request_reschedule": "asks to change the repayment date or get more time",
    "request_callback": "asks for a phone call or to talk to someone",
    "request_skip_today": "can't pay today and asks for it to be taken tomorrow or adjusted later (no distress)",
    "dispute": "says the deduction or amount is wrong",
    "hardship": "illness, death or funeral, wedding in the family, flood, fire or other calamity, shop closed",
    "already_paid": "says they have already paid",
    "unclear": "anything else",
}

SYSTEM_PROMPT = (
    "You label one reply from a small shop owner in India about their daily loan instalment. "
    "The reply may be in Hindi, English or Hinglish. Return only one label from this list, nothing else:\n"
    + "\n".join(f"{k}: {v}" for k, v in LABELS.items())
    + "\nExamples: 'kal de dunga' -> will_pay_later; 'I'll pay tomorrow' -> will_pay_later; "
      "'abhi bhar raha hoon' -> will_pay_today; 'paying now' -> will_pay_today; "
      "'bimar tha, dukaan band thi' -> hardship; 'my father is in hospital' -> hardship; "
      "'paise galat kate' -> dispute; 'you deducted twice' -> dispute; "
      "'aaj nahi de paunga, kal kaat lena' -> request_skip_today; 'can't pay today, take it tomorrow' -> request_skip_today. "
      "If any distress is mentioned, choose hardship or dispute over other labels."
)


def _compile(word: str) -> re.Pattern:
    if word.isascii():
        return re.compile(rf"(?<![a-z]){re.escape(word)}(?![a-z])")
    return re.compile(re.escape(word))


_PATTERNS = [(label, [_compile(w) for w in words]) for label, words in KEYWORDS]


def _prefix(word: str) -> re.Pattern:
    """Left boundary only, so "bhar" also catches "bharta" and "bhej" catches "bhejta"."""
    if word.isascii():
        return re.compile(rf"(?<![a-z]){re.escape(word.lower())}")
    return re.compile(re.escape(word))


def _neg(word: str) -> re.Pattern:
    if word.isascii():
        return re.compile(rf"(?<![a-z']){re.escape(word)}(?![a-z'])")
    return re.compile(rf"(?<![\u0900-\u097F]){re.escape(word)}(?![\u0900-\u097F])")   # whole Devanagari word


_PAY_VERBS = [_prefix(w) for w in PAY_VERBS]
_SKIP = [_compile(w) for w in SKIP_WORDS]
_FROM_TOMORROW = [_compile(w) for w in FROM_TOMORROW]
_TODAY = [_compile(w) for w in TODAY_WORDS]
_ADJUST = [_prefix(w) for w in ADJUST_WORDS]
_LATER = [_prefix(w) for w in LATER_MARKERS]
_NEGATIONS = [_neg(w) for w in NEGATIONS]
_MONEY = [_prefix(w) for w in MONEY_WORDS]


# Prefix match for pay cues, so "bhar" also catches "bharta" and "bhej" catches "bhejta".
def _any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def is_skip_request(text: str) -> bool:
    """Both a skip marker and a tomorrow/deduct/adjust marker (see SKIP_WORDS above)."""
    low = text.lower()
    today = _any(_TODAY, low)
    skip_marker = (_any(_SKIP, low) or _any(_FROM_TOMORROW, low)
                   or (today and (_any(_NEGATIONS, low) or _any(_ADJUST, low))))
    return skip_marker and _any(_LATER, low)


def keyword_classify(text: str) -> str:
    low = text.lower()
    matched = [label for label, patterns in _PATTERNS if _any(patterns, low)]
    for label in ("hardship", "dispute", "already_paid"):          # a) distress first, always
        if label in matched:
            return label
    if is_skip_request(low):                                        # b) "aaj nahi, kal kaat lena"
        return "request_skip_today"
    negated = _any(_NEGATIONS, low)                                 # c) "paise nahi hain" -> hardship
    if negated and _any(_MONEY, low):                               # "paise nahi", "bikri nahi ho rahi"
        return "hardship"
    for label in ("request_lower_deduction", "request_reschedule", "request_callback"):
        if label in matched:
            return label
    for label in ("will_pay_later", "will_pay_today"):
        if label in matched:
            return label if pay_ok(text) else "unclear"
    return "unclear"


def pay_ok(text: str) -> bool:
    """The fail-safe check every will_pay_* label must pass: a payment verb, and no negation."""
    low = text.lower()
    return _any(_PAY_VERBS, low) and not _any(_NEGATIONS, low)


def llm_provider() -> str:
    return os.getenv("PAKKA_LLM_PROVIDER", "").lower()


def llm_model() -> str | None:
    if llm_provider() == "anthropic":
        return os.getenv("PAKKA_LLM_MODEL", "claude-haiku-5-5")   # small, fast model for a fixed label set
    if llm_provider() == "sarvam":
        return os.getenv("PAKKA_LLM_MODEL", "sarvam-105b")        # sarvam-m and sarvam-30b are retired
    return os.getenv("PAKKA_LLM_MODEL") or None                   # gemini: no default, set it explicitly


def llm_enabled() -> bool:
    provider = llm_provider()
    if provider == "anthropic":
        return bool(os.getenv("PAKKA_LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
    if provider == "gemini":
        return bool(os.getenv("PAKKA_LLM_API_KEY") and llm_model())
    if provider == "sarvam":
        return bool(os.getenv("SARVAM_API_KEY"))                  # the same key the Bulbul TTS uses
    return False


def call_llm(text: str) -> str:
    """Return the model's raw label, lowercased. Callers map anything outside the label set to unclear.

    Raises on any API error (including 429 rate limits); classify() then falls back to keywords.
    """
    if llm_provider() == "gemini":
        return _call_gemini(text)
    if llm_provider() == "sarvam":
        return _call_sarvam(text)
    return _call_anthropic(text)


def _sarvam_client():
    try:
        from sarvamai import SarvamAI  # optional dependency, only needed when PAKKA_LLM_PROVIDER=sarvam
    except ImportError:
        log.warning("PAKKA_LLM_PROVIDER=sarvam but the sarvamai SDK isn't installed; using keywords. "
                    "pip install sarvamai")
        raise
    return SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"), timeout=8)


def _call_sarvam(text: str) -> str:
    client = _sarvam_client()
    resp = client.chat.completions(
        model=llm_model(),
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        temperature=0,
        reasoning_effort=None,         # non-think mode: no reasoning tokens
        max_tokens=16,
        request_options={"timeout_in_seconds": 8, "max_retries": 0},   # fail fast, then keywords
    )
    usage = getattr(resp, "usage", None)
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        LLM_USAGE[field] += getattr(usage, field, 0) or 0
    choice = resp.choices[0] if resp.choices else None
    content = choice.message.content if choice and choice.message else None
    return (content or "").strip().lower()


def _gemini_client():
    from google import genai  # optional dependency, only needed when PAKKA_LLM_PROVIDER=gemini
    from google.genai import types

    # Same limits as the Anthropic path: 10 s timeout, one retry, then classify() falls back to keywords.
    return genai.Client(api_key=os.getenv("PAKKA_LLM_API_KEY"),
                        http_options=types.HttpOptions(timeout=10_000,
                                                       retry_options=types.HttpRetryOptions(attempts=2)))


def _call_gemini(text: str) -> str:
    client = _gemini_client()      # keep a reference: a garbage-collected Client closes its HTTP connection
    resp = client.models.generate_content(
        model=llm_model(),
        contents=text,
        config={"system_instruction": SYSTEM_PROMPT, "temperature": 0},
    )
    return (resp.text or "").strip().lower()      # a blocked response has no text, which becomes unclear


def _call_anthropic(text: str) -> str:
    import anthropic  # optional dependency, only needed when PAKKA_LLM_PROVIDER=anthropic

    client = anthropic.Anthropic(api_key=os.getenv("PAKKA_LLM_API_KEY") or None, timeout=10.0, max_retries=1)
    resp = client.messages.create(
        model=llm_model(),
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
        output_config={"effort": "low"},
    )
    if resp.stop_reason == "refusal":
        return "unclear"
    return "".join(b.text for b in resp.content if b.type == "text").strip().lower()


def classify(text: str) -> tuple[str, Literal["llm", "llm_sarvam", "keywords", "none"]]:
    text = mask(text or "")
    if not text.strip():
        return "unclear", "none"
    kw = keyword_classify(text)
    if kw in DISTRESS:            # distress words always win, whatever a model says
        return kw, "keywords"
    if llm_enabled():
        try:
            label = call_llm(text)
        except Exception:          # any API error, timeout or 429 rate limit
            return kw, "keywords"
        return combine(kw, normalise(label), text), llm_source()
    return kw, "keywords"


def llm_source() -> str:
    return "llm_sarvam" if llm_provider() == "sarvam" else "llm"


def normalise(llm_label: str) -> str:
    return llm_label if llm_label in ALL_INTENTS else "unclear"


PAY_INTENT_LABELS = {"will_pay_today", "will_pay_later"}


def combine(keyword_label: str, llm_label: str, text: str) -> str:
    """Safety net for keyword + LLM labels.

    1. Distress (hardship, dispute, already_paid) from either source wins.
    2. "unclear" from either source is an abstain, not a disagreement: the other label is used.
    3. A will_pay_* label, from either source, must pass the fail-safe (payment verb, no negation).
    4. Only two confident, different, non-distress labels go to a person ("unclear").
    """
    for label in (keyword_label, llm_label):
        if label in DISTRESS:
            return label
    if keyword_label == "unclear":
        label = llm_label
    elif llm_label == "unclear" or llm_label == keyword_label:
        label = keyword_label
    else:
        return "unclear"
    if label in PAY_INTENT_LABELS and not pay_ok(text):
        return "unclear"
    return label
