"""Drives traffic against the dummy service and records what happened."""

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from typing import Any

from starlette.testclient import TestClient

from ..sample_app import logging_setup
from . import faults, log_store


@dataclass
class Invocation:
    label: str
    payload: dict
    status_code: int
    response: dict
    elapsed_ms: float
    ok: bool = field(init=False)

    def __post_init__(self) -> None:
        self.ok = 200 <= self.status_code < 400

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "payload": self.payload,
            "status_code": self.status_code,
            "response": self.response,
            "elapsed_ms": self.elapsed_ms,
            "ok": self.ok,
        }


def _load_app():
    """Import (or re-import) the dummy app so code patches take effect immediately."""
    pricing = importlib.import_module("devprod.sample_app.pricing")
    app_module = importlib.import_module("devprod.sample_app.app")
    importlib.reload(pricing)
    importlib.reload(app_module)
    return app_module.app


def _call(run_id: str, label: str, payload: dict) -> Invocation:
    logging_setup.configure(log_store.log_path(run_id))
    app = _load_app()
    started = time.perf_counter()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/orders/price", json=payload)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    return Invocation(label=label, payload=payload, status_code=response.status_code,
                      response=body, elapsed_ms=elapsed_ms)


def healthy_call(run_id: str) -> Invocation:
    """Step 2: prove the service works before we break it."""
    return _call(run_id, "baseline", faults.HEALTHY_PAYLOAD)


def induce(run_id: str, fault_id: str) -> Invocation:
    """Step 3: send the request that reaches the bug."""
    fault = faults.get(fault_id)
    return _call(run_id, f"fault:{fault.id}", fault.payload)


def verify(run_id: str, fault_id: str) -> Invocation:
    """Re-run the failing request after a patch to confirm it is fixed."""
    fault = faults.get(fault_id)
    return _call(run_id, f"verify:{fault.id}", fault.payload)
