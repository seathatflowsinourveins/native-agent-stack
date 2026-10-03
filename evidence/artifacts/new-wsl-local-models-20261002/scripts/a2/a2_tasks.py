#!/usr/bin/env python3
"""The five fixed repository tasks of A2's client part (PREREGISTRATION-local-models.md, Part A2 and amendment 3b),
plus one unscored pilot task. `make <task> <dir>` writes the task's starting repository; `prompt <task>` prints its
fixed prompt; `check <task> <dir>` applies its fixed file check and prints one JSON line. The same files, prompts and
checks are used for every arm and both clients."""
import json
import pathlib
import subprocess
import sys

CONFIG = "[service]\nname = alpha\nmode = draft\nport = 8080\n"
SPEC = ("# Storage service\n\nThe service accepts uploads of up to 20 megabytes.\n"
        "Records are kept for 45 days before deletion.\nBackups run every 6 hours.\n")
PACKAGE = {"name": "sample", "version": "0.0.0", "private": True}
TASKS = {
    "P0": {"prompt": "Create the file pilot.txt in this repository. It must contain exactly one line: pilot", "files": {}},
    "T1": {"prompt": "Create the file notes/hello.txt in this repository. It must contain exactly one line: measurement ready",
           "files": {"README.md": "# Scratch repository\n"}},
    "T2": {"prompt": "In config.ini, change the value of mode from draft to final. Change nothing else.",
           "files": {"config.ini": CONFIG}},
    "T3": {"prompt": "Run tools/count.sh and write its output, and nothing else, into the file result.txt.",
           "files": {"tools/count.sh": "#!/bin/sh\nls data | wc -l | tr -d ' '\n",
                     **{f"data/item-{n}.txt": f"item {n}\n" for n in range(1, 8)}}},
    "T4": {"prompt": "Read docs/spec.md. Write the number of days that records are kept, digits only, into the file answer.txt.",
           "files": {"docs/spec.md": SPEC}},
    "T5": {"prompt": "Run tools/version.sh. Set the version field in package.json to exactly the value it prints. Change nothing else.",
           "files": {"tools/version.sh": "#!/bin/sh\necho 3.4.1\n", "package.json": json.dumps(PACKAGE, indent=2) + "\n"}},
}


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def check(task, root):
    if task == "P0":
        text = read(root / "pilot.txt")
        return text is not None and text.strip() == "pilot" and len(text.strip().splitlines()) == 1
    if task == "T1":
        text = read(root / "notes/hello.txt")
        return text is not None and text.strip() == "measurement ready" and len(text.strip().splitlines()) == 1
    if task == "T2":
        text = read(root / "config.ini")
        return text is not None and text.rstrip("\n") == CONFIG.replace("mode = draft", "mode = final").rstrip("\n")
    if task == "T3":
        text = read(root / "result.txt")
        return text is not None and text.strip() == "7"
    if task == "T4":
        text = read(root / "answer.txt")
        return text is not None and text.strip() == "45"
    if task == "T5":
        text = read(root / "package.json")
        try:
            data = json.loads(text) if text is not None else None
        except json.JSONDecodeError:
            return False
        return data == {**PACKAGE, "version": "3.4.1"}
    raise SystemExit(f"unknown task {task}")


def make(task, root):
    root.mkdir(parents=True, exist_ok=False)
    for name, text in TASKS[task]["files"].items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if name.endswith(".sh"):
            path.chmod(0o755)
    git = ["git", "-C", str(root), "-c", "user.name=measure", "-c", "user.email=<fixture address at example.invalid>"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "start"], check=True)


command, task = sys.argv[1], sys.argv[2]
if command == "prompt":
    print(TASKS[task]["prompt"])
elif command == "make":
    make(task, pathlib.Path(sys.argv[3]))
elif command == "check":
    print(json.dumps({"task": task, "pass": bool(check(task, pathlib.Path(sys.argv[3])))}))
else:
    raise SystemExit("usage: a2_tasks.py make|prompt|check <task> [<dir>]")
