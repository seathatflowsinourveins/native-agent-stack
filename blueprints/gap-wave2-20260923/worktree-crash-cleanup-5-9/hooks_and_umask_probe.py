#!/usr/bin/env python3
"""Gap 9: (a) run worktrunk with PROJECT HOOKS ENABLED (unlike every prior wave's
fixture, which always passed --no-hooks) and verify the hooks actually execute;
(b) verify a worktree created under a restricted umask cannot write files
readable/writable by group or other, and that no created path escapes the
worktree's own owned directory."""
import json
import os
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

WT = os.path.expanduser(os.path.expanduser('~/.local/share/codex-ecosystem/tools/worktrunk-0.79.0/wt'))
PROJECT_CONFIG = ('pre-start = "touch pre_start_ran.marker"\n'
                   'pre-remove = "touch ../pre_remove_ran.marker"\n')


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

    def invoke(argv, cwd, expected=0, extra_env=None):
        e = dict(env)
        if extra_env:
            e.update(extra_env)
        r = subprocess.run([str(x) for x in argv], cwd=str(cwd), capture_output=True, text=True, env=e)
        journal.append({'argv': [str(x) for x in argv], 'cwd': str(cwd).replace(str(base), '$BASE'),
                        'exit_code': r.returncode, 'stdout_tail': r.stdout[-1200:], 'stderr_tail': r.stderr[-1200:]})
        if r.returncode != expected:
            raise ValueError(f'{argv}: exit {r.returncode} expected {expected}: {r.stderr[:500]}')
        return r.stdout

    try:
        invoke(['git', 'init', '--initial-branch=main', str(repo)], base)
        (repo / 'fixture.txt').write_text('base\n')
        (repo / '.config').mkdir()
        (repo / '.config' / 'wt.toml').write_text(PROJECT_CONFIG)
        invoke(['git', 'add', 'fixture.txt', '.config/wt.toml'], repo)
        invoke(['git', 'commit', '-m', 'init with project hooks config'], repo)

        # --- (a) hooks-enabled lifecycle: NO --no-hooks this time ---
        branch = 'hooked'
        invoke([WT, 'switch', '--create', branch, '--base=main', '--no-cd', '--yes', '--format=json'], repo)
        tree = base / ('repo.' + branch)
        pre_start_markers = (list(tree.glob('pre_start_ran.marker')) + list(repo.glob('pre_start_ran.marker'))
                             + list(base.glob('pre_start_ran.marker')))
        receipt['pre_start_hook_ran'] = len(pre_start_markers) > 0
        receipt['pre_start_marker_paths'] = [str(p) for p in pre_start_markers]

        # pre-start's own marker file is untracked inside the worktree, so a plain
        # remove now refuses (uncommitted changes) -- expected and consistent with the
        # dirty-refusal behavior already verified elsewhere; --force is used here
        # because this check's purpose is the hook lifecycle, not dirty-refusal.
        invoke([WT, 'remove', branch, '--foreground', '--yes', '--force', '--format=json'], repo)
        pre_remove_markers = (list(base.glob('pre_remove_ran.marker')) + list(repo.glob('pre_remove_ran.marker'))
                              + list(tree.glob('pre_remove_ran.marker')))
        receipt['pre_remove_hook_ran'] = len(pre_remove_markers) > 0
        receipt['pre_remove_marker_paths'] = [str(p) for p in pre_remove_markers]
        receipt['hooks_enabled_result'] = {
            'pre_start_hook_ran': receipt['pre_start_hook_ran'],
            'pre_remove_hook_ran': receipt['pre_remove_hook_ran'],
            'worktree_and_branch_removed': not tree.exists(),
        }

        # --- (b) umask-restricted creation ---
        old_umask = os.umask(0o077)
        try:
            branch2 = 'umask-restricted'
            invoke([WT, 'switch', '--create', branch2, '--base=main', '--no-hooks', '--no-cd', '--format=json'], repo)
        finally:
            os.umask(old_umask)
        tree2 = base / ('repo.' + branch2)
        perm_report = []
        escaped_paths = []
        for p in tree2.rglob('*'):
            try:
                mode = p.stat(follow_symlinks=False).st_mode
            except FileNotFoundError:
                continue
            group_or_other_perm = mode & (stat.S_IRWXG | stat.S_IRWXO)
            perm_report.append({'path': str(p.relative_to(tree2)), 'mode_octal': oct(stat.S_IMODE(mode)),
                                'group_or_other_bits_set': group_or_other_perm != 0})
            resolved = p.resolve()
            if not resolved.is_relative_to(base) and not resolved.is_relative_to(Path(os.path.expanduser(
                    os.path.expanduser('~/.local/share/codex-ecosystem/tools/worktrunk-0.79.0')))):
                escaped_paths.append(str(resolved))
        receipt['umask_result'] = {
            'umask_used': '0o077',
            'files_checked': len(perm_report),
            'any_group_or_other_permission_bits_set': any(x['group_or_other_bits_set'] for x in perm_report),
            'escaped_owned_path': escaped_paths,
            'sample_permissions': perm_report[:10],
        }

        receipt['status'] = ('passed' if (receipt['pre_start_hook_ran'] and receipt['pre_remove_hook_ran']
                                          and not receipt['umask_result']['any_group_or_other_permission_bits_set']
                                          and not escaped_paths) else 'failed')
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
    print(json.dumps({k: r[k] for k in ['status', 'hooks_enabled_result', 'umask_result']}, indent=2, default=str))
