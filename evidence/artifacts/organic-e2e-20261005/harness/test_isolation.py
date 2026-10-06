"""Focused checks for round 4 of #786 (the harness's own module, run at nice 19, no model call):

  cd evidence/artifacts/organic-e2e-20261005/harness && nice -n 19 python3 -B -m unittest -v test_isolation

- The structural G13 (CC item task-ns2604-coop-20261006T132948Z): in a synthetic trial's namespace, `cat` on a real file
  in each hidden location fails with ENOENT or EACCES (the check fails if it can read one), its own inputs stay
  readable, the receipt carries the hidden list with its sha256s, G13 rejects a receipt that leaves a location out,
  binds an answer source back or ran outside the namespace, and the launcher's wrapped run records the namespace and
  ends the client gracefully. ISOLATION_SKIP_CLIENTS=1 leaves out the client start checks (claude, codex, the SDKs,
  codex app-server through the CL7b wrapper).
- The GPT micro-check of 1f81d645, P3: the deadline and completion decisions read the unrounded offsets, so a result
  that arrived before T is never held.
These are local integration checks of this harness, not upstream acceptance."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# The structural checks need this host's bubblewrap and the experiment's roots; elsewhere (a CI runner) they skip.
HOST_READY = os.access("/usr/bin/bwrap", os.X_OK) and \
    (Path.home() / ".local/state/native-agent-stack/coordination").is_dir()


def _synthetic_plan(client: str = "claude"):
    import isolation
    trial_id = str(uuid.uuid4())
    work = isolation.TRIAL_ROOT_BASE / f"ut{trial_id[:8]}"
    fixture = isolation.NEUTRAL_ROOT / f"ut{trial_id[:8]}"
    cfg = {"trial_root": str(work), "suite": {"path": str(isolation.SUITE_DEFAULT)},
           "fixture": {"oracles_path": str(isolation.FIXTURE_CACHE / "oracles.json")}}
    clone = work / "clones" / trial_id if client == "codex" else None
    settings = work / "settings" / f"{trial_id}.json" if client == "claude" else None
    plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, fixture, clone=clone, settings=settings,
                          prompt=work / "prompts" / f"{trial_id}.txt")
    return isolation, cfg, plan, trial_id, fixture, work


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class StructuralG13(unittest.TestCase):
    report: dict | None = None

    @classmethod
    def setUpClass(cls):
        import isolation
        cls.report = isolation.selftest(clients=os.environ.get("ISOLATION_SKIP_CLIENTS") != "1")

    def test_every_hidden_location_refuses_cat(self):
        hidden = self.report["hidden"]
        self.assertGreaterEqual(len({h["location"] for h in hidden}), 10, "too few hidden locations probed")
        readable = [h for h in hidden if h["inside"] == "READABLE"]
        self.assertEqual(readable, [], "a hidden location was readable inside the namespace")
        self.assertTrue(all(h["inside"] in ("ENOENT", "EACCES") for h in hidden), hidden)
        for client in ("claude", "codex"):
            locations = {h["location"] for h in hidden if h["client"] == client}
            for needed in ("suite cards", "the fixture cache's oracles.json", "another trial's fixture",
                           "another trial's Claude transcript", "the shared Codex transcripts"):
                self.assertIn(needed, locations, f"{client}: no probe for {needed}")
        self.assertIn("the shared sessions alias in the trial's clone",
                      {h["location"] for h in hidden if h["client"] == "codex"})
        for client in ("claude", "codex"):
            siblings = {h["location"] for h in hidden if h["client"] == client and h["location"].startswith("this run's sibling")}
            self.assertEqual(len(siblings), 6, f"{client}: the same-run sibling's files were not all probed: {siblings}")

    def test_own_inputs_and_native_config_stay_readable(self):
        for group in ("own", "native"):
            for client, verdicts in self.report[group].items():
                self.assertTrue(verdicts, f"{group} {client}: nothing checked")
                self.assertTrue(all(v == "READABLE" for v in verdicts.values()), (group, client, verdicts))

    def test_writes_land_in_the_trials_own_folders(self):
        for client, writes in self.report["writes"].items():
            self.assertEqual(writes["rc"], 0, writes)
            self.assertTrue(writes["sessions_write_in_private_folder"], writes)
            self.assertTrue(writes["sessions_write_not_in_native_folder"], writes)
            self.assertTrue(writes["last_write_in_private_folder"], writes)
            self.assertTrue(writes["pid1_argv_shows_no_option_or_hidden_path"], writes)

    def test_namespace_is_the_trials_own(self):
        for client, ns in self.report["namespaces"].items():
            self.assertTrue(ns["namespace"], ns)
            self.assertNotEqual(ns["namespace"], ns["host_namespace"], ns)

    def test_launch_paths_start_under_the_wrapper(self):
        if os.environ.get("ISOLATION_SKIP_CLIENTS") == "1":
            self.skipTest("ISOLATION_SKIP_CLIENTS=1")
        self.assertGreaterEqual(len(self.report["clients"]), 7)
        failing = {k: v for k, v in self.report["clients"].items() if not v.get("ok")}
        self.assertEqual(failing, {})

    def test_selftest_passes(self):
        self.assertTrue(self.report["pass"], json.dumps(self.report, default=str)[:2000])

    def test_selftest_report_is_plain_json(self):
        """prepare.py writes it with common.write_json, which has no default= for a stray Path or set."""
        json.dumps(self.report)


class Receipt(unittest.TestCase):
    def test_receipt_carries_the_hidden_list(self):
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        rec = isolation.receipt(plan, ["bash", "-lc", "<line>"])
        self.assertEqual(rec["decision"], isolation.ISOLATION_DECISION)
        self.assertTrue(rec["version"] and rec["version"].startswith("bubblewrap"), rec["version"])
        self.assertEqual(rec["argv"][0], isolation.BWRAP)
        self.assertEqual(rec["argv_visible"][:2], [isolation.BWRAP, "--args"])
        locations = {h["location"]: h for h in rec["hidden"]}
        for needed in ("run roots: oracle runs, other trials' drafts, grades", "run roots: this run", "suite cards",
                       "the fixture cache's oracles.json", "other trials' fixtures (and their drafts)",
                       "other trials' Claude transcripts", "the shared Codex transcripts",
                       "the shared sessions alias in the trial's clone"):
            self.assertIn(needed, locations)
        for entry in rec["hidden"]:
            self.assertEqual(entry["path_sha256"], isolation.sha256_text(isolation.untilde(entry["path"])))
            if entry["kind"] == "file":
                self.assertEqual(len(entry.get("content_sha256") or ""), 64, entry)
        argv = " ".join(rec["argv"])
        for root in isolation.HIDDEN_ROOTS:
            self.assertIn(f"--tmpfs {isolation.tilde(root)}", argv)
        self.assertIn(f"--bind {isolation.tilde(plan['private'] / 'codex-sessions')} {isolation.tilde(isolation.CODEX_SESSIONS)}", argv)
        json.dumps(rec)   # the launched row is written with plain json.dumps

    def test_finish_moves_the_answer_file_and_publishes_rollouts(self):
        """finish() after the client exits, against a temporary sessions folder (never the real one), twice."""
        import isolation
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            work, private, sessions = base / "work", base / "work" / "iso" / "t1", base / "sessions"
            (private / "last").mkdir(parents=True)
            (private / "last" / "t1.txt").write_text("answer\n")
            rollout = private / "codex-sessions" / "2026" / "10" / "06" / "rollout-2026-10-06T10-00-00-abc.jsonl"
            rollout.parent.mkdir(parents=True)
            rollout.write_text("{}\n")
            saved = isolation.CODEX_SESSIONS
            isolation.CODEX_SESSIONS = sessions
            try:
                plan = {"work": work, "private": private}
                first = isolation.safe_finish(plan)
                second = isolation.safe_finish(plan)
            finally:
                isolation.CODEX_SESSIONS = saved
            self.assertEqual(first, {"last_moved": ["t1.txt"],
                                     "rollouts_published": ["2026/10/06/rollout-2026-10-06T10-00-00-abc.jsonl"]})
            self.assertEqual((work / "last" / "t1.txt").read_text(), "answer\n")
            self.assertTrue((sessions / "2026" / "10" / "06" / rollout.name).exists())
            self.assertEqual(second, {"last_moved": [], "rollouts_published": []})

    def test_app_server_runtime_reads_the_wrappers_record(self):
        """CL7b's exit row: the namespace record bwrap wrote through the wrapper's fd 4, read back without raising."""
        import isolation
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            private = base / "work" / "iso" / "t2"
            private.mkdir(parents=True)
            (private / "info.json").write_text(json.dumps({"child-pid": 7, "mnt-namespace": 4026532999}))
            saved = isolation.CODEX_SESSIONS
            isolation.CODEX_SESSIONS = base / "sessions"
            try:
                runtime = isolation.app_server_runtime({"work": base / "work", "private": private})
            finally:
                isolation.CODEX_SESSIONS = saved
            self.assertEqual(runtime["namespace"], "mnt:[4026532999]")
            self.assertNotIn("finish_error", runtime)
            self.assertNotIn("runtime_error", runtime)
            json.dumps(runtime)


class G13Check(unittest.TestCase):
    def _rows(self, client="claude"):
        isolation, cfg, plan, trial_id, fixture, work = _synthetic_plan(client)
        rec = isolation.receipt(plan, ["bash", "-lc", "<line>"])
        rows = {"prepared": {"fixture_private": str(fixture)}, "launched": {"isolation": rec},
                "exit": {"isolation_runtime": {"namespace": "mnt:[1]", "host_namespace": "mnt:[2]",
                                               "tree": {"processes_seen": 4, "in_trial_namespace": 4, "outside": []}}}}
        return isolation, cfg, trial_id, rows

    def _check(self, isolation, cfg, trial_id, rows, client="claude"):
        return isolation.check(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, client, rows)

    def test_a_complete_receipt_passes(self):
        for client in ("claude", "codex"):
            isolation, cfg, trial_id, rows = self._rows(client)
            result = self._check(isolation, cfg, trial_id, rows, client)
            self.assertTrue(result["ok"], (client, result["failures"]))

    def test_a_missing_location_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["launched"]["isolation"]["hidden"] = [h for h in rows["launched"]["isolation"]["hidden"]
                                                  if h["location"] != "suite cards"]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_tmpfs_left_out_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        ops = rows["launched"]["isolation"]["ops"]
        rows["launched"]["isolation"]["ops"] = [op for op in ops if op[2] != isolation.tilde(isolation.FIXTURE_CACHE_ROOT)]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_another_fixture_bound_back_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        other = isolation.tilde(isolation.NEUTRAL_ROOT / "0123abcd")
        rows["launched"]["isolation"]["ops"].append(["bind", other, other])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_an_experiment_project_bound_back_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        name = isolation.claude_slug(isolation.NEUTRAL_ROOT / "0123abcd")
        path = isolation.tilde(isolation.CLAUDE_PROJECTS / name)
        rows["launched"]["isolation"]["ops"].append(["bind", path, path])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_home_rebound_after_the_tmpfs_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        home = isolation.tilde(isolation.HOME)
        rows["launched"]["isolation"]["ops"].append(["bind", home, home])
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_a_tree_outside_the_namespace_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["exit"]["isolation_runtime"]["tree"]["outside"] = [{"exe": "claude", "namespace": "mnt:[2]"}]
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])
        rows["exit"]["isolation_runtime"]["tree"]["outside"] = []
        rows["exit"]["isolation_runtime"]["namespace"] = "mnt:[2]"
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])

    def test_no_receipt_fails(self):
        isolation, cfg, trial_id, rows = self._rows()
        rows["launched"].pop("isolation")
        self.assertFalse(self._check(isolation, cfg, trial_id, rows)["ok"])


@unittest.skipUnless(HOST_READY, "needs /usr/bin/bwrap and the experiment's roots on this host")
class WrappedLaunch(unittest.TestCase):
    def test_a_nested_namespace_is_no_escape(self):
        """Codex's own sandbox, a nested bwrap or `unshare -rm` puts a process in a namespace below the trial's: counted
        apart, never as outside, and its locked mounts cannot be unmounted to reveal a hidden root."""
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            fixture.mkdir(parents=True)
            (work / "prompts").mkdir(parents=True)
            (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
            (work / "clones" / trial_id).mkdir(parents=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
            isolation.prepare_dirs(plan)
            probe = isolation.COORDINATION_ROOT / "command-center" / "ledger.jsonl"
            line = (f"unshare -rm sh -c 'umount {isolation.COORDINATION_ROOT} 2>/dev/null; "
                    f"if cat {probe} >/dev/null 2>&1; then echo REVEALED > {fixture}/verdict; "
                    f"else echo hidden > {fixture}/verdict; fi; sleep 4'")
            run_cfg = {"binaries": {"claude": {"realpath": "/nonexistent/claude"}, "codex": {"realpath": "/nonexistent/codex"}},
                       "claude_completion": {"policy": "complete-at-result", "t_seconds": 60}}
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outcome = launcher.run_client(root, run_cfg, "codex", line, fixture, root / "s.jsonl", root / "e.err", None,
                                              plan)
            tree = outcome["isolation_runtime"]["tree"]
            self.assertEqual((fixture / "verdict").read_text().strip(), "hidden")
            self.assertGreaterEqual(tree["in_nested_namespaces"], 1, tree)
            self.assertEqual(tree["outside"], [], tree)
            rows = {"prepared": {"fixture_private": str(fixture)},
                    "launched": {"isolation": isolation.receipt(plan, ["bash", "-lc", "<line>"])},
                    "exit": {"isolation_runtime": outcome["isolation_runtime"]}}
            result = isolation.check(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", rows)
            self.assertTrue(result["ok"], result["failures"])
        finally:
            import shutil
            shutil.rmtree(fixture, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    def test_run_client_records_the_namespace(self):
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("codex")
        try:
            fixture.mkdir(parents=True)
            (work / "bin").mkdir(parents=True)
            (work / "prompts").mkdir(parents=True)
            (work / "prompts" / f"{trial_id}.txt").write_text("prompt\n")
            (work / "clones" / trial_id).mkdir(parents=True)
            plan = isolation.plan(cfg, isolation.RUNS_ROOT / "unit-run", trial_id, "codex", fixture,
                                  clone=work / "clones" / trial_id, prompt=work / "prompts" / f"{trial_id}.txt")
            isolation.prepare_dirs(plan)
            events = [{"type": "thread.started", "thread_id": "t"},
                      {"type": "item.completed", "item": {"type": "agent_message", "id": "i1", "text": "done"}},
                      {"type": "turn.completed", "usage": {"input_tokens": 1}}]
            line = "sleep 2; printf '%s\\n' " + " ".join("'" + json.dumps(e) + "'" for e in events) + "; sleep 3"
            run_cfg = {"binaries": {"claude": {"realpath": "/nonexistent/claude"}, "codex": {"realpath": "/nonexistent/codex"}},
                       "claude_completion": {"policy": "complete-at-result", "t_seconds": 60}}
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outcome = launcher.run_client(root, run_cfg, "codex", line, fixture, root / "s.jsonl", root / "e.err", None,
                                              plan)
            runtime = outcome["isolation_runtime"]
            self.assertEqual(outcome["rc"], 0, outcome)
            self.assertTrue(runtime["namespace"], runtime)
            self.assertNotEqual(runtime["namespace"], runtime["host_namespace"])
            self.assertGreaterEqual(runtime["tree"]["processes_seen"], 1, runtime)
            self.assertEqual(runtime["tree"]["outside"], [], runtime)
            self.assertIsInstance(outcome["duration_exact_s"], float)
            self.assertIsNotNone(outcome["time_to_result_exact_s"])
        finally:
            import shutil
            shutil.rmtree(fixture, ignore_errors=True)
            shutil.rmtree(work, ignore_errors=True)

    def test_kill_reaches_the_client_gracefully(self):
        import isolation
        import launcher
        isolation_, cfg, plan, trial_id, fixture, work = _synthetic_plan("claude")
        try:
            fixture.mkdir(parents=True)
            for path in (plan["settings"], plan["prompt"]):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n")
            isolation.prepare_dirs(plan)
            marker = fixture / "graceful"
            inner = f"trap 'sleep 1; echo graceful > {marker}; exit 0' TERM; while :; do sleep 0.2; done"
            line = f"timeout --signal=TERM --kill-after=30s 60 bash -c {json.dumps(inner)}"
            proc, info_fd = isolation.spawn(plan, ["bash", "-lc", line], start_new_session=True,
                                            stdin=subprocess.DEVNULL)
            isolation.read_info(info_fd)
            time.sleep(1.5)
            launcher._kill_group(proc, True)
            proc.wait(timeout=60)
            self.assertTrue(marker.exists(), "the client's TERM handler did not run before the namespace ended")
        finally:
            import shutil
            for path in (fixture, work, plan["own_project"]):
                if path:
                    shutil.rmtree(path, ignore_errors=True)


class UnroundedDeadline(unittest.TestCase):
    """GPT micro-check of 1f81d645, P3 (T = 1800): a result at 1799.96 s in a session that ran 1800.02 s is a result
    before T, not a hold, although both one-decimal presentation fields read 1800.0."""

    outcome = {"duration_s": 1800.0, "time_to_result_s": 1800.0, "duration_exact_s": 1800.02,
               "time_to_result_exact_s": 1799.96, "result_at": "2026-10-06T14:00:00.000Z", "result_before_kill": True,
               "kill_reason": "post_result_grace", "rc": -15}

    def test_hold_reads_the_unrounded_offsets(self):
        import launcher
        self.assertFalse(launcher.holds_cell("claude", dict(self.outcome), 1800))

    def test_completion_reads_the_unrounded_offsets(self):
        import launcher
        policy = {"policy": "complete-at-result", "t_seconds": 1800, "grace_s": 30}
        self.assertTrue(launcher.result_before_t(policy, dict(self.outcome)))
        reason, terminated = launcher.trial_reason("claude", policy, dict(self.outcome), True)
        self.assertIsNone(reason)

    def test_rounded_rows_of_earlier_runs_keep_their_reading(self):
        import launcher
        earlier = {k: v for k, v in self.outcome.items() if not k.endswith("_exact_s")}
        self.assertTrue(launcher.holds_cell("claude", earlier, 1800))

    def test_the_grader_reads_the_unrounded_offsets(self):
        import common
        self.assertEqual(common.decision_times(dict(self.outcome)), (1800.02, 1799.96))
        self.assertFalse(common.deadline_without_result(*common.decision_times(dict(self.outcome)), 1800))

    def test_the_graders_completion_check_reads_the_unrounded_arrival(self):
        import grade
        row = {**self.outcome, "completion_policy": "complete-at-result", "censored": False, "reason": None,
               "t_seconds": 1800}
        self.assertIs(grade.effective_exit(row), row, "a result at 1799.96 s was overridden as one at or after T")


if __name__ == "__main__":
    unittest.main()
