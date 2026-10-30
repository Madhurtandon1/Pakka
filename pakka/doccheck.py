import cv2
import numpy as np

from pakka import aadhaar

BLUR_MIN = 60.0
GLARE_MAX = 0.06
EDGE_MARGIN = 0.02
WHITE_CARD = 245     # a card whose own median brightness is this high is white paper, not glare
FULL_FRAME = 0.85    # a "card" covering more than this is a scan or close-up, not a cut-off photo
READABLE_CHARS = 20  # if OCR reads this much text, "blurry" isn't the reason a card failed
MEASURE_SIDE = 1000  # sharpness is measured at this size, so big phone photos aren't called blurry


def check_image(data: bytes) -> dict:
    """Full upload check: photo quality, then read the card (if OCR is available)."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return {"ok": False, "issues": ["FILE_FORMAT"], "metrics": {}, "card": None}
    quality = check_array(img)
    card = aadhaar.read_card(img)

    q = quality["issues"]
    if "IMG_CROPPED" in q:
        issues = q                                   # KYC needs the whole card, even if it's readable
    elif card is None:
        issues = q                                   # no OCR on this server: photo quality only
    elif card["status"] in ("verified", "masked"):
        issues = []                                  # readable Aadhaar front: blur/glare didn't hide it
    elif card["status"] == "back":
        issues = [card["code"]]                      # clearly the back: say so, whatever the photo quality
    else:
        if card["text_chars"] >= READABLE_CHARS:     # it read plenty of text, so the photo isn't blurry
            q = [i for i in q if i != "IMG_BLUR"]
        issues = q or [card["code"]]                 # a photo problem explains a failed read best
    out = {"ok": not issues, "issues": issues, "metrics": quality["metrics"], "card": card}
    if not issues and q:
        out["warnings"] = q
    return out


def check_array(img: np.ndarray) -> dict:
    """Photo quality only: blur, glare, and a card cut off at the edge of the frame."""
    h, w = img.shape[:2]
    scale = min(1.0, MEASURE_SIDE / max(h, w))
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    cropped, found, rect = _card_touches_edge(gray)
    x, y, cw, ch = rect
    card_median = float(np.median(gray[y:y + ch, x:x + cw]))
    # Glare is saturated light on a card that isn't itself white: a scan of white paper is not glare.
    glare = float((gray >= 250).mean()) if card_median < WHITE_CARD else 0.0

    issues = []
    if cropped:
        issues.append("IMG_CROPPED")
    if sharpness < BLUR_MIN:
        issues.append("IMG_BLUR")
    if glare > GLARE_MAX:
        issues.append("IMG_GLARE")

    return {
        "ok": not issues,
        "issues": issues,
        "metrics": {"sharpness": round(sharpness, 1), "glare_ratio": round(glare, 4),
                    "card_found": found, "size": [w, h]},
    }


def _card_touches_edge(gray: np.ndarray) -> tuple[bool, bool, tuple[int, int, int, int]]:
    """(cut off at the edge?, card found?, card rectangle or the whole image)."""
    h, w = gray.shape
    whole = (0, 0, w, h)
    _, mask = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, False, whole
    card = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(card)
    if area < 0.15 * w * h:
        return False, False, whole
    if area > FULL_FRAME * w * h:
        return False, True, whole  # the card fills the picture (a scan or close-up): nothing visible is cut off
    x, y, cw, ch = cv2.boundingRect(card)
    mx, my = int(w * EDGE_MARGIN), int(h * EDGE_MARGIN)
    touches = x <= mx or y <= my or x + cw >= w - mx or y + ch >= h - my
    return touches, True, (x, y, cw, ch)
