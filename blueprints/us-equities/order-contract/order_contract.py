#!/usr/bin/env python3
"""Validate and serialize an offline basic-equity intent. No broker transport.

``build_envelope`` is the pre-submission validation boundary an owned adapter
calls before it constructs an SDK request; it never constructs one itself."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import re
import sys

MAX_JSON_BYTES = 8192
MAX_NUMBER = Decimal("1000000000")  # Local representation cap, never a risk limit.
REQUIRED = frozenset({"symbol", "qty", "side", "type", "time_in_force", "client_order_id"})
ALLOWED = REQUIRED | {"limit_price", "order_class", "extended_hours"}


class ContractError(ValueError):
    """Invalid or unsupported offline intent; values are not echoed."""


def _number(value: object, field: str, fraction_digits: int = 4, whole_qty: bool = True) -> str:
    # Reject bool and Python float: a float may already have lost decimal intent.
    if type(value) is int:
        if not 0 < value <= 1000000000:
            raise ContractError(f"{field}: outside local numeric bounds")
        text = str(value)
    elif isinstance(value, Decimal):
        if (not value.is_finite() or not 0 < value <= MAX_NUMBER
                or not -fraction_digits <= value.as_tuple().exponent <= 9):
            raise ContractError(f"{field}: finite bounded decimal required")
        text = format(value, "f")  # Exact; no context-sensitive normalize/quantize.
    elif isinstance(value, str):
        text = value
    else:
        raise ContractError(f"{field}: decimal text, Decimal or integer required")
    if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,%d})?" % fraction_digits, text):
        raise ContractError(f"{field}: bounded unsigned decimal required")
    number = Decimal(text)
    if not number.is_finite() or not 0 < number <= MAX_NUMBER:
        raise ContractError(f"{field}: outside local numeric bounds")
    whole, _, fraction = text.partition(".")
    whole = whole.lstrip("0") or "0"
    fraction = fraction.rstrip("0")
    canonical = whole + ("." + fraction if fraction else "")
    if field == "qty" and fraction and whole_qty:
        raise ContractError("qty: only whole shares are supported")
    if field == "limit_price" and len(fraction) > (2 if number >= 1 else 4):
        raise ContractError("limit_price: unsupported price increment")
    return canonical


def _enum(value: object, allowed: tuple[str, ...], field: str) -> str:
    if type(value) is not str or value not in allowed:
        raise ContractError(f"{field}: unsupported value")
    return value


def canonicalize(value: object) -> dict:
    """Return a new offline envelope, never an SDK request or submit-ready client."""
    return build_envelope(value)


def build_envelope(value: object, *, fractional_sell_qty: bool = False,
                   extended_hours_allowed: bool = False) -> dict:
    """Pre-submission validation boundary; the envelope is never an SDK request.

    With the defaults it is exactly ``canonicalize``. An owned adapter may widen
    two policies explicitly: ``fractional_sell_qty`` admits a sell quantity with
    up to nine fractional digits (exact residual exits; buys stay whole shares),
    and ``extended_hours_allowed`` admits the literal boolean ``true``. Every
    other rule, including the limit price increment, is unchanged.
    """
    if type(value) is not dict:
        raise ContractError("intent: JSON object required")
    if any(type(key) is not str or key not in ALLOWED for key in value):
        raise ContractError("intent: unsupported or unknown field")
    if not REQUIRED.issubset(value):
        raise ContractError("intent: missing required field")
    symbol = value["symbol"]
    if type(symbol) is not str or not re.fullmatch(r"[A-Z]{1,5}(?:\.[A-Z])?", symbol):
        raise ContractError("symbol: outside local equity-symbol syntax")
    identifier = value["client_order_id"]
    if type(identifier) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", identifier):
        raise ContractError("client_order_id: outside local identifier syntax")
    kind = _enum(value["type"], ("market", "limit"), "type")
    if (kind == "limit") != ("limit_price" in value):
        raise ContractError("limit_price: required exactly for limit intents")
    extended_hours = value.get("extended_hours", False)
    if extended_hours is not False and not (extended_hours_allowed and extended_hours is True):
        raise ContractError("extended_hours: only false is supported")
    side = _enum(value["side"], ("buy", "sell"), "side")
    fractional = fractional_sell_qty is True and side == "sell"
    intent = {
        "symbol": symbol,
        "qty": _number(value["qty"], "qty", 9 if fractional else 4, not fractional),
        "side": side,
        "type": kind,
        "time_in_force": _enum(value["time_in_force"], ("day",), "time_in_force"),
        "client_order_id": identifier,
        "order_class": _enum(value.get("order_class", "simple"), ("simple",), "order_class"),
        "extended_hours": extended_hours,
    }
    if kind == "limit":
        intent["limit_price"] = _number(value["limit_price"], "limit_price")
    return {"schema_version": 1, "mode": "offline", "submission_enabled": False, "intent": intent}


def _unique_object(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ContractError("intent: duplicate JSON field")
        value[key] = item
    return value


def _invalid_constant(value: str):
    raise ContractError("intent: nonfinite JSON number")


def _json_number(text: str) -> Decimal:
    # Bound the lexical token before Decimal parses an attacker-sized exponent.
    if not re.fullmatch(r"[0-9]{1,10}(?:\.[0-9]{1,4})?", text):
        raise ContractError("intent: bounded plain JSON decimal required")
    return Decimal(text)


def loads(text: str) -> dict:
    """Parse bounded JSON exactly; duplicate keys and nonfinite numbers fail."""
    try:
        if type(text) is not str or len(text.encode("utf-8")) > MAX_JSON_BYTES:
            raise ContractError("intent: JSON input exceeds local size bound")
        value = json.loads(text, parse_float=_json_number, parse_int=_json_number, parse_constant=_invalid_constant,
                           object_pairs_hook=_unique_object)
        return canonicalize(value)
    except (ValueError, RecursionError, UnicodeError) as error:
        if isinstance(error, ContractError):
            raise
        raise ContractError("intent: invalid JSON") from None


def dumps(value: object) -> str:
    return json.dumps(canonicalize(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()  # No endpoint, account, submit, live or paper switch exists.
    try:
        text = sys.stdin.buffer.read(MAX_JSON_BYTES + 1).decode("utf-8")
        envelope = loads(text)
    except (ContractError, UnicodeError) as error:
        print(str(error) if isinstance(error, ContractError) else "intent: invalid UTF-8", file=sys.stderr)
        return 2
    print(json.dumps(envelope, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
