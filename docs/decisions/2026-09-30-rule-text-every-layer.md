# Decision: the standing rule text in every instruction layer (2026-09-30)

**Decided by:** the user's explicit request of 2026-09-30, relayed in the coordinator's unit brief (unit F1): every future session and repository picks up the defaults. This supersedes the last sentence of the scope in [`2026-09-28-top-rule-templates.md:26`](2026-09-28-top-rule-templates.md) ("The operator's user-level file is the operator's own and is not changed"): the portable template now becomes the single managed source of that file. Branch `claude/sota-defaults-f1-20260930`, based on `origin/main@e45328d3`.

## Context

An audit on 2026-09-30 found the top rule present in text but with gaps in all three rule surfaces: the repository's `AGENTS.md`, the portable user-level template [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md) and the Codex user-level block [`adoption/templates/codex.AGENTS.template.md`](../../adoption/templates/codex.AGENTS.template.md). Six standing clauses were missing:

- **(a) GPT-6 through the gateway.** Cross-family research, review and sweep votes run the GPT-6 family through the OmniRoute gateway: `gpt-6-astra` at max for judgment and `gpt-6-sol` at medium for mechanical extraction ([dispatch record, line 33](2026-09-29-sonnet-5-5-dispatch.md); the measured outcome in [`gpt6-family-tiering-20260926/README.md:411-415`](../../blueprints/convergence-practice/gpt6-family-tiering-20260926/README.md)). `gpt-6.1-sol` waits for qualification in the [model-currency record](2026-09-27-model-currency.md). Codex CLI is the second native client.
- **(b) Completeness critic.** Every substantive research or adoption unit ends with a completeness critic (missed modality, source or candidate class), whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task. The sweep method already has one critic per sweep ([`catalogs/sota-convergence/README.md:126`](../../catalogs/sota-convergence/README.md)); the clause makes it standing for every unit.
- **(c) Model-callable skill discovery.** Invoke `search-first` before custom code or a tool choice, discover skills with `find-skills` (registry: `npx skills find`), verify or A/B a skill with `skill-creator`; every manifest skill stays listed for model invocation in both clients.
- **(d) R&D direction.** The harness exists to build complex systems, projects and the north-star R&D; each unit names the north-star action it serves.
- **(e) Upstream harnesses.** A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, `skill-creator`'s paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner.
- **(f) Startup.** No audits, trials or network at startup. The one read-only due-file line that the daily currency timer produces is allowed; its record, `docs/decisions/2026-09-30-session-currency-notice.md`, lands with unit A2 in the same batch.

**Divergence observed.** At `e45328d3` the operator's user-level file and the portable template had drifted apart. The user-level file held nine rules the template lacked:
- research published references and record what you found;
- build only from a cited reference implementation;
- use supported installation commands and tests from the selected source revision;
- stars, installs and popularity guide discovery;
- more tools, more reasoning and reviewer agreement alone do not prove quality;
- retain source pins and reasons;
- research only the relevant layers;
- use a short plan for bounded work;
- delegate so the reads, searches and dead ends stay in the child.

The template, in turn, held the five-step verification procedure that the user-level file lacked. The failing-first run of the new phrase check (below) reproduces this: 29 of its 35 phrases were missing from the unedited template, 9 of them rules that only the user-level file held.

## Alternatives

- **A UserPromptSubmit carrier.** A hook would inject the rules on every prompt. Rejected for its per-turn cost: a hook's `additionalContext` is inserted into the conversation beside each prompt it fires on ([hooks reference, "Add context for Claude"](https://code.claude.com/docs/en/hooks)), while the user-level file loads once at launch as part of the cached prefix ([memory docs](https://code.claude.com/docs/en/memory)). The 2026-09-29 local token-landscape A/B reported the user-level prefix as 17.6K of a 37.4K first prompt. That A/B is a private artifact with no receipt here, so the figure is context, not evidence.
- **Leaving the user-level file unmanaged**, as the 2026-09-28 record did. Rejected: the divergence above is what that produced.
- **Duplicating the text in each agent body.** Agents that omit the user-level file need their own copy. Unit F2 handles those bodies; this unit covers the three rule surfaces only.
- **Pointers instead of text.** `AGENTS.md` would point to the user-level files for (a), (b), (c) and (e). Measured below as the fallback. Not chosen, because it leaves hosts and checkouts without the managed user-level files with no text for those clauses.

## Decision

Each surface states the six clauses in its own place:

| Clause | `AGENTS.md` | `examples/claude-native/CLAUDE.md` | `codex.AGENTS.template.md` (top-rule block) |
| --- | --- | --- | --- |
| (a) | the startup bullet of the token practice (line 28) | a Workers bullet after "Quality comes first" | the "Models:" line, with `codex -p omniroute` as the GPT-6 lane and Claude-side Opus 5.5 at max through the cooperation lanes |
| (b) | the convergence bullet (line 18) | a Core rule bullet | its own line |
| (c) | the top rule (line 3), replacing "with the installed research and skill-discovery skills" | top-rule step 1 | its own line, with implicit invocation from a skill's description and explicit `$skill-name` |
| (d) | the opening paragraph (line 7) | the first Core rule bullet | its own line |
| (e) | the top rule (line 3) | a Core rule bullet | its own line |
| (f) | the startup bullet (line 28), replacing "Do not rerun the full audit or model trials at startup" | the caching bullet of the token practice | its own line |

**The portable template becomes the single managed source of the user-level file.** It is now a superset of that file's rules. Step 1 of its top rule takes the user-level paragraph and the source-revision rule, and its Core rule and token-practice bullets take the other six rules listed above. Every worker, model, Ultracode and agent-team line of the user-level file survives verbatim, with two exceptions:
- "Quality comes first" stays one line in the template, where the user-level file split it into sub-bullets; the word sequence is identical.
- The workflow-sizing line keeps every word of the user-level version and adds "to its task". `@RTK.md` stays the host's own import outside the template ([`recipes/claude-native-profile.md:134-136`](../../recipes/claude-native-profile.md)). Unit A3's installer replaces the file between managed markers.

**The Codex block also takes:**
- skill invocation, as Codex defines it: a named `$SkillName` or a task that matches a skill's description (openai/codex `rust-v0.159.2` `codex-rs/ext/skills/src/catalog_prompt.rs:8`);
- the worker and model rules;
- the rule for dated decision records;
- a token-lanes line that names each of the seven MCP servers that [`codex.config.template.toml`](../../adoption/templates/codex.config.template.toml) registers (lines 37-124), with the one-lane-per-artifact rule.

The RTK upstream text and the exceptions block stay byte-identical, so the F4 block in every Codex role is unchanged.

### Measured size

o200k counts come from the repository's own `tools/token-report/token_manifest.py` `count_files`, with gpt-tokenizer 4.0.0. Words are `wc -w`.

| File | o200k tokens | Bytes | Words |
| --- | --- | --- | --- |
| `AGENTS.md` | 2,392 → 2,627 (+235) | 11,450 → 12,465 | 1,483 → 1,618 |
| `examples/claude-native/CLAUDE.md` | 2,051 → 2,394 (+343) | 9,834 → 11,419 | 1,420 → 1,656 |
| `adoption/templates/codex.AGENTS.template.md` | 829 → 1,297 (+468) | 3,371 → 5,461 (test ceiling 8,192) | 535 → 837 |
| The operator's user-level file today, for comparison | 1,988 | 9,634 | 1,378 |

**Over the unit's growth budget.** The brief set a budget of at most 200 tokens of always-loaded growth, summed over `AGENTS.md` and the portable template. The measured sum is +578.
- **The floor.** The template alone grows by 343, because the brief also requires it to carry the user-level rules (about 80 tokens) and all six clauses. The floor stays above 200 even with `AGENTS.md` unchanged.
- **The measured fallback.** `AGENTS.md` keeps (d) and (f) inline and points to the user-level files for the rest: +106 for `AGENTS.md`, a sum of +449.
- **What this host loads.** In this repository a Claude session loads the user-level file and `AGENTS.md`. Once the template replaces the current user-level file, that start-up text grows by about 641 o200k tokens: 406 for the user-level file (2,394 against 1,988, before the managed markers) and 235 for `AGENTS.md`.

The coordinator decides between the budget and the clause set.

## Overturn condition

- **A behavior comparison.** A preregistered comparison on an upstream harness shows that sessions loading these texts follow the rules no better than with the previous texts, or cost more without a quality gain. Promptfoo would serve for the gateway lanes, and Harbor or Inspect for agent tasks.
- **A client change.** A client release changes how `CLAUDE.md` or `AGENTS.md` is loaded or sized, such as Codex's `project_doc_max_bytes` (32 KiB by default).
- **A rewording.** The operator rewords the rule, or the coordinator's budget decision removes clauses from a surface.

## Checks

These are structural checks on text, pins and registration, not a behavior test.
- **The Codex block's lanes and clauses.** `TemplateTests.test_top_rule_carries_the_standing_clauses_and_a_lane_for_every_configured_server` failed on the unedited block, listing all seven servers as missing (exit 1). It passes now.
- **The Codex pin.** The top-rule pin was re-derived with the test module's own `template_segments()`: 455 words, `7b41478f…`.
- **The portable template's phrases.** `PortableTopRuleTests.test_the_template_carries_the_standing_clauses_and_the_user_level_rules` failed on the unedited template, with 29 phrases missing, 9 of them held only by the user-level file (exit 1). It passes now.
- **The word budget.** The template's baseline moves to 1,656 words, following the re-baselines of 2026-09-27 and 2026-09-29.

## Limitations and integration

- **Settings contradict clause (c).** The frozen settings template keeps `find-skills`, `grill-me` and `improve-codebase-architecture` at `user-invocable-only` ([`claude.settings.template.json:330,331,345`](../../adoption/templates/claude.settings.template.json)). Clause (c) holds only after the settings owner changes those overrides.
- **`gpt-6.1-sol` has no entry yet.** No file at `e45328d3` mentions it. The model-currency record still needs its qualification entry.
- **Codex approvals.** Under `approval_policy = "never"`, Codex refuses the ai-memory, SocratiCode and Headroom tools unless the stack-worker profile approves them ([`codex.config.template.toml:46-51`](../../adoption/templates/codex.config.template.toml)). The token-lanes line names them anyway.
- **Stale line citation.** [`tools/adoption/codex_roles.py:357`](../../tools/adoption/codex_roles.py) cites `codex.AGENTS.template.md:41-46` for the exceptions, which now sit at lines 49-54.
- **Host step.** A host picks up the texts only when unit A3's installer and `tools/adoption/apply_codex_lane.py` run there after the batch merges. The Gate A freeze snapshot hashes both user-level files (`tools/token-e2e/freeze_snapshot.py:1080,1129`), so the operator does not apply them during the Gate A window without its owner.

## Sources

- [Claude Code memory](https://code.claude.com/docs/en/memory) (read 2026-09-30):
  - `~/.claude/CLAUDE.md` holds user instructions for all projects;
  - `@path` imports expand and load at launch;
  - `CLAUDE.md` files above the working directory load at launch.
- [Claude Code hooks](https://code.claude.com/docs/en/hooks) (read 2026-09-30): `additionalContext` is inserted where the hook fired; for UserPromptSubmit that is beside the prompt.
- [Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md) (read 2026-09-30):
  - the global scope reads `AGENTS.override.md`, else `AGENTS.md`, in the Codex home;
  - `project_doc_max_bytes` defaults to 32 KiB.
- openai/codex `rust-v0.159.2`, `codex-rs/ext/skills/src/catalog_prompt.rs:8`: the skill trigger rules.
- Skills:
  - `vercel-labs/skills@7407f389` `skills/find-skills/SKILL.md:27,56` (`npx skills find`);
  - `affaan-m/ECC@2b6e8397` `skills/search-first` (manifest lines 141-161);
  - `anthropics/claude-plugins-official` `plugins/skill-creator/skills/skill-creator/SKILL.md` at `2a40fd2e`, lines 169-185 (with-skill and baseline runs in the same turn);
  - the manifest's exclusion of other `skill-creator` copies ([`adoption/skills/manifest.json:795-797`](../../adoption/skills/manifest.json)).
- Harnesses:
  - Promptfoo 0.123.1 ([`blueprints/native-skill-practice/README.md:92`](../../blueprints/native-skill-practice/README.md));
  - `UKGovernmentBEIS/inspect_ai` and `harbor-framework/harbor` v0.23.0 ([`catalogs/convergence-practice/source-review.md:10-11`](../../catalogs/convergence-practice/source-review.md)).
- Gateway profile: [`adoption/templates/codex.omniroute.config.toml:1`](../../adoption/templates/codex.omniroute.config.toml).
- Spend records: [`2026-09-29-token-spend-attribution.md`](2026-09-29-token-spend-attribution.md), lines 23 and 50 (the run shape, and the memory docs' size guidance for `CLAUDE.md`).
