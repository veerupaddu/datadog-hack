"""Step 6a: turn a root cause into a concrete, reviewable fix plan."""

from __future__ import annotations

import difflib
from dataclasses import asdict, dataclass

from ..analysis.rca import RootCause

TARGET = "src/devprod/sample_app/pricing.py"


@dataclass
class Patch:
    file: str
    old: str
    new: str

    def diff(self) -> str:
        return "".join(
            difflib.unified_diff(
                self.old.splitlines(keepends=True),
                self.new.splitlines(keepends=True),
                fromfile=f"a/{self.file}",
                tofile=f"b/{self.file}",
            )
        )


@dataclass
class FixPlan:
    title: str
    summary: str
    steps: list[str]
    risk: str
    tests: list[str]
    patch: Patch
    expected_status_after_fix: int

    def to_dict(self) -> dict:
        data = asdict(self)
        data["diff"] = self.patch.diff()
        return data

    def spoken(self) -> str:
        steps = " Then ".join(self.steps)
        return f"Here's what I'd change: {self.summary} {steps} Risk is {self.risk}. Shall I do it?"


_ZERO_DIV = Patch(
    file=TARGET,
    old='''def gross_up(net_total: float, discount_rate: float) -> float:
    """Recover the pre-discount total from a discounted one."""
    return round(net_total / (1.0 - discount_rate), 2)
''',
    new='''def gross_up(net_total: float, discount_rate: float) -> float:
    """Recover the pre-discount total from a discounted one."""
    if discount_rate >= 1.0:
        return net_total
    return round(net_total / (1.0 - discount_rate), 2)
''',
)

_KEY_ERROR = Patch(
    file=TARGET,
    old='''def to_usd(amount: float, currency: str) -> float:
    rate = CURRENCY_RATES[currency]
    return round(amount * rate, 2)
''',
    new='''def to_usd(amount: float, currency: str) -> float:
    rate = CURRENCY_RATES.get(currency)
    if rate is None:
        raise UnsupportedCurrencyError(f"unsupported currency {currency!r}")
    return round(amount * rate, 2)
''',
)

_RETRY = Patch(
    file=TARGET,
    old='''def redeem_coupon(coupon: str, attempt: int = 0) -> float:
    """Talk to the (fake) coupon service, retrying on transient failures."""
    time.sleep(0.01)
    if coupon.startswith("FLAKY"):
        return redeem_coupon(coupon, attempt + 1)
    return 0.1 if coupon.startswith("SAVE") else 0.0
''',
    new='''def redeem_coupon(coupon: str, attempt: int = 0) -> float:
    """Talk to the (fake) coupon service with a bounded, backing-off retry."""
    for attempt in range(MAX_RETRIES):
        time.sleep(0.01 * (attempt + 1))
        if not coupon.startswith("FLAKY"):
            return 0.1 if coupon.startswith("SAVE") else 0.0
    return 0.0
''',
)

PLANS: dict[str, FixPlan] = {
    "ZeroDivisionError": FixPlan(
        title="Guard gross_up against a full discount",
        summary="short-circuit the pre-discount check when the discount is 100%.",
        steps=[
            "add a discount_rate >= 1.0 guard in gross_up().",
            "re-run the failing order to confirm it returns 200.",
        ],
        risk="low — one pure function, no behaviour change below a 100% discount",
        tests=["tests/test_pricing.py::test_full_discount_prices_to_zero"],
        patch=_ZERO_DIV,
        expected_status_after_fix=200,
    ),
    "KeyError": FixPlan(
        title="Reject unsupported currencies with a 422 instead of crashing",
        summary="validate the currency before converting.",
        steps=[
            "look the rate up with .get() and raise UnsupportedCurrencyError when missing.",
            "let the API layer turn that into a 422 for the caller.",
        ],
        risk="low — turns a 500 into a typed client error; supported currencies unaffected",
        tests=["tests/test_pricing.py::test_unknown_currency_is_rejected"],
        patch=_KEY_ERROR,
        expected_status_after_fix=422,
    ),
    "RecursionError": FixPlan(
        title="Bound the coupon retry loop",
        summary="replace the unbounded recursion with MAX_RETRIES attempts and backoff.",
        steps=[
            "rewrite redeem_coupon() as a loop capped at MAX_RETRIES.",
            "fall back to no discount when the coupon service stays unavailable.",
        ],
        risk="medium — changes retry behaviour for every coupon redemption",
        tests=["tests/test_pricing.py::test_flaky_coupon_gives_up"],
        patch=_RETRY,
        expected_status_after_fix=200,
    ),
}


def plan_for(root_cause: RootCause) -> FixPlan | None:
    return PLANS.get(root_cause.error_type)
