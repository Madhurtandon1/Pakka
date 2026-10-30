import cv2
import numpy as np

from pakka.doccheck import check_array, check_image


def card(offset_x=80, blur=False, glare=False):
    rng = np.random.default_rng(1)
    img = np.full((480, 720, 3), 55, np.uint8)
    x1, y1, x2, y2 = offset_x, 90, offset_x + 540, 400
    cv2.rectangle(img, (max(x1, 0), y1), (min(x2, 719), y2), (215, 215, 215), -1)
    for _ in range(40):
        x = int(rng.integers(max(x1, 0) + 20, min(x2, 719) - 120))
        y = int(rng.integers(y1 + 20, y2 - 20))
        cv2.line(img, (x, y), (x + 100, y), (30, 30, 30), 2)
    if glare:
        cv2.circle(img, (360, 240), 110, (255, 255, 255), -1)
    if blur:
        img = cv2.GaussianBlur(img, (41, 41), 0)
    return img


def test_good_card_passes():
    r = check_array(card())
    assert r["ok"], r


def test_cropped_card():
    assert "IMG_CROPPED" in check_array(card(offset_x=-120))["issues"]


def test_blurry_card():
    assert "IMG_BLUR" in check_array(card(blur=True))["issues"]


def test_glare():
    assert "IMG_GLARE" in check_array(card(glare=True))["issues"]


def test_not_an_image():
    assert check_image(b"%PDF-1.4 not an image")["issues"] == ["FILE_FORMAT"]


# Demo sample files: the real photo check must judge each one as its button says.
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from pakka.samples import KINDS, make_sample  # noqa: E402

EXPECTED = {"good": [], "cropped": ["IMG_CROPPED"], "blurry": ["IMG_BLUR"],
            "glare": ["IMG_GLARE"], "wrong_file": ["FILE_FORMAT"]}


@pytest.mark.parametrize("kind", KINDS)
def test_sample_gets_expected_verdict(kind):
    data, _, _ = make_sample(kind)
    assert check_image(data)["issues"] == EXPECTED[kind]


@pytest.mark.parametrize("kind", KINDS)
def test_sample_round_trip_through_api(kind):
    c = TestClient(app)
    r = c.get(f"/samples/{kind}")
    assert r.status_code == 200 and "filename=" in r.headers["content-disposition"]
    verdict = c.post("/doccheck", files={"file": ("x", r.content, r.headers["content-type"])}).json()
    assert verdict["issues"] == EXPECTED[kind]


def test_unknown_sample_is_404():
    assert TestClient(app).get("/samples/nope").status_code == 404
