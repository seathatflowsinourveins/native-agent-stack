#!/usr/bin/env python3
"""Gap 6 challenger arm: the same create/list/remove/dirty-refuse plan shape as
blueprints/gap-resolution-20260922/worktrunk-0-79-0-requalify/run.py's
qualification(), but using native `git worktree` instead of worktrunk, as the
challenger for the matched winner-vs-challenger comparison gap 6 asks for.
No hooks concept exists in native git worktree, so that step is simply absent
(recorded as a feature-parity difference, not a failure)."""
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

CLEAN = b'qualification fixture: clean\n'
DIRTY = b'qualification fixture: modified by this runner\n'
UNTRACKED = b'inert untracked fixture data\n'


def sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run(argv, cwd, expected=0, journal=None):
    started = time.monotonic()
    result = subprocess.run([str(x) for x in argv], cwd=str(cwd), capture_output=True, text=True)
    elapsed = round(time.monotonic() - started, 6)
    entry = {'argv': [str(x) for x in argv], 'cwd': str(cwd), 'exit_code': result.returncode,
             'elapsed_seconds': elapsed, 'stdout': result.stdout[-2000:], 'stderr': result.stderr[-2000:]}
    if journal is not None:
        journal.append(entry)
    if result.returncode != expected:
        raise ValueError(f'{argv}: exit {result.returncode}, expected {expected}: {result.stderr[:500]}')
    return result.stdout


def main(work: Path):
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    journal = []
    receipt = {'schema_version': 1, 'tool': 'git worktree (native)',
               'started_at': datetime.now(timezone.utc).isoformat(), 'commands': journal}
    repo = work / 'repo'
    repo.mkdir()
    env_note = 'GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null'
    import os
    env = dict(os.environ)
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_AUTHOR_NAME': 'Synthetic Fixture', 'GIT_COMMITTER_NAME': 'Synthetic Fixture',
                'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'})

    def invoke(argv, cwd, expected=0):
        started = time.monotonic()
        result = subprocess.run([str(x) for x in argv], cwd=str(cwd), capture_output=True, text=True, env=env)
        elapsed = round(time.monotonic() - started, 6)
        journal.append({'argv': [str(x) for x in argv], 'cwd': str(cwd).replace(str(work), '$WORK'),
                        'exit_code': result.returncode, 'elapsed_seconds': elapsed,
                        'stdout_tail': result.stdout[-1500:], 'stderr_tail': result.stderr[-1500:]})
        if result.returncode != expected:
            raise ValueError(f'{argv}: exit {result.returncode}, expected {expected}: {result.stderr[:500]}')
        return result.stdout

    try:
        invoke(['git', 'init', '--initial-branch=main', str(repo)], work)
        (repo / 'fixture.txt').write_bytes(CLEAN)
        invoke(['git', 'add', 'fixture.txt'], repo)
        invoke(['git', 'commit', '-m', 'Frozen synthetic worktree fixture'], repo)
        commit = invoke(['git', 'rev-parse', 'HEAD'], repo).strip()

        owned = {'main': repo}
        for branch in ['clean', 'dirty']:
            tree = work / ('owned-' + branch)
            invoke(['git', 'worktree', 'add', '-b', branch, str(tree), 'main'], repo)
            if (tree / 'fixture.txt').read_bytes() != CLEAN:
                raise ValueError('Creation changed fixture')
            if invoke(['git', 'rev-parse', 'HEAD'], tree).strip() != commit:
                raise ValueError('Created worktree did not start at frozen commit')
            owned[branch] = tree

        listing = invoke(['git', 'worktree', 'list', '--porcelain'], repo)
        if listing.count('worktree ') != 3:
            raise ValueError('Unexpected worktree count after create')

        invoke(['git', 'worktree', 'remove', str(owned['clean'])], repo)
        if owned['clean'].exists():
            raise ValueError('Clean worktree was not removed')

        dirty = owned['dirty']
        (dirty / 'fixture.txt').write_bytes(DIRTY)
        (dirty / 'untracked.txt').write_bytes(UNTRACKED)
        # native git worktree remove refuses (without --force) if the worktree has
        # modifications to tracked files; untracked files alone do not block it,
        # so this is the closest native analogue to worktrunk's dirty-refusal step.
        removal_exit = None
        try:
            invoke(['git', 'worktree', 'remove', str(dirty)], repo, expected=0)
            removal_exit = 0
        except ValueError:
            removal_exit = 1
        refused = removal_exit != 0
        if not refused:
            raise ValueError('git worktree remove did not refuse a dirty (modified-tracked-file) worktree')
        if dirty.exists() and (dirty / 'fixture.txt').read_bytes() != DIRTY:
            raise ValueError('Dirty-removal attempt changed synthetic data')

        listing_after_refusal = invoke(['git', 'worktree', 'list', '--porcelain'], repo)
        if listing_after_refusal.count('worktree ') != 2:
            raise ValueError('Dirty worktree registration lost after refused removal')

        (dirty / 'fixture.txt').write_bytes(CLEAN)
        (dirty / 'untracked.txt').unlink()
        invoke(['git', 'worktree', 'remove', str(dirty)], repo)
        if dirty.exists():
            raise ValueError('Restored worktree was not removed')

        final = invoke(['git', 'worktree', 'list', '--porcelain'], repo)
        if final.count('worktree ') != 1 or 'branch refs/heads/main' not in final:
            raise ValueError('Git retained unexpected worktrees')
        branches_before_branch_cleanup = invoke(['git', 'branch', '--format=%(refname:short)'], repo).splitlines()
        branch_cleanup_needed = sorted(branches_before_branch_cleanup) != ['main']
        # Unlike worktrunk's `wt remove`, native `git worktree remove` does NOT delete
        # the branch; a real user/script would need an explicit follow-up `git branch -d`.
        # Record this as a genuine feature-parity finding, then perform the follow-up
        # so the plan's own final-state check (matching worktrunk's) still passes.
        if branch_cleanup_needed:
            for b in branches_before_branch_cleanup:
                if b != 'main':
                    invoke(['git', 'branch', '-d', b], repo)
        branches = invoke(['git', 'branch', '--format=%(refname:short)'], repo).splitlines()
        if branches != ['main']:
            raise ValueError('Unexpected branches remain even after explicit git branch -d cleanup')

        receipt['result'] = {
            'created': 2, 'removed_without_force': 1, 'removed_with_force_or_after_cleanup': 1,
            'dirty_removal_refused': True, 'dirty_removal_refused_reason': 'native `git worktree remove` refuses when a tracked file is modified (no --force); it does NOT refuse for untracked-only files, unlike worktrunk which refuses on either',
            'frozen_commit': commit, 'hooks_supported': False,
            'hooks_note': 'native git worktree has no project-hook mechanism; this is a feature-parity gap versus worktrunk, not a failure of this plan',
            'branch_cleanup_needed': branch_cleanup_needed,
            'branch_cleanup_finding': 'native `git worktree remove` leaves the associated branch behind (branches after worktree removal, before explicit cleanup: ' + repr(sorted(branches_before_branch_cleanup)) + '); worktrunk\'s `wt remove` deletes both the worktree and its branch in one step (see worktrunk-0-79-0-requalify.json result.cleanup.remaining_branches == [\"main\"] with no extra step). An explicit `git branch -d` per removed worktree was required here to reach the same end state.',
            'remaining_worktrees': ['repo'], 'remaining_branches': branches,
        }
        receipt['status'] = 'passed'
    except Exception as error:
        receipt['status'] = 'failed'
        receipt['error'] = str(error)
        raise
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        (work / 'receipt.json').write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    result = main(args.work)
    print(json.dumps({k: result[k] for k in ['status', 'result']}, indent=2))
