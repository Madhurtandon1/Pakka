"""Loan document steps: format checks, new blockers, ladders, guard, wording and privacy.
All ID numbers here are synthetic (made-up digits with a computed check digit), never real ones."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from pakka import policy
from pakka.agent import rescue
from pakka.detector import detect
from pakka.docs_detector import NEW_BLOCKERS, detect_all
from pakka.docs_templates import CODE_TEMPLATES
from pakka.explain import TEMPLATES, explain
from pakka.idcheck import check_aadhaar, check_ifsc, check_names, check_pan, names_match
from pakka.models import Event
from tests.test_aadhaar import BAD, GOOD, with_check_digit

OLD_BLOCKERS = ["bad_photo", "wrong_format", "liveness", "digilocker", "offer_jargon", "timeout"]


def ev(step, type_, code=None, ts=0.0):
    return Event(type=type_, step=step, ts=ts, code=code)


def fails(step, *codes):
    return [ev(step, "step_view", ts=0)] + [ev(step, "check_failed", c, ts=i + 1) for i, c in enumerate(codes)]


# ---- format checks ----------------------------------------------------------------------

@pytest.mark.parametrize("pan", ["ABCDE1234F", "abcde1234f", " ABCDE 1234F "])
def test_pan_valid(pan):
    assert check_pan(pan) == {"ok": True, "code": None, "display": "ABCDE1234F"}


@pytest.mark.parametrize("pan", ["ABCD1234F", "ABCDE12345", "1BCDE1234F", "ABCDE1234", ""])
def test_pan_invalid(pan):
    assert check_pan(pan)["code"] == "PAN_FORMAT"


def test_aadhaar_valid_returns_only_last_four():
    r = check_aadhaar(f"{GOOD[:4]} {GOOD[4:8]} {GOOD[8:]}")
    assert r["ok"] and r["display"] == f"XXXX XXXX {GOOD[-4:]}" and r["last4"] == GOOD[-4:]
    assert GOOD not in str(r) and GOOD[:8] not in str(r)


@pytest.mark.parametrize("num", [BAD, GOOD[:11], with_check_digit("0" + GOOD[1:11]),
                                 with_check_digit("1" + GOOD[1:11]), "12345678901a"])
def test_aadhaar_invalid(num):
    r = check_aadhaar(num)
    assert r["code"] == "AADHAAR_FORMAT" and r["display"] is None


@pytest.mark.parametrize("ifsc,ok", [("SBIN0001234", True), ("hdfc0abc123", True), ("SBIN1001234", False),
                                     ("SBI00001234", False), ("SBIN000123", False)])
def test_ifsc(ifsc, ok):
    assert check_ifsc(ifsc)["ok"] is ok


@pytest.mark.parametrize("a,b", [("Samina Parveen", "SAMINA  PARVEEN"), ("S. Parveen", "Samina Parveen"),
                                 ("Parveen Samina", "Samina Parveen"), ("Ravi Kumar Sharma", "Ravi Sharma"),
                                 ("Mr Ravi Sharma", "RAVI SHARMA")])
def test_names_that_match(a, b):
    assert names_match(a, b)


@pytest.mark.parametrize("a,b", [("Samina Parveen", "Suresh Patel"), ("Ravi Sharma", "Ravi Verma"),
                                 ("R. S.", "Ravi Sharma"), ("", "Ravi Sharma")])
def test_names_clearly_different(a, b):
    assert not names_match(a, b)


def test_check_names_codes():
    assert check_names("Samina Parveen", "Samina Parveen", "Samina Parveen")["ok"]
    assert check_names("Samina Parveen", "Suresh Patel")["code"] == "NAME_MISMATCH"
    assert check_names("Samina Parveen", "Samina Parveen", "Ankit Rao")["code"] == "ACCOUNT_NAME_MISMATCH"


# ---- new blockers -------------------------------------------------------------------------

@pytest.mark.parametrize("events,blocker,code", [
    (fails("pan", "PAN_FORMAT", "PAN_FORMAT"), "pan_problem", "PAN_FORMAT"),
    (fails("pan", "PAN_NOT_LINKED"), "pan_problem", "PAN_NOT_LINKED"),
    (fails("kyc", "NAME_MISMATCH"), "pan_problem", "NAME_MISMATCH"),
    (fails("kyc", "OTP_NOT_RECEIVED", "OTP_NOT_RECEIVED"), "aadhaar_otp", "OTP_NOT_RECEIVED"),
    (fails("kyc", "MOBILE_NOT_LINKED"), "aadhaar_otp", "MOBILE_NOT_LINKED"),
    (fails("selfie", "FACE_MISMATCH", "FACE_MISMATCH"), "face_match", "FACE_MISMATCH"),
    (fails("bank", "IFSC_FORMAT", "IFSC_FORMAT"), "bank_verify", "IFSC_FORMAT"),
    (fails("bank", "ACCOUNT_NAME_MISMATCH"), "bank_verify", "ACCOUNT_NAME_MISMATCH"),
    (fails("bank", "PENNY_DROP_FAILED"), "bank_verify", "PENNY_DROP_FAILED"),
    (fails("mandate", "MANDATE_BANK_UNSUPPORTED"), "mandate_failed", "MANDATE_BANK_UNSUPPORTED"),
    (fails("mandate", "MANDATE_OTP_TIMEOUT", "MANDATE_OTP_TIMEOUT"), "mandate_failed", "MANDATE_OTP_TIMEOUT"),
    (fails("mandate", "NO_DEBIT_CARD"), "mandate_failed", "NO_DEBIT_CARD"),
])
def test_new_blockers_fire(events, blocker, code):
    d = detect_all(events, now=len(events))
    assert d.stalled and d.blocker == blocker and d.code == code and d.reasons


@pytest.mark.parametrize("events", [
    fails("pan", "PAN_FORMAT"), fails("kyc", "OTP_NOT_RECEIVED"), fails("selfie", "FACE_MISMATCH"),
    fails("bank", "IFSC_FORMAT"), fails("mandate", "MANDATE_OTP_TIMEOUT"),
])
def test_single_retryable_failure_is_not_a_stall(events):
    assert not detect_all(events, now=len(events)).stalled


def test_failure_then_success_is_not_a_stall():
    events = fails("pan", "PAN_FORMAT", "PAN_FORMAT") + [ev("pan", "check_ok", ts=9)]
    assert not detect_all(events, now=10).stalled


def test_liveness_rule_reused_on_selfie_step():
    events = [ev("selfie", "step_view", ts=0), ev("selfie", "liveness_failed", ts=1), ev("selfie", "liveness_failed", ts=2)]
    d = detect_all(events, now=3)
    assert d.blocker == "liveness" and d.step == "selfie"


def test_existing_rules_unchanged_by_extension():
    events = [ev("kyc", "step_view", ts=0), ev("kyc", "upload_failed", "IMG_BLUR", ts=1), ev("kyc", "upload_failed", "IMG_BLUR", ts=2)]
    assert detect_all(events, now=3) == detect(events, now=3)


# ---- ladders and guard ----------------------------------------------------------------------

@pytest.mark.parametrize("blocker,code,expected", [
    ("pan_problem", "PAN_FORMAT", ["explain_pan_issue", "human_handoff", "human_handoff"]),
    ("pan_problem", "PAN_NOT_LINKED", ["explain_pan_issue", "guide_pan_aadhaar_link", "human_handoff"]),
    ("pan_problem", "NAME_MISMATCH", ["explain_pan_issue", "human_handoff", "human_handoff"]),
    ("aadhaar_otp", "OTP_NOT_RECEIVED", ["resend_otp_tips", "switch_to_digilocker", "offline_aadhaar_xml", "human_handoff"]),
    ("aadhaar_otp", "MOBILE_NOT_LINKED", ["switch_to_video_kyc", "human_handoff", "human_handoff"]),
    ("face_match", "FACE_MISMATCH", ["face_match_tips", "guided_selfie_retake", "switch_to_video_kyc", "human_handoff"]),
    ("bank_verify", "IFSC_FORMAT", ["explain_bank_issue", "reenter_bank_details", "try_another_account", "human_handoff"]),
    ("bank_verify", "ACCOUNT_NAME_MISMATCH", ["explain_bank_issue", "try_another_account", "human_handoff"]),
    ("mandate_failed", "MANDATE_BANK_UNSUPPORTED", ["explain_mandate_issue", "switch_mandate_method", "try_another_bank", "human_handoff"]),
])
def test_escalation_ladders(blocker, code, expected):
    assert [policy.choose_for(blocker, code, n) for n in range(len(expected))] == expected


@pytest.mark.parametrize("blocker", OLD_BLOCKERS)
def test_old_blockers_choose_exactly_as_before(blocker):
    for code in (None, "IMG_BLUR", "FILE_FORMAT"):
        for n in range(5):
            assert policy.choose_for(blocker, code, n) == policy.choose(blocker, n)


def test_every_ladder_action_is_approved_for_its_blocker():
    for blocker, ladders in policy.load()["code_ladders"].items():
        if blocker.startswith("_"):
            continue
        for steps in ladders.values():
            assert set(steps) <= set(policy.allowed(blocker))


def test_guard_overrides_unlisted_action(monkeypatch):
    monkeypatch.setattr(policy, "choose_for", lambda b, c, a: "explain_kfs")
    r = rescue("j", fails("pan", "PAN_NOT_LINKED"), now=2)
    assert r.action == "human_handoff" and not r.policy_ok and r.escalated


def test_no_action_can_decide_the_loan(monkeypatch):
    assert not any(policy.decides_loan(a) for a in policy.load()["actions"])
    # even if something tried, the guard turns it into a person
    monkeypatch.setitem(policy.load()["blockers"], "pan_problem", ["approve_loan"])
    monkeypatch.setattr(policy, "choose_for", lambda b, c, a: "approve_loan")
    r = rescue("j", fails("pan", "PAN_NOT_LINKED"), now=2)
    assert r.action == "human_handoff" and not r.policy_ok


# ---- wording ----------------------------------------------------------------------------------

def _all_texts():
    for t in list(TEMPLATES.values()) + list(CODE_TEMPLATES.values()):
        yield from t.values()


def test_templates_never_say_rejected():
    banned = re.compile(r"reject|declin|अस्वीकार|रिजेक्ट|ख़ारिज|खारिज", re.I)
    assert not [t for t in _all_texts() if banned.search(t)]


def test_every_new_action_has_en_and_hi():
    for blocker in NEW_BLOCKERS:
        for action in policy.allowed(blocker):
            assert set(TEMPLATES[action]) >= {"en", "hi"}


def test_every_new_hindi_string_is_marked_for_review():
    src = (Path(__file__).resolve().parents[1] / "pakka" / "docs_templates.py").read_text(encoding="utf-8")
    hi_lines = [ln for ln in src.splitlines() if '"hi":' in ln]
    assert hi_lines and all("# HI: needs native review" in ln for ln in hi_lines)


def test_cause_specific_wording():
    assert "5 letters, 4 numbers, then 1 letter" in explain("explain_pan_issue", "en", "pan", "PAN_FORMAT")
    assert "A person will help" in explain("explain_pan_issue", "en", "kyc", "NAME_MISMATCH")
    assert "UPI AutoPay" in explain("explain_mandate_issue", "en", "mandate", "MANDATE_BANK_UNSUPPORTED")


# ---- API: privacy and one journey end to end ----------------------------------------------

def test_aadhaar_number_never_stored_or_returned():
    c = TestClient(app)
    jid = c.post("/journeys").json()["journey_id"]
    r = c.post("/idcheck", json={"kind": "aadhaar", "value": GOOD}).json()
    assert r["display"] == f"XXXX XXXX {GOOD[-4:]}" and GOOD not in str(r)
    c.post(f"/journeys/{jid}/events", json={"type": "check_ok", "step": "kyc", "ts": 1})
    dump = "\n".join(store.db.iterdump())
    assert GOOD not in dump and GOOD[:8] not in dump


def test_pan_to_mandate_journey_end_to_end():
    c = TestClient(app)
    jid = c.post("/journeys").json()["journey_id"]
    post = lambda **e: c.post(f"/journeys/{jid}/events", json=e)  # noqa: E731
    post(type="step_view", step="pan", ts=1)
    bad = c.post("/idcheck", json={"kind": "pan", "value": "ABCD1234F"}).json()["code"]
    post(type="check_failed", step="pan", ts=2, code=bad)
    post(type="check_failed", step="pan", ts=3, code=bad)
    r1 = c.get(f"/journeys/{jid}/rescue", params={"now": 4}).json()
    assert r1["detection"]["blocker"] == "pan_problem" and r1["action"] == "explain_pan_issue"
    assert "5 letters" in r1["message"]
    r2 = c.get(f"/journeys/{jid}/rescue", params={"now": 5}).json()
    assert r2["action"] == "human_handoff" and r2["escalated"]
    post(type="check_ok", step="pan", ts=6)
    assert not c.get(f"/journeys/{jid}/rescue", params={"now": 7, "dry": True}).json()["detection"]["stalled"]
    post(type="step_view", step="mandate", ts=8)
    post(type="check_failed", step="mandate", ts=9, code="MANDATE_BANK_UNSUPPORTED")
    r3 = c.get(f"/journeys/{jid}/rescue", params={"now": 10, "lang": "hi"}).json()
    assert r3["action"] == "explain_mandate_issue" and r3["lang"] == "hi" and "UPI AutoPay" in r3["message"]
    rows = [a for a in c.get("/audit", params={"limit": 50}).json() if a["journey_id"] == jid]
    assert {a["blocker"] for a in rows} == {"pan_problem", "mandate_failed"}


def test_each_cause_gets_its_own_explanation():
    """A PAN typo and a name mismatch are different problems: each is explained once."""
    c = TestClient(app)
    jid = c.post("/journeys").json()["journey_id"]
    post = lambda **e: c.post(f"/journeys/{jid}/events", json=e)  # noqa: E731
    post(type="step_view", step="pan", ts=1)
    post(type="check_failed", step="pan", ts=2, code="PAN_FORMAT")
    post(type="check_failed", step="pan", ts=3, code="PAN_FORMAT")
    assert c.get(f"/journeys/{jid}/rescue", params={"now": 4}).json()["action"] == "explain_pan_issue"
    assert c.get(f"/journeys/{jid}/rescue", params={"now": 5}).json()["action"] == "human_handoff"
    post(type="step_view", step="kyc", ts=6)
    post(type="check_failed", step="kyc", ts=7, code="NAME_MISMATCH")
    r = c.get(f"/journeys/{jid}/rescue", params={"now": 8}).json()
    assert r["action"] == "explain_pan_issue" and "don't match" in r["message"]
    assert c.get(f"/journeys/{jid}/rescue", params={"now": 9}).json()["action"] == "human_handoff"
