import json
from functools import lru_cache
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("policy.json")


class PolicyViolation(Exception):
    pass


@lru_cache
def load() -> dict:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def allowed(blocker: str) -> list[str]:
    return load()["blockers"].get(blocker, [])


def choose(blocker: str, attempts: int) -> str:
    options = allowed(blocker)
    if not options:
        return "human_handoff"
    if attempts >= load()["max_attempts_before_handoff"] and "human_handoff" in options:
        return "human_handoff"
    return options[min(attempts, len(options) - 1)]


def check(blocker: str, action: str) -> None:
    ok = action in allowed(blocker) or (action == "human_handoff" and not allowed(blocker))
    if not ok:
        raise PolicyViolation(f"{action} is not approved for {blocker}")


def needs_consent(action: str) -> bool:
    return load()["actions"].get(action, {}).get("needs_consent", True)


def ladder(blocker: str, code: str | None = None) -> list[str]:
    """The ordered actions for a blocker, using a per-cause order from code_ladders if there is one."""
    by_code = load().get("code_ladders", {}).get(blocker, {})
    return by_code.get(code or "", allowed(blocker))


def choose_for(blocker: str, code: str | None, attempts: int) -> str:
    """Like choose(), but follows a per-cause ladder when policy.json has one.
    Blockers without code_ladders get exactly choose(blocker, attempts)."""
    if code not in load().get("code_ladders", {}).get(blocker, {}):
        return choose(blocker, attempts)
    options = ladder(blocker, code)
    if attempts >= load()["max_attempts_before_handoff"] and "human_handoff" in options:
        return "human_handoff"
    return options[min(attempts, len(options) - 1)]


FORBIDDEN = ("approve", "reject", "decline", "waive", "sanction", "disburse", "change_loan",
             "reschedule_loan", "limit")


def decides_loan(action: str) -> bool:
    """True for anything that would approve, reject or change the loan. No approved action may."""
    return any(word in action for word in FORBIDDEN)
