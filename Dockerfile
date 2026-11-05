# Zero-setup image for the offline demo and the offline test suite (no GPU, no models, no API key).
#   docker build -t avs .
#   docker run --rm -v "$PWD/out:/out" avs --theme neon
FROM python:3.11-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-ci.txt .
RUN pip install --no-cache-dir -r requirements-ci.txt
COPY . .
ENV PYTHONUTF8=1
ENTRYPOINT ["python", "-X", "utf8", "pipeline/demo/run_demo.py", "--tts", "none", "--out", "/out"]
