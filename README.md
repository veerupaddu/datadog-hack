# Developer Productivity Simulator

Break a service on purpose, let an ElevenLabs voice agent gather the logs, find the root
cause, explain it out loud (in ELI5 or researcher depth, on request), get spoken approval,
ship the fix as a PR and read back the generated documentation.

Full plan: [`documentation/PLAN.md`](documentation/PLAN.md) ·
Agent setup: [`documentation/elevenlabs-agent-setup.md`](documentation/elevenlabs-agent-setup.md) ·
Demo script: [`documentation/runbook.md`](documentation/runbook.md)

## Quick start

```bash
git clone https://github.com/veerupaddu/datadog-hack.git
cd datadog-hack
./init.sh                     # venv + deps + .env, then serves http://localhost:8000
```

`init.sh` also takes `--setup` (install, lint and test only) and `--demo` (headless run of
all eight steps), and honours `PORT=9000 ./init.sh`. Add `ELEVENLABS_API_KEY` and
`ELEVENLABS_AGENT_ID` to the generated `.env` for live voice.

Manual equivalent:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn devprod.server:app --port 8000
python -m devprod.cli demo --fault divide_by_zero_discount   # headless
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
