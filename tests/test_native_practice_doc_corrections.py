"""The native-practice follow-up's two documentation corrections stay aligned with the sources they rest on.

Each check pins one claim that was wrong before the correction, so a later edit cannot silently restore it:

- examples/claude-native/workflows/README.md, `## Adopt`: the installer flags the step tells a reader to run exist in
  tools/adoption/install_claude_profile.py (`--only workflows`, and `--remove-workflows`, which that parser accepts
  only with `--only workflows`), and the directory the first manual step tells the reader to copy resolves from the
  README (it said `agents/`, which is not beside the README).
- docs/native-dashboards.md, the live-archive bullet: it cites the upstream v0.44.0 source line that makes
  `AGENTSVIEW_DATA_DIR` override the default directory, and its session count and date match the dated probe artifact.
  The launcher file itself is a host file, so the repository cannot read it; the probe artifact is the retained reading.

These are repository-text checks, not a run of the installer or of agentsview.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import install_claude_profile as icp  # noqa: E402

README = ROOT / "examples/claude-native/workflows/README.md"
DASHBOARDS = ROOT / "docs/native-dashboards.md"
PROBES = ROOT / "evidence/artifacts/claude-native-practice-20261009/probes-20261009.json"
UPSTREAM_DATA_DIR = ("https://github.com/kenn-io/agentsview/blob/413a87f7bfbd67b2815b1119ac51abc1efbeeaba/"
                     "internal/config/config.go#L2051-L2053")


def adopt_section() -> str:
    return README.read_text(encoding="utf-8").split("\n## Adopt\n", 1)[1].split("\n## ", 1)[0]


def live_archive_bullet() -> str:
    text = DASHBOARDS.read_text(encoding="utf-8")
    return text.split("- On the workstation the unit serves the directory its launcher sets,", 1)[1].split("\n- ", 1)[0]


class WorkflowsReadmeAdoptTests(unittest.TestCase):
    def test_the_installer_accepts_the_flags_the_step_names(self):
        args = icp.build_parser().parse_args(["--only", "workflows", "--remove-workflows"])
        self.assertEqual(args.only, ["workflows"])
        self.assertTrue(args.remove_workflows)

    def test_the_step_names_those_flags(self):
        section = adopt_section()
        self.assertIn("tools/adoption/install_claude_profile.py --only workflows", section)
        self.assertIn("`--only workflows --remove-workflows`", section)

    def test_the_first_manual_step_names_a_directory_beside_the_readme_tree(self):
        step = adopt_section().split("\n1. ", 1)[1].split("\n2. ", 1)[0]
        match = re.match(r"Copy (?:\[`([^`]+)`\]\([^)]*\)|`([^`]+)`) into", step)
        self.assertIsNotNone(match, step[:80])
        target = match.group(1) or match.group(2)
        self.assertTrue((README.parent / target).is_dir(), f"{target} does not resolve from {README.parent}")


class DashboardsLiveArchiveTests(unittest.TestCase):
    def test_the_bullet_cites_the_upstream_source_for_the_data_directory(self):
        bullet = live_archive_bullet()
        self.assertIn(UPSTREAM_DATA_DIR, bullet)
        self.assertIn("AGENTSVIEW_DATA_DIR", bullet)

    def test_the_bullet_matches_the_probe_artifact(self):
        bullet = live_archive_bullet()
        probes = json.loads(PROBES.read_text(encoding="utf-8"))
        coverage = probes["old_archive_coverage"]
        self.assertEqual(coverage["old_sessions_missing_from_live"], 0)
        self.assertIn(f"every one of its {coverage['old_sessions']:,} sessions", " ".join(bullet.split()))
        self.assertIn(f"deleted on {coverage['run_utc'][:10]}", " ".join(bullet.split()))
        self.assertIn(PROBES.relative_to(ROOT).as_posix(), bullet)


if __name__ == "__main__":
    unittest.main()
