"""Fixes from the 30 Oct review: distress always reaches a person, pay-today option,
every-other-day nudges, merchant-chosen contact hours, sensitive-occasion keywords."""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from pakka.merchant.guard import GuardContext, effective_window, guard
from pakka.merchant.intents import keyword_classify
from pakka.merchant.models import ConsentRecord
from pakka.merchant.synth import personas

client = TestClient(app)
P = personas()["tailor_stress"]
NOW = datetime(2026, 10, 16, 18, 0)
CONSENT = {"notice_version": "merchant-ews-v1", "language": "hi", "early_warning_alerts": True,
           "soundbox_cue": True, "repeat_offers": True}


@pytest.fixture(autouse=True)
def fresh():
    client.post("/merchant/reset")
    yield


def consent(**kw):
    base = dict(merchant_id=P.merchant.merchant_id, notice_version="merchant-ews-v1", language="hi",
                early_warning_alerts=True, soundbox_cue=True, repeat_offers=True, granted_at=NOW)
    return ConsentRecord(**{**base, **kw})


def ctx(**kw):
    base = dict(now=NOW, proactive=True, merchant=P.merchant, lender=P.lender, consent=consent(),
                blocker="edi_shortfall")
    return GuardContext(**{**base, **kw})


def test_distress_reply_reaches_a_person_without_consent():
    v = guard("human_handoff", ctx(proactive=False, consent=None, intent="hardship"))
    assert v.action == "human_handoff" and v.channel == "app_card" and v.escalated
    # proactive contact and ordinary replies still need consent
    assert guard("notify_shortfall", ctx(consent=None)).action == "no_action"
    assert guard("send_pay_link", ctx(proactive=False, consent=None, intent="will_pay_today")).action == "no_action"


def test_distress_without_consent_through_the_api():
    client.post("/merchant/tailor_stress/simulate", params={"day": 15})
    r = client.post("/merchant/tailor_stress/reply", json={"text": "papa guzar gaye, dukaan band hai"}).json()
    assert r["intent"] == "hardship" and r["action"] == "human_handoff" and r["lender_request_id"]
    assert client.get("/merchant/dashboard").json()["guard_violations"] == 0


def test_nudges_every_other_day_unless_sma_worsens():
    yesterday = date(2026, 10, 15)
    skip = guard("notify_shortfall", ctx(last_contact_day=yesterday))
    assert skip.action == "no_action" and skip.blocks == ["G3_cadence: every other day"]
    assert guard("notify_shortfall", ctx(last_contact_day=yesterday, sma_worse=True)).channel != "none"
    assert guard("notify_shortfall", ctx(last_contact_day=date(2026, 10, 14))).channel != "none"
    assert guard("no_action", ctx(blocker="cured", last_contact_day=yesterday)).channel == "app_card"


def test_tailor_long_shortfall_is_contacted_on_alternate_days():
    client.post("/merchant/tailor_stress/consent", json=CONSENT)
    sent = []
    for day in range(15, 22):
        r = client.post("/merchant/tailor_stress/simulate", params={"day": day}).json()["rescue"]
        if r["channel"] != "none":
            sent.append((day, r["action"]))
    days = [d for d, _ in sent]
    assert all(b - a >= 2 for a, b in zip(days, days[1:])), sent
    assert sent[-1][1] == "human_handoff"          # third attempt goes to a person (G7)


def test_pay_today_or_total_due():
    client.post("/merchant/tailor_stress/consent", json=CONSENT)
    client.post("/merchant/tailor_stress/simulate", params={"day": 15})
    client.post("/merchant/tailor_stress/simulate", params={"day": 16})   # ₹350 short today, ₹550 due
    r = client.post("/merchant/tailor_stress/reply", json={"text": "abhi pay karta hoon"}).json()
    assert r["template_id"] == "T_PAY_CHOICE"
    assert "₹350" in r["message_en"] and "₹550" in r["message_en"] and "am=350.00" in r["message_en"]


def test_merchant_chosen_contact_hours():
    narrow = consent(contact_window=(10, 13))
    assert effective_window(P.merchant, narrow) == (10, 13)
    assert effective_window(P.merchant, consent(contact_window=(5, 23))) == (8, 19)    # never wider than 08-19
    v = guard("notify_shortfall", ctx(consent=narrow))                                 # 18:00 is outside 10-13
    assert v.scheduled_for == datetime(2026, 10, 17, 10, 0)

    client.post("/merchant/chai_seasonal/consent", json={**CONSENT, "contact_window": [9, 12]})
    r = client.post("/merchant/chai_seasonal/simulate", params={"day": 10, "now": "18:00"}).json()["rescue"]
    assert r["scheduled_for"] == "2026-10-11T09:00:00"
    assert client.get("/merchant/chai_seasonal/consent").json()["consent"]["contact_window"] == [9, 12]


@pytest.mark.parametrize("text", ["papa guzar gaye", "ghar mein shaadi hai", "antim sanskar hai", "baadh aa gayi",
                                  "दुकान में आग लग गई", "my mother passed away", "wedding in the family"])
def test_sensitive_occasions_are_hardship(text):
    assert keyword_classify(text) == "hardship"


def test_handoff_mentions_free_debt_counselling():
    client.post("/merchant/chai_seasonal/consent", json=CONSENT)
    client.post("/merchant/chai_seasonal/simulate", params={"day": 10})
    r = client.post("/merchant/chai_seasonal/reply", json={"text": "paisa galat kaat liya"}).json()
    assert "free debt counselling" in r["message_en"] and "परामर्श" in r["message_hi"]
