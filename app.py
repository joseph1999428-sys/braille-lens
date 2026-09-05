"""Simple Streamlit application for translating a Braille picture."""

from __future__ import annotations

import hashlib
from io import BytesIO

import streamlit as st
from PIL import Image

from braille_ocr import OCRConfig, detect_braille
from braille_ocr.render import render_braille


Image.MAX_IMAGE_PIXELS = 25_000_000

st.set_page_config(page_title="Braille Lens", page_icon="⠃", layout="centered")

st.markdown(
    """
    <style>
    .stApp { background: #f6f8fc; }
    .block-container { max-width: 860px; padding-top: 2.5rem; }
    .intro { margin-bottom: 1.5rem; }
    .intro h1 { color: #172033; margin-bottom: .3rem; letter-spacing: -.03em; }
    .intro p { color: #667085; font-size: 1.05rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="intro"><h1>Braille Lens</h1>'
    '<p>Upload a picture of Braille and translate it into English. Images are processed in your session and are not saved.</p></div>',
    unsafe_allow_html=True,
)

picture = st.file_uploader(
    "Choose a Braille picture",
    type=("png", "jpg", "jpeg", "webp", "tif", "tiff"),
    help="Use a sharp, level image with even lighting. PNG and TIFF scans usually work best.",
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

demo_left, demo_right = st.columns([1, 2])
with demo_left:
    use_demo = st.button("Use demo picture", use_container_width=True)
with demo_right:
    if picture is not None:
        st.caption(f"{picture.name} · {picture.size / 1024:.0f} KB")
    else:
        st.caption("No picture selected")

source: Image.Image | None = None
if use_demo:
    st.session_state["demo_image"] = render_braille("Hello world\nBraille 123", scale=2)
if picture is not None:
    try:
        picture_bytes = picture.getvalue()
        if len(picture_bytes) > MAX_UPLOAD_BYTES:
            st.error("This picture is larger than 10 MB. Please resize it and try again.")
        else:
            source = Image.open(BytesIO(picture_bytes)).convert("RGB")
            source.load()
    except Exception as error:  # pragma: no cover - UI-only error path
        st.error(f"Could not open that picture: {error}")
elif st.session_state.get("demo_image") is not None:
    source = st.session_state["demo_image"]

if source is not None:
    st.image(source, caption="Picture to translate", use_container_width=True)

    with st.expander("Image options", expanded=False):
        threshold = st.radio(
            "Lighting",
            ("Automatic", "Uneven lighting", "Very faint dots"),
            horizontal=True,
            help="Use Uneven lighting when the picture has shadows or a bright gradient.",
        )
        invert = st.checkbox("Light dots on a dark background", value=False)
        grade = st.selectbox("English Braille", ("Grade 1", "Grade 2"))

    translate = st.button("Translate to English", type="primary", use_container_width=True)
    if translate:
        config = OCRConfig(
            threshold_mode=(
                "local_contrast" if threshold == "Very faint dots"
                else "adaptive" if threshold == "Uneven lighting" else "otsu"
            ),
            invert=invert,
        )
        with st.spinner("Reading the Braille picture…"):
            try:
                result = detect_braille(source, config=config, grade=grade)
            except Exception as error:  # pragma: no cover - UI-only error path
                st.error(f"Could not translate this picture: {error}")
                result = None
        if result is None:
            st.stop()
        st.session_state["last_result"] = result
        source_id = hashlib.sha256(picture_bytes).hexdigest() if picture is not None else "demo"
        st.session_state["result_source"] = source_id

current_source = (
    hashlib.sha256(picture_bytes).hexdigest()
    if picture is not None and "picture_bytes" in locals()
    else "demo" if source is not None and st.session_state.get("demo_image") is not None else None
)
result = st.session_state.get("last_result")
if result is not None and st.session_state.get("result_source") != current_source:
    result = None
if result is not None:
    st.divider()
    st.subheader("English translation")
    if result.text:
        if result.warnings:
            for warning in result.warnings:
                st.warning(warning)
        if result.confidence < 0.65:
            st.warning("Overall confidence is low. Retake the picture with the page flat, in focus, and evenly lit.")
        if "□" in result.text:
            st.info("Squares mark cells that could not be read confidently. Review the image and edit the transcription before downloading.")
        edited_text = st.text_area(
            "You can edit the translation before downloading it.",
            value=result.text,
            height=150,
            key="translated_text",
        )
        st.download_button(
            "Download .txt",
            data=edited_text,
            file_name="braille-translation.txt",
            mime="text/plain",
            use_container_width=True,
        )
    else:
        st.warning(result.diagnostics.get("message", "No Braille text was found."))
        st.caption("Try a sharper picture, Automatic lighting, or Uneven lighting for shadows.")

    with st.expander("Recognition details", expanded=False):
        st.write(f"Confidence: **{result.confidence:.0%}**")
        st.caption("The confidence score measures dot geometry and Braille table coverage; it is not a language correction score.")
        st.json(result.diagnostics)
        if result.annotated is not None:
            st.image(result.annotated, caption="OpenCV detection preview", use_container_width=True)
else:
    st.info("Choose a picture above, then press Translate to English.")
