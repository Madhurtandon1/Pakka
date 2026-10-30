import time
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from . import policy
from .docs_detector import detect_all
from .explain import explain
from .models import Detection, Event, Rescue


class State(TypedDict, total=False):
    events: list[Event]
    now: float
    attempts: int
    lang: str
    detection: Detection
    action: Optional[str]
    message: Optional[str]
    policy_ok: bool
    escalated: bool


def _detect(state: State) -> State:
    # Existing rules first (unchanged), then the document-step rules.
    return {"detection": detect_all(state["events"], state["now"])}


def _decide(state: State) -> State:
    d = state["detection"]
    # Same as policy.choose() for every blocker without a per-cause ladder.
    action = policy.choose_for(d.blocker, d.code, state.get("attempts", 0))
    return {"action": action, "escalated": action == "human_handoff"}


def _guard(state: State) -> State:
    try:
        policy.check(state["detection"].blocker, state["action"])
        if policy.decides_loan(state["action"]):
            raise policy.PolicyViolation("Pakka never approves, rejects or changes a loan")
        return {"policy_ok": True}
    except policy.PolicyViolation:
        return {"policy_ok": False, "action": "human_handoff", "escalated": True}


def _explain(state: State) -> State:
    d = state["detection"]
    return {"message": explain(state["action"], state.get("lang", "en"), d.step, d.code)}


def _route(state: State) -> str:
    return "decide" if state["detection"].stalled else END


def build():
    g = StateGraph(State)
    g.add_node("detect", _detect)
    g.add_node("decide", _decide)
    g.add_node("guard", _guard)
    g.add_node("explain", _explain)
    g.set_entry_point("detect")
    g.add_conditional_edges("detect", _route, {"decide": "decide", END: END})
    g.add_edge("decide", "guard")
    g.add_edge("guard", "explain")
    g.add_edge("explain", END)
    return g.compile()


GRAPH = build()


def rescue(journey_id: str, events: list[Event], now: float, attempts: int = 0, lang: str = "en") -> Rescue:
    start = time.perf_counter()
    out = GRAPH.invoke({"events": events, "now": now, "attempts": attempts, "lang": lang})
    action = out.get("action")
    return Rescue(
        journey_id=journey_id,
        detection=out["detection"],
        action=action,
        needs_consent=policy.needs_consent(action) if action else False,
        message=out.get("message"),
        lang=lang,
        escalated=out.get("escalated", False),
        policy_ok=out.get("policy_ok", True),
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )
