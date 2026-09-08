FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLEXSRFPROTECTION=true

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends liblouis20 liblouis-data \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py README.md pyproject.toml ./
COPY braille_ocr ./braille_ocr
COPY packages.txt ./
COPY sample_data ./sample_data

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
