from braille_ocr.alphabet import CAPITAL_MASK, DIGIT_TO_MASK, LETTER_TO_MASK, NUMBER_MASK, PUNCTUATION_TO_MASK
from braille_ocr.models import Cell
from braille_ocr.translator import decode_cells


def test_grade_one_letters_and_capital():
    cells = [
        Cell(CAPITAL_MASK, 0, 0, 0, 1.0),
        Cell(LETTER_TO_MASK["h"], 1, 0, 0, 1.0),
        Cell(LETTER_TO_MASK["i"], 2, 0, 0, 1.0),
    ]
    text, confidence = decode_cells(cells)
    assert text == "Hi"
    assert confidence == 1.0


def test_numbers_and_inferred_space():
    cells = [
        Cell(NUMBER_MASK, 0, 0, 0, 1.0),
        Cell(LETTER_TO_MASK["a"], 1, 0, 0, 1.0),
        Cell(LETTER_TO_MASK["b"], 2, 0, 0, 1.0),
        Cell(0, 3, 0, 0, 1.0, is_space=True),
        Cell(LETTER_TO_MASK["c"], 4, 0, 0, 1.0),
    ]
    text, confidence = decode_cells(cells)
    assert text == "12 c"
    assert confidence == 1.0


def test_grade_two_common_word_contraction():
    cells = [Cell(0b101111, 0, 0, 0, 1.0)]  # dots 1,2,3,4,6 = and
    text, confidence = decode_cells(cells, grade="Grade 2")
    assert text == "and"
    assert confidence == 1.0


def test_punctuation_keeps_its_symbol():
    cells = [Cell(PUNCTUATION_TO_MASK["!"], 0, 0, 0, 1.0)]
    text, confidence = decode_cells(cells)
    assert text == "!"
    assert confidence == 1.0


def test_letter_indicator_is_silent_and_percent_after_number():
    cells = [
        Cell(NUMBER_MASK, 0, 0, 0, 1.0),
        Cell(DIGIT_TO_MASK["8"], 1, 0, 0, 1.0),
        Cell(16, 2, 0, 0, 1.0),
        Cell(52, 3, 0, 0, 1.0),
    ]
    text, _ = decode_cells(cells)
    assert text.endswith("%")
