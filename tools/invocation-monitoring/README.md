# Codex invocation provenance controls

The prototype source is pinned by
`7d20f02732f85ede3521f324efd4a11c5d250413`; its source manifest and earlier
fixture binding remain historical. The current
[controls manifest](codex-organic-controls-manifest.json) names the updated
counter/test hashes. The [decision](../../docs/decisions/2026-10-07-organic-counter-provenance-controls.md)
records source boundaries and alternatives.

This is the existing counter with an opt-in classification API, not another
collector or agent-trial runner. `qualify_records(batches, since=..., until=...,
controls=...)` accepts full retained record batches. `scan(..., controls=...)`
adds that projection, and the existing CLI accepts `--organic-controls`.
Use `python3 tools/invocation-monitoring/codex_counter.py --help` for its native
argument interface. No ordinary scan or native measurement is part of the
fixture acceptance below.

Control schema `codex-organic-control-input/1` carries the policy and mask
references, source owner/history declarations, per-turn requested/smoke flags,
complete named context, parent attribution and relaunch masks. References use
the catalog's exact CanonicalRef keys: `path`, `pointer`, `sha256`,
`source_commit`. Syntax/completeness declarations do not prove external file
resolution or original-context truth; an actual owner receipt needs those
retained sources and its independent observation.

The native adapter joins each owner's complete original streams before masks
or deduplication. Named masks apply to the relevant tool over its full turn,
including commands, skill-read attempts and MCP calls. Missing IDs, provenance,
context, original timing or unsupported call variants remain unknown. Per-tool
attribution may overlap and must not be summed as unique native calls. A skill
read attempt is never called successful activation.

Raw/legacy output remains an unqualified view. Keep native IDs and original
records private; publish only the sanitized proof/aggregates through the
existing registry and owner report. This module makes no READY, OIR, working-day
or adoption decision. The separately retained Claude path is not qualified by
these Codex fixtures.

Fixture check (local synthetic behavior only):

```sh
nice -n 19 ionice -c3 python3 -m unittest discover -s tools/invocation-monitoring -p test_codex_counter.py -v
```

Use an owned external cache for `TMPDIR`. The unchanged three prototype tests
and controlled counterexamples cover directed/smoke/first/named-turn exclusions,
original identity joins across files, copied history, missing inputs and
unsupported native formats. Every earlier failing condition remains in the
source/fixture receipt; no real native counter run is inferred from this check.

Sources: `native-agent-stack@a40a083172af588f4b97646db87dfc8ef3c0b60e:tools/skill-usage/skill_usage.py:1314-1655`
and `examples/claude-native/workflows/child-usage.mjs:2854-2878` for the existing
native ledger; `openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb:codex-rs/protocol/src/models.rs:1061-1155`,
`protocol.rs:1948-1960,2179-2184,3301-3307`,
`codex-rs/history/src/rollout_payload.rs:30-68` and
`codex-rs/rollout/src/recorder.rs:2061-2092` for the verified native wire/turn identities.
