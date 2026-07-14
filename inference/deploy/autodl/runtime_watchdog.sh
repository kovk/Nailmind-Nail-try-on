#!/usr/bin/env bash
set -u

ROOT=/root/autodl-tmp/nailmind
LOG_FILE="${ROOT}/runtime-watchdog.log"
PID_FILE="${ROOT}/runtime-watchdog.pid"

mkdir -p "${ROOT}"
echo $$ >"${PID_FILE}"
trap 'rm -f "${PID_FILE}"' EXIT

while true; do
  "${ROOT}/ensure_runtime.sh" >>"${LOG_FILE}" 2>&1 || true
  sleep 30
done
