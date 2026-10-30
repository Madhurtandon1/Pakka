import json
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.merchant_api import router as merchant_router
from pakka import aadhaar, sarvam
from pakka.agent import rescue
from pakka.doccheck import check_image
from pakka.docs_detector import NEW_BLOCKERS
from pakka.explain import kfs_term
from pakka.models import Event
from pakka.store import Store

STATIC = Path(__file__).with_name("static")
RESULTS = Path(__file__).resolve().parents[1] / "eval" / "results.json"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Load the Aadhaar card reader in the background so the first upload isn't slow.
    threading.Thread(target=aadhaar.warm_up, daemon=True).start()
    yield


app = FastAPI(title="Pakka prototype", version="0.1.0", lifespan=lifespan)
app.include_router(merchant_router)
store = Store()
journeys: set[str] = set()


class SpeakIn(BaseModel):
    text: str
    lang: str = "hi"


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/demo")
def demo():
    return FileResponse(STATIC / "demo.html")


@app.get("/health")
def health():
    return {"ok": True, "sarvam": sarvam.enabled(), "card_reader": aadhaar.state()}


@app.post("/journeys")
def create_journey():
    jid = uuid.uuid4().hex[:8]
    journeys.add(jid)
    return {"journey_id": jid}


@app.post("/journeys/{jid}/events")
def add_event(jid: str, event: Event):
    _known(jid)
    store.add_event(jid, event)
    return {"ok": True, "count": len(store.events(jid))}


@app.get("/journeys/{jid}/rescue")
def get_rescue(jid: str, now: float = Query(ge=0), lang: str = "en", dry: bool = False):
    _known(jid)
    events = store.events(jid)
    probe = rescue(jid, events, now, lang=lang)
    if dry or not probe.detection.stalled:
        return probe
    d = probe.detection
    # Document-step blockers count attempts per cause (a PAN typo and a name mismatch are different
    # problems, each explained once); the original blockers count per blocker, as before.
    attempts = store.attempts(jid, d.blocker, d.code if d.blocker in NEW_BLOCKERS else None)
    out = rescue(jid, events, now, attempts=attempts, lang=lang)
    store.log(jid, out.detection.blocker, out.action, lang, out.message, out.policy_ok, out.escalated, d.code)
    return out


@app.get("/explain")
def get_explain(action: str, lang: str = "en", step: str | None = None, code: str | None = None):
    from pakka.explain import TEMPLATES, explain
    if action not in TEMPLATES:
        raise HTTPException(404, "unknown action")
    return {"action": action, "lang": lang, "message": explain(action, lang, step, code)}


@app.post("/doccheck")
async def doccheck(file: UploadFile = File(...)):
    try:
        data = await file.read()
    finally:
        await file.close()   # deletes any temporary copy of the upload
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "file too large")
    return check_image(data)


class IdIn(BaseModel):
    kind: str          # "pan", "aadhaar" or "ifsc"
    value: str


class NamesIn(BaseModel):
    pan_name: str
    aadhaar_name: str
    bank_name: str | None = None


@app.post("/idcheck")
def id_check(body: IdIn):
    """Offline format check. Nothing is stored; an Aadhaar number comes back only as XXXX XXXX 1234."""
    from pakka import idcheck
    checks = {"pan": idcheck.check_pan, "aadhaar": idcheck.check_aadhaar, "ifsc": idcheck.check_ifsc}
    if body.kind not in checks:
        raise HTTPException(404, "unknown check")
    return checks[body.kind](body.value)


@app.post("/idcheck/names")
def names_check(body: NamesIn):
    from pakka import idcheck
    return idcheck.check_names(body.pan_name, body.aadhaar_name, body.bank_name)


@app.post("/pdfcheck")
async def pdf_check(file: UploadFile = File(...), months: int = Query(3, ge=1, le=24)):
    """Income document check. The file is read into memory, checked, and the upload is closed
    (which deletes any temporary copy); nothing is stored."""
    from pakka.pdfcheck import MAX_BYTES, check_pdf
    try:
        data = await file.read(MAX_BYTES + 1)
    finally:
        await file.close()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file too large (max 8 MB)")
    return check_pdf(data, months)


@app.get("/samples/{kind}")
def sample_document(kind: str):
    """Demo files for the upload step: the real photo check judges them like any upload."""
    from pakka.samples import STATEMENTS, make_sample, make_statement
    try:
        data, media, name = (make_statement if kind in STATEMENTS else make_sample)(kind)
    except KeyError:
        raise HTTPException(404, "unknown sample")
    return Response(data, media_type=media, headers={"Content-Disposition": f'inline; filename="{name}"',
                                                     "Cache-Control": "max-age=3600"})


@app.get("/kfs/{term}")
def kfs(term: str, lang: str = "en"):
    text = kfs_term(term, lang)
    if not text:
        raise HTTPException(404, "unknown term")
    return {"term": term, "lang": lang, "text": text}


@app.post("/speak")
def speak(body: SpeakIn):
    if not sarvam.enabled():
        raise HTTPException(503, "SARVAM_API_KEY not set; the page falls back to browser speech")
    try:
        return Response(sarvam.tts(body.text, body.lang), media_type="audio/wav")
    except Exception as exc:
        raise HTTPException(502, f"Sarvam TTS failed: {exc}") from exc


@app.get("/audit")
def audit(limit: int = 50):
    return store.audit(limit)


@app.get("/eval/docs")
def eval_docs():
    """Document-step scenarios, reported separately from the main results."""
    path = RESULTS.with_name("docs_results.json")
    if not path.exists():
        raise HTTPException(404, "run python eval/docs_scenarios.py first")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/eval")
def eval_results():
    if not RESULTS.exists():
        raise HTTPException(404, "run python eval/run_eval.py first")
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def _known(jid: str):
    if jid not in journeys:
        raise HTTPException(404, "unknown journey")
