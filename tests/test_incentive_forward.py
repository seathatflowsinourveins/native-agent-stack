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
        self.assertNotIn("volatility_halt", B.PROTOCOL["selection"]["required_any_component"])
        for at, pin in B.PROTOCOL["execution"]["configs"].items():
            self.assertEqual(B.sha(ROOT / pin["path"]), pin["sha256"], at)
            config = json.loads((ROOT / pin["path"]).read_text())
            self.assertEqual(config["mover"]["rule"], B.PROTOCOL["execution"]["rule_template"].replace("HH:MM", at))
            self.assertEqual(config["mover"]["rung_schedule"], [{"from_session": 1, "to_session": 400, "rung": "1"}])
        for key in ("cost_table",):
            ref = B.PROTOCOL["outcomes"][key]
            self.assertEqual(B.sha(ROOT / ref["path"]), ref["sha256"])

    def test_filters_and_reasons(self):
        features = {"OK": feat("OK"), "PENNY": feat("PENNY", p=1.5), "WIDE": feat("WIDE", spr=80.0), "THIN": feat("THIN", v=50_000),
                    "UP": feat("UP", chg=0.12), "DOWN": feat("DOWN", chg=-0.01), "STALE": feat("STALE", tt="2026-09-24T17:20:00Z")}
        features["BAD1"] = feat("BAD1")
        board = [row(s) for s in features] + [row("LOW", score=2.5), row("PRICEONLY", parts={"relvol": 3.0}),
                                              row("LUDP", parts={"volatility_halt": 1.0, "relvol": 2.0}),
                                              row("DIL", parts={"news": 1.0, "dilution_filing": -1.0, "news_halt": 2.0, "relvol": 1.5}), row("GONE")]
        chosen, rejected = B.select(board, features, NOW)
        self.assertEqual([r["symbol"] for r in chosen], ["OK"])
        self.assertEqual(rejected, {"PENNY": "price", "WIDE": "spread", "THIN": "dollar_volume", "UP": "gain", "DOWN": "gain", "STALE": "stale_last_trade",
                                    "BAD1": "symbol", "LOW": "score", "PRICEONLY": "no_non_price_component", "LUDP": "no_non_price_component",
                                    "DIL": "excluded_component", "GONE": "no_snapshot"})

    def test_order_and_cap(self):
        features = {s: feat(s) for s in "ABCDEFG"}
        board = [row("A", 3.0), row("B", 5.0), row("C", 4.0, relvol=2.0), row("D", 4.0, relvol=9.0), row("E", 4.0), row("F", 3.0), row("G", 3.0)]
        chosen, _ = B.select(board, features, NOW)
        self.assertEqual([r["symbol"] for r in chosen], ["B", "D", "C", "E", "A"])

    def test_controls_are_matched_deterministic_and_incentive_free(self):
        features = {"SELA": feat("SELA", chg=0.01), "SELB": feat("SELB", chg=0.07)}
        features |= {f"L{c}": feat(f"L{c}", chg=0.02) for c in "ABCDEF"} | {f"H{c}": feat(f"H{c}", chg=0.08) for c in "ABC"}
        features |= {"NEWSY": feat("NEWSY", chg=0.02), "PENNY": feat("PENNY", p=1.0, chg=0.02)}
        chosen = [row("SELA"), row("SELB")]
        excluded = {"SELA", "SELB", "NEWSY"}
        first = B.controls(chosen, features, excluded, NOW, "2026-09-24", "13:30")
        self.assertEqual(first, B.controls(chosen, features, excluded, NOW, "2026-09-24", "13:30"))
        self.assertEqual(len(first["SELA"]), 4)
        self.assertTrue(all(s.startswith("L") for s in first["SELA"]))
        self.assertEqual(sorted(first["SELB"]), ["HA", "HB", "HC"])
        self.assertFalse({"NEWSY", "PENNY"} & set(first["SELA"] + first["SELB"]))
        self.assertEqual(len(B.controls([row("SELA"), row("SELC")], features | {"SELC": feat("SELC", chg=0.02)}, excluded | {"SELC"}, NOW, "d", "13:30")["SELC"]), 2)  # 6 low-bucket names, 4 used

    def test_timing_guard(self):
        at = lambda h, m, s=0: datetime(2026, 9, 24, h, m, s, tzinfo=B.M.ET)
        self.assertEqual(B.timing_refusal(at(13, 29, 59), "13:30"), "before_decision_time")
        self.assertIsNone(B.timing_refusal(at(13, 30), "13:30"))
        self.assertIsNone(B.timing_refusal(at(13, 35), "13:30"))
        self.assertEqual(B.timing_refusal(at(13, 35, 1), "13:30"), "after_late_guard")

    def test_engine_scan_shape(self):
        features = {"OK": feat("OK", p=12.345678901234, chg=0.0312)}
        scan = B.engine_scan([row("OK")], features, NOW, "13:30")
        self.assertEqual(scan["rule"], "13:30|G0|V1000000|any")
        self.assertEqual((scan["protocol"], scan["source"], scan["scan_time"]), ("mover-early-entry-v1-20260924", "incentive-board-forward-v1-20260924", "2026-09-24T17:31:00Z"))
        (sym,) = scan["symbols"]
        self.assertEqual((sym["rank"], sym["price_at_t"], sym["gain_pct_at_t"]), (1, "12.345678901", "3.12"))
        self.assertLessEqual(len(sym["dollar_volume_at_t"].partition(".")[2]), 9)


class Ledger(unittest.TestCase):
    def test_decisions_are_exclusive_and_session_controls_are_shared(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp)
            B.write_exclusive(ledger / "2026-09-24-1030.json", {"selected": [{"symbol": "AAA"}], "controls": {"AAA": [{"symbol": "CCA"}, {"symbol": "CCB"}]}})
            B.write_exclusive(ledger / "2026-09-24-1030-refused-1.json", {"selected": [{"symbol": "ZZZ"}]})
            with self.assertRaises(FileExistsError):
                B.write_exclusive(ledger / "2026-09-24-1030.json", {})
            self.assertEqual(B.session_used(ledger, "2026-09-24", "13:30"), {"AAA", "CCA", "CCB"})
            self.assertEqual(B.session_used(ledger, "2026-09-24", "10:30"), set())  # its own record is not "the other decision"
            self.assertEqual(B.session_used(ledger, "2026-09-25", "10:30"), set())

    def test_operating_universe_excludes_funds(self):
        M = B.M
        names = {"AAPL": "Apple Inc. Common Stock", "SPY": "SPDR S&P 500 ETF Trust", "QQQ": "Invesco QQQ Trust", "GLD": "SPDR Gold Trust",
                 "BRK.B": "Berkshire Hathaway Inc. Class B", "CEF": "Sprott Physical Gold and Silver Fund", "NOSEC": "Unlisted Corp"}
        company = {"AAPL", "SPY", "GLD", "BRK.B", "CEF"}
        self.assertEqual(M.operating_symbols(names, company, {"QQQ"}), {"AAPL", "BRK.B"})
        features = {"AAPL": feat("AAPL"), "SPY": feat("SPY")}
        chosen, rejected = B.select([row("AAPL"), row("SPY")], features, NOW, {"AAPL"})
        self.assertEqual(([r["symbol"] for r in chosen], rejected), (["AAPL"], {"SPY": "not_operating_company"}))


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


class BoardVersion(unittest.TestCase):
    """Protocol v1 runs on board version 1 only (board.json); board-v2.json and unversioned boards are refused."""

    def test_protocol_v1_pins_board_version_1_without_editing_the_frozen_file(self):
        self.assertEqual((B.BOARD_VERSION, B.M.BOARD_VERSION), (1, 1))
        self.assertNotIn("board_version", B.PROTOCOL)

    def decide(self, board: dict):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "board.json").write_text(json.dumps(board))
            at = B.PROTOCOL["decision_times_et"][0]
            pin = B.PROTOCOL["execution"]["configs"][at]["path"]
            with mock.patch.object(B, "timing_refusal", lambda now, at: None):
                rc = B.main(["--env-file", str(tmp / "absent.env"), "--board", str(tmp / "board.json"), "--at-et", at, "--config", str(ROOT / pin),
                             "--engine-dir", str(ROOT / "blueprints/us-equities/adaptive-paper"), "--records", str(tmp / "ledger"), "--out", str(tmp / "scan.json")])
            (refusal,) = list((tmp / "ledger").glob("*-refused-*.json"))
            return rc, json.loads(refusal.read_text())

    def test_boards_of_another_version_are_refused(self):
        v1, v2 = B.M.board_payloads(datetime.now(timezone.utc), [], [], [], [], {"code_sha256": B.sha(B.HERE / "monitor.py")})
        unversioned = {k: v for k, v in v1.items() if k != "board_version"}
        for board in (v2, unversioned, {**v1, "board_version": True}, {**v1, "board_version": "1"}):
            rc, record = self.decide(board)
            self.assertEqual((rc, record["reason"], record["protocol_board_version"]), (4, "board_version_mismatch", 1), board.get("board_version"))
            self.assertEqual(record["board_version"], board.get("board_version"))
        rc, record = self.decide(v1)  # version 1 passes; then this bridge's code is not protocol v1's frozen code
        self.assertEqual((rc, record["reason"], record["board_version"], record["frozen"]), (4, "code_not_frozen", 1, B.M.FROZEN_V1))

    def test_only_the_frozen_code_goes_past_the_code_check(self):
        from unittest import mock
        v1, _ = B.M.board_payloads(datetime.now(timezone.utc), [], [], [], [], {"code_sha256": B.sha(B.HERE / "monitor.py")})
        current = {"monitor.py": B.sha(B.HERE / "monitor.py"), "board_scan.py": B.sha(B.HERE / "board_scan.py")}
        self.assertNotEqual(current, B.M.FROZEN_V1)   # this code is not protocol v1's
        self.assertEqual(B.FROZEN_CODE[B.PROTOCOL["id"]], B.M.FROZEN_V1)
        with mock.patch.dict(B.FROZEN_CODE, {B.PROTOCOL["id"]: current}):
            rc, record = self.decide(v1)
        self.assertEqual((rc, record["reason"], record["board_version"]), (4, "snapshot_failed", 1))  # stops at the absent credential file


class MonitorBinding(unittest.TestCase):
    def test_board_from_other_monitor_code_is_refused(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            board = tmp / "board.json"
            board.write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "board": [], "monitor": {"code_sha256": "0" * 64}}))
            out = tmp / "scan.json"
            out.write_text("stale scan from an earlier decision")
            at = B.PROTOCOL["decision_times_et"][0]
            pin = B.PROTOCOL["execution"]["configs"][at]["path"]
            with mock.patch.object(B, "timing_refusal", lambda now, at: None):
                rc = B.main(["--env-file", str(tmp / "none.env"), "--board", str(board), "--at-et", at, "--config", str(ROOT / pin),
                             "--engine-dir", str(ROOT / "blueprints/us-equities/adaptive-paper"), "--records", str(tmp / "ledger"), "--out", str(out)])
            self.assertEqual(rc, 4)
            self.assertFalse(out.exists())
            (refusal,) = list((tmp / "ledger").glob("*-refused-*.json"))
            self.assertEqual(json.loads(refusal.read_text())["reason"], "monitor_code_mismatch")
