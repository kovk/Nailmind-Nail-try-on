#!/usr/bin/env bash

ROOT=/root/autodl-tmp/nailmind
WATCHDOG="${ROOT}/runtime_watchdog.sh"
PID_FILE="${ROOT}/runtime-watchdog.pid"

mkdir -p "${ROOT}"

watchdog_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
if [[ -z "${watchdog_pid}" ]] || ! kill -0 "${watchdog_pid}" 2>/dev/null; then
  nohup "${WATCHDOG}" >"${ROOT}/startup.log" 2>&1 &
fi
