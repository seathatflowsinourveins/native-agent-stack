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
from core import canon, gate, guards, logs, runner
from core import stage as ST
from core.params import ACCESS_LOG, DATA_DIR, DEVIATIONS, PROTOCOL_PATH, RESULTS_DIR, RUN_LOG, STUDY_PATH
from core.store import Store
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
                    mock.patch.object(run, "transports", lambda *_: transports(market)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(ST, "evaluate_stage", lambda *a, **k: fast(*a, **k)):
                # review round 11, F4: the first run appends only its start line; nothing is fetched before it is
                # committed and pushed
                self.assertEqual(run.main(fetch), 0)
                self.assertEqual(logs.read_lines(repo / RUN_LOG)[0]["purpose"], "fetch_start")
                self.assertEqual(market.calls, [])
                with self.assertRaises(guards.Refused):
                    run.main(fetch)
                FR.commit_push(repo, "2026-11-30T01:00:00+00:00")
                self.assertEqual(run.main(fetch), 0)
                line = logs.read_lines(repo / RUN_LOG)[-1]
                self.assertEqual(line["start_index"], 0)
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


class StageOrder(unittest.TestCase):
    def test_development_is_evaluated_only_after_the_validation_fetch(self):
        """Review round 11, F3: no development outcome exists before validation's snapshot is sealed and logged."""
        line = {"stage": "development", "purpose": "fetch", "status": "complete", "input_snapshot_sha256s": ["a" * 64],
                "fetch_incomplete_rate": 0.0}
        with tempfile.TemporaryDirectory() as tmp:
            ctx = {"repo": Path(tmp), "run_log": [line]}
            with self.assertRaisesRegex(runner.RunRefused, "validation's complete fetch"):
                runner.evaluate_run(ctx, "development", Path(tmp) / "snap", "a" * 64, None, None)
            ctx["run_log"].append(dict(line, stage="validation", input_snapshot_sha256s=["b" * 64]))
            with self.assertRaises(FileNotFoundError):      # past the order check, to the sealed snapshot
                runner.evaluate_run(ctx, "development", Path(tmp) / "snap", "a" * 64, None, None)


class StageTesting(unittest.TestCase):
    def test_a_dropped_2020_does_not_untest_development(self):
        """Review round 11, C9 (coverage_rule.item_rule): dropping 2020 sets p = 1 at validation only; development
        is computed unless every development year is dropped, and says so."""
        cov = {"items_tested": False, "dropped_years": frozenset({2020})}
        self.assertEqual(runner.stage_testing("validation", cov), {"tested": False})
        self.assertEqual(runner.stage_testing("development", cov), {"tested": True, "development_computed": True})
        cov = {"items_tested": True, "dropped_years": frozenset({2017, 2018, 2019})}
        self.assertEqual(runner.stage_testing("development", cov), {"tested": False, "development_computed": False})
        self.assertEqual(runner.stage_testing("validation", cov), {"tested": True})


def amend_main(repo, now, *argv):
    with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), mock.patch.object(run, "now", lambda: now):
        return run.main(list(argv))


def log_amendment(repo, file, line, t):
    """run.py authorize --purpose amend, push, run.py amend, push (review round 10, F2)."""
    amend_main(repo, t, "authorize", "--purpose", "amend")
    aid = logs.read_lines(repo / ACCESS_LOG)[-1]["authorization_id"]
    FR.commit_push(repo, FR.git_date(t + 60))
    amend_main(repo, t + 120, "amend", "--authorization", aid, "--file", file, "--line", str(line))
    FR.commit_push(repo, FR.git_date(t + 180))
    return aid


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
            # review round 10, H2: a locally moved tracking ref is not a push (git ls-remote disagrees)
            pushed = FR.sh(repo, "rev-parse", "origin/main")
            FR.sh(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
            with self.assertRaisesRegex(guards.Refused, "remote's main"):
                self.ctx(repo)
            FR.sh(repo, "update-ref", "refs/remotes/origin/main", pushed)
            FR.push(repo)
            self.ctx(repo)
            (repo / ACCESS_LOG).write_text("")            # a truncated log is refused the same way
            with self.assertRaises(guards.Refused):
                self.ctx(repo)

    def test_append_only_history_on_main(self):
        # review round 10, M1: a pushed commit that removes a line (and the next that restores the current bytes)
        # still leaves an edited version in origin/main's history, which is refused
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            logs.append_line(repo / RUN_LOG, {"stage": "development", "purpose": "fetch", "status": "failed"})
            logs.append_line(repo / RUN_LOG, {"stage": "development", "purpose": "evaluate", "status": "complete"})
            FR.commit_push(repo, "2026-10-03T00:00:00+00:00")
            self.ctx(repo)
            first = (repo / RUN_LOG).read_text().splitlines(keepends=True)[0]
            (repo / RUN_LOG).write_text(first)
            FR.commit_push(repo, "2026-10-03T01:00:00+00:00")
            with self.assertRaisesRegex(guards.Refused, "edited, not appended"):
                self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            dev = {"number": 1, "kind": "ordinary", "cause": "synthetic"}
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [dev]}))
            FR.commit_push(repo, "2026-10-03T00:00:00+00:00")
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [dev, {**dev, "number": 2}]}, indent=1))
            FR.commit_push(repo, "2026-10-03T01:00:00+00:00")
            self.ctx(repo)                                # the list grew; its bytes need not
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [{**dev, "number": 2}]}))
            FR.commit_push(repo, "2026-10-03T02:00:00+00:00")
            with self.assertRaisesRegex(guards.Refused, "edited, not appended"):
                self.ctx(repo)

    def test_reach_times_come_from_signed_merge_commits(self):
        # review round 10, M3: an amendment line whose first commit is not signed by the merge key has no recorded
        # reach time, even if its committer date is early
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp)["repo"]
            ctx = self.ctx(repo)
            s = ctx["cal"].offset(ctx["n0_pinned"], 10)
            logs.append_line(repo / DATA_DIR / "session-calendar-amendments.jsonl",
                             {"kind": "remove_session", "session": s, "source": "notice"})
            FR.commit_push(repo, "2026-11-20T00:00:00+00:00", sign=False)
            with self.assertRaisesRegex(guards.Refused, "not a merge commit signed"):
                self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            repo = FR.build(tmp, freeze_sign=False)["repo"]
            with self.assertRaisesRegex(guards.Refused, "the freeze commit"):
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
            # review round 10, F2: each line must also be logged in the access log under purpose 'amend'
            with self.assertRaisesRegex(guards.Refused, "not logged in the access log under purpose 'amend'"):
                self.ctx(repo)
            t = logs.parse_utc("2026-11-20T01:00:00Z")
            with self.assertRaises(gate.NoAuthorization):    # an 'amend' record runs only under its authorization
                amend_main(repo, t, "amend", "--authorization", "amend-001", "--file", "calendar", "--line", "0")
            log_amendment(repo, "calendar", 0, t)
            with self.assertRaisesRegex(guards.Refused, "line 1: not logged"):
                self.ctx(repo)
            log_amendment(repo, "calendar", 1, t + 600)
            rec = logs.read_lines(repo / ACCESS_LOG)[-1]
            self.assertEqual((rec["amendment"]["file"], rec["amendment"]["line"], rec["amendment"]["source"]),
                             ("session-calendar-amendments.jsonl", 1, "notice"))
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
            # a line pushed in time whose 'amend' record reached origin/main after 09:30 ET of its session
            repo = FR.build(tmp)["repo"]
            s = ctx["cal"].offset(n0, 5)
            logs.append_line(repo / DATA_DIR / "session-calendar-amendments.jsonl",
                             {"kind": "remove_session", "session": s, "source": "notice"})
            FR.commit_push(repo, "2026-11-20T00:00:00+00:00")
            log_amendment(repo, "calendar", 0, ctx["cal"].at(s, "09:40"))
            with self.assertRaisesRegex(guards.Refused, "'amend' record reached origin/main at or after"):
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

    def test_transport_deviation_governs_only_with_its_logged_reproduction_check(self):
        """Review round 10, H1 and F6: a transport deviation governs only when it cites the committed output of a
        logged run.py transport-check run from its tree; a self-declared passes: true is refused."""
        cal = synth.calendar()
        market, symbols = build_market(cal)
        enum = {"symbols": symbols, "actions": [], "active": symbols, "counts": {}}
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, enumeration=enum)
            repo, snap = fx["repo"], str(Path(tmp) / "snap")

            def main(*argv):
                with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                        mock.patch.object(run, "transports", lambda *_: transports(market)), \
                        mock.patch.object(run, "clock", fixed_clock):
                    return run.main(list(argv))
            main("fetch", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap)
            FR.commit_push(repo, "2027-01-03T00:00:00+00:00")                # the start line (F4)
            main("fetch", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap)
            sha = logs.read_lines(repo / RUN_LOG)[-1]["input_snapshot_sha256s"][0]
            FR.commit_push(repo, "2027-01-04T00:00:00+00:00")
            check = ["transport-check", "--stage", "validation", "--enumeration", str(fx["enumeration"]),
                     "--snapshot", snap, "--sha", sha]
            with self.assertRaises(guards.Refused):           # the pinned tree has nothing to check
                main(*check)
            FR.write(repo / STUDY_PATH / "fetch" / "transport.py", "HOST = 'fixture-v2'\n")
            FR.commit_push(repo, "2027-01-04T01:00:00+00:00")
            with self.assertRaises(guards.Refused):
                self.ctx(repo)
            new_tree = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            new_fetch = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}/fetch")
            forged = {"number": 1, "kind": "transport", "cause": "synthetic host change", "diff_reference": "HEAD",
                      "new_tree": new_tree, "new_fetch_tree": new_fetch, "affected_stages": ["holdout"],
                      "transport_check": {"passes": True}}
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [forged]}))
            FR.commit_push(repo, "2027-01-04T02:00:00+00:00")
            with self.assertRaises(guards.Refused):           # a self-declared pass without its logged output
                self.ctx(repo)
            # review round 11, F3: a sealed holdout snapshot is checked too (here a copy of the validation snapshot
            # sealed as a collection batch), so the check needs --holdout-root
            hroot = Path(tmp) / "holdout"
            self.assertEqual(Store.read(snap, sha).write(hroot / "collect-collect-001"), sha)
            logs.append_line(repo / ACCESS_LOG, {"utc": "x", "record_kind": "authorization",
                                                 "authorization_id": "collect-001", "purpose": "collect",
                                                 "decision": "granted", "refusal": None, "requested_items": [],
                                                 "retry_of": None})
            logs.append_line(repo / ACCESS_LOG, gate.completion("collect-001", "x", "complete", sha, 0, None, []))
            FR.commit_push(repo, "2027-01-04T02:30:00+00:00")
            with self.assertRaisesRegex(runner.RunRefused, "holdout-root"):
                main(*check)
            self.assertEqual(main(*check, "--holdout-root", str(hroot)), 0)
            rel = f"{RESULTS_DIR}/transport-check-{new_tree[:12]}.json"
            body = json.loads((repo / rel).read_text())
            self.assertTrue(body["passes"], body)
            self.assertEqual(list(body["holdout"]), ["collect-collect-001"])
            self.assertTrue(body["holdout"]["collect-collect-001"]["live"]["passes"])
            # the live sample's seed is the first origin/main commit holding the new tree
            first = FR.sh(repo, "log", "--first-parent", "--reverse", "--format=%H", "origin/main", "--",
                          STUDY_PATH).splitlines()[-1]
            self.assertEqual(body["live"]["seed"], first)
            self.assertEqual((body["new_tree"], body["changed_paths"]), (new_tree, ["fetch/transport.py"]))
            line = logs.read_lines(repo / RUN_LOG)[-1]
            self.assertEqual((line["purpose"], line["study_tree"], line["results_sha256"]),
                             ("transport_check", new_tree, canon.sha256_file(repo / rel)))
            FR.commit_push(repo, "2027-01-04T03:00:00+00:00")
            with self.assertRaises(runner.RunRefused):         # a tree's check runs once
                main(*check, "--holdout-root", str(hroot))
            wrong = {**forged, "number": 2, "transport_check": {"passes": True, "output_path": rel,
                                                                 "output_sha256": "0" * 64}}
            good = {**forged, "number": 3, "transport_check": {"passes": True, "output_path": rel,
                                                                "output_sha256": canon.sha256_file(repo / rel)}}
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [forged, wrong]}))
            FR.commit_push(repo, "2027-01-04T04:00:00+00:00")
            with self.assertRaises(guards.Refused):           # the output's sha256 differs
                self.ctx(repo)
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [forged, wrong, good]}))
            with self.assertRaises(guards.Refused):           # not yet committed and pushed
                self.ctx(repo)
            FR.commit_push(repo, "2027-01-04T05:00:00+00:00")
            ctx = self.ctx(repo)
            self.assertEqual(ctx["transport_deviation"]["number"], 3)
            self.assertTrue(runner.transport_qualified(ctx, []))
            FR.write(repo / STUDY_PATH / "core" / "__init__.py", "# changed evaluation code\n")
            FR.commit_push(repo, "2027-01-04T06:00:00+00:00")
            tree2 = FR.sh(repo, "rev-parse", f"HEAD:{STUDY_PATH}")
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [forged, wrong, good, {**good, "number": 4,
                                                                                          "new_tree": tree2}]}))
            FR.commit_push(repo, "2027-01-04T07:00:00+00:00")
            with self.assertRaises(guards.Refused):           # a change outside study/fetch/ is an ordinary deviation
                self.ctx(repo)

    def test_a_void_deviation_scores_validation_p_one(self):
        """Review round 10, F4: a committed void deviation (a recorded pre-freeze read) makes every validation item
        score p = 1, and the holdout gate refuses; a malformed void record is refused."""
        cal = synth.calendar()
        market, symbols = build_market(cal)
        enum = {"symbols": symbols, "actions": [], "active": symbols, "counts": {}}
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, enumeration=enum)
            repo, snap = fx["repo"], str(Path(tmp) / "snap")
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [{"number": 1, "kind": "void", "scope": "later"}]}))
            FR.commit_push(repo, "2026-11-01T00:00:00+00:00")
            with self.assertRaisesRegex(guards.Refused, "void deviation"):
                self.ctx(repo)
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [
                {"number": 1, "kind": "void", "scope": "later"},
                {"number": 2, "kind": "void", "scope": "tests", "cause": "a synthetic pre-freeze read"}]}))
            FR.commit_push(repo, "2026-11-01T01:00:00+00:00")
            with self.assertRaisesRegex(guards.Refused, "void deviation"):    # the malformed record stays refused
                self.ctx(repo)
        with tempfile.TemporaryDirectory() as tmp:
            fx = FR.build(tmp, enumeration=enum)
            repo, snap = fx["repo"], str(Path(tmp) / "snap")
            FR.write(repo / DEVIATIONS, json.dumps({"deviations": [
                {"number": 1, "kind": "void", "scope": "tests", "cause": "a synthetic pre-freeze read"}]}))
            FR.commit_push(repo, "2026-11-01T00:00:00+00:00")
            self.assertEqual(self.ctx(repo)["voids"], frozenset({"tests"}))
            fast = functools.partial(ST.evaluate_stage, B=200)
            with FR.isolated_bytecode(), mock.patch.object(run, "REPO", repo), \
                    mock.patch.object(run, "transports", lambda *_: transports(market)), \
                    mock.patch.object(run, "clock", fixed_clock), \
                    mock.patch.object(ST, "evaluate_stage", lambda *a, **k: fast(*a, **k)):
                fetch = ["fetch", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot", snap]
                run.main(fetch)
                FR.commit_push(repo, "2026-11-30T00:00:00+00:00")            # the start line (F4)
                run.main(fetch)
                sha = logs.read_lines(repo / RUN_LOG)[-1]["input_snapshot_sha256s"][0]
                FR.commit_push(repo, "2026-12-01T01:00:00+00:00")
                run.main(["evaluate", "--stage", "validation", "--enumeration", str(fx["enumeration"]), "--snapshot",
                          snap, "--sha", sha])
            body = json.loads((repo / RESULTS_DIR / "validation.json").read_text())
            self.assertEqual(body["void"]["void_deviations"], ["tests"])
            self.assertTrue(all(r["p_stage"] == 1.0 for r in body["items"].values()))
            self.assertTrue(all(v == "underpowered" for v in body["labels"].values()))
            FR.commit_push(repo, "2026-12-01T02:00:00+00:00")
            from core import holdout
            ctx = self.ctx(repo)
            g = holdout.gate_context(ctx, "count", ctx["cal"].at("2027-12-10", "20:00"))
            self.assertTrue(any("validation is void" in r for r in gate.evaluator_refusals(g)))

if __name__ == "__main__":
    unittest.main()
