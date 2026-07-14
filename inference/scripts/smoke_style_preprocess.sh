#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/autodl-tmp/nailmind/inference}"
IMAGE_PATH="${1:-${APP_DIR}/samples/style_01_enhanced.png}"
OUTPUT_PATH="${2:-/root/autodl-tmp/style-preprocess-smoke.json}"

cd "${APP_DIR}"
set -a
source .env
set +a

http_status="$(curl -sS \
  -H "Authorization: Bearer ${INFERENCE_TOKEN}" \
  -F "style_image=@${IMAGE_PATH}" \
  "http://127.0.0.1:${INFERENCE_PORT}/v1/styles/extract-nails" \
  -o "${OUTPUT_PATH}" \
  -w '%{http_code}')"

if [[ "${http_status}" != "200" ]]; then
  cat "${OUTPUT_PATH}" >&2
  printf '\nstyle preprocessing failed with HTTP %s\n' "${http_status}" >&2
  exit 1
fi

"${PYTHON:-/root/autodl-tmp/flux2-env/bin/python}" - "${OUTPUT_PATH}" <<'PY'
from __future__ import annotations

import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
meta = payload.get("meta") or {}
summary = {
    "asset_id": payload.get("asset_id"),
    "status": payload.get("status"),
    "quality_score": payload.get("quality_score"),
    "segmentation_mode": meta.get("segmentation_mode"),
    "yolo_candidate_count": meta.get("yolo_candidate_count"),
    "sam3_candidate_count": meta.get("sam3_candidate_count"),
    "sam3_refined_count": meta.get("sam3_refined_count"),
    "source_nail_count": meta.get("source_nail_count"),
    "segmentation_warning": meta.get("segmentation_warning"),
    "asset_dir": payload.get("asset_dir"),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
