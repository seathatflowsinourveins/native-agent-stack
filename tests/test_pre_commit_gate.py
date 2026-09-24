"""Tracked pre-commit secret gate (scripts/git-hooks/pre-commit).

Local integration class: a temporary repository, a synthetic AWS-shaped key
generated at test time (never a committed literal), and the gitleaks binary
already on PATH. Skips when gitleaks is absent; the fail-closed case runs
without it.
"""

from pathlib import Path
import os
import secrets
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "scripts/git-hooks"


def synthetic_key() -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    return "AKIA" + "".join(secrets.choice(alphabet) for _ in range(16))


class PreCommitGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.git("init", "-q")
        self.git("config", "core.hooksPath", str(HOOKS))
        shutil.copy(ROOT / ".gitleaks.toml", self.repo / ".gitleaks.toml")

    def git(self, *args, env=None):
        return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                              cwd=self.repo, capture_output=True, text=True, env=env, timeout=120)

    def commit(self, name, text, env=None):
        (self.repo / name).write_text(text)
        self.git("add", name)
        return self.git("commit", "-q", "-m", name, env=env)

    def test_hook_is_executable(self):
        self.assertTrue(os.access(HOOKS / "pre-commit", os.X_OK))

    def test_missing_gitleaks_fails_closed(self):
        git_dir = os.path.dirname(shutil.which("git"))
        env = {**os.environ, "PATH": f"{git_dir}:/usr/bin:/bin"}
        if any(Path(d, "gitleaks").exists() for d in env["PATH"].split(":")):
            self.skipTest("gitleaks shares a directory with git")
        result = self.commit("notes.txt", "clean\n", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gitleaks not on PATH", result.stderr)

    @unittest.skipUnless(shutil.which("gitleaks"), "gitleaks not on PATH")
    def test_blocks_synthetic_key_and_passes_clean_commit(self):
        clean = self.commit("notes.txt", "a clean line\n")
        self.assertEqual(clean.returncode, 0, clean.stderr)
        key = synthetic_key()
        blocked = self.commit("config.ini", f"aws_access_key_id = {key}\n")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("leaks found", blocked.stdout + blocked.stderr)
        self.assertNotIn(key, blocked.stdout + blocked.stderr)
        log = self.git("log", "--oneline")
        self.assertEqual(len(log.stdout.strip().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
