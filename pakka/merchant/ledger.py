"""Stand-in for the lender's ledger. Every money figure Pakka shows comes from here.

Pakka never computes dues or penalties itself; short-day handling is lender configuration.
"""
from .models import LedgerDay, LenderConfig, Loan, SettlementDay


def sma_bucket(dpd: int) -> str:
    if dpd <= 0:
        return "standard"
    if dpd <= 30:
        return "SMA-0"
    if dpd <= 60:
        return "SMA-1"
    if dpd <= 90:
        return "SMA-2"
    return "NPA"


def simulate(loan: Loan, settlements: list[SettlementDay], config: LenderConfig) -> list[LedgerDay]:
    """Daily auto-deduction from settlements.

    carry_forward_fifo: a short day's partial deduction is applied to the oldest unpaid
    instalment; the remainder is swept from later settlements, oldest first.
    retain_as_prepayment: partial deductions are held as a prepayment credit and only clear
    an instalment once they cover it in full; the instalment shows as overdue until then.
    """
    unpaid: list[list] = []          # [due_date, remaining_paise], oldest first
    credit = 0
    out = []
    for s in sorted(settlements, key=lambda s: s.day):
        n = (s.day - loan.start_date).days
        if n < 0:
            continue
        edi = loan.edi_paise if n < loan.tenure_days else 0
        if edi:
            unpaid.append([s.day, edi])
        owed = sum(r[1] for r in unpaid) - credit
        deducted = max(0, min(owed, s.gross_settlement_paise))

        if config.shortfall_mode == "carry_forward_fifo":
            pay = deducted
            for row in unpaid:
                take = min(row[1], pay)
                row[1] -= take
                pay -= take
            unpaid = [r for r in unpaid if r[1] > 0]
        else:
            credit += deducted
            while unpaid and credit >= unpaid[0][1]:
                credit -= unpaid[0][1]
                unpaid.pop(0)

        oldest = unpaid[0][0] if unpaid else None
        dpd = (s.day - oldest).days + 1 if oldest else 0
        out.append(LedgerDay(
            loan_id=loan.loan_id, day=s.day, settlement_paise=s.gross_settlement_paise,
            edi_due_paise=edi, deducted_paise=deducted,
            shortfall_today_paise=max(0, edi - deducted),
            total_overdue_paise=sum(r[1] for r in unpaid),
            prepayment_credit_paise=credit,
            oldest_unpaid_date=oldest, dpd=dpd, sma_bucket=sma_bucket(dpd),
        ))
    return out
