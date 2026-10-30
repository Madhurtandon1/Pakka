import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from pakka import sarvam
from pakka.merchant import intents, policy
from pakka.merchant.agent import Desk
from pakka.merchant.guard import effective_window, in_window
from pakka.merchant.models import ConsentIn
from pakka.merchant.rules import THRESHOLDS
from pakka.merchant.synth import DAYS
from pakka.merchant.templates import SOUNDBOX_CUE

STATIC = Path(__file__).with_name("static")
RESULTS = Path(__file__).resolve().parents[1] / "eval" / "merchant_results.json"

router = APIRouter(prefix="/merchant")
desk = Desk()


class ReplyIn(BaseModel):
    text: str
    now: str | None = None          # "HH:MM" on the current simulated day


class SpeakIn(BaseModel):
    text: str
    lang: str = "hi"


def _persona(mid: str):
    if mid not in desk.book:
        raise HTTPException(404, "unknown merchant")
    return desk.persona(mid)


def _hhmm(value: str | None, default: str) -> str:
    value = value or default
    try:
        h, m = (int(x) for x in value.split(":"))
        assert 0 <= h < 24 and 0 <= m < 60
    except Exception:
        raise HTTPException(422, "time must be HH:MM")
    return f"{h:02d}:{m:02d}"


@router.get("")
def page():
    return FileResponse(STATIC / "merchant.html")


@router.get("/personas")
def list_personas():
    out = []
    for mid, p in desk.book.items():
        out.append({
            "merchant_id": mid, "display_name": p.merchant.display_name, "language": p.merchant.language,
            "title": p.title, "story": p.story, "lender": p.lender.lender_name,
            "shortfall_mode": p.lender.shortfall_mode, "edi_paise": p.loan.edi_paise,
            "soundbox_id": p.merchant.soundbox_id, "contact_window": p.merchant.contact_window,
            "day": desk.store.sim_day(mid), "grievance_officer": p.lender.grievance_officer,
            "preferred_window": (desk.store.consent(mid).contact_window if desk.store.consent(mid) else None),
        })
    return {"personas": out, "days": DAYS, "notice_version": policy.notice_version(),
            "soundbox_cues": SOUNDBOX_CUE, "thresholds": THRESHOLDS, "classifier": classifier()}


def classifier() -> dict:
    """Which reader is labelling merchant replies right now. The fail-safe applies either way."""
    if intents.llm_enabled():
        return {"mode": "llm", "provider": intents.llm_provider(), "model": intents.llm_model()}
    return {"mode": "keywords", "provider": None, "model": None}


@router.post("/reset")
def reset():
    desk.store.reset()
    return {"ok": True}


@router.get("/{mid}/consent")
def get_consent(mid: str):
    _persona(mid)
    c = desk.store.consent(mid)
    return {"consent": c.model_dump() if c else None, "active": bool(c and c.active),
            "history": desk.store.consent_history(mid)}


@router.post("/{mid}/consent")
def grant_consent(mid: str, body: ConsentIn, now: str | None = None):
    _persona(mid)
    if body.notice_version != policy.notice_version():
        raise HTTPException(400, f"notice_version must be {policy.notice_version()}")
    at = desk.at(mid, desk.store.sim_day(mid), _hhmm(now, "09:00"))
    return desk.store.grant_consent(mid, body, at).model_dump()


@router.delete("/{mid}/consent")
def withdraw_consent(mid: str, now: str | None = None):
    _persona(mid)
    at = desk.at(mid, desk.store.sim_day(mid), _hhmm(now, "09:00"))
    return {"withdrawn": desk.store.withdraw_consent(mid, at)}


@router.post("/{mid}/simulate")
def simulate_day(mid: str, day: int = Query(ge=1, le=DAYS), now: str | None = None):
    _persona(mid)
    rescue = desk.run_day_end(mid, day, desk.at(mid, day, _hhmm(now, "18:00")))
    return {"rescue": rescue, "ledger_day": desk.ledger(mid, day)[-1]}


@router.post("/{mid}/reply")
def reply(mid: str, body: ReplyIn):
    _persona(mid)
    day = desk.store.sim_day(mid)
    return desk.run_reply(mid, body.text, desk.at(mid, day, _hhmm(body.now, "18:05")), day)


@router.get("/{mid}/offers")
def offers(mid: str):
    _persona(mid)
    return desk.check_offer(mid)


@router.get("/{mid}/ledger")
def ledger(mid: str, day: int | None = Query(default=None, ge=1, le=DAYS)):
    p = _persona(mid)
    day = day or desk.store.sim_day(mid)
    return {"merchant_id": mid, "lender": p.lender.lender_name, "shortfall_mode": p.lender.shortfall_mode,
            "day": day, "rows": desk.ledger(mid, day)}


@router.get("/lender/requests")
def lender_requests(lender_id: str | None = None):
    return desk.store.requests(lender_id)


@router.get("/audit")
def audit(limit: int = 100, merchant_id: str | None = None):
    return desk.store.audit(limit, merchant_id)


def live_violations(rows: list[dict]) -> list[str]:
    """Re-check every audit row against the hard rules. Must always be empty."""
    out, per_day = [], Counter()
    for r in rows:
        if r["merchant_id"] not in desk.book:
            continue
        p = desk.persona(r["merchant_id"])
        delivered = r["channel"] != "none"
        if r["proactive"] and delivered:
            ts = datetime.fromisoformat(r["ts"])
            if not in_window(ts, effective_window(p.merchant, desk.store.consent(r["merchant_id"]))):
                out.append(f"contact outside window: {r['merchant_id']} {r['ts']}")
            per_day[(r["merchant_id"], r["ts"][:10])] += 1
        if delivered and r["action"] not in ("no_action", "human_handoff") and r["action"] not in p.lender.allowed_actions:
            out.append(f"action outside lender scope: {r['merchant_id']} {r['action']}")
        distress_reply = not r["proactive"] and r["intent"] in ("dispute", "hardship", "already_paid")
        if delivered and not r["consent_version"] and not (distress_reply and r["action"] == "human_handoff"):
            out.append(f"contact without consent: {r['merchant_id']} {r['ts']}")
        if distress_reply and r["action"] != "human_handoff":
            out.append(f"distress not handed off: {r['merchant_id']}")
    out += [f"more than one proactive contact on {d}: {m}" for (m, d), n in per_day.items() if n > 1]
    return out


@router.get("/dashboard")
def dashboard():
    rows = desk.store.audit(limit=100_000)
    delivered = [r for r in rows if r["channel"] != "none"]
    episodes = desk.store.episodes()

    def cured_within(n: int) -> int:
        return sum(1 for e in episodes if e["closed_day"] and
                   (date.fromisoformat(e["closed_day"]) - date.fromisoformat(e["opened_day"])).days <= n)

    blocks = Counter(b.split(" ")[0].split(":")[0] for r in rows for b in r["guard_blocks"])
    out = {
        "flagged": len({r["merchant_id"] for r in rows if r["blocker"] in ("edi_shortfall", "sales_dip_risk")}),
        "contacted": len({r["merchant_id"] for r in delivered if r["proactive"]}),
        "episodes": len(episodes),
        "cured_within_1_day": cured_within(1),
        "cured_within_7_days": cured_within(7),
        "handoffs": sum(1 for r in delivered if r["action"] == "human_handoff"),
        "routed_requests": len(desk.store.requests()),
        "guard_blocks": dict(blocks),
        "guard_violations": len(live_violations(rows)),
        "violations": live_violations(rows)[:20],
    }
    if RESULTS.exists():
        out["eval"] = json.loads(RESULTS.read_text(encoding="utf-8"))
    return out


@router.post("/{mid}/soundbox/speak")
def soundbox_speak(mid: str, body: SpeakIn):
    _persona(mid)
    if body.lang not in SOUNDBOX_CUE or body.text != SOUNDBOX_CUE[body.lang]:
        raise HTTPException(400, "the Soundbox only plays the neutral cue")
    if not sarvam.enabled():
        raise HTTPException(503, "SARVAM_API_KEY not set; the page falls back to browser speech")
    try:
        return Response(sarvam.tts(body.text, body.lang), media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(502, f"Sarvam TTS failed: {exc}") from exc
