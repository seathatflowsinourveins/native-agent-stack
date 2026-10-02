# Upstream quality audit of the final catalog's repositories (2026-10-02)

Lane: foundation. North-star action served: every layer of the new WSL rests on upstream repositories whose
maintenance, provenance and security posture are recorded before they are installed. Status: an information record.
No pick, status or selection changes through it.

## Decision

`tools/sota-convergence/upstream_audit.py` audits every GitHub repository the final catalog names as a standing pick,
a challenger or an unjudged incumbent. The output is `catalogs/foundation/upstream-audit-20261002.json`, built from
`evidence/artifacts/upstream-audit-20261002/observations.json`, and CI checks it with `--check`. It covers what the
frozen blind criteria do not score:
- release provenance: asset digests and GitHub attestations;
- published security advisories;
- check runs on the default-branch head;
- the published OpenSSF Scorecard.

It also re-records maintenance and release currency. Its flags are information. A pick still becomes final only
through the agreement rule and the measured comparisons of `docs/decisions/2026-10-01-final-catalog.md`.

## Results (observed 2026-10-02T01:19Z)

The audit covers 80 GitHub repositories. A repository can hold several roles, so the role rows below overlap. There
were 0 fetch errors, and no repository is archived or stale.

| Role | Repositories | Scorecard published | No release | Release > 365 days | No GitHub attestation | Published advisories | Failing head check | Scorecard < 5 | Archived or stale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| standing pick | 34 | 11 | 3 | 0 | 9 | 18 | 7 | 0 | 0 |
| challenger | 31 | 9 | 2 | 1 | 13 | 14 | 10 | 1 | 0 |
| unjudged incumbent | 34 | 14 | 1 | 1 | 13 | 16 | 10 | 1 | 0 |

- **Scorecard:** published for 26 of the 80. Two score below 5.0: `gerrymanoim/exchange_calendars`, an unjudged
  incumbent of the trading layers, and `wilfred/difftastic`, a challenger and the selection of record for structural
  diffs.
- **No GitHub release** (`releases/latest` returns 404): `git/git`, `postgres/postgres`, `trailofbits/skills`,
  `ukgovernmentbeis/inspect_ai` and `anthropics/claude-plugins-official`.
- **Latest release older than 365 days:** `anthropics/claude-code-action` (`v1`, 401 days) and `quantconnect/lean`
  (`v2.4.0.1`).
- **Published advisories, failing head checks and missing attestations** are common across all three roles. Each row
  lists the counts and severities; none of them is a verdict on the repository.

## Method

- **Search first.**
  - GitHub's REST API serves every field but the Scorecard. Calls go through `gh api` with
    `tools/sota-convergence/github_freshness.py` (`fetch_repository`, `gh_api`), and its popularity fields are dropped.
  - The deps.dev v3 project endpoint serves the license and the Scorecard of the OpenSSF weekly scan
    (https://docs.deps.dev/api/v3/#getproject). A repository outside that scan has no published Scorecard and is
    recorded as not covered rather than scored.
  - Running Scorecard locally was considered and rejected before
    (`tools/sota-convergence/practice_references.py`, which rejected the Maintained check as a pin-staleness signal).
    Reading published results is a different use, so that rejection does not apply.
- **Targets.** The standing picks, challengers and unjudged incumbents of
  `catalogs/foundation/final-catalog-20261001.json`, keeping only repositories with a GitHub key. The roles are
  recorded with the observations, so the audit rebuilds from its observations alone. A later change to the final
  catalog shows as drift in `--check`, not as a failure.
- **Flags and their frozen thresholds:**
  - archived;
  - stale: no default-branch commit in 90 days, the Scorecard Maintained window that `practice_references.py`
    already uses;
  - no release, or a latest release older than 365 days;
  - no attestation on a release that has digest-carrying assets;
  - published advisories;
  - a failing default-branch check run;
  - a published Scorecard below 5.0.

  Ages are measured from each observation's own time.

## Limits

- One observation per repository, at the time in `observed_at`. Upstream state moves, so `--collect` re-observes.
- Attestations are looked up for at most five digest-carrying assets of the latest release. A repository that signs
  with another mechanism, such as a Sigstore bundle beside its checksums, can show `no_provenance` here. The flag
  means "no GitHub attestation found", not "unsigned".
- Check runs cover GitHub Actions and Checks API runs on the default-branch head only. They are not a CI health
  history.
- deps.dev publishes a Scorecard for a subset of repositories, so most entries are not covered.
- The audit runs no candidate and measures no capability.

## Alternatives

- **Re-run Scorecard locally for every repository.** Rejected: it needs a token per run and adds minutes per
  repository, and the published scan answers where it covers a repository.
- **Fold these fields into the final catalog's generator.** Rejected: the audit needs the network, and the final
  catalog's `--check` must stay offline and deterministic.

## Overturn

Re-collect when the final catalog changes its standing picks or challengers, before any new-host install wave, or
when a flagged repository publishes a fix.

## Evidence class

`local_integration`: read-only API observations by this repository's script. No upstream test suite ran, and no
candidate was installed.

## SOTA sources

- GitHub REST: releases (asset `digest`), attestations, repository security advisories and check runs
  (https://docs.github.com/en/rest).
- deps.dev API v3, GetProject (https://docs.deps.dev/api/v3/#getproject); OpenSSF Scorecard
  (https://github.com/ossf/scorecard).
- In-repository references: `tools/sota-convergence/github_freshness.py` and
  `tools/sota-convergence/practice_references.py`.
