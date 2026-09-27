"""Offline publication checks for PR-EV, not fresh tool acceptance.

Sources: full-save plan PR-EV / sections 2 and 4.1; the artifact-contract
pattern in tests/test_token_e2e_preregistration.py; Python unittest at
https://docs.python.org/3/library/unittest.html. RTK meanings come from
rtk-ai/rtk v0.50.0 src/discover/mod.rs and src/hooks/decision.rs.
"""

import hashlib
import json
from pathlib import Path
import re
import unittest
from datetime import datetime
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RTK = ROOT / "evidence/artifacts/rtk-coverage-study-20260927"
CURRENCY = ROOT / "evidence/artifacts/token-tool-currency-20260927"
TOOLS = {
    "rtk", "context-mode", "headroom", "toon", "repomix", "ccusage",
    "qmd", "markitdown", "serena", "socraticode", "ast-grep",
    "jcodemunch-mcp", "codebase-memory-mcp", "mcporter", "ai-memory",
    "context-hub", "gpt-tokenizer", "agentsview",
}


class TokenFullSaveEvidenceTests(unittest.TestCase):
    def test_all_eighteen_records_are_published(self):
        self.assertEqual({p.stem for p in (CURRENCY / "records").glob("*.json")}, TOOLS)

    def test_currency_has_separate_history_and_dated_primary_sources(self):
        for tool in sorted(TOOLS):
            with self.subTest(tool=tool):
                record = json.loads((CURRENCY / "records" / f"{tool}.json").read_text())
                self.assertEqual(record["tool"], tool)
                self.assertEqual(record["evidence_class"], "upstream-source-review")
                self.assertTrue(record["pin"])
                self.assertTrue(record["scratch_record"])
                self.assertTrue(record["behind_by"])
                self.assertTrue(record["changes_since_scratch"])
                self.assertEqual(record["retrieved_at"][:10], "2026-09-27")
                datetime.fromisoformat(record["retrieved_at"].replace("Z", "+00:00"))
                release = record["latest_release"]
                for field in ("tag_name", "published_at", "html_url", "source_url"):
                    self.assertTrue(release[field], field)
                datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
                self.assertFalse(release["draft"])
                self.assertFalse(release["prerelease"])
                self.assertEqual(urlparse(release["source_url"]).hostname, "api.github.com")
                self.assertTrue(record["key_new_findings"])
                for finding in record["key_new_findings"]:
                    self.assertTrue(finding["finding"])
                    self.assertTrue(finding["source_urls"])
                    for url in finding["source_urls"]:
                        self.assertEqual(urlparse(url).scheme, "https")
                        self.assertTrue(urlparse(url).hostname)

    def test_rtk_original_table_counts_and_fixture_bytes_are_preserved(self):
        # Independent original aggregate hash, not computed from a new receipt.
        self.assertEqual(
            hashlib.sha256((RTK / "tables.txt").read_bytes()).hexdigest(),
            "39fc4685afb0a955610ab74f389dd6a24ddda7116dc911769e1568ad0e4a74d2",
        )
        frame = (RTK / "frame-summary.txt").read_text()
        self.assertIn("TOTAL 15623 25954", frame)
        self.assertNotIn("unsupported top", frame)
        exactness = (RTK / "exactness.out").read_text()
        for label in ("T1 ", "T2 ", "T3 ", "T4 ", "T5 ", "T6 ", "T7 "):
            self.assertIn(label, exactness)
        self.assertIn("T2 diff a missing (exit code) | 050 | rc=1", exactness)
        self.assertIn("T2 diff a missing (exit code) | 467 | rc=2", exactness)
        self.assertIn("lines=42 bytes=1387", exactness)

    def test_readmes_bound_each_artifact_class_and_reproduction_limit(self):
        for directory in (RTK, CURRENCY):
            with self.subTest(directory=directory.name):
                readme = (directory / "README.md").read_text()
                self.assertIn("## Records", readme)
                self.assertIn("What it does not establish", readme)
                self.assertIn("## Sources", readme)
                for path in directory.iterdir():
                    if path.is_file() and path.name != "README.md":
                        self.assertIn(path.name, readme)
        method = (RTK / "METHOD.md").read_text()
        self.assertIn("2026-09-27 erratum", method)
        self.assertIn("not M-R1", method)
        self.assertIn("private sample", method)
        self.assertIn("not token savings", method)
        self.assertIn("synthetic", method)

    def test_public_artifacts_have_no_identifiers_or_private_paths(self):
        patterns = {
            "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            "uuid": r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
            "personal path": r"/(?:home|Users)/[^\s/]+|/tmp/claude-\d+|[A-Z]:\\Users\\",
            "bearer value": r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}",
            "credential-shaped value": r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})",
            "account or connection value": r'"(?:account|connection|request|session)[_-]?id"\s*:\s*"[^"<>]+"',
        }
        files = [p for directory in (RTK, CURRENCY) for p in directory.rglob("*") if p.is_file()]
        self.assertTrue(files)
        for path in files:
            text = path.read_text()
            for kind, pattern in patterns.items():
                with self.subTest(file=path.name, kind=kind):
                    self.assertIsNone(re.search(pattern, text, re.I), kind)


if __name__ == "__main__":
    unittest.main()
