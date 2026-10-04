# Upstream-surface watch

`scripts/upstream_surface_watch.py` detects new user-switchable features of Claude Code and Codex (settings keys,
hook events, environment variables, built-in mods, Codex config keys and feature flags) without a model call. It
diffs what the current upstream releases expose against the committed
[baseline](../catalogs/foundation/upstream-surface-baseline.json), and lists every new name without a row in the
[dispositions catalog](../catalogs/foundation/upstream-surface-dispositions.json) as *unreviewed*. That list is the
work list of the resolver loop (owned by another session). Release-version drift stays with `scripts/currency_due.py`
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
back to the cache, and its origin says that too. `--dry-run` writes nothing, not even the cache, and creates no
directory. Otherwise a successful run writes the cache and then `latest.json` atomically (temporary file in the same
directory, fsync, mode 0600, `os.replace`). `--write-baseline` writes the baseline from the run's observations: it
refuses to replace an existing file without `--force`, and refuses when a kind was not observed. `--claude-channel`
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
| S3 | `claude:env`, `claude:mod` | <https://code.claude.com/docs/en/env-vars.md> (backticked upper-case tokens of two or more characters, page-wide); <https://code.claude.com/docs/en/plugins/mods/overview.md> (`cc-plugin-*`) | the `# Environment variables` title (100-5000 names); a built-in mods heading (1-300) |
| S4 | `codex:config`, `codex:feature` | `gh api repos/openai/codex/releases/latest` (one REST call, gh's own sign-in as in `tools/sota-convergence/github_freshness.py`), its `config-schema.json` asset verified against the published sha256 digest; `codex features list` of the installed binary | root `properties` with `features` (200-50000 paths, 30+ top-level, 20+ `features.*`); name/stage/enabled rows (30-5000) |
| S5 | changelog delta | <https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md>; Codex stable release notes (one `gh api graphql` call for the newest 100 releases, made only when the stable tag has moved past the baseline) | `## X.Y.Z` headings |
| cross-check | report-only | `amitray007/claude-code-schema` latest release (`settings.catalog.json`, `environment.catalog.json`); <https://raw.githubusercontent.com/chenrui333/codex-docs/main/docs/feature-flags/lifecycle.json> | none: a failure is recorded, never fatal |

The parsing rules:

- `claude:setting` takes the top-level members of `interface Settings` with a comment- and string-aware scanner
  (quoted and `$` keys, nested object types, function types, index signatures and literals).
- `codex:config` takes every named property's dotted path through `$ref`, `allOf`/`anyOf`/`oneOf`, map values (`*`)
  and array items (`[]`); a bare map or array container adds no path of its own.
- `codex:feature` runs `codex features list` with an empty temporary `HOME` and `CODEX_HOME`. The host's Codex home is
  neither read nor written, and `enabled` is the binary's default, not this host's choice.
- An unobserved kind is left out of the diff and named in `coverage.kinds_not_observed`, so it never shows as
  removed. A missing binary, for example, leaves `codex:feature` unobserved.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | the run finished, with or without new names |
| 1 | the baseline or dispositions catalog is invalid (or missing), `--check-dispositions` found errors, or a write failed |
| 2 | usage error, including a state directory inside the checkout and a summary that cannot fit 160 characters |
| 3 | `anchor missing: <name>`: an anchor was not found, or a count was outside its bound |
| 4 | `source unavailable: <name> (...)`: the source could not be fetched and has no usable cache |

## latest.json and the resolver

`latest.json` has the keys `schema_version`, `generated_at`, `versions` (watched, baseline and dist-tag versions;
the SDK match), `new`, `removed`, `stage_changed`, `changelog`, `unreviewed`, `coverage` (mode, every source's URL,
origin, fetch time, version and sha256; observed kinds; counts; notes) and `cross_check`, then `summary_line`.

- Each `new` and `removed` item is `{key, surface, kind, name}`; a new `codex:feature` item also carries `stage` and
  `enabled`.
- `unreviewed` is the list of new keys (`surface:kind:name`) without a dispositions row.
- `changelog.claude` and `changelog.codex` carry the newer versions or releases, the entry counts and the first 20
  entries that start with "Added"/"New", sit under a "New ..." heading, or name a setting, env var, hook, mod or
  command. This is grep-level context, not a classification.

The resolver works through `unreviewed`. For each key it adds one dispositions row; a key that has a row no longer
counts. Applying the decision itself (a settings template, a Codex profile) is the resolver's carrier, not this
script's. `scripts/currency_due.py` reads the same file offline and adds `surface_unreviewed` to the session notice
while `generated_at` is at most three days old.

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
Validation is linear in the rows: about 1,200 rows check in milliseconds.

## Daily run

[`upstream-surface-watch.service`](../adoption/templates/systemd/upstream-surface-watch.service) runs
`upstream_surface_watch.py --network`. [`stack-currency.service`](../adoption/templates/systemd/stack-currency.service)
pulls it in with `Wants=` and orders itself `After=` it, so the existing daily
[`stack-currency.timer`](../adoption/templates/systemd/stack-currency.timer) runs the watch first. `Wants=` is weak, so
a failed, timed-out or uninstalled watch never blocks the currency run. Installing the units is host wiring:

```sh
sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' adoption/templates/systemd/upstream-surface-watch.service > ~/.config/systemd/user/upstream-surface-watch.service
sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' adoption/templates/systemd/stack-currency.service > ~/.config/systemd/user/stack-currency.service
systemd-analyze --user verify ~/.config/systemd/user/upstream-surface-watch.service ~/.config/systemd/user/stack-currency.service ~/.config/systemd/user/stack-currency.timer
systemctl --user daemon-reload
```

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
