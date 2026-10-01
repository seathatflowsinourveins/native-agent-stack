# Decision: stack agents and dispatch by role (2026-09-26)

**Decided by:** a workflow unit on host `nativestack-5975wx-20260925`, following the 2026-09-26 child-dispatch
research (read-only scouts of this host's workflow transcripts, not retained as receipts). Branch
`claude/stack-agents-dispatch-20260926`, based on `origin/main@771f25f8`, checked on Claude Code 2.1.283.

**Scope:**
- three new agents, `stack-researcher`, `stack-verifier` and `security-reviewer`, in
  [`adoption/agents/claude/`](../../adoption/agents/claude/) (installed to `~/.claude/agents/`) and byte-identical
  in [`examples/claude-native/agents/`](../../examples/claude-native/agents/);
- `isolated-builder`, which loses Serena's four symbol-edit tools and preloads two selected skills;
- the role table in the
  [workflow examples](../../examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26), bound by
  `test-envelope.mjs` and `test-contract-mutations.mjs`, plus the rows of the
  [Ultracode recipe](../../recipes/claude-native-ultracode.md) and one pointer line in `AGENTS.md`;
- `tests/test_install_claude_profile.py`, and the agents note in `adoption/bootstrap.md`.

Nothing is installed on a host by this change. Running the installer's agents step is a separate, coordinated step.

## Decision

| Role | `agentType` | Change |
| --- | --- | --- |
| scout | `source-scout` | unchanged |
| researcher | `stack-researcher` | new: Opus, max. Read, Glob, Grep, Bash, WebSearch, ToolSearch; Context Mode `ctx_batch_execute`, `ctx_execute`, `ctx_execute_file`, `ctx_fetch_and_index`, `ctx_search`; `qmd` `query` and `get`; ai-memory `memory_query` with explicit static-client workspace/project; Serena `find_symbol`, `find_referencing_symbols`, `get_symbols_overview`; jCodeMunch `route`, `menu` and read-only `order`. No Edit, Write, NotebookEdit, WebFetch or Skill; no preload |
| builder | `isolated-builder` | Serena `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol` and `rename_symbol` removed; the body says which lanes answer for the parent's project. Targeted `skills:` preload: `context-mode:context-mode` and `verification-before-completion`; ctx commands enter the worktree, while `ctx_execute_file` retains the session-root boundary |
| reviewer | `evidence-reviewer` | unchanged |
| security | `security-reviewer` | new: Opus, max. Read, Glob, Grep, ToolSearch; Serena `find_symbol`, `find_referencing_symbols`, `find_declaration`, `find_implementations`, `get_symbols_overview`, `get_diagnostics_for_file`; SocratiCode `codebase_search`, `codebase_symbol`, `codebase_impact`, `codebase_flow`; jCodeMunch `route` and read-only `order`; Context Mode `ctx_execute`, `ctx_execute_file`, `ctx_batch_execute`, `ctx_search`; ai-memory `memory_query`, `memory_read_page`, `memory_read_session_observations`. Same named read grant as `evidence-reviewer`; no Bash, Edit, Write, WebFetch or Skill. Preloads `security-best-practices`; reports findings, never fixes |
| verifier | `stack-verifier` | new: Sonnet, max, `omitClaudeMd`, `maxTurns: 100`. Read, Glob, Grep, Bash, ToolSearch; Context Mode `ctx_batch_execute`, `ctx_execute`, `ctx_execute_file`, `ctx_search`. Never fixes |
| adjudicator | `blind-adjudicator` | unchanged |

The lane rules live in each agent's body, so a stage packet carries only its task. The researcher and verifier bodies end on an
exhaustive completion criterion and return findings inline, a rule stated to outrank injected guidance to write
artifacts to files. A `general-purpose` stage, or one without `agentType`, carries a `// dispatch: <reason>` comment beside the
call, a fixed form a later launch-time guard can check.

The builder preload narrows, rather than reverses, the no-default-preload constraint quoted as D3 in the WP5
task: D3 deferred a default for every role child because preload viability was unverified `[nv]`. This unit
selects two skills for one named builder role, plus one security skill for its reviewer sibling. The
[skills-trial addendum](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-targeted-role-preloads-security-reviewer-isolated-builder)
records all six roles' choices. Only `on`/`name-only` table entries are eligible; `user-invocable-only`/`off`
are excluded. The plugin skill is available at context-mode 1.0.169 and is checked separately from that table.
The upstream [preload mechanism](https://code.claude.com/docs/en/sub-agents#preload-skills-into-subagents)
is documented, and the [listing-state addendum](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-listing-state-and-agent-preload)
is now present in this checkout with its 2.1.283 `tdd`/`semgrep` probe. That addendum's probe covers
pinned, table-listed skills; `context-mode:context-mode` is a plugin-scoped skill outside the pinned table,
so its eligibility rests on the same upstream mechanism (no `disable-model-invocation` field in its
installed `SKILL.md`) rather than a repeat of the probe on a plugin skill specifically.
`verification-before-completion` and `security-best-practices` likewise have no repeat native probe
specifically. First-prompt size for all three preloaded configurations remains unmeasured; source review
is not preload acceptance. Their first-prompt sizes join the researcher/verifier rows' preregistered comparison.

## Evidence

| Claim | Class | Source |
| --- | --- | --- |
| Serena resolves its project once, from the server process's working directory, and cannot switch it in Claude Code | `source_review` | [oraios/serena@c6fbd1c `src/serena/cli.py`](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py) `--project-from-cwd` ("Auto-detect project from current working directory"), resolved in `start_mcp_server`; `src/serena/resources/config/contexts/claude-code.yml`: `single_project: true` ("The `activate_project` tool is always disabled in this case"). The same context tells agents to edit through `replace_symbol_body` and `insert_*_symbol` ("Edit -> FORBIDDEN") |
| A subagent's MCP tools named by string use the parent session's server | `source_review` | [sub-agents](https://code.claude.com/docs/en/sub-agents), "Scope MCP servers to a subagent": "String references share the parent session's connection" (fetched 2026-09-26) |
| Serena stayed bound to the session project inside subagents | retained observation | [`evidence/artifacts/token-e2e-ultracode-20260925/README.md`](../../evidence/artifacts/token-e2e-ultracode-20260925/README.md), "Serena, attempt 1" |
| `ctx_execute_file` refuses a path outside the session's project root | `source_review` plus retained observation | context-mode 1.0.169 `src/server.ts` `checkProjectBoundary` (issue #852); the same README, "Context Mode, attempt 1" |
| Context Mode's Agent-prompt block asks subagents to write artifacts to files and return only a path | `source_review` | context-mode 1.0.169 `hooks/routing-block.mjs`, `<artifact_policy>` |
| Leaving `Skill` out of `tools` keeps a subagent from invoking skills; a stage's `model` is the per-invocation model and outranks the agent's frontmatter | `source_review` | [sub-agents](https://code.claude.com/docs/en/sub-agents) "Preload skills" and "Choose a model"; [workflows](https://code.claude.com/docs/en/workflows) ("counts as the per-invocation model") |
| `skills:` injects full skill content; invocation-disabled skills cannot preload. Targeted builder/security lists use eligible pinned skills and the available context-mode plugin skill | `source_review`, not native preload acceptance | [sub-agents](https://code.claude.com/docs/en/sub-agents), fetched live for WP5; [pinned skills and preload boundary](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-targeted-role-preloads-security-reviewer-isolated-builder); `semantic-evidence-reviewer` supplies the block-list frontmatter template |
| jCodeMunch `menu` discovers catalog actions, between `route` and read-only `order` dispatch; static ai-memory clients supply workspace/project together | `source_review` | [jgravelle/jcodemunch-mcp@8f7b34a `src/jcodemunch_mcp/server.py`](https://github.com/jgravelle/jcodemunch-mcp/blob/8f7b34abe16fb459e0bf1c04747d584216dfe32e/src/jcodemunch_mcp/server.py), counter tool instructions and schemas; ai-memory `memory_query` tool instructions; [token-session handbook](../token-session-handbook.md#full-reusable-task-prompt) |
| Siblings share a prompt-cache prefix only with the same agent type and tools | `source_review` | [workflows](https://code.claude.com/docs/en/workflows), prompt cache paragraph |
| Read-only research and review agents are defined by a tools allowlist without edit tools | `source_review` | [anthropics/claude-code@7779afb `plugins/feature-dev/agents/code-explorer.md`](https://github.com/anthropics/claude-code/blob/7779afb12e3635f46f56ec823979d68350ae000b/plugins/feature-dev/agents/code-explorer.md); the built-in Explore agent ("Write and Edit are denied"); [giancarloerra/SocratiCode@23569f0 `agents/codebase-explorer.md`](https://github.com/giancarloerra/SocratiCode/blob/23569f0b05089edfe9a941894508ae8b9a35c4d2/agents/codebase-explorer.md); this catalog's `evidence-reviewer` (first prompt 12,164 for the deferred shape, [routing guide](../ultracode-token-routing-20260921.md)) |
| Why a change was needed: 93 of 128 workflow children in one session ran as `general-purpose`; Context Mode was used in 21 of 21 `evidence-reviewer` children and 14 of 93 `general-purpose` children; 10 of 113 URL fetches went through `ctx_fetch_and_index`; median first prompt 37,044 tokens (`general-purpose`, Opus, n=60) against about 17.7k (`evidence-reviewer`, n=21) | unretained scout measurement | read-only 2026-09-26 scouts; role and task confound these counts, and the preregistered comparison below replaces them |
| The agents parse, use documented fields, pin their tool surfaces and match the role table | `local_integration` | `node test-envelope.mjs`, `node test-contract-mutations.mjs`, `python -m unittest tests.test_install_claude_profile` |

## Alternatives

1. **`general-purpose` children with lane text in each packet.** Rejected: in the scouts, lanes a prompt named were
   rarely used (Serena 0 of 14, SocratiCode 0 of 42, QMD 0 of 18), while the allowlist-shaped reviewer used Context
   Mode in every child. It stays the comparison arm below.
2. **SubagentStart injection for these agents too.** Rejected: the Context Mode bridge targets the default child
   types, and a second block would duplicate lane text in the first prompt. Bodies keep one byte-stable text per
   agent type.
3. **Shipping the agents as a plugin.** Rejected: plugin subagents ignore `hooks`, `mcpServers` and
   `permissionMode` ([sub-agents](https://code.claude.com/docs/en/sub-agents)).
4. **An Opus verifier** (the research proposal). Sonnet is the default, as for `source-scout`, which ran the
   acceptance commands of eight native reviews; a stage passes `model: 'opus'` when a verdict needs judgment.
5. **SocratiCode or Headroom for the researcher.** Not granted: a lane is granted only with a written route in the
   body and pruned by measured use. In the scouts, SocratiCode was named in 42 child prompts and used in none.
6. **Keeping Serena's edit tools through an inline per-agent Serena server started in the worktree** (an inline
   `mcpServers` entry in `~/.claude/agents/` loads without a folder-trust check). Deferred: one server process per
   child, not measured.
7. **Writing the role mapping into `AGENTS.md`.** Not now: one pointer line first, with the mapping kept in one
   table; the planned `PreToolUse` guard on the Workflow tool enforces dispatch.
8. **WebFetch for the researcher.** Rejected: without it `ctx_fetch_and_index` is the only fetch tool; a Bash
   `curl` remains possible, so fetch routing is still measured.

## Acceptance and overturn

- **Install check.** After the coordinated installer run, each `~/.claude/agents/` copy matches the checkout
  byte for byte, and a workflow child's `agent-<id>.meta.json` shows the requested `agentType` and resolved model.
  `claude agents` 2.1.283 is the background-session view ("Manage background agents"), so it does not list
  definitions.
- **Preregistered comparison.** Frozen tasks: the 16 checked tasks of #296 and the Codex set of #343. Arm A is
  current practice (`general-purpose` with lane text in the packet); arm B follows the role table. Per child
  (`child-usage.mjs`): correctness on the frozen checks, billed cost per successful task including cache and failed
  attempts, first-prompt tokens, Context Mode lane share, the share of URL fetches through `ctx_fetch_and_index`,
  inline returns and wall time. Include `security-reviewer` and the builder's targeted preload with the
  researcher/verifier rows; none has a measured first-prompt figure for this configuration yet. `blind-*`
  children are the negative control: no lane calls.
- **Adopt B** when its correctness is at least A's, its billed cost per successful task is at most 1.10 times A's,
  the `stack-researcher` median first prompt is below the `general-purpose` median of the same run, and at least
  90% of its URL fetches go through `ctx_fetch_and_index`.
- **Overturn** the table if B's correctness falls below A's or its cost exceeds A's by more than 10%. Restore the
  builder's Serena edit tools only after a probe shows an inline Serena server started in the worktree edits the
  worktree and nothing else.

## Limitations

- None of the three new agents (`stack-researcher`, `stack-verifier`, `security-reviewer`) has a native run.
  The builder's new preload also has no measured first-prompt figure or repeat native probe of its two skills
  specifically; its historical run predates this configuration. The targeted change narrows the task's D3
  no-default-preload constraint, without establishing a default for every child. The cited
  [listing-state/2.1.283 probe addendum](2026-09-25-skills-trial-and-usage.md#addendum-2026-09-26-listing-state-and-agent-preload)
  is now present in this checkout, but its pinned, table-listed `tdd`/`semgrep` probe is not a repeat native
  run of `context-mode:context-mode`, `verification-before-completion` or `security-best-practices`
  specifically. The plugin-scoped skill is outside the pinned table; its eligibility rests on the absent
  `disable-model-invocation` field in its installed `SKILL.md`. These additions remain source review and
  local checks, with measurement preregistered alongside the researcher/verifier rows.
- The read-only rules are instructions: the researcher/verifier's Bash and the reviewers' Context Mode
  `ctx_execute*` can write; named jCodeMunch `order` also requires a read-only action choice.
- The vendored `readiness-audit` verify stage stays on the default child until its agent-lab source changes.
- A host at `v2026.09.26` installs the previous seven definitions; `adoption/bootstrap.md` says so.

## Addendum 2026-09-27: Opus builder and verifier, no frontmatter isolation

Recorded before any run of the preregistered comparison above, so it amends arm B rather than any result
([2026-09-27 record](2026-09-27-claude-harness-settings.md)).

- **The user's rule decides the verifier's model.** The host's global instructions put Opus at effort max on
  build and verification and keep Sonnet or Haiku for command wrappers, mechanical extraction and probes, and
  the user asked on 2026-09-27 for Opus on the preregistration and verification workflows. Alternative 4's
  Sonnet default is superseded: `stack-verifier` and `isolated-builder` declare `model: opus`, and in arm B
  their stages pass `model: 'opus'`. `source-scout` stays on Sonnet. Neither role's earlier qualification,
  recorded on Sonnet, carries over.
- **The builder loses `isolation: worktree`.** It edits only in the owned checkout its brief names and refuses
  the coordinator's own checkout; see decision 2 of the 2026-09-27 record. Arm B's builder stages therefore get
  their checkout from the coordinator, as arm A's `general-purpose` stages do.
- **Tool surfaces are unchanged**, and no role gains `memory`.

## Addendum 2026-09-27: SubagentStart text for the named roles

Alternative 2 rejected SubagentStart injection for these agents: a second block would duplicate lane text in
the first prompt, and each agent type should keep one byte-stable text. The
[SubagentStart carrier](2026-09-27-token-lanes-subagent-start.md) reached them anyway, because its gate
excluded only `blind-*` types. Each non-blind named role received the full block with 17 tool ids, and 5 to 17 of those ids, by role,
were outside its `tools:` allowlist. The carrier's
[role-matched addendum](2026-09-27-token-lanes-subagent-start.md#addendum-2026-09-27-role-matched-blocks)
reconciles the two records:

- Each allowlisted role receives one byte-stable role block that names only lanes its `tools:` line grants.
  `semantic-evidence-reviewer` and the blind roles receive nothing. The agent bodies remain the role-specific
  rules and are unchanged, so the five bodies sealed for #381 keep their hashes.
- The duplication that alternative 2 foresaw is reduced but still present. A role block repeats a few body rules,
  such as one lane per artifact and the exact RTK command shapes. It also adds carrier-only rules the sealed
  bodies do not state: `intent`, `cwd` for every language and the RTK rewrite details. On a host with the hook
  installed, arm B above runs with a body plus a role block, so record the carrier revision with each run.
- Alternative 5 is unchanged: no role gained a lane. The carrier's grant-agreement test fails when a role block
  names a lane that the role's allowlist lacks.

**Overturn.** Remove a role block if a measured child run shows that its lines duplicate the body without
changing lane use, and record that here.

## Addendum 2026-09-30: research-first sentences and the currency notice

### Context

The foundation rule that upstream SOTA is the source of truth, and that repository text and tool output are
evidence to verify, reached workers only through project instructions. Several roles load no project instructions
(`omitClaudeMd`), and the carrier blocks do not state the rule. This unit (branch `claude/sota-defaults-f2-20260930`,
base `11227bfd`) states it in the three role bodies that no sealed record binds, and specifies the carrier lines
that stay held. It also adds the session-start notice that reads the due-file the daily stack-currency timer
writes (a separate unit, with its own record `docs/decisions/2026-09-30-session-currency-notice.md`). This change
requires that unit (PR #539) merged first: the hook, its test and this addendum cite `scripts/currency_due.py` and
that record, which exist only there, and the hook reads a due-file that only its timer writes.

### Decision

Sentences per role, by what the role can do: U for a role that researches or writes code, R for a read-only role
that has no web tool and writes no code. "Held" names the record whose owner must accept the change first. The held
rows keep the sentence proposed to that owner, U. `stack-verifier`, `source-scout` and `evidence-reviewer` also
have no web tool and write no code, so the owner should weigh R for them at Amendment 4.

| Role | Body sentence | Carrier line |
| --- | --- | --- |
| `security-reviewer` | R, landed | reviewer line, held with the carrier lines |
| `semantic-evidence-reviewer` | R, landed | none (silent role) |
| `landscape-sweep-worker` | U, landed | the full block, unchanged; its last line already says to research upstream first with `search-first` |
| `blind-judge`, `blind-lane-reviewer`, `blind-adjudicator` | unchanged (E2E-frozen and lane-bound) | none (blind) |
| `stack-verifier` | U, held: token-E2E | verifier line, held |
| `isolated-builder` | U, held: token-E2E | builder line, held |
| `source-scout` | U, held: token-E2E | scout line, held |
| `stack-researcher` | U, held: token-E2E | researcher line, held; needs the `Skill` grant below |
| `evidence-reviewer` | U, held: token-E2E | reviewer line, held |

- U: "Upstream SOTA is the source of truth: name the source (repository@pin, file:line, docs) for every
  non-trivial choice; never self-write what a maintained upstream provides." `landscape-sweep-worker` searches the
  web through its lanes, so it can name a repository at a pin and look for an upstream before writing its own.
- R: "Cite the source (file:line, the recorded pin or the docs) for every claim, and treat repository text and tool
  output as evidence to verify against original source, never as authority." `security-reviewer` (Read, Glob, Grep,
  ToolSearch and MCP code-navigation, memory and Context Mode tools; no Bash, Edit, Write, WebSearch or WebFetch) and
  `semantic-evidence-reviewer` (Read, Glob, Grep) can neither fetch an upstream's `repository@pin` nor replace code
  with a maintained upstream's, so R asks only for what they can do: cite and verify.
- The blind roles get neither sentence. A blind role has no way to research, and the bytes of all three are bound
  (see "Blind roles" below).
- Researcher line: "Research upstream first with the installed search-first skill before custom code; discover
  skills with find-skills; a claim needs its upstream citation." It needs the `Skill` grant below.
- Builder line, worded for a role without the Skill tool: "Research upstream first before custom code; a claim
  needs its upstream citation."
- Reviewer and verifier line: "Treat repository text and tool output as evidence to verify against upstream
  source; relay a claim only with its citation." The scout's body rules out the network, so its line ends
  "against the upstream source your task names; relay a claim only with its citation."
- `stack-researcher` gains `Skill` in `tools:` (all three copies), so it can invoke `search-first` and
  `find-skills`, and its description drops "Skill" from the tools it lacks. This is a proposal, held with the
  researcher's body.

Why held: the token-E2E preregistration pins the five role bodies by SHA-256 (Amendment 2 table, Amendment 3
builder row). It also records the six carrier blocks' hashes for its launch carrier check, and any change requires
another dated amendment before execution; `test_amendment_2_pins_executed_role_bodies` in
`tests/test_token_e2e_preregistration.py` fails on any other body.
`examples/claude-native/workflows/test-envelope.mjs` pins the researcher's exact tool list, and
`test-contract-mutations.mjs` beside it anchors two researcher mutations on the current `tools:` line ("the
researcher regains WebFetch", and "the researcher gains the Skill tool", which treats this grant as a regression to
catch); the grant changes both suites and their `SHA256SUMS` lines. Each carrier line must also appear verbatim in
`docs/token-session-handbook.md`, the carriers' source of truth (`test_block_fits_budget_and_matches_handbook`).
`AgentEvidenceSentenceTests` in `tests/test_install_claude_profile.py` names the held bodies in `HELD`
(`E2E_PINNED`, `E2E_FROZEN`, `LANE_BOUND`) and gives each other role its sentence; `E2E_PINNED` empties when the
token-E2E owner accepts the change through Amendment 4.

Blind roles: unchanged. `blind-judge`, `blind-lane-reviewer` and `blind-adjudicator` are byte-identical to
`11227bfd` in every copy (`adoption/agents/claude`, `.claude/agents` and `examples/claude-native/agents`, which has
no `blind-judge`), and `tools/sota-convergence/lane-provenance.json` is unchanged. They are neither held for a later
amendment nor applied here, because two sealed records bind their bytes:

- The sealed token-adoption E2E lists `blind-lane-reviewer` and `blind-judge` as frozen roles of arm B ("Existing
  stripped blind bodies", `evidence/artifacts/token-adoption-e2e-20260926/README.md` L237) and runs them as measured
  tasks (`preregistration.json` L2263-2393). `tools/token-e2e/judge.py` refuses a user copy of `blind-lane-reviewer`
  that differs from the repository's (`ROLE_NAME` L48, `role_issue` L697-707).
- `tools/sota-convergence/lane-provenance.json` binds `blind-lane-reviewer` and `blind-adjudicator` by hash:
  `record_verdicts.py` and `scripts/landscape.py` refuse unregistered keys, and `tests/test_verdict_lane_vendoring.py`
  requires the current hashes to be registered, so any change to those two bodies needs new registry digests.

A blind role also has no way to research, so it gets no research-first or evidence clause.
`AgentEvidenceSentenceTests` requires every `blind-*` body to be in `HELD` and to carry neither sentence.

Currency notice: `adoption/hooks/claude/currency-due-notice.py` runs on SessionStart `startup` in Claude Code
(settings template, installer hook map, `SHA256SUMS`).
Codex parity is a template only, not applied by any installer; B1 applies no Codex hook.
B1 is the host-apply unit that follows this change.
`adoption/templates/codex.hooks.template.json` holds the one group that would run the same script under Codex, and
it can only be used by hand-appending that group after ai-memory's one SessionStart group in the user `hooks.json`.
The config template ships no trust entry for it: Codex keys a hand-appended group by its position
(`session_start:1:0` after ai-memory's one SessionStart group, `session_start:2:0` or later after more), and at
every position the handler stays untrusted, and is skipped, until it is reviewed in `/hooks` (Codex's trust rule
for hooks; the keys were measured for the second and third positions with Codex 0.157.1 and 0.159.2; see Sources).

The hook prints only `summary_line`, and prints nothing for a missing or stale (over 8 days) due-file. It also
prints nothing for a malformed or unreadable file, one more than a day ahead, one that is not a regular file, or one
not owned by the user or writable by group or others, and none when no absolute state directory is known (a relative
`HOME` would resolve against the working directory). It uses no network and no subprocess. The owner and mode
condition goes beyond the unit brief; the due-file writer creates the file 0600. The runtime budget is held as the
hook's own share over a bare interpreter start (50 ms, median of nine runs); the whole-process median is printed by
the test, not asserted against 50 ms, and only a 1 s ceiling bounds it.

First-prompt size (preregistered above): the `Skill` grant is held (H3, the Gate A owner's Amendment 4), not
applied by this change. When it lands it adds the Skill tool and its skill listing to every `stack-researcher`
first prompt, and the Adopt-B criterion (its median first prompt below the `general-purpose` median of the same
run), itself unchanged, then includes that listing. The size is unmeasured; the coordinator's headless preload
probe measures it before and after the grant lands, and the result is recorded here.

The Codex-native example role `examples/codex-native/agents/semantic-evidence-reviewer.toml` and the installed
worker role of unit F4 do not carry the reviewer sentence: both are outside this unit's paths, and the Codex copies
take the sentence in one follow-up after this change and F4 merge, so that the two Codex files change together.

### Alternatives

1. The brief's researcher sentence for the builder too. Rejected: the builder has no Skill tool, and the
   carrier's grant test refuses a block that names a skill its role cannot invoke.
2. Codex hooks inline in the user `config.toml`. Rejected: Codex warns when one layer holds hooks in both
   `hooks.json` and TOML, and ai-memory's installer already writes the user `hooks.json`.
3. A second output shape for Codex. Not needed: Codex 0.157.1's SessionStart output schema accepts the
   `hookSpecificOutput` object Claude Code documents.
4. Sentence U on every body, as the unit brief worded it. Rejected for `security-reviewer` and
   `semantic-evidence-reviewer`: neither has a web tool or writes code, so U would ask them to name a
   `repository@pin` and to avoid self-writing what an upstream provides, which they cannot do. R asks for a
   citation and for verification against original source, which they can.
5. An evidence clause on the three blind bodies, with new lane-registry digests. Rejected: the sealed
   token-adoption E2E freezes `blind-judge` and `blind-lane-reviewer`, the lane registry binds
   `blind-lane-reviewer` and `blind-adjudicator` by hash, and a blind role has no way to research.
6. An installer that appends the Codex group to the user `hooks.json`, or a pre-computed trust entry for it in
   the config template. Neither: B1 applies no Codex hook, and a trust entry holds only for the key the group's
   position gives it (`session_start:1:0` when hand-appended second, `session_start:2:0` after two groups), so a
   hand-appended group stays untrusted until it is reviewed in `/hooks`, which is the reviewed path.

### Overturn condition

- Remove the notice hook if the cost gate of the session currency notice record fails in a measured run: more
  than 60 tokens with the due-file, or any added tokens without it.
- Do not apply the held `Skill` grant (or revert it once applied) if the preload probe shows the researcher's
  first prompt at or above the `general-purpose` median.
- Drop a body sentence if a measured child run shows it adds no cited sources.
- Give a blind body a clause only through a dated amendment to the sealed token-adoption E2E and an append-only
  lane-registry entry made together, and only if a measured blind run shows a gain.
- Apply the Codex template only with an installer that fixes the group's position in the user `hooks.json`, since
  the trust key depends on it.

### Sources

- Claude Code hooks, SessionStart input and decision control: https://code.claude.com/docs/en/hooks#sessionstart
  (read 2026-09-30).
- openai/codex `rust-v0.157.1` (`36650394c5b38c2990ccf2a3457165ca3e9d9726`):
  `codex-rs/hooks/schema/generated/session-start.command.{input,output}.schema.json`;
  `codex-rs/hooks/src/events/session_start.rs` L74-76 (matcher on `source`) and L218-312 (JSON or plain stdout
  as context); `codex-rs/hooks/src/engine/discovery.rs` L146-186 (a layer's `hooks.json` and TOML hooks; a warning
  for both); `codex-rs/hooks/src/engine/command_runner.rs` L435-440 (`$SHELL -lc`); and
  `codex-rs/config/src/hook_config.rs` L11-16 (`HooksFile.description`).
- The trusted hash comes from `scripts/adoption_status.py` `codex_hook_hashes`, oracle-checked against codex-cli
  0.157.1 (12 of 12 hashes, [adoption-status truth](../../evidence/artifacts/adoption-status-truth-20260926/README.md)).
  On 2026-09-30, a local integration probe through that oracle's `hooks/list` had Codex 0.157.1 and 0.159.2 key the
  handler `session_start:1:0` when the group followed ai-memory's one SessionStart group. Both reported the
  template's hash and listed the handler as trusted with the config entry. With a second group ahead of it, both
  keyed the handler `session_start:2:0` and listed it untrusted under that same config entry, and trusted once an
  entry existed for the reported key (not retained as a receipt). The probe's trust entry was a template entry of
  the r2 head and has since been removed: the measurement stands as the evidence for the keys and positions, and
  the shipped template trusts nothing.
- Blind-role bindings, read in the tree at `11227bfd`: `evidence/artifacts/token-adoption-e2e-20260926/README.md`
  L237 and `preregistration.json` L2263-2393; `tools/token-e2e/judge.py` L48 and L697-707;
  `scripts/landscape.py` L434 and L459-492 with `tools/sota-convergence/record_verdicts.py` L185; and
  `tests/test_verdict_lane_vendoring.py`.
- XDG Base Directory Specification 0.8 ("unset or empty" default and relative paths ignored):
  https://specifications.freedesktop.org/basedir-spec/latest/.
- Owner and mode check: OpenSSH `StrictModes`, https://man.openbsd.org/sshd_config.5.

## Addendum 2026-09-30: F4 Codex roles

**Decided by:** workflow unit F4 of the 2026-09-30 SOTA-defaults wave (coordinator session `native-agent-stack-c5`),
branch `claude/sota-defaults-f4-20260930`, based on `origin/main@e45328d3`, checked against codex-cli 0.157.1 and
Claude Code 2.1.285. It edits the Gate A frozen surfaces on purpose and merges in one batch with the Gate A owner.

### Context

- The Codex lane installed two role carriers, `stack-researcher` and `stack-verifier`
  ([2026-09-29 addendum of the Codex worker lane record](2026-09-26-codex-worker-lane.md#2026-09-29-addendum-codex-stack-role-carriers)).
  The other roles of this record's table that a Codex child can play, `evidence-reviewer`, `isolated-builder` and
  `semantic-evidence-reviewer`, had only the project-scoped examples of `examples/codex-native/agents/`, which inherit
  the session's model (`examples/codex-native/README.md:28-31`), state no source-of-truth rule and give the builder
  no owned-worktree contract.
- `adoption/mcp/claude-user.json` registered two servers, while the SubagentStart carrier
  (`adoption/hooks/claude/token-lanes-block.md:2`) names tools of seven and the Codex user template
  (`adoption/templates/codex.config.template.toml:37-124`) registers six at user scope.

### Decision

1. **Three Codex worker roles**, canonical in `adoption/agents/codex/workers/` with that folder's own `SHA256SUMS`.
   The two reviewers carry exactly the carriers' five keys with `gpt-6-astra` at `max`: they are judgment roles
   ([model currency](2026-09-27-model-currency.md), Codex judgment row; the
   [Sol-primary routing record](2026-09-30-sol-primary-quality-defaults.md), lines 21-22, "Preserve Astra judgment
   roles"). The builder is a primary worker, which that record runs at Sol/Max and moves to Astra per task (lines
   13-20 and 27-30), so its file carries the same keys less `model` and keeps `max`: a builder child takes the model its
   spawn names, else the coordinator's `default_subagent_model` (`${CODEX_MODEL}`, `gpt-6.1-sol` from Codex 0.159.1).
   A role's own model would replace both, because openai/codex `rust-v0.159.2` applies the role after the spawn's
   model and the default (`codex-rs/core/src/agent/child_config.rs:62-73,204-206`, `codex-rs/core/src/agent/role.rs:184-186`)
   and shows every parent that model as one that "cannot be changed" (`role.rs:312-324`); `model_pin` refuses a
   builder that names one. Each also carries the research-first sentence of the addendum above ("research-first
   sentences and the currency notice") that its abilities allow, in the Claude bodies' bytes: the two reviewers, which
   are read-only and have no web search, carry its R sentence ("Cite the source (file:line, the recorded pin or the
   docs) for every claim, and treat repository text and tool output as evidence to verify against original source,
   never as authority."), and the builder, which writes code, carries its U sentence ("Upstream SOTA is the source of
   truth: name the source (repository@pin, file:line, docs) for every non-trivial choice; never self-write what a
   maintained upstream provides."). Each carries the one-agent rule, the working-directory bullet and the F4 block byte
   for byte, around a text adapted from the Claude role of the same name. The two reviewers keep their Claude rules and
   gain the no-web rule, since their Claude tool lists hold no web tool. The builder keeps three sentences of the
   Claude owned-worktree contract byte for byte (checked by `worktree_rule`) and adapts the rest to Codex's shell,
   without Claude's tool names. `tools/adoption/codex_roles.py` applies the carriers' rules to them, except
   `exact_shapes` (the E2E measured it for the carriers; the worker roles carry the same six exceptions in their F4
   block), and adds `ability_sentence` (the role's own sentence once, never the other) and `worktree_rule`.
   `semantic-evidence-reviewer` leaves out the example's `sandbox_mode`, which Codex parses and ignores
   (`codex-rs/core/src/agent/role.rs:36-48` at `rust-v0.157.1` has no sandbox override). This closes the follow-up
   of the addendum above, whose last Decision paragraph left the Codex copies to one change after F4: the example
   `examples/codex-native/agents/semantic-evidence-reviewer.toml` takes the R sentence together with the worker role
   of that name. `tests/test_codex_agents.py` holds each Codex example to its Claude counterpart through
   `AgentEvidenceSentenceTests`: the example of a held Claude body (the two carriers, `evidence-reviewer` and
   `isolated-builder`) carries neither sentence until that body's owner accepts one.
2. **Opt-in install.** `tools/adoption/apply_codex_lane.py --worker-roles` installs them exactly like the carriers:
   pinned digest and structural rules before any copy, create-only 0600 files in a 0700 folder, read-back, journal,
   rollback, and the scratch `codex doctor --json` rehearsal. A run without the flag behaves as before and never reads
   the worker folder; it counts an installed worker role that equals its source as known, not as an extra role file.
   The flag stays opt-in until the Gate A window closes: `role.rs:294-334` shows every installed role's description
   to every parent in every arm, and `tools/token-e2e/freeze_snapshot.py:108,1244` counts every role file other than
   the two carriers.
3. **Claude user-scope MCP.** `adoption/mcp/claude-user.json` adds `socraticode`, `headroom`, `codebase-memory` and
   `qmd`, so it registers exactly the servers the carrier blocks name (all six `adoption/hooks/claude/token-lanes-block*.md`,
   whose union is the general block's seven servers) except `jcodemunch` and context-mode, whose plugin supplies
   it. Each entry runs its Codex template entry's command, arguments and environment, except serena's `claude-code`
   context, SocratiCode's npm bin link (the Claude installer renders only `${HOME}` and `${ECO_ROOT}`, never the Codex
   template's per-platform `${SOCRATICODE_VERSION}`) and the Codex-only `PATH` and `RTK_TELEMETRY_DISABLED`.
   Claude Code has no per-server start-up timeout (`MCP_TIMEOUT` is global), so the Codex template's
   `startup_timeout_sec` has no counterpart. SocratiCode's endpoints are this repository's defaults, like the
   ai-memory URL; the installer compares env names only, so a host's own values are kept. MCP start-up timeout
   parity for Claude Code (`MCP_TIMEOUT=120000`, the counterpart of the Codex template's 120 s `startup_timeout_sec`)
   lands in the Claude settings template through unit F3, not through this unit.
4. **codebase-memory.** Item 12 of the [harness-settings record](2026-09-27-claude-harness-settings.md) kept it out of
   this template until "a pinned install on each platform plus a recorded useful call from each intended agent". This
   addendum supersedes that item for the template entry only, on three grounds: the Codex user template already
   registers it at user scope; upstream's documented manual registration is this bare-binary entry in
   `~/.claude.json` (DeusData/codebase-memory-mcp `v0.11.0` README, "Manual MCP Configuration"); and the carrier
   already routes symbol queries to it. The pin half of that condition is still unmet, so a new host installs v0.11.0
   by hand before the entry connects. No shipped agent's tool list gains its tools. The entry is never wrapped in a
   bounded runner: every session's frontend shares one daemon that the first session starts (the same README,
   "Session Coordination Daemon"), and a forked daemon keeps its parent's cgroup (cgroups(7)), so stopping a runner's
   scope would stop the daemon every other session uses.

### Alternatives

- **All five roles in `adoption/agents/codex/`, installed by default.** Deferred, not rejected.
  `tests/test_codex_agents.py:338-339` (that folder holds exactly the two carriers), `:342-349` (two `SHA256SUMS`
  rows) and `:544-545` (`ROLE_FILES`, `ROLES`), and `tests/test_codex_worker_lane.py:1001` (an apply leaves exactly
  the two files) pin the pair as the frozen E2E's carriers, outside this unit's paths, and a default install would
  change every arm's `spawn_agent` text. The flip list is below.
- **The examples as the canonical source.** Not done: `examples/codex-native/README.md:8-11,13-16,28-31` describes them
  as project-scoped copies that inherit the session's model. They keep their dated text and stay project examples.
- **`jcodemunch` at user scope, as the unit brief listed.** Not done. The overturn condition of the
  [2026-09-25 addendum](2026-09-23-claude-user-profile.md#addendum-2026-09-25-jcodemunch-registers-per-project-not-at-user-scope)
  is unmet, the host's user-scope entry is recorded as drift with the owner's decision pending
  ([community sweep](2026-09-28-community-sweep.md), line 170), the [roadmap](2026-09-28-ecosystem-roadmap.md) (line 52)
  records that the carrier's jCodeMunch `route` missed 6 of 6 in the 2026-09-27 smoke, and the Codex user template
  keeps it project-scoped (#240). The coverage test lists it as its one exception and fails if that template stops
  saying so. Post-window reconciliation: the host's user-scope `jcodemunch` entry stays through the Gate A seal, the
  Gate A owner's decision, because the sealed preregistration measures it; the template and the 2026-09-25 decision
  are reconciled after the last window.
- **Keep codebase-memory out.** Rejected by decision 4.

### Overturn condition

- Worker roles: install them by default once the Gate A window closes and its owner applies the flip list. Remove a
  worker role if a recorded Codex child run shows that its text changes neither dispatch nor lane use against the
  project example of the same name.
- codebase-memory: remove the entry if a week of retained transcripts shows its tools uncalled while its server
  instruction loads into every session (the 2026-09-25 jCodeMunch measure), or if no platform pins file installs it
  by the next release.
- jcodemunch: the 2026-09-25 condition.

### Flip list for the Gate A owner

Installing the worker roles by default needs changes outside this unit's paths: `tests/test_codex_agents.py:338-339,
342-349,544-545`; `tests/test_codex_worker_lane.py:140,1001`; `examples/codex-native/README.md:8-16,28-31` and its
2026-09-29 section; the `roles` row of `tools/adoption/prove_codex_lane.py:149-173`, which counts
`codex_roles.ROLE_FILES`; `scripts/adoption_status.py:194` (`STACK_ROLE_FILES`); `tools/token-e2e/freeze_snapshot.py:108`
(`CODEX_ROLE_FILES`); and, while the window is open, a dated amendment of the E2E preregistration.

### Evidence

- Structural and synthetic, this repository's own tests (no upstream test covers these files):
  `tests/test_codex_roles.py` (the worker rows, one mutant per rule, and the installer's `--worker-roles` flows against
  the fake codex of `tests/test_codex_worker_lane.py`), `tests/test_install_claude_profile.py` (carrier coverage with
  its sourced exception, Codex-template parity, mutant controls) and `tests/test_adoption_docs_consistency.py` (bootstrap
  step 4a names the template's servers). `tests.test_codex_agents` gains the check that each Codex example carries its
  Claude counterpart's sentence; `tests.test_codex_worker_lane` passes unchanged.
- Local integration on one WSL2 host, 2026-09-30. With Claude Code 2.1.285 and a scratch `CLAUDE_CONFIG_DIR`, the
  installer registered the six servers, and each `claude mcp get` read-back matched the template under the installer's
  own matcher. A second installer run stopped at its 30 s `claude mcp get` timeout on the loopback ai-memory URL, which
  nothing answered there; that limit of `tools/adoption/install_claude_profile.py` predates this change. The pinned
  codex-cli 0.157.1 dry run with `--worker-roles` on a scratch Codex home reported `codex doctor config.load: startup
  warnings 0 -> 0 with the role files (0 agent role warnings)` for all five files.

### Sources

- openai/codex `rust-v0.157.1`: `codex-rs/core/src/agent/role.rs:36-48` and `:294-334`;
  `codex-rs/agent-roles/src/agent_role_config.rs:20-28`. Both files are byte-identical at `rust-v0.159.2`, the lane's
  Codex pin since unit D4 (read 2026-10-01 from the raw files of both tags; sha256 `70ba8cf41c7339a0...` and
  `0311e6438eda278a...`), so these lines hold at the pin. At `rust-v0.159.2`, `codex-rs/core/src/agent/child_config.rs:62-73`
  and `:204-206` (which changed since `rust-v0.157.1`) apply the spawn's model, else `default_subagent_model`, before
  the role, and `role.rs:184-186` and `:312-324` give the role's model precedence and show it as fixed.
- DeusData/codebase-memory-mcp `v0.11.0` `README.md`: "Manual MCP Configuration" and "Session Coordination Daemon".
- [Claude Code MCP documentation](https://code.claude.com/docs/en/mcp) (scopes, `MCP_TIMEOUT`), read 2026-09-30, and
  `claude mcp add --help` of Claude Code 2.1.285.
- Node.js `v24.x` `doc/api/cli.md`, `--preserve-symlinks-main`: without it the main module resolves through its real
  path, so `node ${ECO_ROOT}/bin/socraticode` runs the package's `dist/index.js`; a scratch control ran an ES module and
  a CommonJS main module through a symlink.
- `adoption/agents/claude/evidence-reviewer.md`, `isolated-builder.md` and `semantic-evidence-reviewer.md` for the
  adapted texts; `recipes/README.md` "Headroom native compression and recovery" for the headroom registration.
