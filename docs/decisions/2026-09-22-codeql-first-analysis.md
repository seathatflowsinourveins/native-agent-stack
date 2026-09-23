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
| 1 | `js/xss-through-dom` | `docs/ecosystem/template.html:145` (`link()` sets `node.href = url`) | Defense in depth (build-side filtering is the primary control: `public_url()` in `scripts/build_ecosystem.py` admits only credential-free `https:` source links, and `loopback_url()` admits only explicit `http://` or `https://` links to `127.0.0.1`/`[::1]` (this PC's dashboards); neither admits a `javascript:`/`data:` scheme, and `tests/test_ecosystem_manifest.py` asserts `javascript:` URLs are stripped before the template sees them) | Fixed: added `safeHref(url)` helper that parses the URL and only assigns `href` when the protocol is `http:`/`https:`, else `about:blank`; this is a second, independent barrier at the DOM-write site in case a future data source bypasses `public_url()` | `tests/test_ecosystem_manifest.py::test_safe_href_allowlists_http_https_and_rejects_other_schemes` runs the committed helper (extracted verbatim from `template.html`, not reimplemented) under Node and asserts `javascript:`, `data:`, `vbscript:`, `file:`, and `mailto:` all resolve to `about:blank` while `https:`/`http:`/protocol-relative/relative URLs pass through unchanged; `--check` deterministic rebuild of the template |
| 2 | `js/xss-through-dom` | `docs/ecosystem/template.html:512` (`screenshot.src = "data:image/png;base64," + artifact.content_base64`) | False positive | Dismissed (not changed) | The `data:image/png;base64,` scheme prefix is a fixed source-code literal; the appended payload cannot alter the outer URI scheme, so there is no attacker-controllable sink. See `codeql-dismissals.json` entry #2. |
| 3 | `py/bad-tag-filter` | `scripts/build_ecosystem.py` `render_from_data()` (`re.findall(r"<script>(.*?)</script>", result, re.S)`) | Robustness, not an exploitable defect: the regex reads the repository's own template, and embedded data is `<`-escaped so it cannot open or close a tag | Fixed: replaced the regex with `InlineScripts`, a stdlib `html.parser.HTMLParser` that handles tag case, `</script >` and end-tag attributes like a browser. Where html.parser and a browser disagree (a self-closing `<script/>`, a script after `<!-->` on Python 3.12), the build now fails loudly: it requires no self-closing script and requires the parser's script-start count to equal the raw `"<script"` count | Coordinator check: on the real generated page the parser and the old regex return the identical single body; `InlineScripts('<SCRIPT>x()</script >')` returns `['x()']`; `scripts/build_ecosystem.py --check`; unit tests |
| 4 | `py/bad-tag-filter` | `tests/test_claude_repository_evidence.py` CSP assertion (script-body extraction) | Robustness of a test that asserts a real property (the page admits only its own hashed script) | Fixed: `ExecutableScripts` stdlib parser (excludes `type="application/json"` blocks) instead of the regex | Same equality check on `docs/ecosystem/claude-repository-evidence.html`; `python -m unittest tests.test_claude_repository_evidence` |
| 5 | `py/bad-tag-filter` | `tests/test_ecosystem_manifest.py` Node harness (extracts the template's single inline script) | Robustness | Fixed: the test's existing `Page` parser now also collects attribute-less script bodies (`inline_scripts`) | Template equality check; `python -m unittest tests.test_ecosystem_manifest` |
| 6 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:225` (`write_binary` fixture helper) | False positive / test-only | Dismissed (not changed) | Writes a synthetic, string-concatenation-built fake Hugging Face token to disk specifically to verify the validator's own secret scanner detects and rejects it; not a real credential. See `codeql-dismissals.json` entry #6. |
| 7 | `py/clear-text-logging-sensitive-data` | `blueprints/convergence-practice/wsl-restore/run.py:147` (`print(json.dumps({'status':report['status'],'commands':len(report['commands']),'checks':len(report['checks'])}))`) | False positive | Dismissed (not changed) | The printed sink only carries `report['status']` and two `len()` counts. CodeQL's taint path reaches it through `report`, which accumulates command records from `call()`; `call()`'s `password=` keyword only ever stores a `Path` to a 0600 password *file* (`--password-file`) in `argv`/`report`, never file contents — `private_key()` writes the random password bytes directly to that file and never returns or logs them. The finding is a keyword-name match on `password`, not a flow of secret bytes to the print. See `codeql-dismissals.json` entry #7. |
| 8 | `py/incomplete-url-substring-sanitization` | `tests/test_lifecycle_capture.py:103` (mock `Routed.get` used `"sec.gov" in url`) | Real defect (small, test-scoped) | Fixed: replaced the substring check with `urlparse(url).hostname` compared exactly (`== "sec.gov"` or `.endswith(".sec.gov")`), preserving the test's intent of distinguishing SEC-origin URLs from other publishers | `python -m unittest tests/test_lifecycle_capture.py` |
| 9 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:483` (`ScanFileForPrivateContentTests.write()` helper: `path.write_text(content, encoding="utf-8")`) | False positive / test-only | Dismissed (not changed) | This is the `write()` fixture helper shared by `ScanFileForPrivateContentTests`, not the PDF-fixture tests (those are `test_pdf_*`, lines 401-465, and write through a different `write_binary` helper — see #6). Callers of `write()` (e.g. `test_github_token_is_reported`, `test_cli_scan_file_fails_on_a_planted_secret_without_echoing_it`) pass synthetic, string-concatenation-built fake GitHub/Anthropic-style tokens to verify `scan_file_for_private_content()` and `--scan-file` detect them without echoing them back; none is a real credential. See `codeql-dismissals.json` entry #9. |
| 10 | `py/clear-text-storage-sensitive-data` | `tests/test_validate.py:517` (latin-1 fallback fixture embeds a synthetic token) | False positive / test-only | Dismissed (not changed) | Same synthetic-fake-token pattern, verifying the non-UTF-8 fallback path of `scan_file_for_private_content()`. See `codeql-dismissals.json` entry #10. |

## Alternatives considered

- **Dismiss all 10 as "used in tests".** Rejected for alerts #1, #3, #4, #5, #8: each has a small, idiomatic
  fix (URL-scheme allowlisting, stdlib HTML tokenizer, exact hostname comparison) that keeps the
  flagged code's or test's intent and removes the actual gap, per the project's preference for a code fix
  over dismissal when the fix is small.
- **Add `re.I` to the `<script>` regexes (first pass).** Superseded: `py/bad-tag-filter` also flags patterns
  that miss browser-accepted end-tag variants such as `</script >`, so case-insensitivity alone would likely
  leave the three alerts open. The stdlib `html.parser` (no new dependency; the tests already used it) removes
  the heuristic instead of chasing it.
- **Dismiss #3-#5 as false positives.** Rejected: the parser replacement is small, keeps exact behaviour on the
  real pages, and needs no dismissal.
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
  (credential-free `https:` only) and `loopback_url()` (`http:`/`https:` to loopback hosts only), both present
  before this unit's fix, are the primary control that keeps other schemes out of the catalog data the
  template renders, with `tests/test_ecosystem_manifest.py` asserting `javascript:` URLs
  are stripped at build time. The `safeHref()` DOM-write guard remains as a second, independent barrier. Its
  "smoke check" claim, which named no runnable command, is replaced with an executed, repeatable check:
  `tests/test_ecosystem_manifest.py::test_safe_href_allowlists_http_https_and_rejects_other_schemes` extracts
  the committed helper verbatim from `template.html` (not a reimplementation) and runs it under Node,
  asserting `javascript:`, `data:`, `vbscript:`, `file:`, and `mailto:` all resolve to `about:blank` while
  `https:`/`http:`/protocol-relative/relative URLs pass through unchanged.

The reviewer's rerun also flagged a skipped-test-count mismatch (337 claimed vs. 338 observed) on the full
`python -m unittest discover` run. A second independent rerun of three consecutive runs showed the skip count
itself varies between runs on this host (environment-dependent skips), so neither number is a fixed
property; every run reported 0 failures and 0 errors, which is the acceptance signal.

`manifests/evidence.json`'s `sha256`/`bytes` entries for the two files this pass edited
(`tests/test_ecosystem_manifest.py`, this decision doc) were refreshed via `host_receipts.register_file()`
(the same function the project's own receipt-recording path uses) so `scripts/validate.py` stays green; this
decision doc itself was not previously registered in `files[]` and is now added.

Evidence class for this section: `local_integration` (repeated `python -m unittest`, `--check`, `validate.py`,
`validate_catalogs.py`, `evidence_manifest.py --check`, guarded `gitleaks`, all in this worktree). No live
GitHub Actions CodeQL re-analysis was run locally.
