# Codex operational token-routing proposal (2026-10-06)

Proposal only, owned by overlap-token under TOKEN-STACK-VERIFY/A2. The unified diff in [2026-10-06-codex-token-routing.patch](2026-10-06-codex-token-routing.patch) targets `adoption/templates/codex.AGENTS.template.md` at observed origin/main `ecfa112764c664d35377dd66b8cfcb67e5a94d60`. Neither that shared template nor `adoption/new-wsl/codex-user-instructions.md` is edited by this PR. The command center's template owner sequences this proposal after #709/#758 and regenerates the F9 copy through the existing renderer.

The patch uses Git's zero-context unified format; validate against that base with `git apply --unidiff-zero --cached --check` using an isolated index. It is a review artifact, not an automatically applied patch. The owner must reconcile later template changes before application.

North-star action: give complex engineering and research work one adequate information-contract owner through authorized Codex channels, without per-task tool hints or forced invocations. This operational routing proposal is separate from the original U1 experiment that excludes harness instructions. It does not settle tool quality, native readiness or exclusions.

The counts-only before census is `coordination/ns2604-coop/token-stack-census-20261006.md`, window `[2026-10-05T06:05:00Z, 2026-10-06T06:05:00Z)`: 12 registered lane roots and their descendants, 6,776 persisted MCP items, 6,591 completed and 185 failed. All 11 requested servers are currently configured in all 12 project contexts; historical startup availability remains unknown. These are observed execution counts, not savings or comparative quality. Exact private attribution stays outside the repository.

## Proposed bullets, sources and addressed counts

| Proposed branch | Count addressed | Primary source at its pin | Gate retained |
| --- | --- | --- | --- |
| Native known-path/short/full-original reads | Native shell 8,062; RTK-prefix 6,947 | [Codex 0.160 native source-read/search guidance](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/protocol/src/prompts/base_instructions/default.md#L260); [context-mode file-processing exceptions](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/src/server.ts#L2066) | Short/native and exact-content contracts stay native; prefixes do not prove hook rewriting. |
| Symbol definitions/references | Serena 14; jcodemunch 0 | [Serena reference backend](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/tools/symbol_tools.py#L158); [jcodemunch 1.108.319 native router/index surface](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py#L359) | Keep one selected ready surface; index/reference qualification belongs to the navigation owner. No second indexing default is invented. |
| Static call/dependency graph | codebase-memory 2 | [codebase-memory 0.11 native multi-hop graph contract](https://github.com/DeusData/codebase-memory-mcp/blob/v0.11.0/src/mcp/mcp.c#L508) | Correct repository and current static index; not runtime completeness. |
| Conceptual code search | SocratiCode 0; Semble 0 | [SocratiCode 1.15 exploration skill](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/skills/codebase-exploration/SKILL.md#L3); [Semble 0.6.1 MCP instructions](https://github.com/MinishLab/semble/blob/24497845460960db1839c8485319df189a889225/src/semble/mcp.py#L71) | Selection remains with the deciding quality comparison; literal identifiers/errors use native search. |
| Scoped Markdown/catalog retrieval | QMD 3 | [QMD 2.8.3 native skill/search-get workflow](https://github.com/tobi/qmd/blob/v2.8.3/skills/qmd/SKILL.md#L3) | Collection/index parity and original recovery. |
| Prior decisions across sessions | ai-memory 124 across 11 lane families | [ai-memory 2.5.2 semantic retrieval skill](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-core/src/routing_skills/ai-memory-retrieval/SKILL.md#L3); [native scope/routing instructions](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-mcp/src/server.rs#L164) | Explicit static-client scope and verification of the current source; successful retrieval can still be irrelevant. |
| Large-output processing | context-mode 6,632; one low-activity lane at 1 | [context-mode execution](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/src/server.ts#L1658), [file processing](https://github.com/mksglu/context-mode/blob/6f0cc6841c687e754059f36714a11233fda1a02b/src/server.ts#L2056) | Processing happens before raw bytes enter context. This is contract/fidelity clarification, not a CM underuse claim. |
| Selected existing-text compression with recovery | Headroom 0 in 12 configured families | [Headroom 0.37 compress/retrieve descriptions and inline schema](https://github.com/headroomlabs-ai/headroom/blob/v0.37.0/headroom/ccr/mcp_server.py#L617) | Compressor needs supplied content; preserve full-original baseline and exact-recovery cost. No compression invocation is forced. |

Browser/eval counts (chrome-devtools 0, promptfoo 1) are opportunity/exposure review flags. They do not justify invoking unrelated tools or putting their names in outcome prompts.

## Coordination with navigation readiness

This routing diff names **overlap-codenav's Codex startup-readiness proposal**, recorded in `codenav-parity-20261006.md` and that lane's Q4/A4. Its changes target `adoption/templates/codex.config.template.toml` and `adoption/new-wsl/templates/codex.config.additions.toml`; those source files remain with their live owners. The template owner must merge one consistent routing/readiness change, preserving startup, repository coverage and quality gates.

The private parity census currently has different Serena/Semble counts from this report. Q3 requests reconciliation of cutoff, registry/family scope, canonical thread identity, copied-history exclusions and call units. No peer total is added or averaged into this census.

## First-party skill-exposure proposal

Installed ai-memory is 2.5.2 (`7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83`). Its own semantic retrieval skill is shipped at `crates/ai-memory-core/src/routing_skills/ai-memory-retrieval/SKILL.md`; the current client skill listing lacks it, while context-mode's skill is already present. The independent [native installer](https://github.com/akitaonrails/ai-memory/blob/7580b74d0fb9d14a6d949dc92f5ea8bb7feb3c83/crates/ai-memory-cli/src/commands/install_skills.rs#L46) supports `install-skills`, including a nonmutating preview.

F9 should review `ai-memory install-skills --agent agents --scope global --print`, which targets Codex's cross-agent skill directory through the upstream installer. The installer manages the core skill set, including retrieval; it offers no single-skill selector. Review that full package and its listing cost before applying the supported install, then verify client exposure/reload. Preserve scope/trust guidance and same-name managed-file ownership. No replacement skill, duplicate context-mode, instructions-file installer or new memory system is proposed. No host installation or configuration is performed by this PR; package ownership and the memory comparison remain external gates.

## Hook measurement proposal

The census reports RTK/ai-memory firings and confirmed rewrites as **unknown**. [Codex 0.160 rollout policy](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/rollout/src/policy.rs#L193) excludes hook-start/completion events. Native [app-server hook notifications](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/app-server-protocol/src/protocol/v2/hook.rs#L145) offer prospective thread attribution if already captured. RTK's [optional audit](https://github.com/rtk-ai/rtk/blob/v0.51.0/src/hooks/hook_cmd.rs#L588) has no lane/client identity and does not count all firings. Prefix observations and ai-memory captured-session coverage are different units.

F9/co-op owns any prospective native capture/audit/trust decision. No new hook writer, telemetry runner, replay-as-history counter or direct `~/.codex` edit is proposed here.

## Acceptance and overturn

After F9 applies reviewed sources and reloads clients, record actual revisions and a fresh matched observation window in the census after table. Preserve exact root/descendant rules, inherited-history exclusion, call IDs/states and startup evidence. Judge relevance, source fidelity and task contribution as well as count; a task with no suitable opportunity is not a forced-use target.

Retain the previous carrier if this longer trigger wording does not improve qualified task contribution or increases false use/context cost. A pinned promptfoo/Inspect comparison or upstream-native skill evaluation can overturn this wording. The original U1 native-arm owner/exclusion gates remain separate. No exclusion, READY, net-provider savings or automatic installation claim is made.
