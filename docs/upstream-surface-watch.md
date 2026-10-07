# Upstream-surface watch

`scripts/upstream_surface_watch.py` detects new user-switchable features of Claude Code and Codex (settings keys,
hook events, environment variables, built-in mods, Codex config keys and feature flags) without a model call. It
diffs what the current upstream releases expose against the committed
[baseline](../catalogs/foundation/upstream-surface-baseline.json), and lists every new name without a row in the
[dispositions catalog](../catalogs/foundation/upstream-surface-dispositions.json) as *unreviewed*. That list is the
work list of the resolver loop (owned by the currency lane on NativeStack2604).
Release-version drift stays with `scripts/currency_due.py`
and `tools/sota-convergence/github_freshness.py`; this watch adds the feature names they do not see. Why these
sources, and what no maintained tool covers:
[decision record](decisions/2026-10-04-upstream-surface-watch.md).

## Usage

```sh
python3 scripts/upstream_surface_watch.py --network             # fetch, diff, write the cache and latest.json
python3 scripts/upstream_surface_watch.py --dry-run             # the report as text, replayed from the cache
python3 scripts/upstream_surface_watch.py --dry-run --json      # the latest.json document
python3 scripts/upstream_surface_watch.py --summary             # one line of at most 160 characters
python3 scripts/upstream_surface_watch.py --check-dispositions  # validate the dispositions catalog only
python3 scripts/upstream_surface_watch.py --network --cross-check --dry-run  # add the third-party comparisons
python3 scripts/upstream_surface_watch.py --network --write-baseline --force  # re-baseline (a reviewed change)
```

`--network` is off by default. Without it, the run reads the cached fetches in the state directory
(`${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/surface-watch/cache`) and says so: the summary starts with
`surface watch (cache):`, and every source in `coverage.sources` names its origin. A network fetch that fails falls
back to the cache, and its origin says that too; the summary (and so the journal line) then starts with
`surface watch (partial cache):`, or `(cache)` when every fetch fell back. A report built partly or wholly from the
cache is as old as that cache: `generated_at` is the oldest cached fetch time (`run_at` is the run's own time), so a
gh sign-out or an outage cannot keep an old report looking fresh. A cache entry without a fetch time is no cache.
`--dry-run` writes nothing, not even the cache, and creates no
directory. Otherwise a successful run writes the cache and then `latest.json` atomically (temporary file in the same
directory, fsync, mode 0600, `os.replace`). `--write-baseline` writes the baseline from the run's observations: it
needs `--network` (a usage error without it), refuses to replace an existing file without `--force`, refuses when a kind
was not observed, and refuses (exit 4) when any recorded source came from the cache or was unavailable, because a baseline
made from a cached artifact would grandfather every switch added since that fetch. It writes the cache and `latest.json`
first and the baseline last: a failed earlier write leaves the old baseline, and a failed baseline write puts the earlier
`latest.json` back, or removes this run's when there was none or the earlier one cannot be rewritten (a full filesystem
fails a rewrite, not an unlink), because a re-baselining run's report says "nothing new" and must not sit beside the old
baseline: a lost report is an incomplete check for the currency job, where a fresh one with nothing unreviewed would clear
the notice. A report that can be neither put back nor removed is named in the error. `--claude-channel`
selects the npm dist-tag under watch (default `latest`, the channel of `autoUpdatesChannel` in
`adoption/templates/claude.settings.template.json`). `--codex-bin none` skips the Codex probe.

The summary line ends with a runnable command: the checkout's own copy of the script with `--dry-run`, which
replays the cache. When that command leaves the counts no room, it ends with `cat` of `latest.json` instead.

## Sources

All URLs were re-read on 2026-10-04 (curl, HTTP 200); `S5` is report-only text.

| Id | Kind | Source | Anchor (exit 3 when absent or out of bounds) |
| --- | --- | --- | --- |
| S1 | trigger, versions | <https://registry.npmjs.org/-/package/@anthropic-ai/claude-code/dist-tags>, `.../@openai/codex/dist-tags` | a `latest` version |
| S2 | `claude:setting`, `claude:hook` | the `sdk.d.ts` of the `@anthropic-ai/claude-agent-sdk` release whose `claudeCodeVersion` equals the watched version, resolved through <https://registry.npmjs.org/@anthropic-ai/claude-agent-sdk> and read from `https://unpkg.com/@anthropic-ai/claude-agent-sdk@<version>/sdk.d.ts` | `interface Settings` (top-level keys, 50-2000); `HOOK_EVENTS: readonly [...]` (10-300) |
| S2b | `claude:setting` (second source) | <https://code.claude.com/docs/en/settings-reference.md>: the top-level keys of its key headings, without the `## Global config settings` section's keys and the entries marked removed | the `# All settings` title and a key heading in the `## Global config settings` section; 50-2000 keys |
| S3 | `claude:env`, `claude:mod` | <https://code.claude.com/docs/en/env-vars.md> (backticked upper-case tokens of two or more characters, page-wide); <https://code.claude.com/docs/en/plugins/mods/overview.md> (`cc-plugin-*`) | the `# Environment variables` title (100-5000 names); a built-in mods heading (1-300) |
| S4 | `codex:config`, `codex:feature` | `gh api repos/openai/codex/releases/latest` (one REST call, gh's own sign-in as in `tools/sota-convergence/github_freshness.py`), its `config-schema.json` asset verified against the sha256 digest GitHub publishes for it (a release without one is read unverified: the source's `digest_check` and a coverage note say so); `codex features list` of the installed binary | root `properties` with `features` (200-50000 paths, 30+ top-level, 20+ `features.*`); name/stage/enabled rows (30-5000) |
| S5 | changelog delta | <https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md>; Codex stable release notes (one `gh api graphql` call for the newest 100 releases, made only when the stable tag has moved past the baseline) | `## X.Y.Z` headings |
| cross-check | report-only | `amitray007/claude-code-schema` latest release (`settings.catalog.json`, `environment.catalog.json`); <https://raw.githubusercontent.com/chenrui333/codex-docs/main/docs/feature-flags/lifecycle.json> | none: a failure is recorded, never fatal |

The parsing rules:

- `claude:setting` is the union of two sources, and `coverage.key_sources` and each new item's `sources` say which
  source holds a key, so a key that one source lacks is visible on every run. From `sdk.d.ts` it takes the top-level
  members of `interface Settings` with a comment- and string-aware scanner (quoted and `$` keys, nested object
  types, type arguments such as `Record<string, Array<string>>`, function types, index, call and construct
  signatures, literals, and members that end at a line break rather than `;`). From the settings reference it takes
  every key heading outside fenced code blocks; a dotted heading such as `` `sandbox.enabled` `` gives its first
  segment. It leaves out the keys of the `## Global config settings` section, or whose `**Scope**` bullet says
  `Global config`: they go in `~/.claude.json`, not in a settings file. It also leaves out an entry that opens with
  a `<Warning>` saying `Removed in v...`. That only drops the docs heading: a key that `sdk.d.ts` still types, such as
  `taskOutputMaxChars`, stays (with `sources` `["sdk.d.ts"]`). Each source has its own 80% floor.
- `codex:config` takes every named property's dotted path through `$ref`, `allOf`/`anyOf`/`oneOf`, map values (`*`)
  and array items (`[]`); a bare map or array container adds no path of its own. A named profile repeats most root
  keys (`profiles.*.<path>` beside `<path>`), and such a mirror is left out, so one new Codex feature flag is at most
  one unreviewed key per kind: `codex:config:features.<name>` and `codex:feature:<name>`. A key that only a profile
  has stays.
- `codex:feature` runs `codex features list` with an empty temporary `HOME` and `CODEX_HOME`. The host's Codex home is
  neither read nor written, and `enabled` is the binary's default, not this host's choice.
- An unobserved kind is left out of the diff and named in `coverage.kinds_not_observed`, so it never shows as
  removed. A missing binary, for example, leaves `codex:feature` unobserved.

Integrity checks apply before the baseline floor in every mode: all local Codex `$ref` targets must resolve before
`--write-baseline` can write. Settings headings follow [CommonMark ATX rules](https://spec.commonmark.org/0.31.2/#atx-headings);
their top-level names, including global and removed entries before exclusion, must agree with the Settings index's
first-column backticked names within two distinct keys. TypeScript hook and quoted-setting literals decode
[string escapes](https://tc39.es/ecma262/#sec-literals-string-literals), including line continuations; malformed
numeric escapes fail the anchor. These are local integration checks against cached SDK 0.3.289, Codex rust-v0.160.0
and docs artifacts, with synthetic malformed-input controls.

## Instruction-document watch (2026-10-05)

Enabled `claude:doc:*` and `codex:doc:*` dispositions rows also watch the body
of their HTTPS `source`, against the reviewed `value.sha256`. The three current
rows cover Claude memory, Claude skills and the Codex AGENTS.md guide. Fetches
request Markdown and reuse the existing bounded HTTP, cache and freshness
path; a server that returns HTML instead is compared as that full body.

Each result appears in `documents` with its expected and observed digest,
`changed` flag and `carrier` audit record. A changed body adds the existing
row's key to `unreviewed`, even though its name was already reviewed. The
daily currency notice therefore reopens the instruction audit through its
existing unreviewed count. A failed required fetch keeps the watch incomplete;
an offline replay preserves the cached result and its actual fetch date.

These are body-change alerts, not semantic judgments: site markup changes can
also request review. `--write-baseline` does not accept a changed document.
After rereading the upstream page and rerunning the
[context audit](decisions/2026-10-05-harness-context-budget.md), update the
row's digest and dated review explicitly. The local tests use synthetic
document bodies; the committed digests were fetched from the named pages.

## What the watch does not cover

It compares names from the sources above and nothing else:

- Claude Code's global-config keys in `~/.claude.json`: the settings reference's `## Global config settings` section
  (12 keys on 2026-10-04), left out on purpose.
- Claude Code CLI flags and subcommands, slash commands, keybindings, and the fields inside hook input and output or
  plugin and MCP manifests.
- Codex environment variables, CLI flags and slash commands, `requirements.toml` keys, and config keys that the Codex
  docs describe but `config-schema.json` does not hold (an independent extraction on 2026-10-04 counted 59).
- A change of a key's type, default, scope or meaning: only names are compared, apart from the `codex:feature` stage.
- Anything in the changelogs (S5) beyond the report-only entry titles, and any source not listed above.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | the run finished, with or without new names |
| 1 | the baseline or dispositions catalog is invalid (or missing), `--check-dispositions` found errors, or a write failed |
| 2 | usage error, including a state directory inside the checkout and a summary that cannot fit 160 characters |
| 3 | `anchor missing: <name>`: an anchor was not found, a local schema reference was unresolved, a string literal was malformed, the settings index guard failed, or a count was outside its bound; or `anchor missing: <kind> below 80% of baseline`: an observed kind holds fewer than 80% of its baseline names. A reviewed removal of more than 20% at once needs `--network --write-baseline --force`, which skips the floor while retaining source integrity checks |
| 4 | `source unavailable: <name> (...)`: the source could not be fetched and has no usable cache, or `--write-baseline` found a source that came from the cache |

## latest.json and the resolver

`latest.json` has the keys `schema_version`, `generated_at` (the time of the oldest data it holds), `run_at`,
`versions` (watched, baseline and dist-tag versions; the SDK match), `new`, `removed`, `stage_changed`, `changelog`,
  `unreviewed`, `documents` (the instruction-document digest comparisons), `coverage` (mode; `from_cache`, the sources a `--network` run took from the cache; every source's URL,
origin, fetch time, version, sha256, `required`, `cross_check` and, for a digest-published asset, `digest_check`;
observed kinds; counts; notes) and `cross_check`, then `summary_line`.

- Each `new` and `removed` item is `{key, surface, kind, name}`; a new `codex:feature` item also carries `stage` and
  `enabled`.
- `unreviewed` is the list of new keys (`surface:kind:name`) without a dispositions row.
- `changelog.claude` and `changelog.codex` carry the newer versions or releases, the entry counts and the first 20
  entries that start with "Added"/"New", sit under a "New ..." heading, or name a setting, env var, hook, mod or
  command. This is grep-level context, not a classification.

The resolver works through `unreviewed`. For each key it adds one dispositions row; a key that has a row no longer
counts. Applying the decision itself (a settings template, a Codex profile) is the resolver's carrier, not this
script's. `scripts/currency_due.py` reads the same file offline and adds `surface_unreviewed` to the session notice
while the report's data is at most three days old (its `generated_at`, and the fetch time of every source it took
from the cache, which it re-reads from `coverage.sources`; report-only cross-checks do not count) and neither
`generated_at` nor `run_at` is more than one hour ahead of its clock, and only when `coverage.kinds_not_observed` is
empty and no non-cross-check source in `coverage.sources` has origin `unavailable` or `skipped`. Unobserved kinds or
unavailable or skipped required or probed sources make the check `surface watch incomplete`; report-only sources
with `cross_check: true` do not make it incomplete. Malformed kinds or sources coverage is
`surface watch output unreadable`, and so is a report whose `schema_version` is not the integer that the reader
understands (`SURFACE_SCHEMA_VERSION`, 1, kept equal to the watch's `SCHEMA_VERSION` by a test; absent, a string, a
boolean or a float are refused too), so that a rollback or a partly updated checkout never reads a report whose fields may
mean something else. A missing `latest.json` without a watch state
directory is only the coverage note `surface watch not run` (the unit may not be installed on that host). An existing
watch state directory means observed before: a missing report is `surface watch stale`; an unreadable or non-regular
report is `surface watch output unreadable`. File-access errors, Unicode errors and JSON parsing `ValueError`s,
including integer conversion limits, are unreadable records. These, incomplete coverage and an older or future-dated
report are checks that could not answer, handled as an incomplete skill check is. The earlier due-file stays, and
with nothing else due the line says
`stack currency: nothing known due, surface watch stale; details: <command>` instead of "nothing due".

## Dispositions

Each row has ten fields:

| Field | Rule |
| --- | --- |
| `key` | `surface:kind:name`, unique; any kind is accepted |
| `disposition` | one of `enabled`, `adopt-pending`, `declined`, `default-on`, `not-applicable`, `defer-user`, `baseline-unreviewed` |
| `reason` | one line, at most 160 characters |
| `source` | an https URL or `path:line` (`repo@pin:path:line` included) |
| `carrier` | required for `enabled` and `adopt-pending` |
| `value` | any JSON |
| `scope` | short string or null |
| `overturn` | required except for `baseline-unreviewed` |
| `reviewed_utc` | `YYYY-MM-DDTHH:MM:SSZ` |
| `version` | the upstream version the review read |

The catalog's `rules` block documents every value. `baseline-unreviewed` marks a name grandfathered at the baseline
version; like every row, it is excluded from the unreviewed count. `adopt-pending` is decided but not yet applied.
Validation is linear in the rows: about 1,200 rows check well under a second (the test's bound is 1.0 s).

## Daily run

[`upstream-surface-watch.service`](../adoption/templates/systemd/upstream-surface-watch.service) runs
`upstream_surface_watch.py --network`. [`stack-currency.service`](../adoption/templates/systemd/stack-currency.service)
pulls it in with `Wants=` and orders itself `After=` it, so the existing daily
[`stack-currency.timer`](../adoption/templates/systemd/stack-currency.timer) runs the watch first. `Wants=` is weak, so
a failed, timed-out or uninstalled watch never blocks the currency run, which then records the surface check as not run.
Installing the units is host wiring; [`adoption/lifecycle.md`](../adoption/lifecycle.md) carries the same block as the
canonical installation:

```sh
sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' adoption/templates/systemd/upstream-surface-watch.service > ~/.config/systemd/user/upstream-surface-watch.service
sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' adoption/templates/systemd/stack-currency.service > ~/.config/systemd/user/stack-currency.service
systemd-analyze --user verify ~/.config/systemd/user/upstream-surface-watch.service ~/.config/systemd/user/stack-currency.service ~/.config/systemd/user/stack-currency.timer
systemctl --user daemon-reload
```

The paper window. `stack-currency.timer` is `Persistent=true` with `RandomizedDelaySec=15m`, so after a day the host was
down the catch-up can start the networked watch within 15 minutes of WSL starting, which can be during a paper session.
`upstream-surface-watch.service` therefore runs `upstream_surface_watch.py --paper-window-check` as its `ExecCondition=`
before the run. The check reads no state and makes no request; it exits 1 on a weekday from 09:00 to 16:30
America/New_York (the US regular session, 09:30 to 16:00, with a 30-minute margin each side; a holiday inside it is
deferred too) and 0 otherwise, and 2 on a bad `--now`. `systemd.service(5)` says that an `ExecCondition=` exit status of
1 to 254 skips the remaining commands and the unit "is not marked as failed", so the watch is deferred to the next daily
run, and `stack-currency.service`, which only `Wants=` it, still runs and counts the last report (at most three days old; an
older one is `surface watch stale`). A host without a time-zone database runs the watch rather than never running it, with a
note on stderr. `--now YYYY-MM-DDTHH:MM:SSZ` evaluates the check at another instant. The live paper schedule on this host
(`systemctl --user list-timers`, read 2026-10-04) is three user timers, `paper-recover-a2-gate-20261005.timer` (Monday
06:45 EDT), `paper-alpaca-a1-preflight-20261005.timer` (09:30) and `ibkr-paper-readonly-20261005.timer` (09:35); none is a
repository marker the check could read, so market hours plus the margin stay the definition.

## Overturn conditions

Replace a source when one of these holds:

- Anthropic publishes an official Claude Code settings schema or a command that lists settings, environment variables
  or mods for the installed version (requested in anthropics/claude-code#94232). It replaces S2/S3.
- `amitray007/claude-code-schema` publishes a release for every Claude Code version over a sustained window. It
  could then become the env-var source instead of the docs-page grep.
- OpenAI publishes a machine-readable Codex feature registry or env-var list with each release. It replaces the
  `codex features list` probe.
- A parser regression that passes its anchors: add the failing artifact as a fixture and a mutant control in
  `tests/test_upstream_surface_watch.py`.
