#!/usr/bin/env bash
# One-shot local setup + run for the developer productivity simulator.
#
#   ./init.sh            set up and start the server on http://localhost:8000
#   ./init.sh --setup    set up only (venv, deps, .env)
#   ./init.sh --demo     set up, then run the headless demo instead of the server
#   PORT=9000 ./init.sh  serve on a different port
#
# Anything already listening on PORT is killed first, and the dummy service's
# structured logs (var/logs/*.jsonl) are streamed next to the server output.
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"
VENV=".venv"
MODE="${1:-serve}"
LOG_DIR="var/logs"

free_port() {
  local pids
  pids="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  [ -n "$pids" ] || return 0
  echo "Port $PORT already in use by PID(s): $(echo "$pids" | tr '\n' ' ')- stopping them."
  kill $pids 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 0.3
    pids="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)"
    [ -n "$pids" ] || return 0
  done
  kill -9 $pids 2>/dev/null || true
  sleep 0.5
}

# Follow every per-run JSONL log, including files created after the server starts.
tail_app_logs() {
  mkdir -p "$LOG_DIR"
  (
    # Older runs are already on disk; only stream logs written from now on.
    seen="$(ls "$LOG_DIR"/*.jsonl 2>/dev/null | tr '\n' ' ')"
    while true; do
      for f in "$LOG_DIR"/*.jsonl; do
        [ -e "$f" ] || continue
        case " $seen " in *" $f "*) continue ;; esac
        seen="$seen $f"
        # The file is new, so replay it from the top before following: a run
        # can write its whole log before this tail attaches.
        tail -n +1 -f "$f" | awk '{ print "[app] " $0; fflush() }' &
      done
      sleep 1
    done
  ) &
  TAIL_PID=$!
  trap 'pkill -P "$TAIL_PID" 2>/dev/null || true; kill "$TAIL_PID" 2>/dev/null || true' EXIT
}

command -v "$PYTHON" >/dev/null || { echo "python3 not found"; exit 1; }
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "python 3.10+ required, found $("$PYTHON" --version)"; exit 1; }

[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e ".[dev]"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — add ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID for live voice."
fi

# Undo any fix a previous demo run applied to the intentionally buggy sample app.
git checkout -- src/devprod/sample_app/pricing.py 2>/dev/null || true

case "$MODE" in
  --setup)
    "$VENV/bin/ruff" check .
    "$VENV/bin/python" -m pytest -q
    echo "Ready. Start the app with: ./init.sh"
    ;;
  --demo)
    "$VENV/bin/python" -m devprod.cli demo --fault divide_by_zero_discount
    git checkout -- src/devprod/sample_app/pricing.py
    ;;
  *)
    free_port
    tail_app_logs
    echo "Open http://localhost:$PORT   (service logs are streamed below, prefixed [app])"
    # No --reload: approving a fix rewrites src/devprod/sample_app/, and the
    # reloader would restart the process and drop in-memory runs mid-flow.
    # Graceful-shutdown timeout so Ctrl+C isn't held up by open /ws/events sockets.
    "$VENV/bin/uvicorn" devprod.server:app --host 127.0.0.1 --port "$PORT" \
      --log-level info --timeout-graceful-shutdown 3
    ;;
esac
