const el = (id) => document.getElementById(id);
const state = {
  runId: null, voiceMode: "mock", speaking: true, inCall: false, conversation: null, lastContextStep: null,
};
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
  el("btn-call").disabled = state.conversation ? false : !reached(step, "collected") || state.inCall;
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
    (pr.note ? `<span class="log-error">${escapeHtml(pr.note)}</span><br/>` : "") +
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
  pushContext(runState);
}

/* ---------- agent context (live call) ---------- */

const CONTEXT_STEPS = ["collected", "diagnosed", "plan_ready", "patched", "pr_open", "documented", "summarized"];

function contextFor(runState) {
  const ev = runState.evidence;
  const rc = runState.root_cause;
  const plan = runState.fix_plan;
  const pr = runState.pr;
  const parts = [`Simulator run ${runState.run_id} is now at step "${runState.step}".`];
  if (ev && reached(runState.step, "collected")) {
    const errors = ev.entries.filter((e) => e.level === "ERROR")
      .map((e) => `${e.error_type}: ${e.error}`).join("; ");
    parts.push(`ERROR LOGS (${ev.error_count} of ${ev.entry_count} lines): ${errors}`);
    if (ev.traceback) parts.push(`TRACEBACK:\n${ev.traceback}`);
  }
  if (rc && reached(runState.step, "diagnosed")) {
    parts.push(
      `DIAGNOSIS: ${rc.error_type} in ${rc.function}() at ${rc.file}:${rc.line}. ${rc.headline} ` +
      `${rc.explanations.researcher} Evidence: ${rc.evidence.join("; ")}. ` +
      `Confidence ${(rc.confidence * 100).toFixed(0)}%.`,
    );
  }
  if (plan && reached(runState.step, "plan_ready")) {
    parts.push(`FIX PLAN: ${plan.title}. ${plan.summary} Steps: ${plan.steps.join(" ")} Risk: ${plan.risk}\nDIFF:\n${plan.diff}`);
  }
  if (runState.verify_status && reached(runState.step, "patched")) {
    parts.push(`VERIFICATION: replayed failing request now returns ${runState.verify_status}.`);
  }
  if (pr && pr.url && reached(runState.step, "pr_open")) parts.push(`PULL REQUEST (${pr.mode}): ${pr.url}`);
  if (runState.doc_path) parts.push(`DOCUMENTATION: ${runState.doc_path}`);
  if (runState.summary) parts.push(`SUMMARY: ${runState.summary}`);
  return parts.join("\n\n");
}

function pushContext(runState) {
  if (!state.conversation || !CONTEXT_STEPS.includes(runState.step)) return;
  if (state.lastContextStep === runState.step) return;
  state.lastContextStep = runState.step;
  try {
    state.conversation.sendContextualUpdate(contextFor(runState));
    say(`(context sent to agent: ${runState.step})`, "muted");
  } catch (err) {
    say(`Could not send context to the agent: ${err.message}`, "bad");
  }
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

async function endCall() {
  const conversation = state.conversation;
  state.conversation = null;
  state.inCall = false;
  state.lastContextStep = null;
  el("btn-call").textContent = "Start voice call (sends logs)";
  if (conversation) await conversation.endSession().catch(() => {});
  say("Voice call ended.");
  if (state.runId) render(await api(`/api/run/state?run_id=${state.runId}`));
}

async function startCall() {
  if (state.conversation) return endCall();
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
  say(`Voice call starting — ${session.agent_sync}.`);
  try {
    const { Conversation } = await import("https://esm.sh/@elevenlabs/client@1.24.0");
    state.conversation = await Conversation.startSession({
      signedUrl: session.signed_url,
      dynamicVariables: session.dynamic_variables,
      onConnect: () => say("Agent connected — say hello."),
      onDisconnect: () => { if (state.conversation) endCall(); },
      onError: (message) => say(`Agent error: ${message}`, "bad"),
      onMessage: ({ source, message }) =>
        say(`${source === "ai" ? "Agent" : "You"}: ${message}`, source === "ai" ? "" : "muted"),
    });
    el("btn-call").textContent = "End voice call";
    el("btn-call").disabled = false;
    state.lastContextStep = null;
    render(await api(`/api/run/state?run_id=${state.runId}`));
  } catch (err) {
    state.inCall = false;
    say(`Could not start the ElevenLabs call: ${err.message || err}`, "bad");
    render(await api(`/api/run/state?run_id=${state.runId}`));
  }
}

/* ---------- wiring ---------- */

async function init() {
  const { faults, voice_mode, pr_mode } = await api("/api/faults");
  state.voiceMode = voice_mode;
  el("voice-mode").textContent = `voice: ${voice_mode}`;
  el("pr-mode").textContent = `pr: ${pr_mode}`;
  el("pr-mode").title =
    pr_mode === "real"
      ? "Approval pushes a branch and opens a GitHub PR"
      : "DEVPROD_ENABLE_PR=0 in .env — remove it (or set 1) and restart ./init.sh";
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
  if (state.conversation) await endCall();
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
