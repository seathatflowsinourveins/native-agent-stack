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
prerelease pin in the extracted working files, also request explicit REST pages
of **100 releases, at most three pages (300 release records)**. Count every raw
record toward page exhaustion before filtering drafts and unpublished releases.
Store only compact release fields and the page/cap state.

Select the newest `published_at` among non-draft, published releases whose parsed
major matches the pin. Include both prereleases and a final release in that major;
compare prerelease ordinals so `rc6 > rc5`, and a final release follows its RCs.
The manifest, trading table and workflow's fixed-tool summary use this policy.
Older snapshots without a release list are fetched again for prerelease pins.

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
missing publication time, another major, publication order, RC numeric ordering,
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

## Final checks and remaining acceptance limit

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
