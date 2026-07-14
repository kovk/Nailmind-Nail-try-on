#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/autodl-tmp/nailmind
ENV_FILE="${ROOT}/inference/.env"
MODEL_LINK=/root/autodl-tmp/models/flux2-klein-4B
SNAPSHOT_ROOT=/root/autodl-tmp/huggingface/hub/models--black-forest-labs--FLUX.2-klein-4B/snapshots

snapshot="$(find "${SNAPSHOT_ROOT}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "${snapshot}" ]]; then
  echo "FLUX.2 Klein snapshot not found under ${SNAPSHOT_ROOT}" >&2
  exit 1
fi
mkdir -p "$(dirname "${MODEL_LINK}")"
ln -sfn "${snapshot}" "${MODEL_LINK}"

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >>"${ENV_FILE}"
  fi
}

set_env INFERENCE_HOST 0.0.0.0
set_env INFERENCE_PORT 6006
set_env INFERENCE_MOCK false
set_env EDITOR_BACKEND flux2_klein
set_env PRODUCTION_MODE true
set_env REQUIRE_STYLE_NAIL_ASSET true
set_env PRELOAD_MODEL_ON_STARTUP true
set_env DEVICE cuda
set_env TORCH_DTYPE bfloat16
set_env FLUX2_MODEL_DIR "${MODEL_LINK}"
set_env FLUX2_MODEL_ID black-forest-labs/FLUX.2-klein-4B
set_env FLUX2_STEPS 4
set_env FLUX2_GUIDANCE_SCALE 1.0
set_env FLUX2_SEED 42
set_env FLUX2_MAX_IMAGE_SIDE 2048
set_env PRESERVE_ORIGINAL_RESOLUTION true
set_env STYLE_ASSET_SEGMENTER sam3_text
set_env SAM3_CHECKPOINT_PATH /root/autodl-tmp/models/sam3/sam3.pt
set_env SAM3_PROMPT fingernail
set_env SAM3_MIN_SCORE 0.35
set_env SAM3_ALLOW_YOLO_FALLBACK false
set_env STYLE_ASSET_MASK_ERODE 1

echo "configured FLUX.2 Klein at ${MODEL_LINK}"
