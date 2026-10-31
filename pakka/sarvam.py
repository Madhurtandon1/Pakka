import base64
import json
import os
import urllib.request

from .pii import mask

API = "https://api.sarvam.ai"
LANG_CODES = {"en": "en-IN", "hi": "hi-IN"}


def enabled() -> bool:
    return bool(os.getenv("SARVAM_API_KEY"))


def tts(text: str, lang: str = "hi") -> bytes:
    body = {
        "text": mask(text)[:1500],
        "target_language_code": LANG_CODES.get(lang, "hi-IN"),
        "model": os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
    }
    req = urllib.request.Request(
        f"{API}/text-to-speech",
        data=json.dumps(body).encode(),
        headers={"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    return base64.b64decode(payload["audios"][0])


# Speech-to-text (Sarvam "Saaras"). Checked against sarvamai 0.1.41: speech_to_text.transcribe(file=,
# model="saaras:v3" | "saaras:v4", mode="transcribe" (v3 only), language_code="hi-IN" | "en-IN" | ...).
STT_LAST = {"status": None, "detail": None}


def stt_available() -> bool:
    if not enabled():
        return False
    try:
        import sarvamai  # noqa: F401  (optional dependency)
        return True
    except ImportError:
        return False


def _stt_client():
    from sarvamai import SarvamAI
    return SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"], timeout=8)


def stt(audio: bytes, filename: str, mime: str, lang: str = "hi") -> str:
    """Transcribe a short recorded reply. Raises on any error; the page then uses the browser's voice."""
    client = _stt_client()
    resp = client.speech_to_text.transcribe(
        file=(filename, audio, mime),
        model=os.getenv("SARVAM_STT_MODEL", "saaras:v3"),
        mode="transcribe",
        language_code=LANG_CODES.get(lang, "hi-IN"),
        request_options={"timeout_in_seconds": 8, "max_retries": 0},
    )
    return (getattr(resp, "transcript", "") or "").strip()
