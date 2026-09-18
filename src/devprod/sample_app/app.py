"""The dummy service under test: a tiny order-pricing API."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import logging_setup
from .pricing import Order, UnsupportedCurrencyError, price_order

app = FastAPI(title="orders-service", version="0.1.0")


class OrderRequest(BaseModel):
    order_id: str
    items: list[dict]
    currency: str = "USD"
    discount_rate: float = 0.0
    coupon: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/orders/price")
def price(req: OrderRequest) -> JSONResponse:
    started = time.perf_counter()
    logging_setup.log(logging.INFO, "pricing order", order_id=req.order_id, currency=req.currency)
    try:
        result = price_order(Order(**req.model_dump()))
    except UnsupportedCurrencyError as exc:
        logging_setup.log(
            logging.WARNING, "rejected order", order_id=req.order_id, currency=req.currency
        )
        return JSONResponse(
            status_code=422, content={"error": "unsupported_currency", "detail": str(exc)}
        )
    except RecursionError as exc:
        logging_setup.log(
            logging.ERROR,
            "coupon redemption exhausted the stack",
            exc_info=(type(exc), exc, exc.__traceback__),
            order_id=req.order_id,
        )
        return JSONResponse(status_code=500, content={"error": "coupon_service_retry_storm"})
    except Exception as exc:  # surfaced to the simulator as a 500 with full context
        logging_setup.log(
            logging.ERROR,
            "pricing failed",
            exc_info=(type(exc), exc, exc.__traceback__),
            order_id=req.order_id,
            currency=req.currency,
            discount_rate=req.discount_rate,
        )
        return JSONResponse(
            status_code=500, content={"error": type(exc).__name__, "detail": str(exc)}
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logging_setup.log(
        logging.INFO, "pricing succeeded", elapsed_ms=elapsed_ms, **result
    )
    return JSONResponse(status_code=200, content={**result, "elapsed_ms": elapsed_ms})
