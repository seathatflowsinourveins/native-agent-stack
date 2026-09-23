"""Read-only probe of the NautilusTrader native IB adapter against a paper gateway.

Runs right after ``ibapi_probe.py`` has passed on the same host and port: the
rc5 Python surface used here (``HistoricalInteractiveBrokersClient``) exposes
no managed-account query of its own, so the paper-account check comes from that
receipt, which must be fresh. It resolves the SPY instrument and requests
historical bars only. The historical client has no order methods and none are
called. The Rust-backed client needs an asyncio loop on the calling thread and
cannot be moved to another thread, so everything runs under ``asyncio.run``.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import socket
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The gate's flip receipt; a step-1 probe must never write there.
GATE_RECEIPT = HERE / "receipt.json"
PAPER_PORTS = {4002, 7497}
BAR_SPECS = ("1-DAY-LAST", "5-MINUTE-LAST")
IBAPI_CLIENT = "ibapi (official IB API client)"
EXIT_CODES = {"passed": 0, "instrument_only": 1, "failed": 1, "not_connected": 2}


def paper_precondition(ibapi_receipt: dict, host: str, port: int, now: datetime, max_age_s: float) -> str | None:
    """Refusal reason, or None when the official-client receipt shows a passed
    read-only probe of a paper account on this same host and port, written no
    more than ``max_age_s`` seconds before ``now``."""
    if port not in PAPER_PORTS:
        return "refused_not_paper_port"
    observed = ibapi_receipt.get("observed") or {}
    if (ibapi_receipt.get("client") != IBAPI_CLIENT or ibapi_receipt.get("status") != "passed"
            or ibapi_receipt.get("exit_code") != 0 or observed.get("paper_accounts") is not True):
        return "refused_no_passed_paper_ibapi_receipt"
    if ibapi_receipt.get("port") != port or ibapi_receipt.get("host") != host:
        return "refused_ibapi_receipt_for_other_endpoint"
    try:
        age = (now - datetime.fromisoformat(ibapi_receipt["generated_at"])).total_seconds()
    except (KeyError, TypeError, ValueError):
        return "refused_no_passed_paper_ibapi_receipt"
    if not -60 <= age <= max_age_s:
        return "refused_stale_ibapi_receipt"
    return None


def default_end(now: datetime) -> datetime:
    """20:00 UTC on the previous day: a bar window that is already closed."""
    return (now - timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)


def tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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
        found = [i for i in (list(result or []) or [provider.find(iid)]) if i is not None]
        if not found:
            out["instrument_error"] = "not_found"
        else:
            inst = found[0]
            contract = (inst.info or {}).get("contract", {})
            out["instrument"] = {"id": str(inst.id), "class": type(inst).__name__,
                                 "price_increment": str(inst.price_increment), "conId": contract.get("conId"),
                                 "primaryExchange": contract.get("primaryExchange"),
                                 "currency": contract.get("currency"),
                                 "elapsed_s": round(time.monotonic() - started, 3)}
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
    ap.add_argument("--timeout-seconds", type=int, default=20, help="plan.json per_call_timeout_seconds")
    ap.add_argument("--max-receipt-age-seconds", type=float, default=300)
    a = ap.parse_args(argv)
    if Path(a.receipt).resolve() == GATE_RECEIPT:
        print(json.dumps({"status": "refused_gate_receipt_path", "exit_code": 3}))
        return 3
    now = datetime.now(timezone.utc)
    receipt = {"schema_version": 1, "gate_id": "ibkr-local-acceptance", "step": "acceptance-plan 5.1 read-only",
               "client": "nautilus_trader.adapters.interactive_brokers.HistoricalInteractiveBrokersClient",
               "host": a.host, "port": a.port, "client_id": a.client_id, "generated_at": now.isoformat()}
    try:
        raw = Path(a.ibapi_receipt).read_bytes()
        refusal = paper_precondition(json.loads(raw), a.host, a.port, now, a.max_receipt_age_seconds)
        receipt["paper_check"] = {"ibapi_receipt": {"sha256": hashlib.sha256(raw).hexdigest(),
                                                    "generated_at": json.loads(raw).get("generated_at")}}
    except (OSError, ValueError, AttributeError):
        refusal = "refused_no_passed_paper_ibapi_receipt"
    if refusal:
        receipt.update(status=refusal, evidence_class="none")
        return _write(a.receipt, receipt, 3)
    if not tcp_reachable(a.host, a.port, 5):
        receipt.update(status="not_connected", evidence_class="not_connected")
        return _write(a.receipt, receipt, 2)
    observed = asyncio.run(collect(a.host, a.port, a.client_id, default_end(now), a.timeout_seconds))
    bars_ok = any(b.get("count") for b in observed["bars"])
    instrument_ok = bool(observed["instrument"] and observed["instrument"]["conId"])
    status = "passed" if instrument_ok and bars_ok else ("instrument_only" if instrument_ok else "failed")
    receipt.update(status=status, evidence_class="native_paper_readonly", observed=observed)
    return _write(a.receipt, receipt, EXIT_CODES[status])


def _write(path, receipt, code):
    receipt["exit_code"] = code
    with open(path, "w") as f:
        json.dump(receipt, f, indent=2, default=str)
        f.write("\n")
    print(json.dumps({k: receipt.get(k) for k in ("status", "evidence_class", "exit_code")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
