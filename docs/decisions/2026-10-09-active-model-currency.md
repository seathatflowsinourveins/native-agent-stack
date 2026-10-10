# Active hosted-model currency from native catalogs

The owner's current-model rule needs an active-selector check as well as the
existing model-age review inventory. Adopt the installed clients' model
metadata and extend this repository's currency collector and native hook
output convention. Do not replace either client's catalog or implement a
new gateway. The supported refresh/check procedure and ownership boundary
are in [the operational guide](../active-model-currency.md).

## Primary observations

The 2026-10-09T20:31:55Z private snapshot contains these metadata-only captures:

| Source | Native command or endpoint | Rows | SHA256 |
| --- | --- | ---: | --- |
| Codex 0.162.0 | `codex debug models` | 10 | `cc9279e1a7482f10ad1f79ba102d04f5437673107409f5aaf4921007deaeac37` |
| OmniRoute v3.8.51 | `GET /v1/models` | 625 | `5ed5f7ddf57ee74537291d26c2417c9c27af870370de28256993c981b92ea3ab` |
| Anthropic | authenticated `GET /v1/models`, complete pagination | 13 | `6074378b36551b3b6dfddab931b872a2a20536e7eced1d6c5b355c2174b6f3ec` |

The latest stable native generations for the declared families are
`gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-luna`, `claude-opus-5-5`,
`claude-sonnet-5-5`, `claude-haiku-5-5` and `claude-fable-5-1`.
Gateway aliases only add observed routes/effort names; synthetic gateway
creation times never decide model release rank. Codex's `OnlineIfUncached`
export does not certify a fresh network retrieval. A native routing identity
does not prove which backend or effort a subsequent inference would deliver.
Neither model inference nor a lane Claude process was run for this slice.

## Landscape and decision

Primary implementation references are OpenAI Codex `rust-v0.162.0`
[`debug models`](https://github.com/openai/codex/blob/rust-v0.162.0/codex-rs/cli/src/main.rs),
OmniRoute `v3.8.51`
[`/v1/models`](https://github.com/diegosouzapw/OmniRoute/blob/v3.8.51/src/app/api/v1/models/route.ts),
the official [Anthropic model list](https://platform.claude.com/docs/en/api/models/list),
and the [native SessionStart hook contract](https://developers.openai.com/codex/hooks).

The landscape also checked `taygetea/model-currency` at
`d643fcd076f0c7e7d1d5e8dc55e0e6cfe699f4bd` and `anomalyco/models.dev` at
`4b064e049788abeabe24910bb96f260e3c931d92`. Neither supplies this host's
three native observations plus its distinction between active defaults and
immutable dated measurements. Extend the existing standard-library workflow
for that demonstrated gap. A maintained upstream that provides those exact
inputs and preserves those distinctions would replace this glue.

## Verification and application boundary

Behavioral fixtures exercise newer native generations, stale defaults,
observed alias limits, expired/missing sources, dated-record preservation,
collector failures and the actual shipped SessionStart command. Native host
scan and full repository validation are recorded with the published PR.
The maintained research supervisor's current Opus default moves to 5.5;
its September 19 run records and frozen comparisons remain unchanged.
There is no new 5.5 execution or usage claim.

User-level hook installation belongs to the CC. The PR carries an additive
RFC 6902 patch and its inverse; the lane has applied neither. Production
checks use real UTC, fail incomplete after 24 hours without refreshed native
observations, and make no network call or configuration write themselves.

## Review amendment: retained snapshot and precomputed notice (2026-10-09)

The preceding paragraphs retain the initial proposal and its measurements.
The coordinator's review repair withdraws the separate SessionStart model
audit and its unapplied user patch. Startup uses the existing due-file notice;
the September 30 decision's no-startup-audit contract remains authoritative.
The daily units are templates; native systemd 259.5 readback found no installed
stack-currency.timer. No host unit or user configuration was applied.

The committed catalog is now an explicitly versioned comparison snapshot with
no 24-hour expiry. Unknown/expired live model observations are coverage gaps
for the collector rather than fatal suppression of the other currency checks.
The original bundle label and source hashes/counts remain; independently
unattested source times are null. Generation uses per-source embedded times
when supplied and never copies a bundle label into all sources.

Red-before-green fixtures reproduce both public CLI paths after the old
expiry, argv and single JSON-command omissions, caller-home dependence, source-time
invention, unrelated large/non-UTF8 files, comments/punctuation, repeated JSON
locations, new Claude families and pinned allowlists. The retired append/pop
test is replaced with actual startup-policy guards. Frozen research comparison
source and receipts remain unchanged. Command-list gaps from this repair
are corrected in the October 10 follow-up below. No model/provider execution is claimed.

Pinned implementation sources are CPython v3.13.16 AST/shlex/JSON/subprocess,
Codex 0.162.0 c1382380 models-manager/cache and manager, the Anthropic models
API 2023-06-01, RFC 6901/6902 and systemd v259.5. Exact links and operational
semantics are in the amended [guide](../active-model-currency.md). The earlier
24-hour/startup-patch assertions above are superseded by this dated amendment.

## Review follow-up: command lists and generator parity (2026-10-10)

The earlier JSON-command coverage claim was incomplete: command lists were
treated as argv, and `upstream_commands` was not recognized. The two reported
old-model commands now fail the check when placed at active paths. JSON
command strings and string items in command lists use the POSIX lexer shipped
by [CPython v3.13.16](https://github.com/python/cpython/blob/v3.13.16/Lib/shlex.py),
preserving quoted arguments and locating repeated commands independently.
Normalized command-like keys and nested containers are covered; literal argv
lists keep their argument boundaries. Computed shell commands remain outside
this static check's coverage.

The reported source files retain their bytes as explicit dated records:
the [runtime experiment's October 3 publication note](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a7f411faf6154329ceb592f045b4abae24168a26/blueprints/convergence-practice/omniroute-runtime-workers/experiment.json#L37)
preserves its September 30 commands and observations; the
[September 27 token-efficiency reference edition](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a7f411faf6154329ceb592f045b4abae24168a26/docs/token-efficiency-stack.json#L6)
retains its observed source-host setup. Exemptions name exactly those paths
and reasons. Their same command payloads are required to fail at active paths.

The checkout acceptance now requires model coverage to be `current`, not only
a collector exit of 0. Its fixture is a nonexpiring comparison snapshot and
is checked beyond the former October 10 expiry; explicit live-observation
fixtures still exercise expiry. This follows the repository's versioned
snapshot contract, using [CPython v3.13.16 unittest assertions](https://github.com/python/cpython/blob/v3.13.16/Lib/unittest/case.py).
Selector fields parse their first value without lexing the explanatory tail;
unclosed quoted command arguments still produce a coverage gap. Model `-m`
requires a native client context, respecting [Git v2.53.0's message option](https://github.com/git/git/blob/v2.53.0/Documentation/git-commit.adoc).

The committed catalog was regenerated by `active_model_currency.py generate`
from the three original captures and their retained recording label. Native
model IDs, aliases, routing identities, source hashes and row counts are
unchanged. The generator's null observation times and timestamp origins replace
the manually added source metadata; the original bundle declaration remains
in `recorded_at`. The new generation time describes this regeneration, not a
new upstream observation. Generator-schema and future-clock regressions
guard that distinction. No provider/model call or host application occurred.

The collector documentation now names all seven possible counts and
`model check incomplete`, matching the existing
[`COUNT_KEYS` and coverage handling at a7f411fa](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a7f411faf6154329ceb592f045b4abae24168a26/scripts/currency_due.py#L112).
Spacing in this record, the guide and service comment is corrected without
changing the service invocation. Affected tests and FULL validation are
reported with the fix push; whole-repository CI and CC landing remain separate gates.

The old-base branch's tracked-tip private-name scan also encountered inherited
content already corrected by CC-landed [#934 at 3c01bdddc66896f8e36f9f21d452710808a9557e](https://github.com/seathatflowsinourveins/native-agent-stack/commit/3c01bdddc66896f8e36f9f21d452710808a9557e).
Only that approved commit's two historical file hunks are replayed here, with
native evidence bindings updated. The model experiment and token-efficiency
reference above retain their bytes. No scanner waiver or rebase is used;
the full tracked-tip and exact pushed history-range checks must pass before push.
