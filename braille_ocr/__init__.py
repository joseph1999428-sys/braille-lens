"""Braille image OCR package."""

from .detector import detect_braille
from .models import Cell, Dot, OCRConfig, OCRResult
from .translator import decode_cells

__all__ = [
    "Cell",
    "Dot",
    "OCRConfig",
    "OCRResult",
    "decode_cells",
    "detect_braille",
]

