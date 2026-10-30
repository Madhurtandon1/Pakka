"""Read an Aadhaar card photo: find the number, check its Verhoeff check digit, and look for
front-side fields (date of birth, gender).

This is a document check, not UIDAI verification: it tells us the photo is a readable Aadhaar
front with a well-formed number. Text is read offline with RapidOCR when it is installed.
The image and the text are never stored or logged; only the last four digits leave this module.
"""
import base64
import re
import threading
import time

import cv2
import numpy as np

# Verhoeff tables (the check digit scheme UIDAI uses for Aadhaar numbers)
_D = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
      [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
      [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
      [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]]
_P = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
      [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
      [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]]


def verhoeff_ok(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def valid_aadhaar(number: str) -> bool:
    """12 digits, not starting with 0 or 1, with a correct Verhoeff check digit."""
    return len(number) == 12 and number.isdigit() and number[0] not in "01" and verhoeff_ok(number)


def mask(number: str) -> str:
    return f"XXXX XXXX {number[-4:]}"


# ---- OCR engine (optional) -------------------------------------------------------------
_engine = None
_tried = False
_lock = threading.Lock()


def _ocr():
    global _engine, _tried
    with _lock:
        if not _tried:
            _tried = True
            try:
                from rapidocr_onnxruntime import RapidOCR
                _engine = RapidOCR()
            except Exception:
                _engine = None
    return _engine


def available() -> bool:
    return _ocr() is not None


def state() -> str:
    """'on', 'loading' or 'off' (OCR not installed), without blocking."""
    if _engine is not None:
        return "on"
    return "loading" if not _tried or _lock.locked() else "off"


def warm_up() -> None:
    """Load the OCR models in the background so the first upload isn't slow."""
    eng = _ocr()
    if eng is not None:
        with _lock:
            eng(np.full((64, 64, 3), 255, np.uint8))


# ---- reading ---------------------------------------------------------------------------
FULL = re.compile(r"(?<![\dxX])(\d{4})\s?(\d{4})\s?(\d{4})(?!\s?\d)")
MASKED = re.compile(r"[xX*]{4}\s?[xX*]{4}\s?(\d{4})(?!\s?\d)")
DATE = re.compile(r"\b\d{2}[/-]\d{2}[/-](19|20)\d{2}\b")
MAX_SIDE = 1280


def read_card(img: np.ndarray) -> dict | None:
    """Return what the card shows, or None if OCR isn't installed."""
    eng = _ocr()
    if eng is None:
        return None
    h, w = img.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else img.copy()

    t = time.perf_counter()
    with _lock:
        res, _ = eng(small)
    ocr_ms = round((time.perf_counter() - t) * 1000)
    boxes = [(np.array(b, np.float32), str(txt)) for b, txt, _ in (res or [])]
    text = " ".join(txt for _, txt in boxes)
    compact = re.sub(r"\s", "", text).lower()

    numbers = ["".join(m.groups()) for m in FULL.finditer(text)]
    good = [n for n in numbers if valid_aadhaar(n)]
    masked = [m.group(1) for m in MASKED.finditer(text)]

    fields = []
    if good or masked:
        fields.append("number")
    if DATE.search(text) or any(k in compact for k in ("dob", "dateofbirth", "yearofbirth")):
        fields.append("date_of_birth")
    if re.search(r"female|male|transgender", compact):
        fields.append("gender")
    front = "date_of_birth" in fields or "gender" in fields
    back = not front and "address" in compact

    if good and not back:
        status, code, shown, checksum = "verified", None, mask(good[0]), True
    elif masked and front:
        status, code, shown, checksum = "masked", None, f"XXXX XXXX {masked[0]}", None
    elif (good or masked) and back:
        status, code, shown, checksum = "back", "AADHAAR_BACK", None, None
    elif numbers or front:
        # a front side, or 12 digits that fail the check digit: the number wasn't read reliably
        status, code, shown, checksum = "unreadable", "AADHAAR_UNREADABLE", None, False if numbers else None
    else:
        status, code, shown, checksum = "not_aadhaar", "NOT_AADHAAR", None, None

    return {
        "status": status, "code": code, "number": shown, "checksum_ok": checksum,
        "fields": fields, "sample": "sample" in compact, "ocr_ms": ocr_ms, "text_chars": len(compact),
        "masked_preview": _masked_preview(small, boxes),
    }


def _masked_preview(img: np.ndarray, boxes: list) -> str:
    """A copy of the photo with every long ID number blacked out except its last four digits."""
    out = img.copy()
    for poly, txt in boxes:
        digits = re.sub(r"\D", "", txt)
        if len(digits) >= 12:            # whole number in one box: cover all but the last 4 digits
            f = max(0.0, min(1.0, (len(txt.rstrip()) - 4) / max(len(txt.rstrip()), 1) + 0.03))
        elif len(digits) >= 4 and re.fullmatch(r"\s*\d{4}(\s?\d{4})?\s*", txt):
            f = 1.0                      # a 4- or 8-digit group of a split number
        else:
            continue
        p0, p1, p2, p3 = _pad(poly)
        q1, q2 = p0 + (p1 - p0) * f, p3 + (p2 - p3) * f
        cv2.fillPoly(out, [np.array([p0, q1, q2, p3], np.int32)], (30, 30, 30))
    # Keep the last group of a split number visible: un-cover the right-most masked 4-digit box
    # on the line that ends the number, so people can still see which card it is.
    _restore_last_group(out, img, boxes)
    ok, jpg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()


def _pad(poly: np.ndarray, grow: float = 0.25) -> np.ndarray:
    """Grow an OCR box (top-left, top-right, bottom-right, bottom-left) so a cover hides whole digits."""
    p0, p1, p2, p3 = poly
    down = (p3 - p0) * grow
    left = (p0 - p1) * 0.03
    return np.array([p0 - down + left, p1 - down, p2 + down, p3 + down + left], np.float32)


def _restore_last_group(out: np.ndarray, img: np.ndarray, boxes: list) -> None:
    groups = [(poly, txt) for poly, txt in boxes if re.fullmatch(r"\s*\d{4}\s*", txt)]
    for i in range(len(groups) - 2):
        a, b, c = groups[i:i + 3]
        if valid_aadhaar(re.sub(r"\D", "", a[1] + b[1] + c[1])):
            x, y, w, h = cv2.boundingRect(c[0].astype(np.int32))
            out[y:y + h, x:x + w] = img[y:y + h, x:x + w]
