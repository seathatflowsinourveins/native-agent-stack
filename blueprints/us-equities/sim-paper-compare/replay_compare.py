#!/usr/bin/env python3
"""Replay a retained adaptive-paper trial's order decisions through NautilusTrader's
BacktestEngine, fed with historical Alpaca SIP quotes, and compare simulated fills
against the trial's paper fills.

  python replay_compare.py \
    --trial ../adaptive-paper/trials/20260923g-main-passed \
    --env-file "$PAPER_ENV_FILE" \
    --pages "$PRIVATE_CACHE_DIR/pages" \
    --out "$PRIVATE_CACHE_DIR/run" \
    --receipt receipts/20260923g-main-passed.json

Data fetch is GET-only against the existing Alpaca data path (SIP feed), reusing the
mover-early-entry `Fetcher` page-retention pattern: every response is kept gzip'd with
a sha256 ledger under --pages, and --replay re-derives the same run from those pages
without a new network request (and without opening any credential file -- see main()).
Replay uses the same fee/fill-model configuration as the accepted baseline in
engine-nautilus/equity-replay (native default `FillModel`, `FixedFeeModel`,
`book_type=L1_MBP`): Alpaca equities are commission-free, and the default fill model
matches limit orders against the fed L1 quote book with no synthetic slippage or
partial-fill assumption at zero latency.

This is a single trial with five orders (four filled, one canceled). It measures
paper/simulated fill agreement for that one window, at a declared latency-sensitivity
sweep (see LATENCY_SWEEP_MS). It is not a fill-rate or slippage calibration and must
not be read as one.

Two behaviors of the pinned engine (nautilus_trader==2.0.0rc5) materially affect how
the latency sweep's numbers must be read; both are disclosed rather than hidden:

1. **StaticLatencyModel does not guarantee matching at exactly submit + latency,
   and there are exactly two kinds of eligible settlement event -- not just any
   event on another instrument.** A deferred (latency-delayed) command settles at
   the first of: (a) an event on *that order's own instrument* (its own next
   quote -- this is what a sparse-quote symbol falls back to), or (b) *any* due
   clock timer processed by the engine, from *any* source, including one with no
   order effect at all -- the pinned engine's `advance_time_impl` collects every
   due timer at each processed event and settles *all* instruments' outstanding
   deferred commands together at that point (see `crates/backtest/src/engine.rs`
   L1559-1585 for timer collection across the whole engine and L1716-1747 for
   command processing at that point, commit
   1b0a49d2792a9432a3aca3fcb617ce7a630d905e of
   https://github.com/nautechsystems/nautilus_trader). Concretely (all verified
   on the pinned runtime): order A (quotes at 0ms/100ms) submitted at 10ms with
   20ms latency (modeled arrival 30ms) fills at **100ms** (its own next quote,
   trigger (a)) if order B (a different instrument) merely *has a quote* at 50ms
   with no order of its own -- **a plain market-data quote for a different
   instrument, alone, does not settle A**, since it is neither A's own instrument
   nor a timer. It instead fills at **50ms** if order B is *submitted* at 50ms
   (B's own decision timer, trigger (b)), and fills at **50ms** even with no
   order B at all, given only a bare no-op clock timer scheduled at 50ms with no
   order effect whatsoever -- confirming (b) is genuinely "any due timer," not
   specifically an order-command one. Matching happens at the first settlement
   event *at or after* submit + latency for that order, whichever trigger reaches
   it first, and always against the book as of that settlement instant, not a
   book frozen at exactly submit + latency. When quotes for a symbol are sparse
   and no timer intervenes first, the actual match can land well after the
   modeled arrival instant purely from that symbol's own quotes -- trigger (a) --
   which is exactly what produces order 3's lag in the retained receipt: it fills
   266.9ms after its modeled 5ms arrival, and 466.4ms after its modeled 650ms
   arrival, because no earlier timer happened to intervene and no GOOGL quote
   arrived any sooner. One consequence: the fill-price/fill-time columns at a
   given sweep latency are not a clean function of that latency alone. This is
   disclosed here rather than worked around with synthetic arrival-time wakeups,
   which would need their own validation against sparse-quote symbols and
   multi-instrument settlement interaction.
2. **The declared per-order marketable-window boundary (e.g. "order 4 stops being
   marketable at submit + 69.273ms", derived directly from the fetched SIP quotes) is
   corroborating evidence, not the reported flip point.** The receipt's
   `latency_sensitivity_sweep.flip_bisections` reports the actual bisected fill/
   no-fill boundary from re-running `run_replay` at that resolution (to 1us), which is
   the number that should be cited for "where the outcome changes."
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTIVE_PAPER = HERE.parents[0] / "adaptive-paper"
DATA = "https://data.alpaca.markets"
UTC = timezone.utc
VENUE_NAME = "SIM"
FILL_MODEL_NOTE = ("native default nautilus_trader.execution.FillModel(); matches limit orders "
                    "against the fed L1 top-of-book quotes deterministically (no probabilistic "
                    "slippage or partial-fill draw), the same baseline configuration used by "
                    "engine-nautilus/equity-replay's zero-fee case")
DEFAULT_ORDER_TIMEOUT_SECONDS = 10  # only used when no config match and no recorded cancel request exist
LATENCY_SWEEP_MS = (0, 5, 50, 70, 100, 250, 650, 1000)


# ---------------------------------------------------------------------------
# Small helpers (timestamps, hashing, JSON I/O)
# ---------------------------------------------------------------------------

def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_path(path: Path) -> str:
    return digest_bytes(Path(path).read_bytes())


def chmod_private_dir(path: Path) -> None:
    """mkdir's `mode=` argument is masked by the process umask; chmod explicitly
    so private cache/output directories are 0700 regardless of the caller's umask."""
    os.chmod(path, 0o700)


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")
    os.chmod(path, 0o600)


_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(?:Z|\+00:00)")


def ts_ns(value: str) -> int:
    """Parse an RFC3339 UTC timestamp (Alpaca's `Z` form or the broker readback's
    `+00:00` form) to integer nanoseconds, without floating-point rounding. The
    `Z`-only regex is adapted from alpaca-historical/collect.py; the `+00:00`
    alternative is required by the retained trial's broker-orders.json."""
    match = _TS_RE.fullmatch(value)
    if not match:
        raise ValueError(f"invalid_timestamp:{value!r}")
    parsed = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86400 + delta.seconds) * 10**9 + int((match[2] or "").ljust(9, "0"))


def ns_to_iso(value: int) -> str:
    seconds, ns = divmod(value, 10**9)
    return datetime.fromtimestamp(seconds, UTC).strftime("%Y-%m-%dT%H:%M:%S") + f".{ns:09d}Z"


def epoch_seconds_to_ns(value: float) -> int:
    """Host-clock float seconds (paper-output.json's `requests[].timestamp`) to integer
    nanoseconds. The float carries microsecond resolution in the source, so round to
    the nearest microsecond before scaling to avoid spurious sub-microsecond noise."""
    return int(round(value * 1e6)) * 1000


def bps(sim_price, paper_price):
    if sim_price is None or paper_price is None or paper_price == 0:
        return None
    return float((Decimal(str(sim_price)) / Decimal(str(paper_price)) - 1) * 10000)


def signed_slippage_bps(side, fill_price, limit_price):
    """Side-aware slippage of a fill against its limit price, in bps, where positive
    always means worse for the trader (paid more on a BUY, received less on a SELL)."""
    if fill_price is None or limit_price is None:
        return None
    limit_dec = Decimal(str(limit_price))
    if limit_dec == 0:
        return None
    raw = (Decimal(str(fill_price)) - limit_dec) / limit_dec * 10000
    return float(raw if side == "BUY" else -raw)


# ---------------------------------------------------------------------------
# GET with page retention/replay (adapted from mover-early-entry/mover_scan.py's
# Fetcher; reimplemented locally to avoid pulling that module's numpy/rules/
# sessions_io dependency chain into the pinned Nautilus-only runtime).
# ---------------------------------------------------------------------------

def req_key(path: str, params: dict) -> str:
    return hashlib.sha256((path + "?" + json.dumps(params, sort_keys=True)).encode()).hexdigest()[:32]


class PageFetcher:
    """GET-with-retention fetcher. `--replay` never opens the ledger file for
    writing and never requires headers/credentials; every page it serves in replay
    mode must already be present, keyed by request, in the retained page cache.
    `page_events` records, per served page, whether it came from `network` or
    `cache`, so replay reproducibility claims are backed by per-page evidence
    rather than an aggregate statement."""

    def __init__(self, pages: Path, headers=None, replay: bool = False):
        self.pages, self.headers, self.replay = Path(pages), headers, replay
        self.ledger = {}
        self.page_events: list[dict] = []
        lpath = self.pages / "ledger.jsonl"
        if lpath.exists():
            for line in lpath.read_text().splitlines():
                rec = json.loads(line)
                self.ledger[rec["key"]] = rec
        if not replay:
            self.pages.mkdir(parents=True, exist_ok=True)
            chmod_private_dir(self.pages)

    @property
    def from_cache(self) -> int:
        return sum(1 for e in self.page_events if e["source"] == "cache")

    @property
    def from_network(self) -> int:
        return sum(1 for e in self.page_events if e["source"] == "network")

    def get(self, base: str, path: str, params: dict):
        token = None
        while True:
            q = dict(params, **({"page_token": token} if token else {}))
            key = req_key(base + path, q)
            if self.replay and key not in self.ledger:
                raise SystemExit(f"replay requested but no retained page for {path} (key {key}); "
                                  f"re-run without --replay once to populate the page cache")
            if self.replay or key in self.ledger:
                rec = self.ledger[key]
                raw = gzip.decompress((self.pages / rec["file"]).read_bytes())
                if digest_bytes(raw) != rec["sha256"]:
                    raise SystemExit(f"page hash mismatch {rec['file']}")
                status = rec["status"]
                self.page_events.append({"key": key, "source": "cache"})
            else:
                url = base + path + "?" + urllib.parse.urlencode(q)
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers=self.headers), timeout=30) as r:
                        raw, status = r.read(), r.status
                except urllib.error.HTTPError as exc:
                    raw, status = exc.read() or b"{}", exc.code
                name = f"{key}.json.gz"
                with gzip.open(self.pages / name, "wb", compresslevel=6) as f:
                    f.write(raw)
                rec = {"key": key, "file": name, "path": path, "status": status,
                       "sha256": digest_bytes(raw), "bytes": len(raw)}
                self.ledger[key] = rec
                # Opened and closed per write (not held open for the fetcher's lifetime).
                with (self.pages / "ledger.jsonl").open("a") as lf:
                    lf.write(json.dumps(rec) + "\n")
                self.page_events.append({"key": key, "source": "network"})
            if status != 200:
                raise SystemExit(f"GET {path} returned {status}")
            body = json.loads(raw)
            yield body
            token = body.get("next_page_token") if isinstance(body, dict) else None
            if not token:
                return


# ---------------------------------------------------------------------------
# Paper trial parsing (pure, offline-testable)
# ---------------------------------------------------------------------------

def load_paper_orders(broker_orders: dict) -> list[dict]:
    """Normalize broker-orders.json's read-only order readback into the fields
    needed to replay decisions: symbol, side, qty, order type, limit price and
    timestamps. Raises on anything the replay cannot faithfully reconstruct: a
    non-limit order type, a time-in-force other than DAY (the replay always
    submits TimeInForce.DAY), or a fractional quantity (refused, not truncated)."""
    orders = []
    for raw in broker_orders["orders"]:
        if raw["type"] != "limit":
            raise ValueError(f"unsupported_order_type:{raw['type']}")
        tif = raw["time_in_force"].upper()
        if tif != "DAY":
            raise ValueError(f"unsupported_time_in_force:{tif}")
        qty_dec = Decimal(raw["qty"])
        if qty_dec != qty_dec.to_integral_value():
            raise ValueError(f"fractional_qty_not_supported:{raw['qty']}")
        filled_qty_dec = Decimal(raw["filled_qty"])
        if filled_qty_dec != filled_qty_dec.to_integral_value():
            raise ValueError(f"fractional_filled_qty_not_supported:{raw['filled_qty']}")
        orders.append({
            "client_order_id": raw["client_order_id"],
            "symbol": raw["symbol"],
            "side": raw["side"].upper(),
            "qty": int(qty_dec),
            "limit_price": str(Decimal(raw["limit_price"])),
            "time_in_force": tif,
            "status": raw["status"],
            "filled_qty": int(filled_qty_dec),
            "filled_avg_price": None if raw["filled_avg_price"] in (None, "None") else str(Decimal(raw["filled_avg_price"])),
            "submitted_at_ns": ts_ns(raw["submitted_at"]),
            "filled_at_ns": ts_ns(raw["filled_at"]) if raw.get("filled_at") else None,
        })
    orders.sort(key=lambda o: o["submitted_at_ns"])
    return orders


def parse_cancel_request_ns(paper_output: dict) -> list[int]:
    """Cancel-request host-clock timestamps recorded in paper-output.json's
    `requests` log, sorted ascending. These are the runner's own cancel-submit
    instants -- not a derived/approximated time."""
    return sorted(epoch_seconds_to_ns(r["timestamp"]) for r in paper_output.get("requests", [])
                  if r.get("kind") == "cancel")


def resolve_order_timeout_seconds(ingest_receipt: dict) -> tuple[int, str]:
    """Find the adaptive-paper config file whose sha256 matches this trial's
    ingest-receipt config_sha256 and read its order_timeout_seconds, so the
    fallback cancel time (submit + timeout) uses the config this trial actually
    ran with, not an assumed constant. Falls back to DEFAULT_ORDER_TIMEOUT_SECONDS
    with an explicit "source" marker if no config file matches."""
    config_sha256 = ingest_receipt.get("config_sha256")
    if config_sha256:
        for cfg_path in sorted(ADAPTIVE_PAPER.glob("config*.json")):
            if cfg_path.is_file() and digest_path(cfg_path) == config_sha256:
                cfg = json.loads(cfg_path.read_text())
                if "order_timeout_seconds" in cfg:
                    return int(cfg["order_timeout_seconds"]), f"matched_config:{cfg_path.name}"
    return DEFAULT_ORDER_TIMEOUT_SECONDS, "default_fallback_no_config_match"


def _terminal_at_ns(order: dict):
    """When `order` stops being a plausible target for an unattributed cancel
    request, or None if it never does (within what this replay can determine).
    A canceled order's true cancel instant is exactly what resolve_cancel_timestamps
    is solving for, so a canceled order is *never* treated as terminal here -- it
    remains open until the algorithm resolves it. A filled order is terminal at its
    reported `filled_at_ns`; if that is unknown (fractional/synthetic test fixtures
    only -- real trial data always has it, see load_paper_orders), it is treated
    conservatively as terminal immediately at submission, since we have no evidence
    it was ever open long enough to plausibly race a cancel."""
    if order["status"] == "canceled":
        return None
    return order["filled_at_ns"] if order["filled_at_ns"] is not None else order["submitted_at_ns"]


def _is_open_at(order: dict, at_ns: int) -> bool:
    if order["submitted_at_ns"] > at_ns:
        return False
    terminal_ns = _terminal_at_ns(order)
    return terminal_ns is None or terminal_ns > at_ns


def resolve_cancel_timestamps(paper_orders: list[dict], paper_output: dict, order_timeout_seconds: int) -> dict:
    """Resolve each canceled paper order's actual cancel time, in priority order:
    (1) a recorded cancel request in paper-output.json's `requests` log, matched to
    canceled orders by open-order uniqueness (below); (2) submitted_at +
    order_timeout_seconds, the runner's own cancel-on-timeout rule, used whenever
    (1) does not hold. Both branches use a real, declared, non-negotiated cancel
    instant -- never a successor order's submit time.

    `requests[]` carries no client_order_id and no symbol (adaptive-paper/runner.py's
    `before_request()` records only `{"timestamp": ..., "kind": ...}`), so a cancel
    request cannot be attributed to a specific order directly. The sound rule used
    here: a cancel request at time T is attributed to order O only if O is the
    *unique* order that is open (submitted, and not yet terminal -- see
    `_is_open_at`) across the *entire trial* at T, and O is one of the trial's
    canceled orders. If zero or more than one order is open at T (including the
    tied-input-order case: two same-symbol orders both open at T, one eventually
    filled and one eventually canceled -- the correct outcome, "ambiguous", must not
    depend on which one happens to sort first), or a request maps to an order that
    isn't a canceled order, or two requests map to the same order, or any canceled
    order is left without a match, the recorded log is refused *in its entirety*
    (falling back to `submit + order_timeout_seconds` for every canceled order in
    the trial) rather than guessed at per-order. This correctly accepts an
    unambiguous cross-symbol case (a canceled order's own symbol has no other open
    order at cancel time, even if an unrelated, already-resolved order of a
    different symbol was submitted in between) and correctly refuses a genuinely
    ambiguous one (more than one order, of any symbol, still open at the cancel
    instant) -- see tests.test_sim_paper_compare.CancelTimestampResolutionTests for
    both cases.

    Clock provenance and uncertainty: `submitted_at`/cancel-fallback timing use the
    broker's own reported clock (Alpaca `submitted_at`); the recorded cancel request
    timestamp is the adaptive-paper runner's local host clock, captured just before
    the cancel request is sent, not Alpaca's received-at time. For this trial the
    host clock read +28.0 to +40.8ms ahead of the broker's own submit timestamps
    (measured by comparing each order's `submitted_at` to its corresponding host
    `requests[]` submit entry) -- and because the host timestamp is captured *before*
    network send while the broker timestamp is captured *after* it receives the
    request, this measured gap is a **lower bound** on the true clock-source offset,
    not an upper one: the true offset is at least +28.0 to +40.8ms and could be
    larger by however much network/processing time separates those two capture
    points. This is small relative to this trial's ~10s cancel timeout but is not
    negligible next to sub-100ms marketable windows in general. Since the host
    clock leads the broker clock, the broker-clock instant corresponding to a
    recorded (host-clock) cancel request is *earlier*, not later, than the raw
    number used here. This receipt is not sensitive to that uncertainty (no
    marketable order-4 quote exists in the interval from submit+80ms to the
    recorded cancel time + 1.1s, i.e. shifting the cancel instant earlier within
    the plausible clock-offset range does not change the outcome here), but a
    future trial with a marketable quote near a cancel boundary could flip on this
    offset -- call this out per trial, don't assume it away. Alpaca SIP quote
    timestamps and Alpaca's own broker clock are a third, separate clock source;
    their mutual agreement is not established by this replay and is not assumed."""
    canceled = [o for o in paper_orders if o["status"] == "canceled"]
    canceled_ids = {o["client_order_id"] for o in canceled}
    cancel_reqs = parse_cancel_request_ns(paper_output)
    resolved = {}
    use_recorded = bool(canceled) and len(canceled) == len(cancel_reqs)
    pairing: dict[str, int] = {}
    if use_recorded:
        # Process requests in chronological order: once a *canceled* order is
        # resolved by an earlier request, it must be treated as terminal (at its
        # own resolved cancel instant) when evaluating openness for any *later*
        # request -- otherwise a canceled order that was already resolved would
        # incorrectly still count as "open indefinitely" against a later,
        # unrelated request, causing a false ambiguity. This override only ever
        # applies to canceled-status orders: a filled order's openness always
        # comes from its own `filled_at_ns` regardless of `pairing`, so an
        # erroneous match to a filled order here can never corrupt a later
        # iteration's uniqueness check.
        for cancel_ns in sorted(cancel_reqs):
            def is_open_given_pairing(o, at_ns=cancel_ns):
                if o["status"] == "canceled" and o["client_order_id"] in pairing:
                    return pairing[o["client_order_id"]] > at_ns
                return _is_open_at(o, at_ns)

            open_orders = [o for o in paper_orders if is_open_given_pairing(o)]
            if len(open_orders) != 1:
                use_recorded = False
                break
            pairing[open_orders[0]["client_order_id"]] = cancel_ns
        # A single final check replaces separate per-request "is this a canceled
        # order" / "is this target already paired" guards: those are provably
        # subsumed by requiring the accumulated pairing keys to equal canceled_ids
        # exactly -- any request that matched a non-canceled order, or two
        # requests that matched the same order, would leave `pairing`'s key set
        # unequal to `canceled_ids` (either an extra non-canceled key, or fewer
        # distinct keys than canceled orders), which this catches regardless.
        if use_recorded and set(pairing) != canceled_ids:
            use_recorded = False
    if use_recorded:
        for order in canceled:
            resolved[order["client_order_id"]] = {"cancel_ts_ns": pairing[order["client_order_id"]],
                                                    "source": "recorded_cancel_request"}
    else:
        source = ("submit_plus_order_timeout_seconds" if not canceled or len(canceled) != len(cancel_reqs)
                  else "submit_plus_order_timeout_seconds_ambiguous_recorded_match_refused")
        for order in canceled:
            resolved[order["client_order_id"]] = {
                "cancel_ts_ns": order["submitted_at_ns"] + order_timeout_seconds * 10**9,
                "source": source,
            }
    return resolved


def clock_provenance(paper_orders: list[dict], paper_output: dict) -> dict:
    """Measured host-clock-vs-broker-clock offset for this trial's submit requests
    (see resolve_cancel_timestamps' docstring for why this matters): host request
    timestamp minus the broker's own `submitted_at`, per order, in milliseconds.

    Pairing is chronological-order (both sides sorted by time), and is reported
    *only* when the counts agree (`counts_match`). When they do not, correspondence
    between the two lists cannot be established at all -- a truncated zip of two
    differently-ordered/differently-sized lists produces numbers that look like
    measurements but pair unrelated events (a dropped host entry can shift every
    later pairing by one position, producing offsets of the wrong order of
    magnitude entirely -- observed as large as ~195 seconds in a constructed test
    case). Rather than report those, `host_minus_broker_submit_offset_ms` is `null`
    with an explicit `host_minus_broker_submit_offset_unavailable_reason` whenever
    `counts_match` is false."""
    orders_sorted = sorted(paper_orders, key=lambda o: o["submitted_at_ns"])
    submit_host_ns = sorted(r["timestamp"] for r in paper_output.get("requests", []) if r.get("kind") == "submit")
    counts_match = len(submit_host_ns) == len(orders_sorted)
    if counts_match:
        offsets_ms = [(epoch_seconds_to_ns(host_s) - order["submitted_at_ns"]) / 1e6
                      for order, host_s in zip(orders_sorted, submit_host_ns)]
        unavailable_reason = None
    else:
        offsets_ms = None
        unavailable_reason = (f"submit request count ({len(submit_host_ns)}) does not match order count "
                               f"({len(orders_sorted)}); correspondence between the two lists cannot be "
                               f"established, so no offsets are reported (a truncated pairing would not be "
                               f"a valid incomplete measurement -- see docstring).")
    return {
        "submit_clock_source": "broker-reported (Alpaca order `submitted_at`)",
        "cancel_clock_source": "host clock, captured just before send in adaptive-paper/runner.py's "
                                "before_request() (no client_order_id recorded alongside it)",
        "sip_quote_clock_source": "Alpaca SIP feed timestamps, a third clock whose agreement with either "
                                   "the host clock or the broker clock is not established by this replay",
        "counts_match": counts_match,
        "host_minus_broker_submit_offset_ms": offsets_ms,
        "host_minus_broker_submit_offset_ms_range": [min(offsets_ms), max(offsets_ms)] if offsets_ms else None,
        "host_minus_broker_submit_offset_unavailable_reason": unavailable_reason,
        "host_minus_broker_submit_offset_is_lower_bound": True if counts_match else None,
        "host_minus_broker_submit_offset_note": "host timestamp is captured before network send, broker "
                                                 "timestamp after receipt, so this measured gap understates "
                                                 "(is a lower bound on) the true clock-source offset.",
    }


def build_decisions(paper_orders: list[dict], cancel_resolution: dict | None = None) -> list[dict]:
    """Turn the paper order sequence into submit/cancel decisions. A canceled
    order's cancel decision is timed at its resolved cancel timestamp (see
    resolve_cancel_timestamps) when one is supplied; a canceled order with no
    entry in `cancel_resolution` gets no cancel decision at all (it is left open
    for the strategy's on_stop() end-of-window cleanup) rather than an inferred
    successor-order time."""
    cancel_resolution = cancel_resolution or {}
    decisions = [{"ts_ns": o["submitted_at_ns"], "action": "submit", "order": o} for o in paper_orders]
    for o in paper_orders:
        if o["status"] == "canceled" and o["client_order_id"] in cancel_resolution:
            decisions.append({"ts_ns": cancel_resolution[o["client_order_id"]]["cancel_ts_ns"],
                               "action": "cancel", "order": o})
    decisions.sort(key=lambda d: (d["ts_ns"], 0 if d["action"] == "submit" else 1))
    return decisions


def fetch_window(paper_orders: list[dict], *, pad_seconds: int = 60) -> tuple[int, int]:
    starts = [o["submitted_at_ns"] for o in paper_orders]
    ends = [o["filled_at_ns"] or o["submitted_at_ns"] for o in paper_orders]
    return min(starts) - pad_seconds * 10**9, max(ends) + pad_seconds * 10**9


# ---------------------------------------------------------------------------
# Alpaca SIP historical quotes
# ---------------------------------------------------------------------------

def fetch_quotes(fetcher: PageFetcher, symbols: list[str], start_ns: int, end_ns: int, asof: str) -> dict[str, list[dict]]:
    quotes: dict[str, list[dict]] = {s: [] for s in symbols}
    params = {"symbols": ",".join(symbols), "start": ns_to_iso(start_ns), "end": ns_to_iso(end_ns),
              "feed": "sip", "asof": asof, "limit": 10000, "sort": "asc"}
    for body in fetcher.get(DATA, "/v2/stocks/quotes", params):
        for symbol, rows in (body.get("quotes") or {}).items():
            quotes[symbol].extend(rows)
    return quotes


def normalize_quote_rows(raw_rows: dict[str, list[dict]]) -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Keep two-sided, positively priced NBBO quotes, each stamped in ns, dropping
    crossed quotes (bid > ask, which cannot be matched sanely and would let a
    limit order fill through a data artifact). Locked quotes (bid == ask) are
    valid market data and are kept. Returns (quotes, drop_counts_by_symbol)."""
    out: dict[str, list[dict]] = {}
    drop_counts: dict[str, dict] = {}
    for symbol, rows in raw_rows.items():
        kept = []
        dropped = {"one_sided_or_nonpositive": 0, "crossed": 0}
        for row in rows:
            bp, ap = row.get("bp"), row.get("ap")
            bs, asz = row.get("bs"), row.get("as")
            if not bp or not ap or bp <= 0 or ap <= 0 or not bs or not asz:
                dropped["one_sided_or_nonpositive"] += 1
                continue
            if bp > ap:
                dropped["crossed"] += 1
                continue
            # Quantize both sides to the instrument's 2-decimal price precision:
            # SIP quotes occasionally carry a shorter decimal string on one side
            # (e.g. "120.5" vs "120.50"), and QuoteTick requires equal precision.
            kept.append({"symbol": symbol, "ts_ns": ts_ns(row["t"]),
                         "bid": str(Decimal(str(bp)).quantize(Decimal("0.01"))),
                         "ask": str(Decimal(str(ap)).quantize(Decimal("0.01"))),
                         "bid_size": int(bs), "ask_size": int(asz)})
        kept.sort(key=lambda q: q["ts_ns"])
        out[symbol] = kept
        drop_counts[symbol] = dropped
    return out, drop_counts


# ---------------------------------------------------------------------------
# Comparison (pure, offline-testable)
# ---------------------------------------------------------------------------

def compare_orders(paper_orders: list[dict], sim_orders_by_id: dict[str, dict]) -> dict:
    rows = []
    for paper in paper_orders:
        sim = sim_orders_by_id.get(paper["client_order_id"])
        sim_filled_qty = sim.get("filled_qty", 0) if sim else 0
        row = {
            "client_order_id": paper["client_order_id"], "symbol": paper["symbol"], "side": paper["side"],
            "qty": paper["qty"], "limit_price": paper["limit_price"],
            "paper_status": paper["status"], "paper_filled_qty": paper["filled_qty"],
            "paper_filled": paper["filled_qty"] > 0,
            "paper_fill_price": paper["filled_avg_price"],
            "paper_fill_ts": ns_to_iso(paper["filled_at_ns"]) if paper["filled_at_ns"] else None,
            "sim_present": sim is not None,
            "sim_status": sim.get("status") if sim else None,
            "sim_filled_qty": sim_filled_qty, "sim_filled": sim_filled_qty > 0,
            "sim_reject_reason": sim.get("reject_reason") if sim else None,
            "sim_fill_price": sim.get("avg_px") if sim else None,
            # From the last OrderFilled event's ts_event (see run_replay), not
            # order.ts_last -- a partial fill followed by a cancel must not report
            # the cancel's timestamp as the fill time.
            "sim_fill_ts": ns_to_iso(sim["fill_ts_ns"]) if sim and sim_filled_qty and sim.get("fill_ts_ns") is not None else None,
            # Quantity-based agreement (not a status-string comparison) so a partial
            # fill on one side and a full/no fill on the other is scored as a real
            # disagreement rather than folded into a boolean "filled" match.
            "fill_agreement": paper["filled_qty"] == sim_filled_qty,
            "paper_slippage_vs_limit_bps": (signed_slippage_bps(paper["side"], paper["filled_avg_price"], paper["limit_price"])
                                             if paper["filled_qty"] else None),
            "sim_slippage_vs_limit_bps": (signed_slippage_bps(paper["side"], sim.get("avg_px"), paper["limit_price"])
                                           if sim and sim_filled_qty else None),
        }
        if paper["filled_qty"] and sim_filled_qty and paper["filled_at_ns"] and sim.get("fill_ts_ns") is not None:
            row["fill_price_delta_bps"] = bps(row["sim_fill_price"], row["paper_fill_price"])
            row["fill_time_delta_s"] = (sim["fill_ts_ns"] - paper["filled_at_ns"]) / 1e9
        else:
            row["fill_price_delta_bps"] = None
            row["fill_time_delta_s"] = None
        rows.append(row)

    n = len(rows)
    agreements = sum(1 for r in rows if r["fill_agreement"])
    both_filled = [r for r in rows if r["paper_filled"] and r["sim_filled"]]
    price_deltas = [abs(r["fill_price_delta_bps"]) for r in both_filled if r["fill_price_delta_bps"] is not None]
    time_deltas = [abs(r["fill_time_delta_s"]) for r in both_filled if r["fill_time_delta_s"] is not None]

    def mean(xs):
        return sum(xs) / len(xs) if xs else None

    def median(xs):
        if not xs:
            return None
        s = sorted(xs)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    aggregates = {
        "orders": n, "fill_agreements": agreements, "fill_agreement_rate": agreements / n if n else None,
        "both_filled": len(both_filled),
        "abs_fill_price_delta_bps_mean": mean(price_deltas), "abs_fill_price_delta_bps_median": median(price_deltas),
        "abs_fill_price_delta_bps_max": max(price_deltas) if price_deltas else None,
        "abs_fill_time_delta_s_mean": mean(time_deltas), "abs_fill_time_delta_s_median": median(time_deltas),
        "abs_fill_time_delta_s_max": max(time_deltas) if time_deltas else None,
    }
    return {"rows": rows, "aggregates": aggregates}


# ---------------------------------------------------------------------------
# NautilusTrader BacktestEngine replay (imports deferred; requires the pinned
# 2.0.0rc5 runtime, not needed by the pure functions above or their tests)
# ---------------------------------------------------------------------------

def summarize_sim_order(order) -> dict:
    """Pure extraction of one NautilusTrader `Order`'s replay-relevant summary:
    status, filled quantity, average fill price, and -- the point this function is
    factored out for -- the *actual* fill timestamp from the order's own
    `OrderFilled` event(s) (`fill_ts_ns`), not `order.ts_last` (the order's last
    event of any kind: for a partial fill followed by a later cancel, `ts_last`
    would be the cancel's timestamp, not the fill's).

    Factored out of run_replay so this extraction can be tested directly against a
    constructed event list, independent of whether the pinned engine's current
    no-partial-fill-draw configuration (see module docstring) can produce a native
    partial-fill-then-cancel case at all -- as of this writing it cannot (matching
    disregards quoted size entirely with `liquidity_consumption=False`), so the
    committed tests exercise this function directly with fabricated events rather
    than relying on a native fixture that cannot exhibit the case in the first
    place; see tests.test_sim_paper_compare for both the direct-extraction test and
    a native test that documents (rather than assumes) that current boundary.

    Accepts any order-like object exposing `.client_order_id`, `.status`,
    `.filled_qty`, `.avg_px`, `.ts_last` and `.events()`/`.events` -- real
    NautilusTrader `Order` instances and simple test doubles alike."""
    status = str(order.status).rsplit(".", 1)[-1]
    filled_qty = int(Decimal(str(order.filled_qty))) if order.filled_qty is not None else 0
    avg_px = str(order.avg_px) if order.avg_px is not None else None
    ts_last = int(order.ts_last) if order.ts_last else None
    reject_reason = None
    fill_ts_ns = None
    events = order.events() if callable(order.events) else order.events
    for ev in events:
        ev_type = type(ev).__name__
        if ev_type == "OrderRejected":
            reject_reason = getattr(ev, "reason", None)
        elif ev_type == "OrderFilled":
            fill_ts_ns = int(ev.ts_event)
    return {"status": status, "filled_qty": filled_qty, "avg_px": avg_px,
            "ts_last": ts_last, "fill_ts_ns": fill_ts_ns, "reject_reason": reject_reason}


def run_replay(paper_orders: list[dict], quotes_by_symbol: dict[str, list[dict]], *, out_dir: Path,
                cancel_resolution: dict | None = None, latency_ns: int = 0, queue_position: bool = False,
                extra_timers_ns: tuple[int, ...] = ()) -> dict:
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.common import LogLevel
    from nautilus_trader.config import BacktestEngineConfig, LoggerConfig, StrategyConfig
    from nautilus_trader.execution import FixedFeeModel, StaticLatencyModel
    from nautilus_trader.model import (AccountType, BookType, ClientOrderId, Currency, Equity, InstrumentId,
                                        Money, OmsType, OrderSide, Price, Quantity, QuoteTick, Symbol,
                                        TimeInForce, Venue)
    from nautilus_trader.trading import Strategy

    usd, venue = Currency.from_str("USD"), Venue(VENUE_NAME)
    symbols = sorted(quotes_by_symbol)
    instruments = {}
    for symbol in symbols:
        iid = InstrumentId.from_str(f"{symbol}.{VENUE_NAME}")
        instruments[symbol] = Equity(iid, Symbol(symbol), usd, 2, Price.from_str("0.01"), 0, 0,
                                      lot_size=Quantity.from_int(1))

    decisions = build_decisions(paper_orders, cancel_resolution)
    for d in decisions:
        d["order"] = dict(d["order"], instrument_id=instruments[d["order"]["symbol"]].id)

    ticks = []
    for symbol, rows in quotes_by_symbol.items():
        iid = instruments[symbol].id
        for row in rows:
            ticks.append(QuoteTick(iid, Price.from_str(row["bid"]), Price.from_str(row["ask"]),
                                    Quantity.from_int(row["bid_size"]), Quantity.from_int(row["ask_size"]),
                                    row["ts_ns"], row["ts_ns"]))
    ticks.sort(key=lambda t: t.ts_event)
    if not ticks:
        raise ValueError("no_quote_ticks_fetched")

    out_dir.mkdir(parents=True, exist_ok=True)

    class ScheduledReplay(Strategy):
        def __init__(self):
            super().__init__(StrategyConfig())
            self.decisions = decisions
            self.applied = []

        def on_start(self):
            for iid in {instruments[s].id for s in symbols}:
                self.subscribe_quotes(iid)
            # Exact scheduled submit/cancel times via native time alerts, not "on the
            # next quote of any symbol" (which could arrive up to ~257ms late for a
            # thinly-traded symbol and, worse, misattributed any observed timing gap
            # to the decision itself rather than to the polling granularity).
            for i, d in enumerate(self.decisions):
                self.clock.set_time_alert_ns(f"decision-{i}", d["ts_ns"], lambda event, d=d: self._apply(d))
            # Test-only hook (empty by default in normal use): schedules bare
            # no-op timers with no order effect, to directly verify the module
            # docstring's claim that *any* due clock timer -- not specifically an
            # order-command one -- settles all instruments' outstanding deferred
            # commands. See tests.test_sim_paper_compare.PinnedRuntimeTests.
            for i, ts_ns in enumerate(extra_timers_ns):
                self.clock.set_time_alert_ns(f"noop-timer-{i}", ts_ns, lambda event: None)

        def on_stop(self):
            for order in list(self.cache.orders_open()):
                self.cancel_order(order.client_order_id)

        def _apply(self, d):
            o = d["order"]
            if d["action"] == "submit":
                order = self.order_factory.limit(
                    instrument_id=o["instrument_id"], order_side=OrderSide.BUY if o["side"] == "BUY" else OrderSide.SELL,
                    quantity=Quantity.from_int(o["qty"]), price=Price(Decimal(o["limit_price"]), 2),
                    time_in_force=getattr(TimeInForce, o["time_in_force"]), client_order_id=ClientOrderId(o["client_order_id"]))
                self.submit_order(order)
            else:
                order = self.cache.order(ClientOrderId(o["client_order_id"]))
                if order is not None and order.is_open:
                    self.cancel_order(order.client_order_id)
            # clock_ts_ns is the engine clock's time when this handler actually ran
            # (the scheduled time alert fires as soon as the clock reaches ts_ns, so
            # this is the actual application instant, not a re-statement of ts_ns).
            self.applied.append({"ts_ns": d["ts_ns"], "clock_ts_ns": self.clock.timestamp_ns(),
                                  "action": d["action"], "client_order_id": o["client_order_id"]})

    engine = BacktestEngine(BacktestEngineConfig(logging=LoggerConfig(stdout_level=LogLevel.ERROR)))
    fee_model = FixedFeeModel(Money(Decimal("0"), usd))
    latency_model = StaticLatencyModel(base_latency_nanos=latency_ns) if latency_ns else None
    try:
        engine.add_venue(venue, OmsType.NETTING, AccountType.CASH, [Money(Decimal("10000"), usd)],
                         base_currency=usd, fee_model=fee_model, latency_model=latency_model,
                         book_type=BookType.L1_MBP, liquidity_consumption=False, queue_position=queue_position)
        for instrument in instruments.values():
            engine.add_instrument(instrument)
        engine.add_data(ticks)
        strategy = ScheduledReplay()
        engine.add_strategy(strategy)
        engine.run()

        fills_report = engine.generate_order_fills_report()
        orders_report = engine.generate_orders_report()
        fills_report.to_csv(out_dir / "fills.csv")
        orders_report.to_csv(out_dir / "orders.csv")

        # Built from live order objects (strategy.cache.orders()), not from the
        # pandas reports: ts_last/status/reject reason come straight off the order
        # and its events, with no tz-aware-column-to-int64 conversion in between.
        orders = list(strategy.cache.orders())
        sim_by_id = {str(order.client_order_id): summarize_sim_order(order) for order in orders}

        fill_rows = json.loads(fills_report.reset_index().to_json(orient="records", default_handler=str, date_format="iso"))
        order_rows = json.loads(orders_report.reset_index().to_json(orient="records", default_handler=str, date_format="iso"))
        # init_id is a random UUID assigned per order construction; strip it before
        # hashing so the report hash reflects the run's actual results, not a
        # fresh random ID generated on every replay.
        for row in order_rows:
            row.pop("init_id", None)
        for row in fill_rows:
            row.pop("init_id", None)
        save(out_dir / "reports.json", {"fills": fill_rows, "orders": order_rows, "applied_decisions": strategy.applied})

        return {"sim_by_id": sim_by_id,
                "reports": {
                    "fills": {"rows": len(fill_rows),
                              "sha256_excluding_init_id": digest_bytes(json.dumps(fill_rows, sort_keys=True, default=str).encode())},
                    "orders": {"rows": len(order_rows),
                               "sha256_excluding_init_id": digest_bytes(json.dumps(order_rows, sort_keys=True, default=str).encode())},
                },
                "engine": {"latency_ns": latency_ns, "queue_position": queue_position, "liquidity_consumption": False}}
    finally:
        engine.dispose()


def _order_agrees_at_latency(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, latency_ns):
    result = run_replay(paper_orders, quotes_by_symbol, out_dir=out_dir, cancel_resolution=cancel_resolution,
                         latency_ns=latency_ns)
    row = next(r for r in compare_orders(paper_orders, result["sim_by_id"])["rows"]
               if r["client_order_id"] == client_order_id)
    return row["fill_agreement"]


def bisect_fill_agreement_flip(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id,
                                lo_ns, hi_ns, resolution_ns=1000):
    """Bisect, to `resolution_ns` (default 1us), the exact latency boundary at which
    `client_order_id`'s fill_agreement changes between lo_ns and hi_ns. This is the
    number that should be cited for "where the outcome flips" -- not a boundary
    derived from the raw quote data, since the engine's actual arrival/matching
    instant is not guaranteed to equal submit + latency (see module docstring).

    Returns each endpoint's *actual measured* agreement explicitly (`lo`/`hi`, each
    `{"latency_ns": ..., "agrees": bool}`) rather than assuming which direction the
    flip runs -- for this trial, agreement is False at the lower latency and True at
    the higher one (a lower-latency sim fills an order paper did not), the opposite
    of "agrees below, disagrees above." Do not rename these keys back to an
    assumed-direction pair (e.g. agrees_at_or_below/disagrees_at_or_above)."""
    lo_agrees = _order_agrees_at_latency(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, lo_ns)
    hi_agrees = _order_agrees_at_latency(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, hi_ns)
    if lo_agrees == hi_agrees:
        return None
    lo, hi = lo_ns, hi_ns
    while hi - lo > resolution_ns:
        mid = (lo + hi) // 2
        if _order_agrees_at_latency(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, client_order_id, mid) == lo_agrees:
            lo = mid
        else:
            hi = mid
    return {"client_order_id": client_order_id,
            "lo": {"latency_ns": lo, "agrees": lo_agrees},
            "hi": {"latency_ns": hi, "agrees": hi_agrees},
            "resolution_ns": resolution_ns}


def run_latency_sweep(paper_orders: list[dict], quotes_by_symbol: dict[str, list[dict]], *, cancel_resolution: dict,
                       out_dir: Path, baseline_comparison: dict) -> dict:
    """Run the declared latency-sensitivity sweep (LATENCY_SWEEP_MS), report
    agreement/deltas at each point (with full per-order rows, not just aggregates --
    every per-order figure cited in prose must be traceable to this data), bisect the
    exact latency boundary for any order whose fill_agreement changes between two
    consecutive sweep points, and classify whether each flip is independent or
    depends on another order that flips in the same bracket (see
    classify_flip_dependence). This is a sensitivity check, not a calibration: it
    shows how the zero-latency default's disagreement changes as StaticLatencyModel's
    broker/network latency assumption increases, nothing more -- and per the module
    docstring, the sweep's time/price columns are not a pure function of the modeled
    latency alone."""
    sweep = []
    for ms in LATENCY_SWEEP_MS:
        if ms == 0:
            comparison = baseline_comparison
        else:
            result = run_replay(paper_orders, quotes_by_symbol, out_dir=out_dir / f"{ms}ms",
                                 cancel_resolution=cancel_resolution, latency_ns=ms * 10**6)
            comparison = compare_orders(paper_orders, result["sim_by_id"])
        agg = comparison["aggregates"]
        sweep.append({
            "latency_ms": ms,
            "fill_agreements": agg["fill_agreements"], "orders": agg["orders"],
            "fill_agreement_rate": agg["fill_agreement_rate"], "both_filled": agg["both_filled"],
            "abs_fill_price_delta_bps_mean": agg["abs_fill_price_delta_bps_mean"],
            "abs_fill_time_delta_s_mean": agg["abs_fill_time_delta_s_mean"],
            "disagreeing_client_order_ids": sorted(r["client_order_id"] for r in comparison["rows"] if not r["fill_agreement"]),
            "rows": comparison["rows"],
        })

    flip_bisections = []
    for prev, nxt in zip(sweep, sweep[1:]):
        changed = (set(prev["disagreeing_client_order_ids"]) ^ set(nxt["disagreeing_client_order_ids"]))
        for coid in sorted(changed):
            bisection = bisect_fill_agreement_flip(paper_orders, quotes_by_symbol, cancel_resolution,
                                                     out_dir / "bisect", coid,
                                                     prev["latency_ms"] * 10**6, nxt["latency_ms"] * 10**6)
            if bisection is not None:
                bisection["bracket_ms"] = [prev["latency_ms"], nxt["latency_ms"]]
                flip_bisections.append(bisection)
    classify_flip_dependence(paper_orders, quotes_by_symbol, cancel_resolution, out_dir / "dependence", flip_bisections)
    return {"points": sweep, "flip_bisections": flip_bisections}


def classify_flip_dependence(paper_orders, quotes_by_symbol, cancel_resolution, out_dir, flip_bisections) -> None:
    """For each bracket where more than one order's fill_agreement flips together,
    determine (empirically, not by assumption) whether each flip is independent of
    the others in that bracket, by re-running the replay across the *entire declared
    latency sweep* (LATENCY_SWEEP_MS, not just the bracket's original lo/hi bisection
    endpoints) with the *other* flipping order(s) removed from paper_orders entirely,
    and retaining every one of those observations (`counterfactual_sweep`) in the
    result. Probing only the original endpoints is unsound: removing another order
    can *shift* where this order's own boundary falls (e.g. from ~19.5ms to ~10ms)
    without eliminating the flip, and checking just the old endpoints would then
    misreport a still-independently-flipping order as dependent, because both old
    endpoints now happen to agree. Scanning the full declared sweep instead asks the
    right question directly: does this order's agreement ever change anywhere in the
    declared range once the other order is removed? If it does not change anywhere
    in that range, the flip is recorded as `independent_flip: False` with
    `depends_on_client_order_ids`; if it changes anywhere, `independent_flip: True`.
    Mutates `flip_bisections` in place, adding these fields (plus
    `counterfactual_sweep`) to every entry."""
    by_bracket: dict[tuple, list[dict]] = {}
    for b in flip_bisections:
        by_bracket.setdefault(tuple(b["bracket_ms"]), []).append(b)
    for group in by_bracket.values():
        if len(group) < 2:
            for b in group:
                b["independent_flip"] = True
                b["depends_on_client_order_ids"] = []
                b["counterfactual_sweep"] = None
            continue
        ids_in_group = {b["client_order_id"] for b in group}
        for b in group:
            others = ids_in_group - {b["client_order_id"]}
            reduced_orders = [o for o in paper_orders if o["client_order_id"] not in others]
            counterfactual_sweep = [
                {"latency_ms": ms,
                 "agrees": _order_agrees_at_latency(reduced_orders, quotes_by_symbol, cancel_resolution, out_dir,
                                                      b["client_order_id"], ms * 10**6)}
                for ms in LATENCY_SWEEP_MS
            ]
            distinct_states = {point["agrees"] for point in counterfactual_sweep}
            b["counterfactual_sweep"] = counterfactual_sweep
            b["independent_flip"] = len(distinct_states) > 1
            b["depends_on_client_order_ids"] = [] if b["independent_flip"] else sorted(others)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

REPO_ROOT = HERE.parents[2]  # .../blueprints/us-equities/sim-paper-compare -> repo root
_SENSITIVE_ARG_NAMES = ("env_file", "env_file_from_file", "pages", "out")
_PATH_TRIMMED_ARG_NAMES = ("trial", "receipt")
_ARG_ORDER = ("trial", "env_file", "env_file_from_file", "pages", "out", "replay", "receipt")


def _repo_relative_or_basename(value: str) -> str:
    """Repo-relative path when the value is inside this repository, else just the
    basename -- never the full absolute path, which could carry the invoking user's
    home directory or other personal path segments even for a "non-secret" flag
    like --trial or --receipt."""
    p = Path(value)
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return p.name


def redact_args(args: argparse.Namespace) -> list[str]:
    """Canonical, redacted representation of the *parsed* CLI arguments -- built
    from the argparse namespace, never from raw sys.argv text. Redacting raw text
    is bypassable by any accepted alternate spelling (abbreviations, `--flag=value`
    joins); building the record from the parsed namespace after `allow_abbrev=False`
    closes that off structurally instead of trying to enumerate every spelling.
    `--trial`/`--receipt` are not secret, but are trimmed to a repo-relative path
    (or basename if given outside the repo) rather than recorded verbatim, since an
    absolute path for either would still carry the invoking user's home directory."""
    parts = []
    for name in _ARG_ORDER:
        value = getattr(args, name, None)
        flag = "--" + name.replace("_", "-")
        if name == "replay":
            if value:
                parts.append(flag)
            continue
        if value is None:
            continue
        parts.append(flag)
        if name in _SENSITIVE_ARG_NAMES:
            parts.append("<redacted>")
        elif name in _PATH_TRIMMED_ARG_NAMES:
            parts.append(_repo_relative_or_basename(str(value)))
        else:
            parts.append(str(value))
    return parts


def main(argv=None) -> int:
    started_utc = datetime.now(UTC).isoformat()

    # allow_abbrev=False: with it left at argparse's default, `--pag`/`--ou`/`--rec`
    # etc. are silently accepted as unambiguous prefixes of --pages/--out/--receipt,
    # which bypassed a prior raw-argv-text redaction (only exact flag strings were
    # matched). Rejecting abbreviations outright, plus building the recorded argv
    # from the parsed namespace (see redact_args) rather than scanning argv text,
    # closes this from two independent directions.
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument("--trial", type=Path, required=True, help="Retained adaptive-paper trial directory")
    ap.add_argument("--env-file", type=Path, help="Private paper-credential env file (never printed); "
                                                    "not required in --replay mode")
    ap.add_argument("--env-file-from-file", type=Path,
                     help="A file whose sole line is the private env file's path (for shells that must not "
                          "spell the credential store path directly in a command); not required in --replay mode")
    ap.add_argument("--pages", type=Path, required=True, help="Private page cache (gzip + sha256 ledger)")
    ap.add_argument("--out", type=Path, required=True, help="Fresh private output directory (must not already exist)")
    ap.add_argument("--replay", action="store_true", help="Reuse retained pages only; no network request, "
                                                            "no credential file opened")
    ap.add_argument("--receipt", type=Path, required=True, help="Repo-committed receipt path (hashes and results only)")
    args = ap.parse_args(argv)

    if importlib.metadata.version("nautilus_trader") != "2.0.0rc5":
        raise ValueError("native_version_mismatch")

    # --replay never opens a credential file: the page cache already holds every
    # response this run needs, and PageFetcher(replay=True) never sends a request.
    # `import runner` (the credential loader) is not even reached in this branch.
    key = secret = None
    if not args.replay:
        env_file = args.env_file
        if env_file is None:
            if args.env_file_from_file is None:
                raise SystemExit("one of --env-file or --env-file-from-file is required when not --replay")
            env_file = Path(args.env_file_from_file.read_text().strip())
        sys.path.insert(0, str(ADAPTIVE_PAPER))
        import runner  # noqa: E402  (adaptive-paper/runner.py's credential loader)
        key, secret = runner.credentials(env_file)

    broker_orders_path = args.trial / "broker-orders.json"
    broker_orders = json.loads(broker_orders_path.read_text())
    paper_output = json.loads((args.trial / "paper-output.json").read_text())
    ingest_receipt = json.loads((args.trial / "ingest-receipt.json").read_text())
    paper_orders = load_paper_orders(broker_orders)
    symbols = sorted({o["symbol"] for o in paper_orders})
    start_ns, end_ns = fetch_window(paper_orders)
    day = ns_to_iso(paper_orders[0]["submitted_at_ns"])[:10]

    order_timeout_seconds, timeout_source = resolve_order_timeout_seconds(ingest_receipt)
    cancel_resolution = resolve_cancel_timestamps(paper_orders, paper_output, order_timeout_seconds)
    provenance = clock_provenance(paper_orders, paper_output)

    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit(f"--out must be a fresh (empty or nonexistent) directory: {args.out} is not empty")
    # Narrow the umask only for the directory/file creation below, then restore it --
    # os.umask(0o077) with no matching restore would leave every later os call in
    # this same process (and any code that imports this module as a library) under
    # a process-wide umask change with no obvious cause.
    previous_umask = os.umask(0o077)
    try:
        args.out.mkdir(parents=True, exist_ok=True)
        chmod_private_dir(args.out)
    finally:
        os.umask(previous_umask)

    fetcher = PageFetcher(args.pages, {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret} if key else None,
                           replay=args.replay)
    raw_quotes = fetch_quotes(fetcher, symbols, start_ns, end_ns, day)
    quotes, quote_drop_counts = normalize_quote_rows(raw_quotes)
    save(args.out / "quotes.private.json", quotes)

    replay_result = run_replay(paper_orders, quotes, out_dir=args.out, cancel_resolution=cancel_resolution, latency_ns=0)
    comparison = compare_orders(paper_orders, replay_result["sim_by_id"])
    save(args.out / "comparison.json", comparison)

    latency_sweep = run_latency_sweep(paper_orders, quotes, cancel_resolution=cancel_resolution,
                                       out_dir=args.out / "latency-sweep", baseline_comparison=comparison)

    # alpaca-py's installed version is recorded for the environment record only --
    # this replay fetches quotes with urllib directly (see fetch_quotes/PageFetcher),
    # and --replay makes no request at all, so this is not data provenance.
    try:
        alpaca_py_installed_version = importlib.metadata.version("alpaca-py")
    except importlib.metadata.PackageNotFoundError:
        alpaca_py_installed_version = None

    summary = {"receipt": str(args.receipt), "aggregates": comparison["aggregates"],
               "latency_sweep": [{"latency_ms": s["latency_ms"], "fill_agreement_rate": s["fill_agreement_rate"]}
                                  for s in latency_sweep["points"]]}
    # print() appends a trailing newline; stdout_sha256 must hash exactly the bytes
    # actually written to stdout, not the pre-newline JSON string.
    stdout_bytes = (json.dumps(summary, indent=2) + "\n").encode()
    # Computed once, used identically for both stdout_sha256_basis (below) and the
    # actual write (further below) -- see the comment at stdout_sha256_basis for
    # why `hasattr(sys.stdout, "buffer")` alone would be the wrong check.
    stdout_buffer = getattr(sys.stdout, "buffer", None)
    completed_utc = datetime.now(UTC).isoformat()

    receipt = {
        "kind": "sim_vs_paper_fill_comparison",
        "protocol": "sim-paper-compare-v1-20260924",
        "evidence_class": "local_integration_check",
        "trial": str(broker_orders_path.parent.name),
        "trial_window_utc": broker_orders["window_utc"],
        "inputs_sha256": {
            "broker_orders_json": digest_path(broker_orders_path),
            "paper_output_json": digest_path(args.trial / "paper-output.json"),
            "ingest_receipt_json": digest_path(args.trial / "ingest-receipt.json"),
        },
        # A checksum ledger identifies the retained inputs and supports deterministic
        # replay *from those same retained pages*; it does not demonstrate that an
        # independent, fresh request against the live Alpaca endpoint would return
        # byte-identical data (historical quote revisions are not ruled out).
        "data_provenance": {
            "source": "Alpaca historical quotes, GET https://data.alpaca.markets/v2/stocks/quotes",
            "feed": "sip", "adjustment": "n/a (quotes)", "symbols": symbols,
            "asof": day, "window_utc": [ns_to_iso(start_ns), ns_to_iso(end_ns)],
            "quote_counts": {s: len(rows) for s, rows in quotes.items()},
            "quote_drop_counts": quote_drop_counts,
            "page_ledger_sha256": digest_path(args.pages / "ledger.jsonl"),
            "page_sources": {"cache": fetcher.from_cache, "network": fetcher.from_network,
                              "pages": fetcher.page_events},
            "reproducibility_note": "hashes identify the retained page cache and support same-page replay; "
                                     "independent-request reproducibility against the live endpoint is untested.",
        },
        "runtime_environment": {
            # Informational only -- see the note above run_replay's fetcher usage;
            # this is not part of how the data in this receipt was obtained.
            "alpaca_py_installed_version": alpaca_py_installed_version,
            "note": "alpaca-py is installed in this runtime but not used by this script's fetch path "
                    "(urllib.request directly); recorded for environment reproducibility only.",
        },
        "cancel_timestamp_resolution": {
            "order_timeout_seconds": order_timeout_seconds,
            "order_timeout_seconds_source": timeout_source,
            "by_client_order_id": cancel_resolution,
        },
        "clock_provenance": provenance,
        "engine": {
            "engine_version": importlib.metadata.version("nautilus_trader"),
            "book_type": "L1_MBP", "oms_type": "NETTING", "account_type": "CASH",
            "fee_model": {"class": "FixedFeeModel", "commission_usd": "0", "source": "reused from engine-nautilus/equity-replay baseline case"},
            "fill_model": {"class": "nautilus_trader.execution.FillModel (native default, unconfigured)", "note": FILL_MODEL_NOTE},
            "liquidity_consumption": replay_result["engine"]["liquidity_consumption"],
            "queue_position": replay_result["engine"]["queue_position"],
            "latency_model": None if replay_result["engine"]["latency_ns"] == 0 else
                              {"class": "StaticLatencyModel", "base_latency_nanos": replay_result["engine"]["latency_ns"]},
            "latency_model_semantics": "the pinned engine processes a deferred (latency-delayed) command at "
                                        "the first settlement event at or after submit + latency, not "
                                        "necessarily exactly at that instant; a settlement event is either "
                                        "(a) the next event on that order's own instrument (its own next "
                                        "quote), or (b) any due clock timer the engine processes -- from any "
                                        "source, including one with no order effect at all -- which settles "
                                        "all instruments' outstanding deferred commands together, not only "
                                        "that timer's own instrument; a plain market-data quote for a "
                                        "*different* instrument is neither of these and does not by itself "
                                        "trigger settlement; see module docstring.",
            "reports": replay_result["reports"],
        },
        "results": comparison,
        "latency_sensitivity_sweep": {
            "declared_sweep_ms": list(LATENCY_SWEEP_MS),
            "purpose": "Sensitivity check, not a calibration: shows how fill agreement changes as "
                       "StaticLatencyModel's broker/network latency assumption increases from the "
                       "zero-latency default. Time/price columns are not a pure function of latency "
                       "alone (see module docstring); flip_bisections is the authoritative flip point, "
                       "not a quote-derived marketable-window boundary.",
            "points": latency_sweep["points"],
            "flip_bisections": latency_sweep["flip_bisections"],
        },
        "scope": "One retained trial, five order decisions (four filled, one canceled). This is an agreement "
                 "measurement between one paper session and one deterministic quote-driven replay, not a fill-rate "
                 "or slippage calibration, and not a claim about any other trial, symbol, session or market regime. "
                 "The order-4/order-5 timing explanation in the README is a hypothesis consistent with this "
                 "receipt's data, not a demonstrated broker-side mechanism.",
        "replay_from_retained_pages_only": args.replay,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "argv": redact_args(args),
        "stdout_sha256": digest_bytes(stdout_bytes),
        # When stdout exposes a binary `.buffer` that is actually not None (the
        # normal case for a real process), that buffer is written to directly and
        # stdout_sha256 hashes exactly those bytes -- no encoding or newline
        # translation can intervene. `hasattr(sys.stdout, "buffer")` alone is not
        # the right check here: a wrapper can have a `.buffer` attribute that is
        # itself None, in which case the write path below falls through to
        # text-mode `.write()` -- the exact same condition (`stdout_buffer is not
        # None`, computed once) must gate both the basis recorded here and the
        # write below, or the two could disagree about which path was taken. When
        # there is no usable buffer (e.g. unittest's `-b` output-capture StringIO,
        # which has no `.buffer` attribute at all), stdout_sha256 is only a hash
        # of the UTF-8, LF-normalized text -- it is not a guarantee about the
        # exact bytes some other text stream (e.g. one opened with
        # `newline="\r\n"`) would actually emit.
        "stdout_sha256_basis": "exact_bytes_written" if stdout_buffer is not None else "utf8_lf_normalized_text",
        "runner_sha256": digest_path(Path(__file__)),
    }
    # The receipt is saved before stdout is written: it is the durable evidence
    # artifact, and a stdout write failure downstream (e.g. a closed pipe) should
    # not be allowed to leave a successful run with no receipt on disk.
    save(args.receipt, receipt)
    if stdout_buffer is not None:
        stdout_buffer.write(stdout_bytes)
    else:
        sys.stdout.write(stdout_bytes.decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
