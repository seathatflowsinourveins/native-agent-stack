"""Invariants of the published per-repository evidence bundle (structural checks only; nothing is executed)."""

import base64
import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ID = "claude-repository-evidence-20260921"
ARTIFACTS = ROOT / "evidence/artifacts" / EVIDENCE_ID
PAGE = ROOT / "docs/ecosystem/claude-repository-evidence.html"
CLASS_ORDER = ("version-help", "readiness", "functional")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class ClaudeRepositoryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = load(ROOT / "evidence/receipts" / f"{EVIDENCE_ID}.json")
        cls.results = load(ARTIFACTS / "results.json")
        cls.summary = load(ARTIFACTS / "summary.json")
        cls.provenance = load(ARTIFACTS / "provenance.json")
        cls.stack = {c["id"]: c for c in load(ROOT / "manifests/stack.json")["components"]}

    def test_every_declared_file_matches_its_recorded_size_and_hash(self):
        records = self.receipt["public_artifacts"] + self.receipt["hash_listed_artifacts_not_embedded"] + [self.receipt["page"]]
        self.assertEqual(len({r["path"] for r in records}), len(records))
        for record in records:
            with self.subTest(path=record["path"]):
                raw = (ROOT / record["path"]).read_bytes()
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (record["bytes"], record["sha256"]))
        on_disk = {p.relative_to(ROOT).as_posix() for p in ARTIFACTS.rglob("*") if p.is_file()}
        self.assertEqual(on_disk, {r["path"] for r in records if r["path"].startswith("evidence/artifacts/")})

    def test_a_functional_row_needs_a_passing_asserted_functional_command(self):
        for row in self.results["components"]:
            with self.subTest(row=row["id"]):
                passed = [c["class"] for c in row["commands"]
                          if c.get("exit") == 0 and not c.get("timed_out") and not c.get("skipped_reason") and c["assertion"]["passed"]
                          and not c.get("local_check")]  # a local integration check never counts toward the row
                if row["evidence_class"] == "functional":
                    self.assertTrue(any(c["class"] == "functional" and c.get("exit") == 0 and c["assertion"]["passed"] and c["assertion"]["results"]
                                        and not c.get("local_check") for c in row["commands"]))
                for command in row["commands"]:
                    if command.get("local_check"):
                        self.assertTrue(command.get("local_check_note"))
                        self.assertNotEqual(command["class"], "functional")
                if row["evidence_class"] in CLASS_ORDER:
                    self.assertEqual(row["evidence_class"], max(passed, key=CLASS_ORDER.index))
                else:
                    self.assertEqual(passed, [])

    def test_summary_and_provenance_agree_with_the_results(self):
        counts = {}
        for row in self.results["components"]:
            counts[row["evidence_class"]] = counts.get(row["evidence_class"], 0) + 1
        self.assertEqual(self.summary["evidence_classes"], counts)
        self.assertEqual(self.provenance["evidence_classes"], counts)
        self.assertEqual([r["id"] for r in self.summary["rows"]], [r["id"] for r in self.results["components"]])
        for brief, row in zip(self.summary["rows"], self.results["components"]):
            self.assertEqual((brief["evidence_class"], brief["sota_verdict"]), (row["evidence_class"], row["sota"]["final_verdict"]))

    def test_narrative_counts_are_bound_to_the_results(self):
        counts = {}
        for row in self.results["components"]:
            counts[row["evidence_class"]] = counts.get(row["evidence_class"], 0) + 1
        want = (counts["functional"], counts["readiness"], counts["version-help"], counts["none"])
        guide = (ROOT / "docs/claude-repository-evidence.md").read_text(encoding="utf-8")
        found = re.search(r"\*\*(\d+) rows are functional\*\*.*?\*\*(\d+) rows are readiness\*\*.*?\*\*(\d+) rows are version/help only\*\*.*?\*\*(\d+) rows have no\s+local execution evidence\*\*", guide, re.S)
        self.assertIsNotNone(found)
        self.assertEqual(tuple(int(x) for x in found.groups()), want)
        body = next(g["body"] for g in load(ROOT / "docs/ecosystem/manifest.json")["guides"] if g.get("path") == "docs/claude-repository-evidence.md")
        found = re.search(r"(\d+) rows separate (\d+) asserted functional checks, (\d+) readiness, (\d+) version/help and (\d+) rows without local execution", body)
        self.assertEqual(tuple(int(x) for x in found.groups()), (len(self.results["components"]),) + want)
        found = re.search(r"(\d+) functional rows whose declared assertion passed, (\d+) readiness rows, (\d+) version/help rows and (\d+) rows without local execution evidence", self.receipt["claim"])
        self.assertEqual(tuple(int(x) for x in found.groups()), want)
        unaudited = sum(1 for r in self.results["components"] if not r["sota"]["audited"])
        self.assertIn(f"{unaudited} in all", guide)

    def test_receipt_covers_exactly_the_selected_rows_with_execution_evidence(self):
        covered = sorted({r["catalog_id"] for r in self.results["components"]
                          if r.get("catalog_id") in self.stack and r["evidence_class"] in CLASS_ORDER})
        self.assertEqual(self.receipt["component_ids"], covered)
        for identifier in covered:
            self.assertIn(EVIDENCE_ID, self.stack[identifier]["evidence_ids"])
        for identifier, component in self.stack.items():
            if identifier not in covered:
                self.assertNotIn(EVIDENCE_ID, component["evidence_ids"])
        self.assertEqual(self.receipt["exact_saved_tokens"], {"session": None, "lifetime": None})

    def test_lifetime_figures_are_never_combined_or_promoted_to_provider_savings(self):
        lifetime = self.results["lifetime"]
        self.assertTrue(all(c["provider_tokens_saved"] is None for c in lifetime["comparisons"]))
        self.assertTrue(any(c["tokens_removed"] < 0 for c in lifetime["comparisons"]))
        self.assertIsNone(self.summary["lifetime"]["combined_figure"])
        self.assertFalse([k for k in list(lifetime) + list(lifetime["counts"]) if re.search(r"total|sum|combined|aggregate", k, re.I)])

    def test_only_reviewed_public_screenshots_are_published(self):
        listed = {Path(r["path"]).name for r in self.receipt["public_artifacts"] + self.receipt["hash_listed_artifacts_not_embedded"] if r["path"].endswith(".png")}
        shown = set()
        for dashboard in self.results["dashboards"]:
            with self.subTest(dashboard=dashboard["id"]):
                self.assertFalse(dashboard["private"])
                self.assertEqual(dashboard["review_state"], "reviewed")
                self.assertEqual(dashboard["review"]["privacy_check"], "clear")
                self.assertEqual(dashboard["review"]["image_sha256"], dashboard["image"]["sha256"])
                self.assertRegex(dashboard["image"]["path"], r"^shots/[A-Za-z0-9._-]+\.png$")
                shown.add(Path(dashboard["image"]["path"]).name)
        self.assertEqual(shown, listed)
        self.assertNotIn("private/", json.dumps(self.results))

    def test_verdicts_carry_no_superlative_and_measured_tier_is_limited(self):
        tiers = {"measured", "recorded", "none", "not-contestable", "not-audited"}
        for row in self.results["components"]:
            with self.subTest(row=row["id"]):
                self.assertNotRegex(row["sota"]["final_verdict"], r"(?i)best|sota|state.of.the.art|superior|definitive|winner|unbeaten")
                self.assertIn(row["sota"]["comparison_tier"], tiers)
                if row["sota"]["comparison_tier"] in {"measured", "recorded"}:
                    self.assertTrue(row["sota"]["tier_basis"])
        measured = sorted(r["id"] for r in self.results["components"] if r["sota"]["comparison_tier"] == "measured")
        self.assertEqual(measured, ["jcodemunch", "qmd", "toon"])
        self.assertNotIn("definitive", (json.dumps(self.results) + PAGE.read_text(encoding="utf-8")).lower())

    def test_every_current_stdout_hash_is_backed_by_a_privately_retained_stream(self):
        check = self.provenance["raw_stream_check"]
        self.assertEqual(check["current_commands_with_a_full_stdout_hash"], check["matched_to_a_retained_stdout_stream"])
        retained = {s["sha256"] for s in self.provenance["raw_streams"] if s["stream"] == "stdout"}
        current = [c["full_sha256"] for r in self.results["components"] for c in r["commands"] if c.get("full_sha256")]
        self.assertTrue(current)
        self.assertEqual(len(current), check["current_commands_with_a_full_stdout_hash"])  # recount, not the recorded pair alone
        self.assertEqual(len(self.provenance["raw_streams"]), len({(s["run"], s["component"], s["command_index"], s["stream"], s["observation"]) for s in self.provenance["raw_streams"]}))
        self.assertEqual([h for h in current if h not in retained], [])

    def test_page_admits_only_its_own_script_and_loads_images_from_the_artifact_directory(self):
        page = PAGE.read_text(encoding="utf-8")
        policy = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', page).group(1)
        self.assertIn("default-src 'none'", policy)
        self.assertIn("connect-src 'none'", policy)
        script_src = policy.split("script-src", 1)[1].split(";", 1)[0]
        self.assertNotIn("unsafe", script_src)
        bodies = [body for attrs, body in re.findall(r"<script([^>]*)>(.*?)</script>", page, re.S) if "application/json" not in attrs]
        self.assertEqual(len(bodies), 1)
        expected = "'sha256-" + base64.b64encode(hashlib.sha256(bodies[0].encode("utf-8")).digest()).decode("ascii") + "'"
        self.assertEqual(script_src.split(), [expected])
        self.assertEqual(self.results["image_base"], f"../../evidence/artifacts/{EVIDENCE_ID}/")
        self.assertNotRegex(page, r"(?:src|href)=[\"']https?://")


if __name__ == "__main__":
    unittest.main()
