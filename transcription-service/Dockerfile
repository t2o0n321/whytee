FROM python:3.11-slim

# ffmpeg is required by yt-dlp audio extraction and the chunk splitter.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000
ENV TRANSCRIBER_WORK_DIR=/tmp/transcriber

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
