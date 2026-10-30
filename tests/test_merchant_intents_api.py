import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.merchant_api import desk
from pakka.merchant import intents
from pakka.merchant.templates import SOUNDBOX_CUE

client = TestClient(app)
CONSENT = {"notice_version": "merchant-ews-v1", "language": "hi", "early_warning_alerts": True,
           "soundbox_cue": True, "repeat_offers": True}


@pytest.mark.parametrize("text,label", [
    ("kal de dunga", "will_pay_later"), ("I'll pay tomorrow", "will_pay_later"), ("कल दे दूँगा", "will_pay_later"),
    ("abhi pay karta hoon", "will_pay_today"), ("paying now", "will_pay_today"),
    ("thoda kam kato", "request_lower_deduction"), ("please reduce the deduction", "request_lower_deduction"),
    ("date aage badhao", "request_reschedule"), ("please reschedule", "request_reschedule"),
    ("call karo", "request_callback"), ("mujhe baat karni hai", "request_callback"),
    ("bimar tha, dukaan band thi", "hardship"), ("अस्पताल में हूँ", "hardship"),
    ("paisa galat kaat liya", "dispute"), ("you deducted twice", "dispute"),
    ("maine already pay kiya", "already_paid"), ("पहले ही भर दिया", "already_paid"),
    ("hmm", "unclear"),
])
def test_keyword_intents(text, label):
    assert intents.keyword_classify(text) == label


def test_distress_wins_over_other_words():
    assert intents.keyword_classify("kal hospital jaana hai") == "hardship"
    assert intents.keyword_classify("will pay tomorrow, deduction was wrong") == "dispute"


def test_llm_invalid_label_becomes_unclear(monkeypatch):
    monkeypatch.delenv("PAKKA_LLM_PROVIDER", raising=False)      # generic LLM path, source "llm"
    monkeypatch.setattr(intents, "llm_enabled", lambda: True)
    monkeypatch.setattr(intents, "call_llm", lambda text: "approve_my_loan")
    assert intents.normalise("approve_my_loan") == "unclear"
    assert intents.classify("kal de dunga") == ("will_pay_later", "llm")    # LLM unclear abstains: keywords stand
    assert intents.classify("hmm ok") == ("unclear", "llm")


def test_llm_error_falls_back_to_keywords(monkeypatch):
    def boom(text):
        raise RuntimeError("network down")
    monkeypatch.setattr(intents, "llm_enabled", lambda: True)
    monkeypatch.setattr(intents, "call_llm", boom)
    assert intents.classify("kal de dunga") == ("will_pay_later", "keywords")


def test_pii_is_masked_before_the_llm_sees_it(monkeypatch):
    seen = []
    monkeypatch.setattr(intents, "llm_enabled", lambda: True)
    monkeypatch.setattr(intents, "call_llm", lambda text: seen.append(text) or "request_callback")
    intents.classify("call me on 9876543210, PAN ABCDE1234F")
    assert seen and "9876543210" not in seen[0] and "[PHONE]" in seen[0] and "[PAN]" in seen[0]


def test_no_llm_configured_means_offline_keywords(monkeypatch):
    monkeypatch.delenv("PAKKA_LLM_PROVIDER", raising=False)
    assert intents.classify("call karo") == ("request_callback", "keywords")


@pytest.fixture(autouse=True)
def fresh():
    client.post("/merchant/reset")
    yield


def test_full_merchant_flow_with_consent_and_audit():
    assert client.post("/merchant/chai_seasonal/simulate", params={"day": 10}).json()["rescue"]["action"] == "no_action"

    assert client.post("/merchant/chai_seasonal/consent", json={**CONSENT, "notice_version": "old"}).status_code == 400
    assert client.post("/merchant/chai_seasonal/consent", json=CONSENT).status_code == 200

    out = client.post("/merchant/chai_seasonal/simulate", params={"day": 10, "now": "18:00"}).json()
    r = out["rescue"]
    assert r["action"] == "notify_shortfall" and r["channel"] == "soundbox_cue"
    assert r["soundbox_cue_text"] == SOUNDBOX_CUE["hi"] and "₹400" in r["message_en"]

    again = client.post("/merchant/chai_seasonal/simulate", params={"day": 10, "now": "18:30"}).json()["rescue"]
    assert again["channel"] == "none" and again["guard_blocks"][0].startswith("G3_daily_cap")

    rep = client.post("/merchant/chai_seasonal/reply", json={"text": "kal de dunga"}).json()
    assert rep["intent"] == "will_pay_later" and rep["action"] == "schedule_reminder"
    assert "08:00" in rep["message_en"]          # 20:00 is outside contact hours, so the reminder moves

    cured = client.post("/merchant/chai_seasonal/simulate", params={"day": 11}).json()["rescue"]
    assert cured["blocker"] == "cured" and cured["template_id"] == "T_CURED"

    rows = client.get("/merchant/audit", params={"merchant_id": "chai_seasonal"}).json()
    before, *after = rows[::-1]
    assert before["consent_version"] is None and before["guard_blocks"] == ["G1_consent"]
    assert after and all(row["consent_version"] == "merchant-ews-v1" for row in after)
    assert client.get("/merchant/dashboard").json()["guard_violations"] == 0


def test_late_night_deferral_and_withdrawal():
    client.post("/merchant/general_late_night/consent", json=CONSENT)
    r = client.post("/merchant/general_late_night/simulate", params={"day": 6, "now": "21:30"}).json()["rescue"]
    assert r["scheduled_for"] == "2026-10-07T08:00:00" and r["guard_blocks"][0].startswith("G2_hours")
    assert client.delete("/merchant/general_late_night/consent").json()["withdrawn"]
    r = client.post("/merchant/general_late_night/simulate", params={"day": 7, "now": "09:00"}).json()["rescue"]
    assert r["action"] == "no_action" and r["guard_blocks"] == ["G1_consent"]


def test_hardship_hands_off_and_blocks_offers():
    client.post("/merchant/tailor_stress/consent", json=CONSENT)
    client.post("/merchant/tailor_stress/simulate", params={"day": 15})
    r = client.post("/merchant/tailor_stress/reply", json={"text": "bimar tha, dukaan band thi"}).json()
    assert r["action"] == "human_handoff" and r["escalated"] and r["lender_request_id"]
    assert "Grievance officer" in r["message_en"]
    later = client.post("/merchant/tailor_stress/simulate", params={"day": 16}).json()["rescue"]
    assert later["action"] == "no_action" and later["guard_blocks"] == ["G8_stopped"]
    offer = client.get("/merchant/tailor_stress/offers").json()
    assert offer["action"] == "no_action" and "G4_no_upsell" in offer["guard_blocks"]
    reqs = client.get("/merchant/lender/requests").json()
    assert reqs[0]["status"] == "pending_lender_contact"


def test_steady_merchant_is_never_contacted_and_can_see_offers():
    client.post("/merchant/kirana_steady/consent", json=CONSENT)
    for day in range(1, 31):
        assert client.post("/merchant/kirana_steady/simulate", params={"day": day}).json()["rescue"]["blocker"] is None
    assert client.get("/merchant/kirana_steady/offers").json()["action"] == "show_repeat_offer"


def test_soundbox_speak_rejects_anything_but_the_cue(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    bad = client.post("/merchant/chai_seasonal/soundbox/speak", json={"text": "₹400 overdue", "lang": "hi"})
    assert bad.status_code == 400
    ok = client.post("/merchant/chai_seasonal/soundbox/speak", json={"text": SOUNDBOX_CUE["hi"], "lang": "hi"})
    assert ok.status_code == 503          # allowed, but no TTS key in tests


def test_pages_and_unknown_merchant():
    assert client.get("/merchant").status_code == 200
    assert len(client.get("/merchant/personas").json()["personas"]) == len(desk.book) == 5
    assert client.post("/merchant/nope/simulate", params={"day": 1}).status_code == 404
