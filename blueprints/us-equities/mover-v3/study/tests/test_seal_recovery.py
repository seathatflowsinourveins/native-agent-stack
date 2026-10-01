"""Round 18 R5: extend core.holdout.collect's recovery contract at 803bc351 to
count_only.dry_run and transport_check.seal_live_samples, and its repair after the
round-18 pre-outcome reviews (Claude H1, M1, L1-L3; GPT G-H, G-M): both adopt a seal
only through core.store.recover_seal, against its seal record and a binding that
names the running study tree, protocol and runtime lock. Only temporary synthetic
snapshots are read or damaged; every transport uses FakeMarket.

Second repair, after the cross-family re-check of that repair (GPT-6.1 Sol, 2026-10-01; R2-1 to R2-4): a seal record
without a sha256 of its ledger, a snapshot path that is not a directory, a change of attempt ids alone, and, at the
command level, a study file whose change an index flag hides from git status.
"""
import contextlib
import copy
import gzip
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import count_only as CO
from core import plan, transport_check
from core.canon import dumps, sha256_bytes, sha256_file
from core.store import SEAL_RECORD, SealError, Store, normalized_sha256
from tests import synth
from tests.test_identity import fixed_clock, issuer_data, transports

# the running study tree, protocol and runtime lock (core.runner.seal_run_identity builds it from the context)
RUN = {"study_tree": "synthetic-tree", "protocol_sha256": "synthetic-protocol", "runtime_lock_sha256": "synthetic-lock"}
FETCH_CHANGE = "blueprints/us-equities/mover-v3/study/fetch/transport.py"
FETCH_PREFIX = "blueprints/us-equities/mover-v3/study/fetch"
# R2-1: what a seal record can hold in place of its ledger's sha256 (64 lowercase hexadecimal characters). At 406ad3c5
# only null was adopted (Store.read compares no digest when it is given None); the others were refused by that
# comparison or as a missing field, none as a malformed record.
NOT_A_SHA256 = ("null", "missing", "number", "list", "short", "trailing_newline", "uppercase", "not_hexadecimal")
# R2-3: what can stand at a snapshot path in place of a directory
NOT_A_DIRECTORY = ("regular_file", "dangling_link")


def snapshot_bytes(root):
    """Every file's bytes under root, and every symbolic link's target (a dangling link is not a file)."""
    return {str(p.relative_to(root)): os.readlink(p) if p.is_symlink() else p.read_bytes()
            for p in Path(root).rglob("*") if p.is_symlink() or p.is_file()}


def ledger_lines(directory) -> list:
    return [json.loads(line) for line in (Path(directory) / "ledger.jsonl").read_bytes().splitlines() if line.strip()]


def write_ledger(directory, lines) -> None:
    """Rewrite the ledger in Store.write's line format; a str line is written as it is."""
    text = "\n".join(x if isinstance(x, str) else dumps(x) for x in lines) + "\n"
    (Path(directory) / "ledger.jsonl").write_bytes(text.encode("utf-8"))


def reseal(directory) -> None:
    """A forger who also rewrites the seal record: its ledger_sha256 becomes the edited ledger's, every other field
    stays as sealed, so only the checks after the digest can refuse the edit."""
    path = Path(directory) / SEAL_RECORD
    record = json.loads(path.read_bytes())
    record["ledger_sha256"] = sha256_file(Path(directory) / "ledger.jsonl")
    path.write_bytes((dumps(record) + "\n").encode("utf-8"))


class RecoveryChecks:
    """Store.write's write-once rule also forbids fetching again before refusing a used directory."""

    def assert_refuses_unchanged(self, root, market, call, pattern=""):
        before, calls = snapshot_bytes(root), len(market.calls)
        with self.assertRaisesRegex(SealError, pattern):
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
        elif kind == "record_only":
            # the ledger and the pages are gone; the seal record that precedes the ledger is left
            ledger.unlink()
            shutil.rmtree(directory / "pages")

    def remove_binding(self, directory):
        ledger = directory / "ledger.jsonl"
        lines = [line for line in ledger.read_bytes().splitlines() if json.loads(line)["event"] != "snapshot"]
        ledger.write_bytes(b"\n".join(lines) + b"\n")

    def alter_page(self, directory):
        # Keep gzip valid so Store.read must check the sealed page digest/length.
        next((directory / "pages").iterdir()).write_bytes(gzip.compress(b'{"altered":true}', mtime=0))

    def edit_fetch_times(self, directory):
        """G-H: only the recorded vintages and durations change (dry_run_measured's F12 inputs). The stamps, pages,
        requests and binding the seal record summarizes stay, so only the ledger digest it holds can refuse this."""
        lines = ledger_lines(directory)
        for x in lines:
            if x["event"].startswith("stamp"):
                x["vintage"] = "2000-01-01T00:00:00Z"
                if isinstance(x.get("elapsed_seconds"), (int, float)):
                    x["elapsed_seconds"] += 1000.0
        write_ledger(directory, lines)

    def replace_page_and_digests(self, directory, raw=b'{"altered":true}'):
        """G-H, the GPT review's experiment: the first page is replaced together with its ledger digests (sha256,
        length, normalized sha256); the binding, requests and stamps are kept, and the seal record is not touched."""
        directory = Path(directory)
        lines = ledger_lines(directory)
        page = next(x for x in lines if x["event"] == "page")
        parser = next(x["parser"] for x in lines if x["event"] == "request" and x["key"] == page["key"])
        (directory / page["file"]).write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
        page.update(sha256=sha256_bytes(raw), bytes=len(raw), normalized_sha256=normalized_sha256(parser, raw))
        write_ledger(directory, lines)

    def alter_request(self, directory):
        """G-M: a persisted request whose parameters change while its key, stamps and pages stay, under the expected
        binding, with the seal record resealed: only the request-equality check can refuse it."""
        lines = ledger_lines(directory)
        req = next(x for x in lines if x["event"] == "request")
        req["params"] = {**req["params"], "feed": "altered"}
        write_ledger(directory, lines)
        reseal(directory)

    def break_record_digest(self, directory, kind):
        """R2-1: only the seal record's ledger_sha256 changes, to something that is not a sha256 (NOT_A_SHA256)."""
        path = Path(directory) / SEAL_RECORD
        record = json.loads(path.read_bytes())
        sha = record.pop("ledger_sha256")
        values = {"null": None, "number": 0, "list": [sha], "short": sha[:63], "trailing_newline": sha + "\n",
                  "uppercase": "A" + sha[1:], "not_hexadecimal": "g" + sha[1:]}
        if kind != "missing":
            record["ledger_sha256"] = values[kind]
        path.write_bytes((dumps(record) + "\n").encode("utf-8"))

    def replace_with_a_non_directory(self, directory, kind):
        """R2-3: the snapshot path itself stops being a directory (NOT_A_DIRECTORY)."""
        shutil.rmtree(directory)
        if kind == "regular_file":
            directory.write_bytes(b"not a snapshot directory\n")
        else:
            directory.symlink_to(directory.parent / "absent-target")

    def renumber_attempt(self, directory, key, old, new) -> list:
        """R2-4: one attempt of `key` gets another id, in its page events and in its completion stamp; the seal record
        is resealed. Returns the events changed, after checking that nothing else changed: the ledger keeps every
        other field of every line (stamp counts, statuses, page counts, page digests), the pages keep their bytes and
        the seal record keeps every field but ledger_sha256. So only the attempt ids the seal record holds for its
        stamps can refuse the edit."""
        directory = Path(directory)
        before, record = snapshot_bytes(directory), json.loads((directory / SEAL_RECORD).read_bytes())
        sealed, lines = ledger_lines(directory), ledger_lines(directory)
        changed = [x for x in lines if x["event"] in ("page", "stamp_complete", "stamp_incomplete")
                   and x["key"] == key and x["attempt"] == old]
        for x in changed:
            x["attempt"] = new
        write_ledger(directory, lines)
        reseal(directory)

        def without(field, items):
            return [{k: v for k, v in x.items() if k != field} for x in items]
        self.assertEqual(without("attempt", ledger_lines(directory)), without("attempt", sealed))
        self.assertNotEqual(ledger_lines(directory), sealed)
        after = snapshot_bytes(directory)
        self.assertEqual({k: v for k, v in after.items() if k.startswith("pages/")},
                         {k: v for k, v in before.items() if k.startswith("pages/")})
        self.assertEqual(without("ledger_sha256", [json.loads(after[SEAL_RECORD])]), without("ledger_sha256", [record]))
        return changed


class DryRunSealRecovery(RecoveryChecks, unittest.TestCase):
    def setUp(self):
        self.cal = synth.calendar("2022-06-01", "2023-12-29")
        self.sessions, self.symbols, self.utc_start = ["2023-03-01"], ["AAA"], "2026-09-26T10:00:00Z"
        self.market = synth.FakeMarket(self.cal)
        daily, prints = issuer_data(self.cal, "2022-06-01", "2023-12-29", lambda day: 7.25)
        self.market.add("synthetic", [("2015-01-01", "AAA")], daily=daily, auctions=prints)

    def run_dry(self, root, **overrides):
        args = {"sessions": self.sessions, "symbols": self.symbols, "utc_start": self.utc_start, "run_identity": RUN,
                **overrides}
        return CO.dry_run(self.cal, transports=transports(self.market), snapshot_root=root,
                          clock=fixed_clock, **args)

    def test_matching_seal_is_recovered_without_requests_or_byte_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first_progress, retry_progress = {}, {}
            first = self.run_dry(tmp, progress=first_progress)
            self.assertTrue(self.market.calls)
            record = json.loads((Path(tmp) / "dry-run" / SEAL_RECORD).read_bytes())
            self.assertEqual(record["ledger_sha256"], first["snapshot_sha256"])
            self.assertEqual(record["binding"]["utc_start"], self.utc_start)
            self.assertEqual(record["binding"]["identity"]["study_tree"], RUN["study_tree"])
            before, calls = snapshot_bytes(tmp), len(self.market.calls)
            self.market.issuers.clear()           # a second draw would return different pages
            retry = self.run_dry(tmp, progress=retry_progress)
            self.assertEqual(retry, first)
            self.assertEqual(retry_progress, first_progress)
            self.assertEqual(self.market.calls[calls:], [])
            self.assertEqual(snapshot_bytes(tmp), before)

    def test_a_retry_on_a_later_utc_day_adopts_the_seal_and_reads_back_its_fetch_start(self):
        """M1: the fetch start changes neither the plan nor the fetch (core/driver.py), so it is bound beside the
        identity and read back from the seal, never matched. At af38dced the matched fetch date refused this retry
        for good (and test_mismatched_or_missing_binding_refuses_without_requests asserted that rule)."""
        with tempfile.TemporaryDirectory() as tmp:
            first = self.run_dry(tmp)
            self.assertEqual(first["fetch_utc_start"], self.utc_start)
            before, calls = snapshot_bytes(tmp), len(self.market.calls)
            self.market.issuers.clear()
            retry = self.run_dry(tmp, utc_start="2026-09-28T09:00:00Z")
            self.assertEqual(retry, first)
            self.assertEqual(retry["fetch_utc_start"], self.utc_start)
            self.assertEqual(self.market.calls[calls:], [])
            self.assertEqual(snapshot_bytes(tmp), before)

    def test_another_study_tree_protocol_or_runtime_lock_refuses(self):
        """H1: the seal binds the running study tree, protocol sha256 and runtime-lock sha256, so a run from any other
        one refuses it and must fetch its own (freeze_preconditions[8]); at af38dced the binding held none of them.
        A dry run without all three refuses before any fetch."""
        for key in sorted(RUN):
            with self.subTest(changed=key), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                other = {**RUN, key: "another-" + RUN[key]}
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp, run_identity=other),
                                              f"^dry-run: the snapshot was sealed for another {key}$")
        with tempfile.TemporaryDirectory() as tmp:
            calls = len(self.market.calls)
            for bad in ({}, {**RUN, "study_tree": ""}, {**RUN, "extra": "x"}, None):
                with self.subTest(run_identity=bad), self.assertRaises(ValueError):
                    self.run_dry(tmp, run_identity=bad)
            self.assertEqual((self.market.calls[calls:], snapshot_bytes(tmp)), ([], {}))

    def test_a_changed_request_plan_with_the_same_sessions_and_symbols_refuses(self):
        """The plan-change check: a plan that differs for the same sessions, symbols and run identity (here one
        request fewer) refuses the seal."""
        planned = CO.dry_run_requests
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            with mock.patch.object(CO, "dry_run_requests", lambda *args: planned(*args)[:-1]):
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                              "^dry-run: the snapshot was sealed for another request plan$")

    def test_mismatched_or_missing_binding_refuses_without_requests(self):
        changes = ({"sessions": ["2023-03-02"]}, {"symbols": ["BBB"]}, {})
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                if not change:
                    self.remove_binding(Path(tmp) / "dry-run")
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp, **change))

    def test_partial_snapshot_refuses_without_requests(self):
        for kind in ("pages_only", "partial_json", "missing_stamp", "empty_ledger", "missing_page", "record_only"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                self.damage_partial(Path(tmp) / "dry-run", kind)
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp))

    def test_altered_page_refuses_without_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            self.alter_page(Path(tmp) / "dry-run")
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp))

    def test_a_missing_or_mismatched_seal_record_refuses(self):
        """G-H: a seal is adopted only against the seal record written once at seal time, so a ledger without one, or
        with a record that is unreadable or does not match it, refuses."""
        cases = {"missing": "no seal record", "not_json": "JSONDecodeError", "not_an_object": "seal record is invalid",
                 "other_digest": "ledger sha256 differs", "other_stamps": "differs from its seal record"}
        for kind, pattern in cases.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                path = Path(tmp) / "dry-run" / SEAL_RECORD
                record = json.loads(path.read_bytes())
                if kind == "missing":
                    path.unlink()
                elif kind == "not_json":
                    path.write_bytes(b"{")
                elif kind == "not_an_object":
                    path.write_bytes(b"[]\n")
                else:
                    if kind == "other_digest":
                        record["ledger_sha256"] = "0" * 64
                    else:
                        record["stamps"][0][3] += 1
                    path.write_bytes((dumps(record) + "\n").encode("utf-8"))
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp), pattern)

    def test_a_ledger_with_altered_fetch_times_refuses_against_its_seal_record(self):
        """G-H: an edit that keeps every stamp, page, request and the binding (here the vintages and the durations the
        F12 calibration reads) is refused only because the ledger must have the digest its seal record holds. At
        af38dced recovery hashed the edited ledger itself and adopted it."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            self.edit_fetch_times(Path(tmp) / "dry-run")
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                          "^dry-run: snapshot ledger sha256 differs from the sealed value$")

    def test_a_page_replaced_with_its_ledger_digests_refuses(self):
        """G-H, the GPT review's experiment on the dry run: a page replaced together with its ledger digests, with
        the binding, requests and stamps kept, was adopted at af38dced."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            self.replace_page_and_digests(Path(tmp) / "dry-run")
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp), "ledger sha256 differs")

    def test_a_resealed_page_replacement_refuses(self):
        """G-H, the per-page comparison: the GPT review's experiment with the seal record's ledger_sha256 also rewritten
        to the edited ledger's (reseal). The ledger then reads under the record and the page matches its edited ledger
        digests, so only the page sha256s the seal record holds refuse it. At 5a1d4b0e no test covered that comparison:
        emptying page_sha256s in core.store.seal_record_of passed the whole suite."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            directory = Path(tmp) / "dry-run"
            self.replace_page_and_digests(directory)
            reseal(directory)
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                          "^dry-run: the snapshot differs from its seal record")

    def test_a_resealed_request_change_refuses(self):
        """G-M: a persisted request altered under the expected binding, with the seal record resealed, is refused by
        the comparison of the ledger's request records with the requests its binding names."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            self.alter_request(Path(tmp) / "dry-run")
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                          "^dry-run: the snapshot's requests or completion stamps differ")

    def test_a_resealed_stamp_page_count_change_refuses(self):
        """G-H: Store.read checks every completion stamp's page count against its attempt's page events."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run_dry(tmp)
            directory = Path(tmp) / "dry-run"
            lines = ledger_lines(directory)
            stamp = next(x for x in lines if x["event"] == "stamp_complete" and x["pages"])
            stamp["pages"] += 1
            write_ledger(directory, lines)
            reseal(directory)
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp), "page count differs")

    def test_a_ledger_cut_after_a_refetched_requests_first_stamp_refuses(self):
        """L1: at af38dced, set(state) == set(req) accepted a ledger cut right after the attempt-0 stamp of a request
        that was re-fetched (here the last request in key order, complete at attempt 1). The seal record's ledger
        digest refuses it, and, when the digest is resealed, so does the exact comparison of the attempt stamps."""
        last = max(CO.dry_run_requests(self.cal, self.sessions, self.symbols), key=lambda r: r["key"])

        def first_attempt(path, p):
            return path == last["endpoint"] and all(p.get(k) == str(v) for k, v in last["params"].items())
        for resealed, pattern in ((False, "ledger sha256 differs"), (True, "differs from its seal record")):
            with self.subTest(resealed=resealed), tempfile.TemporaryDirectory() as tmp:
                self.market.fail = [(first_attempt, "urlerror", 4)]      # the first call and its 3 retries
                self.run_dry(tmp)
                directory = Path(tmp) / "dry-run"
                lines = ledger_lines(directory)
                self.assertEqual([(x["attempt"], x["event"]) for x in lines
                                  if x.get("key") == last["key"] and x["event"].startswith("stamp")],
                                 [(0, "stamp_incomplete"), (1, "stamp_complete")])
                cut = next(i for i, x in enumerate(lines)
                           if x["event"] == "stamp_incomplete" and x["key"] == last["key"])
                write_ledger(directory, lines[: cut + 1])
                if resealed:
                    reseal(directory)
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp), pattern)

    def test_unreadable_snapshots_refuse_with_a_seal_error(self):
        """L2: at af38dced a corrupt gzip page (zlib.error), a ledger line that is not a JSON object (TypeError,
        AttributeError) and an unreadable ledger (OSError, from sha256_file outside the try) escaped as other
        exceptions. Each is now a SealError naming the error, with no request and no byte change; the two edited
        ledgers are resealed so their lines reach the parser."""
        cases = {"corrupt_page": "decompressing", "list_line": "TypeError", "number_line": "AttributeError",
                 "ledger_is_a_directory": "IsADirectoryError"}
        for kind, pattern in cases.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                directory = Path(tmp) / "dry-run"
                if kind == "corrupt_page":
                    page = sorted((directory / "pages").iterdir())[0]
                    good = page.read_bytes()
                    page.write_bytes(good[:10] + b"\xff" * (len(good) - 18) + good[-8:])
                elif kind == "ledger_is_a_directory":
                    (directory / "ledger.jsonl").unlink()
                    (directory / "ledger.jsonl").mkdir()
                else:
                    lines = (directory / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                    write_ledger(directory, lines[:-1] + ["[1, 2]" if kind == "list_line" else "7"])
                    reseal(directory)
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp), pattern)

    def test_a_seal_record_without_a_ledger_sha256_refuses(self):
        """R2-1: recovery reads the ledger under the sha256 its seal record holds, so a record that holds none cannot
        verify it. At 406ad3c5 a record whose ledger_sha256 was JSON null was adopted: Store.read compares no digest
        when it is given None, and the record comparison used the same null. With the ledger's vintages and durations
        edited as well (the F12 calibration's inputs), that seal was adopted too, without a request. Every value that
        is not 64 lowercase hexadecimal characters is now refused as a malformed record, before the ledger is read."""
        for ledger_edited in (False, True):
            for kind in NOT_A_SHA256:
                with self.subTest(kind=kind, ledger_edited=ledger_edited), tempfile.TemporaryDirectory() as tmp:
                    self.run_dry(tmp)
                    directory = Path(tmp) / "dry-run"
                    if ledger_edited:
                        self.edit_fetch_times(directory)
                    self.break_record_digest(directory, kind)
                    self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                                  "^dry-run: the seal record holds no sha256 of its ledger")

    def test_a_snapshot_path_that_is_not_a_directory_refuses_without_requests(self):
        """R2-3: a regular file or a dangling symbolic link at the snapshot path holds no ledger, pages or seal record,
        so at 406ad3c5 it counted as unused: the dry run fetched again (16 calls here) and Store.write then failed,
        with NotADirectoryError for the file and with its own 'pages already exist' SealError for the link. It is a
        used path: a SealError that names the dry run, no request, no byte change."""
        for kind in NOT_A_DIRECTORY:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                self.run_dry(tmp)
                self.replace_with_a_non_directory(Path(tmp) / "dry-run", kind)
                self.assertIn("dry-run", snapshot_bytes(tmp))
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                              "^dry-run: the snapshot path exists and is not a directory")

    def fail_the_last_requests_first_attempt(self) -> dict:
        """The L1 test's setup: the last request in key order fails its first call and its 3 retries, so it is sealed
        incomplete at attempt 0 and complete at attempt 1. Returns that request."""
        last = max(CO.dry_run_requests(self.cal, self.sessions, self.symbols), key=lambda r: r["key"])
        self.market.fail = [(lambda path, p: path == last["endpoint"] and
                             all(p.get(k) == str(v) for k, v in last["params"].items()), "urlerror", 4)]
        return last

    def test_a_resealed_attempt_id_change_refuses(self):
        """R2-4, mutant A (st['attempt'] replaced by 0 in core.store.seal_record_of's stamp entries): at 406ad3c5 no
        test compared attempt ids alone, so that mutant passed all 27 recovery tests (the L1 test removes a whole
        stamp, which also changes the stamp count). Here a re-fetched request's second attempt becomes attempt 7 in
        its page events and its completion stamp, with every count, status, page and digest kept and the seal record's
        ledger_sha256 resealed: only the attempt ids the seal record holds refuse it."""
        with tempfile.TemporaryDirectory() as tmp:
            last = self.fail_the_last_requests_first_attempt()
            self.run_dry(tmp)
            changed = self.renumber_attempt(Path(tmp) / "dry-run", last["key"], 1, 7)
            self.assertEqual(sorted({x["event"] for x in changed}), ["page", "stamp_complete"])
            self.assertEqual([(x["event"], x["attempt"]) for x in ledger_lines(Path(tmp) / "dry-run")
                              if x.get("key") == last["key"] and x["event"].startswith("stamp")],
                             [("stamp_incomplete", 0), ("stamp_complete", 7)])
            self.assert_refuses_unchanged(tmp, self.market, lambda: self.run_dry(tmp),
                                          "^dry-run: the snapshot differs from its seal record")


# every change that applies to the whole transport-check run rather than to one label's source
RUN_WIDE = {"seed": {"seed": "another-seed"},
            **{key: {"run_identity": {**RUN, key: "another-" + value}} for key, value in RUN.items()}}


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

    def seal_samples(self, root, seed="synthetic-seed", sources=None, run_identity=RUN):
        sources = self.sources if sources is None else sources
        return transport_check.seal_live_samples(sources["stage"], transports(self.market), seed,
                                                 [("collect-synthetic", sources["collect-synthetic"])],
                                                 root, run_identity, clock=fixed_clock)

    def seal_mixed(self, root, label, **change):
        """L3: a live root whose `label` sample is sealed as the test sealed it and every other label under `change`,
        so a run with `change` adopts the other labels and is refused at `label` itself. At af38dced the holdout
        label's seed case was refused at 'stage' first and never reached the holdout label."""
        with tempfile.TemporaryDirectory() as original, tempfile.TemporaryDirectory() as changed:
            self.seal_samples(original)
            self.seal_samples(changed, **change)
            for name in self.sources:
                shutil.copytree(Path(original if name == label else changed) / name, Path(root) / name)

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

    def test_another_seed_study_tree_protocol_or_runtime_lock_refuses_at_each_label(self):
        """H1 for live samples (each binds the running study tree, protocol and runtime lock) and L3 (a run-wide
        change is refused at the label under test, which the message names)."""
        for label in self.sources:
            for key, change in RUN_WIDE.items():
                with self.subTest(label=label, changed=key), tempfile.TemporaryDirectory() as tmp:
                    self.seal_mixed(tmp, label, **change)
                    self.assert_refuses_unchanged(
                        tmp, self.market, lambda: self.seal_samples(tmp, **change),
                        f"^live sample {re.escape(repr(label))}: the snapshot was sealed for another {key}$")

    def test_mismatched_or_missing_binding_refuses_without_requests(self):
        """A change to one label's source (its requests, a page, or only its Store.binding; G-M) or a ledger without
        its binding refuses at that label."""
        for label in self.sources:
            for change in ("source_request", "source_page", "source_binding", "missing_binding"):
                with self.subTest(label=label, change=change), tempfile.TemporaryDirectory() as tmp:
                    self.seal_samples(tmp)
                    sources = copy.deepcopy(self.sources)
                    if change == "source_request":
                        req = plan.quote_request("quote_exit", "OTHER", "2023-03-01",
                                                 self.cal.at("2023-03-01", "15:55"), self.cal.close("2023-03-01"))
                        sources[label] = Store()
                        synth.put_quotes(sources[label], req, "OTHER", [])
                    elif change == "source_page":
                        state = next(iter(sources[label].state.values()))
                        state["pages"] = [b'{"quotes":{}}']
                    elif change == "source_binding":
                        # G-M: only the source's Store.binding changes; its requests and sealed attempts stay
                        sources[label].binding = {"identity": {"synthetic": "another source binding"}}
                    else:
                        self.remove_binding(Path(tmp) / label)
                    self.assert_refuses_unchanged(tmp, self.market, lambda: self.seal_samples(tmp, sources=sources),
                                                  f"^live sample {re.escape(repr(label))}: ")

    def test_partial_snapshot_refuses_without_requests(self):
        for label in self.sources:
            for kind in ("pages_only", "partial_json", "missing_stamp", "empty_ledger", "missing_page", "record_only"):
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

    def test_a_missing_seal_record_refuses(self):
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                (Path(tmp) / label / SEAL_RECORD).unlink()
                self.assert_refuses_unchanged(tmp, self.market, lambda: self.seal_samples(tmp), "no seal record")

    def test_a_ledger_with_altered_fetch_times_refuses_against_its_seal_record(self):
        """G-H: the same ledger-only edit as the dry run's, for each label."""
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                self.edit_fetch_times(Path(tmp) / label)
                self.assert_refuses_unchanged(
                    tmp, self.market, lambda: self.seal_samples(tmp),
                    f"^live sample {re.escape(repr(label))}: snapshot ledger sha256 differs from the sealed value$")

    def test_a_resealed_request_change_refuses(self):
        """G-M: a persisted request altered under the expected binding, with the seal record resealed."""
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                self.alter_request(Path(tmp) / label)
                self.assert_refuses_unchanged(
                    tmp, self.market, lambda: self.seal_samples(tmp),
                    f"^live sample {re.escape(repr(label))}: the snapshot's requests or completion stamps differ")

    def test_a_resealed_page_replacement_refuses(self):
        """G-H, the per-page comparison for each label, as the dry run's: a page replaced with its ledger digests and
        the seal record's ledger_sha256 resealed is refused only by the page sha256s the seal record holds."""
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                self.replace_page_and_digests(Path(tmp) / label)
                reseal(Path(tmp) / label)
                self.assert_refuses_unchanged(
                    tmp, self.market, lambda: self.seal_samples(tmp),
                    f"^live sample {re.escape(repr(label))}: the snapshot differs from its seal record")

    def test_a_resealed_live_page_cannot_turn_a_failing_check_into_a_pass(self):
        """G-H, the GPT review's experiment end to end: the sealed live sample differs from its source, so the check
        fails; then the live page and its ledger digests are replaced by the source's page, with the binding, requests
        and stamps kept. At af38dced recovery adopted the edited ledger and the check passed, after one provider call
        in all. Now the rerun refuses, with no call and no byte change."""
        s = "2023-03-01"
        req = plan.quote_request("quote_exit", "AAA", s, self.cal.at(s, "15:55"), self.cal.close(s))
        market = synth.FakeMarket(self.cal)
        market.add("AAA", [("2015-01-01", "AAA")], quotes=[synth.quote(self.cal.at(s, "15:55"), 7.1, 7.4)])
        with tempfile.TemporaryDirectory() as tmp:
            sealed = Store()
            synth.put_quotes(sealed, req, "AAA", [synth.quote(self.cal.at(s, "15:55"), 7.2, 7.3)])
            source = Store.read(Path(tmp) / "source", sealed.write(Path(tmp) / "source"))
            live_root = Path(tmp) / "live"

            def check():
                return transport_check.reproduction_check(lambda st: [req], source, transports(market), [FETCH_CHANGE],
                                                          FETCH_PREFIX, seed="synthetic-seed", live_root=live_root,
                                                          clock=fixed_clock, run_identity=RUN)
            first = check()
            self.assertEqual((first["passes"], first["plan"]["passes"], first["reparse"]["passes"],
                              first["live"]["passes"], len(market.calls)), (False, True, True, False, 1))
            self.replace_page_and_digests(live_root / "stage", source.state[req["key"]]["pages"][0])
            self.assert_refuses_unchanged(live_root, market, check,
                                          "^live sample 'stage': snapshot ledger sha256 differs from the sealed value$")
            self.assertEqual(len(market.calls), 1)

    def test_a_seal_record_without_a_ledger_sha256_refuses(self):
        """R2-1 for each label, as the dry run's: a seal record whose ledger_sha256 is null (adopted at 406ad3c5, also
        with the ledger's vintages and durations edited) or anything else that is not a sha256."""
        for label in self.sources:
            for ledger_edited in (False, True):
                for kind in NOT_A_SHA256:
                    with self.subTest(label=label, kind=kind, ledger_edited=ledger_edited), \
                            tempfile.TemporaryDirectory() as tmp:
                        self.seal_samples(tmp)
                        if ledger_edited:
                            self.edit_fetch_times(Path(tmp) / label)
                        self.break_record_digest(Path(tmp) / label, kind)
                        self.assert_refuses_unchanged(
                            tmp, self.market, lambda: self.seal_samples(tmp),
                            f"^live sample {re.escape(repr(label))}: the seal record holds no sha256 of its ledger")

    def test_a_snapshot_path_that_is_not_a_directory_refuses_without_requests(self):
        """R2-3 for each label, as the dry run's: a regular file or a dangling symbolic link at the label's path."""
        for label in self.sources:
            for kind in NOT_A_DIRECTORY:
                with self.subTest(label=label, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    self.seal_samples(tmp)
                    self.replace_with_a_non_directory(Path(tmp) / label, kind)
                    self.assertIn(label, snapshot_bytes(tmp))
                    self.assert_refuses_unchanged(
                        tmp, self.market, lambda: self.seal_samples(tmp),
                        f"^live sample {re.escape(repr(label))}: the snapshot path exists and is not a directory")

    def test_a_resealed_attempt_id_change_refuses(self):
        """R2-4, mutant A, for each label: the sample's one attempt becomes attempt 7 in its page event and its
        completion stamp, with everything else kept and the seal record's ledger_sha256 resealed."""
        for label in self.sources:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                self.seal_samples(tmp)
                key = next(x["key"] for x in ledger_lines(Path(tmp) / label) if x["event"] == "request")
                changed = self.renumber_attempt(Path(tmp) / label, key, 0, 7)
                self.assertEqual(sorted(x["event"] for x in changed), ["page", "stamp_complete"])
                self.assert_refuses_unchanged(
                    tmp, self.market, lambda: self.seal_samples(tmp),
                    f"^live sample {re.escape(repr(label))}: the snapshot differs from its seal record")


class DryRunCommandRecovery(RecoveryChecks, unittest.TestCase):
    """Repair of the round-18 reviews (H1, M1) at the command level. A dry run whose output step fails after the seal
    writes a failed end line in run.py's finally block, so the next run opens a new start line and finds the seal.
    It adopts that seal only for the study tree, protocol and runtime lock that fetched it (H1: freeze_preconditions[8]
    wants the tree the freeze will pin to fetch), and on any later UTC day (M1: the fetch start is read back from the
    seal, never matched)."""

    SESSION = "2023-03-01"
    DAY1, DAY2 = "2026-12-01T00:00:00Z", "2026-12-02T00:00:00Z"

    def setUp(self):
        self.cal = synth.calendar("2022-06-01", "2023-12-29")
        self.market = synth.FakeMarket(self.cal)
        s = self.SESSION
        daily, prints = issuer_data(self.cal, self.cal.offset(s, -60), self.cal.offset(s, 12), lambda day: 7.25)
        self.market.add("synthetic", [("2015-01-01", "AAA")], daily=daily, auctions=prints)
        self.now = [self.DAY1]

    @contextlib.contextmanager
    def command(self):
        import run
        from tests import fixture_repo as FR
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp, frozen=False)["repo"]
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(self.market)), \
                    mock.patch.object(run, "clock", lambda: self.now[0]):
                yield run, repo, Path(tmp)

    def argv(self, root):
        return ["dry-run", "--sessions", self.SESSION, "--symbols", "AAA", "--snapshot-root", str(root)]

    def fail_after_the_seal(self, run, repo, root) -> str:
        """The pushed start line, then a run whose output step fails after the seal; returns the sha256 that its
        failed end line logged (review round 12, F3). Both lines are pushed."""
        from core import logs
        from core.params import RUN_LOG
        from tests import fixture_repo as FR
        self.assertEqual(run.main(self.argv(root)), 0)
        FR.commit_push(repo, "2026-10-01T01:00:00+00:00")
        with mock.patch.object(CO, "dry_run_output", side_effect=RuntimeError("synthetic failure after the seal")), \
                self.assertRaisesRegex(RuntimeError, "after the seal"):
            run.main(self.argv(root))
        line = logs.read_lines(repo / RUN_LOG)[-1]
        self.assertEqual((line["purpose"], line["status"], len(line["input_snapshot_sha256s"])),
                         ("dry_run", "failed", 1))
        FR.commit_push(repo, "2026-10-01T01:05:00+00:00")
        return line["input_snapshot_sha256s"][0]

    def test_a_seal_left_by_a_failed_run_is_refused_to_another_study_tree(self):
        """H1: tree A seals and fails after the seal; tree B changes only study/fetch/ (the request plan is the same).
        At af38dced B adopted A's seal without a request and wrote an output stamped with B's tree, so the F12
        calibration came from a transport B never ran. Now B is refused, nothing is fetched or written, and B fetches
        its own snapshot under a new root."""
        from core.params import DRY_RUN_OUTPUT, STUDY_PATH
        from tests import fixture_repo as FR
        with self.command() as (run, repo, tmp):
            root = tmp / "snap"
            sealed = self.fail_after_the_seal(run, repo, root)
            FR.write(repo / STUDY_PATH / "fetch" / "transport.py", "HOST = 'fixture-fixed'\n")
            FR.commit_push(repo, "2026-10-01T02:00:00+00:00")
            tree_b = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            self.assertEqual(run.main(self.argv(root)), 0)               # B's start line
            FR.commit_push(repo, "2026-10-01T02:05:00+00:00")
            self.assert_refuses_unchanged(root, self.market, lambda: run.main(self.argv(root)),
                                          "^dry-run: the snapshot was sealed for another study_tree$")
            self.assertFalse((repo / DRY_RUN_OUTPUT).exists())
            FR.commit_push(repo, "2026-10-01T02:10:00+00:00")             # the refused run's failed end line
            fresh = tmp / "snap-tree-b"
            self.assertEqual(run.main(self.argv(fresh)), 0)              # a new start line
            FR.commit_push(repo, "2026-10-01T02:15:00+00:00")
            calls = len(self.market.calls)
            self.assertEqual(run.main(self.argv(fresh)), 0)
            self.assertGreater(len(self.market.calls), calls)            # B's own transport fetched
            out = json.loads((repo / DRY_RUN_OUTPUT).read_text())
            self.assertEqual(out["study_tree"], tree_b)
            self.assertNotEqual(out["snapshot_sha256"], sealed)

    def test_a_seal_left_by_a_failed_run_is_adopted_on_a_later_utc_day(self):
        """M1: the same tree, protocol and runtime lock retry on the next UTC day and adopt the seal without a request.
        The output's fetch_utc_start is the first run's start, read back from the seal binding; the end line keeps its
        own start. At af38dced the fetch date was matched, so this retry was refused for good."""
        from core import logs
        from core.params import DRY_RUN_OUTPUT, RUN_LOG
        from tests import fixture_repo as FR
        with self.command() as (run, repo, tmp):
            root = tmp / "snap"
            sealed = self.fail_after_the_seal(run, repo, root)
            self.now[0] = self.DAY2
            self.assertEqual(run.main(self.argv(root)), 0)               # a new start line on the next UTC day
            FR.commit_push(repo, "2026-10-02T01:00:00+00:00")
            before, calls = snapshot_bytes(root), len(self.market.calls)
            self.assertEqual(run.main(self.argv(root)), 0)
            self.assertEqual(self.market.calls[calls:], [])
            self.assertEqual(snapshot_bytes(root), before)
            out = json.loads((repo / DRY_RUN_OUTPUT).read_text())
            self.assertEqual((out["snapshot_sha256"], out["fetch_utc_start"]), (sealed, self.DAY1))
            line = logs.read_lines(repo / RUN_LOG)[-1]
            self.assertEqual((line["purpose"], line["status"], line["input_snapshot_sha256s"], line["utc_start"]),
                             ("dry_run", "complete", [sealed], self.DAY2))

    def test_a_transport_change_hidden_by_an_index_flag_is_refused_before_the_seal_is_adopted(self):
        """R2-2: H1 binds a seal to the tree core.guards.running_tree names, and at 406ad3c5 that was HEAD's tree
        whenever git status reported no change. git status does not report a tracked file whose index entry is marked
        assume-unchanged or skip-worktree (git-update-index(1)), so a transport edited under either flag ran as the
        committed tree: the run opened a start line, and the next one adopted the seal that the failed run of the
        committed tree left and named that tree in its output. Now the run is refused when it builds its context:
        no start line, no request, no byte change, no output."""
        from core import guards
        from core.params import DRY_RUN_OUTPUT, RUN_LOG, STUDY_PATH
        from tests import fixture_repo as FR
        transport = f"{STUDY_PATH}/fetch/transport.py"
        for flag in ("assume-unchanged", "skip-worktree"):
            with self.subTest(flag=flag), self.command() as (run, repo, tmp):
                root = tmp / "snap"
                self.fail_after_the_seal(run, repo, root)
                tree = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
                FR.sh(repo, "update-index", f"--{flag}", transport)
                FR.write(repo / transport, "HOST = 'fixture-changed'\n")    # outside the plan code, as H1's tree B
                self.assertEqual(FR.sh(repo, "status", "--porcelain", "--untracked-files=all", "--", STUDY_PATH), "")
                self.assertEqual(FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}"), tree)
                log, before, calls = (repo / RUN_LOG).read_bytes(), snapshot_bytes(root), len(self.market.calls)
                with self.assertRaisesRegex(guards.Refused, re.escape(f"{transport} ({flag})")):
                    run.main(self.argv(root))
                self.assertEqual(self.market.calls[calls:], [])
                self.assertEqual(snapshot_bytes(root), before)
                self.assertEqual((repo / RUN_LOG).read_bytes(), log)
                self.assertFalse((repo / DRY_RUN_OUTPUT).exists())


if __name__ == "__main__":
    unittest.main()
