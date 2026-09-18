"""Mints short-lived ElevenLabs Conversational AI sessions for the browser."""

from __future__ import annotations

import httpx

from ..analysis import log_collector
from ..config import settings
from . import prompts

SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
AGENT_ENDPOINT = "https://api.elevenlabs.io/v1/convai/agents/{agent_id}"

_agent_synced = False


def sync_agent() -> str:
    """Push the researcher prompt and first message onto the agent.

    The dashboard persona would otherwise win: dynamic variables only fill in the
    placeholders of whatever prompt the agent already has.
    """
    global _agent_synced
    if _agent_synced:
        return "agent prompt already synced"
    body = {
        "conversation_config": {
            "agent": {
                "first_message": prompts.FIRST_MESSAGE,
                "prompt": {"prompt": prompts.SYSTEM_PROMPT},
            }
        }
    }
    response = httpx.patch(
        AGENT_ENDPOINT.format(agent_id=settings.elevenlabs_agent_id),
        json=body,
        headers={"xi-api-key": settings.elevenlabs_api_key or ""},
        timeout=15.0,
    )
    response.raise_for_status()
    _agent_synced = True
    return "agent prompt synced from prompts.py"


def session_payload(
    run_id: str, current_step: str, explain_mode: str = prompts.EXPLAIN_MODE
) -> dict:
    """What the browser needs to start (or fake) a call.

    Every variable the agent's first message can reference must be present, or the
    conversation is rejected with "Missing required dynamic variables in first message".
    """
    variables = {
        "run_id": run_id,
        "developer_name": settings.developer_name,
        "service_name": "orders-service",
        "explain_mode": explain_mode,
        "current_step": current_step,
        "topic": log_collector.topic(log_collector.collect(run_id)),
    }
    if settings.voice_mode == "mock":
        return {
            "mode": "mock",
            "reason": "ELEVENLABS_API_KEY / ELEVENLABS_AGENT_ID not set",
            "dynamic_variables": variables,
            "mode_guidance": prompts.guidance(explain_mode),
        }
    try:
        sync_note = sync_agent()
    except Exception as exc:  # keep the call going with the dashboard persona
        sync_note = f"agent prompt sync failed, dashboard persona in use: {exc}"
    try:
        response = httpx.get(
            SIGNED_URL_ENDPOINT,
            params={"agent_id": settings.elevenlabs_agent_id},
            headers={"xi-api-key": settings.elevenlabs_api_key or ""},
            timeout=15.0,
        )
        response.raise_for_status()
        signed_url = response.json().get("signed_url")
    except Exception as exc:  # fall back to mock so the demo never dead-ends
        return {
            "mode": "mock",
            "reason": f"signed url request failed: {exc}",
            "dynamic_variables": variables,
            "mode_guidance": prompts.guidance(explain_mode),
        }
    return {
        "mode": "live",
        "signed_url": signed_url,
        "agent_id": settings.elevenlabs_agent_id,
        "agent_sync": sync_note,
        "dynamic_variables": variables,
        "mode_guidance": prompts.guidance(explain_mode),
    }
