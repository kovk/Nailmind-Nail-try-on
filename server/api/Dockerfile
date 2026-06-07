FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    wget \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libgl1 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN sh -c 'for attempt in 1 2 3; do pip install --no-cache-dir --default-timeout=180 -r /app/requirements.txt && exit 0; echo "pip install failed on attempt ${attempt}, retrying..."; sleep 5; done; exit 1'
RUN python -m playwright install chromium
COPY app /app/app
COPY main.py /app/main.py
RUN mkdir -p /app/data

EXPOSE 8080
CMD ["python", "/app/main.py"]
