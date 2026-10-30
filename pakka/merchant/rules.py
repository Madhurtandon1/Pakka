"""Rule-based detector over the lender ledger. Each rule has an ID that goes into the audit log."""
from datetime import date, timedelta

from .models import LedgerDay

THRESHOLDS = {
    "dip_window_days": 7,      # R3 looks at the mean settlement over this many days
    "dip_ratio": 1.2,          # R3 fires when that mean is below dip_ratio × EDI
    "dip_renotify_days": 7,    # at most one early-warning nudge per this many days
    "stress_dpd": 7,           # DPD at or above this counts as a stress flag (no offers for 90 days)
    "upsell_cooloff_days": 90,
}


def detect(ledger: list[LedgerDay], edi_paise: int, episode_open: bool = False,
           contacted_oldest: set[date] | None = None,
           last_dip_nudge: date | None = None) -> tuple[str | None, list[str], list[str]]:
    """Return (blocker, reasons, rule_ids) for the last day in `ledger`."""
    if not ledger:
        return None, [], []
    today, prev = ledger[-1], (ledger[-2] if len(ledger) > 1 else None)
    contacted_oldest = contacted_oldest or set()

    if today.total_overdue_paise == 0 and ((prev and prev.total_overdue_paise > 0) or episode_open):
        return "cured", ["R4_cured: previously overdue, now fully paid"], ["R4_cured"]

    reasons, ids = [], []
    if today.shortfall_today_paise > 0:
        ids.append("R1_shortfall")
        reasons.append(f"R1_shortfall: deducted {today.deducted_paise} of {today.edi_due_paise} paise today")
    if today.dpd >= 1 and today.oldest_unpaid_date not in contacted_oldest:
        ids.append("R2_arrears_aging")
        reasons.append(f"R2_arrears_aging: {today.dpd} DPD since {today.oldest_unpaid_date}, not yet contacted")
    if ids:
        return "edi_shortfall", reasons, ids

    window = ledger[-THRESHOLDS["dip_window_days"]:]
    if len(window) == THRESHOLDS["dip_window_days"] and today.dpd == 0:
        mean = sum(d.settlement_paise for d in window) / len(window)
        recent = last_dip_nudge and today.day - last_dip_nudge < timedelta(days=THRESHOLDS["dip_renotify_days"])
        if mean < THRESHOLDS["dip_ratio"] * edi_paise and not recent:
            return "sales_dip_risk", [
                f"R3_sales_dip_risk: {len(window)}-day mean settlement {int(mean)} paise "
                f"< {THRESHOLDS['dip_ratio']} × EDI {edi_paise}"], ["R3_sales_dip_risk"]
    return None, [], []
