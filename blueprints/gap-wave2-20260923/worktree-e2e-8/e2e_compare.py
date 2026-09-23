#!/usr/bin/env python3
"""Gap 8: one scripted change end-to-end (worktree create, structural diff
review, cleanup; NO PUSH per this wave's explicit authorization) run twice:
once with worktrunk + difftastic, once with native `git worktree` + `git diff`.
No `gh pr create`/`merge` is executed (no push authorized in this wave), so
the GitHub-PR leg of gap 8's original next_check is explicitly NOT exercised;
this is recorded as a limitation, not silently skipped."""
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

WT = os.path.expanduser(os.path.expanduser('~/.local/share/codex-ecosystem/tools/worktrunk-0.79.0/wt'))
DIFFT = os.path.expanduser(os.path.expanduser('~/.local/share/codex-ecosystem/bin/difft'))

SCRIPTED_CHANGE_BEFORE = '''def compute_total(items):
    total = 0
    for item in items:
        total = total + item
    return total
'''
SCRIPTED_CHANGE_AFTER = '''def compute_total(items):
    """Return the sum of items, skipping any that are None."""
    total = 0
    for item in items:
        if item is None:
            continue
        total = total + item
    return total
'''


def timed(fn):
    started = time.monotonic()
    result = fn()
    return result, round(time.monotonic() - started, 6)


def run_arm(arm_name: str, base: Path, use_worktrunk: bool):
    base.mkdir(parents=True, exist_ok=False)
    repo = base / 'repo'
    repo.mkdir()
    env = dict(os.environ)
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_AUTHOR_NAME': 'Fixture', 'GIT_COMMITTER_NAME': 'Fixture',
                'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'})
    steps = []
    failures = []

    def step(name, fn):
        t0 = time.monotonic()
        try:
            out = fn()
            steps.append({'name': name, 'ok': True, 'elapsed_s': round(time.monotonic() - t0, 6),
                         'detail': out if isinstance(out, str) else json.dumps(out)[:800]})
            return out
        except Exception as e:
            steps.append({'name': name, 'ok': False, 'elapsed_s': round(time.monotonic() - t0, 6), 'error': str(e)})
            failures.append(name)
            raise

    def sh(argv, cwd, expected=0):
        r = subprocess.run([str(x) for x in argv], cwd=str(cwd), capture_output=True, text=True, env=env)
        if r.returncode != expected:
            raise ValueError(f'{argv}: exit {r.returncode} expected {expected}: {r.stderr[:400]}')
        return r.stdout

    t_start = time.monotonic()
    try:
        step('init-repo', lambda: sh(['git', 'init', '--initial-branch=main', str(repo)], base))
        (repo / 'compute.py').write_text(SCRIPTED_CHANGE_BEFORE)
        step('add-commit-base', lambda: (sh(['git', 'add', 'compute.py'], repo),
                                         sh(['git', 'commit', '-m', 'base'], repo)))

        branch = 'feature-change'
        if use_worktrunk:
            step('worktree-create', lambda: sh([WT, 'switch', '--create', branch, '--base=main',
                                                '--no-hooks', '--no-cd', '--format=json'], repo))
            tree = base / ('repo.' + branch)
        else:
            tree = base / ('owned-' + branch)
            step('worktree-create', lambda: sh(['git', 'worktree', 'add', '-b', branch, str(tree), 'main'], repo))

        step('scripted-change', lambda: (tree / 'compute.py').write_text(SCRIPTED_CHANGE_AFTER))

        if use_worktrunk:
            def diff_review():
                r = subprocess.run([DIFFT, '--exit-code', '--color', 'never',
                                    str(repo / 'compute.py'), str(tree / 'compute.py')],
                                   capture_output=True, text=True)
                if r.returncode not in (0, 1):
                    raise ValueError(f'difft unexpected exit {r.returncode}: {r.stderr[:300]}')
                return {'tool': 'difft', 'exit_code': r.returncode, 'report_bytes': len(r.stdout),
                        'structural': 'Python' in r.stdout and 'failed to parse' not in r.stdout}
            diff_result = step('structural-diff-review', diff_review)
        else:
            def diff_review():
                r = subprocess.run(['git', 'diff', '--no-color', '--', 'compute.py'], cwd=str(tree),
                                   capture_output=True, text=True, env=env)
                return {'tool': 'git diff', 'exit_code': r.returncode, 'report_bytes': len(r.stdout)}
            diff_result = step('structural-diff-review', diff_review)

        step('commit-change-in-worktree', lambda: (sh(['git', 'add', 'compute.py'], tree),
                                                    sh(['git', 'commit', '-m', 'Skip None items in compute_total'], tree)))

        # PR create/merge deliberately NOT executed: no push authorized this wave.
        steps.append({'name': 'gh-pr-create-and-merge', 'ok': None, 'elapsed_s': 0,
                     'detail': 'SKIPPED BY AUTHORIZATION: this wave explicitly forbids push except where a unit task names a scratch branch; gap 8 next_check names gh PR create/merge but the unit brief overrides with \"no push\" for this challenger-arm task. Recorded as not_run, not as a pass.'})

        if use_worktrunk:
            step('cleanup-remove-worktree', lambda: sh([WT, 'remove', branch, '--foreground', '--no-hooks', '--format=json'], repo))
        else:
            step('cleanup-remove-worktree', lambda: sh(['git', 'worktree', 'remove', str(tree)], repo))
            step('cleanup-delete-branch', lambda: sh(['git', 'branch', '-d', branch], repo))

        final_listing = step('final-worktree-listing', lambda: sh(['git', 'worktree', 'list', '--porcelain'], repo))
        residual_worktrees = final_listing.count('worktree ')
        status = 'passed' if residual_worktrees == 1 and not tree.exists() else 'failed'
    except Exception:
        status = 'failed'
    total_elapsed = round(time.monotonic() - t_start, 6)
    return {
        'arm': arm_name, 'status': status, 'total_elapsed_s': total_elapsed,
        'n_steps': len(steps), 'n_failed_steps': len(failures), 'failures': failures,
        'diff_result': diff_result if 'diff_result' in dir() else None,
        'steps': steps,
    }


def main(base: Path):
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=True)
    receipt = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat()}
    arm_a = run_arm('worktrunk+difftastic', base / 'arm-a', use_worktrunk=True)
    arm_b = run_arm('git-worktree+git-diff', base / 'arm-b', use_worktrunk=False)
    receipt['arm_a'] = arm_a
    receipt['arm_b'] = arm_b
    receipt['comparison'] = {
        'arm_a_total_elapsed_s': arm_a['total_elapsed_s'], 'arm_b_total_elapsed_s': arm_b['total_elapsed_s'],
        'arm_a_n_steps': arm_a['n_steps'], 'arm_b_n_steps': arm_b['n_steps'],
        'arm_a_status': arm_a['status'], 'arm_b_status': arm_b['status'],
        'arm_a_diff': arm_a['diff_result'], 'arm_b_diff': arm_b['diff_result'],
    }
    receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
    (base / 'receipt.json').write_text(json.dumps(receipt, indent=2, default=str))
    return receipt


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--base', required=True, type=Path)
    a = p.parse_args()
    r = main(a.base)
    print(json.dumps(r['comparison'], indent=2, default=str))
