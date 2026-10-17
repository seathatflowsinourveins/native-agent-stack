"""Model-free OS boundary regressions; no real credential or network request."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from tools.muse_file_fence import (Fence, sanitized_settings, clean_env, native_argv,
                                  probe, main, DEFAULT_LANE, DEFAULT_RUNTIME)


class MuseFenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='muse-file-fence-test-', dir='/var/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.work = self.root / 'work'
        self.logs = self.root / 'logs'
        self.work.mkdir()
        self.logs.mkdir()
        for name in ('tmp', 'data', 'state', 'cache'):
            (self.logs / name).mkdir()
        self.brief = self.root / 'brief.md'
        self.brief.write_text('A harmless probe.\n')
        self.auth = self.root / 'synthetic-sign-in.json'
        self.auth.write_text('{}\n')
        self.settings = self.root / 'settings.json'
        self.settings.write_text(json.dumps({
            'schema_version': 1, 'mcpServers': {'bad': {'command': '/bin/false'}},
            'mcp_servers': {'bad': {'command': '/bin/false'}},
            'hooks': {'SessionStart': [{'command': '/bin/false'}]},
            'managed_hooks_path': '/outside/hooks.json', 'plugins': ['outside'],
            'managed_plugins_path': '/outside/plugins',
            'contributor_mode_enabled': True, 'unknown_future_plugin': '/bad',
            'contributor_mode_disclosure_acknowledged': True}))
        self.runtime = Path('/usr/bin/python3').resolve()
        self.fence = Fence(self.work, self.brief, self.logs, self.runtime,
                           self.auth, self.settings)

    def run_fenced(self, script):
        with self.fence.prepared() as command:
            return subprocess.run(command + [str(self.runtime), '-I', '-c', script],
                                  env={}, capture_output=True, text=True, timeout=30)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_unfenced_canary_read_fenced_denial(self):
        """FAIL-FIRST: same payload reads the planted host file without bwrap."""
        canary = self.root / 'outside-worktree-canary'
        canary.write_text('PUBLIC SYNTHETIC CANARY\n')
        script = 'from pathlib import Path; Path(' + repr(str(canary)) + ').read_bytes()'
        before = subprocess.run([str(self.runtime), '-I', '-c', script], capture_output=True)
        self.assertEqual(before.returncode, 0, 'unfenced positive control must read canary')
        after = self.run_fenced(script)
        self.assertNotEqual(after.returncode, 0, 'fence must deny the identical read')
        self.assertIn('FileNotFoundError', after.stderr)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_named_masks_and_only_declared_writes(self):
        home = str(Path.home())
        # Test existence/read attempts only, never inspect real secret content.
        masks = {n: str(Path(home) / n) for n in (
            '.ssh', '.codex', '.claude', '.hcom', '.local/state', 'code',
            '.local/state/native-agent-stack/coordination/ns2604-coop',
            '.local/state/native-agent-stack/coordination/command-center')}
        masks.update({'host-run-user': '/run/user', 'windows-mounts': '/mnt',
                      'other-var-tmp': str(self.root), 'staging-siblings': str(self.settings)})
        script = f'''
import json, os
from pathlib import Path
out = {{}}
for name, path in {masks!r}.items():
    p = Path(path)
    if name == 'other-var-tmp':
        out[name] = sorted(x.name for x in p.iterdir()) == ['brief.md', 'logs', 'work']
    else:
        out[name] = not p.exists()
for name, path in {{'worktree-rw': {str(self.work)!r}, 'log-rw': {str(self.logs)!r}}}.items():
    p = Path(path) / 'write-marker'; p.write_text('public'); out[name] = p.read_text() == 'public'
out['brief-ro'] = not os.access({str(self.brief)!r}, os.W_OK)
out['runtime-ro'] = not os.access({str(self.runtime)!r}, os.W_OK)
out['auth-ro'] = not os.access({str(Path.home()/'.config/muse/auth.json')!r}, os.W_OK)
out['settings-ro'] = not os.access({str(Path.home()/'.config/muse/settings.json')!r}, os.W_OK)
out['project-muse-empty-ro'] = not list(Path({str(self.work/'.muse')!r}).iterdir()) and not os.access({str(self.work/'.muse')!r}, os.W_OK)
for name, path in {{'home-ro': {home!r}, 'root-ro': '/', 'etc-ro': '/etc'}}.items():
    try:
        (Path(path) / 'muse-file-fence-no-write').write_text('public'); out[name] = False
    except OSError:
        out[name] = True
out['environment-clean'] = 'META_API_KEY' not in os.environ and 'MUSE_PERMISSION_PROFILE_FAIL_OPEN' not in os.environ
print(json.dumps(out))
'''
        result = self.run_fenced(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(result.stdout)
        self.assertTrue(all(facts.values()), facts)
        self.assertTrue((self.work / 'write-marker').exists())
        self.assertTrue((self.logs / 'write-marker').exists())

    def test_sanitizer_allowlists_inert_preferences(self):
        self.assertEqual(sanitized_settings(self.settings), {
            'schema_version': 1, 'contributor_mode_enabled': False,
            'contributor_mode_disclosure_acknowledged': True})

    def test_symlink_config_mount_refused(self):
        (self.work / '.muse').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError), self.fence.prepared():
            pass

    def test_credential_or_runtime_overlap_refused(self):
        for path in (self.work / 'auth.json', self.logs / 'auth.json'):
            path.write_text('{}')
            with self.assertRaises(ValueError):
                Fence(self.work, self.brief, self.logs, self.runtime, path)

    def test_symlink_dependency_refused(self):
        link = self.root / 'alias'
        link.symlink_to(self.brief)
        with self.assertRaises(ValueError):
            Fence(self.work, link, self.logs, self.runtime, self.auth)

    def test_protected_home_input_refused(self):
        # The actual contents of the chosen existing protected config are not read.
        with self.assertRaises(ValueError):
            Fence(self.work, self.brief, self.logs, self.runtime, self.auth,
                  inputs=[Path.home()/'.config/muse/settings.json'])

    def test_local_share_home_input_refused(self):
        # A2 finding G8-A02: ~/.local/share holds ai-memory's bearer files. Synthetic files under a temporary HOME only.
        home = self.root / 'home'
        store = home / '.local/share/ai-memory/auth-token'
        store.parent.mkdir(parents=True)
        store.write_text('SYNTHETIC-NOT-A-SECRET\n')
        workspace = home / 'workspace/notes.md'
        workspace.parent.mkdir(parents=True)
        workspace.write_text('A harmless input.\n')
        with mock.patch.dict(os.environ, {'HOME': str(home)}):
            with self.assertRaisesRegex(ValueError, 'protected home input refused'):
                Fence(self.work, self.brief, self.logs, self.runtime, self.auth, inputs=[store])
            fence = Fence(self.work, self.brief, self.logs, self.runtime, self.auth, inputs=[workspace])
        self.assertEqual(fence.inputs, [workspace])

    def test_environment_does_not_forward_injection(self):
        env = clean_env(Path.home(), self.logs)
        for name in ('META_API_KEY', 'LD_PRELOAD', 'PYTHONPATH', 'MUSE_AUTH_PATH',
                     'MUSE_TRANSPORT_TRACE', 'MUSE_PERMISSION_PROFILE_FAIL_OPEN',
                     'HTTP_PROXY', 'CODEX_HOME', 'XDG_CONFIG_HOME'):
            self.assertNotIn(name, env)

    def test_notes_publish_no_private_run_commitments(self):
        notes = Path(__file__).resolve().parents[1] / 'notes/muse-file-fence-20261014'
        receipt = json.loads((notes / 'receipt.json').read_text())
        custody = receipt['private_custody']
        self.assertEqual(set(custody), {'reference', 'artifacts', 'note'})
        self.assertIsInstance(custody['reference'], str)
        self.assertTrue(custody['reference'])
        self.assertEqual(set(custody['artifacts']), {
            'muse-exec.jsonl', 'muse-exec.stderr.log', 'fence-probe.json',
            'receipt.json', 'probe-echo.jsonl'})
        self.assertNotRegex(json.dumps(custody), r'[0-9a-fA-F]{64}')
        # Cover the notes publication boundary, including future JSON records.
        # Source/review/vendor fingerprints have separate named fields; native
        # conversation and diagnostic filenames must never key a commitment.
        private_names = set(custody['artifacts'])
        def check(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in private_names and isinstance(item, str):
                        self.assertNotRegex(item, r'^[0-9a-fA-F]{7,64}$')
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)
        for path in notes.glob('*.json'):
            check(json.loads(path.read_text()))
        # Measured historical facts survive the privacy correction unchanged.
        smoke = receipt['live_smoke']
        self.assertEqual((smoke['exit_code'], smoke['event_count']), (0, 39))
        self.assertEqual(smoke['started_utc'], '2026-10-14T22:57:44.899234+00:00')
        self.assertEqual(smoke['finished_utc'], '2026-10-14T22:57:58.138320+00:00')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_cli_absent_default_settings_probe_passes(self):
        home = self.root / 'default-home'
        home.mkdir()
        runtime = self.root / 'synthetic-muse'
        runtime.write_text('''#!/usr/bin/python3
import sys
if '--version' in sys.argv:
 print('Muse Code synthetic (1.4.9-R6297.1)')
else:
 print('{"payload_type":"run.terminal.completed"}')
''')
        runtime.chmod(0o700)
        lane = self.root / 'synthetic-lane'
        lane.write_text('synthetic argv boundary, never executed')
        logs = self.root / 'default-settings-logs'
        argv = ['muse_file_fence.py', '--probe-only', '--lane', str(lane),
                '--runtime', str(runtime), '--auth', str(self.auth),
                str(self.work), str(self.brief), str(logs)]
        plan = [str(runtime), 'exec', '--model', 'synthetic', '--reasoning-effort', 'max']
        with mock.patch('pathlib.Path.home', return_value=home), \
                mock.patch('tools.muse_file_fence.RUNTIME_SHA256', hashlib.sha256(runtime.read_bytes()).hexdigest()), \
                mock.patch('sys.argv', argv), \
                mock.patch('tools.muse_file_fence.native_argv', return_value=plan):
            self.assertEqual(main(), 0)
        self.assertFalse((home / '.config/muse/settings.json').exists())
        self.assertTrue(json.loads((logs / 'fence-probe.json').read_text())['pass'])
        # An explicit nonexistent file is an error, never a defaults fallback.
        malformed = self.root / 'malformed.json'
        malformed.write_text('invalid JSON')
        linked = self.root / 'settings-link.json'
        linked.symlink_to(self.settings)
        for name, path in (('absent', self.root / 'absent.json'),
                           ('malformed', malformed), ('symlink', linked), ('directory', home)):
            explicit_logs = self.root / ('explicit-' + name + '-logs')
            explicit = argv[:-1] + [str(explicit_logs), '--settings', str(path)]
            with self.subTest(explicit=name), \
                    mock.patch('pathlib.Path.home', return_value=home), \
                    mock.patch('sys.argv', explicit), \
                    mock.patch('tools.muse_file_fence.native_argv', return_value=plan), \
                    self.assertRaises(ValueError):
                main()
            if (explicit_logs / 'muse-exec.jsonl').exists():
                self.assertEqual((explicit_logs / 'muse-exec.jsonl').stat().st_size, 0)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_linked_git_worktree_refused_for_every_role(self):
        common = self.root / 'common-repo'
        def git(*args):
            return subprocess.run(['git', *args], check=True, capture_output=True, text=True)
        git('init', '--quiet', str(common))
        git('-C', str(common), 'config', 'user.name', 'Fence fixture')
        git('-C', str(common), 'config', 'user.email', 'fixture@users.noreply.github.com')
        git('-C', str(common), '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null',
            'commit', '--quiet', '--allow-empty', '-m', 'Synthetic Git fixture')
        git('-C', str(common), 'worktree', 'add', '--quiet', '--detach', str(self.work))
        self.assertTrue((self.work / '.git').is_file())
        self.assertEqual(git('-C', str(self.work), 'diff', 'HEAD').returncode, 0)
        for role in ('reviewer', 'builder', 'reader'):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, 'linked Git worktrees'):
                native_argv(DEFAULT_LANE, self.runtime, self.work, self.brief, self.logs, role, 2)
        with self.assertRaises(ValueError), self.fence.prepared():
            self.fail('linked layout accepted by fence API')

    def run_model_free_probe(self):
        # Exercise the real OS payload; substitute only the final echo turn
        # with synthetic terminal JSON so this regression needs no Muse install.
        argv = [str(self.runtime), '-I', '-c',
                'print(\'{"payload_type":"run.terminal.completed"}\')',
                '--model', 'synthetic', '--reasoning-effort', 'max']
        with self.fence.prepared() as command:
            return probe(self.fence, command, argv)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_probe_preserves_existing_worktree_and_log_files(self):
        existing = [self.work / '.muse-fence-probe-marker',
                    self.logs / '.muse-fence-probe-marker']
        for path in existing:
            path.write_bytes(b'existing user data\x00preserve exactly\n')
        snapshots = {path: (path.stat().st_ino, path.read_bytes()) for path in existing}
        self.assertTrue(self.run_model_free_probe()['pass'])
        for path, (inode, data) in snapshots.items():
            self.assertTrue(path.exists(), str(path) + ' was removed by the probe')
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_ino, inode)
        # The probe must clean up only its own files.
        self.assertEqual(set(p.name for p in self.work.iterdir()),
                         {'.muse-fence-probe-marker', '.muse', '.mcp.json', '.git'})

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_tmp_brief_and_input_mounts_remain_readonly(self):
        # Explicit /tmp fixtures reproduce the supported input path regression.
        with tempfile.TemporaryDirectory(prefix='muse-fence-tmp-input-', dir='/tmp') as tmp:
            root = Path(tmp)
            brief = root / 'brief.md'
            named = root / 'named.txt'
            other = root / 'undeclared.txt'
            for path in (brief, named, other):
                path.write_text(path.name)
            self.fence = Fence(self.work, brief, self.logs, self.runtime,
                               self.auth, self.settings, inputs=[named])
            script = f'''
import os
from pathlib import Path
for name in {[str(brief), str(named)]!r}:
    p = Path(name)
    assert p.read_text() == p.name
    assert not os.access(p, os.W_OK)
    try:
        p.write_text('must refuse')
    except OSError:
        pass
    else:
        raise AssertionError('declared input writable')
assert not Path({str(other)!r}).exists()
Path('/tmp/private-write').write_text('log-only')
'''
            after = self.run_fenced(script)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertEqual((self.logs / 'tmp/private-write').read_text(), 'log-only')
            self.assertEqual(brief.read_text(), brief.name)
            self.assertEqual(named.read_text(), named.name)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_declared_worktree_input_readonly_overlay(self):
        named = self.work / 'input.txt'
        named.write_text('preserved input')
        self.fence = Fence(self.work, self.brief, self.logs, self.runtime,
                           self.auth, self.settings, inputs=[named])
        script = f'''
from pathlib import Path
p = Path({str(named)!r})
assert p.read_text() == 'preserved input'
try:
    p.write_text('must refuse')
except OSError:
    pass
else:
    raise AssertionError('declared worktree input writable')
Path({str(self.work / 'ordinary-write')!r}).write_text('allowed')
'''
        after = self.run_fenced(script)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(named.read_text(), 'preserved input')
        self.assertEqual((self.work / 'ordinary-write').read_text(), 'allowed')

    def test_log_local_input_and_worktree_runtime_still_refused(self):
        named = self.logs / 'input.txt'
        named.write_text('not allowed')
        with self.assertRaises(ValueError):
            Fence(self.work, self.brief, self.logs, self.runtime, self.auth, inputs=[named])
        runtime = self.work / 'runtime'
        runtime.write_text('not allowed')
        with self.assertRaises(ValueError):
            Fence(self.work, self.brief, self.logs, runtime, self.auth)

    def custody_runtime(self, phase):
        runtime = self.root / ('custody-runtime-' + phase)
        read_target = self.root / ('retained-input-' + phase)
        read_target.write_text('{"payload_type":"run.terminal.completed"}\n'
                               '{"payload_type":"fixture.private-artifact"}\n')
        write_target = self.root / ('retained-output-' + phase)
        write_target.write_bytes(b'public synthetic preserved fixture\n')
        runtime.write_text('''#!/usr/bin/python3
import json, sys
from pathlib import Path
if '--version' in sys.argv:
 print('Muse Code synthetic (1.4.9-R6297.1)'); raise SystemExit(0)
echo = '--provider' in sys.argv
if echo == ''' + repr(phase == 'probe') + ''':
 for name, target in ''' + repr([
            ('probe-echo.jsonl' if phase == 'probe' else 'muse-exec.jsonl', str(read_target)),
            ('fence-probe.json' if phase == 'probe' else 'receipt.json', str(write_target))]) + ''':
  p = Path(''' + repr(str(self.logs if phase == 'probe' else self.root / 'live-custody-logs')) + ''') / name
  try:
   p.unlink(missing_ok=True); p.symlink_to(target)
  except OSError:
   pass
print(json.dumps({'payload_type':'run.terminal.completed'}))
''')
        runtime.chmod(0o700)
        return runtime, write_target

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_probe_artifact_custody(self):
        runtime, preserved = self.custody_runtime('probe')
        fence = Fence(self.work, self.brief, self.logs, runtime, self.auth, self.settings)
        argv = [str(runtime), 'exec', '--model', 'synthetic', '--reasoning-effort', 'max']
        with fence.prepared() as command:
            result = probe(fence, command, argv)
        self.assertEqual(preserved.read_bytes(), b'public synthetic preserved fixture\n')
        self.assertEqual(result['echo']['event_count'], 1)
        self.assertNotIn('fixture.private-artifact', result['echo']['event_counts'])
        self.assertFalse((self.logs / 'fence-probe.json').is_symlink())

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_live_artifact_custody(self):
        runtime, preserved = self.custody_runtime('live')
        lane = self.root / 'custody-lane'
        lane.write_text('synthetic argv boundary, never executed')
        logs = self.root / 'live-custody-logs'
        argv = ['muse_file_fence.py', '--lane', str(lane), '--runtime', str(runtime),
                '--auth', str(self.auth), '--settings', str(self.settings),
                str(self.work), str(self.brief), str(logs)]
        plan = [str(runtime), 'exec', '--model', 'synthetic', '--reasoning-effort', 'max']
        with mock.patch('sys.argv', argv), \
                mock.patch('tools.muse_file_fence.RUNTIME_SHA256', hashlib.sha256(runtime.read_bytes()).hexdigest()), \
                mock.patch('tools.muse_file_fence.native_argv', return_value=plan):
            self.assertEqual(main(), 0)
        self.assertEqual(preserved.read_bytes(), b'public synthetic preserved fixture\n')
        receipt = json.loads((logs / 'receipt.json').read_text())
        self.assertEqual(receipt['event_count'], 1)
        self.assertNotIn('fixture.private-artifact', receipt['event_counts'])
        self.assertFalse((logs / 'receipt.json').is_symlink())

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_git_metadata_readonly(self):
        subprocess.run(['git', 'init', '--quiet', str(self.work)], check=True)
        config = self.work / '.git/config'
        original = config.read_bytes()
        payload = f'''
from pathlib import Path
root = Path({str(self.work)!r})
for path in [root / '.git/config', root / '.git/fence-test-marker']:
    try:
        path.write_text('public synthetic metadata fixture')
    except OSError:
        pass
    else:
        raise AssertionError('Git metadata must be read-only')
(root / 'ordinary-output').write_text('public work output')
'''
        result = self.run_fenced(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(config.read_bytes(), original)
        self.assertFalse((self.work / '.git/fence-test-marker').exists())
        self.assertTrue((self.work / 'ordinary-output').exists())

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_reader_git_pointer_refused(self):
        """Sealed addendum-01 item 2; real CLI refusal before execution."""
        metadata = self.work / 'administration'
        subprocess.run(['git', 'init', '--quiet', '--separate-git-dir', str(metadata),
                        str(self.work)], check=True, capture_output=True)
        runtime = self.root / 'git-pointer-runtime'
        runtime.write_text('''#!/usr/bin/python3
import json, sys
from pathlib import Path
if '--version' in sys.argv:
 print('Muse Code synthetic (1.4.9-R6297.1)'); raise SystemExit(0)
print(json.dumps({'payload_type':'run.terminal.completed'}))
''')
        runtime.chmod(0o700)
        for layout in ('absolute', 'relative'):
            with self.subTest(layout=layout):
                if layout == 'relative':
                    (self.work / '.git').write_text('gitdir: administration\n')
                logs = self.root / ('git-pointer-logs-' + layout)
                argv = ['muse_file_fence.py', '--lane', str(DEFAULT_LANE),
                        '--runtime', str(runtime), '--auth', str(self.auth),
                        '--settings', str(self.settings), '--role', 'reader',
                        str(self.work), str(self.brief), str(logs)]
                with mock.patch('sys.argv', argv), self.assertRaises(ValueError):
                    main()
                self.assertFalse(logs.exists(), 'layout refusal must precede run setup')

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_external_common_metadata_refused_for_every_role(self):
        """Local pr1120-d8afbf04 review location 288-293, sealed scope."""
        subprocess.run(['git', 'init', '--quiet', str(self.work)], check=True, capture_output=True)
        common = self.work / 'common-administration'
        shutil.copytree(self.work / '.git', common)
        (self.work / '.git/commondir').write_text('../common-administration\n')
        check = subprocess.run(['git', '-C', str(self.work), 'rev-parse', '--git-common-dir'],
                               check=True, capture_output=True, text=True)
        self.assertTrue(check.stdout.strip())
        runtime = self.root / 'common-metadata-runtime'
        runtime.write_text('''#!/usr/bin/python3
import sys
if '--version' in sys.argv:
 print('Muse Code synthetic (1.4.9-R6297.1)')
else:
 print('{"payload_type":"run.terminal.completed"}')
''')
        runtime.chmod(0o700)
        for role in ('reader', 'reviewer', 'builder'):
            logs = self.root / ('common-metadata-logs-' + role)
            argv = ['muse_file_fence.py', '--lane', str(DEFAULT_LANE), '--runtime', str(runtime),
                    '--auth', str(self.auth), '--settings', str(self.settings), '--role', role,
                    str(self.work), str(self.brief), str(logs)]
            with self.subTest(role=role):
                with mock.patch('sys.argv', argv), self.assertRaises(ValueError):
                    main()
                self.assertFalse(logs.exists(), 'layout refusal must precede run setup')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_unresolved_git_pointer_refused_before_execution(self):
        for index, content in enumerate(('invalid pointer', 'gitdir: absent\n', 'gitdir: \n')):
            with self.subTest(pointer=content.split(':')[0]):
                (self.work / '.git').write_text(content)
                logs = self.root / ('invalid-pointer-logs-' + str(index))
                logs.mkdir()
                with self.assertRaises(ValueError):
                    fence = Fence(self.work, self.brief, logs, self.runtime, self.auth, self.settings)
                    with fence.prepared():
                        self.fail('unresolved Git pointer accepted')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_git_pointer_in_log_scratch_refused(self):
        metadata = self.logs / 'tmp/administration'
        subprocess.run(['git', 'init', '--quiet', '--separate-git-dir', str(metadata),
                        str(self.work)], check=True, capture_output=True)
        with self.assertRaises(ValueError), self.fence.prepared():
            self.fail('pointer layout accepted by fence API')

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap not installed')
    def test_bounded_run_timeout_returns_124(self):
        from tools.muse_file_fence import run_bounded_fence
        with self.fence.prepared() as command:
            rc = run_bounded_fence(command + [str(self.runtime), '-I', '-c',
                                             'import time; time.sleep(20)'],
                                   stdout=self.fence.artifacts['muse-exec.jsonl'],
                                   stderr=self.fence.artifacts['muse-exec.stderr.log'], timeout=0.1)
        self.assertEqual(rc, 124)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_launcher_exit_stops_run(self):
        runtime = self.root / 'lifetime-runtime'
        heartbeat = self.work / 'lifetime-heartbeat'
        runtime.write_text('''#!/usr/bin/python3
import sys, time
from pathlib import Path
if '--version' in sys.argv:
 print('Muse Code synthetic (1.4.9-R6297.1)'); raise SystemExit(0)
if '--provider' in sys.argv:
 print('{"payload_type":"run.terminal.completed"}'); raise SystemExit(0)
for i in range(300):
 Path(''' + repr(str(heartbeat)) + ''').write_text(str(i))
 time.sleep(0.1)
''')
        runtime.chmod(0o700)
        logs = self.root / 'lifetime-logs'
        # This synthetic lifetime control supplies its fixture's trusted pin
        # in the test process; the production CLI has no pin override option.
        fixture_sha = hashlib.sha256(runtime.read_bytes()).hexdigest()
        cli = ('from tools import muse_file_fence as m; '
               + 'm.RUNTIME_SHA256 = ' + repr(fixture_sha) + '; raise SystemExit(m.main())')
        child_fds = []
        with (self.root / 'lifetime.stdout').open('w') as out, \
                (self.root / 'lifetime.stderr').open('w') as err:
            launcher = subprocess.Popen(['python3', '-B', '-c', cli, '--lane', str(DEFAULT_LANE),
                '--runtime', str(runtime), '--auth', str(self.auth), '--settings', str(self.settings),
                '--timeout', '30', str(self.work), str(self.brief), str(logs)],
                stdout=out, stderr=err, start_new_session=True)
            try:
                deadline = time.monotonic() + 10
                while not heartbeat.exists() and time.monotonic() < deadline:
                    if launcher.poll() is not None:
                        self.fail('synthetic lifetime fixture did not start')
                    time.sleep(0.05)
                self.assertTrue(heartbeat.exists(), 'synthetic lifetime fixture did not start')
                # Stable handles ensure cleanup targets only this fixture's children.
                children = Path(f'/proc/{launcher.pid}/task/{launcher.pid}/children').read_text().split()
                child_fds = [os.pidfd_open(int(pid)) for pid in children]
                launcher.terminate()
                launcher.wait(timeout=3)
                time.sleep(0.3)
                settled = heartbeat.read_bytes()
                time.sleep(0.3)
                self.assertEqual(heartbeat.read_bytes(), settled, 'run continued after launcher exit')
            finally:
                for fd in child_fds:
                    try:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    finally:
                        os.close(fd)
                if launcher.poll() is None:
                    launcher.kill()
                launcher.wait(timeout=3)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed-client model-free integration')
    def test_native_echo_cannot_start_extensions(self):
        runtime = DEFAULT_RUNTIME
        def hooks(marker):
            return {'SessionStart': [{'hooks': [{'type': 'command', 'command':
                '/usr/bin/touch ' + str(self.logs / marker)}]}]}
        doc = {'schema_version': 1, 'hooks': hooks('user-hook-fired'),
               'managed_hooks_path': str(self.root / 'managed-hooks.json'),
               'mcpServers': {'fence-probe': {'transport': 'stdio',
                   'command': '/bin/sh', 'args': ['-c', '/usr/bin/touch ' +
                                                str(self.logs / 'mcp-fired') + '; exit 0'],
                   'enabled': True, 'mode': 'optional'}}}
        self.settings.write_text(json.dumps(doc))
        (self.root / 'managed-hooks.json').write_text(json.dumps({'hooks': hooks('managed-hook-fired')}))
        (self.work / '.muse').mkdir()
        (self.work / '.muse/hooks.json').write_text(json.dumps({'hooks': hooks('project-hook-fired')}))
        argv = native_argv(DEFAULT_LANE, runtime, self.work, self.brief, self.logs, 'reader', 2)
        # Positive control: native startup sees the planted executable config.
        control_home = self.root / 'control-home'
        config = control_home / '.config/muse'
        config.mkdir(parents=True)
        shutil.copyfile(self.settings, config / 'settings.json')
        echo_argv = list(argv)
        for flag in ('--model', '--reasoning-effort'):
            index = echo_argv.index(flag); del echo_argv[index:index+2]
        before = subprocess.run(echo_argv + ['--provider', 'echo', '--disable-reminders'],
                                env=clean_env(control_home, self.logs), cwd=self.work,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(before.returncode, 0, before.stderr)
        for name in ('mcp-fired', 'user-hook-fired', 'project-hook-fired', 'managed-hook-fired'):
            marker = self.logs / name
            self.assertTrue(marker.exists(), name + ' control absent: ' + before.stderr)
            marker.unlink()
        fence = Fence(self.work, self.brief, self.logs, runtime, self.auth, self.settings)
        with fence.prepared() as command:
            try:
                result = probe(fence, command, argv)
            except ValueError:
                self.fail((self.logs / 'fence-probe.json').read_text() +
                          (self.logs / 'probe-echo.stderr.log').read_text())
        self.assertTrue(result['pass'], result)

    @unittest.skipUnless(os.environ.get('MUSE_FENCE_NATIVE_PROBE') == '1',
                         'explicit installed launcher model-free integration')
    def test_unfenced_launcher_canary_read_fenced_denial(self):
        canary = self.root / 'outside-worktree-canary'
        canary.write_text('public synthetic planted file')
        shim = self.root / 'muse-probe-runtime'
        shim.write_text('''#!/usr/bin/python3
import json, sys
from pathlib import Path
if '--version' in sys.argv:
 print('synthetic model-free read probe'); raise SystemExit(0)
try:
 Path(''' + repr(str(canary)) + ''').read_bytes(); readable = True
except FileNotFoundError:
 readable = False
print(json.dumps({'outside_readable': readable, 'argv': sys.argv[1:]}))
''')
        shim.chmod(0o700)
        env = {**clean_env(Path.home(), self.logs), 'MUSE_BIN': str(shim),
               'MUSE_LANE_MAX_MODEL_STEPS': '2'}
        unfenced_logs = self.root / 'unfenced-logs'
        before = subprocess.run(['/bin/bash', str(DEFAULT_LANE), '--role', 'reader',
                                 str(self.work), str(self.brief), str(unfenced_logs)],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(before.returncode, 0, before.stderr)
        control = json.loads((unfenced_logs / 'muse-exec.jsonl').read_text())
        self.assertTrue(control['outside_readable'])
        argv = native_argv(DEFAULT_LANE, shim, self.work, self.brief, self.logs, 'reader', 2)
        fence = Fence(self.work, self.brief, self.logs, shim, self.auth, self.settings)
        with fence.prepared() as command:
            after = subprocess.run(command + argv, env={}, capture_output=True, text=True, timeout=30)
        self.assertEqual(after.returncode, 0, after.stderr)
        enclosed = json.loads(after.stdout)
        self.assertFalse(enclosed['outside_readable'])
        self.assertEqual(control['argv'], enclosed['argv'])
        self.assertEqual(enclosed['argv'], argv[1:])


if __name__ == '__main__':
    unittest.main()
