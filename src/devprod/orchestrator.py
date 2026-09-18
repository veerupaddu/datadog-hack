"""The eight step state machine every run walks through."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .analysis import log_collector, rca
from .docgen import generator
from .fix import patcher, planner, pr
from .simulator import faults, log_store, runner

STEPS = [
    "idle", "running", "failing", "collected", "diagnosed",
    "plan_ready", "patched", "pr_open", "documented", "summarized",
]

Listener = Callable[[dict], None]


class StepError(RuntimeError):
    """A step was requested before the run reached the state it needs."""


@dataclass
class RunState:
    run_id: str
    step: str = "idle"
    explain_mode: str = "researcher"
    fault_id: str | None = None
    baseline: dict | None = None
    failing_status: int | None = None
    failing_payload: dict | None = None
    verify_status: int | None = None
    evidence: dict | None = None
    root_cause: rca.RootCause | None = None
    fix_plan: planner.FixPlan | None = None
    patch_result: dict | None = None
    test_result: dict | None = None
    pr: dict | None = None
    doc_path: str | None = None
    summary: str | None = None
    acknowledgements: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)

    def public(self) -> dict:
        return {
            "run_id": self.run_id,
            "step": self.step,
            "explain_mode": self.explain_mode,
            "fault_id": self.fault_id,
            "baseline": self.baseline,
            "failing_status": self.failing_status,
            "verify_status": self.verify_status,
            "root_cause": self.root_cause.to_dict() if self.root_cause else None,
            "fix_plan": self.fix_plan.to_dict() if self.fix_plan else None,
            "patch_result": self.patch_result,
            "test_result": self.test_result,
            "pr": self.pr,
            "doc_path": self.doc_path,
            "summary": self.summary,
            "acknowledgements": self.acknowledgements,
            "events": self.events,
        }


class Orchestrator:
    """Holds every run in memory and notifies listeners (the browser) on each transition."""

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._listeners: list[Listener] = []

    # -- plumbing ---------------------------------------------------------
    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _emit(self, state: RunState, step: str, message: str, **data) -> None:
        state.step = step
        event = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": state.run_id,
            "step": step,
            "message": message,
            "data": data,
        }
        state.events.append(event)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                self.unsubscribe(listener)

    def get(self, run_id: str) -> RunState:
        if run_id not in self._runs:
            raise KeyError(f"unknown run {run_id!r}")
        return self._runs[run_id]

    # -- steps ------------------------------------------------------------
    def start(self, run_id: str | None = None, scenario: str = "pricing") -> RunState:
        run_id = run_id or f"run-{uuid.uuid4().hex[:8]}"
        state = RunState(run_id=run_id)
        self._runs[run_id] = state
        log_store.clear(run_id)
        baseline = runner.healthy_call(run_id)
        state.baseline = baseline.as_dict()
        health = (
            f"a healthy order priced fine in {baseline.elapsed_ms} ms"
            if baseline.ok
            else f"but the baseline order already returned {baseline.status_code}"
        )
        self._emit(
            state, "running", f"Started the orders service ({scenario}); {health}.",
            baseline=state.baseline,
        )
        return state

    def induce(self, run_id: str, fault_id: str) -> RunState:
        state = self.get(run_id)
        fault = faults.get(fault_id)
        invocation = runner.induce(run_id, fault_id)
        state.fault_id = fault_id
        state.failing_status = invocation.status_code
        state.failing_payload = invocation.payload
        self._emit(
            state, "failing",
            f"Induced {fault.title.lower()} — the service returned {invocation.status_code}.",
            invocation=invocation.as_dict(), fault=fault.as_dict(),
        )
        return state

    def collect(self, run_id: str) -> RunState:
        state = self.get(run_id)
        state.evidence = log_collector.collect(run_id)
        self._emit(
            state, "collected", log_collector.spoken_summary(state.evidence),
            evidence=state.evidence,
        )
        return state

    def diagnose(self, run_id: str) -> RunState:
        state = self.get(run_id)
        if state.evidence is None:
            self.collect(run_id)
        if not (state.evidence or {}).get("error_count"):
            raise StepError("nothing has failed yet — induce a fault before diagnosing")
        state.root_cause = rca.diagnose(state.evidence or {})
        self._emit(
            state, "diagnosed", state.root_cause.explain(state.explain_mode),
            root_cause=state.root_cause.to_dict(),
        )
        self.build_plan(run_id)
        return state

    def build_plan(self, run_id: str) -> RunState:
        state = self.get(run_id)
        if state.root_cause is None:
            raise StepError("diagnose before planning")
        state.fix_plan = planner.plan_for(state.root_cause)
        if state.fix_plan is None:
            self._emit(state, "diagnosed", "I don't have a canned fix for this one yet.")
            return state
        self._emit(
            state, "plan_ready", state.fix_plan.spoken(), fix_plan=state.fix_plan.to_dict()
        )
        return state

    def approve(self, run_id: str, approved: bool, note: str = "") -> RunState:
        state = self.get(run_id)
        if not approved:
            self._emit(state, "plan_ready", f"Understood, holding off. {note}".strip())
            return state
        if state.fix_plan is None:
            raise StepError("no fix plan to approve — diagnose the failure first")

        state.patch_result = patcher.apply(state.fix_plan)
        verification = runner.verify(run_id, state.fault_id or "")
        state.verify_status = verification.status_code
        fixed = verification.status_code == state.fix_plan.expected_status_after_fix
        self._emit(
            state, "patched",
            f"Patch applied. The same request now returns {verification.status_code}"
            f"{' — fixed.' if fixed else ' — not what I expected, flagging it.'}",
            patch=state.patch_result, verification=verification.as_dict(),
        )

        headline = state.root_cause.headline if state.root_cause else ""
        state.pr = pr.open_pr(state.fix_plan, headline, run_id)
        self._emit(
            state, "pr_open", f"Pull request ready: {state.pr.get('url')}", pr=state.pr
        )

        doc_path = generator.write_doc(state)
        state.doc_path = str(doc_path.relative_to(generator.settings.repo_root))
        self._emit(state, "documented", f"Wrote the incident document to {state.doc_path}.",
                   doc_path=state.doc_path)

        state.summary = generator.summarize(state)
        self._emit(state, "summarized", state.summary, summary=state.summary)
        return state

    # -- conversation -----------------------------------------------------
    def explain_again(self, run_id: str) -> dict:
        """Re-state the current root cause; the agent has a single researcher register."""
        state = self.get(run_id)
        explanation = state.root_cause.explain() if state.root_cause else ""
        self._emit(state, state.step, explanation or "Nothing diagnosed yet.",
                   explanation=explanation)
        return {"mode": state.explain_mode, "explanation": explanation}

    def acknowledge(self, run_id: str, understood: bool, topic: str = "") -> dict:
        state = self.get(run_id)
        ack = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "understood": understood,
            "topic": topic,
        }
        state.acknowledgements.append(ack)
        if not understood:
            return {"ack": ack, **self.explain_again(run_id)}
        self._emit(state, state.step, "Comfort check recorded.", ack=ack)
        return {"ack": ack}


orchestrator = Orchestrator()
