"""Convert detected six-dot cells to English text."""

from __future__ import annotations

from collections.abc import Iterable

from .alphabet import (
    CAPITAL_MASK,
    COMMON_WORD_CONTRACTIONS,
    MASK_TO_DIGIT,
    MASK_TO_LETTER,
    MASK_TO_PUNCTUATION,
    NUMBER_MASK,
    KNOWN_MASKS,
)
from .models import Cell


# UEB uses dot 56 as a letter indicator in a few contexts. It carries no
# English character and is common in photographed worksheets that mix Grade 1
# and Grade 2 notation.
LETTER_INDICATOR_MASK = 48


def _decode_cell(mask: int, numeric: bool) -> tuple[str, bool, bool]:
    """Return (character, recognized, remains_numeric)."""

    if numeric and mask in MASK_TO_DIGIT:
        return MASK_TO_DIGIT[mask], True, True
    if mask in MASK_TO_PUNCTUATION:
        # Punctuation terminates a number only when it is not a decimal-style
        # separator. Keeping the state here also makes ``12,000`` natural.
        return MASK_TO_PUNCTUATION[mask], True, numeric
    if mask in MASK_TO_LETTER:
        return MASK_TO_LETTER[mask], True, False
    return "□", False, False


def _decode_word(cells: list[Cell], grade: str) -> tuple[str, int, int]:
    if not cells:
        return "", 0, 0

    if grade == "Grade 2" and len(cells) == 1:
        contraction = COMMON_WORD_CONTRACTIONS.get(cells[0].mask)
        if contraction is not None:
            return contraction, 1, 1

    output: list[str] = []
    numeric = False
    capital_next = False
    recognized = 0
    total = 0
    index = 0
    while index < len(cells):
        cell = cells[index]
        total += 1
        if cell.mask == CAPITAL_MASK:
            capital_next = True
            recognized += 1
            index += 1
            continue
        if cell.mask == LETTER_INDICATOR_MASK:
            recognized += 1
            numeric = False
            index += 1
            continue
        if cell.mask == NUMBER_MASK:
            numeric = True
            recognized += 1
            index += 1
            continue
        # The UEB percent sign is two cells (46-356). Low-resolution photos
        # commonly fragment it into dot-5 followed by 356; recognize that
        # sequence only while reading a number so ordinary punctuation is not
        # guessed as a percent sign.
        if numeric and cell.mask == 16 and index + 1 < len(cells) and cells[index + 1].mask in (52, 26):
            output.append("%")
            consumed = 2
            if cells[index + 1].mask == 26 and index + 2 < len(cells) and cells[index + 2].mask == 52:
                consumed = 3
            recognized += consumed
            total += consumed - 1
            numeric = False
            index += consumed
            continue
        character, known, numeric_after = _decode_cell(cell.mask, numeric)
        if known:
            recognized += 1
        if capital_next and character.isalpha():
            character = character.upper()
            capital_next = False
        output.append(character)
        numeric = numeric_after
        index += 1
    return "".join(output), recognized, total


def decode_cells(cells: Iterable[Cell], grade: str = "Grade 1") -> tuple[str, float]:
    """Decode cells in reading order and return ``(text, confidence)``.

    The detector inserts blank cells when the image contains a visible word
    gap. This function also accepts a sparse list, which is useful to callers
    that only want to translate known masks in tests or another UI.
    """

    cell_list = list(cells)
    by_line: dict[int, list[Cell]] = {}
    for cell in cell_list:
        by_line.setdefault(cell.line_index, []).append(cell)

    lines: list[str] = []
    recognized = 0
    total = 0
    for line_index in sorted(by_line):
        line_cells = sorted(by_line[line_index], key=lambda cell: cell.x)
        words: list[list[Cell]] = []
        current_word: list[Cell] = []
        for cell in line_cells:
            if cell.is_space or cell.mask == 0:
                if current_word:
                    words.append(current_word)
                    current_word = []
            else:
                current_word.append(cell)
        if current_word:
            words.append(current_word)
        line_parts: list[str] = []
        for word_index, word in enumerate(words):
            if word_index:
                line_parts.append(" ")
            decoded, known, count = _decode_word(word, grade)
            line_parts.append(decoded)
            recognized += known
            total += count
        lines.append("".join(line_parts).strip())

    text = "\n".join(lines).strip()
    coverage = recognized / total if total else 0.0
    weighted = sum(
        max(0.1, float(cell.confidence)) * (1.0 if cell.mask in KNOWN_MASKS else 0.0)
        for cell in cell_list if not cell.is_space
    )
    weight_total = sum(max(0.1, float(cell.confidence)) for cell in cell_list if not cell.is_space)
    table_coverage = weighted / weight_total if weight_total else 0.0
    return text, (0.65 * coverage + 0.35 * table_coverage)
