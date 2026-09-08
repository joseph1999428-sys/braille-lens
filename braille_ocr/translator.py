"""UEB back-translation. Geometry uncertainty is never repaired by word guesses."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import re

from .models import Cell
from .louis_engine import LouisUnavailable, TABLES, get_engine

UNKNOWN = "\u25a1"
UNDEFINED = re.compile(r"\\[1-8]+/")


@dataclass
class Translation:
    text: str = ""
    braille: str = ""
    engine: str = "unavailable"
    table: str = ""
    version: str = ""
    warnings: list[str] = field(default_factory=list)
    uncertain_cells: list[int] = field(default_factory=list)
    unsupported_cells: list[int] = field(default_factory=list)
    coverage: float = 0.0


def translate_cells(cells: Iterable[Cell], grade: str = "Grade 1") -> Translation:
    if grade not in TABLES:
        raise ValueError("grade must be 'Grade 1' or 'Grade 2'")
    indexed = sorted(enumerate(cells, 1), key=lambda item: (item[1].line_index, item[1].x))
    if any(not isinstance(c.mask, int) or not 0 <= c.mask <= 63 for _, c in indexed):
        raise ValueError("Cell masks must be integers in range 0..63")
    # None denotes a line boundary; source ids stay linked to the overlay.
    tokens: list[tuple[int, Cell] | None] = []
    previous_line = None
    for identifier, cell in indexed:
        if previous_line is not None and previous_line != cell.line_index:
            tokens.append(None)
        tokens.append((identifier, cell))
        previous_line = cell.line_index
    raw = "".join("\n" if t is None else " " if t[1].is_space else chr(0x2800 + t[1].mask) for t in tokens)
    result = Translation(braille=raw, table=TABLES[grade])
    if not indexed:
        return result
    try:
        engine = get_engine()
    except LouisUnavailable as error:
        result.warnings = [str(error), "English translation is unavailable. Detected Braille has been preserved."]
        return result
    result.engine, result.version = "Liblouis", engine.version
    parts: list[str] = []
    pending: list[tuple[int, Cell] | None] = []

    def flush() -> None:
        if not pending:
            return
        masks = [0 if t is None or t[1].is_space else t[1].mask for t in pending]
        # OCR commonly splits the UEB percent sign (46-356) into dot-5,
        # dot-26, dot-356. Normalize that exact pattern before table lookup.
        normalized = []
        i = 0
        while i < len(masks):
            if i + 2 < len(masks) and masks[i:i + 3] == [16, 26, 52]:
                normalized.extend([40, 52]); i += 3
            elif i + 1 < len(masks) and masks[i:i + 2] == [16, 52]:
                normalized.extend([40, 52]); i += 2
            else:
                normalized.append(masks[i]); i += 1
        text, positions = engine.back_translate(normalized, grade)
        for match in UNDEFINED.finditer(text):
            source_pos = positions[match.start()] if match.start() < len(positions) else -1
            if 0 <= source_pos < len(pending):
                token = pending[source_pos]
                if token is not None:
                    result.unsupported_cells.append(token[0])
        # Keep paragraph translation context; restore line breaks using the
        # native source-position map, before shortening undefined escapes.
        breaks = {i for i, t in enumerate(pending) if t is None}
        restored = list(text)
        for i, pos in enumerate(positions):
            if i < len(restored) and pos in breaks and restored[i].isspace():
                restored[i] = "\n"
                breaks.remove(pos)
        for i, ch in enumerate(text):
            if 0xE000 <= ord(ch) <= 0xF8FF:
                token = pending[positions[i]]
                if token is not None:
                    result.unsupported_cells.append(token[0])
        text = UNDEFINED.sub(UNKNOWN, "".join(restored)).replace("\xa0", " ")
        text = "".join(UNKNOWN if 0xE000 <= ord(ch) <= 0xF8FF else ch for ch in text)
        if not text.strip() and any(masks):
            text = "".join(" " if m == 0 else UNKNOWN for m in masks)
            result.unsupported_cells.extend(t[0] for t in pending if t is not None and t[1].mask)
        parts.append(text)
        pending.clear()

    word: list[tuple[int, Cell]] = []

    def append_word() -> None:
        if any(c.uncertain for _, c in word):
            flush()
            parts.append("".join(UNKNOWN if c.uncertain else chr(0x2800 + c.mask) for _, c in word))
            result.uncertain_cells.extend(i for i, c in word if c.uncertain)
        else:
            pending.extend(word)
        word.clear()

    try:
        for token in tokens:
            if token is None or token[1].is_space or token[1].mask == 0:
                append_word()
                pending.append(token)
            else:
                word.append(token)
        append_word()
        flush()
    except LouisUnavailable as error:
        result.warnings.append(str(error))
        return result
    result.text = "".join(parts).strip()
    result.unsupported_cells = sorted(set(result.unsupported_cells))
    if result.uncertain_cells:
        result.warnings.append("Words containing uncertain cells remain in Braille; squares mark the uncertain cells. Translation context restarts after them.")
    if result.unsupported_cells:
        result.warnings.append("Some cells or indicator sequences are unsupported in the selected UEB table and are marked with squares.")
    total = sum(not c.is_space and bool(c.mask) for _, c in indexed)
    bad = len(set(result.unsupported_cells + result.uncertain_cells))
    result.coverage = max(0.0, 1.0 - bad / total) if total else 0.0
    return result


def decode_cells(cells: Iterable[Cell], grade: str = "Grade 1") -> tuple[str, float]:
    """Compatibility API: returns text and table coverage, not OCR accuracy."""
    result = translate_cells(cells, grade)
    return result.text, result.coverage
