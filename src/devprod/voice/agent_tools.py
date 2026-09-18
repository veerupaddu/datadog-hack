"""Schemas for the server tools registered on the ElevenLabs agent.

`python -m devprod.voice.agent_tools --print-schema` prints JSON you can paste into the
ElevenLabs dashboard (or feed to their API) when configuring the agent.
"""

from __future__ import annotations

import argparse
import json

_RUN_ID = {"run_id": {"type": "string", "description": "Current simulator run id"}}

TOOLS: list[dict] = [
    {
        "name": "start_run",
        "description": "Boot the dummy orders service and start a simulation run.",
        "method": "POST",
        "path": "/api/run/start",
        "parameters": {
            "type": "object",
            "properties": {
                **_RUN_ID,
                "scenario": {"type": "string", "description": "Scenario label, e.g. 'pricing'"},
            },
            "required": ["run_id"],
        },
    },
    {
        "name": "induce_error",
        "description": "Send the request that triggers a named fault in the service.",
        "method": "POST",
        "path": "/api/run/induce",
        "parameters": {
            "type": "object",
            "properties": {
                **_RUN_ID,
                "fault": {
                    "type": "string",
                    "enum": [
                        "divide_by_zero_discount",
                        "missing_currency_key",
                        "coupon_retry_storm",
                    ],
                },
            },
            "required": ["run_id", "fault"],
        },
    },
    {
        "name": "collect_logs",
        "description": "Return the structured logs and traceback captured for this run.",
        "method": "GET",
        "path": "/api/run/logs",
        "parameters": {"type": "object", "properties": _RUN_ID, "required": ["run_id"]},
    },
    {
        "name": "diagnose",
        "description": "Analyse the logs and return the root cause with explanations.",
        "method": "POST",
        "path": "/api/run/diagnose",
        "parameters": {"type": "object", "properties": _RUN_ID, "required": ["run_id"]},
    },
    {
        "name": "get_fix_plan",
        "description": "Return the proposed fix, its diff, risk and tests.",
        "method": "GET",
        "path": "/api/run/fix-plan",
        "parameters": {"type": "object", "properties": _RUN_ID, "required": ["run_id"]},
    },
    {
        "name": "approve_fix",
        "description": "Apply the patch, verify it and open the pull request. Requires an "
        "explicit spoken yes from the developer.",
        "method": "POST",
        "path": "/api/run/approve",
        "parameters": {
            "type": "object",
            "properties": {
                **_RUN_ID,
                "approved": {"type": "boolean"},
                "note": {"type": "string", "description": "What the developer said"},
            },
            "required": ["run_id", "approved"],
        },
    },
    {
        "name": "get_docs",
        "description": "Return the generated incident documentation and its summary.",
        "method": "GET",
        "path": "/api/run/docs",
        "parameters": {"type": "object", "properties": _RUN_ID, "required": ["run_id"]},
    },
    {
        "name": "explain_again",
        "description": "Re-explain the current root cause when the developer is lost.",
        "method": "POST",
        "path": "/api/voice/explain-again",
        "parameters": {"type": "object", "properties": _RUN_ID, "required": ["run_id"]},
    },
    {
        "name": "confirm_understanding",
        "description": "Record the developer's comfort check after an explanation.",
        "method": "POST",
        "path": "/api/voice/ack",
        "parameters": {
            "type": "object",
            "properties": {
                **_RUN_ID,
                "understood": {"type": "boolean"},
                "topic": {"type": "string"},
            },
            "required": ["run_id", "understood"],
        },
    },
]


def schema(base_url: str = "http://localhost:8000") -> list[dict]:
    return [{**tool, "url": base_url + tool["path"]} for tool in TOOLS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-schema", action="store_true")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    print(json.dumps(schema(args.base_url), indent=2))


if __name__ == "__main__":
    main()
