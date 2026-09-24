"""Synthetic fixtures for the forward study's board-to-scan bridge (local integration; no network, no orders)."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blueprints/us-equities/incentive-monitor"))
import board_scan as B  # noqa: E402

NOW = datetime(2026, 9, 24, 17, 31, tzinfo=timezone.utc)  # 13:31 ET


def feat(symbol, p=10.0, chg=0.03, v=500_000, spr=20.0, tt="2026-09-24T17:30:50Z"):
    return {"s": symbol, "p": p, "chg": chg, "v": v, "spr_bps": spr, "tt": tt, "ref": p / (1 + chg)}


def row(symbol, score=3.5, parts=None, relvol=None):
    return {"symbol": symbol, "score": score, "parts": parts if parts is not None else {"news": 1.0, "relvol": 2.5}, "relvol": relvol}


class Selection(unittest.TestCase):
    def test_protocol_is_frozen_and_consistent(self):
        self.assertEqual(B.PROTOCOL["status"], "frozen_before_first_order")
        self.assertEqual(B.PROTOCOL["selection"]["max_symbols"], 5)
        self.assertEqual(set(B.PROTOCOL["decision_times_et"]), {"10:30", "13:30"})

    def test_filters_and_reasons(self):
        features = {"OK": feat("OK"), "PENNY": feat("PENNY", p=1.5), "WIDE": feat("WIDE", spr=80.0), "THIN": feat("THIN", v=50_000),
                    "UP": feat("UP", chg=0.12), "DOWN": feat("DOWN", chg=-0.01), "STALE": feat("STALE", tt="2026-09-24T17:20:00Z")}
        board = [row(s) for s in features] + [row("LOW", score=2.5), row("PRICEONLY", parts={"relvol": 3.0}),
                                              row("DIL", parts={"news": 1.0, "dilution_filing": -1.0, "news_halt": 2.0, "relvol": 1.5}), row("GONE")]
        chosen, rejected = B.select(board, features, NOW)
        self.assertEqual([r["symbol"] for r in chosen], ["OK"])
        self.assertEqual(rejected, {"PENNY": "price", "WIDE": "spread", "THIN": "dollar_volume", "UP": "gain", "DOWN": "gain", "STALE": "stale_last_trade",
                                    "LOW": "score", "PRICEONLY": "no_non_price_component", "DIL": "excluded_component", "GONE": "no_snapshot"})

    def test_order_and_cap(self):
        features = {s: feat(s) for s in "ABCDEFG"}
        board = [row("A", 3.0), row("B", 5.0), row("C", 4.0, relvol=2.0), row("D", 4.0, relvol=9.0), row("E", 4.0), row("F", 3.0), row("G", 3.0)]
        chosen, _ = B.select(board, features, NOW)
        self.assertEqual([r["symbol"] for r in chosen], ["B", "D", "C", "E", "A"])

    def test_controls_are_deterministic_and_exclude_board(self):
        features = {s: feat(s) for s in ("A", "B", "C", "D")} | {"X": feat("X", p=1.0)}
        first = B.controls(features, {"A"}, NOW, "2026-09-24", "13:30", 2)
        self.assertEqual(first, B.controls(features, {"A"}, NOW, "2026-09-24", "13:30", 2))
        self.assertEqual(len(first), 2)
        self.assertFalse({"A", "X"} & set(first))
        self.assertNotEqual(B.controls(features, set(), NOW, "2026-09-25", "13:30", 4), [])

    def test_engine_scan_shape(self):
        features = {"OK": feat("OK", p=12.345678901234, chg=0.0312)}
        scan = B.engine_scan([row("OK")], features, NOW, "13:30")
        self.assertEqual(scan["rule"], "13:30|G0|V1000000|any")
        self.assertEqual((scan["protocol"], scan["source"], scan["scan_time"]), ("mover-early-entry-v1-20260924", "incentive-board-forward-v1-20260924", "2026-09-24T17:31:00Z"))
        (sym,) = scan["symbols"]
        self.assertEqual((sym["rank"], sym["price_at_t"], sym["gain_pct_at_t"]), (1, "12.345678901", "3.12"))
        self.assertLessEqual(len(sym["dollar_volume_at_t"].partition(".")[2]), 9)


class EngineAcceptsTheScan(unittest.TestCase):
    """The engine's own scan loader accepts the bridge's output under the forward rule (skipped without the engine)."""

    def test_load_scan(self):
        sys.path.insert(0, str(ROOT / "blueprints/us-equities/adaptive-paper"))
        try:
            import mover
        except ImportError as exc:  # the engine's pure module needs only the standard library; keep the guard for partial checkouts
            self.skipTest(str(exc))
        config = json.loads((ROOT / "blueprints/us-equities/adaptive-paper/config-mover.json").read_text())
        config["mover"]["rule"] = "13:30|G0|V1000000|any"
        config["mover"]["session_scope"] = "any_session"
        config["mover"]["trial_end_et"] = "14:45"
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(config))
            _, _, settings = mover.load_mover_config(path)
        features = {"OK": feat("OK")}
        raw = json.dumps(B.engine_scan([row("OK")], features, NOW, "13:30")).encode()
        scan = mover.load_scan(raw, settings, now=None)
        self.assertEqual([s.symbol for s in scan.symbols], ["OK"])


if __name__ == "__main__":
    unittest.main()
