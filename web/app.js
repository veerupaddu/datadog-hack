const el = (id) => document.getElementById(id);
const state = { runId: null, mode: "default", voiceMode: "mock", speaking: true };

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
  el("btn-induce").disabled = !state.runId;
  el("btn-logs").disabled = !state.runId;
  el("btn-diagnose").disabled = !state.runId;
  el("btn-approve").disabled = !["plan_ready", "diagnosed"].includes(step);
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

function renderRootCause(rc) {
  if (!rc) return;
  el("root-cause").className = "card";
  el("root-cause").innerHTML =
    `<b>${rc.error_type}</b> in <code>${rc.function}()</code> at <code>${rc.file}:${rc.line}</code>` +
    `<br/><br/>${rc.headline}<br/><br/>${rc.explanations[state.mode] || rc.explanations.default}` +
    `<br/><br/><small>${rc.evidence.join(" · ")} · confidence ${(rc.confidence * 100).toFixed(0)}%</small>`;
}

function renderPlan(plan) {
  if (!plan) return;
  el("fix-plan").className = "card";
  el("fix-plan").innerHTML =
    `<b>${plan.title}</b><br/>${plan.summary}<br/><br/>` +
    plan.steps.map((s) => `• ${s}`).join("<br/>") +
    `<br/><br/>Risk: ${plan.risk}<pre>${escapeHtml(plan.diff)}</pre>`;
}

function renderOutcome(runState) {
  if (!runState.pr && !runState.doc_path) return;
  const pr = runState.pr || {};
  el("outcome").className = "card";
  el("outcome").innerHTML =
    (pr.url ? `PR (${pr.mode}): <a href="${pr.url}" target="_blank" rel="noreferrer">${pr.url}</a><br/>` : "") +
    (runState.verify_status ? `Replay after fix: <span class="ok">${runState.verify_status}</span><br/>` : "") +
    (runState.doc_path ? `Doc: <code>${runState.doc_path}</code><br/><br/>` : "") +
    (runState.summary || "");
}

function resetCard(id, text) {
  el(id).className = "card muted";
  el(id).textContent = text;
}

function setModeButtons(mode) {
  state.mode = mode;
  document
    .querySelectorAll("button.mode")
    .forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
}

function render(runState) {
  if (state.runId && runState.run_id !== state.runId) return;
  state.runId = runState.run_id;
  if (runState.explain_mode) setModeButtons(runState.explain_mode);
  el("run-id").textContent = runState.run_id;
  setStep(runState.step);
  renderRootCause(runState.root_cause);
  renderPlan(runState.fix_plan);
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
  el("voice-mode").textContent = `voice: ${session.mode}`;
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
  say("Voice call starting — the agent has the incident context.");
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

el("btn-start").onclick = async () => {
  state.runId = null;
  resetCard("root-cause", "Nothing diagnosed yet.");
  resetCard("fix-plan", "No plan yet.");
  resetCard("outcome", "Nothing shipped yet.");
  setModeButtons("default");
  render(await post("/api/run/start", { scenario: "pricing" }));
};
el("btn-induce").onclick = async () =>
  render(await post("/api/run/induce", { run_id: state.runId, fault: el("fault").value }));
el("btn-logs").onclick = async () => {
  const { evidence } = await api(`/api/run/logs?run_id=${state.runId}`);
  say(`${evidence.error_count} error lines out of ${evidence.entry_count}.`);
};
el("btn-diagnose").onclick = async () =>
  render(await post("/api/run/diagnose", { run_id: state.runId }));
el("btn-approve").onclick = async () =>
  render(await post("/api/run/approve", { run_id: state.runId, approved: true, note: "approved in UI" }));
el("btn-call").onclick = startCall;
el("btn-ack-yes").onclick = () =>
  post("/api/voice/ack", { run_id: state.runId, understood: true, topic: el("step").textContent });
el("btn-ack-no").onclick = async () => {
  const res = await post("/api/voice/ack", { run_id: state.runId, understood: false, topic: "root cause" });
  if (res.explanation) {
    setModeButtons("eli5");
    say(res.explanation);
    render(await api(`/api/run/state?run_id=${state.runId}`));
  }
};

document.querySelectorAll("button.mode").forEach((btn) => {
  btn.onclick = async () => {
    setModeButtons(btn.dataset.mode);
    if (!state.runId) return;
    const res = await post("/api/voice/mode", { run_id: state.runId, mode: state.mode });
    if (res.explanation) say(res.explanation);
    render(await api(`/api/run/state?run_id=${state.runId}`));
  };
});

init();
