#!/usr/bin/env bash
# One-shot local setup + run for the developer productivity simulator.
#
#   ./init.sh            set up and start the server on http://localhost:8000
#   ./init.sh --setup    set up only (venv, deps, .env)
#   ./init.sh --demo     set up, then run the headless demo instead of the server
#   PORT=9000 ./init.sh  serve on a different port
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8000}"
PYTHON="${PYTHON:-python3}"
VENV=".venv"
MODE="${1:-serve}"

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
    echo "Open http://localhost:$PORT"
    # No --reload: approving a fix rewrites src/devprod/sample_app/, and the
    # reloader would restart the process and drop in-memory runs mid-flow.
    exec "$VENV/bin/uvicorn" devprod.server:app --host 127.0.0.1 --port "$PORT"
    ;;
esac
