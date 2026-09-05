"""Command-line entry point for batch use outside Streamlit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from .detector import detect_braille
from .models import OCRConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a Braille image into English text")
    parser.add_argument("image", type=Path, help="PNG, JPEG, TIFF, or WebP image")
    parser.add_argument("--grade", choices=["Grade 1", "Grade 2"], default="Grade 1")
    parser.add_argument("--adaptive", action="store_true", help="Use adaptive thresholding")
    parser.add_argument("--invert", action="store_true", help="Treat light pixels as foreground")
    parser.add_argument("--json", action="store_true", help="Print text and diagnostics as JSON")
    args = parser.parse_args()

    result = detect_braille(
        Image.open(args.image),
        OCRConfig(
            threshold_mode="adaptive" if args.adaptive else "otsu",
            invert=args.invert,
        ),
        grade=args.grade,
    )
    if args.json:
        print(json.dumps({"text": result.text, "confidence": result.confidence, "diagnostics": result.diagnostics}))
    else:
        print(result.text)


if __name__ == "__main__":
    main()

