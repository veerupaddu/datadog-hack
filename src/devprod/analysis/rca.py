"""Step 4b: turn a traceback plus logs into a root cause the agent can explain."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

FRAME_RE = re.compile(r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<func>\S+)')

# error_type -> (headline, researcher explanation)
KNOWN_CAUSES: dict[str, dict[str, str]] = {
    "ZeroDivisionError": {
        "headline": "gross_up() divides by (1 - discount_rate), which is zero on a 100% discount",
        "researcher": (
            "The bug is a domain-invariant violation: gross_up assumes discount_rate in [0, 1). "
            "Anything that can set the rate — coupons, admin overrides, promo stacking — can "
            "reach it, so validation belongs at the boundary (Order construction) as well as in "
            "gross_up. Related risk: floating point rates just under 1.0 produce enormous totals "
            "rather than an exception, which is worse because it fails silently downstream in "
            "invoicing and reporting."
        ),
    },
    "KeyError": {
        "headline": "to_usd() indexes CURRENCY_RATES with an unvalidated currency code",
        "researcher": (
            "Two separate defects: a missing input contract (currency should be validated at the "
            "API schema level, e.g. an enum) and unsafe lookup in the pricing core. Prefer failing "
            "at the edge with a 422 and keeping the core total. Also consider where rates come "
            "from — a static dict means new markets require a deploy; a cached rates provider with "
            "a fallback would remove this class of incident entirely."
        ),
    },
    "RecursionError": {
        "headline": "redeem_coupon() retries by recursing and never honours MAX_RETRIES",
        "researcher": (
            "Retry storms are a load-amplification risk, not just a crash: the same code path "
            "against a slow-but-alive dependency would multiply traffic instead of blowing the "
            "stack. The fix should be a bounded loop with exponential backoff and jitter, plus a "
            "circuit breaker, and the retry budget should be shared per request rather than "
            "per call site."
        ),
    },
}

GENERIC = {
    "headline": "unhandled exception in the pricing path",
    "researcher": "Inspect the deepest application frame in the traceback and the inputs "
    "logged alongside it to localise the invariant that was violated.",
}


@dataclass
class RootCause:
    error_type: str
    message: str
    file: str
    line: int
    function: str
    headline: str
    explanations: dict[str, str]
    evidence: list[str]
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)

    def explain(self, mode: str = "researcher") -> str:
        return self.explanations.get(mode, self.explanations["researcher"])


def _app_frame(traceback_text: str) -> tuple[str, int, str]:
    frames = [m.groupdict() for m in FRAME_RE.finditer(traceback_text or "")]
    app_frames = [f for f in frames if "devprod/sample_app" in f["file"]]
    chosen = (app_frames or frames or [{"file": "unknown", "line": "0", "func": "unknown"}])[-1]
    return chosen["file"], int(chosen["line"]), chosen["func"]


def diagnose(evidence: dict) -> RootCause:
    latest = evidence.get("latest_error") or {}
    error_type = latest.get("error_type", "UnknownError")
    traceback_text = evidence.get("traceback") or ""
    file, line, function = _app_frame(traceback_text)
    facts = KNOWN_CAUSES.get(error_type, GENERIC)
    confidence = 0.92 if error_type in KNOWN_CAUSES else 0.45
    evidence_lines = [
        f"{latest.get('error_type', 'error')}: {latest.get('error', '')}".strip(": "),
        f"failing frame: {function}() at {file}:{line}",
        f"{evidence.get('error_count', 0)} error log lines in this run",
    ]
    if latest.get("discount_rate") is not None:
        evidence_lines.append(f"discount_rate={latest['discount_rate']}")
    if latest.get("currency"):
        evidence_lines.append(f"currency={latest['currency']}")
    return RootCause(
        error_type=error_type,
        message=latest.get("error", ""),
        file=file,
        line=line,
        function=function,
        headline=facts["headline"],
        explanations={"researcher": facts["researcher"]},
        evidence=evidence_lines,
        confidence=confidence,
    )
