# Publish Braille Lens as a shareable webpage

The easiest public deployment is Streamlit Community Cloud. It gives you one HTTPS URL that other people can open, upload a picture, and translate in their own browser session.

## Streamlit Community Cloud

1. Create a GitHub repository and upload this project. Include `app.py`, `braille_ocr/`, `requirements.txt`, `pyproject.toml`, `.streamlit/config.toml`, and `sample_data/`. Do not upload private images such as `t1.jpg`.
2. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Select **Create app**, choose the repository and branch, and set the main file to `app.py`.
4. Deploy. Streamlit will install `requirements.txt` and provide a URL such as `https://your-app-name.streamlit.app`.
5. Share that URL. Each visitor gets an isolated Streamlit session and can upload their own image.

The app caps uploads at 10 MB, limits decoded images to 25 million pixels, and does not write uploaded pictures to disk. The current implementation processes images in the server session, so avoid putting sensitive images into a public deployment unless your hosting and privacy policy support that use.

For a quick first release, the repository can be public because the app contains no API keys or external service credentials. Keep private test pictures out of GitHub; the `.gitignore` already excludes `t1.jpg` and generated `t1_*.png` files.

## Docker deployment

For a VPS, Render, Railway, Fly.io, or another container host:

```powershell
docker build -t braille-lens .
docker run --rm -p 8501:8501 braille-lens
```

Open `http://localhost:8501`. Configure the host to expose port `8501`; it will provide the public HTTPS link.

## Updating the public app

Push changes to the selected GitHub branch. Streamlit Community Cloud redeploys the app automatically. The deployment entry point is [app.py](app.py), and the public upload limit is configured in [.streamlit/config.toml](.streamlit/config.toml).
