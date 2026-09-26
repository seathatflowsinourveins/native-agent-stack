import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('progress', ROOT/'observability/grand-dashboard/progress.py')
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)
render_spec = importlib.util.spec_from_file_location('render', ROOT/'observability/grand-dashboard/render.py')
render = importlib.util.module_from_spec(render_spec)
render_spec.loader.exec_module(render)
install_spec = importlib.util.spec_from_file_location('install', ROOT/'observability/grand-dashboard/install.py')
installer = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(installer)


class GrandDashboardTests(unittest.TestCase):
    def test_snapshot_is_bounded_public_fields(self):
        rows = progress.snapshot(ROOT)
        self.assertLessEqual(len(rows), progress.MAX_ENTITIES)
        self.assertGreater(sum(r['record_kind'] == 'decision' for r in rows), 0)
        allowed = {'record_kind','entity_id','title','state','evidence_ref','source_updated_at','number'}
        extra = {'equity_usd','drawdown_pct','fees_usd','fill_count','margin_call_count'}
        self.assertTrue(all(set(r) == allowed | (extra if r['record_kind']=='experiment' else set()) for r in rows if r['record_kind']!='workflow'))
        self.assertEqual(progress.workflow_snapshot(), [r for r in rows if r['record_kind']=='workflow'])
        self.assertEqual(1, sum(r['entity_id'] == 'snapshot' for r in rows))

    def test_combined_inventory_accepts_full_history_and_rejects_overflow(self):
        # Synthetic capacity fixture; actual native publication is separate evidence.
        history = progress.workflow_rows([
            dict(name='research-pair', status='succeeded',
                 startedAt='2026-09-19T21:00:00Z', finishedAt='2026-09-19T21:01:00Z')
            for _ in range(progress.HISTORY_LIMIT)
        ])
        original = progress.read
        with patch.object(progress, 'workflow_snapshot', return_value=history):
            base_count = len(progress.snapshot(ROOT))
            for count in (max(81, base_count), progress.MAX_ENTITIES, progress.MAX_ENTITIES + 1):
                def grown(root, relative):
                    data = original(root, relative)
                    if relative.endswith('/state.json'):
                        template = data['gates'][0]
                        data['gates'].extend(
                            dict(template, id=f'capacity-fixture-{i}')
                            for i in range(max(0, count - base_count)))
                    return data
                with self.subTest(count=count), patch.object(progress, 'read', grown):
                    if count > progress.MAX_ENTITIES:
                        with self.assertRaisesRegex(ValueError, '^too many dashboard entities$'):
                            progress.snapshot(ROOT)
                        with tempfile.TemporaryDirectory() as d:
                            cache = Path(d) / 'cache.json'
                            previous = '{"digest":"previous","sent_ns":1}\n'
                            cache.write_text(previous)
                            with patch.object(progress.urllib.request, 'urlopen') as send:
                                with self.assertRaisesRegex(ValueError, '^too many dashboard entities$'):
                                    progress.publish(ROOT, cache)
                                send.assert_not_called()
                            self.assertEqual(previous, cache.read_text())
                    else:
                        rows = progress.snapshot(ROOT)
                        self.assertEqual(len(rows), max(base_count, count))
                        self.assertEqual(len(history), sum(r['record_kind'] == 'workflow' for r in rows))

    def test_duplicate_inventory_entities_are_rejected(self):
        original = progress.read
        def duplicate(root, relative):
            data = original(root, relative)
            if relative.endswith('/state.json'):
                data['gates'].append(dict(data['gates'][0]))
            return data
        with patch.object(progress, 'read', duplicate):
            with self.assertRaisesRegex(ValueError, '^duplicate dashboard entities$'):
                progress.snapshot(ROOT)

    def test_absolute_and_symlink_evidence_rejected(self):
        original = progress.read
        for ref in ['/etc/passwd', '../outside', 'does-not-exist']:
            def mutated(root, relative):
                data = original(root, relative)
                if relative.endswith('/state.json'):
                    data['lanes'][0]['evidence_ref'] = ref
                return data
            with self.subTest(ref=ref), patch.object(progress,'read',mutated), self.assertRaises(ValueError):
                progress.snapshot(ROOT)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'outside.json';p.symlink_to(ROOT/'manifests/stack.json')
            with self.assertRaises(ValueError):progress.read(Path(d),'outside.json')

    def test_active_plan_drives_wave_rows_with_reference_containment(self):
        original = progress.read
        def current(root, relative):
            data = original(root, relative)
            if relative.endswith('/state.json'):
                data['plan_ref'] = 'blueprints/us-equities/simulation-research/plan.json'
            return data
        with patch.object(progress, 'read', current):
            waves = [r for r in progress.snapshot(ROOT) if r['record_kind'] == 'wave']
        self.assertTrue(any(r['entity_id'] == 'chronological_evaluation' for r in waves))
        self.assertTrue(all(r['evidence_ref'] == 'blueprints/us-equities/simulation-research/plan.json' for r in waves))
        for ref in ['/etc/passwd', '../outside']:
            def unsafe(root, relative):
                data = original(root, relative)
                if relative.endswith('/state.json'): data['plan_ref'] = ref
                return data
            with self.subTest(ref=ref), patch.object(progress,'read',unsafe), self.assertRaises(ValueError):
                progress.snapshot(ROOT)

    def test_arbitrary_source_fields_never_emitted(self):
        original = progress.read
        def mutated(root, relative):
            data=original(root,relative)
            data['private_prompt']='PRIVATE_SENTINEL'
            return data
        with patch.object(progress,'read',mutated):
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(progress.snapshot(ROOT)))

    def test_payload_generation_and_low_cardinality_labels(self):
        body=progress.payload(progress.snapshot(ROOT), 1789855000123456789)
        clocks=set()
        for stream in body['streams']:
            self.assertEqual({'service_name','record_kind'},set(stream['stream']))
            for timestamp, line in stream['values']:
                self.assertIsInstance(timestamp,str)
                clocks.add(json.loads(line)['observed_unix'])
        self.assertEqual(1,len(clocks))

    def test_failed_ingestion_does_not_advance_cache(self):
        with tempfile.TemporaryDirectory() as d:
            cache=Path(d)/'cache.json'
            with patch.object(progress.urllib.request,'urlopen',side_effect=OSError('unreachable')):
                with self.assertRaises(OSError):progress.publish(ROOT,cache)
            self.assertFalse(cache.exists())

    def test_timestamp_requires_zone(self):
        with self.assertRaises(ValueError):progress.stamp('2026-09-19T12:00:00')

    def test_workflow_history_allowlist_and_native_time(self):
        raw = [dict(name='research-pair', status='failed', startedAt='2026-09-19T17:58:33-04:00',
                    finishedAt='2026-09-19T17:59:00-04:00', dagRunId='PRIVATE_SENTINEL',
                    error='PRIVATE_SENTINEL', params='PRIVATE_SENTINEL', workerId='PRIVATE_SENTINEL')]
        self.assertTrue(hasattr(progress, 'workflow_rows'), 'workflow adapter missing')
        rows = progress.workflow_rows(raw)
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(rows))
        self.assertEqual(rows[0]['history_count'], 1)
        self.assertEqual(rows[0]['failed_count'], 1)
        self.assertEqual(rows[1]['state'], 'failed')
        self.assertEqual(rows[1]['finished_at'], '2026-09-19T21:59:00+00:00')
        self.assertEqual(rows[1]['duration_seconds'], 27)

    def test_workflow_unknown_is_not_zero_or_success(self):
        self.assertTrue(hasattr(progress, 'workflow_snapshot'), 'workflow adapter missing')
        rows = progress.workflow_snapshot()
        self.assertEqual(rows[0]['state'], 'not configured / unknown')
        self.assertNotIn('history_count', rows[0])
        with tempfile.TemporaryDirectory() as d:
            rows = progress.workflow_snapshot(Path(d)/'missing', Path(d))
        self.assertEqual(rows[0]['state'], 'unavailable / native history failed')
        self.assertNotIn('history_count', rows[0])

    def test_workflow_rejects_wrong_scope_status_and_invalid_time(self):
        self.assertTrue(hasattr(progress, 'workflow_rows'), 'workflow adapter missing')
        good = dict(name='research-pair', status='succeeded', startedAt='2026-09-19T21:00:00Z', finishedAt='2026-09-19T21:01:00Z')
        for change in [dict(name='private-other-dag'), dict(status='secret'),
                       dict(startedAt='2026-09-19T21:00:00'), dict(finishedAt='2026-09-19T20:00:00Z')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                progress.workflow_rows([good | change])
        with self.assertRaises(ValueError):progress.workflow_rows([good]*11)
        empty = progress.workflow_rows([])[0]
        self.assertEqual(empty['history_count'], 0)
        self.assertEqual(empty['state'], 'no history / last 30 days')

    def test_native_reader_bounds_and_discards_raw_error(self):
        self.assertTrue(hasattr(progress, 'history_output'), 'bounded reader missing')
        import sys
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                progress.history_output([sys.executable, '-c', 'import os;os.write(1,b"x"*200000)'], Path(d), timeout=2)
            with self.assertRaises(TimeoutError):
                progress.history_output([sys.executable, '-c', 'import time;time.sleep(2)'], Path(d), timeout=.05)
            with self.assertRaisesRegex(ValueError, '^native history failed$'):
                progress.history_output([sys.executable, '-c', 'import sys;sys.stderr.write("PRIVATE_SENTINEL");sys.exit(7)'], Path(d))

    def test_configured_adapter_fixed_command_and_failed_generation(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            binary = home/'dagu-fixture'
            expected = ['history','research-pair','--context','local','--dagu-home',d,
                        '--format','json','--last','30d','--limit','10']
            binary.write_text('#!/usr/bin/python3\nimport sys,json\nassert sys.argv[1:] == ' + repr(expected) +
                              '\nprint(json.dumps([dict(name="research-pair",status="running",startedAt="2026-09-19T22:00:00Z")]))\n')
            binary.chmod(0o700)
            rows = progress.snapshot(ROOT, binary, home)
            workflow = [r for r in rows if r['record_kind']=='workflow']
            self.assertEqual(workflow[0]['running_count'], 1)
            self.assertEqual(workflow[1]['finished_at'], 'unknown')
            self.assertNotIn('duration_seconds', workflow[1])
            binary.write_text('#!/usr/bin/python3\nimport sys\nsys.stderr.write("PRIVATE_SENTINEL")\nsys.exit(7)\n')
            rows = progress.snapshot(ROOT, binary, home)
            workflow = [r for r in rows if r['record_kind']=='workflow']
            self.assertEqual(len(workflow), 1)
            self.assertNotIn('history_count', workflow[0])
            self.assertEqual(workflow[0]['state'], 'unavailable / native history failed')
            encoded = json.dumps(progress.payload(rows, 1789855000123456789))
            self.assertNotIn('PRIVATE_SENTINEL', encoded)
            self.assertNotIn('workflow/recent-1', encoded)

    def test_workflow_dashboard_and_optional_unit_paths(self):
        board = render.dashboard()
        self.assertNotIn('127.0.0.1:18525', board['panels'][0]['options']['content'])
        table = next(p for p in board['panels'] if p['title'].startswith('Native workflow history'))
        self.assertIn('record_kind="workflow"', table['targets'][0]['expr'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            binary = root/'dagu'; binary.touch()
            with patch.object(installer.subprocess, 'run'):
                installer.install(ROOT, root/'config', root/'units', root/'data', binary, root)
            service = (root/'units/ecosystem-research-progress.service').read_text()
            # install() resolves dagu_bin/dagu_home (install.py's `optional=[Path(p).resolve() ...]`)
            # before writing them into the unit file, so a system-level symlink ancestor of the
            # temp root (macOS's /tmp -> /private/tmp, /var -> /private/var, ...) legitimately
            # changes the written path; compare against the same resolved form.
            self.assertIn(f'--dagu-bin {binary.resolve()} --dagu-home {root.resolve()}', service)
            with self.assertRaises(ValueError):installer.install(ROOT, root/'c', root/'u', root/'d', binary, None)

    def test_activity_panel_includes_codex_exec_workers(self):
        # codex exec workers log as service_name="codex_exec"; the regex once listed only the Desktop/App Server names.
        expr = next(p for p in render.dashboard()['panels'] if p['id'] == 14)['targets'][0]['expr']
        services = expr.split('"')[1].split('|')
        for service in ('codex_exec', 'codex_cli_rs', 'codex-app-server', 'claude-code', 'claude-code-desktop'):
            with self.subTest(service=service):
                self.assertIn(service, services)


if __name__=='__main__':unittest.main()
