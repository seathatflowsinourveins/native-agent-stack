#!/usr/bin/env python3
"""Offline SDK serialization probe. Never constructs a client or sends an order."""
from __future__ import annotations

import importlib.metadata
import json


def preserved(expected: dict, serialized: dict) -> bool:
    """A missing or altered instruction fails closed; SDK presence is insufficient."""
    return serialized.get("advanced_instructions") == expected


def probe() -> dict:
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OrderRequest

    cases = []
    for algorithm in ("DMA", "VWAP", "TWAP"):
        # A serialization sentinel, not a provider-valid advanced-order fixture.
        # The SDK may drop it and leave a plausible ordinary order. Never submit.
        instructions = {"algorithm": algorithm, "probe_only": "offline-sentinel"}
        try:
            request = LimitOrderRequest(
                symbol="SPY", qty=1, side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY, limit_price=100,
                client_order_id="offline-capability-probe",
                advanced_instructions=instructions,
            )
            serialized = request.to_request_fields()
            cases.append({"algorithm": algorithm,
                          "outcome": "preserved" if preserved(instructions, serialized) else "dropped_or_changed",
                          "serialized": serialized})
        except (ValueError, TypeError) as error:
            cases.append({"algorithm": algorithm, "outcome": "rejected",
                          "error_type": type(error).__name__})
    return {
        "sdk": "alpaca-py", "version": importlib.metadata.version("alpaca-py"),
        "network_requests": 0, "clients_constructed": 0, "orders_submitted": 0,
        "scope": "Synthetic field-preservation probe; not a provider-valid advanced-order fixture, wire/API contract or entitlement test. Never submitted; do not reuse as an order adapter.",
        "advanced_instructions_declared": "advanced_instructions" in OrderRequest.model_fields,
        "cases": cases,
        "serialization_preserved": all(c["outcome"] == "preserved" for c in cases),
        "execution_accepted": False,
    }


if __name__ == "__main__":
    result = probe()
    print(json.dumps(result, indent=2))
    # Successful observation may report incompatibility. Do not use this as an order adapter.
    raise SystemExit(0 if result["serialization_preserved"] else 2)
