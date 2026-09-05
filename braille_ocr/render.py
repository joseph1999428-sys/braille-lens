"""Utilities for making a clean demo image and regression fixtures."""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from .alphabet import (
    CAPITAL_MASK,
    DIGIT_TO_MASK,
    LETTER_TO_MASK,
    NUMBER_MASK,
    PUNCTUATION_TO_MASK,
)


def text_to_masks(text: str) -> list[list[int]]:
    lines: list[list[int]] = []
    for line in text.splitlines() or [""]:
        masks: list[int] = []
        numeric = False
        for character in line:
            if character == " ":
                masks.append(0)
                numeric = False
                continue
            if character.isdigit():
                if not numeric:
                    masks.append(NUMBER_MASK)
                    numeric = True
                masks.append(DIGIT_TO_MASK[character])
                continue
            numeric = False
            if character.isalpha():
                if character.isupper():
                    masks.append(CAPITAL_MASK)
                masks.append(LETTER_TO_MASK[character.lower()])
            elif character in PUNCTUATION_TO_MASK:
                masks.append(PUNCTUATION_TO_MASK[character])
        lines.append(masks)
    return lines


def render_braille(text: str, scale: int = 1) -> Image.Image:
    """Render a high-resolution black-on-white Braille fixture with OpenCV."""

    scale = max(1, int(scale))
    dot_gap = 28 * scale
    cell_pitch = 76 * scale
    row_pitch = 30 * scale
    line_pitch = 132 * scale
    radius = 9 * scale
    margin = 32 * scale
    lines = text_to_masks(text)
    width_cells = max((len(line) for line in lines), default=1)
    height = margin * 2 + max(1, len(lines)) * line_pitch
    width = margin * 2 + max(1, width_cells) * cell_pitch
    canvas = np.full((height, width), 255, dtype=np.uint8)
    for line_index, masks in enumerate(lines):
        y0 = margin + line_index * line_pitch
        for cell_index, mask in enumerate(masks):
            x0 = margin + cell_index * cell_pitch
            for dot in range(1, 7):
                if mask & (1 << (dot - 1)):
                    column = 0 if dot <= 3 else 1
                    row = (dot - 1) % 3
                    center = (
                        int(x0 + column * dot_gap),
                        int(y0 + row * row_pitch),
                    )
                    cv2.circle(canvas, center, radius, 0, thickness=-1, lineType=cv2.LINE_AA)
    return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_GRAY2RGB))

