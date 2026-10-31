"""Bengali, Odia and Telugu: every message, the Soundbox cue, the safety word lists and the demo shops.

All bn/od/te text lives in pakka/merchant/lang_pack.py and is marked for native review. The same guards
apply in every language; the evals and blind sets are unchanged (the new shops exist only with demo=True)."""
import re
import string
from pathlib import Path

import pytest

from pakka import sarvam
from pakka.merchant import lang_pack as lp
from pakka.merchant.agent import Desk
from pakka.merchant.guard import soundbox_safe
from pakka.merchant.intents import keyword_classify
from pakka.merchant.models import ConsentIn
from pakka.merchant.synth import personas
from pakka.merchant.templates import LANGS, REQUEST_NAMES, SOUNDBOX_CUE, TEMPLATES, fmt_date

ROOT = Path(__file__).resolve().parents[1]
SHOPS = {"bn": "sweets_kolkata", "od": "tiffin_cuttack", "te": "saree_vijayawada"}
WANT = {"pay_today": "will_pay_today", "pay_later": "will_pay_later", "skip_today": "request_skip_today",
        "lower_deduction": "request_lower_deduction", "reschedule": "request_reschedule",
        "callback": "request_callback", "already_paid": "already_paid"}


def _fields(text):
    return {f[1] for f in string.Formatter().parse(text) if f[1]}


def test_every_template_has_the_same_placeholders_in_every_language():
    for tid, t in TEMPLATES.items():
        for lang in LANGS:
            assert _fields(t[lang]) == _fields(t["en"]), (tid, lang)
    for names in REQUEST_NAMES.values():
        assert set(names) == set(LANGS)


def test_new_language_text_is_marked_for_native_review():
    src = (ROOT / "pakka/merchant/lang_pack.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    for n, line in enumerate(lines):
        if re.search(r"[ঀ-෿]", line) and not line.lstrip().startswith("#"):
            # on the line itself, or on the block's header comment / closing line just around it
            assert any("needs native review" in l for l in lines[max(0, n - 3):n + 3]), line


@pytest.mark.parametrize("lang", lp.NEW_LANGS)
def test_soundbox_cue_is_neutral_and_passes_g5(lang):
    assert soundbox_safe(SOUNDBOX_CUE[lang])
    assert not soundbox_safe(SOUNDBOX_CUE[lang] + " ₹600")


@pytest.mark.parametrize("word", ["লোন", "বকেয়া", "ଲୋନ", "ବକେୟା", "లోన్", "బకాయి"])
def test_g5_blocks_loan_words_in_new_languages(word):
    assert not soundbox_safe(f"{word} {SOUNDBOX_CUE['bn']}")


@pytest.mark.parametrize("lang", lp.NEW_LANGS)
def test_quick_replies_are_read_correctly(lang):
    for option, text in lp.SAY[lang].items():
        assert keyword_classify(text) == WANT[option], (lang, option, text)


@pytest.mark.parametrize("text", ["আমি অসুস্থ, দোকান বন্ধ ছিল", "ବାତ୍ୟା ପାଇଁ ଦୋକାନ ବନ୍ଦ",
                                  "ఆరోగ్యం బాగాలేదు, షాపు మూసి ఉంది"])
def test_distress_goes_to_a_person_in_every_language(text):
    assert keyword_classify(text) == "hardship"


def test_whole_word_match_in_bengali():
    # "না" (no) must not match inside "জানা" (know)
    assert keyword_classify("জানা নেই") == "unclear"


def test_months_and_sarvam_codes():
    from datetime import date
    assert fmt_date(date(2026, 10, 4), "bn") == "4 অক্টোবর"
    assert fmt_date(date(2026, 10, 4), "te") == "4 అక్టోబర్"
    assert {sarvam.LANG_CODES[l] for l in lp.NEW_LANGS} == {"bn-IN", "od-IN", "te-IN"}


def test_new_shops_only_in_the_demo():
    assert not set(SHOPS.values()) & set(personas())
    demo = personas(demo=True)
    for lang, mid in SHOPS.items():
        assert demo[mid].merchant.language == lang


@pytest.mark.parametrize("lang,mid", SHOPS.items())
def test_demo_shop_end_to_end_in_its_language(lang, mid):
    d = Desk(book=personas(demo=True))
    d.store.grant_consent(mid, ConsentIn(notice_version="merchant-ews-v1", early_warning_alerts=True,
                                         soundbox_cue=True, repeat_offers=True), d.at(mid, 1, "09:00"))
    r = next(r for day in range(1, 8) if (r := d.run_day_end(mid, day)).template_id)
    assert r.template_id == "T_SHORTFALL" and r.soundbox_cue_text == SOUNDBOX_CUE[lang]
    assert set(r.messages) == set(LANGS) and r.messages["en"] == r.message_en
    assert d.store.audit(1, mid)[0]["message"] == r.messages[lang]       # the owner's own language is logged
    skip = d.run_reply(mid, lp.SAY[lang]["skip_today"])
    assert skip.intent == "request_skip_today" and not skip.guard_blocks
    paid = d.pay(mid, 10 ** 7)
    assert paid["total_due_paise"] == 0 and paid["messages"][lang]
