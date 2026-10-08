# Decision: the always-loaded instruction layers keep only the philosophy (2026-10-08)

Date: 2026-10-08. Lane: shared (root `AGENTS.md` is a shared hot file in [`docs/lanes.md`](../lanes.md)).
Status: directed by the owner and ruled by the command center on 2026-10-08; repository record awaiting review.

## Context

On 2026-10-08 the owner said that the rules in the instruction files were not his. His own rules are the
research-convergence philosophy: research-driven and upstream-driven, decided by evidence. He asked for everything
else in those files to be cleaned up. The day before he had asked for curated instruction files that keep his
philosophy, while new sessions still pick up the essentials (skills, agents, MCP tools, handbooks, GitHub workflow)
natively. This record paraphrases that direction and quotes no message.

## Decision

Every always-loaded layer carries the same four-rule core, byte for byte: research before acting, upstream is the
truth, decide by evidence, and the ecosystem compounds. The layers are:

- the portable Claude block `examples/claude-native/CLAUDE.md`;
- the Codex block `adoption/templates/codex.AGENTS.template.md`;
- both generated new-WSL carriers;
- root `AGENTS.md`;
- the scaffold's `AGENTS.md`.

A line beside the core stays only with evidence that its removal causes a mistake, or when the vendor documents it
for the client feature it configures:

| Kept line | Where | Evidence |
| --- | --- | --- |
| The StructuredOutput sentence | Claude user layer only | With it 0 of 30 workflow children made a schema error; without it 5 of 30. The sequential check with the sentence only in the user-level file also counted 0 of 30 ([model-fallback record](2026-09-25-model-fallback-guard.md), lines 108-110). |
| The PR description needs `## SOTA sources` | root `AGENTS.md` | The required `sota-sources` job of `.github/workflows/validate.yml` fails a PR without that section ([required checks](../github-automation.md), lines 29-31). |
| Run `scripts/validate.py` before committing | root `AGENTS.md` | The required `validate` job runs it, and a stale digest in `manifests/evidence.json` fails it. This change reproduced that before its registry refresh. |
| The subtree rule and the trading prerequisite | root `AGENTS.md` | Codex collects `AGENTS.md` only from the project root down to the working directory and never walks past the root (openai/codex `rust-v0.161.0` `codex-rs/core/src/agents_md.rs` lines 7-18). The trading prerequisite is the amendment of the [instruction-core record](2026-10-07-instruction-core.md): paper and broker work runs outside the repository's paths. |
| `@AGENTS.md` and `## Compact Instructions` | root `CLAUDE.md` | The memory page keeps the import for sessions that cannot read `AGENTS.md` directly. The costs page (lines 230-237) and the best-practices page (line 392) document compaction instructions in the project `CLAUDE.md`. |

Text that left an always-loaded layer stays reachable on demand:

- The seven measured RTK exceptions are in [`docs/token-practice.md`](../token-practice.md), word for word, between
  their own markers. The Codex role carriers keep them, and `tools/adoption/codex_roles.py` binds the carriers to that
  section.
- The standing-delegation protocol is retired, which [`docs/command-center.md`](../command-center.md) records in one
  dated line.
- The routing paragraph lives in its own fragment, `adoption/templates/decision-routing.md`, which `decision-md`
  reads.

The Codex block's RTK section is rtk-ai/rtk `v0.51.0`'s default awareness paragraph (`hooks/rtk-awareness.md` at
`e001f773`), verbatim. With the `rtk hook codex` PreToolUse hook rewriting commands, the full text is not needed
(`AWARENESS_CONFIG.md` lines 12-13 and 34-38). It is the same text that rtk's own `rtk init --codex` writes to
`RTK.md`, so `scripts/adoption_status.py` still finds it inline (Codex audit F5). The installer read-back and the lane
prover now look for that paragraph instead of the full text's prefix rule.

The same change sets two Codex configuration values:

- `model_context_window = 800000` in the OmniRoute profile. For this provider Codex 0.161.0 falls back to its bundled
  272K entry, while a 631,410-token request through the gateway answered correctly on 2026-10-08.
- `tool_suggest = false` in the new-WSL `[features]` additions.

The new-WSL `service_tier` was already `"default"`.

## Measured sizes

The startup scopes were measured with `tests.test_install_claude_profile.PortableTopRuleTests.startup_files`. Each
ceiling is the measured scope plus 5%, rounded up, as the
[budget decision](2026-10-05-harness-context-budget.md#fixed-byte-budget-and-review-procedure) requires.

| Surface | Before (`ffd4b850`) | After |
| --- | ---: | ---: |
| Claude startup scope (ceiling) | 19,885 B (20,880) | 3,942 B (4,140) |
| Codex startup scope (ceiling) | 15,983 B (16,783) | 4,043 B (4,246) |
| Codex template (rendered) | 7,418 B (8,484) | 2,105 B (2,105) |
| Portable Claude block | 11,145 B | 1,418 B |
| Root `AGENTS.md` / `CLAUDE.md` | 7,499 B / 975 B | 1,938 B / 320 B |

The first draft of this change measured 3,786 B and 4,617 B, with a 1,613-byte template. That was before two
amendments: the StructuredOutput line came back, and the full RTK text gave way to its default paragraph.

Pin changes in `tests/test_codex_worker_lane.py`:

- `TOP_RULE_SHA256` goes from `0f6b14d8b59cc7b6e39236d2e42241d5769d4bdffe9d75f7608b8bf0542b1f71` to
  `2618406a99bf3414e291651c17446e159c9da5885bb8a72091dc77b35c91fb62`.
- `PRE_RTK_SHA256` is retired.
- `RTK_DEFAULT_AWARENESS_SHA256` (`dc37dc6afdf513200c2aae1931496e433d323f313877a49b0d5ba11992c33ac7`) pins the RTK
  section.
- The full awareness pin stays, for the role carriers.

The core appears twice in a session in this repository, once from the user-level file and once from root `AGENTS.md`,
about 1.3 KB per client.

## Changed test expectations

| Test | Change |
| --- | --- |
| `StandingRuleSurfacesTests` | Now requires the core in all six layers, the StructuredOutput line only in the Claude user layer, and the retired rule families in none. The three-surface, local-time and root-core checks of the earlier rule text are replaced. |
| `PortableTopRuleTests` | The procedure phrases come from the core. Removed: the A/B-sentence test and the standing-clauses test. Ceilings: 4,140 and 4,246. Contract 08 leaves `tests/fixtures/harness-context-moves/contracts.json`. |
| `test_the_role_table_names_shipped_agents`, `test_qmd_serves_the_named_catalog_index`, `test_the_section_keeps_its_anchor` | The assertions on removed root `AGENTS.md` pointers are dropped. The first and third are renamed. |
| `test_codex_worker_lane.TemplateTests` | One top-rule pin plus the default-paragraph pin. The exceptions and lane checks move to their on-demand homes. The omniroute key set gains `model_context_window`. |
| `test_codex_roles`, `test_codex_agents` | The exceptions are cited and read from `docs/token-practice.md`, and the awareness from the pinned full file. |
| `test_new_wsl_client_config` | The scratch catalog carries the ai-memory line for the dependent-sentence tests, the kept-line bound is 6, and the record holds the new counts. |
| `test_landscape_sweep_harness`, `test_managed_block`, `test_scaffold_repo` | Adjusted to the default paragraph, the fragment source and the core's opening. |
| `examples/claude-native/workflows/test-envelope.mjs` (lines 459 and 480) and `test-contract-mutations.mjs` | The `instructions` binding in `contract.config.json` moves from the portable Claude block to the workflows README, whose mechanics section carries the stage effort literal and the `unrestricted` size guideline. The effort mutation now replaces every occurrence, because the README states the rule in several sections. A new mutation removes the size guideline. `SHA256SUMS` was regenerated for the two changed files. |

## Overturn conditions

- A removal is reversed under the same rule that kept the StructuredOutput line. That takes a same-version comparison
  on one task class, with and without the removed line, showing a higher mistake rate without it. The line then
  returns to the layer it left.
- A kept line leaves when its evidence goes. Examples: the `sota-sources` or `validate` check stops being required,
  Codex starts walking past the project root, or a same-version A/B shows no reduction for the StructuredOutput line.
- The full RTK awareness returns to the Codex block on a host where the `rtk hook codex` PreToolUse hook is not
  trusted.

## SOTA sources

- [Claude Code memory](https://code.claude.com/docs/en/memory),
  [best practices](https://code.claude.com/docs/en/best-practices) (lines 174 and 392) and
  [costs](https://code.claude.com/docs/en/costs) (lines 230-237), read 2026-10-08.
- openai/codex `rust-v0.161.0`:
  - `codex-rs/core/src/agents_md.rs` lines 7-18;
  - `codex-rs/models-manager/src/manager.rs` lines 429-440 and 883-911;
  - `codex-rs/models-manager/models.json` lines 4, 34, 178 and 207;
  - `codex-rs/protocol/src/config_types.rs` lines 528-549;
  - `codex-rs/core/src/tools/spec_plan.rs` lines 657-662;
  - `codex-rs/core/config.schema.json`.
- rtk-ai/rtk `v0.51.0` (`e001f773f80b22b7dc4c7a79521b30e35aaef026`): `AWARENESS_CONFIG.md` lines 12-13, 22-23 and
  34-38, and `hooks/rtk-awareness.md`.
- The owner's references, read at their default branches on 2026-10-08:
  [claude-code-ultimate-guide](https://github.com/FlorianBruniaux/claude-code-ultimate-guide),
  [claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) and
  [ECC](https://github.com/affaan-m/ECC).

## Limits

- These are local integration checks of file bytes and bindings. No session, provider call or prompt audit was run.
- The hand-applied host files carry no managed markers, so `tools/adoption/managed_block.py` refuses to merge into
  them and writes nothing until a host window migrates them.
- The landscape sweep's gateway lane home does not set `model_context_window`.
