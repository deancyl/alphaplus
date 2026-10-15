#!/usr/bin/env bash
# Start Alphaplus for internal development / integration testing on port 60100.
#
# Single-implementation principle (research-terminal): the backend also serves
# the built frontend at "/", so one process on 60100 gives both the API and the
# page. Run `cd frontend && npm run build` first if dist/ is missing or stale.
#
#   ./scripts/dev_60100.sh          # start (backend + built frontend on 60100)
#   ./scripts/dev_60100.sh --stop   # stop
#   ./scripts/dev_60100.sh --status # check
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-60100}"
LOG="/tmp/alphaplus_${PORT}.log"

stop() {
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  sleep 1
  echo "stopped anything on :${PORT}"
}

case "${1:-start}" in
  --stop|stop)
    stop
    exit 0
    ;;
  --status|status)
    if fuser "${PORT}/tcp" >/dev/null 2>&1; then
      echo "listening on :${PORT}"
      curl -s "http://127.0.0.1:${PORT}/api/health" || true
      echo
    else
      echo "nothing listening on :${PORT}"
      exit 1
    fi
    exit 0
    ;;
esac

stop

if [ ! -f "${ROOT}/frontend/dist/index.html" ]; then
  echo "frontend/dist missing - building..."
  (cd "${ROOT}/frontend" && npm run build)
fi

echo "starting backend+frontend on :${PORT} (log: ${LOG})"
cd "${ROOT}"
env -u http_proxy -u https_proxy -u all_proxy -u ALL_PROXY \
    -u HTTP_PROXY -u HTTPS_PROXY \
  nohup python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" \
  > "${LOG}" 2>&1 &
echo "pid $!"

# Wait for readiness (max ~30s).
for i in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    echo "ready: http://127.0.0.1:${PORT}/  (docs: /api/docs)"
    exit 0
  fi
  sleep 1
done
echo "WARN: not ready after 30s; check ${LOG}" >&2
exit 1
