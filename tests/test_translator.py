from braille_ocr.alphabet import CAPITAL_MASK, DIGIT_TO_MASK, LETTER_TO_MASK, NUMBER_MASK, PUNCTUATION_TO_MASK
from braille_ocr.models import Cell
from braille_ocr.translator import decode_cells
from braille_ocr.translator import translate_cells


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


def test_grade_two_whole_word_contractions_are_contextual():
    # "but" uses the same cell as Grade 1 b, but only contracts as a
    # standalone Grade 2 word.
    cells = [Cell(LETTER_TO_MASK["b"], 0, 0, 0, 1.0)]
    assert decode_cells(cells, grade="Grade 1")[0] == "b"
    assert decode_cells(cells, grade="Grade 2")[0] == "but"


def test_punctuation_keeps_its_symbol():
    cells = [Cell(PUNCTUATION_TO_MASK["!"], 0, 0, 0, 1.0)]
    text, confidence = decode_cells(cells)
    assert text == "!"
    assert confidence == 1.0


def test_percent_uses_standard_ueb_sequence():
    cells = [
        Cell(NUMBER_MASK, 0, 0, 0, 1.0),
        Cell(DIGIT_TO_MASK["8"], 1, 0, 0, 1.0),
        Cell(40, 2, 0, 0, 1.0),  # dots 46
        Cell(52, 3, 0, 0, 1.0),
    ]
    text, _ = decode_cells(cells)
    assert text.endswith("%")


def test_malformed_percent_like_sequence_is_not_repaired():
    cells = [Cell(NUMBER_MASK, 0, 0, 0, 1.0), Cell(DIGIT_TO_MASK["8"], 1, 0, 0, 1.0), Cell(16, 2, 0, 0, 1.0), Cell(52, 3, 0, 0, 1.0)]
    result = translate_cells(cells)
    assert not result.text.endswith("%")


def test_liblouis_ueb_round_trip_for_grade_two():
    from braille_ocr.louis_engine import get_engine

    engine = get_engine()
    masks = engine.forward("The boy walked to school.", "Grade 2")
    cells = [Cell(mask, i, 0, 0, 1.0, is_space=mask == 0) for i, mask in enumerate(masks)]
    result = translate_cells(cells, "Grade 2")
    assert result.engine == "Liblouis"
    assert result.text == "The boy walked to school."
    assert result.coverage == 1.0
