"""Blind check of the merchant intent classifier on replies written by someone who never saw the keywords.

1. A teammate who did NOT write pakka/merchant/intents.py writes about 50 replies in
   eval/intent_holdout.json, without opening that file: Hindi, Hinglish, English, typos, mixed signals.
   Format: [{"text": "kal tak de dunga bhai", "label": "will_pay_later"}, ...]
   Labels: will_pay_today, will_pay_later, request_lower_deduction, request_reschedule,
   request_callback, dispute, hardship, already_paid, unclear
2. Run:  python eval/intent_holdout.py [path/to/set.json]     (default: eval/intent_holdout.json)
   With an LLM configured, it is scored too: alone, and combined with the keywords exactly as classify()
   does it (distress from either wins; keyword "unclear" abstains; any other disagreement goes to a person).
     Anthropic: PAKKA_LLM_PROVIDER=anthropic, PAKKA_LLM_API_KEY  (pip install anthropic)
     Gemini:    PAKKA_LLM_PROVIDER=gemini, PAKKA_LLM_API_KEY, PAKKA_LLM_MODEL  (pip install google-genai)
     Sarvam:    PAKKA_LLM_PROVIDER=sarvam, SARVAM_API_KEY (read from .env), model sarvam-105b  (pip install sarvamai)
   Optional second argument: where to write the results (default <set>_results.json).
   Calls are spaced PAKKA_LLM_PAUSE seconds apart (default 4.5 for Gemini, to stay under the free-tier
   rate limit; 1 for Sarvam; 0 for Anthropic). On a rate-limit error the script waits and retries once. Each reply is sent once. An API error, including a 429, falls back to
   keywords in the combined score, as in production, and is counted as an LLM error.
   Answers are saved per provider and model as they arrive (<set>_llm_<provider>_<model>.json), so a run
   cut short by a daily quota can be resumed later: only the missing replies are sent.

Headline metric: distress replies that received an automated payment message (will_pay_*). It must be 0.

Report both numbers as they come out. This script is not a CI gate.
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka.merchant import intents  # noqa: E402
from pakka.merchant.models import ALL_INTENTS, DISTRESS  # noqa: E402

DEFAULT_DATA = Path(__file__).with_name("intent_holdout.json")
PAY_NUDGE = {"will_pay_today", "will_pay_later"}


PERSON = DISTRESS | {"unclear", "request_callback"}   # handoff, or a callback from the lender's team
RETRY_WAIT = float(os.getenv("PAKKA_LLM_RETRY_WAIT", "10"))


def load_env() -> None:
    """Read .env (if present) without overriding variables already set. Values are never printed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env", override=False)


def is_rate_limit(exc: Exception) -> bool:
    """429 rate limit, or 503 overload (Sarvam's docs say to retry 503 with backoff)."""
    codes = {getattr(exc, "status_code", None), getattr(exc, "code", None)}
    return bool(codes & {429, 503}) or "TooManyRequests" in type(exc).__name__ or "RateLimit" in type(exc).__name__


def score(rows, classify):
    misses, correct, distress_missed, distress_auto, nudged = [], 0, 0, 0, []
    for r in rows:
        got = classify(r["text"])
        if r["label"] in DISTRESS and got in PAY_NUDGE:
            nudged.append(r["text"])
        if got == r["label"]:
            correct += 1
        else:
            misses.append({"text": r["text"], "want": r["label"], "got": got})
            if r["label"] in DISTRESS and got not in DISTRESS:
                distress_missed += 1
                distress_auto += got not in PERSON
    n_distress = sum(r["label"] in DISTRESS for r in rows)
    handoffs = sum(1 for r in rows if r["label"] in DISTRESS and classify(r["text"]) in DISTRESS)
    return {"distress_got_payment_nudge": len(nudged), "nudged": nudged,
            "distress_proper_handoff": handoffs,
            "n": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 3),
            "distress_samples": n_distress, "distress_missed": distress_missed,
            "distress_reaching_a_person": n_distress - distress_auto, "misses": misses}


def llm_pause() -> float:
    default = {"gemini": "4.5", "sarvam": "1"}.get(intents.llm_provider(), "0")
    return float(os.getenv("PAKKA_LLM_PAUSE", default))


def ask_llm(rows, pause: float, sleep=time.sleep, cache_path: Path | None = None) -> dict:
    """One LLM call per reply (masked first, like production). Returns text -> label, or None on error.

    With cache_path, earlier answers are reused and each new answer is saved immediately.
    """
    saved = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path and cache_path.exists() else {}
    answers, calls = {}, 0
    for i, r in enumerate(rows):
        if saved.get(r["text"]) is not None:
            answers[r["text"]] = saved[r["text"]]
            continue
        if calls and pause:
            sleep(pause)
        calls += 1
        for attempt in (1, 2):
            try:
                answers[r["text"]] = intents.normalise(intents.call_llm(intents.mask(r["text"])))
                break
            except Exception as exc:                # includes 429 rate limits
                answers[r["text"]] = None
                if attempt == 1 and is_rate_limit(exc):
                    print(f"  rate limited or overloaded on reply {i + 1}; waiting {RETRY_WAIT:g}s and retrying once")
                    sleep(RETRY_WAIT)
                    continue
                code = getattr(exc, "code", None) or getattr(exc, "status_code", "")
                print(f"  LLM error on reply {i + 1}: {type(exc).__name__} {code}".rstrip())
                break
        if cache_path and answers[r["text"]] is not None:
            saved[r["text"]] = answers[r["text"]]
            cache_path.write_text(json.dumps(saved, indent=1, ensure_ascii=False), encoding="utf-8")
    if saved:
        print(f"  {len(rows) - calls} answers reused from {cache_path.name}, {calls} calls made")
    return answers


def combined_label(text: str, answers: dict) -> str:
    """Exactly what classify() returns, using the cached LLM answer."""
    kw = intents.keyword_classify(intents.mask(text))
    if kw in DISTRESS or answers.get(text) is None:
        return kw
    return intents.combine(kw, answers[text], intents.mask(text))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    load_env()
    DATA = Path(argv[0]) if argv else DEFAULT_DATA
    OUT = Path(argv[1]) if len(argv) > 1 else DATA.with_name(DATA.stem + "_results.json")
    if not DATA.exists():
        print(__doc__)
        print(f"No {DATA.name} yet. Ask a teammate to write it (see step 1 above).")
        return 0
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    bad = [r for r in rows if r.get("label") not in ALL_INTENTS]
    if bad:
        print("Unknown labels:", bad[:5])
        return 1

    res = {"labels": dict(Counter(r["label"] for r in rows)),
           "keywords": score(rows, intents.keyword_classify)}
    if intents.llm_enabled():
        pause = llm_pause()
        print(f"Scoring {intents.llm_provider()} / {intents.llm_model()} on {len(rows)} replies, "
              f"{pause:g}s between calls...")
        intents.LLM_USAGE.clear()
        model_tag = "".join(c if c.isalnum() or c in "-." else "_" for c in intents.llm_model())
        answers = ask_llm(rows, pause, cache_path=DATA.with_name(f"{DATA.stem}_llm_{intents.llm_provider()}_{model_tag}.json"))
        res["llm_provider"], res["llm_model"] = intents.llm_provider(), intents.llm_model()
        res["blindness"] = ("Keywords are NOT blind on v1: they were tuned after seeing it. The LLM IS blind on v1: "
                            "its prompt contains none of these replies and no rule learned from them.")
        res["llm_errors"] = sum(a is None for a in answers.values())
        res["llm_answered"] = len(rows) - res["llm_errors"]
        res["llm"] = score(rows, lambda t: answers[t] if answers[t] is not None else "unclear")
        res["combined"] = score(rows, lambda t: combined_label(t, answers))
        res["llm_usage_tokens"] = dict(intents.LLM_USAGE) or "not reported (or all answers reused from cache)"
    OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    names = {"keywords": "keywords alone", "llm": f"{res.get('llm_provider', 'llm')} alone", "combined": "combined"}
    for name in ("keywords", "llm", "combined"):
        if name in res:
            s = res[name]
            print(f"{names[name]:16} accuracy {s['correct']}/{s['n']} = {s['accuracy']:.0%}   "
                  f"distress given a payment nudge: {s['distress_got_payment_nudge']}   "
                  f"distress handed off properly: {s['distress_proper_handoff']}/{s['distress_samples']}   "
                  f"(reaching a person incl. callback: {s['distress_reaching_a_person']}/{s['distress_samples']})")
    if "blindness" in res:
        print(res["blindness"])
        print(f"LLM token usage: {res['llm_usage_tokens']}")
    if "llm" in res:
        if res["llm_errors"]:
            print(f"LLM errors (rate limit or other): {res['llm_errors']}. Those replies count as unclear for the "
                  f"LLM alone and fall back to keywords in the combined score.")
    else:
        print("LLM not scored: set PAKKA_LLM_PROVIDER (anthropic, gemini or sarvam) and its key "
              "(PAKKA_LLM_API_KEY, or SARVAM_API_KEY for sarvam); install the matching SDK.")
    for name in ("keywords", "llm", "combined"):
        if name in res and res[name]["misses"]:
            print(f"misses ({names[name]}), also in {OUT.name}:")
            for m in res[name]["misses"]:
                print(f"  {m['want']:<24} got {m['got']:<24} {m['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
