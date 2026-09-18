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

## Headless smoke test (fastest verification)

```bash
python -m devprod.cli demo --fault divide_by_zero_discount
python -m pytest -q
```

Expect the timeline to reach `summarized`, a real PR url (fake `example.invalid` link when `DEVPROD_ENABLE_PR=0`)
and a doc under `documentation/incidents/`.

## Browser demo

```bash
uvicorn devprod.server:app --reload --port 8000
```

Then: *Start run* → pick a fault → *Induce error* → *Collect logs* → *Diagnose* →
*Start voice call* → *I follow* / *I'm lost* → *Approve fix & open PR*.

## Important

- The approve step **edits `src/devprod/sample_app/pricing.py`**. Revert before re-demoing
  the same fault: `git checkout -- src/devprod/sample_app/pricing.py`.
- Faults live in `src/devprod/simulator/faults.py`; each one needs a matching entry in
  `src/devprod/fix/planner.py::PLANS` keyed by the exception type, otherwise the run stops
  at `diagnosed` with "no canned fix".
- ElevenLabs server tools are called from their cloud — the backend must be publicly
  reachable (`cloudflared tunnel --url http://localhost:8000`).
