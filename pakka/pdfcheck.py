"""Income document check (bank statements, salary slips): local only, no network calls.

The file is read in memory and nothing is kept: no text, no dates beyond the summary below.
Codes: FILE_FORMAT (won't open), PDF_LOCKED (password-protected), STATEMENT_UNREADABLE (no text,
e.g. a scanned image), STATEMENT_TOO_OLD (latest date > 45 days ago), STATEMENT_TOO_SHORT
(dates cover less than the months asked for).
"""
import io
import re
from datetime import date, datetime, timedelta

MAX_BYTES = 8 * 1024 * 1024
MAX_AGE_DAYS = 45
SLACK_DAYS = 7          # "3 months" is met by roughly 83+ days of entries
MAX_PAGES = 40

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_NUMERIC = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_WORDY = re.compile(r"\b(\d{1,2})[\s-]([A-Za-z]{3})[A-Za-z]*[\s,-]+(\d{4}|\d{2})\b")


def _year(y: str) -> int:
    return int(y) + 2000 if len(y) == 2 else int(y)


def find_dates(text: str, today: date) -> list[date]:
    found = []
    for m in _ISO.finditer(text):
        found.append((int(m[1]), int(m[2]), int(m[3])))
    for m in _NUMERIC.finditer(text):
        found.append((_year(m[3]), int(m[2]), int(m[1])))          # Indian order: dd/mm/yyyy
    for m in _WORDY.finditer(text):
        if m[2].lower()[:3] in _MONTHS:
            found.append((_year(m[3]), _MONTHS[m[2].lower()[:3]], int(m[1])))
    out = []
    for y, mo, d in found:
        try:
            dt = date(y, mo, d)
        except ValueError:
            continue
        if date(2000, 1, 1) <= dt <= today + timedelta(days=1):
            out.append(dt)
    return out


def check_pdf(data: bytes, months: int = 3, today: date | None = None) -> dict:
    today = today or datetime.now().date()
    base = {"ok": False, "months_required": months}
    if not data.startswith(b"%PDF"):
        return {**base, "code": "FILE_FORMAT"}
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):   # an empty user password still opens some PDFs
            return {**base, "code": "PDF_LOCKED"}
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:MAX_PAGES])
        pages = len(reader.pages)
    except Exception as exc:  # pypdf raises several error types for broken files
        if "password" in str(exc).lower() or "decrypt" in str(exc).lower():
            return {**base, "code": "PDF_LOCKED"}
        return {**base, "code": "FILE_FORMAT"}

    dates = find_dates(text, today)
    if not dates:
        return {**base, "code": "STATEMENT_UNREADABLE", "pages": pages}
    first, latest = min(dates), max(dates)
    info = {"pages": pages, "from": first.isoformat(), "to": latest.isoformat(),
            "span_days": (latest - first).days, "age_days": (today - latest).days}
    if (today - latest).days > MAX_AGE_DAYS:
        return {**base, **info, "code": "STATEMENT_TOO_OLD"}
    if (latest - first).days < months * 30 - SLACK_DAYS:
        return {**base, **info, "code": "STATEMENT_TOO_SHORT"}
    return {**base, **info, "ok": True, "code": None}
