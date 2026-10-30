"""Aadhaar card reading: check digit, privacy, and real-photo verdicts.

The card images here are drawn in code with made-up numbers (layout only, no real data).
"""
import base64

import cv2
import numpy as np
import pytest

from pakka import aadhaar, doccheck
from pakka.aadhaar import _D, _P, mask, valid_aadhaar, verhoeff_ok
from pakka.doccheck import check_array, check_image

_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def with_check_digit(first11: str) -> str:
    c = 0
    for i, ch in enumerate(reversed(first11)):
        c = _D[c][_P[(i + 1) % 8][int(ch)]]
    return first11 + str(_INV[c])


GOOD = with_check_digit("53846219077")
BAD = GOOD[:-1] + str((int(GOOD[-1]) + 1) % 10)


def card(num=GOOD, side="front", w=1010, h=640):
    img = np.full((h, w, 3), 252, np.uint8)
    f = cv2.FONT_HERSHEY_DUPLEX
    if side == "front":
        cv2.putText(img, "Government of India", (330, 70), f, 1.2, (20, 20, 20), 2, cv2.LINE_AA)
        cv2.rectangle(img, (50, 130), (260, 390), (160, 160, 160), -1)
        for i, t in enumerate(["Ravi Kumar", "DOB: 12/03/1990", "MALE"]):
            cv2.putText(img, t, (300, 170 + i * 60), f, 1.0, (20, 20, 20), 2, cv2.LINE_AA)
    else:
        cv2.putText(img, "Address:", (60, 120), f, 1.0, (20, 20, 20), 2, cv2.LINE_AA)
        cv2.putText(img, "S/O Mohan Kumar, 45 Nehru Nagar, Jaipur", (60, 170), f, 0.9, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(img, f"{num[:4]} {num[4:8]} {num[8:]}", (330, 540), f, 1.6, (10, 10, 10), 3, cv2.LINE_AA)
    return img


def on_table(img, big=False):
    bg = np.full((1100, 1600, 3), (60, 70, 80), np.uint8)
    bg[230:230 + img.shape[0], 295:295 + img.shape[1]] = img
    return cv2.resize(bg, (4000, 2750), interpolation=cv2.INTER_CUBIC) if big else bg


def jpg(img):
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


# ---- check digit and masking (no OCR needed) ----------------------------------------------

def test_verhoeff_accepts_valid_and_rejects_one_digit_change():
    assert verhoeff_ok(GOOD) and valid_aadhaar(GOOD)
    assert not valid_aadhaar(BAD)


def test_aadhaar_never_starts_with_0_or_1():
    for first in "01":
        n = with_check_digit(first + GOOD[1:11])
        assert verhoeff_ok(n) and not valid_aadhaar(n)


def test_mask_shows_only_last_four():
    assert mask(GOOD) == f"XXXX XXXX {GOOD[-4:]}"


# ---- photo quality on real-world shapes (no OCR needed) -----------------------------------

def test_full_frame_scan_is_not_called_cut_off():
    assert "IMG_CROPPED" not in check_array(card())["issues"]


def test_white_card_is_not_called_glare():
    assert "IMG_GLARE" not in check_array(card())["issues"]


def test_big_phone_photo_is_not_called_blurry():
    assert "IMG_BLUR" not in check_array(on_table(card(), big=True))["issues"]


def test_without_ocr_falls_back_to_photo_quality(monkeypatch):
    monkeypatch.setattr(doccheck.aadhaar, "read_card", lambda img: None)
    r = check_image(jpg(on_table(card())))
    assert r["ok"] and r["card"] is None


# ---- reading the card (needs the optional OCR) --------------------------------------------

ocr = pytest.mark.skipif(not aadhaar.available(), reason="rapidocr_onnxruntime not installed")


@ocr
@pytest.mark.parametrize("img", [card(), on_table(card()), on_table(card(), big=True)],
                         ids=["scan", "phone photo", "12 MP photo"])
def test_real_front_is_verified(img):
    r = check_image(jpg(img))
    assert r["ok"], r["issues"]
    assert r["card"]["status"] == "verified" and r["card"]["checksum_ok"] is True
    assert r["card"]["number"] == mask(GOOD)
    assert {"date_of_birth", "gender"} <= set(r["card"]["fields"])


@ocr
def test_back_side_is_rejected():
    assert check_image(jpg(card(side="back")))["issues"] == ["AADHAAR_BACK"]


@ocr
def test_wrong_check_digit_is_rejected():
    assert check_image(jpg(card(num=BAD)))["issues"] == ["AADHAAR_UNREADABLE"]


@ocr
def test_not_a_card_is_rejected():
    blank = np.full((700, 1000, 3), 128, np.uint8)
    cv2.putText(blank, "Grocery list: rice, dal, tea", (60, 300), cv2.FONT_HERSHEY_DUPLEX, 1.2, (20, 20, 20), 2)
    assert check_image(jpg(blank))["issues"] == ["NOT_AADHAAR"]


@ocr
def test_full_number_never_leaves_the_server():
    r = check_image(jpg(card()))
    preview = r["card"].pop("masked_preview")
    assert GOOD not in str(r) and GOOD[:8] not in str(r)
    # and the masked preview no longer shows the first 8 digits to OCR
    img = cv2.imdecode(np.frombuffer(base64.b64decode(preview.split(",", 1)[1]), np.uint8), cv2.IMREAD_COLOR)
    seen = aadhaar.read_card(img)
    assert seen["status"] != "verified"
    assert GOOD[:4] not in str(seen) and GOOD[4:8] not in str(seen)
