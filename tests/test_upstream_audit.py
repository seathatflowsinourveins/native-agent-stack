"""Offline tests for tools/sota-convergence/upstream_audit.py (synthetic fixtures; the last tests read the committed
audit). Targets and roles come from the definitive manifest's foundation rows; every flag follows its frozen threshold,
measured from the observation's own time; an erroring or incomplete collection stays unknown and never becomes a
negative fact, including a check-run collection on a head above GitHub's 1000-check-suite limit; each request, queried
asset and digest is recorded; popularity fields never reach an observation; role
drift fails --check; the build depends on the observations alone; the decision record's table is the audit's own; and
a blind export withholds the audit's output, observations and decision record."""

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

import blind_checkout  # noqa: E402
import upstream_audit as audit  # noqa: E402

NOW = "2026-10-02T00:00:00+00:00"
RECORD = "docs/decisions/2026-10-02-upstream-audit.md"


def slot(slot_id, state="definitive", repository="", installs_nothing_extra=False, default="x", catalog="foundation",
         resolution=None):
    return {"catalog": catalog, "layer_id": "layer", "slot_id": slot_id, "state": state, "default": default,
            "repository": repository, "installs_nothing_extra": installs_nothing_extra,
            "resolution": resolution or {"outcome": "final"}}


def manifest():
    return {"slots": [
        slot("kept", repository="https://github.com/Owner/Kept"),
        slot("action", repository="https://github.com/owner/action", installs_nothing_extra=True),
        slot("dropped", state="resolved", repository="", installs_nothing_extra=True, default="Not installed",
             resolution={"outcome": "not_installed",
                         "former_default": {"name": "Old", "repository": "https://github.com/owner/old"}}),
        slot("pair", state="", repository="https://github.com/owner/one ; https://github.com/owner/two"),
        slot("browser", state="split", installs_nothing_extra=True, default="Not installed (owner/texted or none)",
             resolution={"outcome": "split",
                         "former_default": {"name": "Kept again", "repository": "https://github.com/owner/kept"},
                         "arms": [{"name": "owner/kept", "repository": "https://github.com/owner/kept"},
                                  {"name": "Arm B", "repository": "https://github.com/owner/arm-b ; "
                                                                  "https://huggingface.co/owner/model"},
                                  {"name": "native only", "repository": ""}]}),
        slot("memory", state="measurement", installs_nothing_extra=True, default="Waits (the pick is some-name)"),
        slot("distro", repository="https://releases.example.org/1.0/"),
        slot("texted-definitive", default="owner/not-read", repository=""),
        slot("trading", catalog="us-equities", repository="https://github.com/owner/trading-only"),
    ]}


def observation(**overrides):
    obs = {"slug": "owner/kept", "observed_at": NOW, "archived": False, "license": "MIT",
           "head": {"sha": "abc", "date": "2026-09-30T00:00:00Z"},
           "release": {"tag": "v1", "published_at": "2026-09-01T00:00:00Z", "assets": 2, "assets_with_digest": 2,
                       "queried_assets": [{"name": "a.tar.gz", "digest": "sha256:aa", "attestations": 1}]},
           "advisories": {"observed": 0, "complete": True, "pages": 1, "severities": []},
           "check_runs": {"observed": 3, "total": 3, "total_counts": [3], "check_suites": 2, "complete": True,
                          "pages": 1, "conclusions": {"success": 3}},
           "deps_dev": {"status": "ok", "license": "MIT", "scorecard": {"date": "2026-09-28", "overall_score": 7.1}}}
    obs.update(overrides)
    return obs


def release(*queried, assets=2, with_digest=2):
    return {"tag": "v1", "published_at": "2026-09-01T00:00:00Z", "assets": assets, "assets_with_digest": with_digest,
            "queried_assets": list(queried)}


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.roles, self.not_audited = audit.targets(manifest())

    def test_foundation_rows_name_repositories_and_trading_rows_stay_out(self):
        self.assertEqual(sorted(self.roles), ["owner/action", "owner/arm-b", "owner/kept", "owner/old", "owner/one",
                                              "owner/texted", "owner/two"])

    def test_a_role_is_the_slot_its_state_and_whether_the_row_installs_it(self):
        self.assertEqual(self.roles["owner/kept"], [
            {"slot_id": "browser", "state": "split", "installs": False, "named_as": ["former_default", "arm", "text"]},
            {"slot_id": "kept", "state": "definitive", "installs": True, "named_as": ["repository"]}])
        # A row whose default installs nothing extra does not install its repository.
        self.assertEqual(self.roles["owner/action"], [{"slot_id": "action", "state": "definitive",
                                                        "installs": False, "named_as": ["repository"]}])
        self.assertEqual(self.roles["owner/old"], [{"slot_id": "dropped", "state": "resolved", "installs": False,
                                                     "named_as": ["former_default"]}])
        # An empty state is pinned; a field joining several URLs names each.
        for key in ("owner/one", "owner/two"):
            self.assertEqual(self.roles[key], [{"slot_id": "pair", "state": "pinned", "installs": True,
                                                "named_as": ["repository"]}])

    def test_owner_name_text_counts_only_in_split_and_measurement_rows(self):
        self.assertEqual(self.roles["owner/texted"], [{"slot_id": "browser", "state": "split", "installs": False,
                                                        "named_as": ["text"]}])
        self.assertNotIn("owner/not-read", self.roles)
        self.assertEqual(audit.owner_names("see https://github.com/a/b and c/d, 1/2 or e/f."), ["c/d", "e/f"])

    def test_urls_outside_github_and_rows_without_finalist_repositories_are_listed_not_audited(self):
        self.assertEqual(self.not_audited, [
            {"slot_id": "browser", "state": "split", "named_as": "arm", "reason": "not_github",
             "url": "https://huggingface.co/owner/model"},
            {"slot_id": "distro", "state": "definitive", "named_as": "repository", "reason": "not_github",
             "url": "https://releases.example.org/1.0/"},
            {"slot_id": "memory", "state": "measurement", "named_as": None, "reason": "finalists_without_repository",
             "url": None}])


class DriftTests(unittest.TestCase):
    ROLE = {"slot_id": "s", "state": "definitive", "installs": True, "named_as": ["repository"]}

    def test_identical_role_tables_have_no_drift(self):
        self.assertEqual(audit.drift({"a/b": [self.ROLE]}, {"a/b": [self.ROLE]}),
                         {"added": [], "removed": [], "changed": []})

    def test_a_role_change_a_removal_and_an_addition_show(self):
        changed = dict(self.ROLE, state="split", installs=False)
        moved = audit.drift({"a/b": [self.ROLE], "gone/repo": [self.ROLE]}, {"a/b": [changed], "new/repo": [self.ROLE]})
        self.assertEqual(moved["added"], ["new/repo"])
        self.assertEqual(moved["removed"], ["gone/repo"])
        self.assertEqual(moved["changed"], [{"repository": "a/b", "recorded": [self.ROLE], "current": [changed]}])

    def test_check_fails_when_the_manifest_changes_without_regeneration(self):
        if not (ROOT / audit.OUT).is_file():
            self.fail("the committed audit is missing")
        real = audit.sha256

        def changed_manifest(rel):
            return "0" * 64 if rel == audit.MANIFEST else real(rel)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(audit, "sha256", side_effect=changed_manifest), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            self.assertEqual(audit.main(["--check"]), 1)
        self.assertIn("changed since collection", err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"], "failed")

    def test_consistency_reports_a_role_change_a_removal_and_a_changed_sha(self):
        fixture = manifest()
        roles, not_audited = audit.targets(fixture)
        observations = {"manifest": {"path": audit.MANIFEST, "sha256": "s"}, "targets": roles,
                        "not_audited": not_audited}
        self.assertEqual(audit.consistency(observations, "s", fixture),
                         ([], {"added": [], "removed": [], "changed": []}))
        changed = json.loads(json.dumps(fixture))
        changed["slots"][0]["installs_nothing_extra"] = True  # the "kept" row no longer installs owner/kept
        problems, moved = audit.consistency(observations, "s", changed)
        self.assertEqual(problems, ["the role table differs from the one recorded at collection"])
        self.assertEqual([c["repository"] for c in moved["changed"]], ["owner/kept"])
        removed = json.loads(json.dumps(fixture))
        removed["slots"] = [row for row in removed["slots"] if row["slot_id"] != "action"]
        problems, moved = audit.consistency(observations, "s", removed)
        self.assertEqual((problems, moved["removed"]),
                         (["the role table differs from the one recorded at collection"], ["owner/action"]))
        problems, _ = audit.consistency(observations, "t", fixture)
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith(f"{audit.MANIFEST} changed since collection"))


class FlagTests(unittest.TestCase):
    def row(self, **overrides):
        return audit.audit_row("owner/kept", [], observation(**overrides))

    def flags(self, **overrides):
        return self.row(**overrides)["flags"]

    def test_a_healthy_repository_has_no_flag_and_nothing_incomplete(self):
        row = self.row()
        self.assertEqual(row["flags"], [])
        self.assertEqual(row["incomplete"], [])

    def test_staleness_compares_the_commit_time_with_the_ninety_day_cutoff(self):
        self.assertEqual(self.flags(head={"sha": "a", "date": "2026-07-04T00:00:01Z"}), [])  # 90 days minus 1 s
        self.assertEqual(self.flags(head={"sha": "a", "date": "2026-07-04T00:00:00Z"}), ["stale"])  # exactly 90 days
        # 90 days 12 hours: the floored day count (90) would have kept it fresh.
        self.assertEqual(self.flags(head={"sha": "a", "date": "2026-07-03T12:00:00Z"}), ["stale"])

    def test_release_flags(self):
        self.assertEqual(self.flags(release=None), ["no_release"])
        old = {"tag": "v0", "published_at": "2025-10-02T00:00:00Z", "assets": 0, "assets_with_digest": 0,
               "queried_assets": []}
        self.assertEqual(self.flags(release=old), ["old_release"])  # exactly 365 days
        self.assertEqual(self.flags(release=dict(old, published_at="2025-10-02T00:00:01Z")), [])

    def test_no_provenance_needs_every_queried_asset_to_answer_without_an_attestation(self):
        row = self.row(release=release({"name": "a", "digest": "sha256:aa", "attestations": 0},
                                       {"name": "b", "digest": "sha256:bb", "attestations": 0}))
        self.assertEqual(row["flags"], ["no_provenance"])
        self.assertEqual(row["release"]["provenance"], "none")

    def test_the_reviews_rate_limited_attestation_stays_unknown(self):
        # The review's reproduction, verbatim: it printed ['no_provenance'].
        flags = audit.audit_row("x/y", [], {"release": {"assets": 1, "assets_with_digest": 1},
                                            "partial_errors": {"attestations:a": "HTTP 429"}})["flags"]
        self.assertEqual(flags, [])
        row = audit.audit_row("x/y", [], {"release": {"assets": 1, "assets_with_digest": 1},
                                          "partial_errors": {"attestations:a": "HTTP 429"}})
        self.assertEqual(row["release"]["provenance"], "unknown")
        self.assertIn("attestations", row["incomplete"])

    def test_mixed_attestation_answers(self):
        not_found = {"name": "a", "digest": "sha256:aa", "attestations": 0}
        limited = {"name": "b", "digest": "sha256:bb", "attestations": None, "error": "HTTP 429"}
        attested = {"name": "c", "digest": "sha256:cc", "attestations": 2}
        row = self.row(release=release(not_found, limited), partial_errors={"attestations:b": "HTTP 429"})
        self.assertEqual((row["flags"], row["release"]["provenance"]), ([], "unknown"))
        self.assertIn("attestations", row["incomplete"])
        row = self.row(release=release(attested, limited), partial_errors={"attestations:b": "HTTP 429"})
        self.assertEqual((row["flags"], row["release"]["provenance"], row["release"]["attested_assets"]),
                         ([], "attested", 1))
        self.assertEqual(self.row(release=release(assets=3, with_digest=0))["release"]["provenance"], "no_digest")

    def test_an_attestation_partial_error_alone_keeps_provenance_unknown(self):
        # Every recorded asset answered 0, but an attestation request is listed as failed: the error key decides.
        answered = release({"name": "a", "digest": "sha256:aa", "attestations": 0})
        self.assertEqual(self.row(release=answered)["release"]["provenance"], "none")
        row = self.row(release=answered, partial_errors={"attestations:b": "HTTP 502"})
        self.assertEqual((row["flags"], row["release"]["provenance"]), ([], "unknown"))
        self.assertIn("attestations", row["incomplete"])

    def test_an_incomplete_check_run_collection_never_reports_zero_failing(self):
        partial = {"observed": 100, "total": 755, "complete": False, "pages": 1, "conclusions": {"success": 100}}
        row = self.row(check_runs=partial)
        self.assertEqual(row["flags"], [])
        self.assertIsNone(row["check_runs"]["failing"])
        self.assertIn("check_runs", row["incomplete"])
        # A failure seen in a partial collection is still a fact.
        row = self.row(check_runs=dict(partial, conclusions={"success": 99, "failure": 1}))
        self.assertEqual((row["flags"], row["check_runs"]["failing"]), (["ci_failing"], 1))
        # The pre-repair shape (a total and the first page's conclusions, no completeness) is incomplete.
        row = self.row(check_runs={"total": 755, "conclusions": {"success": 100}})
        self.assertIsNone(row["check_runs"]["failing"])
        self.assertEqual(self.row()["check_runs"], {"observed": 3, "total": 3, "total_counts": [3], "check_suites": 2,
                                                    "complete": True, "failing": 0})

    def test_a_head_above_the_check_suite_limit_is_incomplete(self):
        # actions/attest as collected before the limit was read: 1000 of 1000 runs over 10 pages, recorded complete,
        # while its head carried 1606 check suites, so the runs came from the 1000 most recent suites only.
        capped = {"observed": 1000, "total": 1000, "total_counts": [1000], "check_suites": 1606, "complete": True,
                  "pages": 10, "conclusions": {"queued": 1, "success": 999}}
        row = self.row(check_runs=capped)
        self.assertEqual(row["check_runs"], {"observed": 1000, "total": 1000, "total_counts": [1000],
                                             "check_suites": 1606, "complete": False, "failing": None})
        self.assertEqual((row["flags"], row["incomplete"]), ([], ["check_runs"]))
        self.assertIn("1000 most recent of 1606 check suites", audit._check_runs_gap(row))
        # The committed shape before this check (no suite count, no page totals) is incomplete too.
        legacy = {k: v for k, v in capped.items() if k not in ("check_suites", "total_counts")}
        self.assertIsNone(self.row(check_runs=legacy)["check_runs"]["failing"])
        # The limit itself: 1000 suites are read in full, 1001 are not.
        self.assertEqual(self.row(check_runs=dict(capped, check_suites=1000))["check_runs"]["failing"], 0)
        self.assertIsNone(self.row(check_runs=dict(capped, check_suites=1001))["check_runs"]["failing"])
        # A recorded complete flag cannot outvote the counts: a run short, or a total that moved between pages.
        self.assertIsNone(self.row(check_runs=dict(capped, check_suites=1, observed=999))["check_runs"]["failing"])
        moved = self.row(check_runs=dict(capped, check_suites=1, total_counts=[1000, 1001]))
        self.assertIsNone(moved["check_runs"]["failing"])
        self.assertIn("moved between pages: 1000, 1001", audit._check_runs_gap(moved))
        # A failure seen in a capped collection is still a fact.
        row = self.row(check_runs=dict(capped, conclusions={"failure": 2, "success": 998}))
        self.assertEqual((row["flags"], row["check_runs"]["failing"], row["check_runs"]["complete"]),
                         (["ci_failing"], 2, False))

    def test_an_errored_advisory_collection_reports_no_count(self):
        row = self.row(advisories={"observed": None, "complete": False}, partial_errors={"advisories": "HTTP 502"})
        self.assertIsNone(row["advisories"]["count"])
        self.assertIn("advisories", row["incomplete"])
        self.assertEqual(self.flags(advisories={"observed": 1, "complete": True, "severities": ["high"]}),
                         ["advisories"])

    def test_failing_checks_scorecard_and_archived(self):
        self.assertEqual(self.flags(check_runs={"observed": 2, "total": 2, "complete": True,
                                                "conclusions": {"failure": 1, "success": 1}}), ["ci_failing"])
        self.assertEqual(self.flags(deps_dev={"status": "ok", "scorecard": {"date": "d", "overall_score": 4.9}}),
                         ["low_scorecard"])
        self.assertEqual(self.flags(archived=True), ["archived"])

    def test_a_repository_outside_the_scorecard_scan_is_not_covered_not_low(self):
        row = self.row(deps_dev={"status": "not_covered", "http_status": 404})
        self.assertEqual((row["scorecard"], row["flags"], row["incomplete"]), ("not_covered", [], []))
        row = self.row(deps_dev={"status": "error", "http_status": 503})
        self.assertEqual((row["scorecard"], row["incomplete"]), (None, ["deps_dev"]))

    def test_a_fetch_error_short_circuits(self):
        row = audit.audit_row("owner/gone", [], {"slug": "owner/gone", "observed_at": NOW, "error": "HTTP 404"})
        self.assertEqual(row["flags"], ["fetch_error"])


class ObservationTests(unittest.TestCase):
    REPO = {"full_name": "Owner/Kept", "stargazers_count": 9, "forks_count": 1, "open_issues_count": 2,
            "description": "x", "language": "Go", "archived": False, "disabled": False, "fork": False,
            "default_branch": "main", "pushed_at": NOW, "license": {"spdx_id": "MIT"}}

    def observe(self, responses, deps=({"license": "MIT"}, 200, 1)):
        calls = []

        def gh(args, timeout=180):
            calls.append(args)
            path = args[-1]
            if path == "repos/owner/kept":
                return dict(self.REPO), None, 1
            for marker, answer in responses.items():
                if marker in path:
                    return answer
            return None, "gh: Not Found (HTTP 404)", 1

        with mock.patch.object(audit, "gh_call", side_effect=gh), mock.patch.object(audit, "http_json",
                                                                                    return_value=deps):
            return audit.observe("owner/kept"), calls

    def base(self, **extra):
        responses = {"/commits/main": ({"sha": "abc", "commit": {"committer": {"date": NOW}}}, None, 1),
                     "/releases/latest": (None, "gh: Not Found (HTTP 404)", 1),
                     "security-advisories": ([[{"ghsa_id": "GHSA-1", "severity": "low"}]], None, 1),
                     "check-runs": ([{"total_count": 0, "check_runs": []}], None, 1),
                     "check-suites": ({"total_count": 1, "check_suites": [{"id": 7}]}, None, 1)}
        responses.update(extra)
        return responses

    def test_popularity_fields_are_dropped_and_every_request_is_recorded(self):
        obs, calls = self.observe(self.base())
        for key in ("stargazers_count", "forks_count", "open_issues_count", "description", "language"):
            self.assertNotIn(key, obs)
        self.assertIsNone(obs["release"])
        self.assertNotIn("partial_errors", obs)
        self.assertEqual([r.get("path") or r.get("url") for r in obs["requests"]], [
            "repos/owner/kept", "repos/owner/kept/commits/main", "repos/owner/kept/releases/latest",
            "repos/owner/kept/security-advisories?state=published&per_page=100",
            "repos/owner/kept/commits/abc/check-runs?per_page=100",
            "repos/owner/kept/commits/abc/check-suites?per_page=1",
            "https://api.deps.dev/v3/projects/github.com%2Fowner%2Fkept"])
        self.assertEqual(obs["requests"][2]["status"], "HTTP 404")
        self.assertEqual(calls[3][:2], ["--paginate", "--slurp"])
        self.assertEqual(calls[5], ["repos/owner/kept/commits/abc/check-suites?per_page=1"])  # one page, no paginate
        # The advisories endpoint reports no total, so none is recorded.
        self.assertEqual(obs["advisories"], {"observed": 1, "complete": True, "pages": 1, "severities": ["low"]})

    def test_each_queried_asset_keeps_its_name_digest_and_answer(self):
        assets = [{"name": f"a{i}", "digest": f"sha256:{i:02d}"} for i in range(7)] + [{"name": "nd", "digest": None}]
        obs, _ = self.observe(self.base(**{
            "/releases/latest": ({"tag_name": "v1", "published_at": NOW, "assets": assets}, None, 1),
            "/attestations/sha256:00": ({"attestations": [{}, {}]}, None, 1),
            "/attestations/sha256:01": (None, "gh: Too Many Requests (HTTP 429)", 4)}))
        queried = obs["release"]["queried_assets"]
        self.assertEqual(len(queried), audit.MAX_ATTESTED_ASSETS)
        self.assertEqual(queried[0], {"name": "a0", "digest": "sha256:00", "attestations": 2})
        self.assertEqual(queried[1], {"name": "a1", "digest": "sha256:01", "attestations": None, "error": "HTTP 429"})
        self.assertEqual(queried[2], {"name": "a2", "digest": "sha256:02", "attestations": 0})
        self.assertEqual((obs["release"]["assets"], obs["release"]["assets_with_digest"]), (8, 7))
        self.assertEqual(obs["partial_errors"], {"attestations:a1": "HTTP 429"})
        attestation_requests = [r for r in obs["requests"] if "/attestations/" in r.get("path", "")]
        self.assertEqual(attestation_requests[1], {"api": "github", "path": "repos/owner/kept/attestations/sha256:01",
                                                   "status": "HTTP 429", "attempts": 4})

    def test_check_runs_are_counted_across_pages_and_a_short_collection_is_incomplete(self):
        pages = [{"total_count": 3, "check_runs": [{"id": 1, "conclusion": "success"},
                                                    {"id": 2, "conclusion": "failure"}]},
                 {"total_count": 3, "check_runs": [{"id": 3, "conclusion": None, "status": "in_progress"}]}]
        obs, _ = self.observe(self.base(**{"check-runs": (pages, None, 1)}))
        self.assertEqual(obs["check_runs"], {"observed": 3, "total": 3, "total_counts": [3], "check_suites": 1,
                                             "complete": True, "pages": 2,
                                             "conclusions": {"failure": 1, "in_progress": 1, "success": 1}})
        obs, _ = self.observe(self.base(**{"check-runs": (pages[:1], None, 1)}))
        self.assertEqual((obs["check_runs"]["observed"], obs["check_runs"]["complete"]), (2, False))
        # A run added while the pages were read moves the reported total: every distinct total is kept.
        moved = [pages[0], dict(pages[1], total_count=4)]
        obs, _ = self.observe(self.base(**{"check-runs": (moved, None, 1)}))
        self.assertEqual((obs["check_runs"]["observed"], obs["check_runs"]["total_counts"],
                          obs["check_runs"]["complete"]), (3, [3, 4], False))
        obs, calls = self.observe(self.base(**{"check-runs": (None, "gh: Server Error (HTTP 502)", 4)}))
        self.assertEqual(obs["check_runs"], {"observed": None, "total": None, "complete": False})
        self.assertEqual(obs["partial_errors"], {"check_runs": "HTTP 502"})
        self.assertFalse(any("check-suites" in call[-1] for call in calls))  # no suite count without the runs

    def test_the_check_suite_count_read_after_the_runs_decides_completeness(self):
        pages = [{"total_count": 2, "check_runs": [{"id": 1, "conclusion": "success"},
                                                    {"id": 2, "conclusion": "success"}]}]
        for suites, complete in ((1000, True), (1001, False), (1606, False)):
            obs, calls = self.observe(self.base(**{"check-runs": (pages, None, 1),
                                                   "check-suites": ({"total_count": suites}, None, 1)}))
            self.assertEqual((obs["check_runs"]["check_suites"], obs["check_runs"]["complete"]), (suites, complete))
            paths = [call[-1] for call in calls]
            self.assertLess(paths.index("repos/owner/kept/commits/abc/check-runs?per_page=100"),
                            paths.index("repos/owner/kept/commits/abc/check-suites?per_page=1"))
        # A failed suite count leaves the runs' completeness unknown.
        obs, _ = self.observe(self.base(**{"check-runs": (pages, None, 1),
                                           "check-suites": (None, "gh: Server Error (HTTP 502)", 4)}))
        self.assertEqual((obs["check_runs"]["check_suites"], obs["check_runs"]["complete"]), (None, False))
        self.assertEqual(obs["partial_errors"], {"check_suites": "HTTP 502"})
        row = audit.audit_row("owner/kept", [], obs)
        self.assertEqual((row["check_runs"]["failing"], row["incomplete"]), (None, ["check_runs"]))

    def test_an_error_outcome_carries_no_message_text(self):
        self.assertEqual(audit.outcome("gh: API rate limit exceeded for user ID 12345. (HTTP 403)"), "HTTP 403")
        self.assertEqual(audit.outcome("timeout"), "timeout")
        self.assertEqual(audit.outcome("something else entirely"), "error")


class BuildTests(unittest.TestCase):
    def observations(self):
        return {"collected_at": NOW, "manifest": {"path": audit.MANIFEST, "sha256": "0" * 64},
                "targets": {"owner/kept": [{"slot_id": "kept", "state": "definitive", "installs": True,
                                            "named_as": ["repository"]}],
                            "owner/arm": [{"slot_id": "split-slot", "state": "split", "installs": False,
                                           "named_as": ["arm"]}]},
                "not_audited": [],
                "repositories": {"owner/kept": observation(),
                                 "owner/arm": observation(slug="owner/arm", release=None)}}

    def test_the_build_depends_on_the_observations_alone(self):
        observations = self.observations()
        first = audit.build(observations)
        self.assertEqual(first, audit.build(json.loads(json.dumps(observations))))
        self.assertEqual(first["inputs"][audit.MANIFEST], "0" * 64)
        self.assertEqual(first["by_slot"]["kept"][0]["repository"], "owner/kept")
        self.assertEqual(first["summary"]["scorecard_published"], 2)
        self.assertEqual(first["summary"]["by_state"]["split"]["flag_counts"]["no_release"], 1)
        self.assertEqual(first["summary"]["installed"]["repositories"], 1)
        self.assertIn("| split | 1 | 1 | 1 |", audit.results_table(first))

    def test_the_committed_audit_matches_its_observations_and_the_manifest(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(audit.main(["--check"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["drift"], {"added": [], "removed": [], "changed": []})

    def test_the_decision_record_carries_the_audits_own_results(self):
        committed = json.loads((ROOT / audit.OUT).read_text(encoding="utf-8"))
        record = (ROOT / RECORD).read_text(encoding="utf-8")
        self.assertIn(audit.results_markdown(committed), record)
        self.assertIn(audit.results_table(committed), record)


class BlindExportTests(unittest.TestCase):
    def test_the_audit_output_observations_and_decision_record_are_withheld(self):
        for path in (audit.OUT, audit.OBSERVATIONS, RECORD):
            self.assertTrue(blind_checkout.removed_from_blind_export(path), path)

    def test_the_tool_and_its_tests_stay(self):
        for path in ("tools/sota-convergence/upstream_audit.py", "tests/test_upstream_audit.py"):
            self.assertFalse(blind_checkout.removed_from_blind_export(path), path)


if __name__ == "__main__":
    unittest.main()
