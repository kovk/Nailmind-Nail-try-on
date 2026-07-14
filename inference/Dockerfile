FROM pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY requirements-gpu.txt /app/requirements-gpu.txt
RUN pip install --no-cache-dir -r /app/requirements-gpu.txt

COPY app /app/app
COPY main.py /app/main.py

ENV INFERENCE_HOST=0.0.0.0
ENV INFERENCE_PORT=8090
ENV INFERENCE_MOCK=false
ENV EDITOR_BACKEND=sdxl_inpaint

EXPOSE 8090

CMD ["python", "main.py"]
