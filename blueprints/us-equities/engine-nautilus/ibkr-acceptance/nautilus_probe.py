"""Read-only probe of the NautilusTrader native IB adapter against a paper gateway.

Runs after ``ibapi_probe.py`` has passed on the same host and port, since the
rc5 Python surface used here (``HistoricalInteractiveBrokersClient``) exposes
no managed-account query of its own; the paper-account check is taken from
that receipt. It resolves the SPY instrument and requests historical bars
only. The historical client has no order methods and none are called.
The Rust-backed client needs an asyncio loop on the calling thread and cannot
be moved to another thread, so everything runs under ``asyncio.run``.
"""
from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import time
from datetime import datetime, timedelta, timezone

PAPER_PORTS = {4002, 7497}
BAR_SPECS = ("1-DAY-LAST", "5-MINUTE-LAST")


def paper_precondition(ibapi_receipt: dict, host: str, port: int) -> str | None:
    """Refusal reason, or None when the official-client receipt shows a passed
    read-only probe of a paper account on this same host and port."""
    if port not in PAPER_PORTS:
        return "refused_not_paper_port"
    observed = ibapi_receipt.get("observed") or {}
    if ibapi_receipt.get("status") != "passed" or observed.get("paper_accounts") is not True:
        return "refused_no_passed_paper_ibapi_receipt"
    if ibapi_receipt.get("port") != port or ibapi_receipt.get("host") != host:
        return "refused_ibapi_receipt_for_other_endpoint"
    return None


def default_end(now: datetime) -> datetime:
    """20:00 UTC on the previous day: a bar window that is already closed."""
    return (now - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)


async def _maybe_await(value, seconds):
    return await asyncio.wait_for(value, seconds) if inspect.isawaitable(value) else value


async def collect(host, port, client_id, end, timeout):
    import nautilus_trader
    import nautilus_trader.adapters.interactive_brokers as ib
    from nautilus_trader.model import InstrumentId

    out = {"nautilus_trader": nautilus_trader.__version__, "instrument": None, "bars": []}
    iid = InstrumentId.from_str("SPY.ARCA")
    cfg = ib.InteractiveBrokersDataClientConfig(host=host, port=port, client_id=client_id,
                                                connection_timeout=timeout, request_timeout=timeout)
    provider = ib.InteractiveBrokersInstrumentProvider(ib.InteractiveBrokersInstrumentProviderConfig(load_ids={iid}))
    client = ib.HistoricalInteractiveBrokersClient(provider, cfg)
    started = time.monotonic()
    try:
        result = await _maybe_await(client.request_instruments(instrument_ids=[iid]), timeout + 15)
        found = list(result or []) or [provider.find(iid)]
        inst = found[0]
        contract = (inst.info or {}).get("contract", {}) if inst is not None else {}
        out["instrument"] = {"id": str(inst.id), "class": type(inst).__name__, "price_increment": str(inst.price_increment),
                             "conId": contract.get("conId"), "primaryExchange": contract.get("primaryExchange"),
                             "currency": contract.get("currency"), "elapsed_s": round(time.monotonic() - started, 3)}
    except Exception as exc:  # recorded, not retried
        out["instrument_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    for spec in BAR_SPECS:
        started = time.monotonic()
        entry = {"spec": spec, "end": end.isoformat(), "duration": "5 D"}
        try:
            bars = await _maybe_await(client.request_bars(bar_specifications=[spec], end_date_time=end, duration="5 D",
                                                          instrument_ids=[iid], timeout=timeout), timeout + 15)
            rows = list(bars or [])
            entry.update(count=len(rows), first=str(rows[0])[:160] if rows else None,
                         last=str(rows[-1])[:160] if rows else None)
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        entry["elapsed_s"] = round(time.monotonic() - started, 3)
        out["bars"].append(entry)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=4002)
    ap.add_argument("--client-id", type=int, default=76)
    ap.add_argument("--ibapi-receipt", required=True)
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--timeout-seconds", type=int, default=30)
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    receipt = {"schema_version": 1, "gate_id": "ibkr-local-acceptance", "step": "acceptance-plan 5.1 read-only",
               "client": "nautilus_trader.adapters.interactive_brokers.HistoricalInteractiveBrokersClient",
               "host": a.host, "port": a.port, "client_id": a.client_id, "generated_at": now.isoformat()}
    with open(a.ibapi_receipt) as f:
        refusal = paper_precondition(json.load(f), a.host, a.port)
    if refusal:
        receipt.update(status=refusal, evidence_class="none")
        return _write(a.receipt, receipt, 3)
    observed = asyncio.run(collect(a.host, a.port, a.client_id, default_end(now), a.timeout_seconds))
    bars_ok = any(b.get("count") for b in observed["bars"])
    instrument_ok = bool(observed["instrument"] and observed["instrument"]["conId"])
    status = "passed" if instrument_ok and bars_ok else ("instrument_only" if instrument_ok else "failed")
    receipt.update(status=status, evidence_class="native_paper_readonly", observed=observed)
    return _write(a.receipt, receipt, 0 if status == "passed" else 1)


def _write(path, receipt, code):
    receipt["exit_code"] = code
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2, default=str)
        f.write("\n")
    print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
