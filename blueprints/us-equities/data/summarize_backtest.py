#!/usr/bin/env python3
"""Summarize native LEAN simulated order events with DuckDB and an exchange calendar."""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import exchange_calendars as calendars


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("events", type=Path)
    p.add_argument("parquet", type=Path)
    args = p.parse_args()
    if args.parquet.exists():
        p.error("choose a new Parquet output; existing data are preserved")
    with duckdb.connect() as con:
        events = con.read_json(str(args.events)).project(
            'orderId AS order_id, symbolValue AS symbol, '
            'to_timestamp(time) AS event_time_utc, status, '
            'CAST(fillPrice AS DECIMAL(20, 8)) AS fill_price, '
            'CAST(fillQuantity AS DECIMAL(20, 8)) AS fill_quantity')
        events.write_parquet(str(args.parquet), compression="zstd")
        con.read_parquet(str(args.parquet)).create_view("events")
        rows, orders = con.sql('SELECT count(*), count(DISTINCT order_id) FROM events').fetchone()
        statuses = dict(con.sql('SELECT status, count(*) FROM events GROUP BY status ORDER BY status').fetchall())
    calendar = calendars.get_calendar("XNYS")
    session = "2013-10-07"  # Upstream bundled sample; not today's market.
    print(json.dumps({
        "scope": "LEAN bundled historical simulation, not broker fills",
        "events": rows, "distinct_orders": orders, "statuses": statuses,
        "calendar": "XNYS", "sample_session": session,
        "session_open_utc": calendar.session_open(session).isoformat(),
        "session_close_utc": calendar.session_close(session).isoformat(),
        "source_sha256": hashlib.sha256(args.events.read_bytes()).hexdigest(),
        "parquet_sha256": hashlib.sha256(args.parquet.read_bytes()).hexdigest(),
    }, indent=2))


if __name__ == "__main__":
    main()
