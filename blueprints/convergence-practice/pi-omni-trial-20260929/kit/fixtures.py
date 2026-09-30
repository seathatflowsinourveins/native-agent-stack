#!/usr/bin/env python3
"""Frozen S2 task fixtures for the pi trial: synthetic local fixtures, not an upstream benchmark.

    fixtures.py make TASK DEST        create the task workspace (a git repo with one deterministic commit)
    fixtures.py instruction TASK      print the task instruction
    fixtures.py check TASK DEST       print JSON {passed, detail}; exit 0 when the task check passes
    fixtures.py manifest              print the sha256 of this file, each instruction and each initial tree
    fixtures.py selftest              known-fail, known-pass, tamper and malformed controls for every task

Content depends only on this file (seeded generator, fixed commit identity and dates), so the commit id printed
by `manifest` freezes each task. The checks read tracked files and answer.txt only, so tool side effects such as
a .serena directory do not change a verdict.
"""
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = ["calc-sign-bug", "log-triage", "multi-file-rename", "wiring-smoke"]
IDENTITY = {"GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2026-09-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-09-01T00:00:00Z"}

INSTRUCTIONS = {
    "calc-sign-bug": "The unit tests in this directory fail. Find and fix the bug in calc.py so that "
                     "`python3 -m unittest -q` passes. Do not modify test_calc.py.",
    "log-triage": "service.log is a large application log. Find the id of the single request that ended with "
                  "status=failed and error=TimeoutError after more than 3 retries, and write only that request id "
                  "(for example req-123456) followed by a newline to answer.txt. Do not modify service.log.",
    "wiring-smoke": "Do these steps in order. 1) Use the bash tool to run `git status --short`. 2) Call the ctx_stats tool once. "
                    "3) Use tool_search to find the tool that reports the status of the qmd document index, then call that tool once. "
                    "4) Use the bash tool to run `echo done > answer.txt`. Then reply with the single word OK.",
    "multi-file-rename": "Rename the function `fetch_user` to `load_user` everywhere in this repository: its definition, "
                         "every call, import and mock.patch target in the tests, and the README. Behaviour must not "
                         "change and all tests must pass (`python3 -m unittest discover -q`).",
}

CALC = "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n"
CALC_TEST = (
    "import unittest\n\nfrom calc import add, mul\n\n\nclass CalcTests(unittest.TestCase):\n"
    "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n        self.assertEqual(add(-1, 1), 0)\n\n"
    "    def test_mul(self):\n        self.assertEqual(mul(4, 5), 20)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n")

MODULES = {
    "orders": "from shop.users import fetch_user\n\n\ndef order_owner(order):\n    return fetch_user(order[\"user_id\"])[\"name\"]\n",
    "billing": "from shop.users import fetch_user\n\n\ndef invoice_name(invoice):\n    user = fetch_user(invoice[\"user_id\"])\n    return user[\"name\"].upper()\n",
    "notify": "from shop import users\n\n\ndef email_for(user_id):\n    return users.fetch_user(user_id)[\"email\"]\n",
    "reports": "from shop.users import fetch_user\n\n\ndef names(ids):\n    return [fetch_user(i)[\"name\"] for i in ids]\n",
    "api": "from shop.users import fetch_user\n\n\ndef get_user(user_id):\n    user = fetch_user(user_id)\n    return {\"id\": user_id, \"name\": user[\"name\"]}\n",
}
USERS = ("USERS = {1: {\"name\": \"ada\", \"email\": \"ada@example.invalid\"}, 2: {\"name\": \"grace\", \"email\": \"grace@example.invalid\"}}\n\n\n"
         "def fetch_user(user_id):\n    return USERS[user_id]\n")
SHOP_TESTS = {
    "test_orders": "import unittest\nfrom unittest import mock\n\nfrom shop.orders import order_owner\n\n\nclass OrderTests(unittest.TestCase):\n"
                   "    def test_owner(self):\n        self.assertEqual(order_owner({\"user_id\": 1}), \"ada\")\n\n"
                   "    def test_owner_mocked(self):\n        with mock.patch(\"shop.orders.fetch_user\", return_value={\"name\": \"x\"}):\n"
                   "            self.assertEqual(order_owner({\"user_id\": 9}), \"x\")\n",
    "test_billing": "import unittest\nfrom unittest import mock\n\nfrom shop.billing import invoice_name\n\n\nclass BillingTests(unittest.TestCase):\n"
                    "    def test_name(self):\n        self.assertEqual(invoice_name({\"user_id\": 2}), \"GRACE\")\n\n"
                    "    def test_name_mocked(self):\n        with mock.patch(\"shop.billing.fetch_user\", return_value={\"name\": \"y\"}):\n"
                    "            self.assertEqual(invoice_name({\"user_id\": 9}), \"Y\")\n",
    "test_api": "import unittest\n\nfrom shop.api import get_user\nfrom shop.notify import email_for\nfrom shop.reports import names\n\n\nclass ApiTests(unittest.TestCase):\n"
                "    def test_get_user(self):\n        self.assertEqual(get_user(1), {\"id\": 1, \"name\": \"ada\"})\n\n"
                "    def test_email(self):\n        self.assertEqual(email_for(2), \"grace@example.invalid\")\n\n"
                "    def test_names(self):\n        self.assertEqual(names([1, 2]), [\"ada\", \"grace\"])\n",
}
README = "# shop\n\nA tiny fixture package. `fetch_user(user_id)` in `shop/users.py` returns the user record; every module calls it.\n"


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def log_lines():
    rng = random.Random(20260929)
    used, events = [], []

    def new_id():
        while True:
            value = "req-%06d" % rng.randrange(100000, 999999)
            if value not in used:
                used.append(value)
                return value

    target = new_id()
    special = {target: ("failed", "TimeoutError", 5), new_id(): ("failed", "TimeoutError", 2),
               new_id(): ("failed", "ConnectionReset", 6), new_id(): ("ok", "", 5)}
    ids = list(special) + [new_id() for _ in range(2200)]
    handlers = ["checkout", "search", "profile", "upload", "sync"]
    for rid in ids:
        start = rng.randrange(0, 86000)
        handler = rng.choice(handlers)
        status, error, retries = special.get(rid, ("ok", "", rng.choice([0, 0, 0, 1, 2])))
        if rid not in special and rng.random() < 0.03:
            status, error, retries = "failed", rng.choice(["ValueError", "KeyError"]), 0
        events.append((start, "INFO", rid, f"start handler={handler}"))
        for attempt in range(1, retries + 1):
            events.append((start + attempt, "WARN", rid, f"retry attempt={attempt} reason=timeout"))
        end = start + retries + 2
        if status == "ok":
            events.append((end, "INFO", rid, f"done status=ok retries={retries} ms={rng.randrange(20, 900)}"))
        else:
            events.append((end, "ERROR", rid, f"done status=failed error={error} retries={retries}"))
    events.sort(key=lambda e: (e[0], e[2], e[3]))
    lines = ["2026-09-01T%02d:%02d:%02dZ %s %s %s" % (t // 3600, t % 3600 // 60, t % 60, lvl, rid, msg)
             for t, lvl, rid, msg in events]
    return lines, target


def files_for(task):
    if task == "calc-sign-bug":
        return {"calc.py": CALC, "test_calc.py": CALC_TEST}
    if task == "log-triage":
        lines, _ = log_lines()
        return {"service.log": "\n".join(lines) + "\n"}
    if task == "wiring-smoke":
        return {"note.txt": "alpha\n"}
    files = {"README.md": README, "shop/__init__.py": "", "shop/users.py": USERS, "tests/__init__.py": ""}
    files.update({f"shop/{name}.py": text for name, text in MODULES.items()})
    files.update({f"tests/{name}.py": text for name, text in SHOP_TESTS.items()})
    return files


def git(dest, *args, env=None):
    return subprocess.run(["git", *args], cwd=dest, capture_output=True, text=True, env={**os.environ, **(env or {})})


def make(task, dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for name, text in files_for(task).items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", f"fixture {task}", env=IDENTITY)
    return git(dest, "rev-parse", "HEAD").stdout.strip()


def unittest_ok(dest):
    # A one-character edit such as `a - b` -> `a + b` keeps the file size, and a same-second rewrite reuses a stale
    # .pyc (mtime has one-second resolution), so the verdict must not depend on bytecode.
    for cache in Path(dest).rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-q"] if (Path(dest) / "shop").exists()
                            else [sys.executable, "-m", "unittest", "-q"],
                            cwd=dest, capture_output=True, text=True, timeout=120,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    return result.returncode == 0, (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]


def frozen(dest, path):
    return git(dest, "show", f"HEAD:{path}").stdout


def tracked_changes(dest):
    return [line for line in git(dest, "diff", "--name-only", "HEAD").stdout.splitlines() if line]


def check(task, dest):
    dest = Path(dest)
    try:
        if task == "calc-sign-bug":
            passed, tail = unittest_ok(dest)
            tests_intact = (dest / "test_calc.py").read_text() == CALC_TEST
            extra = [f for f in tracked_changes(dest) if f != "calc.py"]
            return {"passed": bool(passed and tests_intact and not extra),
                    "detail": {"unittest": passed, "tests_intact": tests_intact, "other_tracked_changes": extra, "tail": tail}}
        if task == "log-triage":
            _, target = log_lines()
            answer = dest / "answer.txt"
            given = answer.read_text().strip() if answer.exists() else None
            log_intact = (dest / "service.log").read_text() == frozen(dest, "service.log")
            return {"passed": bool(given == target and log_intact and answer.read_text().endswith("\n")),
                    "detail": {"answer_present": given is not None, "answer_matches": given == target, "log_intact": log_intact}}
        if task == "wiring-smoke":
            answer = dest / "answer.txt"
            given = answer.read_text() if answer.exists() else None
            extra = tracked_changes(dest)
            return {"passed": bool(given == "done\n" and not extra),
                    "detail": {"answer_present": given is not None, "answer_exact": given == "done\n", "tracked_changes": extra}}
        if task == "multi-file-rename":
            passed, tail = unittest_ok(dest)
            tracked = git(dest, "ls-files").stdout.split()
            old = new = 0
            for name in tracked:
                text = (dest / name).read_text() if (dest / name).exists() else ""
                old += len(re.findall(r"\bfetch_user\b", text))
                new += len(re.findall(r"\bload_user\b", text))
            original = sum(len(re.findall(r"\bfetch_user\b", frozen(dest, n))) for n in tracked)
            tests_before = sum(frozen(dest, n).count("def test_") for n in tracked if n.startswith("tests/"))
            tests_now = sum((dest / n).read_text().count("def test_") for n in tracked if n.startswith("tests/") and (dest / n).exists())
            return {"passed": bool(passed and old == 0 and new == original and tests_now == tests_before),
                    "detail": {"unittest": passed, "old_left": old, "new": new, "expected_new": original,
                               "tests_before": tests_before, "tests_now": tests_now, "tail": tail}}
    except Exception as error:
        return {"passed": False, "detail": {"check_error": repr(error)[:200]}}
    raise SystemExit("unknown task " + task)


def solve(task, dest):
    """Reference solutions, used only by selftest as known-pass controls."""
    dest = Path(dest)
    if task == "calc-sign-bug":
        (dest / "calc.py").write_text(CALC.replace("a - b", "a + b"))
    elif task == "log-triage":
        (dest / "answer.txt").write_text(log_lines()[1] + "\n")
    elif task == "wiring-smoke":
        (dest / "answer.txt").write_text("done\n")
    else:
        for name in git(dest, "ls-files").stdout.split():
            path = dest / name
            path.write_text(re.sub(r"\bfetch_user\b", "load_user", path.read_text()))


def selftest():
    bad = 0

    def report(ok, text):
        nonlocal bad
        bad += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + text)

    for task in TASKS:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "ws"
            make(task, dest)
            report(not check(task, dest)["passed"], f"{task}: known-fail control (untouched fixture fails)")
            solve(task, dest)
            report(check(task, dest)["passed"], f"{task}: known-pass control (reference solution passes)")
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "ws"
            make(task, dest)
            if task == "calc-sign-bug":
                (dest / "test_calc.py").write_text(CALC_TEST.replace("add(2, 3), 5", "add(2, 3), -1"))
                (dest / "calc.py").write_text(CALC)
                report(not check(task, dest)["passed"], f"{task}: tamper control (edited test file fails)")
                (dest / "calc.py").unlink()
                report(not check(task, dest)["passed"], f"{task}: malformed control (calc.py missing fails cleanly)")
            elif task == "log-triage":
                (dest / "answer.txt").write_text(log_lines()[1] + "\n")
                (dest / "service.log").write_text("tampered\n")
                report(not check(task, dest)["passed"], f"{task}: tamper control (edited log fails)")
                make_bad = Path(tmp) / "ws2"
                make(task, make_bad)
                (make_bad / "answer.txt").write_text("req-000001\n")
                report(not check(task, make_bad)["passed"], f"{task}: malformed control (wrong id fails)")
            elif task == "wiring-smoke":
                (dest / "answer.txt").write_text("done\n")
                (dest / "note.txt").write_text("changed\n")
                report(not check(task, dest)["passed"], f"{task}: tamper control (edited tracked file fails)")
                (dest / "note.txt").write_text("alpha\n")
                (dest / "answer.txt").write_text("Done\n")
                report(not check(task, dest)["passed"], f"{task}: malformed control (wrong answer text fails)")
            else:
                text = (dest / "shop/users.py").read_text().replace("fetch_user", "load_user")
                (dest / "shop/users.py").write_text(text)
                report(not check(task, dest)["passed"], f"{task}: partial-rename control (definition only fails)")
                subprocess.run(["git", "checkout", "-q", "--", "."], cwd=dest)
                solve(task, dest)
                (dest / "tests/test_api.py").write_text("import unittest\n")
                report(not check(task, dest)["passed"], f"{task}: tamper control (deleted tests fail)")
    print("result:", "FAIL" if bad else "ok", f"({bad} failed checks)")
    return 1 if bad else 0


def manifest():
    out = {"fixtures_py_sha256": sha(Path(__file__).read_bytes()), "tasks": {}}
    for task in TASKS:
        with tempfile.TemporaryDirectory() as tmp:
            head = make(task, Path(tmp) / "ws")
        files = files_for(task)
        out["tasks"][task] = {"instruction_sha256": sha(INSTRUCTIONS[task]), "fixture_commit": head,
                              "files": {name: sha(text) for name, text in sorted(files.items())}}
    return out


def main():
    args = sys.argv[1:]
    if args[:1] == ["make"] and len(args) == 3:
        print(make(args[1], args[2]))
    elif args[:1] == ["instruction"] and len(args) == 2:
        print(INSTRUCTIONS[args[1]])
    elif args[:1] == ["check"] and len(args) == 3:
        result = check(args[1], args[2])
        print(json.dumps(result))
        sys.exit(0 if result["passed"] else 1)
    elif args[:1] == ["manifest"]:
        print(json.dumps(manifest(), indent=2))
    elif args[:1] == ["selftest"]:
        sys.exit(selftest())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
