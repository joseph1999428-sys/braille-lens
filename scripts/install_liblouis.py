"""Install the official, checksum-pinned Windows x64 Liblouis release locally."""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
import platform
import shutil
import sys
from urllib.request import Request, urlopen
from zipfile import ZipFile

VERSION = "3.39.0"
SHA256 = "64d669ac30f1411e0023b1cecc81c7a7b5374678ee41302c95ac8c7c8fbc6591"
URL = f"https://github.com/liblouis/liblouis/releases/download/v{VERSION}/liblouis-{VERSION}-win64.zip"
API_URL = "https://api.github.com/repos/liblouis/liblouis/releases/assets/539786293"
ROOT = Path(__file__).resolve().parents[1]


def install() -> None:
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit("This installer requires Windows x64. On Debian/Ubuntu install liblouis20 and liblouis-data.")
    data = None
    for url in (URL, API_URL):
        try:
            with urlopen(Request(url, headers={"Accept": "application/octet-stream"}), timeout=30) as response:
                candidate = response.read(12_000_000)
            if hashlib.sha256(candidate).hexdigest() != SHA256:
                raise ValueError("Liblouis download checksum mismatch")
            data = candidate
            break
        except (OSError, ValueError) as error:
            print(f"Download failed: {error}")
    if data is None:
        raise SystemExit("Could not download the verified Liblouis release. No runtime was changed.")
    destination = ROOT / ".runtime" / "liblouis"
    with ZipFile(BytesIO(data)) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Unsafe path in Liblouis archive")
        archive.extractall(destination)
    (destination / "provenance.json").write_text(json.dumps({
        "version": VERSION, "url": URL, "sha256": SHA256,
        "source": f"https://github.com/liblouis/liblouis/tree/v{VERSION}",
        "license": "LGPL-2.1-or-later (library and tables)",
    }, indent=2), encoding="utf-8")
    sys.path.insert(0, str(ROOT))
    from braille_ocr.louis_engine import get_engine
    engine = get_engine()
    assert engine.back_translate([32, 46], "Grade 2")[0] == "The"
    print(f"Liblouis {engine.version} installed and UEB back-translation verified.")


if __name__ == "__main__":
    install()
