# Decision: an always-loaded instruction core for both clients

Date: 2026-10-07. Lane: the changed paths are foundation paths plus root
`AGENTS.md`, which [`docs/lanes.md`](../lanes.md) lists as a shared hot file. The
pull request's label follows that file's rule and is the coordinator's call.
Status: ruled by the command center on 2026-10-07; repository record awaiting
independent review.

## Context

On 2026-10-07 the owner asked for the instruction files that every session loads
to be cut back to a curated core. The core keeps the research-first philosophy,
with current upstream as the source of truth. Rules that apply to only part of the
work, such as the trading rules, move to the place where they apply. This record
paraphrases that direction and quotes no message.

Three sources feed what a session loads at startup: root `AGENTS.md` for both
clients, the portable Claude block `examples/claude-native/CLAUDE.md` and the Codex
block `adoption/templates/codex.AGENTS.template.md`. At
`475127d43c1cce70dba5cd31238af4e078fa17eb` the root file repeated standing
sentences that both user-level blocks already carry, held a second copy of the
Codex routing paragraph and carried the trading trigger for every session.
Measured with `tests.test_install_claude_profile.PortableTopRuleTests.startup_files`,
the Claude scope was 23,896 bytes under a ceiling of 24,458, and the Codex scope
was 20,101 bytes under a ceiling of 20,103.

## Decision

Trim in place. Every rule sentence that stays keeps its wording, except the vendor
example of item 4 and the root pointer sentences that item 1 lists. The new text
is pointer lines, topic labels and two headings.

1. **Root `AGENTS.md`** keeps a shorter top rule, the pointer to the verification
   order, the pointer to the repository-quality rule, the paragraph that describes
   the stack and its catalogs, and the rules that belong to this repository, now
   under `## Rules of this repository`. A new `## Where things are` section holds
   one pointer line per topic: skills, roles and agents, MCP tools and token
   lanes, handbooks, hosts, GitHub workflow and subtree rules. Apart from the
   routing paragraph of item 2, a standing sentence left the root file only when
   both user-level blocks carry it. The other root text that left has the
   on-demand homes listed below. The pointer sentences are recomposed from the
   base pointers, and nothing else in the file is reworded:
   - Four pointers begin in lower case after their topic label: skills, token
     practice, handbooks and hosts.
   - The harness-defaults pointer loses its summary clause and joins the
     convergence-architecture pointer in one sentence. The two dashboard pointers
     become one sentence.
   - The catalog sentence keeps only its first clause. The limitations sentence
     and the lanes sentence lose their trading clauses, and the lanes sentence now
     says that `docs/lanes.md` assigns each path to a lane.
   - New pointer text names `adoption/skills/manifest.json`, the two agent
     directories, the Codex user-level block for routing,
     `docs/github-automation.md`, the subtree rule and the two block sources.
2. **Codex routing.** Root's 868-byte copy of the routing paragraph becomes a
   141-byte pointer to the Codex user-level block and the
   [Sol-primary record](2026-09-30-sol-primary-quality-defaults.md). The 782-byte
   form stays byte for byte in the Codex template's top-rule block, where
   contract 08 binds it.
3. **Trading trigger.** The root trigger moves word for word into the new
   `.claude/rules/trading.md`. Its `paths:` list holds the directories and files
   that `docs/lanes.md` assigns to the trading lane. It leaves out
   `blueprints/us-equities/`, whose own `CLAUDE.md` imports that subtree's
   `AGENTS.md`, the trading test modules and the two profile entries inside
   `adoption/manifest.json`. For Codex, and for work that starts outside those
   paths, the trigger is the root "Subtree rules" line, whose second sentence
   names where the north star of a coordinator unit is recorded. This change adds
   no file under `catalogs/` or `blueprints/`.
4. **Vendor example.** The Alpaca example leaves the parenthesis of the "Prefer the
   maintainer's own organization repositories" sentence on the three sources, the
   scaffold and both carriers. It stays where it applies, in
   `blueprints/us-equities/AGENTS.md` and in the
   [official-upstream record](2026-10-05-official-upstream-never-rebuild.md).
5. **Portable Claude block.** The RTK installer sentence, the counting bullet, the
   web-research bullet and the Ultracode recipe bullet leave. Three pointers to the
   same README anchor become one line. The upstream-practice citation sentence
   moves word for word to that README section. One bullet is added: the Codex
   block's token-lane sentence, byte for byte, so both clients carry the same lane
   list.
6. **Codex block.** The web-research line and the queue-timing line leave. The
   courier recipe for messaging a Claude Code session moves word for word to the
   same README section, and one pointer line replaces it.
7. **Kept on purpose.** The StructuredOutput bullet, the "Bound discovery"
   paragraph, the dispatch modes, the model routing, the verbatim RTK block with
   its exceptions and the 8,192-byte bound on the compact Codex template do not
   change. Root `CLAUDE.md` is byte-identical to the base.

## Measured sizes

Bytes are UTF-8 file bytes and lines are newline counts, read with `wc` at the base
commit and after the change.

| Surface | Before | After |
| --- | --- | --- |
| Root `AGENTS.md` | 10,959 B, 57 lines | 7,294 B, 34 lines |
| Root `CLAUDE.md` | 766 B, 15 lines | unchanged |
| `examples/claude-native/CLAUDE.md` | 11,905 B, 59 lines | 11,145 B, 55 lines |
| `adoption/templates/codex.AGENTS.template.md` (compact) | 8,076 B, 50 lines | 7,418 B, 48 lines |
| `adoption/new-wsl/claude-user-instructions.md` | 11,905 B, 59 lines | 11,145 B, 55 lines |
| `adoption/new-wsl/codex-user-instructions.md` (rendered) | 9,142 B, 74 lines | 8,484 B, 72 lines |
| `.claude/rules/trading.md` (path-scoped, outside the startup scope) | absent | 630 B, 12 lines |

The startup scopes come from the test's own `startup_files`, and each new ceiling is
the measured scope plus 5%, rounded upward, as the
[budget decision](2026-10-05-harness-context-budget.md#fixed-byte-budget-and-review-procedure)
requires.

| Client | Scope before | Old ceiling | Scope after | New ceiling | Headroom |
| --- | ---: | ---: | ---: | ---: | ---: |
| Claude | 23,896 | 24,458 | 19,885 | 20,880 | 995 |
| Codex | 20,101 | 20,103 | 15,983 | 16,783 | 800 |

The Claude scope is the managed block (11,411 bytes with its markers), root
`AGENTS.md` and root `CLAUDE.md`. The Codex scope is the rendered block and root
`AGENTS.md`. The Claude scope falls by 4,011 bytes (16.8%) and the Codex scope by
4,118 bytes (20.5%). These are file bytes. No session was started and no token
count was taken.

The "after" figures were re-measured at the landing head bcc9f677 with the test's own
`PortableTopRuleTests.startup_files()`: Claude 11,411 + 7,499 + 975 bytes, Codex 8,484 + 7,499 bytes.
The first draft's 19,471 and 15,778 predated the restored trading sentence in root `AGENTS.md` and
#833's pointer line in root `CLAUDE.md`. A review thread on the PR found the mismatch, and the
ceilings remain measured scope + 5%, rounded upward.

The Codex template's two pins, computed with the segmentation of
`tests/test_codex_worker_lane.py`, change as follows.

| Pin | Before | After |
| --- | --- | --- |
| `TOP_RULE_SHA256` | `f4b66fb52b0fceeed8b6207e0003de792cabfaef5ece49b6f5d6a445ee2d26ef` | `0f6b14d8b59cc7b6e39236d2e42241d5769d4bdffe9d75f7608b8bf0542b1f71` |
| `PRE_RTK_SHA256` | `ae8784589d6a042b1feedfbdb746544ba547dac8a38dfb84991923af591764fc` | `7c747c0a8cf80220a2782beef46f26608eb554f30d272af680bc9ef1f994a2e2` |

## Where the displaced text lives

| Passage, by its source at the base | Where it is now |
| --- | --- |
| Root: the standing sentences on coordinator-scoped skill discovery, upstream A/B and E2E harnesses, the compounding ecosystem, what a prompt fixes, the harness purpose, the completeness critic, bounded discovery and a startup without audits | Both user-level blocks, unchanged there; the Codex block names a bounded worker in the discovery sentence, as before |
| Root: the skill-matching sentence | Each user-level block states it in its own wording |
| Root: the Codex routing paragraph (868 bytes) | The Codex template's top-rule block (782-byte form, contract 08); root keeps a pointer |
| Root: the trading trigger (285 bytes) | `.claude/rules/trading.md`, word for word; the root "Subtree rules" line for Codex |
| Root: the trading clauses of the catalog, lane and limitation sentences | `catalogs/README.md`, `docs/lanes.md` and `blueprints/us-equities/AGENTS.md` |
| Root: the summary clause of the harness-defaults pointer | `docs/harness-defaults.md` itself, which root still names |
| Root: the upstream-executables sentence | Each user-level block's top rule, which requires the supported install and test commands of the selected source |
| Root: the two sentences on convergence claims | `docs/convergence-architecture.md` |
| Root: the cheapest-representation and count-once sentences | `docs/token-practice.md` |
| Root: the token-report pointer | `docs/token-session-handbook.md` |
| Three sources and the scaffold: the Alpaca example | `blueprints/us-equities/AGENTS.md`; the official-upstream record |
| Both blocks: the web-research line | No startup text. The tracked entry point is `tools/research/gpt_researcher.sh`, and the trigger is the `native-stack-research` skill that [the G2 record](2026-10-04-2604-e2e-fix-wave-g2-mcp-workers.md) has a host install for both clients. The skill file is host-installed and is not tracked here. |
| Codex block: the courier recipe (485 bytes) | The README's [mechanics section](../../examples/claude-native/workflows/README.md#native-workflow-mechanics-relocated-2026-10-05), word for word (contract 12) |
| Codex block: the queue-timing line | The same section already states it |
| Portable block: the RTK installer sentence | The budget decision's native-defaults section; `tools/adoption/managed_block.py` keeps the `@RTK.md` import outside its markers |
| Portable block: the counting bullet | `docs/token-practice.md` (count once, never add overlapping counters) and `docs/convergence-architecture.md` (elapsed time and complete provider usage, including children, retries and failed attempts) |
| Portable block: the Ultracode recipe bullet | `recipes/claude-native-ultracode.md` |
| Portable block: the upstream-practice citation sentence (319 bytes) | The README's mechanics section, word for word (contract 13) |

## Changed test expectations

The command center ruled these five changes on 2026-10-07. No other expectation
of the two test modules changes.

| # | Test | Change | Kind | What it supersedes |
| --- | --- | --- | --- | --- |
| 1 | `tests.test_install_claude_profile.StandingRuleSurfacesTests.test_the_three_surfaces_carry_the_same_standing_sentences` | `SURFACES` no longer lists root `AGENTS.md`. The nine standing sentences and the two dropped phrases are checked on the portable Claude block and the Codex template. | Assertion relaxed | The three-surface rule of the [2026-09-30 record](2026-09-30-rule-text-every-layer.md), the root clauses of the budget decision's PR #726 addendum, and the root row of the official-upstream record's surface table, which names this test as the binding of root's sentence |
| 2 | The same test | The first standing sentence no longer holds the Alpaca example. | Behaviour changed | The wording that the official-upstream record put on the three surfaces |
| 3 | `tests.test_install_claude_profile.PortableTopRuleTests.test_each_relocated_passage_is_byte_bound_to_its_destination_section` | Contract 01 leaves `tests/fixtures/harness-context-moves/contracts.json`; `01.txt` stays as a snapshot. Contracts 12 and 13 are added. | Assertion relaxed; two assertions added | The temporary full routing paragraph in root `AGENTS.md` of the PR #726 addendum |
| 4 | `tests.test_codex_worker_lane.TemplateTests.test_top_rule_is_pinned_and_rendered_rtk_is_the_unchanged_pinned_source` | `TOP_RULE_SHA256` and `PRE_RTK_SHA256` take the values above. | Behaviour changed | The two pins at the base commit |
| 5 | `tests.test_install_claude_profile.PortableTopRuleTests.test_rendered_startup_files_fit_each_clients_fixed_byte_budget` and `test_growth_in_any_loaded_file_crosses_the_fixed_budget` | `STARTUP_BUDGET_BYTES` changes from 24,458 and 20,103 to 20,880 and 16,783. | Tightened | The amended ceilings of the PR #726 addendum |

## What this record supersedes and what it keeps

In the [budget decision](2026-10-05-harness-context-budget.md#required-startup-behavior-and-accepted-record-amendments)
this record supersedes the root copies only: cross-family dispatch and the full
routing paragraph inline in root `AGENTS.md`, the discovery conditional and the
"Prompts fix the objective" sentence on root, and the root trading trigger. It also
supersedes the three-surface rule of the 2026-09-30 record. Both user-level blocks
keep the cross-family, discovery and prompt sentences, and the Codex block keeps
the routing paragraph.

It also supersedes two further records in part. The 2026-10-05 addendum of the
[cleanup record](2026-09-26-harness-rules-cleanup.md) kept an explicit root
trigger that lists the trading activities, and it said that disclosure to Codex
depends on that trigger. Root now carries the shorter "Subtree rules" line
instead. That addendum's condition stands: a north-star or paper rule missed at a
trigger restores the root text. The cleanup record receives no addendum in this
change. The "Instruction lines" item of the
[client-configuration record](2026-10-02-new-wsl-client-configuration.md) put the
GPT Researcher line and the messaging lines in both sources. The GPT Researcher
line now leaves both, and the Codex messaging lines move to the README behind a
pointer. The context-mode and semble lines of that item stay.

It keeps the StructuredOutput restoration, the verbatim RTK block, root's stop
condition for a material decision, the root pointer to the repository-quality rule
and the 8,192-byte bound. It follows the budget decision's ceiling procedure: a
dated record with old and new rendered bytes, the constants changed in the same
diff, and the carriers regenerated before the tests ran.

That decision left one condition open for replacing the root routing copy: a
read-back of the routing phrases in each actual Codex-home `AGENTS.md`, including
the bounded SDK jobs' `codex-home-full`. The command center waived that condition
for this change on 2026-10-07. The routing text itself stays byte-identical in the
Codex template, and only the root copy becomes a pointer. The 188-byte pointer and
the 24,031 and 19,389 ceilings which that decision projected for the replacement
are replaced by the measured values above.

## Alternatives

- **Keep three surfaces and trim only the user-level blocks.** Rejected. Most of
  the excess was in the root file (down 33%), and the Codex scope sat 2 bytes
  under its ceiling.
- **Start a new repository or a new distribution for the instruction kit.** Not
  needed for this trim; the change is one pull request.
- **Move the dispatch modes and the model routing into a skill.** Not done. The
  one A/B on record, in the
  [model-fallback record](2026-09-25-model-fallback-guard.md), counted a schema
  error in 5 of 30 children without the StructuredOutput sentence and in 0 of 30
  with it, and a sequential check with the sentence only in the user-level file
  also counted 0 of 30. PR #726 reversed an earlier move of that sentence out of
  the user-level block for want of a new comparison. Moving these rules needs
  its own evidence.
- **Retire the courier recipe.** The command center ruled that it moves to the
  README instead.
- **Give Codex a trading trigger in a subtree `AGENTS.md` under `catalogs/`.**
  Left to the trading lane, which owns those paths.

## Overturn conditions

- A session misses a displaced rule at its trigger. Compare that session's record
  with the pointer that should have led to the rule, and return the sentence to
  startup if the pointer failed.
- A fresh session per client, after the host apply, loads a startup context that
  does not fall by about the bytes above. Compare the first request's input
  tokens before and after.
- A read-back of an actual Codex-home `AGENTS.md` lacks `gpt-6.1-sol`, "spawn call
  names neither" or "starts a cross-family lane". This reopens the root routing
  pointer.
- Claude Code changes how path-scoped rules load, or Codex changes its discovery
  walk. Compare the new vendor text with the sources below.

## SOTA sources

- [Claude Code memory documentation](https://code.claude.com/docs/en/memory),
  read 2026-10-07. "Write effective instructions" sets a target of under 200
  lines per file, says that longer files consume more context and reduce
  adherence, and tells authors to move instructions that matter for only part of
  the codebase into path-scoped rules. "Path-specific rules" documents the
  `paths` frontmatter as a YAML list of globs and says that such a rule triggers
  when Claude uses the Read, Write or Edit tool on a matching file. A rule
  without `paths` loads at launch.
- [Claude Code best practices](https://code.claude.com/docs/en/best-practices),
  read 2026-10-07, "Write an effective CLAUDE.md": the file loads every session,
  so it should hold only what applies broadly, and each line should stay only if
  removing it would cause mistakes.
- [Codex AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md),
  read 2026-10-07, when it redirected to
  `https://learn.chatgpt.com/docs/agent-configuration/agents-md`. "How Codex
  discovers guidance": Codex reads the Codex-home file, then walks from the
  project root down to the working directory, takes at most one file per
  directory, concatenates them in that order and stops at `project_doc_max_bytes`
  (32 KiB by default).
- [openai/codex at `rust-v0.160.0`, `codex-rs/core/src/agents_md.rs`, lines 7 to 18](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/core/src/agents_md.rs#L7-L18),
  the loader of the Codex version pinned in `adoption/pins-linux-x86_64.json`. It
  collects every `AGENTS.md` from the project root down to the working directory
  and does not walk past the root. A subtree's `AGENTS.md` therefore loads only
  for a session whose working directory is inside that subtree, which is why
  root keeps the "Subtree rules" line.
- Repository references: the budget decision's ceiling procedure and its passage
  contracts, and `tools/adoption/new_wsl_client_config.py --write-blocks`, which
  wrote both carriers.

## Acceptance

Run on the changed tree in a virtual environment that holds
`.github/requirements-ci.txt` and `.github/requirements-validation.txt`, activated
so that `python3` and `zizmor` on `PATH` are the environment's.

| Command | Exit | Returned result |
| --- | ---: | --- |
| `python tools/adoption/new_wsl_client_config.py --write-blocks --dropped` | 0 | Both carriers written; 0 units left out; 55 of 55 and 72 of 72 lines stay |
| `python tools/adoption/new_wsl_client_config.py --check` | 0 | `check passed` |
| `python -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_new_wsl_client_config tests.test_scaffold_repo tests.test_adoption_docs_consistency` | 0 | Ran 513 tests; OK (skipped=14) |
| `python -m unittest` on the 25 further modules listed below | 0 | Ran 1,602 tests; OK (skipped=13) |
| `node test-envelope.mjs` and `node test-contract-mutations.mjs` in `examples/claude-native/workflows/` | 0 | 254 of 254 and 74 of 74 passed |
| `python scripts/build_new_wsl_handbook.py --check` | 0 | Output identical to the base commit's; the handbook is not regenerated |
| `python scripts/component_matrix.py --check` and `python scripts/new_host_grand_list.py --check` | 0 | Output identical to the base commit's |
| `python scripts/evidence_manifest.py --check` | 0 | 10,533 files; `passed` |
| `python scripts/validate.py` | 0 | 10,533 hashed files; `passed` |
| `git diff --check` | 0 | No whitespace errors |
| `python3 -m unittest -v --durations 50`, the whole suite as CI runs it | 1 | Ran 11,557 tests; 12 failures, skipped=1,080. The same 12 test ids fail at the base commit in the same environment, so none comes from this change |

The 12 whole-suite failures come from this host and from the test environment
inside the worktree, not from the files this change edits. Three scripts run
`dirname` under a reduced `PATH`, where it is not found. A `git clone --local`
from the temporary directory fails with "Invalid cross-device link". One check
reads a systemd scope's task state. One mutant test expects user site-packages
to be visible, which a virtual environment turns off. The verdict gate's
trust-path check finds a file in the environment's own directory, and the
credential-race mutation driver's pristine baseline fails in this checkout. The
hosted CI run of this change is the check for these twelve.

The 14 skips of the five named modules are opt-in or data-dependent: 12 need
`NAS_CODEX_INTEGRATION=1` with the pinned Codex CLI, one needs
`CONTEXT_MODE_SECURITY_JS`, and one runs only when a profile's coverage differs
between the pinned release and HEAD.

The 25 further modules are the other test modules that name a changed path:
`test_codex_agents`, `test_codex_roles`, `test_managed_block`,
`test_context_mode_practice_docs`, `test_sota_sources_gate`,
`test_bootstrap_full_profile`, `test_landscape_sweep_harness`,
`test_runtime_worker_openhands_push_gate`,
`test_runtime_worker_openhands_resolver`, `test_blind_checkout`,
`test_codex_lane`, `test_freeze_snapshot`, `test_upstream_surface_watch`,
`test_evidence_manifest`, `test_validate`, `test_ecosystem_manifest`,
`test_lane_packets`, `test_merge_guard_doc`, `test_github_automation_practice`,
`test_workflow_hardening`, `test_jcodemunch_config`, `test_foundation_catalog`,
`test_retrieval_quality_v2`, `test_token_lanes_subagent_start` and
`test_effort_default_guard`.

## Completeness review and limits

- The checks above are local integration checks. They show file bytes, carrier
  equality and passage contracts. They do not show model behaviour, and no
  session, provider call or `/doctor prompt-audit` was run.
- No host file changes. A host window installs the two carriers with the
  repository's own apply tool, and running sessions keep the old text until they
  restart. Text outside the managed markers in a user-level file is the owner's.
- The path-scoped trading rule loads when Claude reads, writes or edits a matching
  file. A trading task that starts elsewhere relies on the root "Subtree rules"
  line and on `blueprints/us-equities/CLAUDE.md`. That behaviour is documented by
  the vendor and was not observed here.
- The web-research line has no tracked startup home after this change. Its home is
  a host-installed skill.
- Not examined: the user-level text outside the managed blocks, the auto-memory
  index and the skills listing, which are larger parts of the first request than
  the bytes removed here.

## Amendment, 2026-10-07: one trading sentence stays always loaded

The trading lane's custodian asked for it before acknowledging this change. Paper and broker operation, data acquisition and
trading research mostly run outside the repository's paths (the paper roots and engines under the coordination state, the
broker gateway on the host), so a path-scoped rule does not load in exactly the sessions that operate paper. The root file's
"Subtree rules" line therefore says, for every session, that each coordinator unit names the north-star action it serves and
that trading work of any kind reads `blueprints/us-equities/AGENTS.md` first, wherever it runs. The path-scoped rule stays as
it is for sessions that do work in the trading paths.
