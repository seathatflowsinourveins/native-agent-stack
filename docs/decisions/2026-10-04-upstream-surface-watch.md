# Decision: a zero-token watch for new Claude Code and Codex switches (2026-10-04)

**Decided by:** session native-agent-stack-99's unit U4, from the coordinator's source research of 2026-10-04 (first
party, third-party trackers, what nothing maintained covers). The sources were re-read with curl on 2026-10-04.

**Scope:**

- `scripts/upstream_surface_watch.py`;
- `catalogs/foundation/upstream-surface-baseline.json` and `upstream-surface-dispositions.json`;
- the `surface_unreviewed` count in `scripts/currency_due.py` and its handling of a stale or unreadable report;
- `adoption/templates/systemd/upstream-surface-watch.service` and the `Wants=`/`After=` lines of
  `stack-currency.service`;
- the tests, `docs/upstream-surface-watch.md` and this record.

## Requirement

The user, to session 99 on 2026-10-04: "for the sota features form changelogs, make sure we enabled all latest sota
ones into our wsl and new wsl and keep maitnaced updated latest sota aligned". Keeping that aligned needs a standing
signal when a release adds a switch. The repository's daily machinery (`scripts/currency_due.py`,
`tools/sota-convergence/github_freshness.py`) catches version drift only.

## Sources chosen (first party, no model, no account beyond gh's own sign-in)

- **Claude Code settings keys and hook events:** the Agent SDK's `sdk.d.ts`, whose `interface Settings` is "auto-generated
  from the settings JSON schema". It is matched to the Claude Code version by its package.json `claudeCodeVersion`
  through the npm packument (2.1.289 resolves to SDK 0.3.289). This is the only machine-readable, versioned
  first-party form of the settings keys. Anthropic publishes no settings schema of its own (request:
  anthropics/claude-code#94232).
- **Environment variables and built-in mods:** the docs pages `env-vars.md` and `plugins/mods/overview.md`. No
  first-party machine-readable list exists, so the watch greps backticked names. It is page-wide, so a new section
  is not missed.
- **Codex config keys:** the `config-schema.json` asset of the stable GitHub release (generated from `ConfigToml`).
  It is reached through one `gh api .../releases/latest` call and verified against the asset's published sha256
  digest; GitHub published one for rust-v0.160.0 (read 2026-10-04T14:36Z). A release without a digest is read
  unverified, and its coverage record and a note say so.
- **Codex features:** `codex features list` of the installed binary, run under an empty temporary `CODEX_HOME`.
- **Changelogs:** Claude Code's `CHANGELOG.md`, and the Codex stable release notes. The notes come from GraphQL,
  because the REST release list carries about 176 assets per release, 9 MB for 30 releases.
- **Trigger and versions:** the npm dist-tags. The Claude channel under watch is `latest`, which the settings template
  selects. npm's `stable` tag (2.1.285 on 2026-10-04) lags it.

## Third-party trackers: cross-checks, not baselines

The trackers are compared report-only (`--cross-check`). A cross-check failure never fails the run. The version gaps,
the SchemaStore sync point and the two READMEs below come from the coordinator's research of 2026-10-04 and were not
re-read in this unit. This unit observed the amitray007 release v2.1.288 (16 assets, sha256 digests) and the
chenrui333 `lifecycle.json` (codex-cli 0.160.0).

- **amitray007/claude-code-schema** (per-release settings and environment catalogs, digest-published). Its releases
  skip versions (none for 2.1.274-279 and 2.1.284-286). On 2026-10-04 its newest release was v2.1.288, while 2.1.289
  was current.
- **chenrui333/codex-docs** `lifecycle.json` (key, stage, enabled per feature). It is a daily third-party extraction,
  without release assets.
- **SchemaStore's claude-code-settings.json.** It was last synced "to Claude Code v2.1.220", about 69 releases behind.
- **marckrenn/claude-code-changelog.** Its README says it costs server time and tokens to run.

## What no maintained tool covers (why the glue exists)

No maintained tool diffs the Claude Code settings surface, environment variables or mods between versions, apart
from amitray007's repository script, which is not released for every version. Neither vendor publishes a feature-change
feed or action. Per the same research, `getsentry/json-schema-diff` describes itself as a work in progress, and
nvchecker is a version trigger only. The watch is therefore stdlib-only glue: fetch, anchor-checked parse, name diff, cache. It has no
judgment of its own; the dispositions catalog and the resolver loop hold the judgments.

## Measured at the baseline (2026-10-04T10:44Z, the tool's own run)

The baseline holds:

- 173 `claude:setting`, 33 `claude:hook`, 407 `claude:env` and 6 `claude:mod` names;
- 1,341 `codex:config` paths;
- 152 `codex:feature` names (codex-cli 0.159.3 was installed; the release under watch was rust-v0.160.0).

The independent extraction of the same morning differs as follows:

- **Settings.** 161 of the 183 top-level keys the settings reference documents are common. Of the 22 keys only in the
  docs, 12 are global-config keys kept in `~/.claude.json`, not in settings files, and 2 are documented as removed.
  The 12 keys only in the SDK include `$schema` and `remote`.
- **Hooks and mods.** Equal.
- **Environment variables.** All 382 table names are included. The 25 extra names are 11 that the scrub section lists
  (names Claude Code removes from subprocess environments) and 14 that variable descriptions mention (OpenTelemetry's
  standard variables, `PATH`, `TERM`).
- **Codex config paths.** All 1,341 are in the extraction's 1,417. Its 76 extra paths are bare map and array
  containers (`x.*`, `x[]`).
- **Codex features.** The two features missing from the binary were added in rust-v0.160.0.

These are integrity checks of the parsers, not savings or quality measurements; no token-savings claim is made.

## Alternatives and overturn

- **Read SchemaStore or amitray007 as the baseline.** Rejected: they lag or skip versions.
- **Grep the changelog for "Added" only.** Kept as report-only context: prose cannot list names reliably.
- **Run the watch as `ExecStartPre=-` of `stack-currency.service`.** Rejected. That would make the currency unit
  networked (its description and tests say offline) and would share its 900 s start budget.

Overturn this record when:

- Anthropic ships an official settings schema or a listing command (it replaces S2/S3);
- amitray007 publishes every version over a sustained window (it becomes the env-var source);
- OpenAI ships a machine-readable feature or env registry per release.
