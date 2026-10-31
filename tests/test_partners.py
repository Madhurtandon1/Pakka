"""Partner layers: Sarvam speech-to-text, the n8n action layer and Cognee memory.

"Sarvam understands and speaks. Cognee remembers. Rules and guards decide. n8n acts. People handle
hard cases." Every partner is optional, mocked here, and none of them can choose an action."""
import hashlib
import hmac
import json
import re
import sys
import types
import urllib.error

import pytest
from fastapi.testclient import TestClient

from pakka import sarvam
from pakka.merchant import actions, memory
from pakka.merchant.agent import Desk
from pakka.merchant.models import ConsentIn
from pakka.merchant.synth import personas

CONSENT = dict(notice_version="merchant-ews-v1", early_warning_alerts=True, soundbox_cue=True, repeat_offers=True)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for k in ("N8N_WEBHOOK_URL", "N8N_WEBHOOK_SECRET", "PAKKA_MEMORY", "SARVAM_API_KEY", "LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def desk(mid=None, demo=False):
    d = Desk(book=personas(demo=demo))
    if mid:
        d.store.grant_consent(mid, ConsentIn(**CONSENT), d.at(mid, 1, "09:00"))
    return d


def client():
    from app.main import app
    c = TestClient(app)
    c.post("/merchant/reset")
    return c


# ---- Sarvam speech-to-text ----------------------------------------------------------------------

def test_voice_without_sarvam_key_falls_back(monkeypatch):
    r = client().post("/merchant/chai_seasonal/reply/voice?lang=hi", files={"file": ("r.webm", b"x", "audio/webm")})
    assert r.status_code == 503


def test_voice_transcript_is_masked_and_never_sent(monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test")
    monkeypatch.setattr(sarvam, "stt_available", lambda: True)
    monkeypatch.setattr(sarvam, "stt", lambda audio, name, mime, lang: "kal de dunga, mera number 9876543210")
    c = client()
    r = c.post("/merchant/chai_seasonal/reply/voice?lang=hi", files={"file": ("r.webm", b"abc", "audio/webm")}).json()
    assert r["source"] == "sarvam" and r["sent"] is False
    assert "9876543210" not in r["transcript"] and "kal de dunga" in r["transcript"]
    assert c.get("/merchant/audit?merchant_id=chai_seasonal").json() == []      # nothing was sent


def test_stt_call_uses_documented_parameters(monkeypatch):
    seen = {}

    class FakeSTT:
        def transcribe(self, **kw):
            seen.update(kw)
            return types.SimpleNamespace(transcript=" aaj nahi ")
    monkeypatch.setenv("SARVAM_API_KEY", "test")
    monkeypatch.setattr(sarvam, "_stt_client", lambda: types.SimpleNamespace(speech_to_text=FakeSTT()))
    assert sarvam.stt(b"abc", "r.webm", "audio/webm", "en") == "aaj nahi"
    assert seen["model"] == "saaras:v3" and seen["mode"] == "transcribe" and seen["language_code"] == "en-IN"
    assert seen["request_options"] == {"timeout_in_seconds": 8, "max_retries": 0}
    assert seen["file"] == ("r.webm", b"abc", "audio/webm")


def test_voice_error_tells_the_page_to_fall_back(monkeypatch):
    monkeypatch.setattr(sarvam, "stt_available", lambda: True)
    monkeypatch.setattr(sarvam, "stt", lambda *a: (_ for _ in ()).throw(TimeoutError()))
    r = client().post("/merchant/chai_seasonal/reply/voice", files={"file": ("r.webm", b"abc", "audio/webm")})
    assert r.status_code == 502


# ---- n8n action layer ---------------------------------------------------------------------------

def test_nothing_dispatched_without_consent():
    d = desk()
    d.run_day_end("chai_seasonal", 10)
    assert d.store.outbox() == []


def test_deferred_action_is_dispatched_only_when_delivered():
    d = desk("general_late_night")
    r = d.run_day_end("general_late_night", 6, d.at("general_late_night", 6, "21:30"))
    assert r.scheduled_for and d.store.outbox() == []
    d.run_day_end("general_late_night", 7, d.at("general_late_night", 7, "08:00"))
    out = d.store.outbox()
    assert len(out) == 1 and out[0]["action"] == "notify_shortfall"


def test_blocked_contact_is_not_dispatched():
    d = desk("tailor_stress")
    d.run_day_end("tailor_stress", 15)
    d.run_day_end("tailor_stress", 16)           # G3 cadence: no contact
    assert [o["action"] for o in d.store.outbox()] == ["notify_shortfall"]


def test_payload_has_no_pii_or_amounts():
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "Pay ₹400 now, call me on 9876543210", day=10)
    for row in d.store.outbox():
        p = json.loads(row["payload"])
        assert set(p) == {"event_id", "merchant_id", "action", "template_id", "language", "scheduled_for",
                          "lender_id", "requires_human"}
        flat = json.dumps(p)
        assert "chai_seasonal" not in flat and "Ramesh" not in flat and "₹" not in flat
        assert "9876543210" not in flat and "400" not in flat
        assert p["merchant_id"].startswith("m_")


def _capture(monkeypatch, fail=0):
    calls = []

    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        calls.append((req, timeout))
        if len(calls) <= fail:
            raise TimeoutError()
        return Resp()
    monkeypatch.setattr(actions.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_hmac_signature_and_event_id_headers(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n.local/webhook/pakka")
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", "s3cret")
    calls = _capture(monkeypatch)
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    req, timeout = calls[0]
    want = "sha256=" + hmac.new(b"s3cret", req.data, hashlib.sha256).hexdigest()
    assert req.get_header("X-pakka-signature") == want and timeout == 5
    assert req.get_header("X-pakka-event-id") == json.loads(req.data)["event_id"]
    assert d.store.outbox()[0]["status"] == "sent_n8n"


def test_timeout_retries_once_then_falls_back(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n.local/webhook/pakka")
    calls = _capture(monkeypatch, fail=99)   # n8n down for the whole test
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "Bimar hoon, dukaan band hai", day=10)
    rows = {o["action"]: o for o in d.store.outbox()}
    assert rows["notify_shortfall"]["status"] == "failed_fallback" and len(calls) >= 2
    assert any(q["action"] == "human_handoff" for q in d.store.queue())      # a person still gets it


def test_same_event_is_sent_once(monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n.local/webhook/pakka")
    calls = _capture(monkeypatch)
    d = desk("chai_seasonal")
    data = actions.payload(merchant_id="chai_seasonal", at=d.at("chai_seasonal", 10), action="send_pay_link",
                           template_id="T_PAY_LINK", language="hi", scheduled_for=None, lender_id="demo_nbfc_a")
    actions.dispatch(d.store, "chai_seasonal", data, d.at("chai_seasonal", 10))
    actions.dispatch(d.store, "chai_seasonal", data, d.at("chai_seasonal", 10))
    assert len(calls) == 1 and len(d.store.outbox()) == 1


def test_simulated_without_webhook():
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    assert d.store.outbox()[0]["status"] == "simulated"


def test_queue_push_needs_a_valid_signature():
    c = client()
    body = json.dumps({"event_id": "ev_1", "merchant_id": "m_x", "action": "human_handoff"}).encode()
    assert c.post("/merchant/lender/queue", content=body).status_code == 401
    assert c.post("/merchant/lender/queue", content=body, headers={"X-Pakka-Signature": "sha256=bad"}).status_code == 401
    ok = c.post("/merchant/lender/queue", content=body, headers={"X-Pakka-Signature": actions.sign(body)})
    assert ok.status_code == 200 and c.get("/merchant/lender/queue").json()[0]["source"] == "n8n"


def test_n8n_workflow_file_is_valid():
    from pathlib import Path
    wf = json.loads((Path(__file__).resolve().parents[1] / "n8n" / "pakka_workflow.json").read_text(encoding="utf-8"))
    names = {n["name"] for n in wf["nodes"]}
    assert {"Webhook", "Verify HMAC", "Switch on action", "Respond 200"} <= names
    send = [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.twilio"]
    assert send and all(n.get("disabled") for n in send)          # real SMS stays off by default


# ---- memory -------------------------------------------------------------------------------------

def test_no_memory_without_consent():
    d = desk()
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "kal de dunga", day=10)
    assert d.store.memory("chai_seasonal") == []


def test_memory_keeps_structured_facts_only():
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "kal de dunga, number 9876543210, Ramesh", day=10)
    flat = json.dumps(d.store.memory("chai_seasonal"))
    assert "9876543210" not in flat and "Ramesh" not in flat and "will_pay_later" in flat


def test_recall_lines_for_the_demo():
    d = desk("chai_seasonal", demo=True)
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "kal de dunga", day=10)
    d.run_day_end("chai_seasonal", 11)
    r = d.run_day_end("chai_seasonal", 12)
    assert r.recall_template_id == "T_RECALL_PAID" and "and you did" in r.recall_en and r.recall_hi
    d.store.grant_consent("mobile_dispute", ConsentIn(**CONSENT), d.at("mobile_dispute", 1, "09:00"))
    d.run_day_end("mobile_dispute", 8)
    d.run_reply("mobile_dispute", "date aage badhao", day=8)
    r = d.run_day_end("mobile_dispute", 9)
    assert "a new repayment date" in r.recall_en and "Demo Bank B" in r.recall_en


def test_memory_never_changes_the_action(monkeypatch):
    def run(mode):
        monkeypatch.setenv("PAKKA_MEMORY", mode)
        d = desk("chai_seasonal", demo=True)
        out = []
        for day in (10, 11, 12):
            r = d.run_day_end("chai_seasonal", day)
            out.append((r.action, r.channel, r.template_id, r.message_en))
            rr = d.run_reply("chai_seasonal", "kal de dunga", day=day)
            out.append((rr.action, rr.channel, rr.template_id, rr.message_en))
        return out
    assert run("sqlite") == run("off")


def test_withdrawing_consent_deletes_memory():
    c = client()
    c.post("/merchant/chai_seasonal/consent", json=CONSENT)
    c.post("/merchant/chai_seasonal/simulate?day=10&now=18:00")
    from app.merchant_api import desk as live
    assert live.store.memory("chai_seasonal")
    c.delete("/merchant/chai_seasonal/consent")
    assert live.store.memory("chai_seasonal") == [] and c.get("/merchant/chai_seasonal/memory").json()["items"] == []


@pytest.fixture
def fake_cognee(monkeypatch):
    calls = []

    async def remember(text, dataset_name=None):
        calls.append(("remember", text, dataset_name))

    async def recall(query_text=None, datasets=None):
        calls.append(("recall", query_text, datasets))
        return [types.SimpleNamespace(text="Paid the day after a short day.")]

    async def forget(dataset=None, **kw):
        calls.append(("forget", dataset))
    monkeypatch.setitem(sys.modules, "cognee", types.SimpleNamespace(remember=remember, recall=recall, forget=forget))
    monkeypatch.setenv("PAKKA_MEMORY", "cognee")
    return calls


def test_cognee_gets_masked_facts_and_answers(fake_cognee, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test")
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    d.run_reply("chai_seasonal", "kal de dunga, 9876543210", day=10)
    sent = [c for c in fake_cognee if c[0] == "remember"]
    assert sent and all("9876543210" not in c[1] and "chai_seasonal" not in c[2] for c in sent)
    assert memory.recall(d.store, "chai_seasonal")["answer"] == ["Paid the day after a short day."]
    memory.forget(d.store, "chai_seasonal")
    assert fake_cognee[-1][0] == "forget" and d.store.memory("chai_seasonal") == []


def test_cognee_without_key_falls_back_to_local(fake_cognee):
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    assert not [c for c in fake_cognee if c[0] == "remember"]
    assert d.store.memory("chai_seasonal") and "Cognee unavailable" in (memory.STATE["error"] or "")


def test_partner_status_offline():
    s = client().get("/merchant/partners").json()
    assert s["n8n"]["mode"] == "simulated" and s["memory"]["backend"] == "local"
    assert s["sarvam"]["speech_to_text"] == "browser fallback"
    assert "Rules and guards decide" in s["principle"]


def test_whole_merchant_eval_identical_with_memory_on_and_off(monkeypatch):
    """The full merchant_eval run (headline + skip pass) makes exactly the same decisions with memory
    on (local backend) and off, so memory is context only."""
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    from eval import merchant_eval
    monkeypatch.setenv("PAKKA_MEMORY", "sqlite")
    merchant_eval.main(write=False)
    on = list(merchant_eval.TRACE)
    monkeypatch.setenv("PAKKA_MEMORY", "off")
    merchant_eval.main(write=False)
    off = list(merchant_eval.TRACE)
    assert len(on) > 7000 and on == off


def test_reminder_carries_its_time_for_n8n_wait():
    d = desk("chai_seasonal")
    d.run_day_end("chai_seasonal", 10)
    r = d.run_reply("chai_seasonal", "kal de dunga", day=10)
    row = [o for o in d.store.outbox() if o["action"] == "schedule_reminder"][0]
    when = json.loads(row["payload"])["scheduled_for"]
    assert when and when[11:16] in r.message_en           # the same time the shop owner was told
