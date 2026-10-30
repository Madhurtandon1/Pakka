from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

Lang = Literal["en", "hi"]

Intent = Literal["will_pay_today", "will_pay_later", "request_lower_deduction",
                 "request_reschedule", "request_callback", "dispute", "hardship",
                 "already_paid", "unclear"]

MerchantAction = Literal["notify_shortfall", "send_pay_link", "schedule_reminder",
                         "route_lower_deduction_request", "route_reschedule_request",
                         "schedule_callback", "human_handoff", "show_repeat_offer", "no_action"]

ALL_ACTIONS = set(MerchantAction.__args__)
ALL_INTENTS = set(Intent.__args__)
DISTRESS = {"dispute", "hardship", "already_paid"}


class LenderConfig(BaseModel):
    lender_id: str
    lender_name: str
    grievance_officer: str
    shortfall_mode: Literal["carry_forward_fifo", "retain_as_prepayment"]
    allowed_actions: list[str]
    reschedule_requests_enabled: bool = True
    lower_deduction_requests_enabled: bool = True
    penal_charges_note: dict[str, str] = {
        "en": "Charges as per your loan's Key Fact Statement",
        "hi": "शुल्क आपके लोन के Key Fact Statement के अनुसार",
    }
    vpa: str = "lender@demo"


class Merchant(BaseModel):
    merchant_id: str
    display_name: str
    language: Lang
    contact_window: tuple[int, int] = (8, 19)
    soundbox_id: Optional[str] = None


class Loan(BaseModel):
    loan_id: str
    merchant_id: str
    lender_id: str
    principal_paise: int
    edi_paise: int
    start_date: date
    tenure_days: int


class SettlementDay(BaseModel):
    merchant_id: str
    day: date
    gross_settlement_paise: int


class LedgerDay(BaseModel):
    loan_id: str
    day: date
    settlement_paise: int = 0
    edi_due_paise: int
    deducted_paise: int
    shortfall_today_paise: int
    total_overdue_paise: int
    prepayment_credit_paise: int = 0
    oldest_unpaid_date: Optional[date] = None
    dpd: int
    sma_bucket: Literal["standard", "SMA-0", "SMA-1", "SMA-2", "NPA"]


class ConsentIn(BaseModel):
    notice_version: str
    language: Lang = "en"
    early_warning_alerts: bool
    soundbox_cue: bool
    repeat_offers: bool
    channel: Literal["app", "voice"] = "app"
    contact_window: Optional[tuple[int, int]] = None   # merchant's preferred hours, kept inside 08-19


class ConsentRecord(ConsentIn):
    merchant_id: str
    granted_at: datetime
    withdrawn_at: Optional[datetime] = None

    @property
    def active(self) -> bool:
        return self.withdrawn_at is None


class MerchantRescue(BaseModel):
    merchant_id: str
    loan_id: str
    episode_id: Optional[str] = None
    blocker: Optional[str] = None
    reasons: list[str] = []
    rule_ids: list[str] = []
    intent: Optional[Intent] = None
    intent_source: Literal["llm", "llm_sarvam", "keywords", "none"] = "none"
    action: MerchantAction = "no_action"
    needs_consent: bool = False
    escalated: bool = False
    policy_ok: bool = True
    guard_blocks: list[str] = []
    channel: Literal["app_card", "soundbox_cue", "none"] = "none"
    template_id: Optional[str] = None
    message_en: str = ""
    message_hi: str = ""
    options: list[str] = []
    soundbox_cue_text: Optional[str] = None
    lender_request_id: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    latency_ms: float = 0.0
