#!/usr/bin/env python3
"""Run frozen synthetic native quality/worktree checks in a new owned directory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
CLEAN = b'qualification fixture: clean\n'
DIRTY = b'qualification fixture: modified by this runner\n'
UNTRACKED = b'inert untracked fixture data\n'
PROJECT_CONFIG = 'pre-start = "touch HOOK_RAN"\npre-remove = "touch HOOK_RAN"\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def inert_token():
    # Deliberately generated, never issued by any provider; keep its bytes out of public reports.
    return 'ghp_' + sha(b'local inert fixture, never issued')[:36]


def validate_reports(positive, negative, token, logs):
    if len(positive) != 1 or positive[0].get('RuleID') != 'github-pat':
        raise ValueError('Positive fixture did not produce exactly one github-pat finding')
    if positive[0].get('Secret') != 'REDACTED' or token in json.dumps(positive) or any(token in x for x in logs):
        raise ValueError('Synthetic finding was not fully redacted')
    if negative != []:
        raise ValueError('Clean fixture unexpectedly produced findings')


def validate_listing(value, expected):
    if value.get('schema') != 2 or value.get('collected') != {'ci': False, 'summary': False}:
        raise ValueError('Unexpected schema or remote/model collection')
    listed = {x['branch']: Path(x['worktree']['path']).resolve()
              for x in value['items'] if 'worktree' in x}
    if listed != expected or len(value['items']) != len(expected):
        raise ValueError('Worktree list differs from exactly owned expected trees')
    return listed


def verify_dirty(tree):
    if (tree / 'fixture.txt').read_bytes() != DIRTY or (tree / 'untracked.txt').read_bytes() != UNTRACKED:
        raise ValueError('Dirty-removal attempt changed synthetic data')


def environment(work):
    # Empty environment prevents inherited provider, gitleaks and Git overrides.
    # Explicit user/system config paths avoid reading native personal stores.
    return {
        'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'NO_COLOR': '1', 'TERM': 'dumb',
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'core.hooksPath',
        'GIT_CONFIG_VALUE_0': '/dev/null', 'GIT_CONFIG_KEY_1': 'commit.gpgSign',
        'GIT_CONFIG_VALUE_1': 'false', 'GIT_TERMINAL_PROMPT': '0',
        'GIT_AUTHOR_NAME': 'Synthetic Fixture', 'GIT_COMMITTER_NAME': 'Synthetic Fixture',
        'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_EMAIL': 'fixture@example.invalid',
        'GIT_AUTHOR_DATE': '2026-09-20T00:00:00Z', 'GIT_COMMITTER_DATE': '2026-09-20T00:00:00Z',
        'WORKTRUNK_CONFIG_PATH': str(work / 'user.toml'),
        'WORKTRUNK_SYSTEM_CONFIG_PATH': str(work / 'system.toml'),
        'XDG_CONFIG_HOME': str(work / 'config'), 'XDG_CACHE_HOME': str(work / 'cache'),
        'XDG_DATA_HOME': str(work / 'data'), 'XDG_STATE_HOME': str(work / 'state'),
    }


def qualification(prefix, work):
    prefix = prefix.resolve(strict=True)
    work = work.absolute()
    if work.parent.resolve() != prefix:
        raise ValueError('Run directory must be a direct child of its private installation prefix')
    work.mkdir(mode=0o700)  # Fail closed on every existing path, including symlinks.
    logs = work / 'logs'; logs.mkdir()
    journal = []
    receipt = {'schema_version': 1, 'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
               'platform': platform.platform(), 'python': platform.python_version(), 'commands': journal}
    for name in ['run.py', 'install.py', 'pins.json', 'plan.json']:
        receipt.setdefault('frozen_inputs', {})[name] = sha((HERE / name).read_bytes())
    write_json(work / 'receipt.json', receipt)
    env = environment(work)
    (work / 'user.toml').write_text('worktree-path = "{{ repo_path }}/../owned-{{ branch }}"\n[list]\nfull = false\nsummary = false\n')
    (work / 'system.toml').write_text('')

    def invoke(name, args, cwd=work, expected=0):
        started = time.monotonic()
        result = subprocess.run([str(x) for x in args], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, timeout=60)
        out = logs / (name + '.stdout'); err = logs / (name + '.stderr')
        out.write_bytes(result.stdout); err.write_bytes(result.stderr)
        public = [str(x).replace(str(work), '$RUN').replace(str(prefix), '$PREFIX') for x in args]
        journal.append({'name': name, 'argv': public,
                        'cwd': str(cwd).replace(str(work), '$RUN'), 'exit_code': result.returncode,
                        'elapsed_seconds': round(time.monotonic() - started, 6),
                        'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr)})
        write_json(work / 'receipt.json', receipt)
        if result.returncode != expected:
            raise ValueError(f'{name}: exit {result.returncode}, expected {expected}; inspect owned logs')
        return result.stdout.decode()

    try:
        installed = json.loads((prefix / 'installation.json').read_text())
        binaries = {}
        for tool in installed['components']:
            binary = prefix / tool['binary']
            if not binary.resolve().is_relative_to(prefix) or sha(binary.read_bytes()) != tool['binary_sha256']:
                raise ValueError('Installed binary escaped prefix or changed')
            binaries[tool['name']] = binary
        gl = binaries['gitleaks']; wt = binaries['worktrunk']
        receipt['versions'] = {'git': invoke('git-version', ['git', '--version']).strip(),
                               'gitleaks': invoke('gitleaks-version', [gl, 'version']).strip(),
                               'worktrunk': invoke('wt-version', [wt, '--version']).strip()}
        token = inert_token()
        for mode, content, code in [('positive', 'token = "' + token + '"\n', 1),
                                     ('negative', 'project = "synthetic clean fixture"\n', 0)]:
            target = work / mode; target.mkdir(); (target / 'fixture.txt').write_text(content)
            invoke('gitleaks-' + mode, [gl, 'dir', str(target), '--redact=100', '--no-banner',
                   '--report-format=json', '--report-path', str(work / (mode + '.json')), '--timeout=30'], expected=code)
        positive = json.loads((work / 'positive.json').read_text())
        negative = json.loads((work / 'negative.json').read_text())
        validate_reports(positive, negative, token, [p.read_text() for p in logs.iterdir()])
        receipt['gitleaks'] = {'positive_findings': len(positive), 'rule': positive[0]['RuleID'],
                               'negative_findings': len(negative), 'fully_redacted': True,
                               'positive_report_sha256': sha((work / 'positive.json').read_bytes()),
                               'negative_report_sha256': sha((work / 'negative.json').read_bytes())}
        repo = work / 'repo'; repo.mkdir()
        invoke('git-init', ['git', 'init', '--initial-branch=main', str(repo)])
        (repo / 'fixture.txt').write_bytes(CLEAN)
        (repo / '.config').mkdir(); (repo / '.config/wt.toml').write_text(PROJECT_CONFIG)
        invoke('git-add', ['git', 'add', 'fixture.txt', '.config/wt.toml'], repo)
        invoke('git-commit', ['git', 'commit', '-m', 'Frozen synthetic worktree fixture'], repo)
        commit = invoke('git-head', ['git', 'rev-parse', 'HEAD'], repo).strip()
        expected = {'main': repo}
        for branch in ['clean', 'dirty']:
            invoke('wt-create-' + branch, [wt, 'switch', '--create', branch, '--base=main',
                   '--no-hooks', '--no-cd', '--format=json'], repo)
            tree = work / ('owned-' + branch)
            if (tree / 'fixture.txt').read_bytes() != CLEAN or (tree / 'HOOK_RAN').exists():
                raise ValueError('Creation changed fixture or ran a hook')
            if invoke('git-head-' + branch, ['git', 'rev-parse', 'HEAD'], tree).strip() != commit:
                raise ValueError('Created worktree did not start at frozen commit')
            expected[branch] = tree
        validate_listing(json.loads(invoke('wt-list-created', [wt, 'list', '--format=json'], repo)), expected)
        invoke('wt-remove-clean', [wt, 'remove', 'clean', '--foreground', '--no-hooks', '--format=json'], repo)
        if expected.pop('clean').exists():
            raise ValueError('Clean worktree was not removed')
        dirty = expected['dirty']; (dirty / 'fixture.txt').write_bytes(DIRTY)
        (dirty / 'untracked.txt').write_bytes(UNTRACKED)
        invoke('wt-remove-dirty-refused', [wt, 'remove', 'dirty', '--foreground', '--no-hooks', '--format=json'], repo, expected=1)
        verify_dirty(dirty)
        validate_listing(json.loads(invoke('wt-list-refused', [wt, 'list', '--format=json'], repo)), expected)
        receipt['dirty_refusal'] = {'modified_sha256': sha((dirty / 'fixture.txt').read_bytes()),
                                    'untracked_sha256': sha((dirty / 'untracked.txt').read_bytes()),
                                    'registration_preserved': True}
        # Undo only the two exact fixture-authored mutations, after verifying their bytes.
        verify_dirty(dirty); (dirty / 'fixture.txt').write_bytes(CLEAN); (dirty / 'untracked.txt').unlink()
        invoke('wt-remove-restored', [wt, 'remove', 'dirty', '--foreground', '--no-hooks', '--format=json'], repo)
        if expected.pop('dirty').exists():
            raise ValueError('Restored worktree was not removed')
        validate_listing(json.loads(invoke('wt-list-final', [wt, 'list', '--format=json'], repo)), expected)
        porcelain = invoke('git-worktree-final', ['git', 'worktree', 'list', '--porcelain'], repo)
        if porcelain.count('worktree ') != 1 or 'branch refs/heads/main' not in porcelain:
            raise ValueError('Git retained unexpected worktrees')
        branches = invoke('git-branches-final', ['git', 'branch', '--format=%(refname:short)'], repo).splitlines()
        if branches != ['main'] or invoke('git-status-final', ['git', 'status', '--porcelain'], repo):
            raise ValueError('Unexpected branches or dirty primary fixture')
        if list(work.rglob('HOOK_RAN')):
            raise ValueError('A project hook ran')
        receipt['worktrunk'] = {'created': 2, 'removed_without_force': 2, 'dirty_removal_refused': True,
                                'frozen_commit': commit, 'project_hooks_suppressed': True}
        receipt['cleanup'] = {'remaining_worktrees': ['repo'], 'remaining_branches': branches,
                              'owned_clean_path_absent': True, 'owned_dirty_path_absent': True,
                              'primary_fixture_and_logs_retained': True,
                              'services_or_models_started': False}
        receipt['status'] = 'passed'
    except Exception as error:
        receipt['status'] = 'failed'; receipt['error'] = str(error)
        raise
    finally:
        receipt['finished_at'] = datetime.now(timezone.utc).isoformat()
        write_json(work / 'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    args = parser.parse_args()
    result = qualification(args.prefix, args.work)
    print(json.dumps({k: result[k] for k in ['status', 'gitleaks', 'worktrunk', 'cleanup']}, indent=2))
