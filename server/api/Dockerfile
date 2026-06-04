FROM python:3.11-slim

ENV PIP_DEFAULT_TIMEOUT=180 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN sh -c 'for attempt in 1 2 3; do pip install --no-cache-dir --default-timeout=180 -r /app/requirements.txt && exit 0; echo "pip install failed on attempt ${attempt}, retrying..."; sleep 5; done; exit 1'
COPY app /app/app
COPY main.py /app/main.py
RUN mkdir -p /app/data

EXPOSE 8080
CMD ["python", "/app/main.py"]
