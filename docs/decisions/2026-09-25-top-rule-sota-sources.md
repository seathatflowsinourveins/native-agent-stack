# Decision: top rule, never self-write without a SOTA source, enforced by a required PR check (2026-09-25)

**Decided by:** the user, in agent-lab session agent-lab-ea on 2026-09-25. The record is agent-lab's
`docs/tasks/2026-09-24-sota-mover-strategies.md`, sections "Top rule adopted" and "Upstream-first correction". The
same rule lands in agent-lab through PR #71. This change is on branch `claude/top-rule-sota-sources-20260925`,
based on `origin/main@0074a0c3`.

**Scope:**
- `AGENTS.md`, the first rule every session in this repository reads.
- `examples/claude-native/CLAUDE.md`, the portable user-level instructions a new PC installs.
- `.github/pull_request_template.md`, which adds a "SOTA sources" section.
- `.github/workflows/validate.yml`, which adds the `sota-sources` job.
- `.github/main-ruleset.json`, which makes `sota-sources` a required status check.
- `manifests/evidence.json`, with the new hashes for these files.

## Decision

The rule, in the user's words (verbatim): "NEVER SELF WRITTEN EVER AGAIN WITHOUT SOTA REPOS, EVERY LAYERS NEED TO
MANIFEST FORM SOTA REPOS AND REFERENCES, INSTALL DIRECTLY OR REFERENCING, ALL ACTION NEED SOTA REFERENCES BACKED, IF
ONE LINE REMAIN FOR OUR AGENT.MD RULES ETC IS THIS RULE". As the first line of the instruction files:

> **Top rule: never self-write without a SOTA source.** Every layer, component and action comes from a maintained
> SOTA repository or published reference: install it directly, or build only from a cited reference implementation,
> and name that source (repository, pin, file or paper) for every action. With no SOTA source, stop and report
> instead of writing one.

The `sota-sources` job fails a pull request whose description has no non-empty "SOTA sources" section (`##` or
`###`). It reads the description from the `pull_request` payload through the official `actions/github-script`,
pinned to v9.0.0 at commit `3a2844b7e9c422d3c10d287c895573f7108da1b3`. No description text reaches a shell, and
the job needs no permission beyond `contents: read`.

## Evidence

**Why the rule** (`native_proven` on the agent-lab host). On 2026-09-25 an in-house trading engine and its
self-written strategy arms ran on an Alpaca paper account. The arms had no maintained upstream implementation and no
qualified catalog entry: `catalogs/us-equities/engines-strategies.json` qualifies engines and libraries but no
strategy. The session lost $12,443.07, reconciled against 635 broker fills with a $0.00 residual. The arms without
historical support went −6.61R over 35 trades, and a self-written after-hours exit lost $10,928 against the official
close. Their historical tests had already refuted or failed to support the arms:
- ORB-1: −0.76R, n 10,771;
- mover early-entry: 0 of 1,012 development candidates;
- NEWS-3: −19.4 bps/day, t −12.6.

**The check** (`local_integration`):
- The body matcher was run in Node on four cases: empty section, filled, last section and missing.
- zizmor, offline strict, reports no findings.
- actionlint 1.7.12 (pinned, sha256 verified) passes.
- `scripts/validate.py`, `scripts/validate_catalogs.py`, `scripts/build_ecosystem.py --check` and
  `scripts/evidence_manifest.py --check` pass.

**Sources:**
- `actions/github-script`: https://github.com/actions/github-script, v9.0.0.
- The `pull_request` payload: https://docs.github.com/en/webhooks/webhook-events-and-payloads#pull_request
- Ruleset required checks: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets

## Alternatives considered

- **A checklist item in the PR template only.** Rejected: nothing fails, and the rule was already implied by the core
  rule ("research upstream before building"), yet it did not stop self-written arms.
- **A reviewer-only rule.** Rejected: reviewers check what is in front of them, and a missing source is an absence.
- **An automated source check per file.** Rejected for now. No maintained upstream tool maps changed lines to cited
  sources, and writing one would itself break the rule.

## Comparison that would overturn it

Count, over at least 30 merged PRs, those in which the required "SOTA sources" section was satisfied only by filler.
A reviewer finds no real source for at least one change, measured by an independent review of each PR's listed
sources. If that share exceeds 20%, the section check is replaced by a stronger mechanism: required reviewer sign-off
on sources, or a maintained upstream provenance tool once one exists. If PRs are blocked because a legitimate change
has no possible upstream (for example, repository-specific configuration), add an explicit, reviewed exemption line
rather than dropping the check.
