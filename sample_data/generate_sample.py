"""Create a demo PNG for manual testing.

Run from the repository root:
    python sample_data/generate_sample.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from braille_ocr.render import render_braille


output = Path(__file__).with_name("braille_demo.png")
render_braille("Hello world\nBraille 123", scale=2).save(output)
print(f"Wrote {output}")
