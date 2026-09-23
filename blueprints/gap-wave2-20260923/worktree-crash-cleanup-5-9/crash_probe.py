#!/usr/bin/env python3
"""Gap 5/9 delayed-kill crash probe.

Unlike the prior wave's worktrunk-crash-cleanup-probe (immediate SIGKILL right
after Popen() returns, no wait for partial on-disk state), this probe polls for
.git/worktrees/<name> to actually appear on disk before sending SIGKILL, so the
kill lands mid-registration rather than before any state exists. An unrelated,
separately-created dirty worktree is present throughout, and the probe checks
that cleanup (`wt remove`/`git worktree prune`) removes only the crashed target
and leaves the unrelated dirty worktree's registration and bytes untouched.
"""
import json
import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

WT = os.path.expanduser(os.path.expanduser('~/.local/share/codex-ecosystem/tools/worktrunk-0.79.0/wt'))


def sha(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def run(argv, cwd, env=None, expected=None):
    result = subprocess.run([str(x) for x in argv], cwd=str(cwd), capture_output=True, text=True, env=env)
    if expected is not None and result.returncode != expected:
        raise ValueError(f'{argv}: exit {result.returncode} expected {expected}: {result.stderr[:400]}')
    return result


def poll_for_worktree_dir(git_common_dir: Path, admin_dir_name: str, timeout_s=5.0):
    """Busy-poll (no sleep) for .git/worktrees/<admin_dir_name> to appear.
    worktrunk names this admin directory after the WORKTREE DIRECTORY BASENAME
    (e.g. 'repo.<branch>'), not the branch name itself -- confirmed empirically
    (see receipt commands); callers must pass the basename, not the branch.
    A tight busy loop is used (no inotifywait available on this host; `wt
    switch --create` completes in ~20ms end to end, so a sleeping poll at
    millisecond granularity can race past the window where the admin dir
    exists but the process has not yet exited)."""
    target = git_common_dir / 'worktrees' / admin_dir_name
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if target.exists():
            return True, target
    return False, target


def main(base: Path):
    base = base.resolve()
    base.mkdir(parents=True, exist_ok=False)
    repo = base / 'repo'
    repo.mkdir()
    env = dict(os.environ)
    env.update({'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_AUTHOR_NAME': 'Fixture', 'GIT_COMMITTER_NAME': 'Fixture',
                'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'})

    journal = []
    receipt = {'schema_version': 1, 'started_at': datetime.now(timezone.utc).isoformat(), 'commands': journal}

    def invoke(argv, cwd, expected=0):
        r = run(argv, cwd, env=env)
        journal.append({'argv': [str(x) for x in argv], 'cwd': str(cwd).replace(str(base), '$BASE'),
                        'exit_code': r.returncode, 'stdout_tail': r.stdout[-800:], 'stderr_tail': r.stderr[-800:]})
        if r.returncode != expected:
            raise ValueError(f'{argv}: exit {r.returncode} expected {expected}: {r.stderr[:400]}')
        return r.stdout

    try:
        invoke(['git', 'init', '--initial-branch=main', str(repo)], base)
        (repo / 'fixture.txt').write_text('base\n')
        invoke(['git', 'add', 'fixture.txt'], repo)
        invoke(['git', 'commit', '-m', 'init'], repo)

        # Unrelated dirty worktree, created and left dirty BEFORE the crash target.
        unrelated_name = 'unrelated-dirty'
        invoke([WT, 'switch', '--create', unrelated_name, '--base=main', '--no-hooks', '--no-cd', '--format=json'], repo)
        unrelated_tree = base / ('repo.' + unrelated_name)
        (unrelated_tree / 'fixture.txt').write_text('modified by unrelated worktree, must survive\n')
        (unrelated_tree / 'unrelated-untracked.txt').write_text('must survive crash cleanup of a DIFFERENT worktree\n')
        unrelated_before = {
            'fixture_sha256': sha((unrelated_tree / 'fixture.txt').read_bytes()),
            'untracked_sha256': sha((unrelated_tree / 'unrelated-untracked.txt').read_bytes()),
        }

        git_common_dir = Path(invoke(['git', 'rev-parse', '--git-common-dir'], repo).strip())
        if not git_common_dir.is_absolute():
            git_common_dir = repo / git_common_dir

        def crash_trial(trial_name, target_name, wait_predicate):
            """Spawn `wt switch --create target_name`, busy-poll wait_predicate() until
            True (or 5s timeout), SIGKILL, then record the admin-dir filesystem state at
            three checkpoints (detection, immediately after proc.wait(), after a 50ms
            settle) before any cleanup command runs."""
            started = time.monotonic()
            proc = subprocess.Popen([WT, 'switch', '--create', target_name, '--base=main',
                                     '--no-hooks', '--no-cd', '--format=json'],
                                    cwd=str(repo), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 5.0
            detected = False
            while time.monotonic() < deadline:
                if wait_predicate():
                    detected = True
                    break
            detected_at = time.monotonic() - started
            listing_at_detection = sorted(p.name for p in (git_common_dir / 'worktrees').iterdir()) if (git_common_dir / 'worktrees').is_dir() else []
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=5)
            kill_sent_at = time.monotonic() - started
            listing_immediately_after_wait = sorted(p.name for p in (git_common_dir / 'worktrees').iterdir()) if (git_common_dir / 'worktrees').is_dir() else []
            time.sleep(0.05)
            listing_after_settle = sorted(p.name for p in (git_common_dir / 'worktrees').iterdir()) if (git_common_dir / 'worktrees').is_dir() else []
            return {
                'trial': trial_name, 'target_name': target_name,
                'condition_detected_before_kill': detected,
                'admin_dir_listing_at_detection_moment': listing_at_detection,
                'admin_dir_listing_immediately_after_proc_wait': listing_immediately_after_wait,
                'admin_dir_listing_after_50ms_settle': listing_after_settle,
                'admin_dir_still_present_after_50ms_settle': ('repo.' + target_name) in listing_after_settle,
                'condition_detected_at_s': round(detected_at, 6),
                'kill_sent_at_s': round(kill_sent_at, 6),
                'owned_worktree_dir_exists_after_settle': (base / ('repo.' + target_name)).exists(),
            }

        admin_dir = git_common_dir / 'worktrees'
        trial1 = crash_trial('T1_kill_on_admin_dir_appears', 'crash-target-1',
                             lambda: (admin_dir / 'repo.crash-target-1').exists())
        trial2_target_tree = base / 'repo.crash-target-2'
        trial2 = crash_trial('T2_kill_on_working_file_checked_out', 'crash-target-2',
                             lambda: (trial2_target_tree / 'fixture.txt').exists())
        receipt['crash_trials'] = [trial1, trial2]

        listing_after_kill = invoke([WT, 'list', '--format=json'], repo)
        receipt['listing_after_kill'] = json.loads(listing_after_kill)

        # Cleanup: git worktree prune (native, should remove only orphaned crash-target
        # registrations, if any survived to this point; must not touch the unrelated
        # dirty worktree).
        prune_out = invoke(['git', 'worktree', 'prune', '-v'], repo)
        receipt['git_worktree_prune_output'] = prune_out

        listing_after_prune = invoke(['git', 'worktree', 'list', '--porcelain'], repo)
        receipt['git_worktree_list_after_prune'] = listing_after_prune

        # `git worktree prune` only removes admin entries whose linked directory is
        # MISSING; a target killed late enough that its files were already checked
        # out (e.g. trial2) is a fully valid worktree from git's point of view and
        # prune correctly leaves it alone. For any crash target still registered
        # after prune, the actual cleanup path is `wt remove` (or `git worktree
        # remove`), exactly as gap 5's next_check names both tools.
        wt_remove_attempts = []
        for t in [trial1, trial2]:
            name = t['target_name']
            still_present = ('worktree ' + str(base / ('repo.' + name))) in listing_after_prune
            if not still_present:
                wt_remove_attempts.append({'target_name': name, 'attempted': False, 'reason': 'already absent after prune'})
                continue
            try:
                out = invoke([WT, 'remove', name, '--foreground', '--no-hooks', '--format=json'], repo)
                wt_remove_attempts.append({'target_name': name, 'attempted': True, 'exit_code': 0, 'output': out.strip()})
            except ValueError as e:
                wt_remove_attempts.append({'target_name': name, 'attempted': True, 'exit_code': 'nonzero', 'error': str(e)})
        receipt['wt_remove_attempts_for_prune_survivors'] = wt_remove_attempts

        listing_after_wt_remove = invoke(['git', 'worktree', 'list', '--porcelain'], repo)
        receipt['git_worktree_list_after_wt_remove_cleanup'] = listing_after_wt_remove

        unrelated_after = {
            'still_registered': ('worktree ' + str(unrelated_tree)) in listing_after_wt_remove,
            'fixture_sha256': sha((unrelated_tree / 'fixture.txt').read_bytes()),
            'untracked_sha256': sha((unrelated_tree / 'unrelated-untracked.txt').read_bytes()),
        }
        receipt['unrelated_before'] = unrelated_before
        receipt['unrelated_after'] = unrelated_after
        unrelated_preserved = (unrelated_after['still_registered']
                               and unrelated_after['fixture_sha256'] == unrelated_before['fixture_sha256']
                               and unrelated_after['untracked_sha256'] == unrelated_before['untracked_sha256'])
        crash_targets_cleaned = all(
            ('worktree ' + str(base / ('repo.' + t['target_name']))) not in listing_after_wt_remove
            for t in [trial1, trial2])

        listing_final = invoke([WT, 'list', '--format=json'], repo)
        receipt['listing_final'] = json.loads(listing_final)

        receipt['result'] = {
            'trial1_admin_dir_persisted_immediately_after_kill': (
                'repo.crash-target-1' in trial1['admin_dir_listing_immediately_after_proc_wait']),
            'trial1_self_healed_within_50ms_before_any_prune_call': (
                not trial1['admin_dir_still_present_after_50ms_settle']),
            'trial2_admin_dir_persisted_immediately_after_kill': (
                'repo.crash-target-2' in trial2['admin_dir_listing_immediately_after_proc_wait']),
            'trial2_self_healed_within_50ms_before_any_prune_call': (
                not trial2['admin_dir_still_present_after_50ms_settle']),
            'crash_targets_cleaned_by_end_of_probe': crash_targets_cleaned,
            'unrelated_dirty_worktree_preserved': unrelated_preserved,
            'only_target_cleaned': crash_targets_cleaned and unrelated_preserved,
        }
        receipt['status'] = 'passed' if (crash_targets_cleaned and unrelated_preserved) else 'failed'
    except Exception as error:
        receipt['status'] = 'failed'
        receipt['error'] = str(error)
        raise
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        (base / 'receipt.json').write_text(json.dumps(receipt, indent=2, default=str))
    return receipt


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--base', required=True, type=Path)
    a = p.parse_args()
    r = main(a.base)
    print(json.dumps({k: r[k] for k in ['status', 'crash_trials', 'result']}, indent=2, default=str))
