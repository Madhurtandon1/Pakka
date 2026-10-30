"""Browser tests for the merchant demo (Playwright, Edge/Chrome).

    RUN_E2E=1 pytest tests/e2e -v                  # starts the app offline on a free port
    E2E_BASE_URL=https://… pytest tests/e2e -v     # tests a deployed site instead

Skipped in a plain `pytest` run. Writes e2e_report/REPORT.md and a screenshot for every step.
"""
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "e2e_report"
BASE = os.getenv("E2E_BASE_URL", "").rstrip("/")
ENABLED = bool(os.getenv("RUN_E2E") or BASE)
# Without a Sarvam key the voice endpoints answer 503 and the page uses the browser's voice: expected offline.
EXPECTED = re.compile(r"/speak$")

LOG = {"results": {}, "console": [], "requests": [], "shots": [], "notes": []}

# Bugs this suite found and that were fixed in the page (kept in the report for reviewers).
FIXED = [
    "Mic sent the voice transcript straight away; now it goes into the reply box to check, edit and send.",
    "No message when the browser has no speech recognition or the microphone is blocked; both now explain what to do.",
    "After \"Not now\", the permission request came back on every refresh; \"Not now\" is now remembered for that shop.",
    "A shop owner without permission had nowhere to type, so a distress reply couldn't reach a person from the page; "
    "the permission screen now has a \"Need help?\" box (alerts stay off).",
    "Mobile (390 px): the page was 275 px wider than the screen; the header controls and phone now shrink.",
    "Hindi mode left English on the phone: header line, dates (\"10 Oct\", also inside the Hindi message), contact hours "
    "(\"8 am–7 pm\"), the reply-reader line and the permission title; all now in Hindi.",
    "The consent version was only visible with technical details on; it now shows after Allow and on the phone.",
    "Added a \"Listen\" button on the app card (the owner's own phone; the Soundbox still only plays the neutral cue).",
]


def pytest_collection_modifyitems(config, items):
    if ENABLED:
        return
    skip = pytest.mark.skip(reason="browser tests: set RUN_E2E=1 (or E2E_BASE_URL) to run")
    for item in items:
        if "tests/e2e" in item.nodeid.replace("\\", "/"):
            item.add_marker(skip)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait(url: str, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=20)
            return True
        except Exception:
            time.sleep(1)
    return False


@pytest.fixture(scope="session")
def base_url():
    if BASE:
        # a sleeping free Render instance can take about a minute to wake
        assert _wait(BASE + "/health", 150), f"{BASE} didn't answer within 150 s"
        yield BASE
        return
    port = _free_port()
    env = {k: v for k, v in os.environ.items()
           if k not in ("PAKKA_LLM_PROVIDER", "PAKKA_LLM_API_KEY", "PAKKA_LLM_MODEL", "SARVAM_API_KEY")}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        assert _wait(url + "/health", 90), "the app didn't start"
        yield url
    finally:
        proc.terminate()
        proc.wait(15)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    REPORT_DIR.mkdir(exist_ok=True)
    pw = sync_playwright().start()
    b = None
    for channel in ("msedge", "chrome", None):
        try:
            b = pw.chromium.launch(channel=channel, headless=not os.getenv("E2E_HEADED")) if channel \
                else pw.chromium.launch()
            break
        except Exception:
            continue
    if b is None:
        pw.stop()
        pytest.skip("no Edge, Chrome or Playwright Chromium available")
    yield b
    b.close()
    pw.stop()


@pytest.fixture
def context_factory(browser, base_url, request):
    """New isolated browser context per test, with console and network capture."""
    scen = request.node.name.removeprefix("test_")
    made = []

    def make(viewport=(1440, 1000)):
        ctx = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
        page = ctx.new_page()
        page.set_default_timeout(90000 if BASE else 20000)
        page.on("console", lambda m: m.type == "error" and LOG["console"].append(
            (scen, m.text[:300], "status of 503" in m.text)))
        page.on("pageerror", lambda e: LOG["console"].append((scen, "page error: " + str(e)[:300], False)))
        page.on("requestfailed", lambda r: LOG["requests"].append((scen, r.method, r.url, r.failure or "failed", False)))
        page.on("response", lambda r: r.status >= 400 and LOG["requests"].append(
            (scen, r.request.method, r.url, r.status, bool(EXPECTED.search(r.url.split("?")[0])))))
        made.append(ctx)
        return page
    yield make
    for ctx in made:
        ctx.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    out = yield
    rep = out.get_result()
    if "e2e" not in item.nodeid or not ENABLED:
        return
    if rep.when == "call" or (rep.when == "setup" and not rep.passed):
        why = ""
        if rep.failed:
            lines = [ln for ln in str(rep.longrepr).splitlines() if ln.strip()]
            why = next((ln.strip() for ln in reversed(lines) if ln.lstrip().startswith("E ")), lines[-1] if lines else "")[:240]
        doc = (item.function.__doc__ or item.name).strip().splitlines()[0]
        if getattr(item, "callspec", None):
            doc += f" · `{item.callspec.id}`"
        LOG["results"][item.name] = (doc, rep.outcome, why, list(getattr(item, "_notes", [])))


def pytest_sessionfinish(session, exitstatus):
    if not ENABLED or not LOG["results"]:
        return
    REPORT_DIR.mkdir(exist_ok=True)
    rows = sorted(LOG["results"].items())
    passed = sum(1 for _, (_, o, _, _) in rows if o == "passed")
    md = [f"# Merchant UI test report", "",
          f"Run: {datetime.now():%d %b %Y %H:%M} · target: {BASE or 'local app, offline (no LLM, no Sarvam key)'} · "
          f"**{passed} / {len(rows)} scenarios passed**", "",
          "| # | Scenario | Result | Notes |", "|---|---|---|---|"]
    for name, (doc, outcome, why, notes) in rows:
        mark = {"passed": "✅ pass", "failed": "❌ fail", "skipped": "⏭ skipped"}.get(outcome, outcome)
        md.append(f"| {name.split('_')[1]} | {doc} | {mark} | {'; '.join(notes + ([why] if why else [])) or ''} |")
    unexpected_console = [c for c in LOG["console"] if not c[2]]
    md += ["", "## Console errors", ""]
    md += [f"- `{s}`: {t}" for s, t, _ in unexpected_console] or ["- None (apart from the expected ones below)."]
    expected_console = [c for c in LOG["console"] if c[2]]
    if expected_console:
        md.append(f"- Expected offline: {len(expected_console)} × \"503\" from the voice endpoints (no Sarvam key, so the page uses the browser's voice).")
    md += ["", "## Failed network requests", ""]
    bad = [r for r in LOG["requests"] if not r[4]]
    md += [f"- `{s}`: {m} {u} → {st}" for s, m, u, st, _ in bad] or ["- None unexpected."]
    exp = [r for r in LOG["requests"] if r[4]]
    if exp:
        md.append(f"- Expected offline: {len(exp)} × 503 from `/speak` or `/soundbox/speak` (fallback to the browser's voice).")
    md += ["", "## Bugs found and fixed", ""] + [f"- {f}" for f in FIXED]
    md += ["", "## Unclear or inconsistent UI text", ""]
    md += [f"- {n}" for n in dict.fromkeys(LOG["notes"])] or ["- None found."]
    md += ["", f"## Screenshots ({len(LOG['shots'])})", "", "Saved in `e2e_report/`:", ""]
    md += [f"- {s}" for s in LOG["shots"]]
    (REPORT_DIR / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
