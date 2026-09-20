#!/usr/bin/env python3
"""Check retained upstream reports without importing or implementing an engine."""

import argparse
import ast
import copy
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


SOURCE_SHA256 = "487e6807dedd1a38062638eb671f6110799451611819542bf0f0c10646cb2c53"
OBSERVER_SHA256 = "b5cb94472619f6cd5432b7e410f4657fcf8db966fada9032c7dc188739565d30"
UUID4 = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
ENVIRONMENT = {"HOME", "LANG", "PATH", "PYTHONDONTWRITEBYTECODE", "PYTHONHASHSEED",
               "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"}
DISTRIBUTIONS = {"nautilus-trader==2.0.0rc5", "numpy==2.5.3", "pandas==3.0.6",
                 "python-dateutil==2.9.0.post0", "six==1.17.0"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_rows(name, rows):
    """Only the three UUIDv4 locations from the qualified native receipt may vary."""
    result = copy.deepcopy(rows)
    for row in result:
        if name == "fills.csv":
            require(bool(UUID4.fullmatch(row["init_id"])), "fill init_id must be UUIDv4")
            row["init_id"] = "<uuid4>"
        if name == "positions.csv":
            row["position_id"] = UUID4.sub("<uuid4>", row["position_id"])
            events = ast.literal_eval(row["events"])
            require(isinstance(events, list) and events, "position events must be a nonempty list")
            for event in events:
                require(bool(UUID4.fullmatch(event["event_id"])), "event_id must be UUIDv4")
                event["event_id"] = "<uuid4>"
            row["events"] = events
    return result


def reconcile_reports(account, fills, positions):
    require(bool(account and fills and positions), "native reports must not be empty")
    require(all(row["currency"] == "USD" for row in account), "account currency must be USD")
    start = cash = Decimal(account[0]["total"])
    for fill in fills:
        require(fill["status"] == "FILLED", "every order must be filled")
        require(fill["commissions"] == "['0.00 USD']", "unexpected commission")
        require(fill["side"] in {"BUY", "SELL"}, "unexpected fill side")
        cash += Decimal(fill["filled_qty"]) * Decimal(fill["avg_px"]) * (-1 if fill["side"] == "BUY" else 1)
    require(cash == Decimal(account[-1]["total"]), "fill cash does not match the account report")
    require(all(row["realized_pnl"].endswith(" USD") for row in positions), "position PnL currency must be USD")
    pnl = sum((Decimal(row["realized_pnl"].removesuffix(" USD")) for row in positions), Decimal(0))
    require(pnl == cash - start, "position PnL does not reconcile with cash")
    require(all(row["side"] == "FLAT" and Decimal(row["quantity"]) == 0 for row in positions),
            "all positions must finish flat")
    return {"starting_cash_usd": str(start), "ending_cash_usd": str(cash), "realized_pnl_usd": str(pnl)}


def check_isolation(proof, host_namespace):
    require(bool(re.fullmatch(r"net:\[\d+\]", proof["network_namespace"]))
            and proof["network_namespace"] != host_namespace, "network namespace is not isolated")
    require(proof["interfaces"] == [[1, "lo"]], "offline execution must expose only loopback")
    require(proof["home_exists"] is False, "host home must not be mounted")
    require(set(proof["environment_names"]) == ENVIRONMENT, "unexpected inherited environment")


def verify(output):
    require(digest(output / "quickstart.py") == SOURCE_SHA256, "upstream source hash differs")
    require(digest(output / "observe_quickstart.py") == OBSERVER_SHA256, "observer hash differs")
    versions = {line.replace("_", "-") for line in (output / "freeze.txt").read_text().splitlines() if line}
    require(versions == DISTRIBUTIONS, "installed distribution pins differ")
    host_namespace = (output / "host-network-namespace.txt").read_text().strip()
    require(bool(re.fullmatch(r"net:\[\d+\]", host_namespace)), "host network namespace missing")
    summaries, reports, checks = [], [], []
    for run in ("run-1", "run-2"):
        directory = output / run
        require((directory / "exit-code.txt").read_text().strip() == "0", run + " upstream command failed")
        check_isolation(json.loads((directory / "isolation.json").read_text()), host_namespace)
        summary = json.loads((directory / "summary.json").read_text())
        require(summary["version"] == "2.0.0rc5" and summary["generated_bars"] == 10000
                and summary["seed"] == 42 and summary["instrument"] == "EUR/USD.SIM", "fixture identity differs")
        native = summary["native_result"]
        require([native[key] for key in ("iterations", "total_events", "total_orders", "total_positions")]
                == [10000, 1804, 902, 451], "native result counts differ")
        tables = {}
        for name, count in (("account.csv", 903), ("positions.csv", 451), ("fills.csv", 902)):
            with (directory / name).open(newline="") as stream:
                reader = csv.DictReader(stream)
                tables[name] = list(reader)
                require(len(reader.fieldnames or []) == len(set(reader.fieldnames or [])), "duplicate report columns")
            require(len(tables[name]) == count and all(None not in row and None not in row.values()
                    for row in tables[name]), "native report count or shape differs: " + name)
        check = reconcile_reports(tables["account.csv"], tables["fills.csv"], tables["positions.csv"])
        require(Decimal(check["starting_cash_usd"]) == Decimal("1000000.00")
                and Decimal(check["realized_pnl_usd"]) == Decimal("431.00"), "qualified fixture cash result differs")
        cleanup = json.loads((directory / "cleanup.json").read_text())
        require(cleanup == {"upstream_script_completed_after_dispose": True, "account_rows_after_dispose": 0},
                "native cleanup did not complete")
        summaries.append(summary); reports.append(tables); checks.append(check)
    require(summaries[0]["native_result"] == summaries[1]["native_result"], "native analyzer results differ")
    comparisons = {}
    for name in reports[0]:
        left, right = (normalize_rows(name, report[name]) for report in reports)
        require(left == right, "economic report differs outside validated UUIDv4 fields: " + name)
        raw_equal = digest(output / "run-1" / name) == digest(output / "run-2" / name)
        if name == "account.csv":
            require(raw_equal, "account report bytes differ")
        comparisons[name] = {"rows": len(left), "raw_sha256_equal": raw_equal,
            "normalized_sha256": hashlib.sha256(json.dumps(left, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    return {"cash_reconciliation": checks, "report_comparison": comparisons,
            "native_result_equal": True, "source_sha256": SOURCE_SHA256, "observer_sha256": OBSERVER_SHA256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    receipt = {"recorded_at": datetime.now(timezone.utc).isoformat(), "status": "failed", "native_acceptance": False,
        "scope": "Fresh CI host: unchanged upstream synthetic EUR/USD example and fresh-process replay only.",
        "limitations": ["No equity dataset, strategy, broker, account entitlement or order-recovery acceptance.",
                        "Network denial is namespace isolation, not a measured count of attempted external transports."]}
    try:
        receipt["results"] = verify(args.output)
        receipt.update(status="passed", native_acceptance=True)
    except (OSError, ValueError, KeyError, TypeError, SyntaxError, ArithmeticError) as error:
        receipt["error"] = str(error)
    receipt["artifacts"] = {str(path.relative_to(args.output)): {"sha256": digest(path), "bytes": path.stat().st_size}
        for path in sorted(args.output.rglob("*")) if path.is_file() and path.name != "verification.json"}
    (args.output / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"status": receipt["status"], "error": receipt.get("error"), "receipt": str(args.output / "verification.json")}))
    return 0 if receipt["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
