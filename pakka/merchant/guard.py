"""Guard rules G1-G9. They run after an action is chosen and before anything reaches the merchant."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from .models import ALL_ACTIONS, DISTRESS, ConsentRecord, LenderConfig, Merchant
from .policy import PolicyViolation, max_attempts
from .rules import THRESHOLDS
from .templates import SOUNDBOX_CUE

DECISION_ACTIONS = {"approve_loan", "approve_credit", "waive_charges", "waive_penalty",
                    "reschedule_now", "restructure_loan", "change_due_date", "reject_loan"}

SOUNDBOX_BLOCKLIST = ["overdue", "bakaya", "baki", "loan", "emi", "edi", "₹", "rs", "rupaye", "rupee",
                      "rupees", "paise", "due", "kist", "किस्त", "बकाया", "लोन", "रुपये", "penalty"]


@dataclass
class GuardContext:
    now: datetime
    proactive: bool
    merchant: Merchant
    lender: LenderConfig
    consent: Optional[ConsentRecord] = None
    blocker: Optional[str] = None
    intent: Optional[str] = None
    contacts_today: int = 0
    attempts: int = 0
    total_overdue_paise: int = 0
    last_stress: Optional[date] = None
    episode_stopped: bool = False
    last_contact_day: Optional[date] = None     # last shortfall nudge delivered in this episode
    sma_worse: bool = False                     # SMA bucket has worsened since that nudge
    skip_requests_30d: int = 0                  # "can't pay today" requests in the window, including this one


@dataclass
class Verdict:
    action: str
    policy_ok: bool = True
    escalated: bool = False
    blocks: list[str] = field(default_factory=list)
    scheduled_for: Optional[datetime] = None
    channel: str = "none"
    stop_episode: bool = False

    @property
    def delivered(self) -> bool:
        return self.channel != "none" and self.scheduled_for is None


def next_window_start(now: datetime, window: tuple[int, int], tomorrow: bool = False) -> datetime:
    start = now.replace(hour=window[0], minute=0, second=0, microsecond=0)
    if tomorrow or now.hour >= window[0]:
        start += timedelta(days=1)
    return start


def in_window(now: datetime, window: tuple[int, int]) -> bool:
    return window[0] <= now.hour < window[1]


def effective_window(merchant: Merchant, consent: Optional[ConsentRecord]) -> tuple[int, int]:
    """The merchant's own preferred hours, never wider than the 08:00-19:00 limit."""
    lo, hi = merchant.contact_window
    if consent and consent.active and consent.contact_window:
        a, b = max(lo, consent.contact_window[0]), min(hi, consent.contact_window[1])
        if a < b:
            return a, b
    return lo, hi


def guard(action: str, ctx: GuardContext) -> Verdict:
    # G9: decisions are never Pakka's to make. This should be unreachable; it is tested.
    if action in DECISION_ACTIONS or action not in ALL_ACTIONS:
        raise PolicyViolation(f"G9_no_decision: {action} is not an action Pakka may take")

    v = Verdict(action=action)
    consent = ctx.consent if ctx.consent and ctx.consent.active else None
    distress_reply = not ctx.proactive and ctx.intent in DISTRESS

    # G1: early-warning consent must be active; offers also need repeat-offer consent.
    # Exception: when the merchant themselves writes about distress, they always reach a person.
    no_consent = not consent or not consent.early_warning_alerts
    if distress_reply and no_consent:
        v.blocks.append("G1_skipped: merchant's own distress reply")
    elif no_consent or (action == "show_repeat_offer" and not consent.repeat_offers):
        v.action, v.blocks = "no_action", ["G1_consent"]
        return v

    # G8: dispute / hardship / already paid: stop and hand to a person.
    if ctx.intent in DISTRESS:
        v.action, v.escalated, v.stop_episode = "human_handoff", True, True
        v.blocks.append("G8_distress")
    elif ctx.proactive and ctx.episode_stopped:
        v.action = "no_action"
        v.blocks.append("G8_stopped")
        return v

    # G10: Pakka may confirm the lender's carry-forward only for an auto-carry-forward lender and only within
    # the lender's own preset limit. Otherwise the request goes to the lender, or past the limit, to a person.
    if v.action == "acknowledge_carry_forward":
        cfg = ctx.lender.skip_day_policy
        if cfg.mode != "auto_carry_forward":
            v.action = "route_skip_request"
            v.blocks.append("G10_skip_limit: lender decides every request")
        elif ctx.skip_requests_30d > cfg.max_auto_per_30_days:
            v.action, v.escalated, v.stop_episode = "human_callback_booking", True, True
            v.blocks.append(f"G10_skip_limit: over the lender's limit of {cfg.max_auto_per_30_days}")
    if v.action == "human_callback_booking":
        v.escalated, v.stop_episode = True, True     # automatic handling stops; a person helps plan

    # G3 cadence: during a shortfall, nudge every other day at most, unless the SMA bucket worsened.
    if (ctx.proactive and ctx.blocker == "edi_shortfall" and ctx.last_contact_day and not ctx.sma_worse
            and (ctx.now.date() - ctx.last_contact_day).days == 1):     # same day is G3_daily_cap's job
        v.action = "no_action"
        v.blocks.append("G3_cadence: every other day")
        return v

    # G7: too many attempts in this episode.
    if ctx.proactive and v.action not in ("no_action", "human_handoff") and ctx.attempts >= max_attempts():
        v.action, v.escalated, v.stop_episode = "human_handoff", True, True
        v.blocks.append("G7_attempts")

    # G6: the lender decides which actions are in scope.
    if v.action not in ("no_action", "human_handoff") and v.action not in ctx.lender.allowed_actions:
        v.blocks.append(f"G6_lender_scope:{v.action}")
        v.action, v.policy_ok, v.escalated, v.stop_episode = "human_handoff", False, True, True

    # G4: no new-credit offer with arrears or within 90 days of a stress flag.
    if v.action == "show_repeat_offer":
        recent = ctx.last_stress and (ctx.now.date() - ctx.last_stress).days < THRESHOLDS["upsell_cooloff_days"]
        if ctx.total_overdue_paise > 0 or recent:
            v.action = "no_action"
            v.blocks.append("G4_no_upsell")
            return v

    delivers = v.action != "no_action" or ctx.blocker == "cured"
    if not delivers:
        return v

    if ctx.proactive:
        window = effective_window(ctx.merchant, consent)
        if not in_window(ctx.now, window):                       # G2: contact hours only
            v.scheduled_for = next_window_start(ctx.now, window)
            v.blocks.append(f"G2_hours deferred to {v.scheduled_for:%d %b %H:%M}")
        elif ctx.contacts_today >= 1:                           # G3: one proactive contact a day
            v.scheduled_for = next_window_start(ctx.now, window, tomorrow=True)
            v.blocks.append(f"G3_daily_cap deferred to {v.scheduled_for:%d %b %H:%M}")

    if v.scheduled_for:
        v.channel = "none"
    elif ctx.proactive and ctx.blocker != "cured" and consent and consent.soundbox_cue and ctx.merchant.soundbox_id:
        v.channel = "soundbox_cue"
    else:
        v.channel = "app_card"
    return v


def soundbox_safe(text: Optional[str]) -> bool:
    if text is None:
        return True
    low = text.lower()
    if re.search(r"\d", text) or text not in SOUNDBOX_CUE.values():
        return False
    return not any(re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low) for w in SOUNDBOX_BLOCKLIST)


def soundbox_guard(text: Optional[str], channel: str, lang: str,
                   consent: Optional[ConsentRecord]) -> tuple[Optional[str], str, list[str]]:
    """G5: the Soundbox only ever plays the neutral cue."""
    if channel != "soundbox_cue":
        return None, channel, []
    if not consent or not consent.active or not consent.soundbox_cue:
        return None, "app_card", ["G5_soundbox_safe: no soundbox consent"]
    if not soundbox_safe(text):
        return SOUNDBOX_CUE[lang], channel, ["G5_soundbox_safe: replaced with neutral cue"]
    return text, channel, []
