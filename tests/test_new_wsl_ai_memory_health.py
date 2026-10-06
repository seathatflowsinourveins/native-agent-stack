"""Execute the canonical health recipe with synthetic native status output."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"


class AiMemoryHealthBindingTests(unittest.TestCase):
    @staticmethod
    def command():
        spec = importlib.util.spec_from_file_location("health_plan_checker", PLAN / "check_plan.py")
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        body = checker.functions((PLAN / "accept.sh").read_text())["memory-owner"]
        command, = [command for stage, kind, source, command in checker.checks_of(body)
                    if stage == "service_health"]
        return command

    def run_recipe(self, *, bare=False, reported_url=None, exit_code=0):
        command = self.command()
        if bare:
            command = command.replace("AI_MEMORY_SERVER_URL=http://127.0.0.1:29374 ", "")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capture = root / "calls.jsonl"
            (root / "curl").write_text("#!/bin/sh\nexit 0\n")
            (root / "ai-memory").write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,sys\n"
                "url=os.environ.get('AI_MEMORY_SERVER_URL','http://127.0.0.1:49374')\n"
                "with open(os.environ['FIXTURE_CALLS'],'a') as f: f.write(json.dumps({'argv':sys.argv[1:],'url':url})+'\\n')\n"
                "if url!='http://127.0.0.1:29374': sys.exit(1)\n"
                "print(json.dumps({'client':{'server_url':os.environ.get('FIXTURE_REPORTED_URL',url)}}))\n"
                "sys.exit(int(os.environ['FIXTURE_EXIT']))\n")
            for path in root.iterdir():
                path.chmod(0o755)
            env = {"PATH": str(root) + ":" + os.environ["PATH"], "HOME": os.environ["HOME"],
                   "AI_MEMORY_SERVER_URL": "http://127.0.0.1:49374", "FIXTURE_CALLS": str(capture),
                   "FIXTURE_EXIT": str(exit_code), "PYTHONDONTWRITEBYTECODE": "1"}
            if reported_url:
                env["FIXTURE_REPORTED_URL"] = reported_url
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", command], env=env,
                                    capture_output=True, text=True, timeout=10)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
        return result, calls

    def test_existing_plan_binding_overrides_a_synthetic_old_default(self):
        result, calls = self.run_recipe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [{"argv": ["status", "--json"], "url": "http://127.0.0.1:29374"}])

    def test_bare_wrong_target_and_failed_status_do_not_pass(self):
        for kwargs in ({"bare": True}, {"exit_code": 17}):
            with self.subTest(kwargs=kwargs):
                result, calls = self.run_recipe(**kwargs)
                self.assertNotEqual(result.returncode, 0)

    def test_successful_status_reporting_the_wrong_endpoint_is_rejected(self):
        result, calls = self.run_recipe(reported_url="http://127.0.0.1:49374")
        self.assertNotEqual(result.returncode, 0, "wrong native status target passed")


if __name__ == "__main__":
    unittest.main()
