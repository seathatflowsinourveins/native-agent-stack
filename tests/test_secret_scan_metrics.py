"""Execute the shipped scan steps with an inert scanner and native GNU time."""
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/validate.yml"
STEPS = (
    ("gitleaks", "git", "Scan git history for secrets", 10),
    ("gitleaks", "dir", "Scan working tree for secrets", 10),
    ("betterleaks", "git", "Scan git history for secrets with betterleaks (findings do not fail this job)", 20),
    ("betterleaks", "dir", "Scan working tree for secrets with betterleaks (findings do not fail this job)", 20),
)


def script(name):
    lines = WORKFLOW.read_text().splitlines()
    start = lines.index("      - name: " + name)
    begin = next(i for i in range(start + 1, len(lines)) if lines[i] == "        run: |") + 1
    end = next((i for i in range(begin, len(lines)) if lines[i] and not lines[i].startswith("          ")), len(lines))
    return "\n".join(line[10:] for line in lines[begin:end]) + "\n"


@unittest.skipUnless(platform.system() == "Linux" and Path("/usr/bin/time").is_file()
                     and shutil.which("git") and shutil.which("jq"), "native Linux timer/git/jq needed")
class ProductionTimingTests(unittest.TestCase):
    def test_all_four_real_step_scripts_preserve_status_and_record_native_scope(self):
        for scanner, mode, name, budget in STEPS:
            for status in (0, 1, 2):
                with self.subTest(scanner=scanner, mode=mode, status=status), tempfile.TemporaryDirectory() as directory:
                    base = Path(directory)
                    root = base / "repo"
                    root.mkdir()
                    runner = base / "runner"
                    binary = runner / scanner / scanner
                    binary.parent.mkdir(parents=True)
                    binary.write_text("#!/usr/bin/env python3\nimport json,os,sys\n"
                                      "a=sys.argv[1:]\n"
                                      "if '--report-path' in a:\n"
                                      " with open(a[a.index('--report-path')+1],'w') as f:json.dump([],f)\n"
                                      "sys.exit(int(os.environ['FIXTURE_SCAN_STATUS']))\n")
                    binary.chmod(0o755)
                    (root / "scripts").mkdir()
                    metric_script = ROOT / "scripts/secret_scan_metrics.py"
                    if metric_script.exists():
                        shutil.copyfile(metric_script, root / "scripts/secret_scan_metrics.py")
                    (root / ".github/workflows").mkdir(parents=True)
                    shutil.copyfile(WORKFLOW, root / ".github/workflows/validate.yml")
                    (root / ".gitleaks.toml").write_text("title = 'synthetic fixture'\n")
                    (root / ".gitleaksignore").write_text("")
                    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(base),
                           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                           "RUNNER_TEMP": str(runner), "GITHUB_STEP_SUMMARY": str(base / "summary"),
                           "GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/7/merge",
                           "GITHUB_REPOSITORY": "fixture/project", "GITHUB_RUN_ID": "17",
                           "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "secret-scan", "FIXTURE_SCAN_STATUS": str(status)}
                    for args in (("init", "-q"), ("config", "user.name", "Fixture"),
                                 ("config", "user.email", "fixture@example.invalid"),
                                 ("add", "--", ".github", ".gitleaks.toml", ".gitleaksignore"),
                                 ("commit", "-qm", "synthetic scope")):
                        subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)
                    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, env=env, text=True).strip()
                    env["GITHUB_SHA"] = head
                    result = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script(name)],
                                            cwd=root, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, status, "Timed step changed the scanner's exit status")
                    receipt = runner / scanner / f"full-{mode}.metrics.json"
                    self.assertTrue(receipt.is_file(), "Production step did not retain full-scan metrics")
                    record = json.loads(receipt.read_text())
                    self.assertEqual(record["exit_status"], status)
                    self.assertEqual(record["checked_out_commit"], head)
                    self.assertEqual(record["event_name"], "pull_request")
                    self.assertEqual(record["ref"], "refs/pull/7/merge")
                    self.assertEqual(record["history_scope"], "HEAD" if mode == "git" else None)
                    self.assertEqual(record["job_timeout_minutes"], budget)
                    self.assertGreaterEqual(record["elapsed_seconds"], 0)
                    self.assertGreater(record["peak_rss_kib"], 0)
                    self.assertEqual(record["scanner"], scanner)
                    self.assertNotIn(str(base), receipt.read_text())
