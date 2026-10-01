"""The oracle's generators over a range of fresh seeds: how many generated commands the kernel reads as real bash ran them (counts only).

    python3 oracle-scale.py --repo <checkout> --profile base|ext --seeds <first> <last> [--per-seed 60] [--defects <private file>]

The generators are the two classes of tests/test_command_position_oracle.py (Generator, GeneratorExt); the committed test runs eight fixed
seeds of each, this script any other range. Every command runs under REAL bash with logging stub executables (the oracle's harness) and is
compared with the lanes the kernel reads. A command that differs is run again up to 40 times: a pipe whose right side never reads can kill its
writer with SIGPIPE, so a first-run difference that a rerun reproduces the kernel's reading for is a race of the run, not a difference.
A command whose lanes equal the run but whose tree has a parse error is counted apart (`parse_error_lanes_agree`): the reading is right and
`parse_errors` counts the call. The commands that differ for good are written to --defects (private: they are command text); the output is counts.
"""
import argparse
import collections
import json
import sys
import tempfile
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--profile", choices=["base", "ext"], required=True)
parser.add_argument("--seeds", nargs=2, type=int, required=True)
parser.add_argument("--per-seed", type=int, default=60)
parser.add_argument("--defects")
args = parser.parse_args()
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(args.repo).resolve()))
from tests import test_command_position_oracle as oracle  # noqa: E402

generator_class = oracle.GeneratorExt if args.profile == "ext" else oracle.Generator
seen, commands = set(), []
for seed in range(*args.seeds):
    generator = generator_class(seed)
    for _ in range(args.per_seed):
        command = generator.statement(generator.rnd.choice([1, 2, 2, 3, 3, 4]))
        if command not in seen and oracle.valid(command):
            seen.add(command)
            commands.append(command)
with tempfile.TemporaryDirectory(prefix="scale-") as scratch:
    home = Path(scratch)
    bin_dir = oracle.make_stubs(home)
    start = time.time()
    truth = oracle.run_real(commands, bin_dir, home)
    read = oracle.read_lanes(commands)
    differ, timeouts, ran, errors, races = [], 0, 0, 0, 0
    for command, real, seen_lanes in zip(commands, truth, read):
        errors += bool(seen_lanes["error"])
        if real is None:
            timeouts += 1
            continue
        ran += sum(real.values())
        if collections.Counter(seen_lanes["tokens"]) != real or seen_lanes["error"]:
            differ.append((command, real, seen_lanes))
    defects, lane_differences, parse_error_only = [], 0, 0
    for command, real, seen_lanes in differ:
        reader = collections.Counter(seen_lanes["tokens"])
        if reader == real:
            parse_error_only += 1  # the lanes agree with the run; the tree has an ERROR (its valid parts were read)
            defects.append({"command": command, "ran": dict(real), "read": seen_lanes["tokens"], "kind": "parse_error_lanes_agree"})
        elif any(oracle.run_real([command], bin_dir, home)[0] == reader for _ in range(40)):
            races += 1
        else:
            lane_differences += 1
            defects.append({"command": command, "ran": dict(real), "read": seen_lanes["tokens"], "kind": "lanes_differ", "parse_error": seen_lanes["error"]})
if args.defects:
    Path(args.defects).write_text(json.dumps(defects))
    Path(args.defects).chmod(0o600)
print(json.dumps({"profile": args.profile, "seeds": args.seeds, "commands": len(commands), "lane_runs": ran, "timeouts": timeouts, "first_run_differences": len(differ),
                  "pipe_races": races, "lane_differences": lane_differences, "parse_error_lanes_agree": parse_error_only, "seconds": round(time.time() - start)}))
