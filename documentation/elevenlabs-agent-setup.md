# ElevenLabs Conversational AI — agent setup

## 1. Create the agent

ElevenLabs dashboard → Conversational AI → Agents → New agent.

- **Name**: DevProd Copilot
- **First message**:
  "Hi, I'm your incident copilot. I'll run the service, break it on purpose, then walk you
  through what happened. Stop me any time and say 'explain it simply' if I get too technical."
- **System prompt**: paste `src/devprod/voice/prompts.py::SYSTEM_PROMPT` (it references the
  dynamic variables below).
- **LLM**: any tool-calling capable model.

## 2. Dynamic variables

Injected per call by the browser from `POST /api/voice/session`:

| Variable | Meaning |
|----------|---------|
| `run_id` | current simulator run |
| `developer_name` | who is on the call |
| `service_name` | the dummy app under test |
| `explain_mode` | `default` \| `eli5` \| `researcher` |
| `current_step` | orchestrator step at call start |

## 3. Server tools

Add each as a **Webhook tool** pointing at your backend base URL
(`https://<tunnel>/api/...`). Bodies are JSON; all take `run_id`.

```
start_run              POST {base}/api/run/start        body: {run_id, scenario}
induce_error           POST {base}/api/run/induce       body: {run_id, fault}
collect_logs           GET  {base}/api/run/logs?run_id=
diagnose               POST {base}/api/run/diagnose     body: {run_id}
get_fix_plan           GET  {base}/api/run/fix-plan?run_id=
approve_fix            POST {base}/api/run/approve      body: {run_id, approved, note}
get_docs               GET  {base}/api/run/docs?run_id=
set_explain_mode       POST {base}/api/voice/mode       body: {run_id, mode}
confirm_understanding   POST {base}/api/voice/ack        body: {run_id, understood, topic}
```

Generate the exact JSON schemas with:

```bash
python -m devprod.voice.agent_tools --print-schema
```

## 4. Conversation rules to set on the agent

- Never advance a step without saying what you are about to do.
- After every explanation, ask a short comfort check; call `confirm_understanding`.
- If the developer says "I don't get it" / "simpler" → call `set_explain_mode` with `eli5`
  and re-explain the same step with an analogy, no jargon, ≤2 sentences per idea.
- If asked "why" / "what else could break" → `set_explain_mode` with `researcher`.
- Require an explicit yes before calling `approve_fix`.
- Read the PR link digit-by-digit style (slowly) and then the doc summary.

## 5. Local env

```bash
cp .env.example .env
# ELEVENLABS_API_KEY=sk_...
# ELEVENLABS_AGENT_ID=agent_...
```

Without these the backend runs in `mock` voice mode: `/api/voice/session` returns
`{"mode": "mock"}` and the browser uses Web Speech API so the demo still works offline.

## 6. Exposing the backend to ElevenLabs

Server tools are called from ElevenLabs' cloud, so the backend must be reachable. Use any
tunnel (`cloudflared tunnel --url http://localhost:8000`) and set that URL as the tool base.
