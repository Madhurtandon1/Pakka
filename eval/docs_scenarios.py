"""Hand-written scenarios for the loan document steps (PAN, Aadhaar OTP, selfie, bank, auto-pay, income documents).

Reported separately: these are NOT part of the 30/30 scripted scenarios or the 0.85 held-out score.
Like the 30/30, they were written alongside the rules, so they check the logic, not real-world accuracy.

    python eval/docs_scenarios.py      # writes eval/docs_results.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pakka.agent import rescue  # noqa: E402
from pakka.models import Event  # noqa: E402

OUT = ROOT / "eval" / "docs_results.json"


def run(step, *items):
    """items: failure codes, or "ok" for a success, or "live" for a failed face check."""
    events = [Event(type="step_view", step=step, ts=0)]
    for i, it in enumerate(items, 1):
        if it == "ok":
            events.append(Event(type="check_ok", step=step, ts=i))
        elif it == "live":
            events.append(Event(type="liveness_failed", step=step, ts=i))
        elif it.startswith("doc:"):
            code = it[4:] or None
            events.append(Event(type="doc_failed" if code else "doc_ok", step=step, ts=i, code=code))
        else:
            events.append(Event(type="check_failed", step=step, ts=i, code=it))
    return events


# (name, events, attempts so far, expected blocker or None, expected action or None)
SCENARIOS = [
    ("PAN typed wrong twice", run("pan", "PAN_FORMAT", "PAN_FORMAT"), 0, "pan_problem", "explain_pan_issue"),
    ("PAN typed wrong once, then fixed", run("pan", "PAN_FORMAT", "ok"), 0, None, None),
    ("PAN typed wrong once (keep typing)", run("pan", "PAN_FORMAT"), 0, None, None),
    ("PAN not linked, first help", run("pan", "PAN_NOT_LINKED"), 0, "pan_problem", "explain_pan_issue"),
    ("PAN not linked, second help: link guide", run("pan", "PAN_NOT_LINKED"), 1, "pan_problem", "guide_pan_aadhaar_link"),
    ("PAN not linked, third time: person", run("pan", "PAN_NOT_LINKED"), 2, "pan_problem", "human_handoff"),
    ("Name on PAN and Aadhaar differ: explain", run("kyc", "NAME_MISMATCH"), 0, "pan_problem", "explain_pan_issue"),
    ("Name mismatch again: straight to a person", run("kyc", "NAME_MISMATCH"), 1, "pan_problem", "human_handoff"),
    ("OTP not received twice", run("kyc", "OTP_NOT_RECEIVED", "OTP_NOT_RECEIVED"), 0, "aadhaar_otp", "resend_otp_tips"),
    ("OTP still not received: DigiLocker", run("kyc", "OTP_NOT_RECEIVED", "OTP_NOT_RECEIVED"), 1, "aadhaar_otp", "switch_to_digilocker"),
    ("OTP third help: offline Aadhaar", run("kyc", "OTP_NOT_RECEIVED", "OTP_NOT_RECEIVED"), 2, "aadhaar_otp", "offline_aadhaar_xml"),
    ("OTP after 3 attempts: person", run("kyc", "OTP_NOT_RECEIVED", "OTP_NOT_RECEIVED"), 3, "aadhaar_otp", "human_handoff"),
    ("Mobile not linked to Aadhaar: video KYC", run("kyc", "MOBILE_NOT_LINKED"), 0, "aadhaar_otp", "switch_to_video_kyc"),
    ("Selfie doesn't match twice", run("selfie", "FACE_MISMATCH", "FACE_MISMATCH"), 0, "face_match", "face_match_tips"),
    ("Selfie mismatch, third help: video KYC", run("selfie", "FACE_MISMATCH", "FACE_MISMATCH"), 2, "face_match", "switch_to_video_kyc"),
    ("Face check fails twice on the selfie step", run("selfie", "live", "live"), 0, "liveness", "retry_liveness_tips"),
    ("Wrong IFSC twice", run("bank", "IFSC_FORMAT", "IFSC_FORMAT"), 0, "bank_verify", "explain_bank_issue"),
    ("Bank account in someone else's name, second help", run("bank", "ACCOUNT_NAME_MISMATCH"), 1, "bank_verify", "try_another_account"),
    ("Rs 1 test deposit failed", run("bank", "PENNY_DROP_FAILED"), 0, "bank_verify", "explain_bank_issue"),
    ("Bank doesn't support auto-pay, second help", run("mandate", "MANDATE_BANK_UNSUPPORTED"), 1, "mandate_failed", "switch_mandate_method"),
    ("Auto-pay OTP timed out twice", run("mandate", "MANDATE_OTP_TIMEOUT", "MANDATE_OTP_TIMEOUT"), 0, "mandate_failed", "explain_mandate_issue"),
    ("No debit card, third time: person", run("mandate", "NO_DEBIT_CARD"), 3, "mandate_failed", "human_handoff"),
    ("Bank statement is password-protected", run("bank", "doc:PDF_LOCKED"), 0, "income_doc", "explain_doc_issue"),
    ("Statement too old, second help: re-upload", run("pan", "doc:STATEMENT_TOO_OLD"), 1, "income_doc", "guided_reupload"),
    ("Statement fixed with a good upload", run("bank", "doc:STATEMENT_TOO_SHORT", "doc:"), 0, None, None),
]


def main() -> dict:
    rows, passed = [], 0
    for name, events, attempts, blocker, action in SCENARIOS:
        r = rescue("eval", events, now=len(events), attempts=attempts)
        got_b = r.detection.blocker if r.detection.stalled else None
        ok = got_b == blocker and r.action == action and r.policy_ok
        passed += ok
        rows.append({"name": name, "expected": [blocker, action], "got": [got_b, r.action], "pass": ok})
    out = {
        "scenarios": len(SCENARIOS), "passed": passed,
        "note": "Loan document steps only. Reported separately from the 30/30 scripted scenarios and the "
                "held-out score; written alongside the rules, so it checks the logic, not real-world accuracy.",
        "results": rows,
    }
    OUT.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for r in rows:
        print(("PASS " if r["pass"] else "FAIL ") + r["name"] + ("" if r["pass"] else f"  expected {r['expected']} got {r['got']}"))
    print(f"document-step scenarios: {passed}/{len(SCENARIOS)} passed")
    return out


if __name__ == "__main__":
    sys.exit(0 if (lambda o: o["passed"] == o["scenarios"])(main()) else 1)
