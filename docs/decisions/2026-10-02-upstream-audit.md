# Upstream quality audit of the definitive manifest's foundation repositories (2026-10-02)

Lane: foundation. North-star action served: every slot of the new WSL's clean install rests on upstream repositories
whose maintenance, provenance and security posture are recorded before they are installed. Status: an information
record. No default, state or slot changes through it.

## Decision

`tools/sota-convergence/upstream_audit.py` audits every GitHub repository that a foundation row of the definitive
manifest names. The manifest is `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json`,
the install record merged in #602. The output is `catalogs/foundation/upstream-audit-20261002.json`, built from
`evidence/artifacts/upstream-audit-20261002/observations.json`. Both record the manifest's sha256, and CI checks them
with `--check`. The audit records what the manifest does not:
- release provenance: the name and digest of each queried asset of the latest release, and its GitHub attestations;
- published security advisories, read to the last page;
- the check runs on the default-branch head, read to the last page, and the head's check-suite count: above 1000
  suites GitHub lists only the runs of the most recent 1000, so such a collection is recorded incomplete;
- the published OpenSSF Scorecard.

It also re-records maintenance and release currency. Its flags are observed facts, not verdicts. A slot's default and
state change only through the manifest's own rule (`docs/decisions/2026-10-01-new-wsl-definitive-defaults.md`).

## Results (observed 2026-10-02T21:40Z)

The audit covers 56 GitHub repositories that the manifest's foundation rows name, observed until 2026-10-02T21:40:36+00:00; a row installs 36 of them. A repository can hold roles in several slots, so the state rows overlap. "Provenance unknown" and "Check runs incomplete" count collections that could not establish a negative fact.

| Role | Repositories | Scorecard published | No release | Release > 365 days | No GitHub attestation | Provenance unknown | Published advisories | Failing head check | Check runs incomplete | Scorecard < 5 | Archived or stale | Fetch errors |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | 56 | 19 | 6 | 1 | 16 | 0 | 24 | 15 | 1 | 1 | 1 | 0 |
| definitive | 27 | 9 | 3 | 0 | 6 | 0 | 15 | 9 | 1 | 1 | 0 | 0 |
| resolved | 14 | 6 | 1 | 1 | 3 | 0 | 6 | 1 | 0 | 0 | 0 | 0 |
| split | 9 | 4 | 2 | 0 | 4 | 0 | 2 | 3 | 0 | 0 | 1 | 0 |
| measurement | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pinned | 5 | 0 | 0 | 0 | 2 | 0 | 1 | 2 | 0 | 0 | 0 | 0 |
| installed by a row | 36 | 11 | 3 | 0 | 11 | 0 | 18 | 12 | 0 | 1 | 0 | 0 |

- **Collections:** 1 incomplete (head 0, release 0, attestations 0, advisories 0, check runs 1, deps.dev 0); 0 repositories could not be read.
- **Stale** (no default-branch commit after the 90-day cutoff): `qwenlm/qwen3-embedding` (last commit 2025-09-30T06:10:27Z, 367 days) in `embedding-model` (split).
- **No GitHub release** (`releases/latest` answers 404): `anthropics/claude-plugins-official` in `claude-plugins-official-code-intelligence-lsp-pl` (resolved); `git/git` in `git` (definitive, installed); `qwenlm/qwen3-embedding` in `embedding-model` (split); `qwenlm/qwen3.8` in `local-generation-model` (split); `trailofbits/skills` in `trail-of-bits-security-skills-trailofbits-skills` (definitive, installed); `ukgovernmentbeis/inspect_ai` in `inspect-ai` (definitive, installed).
- **Latest release older than 365 days:** `anthropics/claude-code-action` (`v1`, 402 days) in `claude-code-action` (resolved).
- **No GitHub attestation on any queried asset:** `aannoo/hcom` (5 of 23 digest-carrying assets queried) in `agent-messaging` (split); `ast-grep/ast-grep` (5 of 7 digest-carrying assets queried) in `structural-search` (resolved, installed); `diegosouzapw/omniroute` (5 of 17 digest-carrying assets queried) in `gpt-gateway` (pinned, installed); `docker/compose` (5 of 56 digest-carrying assets queried) in `docker-compose` (definitive, installed); `grafana/grafana` (5 of 13 digest-carrying assets queried) in `grafana` (split), `loki` (split); `grafana/loki` (5 of 47 digest-carrying assets queried) in `grafana` (split), `loki` (split); `ollama/ollama` (5 of 17 digest-carrying assets queried) in `local-model-server` (measurement, installed); `openai/codex` (5 of 176 digest-carrying assets queried) in `codex` (definitive, installed), `codex-sdk-and-codex-exec-app-server` (definitive, installed); `openclaw/mcporter` (5 of 5 digest-carrying assets queried) in `mcporter` (definitive, installed); `opendatalab/mineru` (1 of 1 digest-carrying assets queried) in `mineru` (definitive, installed); `openhands/software-agent-sdk` (5 of 7 digest-carrying assets queried) in `agent-runtime-worker` (pinned, installed); `prometheus/alertmanager` (5 of 40 digest-carrying assets queried) in `alerting` (resolved, installed); `restic/restic` (5 of 29 digest-carrying assets queried) in `restic` (definitive, installed); `trufflesecurity/trufflehog` (5 of 9 digest-carrying assets queried) in `trufflehog` (resolved); `vercel-labs/agent-browser` (5 of 7 digest-carrying assets queried) in `playwright-cli` (split); `wilfred/difftastic` (5 of 7 digest-carrying assets queried) in `difftastic` (definitive, installed).
- **Provenance of the latest release:** attested 13, no attestation 16, unknown 0, no digest-carrying asset 0, no asset 21, no release 6.
- **Scorecard:** published for 19 of 56; below 5.0: `wilfred/difftastic` (3.9, scan of 2026-08-24) in `difftastic` (definitive, installed).
- **Failing check runs on the default-branch head:** `anchore/syft` (1 of 14) in `syft` (definitive, installed); `anthropics/claude-agent-sdk-python` (2 of 13) in `claude-agent-sdk` (definitive, installed); `anthropics/claude-code` (2 of 180) in `claude-code` (definitive, installed); `diegosouzapw/omniroute` (11 of 120) in `gpt-gateway` (pinned, installed); `docker/compose` (7 of 141) in `docker-compose` (definitive, installed); `google-deepmind/gemma` (2 of 10) in `embedding-model` (split); `grafana/loki` (2 of 207) in `grafana` (split), `loki` (split); `kjanat/actionlint` (1 of 53) in `actionlint-kjanat` (definitive, installed); `moby/moby` (2 of 296) in `container-engine` (definitive, installed); `openai/codex` (42 of 105) in `codex` (definitive, installed), `codex-sdk-and-codex-exec-app-server` (definitive, installed); `oraios/serena` (1 of 28) in `serena` (definitive, installed); `prometheus/alertmanager` (2 of 54) in `alerting` (resolved, installed); `seathatflowsinourveins/native-agent-stack` (1 of 23) in `convergence-validators` (pinned, installed), `credential-guard` (pinned, installed); `vercel-labs/agent-browser` (1 of 23) in `playwright-cli` (split); `wilfred/difftastic` (1 of 17) in `difftastic` (definitive, installed).
- **Check runs incomplete** (a head above 1000 check suites, or a short or failed read): `actions/attest` (1000 runs read from the 1000 most recent of 1607 check suites) in `attest` (definitive).
- **Published advisories:** `aannoo/hcom` (1) in `agent-messaging` (split); `anchore/syft` (3) in `syft` (definitive, installed); `anthropics/claude-agent-sdk-python` (1) in `claude-agent-sdk` (definitive, installed); `anthropics/claude-code` (32) in `claude-code` (definitive, installed); `anthropics/claude-code-action` (1) in `claude-code-action` (resolved); `anthropics/sandbox-runtime` (1) in `sandbox-runtime-srt` (definitive, installed); `cli/cli` (17) in `gh-github-cli` (definitive, installed); `dagucloud/dagu` (6) in `dagu` (definitive, installed); `dependabot/dependabot-core` (1) in `dependabot` (resolved); `diegosouzapw/omniroute` (1) in `gpt-gateway` (pinned, installed); `docker/compose` (1) in `docker-compose` (definitive, installed); `git/git` (32) in `git` (definitive, installed); `github/codeql-action` (2) in `codeql-sarif` (resolved); `grafana/grafana` (28) in `grafana` (split), `loki` (split); `jdx/mise` (12) in `mise` (definitive, installed); `moby/moby` (26) in `container-engine` (definitive, installed); `modelcontextprotocol/inspector` (2) in `mcp-inspector` (definitive, installed); `open-telemetry/opentelemetry-collector-contrib` (7) in `otel-collector-contrib` (definitive, installed); `openai/codex` (1) in `codex` (definitive, installed), `codex-sdk-and-codex-exec-app-server` (definitive, installed); `oraios/serena` (2) in `serena` (definitive, installed); `prometheus/alertmanager` (1) in `alerting` (resolved, installed); `prometheus/prometheus` (6) in `prometheus` (resolved, installed); `trufflesecurity/trufflehog` (1) in `trufflehog` (resolved); `zizmorcore/zizmor` (1) in `zizmor` (definitive, installed).
- **Not audited** (4): `base-distribution` (definitive): https://releases.ubuntu.com/26.04.1/; `code-search` (split): finalists named without a repository; `embedding-model` (split): https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16; `memory-owner` (measurement): finalists named without a repository.

## Method

- **Search first.**
  - GitHub's REST API serves every field but the Scorecard. Calls go through the GitHub CLI (`gh api`), as
    `tools/sota-convergence/github_freshness.py` makes them, and no popularity field is copied.
  - The deps.dev v3 project endpoint serves the license and the Scorecard of the OpenSSF weekly scan
    (https://docs.deps.dev/api/v3/#getproject). A repository outside that scan has no published Scorecard and is
    recorded as not covered rather than scored.
  - Running Scorecard locally was considered and rejected before
    (`tools/sota-convergence/practice_references.py`, which rejected the Maintained check as a pin-staleness signal).
    Reading published results is a different use, so that rejection does not apply.
- **Targets.** Only rows whose `catalog` is `foundation` count; the trading rows stay out.
  - A row names a repository through a GitHub URL in its `repository`, in its resolution's
    `former_default.repository` or in an `arms[].repository`. A field can join several URLs with " ; ".
  - A split or measurement row can also name a finalist as owner/name text in its `default` or in its former
    default's or arms' `name`. The current manifest has none.
  - URLs outside GitHub, and split or measurement rows that name no finalist repository, are listed as not audited
    (above). A finalist named only by a product name is not mapped to a repository by guess.
- **Roles.** A repository's role in a row is the row's `slot_id`, its `state` (`pinned` when the state is empty),
  whether the row installs it and where the row names it. A row installs only its own `repository`, and only when its
  default is not `installs_nothing_extra`; this is the rule of `scripts/build_new_wsl_handbook.py`. The role table is
  recorded with the observations, so the audit rebuilds from its observations alone.
- **Drift.** `--check` fails when the manifest's sha256, or the role table or not-audited list the manifest yields,
  differs from the one recorded at collection. It then prints each repository that was added, was removed or has
  changed roles. Re-collect with `--collect`, then run `--build`.
- **Requests.** Each observation lists every request it made, in order, with its outcome:
  - the GitHub REST paths `repos/{owner}/{repo}`, `repos/{owner}/{repo}/commits/{default branch}`,
    `repos/{owner}/{repo}/releases/latest` and `repos/{owner}/{repo}/attestations/{digest}` for each queried asset;
  - `repos/{owner}/{repo}/security-advisories?state=published&per_page=100` and
    `repos/{owner}/{repo}/commits/{head sha}/check-runs?per_page=100`, each with its page count;
  - `repos/{owner}/{repo}/commits/{head sha}/check-suites?per_page=1`, read after the check runs for its
    `total_count`;
  - the deps.dev URL `https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}`.

  A failed request is recorded by its HTTP status or as a timeout, never by its message. The collector refuses to
  start with less than 20 requests of GitHub REST budget per repository, as the `rate_limit` endpoint reports it. It
  retries a 429, a rate-limit 403, a 5xx or a timeout up to three times, pausing longer each time.
- **Pagination.** `gh api --paginate --slurp` reads every page of the advisories (cursor pages) and of the check runs
  (numbered pages).
  - A check-run collection is complete when the distinct runs read equal the `total_count` that every page reports
    and the head carries at most 1000 check suites. The observation keeps each distinct `total_count` the pages
    reported; more than one means runs moved while they were listed.
  - Above 1000 suites the check-runs endpoint lists only the runs of the 1000 most recent suites, so its
    `total_count` describes that truncated set
    (https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference). The suite count is read after
    the runs, so a suite added meanwhile is counted; a failed suite request leaves the collection incomplete.
  - An advisory collection is complete when every page was read. The advisories endpoint reports no total, so the
    observation records only the count it read.
  - An incomplete or failed collection never reports a negative fact: no failing count of 0 and no advisory count
    of 0.
- **Provenance.** `attestations/{digest}` is queried for the first five digest-carrying assets of the latest release,
  and a 404 means that asset has no attestation. `no_provenance` needs an answer from every queried asset and an
  attestation on none. One failed request without an attested asset makes provenance unknown.
- **Flags and their frozen thresholds:**
  - archived;
  - stale: no default-branch commit after the observation time minus 90 days, the Scorecard Maintained window,
    compared directly with that cutoff as `tools/sota-convergence/practice_references.py` compares it;
  - no release, or a latest release published no later than the observation time minus 365 days;
  - no attestation on any queried asset of a release with digest-carrying assets;
  - published advisories;
  - a failing check run on the default-branch head (failure, timed_out or startup_failure);
  - a published Scorecard below 5.0.

  Ages are measured from each observation's own time.

## Limits

- One observation per repository, at the time in its `observed_at`. Upstream state moves, so `--collect` re-observes.
- Digests are recorded only for the queried assets: at most five per repository, the first five digest-carrying
  assets in the release's asset order. They need not include the main binaries; for `openai/codex` they are its
  `argument-comment-lint` archives. `no_provenance` therefore means "no GitHub attestation on the queried assets",
  not "unsigned". A project that signs another way, such as a Sigstore bundle beside its checksums, also shows it.
- An attestation count is the number of attestations one request returned.
- Check runs cover the Checks API on the default-branch head only, with the endpoint's default filter, `latest`,
  which returns the most recent check runs. They are not a CI health history. A head above 1000 check suites is
  recorded incomplete, not read suite by suite; a failure among the runs that were read still counts.
- deps.dev publishes a Scorecard for a subset of repositories, so most entries are not covered.
- The project's own repository is audited because two pinned rows name it.
- The audit runs no candidate and measures no capability.

## Alternatives

- **Re-run Scorecard locally for every repository.** Rejected: it needs a token per run and adds minutes per
  repository, and the published scan answers where it covers a repository.
- **Fold these fields into the manifest's generator.** Rejected: the audit needs the network, and the manifest's
  checks must stay offline and deterministic.
- **Read each suite's runs on a head above the 1000-suite limit** (`check-suites/{id}/check-runs`, the route the
  REST reference gives). Not taken: it costs one request per suite, more than a thousand for each such head, to
  complete one Checks figure. The row records the collection incomplete instead.
- **Keep the final catalog of #595 as the target.** Rejected: the definitive manifest merged in #602 is the install
  record, and this audit must stand on `main` alone.

## Overturn

Re-collect when the definitive manifest changes (`--check` fails until then), before any new-host install wave, or
when a flagged repository publishes a fix.

## Evidence class

`local_integration`: read-only API observations by this repository's script. No upstream test suite ran, and no
candidate was installed.

## SOTA sources

- GitHub REST: repositories, commits, releases (asset `digest`), artifact attestations, repository security
  advisories, check runs and check suites (https://docs.github.com/en/rest); every page read through the GitHub
  CLI's `gh api --paginate --slurp` (https://cli.github.com/manual/gh_api).
- The 1000-suite limit of "List check runs for a Git reference"
  (https://docs.github.com/en/rest/checks/runs#list-check-runs-for-a-git-reference), and the suite count of "List
  check suites for a Git reference"
  (https://docs.github.com/en/rest/checks/suites#list-check-suites-for-a-git-reference).
- deps.dev API v3, GetProject (https://docs.deps.dev/api/v3/#getproject); OpenSSF Scorecard
  (https://github.com/ossf/scorecard).
- In-repository references: `tools/sota-convergence/github_freshness.py`,
  `tools/sota-convergence/practice_references.py` and `scripts/build_new_wsl_handbook.py`.
