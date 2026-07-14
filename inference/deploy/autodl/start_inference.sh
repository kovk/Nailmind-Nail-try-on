#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/autodl-tmp/nailmind
APP_DIR="${ROOT}/inference"
PYTHON=/root/autodl-tmp/flux2-env/bin/python
PID_FILE="${APP_DIR}/inference.pid"
LOG_FILE="${APP_DIR}/logs/inference.log"

cd "${APP_DIR}"
mkdir -p logs outputs/style-assets

if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    kill "${old_pid}" || true
    for _ in {1..20}; do
      kill -0 "${old_pid}" 2>/dev/null || break
      sleep 0.5
    done
  fi
fi

export PYTHONUNBUFFERED=1
export HF_HOME=/root/autodl-tmp/huggingface
export HF_HUB_CACHE=/root/autodl-tmp/huggingface/hub
export HF_ENDPOINT=https://hf-mirror.com
export HF_HUB_DISABLE_XET=1

nohup "${PYTHON}" main.py >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"

set -a
source .env
set +a
for _ in {1..120}; do
  if curl -fsS -H "Authorization: Bearer ${INFERENCE_TOKEN}" \
    "http://127.0.0.1:${INFERENCE_PORT}/health" >/dev/null 2>&1; then
    echo "inference ready: pid=$(cat "${PID_FILE}") port=${INFERENCE_PORT}"
    exit 0
  fi
  if ! kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    tail -n 120 "${LOG_FILE}" || true
    exit 1
  fi
  sleep 1
done

echo "inference startup timed out" >&2
tail -n 120 "${LOG_FILE}" || true
exit 1
