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
excluded only `blind-*` types. Each named role received the full block with 17 tool ids, and most of those ids
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
