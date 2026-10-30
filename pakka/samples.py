"""Sample ID documents for the demo upload step.

Each sample is drawn here so the real photo check (doccheck.py) judges it, not a flag.
They are generic cards marked "SAMPLE", not a copy of any real ID design.
"""
import cv2
import numpy as np

KINDS = ("good", "cropped", "blurry", "glare", "wrong_file")
W, H = 960, 640


def _card(img: np.ndarray, x: int, y: int) -> None:
    cw, ch = 760, 470
    cv2.rectangle(img, (x, y), (x + cw, y + ch), (236, 238, 240), -1)
    cv2.rectangle(img, (x, y), (x + cw, y + 70), (205, 222, 236), -1)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, "SAMPLE IDENTITY CARD", (x + 30, y + 46), font, 1.1, (40, 52, 70), 2, cv2.LINE_AA)
    cv2.putText(img, "DEMO ONLY", (x + cw - 200, y + 46), font, 0.8, (30, 90, 170), 2, cv2.LINE_AA)
    # photo box with a simple face outline
    px, py = x + 40, y + 110
    cv2.rectangle(img, (px, py), (px + 190, py + 240), (190, 196, 204), -1)
    cv2.circle(img, (px + 95, py + 95), 48, (120, 128, 140), -1)
    cv2.ellipse(img, (px + 95, py + 230), (80, 70), 0, 180, 360, (120, 128, 140), -1)
    lines = [("Name", "Samina P."), ("Date of birth", "01 / 01 / 1995"), ("Gender", "F"),
             ("ID number", "XXXX XXXX 1234"), ("Address", "12 Sample Road, New Delhi")]
    for i, (k, v) in enumerate(lines):
        ty = y + 140 + i * 58
        cv2.putText(img, k, (x + 270, ty), font, 0.6, (110, 118, 130), 1, cv2.LINE_AA)
        cv2.putText(img, v, (x + 270, ty + 28), font, 0.85, (25, 30, 40), 2, cv2.LINE_AA)
    for i in range(14):  # barcode strip
        bx = x + 40 + i * 14
        cv2.rectangle(img, (bx, y + 380), (bx + (4 if i % 3 else 8), y + 440), (40, 40, 40), -1)


def make_sample(kind: str) -> tuple[bytes, str, str]:
    """Return (file bytes, media type, file name) for one sample."""
    if kind not in KINDS:
        raise KeyError(kind)
    if kind == "wrong_file":
        # a Word file where a photo was expected: the classic wrong upload
        body = b"PK\x03\x04" + b"\x00" * 26 + b"word/document.xml Sample ID scan - demo only"
        return body, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "id_card_scan.docx"
    img = np.full((H, W, 3), (62, 58, 54), np.uint8)  # dark table top
    rng = np.random.default_rng(7)
    img = np.clip(img + rng.integers(-6, 7, img.shape), 0, 255).astype(np.uint8)
    _card(img, -260 if kind == "cropped" else 100, 85)
    if kind == "glare":
        # a soft light reflection: saturated in the middle, fading at the edges
        mask = np.zeros((H, W), np.float32)
        cv2.ellipse(mask, (540, 320), (220, 140), -20, 0, 360, 1.0, -1)
        mask = np.clip(cv2.GaussianBlur(mask, (0, 0), 45) * 1.7, 0, 1)[..., None]
        img = (img * (1 - mask) + 255 * mask).astype(np.uint8)
    if kind == "blurry":
        img = cv2.GaussianBlur(img, (45, 45), 0)
    ok, png = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return png.tobytes(), "image/jpeg", f"id_card_{kind}.jpg"
