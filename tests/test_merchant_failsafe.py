"""Fail-safe intent rules: when unsure, Pakka routes to a person, never to a payment nudge."""
import pytest

from pakka.merchant import intents
from pakka.merchant.intents import combine, keyword_classify

PAY_NUDGE = {"will_pay_today", "will_pay_later"}
PERSON = {"hardship", "dispute", "already_paid", "unclear", "request_callback"}


# The four distress replies from blind set v1 that received an automated payment message.
@pytest.mark.parametrize("text", [
    "भाई अभी दुकान में बिल्कुल बिक्री नहीं हो रही है",
    "भाई धंधा बहुत मंदा चल रहा है आजकल",
    "अभी खाते में पैसे ही नहीं हैं",
    "थोड़ा समझिए भाई, अभी हालात ठीक नहीं हैं",
])
def test_blind_v1_distress_never_gets_a_payment_nudge(text):
    assert keyword_classify(text) == "hardship"


@pytest.mark.parametrize("text", [
    "abhi meeting mein hoon", "अभी मीटिंग में हूं", "kal dukaan pe aana", "aaj match kitne baje hai",
    "next week pakka",                       # a time word, but no payment verb
])
def test_time_word_without_payment_verb_goes_to_a_person(text):
    assert keyword_classify(text) == "unclear"


@pytest.mark.parametrize("text", ["aaj nahi kar paunga, kal dunga", "abhi nahi bhej sakta", "I can't pay today"])
def test_negation_blocks_a_payment_nudge(text):
    assert keyword_classify(text) not in PAY_NUDGE


@pytest.mark.parametrize("text", ["paise nahi hai abhi", "bikri nahi ho rahi", "no money this week",
                                  "cash nahi hai bhai", "धंधा नहीं चल रहा"])
def test_negation_with_money_or_sales_is_hardship(text):
    assert keyword_classify(text) == "hardship"


@pytest.mark.parametrize("text,label", [
    ("kal de dunga", "will_pay_later"), ("I'll pay tomorrow", "will_pay_later"),
    ("कल दे दूँगा", "will_pay_later"), ("abhi pay karta hoon", "will_pay_today"),
    ("अभी भरता हूँ", "will_pay_today"), ("QR bhej do abhi daal deta hoon", "will_pay_today"),
])
def test_clear_promises_still_work(text, label):
    assert keyword_classify(text) == label


# Task 1: the four combining cases.
SUNDAY = "रविवार तक पक्का पैसे भेज दूंगा"


def test_case1_distress_from_either_source_wins():
    assert combine("hardship", "will_pay_today", SUNDAY) == "hardship"
    assert combine("will_pay_later", "dispute", SUNDAY) == "dispute"
    assert combine("unclear", "already_paid", "hmm") == "already_paid"


def test_case2_keyword_unclear_is_an_abstain():
    assert combine("unclear", "will_pay_later", SUNDAY) == "will_pay_later"
    assert combine("unclear", "request_reschedule", "thoda time chahiye") == "request_reschedule"
    assert combine("will_pay_later", "unclear", SUNDAY) == "will_pay_later"      # LLM unclear abstains too
    assert combine("unclear", "unclear", "hmm") == "unclear"


def test_case3_will_pay_from_either_source_must_pass_the_fail_safe():
    assert combine("unclear", "will_pay_today", "abhi meeting mein hoon") == "unclear"     # no payment verb
    assert combine("unclear", "will_pay_later", "kal nahi bhej paunga") == "unclear"       # negation
    assert combine("unclear", "will_pay_later", SUNDAY) == "will_pay_later"               # verb, no negation


def test_case4_two_confident_different_labels_go_to_a_person():
    assert combine("will_pay_later", "will_pay_today", SUNDAY) == "unclear"
    assert combine("request_callback", "request_reschedule", "call karo") == "unclear"
    assert combine("will_pay_later", "will_pay_later", SUNDAY) == "will_pay_later"


def test_classify_uses_the_agreement_rule(monkeypatch):
    monkeypatch.delenv("PAKKA_LLM_PROVIDER", raising=False)      # generic LLM path, source "llm"
    monkeypatch.setattr(intents, "llm_enabled", lambda: True)
    monkeypatch.setattr(intents, "call_llm", lambda text: "will_pay_today")
    assert intents.classify("kal de dunga") == ("unclear", "llm")                # keywords say later: disagree
    assert intents.classify("abhi meeting mein hoon") == ("unclear", "llm")      # LLM label fails the fail-safe
    assert intents.classify("paise bhej raha hoon") == ("will_pay_today", "llm")           # keywords abstain, verb present
    monkeypatch.setattr(intents, "call_llm", lambda text: "hardship")
    assert intents.classify("abhi meeting mein hoon") == ("hardship", "llm")
