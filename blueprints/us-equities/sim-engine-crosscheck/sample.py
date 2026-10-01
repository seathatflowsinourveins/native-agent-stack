#!/usr/bin/env python3
"""Extract a bounded, private sample of already-retained sim-capacity quotes
for the engine-vs-engine cross-check (Phase C).

Reads only the private, non-repo cache written by
`sim-capacity/runner.py fetch` (`~/.local/state/native-agent-stack/sim-capacity/
catalog/{quotes,trades}.private.json`). Never touches the network and never
opens a credential file -- this is pure local filtering of data sim-capacity
already fetched and retained; see sim-capacity/README.md's "Data" section for
how that cache was populated (Alpaca SIP `/v2/stocks/quotes` and `/v2/stocks/
trades`, `--replay`-only reuse). Writes a private bounded sample
(`sample.private.json`, 0600) plus a small, non-sensitive manifest (window,
per-symbol counts, sha256 hashes) suitable for the committed receipt -- raw
quotes/trades are never printed to stdout and never committed.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SOURCE_CATALOG = Path.home() / ".local/state/native-agent-stack/sim-capacity/catalog"
DEFAULT_SAMPLE_DIR = Path.home() / ".local/state/native-agent-stack/sim-engine-crosscheck"

# 8 minutes, inside sim-capacity's reported 2026-09-24T14:00:00Z-14:30:00Z
# analysis window (avoiding both the window's open, already avoided by
# sim-capacity itself, and its own tail, kept clear of the +5min flatten pad).
WINDOW_START_ISO = "2026-09-24T14:05:00Z"
WINDOW_END_ISO = "2026-09-24T14:13:00Z"
# SPY (the index proxy already used throughout sim-capacity) plus NVDA, a
# high-volume single name from the same 8-symbol universe
# (blueprints/us-equities/sim-capacity/fetcher.py SYMBOLS).
SYMBOLS = ("SPY", "NVDA")


def iso_to_ns(iso: str) -> int:
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def _digest_obj(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def extract_bounded_sample(*, source_catalog: Path = DEFAULT_SOURCE_CATALOG, symbols=SYMBOLS,
                            start_iso: str = WINDOW_START_ISO, end_iso: str = WINDOW_END_ISO,
                            out_dir: Path = DEFAULT_SAMPLE_DIR) -> dict:
    """Filter the retained private quote/trade cache down to `symbols` and
    [start_iso, end_iso], write the bounded sample privately, and return a
    manifest of counts and hashes (no raw rows)."""
    start_ns, end_ns = iso_to_ns(start_iso), iso_to_ns(end_iso)
    quotes_all = json.loads((source_catalog / "quotes.private.json").read_text())
    trades_all = json.loads((source_catalog / "trades.private.json").read_text())

    quotes: dict[str, list] = {}
    trades: dict[str, list] = {}
    counts: dict[str, dict] = {}
    for symbol in symbols:
        qrows = [r for r in quotes_all.get(symbol, []) if start_ns <= r["ts_ns"] <= end_ns]
        trows = [r for r in trades_all.get(symbol, []) if start_ns <= r["ts_ns"] <= end_ns]
        qrows.sort(key=lambda r: r["ts_ns"])
        trows.sort(key=lambda r: r["ts_ns"])
        quotes[symbol] = qrows
        trades[symbol] = trows
        counts[symbol] = {"quotes": len(qrows), "trades": len(trows)}

    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)
    sample_path = out_dir / "sample.private.json"
    payload = {"window": {"start": start_iso, "end": end_iso}, "symbols": list(symbols),
               "quotes": quotes, "trades": trades}
    sample_text = json.dumps(payload, sort_keys=True)
    sample_path.write_text(sample_text)
    os.chmod(sample_path, 0o600)

    manifest = {
        "window": {"start": start_iso, "end": end_iso, "start_ns": start_ns, "end_ns": end_ns},
        "symbols": list(symbols),
        "counts": counts,
        "source_catalog": str(source_catalog),
        "sample_sha256": hashlib.sha256(sample_text.encode()).hexdigest(),
        "sample_bytes": len(sample_text),
        "source_fetch_manifest_sha256": _digest_obj(json.loads((source_catalog / "fetch-manifest.json").read_text())),
    }
    manifest_path = out_dir / "sample-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.chmod(manifest_path, 0o600)
    return manifest


def load_bounded_sample(sample_dir: Path = DEFAULT_SAMPLE_DIR) -> dict:
    return json.loads((sample_dir / "sample.private.json").read_text())


def load_sample_manifest(sample_dir: Path = DEFAULT_SAMPLE_DIR) -> dict:
    return json.loads((sample_dir / "sample-manifest.json").read_text())


if __name__ == "__main__":
    result = extract_bounded_sample()
    print(json.dumps(result, indent=2, sort_keys=True))
