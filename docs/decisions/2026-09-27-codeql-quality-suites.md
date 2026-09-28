# Decision: keep CodeQL quality suites out of the merge gate for now (2026-09-27)

**Decided by:** unit `codeql` (plan move M4), branch
`claude/codeql-quality-measure-20260927`, base `ba1700a`. This is a
recommendation to the coordinator. This unit changed no workflow file,
repository setting or ruleset. The record sits beside
[the first-analysis triage](2026-09-22-codeql-first-analysis.md).

**Question.** Should code scanning move from CodeQL default setup to advanced
setup with `security-and-quality`, mirroring the live language list? The
constraints:
- Default setup offers only the `default` and `extended` suites.
- The upstream `<lang>-code-quality.qls` and `<lang>-security-and-quality.qls`
  suites need advanced setup.
- The paid GitHub Code Quality product is licensed per seat. The plan's
  landscape verdict records that it is not available to this user-owned
  repository.

**Decision.**
- Keep default setup with the `default` suite, and do not switch now.
- Keep the PATCH to `extended` deferred.
- Keep `.github/main-ruleset.json:46-53` as it is.

## Measurement

Everything below was measured at `ba1700ad`. The receipt is
[`evidence/artifacts/codeql-quality-measure-20260927/`](../../evidence/artifacts/codeql-quality-measure-20260927/README.md).

**How it ran.**
- **Engine:** CodeQL CLI 2.27.1 from release `codeql-bundle-v2.27.1` of
  `github/codeql-action`. This is the version live default setup used at
  this commit.
- **Bundle verification, before any execution:** the release asset digest,
  the published checksum and `gh release verify-asset` all passed. Each
  check failed on a negative control, as the evidence policy requires.
- **Databases:** python and javascript-typescript were built with
  `--build-mode=none`; actions needs no build mode.

**Results by suite.** The Security high+ column counts alerts with security
severity 7.0 or higher.

| Suite | Language | Results | Rules in suite (fired) | Error / warning / note | Security high+ |
| --- | --- | --- | --- | --- | --- |
| default | python | 16 | 43 (2) | 16 / 0 / 0 | 16 |
| default | javascript-typescript | 1 | 87 (1) | 0 / 1 / 0 | 1 |
| default | actions | 0 | 17 (0) | 0 / 0 / 0 | 0 |
| `security-extended` | python | 50 | 50 (4) | 17 / 33 / 0 | 50 |
| `security-extended` | javascript-typescript | 2 | 103 (2) | 0 / 2 / 0 | 2 |
| `security-extended` | actions | 0 | 23 (0) | 0 / 0 / 0 | 0 |
| `code-quality` | python | 979 | 101 (27) | 60 / 418 / 501 | 0 |
| `code-quality` | javascript-typescript | 188 | 98 (7) | 13 / 173 / 2 | 0 |
| `code-quality` | actions | 0 | **0 queries** | 0 / 0 / 0 | 0 |
| `security-and-quality` | python | 1072 | 172 (34) | 107 / 453 / 512 | 50 |
| `security-and-quality` | javascript-typescript | 190 | 201 (9) | 13 / 175 / 2 | 2 |
| `security-and-quality` | actions | 0 | 27 (0) | 0 / 0 / 0 | 0 |

**How the suites nest.**
- `security-and-quality` contains every default and code-quality result for
  both languages. Python adds 77 results beyond those two sets:
  - 33 `py/overly-permissive-file`;
  - 30 `py/uninitialized-local-variable`;
  - 11 `py/cyclic-import`;
  - 2 `py/unnecessary-delete`;
  - 1 `py/partial-ssrf`.
- JavaScript adds 1 result, `js/file-system-race`.
- Upstream froze the quality list of `security-and-quality`: github/codeql#19578
  did so for JavaScript and #19891 for Python. In the bundle this is
  `security-and-frozen-quality-selectors.yml` plus explicit ids. Newer
  quality queries therefore reach only `code-quality`. At 2.27.1 the only
  such query is `js/unhandled-error-in-stream-pipeline`, which has 0 results
  here.

**Lane split.** The split reads [`docs/lanes.md`](../lanes.md) literally.
Unlisted means `evidence/artifacts/` and the non-trading `scripts/`, which
that file does not assign.

| Suite, python | Foundation | Trading | Unlisted |
| --- | --- | --- | --- |
| default (16) | 7 | 1 | 8 (evidence) |
| `code-quality` (979) | 366 | 407 | 206 (evidence 170, scripts 36) |
| `security-and-quality` (1072) | 406 | 445 | 221 (evidence 183, scripts 38) |

For javascript-typescript, all 188 code-quality results fall in 7 captured
third-party pages under
`evidence/artifacts/gap-wave2-20260923/us-equities__market-data-reference/raw/`.
They are trading material by intent, but `lanes.md` lists only the
`blueprints/` form of that glob, so they count as unlisted. Of the 60
error-level Python code-quality results, 52 are trading, 7 foundation and 1
unlisted.

**Production parity.** For each language, the local default-suite SARIF
equals the live default-setup SARIF of the same commit. The comparison
treats both as multisets of (rule, path, line, column):
- python: 16 = 16 results, 43 = 43 rules;
- javascript-typescript: 1 = 1 results, 87 = 87 rules;
- actions: 0 = 0 results, 17 = 17 rules.

The actions result match is vacuous; only its rule set is a real match. The
same comparator reports `identical=false` when given the local code-quality
SARIF instead. Default setup passes extra database flags (baseline, overlay
and config), but they did not change the result set.

## Signal

**Main sample.** The brief asked for 20 code-quality alerts stratified by
language and rule, drawn with a fixed seed:
- 16 python alerts: every error-level rule, then the highest-volume rules;
- 4 javascript-typescript alerts;
- 0 actions alerts, because its code-quality suite has no queries.

Each alert was judged against its source and the definitions that its SARIF
`relatedLocations` name. The reasons are in `triage.json`.

| Id | Rule (results) | Level | Location | Verdict |
| --- | --- | --- | --- | --- |
| S01 | `py/call/wrong-arguments` (53) | error | `blueprints/us-equities/mover-v3/study/tests/test_cli.py:109` | false positive: callee resolved to another project's `run.py` |
| S02 | `py/call/wrong-named-argument` (1) | error | `blueprints/gap-wave2-20260923/restic-mtime-sparse-uid/extend_fixture.py:57` | false positive: callee resolved to the wrong `fixture.py` |
| S03 | `py/regex/unmatchable-dollar` (1) | error | `tools/sota-convergence/codex_lane.py:339` | false positive: the pattern, executed, matches through that `$` |
| S04 | `py/side-effect-in-assert` (4) | error | `blueprints/convergence-practice/worker-recovery/native_audit.py:161` | false positive: a read-only `git diff` |
| S05 | `py/unused-loop-variable` (1) | error | `tools/sota-convergence/adjudicate.py:800` | false positive: an intentional `_attempt` retry loop |
| S06 | `py/file-not-closed` (248) | warning | `blueprints/gap-wave2-20260923/foundation__quality-evaluation/build_typesafe_extension.py:76` | real, hygiene |
| S07 | `py/implicit-string-concatenation-in-list` (145) | warning | `blueprints/gap-wave2-20260923/foundation__agent-sdks/build_round4.py:527` | false positive: wrapped prose |
| S08 | `py/empty-except` (137) | note | `blueprints/gap-wave2-20260923/us-equities__agents-models-workers/workers/deerflow_arm.py:37` | real, hygiene |
| S09 | `py/unused-import` (102) | note | `blueprints/gap-wave2-20260923/us-equities__backtesting-engine/lean_alpaca_brokerage_oracle.py:22` | real, hygiene |
| S10 | `py/import-and-import-from` (93) | note | `tests/test_adaptive_paper_runner.py:4469` | real, hygiene |
| S11 | `py/repeated-import` (49) | note | `tests/test_adaptive_paper_runner.py:3448` | real, hygiene |
| S12 | `py/unused-local-variable` (31) | note | `tests/test_adaptive_paper_selector.py:265` | real, hygiene |
| S13 | `py/ineffectual-statement` (23) | note | `blueprints/us-equities/adaptive-paper/selector.py:57` | false positive: a `typing.Protocol` stub |
| S14 | `py/mixed-returns` (21) | note | `tests/test_native_token_ci.py:1612` | false positive: the fall-through calls `self.fail` |
| S15 | `py/imprecise-assert` (17) | note | `tests/test_native_dashboard_data.py:153` | real, hygiene |
| S16 | `py/catch-base-exception` (11) | note | `blueprints/us-equities/engine-nautilus/spy-parity/distribution_module.py:165` | real, reliability: swallows interrupts |
| S17 | `js/overwritten-property` (13) | error | `evidence/.../raw/6-nyse-hours-calendars.html:59` | real, not actionable: an artifact of our UUID redaction |
| S18 | `js/duplicate-property` (149) | warning | `evidence/.../raw/14-wayback-nyse-20240111002222.html:442` | real, not actionable: the same redaction artifact |
| S19 | `js/duplicate-html-attribute` (12) | warning | `evidence/.../raw/7-sec-accessing-edgar-data-wb20260821.html:1620` | real, not actionable: third-party markup |
| S20 | `js/use-of-returnless-function` (11) | warning | `evidence/.../raw/14-wayback-nyse-20170301172132.html:602` | real, not actionable: a third-party bug |

Totals:
- 8 false positives.
- 8 real and actionable: 7 hygiene findings and 1 reliability finding.
- 4 real but not actionable.
- Error-level alerts: 0 of 6 actionable (5 false positives, 1 not
  actionable).

**Supplement.** These rules come only with `security-and-quality`, and
`extended` also brings the security ones. The current thresholds act on all
of them.

| Id | Rule (results) | Level or severity | Verdict |
| --- | --- | --- | --- |
| X01, X02 | `py/uninitialized-local-variable` (30) | error | false positive: the `except` branch calls `self.skipTest`, which always raises |
| X03, X04 | `py/overly-permissive-file` (33) | high, 7.8 | false positive: negative permission tests on a TemporaryDirectory, restored in `finally` |
| X05 | `py/partial-ssrf` (1) | critical, 9.1 | false positive: a loopback-bound reverse proxy to a fixed upstream |
| X06 | `js/file-system-race` (1) | high, 7.7 | false positive: the write uses the exclusive `wx` flag |

**Population checks.** These are structural checks over each whole rule, not
per-result verdicts; details are in `heuristics.json`.
- `py/call/wrong-arguments` and `py/call/wrong-named-argument`: all 54
  resolved callees lie in another project. In 52 cases the caller's own
  project holds a module of the same name, which is the one its `sys.path`
  import loads. The repository tracks 24 `run.py` and 7 `fixture.py`
  modules.
- `py/uninitialized-local-variable`: 22 of 30 results follow a
  never-returning call within 8 lines.
- `py/implicit-string-concatenation-in-list`: in 139 of 145 results every
  literal boundary carries whitespace. The other 6 were read by hand, and
  all are intentional.
- `py/file-not-closed`: 114 of 248 results sit under `evidence/`.

**Volume-weighted estimate.** This applies each sampled verdict to its whole
rule and treats rule results under `evidence/` as not actionable.

Python code-quality, 979 results:

| Class | Results | Levels |
| --- | --- | --- |
| False positive | 249 | all 60 error-level results |
| Real, hygiene | 521 | 387 note, 134 warning |
| Real, reliability | 10 | note |
| Not actionable (evidence) | 157 | |
| Unsampled rules | 42 | |

JavaScript code-quality: all 188 results are not actionable (185 from
sampled rules and 3 from unsampled rules, all under `evidence/`).

## Effect of a switch under the current ruleset

The `code_scanning` rule has two thresholds:
- `security_alerts_threshold: high_or_higher` applies to alerts that carry a
  security severity;
- `alerts_threshold: errors` applies to the other alerts.

With the default suite, every alert at this commit carries a security
severity, so the `errors` threshold has nothing to act on.
`security-and-quality` would feed it 90 Python and 13 JavaScript error-level
results:
- Every Python error-level rule was sampled: 7 of the 90 results, all false
  positives.
- The population checks tie 74 of the 84 results of the two largest rules to
  the same false-positive patterns.
- All 13 JavaScript results sit in captured evidence pages.

GitHub shows an alert on a pull request only when all of its lines are in
the diff. The existing backlog therefore would not block merges, but new
code would, and the false-positive patterns are ones this repository adds
routinely:
- script modules with shared names loaded through `sys.path`;
- tests whose `except` branch calls `self.skipTest` after an optional import;
- underscore-named retry loops;
- negative permission tests, which also trip `extended` at high severity.

The CodeQL alert list for `main` has no open alerts today: 0 open, 17
dismissed and 5 fixed (code-scanning alerts API, 2026-09-28T02:36Z). A switch
would add about 1,250 open alerts (1,056 Python, 189 JavaScript). 363 of them
(175 Python, 188 JavaScript) would sit in hash-listed evidence bytes that must
not be edited.

## Recommendation

Keep default setup, for four measured reasons:
1. **The gate-relevant part of the quality signal is noise at this commit.**
   It would block pull requests on false positives.
2. **The useful part is hygiene the gate ignores.** By the volume-weighted
   estimate, about 530 notes and warnings in maintained Python are real
   (unused and repeated imports, silent `except`, unclosed one-line `open`,
   imprecise asserts), and 1 sampled finding (S16) is a real reliability
   issue. None of them reaches the `errors` threshold.
3. **Two languages add no maintained-code quality signal.** JavaScript
   quality results come only from captured pages, and actions has no
   quality queries at all.
4. **A switch costs more than it returns.** It needs:
   - an advanced-setup workflow to maintain, with a hand-mirrored language
     list;
   - SHA pins. The repository's `github/codeql-action` pin, v4.38.1
     (`1c5b6756`), links CLI 2.27.0 through `src/defaults.json`, one release
     behind this measurement, until Dependabot moves it to v4.38.2
     (`2892aa5e`, CLI 2.27.1) or later;
   - disabling default setup first, because default setup disables other
     CodeQL workflows and blocks CodeQL analysis uploads (GitHub docs, "Two
     CodeQL workflows").

The real findings in S06, S08 to S12, S15 and S16 can be fixed in ordinary
lane work without any setup change.

## Deferred fallback: PATCH default setup to `extended`

Measured at `ba1700ad`, `extended` adds 35 alerts, all high or critical:

| Language | Alerts added |
| --- | --- |
| Python | 33 `py/overly-permissive-file` (7.8), 1 `py/partial-ssrf` (9.1) |
| JavaScript | 1 `js/file-system-race` (7.7) |

All four sampled alerts (X03 to X06) are false positives in context. Under
`high_or_higher`, each pattern would block a pull request that adds another
instance. The PATCH stays deferred and was not run:

```sh
gh api -X PATCH repos/seathatflowsinourveins/native-agent-stack/code-scanning/default-setup -f query_suite=extended
```

## Alternatives considered

1. **Switch to advanced setup with `security-and-quality`, as the plan
   proposed if the signal proved useful.** Rejected for now for the reasons
   above.
2. **The same switch plus a CodeQL config file.** The file would add
   `query-filters` to exclude the false-positive-prone error-level rules and
   `paths-ignore: evidence/**`. GitHub's workflow configuration options
   support both. Rejected for now:
   - the exclusions are a hand-maintained list;
   - the path filter would also stop security scanning of `evidence/`;
   - what remains is hygiene that does not gate.
3. **`security-and-quality` with `alerts_threshold: none`.** This changes
   the ruleset, which the plan keeps, and makes quality alerts informational
   only.
4. **`security-extended` plus each language's `code-quality.qls`.** The
   gate effect is the same as option 1. It differs only by the unfrozen JS
   query, which has 0 results.
5. **A dedicated hygiene linter for the classes found real here.** Not
   measured in this unit. It would need its own sourced comparison.

## Overturn

Rerun this receipt's scripts, using the CodeQL version that default setup
then uses. Switch to advanced setup with `security-and-quality` when either
condition holds:
- a stratified sample of error-level quality results outside `evidence/` is
  at least half real and actionable (here 0 of 7 sampled Python error-level
  results: S01 to S05, X01 and X02);
- the ruleset owner decides that quality results must not block merges, in
  which case the switch is judged on hygiene value alone.

Adopt the `extended` PATCH when an `extended`-only rule yields an actionable
result in maintained code (here 0 of 4 sampled).

## Facts for a later switch

- **Languages** (default-setup GET): actions, csharp, go,
  javascript-typescript, python and rust.
- **Build modes** (logs of default-setup run 36364716716): `autobuild` for
  go and `none` for all the others. C# with `none` reported 77% of calls
  with a call target, below its 85% threshold.
- **Template:** `actions/starter-workflows@fbc8bd851e74a7296904aa1a44ac0edded32deaf`,
  `code-scanning/codeql.yml`.
- **Checkout:** mirror the repository's `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1`
  (v7.0.1) with `persist-credentials: false`, which all 30 checkouts here
  use, plus the `step-security/harden-runner` step.
- **Permissions:** `contents: read` at the top level and
  `security-events: write` on the job. The starter's `packages: read` and
  `actions: read` serve private packs and private repositories.
- **Pin and order:** pin `github/codeql-action` init and analyze by SHA at a
  release that links the CLI version being measured. Disable default setup
  before the first upload.

## Evidence classes

- **upstream-unchanged:**
  - the CodeQL 2.27.1 runs and suites;
  - bundle verification through GitHub's native verifiers, each with a
    failing negative control.
- **our-integration:**
  - the counts, lane split and overlap calculations;
  - the parity comparison and its failing control;
  - the seeded draw, population checks and extrapolation;
  - the 26 verdicts, which are this unit's reading of the source.
- **live-run-pending:**
  - no advanced-setup or `extended` analysis ran on GitHub;
  - merge-protection behaviour on a real pull request is taken from
    GitHub's docs, not observed;
  - csharp, go and rust were not analysed locally. Their live default-suite
    analyses have 0 results each.

## Sources

- **Bundle:** `github/codeql-action` release `codeql-bundle-v2.27.1`, asset
  `codeql-bundle-linux64.tar.gz`, sha256 `1d380f79…c6b815`.
- **Suite and selector files** in that bundle.
- **Frozen quality list:** github/codeql#19578 (JavaScript) and #19891
  (Python).
- **Action pins:** `github/codeql-action` `src/defaults.json` at v4.38.1 and
  v4.38.2.
- **Starter workflow:** `actions/starter-workflows@fbc8bd85`,
  `code-scanning/codeql.yml`.
- **GitHub Docs, fetched 2026-09-28 UTC:**
  - code-scanning alerts: severity, security severity, alerts in pull
    requests;
  - CodeQL query suites;
  - workflow configuration options;
  - rulesets, "Require code scanning results";
  - set code scanning merge protection;
  - "Two CodeQL workflows";
  - GitHub Code Quality, availability and billing.
- **Live records:** the `code-scanning/default-setup` and
  `code-scanning/analyses` API responses, the six default-setup SARIF
  files, and the logs of run 36364716716.
