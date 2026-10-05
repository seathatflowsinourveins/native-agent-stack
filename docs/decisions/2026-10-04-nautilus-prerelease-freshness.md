# Prerelease engine currency in the shared freshness lane — 2026-10-04

Implements unit T's final record, section 5 "Engine currency watch", PR-6, on
`3b8f9c8a1b938358d65bf422f61592dc3b89407d`. The North Star action is detecting
published NautilusTrader 2.x engine updates for the US-equities research and
broker-paper qualification lane. This is report-only currency metadata.

## Sources and bounded research

- GitHub's official REST [List releases](https://docs.github.com/en/rest/releases/releases#list-releases)
  specifies `GET /repos/{owner}/{repo}/releases`, `per_page` (maximum 100),
  `page`, and the release's `draft`, `prerelease` and `published_at` fields.
  Drafts may appear to users with push access, so the fetch explicitly filters
  them. Unpublished Git tags are not published releases.
- GitHub's official REST [Get the latest release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
  specifies `GET /repos/{owner}/{repo}/releases/latest` and excludes prereleases
  and drafts. It therefore cannot watch a pinned `2.0.0rc5` stream by itself.
  Both official sections were read on 2026-10-04 from the documentation's
  `/api/article/body?pathname=/en/rest/releases/releases` representation.
- [pypa/packaging, tag 26.0, `src/packaging/version.py`](https://github.com/pypa/packaging/blob/26.0/src/packaging/version.py)
  supplies the reference release/pre regex, spelling normalization and ordering
  (`_VERSION_PATTERN`, `_parse_letter_version`, `_cmpkey`). The integration
  follows only its major/minor/patch and alpha/beta/rc/final subset, including
  an optional leading `v` and normalized prerelease spellings. It adds no package
  dependency. Development, post, local and epoch versions remain outside this
  stream comparison. Stable pins retain the existing leading-version parser.
- The installed search-first skill's bounded inline workflow and diagnosing-bugs
  regression loop guided source selection and the failing/passing fixture. The
  documented endpoint and the existing `gh api` wrapper provide the integration;
  a new HTTP client, service, registry search or agent fan-out was unnecessary.

## Decision and alternatives

Keep `releases/latest` unchanged for stable pins. For a repository with a
prerelease pin using the release stream in the extracted working files, also request
explicit REST pages
of **100 releases, at most three pages (300 release records)**. Count every raw
record toward page exhaustion before filtering drafts and unpublished releases.
Store only compact release fields and the page/cap state.

Select the highest parsed version among non-draft, published releases whose major
matches the pin; `published_at` breaks normalized version ties. A lower version
republished later cannot hide a higher available version. Include both prereleases
and a final release in that major; compare prerelease ordinals so `rc6 > rc5`, and
a final release follows its RCs.
The manifest, trading table and workflow's fixed-tool summary use this policy.
Older snapshots without a release list are fetched again for prerelease pins.
Refetching replaces every retained record of the normalized slug, including alias
URLs and older records without a slug field, before storing the new representative.

Runtime entries with declared tag patterns use the tag path and require no release
list unless another entry of the same slug uses the release stream. A tag-list miss
retains the ordinary release fallback as display metadata; a prerelease-shaped pin
is not compared against it because it may belong to another package. Stable pins
keep their previous fallback comparison, and matched tags keep numeric comparison.
Trading and runtime dormancy include the
selected release-stream publication alongside the stable release and default-branch
head; unknown or capped selections supply no additional activity date.

Known limitation: dormancy is per row. A stable-pinned or tag-declared row ignores
a fresh RC in a release list fetched for another row, so the same repository can
appear dormant in one row and active in another. This preserves those rows'
existing stable-release activity channel and uses only a row's selected stream
evidence, excluding unused or withheld candidates. The t1 dormancy regression
deliberately keeps the stable-pin case dormant; t2 documents that limit without
changing its computation.

A short page establishes exhaustion. A full third page reports **unknown beyond
cap**, even if a candidate appeared among the records read or the history happens
to contain exactly 300 records. No fourth-page probe or unbounded `gh --paginate`
is used. The snapshot retains `pages`, `per_page`, `page_cap` and `truncated`; the
row has a null comparison with the reason `unknown beyond cap`, and the workflow
summary prints that reason. Missing or failed lists are also unknown and never
fall back to another major's stable release or an unpublished tag. Failed page
requests retain retryable `partial_errors`.

Alternatives considered:

- `releases/latest` alone: excludes the stream under watch.
- One release (`per_page=1`): a later stable 1.x backport hides a published 2.x RC.
- Unbounded pagination: violates the requested request bound.
- GraphQL releases connection: supported, but the existing REST client already
  supplies the needed fields and documented page controls without another path.

Reopen the cap if a native freshness snapshot regularly reaches it, comparing a
larger explicit bound or a GraphQL connection on the same backport, draft and
exhaustion fixtures and reporting the request cost. Reopen the version subset if
an engine's actual published tag grammar falls outside it; use the maintained
parser's supported interface rather than extending comparisons without evidence.

## Regression evidence and completeness critic

The discriminating command was
`python3 -m unittest tests.test_catalog_freshness_trading.PrereleaseCurrencyTests.test_rc6_is_drift_in_the_manifest_and_trading_report -v`.
Before the implementation it exited **1**, with
`AssertionError: 'v1.231.0' != 'v2.0.0rc6'`. The same test passes after the change.
This corrects both the excluded release channel and the prior leading-number
comparison that treated `2.0.0rc5` and `2.0.0rc6` as equal.

Synthetic fixtures exercise the actual fetch, manifest/trading comparison and
rendered report, as well as the Python read embedded in the workflow summary.
They cover a later 1.x backport on the first page with rc6 on the second, drafts,
missing publication time, another major, version ranking with publication
tie-breaking, RC numeric ordering,
the final release, a missing list, failed/malformed pages, cap exhaustion, stable
pins and resuming an older snapshot. These are local integration/fixture checks,
not an upstream test suite or a live rc6 observation.

The bounded completeness review checked release-channel coverage (stable,
prerelease, final and unpublished), pagination beyond the first result, request
failure, snapshot reuse, and both reporting consumers. It found that exposing rc6
alone was insufficient while the comparator ignored its ordinal; the regression
now checks both the selected tag and positive drift. The remaining coverage limit
is the explicit 300-record cap and the documented version subset. Feed an observed
cap or unsupported published tag back into the next engine-currency sweep.

## Workspace test environment correction

The first expanded freshness/convergence check was interrupted with exit **130**.
Its TMPDIR under `.tmp-build/` was included by the repository-copy fixtures,
recursively copying their own scratch directory. The first full-suite attempt
used `.pytest_cache/freshness` and was also interrupted with exit **130**:
`scripts/validate.py` exited **1** on Node's binary compile cache there, since
`.pytest_cache/` is not a publication-ignored root in this checkout.

The corrected TMPDIR is **`.tmp-build/.pytest_cache/freshness`**, inside this
worktree and under `nice -n 19`. The existing `.tmp-build/` ignore keeps temporary
publication files out of validation, while the original `.pytest_cache` exclusions
in `tests/test_catalog_freshness_propose.py`'s default and tracked explorer fixtures
prevent recursive copies. Only scratch directories created by these interrupted
runs were removed. Both are environment corrections, not passing acceptance
results or changes to the existing fixtures.

## Initial checks and remaining acceptance limit

The standalone check of `tests.test_catalog_freshness_pins`,
`tests.test_catalog_freshness_trading`, `tests.test_catalog_freshness_runtime` and
`tests.test_catalog_freshness_propose` ran **238 tests**, exit **0**. An earlier
expanded check exited **1** because a publication fixture copied raw temporary
test logs; another exited **1** on ENOSPC during a fixture copy. Temporary artifacts
now live under `.tmp-build/.pytest_cache/freshness-artifacts`, which the existing
copy exclusions omit. These runs and the initial failing RC fixture remain
distinct; their test counts are not added together.

The full `python3 -m unittest -v --durations 50` invocation exited **1** with
`OSError: [Errno 28] No space left on device` before completing. Before that abort,
unmodified credential fixtures reported `credential_file_permissions:ancestor`,
and blind-judge fixtures refused Git history above their workspace-contained
scratch directories. Separate invocations reproduced each refusal with exit
**1**. Full-suite acceptance therefore remains open under the required workspace
TMPDIR constraint; this record makes no full-suite pass claim. Temporary directories
owned by these runs were cleaned before the passing standalone freshness check.

`scripts/validate.py`, `scripts/evidence_manifest.py --check` and `git diff --check`
pass locally. `actionlint` is **nv** (not available on PATH); `bash -n` passes for
the changed workflow step. Registry-covered files were finalized through
`scripts/host_receipts.py`'s `register_file`; the two edited test modules were not
previously registry-covered. These checks establish integration and artifact
consistency, not a live upstream release observation or hosted CI acceptance.

## Repair round freshness-r1

The cross-family review identified an import-time dependency introduced by this
change: importing `build_manifest.py` also executed `github_freshness.py`, outside
the verdict gate's declared transitive trust paths. Following the coordinator's
decision, the exact-path load now happens lazily inside the freshness functions
that need the release policy. The import regression prohibits sibling discovery,
network calls and file read/write helpers during import; it catches the original
load regardless of an existing bytecode cache. No verdict rules were changed.

The drift-report consumer now treats release-stream uncertainty as unfetched and
prints **unknown** with the specific reason. Both `unknown beyond cap` and
`no published release in pinned major` stay out of the generic claim that a
repository has no GitHub release or tag at all. Report fixtures cover the initial
transition from a stable latest and a subsequent manifest whose latest is already
null, using either `latest_flag.reason` or `pin_comparison_reason`. Local pin
changes still use the existing drift path even when upstream is unknown.

Runtime rows with declared tag patterns retain the pre-change numeric comparison,
including a prerelease-shaped pin and a prefixed upstream tag. The new fixture
compares `1.1.0rc5` with `inspect-tool-support-1.2.0`; ordinary release-stream pins
keep their RC ordinal comparison. This is a separate tag declaration path, not an
extension of the published-release parser's documented grammar.
The three proven mistakes now have individual prevention and verification rows in
the [anti-pattern log](../harness-defaults.md#anti-pattern-log); they were missing
from that log until the PR #707 thread repair below.

The four focused regressions first exited **1**, reproducing all three findings.
An intermediate run exited **1** because the new tag fixture indexed an optional
reason field that is absent after a successful comparison; the fixture now uses
`get`. The final focused run passed four tests, exit **0**. These are synthetic
and local integration checks, not a hosted or upstream test run.

For this repair, the coordinator superseded the earlier in-worktree TMPDIR
recommendation with an owned cache directory outside both the checkout and
`/tmp`, under `nice -n 19`. Only the three touched freshness test modules and the
requested integrity checks are acceptance scope; CI owns the full-suite run.

## PR #707 review-thread repair — 2026-10-05

All five thread premises were checked against `0c5695a556312d003f31537f86f0a34a8d0d8e20`
and confirmed. The local regressions reproduced suppressed shared-repository drift
from an unused release-list failure, false dormancy beside a fresh RC, a later rc5
hiding rc7 from an rc6 pin, the three missing anti-pattern rows, and stale alias
lookups persisting through resume. No network read was needed for this repair.

The collector now excludes tag-declared runtime entries from release-stream
requirements, while foundation, trading and untagged runtime stream pins of the
same slug still require the bounded list. Tag-declared rows also bypass stream
selection, retaining the documented stable-release fallback on a tag-list miss
(t2 below withholds comparison for prerelease-shaped pins on that fallback).
Dormancy receives the definitively selected publication date for trading and
runtime rows; stable pins keep their previous dates. Candidate ranking now uses
version before publication time, with the latter only a tie-breaker. A refetch
removes all records for its normalized slug before adding the new representative,
preserving unrelated repositories and leaving every alias on the fresh snapshot.

The anti-pattern log records the three freshness-r1 mistakes individually, and
also records the four code defects proven in this thread repair. Its regression
now checks all seven freshness-r1/thread-repair rows within the contiguous Markdown
table, non-empty prevention and verification fields, and every cited class and
method at its cited path. The t1 version checked only the three freshness-r1 rows
and their first methods without verifying class ownership; t2 closes that evidence
gap and rejects removed or duplicated thread rows and invalid citations.

The first focused run exited **1** (seven tests); after refining the alias fixture
to make the canonical URL the new representative and adding the tag-miss fallback
case, the second pre-fix run exited **1** (eight tests). All five threads had a
discriminating failure. The post-fix focused run passed eight tests, exit **0**.
These are synthetic/local integration checks, not upstream or hosted execution.
The t1 targeted run covered `tests.test_catalog_freshness_runtime`,
`tests.test_catalog_freshness_propose`, `tests.test_sota_convergence`,
`scripts/validate.py`, `scripts/evidence_manifest.py --check` and `git diff --check`.
Scratch files use the authorized cache outside both the worktree and `/tmp`, under
`nice -n 19`; CI owns the full suite.

## Follow-up round freshness-t2 — 2026-10-05

The four p2 premises were confirmed against `048dc5696`, with no network read.
Alias cleanup now uses the existing URL slug normalizer and consults a retained
value's slug field only when it is a dictionary. A regression retains unrelated
null, string and list values while refetching and resuming the engine, and checks
mixed-case owner/repository and `.git` release aliases against the fresh record.

The anti-pattern check covers the seven earlier repair rows and the three new t2
mistakes. It verifies every cited `Class.method` against the class's definitions
in the named test file. Negative controls remove or duplicate each of the four
thread rows, corrupt both second-method citations, change a cited class, or rename
the declaring class in the source; every control is rejected. The uncertainty row
now qualifies its second method with its class name. Those twelve controls did not
prove AST method ownership: t3 below adds source-side method renaming and moving
with exact failure attribution.

The per-row dormancy rule and its deliberate stable-pin guard remain unchanged.
The README and rendered trading/runtime explanations now state which activity
each row considers; the known limitation is documented above. For tag-declared
prerelease pins, missing, failed, empty or unrelated tag lists keep the fallback
release visible but publish `not_compared`, null `pin_behind_upstream`, and reason
`tag_pattern_unfetched` or `tag_pattern_unmatched`. This prevents another package's
release from claiming currency. Matched tags, stable pins and the existing
watch/unresolved/truncated precedence retain their previous behavior.

Four focused tests first exited **1**: alias cleanup raised `AttributeError`, the
checker accepted all twelve invalid metadata controls, and both tag-miss fixtures
reported `compared`. The first post-fix run exited **1** because the alias fixture
also uppercased the URL scheme and host, outside the existing parser's supported
form; it now varies only owner/repository case. The final run passed all four
tests, exit **0**. These are synthetic/local integration checks. That round ran only
the three requested freshness modules and the validate, evidence-manifest and diff
checks named above, omitting the trading consumer of the changed renderer. CI owns
the full suite. Scratch stays outside the checkout and
`/tmp`, under `nice -n 19`.

## Repair round freshness-t3 — 2026-10-05

The p1 and p2 were confirmed against `dcd25f66c`. The existing trading report test
failed on the obsolete dormancy-summary sentence; its assertion now matches the
per-row wording. Trading tests are included in this round's targeted acceptance.
The renderer and dormancy computation are unchanged.

The anti-pattern controls now include source-side renaming of a cited method and
moving it to another class, leaving the log unchanged. All fourteen controls
require the exact failing subtest and its expected diagnostic; unrelated failures
and errors cannot satisfy them. A regression disables each AST check in turn and
requires failures from its specific controls. With the t2 control body, disabling
method ownership went undetected and the new regression exited **1**. The repaired
controls detect both disabled checks. The existing log row records this correction
and the new trading-consumer mistake has its own row.

The nv stable-pin coverage gap now has a fixture for both unfetched and unmatched
tag lists with a version-shaped fallback release, asserting `compared` and behind.
A guard mutation that treats stable pins as prereleases makes that fixture exit
**1**; the unchanged guard passes it. No runtime comparison behavior changed.

The first focused p1/p2 run exited **1** (two tests); the final focused run passed
four tests, exit **0**. The t2 nv reproduction also ran the four historical test
bodies against retained sources: `048dc5696` with its original checker exits **1**,
and the reviewed `dcd25f66c` exits **0**. Initial minimal snapshots omitted three
import dependencies and both exited **1**; those incomplete-fixture runs are not
evidence for the historical claim. Only the completed source snapshots are used.

Targeted acceptance includes `tests.test_catalog_freshness_trading`,
`tests.test_catalog_freshness_runtime`, `tests.test_catalog_freshness_propose`,
`tests.test_sota_convergence`, `tests.test_catalog_freshness_pins` and
`tests.test_adoption_docs_consistency.UpstreamVerificationSectionTests`, plus
`scripts/validate.py`, `scripts/evidence_manifest.py --check` and `git diff --check`.
These are local integration and artifact checks; no hosted CI observation or
full-suite pass is claimed. Scratch remains in the authorized cache outside the
checkout and `/tmp`, under `nice -n 19`.
