FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY worker/requirements.txt /app/requirements.txt
RUN sh -c 'for attempt in 1 2 3; do pip install --no-cache-dir --default-timeout=180 --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1 && exit 0; echo "torch install failed on attempt ${attempt}, retrying..."; sleep 5; done; exit 1'
RUN sh -c 'for attempt in 1 2 3; do pip install --no-cache-dir --default-timeout=180 Pillow==10.4.0 requests==2.32.3 numpy==2.1.1 mediapipe==0.10.14 opencv-python-headless==4.10.0.84 && exit 0; echo "base deps install failed on attempt ${attempt}, retrying..."; sleep 5; done; exit 1'
RUN sh -c 'for attempt in 1 2 3; do pip install --no-cache-dir --default-timeout=180 ultralytics==8.3.156 && exit 0; echo "ultralytics install failed on attempt ${attempt}, retrying..."; sleep 5; done; exit 1'
COPY worker/main.py /app/main.py

CMD ["python", "/app/main.py"]
