---
name: add-simulator-fault
description: Add a new failure scenario to the developer productivity simulator (fault, root cause knowledge, fix plan, test). Use when extending the demo with another bug class.
---

# Add a fault to the simulator

Four files change, in this order.

1. **Plant the bug** in `src/devprod/sample_app/` (usually `pricing.py`). It must be real
   code reachable from `POST /orders/price` — not a feature flag — so the traceback and the
   patch are genuine.

2. **Register the fault** in `src/devprod/simulator/faults.py`:

```python
"my_fault": Fault(
    id="my_fault",
    title="<what the developer sees>",
    instruction="<what the agent says it is about to do>",
    payload={...},                 # request that reaches the bug
    expected_error="MyError",      # exception type name
    hint="<one line cause>",
    tags=["..."],
),
```

3. **Teach the analyser** — add a `KNOWN_CAUSES["MyError"]` entry in
   `src/devprod/analysis/rca.py` with all three registers: `default`, `eli5` (analogy, no
   jargon), `researcher` (other reachable paths, trade-offs, what else breaks).

4. **Write the fix plan** — add `PLANS["MyError"]` in `src/devprod/fix/planner.py` with a
   `Patch(old=..., new=...)` whose `old` string matches the source byte for byte, plus
   `expected_status_after_fix` (200 for a real fix, 4xx when the correct behaviour is to
   reject the request).

Also update the `induce_error` enum in `src/devprod/voice/agent_tools.py`.

## Verify

```bash
python -m devprod.cli demo --fault my_fault
git checkout -- src/devprod/sample_app/pricing.py   # undo the applied patch
python -m pytest -q
```

`tests/test_flow.py::test_induce_and_diagnose` is parametrised — add the new fault id to
its `FAULTS` list.
