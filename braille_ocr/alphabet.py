"""English Braille tables used by the OCR pipeline.

Dot numbers follow the conventional six-dot numbering (top to bottom in the
left column, then top to bottom in the right column).  A pattern is represented
as an integer bit mask, where dot 1 is the least significant bit.
"""

from __future__ import annotations


def dots(*numbers: int) -> int:
    """Return the bit mask for a set of Braille dot numbers."""

    value = 0
    for number in numbers:
        value |= 1 << (number - 1)
    return value


LETTER_TO_MASK = {
    "a": dots(1),
    "b": dots(1, 2),
    "c": dots(1, 4),
    "d": dots(1, 4, 5),
    "e": dots(1, 5),
    "f": dots(1, 2, 4),
    "g": dots(1, 2, 4, 5),
    "h": dots(1, 2, 5),
    "i": dots(2, 4),
    "j": dots(2, 4, 5),
    "k": dots(1, 3),
    "l": dots(1, 2, 3),
    "m": dots(1, 3, 4),
    "n": dots(1, 3, 4, 5),
    "o": dots(1, 3, 5),
    "p": dots(1, 2, 3, 4),
    "q": dots(1, 2, 3, 4, 5),
    "r": dots(1, 2, 3, 5),
    "s": dots(2, 3, 4),
    "t": dots(2, 3, 4, 5),
    "u": dots(1, 3, 6),
    "v": dots(1, 2, 3, 6),
    "w": dots(2, 4, 5, 6),
    "x": dots(1, 3, 4, 6),
    "y": dots(1, 3, 4, 5, 6),
    "z": dots(1, 3, 5, 6),
}

MASK_TO_LETTER = {mask: letter for letter, mask in LETTER_TO_MASK.items()}

# UEB / English Braille punctuation that can be decoded without word context.
PUNCTUATION_TO_MASK = {
    ",": dots(2),
    ";": dots(2, 3),
    ":": dots(2, 5),
    ".": dots(2, 5, 6),
    "!": dots(2, 3, 5),
    "?": dots(2, 3, 6),
    "'": dots(3),
    "-": dots(3, 6),
    '"': dots(2, 3, 5, 6),
    "(": dots(1, 2, 3, 5, 6),
    ")": dots(2, 3, 4, 5, 6),
    "/": dots(3, 4),
    "*": dots(3, 5),
    "&": dots(1, 2, 3, 4, 6),
    "@": dots(4),
    "+": dots(3, 4, 6),
    "=": dots(2, 3, 5, 6),
}

# Some literary and mathematical symbols share a cell in UEB and are resolved
# by context. Keep the first literary symbol as the safe default for OCR.
MASK_TO_PUNCTUATION: dict[int, str] = {}
for character, mask in PUNCTUATION_TO_MASK.items():
    MASK_TO_PUNCTUATION.setdefault(mask, character)

CAPITAL_MASK = dots(6)
NUMBER_MASK = dots(3, 4, 5, 6)

# In a number, a-j are represented by the same patterns as 1-0.
DIGIT_TO_MASK = {
    "1": LETTER_TO_MASK["a"],
    "2": LETTER_TO_MASK["b"],
    "3": LETTER_TO_MASK["c"],
    "4": LETTER_TO_MASK["d"],
    "5": LETTER_TO_MASK["e"],
    "6": LETTER_TO_MASK["f"],
    "7": LETTER_TO_MASK["g"],
    "8": LETTER_TO_MASK["h"],
    "9": LETTER_TO_MASK["i"],
    "0": LETTER_TO_MASK["j"],
}
MASK_TO_DIGIT = {mask: digit for digit, mask in DIGIT_TO_MASK.items()}

# Whole-word contractions from Grade 2 English Braille.  They are deliberately
# limited to unambiguous single-cell words in this first release.
COMMON_WORD_CONTRACTIONS = {
    dots(1, 2, 3, 4, 6): "and",
    dots(1, 2, 3, 4, 5, 6): "for",
    dots(2, 3, 4, 6): "the",
}

KNOWN_MASKS = (
    set(MASK_TO_LETTER)
    | set(MASK_TO_PUNCTUATION)
    | {CAPITAL_MASK, NUMBER_MASK}
    | set(MASK_TO_DIGIT)
    | set(COMMON_WORD_CONTRACTIONS)
)
