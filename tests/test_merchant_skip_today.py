""""Can't pay today": keywords, the ladder, rolling counts, G10, stress flag, callbacks and templates.

Principle under test: Pakka explains the lender's carry-forward and applies only the lender's preset
limit; it never decides to skip a payment."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pakka.merchant import policy
from pakka.merchant.agent import Desk, callback_slots, Facts
from pakka.merchant.guard import GuardContext, guard, in_window
from pakka.merchant.intents import combine, keyword_classify, normalise
from pakka.merchant.models import ConsentIn, SkipDayPolicy
from pakka.merchant.synth import LENDERS
from pakka.merchant.templates import TEMPLATES

SKIP = "aaj nahi de paunga, kal kaat lena"
ROOT = Path(__file__).resolve().parents[1]


def desk_with(mid="fruit_cart", window=None):
    d = Desk()
    d.store.grant_consent(mid, ConsentIn(notice_version="merchant-ews-v1", early_warning_alerts=True,
                                         soundbox_cue=True, repeat_offers=True, contact_window=window),
                          d.at(mid, 1, "09:00"))
    return d


# ---- keywords, in the required order -----------------------------------------------------------

@pytest.mark.parametrize("text", ["aaj nahi de paunga kal kaat lena", "aaj skip", "kal se kaat lo",
                                  "आज नहीं, कल काट लेना", "can't pay today, take it tomorrow",
                                  "aaj ka kal adjust kar do"])
def test_skip_phrases(text):
    assert keyword_classify(text) == "request_skip_today"


@pytest.mark.parametrize("text", ["bimar hoon, aaj nahi, kal kaat lena", "ghar mein maut ho gayi, aaj skip",
                                  "flood aaya, aaj nahi, kal kaat lo"])
def test_distress_is_checked_before_skip(text):
    assert keyword_classify(text) == "hardship"


@pytest.mark.parametrize("text", ["paise nahi hain", "bikri nahi hui"])
def test_negation_with_money_is_still_hardship(text):
    assert keyword_classify(text) == "hardship"


@pytest.mark.parametrize("text,label", [("aaj nahi, kal kar dunga", "unclear"), ("aaj kaat lo", "unclear"),
                                        ("kal de dunga", "will_pay_later"), ("aaj nahi de paunga", "unclear")])
def test_one_marker_alone_is_not_a_skip(text, label):
    assert keyword_classify(text) == label


def test_blind_v1_replies_never_become_skip_requests():
    rows = json.loads((ROOT / "eval" / "intent_holdout.json").read_text(encoding="utf-8"))
    rows = rows["replies"] if isinstance(rows, dict) else rows
    assert not [r["text"] for r in rows if keyword_classify(r["text"]) == "request_skip_today"]


def test_llm_label_is_accepted_and_combined():
    assert normalise("request_skip_today") == "request_skip_today"
    assert combine("unclear", "request_skip_today", SKIP) == "request_skip_today"
    assert combine("hardship", "request_skip_today", SKIP) == "hardship"


# ---- the ladder ---------------------------------------------------------------------------------

def test_fruit_cart_ladder_and_stress_flag():
    d = desk_with()
    got = []
    for day in (5, 6, 7):
        d.run_day_end("fruit_cart", day)
        got.append(d.run_reply("fruit_cart", SKIP, day=day))
    assert [r.action for r in got] == ["acknowledge_carry_forward", "acknowledge_carry_forward", "human_callback_booking"]
    assert [r.skip_requests_30d for r in got] == [1, 2, 3]
    assert "as your lender's plan allows" in got[0].message_en and "Charges as per your loan agreement." in got[0].message_en
    assert "Is everything okay?" in got[2].message_en and got[2].callback_slots
    assert d.store.last_stress("fruit_cart") == d.date_of("fruit_cart", 6)   # flagged on the 2nd request
    assert "G4_no_upsell" in d.check_offer("fruit_cart", day=8).guard_blocks


def test_first_request_sets_no_stress_flag():
    d = desk_with()
    d.run_day_end("fruit_cart", 5)
    d.run_reply("fruit_cart", SKIP, day=5)
    assert d.store.flags("fruit_cart") == []


def test_same_day_repeat_counts_once():
    d = desk_with()
    d.run_day_end("fruit_cart", 5)
    a = d.run_reply("fruit_cart", SKIP, day=5)
    b = d.run_reply("fruit_cart", "aaj skip", day=5)
    assert a.skip_requests_30d == b.skip_requests_30d == 1


def test_request_only_lender_routes_without_promising():
    d = desk_with("mobile_dispute")
    d.run_day_end("mobile_dispute", 8)
    r = d.run_reply("mobile_dispute", SKIP, day=8)
    assert r.action == "route_skip_request" and r.lender_request_id
    assert "They will decide" in r.message_en
    assert not re.search(r"approved|skipped|will be collected", r.message_en, re.I)
    assert d.store.requests()[0]["kind"] == "route_skip_request"


def test_rolling_window_forgets_old_requests():
    d = desk_with()
    start = d.at("fruit_cart", 1, "18:05")
    d.run_reply("fruit_cart", SKIP, start, day=1)
    d.run_reply("fruit_cart", SKIP, start + timedelta(days=1), day=2)
    r = d.run_reply("fruit_cart", SKIP, start + timedelta(days=30), day=30)   # 1 Oct is out of the window, 2 Oct is in
    assert r.skip_requests_30d == 2 and r.action == "acknowledge_carry_forward"


def test_three_requests_spread_out_still_reach_a_person():
    d = desk_with()
    start = d.at("fruit_cart", 1, "18:05")
    for gap in (0, 5, 10):
        r = d.run_reply("fruit_cart", SKIP, start + timedelta(days=gap), day=1 + gap)
    assert r.action == "human_callback_booking"


def test_consecutive_days_rule():
    a = LENDERS["demo_nbfc_a"].model_copy(update={"skip_day_policy": SkipDayPolicy(mode="auto_carry_forward",
                                                                                   max_auto_per_30_days=10)})
    assert policy.skip_action(a, requests_30d=2, consecutive_days=3) == "human_callback_booking"
    assert policy.skip_action(a, requests_30d=2, consecutive_days=2) == "acknowledge_carry_forward"


def test_lender_limit_is_the_lenders():
    one = LENDERS["demo_nbfc_a"].model_copy(update={"skip_day_policy": SkipDayPolicy(mode="auto_carry_forward",
                                                                                     max_auto_per_30_days=1)})
    assert policy.skip_action(one, 1, 1) == "acknowledge_carry_forward"
    assert policy.skip_action(one, 2, 1) == "human_callback_booking"


# ---- G10 ----------------------------------------------------------------------------------------

def _ctx(lender, n, d=None):
    d = d or desk_with()
    return GuardContext(now=d.at("fruit_cart", 5, "18:05"), proactive=False,
                        merchant=d.persona("fruit_cart").merchant, lender=lender,
                        consent=d.store.consent("fruit_cart"), intent="request_skip_today", skip_requests_30d=n)


def test_g10_blocks_carry_forward_for_request_only_lenders():
    v = guard("acknowledge_carry_forward", _ctx(LENDERS["demo_bank_b"], 1))
    assert v.action == "route_skip_request" and any(b.startswith("G10") for b in v.blocks)


def test_g10_blocks_carry_forward_over_the_limit():
    v = guard("acknowledge_carry_forward", _ctx(LENDERS["demo_nbfc_a"], 3))
    assert v.action == "human_callback_booking" and v.escalated and v.stop_episode
    assert any(b.startswith("G10") for b in v.blocks)


def test_g10_allows_carry_forward_within_the_limit():
    v = guard("acknowledge_carry_forward", _ctx(LENDERS["demo_nbfc_a"], 2))
    assert v.action == "acknowledge_carry_forward" and not v.blocks


# ---- distress, consent --------------------------------------------------------------------------

def test_distress_reason_chip_goes_to_a_person():
    d = desk_with()
    d.run_day_end("fruit_cart", 5)
    r = d.run_reply("fruit_cart", SKIP, day=5, reason="illness")
    assert r.intent == "hardship" and r.action == "human_handoff"


def test_plain_reason_chip_is_optional_and_not_distress():
    d = desk_with()
    d.run_day_end("fruit_cart", 5)
    assert d.run_reply("fruit_cart", SKIP, day=5, reason="low_sales").action == "acknowledge_carry_forward"


def test_distress_in_free_text_goes_to_a_person():
    d = desk_with()
    d.run_day_end("fruit_cart", 5)
    r = d.run_reply("fruit_cart", "Aaj nahi de paunga, kal kaat lena. Kaaran: papa hospital mein hain", day=5)
    assert r.action == "human_handoff"


def test_no_consent_means_no_automatic_reply():
    d = Desk()
    d.run_day_end("fruit_cart", 5)
    r = d.run_reply("fruit_cart", SKIP, day=5)
    assert r.action == "no_action" and r.channel == "none"


# ---- callbacks inside contact hours -------------------------------------------------------------

def test_callback_slots_are_inside_the_merchants_hours():
    d = desk_with(window=(10, 13))
    for day in (5, 6, 7):
        d.run_day_end("fruit_cart", day)
        r = d.run_reply("fruit_cart", SKIP, day=day)
    assert r.callback_slots and all(in_window(s, (10, 13)) for s in r.callback_slots)


def test_booking_inside_hours_creates_appointment_and_reminder():
    d = desk_with()
    for day in (5, 6, 7):
        d.run_day_end("fruit_cart", day)
        r = d.run_reply("fruit_cart", SKIP, day=day)
    appt = d.book_callback("fruit_cart", r.callback_slots[0])
    assert appt["status"] == "booked" and appt["reminder_at"] == appt["slot"]
    assert in_window(datetime.fromisoformat(appt["reminder_at"]), (8, 19))
    assert "will call you at" in appt["message_en"]


@pytest.mark.parametrize("hour", [7, 19, 21])
def test_booking_outside_hours_is_refused(hour):
    d = desk_with()
    d.store.set_sim_day("fruit_cart", 7)
    with pytest.raises(ValueError):
        d.book_callback("fruit_cart", d.at("fruit_cart", 8, f"{hour:02d}:00"))
    assert d.store.appointments() == []


def test_api_flow_with_lender_view():
    from app.merchant_api import desk
    c = TestClient(__import__("app.main", fromlist=["app"]).app)
    c.post("/merchant/reset")
    c.post("/merchant/fruit_cart/consent", json={"notice_version": "merchant-ews-v1", "early_warning_alerts": True,
                                                  "soundbox_cue": True, "repeat_offers": True})
    for day in (5, 6, 7):
        c.post(f"/merchant/fruit_cart/simulate?day={day}&now=18:00")
        r = c.post("/merchant/fruit_cart/reply", json={"text": SKIP, "reason": "low_sales" if day == 5 else None}).json()
    assert r["action"] == "human_callback_booking"
    bad = c.post("/merchant/fruit_cart/callbacks", json={"slot": r["callback_slots"][0][:11] + "21:00:00"})
    assert bad.status_code == 400
    ok = c.post("/merchant/fruit_cart/callbacks", json={"slot": r["callback_slots"][0]})
    assert ok.status_code == 200
    s = c.get("/merchant/fruit_cart/skips").json()
    assert s["requests_30d"] == 3 and s["flag"] == "Asked to skip 3 times this month — callback booked"
    assert c.get("/merchant/lender/appointments").json()[0]["merchant_id"] == "fruit_cart"
    c.post("/merchant/reset")
    assert desk.store.appointments() == []


# ---- templates ----------------------------------------------------------------------------------

@pytest.mark.parametrize("tid", ["T_SKIP_ACK", "T_SKIP_ROUTED", "T_SKIP_CALLBACK", "T_CALLBACK_BOOKED"])
def test_new_templates_in_both_languages(tid):
    assert TEMPLATES[tid]["en"] and TEMPLATES[tid]["hi"]
    assert not re.search(r"reject|approved|waive", TEMPLATES[tid]["en"], re.I)


def test_new_hindi_strings_are_marked_for_review():
    src = (ROOT / "pakka" / "merchant" / "templates.py").read_text(encoding="utf-8")
    block = src[src.index('"T_SKIP_ACK"'):src.index('"T_REPEAT_OFFER"')]
    hi = [ln for ln in block.splitlines() if "# HI:" in ln]
    assert len(hi) == 4
