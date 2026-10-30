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
    attempts = store.attempts(jid, probe.detection.blocker)
    out = rescue(jid, events, now, attempts=attempts, lang=lang)
    store.log(jid, out.detection.blocker, out.action, lang, out.message, out.policy_ok, out.escalated)
    return out


@app.get("/explain")
def get_explain(action: str, lang: str = "en", step: str | None = None, code: str | None = None):
    from pakka.explain import TEMPLATES, explain
    if action not in TEMPLATES:
        raise HTTPException(404, "unknown action")
    return {"action": action, "lang": lang, "message": explain(action, lang, step, code)}


@app.post("/doccheck")
async def doccheck(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "file too large")
    return check_image(data)


@app.get("/samples/{kind}")
def sample_document(kind: str):
    """Demo files for the upload step: the real photo check judges them like any upload."""
    from pakka.samples import make_sample
    try:
        data, media, name = make_sample(kind)
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


@app.get("/eval")
def eval_results():
    if not RESULTS.exists():
        raise HTTPException(404, "run python eval/run_eval.py first")
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def _known(jid: str):
    if jid not in journeys:
        raise HTTPException(404, "unknown journey")
