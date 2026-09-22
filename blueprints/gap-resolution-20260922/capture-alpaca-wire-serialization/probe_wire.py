#!/usr/bin/env python3
"""Extend blueprints/us-equities/order-contract/sdk_probe.py's network-isolated
pattern to capture the LITERAL JSON wire bytes alpaca-py 0.44.0's TradingClient
would send for qty/limit_price/notional edge cases.

Traced (not guessed) from installed alpaca-py 0.44.0 source at
<HOME>/.local/share/codex-ecosystem/tools/adaptive-paper-20260921/lib/python3.12/site-packages/alpaca:
  trading/client.py:99-100  data = order_data.to_request_fields(); self.post("/orders", data)
  common/rest.py:125        opts["json"] = data   (non-GET/DELETE)
  common/rest.py:195        self._session.request(method, url, **opts)
requests 2.34.2 (installed alongside) models.py:592:
  body = complexjson.dumps(json, allow_nan=False)
So the literal wire bytes for a submit_order call are exactly:
  json.dumps(order_data.to_request_fields(), allow_nan=False).encode("utf-8")
This script reproduces that exact call chain via requests.PreparedRequest.prepare_body
(pure local serialization, no I/O) instead of guessing at a private method name.
No TradingClient network method is invoked; the audit hook (copied from sdk_probe.py)
still blocks connect/DNS/socket/process events as defense in depth, and the whole
process is expected to run inside a network namespace with no route (bwrap --unshare-net).
Never supply real broker credentials: TradingClient is constructed only with the
placeholder strings "k"/"s" (rejected by the real API, never used to attempt a request).
"""
import decimal
import hashlib
import importlib.metadata
import json
import sys

import requests


def probe():
    blocked_events = []

    def prohibit_transport(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr",
                     "socket.sendto", "socket.sendmsg", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"}:
            blocked_events.append(event)
            raise RuntimeError("offline probe forbids network and process transport")

    sys.addaudithook(prohibit_transport)

    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    # Constructed only to exercise the identical local method (to_request_fields())
    # TradingClient.submit_order calls; never used to open a connection.
    client = TradingClient("k", "s", paper=True)
    assert not hasattr(client, "_prepare_order_data"), (
        "alpaca-py 0.44.0 has no _prepare_order_data method; submit_order calls "
        "order_data.to_request_fields() directly (verified against installed source)."
    )

    D = decimal.Decimal
    cases = {
        "basic_limit_int_qty": lambda: LimitOrderRequest(
            symbol="SPY", qty=2, limit_price=D("100.10"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "fractional_qty_decimal": lambda: LimitOrderRequest(
            symbol="SPY", qty=D("0.5"), limit_price=D("100.10"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "subpenny_limit_price": lambda: LimitOrderRequest(
            symbol="SPY", qty=1, limit_price=D("100.105"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "large_qty": lambda: LimitOrderRequest(
            symbol="SPY", qty=D("1000000"), limit_price=D("100.10"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "qty_python_float_input": lambda: LimitOrderRequest(
            symbol="SPY", qty=2.5, limit_price=100.10, side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "notional_only_market": lambda: MarketOrderRequest(
            symbol="SPY", notional=D("500.00"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "notional_subpenny": lambda: MarketOrderRequest(
            symbol="SPY", notional=D("500.005"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "zero_qty": lambda: LimitOrderRequest(
            symbol="SPY", qty=0, limit_price=D("100.10"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
        "negative_qty": lambda: LimitOrderRequest(
            symbol="SPY", qty=-1, limit_price=D("100.10"), side=OrderSide.BUY, time_in_force=TimeInForce.DAY),
    }

    results = {}
    for name, build in cases.items():
        entry = {}
        try:
            req = build()
        except Exception as exc:  # pydantic ValidationError or similar, at construction time
            entry["stage"] = "model_construction"
            entry["rejected"] = True
            entry["error_type"] = type(exc).__name__
            entry["error_str"] = str(exc)[:500]
            results[name] = entry
            continue
        try:
            fields = req.to_request_fields()
        except Exception as exc:
            entry["stage"] = "to_request_fields"
            entry["rejected"] = True
            entry["error_type"] = type(exc).__name__
            entry["error_str"] = str(exc)[:500]
            results[name] = entry
            continue
        entry["stage"] = "wire_body"
        entry["fields_dict"] = fields
        entry["fields_repr"] = {k: repr(v) for k, v in fields.items()}
        try:
            prepared = requests.PreparedRequest()
            # PreparedRequest.prepare() normally calls prepare_headers() before
            # prepare_body(); prepare_body() writes Content-Type into self.headers,
            # so headers must be a real mapping first (matches Session.prepare_request).
            prepared.prepare_headers({})
            # Exact call chain traced from alpaca-py TradingClient.post -> _request:
            # opts["json"] = data; self._session.request(method, url, **opts)
            # requests.sessions.Session.request builds a PreparedRequest via
            # Request(...).prepare(), whose prepare_body(json=...) computes:
            #   body = complexjson.dumps(json, allow_nan=False)
            prepared.prepare_body(data=None, files=None, json=fields)
            body_bytes = prepared.body
            if isinstance(body_bytes, str):
                body_bytes = body_bytes.encode("utf-8")
            entry["rejected"] = False
            entry["literal_wire_body_utf8"] = body_bytes.decode("utf-8")
            entry["literal_wire_body_sha256"] = hashlib.sha256(body_bytes).hexdigest()
            entry["literal_wire_body_byte_length"] = len(body_bytes)
            entry["content_type_header"] = dict(prepared.headers).get("Content-Type")
        except Exception as exc:
            entry["stage"] = "wire_serialization"
            entry["rejected"] = True
            entry["error_type"] = type(exc).__name__
            entry["error_str"] = str(exc)[:500]
        results[name] = entry

    return {
        "sdk": "alpaca-py", "version": importlib.metadata.version("alpaca-py"),
        "requests_version": importlib.metadata.version("requests"),
        "python_version": sys.version.split()[0],
        "scope": ("Offline literal-wire-byte capture via requests.PreparedRequest.prepare_body "
                  "(the identical function alpaca-py's own _request/post path invokes for non-GET/DELETE "
                  "methods); TradingClient constructed with placeholder credentials 'k'/'s' only to confirm "
                  "no alternate private serialization method exists; no HTTP connection is opened, no "
                  "provider-valid order is claimed accepted."),
        "clients_constructed": 1, "orders_submitted": 0,
        "blocked_transport_audit_events": blocked_events,
        "cases": results,
    }


if __name__ == "__main__":
    result = probe()
    print(json.dumps(result, indent=2, sort_keys=True))
    # Sanity: every case must have reached a terminal, recorded stage.
    ok = all("stage" in v for v in result["cases"].values()) and not result["blocked_transport_audit_events"]
    raise SystemExit(0 if ok else 2)
