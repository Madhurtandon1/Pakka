from datetime import date, timedelta

import pytest

from pakka.merchant.ledger import simulate, sma_bucket
from pakka.merchant.models import Loan, SettlementDay
from pakka.merchant.rules import detect
from pakka.merchant.synth import LENDERS, START
from pakka.merchant.templates import rupees

FIFO, PREPAY = LENDERS["demo_nbfc_a"], LENDERS["demo_bank_b"]
LOAN = Loan(loan_id="L1", merchant_id="m", lender_id="x", principal_paise=1_00_000_00, edi_paise=60_000,
            start_date=START, tenure_days=180)


def ledger(values, config=FIFO):
    days = [SettlementDay(merchant_id="m", day=START + timedelta(days=i), gross_settlement_paise=v)
            for i, v in enumerate(values)]
    return simulate(LOAN, days, config)


def test_fifo_carries_forward_and_clears_oldest_first():
    rows = ledger([100_000, 20_000, 30_000, 200_000])
    assert [r.deducted_paise for r in rows] == [60_000, 20_000, 30_000, 130_000]
    assert rows[1].shortfall_today_paise == 40_000 and rows[1].total_overdue_paise == 40_000
    assert rows[2].total_overdue_paise == 70_000
    assert rows[2].oldest_unpaid_date == START + timedelta(days=1)   # day 2's instalment is still the oldest
    assert rows[2].dpd == 2
    assert rows[3].total_overdue_paise == 0 and rows[3].dpd == 0


def test_prepayment_mode_holds_partial_deductions_as_credit():
    rows = ledger([100_000, 40_000, 100_000], PREPAY)
    assert rows[1].total_overdue_paise == 60_000 and rows[1].prepayment_credit_paise == 40_000
    assert rows[1].dpd == 1
    assert rows[2].total_overdue_paise == 0 and rows[2].prepayment_credit_paise == 0


@pytest.mark.parametrize("dpd,bucket", [(0, "standard"), (1, "SMA-0"), (30, "SMA-0"), (31, "SMA-1"),
                                        (60, "SMA-1"), (61, "SMA-2"), (90, "SMA-2"), (91, "NPA")])
def test_sma_bucket_boundaries(dpd, bucket):
    assert sma_bucket(dpd) == bucket


def test_r1_fires_on_partial_deduction_only():
    full = ledger([100_000, 60_000])
    assert detect(full, 60_000)[0] is None
    short = ledger([100_000, 59_999])
    blocker, reasons, ids = detect(short, 60_000)
    assert blocker == "edi_shortfall" and "R1_shortfall" in ids and reasons


def test_r2_only_until_the_oldest_date_is_contacted():
    rows = ledger([100_000, 20_000, 70_000])          # day 3 covers today's EDI but arrears remain
    blocker, _, ids = detect(rows, 60_000)
    assert blocker == "edi_shortfall" and ids == ["R2_arrears_aging"]
    assert detect(rows, 60_000, contacted_oldest={rows[-1].oldest_unpaid_date})[0] is None


def test_r3_sales_dip_risk_while_nothing_is_overdue():
    rows = ledger([65_000] * 7)
    blocker, _, ids = detect(rows, 60_000)
    assert blocker == "sales_dip_risk" and ids == ["R3_sales_dip_risk"]
    assert detect(rows, 60_000, last_dip_nudge=rows[-1].day - timedelta(days=2))[0] is None
    assert detect(ledger([90_000] * 7), 60_000)[0] is None


def test_r4_cured_after_arrears_clear():
    rows = ledger([100_000, 20_000, 200_000])
    assert detect(rows, 60_000)[0] == "cured"


def test_rupees_uses_indian_grouping():
    assert rupees(1_00_000_00) == "₹1,00,000"
    assert rupees(1_23_45_678_90) == "₹1,23,45,678.90"
    assert rupees(60_000) == "₹600"
    assert date(2026, 10, 1) == START
