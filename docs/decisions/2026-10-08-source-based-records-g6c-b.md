# Source-based practice records and frozen replay inputs (2026-10-08)

Practice records explain their requirement, the supported upstream interface,
the evidence actually returned, alternatives and the condition that would reopen
the decision. The [MADR template](https://github.com/adr/madr/blob/ba75bb1b20d42af5746b246ad348c202419ae681/template/adr-template.md)
supplies that decision structure. The G6c review of 2026-10-08 is the dated
trigger for this correction; its conversation content is not record evidence.

The 27 documents assigned to this half of the review preserve their named
tools, pins, measurements, dates and acceptance boundaries. Twenty-three
current explanatory documents replace personal-message wording and links to
that wording with practice and primary-source references. Four documents stay
byte-identical as inputs to the earlier sealed registry. Existing line counts
are preserved so source citations can be reviewed without arithmetic drift.
The supplemental top-rule template span belongs to the separate half-A PR.

Material interface sources checked for the revised spans include:

- [RTK v0.51.0 native Codex installation and inverse](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/codex.rs)
  and the same pin's [awareness carrier](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/hooks/rtk-awareness-full.md).
- [Codex's historical hook trust discovery](https://github.com/openai/codex/blob/01fc69f4026735edfdf6789820549727a4867b11/codex-rs/hooks/src/engine/discovery.rs),
  [0.160.0 hook RPC](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/tui/src/hooks_rpc.rs)
  and [service-tier handling](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/tui/src/service_tier_resolution.rs).
- [OmniRoute's recorded 3.8.51 effort suffix](https://github.com/diegosouzapw/OmniRoute/blob/c1e30b7676975feb298b49eff6ff58923c04b89e/open-sse/executors/codex/reasoningSuffix.ts),
  [native release scripts at the recorded 3.8.52 pin](https://github.com/diegosouzapw/OmniRoute/blob/52823517533cfceec7abef2ff3e6285a19fe4121/package.json),
  and [the recorded compression/exclusion implementation](https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/open-sse/handlers/chatCore.ts).
- [jCodeMunch's pinned integration guide](https://github.com/jgravelle/jcodemunch-mcp/blob/6d5ae86c130f96624e2ca2d797fa3b853c210b9d/README.md),
  [Context Mode 1.0.169](https://github.com/mksglu/context-mode/blob/v1.0.169/README.md),
  and [the OTel 0.161.0 transform processor](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/v0.161.0/processor/transformprocessor/README.md).
- [Harbor's native evaluation interface](https://github.com/harbor-framework/harbor/blob/1e5c5c6db929a10a140d05e606882c671ae20729/README.md),
  the [MTEB methodology](https://arxiv.org/abs/2210.07316) and the
  [Ollama Modelfile contract](https://docs.ollama.com/modelfile).

Those interface reads are source review. They do not re-run the older model,
gateway, hook, broker, GPU or destination acceptance results. Historical tags,
observations and measured scopes remain dated; current upstream currency is a
separate check rather than a retrospective revision of an old experiment.

## Frozen registry boundary and the c8 expectation change

The historical registry
`evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json` has SHA256
`d5441b11b0641c3a1666851443db76e1703697962badb28f0fe48eac40f8171e`.
Its 15 hashed record occurrences reproduce at the review baseline. Four of
those records are documents assigned to this half:

| Frozen record | SHA256 |
| --- | --- |
| `2026-10-04-token-full-stack-owner-default.md` | `d6d0ba48d8881d746bdb9d4dc214339c2f8dba9842fad4152675437811a818d5` |
| `2026-10-04-2604-e2e-fix-wave.md` | `e60ca8cf00843aafeee60871ee638252c2a942688653c79669b6a96bccaadb4a` |
| `2026-10-04-repository-quality-rule.md` | `b11fac1ba8dfa8b64a1a1c53c24fe5bea69228e74c7142aa38ec169890326e91` |
| `2026-10-04-final-architecture-round2.md` | `98b57badb6779c9ef09c7ad3ba54773c1428042fe3cdf6f39362259741d10768` |

The registry's own consumer,
`evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py`,
checks the hashes and original authority fields while replaying the dated
batches. Its supported no-argument command regenerates the derived manifest;
`--check` checks that result. `render_tables.py --write RECORD` regenerates the
manifest's tables in the current explanatory record. Neither command provides
a migration or rewriting route for the sealed consensus inputs. The four
records and the registry therefore remain byte-identical. Their historical
content is retained replay evidence, not a current instruction or a source for
reintroducing personal-message text into new practice records.

The current explanatory layer-consensus document is outside that registry's
hash closure. Its test previously required the old authorization wording to
appear in current prose. The declared expectation now requires that wording
to be absent and a pinned upstream source to be present, while preserving the
rule, amendment, slot, limitation and registry-integrity assertions. Historical
`check_owner_batch` and its replay tests keep their original checks. This
changes current presentation rather than the recorded decision or the sealed
evidence chain. Only already registered edited documents use the repository's
native `host_receipts.register_file` route for their current-file registry.

The supported generation commands for this bounded check are:

```sh
python3 evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py --check
python3 evidence/artifacts/new-wsl-definitive-defaults-20261001/render_tables.py --check docs/decisions/2026-10-01-new-wsl-definitive-defaults.md
```

The registry regeneration predicates remain enforced. No frozen registry is
hand-edited, no selected component changes, and no new runtime acceptance
follows from the documentary correction.
