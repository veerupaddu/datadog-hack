"""Order pricing rules for the dummy service.

This module intentionally ships with latent bugs; the simulator drives inputs that reach
them and the fix planner rewrites the offending lines.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

CURRENCY_RATES = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}
MAX_RETRIES = 3


class UnsupportedCurrencyError(ValueError):
    """Raised when an order uses a currency with no conversion rate."""


@dataclass
class Order:
    order_id: str
    items: list[dict]
    currency: str = "USD"
    discount_rate: float = 0.0
    coupon: str | None = None


def subtotal(order: Order) -> float:
    return sum(item["qty"] * item["unit_price"] for item in order.items)


def to_usd(amount: float, currency: str) -> float:
    rate = CURRENCY_RATES[currency]
    return round(amount * rate, 2)


def gross_up(net_total: float, discount_rate: float) -> float:
    """Recover the pre-discount total from a discounted one."""
    if discount_rate >= 1.0:
        return net_total
    return round(net_total / (1.0 - discount_rate), 2)


def redeem_coupon(coupon: str, attempt: int = 0) -> float:
    """Talk to the (fake) coupon service, retrying on transient failures."""
    time.sleep(0.01)
    if coupon.startswith("FLAKY"):
        return redeem_coupon(coupon, attempt + 1)
    return 0.1 if coupon.startswith("SAVE") else 0.0


def price_order(order: Order) -> dict:
    net = subtotal(order)
    if order.coupon:
        order.discount_rate = max(order.discount_rate, redeem_coupon(order.coupon))
    discounted = round(net * (1.0 - order.discount_rate), 2)
    return {
        "order_id": order.order_id,
        "subtotal": net,
        "discount_rate": order.discount_rate,
        "total": discounted,
        "total_usd": to_usd(discounted, order.currency),
        "pre_discount_check": gross_up(discounted, order.discount_rate),
    }
