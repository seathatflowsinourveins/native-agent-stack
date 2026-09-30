# Decision: the standing rule text in every instruction layer (2026-09-30)

**Decided by:** the user's explicit request of 2026-09-30, relayed in the coordinator's unit brief (unit F1): every future session and repository picks up the defaults. The Gate A owner's ACCEPT-WITH-CHANGES review of PR #557 (2026-09-30) set the final wording (decisions 1 and 2 below).

This supersedes the last sentence of the scope in [`2026-09-28-top-rule-templates.md:26`](2026-09-28-top-rule-templates.md) ("The operator's user-level file is the operator's own and is not changed"): the portable template now becomes the single managed source of that file.

Branch `claude/sota-defaults-f1-20260930` is stacked on F2's head `021c61f7` (#547, re-stacked on #545 `3805a598`), over #539 `86fe8c3d` and main `1f2cdce5`. The three rule surfaces are byte-identical at main and at every commit of the stack below this branch.

## Context

An audit on 2026-09-30 found the top rule present in text but with gaps in all three rule surfaces: the repository's `AGENTS.md`, the portable user-level template [`examples/claude-native/CLAUDE.md`](../../examples/claude-native/CLAUDE.md) and the Codex user-level block [`adoption/templates/codex.AGENTS.template.md`](../../adoption/templates/codex.AGENTS.template.md). Six standing clauses were missing. Each clause below names who acts: the imperatives are a coordinator's, so a delegated child (a Codex bounded worker) adds no calls for them.

- **(a) Codex and the gateway.** Codex CLI is the second native client. Its routing follows the [Sol-primary record](2026-09-30-sol-primary-quality-defaults.md) (unit D4, on main):
  - for unpinned work, `gpt-6.1-sol` at ultra coordinates and at max runs workers;
  - `gpt-6-astra` at ultra coordinates a complex workflow that needs Astra;
  - `gpt-6-astra` at max takes a single consequential judgment: conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair;
  - where a launch pins the model and effort (`-m`, `-c model_reasoning_effort`), children inherit that pin and a spawn call names neither;
  - explicit model choices and role definitions win, and a coordinator records the trigger and acceptance result.

  Cross-family research, review and sweep votes run through the OmniRoute gateway; a coordinator, never a delegated child, starts a cross-family lane.

  - **The split.** It follows the Codex catalog semantics the Sol-primary record documents: ultra selects proactive delegation with the model's `xhigh` reasoning, while max sends the highest reasoning effort ([Codex worker lane recipe](../../recipes/README.md#codex-worker-lane)). The user's words of 2026-09-30, as the coordinator relayed them, were "gpt6.1 sol as main workers and use astra ultra when tasks needed suitable for complex workflow".
  - **The pinned-launch rule.** It comes from the Gate A owner's review: the sealed E2E case `seed-binding-4` runs without a role or agent type and inherits its parent's pin ([E2E README:157](../../evidence/artifacts/token-adoption-e2e-20260926/README.md)), so the routing default must not override a pinned launch.
  - **Superseded wordings.** The brief first had `gpt-6-astra` max for judgment, `gpt-6-sol` medium for extraction and `gpt-6.1-sol` pending qualification. The first rebuild of this branch had Astra only at max.
- **(b) Completeness critic.** A coordinator ends every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class), whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.
  - **Upstream sources.** The critic is the evaluator half of the evaluator-optimizer workflow in Anthropic's [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): "one LLM call generates a response while another provides evaluation and feedback in a loop". Its criterion is the rubric criterion that Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) grades: "completeness (are all requested aspects covered?)". Both pages were read on 2026-09-30.
  - **In this repository.** The sweep method already has one critic per sweep ([`catalogs/sota-convergence/README.md:126`](../../catalogs/sota-convergence/README.md)); the clause makes it standing for every coordinator unit.
- **(c) Model-callable skill discovery.** The sentence on the Claude surfaces is "A coordinator, not a delegated child, invokes `search-first` before custom code or a tool choice; when no listed skill fits the task, it discovers one with `find-skills` and verifies or A/B-tests it with `skill-creator`". The Codex block's bounded-worker variant names "a bounded worker" instead of "a delegated child".
  - **How discovery runs.** The pinned registry search the checkout records is `DISABLE_TELEMETRY=1 <tools-root>/skills-1.7.0/bin/skills find "<query>"` ([`evidence/artifacts/skills-agents-layer-20260926/README.md:90`](../../evidence/artifacts/skills-agents-layer-20260926/README.md); [`adoption/skills/manifest.json:22`](../../adoption/skills/manifest.json): discovery uses the CLI's unauthenticated `skills find <query>`). The surfaces name no command, and no longer a bare `npx skills find`.
  - **Dropped until F3's settings land.** The clause "every manifest skill stays listed for model invocation in both clients" is false at this head. The settings template keeps `find-skills`, `grill-me` and `improve-codebase-architecture` at `user-invocable-only`, and the skills manifest gives `find-skills` `codex_enabled: false`.
- **(d) R&D direction.** The harness exists to build complex systems, projects and the north-star R&D; each coordinator unit names the north-star action it serves.
  - **No upstream source exists.** Checked on 2026-09-30: Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) requires each delegated task to carry "an objective, an output format, guidance on the tools and sources to use, and clear task boundaries". [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) prescribes no such field. Neither ties a unit to a project-level goal.
  - **Where it comes from instead.** The clause is this repository's direction, from the user's 2026-09-30 request, and serves the north star in `AGENTS.md`.
- **(e) Upstream harnesses.** A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, Claude's `skill-creator` paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner.
- **(f) Startup.** No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed. Its record, [`2026-09-30-session-currency-notice.md`](2026-09-30-session-currency-notice.md), is in the stack below this branch (#539, unit A2).

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
- **Pointers instead of text.** `AGENTS.md` would point to the user-level files for (a), (b), (c) and (e). Measured as the fallback (below). Not chosen, because it leaves hosts and checkouts without the managed user-level files with no text for those clauses.

## Decision

**One wording on the three surfaces.** Each standing clause is the same sentence on `AGENTS.md`, the portable template and the Codex block. The only variant is in the skill-discovery sentence, where the Codex block names a bounded worker and the Claude surfaces a delegated child. `StandingRuleSurfacesTests` in [`tests/test_install_claude_profile.py`](../../tests/test_install_claude_profile.py) checks every shared sentence on all three surfaces and keeps the dropped clause off them. Surface-specific additions follow the shared sentences:
- **`AGENTS.md`** names the Sol-primary record as the dispatch contract, gives the currency-notice path after the startup sentence, and points to `adoption/skills/lifecycle.md` with "(lands with unit F3)".
- **The Codex block** names `codex -p omniroute` as the GPT-6 lane and Claude-side judgment on Opus 5.5 at max through the cooperation lanes. It also has the coordinator's dated decision records (`docs/decisions/YYYY-MM-DD-<slug>.md`) and a token-lanes line for each MCP server its config template registers.

| Clause | `AGENTS.md` | `examples/claude-native/CLAUDE.md` | `codex.AGENTS.template.md` (top-rule block) |
| --- | --- | --- | --- |
| (a) | the Codex bullet under Workers | a Workers bullet after "Quality comes first" | its own line, line 13 |
| (b) | the convergence bullet | a Core rule bullet | its own line |
| (c) | the top rule, after "record what you found"; the folded skill-matching bullet sits in the token practice | top-rule step 1; the token-practice bullet "Keep context small" also takes skill matching | the skills line, after implicit invocation from a skill's description and explicit `$skill-name` |
| (d) | the opening paragraph | the first Core rule bullet | its own line |
| (e) | the top rule | a Core rule bullet | its own line |
| (f) | the startup bullet of the token practice, replacing "Do not rerun the full audit or model trials at startup" | the caching bullet of the token practice | its own line |

**The portable template becomes the single managed source of the user-level file.** It is now a superset of that file's rules. Step 1 of its top rule takes the user-level paragraph and the source-revision rule, and its Core rule and token-practice bullets take the other six rules listed above. Every worker, model, Ultracode and agent-team line of the user-level file survives verbatim, with two exceptions:
- "Quality comes first" stays one line in the template, where the user-level file split it into sub-bullets; the word sequence is identical.
- The workflow-sizing line keeps every word of the user-level version and adds "to its task". `@RTK.md` stays the host's own import outside the template ([`recipes/claude-native-profile.md:134-136`](../../recipes/claude-native-profile.md)). Unit A3's installer replaces the file between managed markers.

The user-level file's GPT-6 routing wording is replaced, not kept, because the Sol-primary record supersedes it. Skill invocation in the Codex block follows Codex's own rule: a named `$SkillName` or a task that matches a skill's description (openai/codex `rust-v0.159.2` `codex-rs/ext/skills/src/catalog_prompt.rs:8`). The RTK upstream text and the exceptions block stay byte-identical, so the F4 block in every Codex role is unchanged.

**The scaffold copy (post-A3 step, done).** Unit A3 (#545, in the stack below) added `adoption/scaffold/AGENTS.md`, which `tests/test_scaffold_repo.py` requires to carry the Codex block's top-rule text byte for byte. This branch copies the final block there.

### The window-W guard (decision 1 of the Gate A owner's review)

B1 applies neither user-level template. `~/.claude/CLAUDE.md` (the managed block) and `~/.codex/AGENTS.md` stay byte-identical until the last Gate A window closes, and F1's templates apply after window W.
- **Why.** Line 16 of the Codex block names seven lane tools (`serena`, `socraticode`, `codebase-memory`, `qmd`, `ai-memory`, `context-mode`, `headroom`), and every Codex arm reads the global `AGENTS.md`. The sealed design appends no LANES block ([E2E README:188](../../evidence/artifacts/token-adoption-e2e-20260926/README.md)), and arm N is "config-free, not guidance-free" ([README:275](../../evidence/artifacts/token-adoption-e2e-20260926/README.md)). The line would therefore give arms A and N the guidance that only B gets, through its carriers.
- **Seal.** Per the Gate A owner's review, Amendment 4 seals the pre-change hashes of both files; the amendment text is not in this repository.

This guard covers window W only. Once the last Gate A window closes, B1 applies both templates.

### Coordinator-scoped discovery (correction)

The previous commit on this branch made discovery conditional: `find-skills` ran only when no listed skill fit the task. Its record said that "a task with a fitting listed skill makes no extra call". That claim was wrong. The conditional gated only `find-skills`: `search-first` still ran before every custom code or tool choice, so a measured child could still add a Skill call.

The review scopes both skills to a coordinator. A delegated child invokes neither, and B roles have no Skill tool at all (only the researcher has one, after H3).

### Folded from the main checkout

Provenance for every item in this list: pre-existing uncommitted changes observed in the main checkout; original author not established. The unit brief and the fold brief had attributed these items to the Codex coordinator lane on the strength of a process census of file writes; a census does not establish document authorship, and the Codex runtime lane asked for the neutral wording, so the coordinator's 2026-09-30 amendment to the brief adopts it. The coordinator delegated the fold to this unit and took read-only snapshots of that state on 2026-09-30: r1 (tracked diff sha256 `5de56d6d81453ed3`) and r2 (`314bd1b260da0939`, relative to checkout commit `5cfa2400`). Only the true delta against origin/main was taken, by a three-way merge with `5cfa2400` as the base, so main's later edits stay.

- **`AGENTS.md`.** Two bullets:
  - the skill-lifecycle bullet, whose target `adoption/skills/lifecycle.md` lands with unit F3, as the bullet now says;
  - the Codex defaults bullet, now replaced by the shared routing sentences of clause (a).
- **The Codex block.** The routing line and the skill-matching line, merged into the routing and skills lines. The observed change's test comment said the skill routing was "reviewed against OpenAI's 2026-09-11 Astra guidance and native model routing at rust-v0.159.2". That note came without a URL; it is relayed here unverified, and the test comment states only what this unit derived.
- **The portable template.** The skill-matching wording, merged into "Keep context small", since the observed change had dropped that user-level rule.
- **`docs/convergence-architecture.md`.** The Ultracode paragraph, checked against line 206 of the tagged `anthropics/claude-code` v2.1.285 `CHANGELOG.md`.
- **`docs/token-session-handbook.md`.** The worker command's `-m gpt-6.1-sol`. At the review's point (g) it is marked as the command after D4, beside the sealed Gate A E2E route: `-m gpt-6-astra` at max ([`RUNBOOK.md:371`](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md)).
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
- **The finalization record's evidence.** 18 of the 19 files of [`evidence/artifacts/sota-finalization-20260930/`](../../evidence/artifacts/sota-finalization-20260930/receipt.json), byte-identical to snapshot r2. The coordinator amended this unit's allowed paths for them.

Not folded:
- `recipes/README.md`: unit D4 carries the identical hunk, now on main.
- The "Sol-primary quality defaults" paragraph of `docs/harness-defaults.md`, which is unit D4's.
- The removal lines in a plain diff of the snapshot against main. They are main's newer #532 rows and handbook text, which the snapshot predates.
- `evidence/artifacts/codex-01592-qualification-20260930/`, which unit D4's fold decides.
- `evidence/artifacts/sota-finalization-20260930/convergence.json`, held back:
  - **Why.** It is a `convergence_experiment` record. Its frozen inputs and observations pin eight files of other units by path and sha256:
    - five of `native-skill-finalization-20260930` (unit F3), all matching F3's branch bytes;
    - three of `codex-01592-qualification-20260930`, which are on no branch.

    `scripts/validate_convergence.py --all-recorded`, which CI runs (`adoption-bootstrap.yml`, `publish-catalog.yml`), rejects both ways of publishing it here. Hash-listed but undeclared, it fails record discovery; declared in `convergence_records`, it fails validation on the missing files. Folded with the other 18 files, it made discovery fail on this branch.
  - **When it can land.** Fold it and declare it once F3 lands and D4 publishes those three files unchanged at those paths. Its pins on six folded files here match, and so do the five F3 pins.

### Sanitization of the folded evidence

Nothing needed stripping, and no file was changed; the one file held back above was held for validation, not privacy:
- **validate.py.** `python3 scripts/validate.py --scan-file` over all 19 snapshot files returned `{"scanned_files": 19, "status": "passed"}`, and over the 18 folded files `{"scanned_files": 18, "status": "passed"}`. Its patterns cover UUID session identifiers, personal home paths, Windows user paths and token shapes.
- **A wider scan found none of these:** a personal home path, the host user name, a session UUID, a `/tmp/claude-*` path, an e-mail address, an IPv4 address or a token.
- **Three kinds of string were reviewed and kept:**
  - the one `/home/` string, the literal placeholder `/home/example` in `claude-review.json`'s prose ("found no /home paths (except the /home/example fixture)"), which validate.py's pattern exempts;
  - three generic install locations (`~/.agents/skills/...`, `~/.codex/config.toml`, `~/.claude/`);
  - 28 configuration-key strings in `convergence.json`, all inside recorded `codex exec` command lines whose outputs were already redacted to `<private-path>`. They are not quotes of a host configuration file, and the `claude_settings` and `codex_config` fields of `installed-skills.json` hold only `{"state": "ok"}`.
- **Correction.** This unit's first handoff counted 21 files and one home path. The directory holds 19 files, and the "home path" is the placeholder above. Replacing it with `<home>` would have changed a retained review without removing any host data. It would also have broken the sha256 pin that the lane's convergence record holds for `claude-review.json`. So the file stays byte-exact.

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

### Measured size and the token budget

o200k counts come from the repository's own `tools/token-report/token_manifest.py` `count_files`, with gpt-tokenizer 4.0.0, re-run at this branch's final content. Words are Python `str.split()` counts, as the tests count them. The base is main `1f2cdce5`; for these files it equals every commit of the stack below this branch.

| File | o200k tokens | Bytes | Words |
| --- | --- | --- | --- |
| `AGENTS.md` | 2,392 → 2,812 (+420) | 11,450 → 13,374 | 1,483 → 1,746 |
| `examples/claude-native/CLAUDE.md` | 2,051 → 2,506 (+455) | 9,834 → 12,044 | 1,420 → 1,750 |
| `adoption/templates/codex.AGENTS.template.md` | 829 → 1,397 (+568) | 3,371 → 6,054 (test ceiling 8,192) | 535 → 920 |
| `adoption/scaffold/AGENTS.md` (a new repository's always-loaded file) | 373 → 941 (+568) | 1,825 → 4,508 | 268 → 653 |
| The operator's user-level file today, for comparison | 1,988 | 9,634 | 1,378 |

How the budgeted sum grew, over `AGENTS.md` and the portable template:
- **+723** after the Ultra/Max split and one tightening pass. The folded text alone was +139 of it.
- **+739** after the conditional-discovery commit (+8 and +8 tokens).
- **+875** after the review's changes: +71 for `AGENTS.md` (2,741 → 2,812) and +65 for the portable template (2,441 → 2,506). They added the coordinator scoping, the pinned-launch rule and one harness wording, and removed the dropped clause.

The Codex block moved 1,354 → 1,397 in the same round.

**Over the unit's growth budget.** The brief set a budget of at most 200 tokens of always-loaded growth, summed over `AGENTS.md` and the portable template; the measured sum at this branch's final content is +875.
- **The acceptance.** The coordinator's dated amendment to the unit brief (2026-09-30) accepted the miss at +723, because the six clauses are the user's explicit directive. The +152 since then is text the Gate A owner's review requires.
- **The floor.** The portable template alone grows by 455, because it must carry the user-level rules and all six clauses. The floor stays above 200 even with `AGENTS.md` unchanged.
- **The fallback.** In the first build, `AGENTS.md` kept (d) and (f) inline and pointed to the user-level files for the rest. That measured +106 before the fold.
- **What this host loads.** In this repository a Claude session loads the user-level file and `AGENTS.md`. Once the template replaces the current user-level file (after window W; see the guard above), those two files grow from 1,988 + 2,392 to 2,506 + 2,812 o200k tokens: +938, before the managed markers.

## Overturn condition

- **The 2026-09-29 user-prefix A/B.** Rerun that A/B with these texts on an upstream harness, measuring first-prompt prefix size and task outcome with and without the added clauses. If it shows the added always-loaded text raising cost without a measured rule-following gain, the measured pointer fallback replaces the inline clauses on each surface without a gain. Promptfoo would serve for the gateway lanes, and Harbor or Inspect for agent tasks.
- **A client change.** A client release changes how `CLAUDE.md` or `AGENTS.md` is loaded or sized, such as Codex's `project_doc_max_bytes` (32 KiB by default).
- **A rewording.** The operator rewords the rule, the Sol-primary record changes the Codex routing, or the coordinator removes clauses from a surface.

## Checks

These are structural checks on text, pins and registration, not a behavior test. Each check below failed first against the unedited text with exit 1, and each passes now.
- **`StandingRuleSurfacesTests.test_the_three_surfaces_carry_the_same_standing_sentences`** (new) failed first with 21 failing subtests.
- **`TemplateTests.test_top_rule_carries_the_standing_clauses_and_a_lane_for_every_configured_server`** checks the Codex block's lanes and clauses. It failed first each time:
  - on the first build's unedited block it listed all seven servers as missing;
  - after the fold it listed five routing and skill-matching phrases;
  - before the Ultra/Max split it listed four split phrases;
  - before the review's wording it listed nine phrases.
- **`PortableTopRuleTests.test_the_template_carries_the_standing_clauses_and_the_user_level_rules`** checks the portable template's phrases. It failed first each time:
  - on the unedited template it found 29 phrases missing, 9 of them held only by the user-level file;
  - after the fold it found four routing and skill-matching phrases missing;
  - before the split it found four split phrases missing;
  - before the review's wording it found the new coordinator and pinned-launch phrases missing.

  It also requires "Keep context small"; run against the observed version of the template, it reports that phrase missing.
- **The Codex pin.** The top-rule pin was re-derived with the test module's own `template_segments()`: 538 words by Python `str.split()`, `9565217f…`.
- **The word budget.** The portable template's baseline moves to 1,750 words (`str.split()`), following the re-baselines of 2026-09-27 and 2026-09-29.
- **The scaffold.** `tests/test_scaffold_repo.py` passes with the synced block.
- **The folded evidence.** `validate.py --scan-file` passed over the 18 folded files. `python3 scripts/validate.py` passes with them hash-listed in `manifests/evidence.json`, and `python3 scripts/validate_convergence.py --all-recorded` still finds and validates the declared records.

## Limitations and integration

- **Clause (c) and the settings.** The clause "every manifest skill stays listed for model invocation in both clients" is dropped. It can return once F3's settings make it true. Even then, `grill-me` and `improve-codebase-architecture` stay user-invocable-only unless they change or are replaced.
- **Known residual links.** Six relative link targets do not resolve on this branch. Four resolve when unit F3 lands:
  - `docs/decisions/2026-09-30-native-skill-lifecycle.md`;
  - `evidence/artifacts/native-skill-lifecycle-20260930/receipt.json`;
  - `evidence/artifacts/native-skill-finalization-20260930/results.json`;
  - `evidence/artifacts/native-skill-finalization-20260930/usage-summary.json`.

  The other two are `evidence/artifacts/codex-01592-qualification-20260930/qualification.json` and `profile-command-correction.json`. They stay broken until D4's fold of that directory decides its path; two folded rows and the finalization record cite them. `AGENTS.md` names `adoption/skills/lifecycle.md` in code format with "(lands with unit F3)".
- **Older Codex pins.** The Codex block routes unpinned work to `gpt-6.1-sol`, while unit D4 renders `gpt-6-astra` for Codex pins before 0.159.1 (macOS). That wording follow-up is D4's.
- **Stale line citation.** [`tools/adoption/codex_roles.py:357`](../../tools/adoption/codex_roles.py) cites `codex.AGENTS.template.md:41-46` for the exceptions, which now sit at lines 49-54.
- **Codex approvals.** Under `approval_policy = "never"`, Codex refuses the ai-memory, SocratiCode and Headroom tools unless the stack-worker profile approves them ([`codex.config.template.toml:46-51`](../../adoption/templates/codex.config.template.toml)). The token-lanes line names them anyway.
- **Host step.** A host picks up the texts only when unit A3's installer and `tools/adoption/apply_codex_lane.py` run there, after window W (the guard above). The Gate A freeze snapshot hashes both user-level files (`tools/token-e2e/freeze_snapshot.py:1080,1129`).

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
- Anthropic engineering (read 2026-09-30):
  - [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): the evaluator-optimizer workflow;
  - [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system): the judge rubric's completeness criterion, and the objective, output format, tool guidance and boundaries of each delegated task.
- Model routing:
  - the Sol-primary record (unit D4, on main);
  - the [model-currency record](2026-09-27-model-currency.md);
  - the effort semantics in the [Codex worker lane recipe](../../recipes/README.md#codex-worker-lane) (`resolve_reasoning_effort` in openai/codex `codex-rs/protocol/src/openai_models/reasoning_effort.rs`).
- The Gate A E2E design: [`evidence/artifacts/token-adoption-e2e-20260926/README.md`](../../evidence/artifacts/token-adoption-e2e-20260926/README.md) lines 157, 188, 266 and 275, and [`RUNBOOK.md:371`](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md).
- [anthropics/claude-code v2.1.285 `CHANGELOG.md` line 206](https://github.com/anthropics/claude-code/blob/v2.1.285/CHANGELOG.md#L206) (read 2026-09-30): Ultracode "no longer forces xhigh effort and stays on at any effort level", under 2.1.284.
- Skills:
  - the pinned discovery command `DISABLE_TELEMETRY=1 <tools-root>/skills-1.7.0/bin/skills find "<query>"` ([`evidence/artifacts/skills-agents-layer-20260926/README.md:90`](../../evidence/artifacts/skills-agents-layer-20260926/README.md), [`adoption/skills/manifest.json:22`](../../adoption/skills/manifest.json)), from `vercel-labs/skills@7407f389` (`skills/find-skills/SKILL.md:27,56`);
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
