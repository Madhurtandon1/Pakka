"""Seeded synthetic merchants: five demo personas and randomised merchants for the eval."""
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import LenderConfig, Loan, Merchant, SettlementDay

START = date(2026, 10, 1)
DAYS = 30
EDI = 60_000                  # ₹600 a day, in paise
PRINCIPAL = 1_00_000_00       # ₹1,00,000, in paise

ALL_LENDER_ACTIONS = ["notify_shortfall", "send_pay_link", "schedule_reminder",
                      "route_lower_deduction_request", "route_reschedule_request",
                      "schedule_callback", "human_handoff", "show_repeat_offer", "no_action"]

LENDERS = {
    "demo_nbfc_a": LenderConfig(
        lender_id="demo_nbfc_a", lender_name="Demo NBFC A",
        grievance_officer="R. Mehta, grievance@demo-nbfc-a.example, 1800-000-0001",
        shortfall_mode="carry_forward_fifo", allowed_actions=ALL_LENDER_ACTIONS,
        vpa="collections@demo-nbfc-a",
    ),
    "demo_bank_b": LenderConfig(
        lender_id="demo_bank_b", lender_name="Demo Bank B",
        grievance_officer="S. Iyer, nodal.officer@demo-bank-b.example, 1800-000-0002",
        shortfall_mode="retain_as_prepayment",
        allowed_actions=[a for a in ALL_LENDER_ACTIONS if a != "route_lower_deduction_request"],
        lower_deduction_requests_enabled=False, vpa="loans@demo-bank-b",
    ),
}


@dataclass
class Persona:
    merchant: Merchant
    loan: Loan
    lender: LenderConfig
    settlements: list[SettlementDay]
    title: str = ""
    story: str = ""
    tags: list[str] = field(default_factory=list)


def _days(values: list[int], mid: str) -> list[SettlementDay]:
    return [SettlementDay(merchant_id=mid, day=START + timedelta(days=i), gross_settlement_paise=v)
            for i, v in enumerate(values)]


def _base(rng: random.Random, lo: int, hi: int) -> list[int]:
    return [rng.randint(lo, hi) for _ in range(DAYS)]


def _make(mid, name, lang, lender_id, values, title, story, soundbox=True) -> Persona:
    m = Merchant(merchant_id=mid, display_name=name, language=lang,
                 soundbox_id=f"SB-{mid[:4].upper()}" if soundbox else None)
    loan = Loan(loan_id=f"L-{mid}", merchant_id=mid, lender_id=lender_id, principal_paise=PRINCIPAL,
                edi_paise=EDI, start_date=START, tenure_days=180)
    return Persona(m, loan, LENDERS[lender_id], _days(values, mid), title, story)


def personas() -> dict[str, Persona]:
    rng = random.Random(31)

    kirana = _base(rng, 150_000, 300_000)

    chai = _base(rng, 120_000, 200_000)
    chai[8], chai[9], chai[10] = 70_000, 20_000, 250_000           # rain on days 9-10, recovery day 11

    tailor = _base(rng, 85_000, 95_000)
    tailor[8:14] = [75_000, 70_000, 65_000, 62_000, 61_000, 60_000]  # slow week: early warning day 14
    tailor[14:] = [40_000, 25_000, 12_000, 5_000, 0, 0] + [rng.randint(5_000, 20_000) for _ in range(10)]

    mobile = _base(rng, 110_000, 180_000)
    mobile[7] = 40_000                                              # short day under prepayment mode

    late = _base(rng, 100_000, 160_000)
    late[5], late[6] = 30_000, 70_000                               # short day 6, partial catch-up day 7

    out = [
        _make("kirana_steady", "Sharma Kirana Store", "en", "demo_nbfc_a", kirana,
              "Steady kirana", "Sales comfortably cover the instalment every day. Pakka should never contact them."),
        _make("chai_seasonal", "Ramesh Chai Stall", "hi", "demo_nbfc_a", chai,
              "Chai stall, rainy days", "Rain cuts sales on days 9-10. Day 10 falls short; sales recover on day 11."),
        _make("tailor_stress", "Noor Tailors", "hi", "demo_nbfc_a", tailor,
              "Tailor, illness", "A slow week (early warning on day 14), then illness: sales fall to zero from day 15."),
        _make("mobile_dispute", "City Mobile Repair", "hi", "demo_bank_b", mobile,
              "Mobile shop, disputed deduction",
              "Day 8 is short. Demo Bank B holds partial deductions as prepayment, so the merchant thinks they already paid."),
        _make("general_late_night", "Gupta General Store", "en", "demo_nbfc_a", late,
              "General store, late-night shortfall",
              "Day 6 falls short and is detected at 21:30. Pakka must wait until 08:00."),
    ]
    return {p.merchant.merchant_id: p for p in out}


def random_merchants(n: int = 200, seed: int = 2026) -> dict[str, Persona]:
    rng = random.Random(seed)
    out = {}
    for i in range(n):
        mid = f"m{i:03d}"
        kind = rng.choice(["steady", "steady", "dips", "dips", "stress", "dip_risk"])
        lo = rng.randint(65_000, 160_000)
        values = _base(rng, lo, lo + rng.randint(10_000, 120_000))
        if kind == "dips":
            for _ in range(rng.randint(1, 3)):
                d = rng.randrange(DAYS)
                values[d] = rng.randint(0, EDI - 1)
        elif kind == "stress":
            d = rng.randrange(5, DAYS - 3)
            for j in range(d, DAYS):
                values[j] = rng.randint(0, 30_000)
        elif kind == "dip_risk":
            d = rng.randrange(5, DAYS - 7)
            for j in range(d, d + 7):
                values[j] = rng.randint(EDI, 70_000)
        lender = rng.choice(list(LENDERS))
        p = _make(mid, f"Merchant {i}", rng.choice(["en", "hi"]), lender, values, kind, kind,
                  soundbox=rng.random() < 0.7)
        p.tags = [kind]
        out[mid] = p
    return out
