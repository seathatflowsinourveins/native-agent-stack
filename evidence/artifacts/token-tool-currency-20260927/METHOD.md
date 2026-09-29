# Currency record method (2026-09-27)

These are **upstream-source-review** receipts for the 18 token tools named in
the full-save plan section 2 and PR-EV. They compare the supplied **2026-09-26
scratch review** with live public release metadata retrieved on **2026-09-27**.
They do not change repository pins or install, upgrade or qualify any tool.

## Inputs and selection

The supplied combined currency-record collection contains all 18 structured
scratch records. Per-tool draft filenames differ; only two use the literal
`record-draft.json` spelling. The combined collection and each tool's `gpt6.md`
review were therefore used to locate the historical pin, release and findings.
Reviewer prose was a discovery lead. Published findings cite primary upstream
release notes, immutable source or issue/PR metadata, with separate boundaries
for package releases, stable tags, prereleases and unreleased main changes.

`pin` identifies the revision reviewed in the scratch study and its repository
metadata location. Its `metadata_sources` file:line references point to the
component's version; `metadata_revision` names the repository commit read,
including the locations of any `secondary_pins`. These are repository source
coordinates, separate from an upstream `source_pin` or `source_commit`.
It does not assert the installed version on the reader's
host. `scratch_record` preserves the historical latest-release and distance
claims separately. `changes_since_scratch` states both newly published versions
and dated corrections or changes in unreleased source observations. No previous
scratch facts are changed; the dated repair erratum below identifies corrections
to this publication's provenance and interpretation.

## Live source retrieval

The primary release check uses GitHub's
[get latest release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
through the installed `gh api` command. Each `latest_release` retains only
allowlisted returned values: tag, publication timestamp, release URL, draft and
prerelease flags. Its `source_url` records the public endpoint queried; each
record's `retrieved_at` is a retrieval time, not the release time. It was
recorded in two batches. In batch a (context-mode, headroom, repomix, rtk, toon,
ccusage, markitdown, qmd, serena), records share batch stamps (12:40:10.076Z and
12:40:20.547Z), so their `retrieved_at` is the batch start time of the
latest-release query, not a per-request completion time. The nine batch b
records carry distinct per-record stamps (12:40:31.483Z to 12:40:31.842Z); how
those stamps were produced was not retained. Package-channel and compare
observations carry only a retrieval date, 2026-09-27. Shared millisecond stamps
do not imply simultaneous requests. GitHub's
latest stable release excludes drafts and prereleases; it is not necessarily
the newest tag or default-branch revision.

Where publication channels matter, records retain separate npm/PyPI observations
and their source URLs. In particular, ccusage's v20.0.25 tag is not promoted to a
published package release, Serena's development commit is not measured as a
stable semantic-version downgrade, and RTK prerelease changes do not replace
the latest stable release. Headroom's new v0.39.1 is a new observation after the
scratch record, not evidence that the installed route or acceptance changed.

`behind_by` names the compared channel and reference. Stable release counts
count published non-draft/non-prerelease releases after the reviewed pin;
commit counts compare the named revisions and are explicitly distinct from
release lag. A development-commit pin can be ahead of stable and behind main at
the same time. Counts apply only to the observations on the retrieval date.
A comparison between fixed commits does not re-verify a mutable branch head.
Package upload
timestamps, GitHub release publication and source commit dates stay distinct.

Primary source review uses maintained upstream code at the stated revision and
official changelogs/release notes. Each finding carries its own source URL(s).
A source-inspection statement establishes what that revision says or does in
code; it does not establish that the code ran successfully in the selected
client, that an issue was reproduced, or that a model/tool binding was exercised.

## Retained evidence and exclusions

- **Upstream source/documentation review:** live release metadata, package
  publication metadata where relevant, source comparisons and cited findings.
- **Historical local measurement or unchanged upstream tests:** if a scratch
  review mentions these, they remain historical claims with their stated
  boundaries. This publication does not replay them or promote reviewer prose
  to independently retained native-test stdout.
- **Structural validation:** offline unittest checks validate publication structure,
  metadata references, required source fields and sanitized content. They are
  authored here and establish artifact consistency, not execution or adoption.
- **Synthetic fixtures:** the separate RTK receipt directory contains the
  historical exactness fixture output. It is not part of a currency verdict.
- **Live provider execution:** none performed or claimed for these receipts.

Release snapshots omit authors, account/connection identifiers, request bodies
and unrelated API fields. No credential store was read. Home paths are not
retained; no host installation paths or private reviewer transcripts are
published. Commit hashes and release tags are public source identities.

## 2026-09-27 repair erratum: source coordinates and claim boundaries

Some `pin.metadata_sources` line numbers came from the scratch review of
repository revision `803bc351` without naming that revision. They drifted from
their component entries. All primary and secondary metadata coordinates were
recomputed against `1c32ad22d76479fdc0385f2bbbada15b3f9f6a5f`, and each
record now names that revision as `metadata_revision`. The coordinates are valid
at that revision; later commits may move the lines. The unittest reads each
file at the recorded revision (`git show <revision>:<path>`), opens the cited
line, checks the version and component, and requires a repository revision. No pin version or `scratch_record` was changed.

The earlier claim that `retrieved_at` was each observation's retrieval time
was too precise. The batch-a research note also records an ENOBUFS failure
and successful rerun of Headroom's release-list query with a larger buffer;
its separate request times were not retained. Millisecond stamps are preserved
with the batch-start boundary above, not promoted to per-request timing.

Serena's retained comparison to fixed commit `7a2968335f2198b966864de1ce3655c8e485a653`
does not establish the main branch head on the refresh date. The 30-commit
main distance remains in `scratch_record`; its refreshed distance is null and
marked `not_reverified`. The stable comparison remains separate. No new live
release or compare requests were made for these repair edits.

The offline tests were previously mislabelled local integration. The
[acceptance policy](../../../docs/acceptance-evidence-policy.md#identify-what-each-check-proves)
classifies these artifact checks as structural validation. The shared
identifier-pattern assertion now also rejects planted synthetic samples;
an empty-publication failure alone was not evidence that the patterns matched.

## Re-verification and limits

Query each record's release `source_url` again, compare its allowlisted fields,
then inspect the tagged source links for each finding. A later release can
change the answer; append a dated receipt or erratum instead of rewriting this
one. The GitHub endpoint is live and mutable, while each retained release URL
and timestamp identify what was observed at retrieval. Repository pins require
their own integration checks before adoption, even when upstream is newer.

The compact snapshots do not preserve full HTTP responses, response headers,
release-list pages or provider billing/usage. They preserve actual selected
returned metadata, not cryptographic proof of the upstream response. The
scratch reviews and their private environment are not independently reproducible
from this publication. Nothing here is acceptance for a new host or evidence of
complete capability absence.

2026-09-29 limitation: five batch-a records (context-mode, ccusage, qmd, repomix and
toon) state main-branch distances from the 2026-09-27 refresh with no `unreleased_main`
block, so that refresh retained no returned head of `main`. Each keeps only the
2026-09-26 `scratch_record` observation of a `main` head (context-mode `6c8dbf22`,
ccusage prefix `ffa39de8`, qmd `04e4dbd8`, repomix `75f9f860`, toon `f151a5d8`).
context-mode's `main_commits_ahead_of_reviewed_revision` (12 in the 2026-09-27 refresh;
10 in the scratch record) and its finding on changes up to current main, and ccusage's
`main_commits_ahead` (198; 183 in the scratch record), rest on the compares each record
names; those retain their end commits (`5d13dc45`, `db400ad4`), but no retained
observation shows either was main's head on 2026-09-27. qmd, repomix and toon mark
`latest_stable_and_main_distance` `unchanged` against a compare of the mutable `main`
ref whose returned head and count were not retained, so their only retained distances
are the 2026-09-26 `scratch_record` figures (24, 28 and 11 commits at the `main_head`
commits named there), which qmd's and toon's `behind_by` basis repeats. Treat all of
these figures as fixed-revision or 2026-09-26 observations, not current main distances,
and re-query each named compare before use.

## Sources

- [GitHub REST releases](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
  and [gh api](https://cli.github.com/manual/gh_api): supported release retrieval.
- Each tool record's repository, revision and primary-source URLs: release and
  finding provenance; see the README records table.
- [Acceptance evidence policy](../../../docs/acceptance-evidence-policy.md):
  class boundaries and retained-result requirements.
- [Python unittest](https://docs.python.org/3/library/unittest.html) and the
  repository's [artifact contract pattern](../../../tests/test_token_e2e_preregistration.py):
  offline publication checks only.
