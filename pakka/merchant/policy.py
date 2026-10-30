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
