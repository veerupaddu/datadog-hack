import pytest
from fastapi.testclient import TestClient

from devprod import server
from devprod.fix import patcher
from devprod.orchestrator import Orchestrator, StepError

FAULTS = ["divide_by_zero_discount", "missing_currency_key", "coupon_retry_storm"]


@pytest.mark.parametrize("fault", FAULTS)
def test_induce_and_diagnose(fault):
    orch = Orchestrator()
    state = orch.start()
    orch.induce(state.run_id, fault)
    assert state.failing_status >= 400

    orch.diagnose(state.run_id)
    assert state.root_cause is not None
    assert state.root_cause.confidence > 0.5
    assert state.fix_plan is not None
    assert "sample_app" in state.fix_plan.patch.file
    for mode in ("default", "eli5", "researcher"):
        assert state.root_cause.explain(mode)


def test_approve_patches_and_documents():
    orch = Orchestrator()
    state = orch.start()
    orch.induce(state.run_id, "divide_by_zero_discount")
    orch.diagnose(state.run_id)
    plan = state.fix_plan
    try:
        orch.approve(state.run_id, approved=True, note="pytest")
        assert state.verify_status == plan.expected_status_after_fix
        assert state.pr and state.pr["url"]
        assert state.doc_path and state.summary
        assert state.step == "summarized"
    finally:
        patcher.revert(plan)


def test_out_of_order_steps_raise_step_error():
    orch = Orchestrator()
    state = orch.start()
    with pytest.raises(StepError):
        orch.diagnose(state.run_id)
    with pytest.raises(StepError):
        orch.approve(state.run_id, approved=True)
    assert state.step == "collected"


def test_out_of_order_approve_returns_409():
    with TestClient(server.app) as client:
        run_id = client.post("/api/run/start", json={"scenario": "pricing"}).json()["run_id"]
        assert client.post("/api/run/diagnose", json={"run_id": run_id}).status_code == 409
        response = client.post(
            "/api/run/approve", json={"run_id": run_id, "approved": True}
        )
        assert response.status_code == 409
        assert "fix plan" in response.json()["detail"]


def test_lost_developer_switches_to_eli5():
    orch = Orchestrator()
    state = orch.start()
    orch.induce(state.run_id, "missing_currency_key")
    orch.diagnose(state.run_id)
    result = orch.acknowledge(state.run_id, understood=False, topic="root cause")
    assert state.explain_mode == "eli5"
    assert result["explanation"] == state.root_cause.explain("eli5")
