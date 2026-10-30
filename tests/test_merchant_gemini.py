"""Gemini provider for merchant reply labelling, tested with a mocked google-genai client (no SDK or network)."""
import json

import pytest

from eval import intent_holdout
from pakka.merchant import intents
from pakka.merchant.intents import SYSTEM_PROMPT


class FakeModels:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def generate_content(self, *, model, contents, config=None):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error
        return type("Resp", (), {"text": self.reply})()


class FakeClient:
    def __init__(self, models):
        self.models = models


class RateLimited(Exception):
    """Stands in for google.genai.errors.ClientError, which carries .code == 429."""
    code = 429


@pytest.fixture
def gemini(monkeypatch):
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("PAKKA_LLM_API_KEY", "test-key")
    monkeypatch.setenv("PAKKA_LLM_MODEL", "gemini-test-model")

    def use(reply=None, error=None):
        models = FakeModels(reply, error)
        monkeypatch.setattr(intents, "_gemini_client", lambda: FakeClient(models))
        return models
    return use


def test_gemini_needs_provider_key_and_model(monkeypatch):
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("PAKKA_LLM_API_KEY", "k")
    monkeypatch.delenv("PAKKA_LLM_MODEL", raising=False)
    assert not intents.llm_enabled()                     # no default Gemini model
    monkeypatch.setenv("PAKKA_LLM_MODEL", "gemini-test-model")
    assert intents.llm_enabled()
    monkeypatch.delenv("PAKKA_LLM_API_KEY")
    assert not intents.llm_enabled()


def test_gemini_request_shape(gemini):
    models = gemini(reply="  Will_Pay_Later \n")
    assert intents.classify("kal de dunga") == ("will_pay_later", "llm")
    call = models.calls[0]
    assert call["model"] == "gemini-test-model" and call["contents"] == "kal de dunga"
    assert call["config"] == {"system_instruction": SYSTEM_PROMPT, "temperature": 0}


def test_gemini_sees_masked_text_only(gemini):
    models = gemini(reply="request_callback")
    intents.classify("call me on 9876543210, PAN ABCDE1234F")
    sent = models.calls[0]["contents"]
    assert "9876543210" not in sent and "[PHONE]" in sent and "[PAN]" in sent


@pytest.mark.parametrize("reply", ["approve my loan", "", None, "Label: will_pay_today"])
def test_gemini_unknown_or_empty_label_becomes_unclear(gemini, reply):
    gemini(reply=reply)
    assert intents.classify("hmm ok") == ("unclear", "llm")


@pytest.mark.parametrize("error", [RateLimited("429 RESOURCE_EXHAUSTED"), RuntimeError("network down")])
def test_gemini_error_or_429_falls_back_to_keywords(gemini, error):
    gemini(error=error)
    assert intents.classify("kal de dunga") == ("will_pay_later", "keywords")


def test_distress_keywords_never_reach_gemini(gemini):
    models = gemini(reply="will_pay_today")
    assert intents.classify("bimar tha, dukaan band thi") == ("hardship", "keywords")
    assert models.calls == []


def test_holdout_eval_paces_calls_and_scores_once_per_reply(gemini, monkeypatch, tmp_path):
    models = gemini(reply="will_pay_today")
    rows = [{"text": "paise bhej raha hoon", "label": "will_pay_today"},           # keywords abstain -> LLM wins
            {"text": "kal de dunga", "label": "will_pay_later"},          # disagree -> person
            {"text": "bimar hoon", "label": "hardship"}]                  # distress keywords win
    pauses = []
    answers = intent_holdout.ask_llm(rows, pause=4.5, sleep=pauses.append)
    assert pauses == [4.5, 4.5] and len(models.calls) == 3
    assert [intent_holdout.combined_label(r["text"], answers) for r in rows] == \
        ["will_pay_today", "unclear", "hardship"]

    data = tmp_path / "set.json"
    data.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(intent_holdout.time, "sleep", lambda s: None)
    assert intent_holdout.main([str(data)]) == 0
    res = json.loads((tmp_path / "set_results.json").read_text(encoding="utf-8"))
    assert res["llm_provider"] == "gemini" and res["llm_errors"] == 0
    assert res["combined"]["distress_got_payment_nudge"] == 0


def test_holdout_eval_counts_rate_limits_as_errors(gemini):
    models = gemini(error=RateLimited("429"))
    waits = []
    answers = intent_holdout.ask_llm([{"text": "kal de dunga", "label": "will_pay_later"}], pause=0, sleep=waits.append)
    assert answers == {"kal de dunga": None}
    assert len(models.calls) == 2 and waits == [intent_holdout.RETRY_WAIT]      # waited, retried once
    assert intent_holdout.combined_label("kal de dunga", answers) == "will_pay_later"   # keywords, as in production


def test_default_pause_is_for_gemini_free_tier(gemini, monkeypatch):
    monkeypatch.delenv("PAKKA_LLM_PAUSE", raising=False)
    assert 4 <= intent_holdout.llm_pause() <= 5
    monkeypatch.setenv("PAKKA_LLM_PROVIDER", "anthropic")
    assert intent_holdout.llm_pause() == 0


def test_holdout_eval_resumes_from_saved_answers(gemini, tmp_path):
    models = gemini(reply="will_pay_later")
    rows = [{"text": "kal de dunga", "label": "will_pay_later"}, {"text": "parso bhar dunga", "label": "will_pay_later"}]
    cache = tmp_path / "set_llm_gemini_m.json"
    cache.write_text(json.dumps({"kal de dunga": "will_pay_later"}), encoding="utf-8")
    pauses = []
    answers = intent_holdout.ask_llm(rows, pause=4.5, sleep=pauses.append, cache_path=cache)
    assert len(models.calls) == 1 and pauses == []                  # only the missing reply is sent
    assert answers == {"kal de dunga": "will_pay_later", "parso bhar dunga": "will_pay_later"}
    assert json.loads(cache.read_text(encoding="utf-8")) == answers  # new answer saved for next time
