"""Headless walk through all eight steps — useful as a smoke test."""

from __future__ import annotations

import argparse
import json

from .orchestrator import orchestrator


def demo(fault: str, approve: bool = True) -> dict:
    state = orchestrator.start()
    run_id = state.run_id
    orchestrator.induce(run_id, fault)
    orchestrator.collect(run_id)
    orchestrator.diagnose(run_id)
    orchestrator.set_mode(run_id, "eli5")
    orchestrator.acknowledge(run_id, understood=True, topic="root cause")
    if approve:
        orchestrator.approve(run_id, approved=True, note="cli demo")
    return orchestrator.get(run_id).public()


def main() -> None:
    parser = argparse.ArgumentParser(prog="devprod")
    sub = parser.add_subparsers(dest="command", required=True)
    demo_cmd = sub.add_parser("demo", help="run the full loop headless")
    demo_cmd.add_argument("--fault", default="divide_by_zero_discount")
    demo_cmd.add_argument("--no-approve", action="store_true")
    demo_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = demo(args.fault, approve=not args.no_approve)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return
    for event in result["events"]:
        print(f"[{event['step']:<11}] {event['message']}")
    print("\nPR:", (result.get("pr") or {}).get("url"))
    print("Doc:", result.get("doc_path"))
    print("\nSummary:\n" + (result.get("summary") or ""))


if __name__ == "__main__":
    main()
