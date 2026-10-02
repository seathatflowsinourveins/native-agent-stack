"""Offline tests for tools/sota-convergence/upstream_audit.py: targets come from the final catalog's standing picks,
challengers and unjudged incumbents; every flag follows its frozen threshold, measured from the observation's own time;
popularity fields never reach an observation; the build depends on the observations alone; and the committed audit
matches its committed observations."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "sota-convergence"))

import upstream_audit as audit  # noqa: E402

NOW = "2026-10-02T00:00:00+00:00"


def final_catalog():
    return {"rows": [
        {"layer_id": "memory", "blind": {"status": "compare"}, "selection_of_record": [],
         "final": {"standing_picks": ["owner/kept"], "challengers": ["Owner/Challenger", "Ubuntu 26.04 image"]}},
        {"layer_id": "workers", "blind": None,
         "selection_of_record": [{"repository": "https://github.com/owner/incumbent.git"},
                                 {"repository": "https://example.org/not-github"}],
         "final": {"standing_picks": [], "challengers": []}},
        {"layer_id": "isolation", "blind": {"status": "recommended"}, "selection_of_record": [],
         "final": {"standing_picks": ["owner/kept"], "challengers": []}},
    ]}


def observation(**overrides):
    obs = {"slug": "owner/kept", "observed_at": NOW, "archived": False, "license": "MIT",
           "head": {"sha": "abc", "date": "2026-09-30T00:00:00Z"},
           "release": {"tag": "v1", "published_at": "2026-09-01T00:00:00Z", "assets": 2, "assets_with_digest": 2,
                       "attested_assets": [{"name": "a.tar.gz", "attestations": 1}]},
           "advisories": [], "check_runs": {"total": 3, "conclusions": {"success": 3}},
           "deps_dev": {"status": "ok", "license": "MIT", "scorecard": {"date": "2026-09-28", "overall_score": 7.1}}}
    obs.update(overrides)
    return obs


class TargetTests(unittest.TestCase):
    def test_standing_picks_challengers_and_unjudged_incumbents_with_their_roles(self):
        found = audit.targets(final_catalog())
        self.assertEqual(sorted(found), ["owner/challenger", "owner/incumbent", "owner/kept"])
        self.assertEqual(found["owner/kept"], [{"layer_id": "isolation", "role": "standing_pick"},
                                               {"layer_id": "memory", "role": "standing_pick"}])
        self.assertEqual(found["owner/challenger"], [{"layer_id": "memory", "role": "challenger"}])
        self.assertEqual(found["owner/incumbent"], [{"layer_id": "workers", "role": "unjudged_incumbent"}])


class FlagTests(unittest.TestCase):
    def flags(self, **overrides):
        return audit.audit_row("owner/kept", [], observation(**overrides))["flags"]

    def test_a_healthy_repository_has_no_flag(self):
        self.assertEqual(self.flags(), [])

    def test_staleness_uses_the_ninety_day_window_from_the_observation_time(self):
        self.assertEqual(self.flags(head={"sha": "a", "date": "2026-07-04T00:00:00Z"}), [])  # 90 days
        self.assertEqual(self.flags(head={"sha": "a", "date": "2026-07-03T00:00:00Z"}), ["stale"])  # 91 days

    def test_release_flags(self):
        self.assertEqual(self.flags(release=None), ["no_release"])
        old = {"tag": "v0", "published_at": "2025-09-01T00:00:00Z", "assets": 0, "assets_with_digest": 0,
               "attested_assets": []}
        self.assertEqual(self.flags(release=old), ["old_release"])
        unattested = {"tag": "v1", "published_at": "2026-09-01T00:00:00Z", "assets": 2, "assets_with_digest": 2,
                      "attested_assets": [{"name": "a", "attestations": 0}]}
        self.assertEqual(self.flags(release=unattested), ["no_provenance"])

    def test_advisories_failing_checks_scorecard_and_archived(self):
        self.assertEqual(self.flags(advisories=["high"]), ["advisories"])
        self.assertEqual(self.flags(check_runs={"total": 2, "conclusions": {"failure": 1, "success": 1}}),
                         ["ci_failing"])
        self.assertEqual(self.flags(deps_dev={"status": "ok", "scorecard": {"date": "d", "overall_score": 4.9}}),
                         ["low_scorecard"])
        self.assertEqual(self.flags(archived=True), ["archived"])

    def test_a_repository_outside_the_scorecard_scan_is_not_covered_not_low(self):
        row = audit.audit_row("owner/kept", [], observation(deps_dev={"status": "ok", "scorecard": None}))
        self.assertEqual(row["scorecard"], "not_covered")
        self.assertEqual(row["flags"], [])

    def test_a_fetch_error_short_circuits(self):
        row = audit.audit_row("owner/gone", [], {"slug": "owner/gone", "observed_at": NOW, "error": "gh: HTTP 404"})
        self.assertEqual(row["flags"], ["fetch_error"])


class ObservationTests(unittest.TestCase):
    def test_popularity_fields_are_dropped(self):
        fetched = {"slug": "owner/kept", "observed_at": NOW, "stargazers_count": 9, "forks_count": 1,
                   "open_issues_count": 2, "description": "x", "language": "Go", "archived": False,
                   "default_branch": "main", "head": {"sha": "abc", "date": NOW}}

        def gh(path, timeout=60):
            if path.endswith("/releases/latest"):
                return None, "gh: Not Found (HTTP 404)"
            if "security-advisories" in path:
                return [], None
            return {"total_count": 0, "check_runs": []}, None

        with mock.patch.object(audit, "fetch_repository", return_value=dict(fetched)), \
                mock.patch.object(audit, "gh_api", side_effect=gh), \
                mock.patch.object(audit, "deps_dev", return_value={"status": "not_covered", "http_status": 404}):
            obs = audit.observe("owner/kept")
        for key in audit.POPULARITY:
            self.assertNotIn(key, obs)
        self.assertIsNone(obs["release"])
        self.assertNotIn("partial_errors", obs)


class BuildTests(unittest.TestCase):
    def test_the_build_depends_on_the_observations_alone(self):
        observations = {"collected_at": NOW, "final_catalog_sha256": "0" * 64,
                        "targets": {"owner/kept": [{"layer_id": "memory", "role": "standing_pick"}]},
                        "repositories": {"owner/kept": observation()}}
        first = audit.build(observations)
        self.assertEqual(first, audit.build(json.loads(json.dumps(observations))))
        self.assertEqual(first["by_layer"]["memory"]["standing_pick"][0]["repository"], "owner/kept")
        self.assertEqual(first["summary"]["scorecard_published"], 1)

    def test_the_committed_audit_matches_its_observations(self):
        if not (ROOT / audit.OUT).is_file():
            self.skipTest("audit not collected yet")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(audit.main(["--check"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "passed")


if __name__ == "__main__":
    unittest.main()
