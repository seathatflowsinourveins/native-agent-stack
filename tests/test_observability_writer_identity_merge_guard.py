"""Local source-merger controls; no host apply or service execution."""
import copy
import importlib.util
from pathlib import Path
import unittest

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(yaml, "the maintained collector merger needs PyYAML")
class MetricExportGuardMergeTests(unittest.TestCase):
    def setUp(self):
        path = ROOT / "evidence/artifacts/telemetry-writer-identity-20260926/host/merge_collector.py"
        spec = importlib.util.spec_from_file_location("metric_export_guard_merge", path)
        self.merger = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.merger)
        self.repo = yaml.safe_load((ROOT / "observability/collector/collector.yaml").read_text())
        self.host = copy.deepcopy(self.repo)
        # A valid old host with just the original metrics route and no guard definition.
        self.host["service"]["pipelines"] = {"metrics": copy.deepcopy(self.repo["service"]["pipelines"]["metrics"])}
        self.host["service"]["pipelines"]["metrics"]["processors"] = [
            "memory_limiter", "transform/privacy", "delta_to_cumulative", "batch"]
        self.host["processors"].pop("groupbyattrs/session")
        self.host["processors"].pop(self.merger.METRIC_EXPORT_GUARD)

    def test_known_guard_is_copied_before_conversion_without_mutating_inputs(self):
        before = copy.deepcopy((self.host, self.repo))
        merged = self.merger.merge(self.host, self.repo)
        guard = self.merger.METRIC_EXPORT_GUARD
        self.assertEqual(merged["processors"][guard], self.repo["processors"][guard])
        self.assertEqual(merged["service"]["pipelines"]["metrics"]["processors"],
                         self.repo["service"]["pipelines"]["metrics"]["processors"])
        self.assertEqual(self.merger.merge(merged, self.repo), merged)
        self.assertEqual((self.host, self.repo), before)

    def test_unknown_repository_processor_addition_is_refused(self):
        unknown = "transform/unreviewed"
        self.repo["processors"][unknown] = {"metric_statements": []}
        self.repo["service"]["pipelines"]["metrics"]["processors"].insert(1, unknown)
        with self.assertRaisesRegex(ValueError, "service.pipelines.metrics.processors"):
            self.merger.merge(self.host, self.repo)

    def test_guard_after_conversion_is_refused_even_when_host_order_matches(self):
        guard = self.merger.METRIC_EXPORT_GUARD
        order = self.repo["service"]["pipelines"]["metrics"]["processors"]
        order.remove(guard)
        order.insert(order.index("delta_to_cumulative") + 1, guard)
        self.host = copy.deepcopy(self.repo)
        with self.assertRaisesRegex(ValueError, "service.pipelines.metrics.processors"):
            self.merger.merge(self.host, self.repo)

    def test_existing_host_guard_settings_are_not_overwritten(self):
        guard = self.merger.METRIC_EXPORT_GUARD
        self.host["processors"][guard] = copy.deepcopy(self.repo["processors"][guard])
        self.host["processors"][guard]["error_mode"] = "silent"
        with self.assertRaisesRegex(ValueError, "processors.transform/metric_export_privacy"):
            self.merger.merge(self.host, self.repo)

    def test_missing_profile_guard_definition_is_refused(self):
        self.repo["processors"].pop(self.merger.METRIC_EXPORT_GUARD)
        with self.assertRaisesRegex(ValueError, "profile guard definition is missing"):
            self.merger.merge(self.host, self.repo)

    def test_duplicate_guard_is_refused_even_when_host_order_matches(self):
        guard = self.merger.METRIC_EXPORT_GUARD
        order = self.repo["service"]["pipelines"]["metrics"]["processors"]
        order.insert(order.index(guard), guard)
        self.host = copy.deepcopy(self.repo)
        with self.assertRaisesRegex(ValueError, "service.pipelines.metrics.processors"):
            self.merger.merge(self.host, self.repo)


if __name__ == "__main__":
    unittest.main()
