"""Offline format checks for the loan documents: PAN, Aadhaar number, IFSC and name match.

No network calls. These say a value is *well-formed*; they don't prove it belongs to the person
(that needs NSDL, UIDAI or a penny drop with the bank, which the lender runs).
The full Aadhaar number is never returned or stored: only "XXXX XXXX 1234".
"""
import re

from .aadhaar import valid_aadhaar

PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
TITLES = {"MR", "MRS", "MS", "MISS", "SHRI", "SMT", "KUMARI", "KU", "DR", "SRI"}


def check_pan(value: str) -> dict:
    v = re.sub(r"\s", "", value or "").upper()
    ok = bool(PAN.match(v))
    return {"ok": ok, "code": None if ok else "PAN_FORMAT", "display": v if ok else None}


def check_aadhaar(value: str) -> dict:
    """12 digits, not starting with 0 or 1, valid Verhoeff check digit. Returns only the last 4."""
    v = re.sub(r"[\s-]", "", value or "")
    ok = valid_aadhaar(v)
    return {"ok": ok, "code": None if ok else "AADHAAR_FORMAT",
            "last4": v[-4:] if ok else None, "display": f"XXXX XXXX {v[-4:]}" if ok else None}


def check_ifsc(value: str) -> dict:
    v = re.sub(r"\s", "", value or "").upper()
    ok = bool(IFSC.match(v))
    return {"ok": ok, "code": None if ok else "IFSC_FORMAT", "display": v if ok else None}


def name_tokens(name: str) -> list[str]:
    words = re.sub(r"[^A-Z ]", " ", (name or "").upper()).split()
    return [w for w in words if w not in TITLES]


def _same(a: str, b: str) -> bool:
    """Equal words, or an initial that matches the other word's first letter."""
    if a == b:
        return True
    return (len(a) == 1 or len(b) == 1) and a[0] == b[0]


def names_match(a: str, b: str) -> bool:
    """Lenient match: case, spacing, titles, word order, initials and one missing middle name are fine.
    Only clearly different names (e.g. a different first name or surname) count as a mismatch."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(long_) - len(short) > 1:
        return False
    left = list(long_)
    for t in short:
        hit = next((x for x in left if _same(t, x)), None)
        if hit is None:
            return False
        left.remove(hit)
    # at least one full word must agree (two initials alone prove nothing)
    return any(len(t) > 1 and t in long_ for t in short)


def check_names(pan_name: str, aadhaar_name: str, bank_name: str | None = None) -> dict:
    """NAME_MISMATCH if PAN and Aadhaar names clearly differ; ACCOUNT_NAME_MISMATCH for the bank."""
    if not names_match(pan_name, aadhaar_name):
        return {"ok": False, "code": "NAME_MISMATCH"}
    if bank_name is not None and not names_match(pan_name, bank_name):
        return {"ok": False, "code": "ACCOUNT_NAME_MISMATCH"}
    return {"ok": True, "code": None}
