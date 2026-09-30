# Decision: the standing rule text in every instruction layer (2026-09-30)

**Decided by:** the user's explicit request of 2026-09-30, relayed in the coordinator's unit brief (unit F1): every future session and repository picks up the defaults. This supersedes the last sentence of the scope in [`2026-09-28-top-rule-templates.md:26`](2026-09-28-top-rule-templates.md) ("The operator's user-level file is the operator's own and is not changed"): the portable template now becomes the single managed source of that file. Branch `claude/sota-defaults-f1-20260930`, rebuilt on `origin/main@11227bfd`. It was first built on `e45328d3`; the three rule surfaces are byte-identical at both commits.

## Context

An audit on 2026-09-30 found the top rule present in text but with gaps in all three rule surfaces: the repository's `AGENTS.md`, the portable user-level template [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md) and the Codex user-level block [`adoption/templates/codex.AGENTS.template.md`](../../adoption/templates/codex.AGENTS.template.md). Six standing clauses were missing:

- **(a) Codex and the gateway.** Codex CLI is the second native client. Its routing follows the [Sol-primary record](2026-09-30-sol-primary-quality-defaults.md), which lands with unit D4 in the same batch:
  - `gpt-6.1-sol` at ultra coordinates, and `gpt-6.1-sol` at max runs primary workers;
  - `gpt-6-astra` at max takes consequential architecture, conflicting primary evidence or a failure unresolved after one bounded Sol repair;
  - explicit model choices and role definitions win, so judgment lanes keep their recorded Astra bindings.

  Cross-family research, review and sweep votes run through the OmniRoute gateway. The brief first worded this clause as `gpt-6-astra` max for judgment, `gpt-6-sol` medium for extraction and `gpt-6.1-sol` pending qualification. Its 04:35Z relay then worded it as "GPT-6 Astra at ultra for complex workflow tasks". The Sol-primary record is the later and more specific user selection, so this unit words (a) by it.
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
| (a) | the folded Codex defaults bullet under Workers, which also names the gateway | a Workers bullet after "Quality comes first" | the "Models:" line, with `codex -p omniroute` as the GPT-6 lane and Claude-side Opus 5.5 at max through the cooperation lanes |
| (b) | the convergence bullet | a Core rule bullet | its own line |
| (c) | the top rule, replacing "with the installed research and skill-discovery skills"; the folded skill-matching bullet sits in the token practice | top-rule step 1; the token-practice bullet "Keep context small" also takes skill matching | the skills line, with implicit invocation from a skill's description and explicit `$skill-name` |
| (d) | the opening paragraph | the first Core rule bullet | its own line |
| (e) | the top rule | a Core rule bullet | its own line |
| (f) | the startup bullet of the token practice, replacing "Do not rerun the full audit or model trials at startup" | the caching bullet of the token practice | its own line |

**The portable template becomes the single managed source of the user-level file.** It is now a superset of that file's rules. Step 1 of its top rule takes the user-level paragraph and the source-revision rule, and its Core rule and token-practice bullets take the other six rules listed above. Every worker, model, Ultracode and agent-team line of the user-level file survives verbatim, with two exceptions:
- "Quality comes first" stays one line in the template, where the user-level file split it into sub-bullets; the word sequence is identical.
- The workflow-sizing line keeps every word of the user-level version and adds "to its task". `@RTK.md` stays the host's own import outside the template ([`recipes/claude-native-profile.md:134-136`](../../recipes/claude-native-profile.md)). Unit A3's installer replaces the file between managed markers.

The user-level file's GPT-6 routing wording is replaced, not kept, because the Sol-primary record supersedes it.

**The Codex block also takes:**
- skill invocation, as Codex defines it: a named `$SkillName` or a task that matches a skill's description (openai/codex `rust-v0.159.2` `codex-rs/ext/skills/src/catalog_prompt.rs:8`);
- the worker and model rules;
- the rule for dated decision records;
- a token-lanes line that names each of the seven MCP servers that [`codex.config.template.toml`](../../adoption/templates/codex.config.template.toml) registers (lines 37-124), with the one-lane-per-artifact rule.

The RTK upstream text and the exceptions block stay byte-identical, so the F4 block in every Codex role is unchanged.

### Folded from the main checkout

Provenance for every item in this list: pre-existing uncommitted changes observed in the main checkout; original author not established. The coordinator delegated the fold to this unit and took read-only snapshots of that state on 2026-09-30: r1 (tracked diff sha256 `5de56d6d81453ed3`) and r2 (`314bd1b260da0939`, relative to checkout commit `5cfa2400`). Only the true delta against origin/main was taken, by a three-way merge with `5cfa2400` as the base, so main's later edits stay.

- **`AGENTS.md`.** Two bullets:
  - the skill-lifecycle bullet, whose target `adoption/skills/lifecycle.md` lands with unit F3;
  - the Codex defaults bullet, merged with clause (a) so the model routing is stated once.

  Neither bullet was on origin/main at `11227bfd` or on any other unit branch.
- **The Codex block.** The routing line and the skill-matching line, merged into the Models and skills lines. The observed change's test comment said the skill routing was "reviewed against OpenAI's 2026-09-11 Astra guidance and native model routing at rust-v0.159.2". That note came without a URL; it is relayed here unverified, and the test comment states only what this unit derived.
- **The portable template.** The skill-matching wording, merged into "Keep context small", since the observed change had dropped that user-level rule.
- **`docs/convergence-architecture.md`.** The Ultracode paragraph, checked against line 206 of the tagged `anthropics/claude-code` v2.1.285 `CHANGELOG.md`.
- **`docs/token-session-handbook.md`.** The worker command's `-m gpt-6.1-sol`.
- **`docs/harness-defaults.md`.** Ten anti-pattern rows, byte for byte:
  - "Finalizing from a stale checkout and colliding with an owner receipt";
  - "Queuing a rollout with an incomplete source checksum closure";
  - "Coupling Ultracode to xhigh and treating the preregistration PR as an open Gate A issue";
  - "Updating selected skill pins without checking their declarative consumers";
  - "Assuming an unfamiliar effort string is an invalid native configuration";
  - "Treating a dated active-PR reference as current ownership evidence";
  - "Repinning skill metadata while retaining the old install URL";
  - "Treating a broad output assertion as proof of a generated apply command";
  - "Assuming a systemd verifier's zero exit means every directive was recognized";
  - "Recommending a generic updater for a CLI behind a versioned launcher".
- **The finalization record.** [`2026-09-30-sota-native-finalization.md`](2026-09-30-sota-native-finalization.md), unchanged below an attribution paragraph.

Not folded:
- `recipes/README.md`: unit D4's branch at `a3a276ac` already carries the identical hunk.
- The "Sol-primary quality defaults" paragraph of `docs/harness-defaults.md`, which is unit D4's.
- The removal lines in a plain diff of the snapshot against main. They are main's newer #532 rows and handbook text, which the snapshot predates.
- The finalization record's evidence directory, which is not assigned to this unit.

### Rows reported by the Codex runtime lane

Six further rows are attributed to the Codex runtime lane in their last cell. The lane sent two relays: `codex-runtime-anti-pattern-owner-handoff-20260930` for the relock, usage, macOS fixture and rollup rows, and `codex-f1-source-correction-handoff-20260930` for the image tag and scan threshold rows. Verified before writing:
- each cited file exists at the cited commit;
- the relock, usage and scan figures appear in those files;
- `build.py` lines 581 and 925 at OpenHands `software-agent-sdk@dcf401af` hold the tag derivation and the `--load` branch;
- the GitHub Actions job conclusions were re-read through the REST jobs API.

The earlier PR #535 head `6a7b1646` is no longer held by any remote ref. The rows therefore link the same bytes at PR #535 head `00aa6c25`.

The same relay asked for three guards, stated here rather than as rows:
- Never describe #543 as published without a native `gh` lookup that exits 0. On 2026-09-30, `git ls-remote` returned no `refs/pull/543/head`.
- The actor behind the 07:34Z and 06:46Z timer and settings changes stays unknown.
- A historical OSV pass is not current after the advisories of 2026-09-30 (#546).

### Measured size

o200k counts come from the repository's own `tools/token-report/token_manifest.py` `count_files`, with gpt-tokenizer 4.0.0. Words are `wc -w`. The base is `origin/main@11227bfd`.

| File | o200k tokens | Bytes | Words |
| --- | --- | --- | --- |
| `AGENTS.md` | 2,392 → 2,715 (+323) | 11,450 → 12,910 | 1,483 → 1,674 |
| `examples/claude-native/CLAUDE.md` | 2,051 → 2,414 (+363) | 9,834 → 11,566 | 1,420 → 1,680 |
| `adoption/templates/codex.AGENTS.template.md` | 829 → 1,336 (+507) | 3,371 → 5,750 (test ceiling 8,192) | 535 → 878 |
| The operator's user-level file today, for comparison | 1,988 | 9,634 | 1,378 |

The folded text alone (origin/main plus the true delta, before this unit's clauses) measures:
- `AGENTS.md`: +134;
- the portable template: +5;
- the Codex template: +78.

**Over the unit's growth budget.** The brief set a budget of at most 200 tokens of always-loaded growth, summed over `AGENTS.md` and the portable template. The measured sum is +686: +139 from the folded text and +547 from this unit's clauses and the user-level rules.
- **The floor.** The template alone grows by 358 without the fold, because the brief also requires it to carry the user-level rules and all six clauses. The floor stays above 200 even with `AGENTS.md` unchanged.
- **The fallback.** In the first build, `AGENTS.md` kept (d) and (f) inline and pointed to the user-level files for the rest. That measured +106 before the fold.
- **What this host loads.** In this repository a Claude session loads the user-level file and `AGENTS.md`. Once the template replaces the current user-level file, those two files grow from 1,988 + 2,392 to 2,414 + 2,715 o200k tokens: +749, before the managed markers.

The coordinator decides between the budget and the clause set.

## Overturn condition

- **A behavior comparison.** A preregistered comparison on an upstream harness shows that sessions loading these texts follow the rules no better than with the previous texts, or cost more without a quality gain. Promptfoo would serve for the gateway lanes, and Harbor or Inspect for agent tasks.
- **A client change.** A client release changes how `CLAUDE.md` or `AGENTS.md` is loaded or sized, such as Codex's `project_doc_max_bytes` (32 KiB by default).
- **A rewording.** The operator rewords the rule, the Sol-primary record changes the Codex routing, or the coordinator's budget decision removes clauses from a surface.

## Checks

These are structural checks on text, pins and registration, not a behavior test.
- **The Codex block's lanes and clauses.** `TemplateTests.test_top_rule_carries_the_standing_clauses_and_a_lane_for_every_configured_server` failed first, exit 1 each time. On the first build's unedited block it listed all seven servers as missing. On this build's block it listed five phrases: `SKILL.md`, "native workflow" and three routing phrases. It passes now.
- **The Codex pin.** The top-rule pin was re-derived with the test module's own `template_segments()`: 496 words, `2d3107a2…`.
- **The portable template's phrases.** `PortableTopRuleTests.test_the_template_carries_the_standing_clauses_and_the_user_level_rules` failed first, exit 1 each time. On the unedited template it found 29 phrases missing, 9 of them held only by the user-level file. On this build's template it found four routing and skill-matching phrases missing. It passes now. It also requires "Keep context small"; run against the observed version of the template, it reports that phrase missing.
- **The word budget.** The template's baseline moves to 1,680 words, following the re-baselines of 2026-09-27 and 2026-09-29.

## Limitations and integration

- **Clause (c) and the settings.** origin/main keeps `find-skills`, `grill-me` and `improve-codebase-architecture` at `user-invocable-only` in the frozen [settings template](../../adoption/templates/claude.settings.template.json). Unit F3 turns `find-skills`, `search-first` and `skill-creator` on. `grill-me` and `improve-codebase-architecture` stay user-invocable-only, so "every manifest skill" holds only once those two change or are replaced.
- **References to other units.** `AGENTS.md` cites files that land elsewhere in the batch and resolve when it merges:
  - `adoption/skills/lifecycle.md` (F3);
  - `docs/decisions/2026-09-30-sol-primary-quality-defaults.md` (D4);
  - `docs/decisions/2026-09-30-session-currency-notice.md` (A2).
- **Unpublished evidence.** `evidence/artifacts/sota-finalization-20260930/` has no owner; the folded finalization record and four folded rows cite it. `evidence/artifacts/codex-01592-qualification-20260930/` is on no branch yet, and its name collides with unit D4's receipt id; two folded rows and the record cite it.
- **Older Codex pins.** The Codex block says "default to `gpt-6.1-sol`", while unit D4 renders `gpt-6-astra` for Codex pins before 0.159.1 (macOS). That wording follow-up is D4's.
- **The scaffold copy.** Unit A3's `adoption/scaffold/AGENTS.md` must carry the Codex template's top-rule block byte for byte (`tests/test_scaffold_repo.py` on A3's branch). Whichever of A3 and this unit lands second copies the block across.
- **Stale line citation.** [`tools/adoption/codex_roles.py:357`](../../tools/adoption/codex_roles.py) cites `codex.AGENTS.template.md:41-46` for the exceptions, which now sit at lines 49-54.
- **Codex approvals.** Under `approval_policy = "never"`, Codex refuses the ai-memory, SocratiCode and Headroom tools unless the stack-worker profile approves them ([`codex.config.template.toml:46-51`](../../adoption/templates/codex.config.template.toml)). The token-lanes line names them anyway.
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
- Model routing: the Sol-primary record (unit D4) and the [model-currency record](2026-09-27-model-currency.md), whose 2026-09-30 addendum lands with D4.
- [anthropics/claude-code v2.1.285 `CHANGELOG.md` line 206](https://github.com/anthropics/claude-code/blob/v2.1.285/CHANGELOG.md#L206) (read 2026-09-30): Ultracode "no longer forces xhigh effort and stays on at any effort level", under 2.1.284.
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
- The Codex runtime lane's sources, at full SHAs:
  - PR #535 head `00aa6c25fe6f27e9f5974e9f6a5592aa31683479`: `docs/decisions/2026-09-30-runtime-convergence-followup.md`, `blueprints/convergence-practice/runtime-image-browser-20260930/README.md` and `experiment.json`, `blueprints/runtime-workers/openhands/evidence/main-reconcile-20260930.json` and `image-triage-20260930.json`, `tests/test_openhands_150.py`;
  - SDK branch head `404b821cd3af25800ea418dc6145cc5cb6fe33c5`: `evidence/artifacts/runtime-sdk-20260930/usage-scope-receipt.json`, `tests/test_sdk_usage_scope.py`;
  - [OpenHands `software-agent-sdk@dcf401af` `build.py`](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/build.py), lines 581 and 925;
  - GitHub Actions runs 36695388851 and 36690153586, read through the REST jobs API on 2026-09-30.
