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

from . import intents, policy, rules
from .guard import GuardContext, Verdict, effective_window, guard, in_window, next_window_start, soundbox_guard
from .ledger import simulate
from .models import ConsentRecord, LedgerDay, MerchantRescue
from .store import MerchantStore
from .synth import Persona, personas
from .templates import OPTIONS, REQUEST_NAMES, SOUNDBOX_CUE, fmt_date, render_both, rupees

SMA_ORDER = {"standard": 0, "SMA-0": 1, "SMA-1": 2, "SMA-2": 3, "NPA": 4}
ROUTED = {"route_lower_deduction_request", "route_reschedule_request", "human_handoff"}


@dataclass
class Facts:
    mode: str                       # "day_end" | "reply" | "offer"
    persona: Persona
    ledger: list[LedgerDay]
    now: datetime
    store: MerchantStore
    consent: Optional[ConsentRecord] = None
    text: str = ""
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
    return {"action": action}


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
        last_contact_day=last_contact, sma_worse=SMA_ORDER[f.today.sma_bucket] > SMA_ORDER[sma_then])
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
    }.get(action)
    if action == "notify_shortfall":
        if blocker == "sales_dip_risk":
            tid = "T_DIP_RISK"
        else:
            tid = "T_SHORTFALL" if today.shortfall_today_paise else "T_ARREARS"
    if action == "send_pay_link" and 0 < today.shortfall_today_paise < today.total_overdue_paise:
        tid = "T_PAY_CHOICE"
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
            "oldest": fmt_date(today.oldest_unpaid_date) if today.oldest_unpaid_date else fmt_date(today.day),
            "amount": rupees(amount), "link": link,
            "short_amount": rupees(today.shortfall_today_paise), "short_link": upi(today.shortfall_today_paise), "time": f"{when:%H:%M}", "date": fmt_date(when),
            "request": REQUEST_NAMES.get(action, {}).get(lang, ""), "officer": lender.grievance_officer,
            "window": days, "avg": rupees(avg), "edi": rupees(p.loan.edi_paise),
        }
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
        soundbox_cue_text=s.get("cue"), lender_request_id=request_id, scheduled_for=v.scheduled_for)
    return {"rescue": rescue}


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
        if merchant_id not in self._ledgers:
            p = self.persona(merchant_id)
            self._ledgers[merchant_id] = simulate(p.loan, p.settlements, p.lender)
        full = self._ledgers[merchant_id]
        return full if day is None else full[:max(1, min(day, len(full)))]

    def _run(self, mode: str, merchant_id: str, day: int, now: datetime, text: str = "") -> MerchantRescue:
        start = time.perf_counter()
        p = self.persona(merchant_id)
        facts = Facts(mode=mode, persona=p, ledger=self.ledger(merchant_id, day), now=now, store=self.store,
                      consent=self.store.consent(merchant_id), text=text)
        out = GRAPH.invoke({"f": facts})
        rescue = out.get("rescue") or MerchantRescue(
            merchant_id=merchant_id, loan_id=p.loan.loan_id, reasons=["no rule fired"])
        rescue.latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return rescue

    def run_day_end(self, merchant_id: str, day: int, now: datetime | None = None) -> MerchantRescue:
        self.store.set_sim_day(merchant_id, day)
        return self._run("day_end", merchant_id, day, now or self.at(merchant_id, day))

    def run_reply(self, merchant_id: str, text: str, now: datetime | None = None,
                  day: int | None = None) -> MerchantRescue:
        day = day or self.store.sim_day(merchant_id)
        return self._run("reply", merchant_id, day, now or self.at(merchant_id, day, "18:05"), text)

    def check_offer(self, merchant_id: str, now: datetime | None = None, day: int | None = None) -> MerchantRescue:
        day = day or self.store.sim_day(merchant_id)
        return self._run("offer", merchant_id, day, now or self.at(merchant_id, day, "18:10"))
