"""Sample ID documents for the demo upload step.

Each sample is drawn here so the real photo check (doccheck.py) judges it, not a flag.
They are generic cards marked "SAMPLE", not a copy of any real ID design, and show only a
masked number (XXXX XXXX 1234), so no real Aadhaar number is ever generated.
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
    # Masked format (only the last 4 digits), as UIDAI's masked Aadhaar shows: no real number appears.
    lines = [("Name", "Samina P."), ("Date of birth", "01/01/1995"), ("Gender", "FEMALE"),
             ("Aadhaar no. (masked)", "XXXX XXXX 1234"), ("Address", "12 Sample Road, New Delhi")]
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


# ---- Bank statement samples (PDF) for the income-document check ----------------------------
STATEMENTS = ("statement_good", "statement_locked", "statement_old", "statement_short")


def _pdf(lines: list[str]) -> bytes:
    """A minimal one-page text PDF (Helvetica), written by hand so no PDF library is needed."""
    body = "BT /F1 10 Tf 50 800 Td 13 TL " + " ".join(
        "(" + ln.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)") + ") '" for ln in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(body)} >>\nstream\n{body}\nendstream"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def make_statement(kind: str, today=None) -> tuple[bytes, str, str]:
    """Synthetic bank statement, dated relative to today so the samples never go stale."""
    from datetime import date, timedelta
    if kind not in STATEMENTS:
        raise KeyError(kind)
    today = today or date.today()
    end = today - timedelta(days=130 if kind == "statement_old" else 4)
    days = 25 if kind == "statement_short" else 92
    lines = ["SAMPLE BANK STATEMENT - DEMO ONLY (synthetic data)", "Account holder: Samina Parveen",
             "Account: XXXXXXXX4821   IFSC: HDFC0001234", "",
             f"Statement period: {(end - timedelta(days=days)):%d/%m/%Y} to {end:%d/%m/%Y}", "",
             "Date        Description                 Amount (Rs)"]
    for i in range(0, days + 1, 15):
        d = end - timedelta(days=days - i)
        lines.append(f"{d:%d/%m/%Y}  {'SALARY CREDIT' if i % 30 == 0 else 'UPI PAYMENT'}            "
                     f"{'45,000.00' if i % 30 == 0 else '-1,250.00'}")
    data = _pdf(lines)
    if kind == "statement_locked":
        import io
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
        w.encrypt(user_password="demo1234", algorithm="RC4-128")
        buf = io.BytesIO()
        w.write(buf)
        data = buf.getvalue()
    return data, "application/pdf", f"bank_{kind}.pdf"
