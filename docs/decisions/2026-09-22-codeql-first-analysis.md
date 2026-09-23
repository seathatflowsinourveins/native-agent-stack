# Decision: CodeQL default-setup first-analysis triage (2026-09-22)

**Decided by:** unit `nas-codeql-fixes`, worktree branch `claude/codeql-alert-fixes`, base `796f759` (newer than
the alert catalog's analysed commit `168a3a8`; PR #96 changed the generated-explorer manifest between the two,
so every alert location below was re-located at `796f759` before triage rather than trusted from the catalog).

**Scope:** the 10 open alerts from the repository's first CodeQL default-setup analysis
(commit `168a3a8`, alert numbers 1-10). Fixes cover only the flagged lines and their immediate helper
functions; no unrelated refactor. This closes the alert backlog so the planned `code_scanning` ruleset rule
(`security_alerts_threshold: high_or_higher`, `alerts_threshold: errors`) can be enabled without blocking
future work.

## Alerts

| # | Rule | Location (re-located at 796f759) | Classification | Action | Evidence |
|---|------|------------------------------------|-----------------|--------|----------|
| 1 | `js/xss-through-dom` | `docs/ecosystem/template.html:145` (`link()` sets `node.href = url`) | Defense in depth (build-side `public_url()` in `scripts/build_ecosystem.py:121-133` is the primary control: it already allows only credential-free `https:` URLs with no userinfo/loopback host into the catalog data the template renders, and `tests/test_ecosystem_manifest.py:256-271,799-802` assert `javascript:` URLs are stripped before the template ever sees them) | Fixed: added `safeHref(url)` helper that parses the URL and only assigns `href` when the protocol is `http:`/`https:`, else `about:blank`; this is a second, independent barrier at the DOM-write site in case a future data source bypasses `public_url()` | `tests/test_ecosystem_manifest.py::test_safe_href_allowlists_http_https_and_rejects_other_schemes` runs the committed helper (extracted verbatim from `template.html`, not reimplemented) under Node and asserts `javascript:`, `data:`, `vbscript:`, `file:`, and `mailto:` all resolve to `about:blank` while `https:`/`http:`/protocol-relative/relative URLs pass through unchanged; `--check` deterministic rebuild of the template |
| 2 | `js/xss-through-dom` | `docs/ecosystem/template.html:512` (`screenshot.src = "data:image/png;base64," + artifact.content_base64`) | False positive | Dismissed (not changed) | The `data:image/png;base64,` scheme prefix is a fixed source-code literal; the appended payload cannot alter the outer URI scheme, so there is no attacker-controllable sink. See `codeql-dismissals.json` entry #2. |
| 3 | `py/bad-tag-filter` | `scripts/build_ecosystem.py:704` (`re.findall(r"<script>(.*?)</script>", result, re.S)`) | Real defect | Fixed: added `re.I` so an injected uppercase `<SCRIPT>` tag is still counted/hashed into the page's inline-script CSP hash instead of silently bypassing the `require(len(scripts) == 1)` guard | `python -m unittest tests/test_ecosystem_manifest.py`; `scripts/build_ecosystem.py --check` |
| 4 | `py/bad-tag-filter` | `tests/test_claude_repository_evidence.py:147` (script-body extraction for the CSP `script-src 'sha256-...'` assertion) | Real defect (test asserts a real security property: the page admits only its own script) | Fixed: added `re.I` so the test still catches an uppercase `<SCRIPT>` tag the CSP hash would otherwise miss | `python -m unittest tests/test_claude_repository_evidence.py` |
| 5 | `py/bad-tag-filter` | `tests/test_ecosystem_manifest.py:231` (extracts the template's single inline script for a Node harness) | Real defect (robustness of the "exactly one inline script" precondition) | Fixed: added `re.I` | `python -m unittest tests/test_ecosystem_manifest.py` |
| 6 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:225` (`write_binary` fixture helper) | False positive / test-only | Dismissed (not changed) | Writes a synthetic, string-concatenation-built fake Hugging Face token to disk specifically to verify the validator's own secret scanner detects and rejects it; not a real credential. See `codeql-dismissals.json` entry #6. |
| 7 | `py/clear-text-logging-sensitive-data` | `blueprints/convergence-practice/wsl-restore/run.py:147` (`print(json.dumps({'status':report['status'],'commands':len(report['commands']),'checks':len(report['checks'])}))`) | False positive | Dismissed (not changed) | The printed sink only carries `report['status']` and two `len()` counts. CodeQL's taint path reaches it through `report`, which accumulates command records from `call()`; `call()`'s `password=` keyword only ever stores a `Path` to a 0600 password *file* (`--password-file`) in `argv`/`report`, never file contents — `private_key()` writes the random password bytes directly to that file and never returns or logs them. The finding is a keyword-name match on `password`, not a flow of secret bytes to the print. See `codeql-dismissals.json` entry #7. |
| 8 | `py/incomplete-url-substring-sanitization` | `tests/test_lifecycle_capture.py:103` (mock `Routed.get` used `"sec.gov" in url`) | Real defect (small, test-scoped) | Fixed: replaced the substring check with `urlparse(url).hostname` compared exactly (`== "sec.gov"` or `.endswith(".sec.gov")`), preserving the test's intent of distinguishing SEC-origin URLs from other publishers | `python -m unittest tests/test_lifecycle_capture.py` |
| 9 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:483` (`ScanFileForPrivateContentTests.write()` helper: `path.write_text(content, encoding="utf-8")`) | False positive / test-only | Dismissed (not changed) | This is the `write()` fixture helper shared by `ScanFileForPrivateContentTests`, not the PDF-fixture tests (those are `test_pdf_*`, lines 401-465, and write through a different `write_binary` helper — see #6). Callers of `write()` (e.g. `test_github_token_is_reported`, `test_cli_scan_file_fails_on_a_planted_secret_without_echoing_it`) pass synthetic, string-concatenation-built fake GitHub/Anthropic-style tokens to verify `scan_file_for_private_content()` and `--scan-file` detect them without echoing them back; none is a real credential. See `codeql-dismissals.json` entry #9. |
| 10 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:517` (latin-1 fallback fixture embeds a synthetic token) | False positive / test-only | Dismissed (not changed) | Same synthetic-fake-token pattern, verifying the non-UTF-8 fallback path of `scan_file_for_private_content()`. See `codeql-dismissals.json` entry #10. |

## Alternatives considered

- **Dismiss all 10 as "used in tests".** Rejected for alerts #1, #3, #4, #5, #8: each has a small, idiomatic
  fix (URL-scheme allowlisting, case-insensitive tag regex, exact hostname comparison) that keeps the
  flagged code's or test's intent and removes the actual gap, per the project's preference for a code fix
  over dismissal when the fix is small.
- **Replace the `<script>` regex scan with a real HTML parser (e.g. `html.parser`).** Considered for alerts
  #3-#5; deferred as unnecessary scope expansion — the only requirement is "does not miss an uppercase
  `<SCRIPT>` tag that a browser would still execute", which `re.I` alone satisfies without introducing a new
  dependency into a build script and two test modules.
- **Rename the `password=` parameter in `run.py`'s `call()` to sidestep CodeQL's naming heuristic.** Rejected:
  this would only game the scanner's keyword match, not fix or clarify anything; the dismissal correctly
  records why the flow is safe instead.

## Evidence class

`local_integration`: `python -m unittest` over each touched test module (and the full suite) plus
`scripts/build_ecosystem.py --check`, run from this worktree. No live GitHub Actions CodeQL re-analysis was
run locally; the hosted default-setup workflow re-analyses the PR when opened, per the task's acceptance
scope.

## Independent-review resolution (2026-09-23)

An independent reviewer of the first pass (commit `65f73e2`) found the location prose for alerts #7 and #9
pointed at the wrong code (both misidentified their sink after the `796f759` re-location), and that alert #1
lacked an executed, repeatable check of the committed `safeHref` helper. All three are resolved here:

- **#7** — corrected: the flagged sink is `run.py:147`'s `print(json.dumps(...))` of `report['status']` and
  two `len()` counts, reached through `report`'s accumulation of `call()`'s command records, not the earlier
  `call(..., password=root/'wrong-password', ...)` line. The "false positive" conclusion is unchanged (only
  a password-*file* path is ever stored, never file contents); the location description and the corresponding
  `codeql-dismissals.json` comment are now accurate.
- **#9** — corrected: the flagged sink is `ScanFileForPrivateContentTests.write()` (line 483,
  `path.write_text(content, encoding="utf-8")`), not the PDF-fixture tests (which use a separate
  `write_binary` helper and are alert #6's site). The "used in tests" conclusion is unchanged; the location
  description and dismissal comment now name the correct helper and its actual callers.
- **#1** — relabeled from "real defect" to defense in depth: `scripts/build_ecosystem.py`'s `public_url()`
  (already present before this unit's fix) is the primary control that keeps non-`https:` URLs out of the
  catalog data the template renders, with `tests/test_ecosystem_manifest.py` asserting `javascript:` URLs
  are stripped at build time. The `safeHref()` DOM-write guard remains as a second, independent barrier. Its
  "smoke check" claim, which named no runnable command, is replaced with an executed, repeatable check:
  `tests/test_ecosystem_manifest.py::test_safe_href_allowlists_http_https_and_rejects_other_schemes` extracts
  the committed helper verbatim from `template.html` (not a reimplementation) and runs it under Node,
  asserting `javascript:`, `data:`, `vbscript:`, `file:`, and `mailto:` all resolve to `about:blank` while
  `https:`/`http:`/protocol-relative/relative URLs pass through unchanged.

The reviewer's rerun also flagged a skipped-test-count mismatch (337 claimed vs. 338 observed) on the full
`python -m unittest discover` run. Re-running the full suite three times after this pass (once before and
twice after the fixes above) consistently reports `Ran 2496 tests ... OK (skipped=338)` — the count is
deterministic on this host; the original claim of 337 in the prior handoff was simply a transcription slip,
not a flake, since every independent observation since (including the reviewer's own rerun) agrees on 338.

`manifests/evidence.json`'s `sha256`/`bytes` entries for the two files this pass edited
(`tests/test_ecosystem_manifest.py`, this decision doc) were refreshed via `host_receipts.register_file()`
(the same function the project's own receipt-recording path uses) so `scripts/validate.py` stays green; this
decision doc itself was not previously registered in `files[]` and is now added.

Evidence class for this section: `local_integration` (repeated `python -m unittest`, `--check`, `validate.py`,
`validate_catalogs.py`, `evidence_manifest.py --check`, guarded `gitleaks`, all in this worktree). No live
GitHub Actions CodeQL re-analysis was run locally.
