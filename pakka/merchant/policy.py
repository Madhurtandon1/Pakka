import json
from functools import lru_cache
from pathlib import Path

from pakka.policy import PolicyViolation  # noqa: F401  (shared exception type)

POLICY_PATH = Path(__file__).with_name("policy.json")


@lru_cache
def load() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def notice_version() -> str:
    return load()["notice_version"]


def first_action(blocker: str) -> str:
    return load()["blocker_first_action"].get(blocker, "human_handoff")


def intent_actions(intent: str) -> list[str]:
    return load()["intent_actions"].get(intent, ["schedule_callback"])


def needs_consent(action: str) -> bool:
    return load()["needs_consent"].get(action, True)


def max_attempts() -> int:
    return load()["max_attempts_before_handoff"]


def skip_rules() -> dict:
    return load()["skip_today"]


def skip_action(lender, requests_30d: int, consecutive_days: int) -> str:
    """The "can't pay today" ladder. requests_30d and consecutive_days include today's request.

    3rd request in the window, or a 3rd day in a row, or over the lender's own limit -> a person (callback);
    a request-only lender -> route the request; otherwise explain the lender's carry-forward.
    """
    r = skip_rules()
    cfg = lender.skip_day_policy
    if (requests_30d >= r["callback_at_request"] or consecutive_days >= r["callback_at_consecutive_days"]
            or (cfg.mode == "auto_carry_forward" and requests_30d > cfg.max_auto_per_30_days)):
        return "human_callback_booking"
    if cfg.mode != "auto_carry_forward":
        return "route_skip_request"
    return "acknowledge_carry_forward"
