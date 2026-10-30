"""Detector extension for the loan document steps (PAN, Aadhaar OTP, selfie, bank, auto-pay).

The existing rules in detector.py run first and are not changed. This module only adds rules
for the new steps, plus an adapter so the existing face-check (liveness) rule also works on the
selfie step. As with the existing rules, a failure followed by a success is not a stall.
"""
from collections import Counter

from .detector import _after_last, detect
from .models import Detection, Event

# blocker: (step it applies to, codes that fire on the first failure, codes that need two failures)
RULES = {
    "pan_problem": ("pan", ("PAN_NOT_LINKED",), ("PAN_FORMAT",)),
    "aadhaar_otp": ("kyc", ("MOBILE_NOT_LINKED",), ("OTP_NOT_RECEIVED",)),
    "face_match": ("selfie", (), ("FACE_MISMATCH",)),
    "bank_verify": ("bank", ("ACCOUNT_NAME_MISMATCH", "PENNY_DROP_FAILED"), ("IFSC_FORMAT",)),
    "mandate_failed": ("mandate", ("MANDATE_BANK_UNSUPPORTED", "NO_DEBIT_CARD"), ("MANDATE_OTP_TIMEOUT",)),
}
INCOME_CODES = ("FILE_FORMAT", "PDF_LOCKED", "STATEMENT_UNREADABLE", "STATEMENT_TOO_OLD", "STATEMENT_TOO_SHORT")
NEW_BLOCKERS = set(RULES) | {"income_doc"}


def detect_all(events: list[Event], now: float) -> Detection:
    """Existing rules first (unchanged), then the document-step rules."""
    base = detect(events, now)
    if base.stalled or not events:
        return base
    events = sorted(events, key=lambda e: e.ts)
    step = events[-1].step

    if step == "selfie":
        # Reuse the existing liveness rule as-is by presenting the selfie events as the KYC step.
        as_kyc = [e.model_copy(update={"step": "kyc"}) for e in events if e.step == "selfie"]
        live = detect(as_kyc, now)
        if live.stalled and live.blocker == "liveness":
            return live.model_copy(update={"step": "selfie"})

    here = [e for e in events if e.step == step]
    fails = [e for e in _after_last(here, "check_ok") if e.type == "check_failed" and e.code]

    # A PAN/Aadhaar name mismatch is found once both names are known (on the PAN or Aadhaar step).
    if step in ("pan", "kyc") and any(e.code == "NAME_MISMATCH" for e in fails):
        return Detection(stalled=True, blocker="pan_problem", step=step, code="NAME_MISMATCH",
                         reasons=["name on PAN and Aadhaar don't match"])

    for blocker, (rule_step, once, twice) in RULES.items():
        if step != rule_step:
            continue
        counts = Counter(e.code for e in fails)
        for code in once:
            if counts[code]:
                return Detection(stalled=True, blocker=blocker, step=step, code=code,
                                 reasons=[f"{code} reported"])
        for code in twice:
            if counts[code] >= 2:
                return Detection(stalled=True, blocker=blocker, step=step, code=code,
                                 reasons=[f"{counts[code]} x {code}"])

    # Income documents can be uploaded from the checklist at any step. Each of these problems is
    # about the file itself (sending the same file again won't help), so one failure is enough.
    # It fires right after the failed upload only, so later clicks on other steps don't re-trigger it
    # (the checklist keeps showing "needs attention" until a good file is uploaded).
    doc_fails = [e for e in _after_last(events, "doc_ok") if e.type == "doc_failed" and e.code in INCOME_CODES]
    if doc_fails and events[-1].type == "doc_failed":
        code = doc_fails[-1].code
        return Detection(stalled=True, blocker="income_doc", step=step, code=code,
                         reasons=[f"income document: {code}"])
    return base
