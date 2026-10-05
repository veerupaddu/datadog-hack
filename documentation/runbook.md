# Runbook — demoing the simulator

## Install

```bash
./init.sh --setup   # venv + deps + .env + lint + tests
```

Or manually:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run

```bash
./init.sh           # or: uvicorn devprod.server:app --port 8000
# open http://localhost:8000
```

Run without `--reload` when demoing: approving a fix edits `src/devprod/sample_app/`,
and the reloader would restart the process and drop the in-memory runs mid-flow.

## Demo script (≈4 minutes)

1. **Start run** — click *Start run* (or say "start the run"). The dummy order service boots
   and a healthy request succeeds.
2. **Induce the error** — pick `divide_by_zero_discount` and click *Induce error*. The
   service 500s; the timeline shows the failing request.
3. **Collect logs** — *Run log collector agent*. The collected logs card lists the entries
   with error lines in red.
4. **Start voice call** — the logs are sent to the researcher agent as its `topic`.
5. **Diagnose in the call** — the agent calls `diagnose` (or click *Ask agent to diagnose*);
   the diagnosis card fills in with file, line, evidence and confidence.
6. **Fix point** — highlighted in amber (`file:line`) with the added lines of the diff in green.
7. **Approve** — say "yes, go ahead". The patch is applied, tests run, PR link appears.
8. **PR & docs** — the PR link and `documentation/incidents/<run_id>.md` summary appear.
9. **Feedback** — *I follow* / *I'm lost*; lost re-explains with a concrete example.

## CLI (no browser)

```bash
python -m devprod.cli demo --fault divide_by_zero_discount
```

Runs all 8 steps headless and prints the PR link + doc summary. Useful for CI smoke tests.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Voice button says "mock mode" | `ELEVENLABS_API_KEY` / `ELEVENLABS_AGENT_ID` not set |
| Agent tools 404 | Tunnel URL stale — re-run `cloudflared` and update the tool base URL |
| PR step returns a fake `example.invalid` link | `DEVPROD_ENABLE_PR=0` in `.env` (server reads it at startup) |
| PR step shows a compare link instead of a PR | `gh` CLI missing or not logged in — run `gh auth login` |
| Patch step fails | `git status` in the repo is dirty on `src/devprod/sample_app/` |
| Re-running the same fault does nothing | The previous approval already fixed it — `git checkout -- src/devprod/sample_app/pricing.py` |
| Nothing is spoken in mock mode | The browser has no speech-synthesis voices installed; the transcript still shows every line |
