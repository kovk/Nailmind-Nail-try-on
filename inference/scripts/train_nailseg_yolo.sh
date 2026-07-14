#!/usr/bin/env bash
set -euo pipefail

DATASET_YAML="${1:-datasets/nail-yolo/data.yaml}"
MODEL="${MODEL:-yolo11n-seg.pt}"
EPOCHS="${EPOCHS:-80}"
IMGSZ="${IMGSZ:-768}"
BATCH="${BATCH:-16}"
DEVICE="${DEVICE:-0}"
PROJECT="${PROJECT:-runs/nailseg}"
NAME="${NAME:-yolo11n-seg-nail}"

YOLO_BIN="${YOLO_BIN:-yolo}"

"${YOLO_BIN}" \
  segment \
  train \
  model="${MODEL}" \
  data="${DATASET_YAML}" \
  epochs="${EPOCHS}" \
  imgsz="${IMGSZ}" \
  batch="${BATCH}" \
  device="${DEVICE}" \
  project="${PROJECT}" \
  name="${NAME}" \
  patience=20 \
  close_mosaic=10
