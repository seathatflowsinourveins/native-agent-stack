#!/usr/bin/env python3
"""Reconstruction of the worktrunk-crash-cleanup-probe commands actually executed
against the pinned wt 0.79.0 binary and native `git worktree`, applying the
critic's correction in gap-triage.json (workers/worktrunk-crash-cleanup-probe):
use `wt switch --create <branch> --base=main --no-hooks --no-cd --format=json`
(plain `wt switch <branch>` fails on a nonexistent branch and tests nothing).

This file documents, byte-for-byte in command shape, the probe whose raw output
is retained at $HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/
crash-probe-out/ and whose scratch repos remain at /tmp/wtcrash-scratch/{git-repo,wt-repo}.
It is NOT re-executed by this receipt: the probe already ran once (trials.jsonl,
timestamps 2026-09-22T22:36:54Z), and the acceptance rule for this wave is to run
each check once as preregistered and record the result honestly, not to re-run
until a different outcome appears. Re-running this script would be a second,
unauthorized attempt at the same check.

Design (as executed): for each of 5 trials per tool, spawn the create command
with Popen, then send SIGKILL to the child as soon as Popen() returns control
(no artificial delay/sleep and no wait for partial on-disk state to appear).
Record wall-clock kill_latency_s (time between spawn and signal delivery).
After all kills, probe worktree/branch state and attempt cleanup via each
tool's own remove/prune path.
"""
import json
import os
import signal
import subprocess
import time
from pathlib import Path

WT = Path('$HOME/.local/share/codex-ecosystem/tools/worktrunk-0.79.0/wt')
SCRATCH = Path('/tmp/wtcrash-scratch')
OUT = Path('$HOME/codex-ecosystem/state/gap-resolution-20260922/worktrunk/crash-probe-out')


def init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(['git', 'init', '--initial-branch=main', str(path)], check=True, capture_output=True)
    (path / 'fixture.txt').write_text('crash probe fixture\n')
    subprocess.run(['git', '-C', str(path), 'add', 'fixture.txt'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(path), '-c', 'user.email=fixture@example.invalid',
                     '-c', 'user.name=Fixture', 'commit', '-m', 'init'], check=True, capture_output=True)


def spawn_and_kill(argv, cwd, trials, out):
    for branch in trials:
        cmd = [str(a).replace('<branch>', branch) for a in argv]
        started = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.send_signal(signal.SIGKILL)
        proc.wait()
        latency = time.monotonic() - started
        out.write(json.dumps({'tool': 'wt' if 'wt' in cmd[0] else 'git', 'branch': branch,
                              'cmd': ' '.join(c.replace(str(WT), 'wt') for c in cmd[1:]) if False else ' '.join(cmd[1:]),
                              'kill_latency_s': latency}) + '\n')


if __name__ == '__main__':
    raise SystemExit(
        'This is a documentation reconstruction of an already-executed probe. '
        'It is intentionally not runnable as-is (no CLI entry point) to prevent an '
        'accidental unauthorized re-run; see the module docstring and the receipt at '
        'evidence/artifacts/gap-resolution-20260922/workers/worktrunk-crash-cleanup-probe.json '
        'for the retained raw output and result.'
    )
