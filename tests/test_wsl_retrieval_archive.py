"""Prospective archival refusal contract; no native retrieval is executed."""

from contextlib import ExitStack, redirect_stderr
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import wsl_retrieval_archive as ARCHIVE
from scripts.validate_convergence import validate_record


ROOT = Path(__file__).resolve().parents[1] / "blueprints/convergence-practice/wsl-retrieval"
SPEC = importlib.util.spec_from_file_location("wsl_retrieval_archive_runner", ROOT / "run.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
REFUSAL = "archived_qmd_activation_denied"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WslRetrievalArchiveTests(unittest.TestCase):
    def test_qmd_refuses_even_before_platform_or_missing_input_checks(self):
        stderr = io.StringIO()
        argv = [str(ROOT / "run.py"), "--mode", "qmd", "--run-dir", "/unused-private-run"]
        with patch.object(sys, "argv", argv), redirect_stderr(stderr), \
                patch.object(RUNNER.platform, "system", side_effect=AssertionError("platform checked")), \
                patch.object(RUNNER.subprocess, "run", side_effect=AssertionError("native launch")):
            with self.assertRaises(SystemExit) as refused:
                RUNNER.main()
        self.assertEqual(refused.exception.code, 2)
        self.assertIn(REFUSAL, stderr.getvalue())

    def test_qmd_refuses_complete_pinned_inputs_before_any_recorder_effect(self):
        # These are complete synthetic pins, not a native Node/QMD acceptance.
        # Only the copied fixture pins change; repository historical bytes do not.
        with tempfile.TemporaryDirectory(prefix="wsl-retrieval-archive-") as folder:
            base = Path(folder)
            fixture = base / "historical fixture"
            fixture.mkdir()
            for name in ("run.py", "oracle.json", "package.json", "package-lock.json"):
                (fixture / name).write_bytes((ROOT / name).read_bytes())
            for source in (ROOT / "seed").rglob("*"):
                if source.is_file():
                    target = fixture / source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(source.read_bytes())

            node = base / "owned tools" / "node"
            node.parent.mkdir()
            node.write_bytes(b"synthetic Node fixture; never executed\n")
            prefix = base / "owned package prefix"
            qmd = prefix / "node_modules" / "@tobilu" / "qmd"
            (qmd / "bin").mkdir(parents=True)
            (qmd / "package.json").write_text('{"version":"2.8.3"}\n')
            (qmd / "LICENSE").write_bytes(b"synthetic license fixture\n")
            (qmd / "bin" / "qmd").write_bytes(b"synthetic QMD entrypoint; never executed\n")
            (prefix / "package-lock.json").write_bytes((ROOT / "package-lock.json").read_bytes())
            pins = copy.deepcopy(json.loads((ROOT / "pins.json").read_text()))
            pins["node"]["binary_sha256"] = digest(node)
            pins["qmd"]["license_sha256"] = digest(qmd / "LICENSE")
            pins["qmd"]["entrypoint_sha256"] = digest(qmd / "bin" / "qmd")
            (fixture / "pins.json").write_text(json.dumps(pins) + "\n")

            self.assertEqual(digest(node), pins["node"]["binary_sha256"])
            self.assertEqual(digest(qmd / "LICENSE"), pins["qmd"]["license_sha256"])
            self.assertEqual(digest(qmd / "bin" / "qmd"), pins["qmd"]["entrypoint_sha256"])
            self.assertEqual(json.loads((qmd / "package.json").read_text())["version"], pins["qmd"]["version"])
            self.assertEqual((prefix / "package-lock.json").read_bytes(), (fixture / "package-lock.json").read_bytes())

            run = base / "new private run"
            argv = [str(ROOT / "run.py"), "--mode", "qmd", "--run-dir", str(run),
                    "--node", str(node), "--package-prefix", str(prefix)]
            stderr = io.StringIO()
            with ExitStack() as stack:
                stack.enter_context(patch.object(RUNNER, "HERE", fixture))
                stack.enter_context(patch.object(sys, "argv", argv))
                stack.enter_context(patch.object(RUNNER.platform, "system", return_value="Linux"))
                stack.enter_context(patch.object(RUNNER.platform, "machine", return_value="x86_64"))
                stack.enter_context(redirect_stderr(stderr))
                trapped = {}
                for owner, name in ((RUNNER.os, "umask"), (Path, "mkdir"),
                                    (RUNNER.shutil, "copyfile"), (RUNNER.shutil, "copytree"),
                                    (RUNNER.subprocess, "run"), (RUNNER, "record_command")):
                    trapped[name] = stack.enter_context(patch.object(
                        owner, name, side_effect=AssertionError("pre-refusal effect attempted: " + name)))
                with self.assertRaises(SystemExit) as refusal:
                    RUNNER.main()
                self.assertEqual(refusal.exception.code, 2)
                self.assertIn(REFUSAL, stderr.getvalue())
                for effect in trapped.values():
                    effect.assert_not_called()
            self.assertFalse(run.exists())


class ArchivePolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="wsl-retrieval-archive-policy-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        repository = ROOT.parents[2]
        record = json.loads((repository / ARCHIVE.RECORD).read_text())
        files = {artifact["path"] for _, artifact in ARCHIVE.artifact_pairs(record)}
        files.update({ARCHIVE.RECORD, ARCHIVE.POLICY, ARCHIVE.SNAPSHOT, ARCHIVE.CONFIG,
                      ".github/osv-scanner.toml", ".github/osv-scanner-lockfiles.json",
                      ".github/workflows/security-scan.yml"})
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((repository / name).read_bytes())
        self.now = datetime(2026, 10, 4, tzinfo=timezone.utc)

    def result(self):
        return ARCHIVE.validate_archive(self.root, self.now)

    def mutate_json(self, name, change):
        path = self.root / name
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value) + "\n")

    def assert_invalid(self, fragment):
        result = self.result()
        self.assertFalse(result["valid"], result)
        self.assertIn(fragment, "\n".join(result["errors"]))

    def test_production_preflight_verifies_snapshot_guard_and_all_historical_pairs(self):
        result = self.result()
        self.assertTrue(result["valid"], result)
        self.assertGreater(result["archival_binding"]["historical_artifact_pairs_checked"], 10)
        self.assertEqual(result["archival_binding"]["declared_sha256"], ARCHIVE.ORIGINAL_SHA)
        self.assertEqual(result["archival_binding"]["current_guard_sha256"], ARCHIVE.GUARDED_SHA)

    def test_original_experiment_stays_byte_exact_and_mapping_is_reported(self):
        before = (self.root / ARCHIVE.RECORD).read_bytes()
        result = validate_record(self.root, ARCHIVE.RECORD)
        self.assertTrue(result["valid"], result)
        self.assertEqual(len(result["archival_bindings"]), 1)
        self.assertEqual((self.root / ARCHIVE.RECORD).read_bytes(), before)

    def test_registry_cannot_change_scope_pointer_digest_or_activation(self):
        original = (self.root / ARCHIVE.POLICY).read_bytes()
        mutations = [lambda p: p.update(pointer="/frozen_inputs/evaluation/0"),
                     lambda p: p.update(activation_allowed=True),
                     lambda p: p.update(automatic_renewal=True),
                     lambda p: p.update(extra_mapping={}),
                     lambda p: p["record"].update(sha256="0" * 64),
                     lambda p: p["snapshot"].update(path="../escape"),
                     lambda p: p.update(expires_utc="2027-01-02T00:00:00Z")]
        for change in mutations:
            with self.subTest(change=change):
                (self.root / ARCHIVE.POLICY).write_bytes(original)
                self.mutate_json(ARCHIVE.POLICY, change)
                self.assert_invalid("exact versioned scope")

    def test_expiry_and_future_issue_fail_closed(self):
        for now in [datetime(2026, 10, 2, tzinfo=timezone.utc),
                    datetime(2026, 11, 2, tzinfo=timezone.utc),
                    datetime(2026, 12, 1, tzinfo=timezone.utc)]:
            with self.subTest(now=now):
                self.assertFalse(ARCHIVE.validate_archive(self.root, now)["valid"])

    def test_snapshot_guard_lock_receipt_and_workflow_drift_fail(self):
        for name in [ARCHIVE.SNAPSHOT, ARCHIVE.RUNNER, ARCHIVE.LOCK,
                     ARCHIVE.LEAF + "qmd-receipt.json", ".github/workflows/security-scan.yml"]:
            with self.subTest(name=name):
                path = self.root / name
                before = path.read_bytes()
                path.write_bytes(before + b"\n")
                self.assertFalse(self.result()["valid"])
                path.write_bytes(before)

    def test_guard_removal_cannot_be_reapproved_by_only_rewriting_policy_hash(self):
        runner = self.root / ARCHIVE.RUNNER
        runner.write_text(runner.read_text().replace("    if args.mode == 'qmd':\n        parser.error('archived_qmd_activation_denied')\n", ""))
        self.mutate_json(ARCHIVE.POLICY, lambda p: p["guarded_runner"].update(sha256=digest(runner)))
        self.assert_invalid("exact versioned scope")

    def assert_recorder_refuses_before_effects(self, mode, fragment):
        path = self.root / ARCHIVE.RUNNER
        spec = importlib.util.spec_from_file_location("wsl_archive_mutant_recorder", path)
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        argv = [str(path), "--mode", mode, "--run-dir", str(self.root / "private-run"),
                "--node", str(self.root / "owned-node"), "--package-prefix", str(self.root / "owned-prefix"),
                "--source", str(self.root / ARCHIVE.LEAF / "seed/planner.py"),
                "--rg", str(self.root / "owned-rg"), "--ast-grep", str(self.root / "owned-ast-grep")]
        stderr = io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(redirect_stderr(stderr))
            stack.enter_context(patch.object(runner.platform, "system", return_value="Linux"))
            stack.enter_context(patch.object(runner.platform, "machine", return_value="x86_64"))
            effects = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError(name)))
                       for owner, name in ((runner.os, "umask"), (Path, "mkdir"),
                                           (runner.shutil, "copyfile"), (runner.shutil, "copytree"),
                                           (runner.subprocess, "run"), (runner, "record_command"))]
            with self.assertRaises(SystemExit) as refused:
                runner.main()
            self.assertEqual(refused.exception.code, 2)
            self.assertIn(fragment, stderr.getvalue())
            for effect in effects:
                effect.assert_not_called()

    def test_actual_guard_removed_recorder_still_refuses_before_effects(self):
        path = self.root / ARCHIVE.RUNNER
        path.write_text(path.read_text().replace(
            "    if args.mode == 'qmd':\n        parser.error('archived_qmd_activation_denied')\n", ""))
        self.assert_recorder_refuses_before_effects("qmd", "archive guard: reviewed bytes changed")

    def test_actual_source_recorder_refuses_missing_changed_metadata_and_lock_drift(self):
        for name, mutation, fragment in [
                (ARCHIVE.POLICY, lambda p: p.unlink(), "file missing"),
                (ARCHIVE.POLICY, lambda p: self.mutate_json(ARCHIVE.POLICY, lambda v: v.update(activation_allowed=True)),
                 "exact versioned scope"),
                (ARCHIVE.LOCK, lambda p: p.write_bytes(p.read_bytes() + b"\n"), "original bytes changed")]:
            with self.subTest(name=name, fragment=fragment):
                path = self.root / name
                before = path.read_bytes()
                try:
                    mutation(path)
                    self.assert_recorder_refuses_before_effects("source", fragment)
                finally:
                    path.write_bytes(before)

    def test_actual_source_recorder_refuses_expired_policy_before_effects(self):
        class ExpiredClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 2, tzinfo=timezone.utc)

        with patch.object(ARCHIVE, "datetime", ExpiredClock):
            self.assert_recorder_refuses_before_effects("source", "not active or expired")

    def test_missing_policy_and_snapshot_fail_closed(self):
        for name in [ARCHIVE.POLICY, ARCHIVE.SNAPSHOT]:
            with self.subTest(name=name):
                path = self.root / name
                before = path.read_bytes()
                path.unlink()
                self.assertFalse(self.result()["valid"])
                path.write_bytes(before)

    def test_symlink_snapshot_and_declared_runner_are_refused(self):
        for name in [ARCHIVE.SNAPSHOT, ARCHIVE.RUNNER]:
            with self.subTest(name=name):
                path = self.root / name
                target = self.root / "saved-source.txt"
                before = path.read_bytes()
                target.write_bytes(before)
                path.unlink()
                path.symlink_to(target)
                self.assert_invalid("symlinks")
                path.unlink()
                path.write_bytes(before)

    def test_record_change_and_unrelated_record_do_not_receive_a_fallback(self):
        original = (self.root / ARCHIVE.RECORD).read_bytes()
        (self.root / ARCHIVE.RECORD).write_bytes(original + b"\n")
        self.assertFalse(validate_record(self.root, ARCHIVE.RECORD)["valid"])
        other = self.root / "unrelated-record.json"
        other.write_bytes(original)
        result = validate_record(self.root, "unrelated-record.json")
        self.assertFalse(result["valid"])
        self.assertIn("SHA-256 mismatch", "\n".join(result["errors"]))
        self.assertNotIn("archival_bindings", result)

    def test_mapping_cannot_resolve_another_pointer_or_declared_pair(self):
        for pointer, artifact in [("/frozen_inputs/evaluation/0", {"path": ARCHIVE.RUNNER, "sha256": ARCHIVE.ORIGINAL_SHA}),
                                  (ARCHIVE.POINTER, {"path": ARCHIVE.RUNNER, "sha256": "0" * 64})]:
            with self.subTest(pointer=pointer), self.assertRaisesRegex(ValueError, "exact original"):
                ARCHIVE.resolve_evaluation(self.root, ARCHIVE.RECORD, ARCHIVE.RECORD_SHA, pointer, artifact)

    def test_unrelated_lock_cannot_share_the_scoped_exception(self):
        self.mutate_json(".github/osv-scanner-lockfiles.json", lambda p: p["lockfiles"].append(
            {"path": "unrelated/package-lock.json", "config": ARCHIVE.CONFIG}))
        self.assert_invalid("exact single lock scope")

    def test_ordinary_ignore_and_expiry_timezone_tail_are_refused(self):
        ordinary = self.root / ".github/osv-scanner.toml"
        ordinary.write_text(ordinary.read_text() + '\n[[IgnoredVulns]]\nid = "' + ARCHIVE.ADVISORY + '"\n')
        self.assert_invalid("ordinary advisory suppression")
        ordinary.write_bytes((ROOT.parents[2] / ".github/osv-scanner.toml").read_bytes())
        config = self.root / ARCHIVE.CONFIG
        config.write_text(config.read_text().replace("2026-11-02T00:00:00Z", "2026-11-02"))
        self.assert_invalid("expiry mismatch")

    def test_workflow_preflight_failure_stops_before_any_scanner(self):
        text = (self.root / ".github/workflows/security-scan.yml").read_text()
        first = text.index("          set +e -u -o pipefail")
        last = text.index('          exit "$status"', first) + len('          exit "$status"')
        script = "\n".join(line[10:] for line in text[first:last].splitlines())
        binaries = self.root / "preflight-bin"
        binaries.mkdir()
        fake_python = binaries / "python3"
        fake_python.write_text("#!/bin/sh\nexit 17\n")
        fake_python.chmod(0o700)
        marker = self.root / "scanner-started"
        scanner = self.root / "osv-scanner" / "osv-scanner"
        scanner.parent.mkdir()
        scanner.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\nexit 0\n')
        scanner.chmod(0o700)
        result = subprocess.run(["/bin/bash", "-c", script], cwd=self.root,
                                env={"PATH": str(binaries), "RUNNER_TEMP": str(self.root), "WRITE_SARIF": "false"},
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertFalse(marker.exists(), "scanner ran despite failed production preflight")

    def test_workflow_keeps_all_sarif_and_worst_table_or_sarif_status(self):
        # Execute the actual workflow shell with synthetic commands only.
        text = (self.root / ".github/workflows/security-scan.yml").read_text()
        first = text.index("          set +e -u -o pipefail")
        last = text.index('          exit "$status"', first) + len('          exit "$status"')
        script = "\n".join(line[10:] for line in text[first:last].splitlines())
        # macOS ships Bash 3; the Linux runner's mapfile builtin only gathers
        # the three synthetic input arrays here. Do not alter production shell.
        script = """if ! type mapfile >/dev/null 2>&1; then
          mapfile() {
            local target="$2" item
            case "$target" in lockfiles) lockfiles=();; frozen) frozen=();; wsl) wsl=();; *) return 2;; esac
            while IFS= read -r item; do
              case "$target" in lockfiles) lockfiles+=("$item");; frozen) frozen+=("$item");; wsl) wsl+=("$item");; esac
            done
          }
        fi
        """ + script
        binaries = self.root / "status-bin"
        binaries.mkdir()
        fake_python = binaries / "python3"
        fake_python.write_text("#!/bin/sh\nexit 0\n")
        fake_python.chmod(0o700)
        jq = binaries / "jq"
        jq.write_text("#!" + sys.executable + "\nimport sys\n"
                      "args=sys.argv[1:]\n"
                      "if args[0] != '-r': print(3)\n"
                      "elif '--arg' not in args: print('--lockfile=:ordinary/package-lock.json')\n"
                      "elif 'macos' in args[args.index('--arg')+2]: print('--lockfile=:macos/pnpm-lock.yaml')\n"
                      "else: print('--lockfile=:blueprints/convergence-practice/wsl-retrieval/package-lock.json')\n")
        jq.chmod(0o700)
        calls = self.root / "scanner-calls.jsonl"
        scanner = self.root / "osv-scanner/osv-scanner"
        scanner.parent.mkdir()
        scanner.write_text("#!" + sys.executable + "\nimport json,os,sys\nfrom pathlib import Path\n"
                           "calls=Path(os.environ['SYNTHETIC_CALLS'])\n"
                           "index=len(calls.read_text().splitlines()) if calls.exists() else 0\n"
                           "with calls.open('a') as handle: handle.write(json.dumps(sys.argv[1:])+'\\n')\n"
                           "if '--output-file' in sys.argv:\n"
                           " Path(sys.argv[sys.argv.index('--output-file')+1]).write_text('{}\\n')\n"
                           "raise SystemExit(int(os.environ['SYNTHETIC_STATUSES'].split(',')[index]))\n")
        scanner.chmod(0o700)
        for statuses, expected in [([3, 0, 0, 2, 4, 1], 4), ([0, 1, 0, 0, 0, 0], 1),
                                   ([0, 0, 0, 0, 0, 1], 1), ([1, 5, 2, 0, 0, 0], 5)]:
            with self.subTest(statuses=statuses):
                calls.unlink(missing_ok=True)
                result = subprocess.run(["/bin/bash", "-c", script], cwd=self.root,
                                        env={"PATH": str(binaries), "RUNNER_TEMP": str(self.root), "WRITE_SARIF": "true",
                                             "SYNTHETIC_CALLS": str(calls),
                                             "SYNTHETIC_STATUSES": ",".join(map(str, statuses))},
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, expected, result.stderr)
                invocations = [json.loads(line) for line in calls.read_text().splitlines()]
                self.assertEqual(len(invocations), 6)
                self.assertEqual(len([args for args in invocations if '--format' in args]), 3)
                for name in ["osv-scanner.sarif", "osv-scanner-frozen-macos.sarif",
                             "osv-scanner-frozen-wsl-retrieval.sarif"]:
                    self.assertTrue((scanner.parent / name).is_file(), name)


if __name__ == "__main__":
    unittest.main()
