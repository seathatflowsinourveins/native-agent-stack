"""Synthetic SQLite consolidation checks; no accounts, sockets, or real STOP files."""
from dataclasses import replace
from decimal import Decimal as D
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "blueprints/us-equities/adaptive-paper/ledger_consolidation.py"
SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE intents(client_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,side TEXT NOT NULL,
 qty TEXT NOT NULL,limit_price TEXT NOT NULL,status TEXT NOT NULL,filled_qty TEXT NOT NULL,
 average_price TEXT,broker_id TEXT UNIQUE,submit_attempted INTEGER NOT NULL,updated_at REAL);
CREATE TABLE positions(symbol TEXT PRIMARY KEY,qty TEXT NOT NULL,cost_basis TEXT NOT NULL);
CREATE TABLE marks(symbol TEXT PRIMARY KEY,bid TEXT NOT NULL,ask TEXT NOT NULL,at REAL NOT NULL);
CREATE TABLE requests(id INTEGER PRIMARY KEY,at REAL NOT NULL,kind TEXT NOT NULL,
 client_id TEXT REFERENCES intents(client_id));
CREATE TABLE events(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,client_id TEXT,payload TEXT NOT NULL);
CREATE TABLE trials(trial_id TEXT PRIMARY KEY,started_at REAL NOT NULL);
"""


class ConsolidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODULE.exists():
            raise AssertionError("The bounded consolidation API has not been implemented")
        spec = importlib.util.spec_from_file_location("paper_ledger_consolidation", MODULE)
        cls.m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.m
        spec.loader.exec_module(cls.m)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.fp = hashlib.sha256(b"synthetic-account").hexdigest()
        self.lock = self.root / (self.fp + ".lock")
        self.lock_file = self.lock.open("w")
        fcntl.flock(self.lock_file, fcntl.LOCK_EX)
        self.stop = self.root / "STOP"
        self.stop.write_text("test-only stop remains")
        self.original = self.fixture("original", 100, "10000", halt="recovery_only")
        self.first = self.fixture("first", 200, "10000", sells=("99.70", "100.01"))
        self.second = self.fixture("second", 300, "9999.71", sells=("99.18", "100.30"), peak="0.45", high_limits=True)

    def tearDown(self):
        self.lock_file.close()
        self.tmp.cleanup()

    def fixture(self, label, start, baseline, *, sells=(), peak="0", halt=None,
                high_limits=False, trials=True, account_path=True, canceled=False):
        parent = self.root / label / (self.fp if account_path else "unscoped")
        parent.mkdir(parents=True)
        dbpath = parent / "ledger.sqlite3"
        db = sqlite3.connect(dbpath)
        db.executescript(SCHEMA)
        limits = {"max_order_qty": "100" if high_limits else "1",
                  "max_order_qty_mode": "notional" if high_limits else "fixed",
                  "max_gross_exposure_usd": "10000" if high_limits else "5000"}
        meta = {"schema_version": "1", "limits": json.dumps(limits, sort_keys=True),
                "realized": "0", "cash_delta": "0", "realized_loss": "0",
                "peak_pnl": peak, "trial_start": str(start)}
        if halt:
            meta["halted_reason"] = halt
            meta["recovery_only"] = "1"
        if trials:
            meta["trial_id"] = label
            db.execute("INSERT INTO trials VALUES (?,?)", (label, start))
        db.execute("INSERT INTO requests(at,kind) VALUES (?,?)", (start, "read"))
        db.execute("INSERT INTO events(kind,payload) VALUES (?,?)", ("trial_start", json.dumps({"at": start})))
        cash = loss = D(0)
        for index, price in enumerate(sells):
            for side, fill in (("buy", "100"), ("sell", price)):
                cid = f"{label}-{index}-{side}"
                at = start + index * 4 + (1 if side == "buy" else 2)
                limit = "101" if side == "buy" else "90"
                db.execute("INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (cid, "SPY", side, "1", limit, "filled", "1", fill, "b-" + cid, 1, at))
                db.execute("INSERT INTO requests(at,kind,client_id) VALUES (?,?,?)", (at, "submit", cid))
                payload = {"at": at, "broker_id": "b-" + cid, "status": "filled",
                           "filled_qty": "1", "average_price": fill, "delta_qty": "1", "delta_notional": fill}
                db.execute("INSERT INTO events(kind,client_id,payload) VALUES (?,?,?)", ("order_observed", cid, json.dumps(payload)))
                cash += D(fill) * (1 if side == "sell" else -1)
            loss += max(D(0), D(100) - D(price))
        if sells:
            db.execute("INSERT INTO positions VALUES ('SPY','0','0')")
        if canceled:
            cid = label + "-cancel"
            db.execute("INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (cid, "SPY", "buy", "1", "100", "canceled", "0", None, "b-" + cid, 1, start + 2))
            db.execute("INSERT INTO requests(at,kind,client_id) VALUES (?,?,?)", (start + 1, "submit", cid))
            db.execute("INSERT INTO requests(at,kind,client_id) VALUES (?,?,?)", (start + 2, "cancel", cid))
            payload = {"at": start + 2, "broker_id": "b-" + cid, "status": "canceled", "filled_qty": "0",
                       "average_price": None, "delta_qty": "0", "delta_notional": "0"}
            db.execute("INSERT INTO events(kind,client_id,payload) VALUES (?,?,?)", ("order_observed", cid, json.dumps(payload)))
        meta.update(cash_delta=str(cash), realized=str(cash), realized_loss=str(loss))
        db.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
        db.commit()
        db.close()
        if baseline is not None:
            (parent / "trial.json").write_text(json.dumps({"baseline_cash": baseline, "started_at": start,
                                                         "phase": "finished", "status": "passed"}))
        return dbpath

    def plan(self, sources=None):
        return self.m.plan(self.original, sources if sources is not None else [self.first, self.second], lock_path=self.lock)

    def proof(self, sources=None):
        orders = []
        delta = D(0)
        for path in [self.original] + (sources if sources is not None else [self.first, self.second]):
            path = path.db_path if isinstance(path, self.m.Source) else path
            with sqlite3.connect(path) as db:
                db.row_factory = sqlite3.Row
                delta += D(db.execute("SELECT value FROM meta WHERE key='cash_delta'").fetchone()[0])
                for row in db.execute("SELECT * FROM intents"):
                    orders.append({"client_order_id": row["client_id"], "id": row["broker_id"], "symbol": row["symbol"],
                                   "side": row["side"], "qty": row["qty"], "filled_qty": row["filled_qty"],
                                   "filled_avg_price": row["average_price"], "status": row["status"],
                                   "limit_price": row["limit_price"]})
        activities = [{"id": "activity-" + r["id"], "activity_type": "FILL", "order_id": r["id"],
                       "symbol": r["symbol"], "side": r["side"], "qty": r["filled_qty"], "price": r["filled_avg_price"]}
                      for r in orders if D(r["filled_qty"]) > 0]
        return {"account_fingerprint": self.fp, "observed_at": 1000.0, "endpoint": "https://paper-api.alpaca.markets",
                "cash": str(D(10000) + delta), "positions": [], "open_orders": [], "orders": orders,
                "history_complete": True, "unmatched_activity": [], "activities_complete": True,
                "activities": activities}

    def apply(self, plan=None, proof=None):
        return self.m.apply(plan or self.plan(), proof or self.proof(), lock_path=self.lock, now=1001.0)

    def edit(self, path, sql, args=()):
        with sqlite3.connect(path) as db:
            db.execute(sql, args)

    def snapshot(self, path):
        with sqlite3.connect(path) as db:
            return {t: list(db.execute("SELECT * FROM " + t + " ORDER BY rowid"))
                    for t in ("meta", "intents", "positions", "marks", "requests", "events", "trials")}

    def test_read_only_plan_and_atomic_append_preserve_original_limits_baseline_halt(self):
        original = self.snapshot(self.original)
        sidecar = (self.original.parent / "trial.json").read_bytes()
        source = self.snapshot(self.first)
        plan = self.plan()
        self.assertEqual(self.snapshot(self.original), original)
        self.assertEqual(plan.summary["cash_delta"], "-0.81")
        self.assertEqual(plan.summary["realized_loss"], "1.12")
        self.assertEqual(plan.summary["peak_pnl"], "0.16")
        receipt = self.apply(plan)
        self.assertEqual(receipt["status"], "applied")
        after = self.snapshot(self.original)
        self.assertEqual(len(after["intents"]), 8)
        self.assertEqual(len(after["requests"]), 11)
        self.assertEqual(len(after["trials"]), 3)
        before_meta, after_meta = dict(original["meta"]), dict(after["meta"])
        for key in ("limits", "halted_reason", "recovery_only", "trial_start", "trial_id"):
            self.assertEqual(after_meta[key], before_meta[key])
        self.assertEqual(after_meta["realized_loss"], "1.12")
        self.assertEqual((self.original.parent / "trial.json").read_bytes(), sidecar)
        self.assertEqual(self.snapshot(self.first), source)
        self.assertEqual(self.stop.read_text(), "test-only stop remains")

    def test_wal_backup_includes_uncheckpointed_rows(self):
        db = sqlite3.connect(self.first)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("INSERT INTO requests(at,kind) VALUES (208,'read')")
            db.commit()
            self.assertGreater(Path(str(self.first) + "-wal").stat().st_size, 0)
            self.assertEqual(self.plan().summary["counts"]["requests"], 12)
        finally:
            db.close()

    def test_apply_refuses_changed_wal_and_changed_trial_sidecar(self):
        for change in ("wal", "sidecar"):
            with self.subTest(change=change):
                plan = self.plan()
                if change == "wal":
                    self.edit(self.first, "INSERT INTO requests(at,kind) VALUES (209,'read')")
                else:
                    (self.first.parent / "trial.json").write_text('{"baseline_cash":"10001","started_at":200}')
                with self.assertRaisesRegex(self.m.ConsolidationError, "source_changed"):
                    self.apply(plan)

    def test_requires_actual_current_process_global_flock(self):
        fcntl.flock(self.lock_file, fcntl.LOCK_UN)
        with self.assertRaisesRegex(self.m.ConsolidationError, "account_lock"):
            self.plan()

    def test_refuses_baseline_gap_nonflat_nonterminal_and_duplicate_identity(self):
        cases = [("UPDATE positions SET qty='1'", "flat"),
                 ("UPDATE intents SET status='new' WHERE side='buy'", "terminal"),
                 ("UPDATE meta SET value='8' WHERE key='realized_loss'", "replay")]
        for sql, message in cases:
            with self.subTest(sql=sql):
                before = self.first.read_bytes()
                self.edit(self.first, sql)
                with self.assertRaisesRegex(self.m.ConsolidationError, message):
                    self.plan()
                self.first.write_bytes(before)
        sidecar = self.second.parent / "trial.json"
        sidecar.write_text('{"baseline_cash":"9999","started_at":300}')
        with self.assertRaisesRegex(self.m.ConsolidationError, "baseline"):
            self.plan()

    def test_unknown_order_stale_cash_account_and_live_endpoint_proofs_refused(self):
        plan = self.plan()
        for mutation in (lambda p:p.update(observed_at=900), lambda p:p.update(cash="9990"),
                         lambda p:p.update(account_fingerprint="0"*64),
                         lambda p:p.update(endpoint="https://api.alpaca.markets"),
                         lambda p:p["orders"].append(dict(p["orders"][0], id="unknown",client_order_id="unknown")),
                         lambda p:p.update(history_complete=False), lambda p:p.update(unmatched_activity=["fee"]),
                         lambda p:p["orders"][0].update(filled_qty="0")):
            with self.subTest(mutation=mutation):
                proof = self.proof()
                mutation(proof)
                with self.assertRaises(self.m.ConsolidationError):
                    self.apply(plan, proof)
        self.assertEqual(len(self.snapshot(self.original)["intents"]), 0)

    def test_duplicate_trial_or_order_identity_is_not_silently_deduplicated(self):
        self.edit(self.second, "UPDATE trials SET trial_id='first'")
        with self.assertRaisesRegex(self.m.ConsolidationError, "duplicate"):
            self.plan()

    def test_zero_fill_fault_ledger_without_trial_requires_account_attestation(self):
        fault = self.fixture("fault", 205, None, trials=False, account_path=False, canceled=True)
        with self.assertRaisesRegex(self.m.ConsolidationError, "account"):
            self.plan([self.first, fault, self.second])
        provenance = fault.parent / "receipt.json"
        provenance.write_text('{"endpoint":"https://paper-api.alpaca.markets","status":"incomplete"}')
        source = self.m.Source(fault, account_fingerprint=self.fp, provenance_path=provenance)
        sources = [self.first, source, self.second]
        receipt = self.apply(self.plan(sources), self.proof(sources))
        self.assertEqual(receipt["counts"]["intents"], 9)
        self.assertEqual(receipt["counts"]["trials"], 3)

    def test_native_fault_legacy_receipt_pair_preserved_without_changing_broker_proof(self):
        fault = self.fixture("legacy-fault", 205, None, trials=False, account_path=False, canceled=True)
        provenance = fault.parent / "receipt.json"
        original = b'{"broker":"alpaca", "endpoint":"paper", "status":"native_faults_incomplete"}\n'
        provenance.write_bytes(original)
        source = self.m.Source(fault, account_fingerprint=self.fp, provenance_path=provenance)
        sources = [self.first, source, self.second]
        plan, proof = self.plan(sources), self.proof(sources)
        enum_proof = dict(proof, endpoint="paper")
        with self.assertRaisesRegex(self.m.ConsolidationError, "not_paper"):
            self.apply(plan, enum_proof)
        receipt = self.apply(plan, proof)
        self.assertEqual(receipt["counts"]["intents"], 9)
        self.assertEqual(provenance.read_bytes(), original)
        with sqlite3.connect(self.original) as db:
            archived = json.loads(db.execute("SELECT payload FROM consolidation_sources WHERE path=?", (str(fault),)).fetchone()[0])
        self.assertEqual(archived["provenance"]["endpoint"], "paper")
        self.assertEqual(archived["provenance"]["broker"], "alpaca")

    def test_legacy_fault_provenance_wrong_broker_or_live_endpoint_refused(self):
        fault = self.fixture("bad-provenance", 205, None, trials=False, account_path=False, canceled=True)
        provenance = fault.parent / "receipt.json"
        source = self.m.Source(fault, account_fingerprint=self.fp, provenance_path=provenance)
        for broker, endpoint in (("other", "paper"), ("alpaca", "live"),
                                 ("alpaca", "https://api.alpaca.markets"), (None, "paper"),
                                 ("other", "https://paper-api.alpaca.markets")):
            with self.subTest(broker=broker, endpoint=endpoint):
                provenance.write_text(json.dumps({"broker": broker, "endpoint": endpoint}))
                with self.assertRaisesRegex(self.m.ConsolidationError, "account_attestation"):
                    self.plan([self.first, source, self.second])

    def test_retry_same_plan_is_idempotent_and_preserves_append_only_history(self):
        plan, proof = self.plan(), self.proof()
        first = self.apply(plan, proof)
        before = self.snapshot(self.original)
        second = self.apply(plan, proof)
        self.assertEqual(first["plan_digest"], second["plan_digest"])
        self.assertEqual(second["status"], "already_applied")
        self.assertEqual(self.snapshot(self.original), before)

    def test_transaction_failure_rolls_back_every_insert_and_accounting_change(self):
        plan = self.plan()
        before = self.snapshot(self.original)
        copy = self.m._append_source
        def fail_after_copy(*args, **kwargs):
            copy(*args, **kwargs)
            raise RuntimeError("injected interruption")
        with patch.object(self.m, "_append_source", fail_after_copy):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.apply(plan)
        self.assertEqual(self.snapshot(self.original), before)

    def test_partial_fill_replay_preserves_gross_loss_hidden_by_terminal_average(self):
        with sqlite3.connect(self.first) as db:
            rows = list(db.execute("SELECT kind,client_id,payload FROM events ORDER BY id"))
            db.execute("DELETE FROM events")
            for kind, cid, raw in rows:
                value = json.loads(raw)
                if cid == "first-0-sell":
                    partial = dict(value, status="partially_filled", filled_qty="0.5", average_price="100.10",
                                   delta_qty="0.5", delta_notional="50.050", at=value["at"] - .1)
                    db.execute("INSERT INTO events(kind,client_id,payload) VALUES (?,?,?)", (kind, cid, json.dumps(partial)))
                    value.update(delta_qty="0.5", delta_notional="49.650")
                db.execute("INSERT INTO events(kind,client_id,payload) VALUES (?,?,?)", (kind, cid, json.dumps(value)))
            db.execute("UPDATE meta SET value='0.35' WHERE key='realized_loss'")
        plan = self.plan()
        self.assertEqual(D(plan.summary["cash_delta"]), D("-0.81"))
        self.assertEqual(D(plan.summary["realized_loss"]), D("1.17"))
        receipt = self.apply(plan)
        self.assertEqual(receipt["destination_counts"]["events"], plan.summary["counts"]["events"] + 1)

    def test_audited_accounting_oracle_does_not_copy_later_local_peak(self):
        e = self.fixture("e", 200, "10000", sells=("99.99",))
        f = self.fixture("f", 300, "9999.99", sells=("99.70", "100.01"))
        g = self.fixture("g", 400, "9999.70", sells=("99.72",))
        i = self.fixture("i", 500, "9999.42", sells=("99.18", "100.30"), peak="0.45", high_limits=True)
        plan = self.plan([e, f, g, i])
        self.assertEqual(D(plan.summary["cash_delta"]), D('-1.10'))
        self.assertEqual(D(plan.summary["realized_loss"]), D('1.41'))
        self.assertEqual(D(plan.summary["peak_pnl"]), 0)
        self.assertEqual(D(plan.summary["drawdown"]), D('1.10'))

    def test_request_only_overlap_preserves_all_requests(self):
        diagnostic = self.fixture("diagnostic", 203, "9999.70")
        plan = self.plan([self.first, diagnostic, self.second])
        self.assertEqual(plan.summary["counts"]["requests"], 12)
        self.apply(plan, self.proof([self.first, diagnostic, self.second]))

    def test_overlapping_economic_segments_are_refused(self):
        overlap = self.fixture("overlap", 201.5, "9900", sells=("100",))
        with self.assertRaisesRegex(self.m.ConsolidationError, "overlapping"):
            self.plan([self.first, overlap])

    def test_tampered_plan_and_unknown_schema_are_refused(self):
        plan = self.plan()
        with self.assertRaisesRegex(self.m.ConsolidationError, "plan_digest"):
            self.apply(replace(plan, digest="0" * 64))
        self.edit(self.first, "ALTER TABLE intents ADD COLUMN unexpected TEXT")
        with self.assertRaisesRegex(self.m.ConsolidationError, "schema"):
            self.plan()

    def test_source_mutation_during_apply_rolls_back_destination(self):
        plan = self.plan()
        before = self.snapshot(self.original)
        copy = self.m._append_source
        def mutate_source(*args, **kwargs):
            copy(*args, **kwargs)
            self.edit(self.first, "INSERT INTO requests(at,kind) VALUES (208,'read')")
        with patch.object(self.m, "_append_source", mutate_source):
            with self.assertRaisesRegex(self.m.ConsolidationError, "source_changed"):
                self.apply(plan)
        self.assertEqual(self.snapshot(self.original), before)

    def test_original_sidecar_change_during_apply_is_not_committed(self):
        plan = self.plan()
        before = self.snapshot(self.original)
        copy = self.m._append_source
        def mutate_baseline(*args, **kwargs):
            copy(*args, **kwargs)
            (self.original.parent / "trial.json").write_text('{"baseline_cash":"5000","started_at":100}')
        with patch.object(self.m, "_append_source", mutate_baseline):
            with self.assertRaisesRegex(self.m.ConsolidationError, "baseline_changed"):
                self.apply(plan)
        self.assertEqual(self.snapshot(self.original), before)

    def test_larger_historical_quantity_does_not_raise_original_quantity_limit(self):
        with sqlite3.connect(self.first) as db:
            db.execute("UPDATE intents SET qty='2',filled_qty='2'")
            for rowid, raw in list(db.execute("SELECT id,payload FROM events WHERE kind='order_observed'")):
                value = json.loads(raw)
                value.update(filled_qty="2", delta_qty="2", delta_notional=str(D(value["delta_notional"]) * 2))
                db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(value), rowid))
            for key in ("cash_delta", "realized", "realized_loss"):
                old = db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()[0]
                db.execute("UPDATE meta SET value=? WHERE key=?", (str(D(old) * 2), key))
        sources = [self.first]
        self.apply(self.plan(sources), self.proof(sources))
        after = self.snapshot(self.original)
        self.assertTrue(all(row[3] == "2" for row in after["intents"]))
        self.assertEqual(json.loads(dict(after["meta"])["limits"])["max_order_qty"], "1")

    def test_request_history_survives_row_id_remapping_exactly(self):
        expected = []
        for path in (self.original, self.first, self.second):
            with sqlite3.connect(path) as db:
                expected.extend(db.execute("SELECT at,kind,client_id FROM requests"))
        self.apply()
        with sqlite3.connect(self.original) as db:
            self.assertEqual(sorted(db.execute("SELECT at,kind,client_id FROM requests")), sorted(expected))
            self.assertEqual(db.execute("SELECT count(*) FROM consolidation_sources").fetchone()[0], 3)

    def test_broker_proof_cannot_age_out_during_transaction(self):
        plan = self.plan()
        before = self.snapshot(self.original)
        with patch.object(self.m.time, "monotonic", side_effect=[100.0, 140.0]):
            with self.assertRaisesRegex(self.m.ConsolidationError, "stale"):
                self.apply(plan)
        self.assertEqual(self.snapshot(self.original), before)

    def test_broker_limit_price_must_match_frozen_intent(self):
        proof = self.proof()
        proof["orders"][0]["limit_price"] = "999"
        with self.assertRaisesRegex(self.m.ConsolidationError, "price_mismatch"):
            self.apply(self.plan(), proof)

    def test_replaced_is_not_a_supported_terminal_status(self):
        with sqlite3.connect(self.first) as db:
            db.execute("UPDATE intents SET status='replaced'")
            for rowid, raw in list(db.execute("SELECT id,payload FROM events WHERE kind='order_observed'")):
                value = json.loads(raw)
                value["status"] = "replaced"
                db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(value), rowid))
        with self.assertRaisesRegex(self.m.ConsolidationError, "terminal"):
            self.plan()

    def test_economic_fills_cannot_lose_broker_identity_and_escape_proof(self):
        with sqlite3.connect(self.first) as db:
            db.execute("UPDATE intents SET broker_id=NULL")
            for rowid, raw in list(db.execute("SELECT id,payload FROM events WHERE kind='order_observed'")):
                value = json.loads(raw)
                value["broker_id"] = None
                db.execute("UPDATE events SET payload=? WHERE id=?", (json.dumps(value), rowid))
        with self.assertRaisesRegex(self.m.ConsolidationError, "broker_identity"):
            self.plan()

    def test_peak_cannot_be_below_replayed_intermediate_flat_profit(self):
        source = self.fixture("profit_then_loss", 200, "10000", sells=("101", "98"), peak="0")
        with self.assertRaisesRegex(self.m.ConsolidationError, "peak"):
            self.plan([source])

    def test_activity_coverage_must_be_complete_known_and_exact(self):
        plan = self.plan()
        mutations = [lambda p:p.update(activities_complete=False),
                     lambda p:p["activities"].pop(),
                     lambda p:p["activities"].append(dict(p["activities"][0])),
                     lambda p:p["activities"][0].update(order_id="unknown"),
                     lambda p:p["activities"][0].update(qty="0"),
                     lambda p:p["activities"][0].update(price="99.999999999"),
                     lambda p:p["activities"][0].update(symbol="QQQ"),
                     lambda p:p["activities"][0].update(side="sell"),
                     lambda p:p["activities"].extend([{"id":"fee","activity_type":"FEE","net_amount":"-1"},
                                                        {"id":"rebate","activity_type":"DIV","net_amount":"1"}])]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                proof = self.proof()
                mutate(proof)
                with self.assertRaisesRegex(self.m.ConsolidationError, "activit"):
                    self.apply(plan, proof)
        self.assertEqual(len(self.snapshot(self.original)["intents"]), 0)

    def test_separate_partial_activities_match_terminal_cumulative_notional(self):
        proof = self.proof()
        row = proof["activities"].pop(0)
        proof["activities"].extend([dict(row, id="partial-one",qty="0.25",price="99.97"),
                                     dict(row, id="partial-two",qty="0.75",price="100.01")])
        self.apply(self.plan(), proof)

    def test_actual_ledger_weighted_basis_retains_native_40_digit_precision(self):
        file = MODULE.parent / "safety.py"
        spec = importlib.util.spec_from_file_location("consolidation_native_safety_fixture", file)
        safety = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = safety
        spec.loader.exec_module(safety)
        path = self.root / "native" / self.fp / "ledger.sqlite3"
        ledger = safety.Ledger(path, replace(safety.RiskLimits(), max_order_qty="3"))
        try:
            ledger.begin_next_trial(200, "native-rounding")
            operations = [("buy", "1", "100"), ("buy", "1", "101"), ("buy", "1", "100"),
                          ("sell", "1", "100"), ("sell", "2", "100")]
            for index, (side, qty, price) in enumerate(operations):
                at, cid = 201 + index, "native-" + str(index)
                ledger.reserve_intent(cid, "SPY", side, qty, "101" if side == "buy" else "99",
                                      quote=safety.Quote("SPY", "100", "100.01", at), now=at,
                                      market_open=True, session_close=5000, stop_file=self.root / "absent-fixture-stop")
                ledger.request_budget(at, "submit", cid)
                ledger.record_order(cid, "broker-" + cid, "filled", qty, price, timestamp=at)
            expected = dict(ledger.db.execute("SELECT key,value FROM meta"))
        finally:
            ledger.close()
        (path.parent / "trial.json").write_text('{"baseline_cash":"10000","started_at":200}')
        self.assertLess(D(expected["realized_loss"]).as_tuple().exponent, -18)
        plan = self.plan([path])
        self.assertEqual(plan.summary["realized"], expected["realized"])
        self.assertEqual(plan.summary["realized_loss"], expected["realized_loss"])
        self.assertEqual(D(plan.summary["cash_delta"]), D('-1'))
        self.apply(plan, self.proof([path]))


if __name__ == "__main__":
    unittest.main()
