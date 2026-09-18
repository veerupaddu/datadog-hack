"""Catalog of failures the developer can induce on the dummy service."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Fault:
    id: str
    title: str
    instruction: str
    payload: dict
    expected_error: str
    hint: str
    target_file: str = "src/devprod/sample_app/pricing.py"
    tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "instruction": self.instruction,
            "expected_error": self.expected_error,
            "tags": self.tags,
        }


HEALTHY_PAYLOAD = {
    "order_id": "ord-healthy",
    "items": [{"sku": "kb-1", "qty": 2, "unit_price": 49.5}],
    "currency": "USD",
    "discount_rate": 0.1,
}

FAULTS: dict[str, Fault] = {
    "divide_by_zero_discount": Fault(
        id="divide_by_zero_discount",
        title="100% discount blows up the pre-discount check",
        instruction="Price an order with a full (100%) discount coupon.",
        payload={
            "order_id": "ord-zero-div",
            "items": [{"sku": "kb-1", "qty": 1, "unit_price": 120.0}],
            "currency": "USD",
            "discount_rate": 1.0,
        },
        expected_error="ZeroDivisionError",
        hint="gross_up() divides by (1 - discount_rate), which is 0 at a 100% discount.",
        tags=["math", "edge-case"],
    ),
    "missing_currency_key": Fault(
        id="missing_currency_key",
        title="Unsupported currency raises KeyError",
        instruction="Price an order in a currency the rate table does not know (INR).",
        payload={
            "order_id": "ord-inr",
            "items": [{"sku": "kb-1", "qty": 3, "unit_price": 20.0}],
            "currency": "INR",
            "discount_rate": 0.0,
        },
        expected_error="KeyError",
        hint="to_usd() indexes CURRENCY_RATES directly instead of validating the currency.",
        tags=["input-validation"],
    ),
    "coupon_retry_storm": Fault(
        id="coupon_retry_storm",
        title="Flaky coupon service triggers an unbounded retry",
        instruction="Price an order using a coupon the coupon service keeps failing on.",
        payload={
            "order_id": "ord-flaky",
            "items": [{"sku": "kb-1", "qty": 1, "unit_price": 75.0}],
            "currency": "USD",
            "coupon": "FLAKY-42",
        },
        expected_error="RecursionError",
        hint="redeem_coupon() recurses on every failure and never honours MAX_RETRIES.",
        tags=["resilience", "retries"],
    ),
}


def get(fault_id: str) -> Fault:
    if fault_id not in FAULTS:
        raise KeyError(f"unknown fault {fault_id!r}; known: {sorted(FAULTS)}")
    return FAULTS[fault_id]


def catalog() -> list[dict]:
    return [f.as_dict() for f in FAULTS.values()]
