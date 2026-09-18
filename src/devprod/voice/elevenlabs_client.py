"""Mints short-lived ElevenLabs Conversational AI sessions for the browser."""

from __future__ import annotations

import httpx

from ..analysis import log_collector
from ..config import settings
from . import prompts

SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"


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
        "dynamic_variables": variables,
        "mode_guidance": prompts.guidance(explain_mode),
    }
