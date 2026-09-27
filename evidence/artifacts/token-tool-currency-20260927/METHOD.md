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
metadata location. It does not assert the installed version on the reader's
host. `scratch_record` preserves the historical latest-release and distance
claims separately. `changes_since_scratch` states both newly published versions
and dated corrections or changes in unreleased source observations. No previous
committed receipt is rewritten.

## Live source retrieval

The primary release check uses GitHub's
[get latest release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)
through the installed `gh api` command. Each `latest_release` retains only
allowlisted returned values: tag, publication timestamp, release URL, draft and
prerelease flags. Its `source_url` records the public endpoint queried; each
record's `retrieved_at` is the retrieval time, not the release time. GitHub's
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
the same time. Counts apply only at the recorded retrieval time. Package upload
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
- **Local integration:** offline unittest checks validate publication structure,
  required source fields and sanitized content. They are authored here.
- **Synthetic fixtures:** the separate RTK receipt directory contains the
  historical exactness fixture output. It is not part of a currency verdict.
- **Live provider execution:** none performed or claimed for these receipts.

Release snapshots omit authors, account/connection identifiers, request bodies
and unrelated API fields. No credential store was read. Home paths are not
retained; no host installation paths or private reviewer transcripts are
published. Commit hashes and release tags are public source identities.

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
