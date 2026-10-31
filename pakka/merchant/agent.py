"""LangGraph merchant agent, following the same pattern as pakka/agent.py.

    day-end:  detect (rules on the lender ledger) --no blocker--> END
                 └─> decide -> guard (G1-G4, G6-G9) -> render -> soundbox guard (G5) -> audit
    reply:    classify (fixed intents) -> decide -> guard -> render -> soundbox guard -> audit
    offer:    decide (show_repeat_offer) -> guard -> render -> soundbox guard -> audit

Rules choose the action, the guard checks it, and reviewed templates write the message.
"""
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Optional, TypedDict
from urllib.parse import quote

from langgraph.graph import END, START, StateGraph

from pakka.pii import mask

from . import actions, intents, memory, policy, rules
from .guard import GuardContext, Verdict, effective_window, guard, in_window, next_window_start, soundbox_guard
from .ledger import simulate
from .models import ConsentRecord, LedgerDay, MerchantRescue
from .store import MerchantStore
from .synth import Persona, personas
from .templates import OPTIONS, REQUEST_NAMES, SOUNDBOX_CUE, fmt_date, render_both, rupees

SMA_ORDER = {"standard": 0, "SMA-0": 1, "SMA-1": 2, "SMA-2": 3, "NPA": 4}
ROUTED = {"route_lower_deduction_request", "route_reschedule_request", "human_handoff",
          "route_skip_request", "human_callback_booking"}
# Optional reasons for "can't pay today". Any that mean illness, a death or a calamity go to a person (G8).
DISTRESS_REASONS = {"illness", "death", "calamity", "emergency"}


@dataclass
class Facts:
    mode: str                       # "day_end" | "reply" | "offer"
    persona: Persona
    ledger: list[LedgerDay]
    now: datetime
    store: MerchantStore
    consent: Optional[ConsentRecord] = None
    text: str = ""
    reason: Optional[str] = None
    episode: Optional[dict] = None

    @property
    def mid(self) -> str:
        return self.persona.merchant.merchant_id

    @property
    def today(self) -> LedgerDay:
        return self.ledger[-1]


class State(TypedDict, total=False):
    f: Facts
    blocker: Optional[str]
    reasons: list[str]
    rule_ids: list[str]
    intent: Optional[str]
    intent_source: str
    action: str
    verdict: Verdict
    template_id: Optional[str]
    message_en: str
    message_hi: str
    cue: Optional[str]
    channel: str
    g5_blocks: list[str]
    rescue: MerchantRescue
    skip_requests_30d: int
    skip_consecutive: int


def _entry(s: State) -> str:
    return {"day_end": "detect", "reply": "classify", "offer": "offer"}[s["f"].mode]


def _detect(s: State) -> State:
    f = s["f"]
    ep = f.store.open_episode(f.mid)
    blocker, reasons, ids = rules.detect(
        f.ledger, f.persona.loan.edi_paise, episode_open=bool(ep),
        contacted_oldest=f.store.contacted_oldest(ep["episode_id"]) if ep else set(),
        last_dip_nudge=f.store.last_dip_nudge(f.mid))
    if blocker == "edi_shortfall" and not ep:
        ep = f.store.start_episode(f.mid, f.persona.loan.loan_id, f.today.day)
    f.episode = ep
    return {"blocker": blocker, "reasons": reasons, "rule_ids": ids, "intent": None, "intent_source": "none"}


def _after_detect(s: State) -> str:
    return "decide" if s["blocker"] else END


def _classify(s: State) -> State:
    f = s["f"]
    intent, source = intents.classify(f.text)
    if f.reason in DISTRESS_REASONS:          # a reason chip about illness, a death or a calamity
        intent, source = "hardship", "keywords"
    f.episode = f.store.open_episode(f.mid)
    return {"blocker": "edi_shortfall" if f.episode else "reply", "intent": intent, "intent_source": source,
            "reasons": [f"reply classified as {intent} ({source})"], "rule_ids": []}


def _offer(s: State) -> State:
    f = s["f"]
    f.episode = f.store.open_episode(f.mid)
    return {"blocker": "offer_request", "intent": None, "intent_source": "none",
            "reasons": ["merchant opened the offers screen"], "rule_ids": []}


def _decide(s: State) -> State:
    f = s["f"]
    if f.mode == "day_end":
        action = policy.first_action(s["blocker"])
    elif f.mode == "offer":
        action = "show_repeat_offer"
    else:
        action = policy.intent_actions(s["intent"])[0]
    if s.get("intent") == "request_skip_today":
        n, streak = _skip_counts(f)
        return {"action": policy.skip_action(f.persona.lender, n, streak),
                "skip_requests_30d": n, "skip_consecutive": streak}
    return {"action": action, "skip_requests_30d": 0, "skip_consecutive": 0}


def _skip_counts(f: Facts) -> tuple[int, int]:
    """Requests in the rolling window and days in a row, both including today (one per day)."""
    today = f.now.date()
    days = set(f.store.skip_days(f.mid, f.persona.loan.loan_id,
                                 today - timedelta(days=policy.skip_rules()["window_days"] - 1), today)) | {today}
    streak = 0
    while today - timedelta(days=streak) in days:
        streak += 1
    return len(days), streak


def _guard(s: State) -> State:
    f = s["f"]
    ep = f.episode
    stress_days = [d.day for d in f.ledger if d.dpd >= rules.THRESHOLDS["stress_dpd"]]
    stress = [d for d in [f.store.last_stress(f.mid), max(stress_days, default=None)] if d]
    last_contact = f.store.last_contact_day(ep["episode_id"]) if ep else None
    sma_then = next((d.sma_bucket for d in f.ledger if d.day == last_contact), "standard")
    ctx = GuardContext(
        now=f.now, proactive=f.mode == "day_end", merchant=f.persona.merchant, lender=f.persona.lender,
        consent=f.consent, blocker=s["blocker"], intent=s.get("intent"),
        contacts_today=f.store.contacts_on(f.mid, f.now.date()),
        attempts=f.store.attempts(ep["episode_id"]) if ep else 0,
        total_overdue_paise=f.today.total_overdue_paise,
        last_stress=max(stress, default=None),
        episode_stopped=bool(ep and ep["stopped"]),
        last_contact_day=last_contact, sma_worse=SMA_ORDER[f.today.sma_bucket] > SMA_ORDER[sma_then],
        skip_requests_30d=s.get("skip_requests_30d", 0))
    v = guard(s["action"], ctx)
    return {"verdict": v, "action": v.action}


def _slot(now: datetime, window: tuple[int, int], hours: int) -> datetime:
    t = (now + timedelta(hours=hours)).replace(minute=0, second=0, microsecond=0)
    return t if in_window(t, window) else next_window_start(t, window)


def _render(s: State) -> State:
    f, v = s["f"], s["verdict"]
    p, today = f.persona, f.today
    lender = p.lender
    action, blocker = v.action, s["blocker"]

    tid = {
        "send_pay_link": "T_PAY_LINK", "schedule_reminder": "T_REMINDER_SET",
        "route_lower_deduction_request": "T_REQ_ROUTED", "route_reschedule_request": "T_REQ_ROUTED",
        "schedule_callback": "T_CALLBACK", "human_handoff": "T_HANDOFF", "show_repeat_offer": "T_REPEAT_OFFER",
        "acknowledge_carry_forward": "T_SKIP_ACK", "route_skip_request": "T_SKIP_ROUTED",
        "human_callback_booking": "T_SKIP_CALLBACK",
    }.get(action)
    if action == "notify_shortfall":
        if blocker == "sales_dip_risk":
            tid = "T_DIP_RISK"
        else:
            tid = "T_SHORTFALL" if today.shortfall_today_paise else "T_ARREARS"
    if action == "send_pay_link" and 0 < today.shortfall_today_paise < today.total_overdue_paise:
        tid = "T_PAY_CHOICE"
    if action == "acknowledge_carry_forward" and not today.shortfall_today_paise and not today.total_overdue_paise:
        tid = "T_SKIP_NOTHING_DUE"            # a spontaneous "can't pay today" on a day that's already covered
    if action == "no_action" and blocker == "cured" and "G1_consent" not in v.blocks:
        tid = "T_CURED"
    if not tid:
        return {"template_id": None, "message_en": "", "message_hi": "", "cue": None}

    def upi(paise: int) -> str:
        return f"upi://pay?pa={lender.vpa}&pn={quote(lender.lender_name)}&am={paise / 100:.2f}&tn={p.loan.loan_id}"

    amount = today.total_overdue_paise or p.loan.edi_paise
    link = upi(amount)
    window = effective_window(p.merchant, f.consent)
    when = _slot(f.now, window, 2 if action == "schedule_reminder" else 1)
    days = rules.THRESHOLDS["dip_window_days"]
    avg = sum(d.settlement_paise for d in f.ledger[-days:]) // max(1, len(f.ledger[-days:])) // 100 * 100
    by_lang = {}
    for lang in ("en", "hi"):
        by_lang[lang] = {
            "lender": lender.lender_name, "shortfall": rupees(today.shortfall_today_paise),
            "overdue": rupees(today.total_overdue_paise), "penal_note": lender.penal_charges_note[lang],
            "oldest": fmt_date(today.oldest_unpaid_date or today.day, lang),
            "amount": rupees(amount), "link": link,
            "short_amount": rupees(today.shortfall_today_paise), "short_link": upi(today.shortfall_today_paise), "time": f"{when:%H:%M}", "date": fmt_date(when, lang),
            "request": REQUEST_NAMES.get(action, {}).get(lang, ""), "officer": lender.grievance_officer,
            "window": days, "avg": rupees(avg), "edi": rupees(p.loan.edi_paise),
            "charges_note": getattr(lender.skip_day_policy, f"charges_note_{lang}"),
        }
        if action == "acknowledge_carry_forward":      # "pay part now": today's gap, or the EDI if none yet
            by_lang[lang]["link"] = upi(today.shortfall_today_paise or p.loan.edi_paise)
    en, hi = render_both(tid, by_lang)
    cue = SOUNDBOX_CUE[p.merchant.language] if v.channel == "soundbox_cue" else None
    return {"template_id": tid, "message_en": en, "message_hi": hi, "cue": cue}


def _soundbox(s: State) -> State:
    f, v = s["f"], s["verdict"]
    cue, channel, blocks = soundbox_guard(s.get("cue"), v.channel, f.persona.merchant.language, f.consent)
    return {"cue": cue, "channel": channel, "g5_blocks": blocks}


def _audit(s: State) -> State:
    f, v = s["f"], s["verdict"]
    p, ep = f.persona, f.episode
    channel = s["channel"]
    delivered = channel != "none"
    blocks = v.blocks + s.get("g5_blocks", [])

    request_id = None
    if delivered and v.action in ROUTED:
        note = mask(f.text) if f.text else "; ".join(s["reasons"])
        request_id = f.store.add_request(f.mid, p.loan.loan_id, p.lender.lender_id, v.action, note, f.now)
    if ep and delivered and v.stop_episode:
        f.store.stop_episode(ep["episode_id"])
    if ep and s["blocker"] == "cured":
        f.store.close_episode(ep["episode_id"], f.today.day)

    # Stress flag on the 2nd "can't pay today" in the window: no loan offers for 90 days (G4).
    if delivered and s.get("intent") == "request_skip_today" \
            and s.get("skip_requests_30d") == policy.skip_rules()["stress_flag_at_request"]:
        f.store.add_flag(f.mid, "stress", f.now, "2nd can't-pay-today request in 30 days")
    slots = callback_slots(f) if delivered and v.action == "human_callback_booking" else []

    lang = p.merchant.language
    message = s["message_hi"] if lang == "hi" else s["message_en"]
    consent = f.consent if f.consent and f.consent.active else None
    f.store.log({
        "ts": f.now.isoformat(), "merchant_id": f.mid, "loan_id": p.loan.loan_id,
        "episode_id": ep["episode_id"] if ep else None, "blocker": s["blocker"], "rule_ids": s["rule_ids"],
        "intent": s.get("intent"), "intent_source": s.get("intent_source", "none"), "action": v.action,
        "template_id": s.get("template_id"), "channel": channel,
        "consent_version": consent.notice_version if consent else None, "guard_blocks": blocks,
        "policy_ok": int(v.policy_ok), "escalated": int(v.escalated), "lender_request_id": request_id,
        "scheduled_for": v.scheduled_for.isoformat() if v.scheduled_for else None, "language": lang,
        "proactive": int(f.mode == "day_end"),
        "oldest_unpaid": f.today.oldest_unpaid_date.isoformat() if f.today.oldest_unpaid_date else None,
        "message": message,
    })
    rescue = MerchantRescue(
        merchant_id=f.mid, loan_id=p.loan.loan_id, episode_id=ep["episode_id"] if ep else None,
        blocker=s["blocker"], reasons=s["reasons"], rule_ids=s["rule_ids"], intent=s.get("intent"),
        intent_source=s.get("intent_source", "none"), action=v.action,
        needs_consent=policy.needs_consent(v.action), escalated=v.escalated, policy_ok=v.policy_ok,
        guard_blocks=blocks, channel=channel, template_id=s.get("template_id"),
        message_en=s["message_en"], message_hi=s["message_hi"],
        options=OPTIONS.get(s.get("template_id"), []) if delivered else [],
        soundbox_cue_text=s.get("cue"), lender_request_id=request_id, scheduled_for=v.scheduled_for,
        callback_slots=slots, skip_requests_30d=s.get("skip_requests_30d", 0))
    return {"rescue": rescue}


def callback_slots(f: Facts, per_day: int = 3) -> list[datetime]:
    """Callback times inside the merchant's own contact hours, over the next few days."""
    lo, hi = effective_window(f.persona.merchant, f.consent)
    hours = sorted({lo, (lo + hi) // 2, hi - 1})[:per_day]
    out = []
    for d in range(policy.skip_rules()["callback_days_ahead"] + 1):
        day = (f.now + timedelta(days=d)).date()
        out += [datetime.combine(day, dtime(h)) for h in hours if datetime.combine(day, dtime(h)) > f.now + timedelta(hours=1)]
    return out[:6]


def build():
    g = StateGraph(State)
    for name, fn in [("detect", _detect), ("classify", _classify), ("offer", _offer), ("decide", _decide),
                     ("guard", _guard), ("render", _render), ("soundbox", _soundbox), ("audit", _audit)]:
        g.add_node(name, fn)
    g.add_conditional_edges(START, _entry, {"detect": "detect", "classify": "classify", "offer": "offer"})
    g.add_conditional_edges("detect", _after_detect, {"decide": "decide", END: END})
    g.add_edge("classify", "decide")
    g.add_edge("offer", "decide")
    g.add_edge("decide", "guard")
    g.add_edge("guard", "render")
    g.add_edge("render", "soundbox")
    g.add_edge("soundbox", "audit")
    g.add_edge("audit", END)
    return g.compile()


GRAPH = build()


class Desk:
    """Holds the merchant book and store, and runs the agent for one merchant at a time."""

    def __init__(self, store: MerchantStore | None = None, book: dict[str, Persona] | None = None):
        self.store = store or MerchantStore()
        self.book = book if book is not None else personas()
        self._ledgers: dict[str, list[LedgerDay]] = {}

    def persona(self, merchant_id: str) -> Persona:
        return self.book[merchant_id]

    def date_of(self, merchant_id: str, day: int):
        return self.persona(merchant_id).loan.start_date + timedelta(days=day - 1)

    def at(self, merchant_id: str, day: int, hhmm: str = "18:00") -> datetime:
        h, m = (int(x) for x in hhmm.split(":"))
        return datetime.combine(self.date_of(merchant_id, day), dtime(h, m))

    def ledger(self, merchant_id: str, day: int | None = None) -> list[LedgerDay]:
        paid = self.store.payments(merchant_id)
        if paid:                                    # live payments: recompute (cheap), never cached
            p = self.persona(merchant_id)
            full = simulate(p.loan, p.settlements, p.lender, paid)
            return full if day is None else full[:max(1, min(day, len(full)))]
        if merchant_id not in self._ledgers:
            p = self.persona(merchant_id)
            self._ledgers[merchant_id] = simulate(p.loan, p.settlements, p.lender)
        full = self._ledgers[merchant_id]
        return full if day is None else full[:max(1, min(day, len(full)))]

    def _run(self, mode: str, merchant_id: str, day: int, now: datetime, text: str = "",
             reason: str | None = None) -> MerchantRescue:
        start = time.perf_counter()
        p = self.persona(merchant_id)
        facts = Facts(mode=mode, persona=p, ledger=self.ledger(merchant_id, day), now=now, store=self.store,
                      consent=self.store.consent(merchant_id), text=text, reason=reason)
        out = GRAPH.invoke({"f": facts})
        rescue = out.get("rescue") or MerchantRescue(
            merchant_id=merchant_id, loan_id=p.loan.loan_id, reasons=["no rule fired"])
        rescue.latency_ms = round((time.perf_counter() - start) * 1000, 2)
        self._after(p, rescue, now)
        return rescue

    def _after(self, p: Persona, rescue: MerchantRescue, now: datetime) -> None:
        """Runs only after the graph has decided and the guard has checked. Memory and partner actions
        live here, so neither can influence the action that was chosen."""
        mid = p.merchant.merchant_id
        delivered = rescue.channel != "none" and rescue.scheduled_for is None
        # Optional recall line (from facts before today) on proactive cards, including the thank-you.
        if delivered and rescue.template_id in ("T_SHORTFALL", "T_ARREARS", "T_DIP_RISK", "T_CURED")                 and memory.backend() != "off" and memory.consented(self.store, mid):
            hit = memory.recall_line(self.store, mid, now.date())
            if hit:
                tid, extra = hit
                vals = {lang: {"lender": p.lender.lender_name,
                               "request": REQUEST_NAMES.get(extra.get("request_action"), {}).get(lang, "")}
                        for lang in ("en", "hi")}
                rescue.recall_template_id = tid
                rescue.recall_en, rescue.recall_hi = render_both(tid, vals)
        memory.remember(self.store, mid, now.date(), rescue)
        # Partner action layer: only a final, delivered action. Deferred ones go when delivered.
        if delivered and rescue.action != "no_action":
            when = None
            if rescue.action == "schedule_reminder":    # the reminder time shown in the message, inside contact hours
                when = _slot(now, effective_window(p.merchant, self.store.consent(mid)), 2)
            data = actions.payload(merchant_id=mid, at=now, action=rescue.action, template_id=rescue.template_id,
                                   language=p.merchant.language, scheduled_for=when, lender_id=p.lender.lender_id)
            rescue.dispatch_status = actions.dispatch(self.store, mid, data, now)["status"]

    def run_day_end(self, merchant_id: str, day: int, now: datetime | None = None) -> MerchantRescue:
        self.store.set_sim_day(merchant_id, day)
        return self._run("day_end", merchant_id, day, now or self.at(merchant_id, day))

    def run_reply(self, merchant_id: str, text: str, now: datetime | None = None,
                  day: int | None = None, reason: str | None = None) -> MerchantRescue:
        day = day or self.store.sim_day(merchant_id)
        return self._run("reply", merchant_id, day, now or self.at(merchant_id, day, "18:05"), text, reason)

    def pay(self, merchant_id: str, amount_paise: int, now: datetime | None = None) -> dict:
        """The owner pays through the pay link (simulated UPI in the demo). The lender's ledger records it;
        Pakka only confirms the lender's figures."""
        p = self.persona(merchant_id)
        day = self.store.sim_day(merchant_id)
        now = now or self.at(merchant_id, day, "18:20")
        owed = self.ledger(merchant_id, day)[-1].total_overdue_paise
        if amount_paise <= 0 or owed <= 0:
            raise ValueError("nothing is due")
        amount = min(amount_paise, owed)
        self.store.add_payment(merchant_id, now.date(), amount, "upi_link_simulated", now)
        after = self.ledger(merchant_id, day)[-1]
        tid = "T_PAYMENT_ALL_CLEAR" if after.total_overdue_paise == 0 else "T_PAYMENT_RECEIVED"
        vals = {lang: {"lender": p.lender.lender_name, "amount": rupees(amount),
                       "overdue": rupees(after.total_overdue_paise)} for lang in ("en", "hi")}
        en, hi = render_both(tid, vals)
        self.store.log({"ts": now.isoformat(), "merchant_id": merchant_id, "loan_id": p.loan.loan_id,
                        "blocker": "payment", "rule_ids": [], "intent": None, "intent_source": "none",
                        "action": "no_action", "template_id": tid, "channel": "app_card", "guard_blocks": [],
                        "policy_ok": 1, "escalated": 0, "language": p.merchant.language, "proactive": 0,
                        "message": hi if p.merchant.language == "hi" else en})
        if after.total_overdue_paise == 0 and memory.consented(self.store, merchant_id):
            self.store.memory_add(merchant_id, now.date(), "paid_up", "{}")
        return {"template_id": tid, "message_en": en, "message_hi": hi, "paid_paise": amount,
                "total_due_paise": after.total_overdue_paise, "ledger_day": after}

    def book_callback(self, merchant_id: str, slot: datetime, now: datetime | None = None) -> dict:
        """Book a callback with a person at the lender, only inside the merchant's contact hours."""
        p = self.persona(merchant_id)
        now = now or self.at(merchant_id, self.store.sim_day(merchant_id), "18:10")
        window = effective_window(p.merchant, self.store.consent(merchant_id))
        if not in_window(slot, window):
            raise ValueError(f"slot {slot:%H:%M} is outside the merchant's contact hours")
        if not now < slot <= now + timedelta(days=policy.skip_rules()["callback_days_ahead"] + 1):
            raise ValueError("slot must be in the next few days")
        appt = self.store.add_appointment(merchant_id, p.loan.loan_id, p.lender.lender_id, slot,
                                          reminder_at=slot, at=now, reason="can't pay today, repeatedly")
        vals = {lang: {"lender": p.lender.lender_name, "time": f"{slot:%H:%M}", "date": fmt_date(slot, lang)}
                for lang in ("en", "hi")}
        en, hi = render_both("T_CALLBACK_BOOKED", vals)
        data = actions.payload(merchant_id=merchant_id, at=now, action="schedule_callback",
                               template_id="T_CALLBACK_BOOKED", language=p.merchant.language, scheduled_for=slot,
                               lender_id=p.lender.lender_id)
        actions.dispatch(self.store, merchant_id, data, now)
        self.store.log({"ts": now.isoformat(), "merchant_id": merchant_id, "loan_id": p.loan.loan_id,
                        "blocker": "reply", "rule_ids": [], "intent": None, "intent_source": "none",
                        "action": "schedule_callback", "template_id": "T_CALLBACK_BOOKED", "channel": "app_card",
                        "guard_blocks": [], "policy_ok": 1, "escalated": 1, "language": p.merchant.language,
                        "proactive": 0, "message": hi if p.merchant.language == "hi" else en,
                        "scheduled_for": slot.isoformat()})
        return {**appt, "message_en": en, "message_hi": hi}

    def check_offer(self, merchant_id: str, now: datetime | None = None, day: int | None = None) -> MerchantRescue:
        day = day or self.store.sim_day(merchant_id)
        return self._run("offer", merchant_id, day, now or self.at(merchant_id, day, "18:10"))
