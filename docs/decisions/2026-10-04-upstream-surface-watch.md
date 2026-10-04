# Decision: a zero-token watch for new Claude Code and Codex switches (2026-10-04)

**Decided by:** session native-agent-stack-99's unit U4, from the coordinator's source research of 2026-10-04 (first
party, third-party trackers, what nothing maintained covers). The sources were re-read with curl on 2026-10-04.
Revised the same day by unit U4-REPAIR, the one repair round after an independent review of the series: a second
settings source, an 80% floor per kind, cache-aged reports, profile mirrors dropped and the baseline regenerated.

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
  through the npm packument (2.1.289 resolves to SDK 0.3.289). It is machine-readable and versioned, but it is not
  the whole documented surface: on 2026-10-04 the settings reference documented 10 settings keys that sdk.d.ts
  0.3.289 does not type (among them `autoMode`, `sshHostAllowlist`, `useAutoModeDuringPlan`). Anthropic publishes no
  settings schema of its own (request: anthropics/claude-code#94232).
- **Claude Code settings keys, second source:** the key headings of
  <https://code.claude.com/docs/en/settings-reference.md> (live docs, no version stamp). `claude:setting` is the union
  of both sources, and each run records which source holds each key. The page's own structure decides what is not a
  settings key: the `## Global config settings` section, whose keys go in `~/.claude.json` and whose `**Scope**`
  bullets say `Global config` (12 keys, the same 12 by both rules on the 14:31Z copy), and the entries that open with
  a `<Warning>` "Removed in v...". There are three of those: `taskOutputMaxChars`, `permissionExplainerEnabled` and
  `teammateDefaultModel`; the last two are global-config keys.
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

The trackers are compared report-only (`--cross-check`). A cross-check failure never fails the run. The SchemaStore
sync point and the two READMEs below come from the coordinator's research of 2026-10-04 and were not re-read in this
unit. The unit's 14:00Z cross-check read the amitray007 release v2.1.289 and the chenrui333 `lifecycle.json`
(codex-cli 0.160.0).

- **amitray007/claude-code-schema** (per-release settings and environment catalogs, digest-published). Its releases
  skip versions: `gh api .../releases` at 2026-10-04T15:05Z lists none for 2.1.274-279 or 2.1.284-286. Its newest
  release, v2.1.289 (16 assets, each with a sha256 digest), was published 2026-10-04T08:29:40Z, and v2.1.288 on
  2026-10-03T08:09:34Z (`gh api .../releases/latest`, read 14:36Z). An earlier draft of this record called v2.1.288
  the newest; that held only before 08:29Z.
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

## Measured at the baseline (2026-10-04T15:03Z, the tool's own run)

The first baseline (10:44Z) was regenerated with the tool after the review round: the settings reference joined
`claude:setting`, and profile mirrors left `codex:config`. The versions are unchanged. The baseline holds:

- 183 `claude:setting` names, the union of 173 in `sdk.d.ts` and 171 in the settings reference. 161 are in both, 12
  only in `sdk.d.ts` (among them `$schema` and `taskOutputMaxChars`, which the reference marks removed) and 10 only
  in the reference;
- 33 `claude:hook`, 407 `claude:env` and 6 `claude:mod` names (unchanged);
- 1,034 `codex:config` paths: the 1,341 of 10:44Z without the 307 `profiles.*.<path>` mirrors of a root `<path>`;
- 152 `codex:feature` names (codex-cli 0.159.3 was installed; the release under watch was rust-v0.160.0).

The independent extraction of the same morning differs as follows:

- **Settings.** 171 of the 183 top-level keys the settings reference documents are in the baseline. Its 12 others are
  the global-config keys, two of them marked removed. The review round's count of 8 settings keys missing from the
  SDK (22 docs-only keys, minus 12 global-config, minus 2 removed) subtracted the two removed global-config keys
  twice; the live page gives 10. The baseline's 12 keys outside the extraction are 11 that only `sdk.d.ts` holds and
  `remote`, which the page documents only through `remote.defaultEnvironmentId`.
- **Hooks and mods.** Equal.
- **Environment variables.** All 382 table names are included. The 25 extra names are 11 that the scrub section lists
  (names Claude Code removes from subprocess environments) and 14 that variable descriptions mention (OpenTelemetry's
  standard variables, `PATH`, `TERM`).
- **Codex config paths.** All 1,034 are in the extraction's 1,417 schema paths. Its 383 others are 311 under
  `profiles.*` (the 310 mirrors of a root path and the bare `profiles.*` container) and 72 other bare map and array
  containers (`x.*`, `x[]`).
- **Codex features.** The two features missing from the binary were added in rust-v0.160.0.

The degraded artifacts of the review round, re-run with that round's parser on the real artifacts fetched at 15:03Z
against this baseline, each passed the absolute bounds and stopped at the 80% floor (exit 3):

- `config-schema.json` without its definitions gives 266 paths, and without `allOf`/`anyOf`/`oneOf` 361 (553 before
  the mirrors were dropped);
- `env-vars.md` cut at half its table gives 218 names.

This was a local integration check in scratch, not an upstream test.

The later offline repair records five anti-patterns and their regression checks: unresolved local Codex references
now fail integrity before any floor or baseline write; an existing watch state directory preserves prior findings
when its report disappears; CommonMark ATX headings are checked against all top-level Settings index names with a
two-key symmetric-difference tolerance before global/removed exclusions; bounded malformed JSON and Unicode inputs
remain unreadable records; and TypeScript hook and quoted-setting names use decoded escapes. The checks use cached
SDK 0.3.289, Codex rust-v0.160.0 and settings-reference artifacts plus synthetic mutations in
`tests/test_upstream_surface_watch.py` and `tests/test_currency_due.py`; they are local integration checks and
synthetic fixtures, not upstream tests.

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
