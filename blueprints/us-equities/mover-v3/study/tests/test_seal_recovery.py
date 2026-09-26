"""Round 18 R5: extend core.holdout.collect's recovery contract at 803bc351 to
count_only.dry_run and transport_check.seal_live_samples. Only temporary synthetic
snapshots are read or damaged; every transport uses FakeMarket.
"""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path

from core import count_only as CO
from core import plan, transport_check
from core.store import SealError, Store
from tests import synth
from tests.test_identity import fixed_clock, issuer_data, transports


def snapshot_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in Path(root).rglob("*") if p.is_file()}


class RecoveryChecks:
    """Store.write's write-once rule also forbids fetching again before refusing a used directory."""

    def assert_refuses_unchanged(self, root, market, call):
        before, calls = snapshot_bytes(root), len(market.calls)
        with self.assertRaises(SealError):
            call()
        self.assertEqual(market.calls[calls:], [], "a used snapshot must not draw provider data again")
        self.assertEqual(snapshot_bytes(root), before)

    def damage_partial(self, directory, kind):
        ledger = directory / "ledger.jsonl"
        if kind == "pages_only":
            ledger.unlink()
        elif kind == "partial_json":
            ledger.write_bytes(ledger.read_bytes()[:-5])
        elif kind == "missing_stamp":
            # A syntactically valid prefix is still an unfinished snapshot.
            ledger.write_bytes(b"\n".join(ledger.read_bytes().splitlines()[:-1]) + b"\n")
        elif kind == "empty_ledger":
            ledger.write_bytes(b"")
        elif kind == "missing_page":
            next((directory / "pages").iterdir()).unlink()

    def remove_binding(self, directory):
        ledger = directory / "ledger.jsonl"
        lines = [line for line in ledger.read_bytes().splitlines() if json.loads(line)["event"] != "snapshot"]
        ledger.write_bytes(b"\n".join(lines) + b"\n")

    def alter_page(self, directory):
        # Keep gzip valid so Store.read must check the sealed page digest/length.
        next((directory / "pages").iterdir()).write_bytes(gzip.compress(b'{"altered":true}', mtime=0))


class DryRunSealRecovery(RecoveryChecks, unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2022-06-01", "2023-12-29")
        self.sessions, self.symbols, self.fetch_date = ["2023-03-01"], ["AAA"], "2026-09-26"
        self.market = synth.FakeMarket(self.cal)
        daily, prints = issuer_data(self.cal, "2022-06-01", "2023-12-29", lambda day: 7.25)
        self.market.add("synthetic", [("2015-01-01", "AAA")], daily=daily, auctions=prints)

    def run_dry(self, root, **overrides):
        args = {"sessions": self.sessions, "symbols": self.symbols, "fetch_date": self.fetch_date, **overrides}
        return CO.dry_run(self.cal, transports=transports(self.market), snapshot_root=root,
                          clock=fixed_clock, **args)

    def test_matching_seal_is_recovered_without_requests_or_byte_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first_progress, retry_progress = {}, {}
            first = self.run_dry(tmp, progress=first_progress)
            self.assertTrue(self.market.calls)
            before, calls = snapshot_bytes(tmp), len(self.market.calls)
            self.market.issuers.clear()           # a second draw would return different pages
            retry = self.run_dry(tmp, progress=retry_progress)
            self.assertEqual(retry, first)
            self.assertEqual(retry_progress, first_progress)
            self.assertEqual(self.market.calls[calls:], [])
            self.assertEqual(snapshot_bytes(tmp), before)

    def test_mismatched_or_missing_binding_refuses_without_requests(self):
        changes = ({"sessions": ["2023-03-02"]}, {"symbols": ["BBB"]},
                   {"fetch_date": "2026-09-27"}, {})
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                if not change:
                    self.remove_binding(Path(tmp) / "dry-run")
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp, **change))

    def test_partial_snapshot_refuses_without_requests(self):
        for kind in ("pages_only", "partial_json", "missing_stamp", "empty_ledger", "missing_page"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                self.damage_partial(Path(tmp) / "dry-run", kind)
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp))

    def test_altered_page_refuses_without_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            self.alter_page(Path(tmp) / "dry-run")
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp))


class LiveSampleSealRecovery(RecoveryChecks, unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2022-06-01", "2023-12-29")
        self.market = synth.FakeMarket(self.cal)
        self.sources = {}
        for label, symbol in (("stage", "AAA"), ("collect-synthetic", "BBB")):
            req = plan.quote_request("quote_exit", symbol, "2023-03-01",
                                     self.cal.at("2023-03-01", "15:55"), self.cal.close("2023-03-01"))
            source = Store()
            synth.put_quotes(source, req, symbol, [synth.quote(self.cal.at("2023-03-01", "15:55"), 7.2, 7.3)])
            self.sources[label] = source
            self.market.add(symbol, [("2015-01-01", symbol)],
                            quotes=[synth.quote(self.cal.at("2023-03-01", "15:55"), 7.2, 7.3)])

    def seal_samples(self, root, seed="synthetic-seed", sources=None):
        sources = self.sources if sources is None else sources
        return transport_check.seal_live_samples(sources["stage"], transports(self.market), seed,
                                                 [("collect-synthetic", sources["collect-synthetic"])],
                                                 root, clock=fixed_clock)

    def test_matching_seal_is_recovered_without_requests_or_byte_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.seal_samples(tmp)
            self.assertEqual(set(first), set(self.sources))
            self.assertEqual(len(self.market.calls), 2)
            before, calls = snapshot_bytes(tmp), len(self.market.calls)
            self.market.issuers.clear()
            self.assertEqual(self.seal_samples(tmp), first)
            self.assertEqual(self.market.calls[calls:], [])
            self.assertEqual(snapshot_bytes(tmp), before)

    def test_mismatched_or_missing_binding_refuses_without_requests(self):
        for label in self.sources:
            for change in ("seed", "source_request", "source_page", "missing_binding"):
                with self.subTest(label=label, change=change), tempfile.TemporaryDirectory() as tmp:
                    self.seal_samples(tmp)
                    sources, seed = copy.deepcopy(self.sources), "synthetic-seed"
                    if change == "seed":
                        seed = "different-seed"
                    elif change == "source_request":
                        req = plan.quote_request("quote_exit", "OTHER", "2023-03-01",
                                                 self.cal.at("2023-03-01", "15:55"), self.cal.close("2023-03-01"))
                        sources[label] = Store()
                        synth.put_quotes(sources[label], req, "OTHER", [])
                    elif change == "source_page":
                        state = next(iter(sources[label].state.values()))
                        state["pages"] = [b'{"quotes":{}}']
                    else:
                        self.remove_binding(Path(tmp) / label)
                    self.assert_refuses_unchanged(tmp, self.market, lambda: self.seal_samples(tmp, seed, sources))

    def test_partial_snapshot_refuses_without_requests(self):
        for label in self.sources:
            for kind in ("pages_only", "partial_json", "missing_stamp", "empty_ledger", "missing_page"):
                with self.subTest(label=label, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    self.seal_samples(tmp)
                    self.damage_partial(Path(tmp) / label, kind)
                    self.assert_refuses_unchanged(tmp, self.market, lambda: self.seal_samples(tmp))

    def test_altered_page_refuses_without_requests(self):
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                self.alter_page(Path(tmp) / label)
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.seal_samples(tmp))


if __name__ == "__main__":
    unittest.main()
