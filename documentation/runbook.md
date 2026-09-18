# Runbook — demoing the simulator

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Run

```bash
uvicorn devprod.server:app --port 8000
# open http://localhost:8000
```

Run without `--reload` when demoing: approving a fix edits `src/devprod/sample_app/`,
and the reloader would restart the process and drop the in-memory runs mid-flow.

## Demo script (≈4 minutes)

1. **Start run** — click *Start run* (or say "start the run"). The dummy order service boots
   and a healthy request succeeds.
2. **Induce the error** — pick `divide_by_zero_discount` and click *Induce error*. The
   service 500s; the timeline shows the failing request.
3. **Collect + diagnose** — *Collect logs* then *Diagnose*. The root cause card shows file,
   line, failing expression, evidence and confidence.
4. **Talk it through** — click *Start voice call*. Ask: "explain that like I'm five" →
   the agent switches to ELI5. Ask: "what else could break?" → researcher mode.
5. **Approve** — say "yes, go ahead". The patch is applied, tests run, PR link appears.
6. **Docs** — the incident doc is written to `documentation/incidents/<run_id>.md`; the
   agent reads out the summary.

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
| PR step returns a fake link | `DEVPROD_ENABLE_PR` not `1`, or no git remote configured |
| Patch step fails | `git status` in the repo is dirty on `src/devprod/sample_app/` |
| Re-running the same fault does nothing | The previous approval already fixed it — `git checkout -- src/devprod/sample_app/pricing.py` |
| Nothing is spoken in mock mode | The browser has no speech-synthesis voices installed; the transcript still shows every line |
