# Offline Alpaca order-intent boundary

This small boundary closes the observed **silent field-loss** failure locally.
It rejects unsupported fields before they can enter `alpaca-py`, preserves exact
decimal text and produces a deterministic **offline envelope**. It has no SDK
dependency, client, endpoint, credentials, order submission, retry loop or broker
state. Passing this check establishes local input validity only.

The adaptive-paper `AlpacaPaperTransport` and the order-throughput
`AlpacaCapacityPort` now call `build_envelope()` before every alpaca-py submit
(see `../adaptive-paper/README-transport.md`, "Pre-submission order-contract
boundary"): the SDK request is built only from a validated envelope, and the
guarded HTTP session admits an order POST only when its serialized body equals
that envelope. Other adapters must call the boundary explicitly. Passing it is
still local input validity only; risk, asset/account, order-state and provider
acceptance remain separate. The envelope itself is never a submit-ready request.

`build_envelope(value, *, fractional_sell_qty=False, extended_hours_allowed=False)`
equals `canonicalize` with its defaults. An owned adapter may widen exactly two
policies: a sell quantity with up to nine fractional digits (exact residual
exits; buys stay whole shares) and the literal boolean `extended_hours: true`.
The envelope shape, `mode: offline` and `submission_enabled: false` are
unchanged. The [receipt](receipt.json) (2026-09-19) predates `build_envelope`;
its nine-test count is historical, and the widened policies have only local
synthetic test coverage.

## Supported local policy

- Create intents only: `symbol`, `qty`, `side`, `type`, `time_in_force`,
  `client_order_id`, plus `limit_price` exactly for limit intents.
- Market or limit; buy or sell; `day`; whole shares. Optional `order_class` must
  be `simple`, and optional `extended_hours` must be the literal boolean `false`.
- ASCII symbol syntax `[A-Z]{1,5}(\.[A-Z])?`; caller-supplied ID uses 1–128 ASCII
  letters/digits/underscore/dot/hyphen, beginning with a letter or digit. These
  intentionally narrow syntax policies do not prove an asset exists or is tradable.
- Positive plain decimal strings, integers or finite `Decimal` values; Python
  floats and booleans are rejected. JSON numeric literals are parsed exactly.
  Numeric strings/JSON literals reject exponent notation, signs, whitespace and
  more than four fractional digits. Decimal objects also have bounded exponents.
  Quantity and price are at most 1,000,000,000: a **local representation bound,
  not an approved position, capital or risk limit**. Quantity must be integral.
- Limit increments: at most two significant fractional digits for prices ≥1,
  four below 1. Trailing fractional zeros are removed without rounding. Input
  precision is bounded before normalization. [Alpaca price rules](https://docs.alpaca.markets/us/docs/orders-at-alpaca)
  support these increment checks, but do not establish broader order acceptance.
- Unknown fields, duplicate JSON keys, oversized input (>8,192 UTF-8 bytes),
  nonfinite numbers, fractional quantities, notional, bracket/stop/option orders,
  advanced instructions, account/transport switches and replace/cancel operations
  fail closed. Values are not echoed in errors.

The output always states `mode: offline` and `submission_enabled: false`.
Canonical JSON uses sorted keys and exact decimal strings. Its hash identifies
bytes, not a unique trading intent or an idempotency guarantee.

## Reproduce locally

From the repository root, use the existing locked SDK Python for the native
probe; system Python suffices for the contract and focused tests:

```sh
python3 blueprints/us-equities/order-contract/order_contract.py \
  < blueprints/us-equities/order-contract/basic-intent.json
python3 -m unittest tests.test_order_contract -v
bwrap --unshare-net --ro-bind / / --proc /proc --dev /dev --die-with-parent \
  "$SDK_PYTHON" blueprints/us-equities/order-contract/sdk_probe.py
```

`bwrap` provides Linux network-namespace isolation for the observed probe. This
is not macOS host acceptance. The probe also blocks audited connect/DNS/datagram
send and subprocess events. It imports request models and calls native
`LimitOrderRequest(...).to_request_fields()`; it never constructs `TradingClient`.
Do not substitute a network-enabled client command. The synthetic advanced
sentinels test preservation, not valid provider instructions.

Observed `alpaca-py==0.44.0` native basic serialization:

```json
{"client_order_id":"offline-example-001","limit_price":100.1,"qty":2.0,"side":"buy","symbol":"SPY","time_in_force":"day","type":"limit"}
```

The SDK uses float fields and drops `advanced_instructions` for DMA, VWAP and
TWAP sentinels, plus an unrelated unknown field. Our exact decimal envelope is
not round-tripped through those floats. All three advanced cases and eight
additional negatives were rejected locally. The final native probe exited 0;
nine focused tests passed on Python 3.12.3 and SDK Python 3.13.15.

An initial overbroad audit rejected urllib3's import-time IPv6 socket constructor
and made the probe exit 2 despite successful rejection cases. A retained stack
trace identified `_has_ipv6`; socket creation was not a sent request. The final
network-isolated run allowed construction, recorded one constructor and zero
blocked connect/DNS/send/process events. The [receipt](receipt.json) retains
this distinction and raw-output hashes.

## Upstream semantics and remaining gates

[Create](https://docs.alpaca.markets/us/reference/postorder) describes REST field
types and the 128-character client identifier; this contract deliberately
supports a smaller subset. Supplying an ID does not check its account-wide
uniqueness. [Lookup by client ID](https://docs.alpaca.markets/us/reference/getorderbyclientorderid)
is a reconciliation tool, not proof that blind resubmission after a timeout is safe.

[Replacement](https://docs.alpaca.markets/us/reference/patchorderbyorderid-1)
updates supplied attributes, but HTTP success does not prove replacement reached
the venue before a fill. Several pending states prohibit replacement. Non-IPO
notional orders cannot be replaced; fractional quantity changes are unsupported.
[Cancellation](https://docs.alpaca.markets/us/reference/deleteorderbyorderid-1)
returns 204 for accepted requests or 422 if no longer cancelable. A future
execution service must reconcile broker updates and race outcomes before treating
either operation as complete; neither is implemented here.

[Smart Router](https://docs.alpaca.markets/us/docs/alpaca-elite-smart-router)
documents an upstream advanced REST contract. DMA parameters cannot be replaced;
VWAP/TWAP replacements that include advanced instructions must include the whole
object. The paper service accepts these fields, but these advanced orders are
not simulated in paper.
Entitlement and actual execution semantics therefore remain unaccepted.

The [pinned source manifest](sources.json) records a real maintained alternative:
official JavaScript SDK package 4.0.2 exposes `advancedInstructions` through
`buildOrder`; generated create/replace serializers map it to
`advanced_instructions`. Python 0.44.0 and the selected Go request structs do not
declare that field. This is **source review, not a JavaScript installation or
wire test**, and does not justify changing languages or relaxing this boundary.
All three repositories' inspected licenses are Apache-2.0.

Future acceptance still needs exact SDK/wire preservation (including decimal
and time semantics), unknown-field rejection, documented provider capability,
account authorization, risk limits and order-state/recovery tests. No broker
orders, account keys, live configuration or advanced execution were enabled.
