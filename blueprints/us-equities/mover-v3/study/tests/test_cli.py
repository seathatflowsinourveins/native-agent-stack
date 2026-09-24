"""run.py and core.runner.context against a temporary repository (review round 9, F6): refusals on a draft protocol,
a development or validation stage fetched once and evaluated into one results file (F1, M-4, F10), and the context
refusals: bytecode isolation and ignored files (F9), logs equal to origin/main (F2), the frozen protocol blob (F3),
amendment timing (M-3, F5), coverage_decision (F7) and transport deviations (H-2). Nothing here reads the real
protocol's status or writes to the real run log."""
import functools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run
from core import canon, guards, logs, runner
from core import stage as ST
from core.params import ACCESS_LOG, DATA_DIR, DEVIATIONS, PROTOCOL_PATH, RESULTS_DIR, RUN_LOG, STUDY_PATH
from tests import fixture_repo as FR
from tests import synth
from tests.test_e2e import build_market
from tests.test_identity import fixed_clock, transports

REAL_RUN_LOG = FR.REAL / RUN_LOG


class Calendar(unittest.TestCase):
    def test_build_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "session-calendar.json"
            self.assertEqual(run.main(["build-calendar", "--first", "2016-11-23", "--last", "2016-11-28", "--out", str(out)]), 0)
            body = json.loads(out.read_text())
            self.assertEqual([s["d"] for s in body["sessions"]], ["2016-11-23", "2016-11-25", "2016-11-28"])
            self.assertEqual(body["sessions"][1]["close"], "2016-11-25T18:00:00Z")


class DraftProtocol(unittest.TestCase):
    def test_every_command_refuses_on_a_draft_and_writes_nothing(self):
        before = REAL_RUN_LOG.read_bytes() if REAL_RUN_LOG.exists() else None
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, frozen=False)
            snap = str(Path(tmp) / "snap")
            argvs = (["fetch", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap],
                     ["evaluate", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap,
                      "--sha", "0" * 64],
                     ["authorize", "--purpose", "count"], ["count", "--authorization", "count-001", "--snapshot-root", snap],
                     ["read", "--authorization", "read-001", "--snapshot-root", snap],
                     ["collect", "--authorization", "collect-001", "--snapshot-root", snap, "--last", "2026-10-09",
                      "--accrual-log", snap])
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", fx["repo"]):
                for argv in argvs:
                    with self.assertRaises(guards.Refused, msg=argv[0]):
                        run.main(argv)
            self.assertEqual((fx["repo"] / RUN_LOG).read_text(), "")
            self.assertEqual((fx["repo"] / ACCESS_LOG).read_text(), "")
            self.assertFalse(Path(snap).exists())
        self.assertEqual(REAL_RUN_LOG.read_bytes() if REAL_RUN_LOG.exists() else None, before)


class StageRunsOnce(unittest.TestCase):
    """A frozen fixture: fetch validation once, evaluate it into results/validation.json once."""

    def test_fetch_once_evaluate_once_with_a_kill_after_the_write(self):
        cal = synth.calendar()
        market, symbols = build_market(cal)
        enum = {"symbols": symbols, "actions": [], "active": symbols, "counts": {}}
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, enumeration=enum)
            repo, snap = fx["repo"], str(Path(tmp) / "snap")
            fetch = ["fetch", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap]
            fast = functools.partial(ST.evaluate_stage, B=200)
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda: transports(market)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(ST, "evaluate_stage", lambda *a, **k: fast(*a, **k)):
                self.assertEqual(run.main(fetch), 0)
                line = logs.read_lines(repo / RUN_LOG)[0]
                self.assertEqual((line["purpose"], line["status"], line["study_tree"]), ("fetch", "complete", fx["tree"]))
                sha = line["input_snapshot_sha256s"][0]
                # F2: the next run refuses until the fetch line is committed and pushed
                with self.assertRaises(guards.Refused):
                    run.main(fetch)
                FR.commit_push(repo, "2026-12-01T01:00:00+00:00")
                # F1: a stage is fetched once
                with self.assertRaises(runner.RunRefused):
                    run.main(fetch)
                evaluate = ["evaluate", "--stage", "validation", "--enumeration", str(fx["enumeration"]),
                            "--snapshot", snap, "--sha", sha]
                with self.assertRaises(runner.RunRefused):     # a snapshot the fetch line did not seal
                    run.main(evaluate[:-1] + ["f" * 64])
                other = Path(tmp) / "other-enum.json"
                other.write_text(json.dumps(enum))
                with self.assertRaises(guards.Refused):        # an enumeration other than the sealed one
                    run.main(evaluate[:4] + [str(other)] + evaluate[5:])
                # a run that fails before its write leaves no results file and a failed line; the retry may follow
                with mock.patch.object(ST, "evaluate_stage", side_effect=RuntimeError("killed")):
                    with self.assertRaises(RuntimeError):
                        run.main(evaluate)
                results = repo / RESULTS_DIR / "validation.json"
                self.assertFalse(results.exists())
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[-1]["status"], "failed")
                FR.commit_push(repo, "2026-12-01T02:00:00+00:00")
                # F10: killed after the atomic write: the line records the file's sha256 as complete
                real_write = runner.atomic_write_results

                def write_then_die(path, obj):
                    real_write(path, obj)
                    raise KeyboardInterrupt("killed after the results write")
                with mock.patch.object(runner, "atomic_write_results", write_then_die):
                    with self.assertRaises(KeyboardInterrupt):
                        run.main(evaluate)
                last = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual((last["status"], last["results_sha256"]), ("complete", canon.sha256_file(results)))
                self.assertEqual(json.loads(results.read_text())["protocol_sha256"], fx["protocol_sha256"])
                FR.commit_push(repo, "2026-12-01T03:00:00+00:00")
                # M-4 and F1: the first results file governs; a second evaluate is refused
                with self.assertRaises(runner.RunRefused):
                    run.main(evaluate)
                self.assertEqual(logs.governing_results(logs.read_lines(repo / RUN_LOG), "validation")["results_sha256"],
                                 canon.sha256_file(results))
                body = json.loads(results.read_text())
                self.assertEqual(body["stage_labels"], [])
                self.assertTrue(all(r["qualifiers"] == [] for r in body["items"].values()))


class ContextRefusals(unittest.TestCase):
    def ctx(self, repo):
        with FR.isolated_bytecode():
            return runner.context(repo)

    def test_bytecode_isolation_and_ignored_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            with self.assertRaises(guards.Refused):      # not through run.py
                runner.context(repo)
            self.ctx(repo)
            FR.write(repo / STUDY_PATH / "core" / "__pycache__" / "x.cpython-313.pyc", b"\0")
            self.ctx(repo)                                # caches are allowed, and never read (sys.pycache_prefix)
            FR.write(repo / STUDY_PATH / ".env", "planted\n")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)

    def test_logs_must_equal_origin_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            logs.append_line(repo / ACCESS_LOG, {"record_kind": "authorization"})
            with self.assertRaises(guards.Refused):      # not committed
                self.ctx(repo)
            FR.sh(repo, "add", "-A")
            FR.sh(repo, "commit", "-q", "-m", "log", when="2026-10-03T00:00:00+00:00")
            with self.assertRaises(guards.Refused):      # committed, not pushed
                self.ctx(repo)
            FR.sh(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
            self.ctx(repo)
            (repo / ACCESS_LOG).write_text("")            # a truncated log is refused the same way
            with self.assertRaises(guards.Refused):
                self.ctx(repo)

    def test_the_protocol_that_runs_is_the_freeze_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            self.assertEqual(self.ctx(repo)["protocol_sha256"], fx["protocol_sha256"])
            body = json.loads((repo / PROTOCOL_PATH).read_text())
            body["id"] = "another-id-changes-every-seed"
            FR.write(repo / PROTOCOL_PATH, json.dumps(body, indent=1) + "\n")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)
            FR.commit_push(repo, "2026-10-03T00:00:00+00:00")
            with self.assertRaises(guards.Refused):       # committed and pushed: still not the freeze blob
                self.ctx(repo)

    def test_amendment_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            ctx = self.ctx(repo)
            n0 = ctx["n0_pinned"]
            cal_amend = repo / DATA_DIR / "session-calendar-amendments.jsonl"
            # a line for a validation session (before the freeze session) is refused, even pushed in time
            logs.append_line(cal_amend, {"kind": "remove_session", "session": "2020-06-01", "source": "notice"})
            FR.commit_push(repo, "2026-10-03T00:00:00+00:00")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            cal_amend = repo / DATA_DIR / "session-calendar-amendments.jsonl"
            removed = ctx["cal"].offset(n0, 10)
            logs.append_line(cal_amend, {"kind": "remove_session", "session": n0, "source": "notice"})
            logs.append_line(cal_amend, {"kind": "remove_session", "session": removed, "source": "notice"})
            FR.commit_push(repo, "2026-11-20T00:00:00+00:00")   # before 09:30 ET of both sessions
            c2 = self.ctx(repo)
            self.assertFalse(c2["cal"].is_session(removed))
            self.assertEqual(c2["n0_pinned"], n0)                    # M-5: N0 keeps its freeze-time date
            self.assertEqual(c2["cal"].next_on_or_after(n0), ctx["cal"].offset(n0, 1))
            late = ctx["cal"].offset(n0, 20)
            logs.append_line(cal_amend, {"kind": "remove_session", "session": late, "source": "notice"})
            FR.commit_push(repo, FR.git_date(ctx["cal"].at(late, "10:00")))   # after 09:30 ET of its session
            with self.assertRaises(guards.Refused):
                self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            logs.append_line(repo / DATA_DIR / "fees-v3-amendments.jsonl",
                             {"kind": "finra_taf", "from": "2020-01-01", "to": "2020-12-31", "usd_per_share": 0.0002,
                              "max_per_trade": 9.0})
            FR.commit_push(repo, "2026-10-03T00:00:00+00:00")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)

    def test_coverage_decision_must_equal_the_committed_count_only_output(self):
        from core.params import COUNT_ONLY_OUTPUT
        for bad in ({"dropped_years": ["2018"], "items_tested": True},
                    {"dropped_years": [2018], "items_tested": True},
                    {"dropped_years": [], "items_tested": "yes"},
                    {"dropped_years": [], "items_tested": False}):
            with tempfile.TemporaryDirectory() as tmp:
                probe = FR.build(tmp, frozen=False)
                cd = {**bad, "count_only_output": COUNT_ONLY_OUTPUT,
                      "count_only_output_sha256": canon.sha256_file(probe["repo"] / COUNT_ONLY_OUTPUT)}
            with tempfile.TemporaryDirectory() as tmp:
                repo = FR.build(tmp, coverage_decision=cd)["repo"]
                with self.assertRaises(guards.Refused, msg=json.dumps(bad)):
                    self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp, coverage_decision={"dropped_years": [], "items_tested": True})["repo"]
            with self.assertRaises(guards.Refused):          # no pinned output
                self.ctx(repo)

    def test_transport_deviation_governs_only_when_committed_and_passing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp)
            repo = fx["repo"]
            FR.write(repo / STUDY_PATH / "fetch" / "transport.py", "HOST = 'fixture-v2'\n")
            FR.commit_push(repo, "2027-01-04T00:00:00+00:00")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)
            new_tree = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            new_fetch = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
            dev = {"number": 1, "kind": "transport", "cause": "synthetic host change", "diff_reference": "HEAD",
                   "new_tree": new_tree, "new_fetch_tree": new_fetch, "affected_stages": ["holdout"],
                   "transport_check": {"passes": False}}
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [dev]}))
            FR.commit_push(repo, "2027-01-04T01:00:00+00:00")
            with self.assertRaises(guards.Refused):           # its reproduction check did not pass
                self.ctx(repo)
            dev["transport_check"] = {"passes": True}
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [dev]}))
            with self.assertRaises(guards.Refused):           # not yet committed and pushed
                self.ctx(repo)
            FR.commit_push(repo, "2027-01-04T02:00:00+00:00")
            ctx = self.ctx(repo)
            self.assertEqual(ctx["transport_deviation"]["number"], 1)
            self.assertTrue(runner.transport_qualified(ctx, []))
            FR.write(repo / STUDY_PATH / "core" / "__init__.py", "# changed evaluation code\n")
            FR.commit_push(repo, "2027-01-04T03:00:00+00:00")
            tree2 = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [dev, {**dev, "number": 2, "new_tree": tree2}]}))
            FR.commit_push(repo, "2027-01-04T04:00:00+00:00")
            with self.assertRaises(guards.Refused):           # a change outside study/fetch/ is an ordinary deviation
                self.ctx(repo)


if __name__ == "__main__":
    unittest.main()
