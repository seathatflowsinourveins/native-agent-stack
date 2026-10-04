"""Run the whole differential and write counts.json (numbers only).

    python3 run-differential.py --repo <checkout> --old <0c421c66 child-usage.mjs> --pre-ast <f1ed98ac child-usage.mjs> \
        --work <private scratch directory> [--real <real-commands.json> [--real-until <instant>]] [--covering NAME=PATH ...]

--old is the scanner reading the AST reading replaced (`git show 0c421c66:examples/claude-native/workflows/child-usage.mjs`, sha256
acc7bb51...), --pre-ast the kernel before the AST walker (f1ed98ac, sha256 1dcf6ff9...: its M4 helpers are the ones kept). Neither is
committed. --work holds every input, witness and log: it contains command text (the private real-command list and the reduced witnesses
of real commands) and must stay outside every checkout. --real is the output of real-commands.mjs and --covering NAME=PATH (repeatable) of
capture-covering.py; a step that needs a missing input is skipped. Each step is one of the scripts next to this file; the parser (tree-sitter-bash 0.25.1) and
bash must be installed. Steps run in parallel where they are independent.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--old", required=True)
parser.add_argument("--pre-ast", required=True)
parser.add_argument("--work", required=True)
parser.add_argument("--real")
parser.add_argument("--real-until", help="the --until instant real-commands.mjs was run with (recorded in counts.json with the size of the corpus, so the corpus can be rebuilt; see the header of real-commands.mjs when it is reconstructed)")
parser.add_argument("--pre-repair-kernel", help="the kernel before this stage's repairs (2bad7320 child-usage.mjs): the oracle's generators run against it too")
parser.add_argument("--marks-before", help="child-usage.mjs of 11d7e0bd (before the marks collector): with --marks-after, re-runs the executedText/fetchKind identity check of commit 9a4e9f97")
parser.add_argument("--marks-after", help="child-usage.mjs of 9a4e9f97")
parser.add_argument("--covering", nargs="*", default=[], help="NAME=PATH of a list from capture-covering.py (or any list of shell texts)")
args = parser.parse_args()
here = Path(__file__).resolve().parent
repo = Path(args.repo).resolve()
work = Path(args.work).resolve()
work.mkdir(parents=True, exist_ok=True)
kernel = repo / "examples/claude-native/workflows/child-usage.mjs"
new_kernel = str(kernel)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def node(script, *argv):
    done = subprocess.run(["node", str(here / script), *map(str, argv)], capture_output=True, text=True, check=False)
    if done.returncode:
        sys.exit(script + " failed: " + done.stderr[-600:])
    return done.stdout


def last_json(text):
    return json.loads(text.strip().splitlines()[-1])


counts = {"kernels": {"old_sha256": sha(args.old), "pre_ast_sha256": sha(args.pre_ast), "new_sha256": sha(kernel)}}
# The two baselines run from copies beside the pin file, so a baseline that loads the parser (the pre-AST kernel) finds it.
shutil.copy(kernel.parent / "shell-parser.pin.json", work / "shell-parser.pin.json")
shutil.copy(args.old, work / "old-kernel.mjs")
shutil.copy(args.pre_ast, work / "pre-ast-kernel.mjs")
args.old, args.pre_ast = str(work / "old-kernel.mjs"), str(work / "pre-ast-kernel.mjs")
PROFILES = [("soup", 432, 40000), ("heredoc", 434, 20000), ("lanes", 435, 20000)]

# 1. the seeded inputs and their bash -n validity
with ThreadPoolExecutor(len(PROFILES)) as pool:
    made = list(pool.map(lambda p: last_json(node("make-inputs.mjs", p[0], p[1], p[2], work)), PROFILES))
counts["inputs"] = {m["profile"]: m for m in made}

# 2. the differential of each corpus, with minimal witnesses
jobs = {}
for name, seed, _ in PROFILES:
    stem = f"{name}-{seed}"
    jobs[name] = ["differential.mjs", "--old", args.old, "--new", new_kernel, "--inputs", work / (stem + "-inputs.json"), "--valid", work / (stem + "-valid.json"),
                  "--profile", name, "--seed", seed, "--reduce", "--out", work / (stem + "-diffs.jsonl")]
covering = dict(spec.split("=", 1) for spec in args.covering)
for name, path in covering.items():
    jobs["covering_" + name] = ["differential.mjs", "--old", args.old, "--new", new_kernel, "--inputs", path, "--reduce-text", "--out", work / f"covering-{name}-diffs.jsonl"]
if args.real:
    jobs["real"] = ["differential.mjs", "--old", args.old, "--new", new_kernel, "--inputs", args.real, "--reduce-text", "--out", work / "real-diffs.jsonl"]
    jobs["real_vs_pre_ast"] = ["differential.mjs", "--old", args.pre_ast, "--new", new_kernel, "--inputs", args.real, "--reduce-text", "--out", work / "real-pre-ast-diffs.jsonl"]
with ThreadPoolExecutor(len(jobs)) as pool:
    results = dict(zip(jobs, pool.map(lambda j: last_json(node(*jobs[j])), jobs)))
counts["differential"] = results

# 3. classification: the fuzz and covering differences are run under real bash, real commands are never run
fuzz = [f"{n}={work / f'{n}-{s}-diffs.jsonl'}" for n, s, _ in PROFILES] + [f"covering_{n}={work / f'covering-{n}-diffs.jsonl'}" for n in covering]
counts["classes"] = {}
for label, specs, no_run in [("fuzz_and_covering", fuzz, []),
                             ("real", [f"real={work / 'real-diffs.jsonl'}"] if args.real else [], ["real"]),
                             ("real_vs_pre_ast", [f"real_pre_ast={work / 'real-pre-ast-diffs.jsonl'}"] if args.real else [], ["real_pre_ast"])]:
    if not specs:
        continue
    command = [sys.executable, str(here / "classify.py"), "--repo", str(repo), "--diffs", *specs]
    if no_run:
        command += ["--no-run", *no_run]
    done = subprocess.run(command, capture_output=True, text=True, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    counts["classes"][label] = json.loads(done.stdout)

# 4. M4 is unchanged by the lane layer: the kernel before the walker against this one
m4 = {}
for name, seed, _ in PROFILES:
    m4[f"{name}-{seed}"] = last_json(node("m4-identity.mjs", "--a", args.pre_ast, "--b", new_kernel, "--inputs", work / f"{name}-{seed}-inputs.json", "--valid", work / f"{name}-{seed}-valid.json"))
for name, path in covering.items():
    m4["covering_" + name] = last_json(node("m4-identity.mjs", "--a", args.pre_ast, "--b", new_kernel, "--inputs", path))
if args.real:
    m4["real"] = last_json(node("m4-identity.mjs", "--a", args.pre_ast, "--b", new_kernel, "--inputs", args.real))
counts["m4_identity"] = m4

# 4b. commit 9a4e9f97's own claim ("executedText and fetchKind unchanged"): the kernels before and after it, on the same corpora
if args.marks_before and args.marks_after:
    marks = {}
    for name, seed, _ in PROFILES:
        marks[f"{name}-{seed}"] = last_json(node("m4-identity.mjs", "--a", args.marks_before, "--b", args.marks_after, "--fields", "text", "--inputs", work / f"{name}-{seed}-inputs.json", "--valid", work / f"{name}-{seed}-valid.json"))
    for name, path in covering.items():
        marks["covering_" + name] = last_json(node("m4-identity.mjs", "--a", args.marks_before, "--b", args.marks_after, "--fields", "text", "--inputs", path))
    if args.real:
        marks["real"] = last_json(node("m4-identity.mjs", "--a", args.marks_before, "--b", args.marks_after, "--fields", "text", "--inputs", args.real))
    counts["marks_commit_text_identity"] = marks

# 4c. the oracle's generators over fresh seeds, against this kernel and (for the ext generator) the kernel before the repairs
def scale(repo_dir, profile, first, last):
    chunks = [(a, min(a + 40, last)) for a in range(first, last, 40)]

    def one(chunk):
        done = subprocess.run([sys.executable, str(here / "oracle-scale.py"), "--repo", str(repo_dir), "--profile", profile, "--seeds", str(chunk[0]), str(chunk[1])],
                              capture_output=True, text=True, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if done.returncode:
            sys.exit("oracle-scale failed: " + done.stderr[-400:])
        return json.loads(done.stdout.strip().splitlines()[-1])
    with ThreadPoolExecutor(min(12, len(chunks))) as pool:
        parts = list(pool.map(one, chunks))
    total = {k: sum(p[k] for p in parts) for k in ("commands", "lane_runs", "timeouts", "first_run_differences", "pipe_races", "lane_differences", "parse_error_lanes_agree")}
    return {"profile": profile, "seeds": [first, last], "chunks": len(chunks), **total}


oracle = {"base": scale(repo, "base", 7000, 7480), "ext": scale(repo, "ext", 8000, 8480)}
if args.pre_repair_kernel:
    tree = work / "pre-repair-tree"
    for name in ("tests", "examples/claude-native/workflows"):
        (tree / name).mkdir(parents=True, exist_ok=True)
    (tree / "tests/__init__.py").write_text("")
    shutil.copy(repo / "tests/test_command_position_oracle.py", tree / "tests/test_command_position_oracle.py")
    shutil.copy(args.pre_repair_kernel, tree / "examples/claude-native/workflows/child-usage.mjs")
    shutil.copy(kernel.parent / "shell-parser.pin.json", tree / "examples/claude-native/workflows/shell-parser.pin.json")
    oracle["ext_before_the_repairs"] = scale(tree, "ext", 100, 580)
counts["oracle_fresh_seeds"] = oracle

# 4d. the committed oracle test (fixed seeds): the agreement lines it prints
import re
done = subprocess.run([sys.executable, "-B", "-m", "unittest", "tests.test_command_position_oracle"], cwd=repo, capture_output=True, text=True, check=False)
committed = {}
for key, label in (("probes", "oracle probes"), ("recovery", "oracle recovery probes"), ("generated", "oracle generated"), ("extended", "oracle extended")):
    m = re.search(re.escape(label) + r": (\d+) of (\d+) agree \((\d+)", done.stdout + done.stderr)
    committed[key] = [int(m.group(1)), int(m.group(2)), int(m.group(3))] if m else None
counts["oracle_committed"] = {**committed, "unittest_exit": done.returncode}

# 5. shapes, timing and states of the real commands
if args.real:
    counts["corpus"] = {"source": "real-commands.mjs", "until": args.real_until, "distinct_shell_texts": len(json.loads(Path(args.real).read_text()))}
    counts["shapes"] = json.loads(node("shape-counts.mjs", "--kernel", new_kernel, "--inputs", args.real, "--scanner", args.old))
    counts["timing"] = json.loads(node("timing.mjs", "--kernel", new_kernel, "--inputs", args.real))
counts["states"] = json.loads(node("states-count.mjs"))

(here / "counts.json").write_text(json.dumps(counts, indent=1) + "\n")
print(json.dumps({"written": "counts.json", "unexplained": {k: v.get("unexplained") for k, v in counts["classes"].items()}}))
