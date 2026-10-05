---
status: proposed
date: 2026-10-05
decision-makers:
  - The user
consulted:
  - "GPT drafting and source-review lane; exact model/effort receipt unresolved; reference: this draft."
  - "Claude-family exact-head review requested; model, effort and verdict link pending."
informed:
  - Command center
  - Foundation and trading lane owners
overturn_when:
  - The organization and merge-queue phase becomes qualified, or the user chooses the strict-check fallback.
  - Opened PRs exceed landed PRs for seven consecutive days in the dated queue report.
  - A required context fails more than 10 percent of its last 20 observed runs.
  - A PR remains idle for 60 days in the dated queue report.
  - The private trading lineage has fully joined its destination, or the user changes the trading or naming decisions.
review_by: 2026-12-31
supersedes: null
superseded_by: null
evidence_class: source_review
---

# Proposed GitHub estate consolidation

## Context and Problem Statement

The public foundation, private operations and domain research need clear homes
without making every host or project depend on the entire estate. This record
summarizes the user's chosen direction in public terms and proposes its
architecture of record. The private companion retains the repository inventory,
URL map, recovery revisions and system landscape. Private repositories have
generic role names here, including the future trading home.

This draft changes documentation only. Its acceptance requires the command
center's Claude read of the exact PR head and the user's subsequent decision.
Until then `status: proposed` remains in both records. A merged draft, a passing
publication validator or a model review does not constitute user acceptance.

The north-star action is to maintain a portable agent foundation that supports
independently qualified research and historical simulation, then broker-specific
paper operation in the private trading home. The existing foundation/trading
path boundary remains in force during the transition
([native-agent-stack@fead5d8f:docs/lanes.md:25](https://github.com/seathatflowsinourveins/native-agent-stack/blob/fead5d8f8042f01ffc1a785f3b8ad6c410ccb506/docs/lanes.md#path-ownership)).

## Decision Drivers

- Improve landing correctness, release identity and workflow quality.
- Reuse vendor-maintained releases, CI features and supported interfaces.
- Keep public recipes reusable and private project operations independently owned.
- Preserve original lineage while moving only upstream-aligned, evidenced material.
- Stage changes behind their actual prerequisites and keep dated facts separate
  from proposed topology and execution acceptance.

## Considered Options

1. Keep all active research, operations and reusable recipes in the public foundation.
2. Separate reusable public foundation material from private operations and domain
   projects, with staged native GitHub automation.
3. Immediately combine the estate in a new organization and activate every
   proposed policy and automation together.

## Decision Outcome

Proposed option: **separate public foundation from private operations and domain
projects, with staged native automation**. This follows the user's direction
while leaving execution gates and the architecture record's acceptance visible.

| Role | Proposed destination and boundary | Confirmation needed |
| --- | --- | --- |
| Public foundation | `native-agent-stack`: portable recipes, catalog evidence, scaffold and public documentation | Existing lane ownership and review/landing practice |
| Private ecosystem control plane | Estate inventory, operations, URL/recovery map and the private companion record | Its own draft review and user acceptance |
| Private trading home | Trading research, deterministic simulation and broker-specific qualified paper paths | Source-backed migration and joining the required lineage |
| Private domain research repositories | Retain useful evidenced work for migration; retain superseded material in archives | Fresh source/recovery checks before each separate migration or archive |
| Private active application repositories | Adopt the released scaffold first | Project-specific native acceptance |
| Private dormant application repositories | Adopt the scaffold when work resumes | Confirmation at resumption |
| Private workflow archive | Preserve reusable workflow lineage until its copies and trading lineage are confirmed | Byte identity and completed lineage join before archiving |

The public/private boundary has two public upstream-fork exceptions retained in
the private inventory; this record does not infer their present archive state.
Generic private names are retained until the user resolves publication naming.
No transfer, archive, deletion, scaffold installation or organization creation
is performed by either decision-record PR.

The campaign's cleanup authority is limited to the specific actions already
approved by the user. Their execution owner checks each item's supporting facts
again immediately before acting; if those facts differ, that item is omitted
and the difference is reported. This proposed record expands neither the list
nor the execution owner's authority.

### Landing phases

The interim retains the current non-strict lander. The repository's checked
ruleset snapshot has `strict_required_status_checks_policy: false` and
squash-only PR merges; this is source inspection, not a new live API acceptance
([native-agent-stack@fead5d8f:.github/main-ruleset.json](https://github.com/seathatflowsinourveins/native-agent-stack/blob/fead5d8f8042f01ffc1a785f3b8ad6c410ccb506/.github/main-ruleset.json)).
The strict-check approach in [PR #708](https://github.com/seathatflowsinourveins/native-agent-stack/pull/708)
is a fallback if an organization cannot be created. It is an unmerged proposal
at source head `2c943a9e30f9caa222ef6098f9ab1368616bcc4b`, rather than an applied
rule or a prerequisite for this record.

The destination is a native GitHub merge queue for the public foundation in an
organization selected by the user. Naming and organization-gated changes remain
pending. GitHub supports queues for organization-owned public repositories;
private organization repositories require Enterprise Cloud. A free organization
therefore does not establish queue availability for the private estate
([GitHub merge-queue documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)).

Before requiring the queue, every required Actions context must report on the
merge-group SHA through `merge_group: checks_requested`, alongside its applicable
PR/push triggers. The queue tests the current base with preceding queued changes.
A successful PR-head check alone does not qualify a merge group
([GitHub `merge_group` reference](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#merge_group)).

### Native automation and release cadence

Use GitHub's existing features and action configuration for the work they ship:

| Feature | Proposed use and constraint | Official source |
| --- | --- | --- |
| Actions concurrency | Serialize the relevant workflow in its repository. Default `queue: single` replaces an existing pending run; preserving the running run with `cancel-in-progress: false` does not retain every arrival. Current GitHub.com docs support `queue: max` for up to 100 pending runs, with excess arrivals canceled; it cannot be combined with `cancel-in-progress: true`. Waiting order is not a guarantee of dispatch order or cross-repository ordering. Select the policy in the workflow's own reviewed change. | [Concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [github/docs@ddc34e6c:data/reusables/actions/actions-group-concurrency.md:15](https://github.com/github/docs/blob/ddc34e6c76d8836ec12ed3edfaffb1c4be41829e/data/reusables/actions/actions-group-concurrency.md#L15) |
| Dependency review | Reuse `actions/dependency-review-action` with its existing configured policy. The reviewed v5.0.0 source runs Node 24 and requires runner >=2.327.1. For non-PR events, including merge groups, configure and qualify explicit `base-ref`/`head-ref`; PR defaults do not apply. Availability is public repositories or suitably licensed private repositories. This record adds no scan or entitlement. | [actions/dependency-review-action@a1d282b:README.md:57](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/README.md#L57), [action.yml:25](https://github.com/actions/dependency-review-action/blob/a1d282b36b6f3519aa1f3fc636f609c47dddb294/action.yml#L25), [GitHub availability](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-review) |
| Release notes | Generate notes through the supported GitHub release interface, then review the result. Keep the daily release proposal as an issue until its release conditions hold. | [GitHub generated release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes), [gh release create](https://cli.github.com/manual/gh_release_create) |
| Release identity | Preserve annotated tags on main ancestry, attach final assets before immutable publication, and retain native release verification at the matching re-pin. Latest-release selection requires the intended main head. These are the campaign's proposed release-integrity conditions; this record neither cuts a release nor re-verifies an existing one. | [GitHub immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases), [gh release verify](https://cli.github.com/manual/gh_release_verify) |

Organization-independent automation stays in its own bounded PRs: release
integrity, daily proposals, ruleset/queue observations and decision freshness.
Records and execution evidence belong in GitHub. A step is retained when it
serves landing correctness, release integrity or workflow quality; the campaign
does not add a separate crossing classifier, link guard or security-hardening
program. Native model/provider or host acceptance is outside this record's
publication checks.

### Consequences

The public catalog remains useful without access to private inventory. Private
operations can preserve recovery revisions and domain context, while the
foundation retains explicit ownership during the trading split. Source-backed
migration and native project acceptance take additional work; naming, licensing
and organization prerequisites keep the complete target topology provisional.
The organization-first alternative would couple those independent prerequisites.
The single-public-repository alternative would retain the current ownership
coupling rather than resolve it.

### Confirmation and evidence classes

| Check or claim | Evidence class and limit |
| --- | --- |
| Official GitHub behavior, MADR structure and pinned repository policy | `source_review`; primary documentation/source read on 2026-10-05, not deployed-feature acceptance |
| Decision metadata/registry validation and private-name exclusion | `local_integration`; reproducible publication checks, with actual results in the PR/status record |
| A8-R5 field test | Required A9 completion gate, pending the owning unit's executable; no passing result asserted here. The publication validator does not substitute for this field test. |
| Claude-family exact-head read, one repair round and command-center landing acknowledgement | Requested; verdict link and reviewed head must be recorded before release from draft |
| Architecture acceptance | Pending the user's decision; no model verdict substitutes for it |
| Host/runtime readiness | Separate qualification; a new figure comes only from the final verified E2E with independent review/adjudication |

Follow the existing [hot-file protocol](../lanes.md#hot-file-protocol): registry
changes are committed last, refreshed from main through the existing native
registration command, and never hand-merged. The public PR uses `lane:shared`
and needs the other lane's acknowledgement before landing. The command center
owns landing; this draft author does not merge.

## Revisit and append-only history

Review by 2026-12-31, within 90 days of this record. The campaign's decision-field
and due-date integration is a separately owned automation unit, so a metadata
field alone does not prove the timer watches it. When deployed, the queue report
provides opened/landed, 60-day idle and last-20-run context-failure observations;
release proposals and the private lineage join timestamps provide the other
named sensors. Until those observations exist, their values remain unknown.

Overturn this proposal when its frontmatter conditions occur, or when the user
changes the merge, trading or publication-naming decisions. Compare the new
native queue's landing rate and context failures with the dated interim report
before changing the fallback. Append later facts or write a superseding record;
preserve the original snapshot and link `supersedes`/`superseded_by` rather than
rewriting historical acceptance.

## Sources and record method

This uses the maintained [MADR 4.0.0 template](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md#L1)
for metadata, context, alternatives, outcome, consequences and confirmation;
`review_by`, `overturn_when` and `evidence_class` are the campaign's explicit
local additions. The private companion uses
[arc42@2026.10.2](https://github.com/arc42/arc42-template/releases/tag/2026.10.2)
sections 1/3/5/9/11 and the [C4 system-landscape model](https://c4model.com/diagrams/system-landscape)
to describe the whole estate. The user's instructions are summarized, with
the private names and original instruction text kept out of this public record.

The architectural direction comes from the 2026-10-05 revised campaign and user
decisions. It is not presented as an upstream-prescribed estate topology.
The pinned repository sources above establish the existing public boundary and
interim policy; current official GitHub documentation establishes feature
behavior. Draft review, later user acceptance and native execution have separate
evidence requirements.
