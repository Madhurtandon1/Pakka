"""Merchant evaluation: 5 personas + 200 randomised merchants, 30 days each.

The headline run below is unchanged (the original 5 personas, the original reply mix). The
"can't pay today" requests are measured in a separate pass (skip_pass) and reported separately.

Checks that the rules and guards behave as designed on synthetic data. Fails (exit 1) on any guard
violation or if any hardship/dispute reply is not handed to a person. These numbers say nothing about
real-world impact; that needs a pilot with a randomised holdout.
"""
import json
import random
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka.merchant.agent import Desk  # noqa: E402
from pakka.merchant.guard import DECISION_ACTIONS, effective_window, in_window, soundbox_safe  # noqa: E402
from pakka.merchant.intents import keyword_classify  # noqa: E402
from pakka.merchant.models import DISTRESS, ConsentIn  # noqa: E402
from pakka.merchant.rules import THRESHOLDS  # noqa: E402
from pakka.merchant.store import MerchantStore  # noqa: E402
from pakka.merchant.synth import DAYS, personas, random_merchants  # noqa: E402

OUT = Path(__file__).with_name("merchant_results.json")
TRACE: list = []      # every decision (merchant, time, action, channel, template, guard blocks), for comparisons

# Labelled replies (Hindi, romanised Hindi, English, Hinglish). Used both to drive the simulation and
# to measure the offline keyword classifier.
REPLIES = [
    ("kal de dunga", "will_pay_later"), ("I'll pay tomorrow", "will_pay_later"), ("parso tak bhar dunga", "will_pay_later"),
    ("कल दे दूँगा", "will_pay_later"), ("next week pakka", "will_pay_later"),
    ("abhi pay karta hoon", "will_pay_today"), ("paying now", "will_pay_today"), ("aaj shaam tak", "will_pay_today"),
    ("अभी भरता हूँ", "will_pay_today"),
    ("thoda kam kato", "request_lower_deduction"), ("please reduce the daily deduction", "request_lower_deduction"),
    ("कम कटौती कर दो", "request_lower_deduction"),
    ("date aage badhao", "request_reschedule"), ("can you reschedule", "request_reschedule"),
    ("तारीख बदल दो", "request_reschedule"),
    ("call karo", "request_callback"), ("please call me", "request_callback"), ("mujhe baat karni hai", "request_callback"),
    ("bimar tha, dukaan band thi", "hardship"), ("kal hospital jaana hai", "hardship"), ("shop closed due to flood", "hardship"),
    ("पिताजी अस्पताल में हैं", "hardship"), ("I am sick this week", "hardship"),
    ("paisa galat kaat liya", "dispute"), ("you deducted twice", "dispute"), ("यह गलत है", "dispute"),
    ("maine already pay kiya", "already_paid"), ("I already paid", "already_paid"), ("पहले ही भर दिया", "already_paid"),
    ("hmm ok", "unclear"), ("kaun bol raha hai", "unclear"),
]
ORIGINAL_PERSONAS = ["kirana_steady", "chai_seasonal", "tailor_stress", "mobile_dispute", "general_late_night"]

# "Can't pay today" replies for the separate pass. Distress always wins over a skip request.
SKIP_REPLIES = [
    ("aaj nahi de paunga, kal kaat lena", "request_skip_today"), ("aaj skip", "request_skip_today"),
    ("kal se kaat lo", "request_skip_today"), ("आज नहीं, कल काट लेना", "request_skip_today"),
    ("can't pay today, take it tomorrow", "request_skip_today"), ("aaj ka kal adjust kar do", "request_skip_today"),
    ("aaj nahi ho payega, kal kaat lena bhai", "request_skip_today"), ("today skip please, deduct tomorrow", "request_skip_today"),
    ("bimar hoon, aaj nahi, kal kaat lena", "hardship"), ("ghar mein maut ho gayi, aaj skip", "hardship"),
    ("paise nahi hain aaj", "hardship"), ("aaj nahi, kal kar dunga", "unclear"),
]


def main(seed: int = 11, write: bool = True) -> int:
    TRACE.clear()
    rng = random.Random(seed)
    book = {**{k: v for k, v in personas().items() if k in ORIGINAL_PERSONAS}, **random_merchants(200)}
    desk = Desk(MerchantStore(":memory:"), book)

    for mid in book:
        r = rng.random()
        if r < 0.08:
            continue                                           # never consented
        window = rng.choice([None, None, None, (9, 13), (10, 18), (15, 19)])
        desk.store.grant_consent(mid, ConsentIn(
            notice_version="merchant-ews-v1", early_warning_alerts=True,
            soundbox_cue=rng.random() < 0.8, repeat_offers=rng.random() < 0.7, contact_window=window),
            datetime(2026, 9, 30, 9))

    violations, rescues, latencies = [], [], []
    actions, intents_seen, blocks = Counter(), Counter(), Counter()
    distress_total = distress_handed = 0
    r1_tp = r1_fp = r1_fn = 0
    delivered_per_day = Counter()
    nudge_days: dict[str, list] = {}                 # episode -> [(date, sma)] of delivered shortfall nudges
    sma_rank = {"standard": 0, "SMA-0": 1, "SMA-1": 2, "SMA-2": 3, "NPA": 4}

    def check(mid, r, now, proactive):
        p = book[mid]
        TRACE.append((mid, now.isoformat(), r.action, r.channel, r.template_id, tuple(r.guard_blocks)))
        latencies.append(r.latency_ms)
        rescues.append(r)
        actions[r.action] += 1
        blocks.update(b.split(" ")[0].split(":")[0] for b in r.guard_blocks)
        delivered = r.channel != "none"
        if r.action in DECISION_ACTIONS:
            violations.append(f"{mid}: decision action {r.action}")
        if r.channel == "soundbox_cue" and not soundbox_safe(r.soundbox_cue_text):
            violations.append(f"{mid}: unsafe soundbox text {r.soundbox_cue_text!r}")
        if proactive and delivered:
            delivered_per_day[(mid, now.date())] += 1
            if not in_window(now, effective_window(p.merchant, desk.store.consent(mid))):
                violations.append(f"{mid}: contact outside the merchant's window at {now}")
            if r.blocker == "edi_shortfall" and r.episode_id:
                sma = desk.ledger(mid, desk.store.sim_day(mid))[-1].sma_bucket
                prev = nudge_days.setdefault(r.episode_id, [])
                if prev and (now.date() - prev[-1][0]).days < 2 and sma_rank[sma] <= sma_rank[prev[-1][1]]:
                    violations.append(f"{mid}: shortfall nudges on consecutive days")
                prev.append((now.date(), sma))
        if delivered and r.action not in ("no_action", "human_handoff") and r.action not in p.lender.allowed_actions:
            violations.append(f"{mid}: action {r.action} outside lender scope")
        consent = desk.store.consent(mid)
        own_distress = not proactive and r.intent in DISTRESS and r.action == "human_handoff"
        if delivered and not own_distress and not (consent and consent.active and consent.early_warning_alerts):
            violations.append(f"{mid}: contact without consent")
        if r.action == "show_repeat_offer" and delivered:
            today = desk.ledger(mid, desk.store.sim_day(mid))[-1]
            stress = desk.store.last_stress(mid)
            if today.total_overdue_paise > 0 or (stress and (now.date() - stress).days < THRESHOLDS["upsell_cooloff_days"]):
                violations.append(f"{mid}: offer shown with arrears or recent stress")

    for mid, p in book.items():
        for day in range(1, DAYS + 1):
            hour = rng.choice([18] * 8 + [21, 6, 12])
            now = desk.at(mid, day, f"{hour:02d}:{rng.choice([0, 30]):02d}")
            r = desk.run_day_end(mid, day, now)
            check(mid, r, now, True)

            led = desk.ledger(mid, day)[-1]
            fired = "R1_shortfall" in r.rule_ids
            truth = led.shortfall_today_paise > 0
            r1_tp += fired and truth
            r1_fp += fired and not truth
            r1_fn += truth and not fired and r.blocker != "cured"

            if rng.random() < 0.1:                             # a second run the same day: G3 must defer it
                again = desk.at(mid, day, "18:50")
                check(mid, desk.run_day_end(mid, day, again), again, True)

            unsolicited = desk.store.consent(mid) is None and r.blocker and rng.random() < 0.3
            if unsolicited or (r.channel != "none" and r.blocker in ("edi_shortfall", "sales_dip_risk")
                               and rng.random() < 0.6):
                text, _ = rng.choice(REPLIES)
                rr = desk.run_reply(mid, text, desk.at(mid, day, "18:45"), day)
                check(mid, rr, desk.at(mid, day, "18:45"), False)
                intents_seen[rr.intent] += 1
                if rr.intent in DISTRESS:
                    distress_total += 1
                    distress_handed += rr.action == "human_handoff"
                    if rr.action != "human_handoff":
                        violations.append(f"{mid}: {rr.intent} not handed off")
        o = desk.check_offer(mid, desk.at(mid, DAYS, "12:00"), DAYS)
        check(mid, o, desk.at(mid, DAYS, "12:00"), False)

    violations += [f"{m}: {n} proactive contacts on {d}" for (m, d), n in delivered_per_day.items() if n > 1]

    kw_correct = sum(keyword_classify(t) == label for t, label in REPLIES)
    latencies.sort()
    episodes = desk.store.episodes()
    res = {
        "merchants": len(book), "days": DAYS, "rescues": len(rescues),
        "guard_violations": len(violations), "violations": violations[:20],
        "detection": {
            "r1_precision": round(r1_tp / (r1_tp + r1_fp), 3) if r1_tp + r1_fp else None,
            "r1_recall": round(r1_tp / (r1_tp + r1_fn), 3) if r1_tp + r1_fn else None,
            "shortfall_days": r1_tp + r1_fn,
            "note": "vs the lender ledger itself, so this checks the rule is wired correctly",
        },
        "episodes": len(episodes),
        "episodes_cured": sum(1 for e in episodes if e["closed_day"]),
        "distress_replies": distress_total,
        "distress_handoff_rate": round(distress_handed / distress_total, 3) if distress_total else 1.0,
        "intent_keywords": {"samples": len(REPLIES), "correct": kw_correct,
                            "accuracy": round(kw_correct / len(REPLIES), 3),
                            "note": "hand-written samples, written alongside the keyword lists"},
        "actions": dict(actions), "intents": dict(intents_seen), "guard_blocks": dict(blocks),
        "latency": {"p50_ms": round(statistics.median(latencies), 2),
                    "p95_ms": round(latencies[int(0.95 * len(latencies)) - 1], 2),
                    "note": "keyword path, no network"},
    }
    skip = skip_pass()
    res["skip_requests"] = skip
    if write:
        OUT.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"merchants: {res['merchants']} x {DAYS} days, rescues: {res['rescues']}")
    print(f"guard violations: {res['guard_violations']}")
    for v in violations[:10]:
        print("  ", v)
    d = res["detection"]
    print(f"R1 vs ledger: precision {d['r1_precision']} recall {d['r1_recall']} ({d['shortfall_days']} short days)")
    print(f"episodes: {res['episodes']} opened, {res['episodes_cured']} cured")
    print(f"distress replies handed to a person: {distress_handed}/{distress_total}")
    print(f"keyword intents: {kw_correct}/{len(REPLIES)} correct")
    print(f"guard blocks: {dict(blocks)}")
    print(f"latency: p50 {res['latency']['p50_ms']} ms, p95 {res['latency']['p95_ms']} ms")
    print(f"--- \"can't pay today\" pass (reported separately): {skip['merchants']} merchants, "
          f"{skip['skip_replies']} replies, guard violations {skip['guard_violations']}")
    for v in skip["violations"][:10]:
        print("  ", v)
    print(f"    actions {skip['actions']}, callbacks booked {skip['callbacks_booked']}, "
          f"keyword labels {skip['keywords']['correct']}/{skip['keywords']['samples']}")
    ok = not violations and res["distress_handoff_rate"] == 1.0 and not skip["violations"]
    return 0 if ok else 1


def skip_pass(seed: int = 23) -> dict:
    """Separate pass for "can't pay today": every persona (incl. Verma Fruit Cart) and the 200 random
    merchants, all consented; on short days some send a skip reply. Checks, live, on every reply:
    G10 (carry-forward only for auto lenders and within their limit), the 3rd request -> a person,
    callbacks and reminders inside contact hours, distress -> a person, and no decision actions."""
    from datetime import timedelta
    from pakka.merchant import policy as mpolicy
    rng = random.Random(seed)
    book = {**personas(), **random_merchants(200)}
    desk = Desk(MerchantStore(":memory:"), book)
    for mid in book:
        desk.store.grant_consent(mid, ConsentIn(notice_version="merchant-ews-v1", early_warning_alerts=True,
                                                soundbox_cue=True, repeat_offers=True), datetime(2026, 9, 30, 9))
    violations, actions = [], Counter()
    sent = booked = 0
    for mid, p in book.items():
        cfg = p.lender.skip_day_policy
        for day in range(1, DAYS + 1):
            desk.run_day_end(mid, day)
            short = desk.ledger(mid, day)[-1].shortfall_today_paise > 0
            if not short or rng.random() > (0.95 if mid == "fruit_cart" else 0.5):
                continue
            text, want = rng.choice(SKIP_REPLIES) if mid != "fruit_cart" else SKIP_REPLIES[0]
            now = desk.at(mid, day, "18:45")
            r = desk.run_reply(mid, text, now, day)
            TRACE.append((mid, now.isoformat(), r.action, r.channel, r.template_id, tuple(r.guard_blocks)))
            sent += 1
            actions[r.action] += 1
            if r.action in DECISION_ACTIONS:
                violations.append(f"{mid}: decision action {r.action}")
            if r.intent in DISTRESS and r.action != "human_handoff":
                violations.append(f"{mid}: {r.intent} not handed off")
            if r.action == "acknowledge_carry_forward":
                if cfg.mode != "auto_carry_forward":
                    violations.append(f"{mid}: carry-forward confirmed for a request-only lender (G10)")
                if r.skip_requests_30d > cfg.max_auto_per_30_days:
                    violations.append(f"{mid}: carry-forward beyond the lender's limit (G10)")
            if r.intent == "request_skip_today" and r.skip_requests_30d >= mpolicy.skip_rules()["callback_at_request"] \
                    and r.action not in ("human_callback_booking", "human_handoff", "no_action"):
                violations.append(f"{mid}: 3rd request not passed to a person ({r.action})")
            window = effective_window(p.merchant, desk.store.consent(mid))
            if any(not in_window(sl, window) for sl in r.callback_slots):
                violations.append(f"{mid}: callback slot outside contact hours")
            if r.callback_slots and rng.random() < 0.7:
                appt = desk.book_callback(mid, r.callback_slots[0], now)
                booked += 1
                if not in_window(datetime.fromisoformat(appt["reminder_at"]), window):
                    violations.append(f"{mid}: reminder outside contact hours")
    correct = sum(keyword_classify(t) == label for t, label in SKIP_REPLIES)
    return {"merchants": len(book), "skip_replies": sent, "guard_violations": len(violations),
            "violations": violations[:20], "actions": dict(actions), "callbacks_booked": booked,
            "keywords": {"samples": len(SKIP_REPLIES), "correct": correct},
            "note": "separate pass; not part of the headline numbers above"}


if __name__ == "__main__":
    raise SystemExit(main())
