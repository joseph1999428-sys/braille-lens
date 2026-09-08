"""Small ctypes adapter to the official Liblouis C ABI (no PyPI namesakes)."""

from __future__ import annotations

import ctypes as ct
from ctypes.util import find_library
from functools import lru_cache
import os
from pathlib import Path
from threading import RLock


class LouisUnavailable(RuntimeError):
    pass


# Liblouis caches compiled tables globally and is not thread safe.
_LOCK = RLock()
TABLES = {"Grade 1": "en-ueb-g1.ctb", "Grade 2": "en-ueb-g2.ctb"}
RUNTIME = Path(__file__).resolve().parents[1] / ".runtime" / "liblouis"


class LouisEngine:
    def __init__(self) -> None:
        requested = os.environ.get("BRAILLE_LIBLOUIS_LIBRARY")
        library = requested or (
            str(RUNTIME / "bin" / "liblouis.dll") if os.name == "nt"
            else find_library("louis")
        )
        if not library:
            raise LouisUnavailable("Liblouis is not installed. See README.md for runtime setup.")
        try:
            self.lib = ct.CDLL(library)
        except OSError as error:
            raise LouisUnavailable("Liblouis could not be loaded. Run the runtime setup in README.md.") from error
        self.lib.lou_version.restype = ct.c_char_p
        self.lib.lou_charSize.restype = ct.c_int
        size = self.lib.lou_charSize()
        if size not in (2, 4):
            raise LouisUnavailable(f"Unsupported Liblouis character width: {size}")
        self.widechar = ct.c_uint16 if size == 2 else ct.c_uint32
        self.version = self.lib.lou_version().decode("ascii")
        wideptr, intptr = ct.POINTER(self.widechar), ct.POINTER(ct.c_int)
        self.lib.lou_backTranslate.argtypes = [
            ct.c_char_p, wideptr, intptr, wideptr, intptr,
            ct.c_void_p, ct.c_void_p, intptr, intptr, intptr, ct.c_int,
        ]
        self.lib.lou_backTranslate.restype = ct.c_int
        self.lib.lou_translateString.argtypes = [
            ct.c_char_p, wideptr, intptr, wideptr, intptr, ct.c_void_p, ct.c_void_p, ct.c_int,
        ]
        self.lib.lou_translateString.restype = ct.c_int
        self.lib.lou_checkTable.argtypes = [ct.c_char_p]
        self.lib.lou_checkTable.restype = ct.c_int
        table_root = os.environ.get("BRAILLE_LIBLOUIS_TABLES")
        if not table_root and os.name == "nt":
            table_root = str(RUNTIME / "share" / "liblouis" / "tables")
        self.tables = {
            grade: str(Path(table_root) / name).encode("utf-8") if table_root else name.encode("ascii")
            for grade, name in TABLES.items()
        }
        with _LOCK:
            for table in self.tables.values():
                if not self.lib.lou_checkTable(table):
                    raise LouisUnavailable("Liblouis UEB tables are missing or incompatible with the library.")

    def back_translate(self, masks: list[int], grade: str) -> tuple[str, list[int]]:
        """Return text and the source cell index for each output character."""
        if grade not in TABLES:
            raise ValueError("Expected Grade 1 or Grade 2")
        if any(not isinstance(mask, int) or not 0 <= mask <= 63 for mask in masks):
            raise ValueError("Expected six-dot masks in range 0..63")
        if len(masks) > 20000:
            raise ValueError("Too many Braille cells in one translation")
        if not masks:
            return "", []
        # dotsIO uses Liblouis's dot marker (0x8000), not Unicode code points.
        source = (self.widechar * len(masks))(*(0x8000 | mask for mask in masks))
        capacity = max(256, len(masks) * 32 + 64)
        target = (self.widechar * capacity)()
        input_positions = (ct.c_int * capacity)()
        in_len, out_len = ct.c_int(len(masks)), ct.c_int(capacity)
        with _LOCK:
            ok = self.lib.lou_backTranslate(
                self.tables[grade], source, ct.byref(in_len), target, ct.byref(out_len),
                None, None, None, input_positions, None, 4,
            )
        if not ok or in_len.value != len(masks) or out_len.value >= capacity:
            raise LouisUnavailable("Liblouis did not complete the translation; no partial result was accepted.")
        return "".join(chr(c) for c in target[:out_len.value]), list(input_positions[:out_len.value])

    def forward(self, text: str, grade: str = "Grade 1") -> list[int]:
        """Generate standards-based Braille for fixtures and the demo."""
        if grade not in TABLES or len(text) > 20000 or any(ord(c) > 0xFFFF for c in text):
            raise ValueError("Unsupported fixture text or grade")
        source = (self.widechar * len(text))(*(ord(c) for c in text))
        capacity = max(256, len(text) * 32 + 64)
        target = (self.widechar * capacity)()
        in_len, out_len = ct.c_int(len(text)), ct.c_int(capacity)
        with _LOCK:
            ok = self.lib.lou_translateString(
                self.tables[grade], source, ct.byref(in_len), target, ct.byref(out_len), None, None, 4,
            )
        if not ok or in_len.value != len(text):
            raise LouisUnavailable("Liblouis could not generate the fixture")
        masks = [c & 0xFF for c in target[:out_len.value]]
        if any(mask > 63 for mask in masks):
            raise ValueError("Fixture needs more than six dots")
        return masks


@lru_cache(maxsize=1)
def get_engine() -> LouisEngine:
    return LouisEngine()
