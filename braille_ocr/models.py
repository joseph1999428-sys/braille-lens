"""Small data models shared by detection, translation, and the web app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OCRConfig:
    """Controls for the OpenCV detector.

    Values are intentionally expressed in relative terms where possible so
    that a 300 dpi scan and a phone photo can use the same defaults.
    """

    threshold_mode: str = "otsu"  # otsu | adaptive | local_contrast
    invert: bool = False
    min_component_area: int = 8
    max_component_area: int = 100000
    adaptive_block_size: int = 31
    adaptive_c: int = 7
    dot_row_tolerance: float = 0.65
    cell_gap_ratio: float = 1.30


@dataclass(frozen=True)
class Dot:
    x: float
    y: float
    area: float
    radius: float
    score: float = 1.0


@dataclass
class Cell:
    """One six-dot Braille cell.

    ``mask`` uses the same dot numbering as :mod:`braille_ocr.alphabet`.
    ``is_space`` is true for an inferred blank cell (no connected component).
    """

    mask: int
    x: float
    y: float
    line_index: int
    confidence: float
    is_space: bool = False
    dot_count: int = 0
    uncertain: bool = False


@dataclass
class OCRResult:
    text: str
    cells: list[Cell] = field(default_factory=list)
    dots: list[Dot] = field(default_factory=list)
    binary: Any = None
    annotated: Any = None
    confidence: float = 0.0
    diagnostics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    rejected_components: int = 0
    ambiguous_cells: list[int] = field(default_factory=list)
