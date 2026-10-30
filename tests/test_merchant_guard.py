import re
from datetime import date, datetime

import pytest

from pakka.merchant.guard import GuardContext, guard, soundbox_guard, soundbox_safe
from pakka.merchant.models import ConsentRecord
from pakka.merchant.policy import PolicyViolation
from pakka.merchant.synth import LENDERS, personas
from pakka.merchant.templates import SOUNDBOX_CUE, TEMPLATES

P = personas()["chai_seasonal"]
NOW = datetime(2026, 10, 10, 18, 0)


def consent(**kw):
    base = dict(merchant_id="chai_seasonal", notice_version="merchant-ews-v1", language="hi",
                early_warning_alerts=True, soundbox_cue=True, repeat_offers=True, granted_at=NOW)
    return ConsentRecord(**{**base, **kw})


def ctx(**kw):
    base = dict(now=NOW, proactive=True, merchant=P.merchant, lender=P.lender, consent=consent(),
                blocker="edi_shortfall")
    return GuardContext(**{**base, **kw})


def test_g1_no_or_withdrawn_consent_means_no_action():
    assert guard("notify_shortfall", ctx(consent=None)).action == "no_action"
    v = guard("notify_shortfall", ctx(consent=consent(withdrawn_at=NOW)))
    assert v.action == "no_action" and v.blocks == ["G1_consent"] and v.channel == "none"


def test_g2_late_night_is_deferred_to_morning():
    v = guard("notify_shortfall", ctx(now=datetime(2026, 10, 10, 21, 30)))
    assert v.action == "notify_shortfall" and v.channel == "none"
    assert v.scheduled_for == datetime(2026, 10, 11, 8, 0) and v.blocks[0].startswith("G2_hours")
    early = guard("notify_shortfall", ctx(now=datetime(2026, 10, 10, 6, 0)))
    assert early.scheduled_for == datetime(2026, 10, 10, 8, 0)


def test_g3_second_contact_same_day_is_deferred():
    v = guard("notify_shortfall", ctx(contacts_today=1))
    assert v.scheduled_for == datetime(2026, 10, 11, 8, 0) and v.blocks[0].startswith("G3_daily_cap")


def test_g4_no_offer_with_arrears_or_recent_stress():
    off = dict(proactive=False, blocker="offer_request")
    assert guard("show_repeat_offer", ctx(**off, total_overdue_paise=1)).blocks == ["G4_no_upsell"]
    assert guard("show_repeat_offer", ctx(**off, last_stress=date(2026, 8, 1))).action == "no_action"
    clean = guard("show_repeat_offer", ctx(**off, last_stress=date(2026, 6, 1)))
    assert clean.action == "show_repeat_offer" and clean.channel == "app_card"
    assert guard("show_repeat_offer", ctx(**off, consent=consent(repeat_offers=False))).blocks == ["G1_consent"]


def test_g5_soundbox_only_plays_the_neutral_cue():
    for bad in ["Your EDI of ₹600 is overdue", "Bakaya 400", "Loan payment due", "You have 1 message"]:
        assert not soundbox_safe(bad)
        text, channel, blocks = soundbox_guard(bad, "soundbox_cue", "en", consent())
        assert text == SOUNDBOX_CUE["en"] and blocks
    assert all(soundbox_safe(t) for t in SOUNDBOX_CUE.values())
    text, channel, _ = soundbox_guard(SOUNDBOX_CUE["hi"], "soundbox_cue", "hi", consent(soundbox_cue=False))
    assert text is None and channel == "app_card"


def test_g6_action_outside_lender_scope_goes_to_a_person():
    bank_b = personas()["mobile_dispute"]
    v = guard("route_lower_deduction_request", ctx(proactive=False, lender=bank_b.lender, merchant=bank_b.merchant))
    assert v.action == "human_handoff" and not v.policy_ok and v.escalated
    assert v.blocks[0].startswith("G6_lender_scope")


def test_g7_third_attempt_hands_off():
    v = guard("notify_shortfall", ctx(attempts=3))
    assert v.action == "human_handoff" and "G7_attempts" in v.blocks and v.stop_episode
    assert guard("notify_shortfall", ctx(attempts=2)).action == "notify_shortfall"


@pytest.mark.parametrize("intent", ["hardship", "dispute", "already_paid"])
def test_g8_distress_hands_off_and_stops_the_episode(intent):
    v = guard("schedule_callback", ctx(proactive=False, intent=intent))
    assert v.action == "human_handoff" and v.stop_episode and "G8_distress" in v.blocks
    later = guard("notify_shortfall", ctx(episode_stopped=True))
    assert later.action == "no_action" and later.blocks == ["G8_stopped"]


def test_g9_decisions_are_never_allowed():
    for action in ["approve_loan", "waive_charges", "reschedule_now", "made_up_action"]:
        with pytest.raises(PolicyViolation):
            guard(action, ctx())


def test_soundbox_channel_needs_a_device_and_consent():
    assert guard("notify_shortfall", ctx()).channel == "soundbox_cue"
    assert guard("notify_shortfall", ctx(consent=consent(soundbox_cue=False))).channel == "app_card"
    assert guard("send_pay_link", ctx(proactive=False)).channel == "app_card"


def test_templates_are_bilingual_and_hold_no_computed_amounts():
    for tid, t in TEMPLATES.items():
        assert set(t) == {"en", "hi"}, tid
        for text in t.values():
            static = re.sub(r"\{\w+\}", "", text)
            assert not re.search(r"[\d₹%]", static), (tid, text)
    assert LENDERS["demo_nbfc_a"].penal_charges_note["en"].startswith("Charges as per")
