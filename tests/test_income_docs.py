"""Income document check (bank statements): PDF codes, the income_doc blocker, its ladder and the API.
The statements are synthetic PDFs generated with dates relative to the test date."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from pakka import policy
from pakka.agent import rescue
from pakka.docs_detector import detect_all
from pakka.explain import explain
from pakka.models import Event
from pakka.pdfcheck import check_pdf, find_dates
from pakka.samples import STATEMENTS, make_statement

TODAY = date(2026, 10, 31)


@pytest.mark.parametrize("kind,code", [("statement_good", None), ("statement_locked", "PDF_LOCKED"),
                                       ("statement_old", "STATEMENT_TOO_OLD"), ("statement_short", "STATEMENT_TOO_SHORT")])
def test_sample_statements(kind, code):
    r = check_pdf(make_statement(kind, TODAY)[0], months=3, today=TODAY)
    assert r["code"] == code and r["ok"] is (code is None)


def test_three_months_is_too_short_when_six_are_needed():
    assert check_pdf(make_statement("statement_good", TODAY)[0], months=6, today=TODAY)["code"] == "STATEMENT_TOO_SHORT"


@pytest.mark.parametrize("data", [b"hello", b"%PDF-1.4 broken", b""])
def test_not_a_pdf(data):
    assert check_pdf(data, today=TODAY)["code"] == "FILE_FORMAT"


def test_pdf_without_dates_is_unreadable():
    from pakka.samples import _pdf
    assert check_pdf(_pdf(["no dates in here"]), today=TODAY)["code"] == "STATEMENT_UNREADABLE"


def test_find_dates_formats():
    got = find_dates("05/08/2026 · 2026-09-01 · 3 Sep 2026 · 12-Oct-26 · 31/02/2026 · 01/01/2099", TODAY)
    assert set(got) == {date(2026, 8, 5), date(2026, 9, 1), date(2026, 9, 3), date(2026, 10, 12)}


def test_result_never_contains_the_text():
    r = check_pdf(make_statement("statement_good", TODAY)[0], today=TODAY)
    assert "Samina" not in str(r) and "SALARY" not in str(r)


def _ev(*items):
    return [Event(type="step_view", step="bank", ts=0)] + [
        Event(type=t, step="bank", ts=i, code=c) for i, (t, c) in enumerate(items, 1)]


def test_income_doc_fires_right_after_a_failed_upload():
    d = detect_all(_ev(("doc_failed", "PDF_LOCKED")), now=2)
    assert d.blocker == "income_doc" and d.code == "PDF_LOCKED"


def test_income_doc_does_not_follow_the_user_to_later_clicks():
    assert not detect_all(_ev(("doc_failed", "PDF_LOCKED"), ("check_ok", None)), now=3).stalled


def test_good_upload_clears_income_doc():
    assert not detect_all(_ev(("doc_failed", "STATEMENT_TOO_OLD"), ("doc_ok", None)), now=3).stalled


def test_income_doc_ladder():
    assert [policy.choose_for("income_doc", "PDF_LOCKED", n) for n in range(3)] == \
        ["explain_doc_issue", "guided_reupload", "human_handoff"]


def test_locked_message_wording():
    r = rescue("j", _ev(("doc_failed", "PDF_LOCKED")), now=2)
    assert r.message.startswith("Your bank statement is password-protected")
    assert "Fetch from bank" in explain("explain_doc_issue", "en", "bank", "PDF_LOCKED")


@pytest.mark.parametrize("kind", STATEMENTS)
def test_pdfcheck_api_with_samples(kind):
    c = TestClient(app)
    pdf = c.get(f"/samples/{kind}")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    r = c.post("/pdfcheck", params={"months": 3}, files={"file": ("s.pdf", pdf.content, "application/pdf")}).json()
    assert r["ok"] is (kind == "statement_good")


def test_pdfcheck_rejects_over_8mb():
    big = b"%PDF-1.4\n" + b"0" * (8 * 1024 * 1024 + 10)
    r = TestClient(app).post("/pdfcheck", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413
