---
name: run-devprod-demo
description: Run the developer productivity simulator end to end (start service, induce a fault, diagnose, approve, PR, docs), in the browser or headless. Use when demoing or smoke-testing this repo.
---

# Run the DevProd demo

## Setup (once per machine)

```bash
cd <repo> && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Reuse an existing editable `.venv` when present. Confirm `settings.voice_mode` and
`settings.enable_pr` before a local demo; use mock voice and dry-run PRs unless
live external actions are explicitly requested.

## Headless smoke test (fastest verification)

```bash
python -m devprod.cli demo --fault divide_by_zero_discount
python -m pytest -q
```

Expect the timeline to reach `summarized`, a PR url (dry-run unless `DEVPROD_ENABLE_PR=1`)
and a doc under `documentation/incidents/`.

## Browser demo

```bash
uvicorn devprod.server:app --port 8000
```

Prefer no `--reload` for full-loop testing: approval edits Python source, while run
state is in memory. Development auto-reload can interfere with observing a run.

Then: *Start run* → pick a fault → *Induce error* → *Collect logs* → *Diagnose* →
*Start voice call* → ELI5 / Researcher buttons → *Approve fix & open PR*.

- Each fault should first return 500. Expected replay statuses: discount 200,
  unsupported currency 422, flaky coupon 200.
- Coupon induction takes approximately 10 seconds to exhaust recursive retries;
  wait for its failing event before collecting logs.
- Capture the new run id after every Start. If stale events overwrite selection,
  record the failure, then reload and start again to isolate the next fault.
- Read generated JSONL files under `var/logs/` and incident docs under
  `documentation/incidents/` as supporting evidence, not a substitute for UI checks.
- Mock speech still requires browser TTS voices. Check `speechSynthesis.getVoices()`
  and speech error events when audio is absent; text transcripts alone do not
  demonstrate audible narration.

## Important

- The approve step **edits `src/devprod/sample_app/pricing.py`**. Revert between fault
  loops and at cleanup: `git checkout -- src/devprod/sample_app/pricing.py`.
  Check the initial working tree before reverting so unrelated user edits are preserved.
- Faults live in `src/devprod/simulator/faults.py`; each one needs a matching entry in
  `src/devprod/fix/planner.py::PLANS` keyed by the exception type, otherwise the run stops
  at `diagnosed` with "no canned fix".
- ElevenLabs server tools are called from their cloud — the backend must be publicly
  reachable (`cloudflared tunnel --url http://localhost:8000`).

## Devin Secrets Needed

None for the local mock-voice/dry-run demo. Real voice requires
`ELEVENLABS_API_KEY` and `ELEVENLABS_AGENT_ID`, and is a separate test scope.
