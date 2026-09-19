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


class GrandDashboardTests(unittest.TestCase):
    def test_snapshot_is_bounded_public_fields(self):
        rows = progress.snapshot(ROOT)
        self.assertLessEqual(len(rows), 80)
        self.assertGreater(sum(r['record_kind'] == 'decision' for r in rows), 0)
        allowed = {'record_kind','entity_id','title','state','evidence_ref','source_updated_at','number'}
        extra = {'equity_usd','drawdown_pct','fees_usd','fill_count','margin_call_count'}
        self.assertTrue(all(set(r) == allowed | (extra if r['record_kind']=='experiment' else set()) for r in rows))
        self.assertEqual(1, sum(r['entity_id'] == 'snapshot' for r in rows))

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


if __name__=='__main__':unittest.main()
