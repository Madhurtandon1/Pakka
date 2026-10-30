"""Sarvam provider for merchant reply labelling, tested with a mocked sarvamai client (no SDK or network)."""
import json
import sys
from pathlib import Path

import pytest

from pakka.merchant import intents
from pakka.merchant.intents import SYSTEM_PROMPT

EVAL = Path(__file__).resolve().parents[1] / "eval"


class FakeChat:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def completions(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        msg = type("Msg", (), {"content": self.reply})()
        usage = type("Usage", (), {"prompt_tokens": 120, "completion_tokens": 4, "total_tokens": 124})()
        return type("Resp", (), {"choices": [type("Choice", (), {"message": msg})()], "usage": usage})()


class TooManyRequestsError(Exception):
    status_code = 429


@pytest.fixture
def sarvam(monkeypatch):
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "sarvam")
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    monkeypatch.delenv("PAKKA_LLM_MODEL", raising=False)

    def use(reply=None, error=None):
        chat = FakeChat(reply, error)
        monkeypatch.setattr(intents, "_sarvam_client", lambda: type("Client", (), {"chat": chat})())
        return chat
    return use


def test_sarvam_enabled_by_key_and_defaults_to_sarvam_105b(monkeypatch):
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "sarvam")
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert not intents.llm_enabled()
    monkeypatch.setenv("SARVAM_API_KEY", "k")
    monkeypatch.delenv("PAKKA_LLM_MODEL", raising=False)
    assert intents.llm_enabled() and intents.llm_model() == "sarvam-105b"


def test_sarvam_valid_label_and_request_shape(sarvam):
    chat = sarvam(reply="  Will_Pay_Later\n")
    assert intents.classify("kal de dunga") == ("will_pay_later", "llm_sarvam")
    call = chat.calls[0]
    assert call["model"] == "sarvam-105b" and call["temperature"] == 0
    assert call["reasoning_effort"] is None and call["max_tokens"] <= 32          # non-think, small output
    assert call["request_options"]["timeout_in_seconds"] == 8
    assert call["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}


@pytest.mark.parametrize("reply", ["approve my loan", "", None, "label: will_pay_today", "will_pay_today."])
def test_sarvam_invalid_label_becomes_unclear(sarvam, reply):
    sarvam(reply=reply)
    assert intents.classify("hmm ok") == ("unclear", "llm_sarvam")


@pytest.mark.parametrize("error", [TooManyRequestsError("429"), TimeoutError("8s"), RuntimeError("boom")])
def test_sarvam_error_falls_back_to_keywords(sarvam, error):
    sarvam(error=error)
    assert intents.classify("kal de dunga") == ("will_pay_later", "keywords")


def test_missing_sdk_falls_back_to_keywords_with_a_warning(monkeypatch, caplog):
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "sarvam")
    monkeypatch.setenv("SARVAM_API_KEY", "k")
    monkeypatch.setitem(sys.modules, "sarvamai", None)          # import now fails
    with caplog.at_level("WARNING"):
        assert intents.classify("kal de dunga") == ("will_pay_later", "keywords")
    assert "sarvamai SDK isn't installed" in caplog.text


def test_pii_is_masked_before_the_sarvam_call(sarvam):
    chat = sarvam(reply="request_callback")
    intents.classify("call me on 9876543210 or a@b.com, PAN ABCDE1234F")
    sent = chat.calls[0]["messages"][1]["content"]
    assert "9876543210" not in sent and "a@b.com" not in sent and "ABCDE1234F" not in sent
    assert "[PHONE]" in sent and "[EMAIL]" in sent and "[PAN]" in sent


def test_usage_is_counted(sarvam):
    sarvam(reply="will_pay_later")
    intents.LLM_USAGE.clear()
    intents.classify("kal de dunga")
    assert intents.LLM_USAGE["total_tokens"] == 124


def test_distress_never_reaches_sarvam(sarvam):
    chat = sarvam(reply="will_pay_today")
    assert intents.classify("bimar tha, dukaan band thi") == ("hardship", "keywords")
    assert chat.calls == []


def test_prompt_contains_nothing_from_any_holdout_set():
    for path in EVAL.glob("intent_holdout*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        texts = [r["text"] for r in data] if isinstance(data, list) and data and "text" in data[0] else []
        for t in texts:
            assert t not in SYSTEM_PROMPT, (path.name, t)


def test_default_is_still_offline_keywords(monkeypatch):
    monkeypatch.delenv("PAKKA_LLM_PROVIDER", raising=False)
    assert not intents.llm_enabled()
    assert intents.classify("kal de dunga") == ("will_pay_later", "keywords")
