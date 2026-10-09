# Hosted model selector currency

The [latest-models manifest](../catalogs/foundation/latest-models.json) is
generated from the native Codex catalog, OmniRoute's `/v1/models` and the
Anthropic model-list API. It selects the greatest stable generation within
the owner's seven hosted families: GPT Sol, Astra and Luna; Claude Opus,
Sonnet, Haiku and Fable. Availability alone does not mean latest: both native
catalogs retain older models. Gateway `created` values describe catalog
construction and are never used as model release dates.

## Generate and check

Collect all three native JSON catalogs into a dated private snapshot. Use
the installed `codex debug models` command, the configured OmniRoute models
endpoint and Anthropic's paginated `GET /v1/models`. The existing credential
runner supplies the declared Anthropic variable to the metadata-only runtime;
never put a value in commands or records. No Claude process, SDK inference
or model invocation is needed. Preserve the raw captures and their timestamps.

```sh
python3 scripts/active_model_currency.py generate \
  --codex /private/model-snapshot/codex-models.json \
  --omniroute /private/model-snapshot/omniroute-models.json \
  --claude /private/model-snapshot/claude-models.json \
  --observed-at 2026-10-09T20:31:55Z \
  --output catalogs/foundation/latest-models.json

python3 scripts/active_model_currency.py check --root . --host --json
```

The timestamp is the actual snapshot observation, never a later date used
to disguise old input. The manifest carries source hashes and counts.
Codex 0.162.0's native export uses `OnlineIfUncached`; a successful export
can be cached or a fallback. The manifest explicitly does not certify a
fresh upstream network fetch, a delivered effort tier or routing quality.
OmniRoute's advertised effort aliases are accepted only when observed in
the captured catalog. For v3.8.51, requested Sol `max` is capped at `xhigh`;
the model ID check does not override or qualify that transport behavior.

Check exits **0** for current declared selectors, **1** for stale selectors,
and **2** when the manifest or scan cannot answer. A manifest older than
24 hours, more than five minutes ahead, missing a catalog, or carrying an
invalid alias target cannot produce a current result. Refresh from native
metadata before the next currency run when it expires. No check switches
models, edits user settings or silently substitutes another family.

## Active scope and preserved records

The checker extracts actual model fields, Python/environment/argument
defaults, shell launcher flags and structured Markdown agent/template
selectors. It covers active lane configuration too; `.md` and `lanes/`
are not blanket exemptions. `--host` adds the two named user settings files,
agent directories, launcher directories, CC/co-op/API-action tools and the
named `~/code/us-equities-trading` repository when present. There is no
home-directory or disk crawl. Findings contain a locator and model IDs;
other configuration values and source lines are never printed.

Exemptions identify records by role: evidence/receipts, dated decisions and
research, native timestamped measurement objects, tests/dependencies, and
the explicitly frozen convergence experiments listed in the implementation.
A date in an active config filename does not exempt it. The maintained
new-WSL install-kit configs remain active despite the dated kit directory.
Historical sections of mixed guides are separate from their current
commands. Other lanes' N2, paper-open-e2e and STOP paths are outside this
currency scan's ownership and are not read.

The existing model-age inventory is source-review metadata for
`freshness_propose.py`; it does not select a runtime model. Its October 7
Haiku 4.5 observed-use declaration remains a dated claim requiring separate
reconciliation after owner application/readback. This check does not rewrite
it into evidence that a host switched. Local weights/package age and their
landscape exceptions remain under that existing inventory and validator.

The maintained research supervisor had an actual Opus 5 default. Its current
launch and response check now select Opus 5.5. The September 19 acceptance,
usage records and frozen comparison inputs retain the models they ran with;
this source change makes no new native execution claim.

## Currency and SessionStart wiring

Every `scripts/currency_due.py` collection invokes the offline check. A stale
selector contributes a due notice and returns 1. An incomplete check returns
2 and preserves any existing due notice. The daily timer already calls this
collector; no separate daemon is introduced.

[model-currency.hooks.template.json](../adoption/templates/model-currency.hooks.template.json)
adds an independent `startup|resume` SessionStart group for both native clients.
Its offline check emits the supported `hookSpecificOutput.additionalContext`
notice only for stale/incomplete results. It starts no model and makes no
network call. The thirty-second command timeout covers the measured bounded
host scan; existing currency notices keep their own group and behavior.

The [CC-apply RFC 6902 patch](../adoption/templates/model-currency.user-hooks.patch.json)
appends only the new SessionStart group to each client's existing list.
The CC applies it once after merge, preserves all other groups/settings,
checks for an existing identical command, and reviews the new Codex handler
through the native `/hooks` interface at its discovered source/key. No trust
state, user settings, hooks or running session is changed by this PR.

The Codex-native routing identities `gpt-reserve` and `codex-auto-review` are
recorded only if present in that native capture. They do not name a model
generation; the manifest does not claim to resolve their selected backend.
An arbitrary old model cannot be declared a routing identity to pass the check.

## Primary sources and existing practice

- Installed Codex 0.162.0 `debug models`; [native CLI source](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/cli/src/main.rs#L2093).
- [Official GPT Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
  [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
  [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) guidance.
- [Anthropic model-list API](https://platform.claude.com/docs/en/api/models/list),
  [current models](https://platform.claude.com/docs/en/about-claude/models/overview)
  and [native model alias semantics](https://code.claude.com/docs/en/model-config).
- OmniRoute v3.8.51's maintained [models route](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/app/api/v1/models/route.ts)
  and [catalog construction](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/app/api/v1/models/catalog.ts).
- [Native SessionStart hooks](https://developers.openai.com/codex/hooks) and
  this repository's existing currency collector/notice output conventions.

The landscape also checked `taygetea/model-currency` at
`d643fcd076f0c7e7d1d5e8dc55e0e6cfe699f4bd` and `anomalyco/models.dev` at
`4b064e049788abeabe24910bb96f260e3c931d92`. Their catalogs provide useful
leads but do not supply this host's three native catalogs or active-selector
policy. This implementation extends the existing stdlib repository workflow
without a new catalog or gateway dependency.
