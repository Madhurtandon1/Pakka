"""Action layer: hands a FINAL, guard-checked, delivered action to n8n (or a simulated outbox).

"Sarvam understands and speaks. Cognee remembers. Rules and guards decide. n8n acts. People handle
hard cases." n8n never chooses anything: it receives an action Pakka's guard has already approved.

The payload carries no names, phone numbers, message text or amounts, only ids, codes and times.
n8n would look details up by id in production; in the demo it just logs. Optional: with no
N8N_WEBHOOK_URL (the default) or on any error, the same payload goes to a local outbox, "simulated".
"""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import datetime

REQUIRES_HUMAN = {"human_handoff", "human_callback_booking", "schedule_callback", "route_lower_deduction_request",
                  "route_reschedule_request", "route_skip_request"}
LAST = {"mode": None, "status": None, "detail": None}      # shown in the partner status strip


def webhook_url() -> str:
    return os.getenv("N8N_WEBHOOK_URL", "").strip()


def _secret() -> bytes:
    return os.getenv("N8N_WEBHOOK_SECRET", "pakka-demo-secret").encode()


def pseudonym(merchant_id: str) -> str:
    """Stable pseudonymous id: n8n can join on it, but it isn't the merchant's id or name."""
    return "m_" + hmac.new(_secret(), merchant_id.encode(), hashlib.sha256).hexdigest()[:12]


def event_id(merchant_id: str, at: datetime, action: str, template_id: str | None) -> str:
    raw = f"{merchant_id}|{at.isoformat()}|{action}|{template_id or ''}"
    return "ev_" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def payload(*, merchant_id: str, at: datetime, action: str, template_id: str | None, language: str,
            scheduled_for: datetime | None, lender_id: str) -> dict:
    return {
        "event_id": event_id(merchant_id, at, action, template_id),
        "merchant_id": pseudonym(merchant_id),
        "action": action,
        "template_id": template_id,
        "language": language,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "lender_id": lender_id,
        "requires_human": action in REQUIRES_HUMAN,
    }


def canonical(data: dict) -> bytes:
    """Compact JSON with sorted keys: n8n's Code node rebuilds exactly these bytes to check the HMAC."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(_secret(), body, hashlib.sha256).hexdigest()


def _post(url: str, body: bytes, event: str) -> int:
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "X-Pakka-Signature": sign(body), "X-Pakka-Event-Id": event})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.status


def dispatch(store, merchant_id: str, data: dict, at: datetime) -> dict:
    """Send one final action. Idempotent on event_id: a repeated event is not sent again."""
    seen = store.outbox_get(data["event_id"])
    if seen:
        return seen
    body = canonical(data)
    url = webhook_url()
    status, detail = "simulated", "N8N_WEBHOOK_URL not set: written to the local outbox"
    if url:
        for attempt in (1, 2):                     # one retry
            try:
                code = _post(url, body, data["event_id"])
                if 200 <= code < 300:
                    status, detail = "sent_n8n", f"n8n answered {code}"
                    break
                detail = f"n8n answered {code}"
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                detail = f"n8n unreachable ({type(exc).__name__}) on attempt {attempt}"
        if status != "sent_n8n":
            status = "failed_fallback"
            detail += ": kept in the local outbox instead"
    LAST.update(mode="live" if url else "simulated", status=status, detail=detail)
    store.outbox_add(data["event_id"], merchant_id, data["action"], body.decode(), status, detail, at)
    if data["requires_human"] and status != "sent_n8n":
        # Without n8n, the simulated dispatcher puts hard cases straight into the people queue.
        store.queue_add(data["event_id"], data["merchant_id"], data["action"],
                        "needs a person (simulated dispatcher)", "simulated", at)
    return store.outbox_get(data["event_id"])
