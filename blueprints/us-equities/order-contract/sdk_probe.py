#!/usr/bin/env python3
"""Reproduce SDK field loss and strict local rejection without a broker client."""
import hashlib
import importlib.metadata
import json
import sys

from order_contract import ContractError, canonicalize, dumps


def probe():
    blocked_events = []
    socket_constructors = []

    def prohibit_transport(event, args):
        if event == "socket.__new__":
            socket_constructors.append(event)
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                     "socket.sendto", "socket.sendmsg", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
            blocked_events.append(event)
            raise RuntimeError("offline probe forbids network and process transport")

    sys.addaudithook(prohibit_transport)
    from alpaca.trading.requests import LimitOrderRequest, OrderRequest, ReplaceOrderRequest

    basic = dict(symbol="SPY", qty="2", side="buy", type="limit", time_in_force="day",
                 limit_price="100.10", client_order_id="offline-example-001")
    basic_sdk = LimitOrderRequest(**basic).to_request_fields()
    cases = []
    for algorithm in ("DMA", "VWAP", "TWAP"):
        # Deliberately synthetic, not a provider-valid advanced instruction.
        raw = dict(basic, advanced_instructions={"algorithm": algorithm, "probe_only": "field-preservation"})
        serialized = LimitOrderRequest(**raw).to_request_fields()
        try:
            canonicalize(raw)
            boundary = "unexpectedly_accepted"
        except ContractError:
            boundary = "rejected_before_sdk"
        cases.append({"case": algorithm, "sdk_advanced_field_present": "advanced_instructions" in serialized,
                      "native_sdk_serialized": serialized, "boundary_result": boundary})
    negatives = {"unknown_field": dict(basic, unexpected="sentinel"),
                 "notional": dict(basic, notional="200.20"),
                 "network_endpoint": dict(basic, endpoint="https://example.invalid"),
                 "live_switch": dict(basic, live=True),
                 "nonfinite": dict(basic, qty="NaN"),
                 "python_float": dict(basic, limit_price=100.10),
                 "fractional_qty": dict(basic, qty="0.5"),
                 "subpenny": dict(basic, limit_price="100.101")}
    negative_results = {}
    for name, raw in negatives.items():
        try:
            canonicalize(raw)
            negative_results[name] = "unexpectedly_accepted"
        except ContractError:
            negative_results[name] = "rejected"
    serialized_unknown = LimitOrderRequest(**dict(basic, unexpected="sentinel")).to_request_fields()
    canonical = dumps(basic)
    return {
        "sdk": "alpaca-py", "version": importlib.metadata.version("alpaca-py"),
        "python_version": sys.version.split()[0],
        "scope": "Offline synthetic serialization and local validation; no provider-valid advanced fixture or wire acceptance.",
        "clients_constructed": 0, "orders_submitted": 0,
        "blocked_transport_audit_events": blocked_events,
        "socket_constructor_events": len(socket_constructors),
        "transport_guard": "Python audit hook blocks audited connect, DNS, datagram send and process launch; run in the documented network namespace. Socket construction alone is not a sent request.",
        "order_request_declares_advanced_instructions": "advanced_instructions" in OrderRequest.model_fields,
        "replace_request_declares_advanced_instructions": "advanced_instructions" in ReplaceOrderRequest.model_fields,
        "native_sdk_basic_serialized": basic_sdk,
        "native_sdk_unknown_field_present": "unexpected" in serialized_unknown,
        "advanced_cases": cases, "negative_cases": negative_results,
        "canonical_basic": json.loads(canonical),
        "canonical_utf8_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "accepted_offline_basic": True,
        "advanced_execution_accepted": False, "broker_execution_accepted": False,
    }


if __name__ == "__main__":
    result = probe()
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    passed = (all(c["boundary_result"] == "rejected_before_sdk" for c in result["advanced_cases"])
              and all(v == "rejected" for v in result["negative_cases"].values())
              and not result["blocked_transport_audit_events"])
    raise SystemExit(0 if passed else 2)
