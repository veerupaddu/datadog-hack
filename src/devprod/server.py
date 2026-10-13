"""FastAPI backend: UI endpoints, ElevenLabs server tools and the live event stream."""

from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .orchestrator import StepError, orchestrator
from .simulator import faults
from .voice import elevenlabs_client

WEB_DIR = settings.repo_root / "web"

app = FastAPI(title="devprod-simulator", version="0.1.0")


class StartBody(BaseModel):
    run_id: str | None = None
    scenario: str = "pricing"


class InduceBody(BaseModel):
    run_id: str
    fault: str


class RunBody(BaseModel):
    run_id: str


class ApproveBody(BaseModel):
    run_id: str
    approved: bool
    note: str = ""


class AckBody(BaseModel):
    run_id: str
    understood: bool
    topic: str = ""


def _state(run_id: str):
    try:
        return orchestrator.get(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.exception_handler(StepError)
def _step_error(request: Request, exc: StepError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/api/faults")
def list_faults() -> dict:
    return {
        "faults": faults.catalog(),
        "voice_mode": settings.voice_mode,
        "pr_mode": "real" if settings.enable_pr else "dry-run",
    }


@app.post("/api/run/start")
def start(body: StartBody) -> dict:
    return orchestrator.start(body.run_id, body.scenario).public()


@app.post("/api/run/induce")
def induce(body: InduceBody) -> dict:
    _state(body.run_id)
    try:
        return orchestrator.induce(body.run_id, body.fault).public()
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/run/logs")
def logs(run_id: str) -> dict:
    _state(run_id)
    state = orchestrator.collect(run_id)
    return {"evidence": state.evidence, "step": state.step}


@app.post("/api/run/diagnose")
def diagnose(body: RunBody) -> dict:
    _state(body.run_id)
    return orchestrator.diagnose(body.run_id).public()


@app.get("/api/run/fix-plan")
def fix_plan(run_id: str) -> dict:
    state = _state(run_id)
    if state.fix_plan is None:
        raise HTTPException(status_code=409, detail="diagnose first")
    return state.fix_plan.to_dict()


@app.post("/api/run/approve")
def approve(body: ApproveBody) -> dict:
    _state(body.run_id)
    return orchestrator.approve(body.run_id, body.approved, body.note).public()


@app.get("/api/run/docs")
def docs(run_id: str) -> dict:
    state = _state(run_id)
    if not state.doc_path:
        raise HTTPException(status_code=409, detail="no documentation yet")
    content = (settings.repo_root / state.doc_path).read_text(encoding="utf-8")
    return {"path": state.doc_path, "summary": state.summary, "content": content}


@app.get("/api/run/state")
def run_state(run_id: str) -> dict:
    return _state(run_id).public()


@app.post("/api/voice/session")
def voice_session(body: RunBody) -> dict:
    state = _state(body.run_id)
    return elevenlabs_client.session_payload(body.run_id, state.step, state.explain_mode)


@app.post("/api/voice/explain-again")
def voice_explain_again(body: RunBody) -> dict:
    _state(body.run_id)
    return orchestrator.explain_again(body.run_id)


@app.post("/api/voice/ack")
def voice_ack(body: AckBody) -> dict:
    _state(body.run_id)
    return orchestrator.acknowledge(body.run_id, body.understood, body.topic)


@app.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    await ws.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict] = asyncio.Queue()

    def listener(event: dict) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    orchestrator.subscribe(listener)
    try:
        while True:
            event = await queue.get()
            await ws.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        orchestrator.unsubscribe(listener)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
