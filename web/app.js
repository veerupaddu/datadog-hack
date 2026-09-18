const el = (id) => document.getElementById(id);
const state = { runId: null, voiceMode: "mock", speaking: true, inCall: false };
const STEPS = ["idle", "running", "failing", "collected", "diagnosed", "plan_ready", "patched",
  "pr_open", "documented", "summarized"];
const reached = (step, target) => STEPS.indexOf(step) >= STEPS.indexOf(target);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail || body;
    } catch (err) {
      /* non-JSON error body */
    }
    say(detail, "bad");
    throw new Error(detail);
  }
  return res.json();
}

const post = (path, body) => api(path, { method: "POST", body: JSON.stringify(body) });

/* ---------- rendering ---------- */

function setStep(step) {
  el("step").textContent = step;
  el("btn-induce").disabled = !state.runId || !reached(step, "running");
  el("btn-logs").disabled = !reached(step, "failing");
  el("btn-call").disabled = !reached(step, "collected") || state.inCall;
  el("btn-diagnose").disabled = !state.inCall || !reached(step, "collected") || reached(step, "diagnosed");
  el("btn-approve").disabled = !["plan_ready", "diagnosed"].includes(step);
  const feedbackOff = !state.inCall || !reached(step, "diagnosed");
  el("btn-ack-yes").disabled = feedbackOff;
  el("btn-ack-no").disabled = feedbackOff;
}

function timelineEntry(event) {
  const li = document.createElement("li");
  li.innerHTML = `<b>${event.step}</b> ${event.message}<span>${new Date(event.ts).toLocaleTimeString()}</span>`;
  el("timeline").prepend(li);
}

function say(text, cls = "") {
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text;
  el("transcript").prepend(div);
  if (state.voiceMode === "mock" && state.speaking && window.speechSynthesis) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    window.speechSynthesis.speak(utterance);
  }
}

function renderLogs(evidence) {
  if (!evidence) return;
  el("logs").className = "card scroll";
  const lines = evidence.entries.map((e) => {
    const cls = e.level === "ERROR" ? "log-error" : "";
    const detail = e.error_type ? ` — ${e.error_type}: ${e.error || ""}` : "";
    return `<div class="${cls}">[${e.level}] ${escapeHtml(e.message || e.event || "")}${escapeHtml(detail)}</div>`;
  });
  el("logs").innerHTML =
    `<b>${evidence.error_count} error lines / ${evidence.entry_count} total</b><br/>` +
    lines.join("") +
    (evidence.traceback ? `<pre>${escapeHtml(evidence.traceback)}</pre>` : "");
}

function renderRootCause(rc) {
  if (!rc) return;
  el("root-cause").className = "card";
  el("root-cause").innerHTML =
    `<b>${rc.error_type}</b> in <code>${rc.function}()</code> at ` +
    `<span class="fix-point">${rc.file}:${rc.line}</span>` +
    `<br/><br/>${rc.headline}<br/><br/>${rc.explanations.researcher}` +
    `<br/><br/><small>${rc.evidence.join(" · ")} · confidence ${(rc.confidence * 100).toFixed(0)}%</small>`;
}

function diffHtml(diff) {
  return diff
    .split("\n")
    .map((line) => {
      const text = escapeHtml(line);
      if (line.startsWith("+") && !line.startsWith("+++")) return `<span class="fix-add">${text}</span>`;
      if (line.startsWith("-") && !line.startsWith("---")) return `<span class="fix-del">${text}</span>`;
      return text;
    })
    .join("\n");
}

function renderPlan(plan, rc) {
  if (!plan) return;
  el("fix-plan").className = "card";
  const where = rc ? `<div>Fix point: <span class="fix-point">${rc.file}:${rc.line}</span> in <code>${rc.function}()</code></div><br/>` : "";
  el("fix-plan").innerHTML =
    where +
    `<b>${plan.title}</b><br/>${plan.summary}<br/><br/>` +
    plan.steps.map((s) => `• ${s}`).join("<br/>") +
    `<br/><br/>Risk: ${plan.risk}<pre>${diffHtml(plan.diff)}</pre>`;
}

function renderOutcome(runState) {
  if (!runState.pr && !runState.doc_path) return;
  const pr = runState.pr || {};
  el("outcome").className = "card";
  el("outcome").innerHTML =
    (pr.url ? `PR (${pr.mode}): <a href="${pr.url}" target="_blank" rel="noreferrer">${pr.url}</a><br/>` : "") +
    (pr.error ? `<span class="log-error">PR step: ${escapeHtml(pr.error)}</span><br/>` : "") +
    (runState.verify_status ? `Replay after fix: <span class="ok">${runState.verify_status}</span><br/>` : "") +
    (runState.doc_path ? `Doc: <code>${runState.doc_path}</code><br/><br/>` : "") +
    (runState.summary || "");
}

function resetCard(id, text) {
  el(id).className = "card muted";
  el(id).textContent = text;
}

function render(runState) {
  if (state.runId && runState.run_id !== state.runId) return;
  state.runId = runState.run_id;
  el("run-id").textContent = runState.run_id;
  setStep(runState.step);
  renderLogs(runState.evidence);
  renderRootCause(runState.root_cause);
  renderPlan(runState.fix_plan, runState.root_cause);
  renderOutcome(runState);
}

const escapeHtml = (s = "") =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

/* ---------- live events ---------- */

function connectEvents() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/events`);
  ws.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (state.runId && event.run_id && event.run_id !== state.runId) return;
    timelineEntry(event);
    say(event.message);
    if (state.runId) api(`/api/run/state?run_id=${state.runId}`).then(render).catch(() => {});
  };
  ws.onclose = () => setTimeout(connectEvents, 2000);
}

/* ---------- voice ---------- */

async function startCall() {
  if (!state.runId) {
    say("Start a run first.", "bad");
    return;
  }
  const session = await post("/api/voice/session", { run_id: state.runId });
  state.voiceMode = session.mode;
  state.inCall = true;
  el("voice-mode").textContent = `voice: ${session.mode}`;
  el("voice-mode").title = session.reason || "ElevenLabs agent connected";
  say(`Topic sent to the agent: ${session.dynamic_variables.topic}`);
  render(await api(`/api/run/state?run_id=${state.runId}`));
  if (session.mode !== "live") {
    say(`Mock voice mode (${session.reason}). I'll narrate each step with browser speech.`);
    return;
  }
  const widget = document.createElement("elevenlabs-convai");
  widget.setAttribute("agent-id", session.agent_id);
  widget.setAttribute("signed-url", session.signed_url);
  widget.setAttribute("dynamic-variables", JSON.stringify(session.dynamic_variables));
  document.body.appendChild(widget);
  const script = document.createElement("script");
  script.src = "https://unpkg.com/@elevenlabs/convai-widget-embed";
  script.async = true;
  document.body.appendChild(script);
  say(`Voice call starting — ${session.agent_sync}.`);
}

/* ---------- wiring ---------- */

async function init() {
  const { faults, voice_mode } = await api("/api/faults");
  state.voiceMode = voice_mode;
  el("voice-mode").textContent = `voice: ${voice_mode}`;
  el("fault").innerHTML = faults
    .map((f) => `<option value="${f.id}">${f.title}</option>`)
    .join("");
  connectEvents();
}

// api() already reports failures in the transcript; swallow so clicks never reject.
const onClick = (target, handler) => {
  const node = typeof target === "string" ? el(target) : target;
  node.onclick = () => Promise.resolve(handler()).catch(() => {});
};

onClick("btn-start", async () => {
  state.runId = null;
  state.inCall = false;
  resetCard("logs", "No logs collected yet.");
  resetCard("root-cause", "Nothing diagnosed yet.");
  resetCard("fix-plan", "No plan yet.");
  resetCard("outcome", "Nothing shipped yet.");
  render(await post("/api/run/start", { scenario: "pricing" }));
});
onClick("btn-induce", async () =>
  render(await post("/api/run/induce", { run_id: state.runId, fault: el("fault").value })));
onClick("btn-logs", async () => {
  const { evidence } = await api(`/api/run/logs?run_id=${state.runId}`);
  say(`Log collector: ${evidence.error_count} error lines out of ${evidence.entry_count}.`);
  render(await api(`/api/run/state?run_id=${state.runId}`));
});
onClick("btn-diagnose", async () =>
  render(await post("/api/run/diagnose", { run_id: state.runId })));
onClick("btn-approve", async () =>
  render(await post("/api/run/approve", { run_id: state.runId, approved: true, note: "approved in UI" })));
onClick("btn-call", startCall);
onClick("btn-ack-yes", () =>
  post("/api/voice/ack", { run_id: state.runId, understood: true, topic: el("step").textContent }));
onClick("btn-ack-no", async () => {
  const res = await post("/api/voice/ack", { run_id: state.runId, understood: false, topic: "error logs" });
  if (res.explanation) {
    say(res.explanation);
    render(await api(`/api/run/state?run_id=${state.runId}`));
  }
});

init();
