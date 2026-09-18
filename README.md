# Developer Productivity Simulator

Break a service on purpose, let an ElevenLabs voice agent gather the logs, find the root
cause, explain it out loud (in ELI5 or researcher depth, on request), get spoken approval,
ship the fix as a PR and read back the generated documentation.

Full plan: [`documentation/PLAN.md`](documentation/PLAN.md) ·
Agent setup: [`documentation/elevenlabs-agent-setup.md`](documentation/elevenlabs-agent-setup.md) ·
Demo script: [`documentation/runbook.md`](documentation/runbook.md)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # optional: ElevenLabs keys
uvicorn devprod.server:app --reload --port 8000
# http://localhost:8000
```

Headless run of all eight steps:

```bash
python -m devprod.cli demo --fault divide_by_zero_discount
```

## Layout

```
src/devprod/
  sample_app/      dummy order-pricing service with real, reachable bugs
  simulator/       fault catalog + runner that drives requests and captures JSON logs
  analysis/        log collection and root cause analysis (3 explanation registers)
  voice/           ElevenLabs session minting, agent server-tool schemas, prompts
  fix/             fix planner, guarded patcher, PR creation
  docgen/          incident doc generation + spoken summary
  orchestrator.py  the 8 step state machine, emits live events
  server.py        FastAPI backend (UI + agent tools + /ws/events)
web/               browser UI: timeline, root cause, diff, voice call
.agents/skills/    reusable skills for running the demo and extending it
```

Without ElevenLabs credentials the app runs in **mock voice mode**: the same narration is
spoken with the browser's speech synthesis, so the whole flow is demoable offline.
