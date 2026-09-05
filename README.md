# Braille Lens

Braille Lens is a local Streamlit app that reads a high-quality image of six-dot Braille and converts it into editable English text. The recognition path is deliberately inspectable:

1. OpenCV converts the image to grayscale, denoises it, and applies Otsu, adaptive, or local-contrast thresholding. Faint full-page pictures automatically retry with adaptive thresholding.
2. OpenCV connected components find dot-sized blobs and their centroids.
3. Dot centers are clustered into rows and six-dot cells, including visible word gaps.
4. A small English Braille table handles Grade 1 letters, capitals, numbers, punctuation, and a few unambiguous Grade 2 whole-word contractions.

The project does not upload images to a third-party service. It handles clean scans and faint, full-page photographs, while camera perspective, glare, touching dots, and heavily embossed shadows may need deskewing or a learned detector in a later iteration.

## Run it

From PowerShell:

```powershell
Set-Location D:\braille_app
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL shown by Streamlit. Use **Use demo picture** to verify the installation before uploading a scan.

To give other people a public link, follow [DEPLOY.md](DEPLOY.md). Streamlit Community Cloud is the quickest option: connect the GitHub repository, select `app.py`, and share the generated `streamlit.app` URL.

Run the unit tests with:

```powershell
python -m pytest
```

For batch use, the same detector is available without Streamlit:

```powershell
python -m braille_ocr.cli sample_data\braille_demo.png --json
```

## Image guidance

PNG or TIFF scans preserve dot boundaries best. Aim for dots at least 8 pixels across, even lighting, and a page that is close to horizontal. If the background is uneven, choose **Uneven lighting**. For light dots on a dark background, enable that option in **Image options**. Recognition details include the OpenCV detection preview and confidence diagnostics.

## Layout

```text
app.py                    Streamlit interface
braille_ocr/
  alphabet.py             Unified English Braille masks and symbols
  detector.py             OpenCV preprocessing, geometry, and diagnostics
  models.py               OCRConfig, Dot, Cell, and OCRResult data models
  render.py               High-resolution demo/fixture image generator
  translator.py          Stateful English translation (capitals and numbers)
tests/                    Translation and image-pipeline regression tests
```

The letter and punctuation masks follow the six-dot numbering used by Unicode Braille Patterns and Unified English Braille. For broader Grade 2 coverage, the translator can later be backed by the open-source [Liblouis](https://github.com/liblouis/liblouis) tables without changing the OpenCV detector interface.
