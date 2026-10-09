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
