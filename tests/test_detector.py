from braille_ocr import OCRConfig, detect_braille
from braille_ocr.render import render_braille
import numpy as np
from pathlib import Path
from PIL import Image


def test_demo_image_round_trip():
    image = render_braille("Hello world\nBraille 123", scale=1)
    result = detect_braille(image, OCRConfig())
    assert result.diagnostics["dots"] > 20
    assert result.diagnostics["cells"] > 10
    assert "Hello" in result.text
    assert "world" in result.text
    assert "123" in result.text


def test_sparse_cells_and_word_gaps():
    result = detect_braille(render_braille("A B C"), OCRConfig())
    assert result.text == "A B C"


def test_inverted_photo_mode():
    image = np.asarray(render_braille("Test 42"))
    result = detect_braille(255 - image, OCRConfig(threshold_mode="adaptive", invert=True))
    assert result.text == "Test 42"


def test_small_camera_roll_is_corrected():
    image = render_braille("Hello world", scale=2).rotate(4, expand=True, fillcolor="white")
    result = detect_braille(image, OCRConfig())
    assert result.text == "Hello world"
    assert abs(result.diagnostics["deskew_angle_deg"]) > 2


def test_supplied_low_contrast_page_recovers_body_text():
    picture = Path(__file__).parents[1] / "t1.jpg"
    if not picture.exists():
        return
    result = detect_braille(Image.open(picture), OCRConfig())
    assert "Because according to" in result.text
    assert "89%" in result.text
