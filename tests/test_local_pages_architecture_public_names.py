"""The complete publisher exposes denied inventory as counts, never names."""

from contextlib import redirect_stdout
import io
import json
import unittest

from tests import test_local_pages_architecture_read_boundary as boundary


class PublishedNamePrivacy(unittest.TestCase):
    def setUp(self):
        self.fixture = boundary.ArchitectureReadBoundaryTests(
            "test_real_build_binds_retained_identity_without_native_sdk_reads")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.denied = (
            self.fixture.user / ".config/systemd/user/synthetic-calendar-fixture.service",
            self.fixture.user / ".agents/skills/synthetic-lab-fixture/SKILL.md",
            self.fixture.user / ".codex/agents/synthetic-assistant-fixture.toml",
        )
        self.tokens = (b"synthetic-calendar-fixture", b"synthetic-lab-fixture",
                       b"synthetic-assistant-fixture")
        for path in self.denied:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic ungranted target; content must remain unread.\n", encoding="utf-8")
        self.targets = (*self.denied, self.denied[1].parent)

    def assert_every_served_file_is_private(self):
        served = [path for path in self.fixture.output.rglob("*") if path.is_file()]
        self.assertTrue(served)
        self.assertTrue(any(path.name == "architecture.html" for path in served))
        self.assertTrue(any(path.parent.name == "layers" for path in served))
        leaks = []
        for path in served:
            raw = path.read_bytes()
            for token in self.tokens:
                if token in raw:
                    leaks.append((path.relative_to(self.fixture.output).as_posix(), token.decode()))
        self.assertFalse(leaks, "ungranted synthetic identifiers reached served outputs: " + repr(leaks))

    def guarded(self, operation):
        with boundary.observed_forbidden_targets(self.targets) as calls, self.fixture.read_guard():
            result = operation()
        self.assertEqual(calls, {kind: [] for kind in ("open", "metadata", "resolve", "hash")})
        return result

    def refresh(self):
        fixture = self.fixture
        return self.guarded(lambda: boundary.builder.refresh_if_changed(
            fixture.root, fixture.state, fixture.output, fixture.receipt))

    def test_complete_builder_cli_preserves_availability_without_publishing_ungranted_names(self):
        fixture = self.fixture
        stream = io.StringIO()
        with redirect_stdout(stream):
            rc = self.guarded(lambda: boundary.builder.main([
                "--root", str(fixture.root), "--state-root", str(fixture.state),
                "--output-dir", str(fixture.output), "--receipt", str(fixture.receipt)]))
        self.assertEqual(rc, 0)
        result = json.loads(fixture.receipt.read_text())
        self.assertEqual(result["rendered_layer_count"], 1)
        self.assertEqual(result["canonical_layer_count"], 1)
        self.assertGreater(result["detail_file_count"], 0)
        self.assertEqual(json.loads(stream.getvalue())["rendered_layer_count"], 1)
        self.assert_every_served_file_is_private()
        counts = result["unapproved_inventory_counts"]
        self.assertGreaterEqual(counts["total"], 3)
        self.assertEqual(counts["total"], sum(row["count"] for row in counts["by_kind_root"]))
        self.assertTrue(any(row["root"] == "user" and row["count"] > 0 for row in counts["by_kind_root"]))
        self.assertEqual(result["unapproved_inventory_items"], counts["total"])
        for token in self.tokens:
            self.assertNotIn(token.decode(), json.dumps(result))

    def test_corrected_build_removes_old_unsafe_detail_before_publication(self):
        fixture = self.fixture
        self.refresh()
        stale = fixture.output / "architecture/layers/obsolete-0123456789abcdef.html"
        stale.write_bytes(b"Old unsafe detail: " + b" ".join(self.tokens))
        unrelated = fixture.output / "operator-note.html"
        unrelated.write_bytes(b"Unrelated operator output remains available.")
        result = self.guarded(lambda: boundary.builder.build(
            fixture.root, fixture.state, fixture.output, fixture.receipt))
        self.assertEqual(result["rendered_layer_count"], 1)
        self.assertFalse(stale.exists())
        self.assertEqual(unrelated.read_bytes(), b"Unrelated operator output remains available.")
        self.assert_every_served_file_is_private()

    def test_cache_hit_removes_stale_unsafe_details_and_keeps_current_publication(self):
        fixture = self.fixture
        self.refresh()
        previous = self.refresh()
        before = {name: (fixture.output / name).read_bytes() for name in previous["outputs"]}
        stale = fixture.output / "architecture/layers/obsolete-fedcba9876543210.html"
        stale.write_bytes(b"Old unsafe detail: " + b" ".join(self.tokens))
        cached = self.refresh()
        self.assertEqual(cached["generated_utc"], previous["generated_utc"])
        self.assertEqual(cached["outputs"], previous["outputs"])
        self.assertFalse(stale.exists())
        self.assertEqual({name: (fixture.output / name).read_bytes() for name in cached["outputs"]}, before)
        self.assert_every_served_file_is_private()


if __name__ == "__main__":
    unittest.main()
