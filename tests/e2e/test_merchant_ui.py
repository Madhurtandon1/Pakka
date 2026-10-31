"""Full browser test of the merchant demo (/merchant). Every step checks visible plain-language text and
saves a screenshot to e2e_report/. Run with:  RUN_E2E=1 pytest tests/e2e -v"""
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import LOG, REPORT_DIR

# The browser's voice is replaced by a recorder, so tests can check exactly what would be spoken.
SPEECH = """window.__spoken=[];
if(window.speechSynthesis){speechSynthesis.speak=u=>{window.__spoken.push({text:u.text,lang:u.lang});setTimeout(()=>u.onend&&u.onend(),10)};speechSynthesis.cancel=()=>{}}"""
MIC = {
    "fake": """class FakeRec{start(){window.__recLang=this.lang;setTimeout(()=>{this.onresult&&this.onresult({results:[[{transcript:window.__transcript||"kal de dunga"}]]});this.onend&&this.onend()},60)}stop(){}abort(){}}
window.SpeechRecognition=FakeRec;window.webkitSpeechRecognition=FakeRec;""",
    "none": """Object.defineProperty(window,"SpeechRecognition",{value:undefined,configurable:true});
Object.defineProperty(window,"webkitSpeechRecognition",{value:undefined,configurable:true});""",
    "denied": """class DeniedRec{start(){setTimeout(()=>{this.onerror&&this.onerror({error:"not-allowed"});this.onend&&this.onend()},60)}stop(){}abort(){}}
window.SpeechRecognition=DeniedRec;window.webkitSpeechRecognition=DeniedRec;""",
}
MONEY_OR_LOAN = re.compile(r"[0-9₹]|\b(rs|rupee|rupees|loan|lone|emi|edi|kist|kisht|due|overdue|payment|paisa|paise)\b|किस्त|लोन|बकाया|रुपये|पैसे", re.I)


class Merchant:
    """Small driver for the merchant page."""

    def __init__(self, page, base, scen, notes):
        self.p, self.base, self.scen, self.notes, self.n = page, base, scen, notes, 0

    # -- helpers
    def shot(self, step):
        self.n += 1
        name = f"{self.scen}_{self.n:02d}_{step}.png"
        self.p.screenshot(path=str(REPORT_DIR / name))
        LOG["shots"].append(name)

    def note(self, text):
        self.notes.append(text)
        LOG["notes"].append(text)

    def reset(self):
        self.p.request.post(self.base + "/merchant/reset")

    def open(self, mid=None, path="/merchant", mic=None):
        self.p.add_init_script(SPEECH + (MIC[mic] if mic else ""))
        self.reset()
        self.p.goto(self.base + path)
        self.p.wait_for_function("()=>document.querySelector('#persona')?.options.length>0")
        if mid:
            self.pick(mid)

    def pick(self, mid):
        self.p.select_option("#persona", mid)
        self.p.wait_for_timeout(600)

    def allow(self):
        self.p.click("#allow")
        expect(self.p.locator("#appView")).to_be_visible()
        self.p.wait_for_timeout(300)

    def run(self, day, time="18:00"):
        self.p.evaluate(f"setDay({day})")
        self.p.fill("#clock", time)
        with self.p.expect_response(lambda r: "/simulate" in r.url):
            self.p.click("#run")
        self.p.wait_for_timeout(500)

    def say(self, text):
        self.p.fill("#replyText", text)
        with self.p.expect_response(lambda r: r.url.endswith("/reply")):
            self.p.click("#send")
        self.p.wait_for_timeout(500)

    def tap(self, opt):
        with self.p.expect_response(lambda r: r.url.endswith("/reply")):
            self.p.click(f"[data-opt={opt}]")
        self.p.wait_for_timeout(500)

    def switch(self, cid, on):
        """The consent toggles are styled switches: click the visible slider, as a person would."""
        if self.p.is_checked(f"#{cid}") != on:
            self.p.click(f"#{cid} + span")

    def card(self):
        return self.p.inner_text("#card")

    def audit(self, mid):
        return self.p.request.get(f"{self.base}/merchant/audit?merchant_id={mid}&limit=60").json()

    def latest(self, mid):
        return self.audit(mid)[0]

    def see(self, selector, text, timeout=15000):
        expect(self.p.locator(selector)).to_contain_text(text, timeout=timeout)


@pytest.fixture
def ui(context_factory, base_url, request):
    request.node._notes = []
    return Merchant(context_factory(), base_url, request.node.name.removeprefix("test_"), request.node._notes)


@pytest.fixture
def phone_ui(context_factory, base_url, request):
    request.node._notes = []
    return Merchant(context_factory((390, 844)), base_url, request.node.name.removeprefix("test_"), request.node._notes)


# ------------------------------------------------------------------------------------------------

def test_01_landing_link(ui):
    """1. Landing page → merchant demo link works"""
    ui.p.goto(ui.base + "/")
    ui.see("body", "Pakka")
    ui.shot("landing")
    ui.p.locator("a[href='/merchant']").first.click()
    ui.p.wait_for_url("**/merchant")
    ui.see("body", "Run the day")
    ui.shot("merchant_page")


def test_02_consent_screen(ui):
    """2. Consent: notice, independent toggles, hours limit, Not now, Allow + version"""
    ui.open("chai_seasonal")
    for part in ["Who:", "Purpose:", "Data used:", "How long:", "Withdraw:", "Grievance officer:", "lending service provider"]:
        ui.see("#consentView", part)
    ui.see("#consentView", "merchant-ews-v1")
    ui.shot("notice")
    # three toggles move independently
    ui.switch("c_ro", False)
    assert ui.p.is_checked("#c_ew") and ui.p.is_checked("#c_sb") and not ui.p.is_checked("#c_ro")
    ui.switch("c_sb", False)
    assert ui.p.is_checked("#c_ew") and not ui.p.is_checked("#c_sb")
    ui.switch("c_sb", True)
    # hours can't go wider than 08:00-19:00
    froms = [int(x) for x in ui.p.eval_on_selector_all("#c_from option", "o=>o.map(x=>x.value)")]
    tos = [int(x) for x in ui.p.eval_on_selector_all("#c_to option", "o=>o.map(x=>x.value)")]
    assert min(froms) >= 8 and max(tos) <= 19, (froms, tos)
    ui.shot("toggles_and_hours")
    # Not now → nothing is sent
    ui.p.click("#notnow")
    ui.see("#consentView", "Alerts are off")
    ui.run(10)
    row = ui.latest("chai_seasonal")
    assert row["channel"] == "none" and any(b.startswith("G1") for b in row["guard_blocks"]), row
    ui.shot("not_now_no_contact")
    # Allow → saved with version shown
    ui.p.click("#again")
    ui.switch("c_ro", False)
    ui.p.select_option("#c_from", "9")
    ui.p.select_option("#c_to", "18")
    ui.allow()
    ui.see("#toast", "Permission saved (notice merchant-ews-v1)")
    ui.see("#hours", "merchant-ews-v1")
    ui.see("#hours", "9 am to 6 pm")
    c = ui.p.request.get(ui.base + "/merchant/chai_seasonal/consent").json()
    assert c["active"] and c["consent"]["notice_version"] == "merchant-ews-v1"
    assert c["consent"]["repeat_offers"] is False and c["consent"]["early_warning_alerts"] is True
    ui.shot("allowed")


def test_03_kirana_steady(ui):
    """3. Sharma Kirana (steady): several days, no messages, offers allowed"""
    ui.open("kirana_steady")
    ui.allow()
    for d in range(1, 6):
        ui.run(d)
        ui.see("#card", "No messages from Pakka")
    assert all(r["channel"] == "none" for r in ui.audit("kirana_steady"))
    ui.shot("five_quiet_days")
    with ui.p.expect_response(lambda r: "/offers" in r.url):
        ui.p.click("#offers")
    ui.see("#card", "offers")
    assert ui.latest("kirana_steady")["action"] == "show_repeat_offer"
    ui.shot("offers_allowed")


def test_04_chai_rain(ui):
    """4. Ramesh Chai (rain): neutral cue, lender figures, reminder in hours, cured with no offer"""
    cues = ui.p.request.get(ui.base + "/merchant/personas").json()["soundbox_cues"]
    ui.open("chai_seasonal")
    ui.allow()
    ui.run(10)
    cue = re.search(r"“(.+)”", ui.p.inner_text("#cue")).group(1)
    assert cue == cues["hi"], cue
    assert not MONEY_OR_LOAN.search(cue), cue
    ui.see("#card", "Today's sales weren't enough")
    ui.see("#card", "Short today: ₹")
    ui.see("#card", "Demo NBFC A")
    ui.shot("shortfall_card_and_cue")
    ui.tap("pay_later")
    ui.see("#card", "remind you at")
    t = re.search(r"remind you at (\d\d):(\d\d)", ui.card())
    assert 8 <= int(t.group(1)) < 19, t.group(0)
    ui.see("#card", "Pay via UPI")
    ui.shot("pay_tomorrow_reminder")
    ui.say("Kal de dunga")
    ui.see("#card", "remind you at")
    assert ui.latest("chai_seasonal")["action"] == "schedule_reminder"
    ui.shot("typed_kal_de_dunga")
    ui.run(11)
    ui.see("#card", "up to date")
    assert "offer" not in ui.card().lower()
    assert ui.p.locator("#card [data-opt]").count() == 0
    ui.shot("cured_no_offer")


@pytest.mark.parametrize("opt,action,plain", [
    ("pay_today", "send_pay_link", "Pay via UPI"),
    ("pay_later", "schedule_reminder", "remind you"),
    ("lower_deduction", "route_lower_deduction_request", "has been sent to Demo NBFC A"),
    ("reschedule", "route_reschedule_request", "has been sent to Demo NBFC A"),
    ("callback", "schedule_callback", "will call you"),
    ("already_paid", "human_handoff", "A person from Demo NBFC A"),
])
def test_05_quick_replies(ui, opt, action, plain):
    """5. Every quick-reply button gives its documented action and an audit row"""
    ui.open("chai_seasonal")
    ui.allow()
    ui.run(10)
    before = len(ui.audit("chai_seasonal"))
    ui.tap(opt)
    ui.see("#card", plain)
    rows = ui.audit("chai_seasonal")
    assert len(rows) == before + 1 and rows[0]["action"] == action, rows[0]
    ui.see("#auditTbl", "Reply:")
    ui.shot(opt)


def test_06_pay_choice(ui):
    """6. Pay choice: two buttons when total due > today's gap, one when equal"""
    ui.open("mobile_dispute")
    ui.allow()
    ui.run(8)
    ui.tap("pay_today")
    ui.see("#card", "today's shortfall of ₹200")
    assert ui.p.locator("#card a.paylink").count() == 2
    ui.shot("two_links")
    ui.pick("chai_seasonal")
    ui.reset()
    ui.pick("chai_seasonal")
    ui.allow()
    ui.run(10)
    ui.tap("pay_today")
    assert ui.p.locator("#card a.paylink").count() == 1
    ui.shot("one_link")


def test_07_late_night(ui):
    """7. Gupta General Store at 21:30: deferred, delivered next morning"""
    ui.open("general_late_night")
    ui.allow()
    ui.run(6, "21:30")
    ui.see("#card", "will wait until")
    ui.see("#card", "08:00")
    ui.shot("deferred")
    ui.run(7, "08:00")
    ui.see("#card", "You're behind")
    row = ui.latest("general_late_night")
    assert row["channel"] != "none" and row["ts"][11:16] == "08:00", row
    ui.shot("delivered_8am")


def test_08_tailor_illness(ui):
    """8. Noor Tailors: early warning, hardship → person, contact stops, offers greyed"""
    ui.open("tailor_stress")
    ui.allow()
    ui.run(14)
    ui.see("#card", "Nothing is late yet")
    ui.shot("early_warning")
    ui.run(15)
    ui.say("Bimar tha, dukaan band thi")
    ui.see("#card", "A person from Demo NBFC A")
    ui.see("#card", "R. Mehta")
    ui.see("#card", "debt counselling")
    ui.see("#card", "hard time")
    ui.shot("handoff")
    ui.run(17)
    row = ui.latest("tailor_stress")
    assert row["channel"] == "none" and any(b.startswith("G8") for b in row["guard_blocks"]), row
    ui.shot("contact_stopped")
    ui.p.click("#offers")
    ui.see("#toast", "No loan offers right now")
    expect(ui.p.locator("#offers")).to_be_disabled()
    ui.see("#offers", "Offers unavailable")
    ui.shot("offers_blocked")


def test_09_mobile_dispute(ui):
    """9. City Mobile Repair: "I already paid" → person; out-of-scope request → person"""
    ui.open("mobile_dispute")
    ui.allow()
    ui.run(8)
    ui.tap("already_paid")
    ui.see("#card", "A person from Demo Bank B")
    assert ui.latest("mobile_dispute")["action"] == "human_handoff"
    ui.shot("already_paid")
    ui.reset()
    ui.pick("kirana_steady")
    ui.pick("mobile_dispute")
    ui.allow()
    ui.run(8)
    ui.tap("lower_deduction")
    row = ui.latest("mobile_dispute")
    assert row["action"] == "human_handoff" and any(b.startswith("G6") for b in row["guard_blocks"]), row
    ui.see("#card", "A person from Demo Bank B")
    ui.shot("out_of_scope")


def test_10_cadence(ui):
    """10. Cadence: every other day during a long shortfall, then a person"""
    ui.open("tailor_stress")
    ui.allow()
    got = {}
    for d in range(15, 22):
        ui.run(d)
        r = ui.latest("tailor_stress")
        got[d] = (r["action"], r["channel"], [b.split(":")[0] for b in r["guard_blocks"]])
    assert got[15][0] == got[17][0] == got[19][0] == "notify_shortfall"
    assert all(got[d][1] == "none" and "G3_cadence" in got[d][2] for d in (16, 18, 20))
    assert got[21][0] == "human_handoff" and "G7_attempts" in got[21][2]
    ui.see("#auditTbl", "Messaged yesterday, giving them a day")
    ui.shot("cadence")
    ui.note("Cadence: the person takes over on the 4th proactive contact (days 15, 17, 19 messaged; day 21 → person). "
            "The feature doc and README say \"the third attempt goes to a person\"; the code hands off after three attempts. "
            "The wording should say \"after three messages\". A worsening overdue stage (SMA-0 → SMA-1) can't be reached "
            "in the 30-day demo; it is covered by the unit tests.")
    ui.note("The audit chip for that handover reads \"Third try, so a person takes over\" although it is the 4th contact.")


def test_11_withdraw(ui):
    """11. Withdraw consent: one tap, contact stops, distress still reaches a person"""
    ui.open("tailor_stress")
    ui.allow()
    ui.run(15)
    ui.p.click("#withdraw")
    ui.see("#toast", "Permission taken back")
    ui.see("#consentView", "Permission withdrawn")
    ui.shot("withdrawn")
    ui.run(17)
    row = ui.latest("tailor_stress")
    assert row["channel"] == "none" and any(b.startswith("G1") for b in row["guard_blocks"]), row
    ui.p.fill("#cvText", "Bimar tha, dukaan band thi")
    ui.p.click("#cvSend")
    ui.see("#cvOut", "A person from Demo NBFC A")
    assert ui.latest("tailor_stress")["action"] == "human_handoff"
    ui.shot("distress_after_withdraw")


def test_12_distress_without_consent(ui):
    """12. Never consented: a hardship reply still reaches a person"""
    ui.open("chai_seasonal")
    ui.see("#consentView", "Need help?")
    ui.p.fill("#cvText", "Ghar mein maut ho gayi, dukaan band hai")
    ui.p.click("#cvSend")
    ui.see("#cvOut", "A person from Demo NBFC A")
    row = ui.latest("chai_seasonal")
    assert row["action"] == "human_handoff" and row["consent_version"] in (None, ""), row
    ui.shot("handoff_without_consent")
    ui.p.fill("#cvText", "theek hai")
    ui.p.click("#cvSend")
    ui.see("#cvOut", "Alerts are off")
    ui.shot("non_distress_without_consent")


ALLOWED_LATIN = {"pakka", "paytm", "soundbox", "upi", "lsp", "demo", "nbfc", "a", "b", "bank", "business", "app", "ramesh",
                 "chai", "stall", "r", "mehta", "grievance", "nbfc-a", "example", "chrome", "edge", "otp", "emi", "edi",
                 "kfs", "key", "fact", "statement", "english", "hinglish", "am", "pm", "merchant-ews-v", "ai", "x"}


def _latin_words(page):
    # visible text only; the chips are demo annotations for the audience, not words the owner reads
    text = page.evaluate("""()=>{let t=document.querySelector('#phone').innerText;
      document.querySelectorAll('#phone .chips,#phone .hist').forEach(c=>{if(c.innerText)t=t.split(c.innerText).join(' ')});return t}""")
    text = re.sub(r"\S+@\S+|\d[\d\-]*|upi://\S+", " ", text)
    return sorted({w for w in re.findall(r"[A-Za-z][A-Za-z\-]+", text) if w.lower() not in ALLOWED_LATIN})


def test_13_hindi(ui):
    """13. Language toggle: notice, card and buttons in Hindi, no untranslated English"""
    ui.open("chai_seasonal")
    ui.p.click("#lang button[data-lang=hi]")
    ui.p.wait_for_timeout(400)
    ui.see("#consentView", "कौन:")
    ui.see("#allow", "अनुमति दें")
    left = _latin_words(ui.p)
    ui.shot("hindi_notice")
    ui.allow()
    ui.run(10)
    ui.see("#card", "आज की बिक्री")
    ui.see("#card [data-opt=pay_later]", "कल भरूँगा")
    left += _latin_words(ui.p)
    ui.shot("hindi_card")
    ui.p.click("#lang button[data-lang=en]")
    ui.see("#card", "Today's sales")
    ui.shot("back_to_english")
    left = sorted(set(left))
    if left:
        ui.note("English words left in Hindi mode on the phone: " + ", ".join(left))
    assert not left, left


def test_14_technical_details(ui):
    """14. "Show technical details" shows and hides codes"""
    ui.open("chai_seasonal")
    ui.allow()
    ui.run(10)
    ui.see("#card", "Today's payment was short")
    assert "R1_shortfall" not in ui.card()
    ui.p.check("#tech")
    ui.see("#card", "R1_shortfall")
    ui.see("#card", "notify_shortfall")
    ui.shot("tech_on")
    ui.p.uncheck("#tech")
    expect(ui.p.locator("#card")).not_to_contain_text("R1_shortfall")
    ui.shot("tech_off")


def test_15_lender_view(ui):
    """15. Lender view: ledger stages, requests, audit chips, tiles with 0 rules broken"""
    ui.open("chai_seasonal")
    ui.allow()
    ui.run(10)
    ui.tap("lower_deduction")
    assert ui.p.locator("#ledgerTbl tr").count() >= 11
    ui.see("#ledgerTbl", "1–30 days late")
    ui.see("#reqs", "Smaller daily payment")
    ui.see("#reqs", "Waiting for the lender's decision")
    ui.see("#auditTbl", "Safety check")
    ui.see("#auditTbl", "Today's payment was short")
    tiles = ui.p.inner_text("#tiles")
    assert re.search(r"\b0\s*Safety rules broken", tiles), tiles
    ui.shot("lender_view")


def test_16_tour(ui):
    """16. Guided tour runs to the end without errors"""
    ui.open(path="/merchant?tour=1")
    expect(ui.p.locator("#cap .n")).to_contain_text("That's the loop", timeout=240000)
    ui.shot("tour_end")
    errors = [c for c in LOG["console"] if c[0] == ui.scen and not c[2]]
    assert not errors, errors


def test_17_reset(ui):
    """17. Reset returns to a clean state"""
    ui.open("chai_seasonal")
    ui.allow()
    ui.run(10)
    ui.tap("lower_deduction")
    ui.p.click("#reset")
    ui.see("#toast", "Demo reset")
    ui.see("#consentView", "Permission request")
    ui.see("#auditTbl", "Nothing yet")
    ui.see("#reqs", "No requests yet")
    assert ui.audit("chai_seasonal") == []
    ui.shot("clean")


def test_18_speaker(ui):
    """18. Speaker: Soundbox plays only the neutral cue; Listen reads the card; other text refused"""
    cues = ui.p.request.get(ui.base + "/merchant/personas").json()["soundbox_cues"]
    ui.open("chai_seasonal")
    ui.allow()
    with ui.p.expect_response(lambda r: r.url.endswith("/soundbox/speak")) as resp:
        ui.run(10)
    assert resp.value.status in (200, 503)
    ui.p.wait_for_timeout(300)
    spoken = ui.p.evaluate("window.__spoken")
    if resp.value.status == 503:   # offline: falls back to the browser's voice
        assert spoken and all(s["text"] == cues["hi"] for s in spoken), spoken
    ui.p.click("#replay")
    ui.p.wait_for_timeout(500)
    assert all(s["text"] == cues["hi"] for s in ui.p.evaluate("window.__spoken"))
    ui.shot("cue_played")
    # Listen on the app card (owner's own phone)
    with ui.p.expect_response(lambda r: r.url.endswith("/speak") and "soundbox" not in r.url):
        ui.p.click("#listenCard")
    ui.p.wait_for_timeout(400)
    last = ui.p.evaluate("window.__spoken.at(-1)")
    assert "Today's sales weren't enough" in last["text"] and "upi://" not in last["text"], last
    ui.shot("listen_card")
    # The Soundbox endpoint refuses anything but the cue
    bad = ui.p.request.post(ui.base + "/merchant/chai_seasonal/soundbox/speak", data={"text": "Pay ₹400 now", "lang": "hi"})
    assert bad.status == 400
    ok = ui.p.request.post(ui.base + "/merchant/chai_seasonal/soundbox/speak", data={"text": cues["hi"], "lang": "hi"})
    assert ok.status in (200, 503)


def test_19a_mic_transcript(ui):
    """19. Mic: transcript goes to the reply box, is not sent until Send; language follows toggle"""
    ui.open("chai_seasonal", mic="fake")
    ui.allow()
    ui.run(10)
    ui.see("#micNote", "Voice works in Chrome or Edge")
    before = len(ui.audit("chai_seasonal"))
    ui.p.click("#mic")
    expect(ui.p.locator("#replyText")).to_have_value("kal de dunga")
    ui.see("#toast", "tap ➤ to send")
    ui.p.wait_for_timeout(600)
    assert len(ui.audit("chai_seasonal")) == before, "voice transcript was sent without tapping Send"
    assert ui.p.evaluate("window.__recLang") == "en-IN"
    ui.shot("transcript_in_box")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#send")
    ui.see("#card", "remind you at")
    ui.shot("sent_after_tap")
    ui.p.click("#lang button[data-lang=hi]")
    ui.p.click("#mic")
    ui.p.wait_for_timeout(300)
    assert ui.p.evaluate("window.__recLang") == "hi-IN"


def test_19b_mic_unsupported(ui):
    """19. Mic: browser without speech recognition → clear message"""
    ui.open("chai_seasonal", mic="none")
    ui.allow()
    ui.p.click("#mic")
    ui.see("#toast", "Voice isn't supported in this browser. Please type your reply.")
    ui.shot("unsupported")


def test_19c_mic_denied(ui):
    """19. Mic: permission denied → clear message"""
    ui.open("chai_seasonal", mic="denied")
    ui.allow()
    ui.p.click("#mic")
    ui.see("#toast", "Microphone permission was denied")
    ui.shot("denied")


def test_20_mobile(phone_ui):
    """20. Mobile viewport 390×844: no sideways overflow, buttons usable"""
    ui = phone_ui
    ui.open("chai_seasonal")
    ui.shot("mobile_consent")
    ui.allow()
    ui.run(10)
    ui.tap("pay_later")
    ui.see("#card", "remind you at")
    over = ui.p.evaluate("()=>document.documentElement.scrollWidth-innerWidth")
    assert over <= 1, f"page is {over}px wider than the screen"
    for sel in ["#run", "#send", "#mic", "#offers"]:
        box = ui.p.locator(sel).bounding_box()
        assert box and box["width"] >= 24 and box["height"] >= 24, (sel, box)
    ui.shot("mobile_card")


def test_21_fruit_cart_cant_pay_today(ui):
    """21. Verma Fruit Cart: "Can't pay today" ×3 → carry-forward explained twice, then a callback is booked"""
    ui.open("fruit_cart", mic="fake")
    ui.allow()
    ui.run(5)
    ui.see("#card", "Today's sales weren't enough")
    ui.p.click("#card [data-opt=skip_today]")
    ui.see("#card .reasons", "optional")
    ui.see("#card .reasons", "Prefer not to say")
    ui.shot("reason_chips")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#card [data-reason=low_sales]")
    ui.see("#card", "as your lender's plan allows")
    ui.see("#card", "Pay via UPI")
    assert ui.latest("fruit_cart")["action"] == "acknowledge_carry_forward"
    ui.shot("day5_carry_forward")
    # day 6: no new message from Pakka (every other day); the owner speaks instead
    ui.run(6)
    ui.p.evaluate("window.__transcript='aaj nahi de paunga, kal kaat lena'")
    ui.p.click("#mic")
    expect(ui.p.locator("#replyText")).to_have_value("aaj nahi de paunga, kal kaat lena")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#send")
    ui.see("#card", "as your lender's plan allows")
    ui.see("#skips", "2 requests")
    ui.see("#skips", "Stress flag")
    ui.shot("day6_voice_and_stress_flag")
    # day 7: third in a row -> a person, with times inside contact hours
    ui.run(7)
    ui.p.click("#skipBtn")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#card [data-reason=none]")
    ui.see("#card", "Is everything okay?")
    slots = ui.p.locator("#card [data-slot]")
    assert slots.count() >= 3
    hours = [int(x[11:13]) for x in ui.p.eval_on_selector_all("#card [data-slot]", "b=>b.map(x=>x.dataset.slot)")]
    assert all(8 <= h < 19 for h in hours), hours
    ui.shot("day7_callback_offer")
    with ui.p.expect_response(lambda r: r.url.endswith("/callbacks")):
        slots.first.click()
    ui.see("#toast", "will call you at")
    ui.see("#card", "Callback booked")
    ui.see("#skips", "Asked to skip 3 times this month — callback booked")
    ui.see("#skips", "Booked")
    ui.see("#reqs", "Call with a person (can't pay today)")
    with ui.p.expect_response(lambda r: "/offers" in r.url):
        ui.p.click("#offers")
    ui.see("#toast", "No loan offers")
    ui.shot("callback_booked_lender_view")


def test_22a_partners_offline(ui):
    """22. Partners offline: status strip, simulated actions, people queue, memory and recall lines"""
    ui.open("chai_seasonal")
    ui.see("#partners", "n8n: simulated")
    ui.see("#partners", "Memory: local")
    ui.see("#partners", "Sarvam speech-to-text: browser fallback")
    assert "Rules and guards decide" in ui.p.get_attribute("#partners .why", "title")
    ui.allow()
    ui.run(10)
    ui.see("#actionsList", "Action sent (simulated)")
    ui.tap("pay_later")
    ui.run(11)
    ui.see("#memoryList", "Replied: will pay later")
    ui.see("#memoryList", "Paid up")
    ui.run(12)                                     # demo data: a second rainy day
    ui.see("#card .recall", "you did. Thank you")
    ui.shot("recall_ramesh")
    ui.say("Bimar hoon, dukaan band hai")
    ui.see("#queueList", "Passed to a person")
    ui.see("#queueList", "Simulated")
    ui.shot("actions_queue_memory")
    ui.p.click("#withdraw")
    ui.see("#memoryList", "Nothing remembered")
    ui.shot("memory_deleted_on_withdraw")
    # City Mobile: the pending request is remembered on the thank-you card
    ui.reset()
    ui.pick("kirana_steady")
    ui.pick("mobile_dispute")
    ui.allow()
    ui.run(8)
    ui.tap("reschedule")
    ui.run(9)
    ui.see("#card .recall", "a new repayment date")
    ui.see("#card .recall", "Demo Bank B")
    ui.shot("recall_city_mobile")


def test_22b_sarvam_voice_path(ui):
    """22. Sarvam speech-to-text path: recorded audio → transcript in the box, not sent until Send"""
    ui.p.add_init_script("""
      navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop(){}}]});
      window.MediaRecorder=class{constructor(){this.state="inactive"}start(){this.state="recording";
        setTimeout(()=>this.stop(),80)}stop(){if(this.state!=="recording")return;this.state="inactive";
        this.ondataavailable&&this.ondataavailable({data:new Blob(["x"])});this.onstop&&this.onstop()}};""")
    def partners(route):
        resp = route.fetch()
        data = resp.json()
        data["sarvam"]["speech_to_text"] = "live"
        route.fulfill(response=resp, json=data)
    ui.p.route("**/merchant/partners", partners)
    ui.p.route("**/reply/voice*", lambda route: route.fulfill(
        json={"transcript": "aaj nahi de paunga, kal kaat lena", "source": "sarvam", "sent": False}))
    ui.open("fruit_cart")
    ui.allow()
    ui.run(5)
    before = len(ui.audit("fruit_cart"))
    with ui.p.expect_request(lambda r: "/reply/voice" in r.url):
        ui.p.click("#mic")
    expect(ui.p.locator("#replyText")).to_have_value("aaj nahi de paunga, kal kaat lena")
    ui.see("#toast", "Voice by Sarvam")
    ui.p.wait_for_timeout(500)
    assert len(ui.audit("fruit_cart")) == before, "a voice transcript was sent without tapping Send"
    ui.shot("sarvam_transcript")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#send")
    ui.see("#card", "as your lender's plan allows")
    ui.p.unroute_all(behavior="ignoreErrors")    # don't leave the fake routes open at browser close


def test_23_live_replies_and_payments_in_the_record(ui):
    """23. Spontaneous replies on any day and pay-link payments show up live in the lender's payment record"""
    ui.open("chai_seasonal", mic="fake")
    ui.allow()
    ui.run(3)                                      # an ordinary day: sales covered the payment
    ui.p.evaluate("window.__transcript='aaj nahi dunga'")
    ui.p.click("#mic")
    expect(ui.p.locator("#replyText")).to_have_value("aaj nahi dunga")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#send")
    ui.see("#card", "nothing is pending")
    ui.see("#ledgerTbl tr.now", "Owner: can't pay today")
    ui.shot("spontaneous_reply_recorded")
    ui.run(10)                                     # the rainy day: ₹400 short
    ui.tap("pay_today")
    ui.p.click("#card a.paylink")
    ui.see("#card .paybox", "simulate a UPI payment of ₹400")
    with ui.p.expect_response(lambda r: r.url.endswith("/pay")):
        ui.p.click("#payGo")
    ui.see("#toast", "has received ₹400")
    ui.see("#card", "Payment recorded by the lender")
    ui.see("#ledgerTbl tr.now", "₹400 received via pay link")
    row = ui.p.inner_text("#ledgerTbl tr.now")
    assert "Owner: will pay today" in row, row
    ui.shot("payment_recorded")
    ui.run(11)
    ui.see("#card", "up to date")


def test_24_bengali_odia_telugu(ui):
    """24. A Bengali shop: notice, card, quick replies and voice in Bengali; the same card in Odia and Telugu"""
    ui.open("sweets_kolkata", mic="fake")
    expect(ui.p.locator('#lang button[data-lang="bn"]')).to_have_class(re.compile(r"\bon\b"))
    ui.see("#consentView", "অভিযোগ আধিকারিক")                  # the permission notice, in Bengali
    ui.allow()
    ui.run(4)                                                    # day 4 falls short by ₹250
    ui.see("#card", "আজ কম: ₹250")
    ui.see("#cue", "আপনার Paytm for Business অ্যাপে একটি জরুরি বার্তা আছে।")
    ui.shot("bengali_card")
    ui.p.click("[data-opt=skip_today]")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click('[data-reason="low_sales"]')
    ui.see("#card", "কালকের বিক্রি থেকে")                       # the lender's carry-forward, explained
    ui.see("#ledgerTbl tr.now", "Owner: can't pay today")
    assert ui.latest("sweets_kolkata")["language"] == "bn"
    ui.p.evaluate("window.__transcript='কাল দিয়ে দেব'")       # voice reply in Bengali
    ui.p.click("#mic")
    expect(ui.p.locator("#replyText")).to_have_value("কাল দিয়ে দেব")
    with ui.p.expect_response(lambda r: r.url.endswith("/reply")):
        ui.p.click("#send")
    ui.see("#card", "মনে করিয়ে দেব")
    ui.p.click('#lang button[data-lang="te"]')
    ui.see("#card", "గుర్తు చేస్తాను")                           # the same message, in Telugu
    ui.p.click('#lang button[data-lang="od"]')
    ui.see("#card", "ମନେ ପକାଇଦେବି")
    ui.shot("odia_card")
