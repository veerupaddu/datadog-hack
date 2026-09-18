---
name: elevenlabs-voice-agent
description: Configure or debug the ElevenLabs conversational agent that narrates the simulator (server tools, dynamic variables, signed URLs, ELI5/researcher modes). Use when wiring voice into this repo.
---

# ElevenLabs agent for the simulator

## Where things live

| Concern | File |
|---------|------|
| System prompt + mode guidance | `src/devprod/voice/prompts.py` |
| Server tool schemas | `src/devprod/voice/agent_tools.py` |
| Signed URL / session minting | `src/devprod/voice/elevenlabs_client.py` |
| Browser call start | `web/app.js::startCall` |
| Backend endpoints the agent calls | `src/devprod/server.py` |

## Wire it up

```bash
python -m devprod.voice.agent_tools --print-schema --base-url https://<tunnel>
```

Paste each entry as a webhook tool on the agent, set `ELEVENLABS_API_KEY` and
`ELEVENLABS_AGENT_ID` in `.env`, restart the backend. Full walkthrough:
`documentation/elevenlabs-agent-setup.md`.

## Rules that must survive any edit

- The agent never invents logs, line numbers, diffs or PR links — every fact comes from a
  tool result.
- `approve_fix` requires an explicit spoken yes.
- After each explanation: comfort check → `confirm_understanding`. A `false` answer
  automatically flips the run to `eli5` (`Orchestrator.acknowledge`).
- Three registers only: `default`, `eli5`, `researcher` (`prompts.EXPLAIN_MODES`).

## Debugging

| Symptom | Check |
|---------|-------|
| `voice: mock` badge | keys missing, or the signed-URL call failed — see the `reason` field in `POST /api/voice/session` |
| Tools time out | ElevenLabs calls from its cloud; the tunnel URL must be live and the base URL updated |
| Agent narrates stale state | the browser pushes context from `/ws/events`; confirm the socket is open |
