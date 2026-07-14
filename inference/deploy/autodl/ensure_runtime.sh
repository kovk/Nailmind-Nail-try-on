#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/autodl-tmp/nailmind
set -a
source "${ROOT}/inference/.env"
set +a

if ! curl -fsS -H "Authorization: Bearer ${INFERENCE_TOKEN}" \
  "http://127.0.0.1:${INFERENCE_PORT}/health" >/dev/null 2>&1; then
  "${ROOT}/start_inference.sh" >"${ROOT}/ensure-inference.log" 2>&1 || true
fi

if ! pgrep -af "ssh .*172.17.0.1:16006:127.0.0.1:${INFERENCE_PORT}" >/dev/null 2>&1; then
  "${ROOT}/start_tunnel.sh" >"${ROOT}/ensure-tunnel.log" 2>&1 || true
fi
