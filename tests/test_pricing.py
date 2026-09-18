import pytest

from devprod.sample_app import pricing


def order(**kwargs):
    base = {"order_id": "t-1", "items": [{"sku": "a", "qty": 2, "unit_price": 10.0}]}
    return pricing.Order(**{**base, **kwargs})


def test_healthy_order_prices():
    result = pricing.price_order(order(discount_rate=0.1))
    assert result["subtotal"] == 20.0
    assert result["total"] == 18.0


@pytest.mark.xfail(reason="fixed by the simulator's ZeroDivisionError fix plan", strict=False)
def test_full_discount_prices_to_zero():
    result = pricing.price_order(order(discount_rate=1.0))
    assert result["total"] == 0.0


@pytest.mark.xfail(reason="fixed by the simulator's KeyError fix plan", strict=False)
def test_unknown_currency_is_rejected():
    with pytest.raises(pricing.UnsupportedCurrencyError):
        pricing.to_usd(10.0, "INR")


@pytest.mark.xfail(reason="fixed by the simulator's RecursionError fix plan", strict=False)
def test_flaky_coupon_gives_up():
    assert pricing.redeem_coupon("FLAKY-1") == 0.0
