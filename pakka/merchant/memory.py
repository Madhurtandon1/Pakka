"""Merchant memory: CONTEXT ONLY. It can fill an optional, pre-written recall line on the app card;
it is never passed to the policy or the guard and can't change an action (it runs after the graph).

Backends, chosen by PAKKA_MEMORY:
  sqlite (default) - a per-merchant timeline of structured facts in the local store
  cognee           - also sends the same masked facts to Cognee (needs `pip install cognee` and
                     LLM_API_KEY per Cognee's docs); any error falls back to the local timeline
  off              - remember nothing

Only structured facts are kept (dates, intent labels, request types and statuses, handoffs, paid-up),
never free text, names, phone numbers or amounts. Only for merchants with active alerts consent;
withdrawing consent deletes the memory in both backends.
"""
import asyncio
import json
import os

from .actions import pseudonym

STATE = {"backend": None, "error": None}      # shown in the partner status strip

REQUEST_KINDS = {"route_lower_deduction_request", "route_reschedule_request", "route_skip_request"}


def backend() -> str:
    b = os.getenv("PAKKA_MEMORY", "sqlite").lower()
    return b if b in ("sqlite", "cognee", "off") else "sqlite"


def _dataset(merchant_id: str) -> str:
    return f"pakka_{pseudonym(merchant_id)}"


def _cognee(fn: str, *args, **kwargs):
    """Call the documented cognee API (remember / recall / forget). Raises if cognee isn't usable."""
    import cognee  # optional dependency
    if not os.getenv("LLM_API_KEY"):
        raise RuntimeError("Cognee needs LLM_API_KEY")
    return asyncio.run(getattr(cognee, fn)(*args, **kwargs))


def _sentence(day: str, kind: str, data: dict) -> str:
    bits = ", ".join(f"{k}={v}" for k, v in sorted(data.items()))
    return f"{day}: {kind}" + (f" ({bits})" if bits else "")


def consented(store, merchant_id: str) -> bool:
    c = store.consent(merchant_id)
    return bool(c and c.active and c.early_warning_alerts)


def facts_from(rescue) -> list[tuple[str, dict]]:
    """Turn a final rescue into structured facts. No text, no amounts."""
    out = []
    delivered = rescue.channel != "none"
    if rescue.blocker == "edi_shortfall" and delivered and "R1_shortfall" in rescue.rule_ids:
        out.append(("shortfall", {}))
    if rescue.blocker == "cured":
        out.append(("paid_up", {}))
    if rescue.intent:
        out.append(("reply", {"intent": rescue.intent}))
    if rescue.lender_request_id and rescue.action in REQUEST_KINDS:
        out.append(("request", {"type": rescue.action, "status": "pending_lender_decision"}))
    if rescue.action == "human_handoff" and delivered:
        out.append(("handoff", {}))
    return out


def remember(store, merchant_id: str, day, rescue) -> None:
    b = backend()
    if b == "off" or not consented(store, merchant_id):
        return
    facts = facts_from(rescue)
    for kind, data in facts:
        store.memory_add(merchant_id, day, kind, json.dumps(data, sort_keys=True))
    STATE.update(backend="local")
    if b == "cognee" and facts:
        try:
            text = "\n".join(_sentence(day.isoformat(), k, d) for k, d in facts)
            _cognee("remember", text, dataset_name=_dataset(merchant_id))
            STATE.update(backend="cognee", error=None)
        except Exception as exc:                          # missing package, no key, API error
            STATE.update(backend="local", error=f"Cognee unavailable ({type(exc).__name__}): using local memory")


def timeline(store, merchant_id: str) -> list[dict]:
    return [{"day": r["day"], "kind": r["kind"], **json.loads(r["data"] or "{}")} for r in store.memory(merchant_id)]


def recall(store, merchant_id: str, question: str = "What happened before?") -> dict:
    """What Pakka remembers, for the lender's Memory panel. Cognee answers if it's on and working."""
    items = timeline(store, merchant_id)
    out = {"backend": "local", "items": items, "answer": None}
    if backend() == "cognee" and items:
        try:
            res = _cognee("recall", query_text=question, datasets=[_dataset(merchant_id)])
            out.update(backend="cognee", answer=[getattr(r, "text", str(r)) for r in (res or [])][:5])
        except Exception as exc:
            out["note"] = f"Cognee unavailable ({type(exc).__name__}): showing local memory"
    return out


def forget(store, merchant_id: str) -> None:
    """Consent withdrawn: delete this merchant's memory in both backends."""
    store.memory_forget(merchant_id)
    if backend() == "cognee":
        try:
            _cognee("forget", dataset=_dataset(merchant_id))
        except Exception as exc:
            STATE.update(error=f"Cognee forget failed ({type(exc).__name__}); local memory deleted")


def recall_line(store, merchant_id: str, before_day) -> tuple[str, dict] | None:
    """Pick an optional, pre-written recall template from facts BEFORE today. Never decides anything."""
    items = [i for i in timeline(store, merchant_id) if i["day"] < before_day.isoformat()]
    if not items:
        return None
    pending = [i for i in items if i["kind"] == "request" and i.get("status") == "pending_lender_decision"]
    if pending:
        return "T_RECALL_PENDING_REQUEST", {"request_action": pending[-1]["type"]}
    later = [i for i in items if i["kind"] == "reply" and i.get("intent") == "will_pay_later"]
    if later and any(i["kind"] == "paid_up" and i["day"] > later[-1]["day"] for i in items):
        return "T_RECALL_PAID", {}
    return None
