# Developer Productivity Simulator — Plan

A browser app that simulates the "incident → voice conversation → fix → PR → docs" loop
for a developer, with an ElevenLabs conversational agent as the co-pilot that talks the
developer through every step in real time.

## Goal

Demonstrate, end to end and hands-free, how much of an incident-response / bugfix cycle
can be handled by an agent while the developer stays in a voice conversation:

```
dummy app  ->  induced failure  ->  log collection  ->  root cause
            ->  voice explanation (ELI5 on demand)   ->  fix plan approval
            ->  patch + PR        ->  generated docs  ->  spoken summary
```

## The 8 steps (as requested) and how each is implemented

| # | Step | Implementation |
|---|------|----------------|
| 1 | Dummy Python app | `src/devprod/sample_app/` — a small order-pricing service (`FastAPI`) with real, reachable bugs (no feature flags — the bad input reaches genuine buggy code). Emits structured JSON logs. |
| 2 | Invoke app from the simulator | `src/devprod/simulator/runner.py` drives requests against the app in-process (re-importing it after a patch) and records status, latency and logs. |
| 3 | Instructions to induce an error | `src/devprod/simulator/faults.py` — a fault catalog (`divide_by_zero_discount`, `missing_currency_key`, `coupon_retry_storm`). The UI (or the voice agent, via a tool call) selects a fault; the runner replays a request that triggers it. |
| 4 | ElevenLabs agent gathers logs + finds root cause | `src/devprod/analysis/log_collector.py` tails the run's JSON log + stack traces; `analysis/rca.py` produces a `RootCause` (file, line, failing symbol, evidence, confidence). Exposed to the agent as the server tools `collect_logs` and `diagnose`. |
| 5 | Interactive voice call from the browser | `web/` opens a WebRTC/WebSocket session with the ElevenLabs Conversational AI agent using a short-lived signed URL minted by `POST /api/voice/session` (`voice/elevenlabs_client.py`). The agent has the incident context injected as dynamic variables. |
| 6 | Developer approves fix plan → fix + PR | `fix/planner.py` turns the root cause into a concrete `FixPlan` (diff preview, risk, tests). The agent asks for spoken approval; approval calls the `approve_fix` tool → `fix/patcher.py` applies the patch, runs tests, `fix/pr.py` pushes a branch and opens the PR. |
| 7 | PR link + quick documentation | `docgen/generator.py` writes an incident doc (timeline, root cause, fix, PR link, verification) into `documentation/incidents/`. |
| 8 | Summarize the documentation | `docgen/generator.py::summarize()` produces a 5-sentence summary that the agent reads aloud and the UI displays. |

## Continuous voice interaction

The ElevenLabs agent is present for the whole run, not just step 5:

- **Event narration** — every orchestrator state transition is pushed to the browser over
  `/ws/events`; the UI forwards it to the agent as contextual updates, so the agent
  narrates "I'm reproducing the failure now…", "I have the stack trace…".
- **Explain modes** — `voice/prompts.py` defines three personas the developer can switch
  to mid-call by simply asking:
  - `default` — concise senior engineer.
  - `eli5` — plain language, no jargon, analogies, one idea per sentence.
  - `researcher` — deeper: related code paths, references, trade-offs, what else could break.
  The agent calls the `set_explain_mode` tool and re-explains the current step in that register.
- **Comfort check** — after each major step the agent asks "does that make sense, or should
  I go simpler?" and only advances when the developer confirms (`confirm_understanding` tool).
- **Lost-developer shortcut** — `confirm_understanding(understood=false)` automatically flips
  the run into `eli5` and returns the re-explanation, so neither the agent nor the "I'm lost"
  button in the UI can leave the developer behind.

## Agent server tools (backend endpoints the ElevenLabs agent may call)

| Tool | Endpoint | Purpose |
|------|----------|---------|
| `start_run` | `POST /api/run/start` | Boot the dummy app and begin a scenario |
| `induce_error` | `POST /api/run/induce` | Trigger a named fault |
| `collect_logs` | `GET /api/run/logs` | Return the structured logs + traceback |
| `diagnose` | `POST /api/run/diagnose` | Return the root cause analysis |
| `get_fix_plan` | `GET /api/run/fix-plan` | Return the proposed fix with a diff preview |
| `approve_fix` | `POST /api/run/approve` | Apply patch, run tests, open PR |
| `get_docs` | `GET /api/run/docs` | Return the generated doc + summary |
| `set_explain_mode` | `POST /api/voice/mode` | Switch default / eli5 / researcher |
| `confirm_understanding` | `POST /api/voice/ack` | Record the comfort check |

All tools are also callable from the UI buttons, so the demo works with or without audio.

## Architecture

```
browser (web/)
  ├── timeline UI  ── WebSocket /ws/events ──┐
  └── ElevenLabs widget ── signed URL ───────┤
                                             ▼
                              FastAPI backend (src/devprod/server.py)
                                             │
                      ┌──────────────────────┼───────────────────────┐
                      ▼                      ▼                       ▼
              simulator/runner        analysis/rca            fix/planner+pr
                      │                                              │
                      ▼                                              ▼
              sample_app (dummy)                            docgen/generator
```

State lives in a single in-memory `RunState` (`orchestrator.py`) keyed by run id, with the
step machine: `idle → running → failing → collected → diagnosed → plan_ready → patched →
pr_open → documented → summarized`.

## Safety / demo guardrails

- The patcher only rewrites files under `src/devprod/sample_app/` and only applies
  planner-generated diffs.
- PR creation is skipped (dry-run, fake link) unless `DEVPROD_ENABLE_PR=1` and a git remote
  with credentials is present.
- No ElevenLabs key → the backend serves a `mock` voice mode: the same script is rendered as
  text and spoken with the browser's speech synthesis, so the flow is still demoable.

## Milestones

1. **Scaffold** (this change) — app, simulator, RCA, voice layer, fix/PR, docs, UI, skills.
2. **Wire a real ElevenLabs agent** — create the agent, paste the tool schema from
   `documentation/elevenlabs-agent-setup.md`, set `ELEVENLABS_API_KEY` / `ELEVENLABS_AGENT_ID`.
3. **Real PR path** — set `DEVPROD_ENABLE_PR=1` with `gh` authenticated against the repo.
4. **More scenarios** — add faults (N+1 query, latency spike, memory leak) following
   `.agents/skills/add-simulator-fault/SKILL.md`.
5. **Metrics** — time-to-diagnosis / time-to-PR per run, shown as the "productivity" score.
