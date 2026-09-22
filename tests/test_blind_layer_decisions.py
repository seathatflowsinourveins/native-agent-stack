"""Reject misleading adoption labels while preserving historical peer evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('blind_report_audit', ROOT / 'blueprints/blind-catalog-convergence/audit_reports.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class BlindLayerDecisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        for path in ('catalogs/landscape/foundation.json', 'catalogs/landscape/us-equities.json',
                     'catalogs/landscape/blind-convergence.json', 'docs/blind-catalog-layer-findings-20260921.md'):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / path, target)

    def mutate(self, change):
        path = self.root / 'catalogs/landscape/blind-convergence.json'
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_current_catalog_matches_canonical(self):
        self.assertEqual(AUDIT.check_layer_decisions(self.root), 20)

    def test_rejects_retain_when_comparison_is_open(self):
        self.mutate(lambda data: next(row for row in data['layers'] if row['layer_id'] == 'workers').update(coordinator_disposition='retain'))
        with self.assertRaisesRegex(AssertionError, 'workers: coordinator decision'):
            AUDIT.check_layer_decisions(self.root)

    def test_rejects_wrong_canonical_pointer(self):
        self.mutate(lambda data: data['layers'][0]['canonical_decision_ref'].update(pointer='/layers/1/decision'))
        with self.assertRaisesRegex(AssertionError, 'wrong canonical decision pointer'):
            AUDIT.check_layer_decisions(self.root)

    def test_rejects_missing_layer(self):
        self.mutate(lambda data: data['layers'].pop())
        with self.assertRaisesRegex(AssertionError, 'layer coverage'):
            AUDIT.check_layer_decisions(self.root)

    def test_rejects_handbook_promotion(self):
        path = self.root / 'docs/blind-catalog-layer-findings-20260921.md'
        path.write_text(path.read_text().replace('| workers | keep but compare |', '| workers | retain |'))
        with self.assertRaisesRegex(AssertionError, 'handbook decisions'):
            AUDIT.check_layer_decisions(self.root)

    def test_historical_peer_label_does_not_override_canonical(self):
        self.mutate(lambda data: data['layers'][0].update(claude_final_disposition='historical_source_only_judgment'))
        self.assertEqual(AUDIT.check_layer_decisions(self.root), 20)
