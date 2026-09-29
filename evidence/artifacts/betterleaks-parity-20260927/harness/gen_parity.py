#!/usr/bin/env python3
"""Build evidence/artifacts/betterleaks-parity-20260927/parity.json from the scratch reports and logs
(local helper). Copies rule/file/line rows and counts from the --redact'ed reports; adds the value-blind
triage classes recorded in this run, the explorer line sizes (measure_explorer_lines.py) and the fixture
outcomes after the null-report port (run_fixtures_ported.sh). Writes no value, commit, fingerprint,
author or hex digest. Since the coordinator repair (2026-09-28) the three passphrase rows carry the
coordinator's host observation (run-record.json, coordinator_repair.passphrase_rows)."""
import collections
import json
import re
import sys
from pathlib import Path

D, out = Path(sys.argv[1]), Path(sys.argv[2])
dir_rep = json.loads((D / "reports/betterleaks-dir.json").read_text())
git_rep = json.loads((D / "reports/betterleaks-git-attempt2.json").read_text())
fx_diff = json.loads((D / "logs/fixtures-diff.json").read_text())
fx_gl = json.loads((D / "logs/fixtures-gl-fixture-classes.json").read_text())
fx_bl = json.loads((D / "logs/fixtures-bl-fixture-classes.json").read_text())
ported = {tool: json.loads((D / f"repair/fixtures-{tool}-ported.json").read_text()) for tool in ("gl", "bl")}
explorer = json.loads((D / "repair/explorer-lines.json").read_text())
assert all(f["Secret"] == "REDACTED" for f in dir_rep + git_rep)
ARMS = "blueprints/gap-wave2-20260923/us-equities__observability-hosting/"
RERUN = "evidence/artifacts/gap-resolution-20260922/recovery-portability/ai-memory-isolated-rerun-20260923/rerun-isolated.sh"

CLASS = {  # file -> (category, value-blind description); from the triage recorded in README.md
    "tests/test_codex_lane.py#generic-password": ("false_positive", "/etc/passwd inside test command strings; the matched value is a prose JSON string"),
    "tests/test_codex_lane.py#generic-credential-uri": ("fixture", "URL fixture whose password is a six-letter placeholder word"),
    "tests/test_ecosystem_manifest.py": ("fixture", "bad-URL and redaction fixtures whose password is a six-letter placeholder word"),
    "tests/test_host_requests.py": ("fixture", "URL userinfo parsing fixture; two-letter password; loopback host"),
    "observability/backends/configure.py": ("false_positive", "code expression between the quotes (a secrets.token_hex call), not a literal"),
    "blueprints/gap-wave2-20260923/us-equities__data-quality-orchestration/auth_none_with_basic_block.sh":
        ("false_positive", "printf template (%s), not a literal password"),
    ARMS + "paper_arm.sh":
        ("local_test_passphrase", "25-character passphrase (lowercase words, digits and hyphens) that the test arm exports "
                                  "for the restic repositories it initialises under its scratch-directory argument; the same "
                                  "value is in dagu_arm.sh; a fixed disposable test value, no retained repository "
                                  "(coordinator observation, 2026-09-28)"),
    ARMS + "dagu_arm.sh":
        ("local_test_passphrase", "25-character passphrase (lowercase words, digits and hyphens) that the test arm exports "
                                  "for the restic repository it initialises under its scratch-directory argument; the same "
                                  "value is in paper_arm.sh; a fixed disposable test value, no retained repository "
                                  "(coordinator observation, 2026-09-28)"),
    RERUN:
        ("local_test_passphrase", "28-character passphrase (lowercase words, an 8-digit run and hyphens) for an existing "
                                  "restic repository under a host state directory; the script lists, checks and restores "
                                  "that repository and does not create it; its comment calls the value a fixed disposable "
                                  "test string; that repository is not retained on the host that ran the script "
                                  "(coordinator observation, 2026-09-28)"),
    "catalogs/sota-convergence/sdk-runtime-coverage-20260922.json": ("false_positive", "four-word prose phrase in a catalog note about CLI login"),
    "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/raw/compare/osv-positive.json":
        ("example", "the advisory text's own username:password example URL in retained scanner output"),
    "evidence/artifacts/gap-wave2-20260923/us-equities__security-supply-chain/raw/compare/pip-audit-positive.json":
        ("example", "the advisory text's own username:password example URL in retained scanner output"),
    "blueprints/us-equities/hosting/config.yaml.example": ("placeholder", "all-caps REPLACE_... placeholder in an example config; history only"),
    "docs/ecosystem/index.html": ("digest", "64-hex content digests under a *_sha256 field of the catalog data embedded in the "
                                            "generated explorer HTML; history only (the file is no longer committed). Each finding "
                                            f"sits on a line of {explorer['line_bytes']['min']:,} to {explorer['line_bytes']['max']:,} "
                                            "bytes (measure_explorer_lines.py), and gitleaks 8.30.1 skips a git-mode fragment of "
                                            "3,000,000 bytes or more at --max-target-megabytes 2"),
}
assert explorer["findings_on_lines_of_at_least_3000000_bytes"] == explorer["findings"]


def klass(rule, path):
    return CLASS.get(f"{path}#{rule}") or CLASS[path]


dir_rows = sorted([f["RuleID"], f["File"], f["StartLine"], *klass(f["RuleID"], f["File"])] for f in dir_rep)
groups = collections.defaultdict(lambda: {"lines": set(), "findings": 0, "commits": set()})
for f in git_rep:
    g = groups[(f["RuleID"], f["File"])]
    g["lines"].add(f["StartLine"]); g["findings"] += 1; g["commits"].add(f["Commit"])
git_rows = sorted([rule, path, sorted(g["lines"]), g["findings"], len(g["commits"]), *klass(rule, path)]
                  for (rule, path), g in groups.items())
outcomes = {r["id"]: r["outcome"] for r in fx_gl["rows"]}
bl_out = {r["id"]: (r["outcome"], r["detail"]) for r in fx_bl["rows"]}
fixture_rows = []
for tid in sorted(outcomes):
    short = tid.split(".")[-1]
    d = fx_diff.get(short, {})
    fixture_rows.append({"test": tid, "gitleaks": outcomes[tid], "betterleaks": bl_out[tid][0] + (f" ({bl_out[tid][1]})" if bl_out[tid][1] else ""),
                         **({"betterleaks_empty_report_written_as_null": d["betterleaks_null_reports"]} if d.get("betterleaks_null_reports") else {}),
                         **({"missing_in_betterleaks": [r[:3] for r in d["missing_in_betterleaks"]]} if d.get("missing_in_betterleaks") else {}),
                         **({"extra_in_betterleaks": [r[:3] for r in d["extra_in_betterleaks"]]} if d.get("extra_in_betterleaks") else {})})
cat = collections.Counter(r[3] for r in dir_rows)
gcat = collections.Counter()
for r in git_rows:
    gcat[r[5]] += r[3]
passphrase_rows = [r[:3] for r in dir_rows if r[3] == "local_test_passphrase"]
assert sorted(p[1] for p in passphrase_rows) == sorted([ARMS + "dagu_arm.sh", ARMS + "paper_arm.sh", RERUN]), passphrase_rows
unported = {r["id"]: r["outcome"] for r in fx_bl["rows"]}
ported_rows = {tool: {r["id"]: r["outcome"] for r in doc["rows"]} for tool, doc in ported.items()}
doc = {
    "schema_version": 1,
    "kind": "secret_scanner_parity",
    "recorded_on": "2026-09-27",
    "baseline": "gitleaks 8.30.1 (pinned, checksum-verified linux_x64 archive)",
    "candidate": "betterleaks 1.8.1 (Sigstore- and checksum-verified linux_x64 archive)",
    "config": ".gitleaks.toml at the catalog_revision in run-record.json, passed with --config to both tools",
    "evidence_class": "our-integration: both unchanged upstream binaries executed on this host over this repository and the "
                      "unchanged tests/test_gitleaks_config.py fixtures; classification is our value-blind triage of "
                      "--redact'ed reports. Not an upstream test and not a CI run.",
    "row_formats": {"dir_mode.new_findings": ["rule", "file", "line", "category", "description"],
                    "git_mode.new_findings": ["rule", "file", "lines", "findings", "distinct_commits", "category", "description"],
                    "missing_in_betterleaks / extra_in_betterleaks": ["rule", "fixture file", "line"]},
    "dir_mode": {
        "argv": "dir . --config .gitleaks.toml --max-target-megabytes 2 --redact --no-banner --report-format json --report-path <scratch>",
        "gitleaks": {"rc": 0, "findings": 0, "bytes_scanned": 138080098, "skipped_over_2mb": 2},
        "betterleaks": {"rc": 1, "findings": len(dir_rep), "bytes_scanned": 138080098, "skipped_over_2mb": 2,
                        "by_rule": dict(collections.Counter(f["RuleID"] for f in dir_rep))},
        "new_findings": dir_rows,
        "new_findings_by_category": dict(cat),
    },
    "git_mode": {
        "argv": "git . --config .gitleaks.toml --max-target-megabytes 2 --log-opts=HEAD --redact --no-banner --report-format json --report-path <scratch>",
        "gitleaks": {"rc": 0, "findings": 0, "commits_scanned": 697, "bytes_scanned": 1156580072},
        "betterleaks": {"rc": 1, "findings": len(git_rep), "bytes_scanned": 1156384789, "commits_scanned": "not reported by betterleaks 1.8.1",
                        "by_rule": dict(collections.Counter(f["RuleID"] for f in git_rep))},
        "new_findings": git_rows,
        "new_findings_by_category": dict(gcat),
        "note": "Attempt 2 of the betterleaks scan (raised caps); attempt 1 under the host gitleaks guard's caps was stopped "
                "at 600 s with no result (run-record.json, scans).",
    },
    "fixtures": {
        "driver": "tests/test_gitleaks_config.py classes GitleaksPresenceTests, GitleaksConfigContextRestrictionTests "
                  "and GitleaksIgnoreFingerprintTests, unchanged at the base commit, run with a PATH directory whose "
                  "`gitleaks` symlink points at each verified binary, GITLEAKS_TESTS_REQUIRED=1",
        "gitleaks": {"tests_run": fx_gl["tests_run"], **fx_gl["counts"]},
        "betterleaks": {"tests_run": fx_bl["tests_run"], **fx_bl["counts"]},
        "tests": fixture_rows,
    },
    "fixtures_ported": {
        "change": "tests/test_gitleaks_config.py reads a JSON report of `null` as no findings (_findings); gitleaks writes "
                  "[] and is unaffected. Same classes, symlinks and environment as above (harness/run_fixtures_ported.sh).",
        "gitleaks": {"tests_run": ported["gl"]["tests_run"], **ported["gl"]["counts"]},
        "betterleaks": {"tests_run": ported["bl"]["tests_run"], **ported["bl"]["counts"]},
        "betterleaks_not_ok": sorted(k for k, v in ported_rows["bl"].items() if v != "ok"),
        "betterleaks_changed_by_the_port": {k: [unported[k], v] for k, v in sorted(ported_rows["bl"].items())
                                             if unported[k] != v},
    },
    "classification": {
        "superset": False,
        "missing": "fixtures only: 13 sourcegraph-access-token detections of bare 40-hex values in tests d2, d4 and d5; "
                   "betterleaks 1.8.1 requires the sgp_ prefix (config/betterleaks.toml) where gitleaks 8.30.1 also matches any "
                   "40-hex value near the keyword (config/gitleaks.toml). Both real scans had no gitleaks finding to miss.",
        "extra_in_fixtures": "3 generic-api-key detections at lines where gitleaks reported the sourcegraph rule (one per test d2, d4, d5)",
        "schema": "betterleaks writes an empty JSON report as null, gitleaks as []; 5 negative fixture tests failed on that alone "
                  "until the tests read null as no findings (fixtures_ported)",
        "new_findings": f"{len(dir_rep)} in dir mode and {len(git_rep)} in git mode, from betterleaks-only rules generic-password and "
                        "generic-credential-uri and from generic-api-key on explorer HTML that gitleaks skips by size",
        "real_secret_status": "disposable_test_values_no_retained_repository",
        "real_secret_note": "Value-blind triage matched no live credential. The three local_test_passphrase rows hold two fixed "
                            "disposable test values for synthetic fixtures, and no restic repository they protected is "
                            "retained: the coordinator's host observation of 2026-09-28 (our-integration; run-record.json, "
                            "coordinator_repair.passphrase_rows). dagu_arm.sh and paper_arm.sh initialise their repositories "
                            "under a per-run scratch-directory argument, rerun-isolated.sh comments its value as a fixed "
                            "disposable test string, and restic-filesystem-semantics.json backs up trees that fixture.py "
                            "builds. Neither the ai-memory rerun repository under the host state directory nor the "
                            "Windows-drive gap-resolution-restic* directories exist on the host that ran them, and a depth-7 "
                            "search of the home directory, /var/tmp and /tmp found no directory named restic-repo, "
                            "restic-hot or gap-resolution-restic*. Two rows sit in trading-lane paths. The 25-character value "
                            "is also in 4 retained round copies of the step script the paper arm generates "
                            "(raw/paper-arm-round5..8/cfg/hot_step.sh), and the 28-character value is also quoted in 2 "
                            "receipts of the same recovery wave, one of which records it as the password of restic round "
                            "trips that include a repository on the Windows drive. Neither scanner flags those 6 files. "
                            "Before a swap, allowlist these three rows by fingerprint, with this note as the reason.",
        "local_test_passphrase_rows": passphrase_rows,
        "triage_method": "each finding's line was re-read from the tree or from its commit, the rule's upstream regex was "
                         "re-applied at the reported byte columns, and only key text, value length, character classes, "
                         "structural shape and marker words were printed (harness/triage.py, harness/triage_history.py); "
                         "no value was printed or stored",
    },
}
out.write_text(json.dumps(doc, indent=1) + "\n")
text = out.read_text()
assert not re.search(r"\b[0-9a-f]{40}\b", text), "no 40-hex value may sit beside the sourcegraph rule id"
print(out.name, len(text), "bytes; dir rows", len(dir_rows), "git rows", len(git_rows), "fixture rows", len(fixture_rows))
