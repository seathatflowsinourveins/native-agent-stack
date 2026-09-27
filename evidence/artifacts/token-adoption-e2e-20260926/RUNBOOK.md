# Measurement runbook — PR-H

**Prospective only. Do not run the E2E from this PR.** Follow
[README.md](README.md) after it and its dependency gates have
merged. This file freezes collection and interpretation; no command below is
a claim that a model, capability probe or telemetry query has run.

## Freeze and preflight — AA §7, §8.1, §8.4 steps 1–2

Record the merged preregistration commit, its merge/start chronology, hashes of
all frozen files and fixtures, actual execution checkout revision, tool
versions/pins, agent/profile/skill bytes, settings truthiness and Q1's strict
process. Record the actual identity table with the format
`<run>.<arm>.<task>.<attempt>`; keep native session/workflow/thread/call IDs and
host paths private. Freeze task input bindings before capability probes:
source receipts, original source revision, private task-output directories,
isolated builder worktrees, the exact revision each prepared Workflow worktree
was created at (`worktree_bases`) and two different per-tree sentinels. Do not
replace missing retained source bytes with a convenient new fixture after a run.
The two reused history tasks require the original retained 150-entry report.
The two reused table tasks require the pointer value from the preregistration
commit, not the execution checkout. Extract
`/summary/needs_host/macos-arm64` from the committed
`catalogs/landscape/component-evidence-matrix.json`, serialize with Python
`json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))`
as UTF-8 with no trailing newline, and retain those exact bytes at the neutral
`<retained-input>` path. Verify the JSON's `frozen_input` SHA256, 6,552-byte
length and 60-record count before probes and again before grading. Use the
same bytes in every arm. Missing bytes or a mismatch blocks launch.
The two reused command-fidelity tasks require recovery of the original six
observation command identities, whose receipt fields are truncated; the frozen
test target is `tests.test_host_requests`. Their checker compares newest commit
subject, test count and result status against exact originals. Missing inputs
block launch before probes. A changed information need requires a merged
protocol amendment, not an operator-selected replacement.

The four merge gates are #376, the unfinished Codex profile/checkpoint,
#364 **with preservation fixes**, and PR-A. **Dated update, after this
preregistration's own repair round:** #376 and #364 have both since merged
(`623d34fa`, `c71d66d0`); #376's remaining gate is a host install/read-back
proof, not the merge itself, and #364's field-preservation gap
(`workflow.run_id`/`tool_use_id` still absent from `collector.yaml`) persists
after its merge. See the preregistration for full, current statuses.
**Dated scope note, 2026-09-26:** AA §6's `baseline.json` is deferred to PR-A's
remaining scope (full-save §5 step 4); do not fabricate it or silently treat it
as supplied. #369 is a **pre-fix reference baseline only**. PR-A's
all-carrier M3/M5, nested fetches, all-hook context, call-state and token
extensions are not supplied by this PR.

**Amendment 2 (2026-09-27), role definitions and load order.** #402 (`d022295a`,
merged 2026-09-27T14:04:25Z) supplies the `stack-verifier`, `isolated-builder`
and `source-scout` bodies and joins #376's host install/read-back gate. At an
execution checkout at or after `d022295a`, the project-scope `.claude/agents/*.md`
definitions shadow the user-scope `~/.claude/agents/*.md` definitions of the same
name ([sub-agents](https://code.claude.com/docs/en/sub-agents), “Choose the
subagent scope”: project priority 3 outranks user priority 4; only managed
settings and the `--agents` flag rank higher, and the launches below pass no
`--agents`). For every `adoption/agents/claude/*.md` at the execution HEAD, the
freeze record retains the SHA256 of that file and of its same-named
`.claude/agents/` and `~/.claude/agents/` copies, read back from disk after
installation, and requires all three to be byte-identical. A missing copy or any
difference blocks capability probes and launch. **Repair round (2026-09-27):**
for the five role bodies in README's Amendment 2 role-body table
(`stack-verifier`, `isolated-builder`, `source-scout`, `stack-researcher` and
`evidence-reviewer`), all three copies must also equal the SHA256 recorded there
for `d022295a`; byte identity at the execution HEAD alone does not suffice. A
differing body blocks capability probes and launch, and any later change to
these bodies requires another dated amendment before execution. Child
`meta.json` types are still observed separately (README dependency table).

Use these shell variables as **operator inputs**, with real values recorded
privately: `E2E_DIR` (owned private output directory), `RUN_TOKEN`,
`SINCE`/`UNTIL` (UTC ISO timestamps, half-open run window),
`CLAUDE_ROOT` (projects transcript root), `CODEX_SESSIONS` (rollout root),
`CLAUDE_B_DIR`/`CLAUDE_A_DIR`/`CLAUDE_A0_DIR` (actual workflow transcript
directories), and `WF_B`/`WF_A`/`WF_A0` (observed workflow IDs).
These variable names are runbook inputs, not new CLI flags. Use the main
checkout as the dedicated headless coordinator's cwd (AA §8.1).

Before starting that process:

```sh
test -z "${CLAUDE_CODE_EFFORT_LEVEL+x}"
export RTK_DB_PATH="${E2E_DIR}/rtk.db"
export OTEL_RESOURCE_ATTRIBUTES="ecosystem.task.id=${RUN_TOKEN}"
```

Stop if the first check fails; the coordinator environment must leave
`CLAUDE_CODE_EFFORT_LEVEL` unset. Do not set it to xhigh or max, and do not
modify it in the workflow. The coordinator uses Ultracode/xhigh, while every
child explicitly requests max ([AGENTS.md](../../../AGENTS.md), Workers).
AA §7 is the source of the two exported run variables. This resource tag's
propagation to in-process Workflow children is **[nv until reconciliation]**.
Claude withholds `OTEL_*` from subprocesses; it does not automatically tag
a Codex worker launched through a shell.

If selected and the collector accepts traces, AA §8.1 permits process-local
`CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` and `OTEL_TRACES_EXPORTER=otlp`.
Do not infer exact child attribution from logs alone. Native transcripts and
the qualified call-ID join remain authoritative (AA D5/§7).

## Three accounting views — full-save §4.0

**Three views, never summed:**

1. Execution: what ran, per child, worker, role and tool.
2. Tool-reported savings: each tool's own counter at its own scope, taken as a
   window delta.
3. Provider usage and its priced token estimate: the whole task, with failures,
   retries and interrupted attempts included. It is never labelled billed cost.

**“Every baseline states its tool, window and denominator. Numbers with
different denominators are neither compared nor added.”** Unknown is not zero.
A host/session counter is never labelled per child. Exact o200k comparison
through `token_manifest.py compare` is the only artifact reduction claim
(full-save §4.0). Tool estimates, artifact comparisons and provider usage remain
separate tables in the receipt, even when they concern the same task.

Window labels used below:

- **W0:** #369's historical baseline,
  `[2026-09-25T17:18:00Z, 2026-09-26T15:05:00Z)`.
- **WAA:** AA §1's separate historical window,
  `[2026-09-26T00:00Z, 2026-09-26T18:37Z)`.
- **W:** this future run's recorded `[SINCE, UNTIL)`, separately partitioned by
  actual arm identity and task/attempt.
- **S:** a before/after native-counter snapshot pair bracketing W at one
  unchanged native scope.

W0 and WAA are different baselines; neither is a new organic run.

## Counter snapshots — AA §7; full-save §4.4

Set `SNAPSHOT` to `before` for step 2; repeat the same calls with
`SNAPSHOT=after` only after execution and flushing. Capture raw returns and
exit status privately, with timestamps and hashes. These are upstream flags
verified from installed help; gain has no ISO-window flags, and discover's
`--since` means a number of days, not an ISO timestamp.

```sh
rtk gain --all --format json > "${E2E_DIR}/rtk-gain-${SNAPSHOT}.json"
rtk gain --project --format json > "${E2E_DIR}/rtk-project-${SNAPSHOT}.json"
rtk gain --history > "${E2E_DIR}/rtk-history-${SNAPSHOT}.txt"
rtk discover --format json > "${E2E_DIR}/rtk-discover-${SNAPSHOT}.json"
headroom savings --json > "${E2E_DIR}/headroom-${SNAPSHOT}.json"
```

Sources: AA §5/§7; full-save §4.4;
[handbook lines 271–283](../../../docs/token-session-handbook.md);
`rtk gain --help`, `rtk discover --help` (installed help, read 2026-09-26).
A history snapshot may contain private commands; never commit it. Preserve a
consistent read-only SQLite backup of the isolated `RTK_DB_PATH` for the
`hook_decisions` join. The native `commands` table has no `tool_use_id`.
Do not relabel discover's broader scan as a W-only counter. If a Codex sandbox
cannot write history, use its rollout for coverage and report history unknown.

Take the following MCP returns in the **same connected process/session** before
and after; a new bridge process is not that session's “after” snapshot.
Record reset/restart/scope changes and refuse a delta across them.

| Tool / exact counter | Window | Native scope / denominator | Interpretation |
| --- | --- | --- | --- |
| RTK gain/history above | S; isolated run DB | Commands tracked in that DB; project is a subset | Estimated input/output/saved counts; do not add host and project totals |
| context-mode `ctx_stats({})` | S | Connected session/project; children share the parent | Estimates, not provider usage; not per-child |
| headroom `headroom_stats`, `headroom savings --json` | S | MCP instance and separate ledger; ledger “lifetime” is retention bounded | Separate views; unknown-model pricing and pricing-era caveat |
| jcodemunch `order({"action":"get_session_stats","args":{}})`; per-call `_meta.tokens_saved` | S / actual calls in W | Same MCP session; separate retained ledger | Estimates; no sum of per-call and cumulative overlapping values |
| TOON `--stats` and strict decode | Each selected payload in W | That encode/decode pair and exact original | Estimate plus independently checked equality |
| Repomix pack summary | Each selected pack in W | The explicitly selected files/pack | Token counts, not savings |
| QMD `qmd --index native-agent-stack-catalog status` | S | That named index/collections | State, no savings counter |
| ai-memory `memory_status` | S | Explicit `workspace="local", project="native-agent-stack"` | Operations/observations, no savings counter; AA §5/§9.2 |
| SocratiCode `codebase_status` | S | Explicit indexed project | State, no savings counter |
| Serena dashboard/logs | S | Client's bound project/server | No savings counter (AA §5) |
| codebase-memory | S only after Q3 | Qualified disposable-clone graph | Blocked until Q3; counters cannot show savings |
| MCPorter daemon call log, if B5 selected | W | Logged keep-alive downstream calls | Attribute downstream operation to its server; ad hoc calls stay unknown |
| ccusage daily JSON below | Explicit calendar dates overlapping W | Selected client's host logs | Usage, not per-task savings or billed cost |
| gpt-tokenizer via `token_manifest.py compare` | One frozen artifact pair | Exact original vs selected output | Only exact artifact reduction measure |
| Prometheus / published native-data counters | W or S, explicitly labelled | Process/host aggregates | Never per child; Prometheus invalid until G1's reset/identity proof |

Retain no cross-tool total. AA §7's Grafana/Loki live view is an observation
of events, not another quantity to add to usage. Native-data publication
readiness does not establish per-child attribution.

## Capability qualification and launch — AA §8.1b, §8.2, §8.4 step 3

For every eligible role/tool pair, perform two discriminating fixtures three
times each, checking the executed call, successful result and an own-tree
sentinel. Require 100% where capability exists. A disabled server and a
wrong-root binding must fail. Archive these as capability evidence, excluded
from organic task counts. For plugin tools, AA §8.1b's optional native harness
is `claude plugin eval` with `--mocks off` and
`--allow-tools "mcp__plugin_context-mode_context-mode__*"`; a real returned
sentinel is required. `--allow-real-servers` alone may still use mocks.
QMD is user-scoped and is not covered by that plugin harness.

**Amendment 2 repair round (2026-09-27), builder brief.** The B-route
`isolated-builder` probe must use exactly the frozen brief shape: the prepared
path plus `<assigned-base>`, worded as the builder tasks' clause “the prepared
control checkout `<assigned-worktree>`, prepared at the exact base
`<assigned-base>`”. The probe binds its own prepared tree's absolute path and
the full 40-hex revision that tree was created at, the way `worktree_paths` and
`worktree_bases` bind them, and no other base text. A probe with other base
wording, an abbreviated base or added base instructions does not qualify the
route. A refusal on this shape is a retained gate failure, never repaired by
rewording the brief.

Run the M13 binding probe in two concurrent owned worktrees, 20 repetitions
per worktree, covering shell, cwd-less execution, relative file read,
index/search and the granted symbol service. Also test spawned children.
An own-tree sentinel establishes the binding; a printed cwd does not.
Run the scratch Agent-tool blind contamination probe outside any verdict wave.
No capability output counts toward the five organic opportunities.

### Claude Workflow runs

Use `claude -p` with the native Workflow tool, once per arm **B → A → A0**.
The exact supported CLI shell form is:

```sh
claude --effort ultracode -p "${COORDINATOR_REQUEST}"
```

`COORDINATOR_REQUEST` explicitly asks the coordinator to invoke Workflow with
`scriptPath=evidence/artifacts/token-adoption-e2e-20260926/token-e2e-run.mjs`
(kept beside this runbook and the preregistration, not under
`examples/claude-native/workflows/` — see README.md's integrator correction;
`scriptPath` accepts any committed path) from the merged preregistration and
the following native `args` object. Supplying the keyword alone to `-p` is
not enough (Workflow reference, “Where the keyword works”, lines 131–141).

| args key | Value and frozen-input check |
| --- | --- |
| arm | B, then A, then A0, one Workflow call each |
| run | Private run token from the identity table |
| attempt | Initial positive integer 1; new recorded integer on retry |
| preregistration_commit | Actual merged revision whose files were checked |
| gates_verified | true only after inspecting the retained merge/read-back/capability evidence |
| frozen_tasks | Entire parsed committed `preregistration.json`, without edits |
| worktree_paths | Every selected task with `worktree_required` mapped to this arm's prepared owned absolute checkout/clone path; six distinct prepared builder paths plus per-arm command-observation checkouts and caller clones, frozen privately before probes. For builders this is the owned checkout each arm's brief names (Amendment 2, 2026-09-27), not proof of the edited tree; follow the builder section below |
| worktree_bases | Every selected task with `worktree_required` mapped to the full 40-hex revision its prepared checkout/clone was created at, recorded privately with `worktree_paths` before probes (Amendment 2 repair round, 2026-09-27). Builder trees are prepared at the frozen execution revision, which their unchanged check requires. The script replaces `<assigned-base>` with it in both builder briefs and refuses to start when a value is missing or malformed or the placeholder stays unbound. The two reused worktree tasks have no base placeholder: their value is recorded only, and their text and checks are unchanged |
| input_paths | Every selected task with `input_required` mapped to its pre-recorded neutral absolute input path; history originals, the sealed table pointer value and the HTML seed retain identical bytes/hash across arms |

The runtime cannot read files or import modules. The coordinator passes JSON
through the supported Workflow `args` input; verify its task ids, role/model,
task text, checks and denylist against the hashed committed file before launch.
The script's boolean guard is not acceptance evidence. Do not ask a model to
rewrite the task array. The native API is documented in
[WorkflowInput](https://code.claude.com/docs/en/agent-sdk/typescript#workflow);
`scriptPath` and JSON-valued `args` are tool inputs, not invented CLI flags.

The script reserves 49/43/43 child slots, sequentially, with explicit model and
max effort on every `agent()`. It never calls Codex. It logs each returned,
null or failed result; graders use the independent frozen checks, not the
child's self-assessment. Preserve native StructuredOutput retry attempts and
all their usage. The response schema and task text stay unchanged between
arms. Cache-prefix rules come from Workflow reference lines 348–355; size
guidance is advisory (lines 432–449).

`reuse-296-15` is blocked pending a qualified loopback role amendment.
`source-scout.md:11` forbids network use, and no equivalent Sonnet/max role
without added worktree isolation is evidenced in this checkout. Preserve the
information need and all arm slots. The script rejects a selected blocked task
before launching any child; a true `gates_verified` flag cannot bypass it.
A dated merged amendment must name and qualify the permitted role before any
organic arm runs. Do not weaken source-scout or silently skip the task.

Run the main and native Agent-path observations outside the script, as the
JSON's `dispatch` fields specify: one main B observation, one researcher
Agent child in B and one general-purpose Agent child in A, all matching the
frozen route. The one `dispatch: main` task stays at xhigh; every child stays
at max. Blind tasks never use the Agent tool in organic execution.

The positive control requests only the first five records of the 84,003-byte
log fixture (events 1–5, all INFO). AA §3.1 Path 2 and the inspected
context-mode v1.0.169 `hooks/core/routing.mjs:848–866` use file size, not
Read offset/limit, for the over-50,000-byte injection condition. Require the
actual Read hook row; zero remains incomplete. Include every returned result
in ordinary M3 accounting, with no control-specific exclusion.

For the six strict repeats, after Q1 qualifies the exact process (AA §3.1c):

```sh
claude --safe-mode -p --tools "Read,Glob,Grep" --model opus --effort max \
  --system-prompt-file "${BLIND_BODY}" "${BLIND_PACKET}"
```

`BLIND_BODY` is the frozen stripped role body; `BLIND_PACKET` is precisely
the corresponding frozen task text and permitted fixture binding. Q1 remains
**[nv]** until observed native auth, route, inventory/deny rules, first-prompt
purity, zero hooks and verdict parity all hold. The installed plugin must not
load. Do not switch silently to `--bare`, which changes authentication.

### Builder worktrees and hooks restoration

**Amendment 2 (2026-09-27).** Sources: `adoption/agents/claude/isolated-builder.md:3,12`
at `d022295a`, `examples/claude-native/workflows/test-envelope.mjs:418–427`, the
observed shared-configuration failure in `docs/harness-defaults.md:91`, and
[sub-agents](https://code.claude.com/docs/en/sub-agents) on the `isolation` field
and a subagent's starting directory. #402 removed the role's frontmatter worktree
isolation, which Repair 1 kept here. The builder now edits only in the
coordinator-prepared owned checkout its brief names, and refuses to edit when the
brief names none, when that checkout's top level is its starting directory's, or
when its `HEAD` is not the brief's base. No arm expects a harness-created tree.
Every builder launch in B, A and A0 carries this arm's frozen prepared path from
`worktree_paths` in its brief, where it replaces `<assigned-worktree>`, and the
child must edit there. **Repair round (2026-09-27):** the same brief names that
tree's exact base. The script replaces `<assigned-base>` with the full revision
from `worktree_bases`, recorded privately before probes when the tree was
prepared, and refuses to start without it. The role's refusal when `HEAD` is not
the brief's base is kept. A and A0 reuse the identical task text, so they
receive the same bound placeholders. Whether the Opus route proceeds on this
brief is **[nv]** until the capability gate, which uses exactly this brief
shape, observes it. A refusal is a retained failed attempt, never a reason to
change task text after seeing results.

Before each builder launch, from its prepared repository, retain the effective
origin/value and whether local values existed, including all values and exits:

```sh
git config --show-origin --get core.hooksPath
git config --local --get-all core.hooksPath
```

Exit 1 means unset for these reads; retain it. Keep this snapshot private.
After completion or failure, repeat the effective-origin check. Restore the
exact preflight repository-local value(s): remove the local key with
`git config --local --unset-all core.hooksPath`, then for each recorded
local value use `git config --local --add core.hooksPath "${HOOKS_PATH_BEFORE}"`.
If no local value existed, leave it unset so the original inherited origin
applies. An unset of an already absent key can report exit 5; verify final
state rather than masking arbitrary errors. Never write global/system config.
Re-run `git config --show-origin --get core.hooksPath` and compare
origin, value and exit with preflight. Retain any mutation and its restoration
evidence, including on failed attempts; unresolved differences stop further
builder launches. The workflow is sequential, so another builder must not
race this snapshot/restore.

For each builder identity, independently read the child's native transcript
and `meta.json`. A subagent starts in the coordinator's working directory, so
the child's session directory is not its edit location. Record the actual
edited worktree and starting revision from the transcript's edit and write
paths, the directories its commands ran in, its revision reads and available
metadata, joined by child identity. Do not invent a metadata field or accept
the child's final answer alone as proof. If metadata does not record the tree,
its identity must join to transcript observations that do. The observed edit
tree must be the frozen prepared path for this arm and task, with every edited
or written file inside it; any other tree, including a harness-created one, is
a conflicting identity. Require the starting revision and fixture bytes to
match the frozen execution inputs. Missing or conflicting evidence blocks
grading.

Run the independent tracked **and untracked** diff/checks in that observed tree
against its recorded starting revision. Only `fixtures/before.py`
may change; compare its final bytes to `fixtures/after.py` in the same
tree, and retain the actual Ada/Grace test output. An empty diff from the
prepared tree cannot pass. The same read-back and revision checks apply in every
arm. The script's `worktreeEvidence.actual_path: null` means pending independent
read-back, never the supplied path by default. The freeze section's two
per-tree sentinels and the capability gate's own-tree sentinel checks are
unchanged. Retain that tree until independent grading and patch capture finish,
then clean up only the owned tree through the native lifecycle.

### Codex launches (separate shell step)

The pending carrier's actual header, `adoption/templates/codex.stack-worker.config.toml:3`
at the supplied local checkpoint, specifies:

```text
codex exec -p stack-worker -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" -s <sandbox> ...
```

Its local branch is `claude/codex-lane-token-stack-20260926`, checkpoint
`a6ed3c57`: unpushed, unmerged, with recorded cleanup/verdict/README defects.
This runbook does not accept it. Once those gates are resolved, this is B's
expanded command shape (AA §7/§8.1/§8.7):

```sh
codex exec -p stack-worker -m gpt-6-astra \
  -c model_reasoning_effort='"max"' -c web_search='"live"' \
  -c "otel.environment=\"${IDENTITY}\"" \
  -s "${SANDBOX}" -C "${TASK_CWD}" --json "${TASK_TEXT}" \
  < /dev/null > "${E2E_DIR}/${IDENTITY}.events.jsonl" \
  2> "${E2E_DIR}/${IDENTITY}.err"
```

`TASK_TEXT` is the JSON `task_text` with only its declared neutral placeholders
bound: `<assigned-worktree>` to the frozen owned checkout/clone,
`<retained-input>` to the retained source pathname, and `<run-token>` to
`RUN_TOKEN`. Apply the same bindings in the Workflow args above. No Codex task
text carries `<assigned-base>`; only the Workflow builder briefs bind it, from
`worktree_bases`. Check resolved
prompts against the JSON denylist; no receipt commands, tool names or lane
guidance are appended. `IDENTITY` follows the frozen format.
Record the actual exit status, start/end and `thread.started` ID separately.
A uses the identical command **with the `-p stack-worker` pair removed**,
retaining user config and all explicit route/identity settings.

N adds `--ignore-user-config -c features.hooks=false -c features.plugins=false`
to A and supplies the previously frozen native exporter configuration through
its supported per-launch `-c` entries. Do not invent exporter keys or assume
they survive ignored user config. Qualify those exact entries at the telemetry
gate. Q2's candidate isolated client home and repository-external fixture must
pass prompt-input plus rollout read-back before N can be called guidance-free.
Its native auth link stays private; never copy an authentication store.
Until Q2 passes, report config-free N and compare M6c B with A (AA §3.2).

For each arm launch one worker for each of its 20 exec tasks, in manifest
order, at most two concurrent owned worktrees. Each launch retains its own
identity. B's five child cases are `fork_turns` none, 2 and all with the
researcher role, all without a role, and a resumed finished researcher child.
A repeats `seed-binding-1` (none with its existing researcher role, explicitly
retained by repair 1) and `seed-binding-4` (all with no role/agent_type). This
retained none case is an explicit exception to AA §8.2's no-role wording.
Retain actual spawn/resume arguments,
role TOML hash, own-rollout start boundary, model, effort and source binding.
Do not count replayed parent history as the child's calls or usage.
Compaction remains untested if absent (AA §8.2/§10).

The `source-scout` and `evidence-reviewer` role lanes are Claude-only (AA §6:372).
Their shared Codex information needs remain exec tasks under the selected arm
profile, with `role: null` and explicit Claude provenance. Do not dispatch a
Codex agent by either nonexistent role name. The only Codex custom carriers
specified by AA are `stack-researcher` and `stack-verifier`.

## Transcript measurement — AA §8.4 step 5

These flags were verified against the **actual parsers**, not inferred:

- [child-usage.mjs](../../../examples/claude-native/workflows/child-usage.mjs):
  usage lines 596–597; parser lines 599–627. Lines 622–626 reject combining
  `--require-effort` with a sweep, and require sweep mode for time/root flags.
- [skill_usage.py](../../../tools/skill-usage/skill_usage.py):
  `--claude-skill-doctor` 1095–1098, `--codex-root` 1105–1107,
  `--now` 1110–1111, `--json`/`--out` 1115–1118,
  lane flags 1120–1129. `--out` refuses paths inside this checkout.

Run each effort check on one actual arm directory:

```sh
node examples/claude-native/workflows/child-usage.mjs "${CLAUDE_B_DIR}" --require-effort max
node examples/claude-native/workflows/child-usage.mjs "${CLAUDE_A_DIR}" --require-effort max
node examples/claude-native/workflows/child-usage.mjs "${CLAUDE_A0_DIR}" --require-effort max
```

Capture each full return, stderr and exit status privately. Then collect the
same fixed-window forms used by #369's Method:

```sh
node examples/claude-native/workflows/child-usage.mjs --lanes-sweep \
  --root "${CLAUDE_ROOT}" --since "${SINCE}" --until "${UNTIL}" \
  --rtk-db "${RTK_DB_PATH}" --marker '<context_window_protection>' \
  > "${E2E_DIR}/claude-lanes.json"

python3 tools/skill-usage/skill_usage.py --lanes \
  --codex-root "${CODEX_SESSIONS}" --since "${SINCE}" --until "${UNTIL}" \
  --marker '<context_window_protection>' --now "${UNTIL}" --json \
  --out "${E2E_DIR}/codex-lanes.json"
```

`--now` is the reference instant; it does not replace `--since/--until`.
For a separately captured skills-invoke view, reuse a native doctor capture:

```sh
python3 tools/skill-usage/skill_usage.py \
  --claude-skill-doctor "${SKILL_DOCTOR_CAPTURE}" \
  --codex-root "${CODEX_SESSIONS}" --now "${UNTIL}" --json \
  --out "${E2E_DIR}/skill-invoke-rate.json"
```

That doctor view is not windowed by W and must not be relabelled an organic
lane rate. #369 pinned its separate capture instant to
`2026-09-26T17:07:04Z`; it did not use W0 for that view.

The historical parsers count deduplicated calls at their first record in the
window. Child rewrites count at the hook row; the RTK join matches
`hook_decisions` 1:1 by `tool_use_id`. Codex own calls exclude inherited
history. Compare matching types/paths, retain history-mode gaps, and preserve
boundary-straddling attempts. Historical baseline fetch classification
excludes nested fetches, and its context detection is not the all-hook M12
counter. PR-A must supply those measurements before acceptance. Sources:
[#369 Method and Limitations](../../../evidence/artifacts/child-lane-baseline-20260926/README.md),
lines 29–80 and 192–222; AA §6 PR-A/§7.

## Loki queries and reconciliation — AA §7, §8.4 steps 6–7

**Check delivery and exporter flushes before querying.** Missing events are
unknown; an empty query does not demonstrate zero calls. #364 is open.
At its inspected head `8e6613488f8ff4a50a6c4c4867bee563aca856e7`,
[collector.yaml lines 78 and 91](https://github.com/seathatflowsinourveins/native-agent-stack/blob/8e6613488f8ff4a50a6c4c4867bee563aca856e7/observability/collector/collector.yaml#L78)
keep `ecosystem.task.id` but omit `workflow.run_id`, `tool_use_id` and
Codex `env` (and the Codex call join needs `call_id`). Repair and prove
preservation before using these queries. A merge by itself is not proof.

Only `service.name` is an index label in
[the Loki template](../../../observability/backends/templates/ecosystem-loki.yml.example)
lines 45–52. Dots normalize to underscores, including structured metadata:
`ecosystem.task.id → ecosystem_task_id`,
`workflow.run_id → workflow_run_id`. Query the latter with pipeline filters,
not labels, and do not use `| json` on a body that the collector scrubs.
Sources: [Loki OTLP normalization](https://grafana.com/docs/loki/latest/send-data/otel/#format-considerations)
and [structured-metadata queries](https://grafana.com/docs/loki/latest/get-started/labels/structured-metadata/#querying-structured-metadata).

One distinct query per actual arm, with placeholder tokens replaced privately:

```logql
{service_name="claude-code"} | ecosystem_task_id="<run>" | workflow_run_id="<B workflow id>"
{service_name="claude-code"} | ecosystem_task_id="<run>" | workflow_run_id="<A workflow id>"
{service_name="claude-code"} | ecosystem_task_id="<run>" | workflow_run_id="<A0 workflow id>"
```

Whole-run and call-join views:

```logql
{service_name="claude-code"} | ecosystem_task_id="<run>"
{service_name="claude-code"} | ecosystem_task_id="<run>" | session_id="<session id>" | tool_use_id="<tool use id>"
{service_name="codex_exec"} | env="<run>.<arm>.<task>.<attempt>"
```

Codex's `otel.environment` is emitted as resource **`env`**, not a field
called `otel_environment`: [openai/codex rust-v0.157.1,
provider.rs:53,381](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/otel/src/provider.rs#L53).
Its end-to-end tag remains **[nv]**. Record `thread.started` as the fallback
join and verify the relationship to retained conversation/thread metadata.
Claude's workflow/tool fields are documented by the
[native monitoring reference](https://code.claude.com/docs/en/monitoring-usage).

Use the same W bounds in the native HTTP request; `LOKI_QUERY` is one of
the fully substituted queries, `LOKI_URL` the adopted loopback endpoint:

```sh
curl --fail --silent --show-error --get "${LOKI_URL}/loki/api/v1/query_range" \
  --data-urlencode "query=${LOKI_QUERY}" \
  --data-urlencode "start=${SINCE}" --data-urlencode "end=${UNTIL}" \
  --data-urlencode "direction=forward" --data-urlencode "limit=5000" \
  > "${LOKI_RESULT}"
```

Source: [Loki query_range API](https://grafana.com/docs/loki/latest/reference/loki-http-api/#query-logs-within-a-range-of-time).
Paginate capped returns using the actual last timestamp and deduplicate by
qualified call/event identity; verify W's exclusive end when reconciling.
Never treat the first page as complete or sum overlapping pages.

Reconcile attempted, decided (accept/reject), executed, failed, cancelled and
unfinished states. Rejects need `tool_decision`, not a nonexistent
`tool_result`. Join Claude session+tool-use IDs and Codex conversation+call
IDs. Require ≥99% of executed calls matched, zero duplicates, every reject
represented, and per-run counts agreeing within 2%. List unknown joins and
missing attempts, and never label a global counter per child (AA M14).

## Usage and priced estimate — full-save §4.5; AA G-C

Supplement the native transcript/rollout totals with the requested native
calendar reports. `DAY_SINCE` and `DAY_UNTIL` use `YYYYMMDD`;
`--offline` affects pricing lookup, not the run identity partition.

```sh
ccusage claude daily --json --offline --timezone UTC \
  --since "${DAY_SINCE}" --until "${DAY_UNTIL}" \
  > "${E2E_DIR}/ccusage-claude.json"
ccusage codex daily --json --offline --timezone UTC \
  --since "${DAY_SINCE}" --until "${DAY_UNTIL}" \
  > "${E2E_DIR}/ccusage-codex.json"
```

Sources: full-save §4.4/§4.5; both installed `daily --help` outputs, read
2026-09-26. `--no-cost` is a Codex flag, not asserted for Claude.
Daily host aggregates are not per-arm/task denominators. The recorded offline
pricing gaps for claude-opus-5-5 and gpt-6-luna remain limitations of the
historical pin; an unpriced model is not free.

Claude: deduplicate per-message usage by message ID, retaining ordinary input,
cache writes, cache reads and output from each child's transcript. Use
run-grouped `api_request` as an independent view only after #364's fields
are actually preserved. Codex: difference cumulative rollout `token_count`
totals per thread and attempt, excluding copied parent baseline. Do not sum
`turn.completed` cumulative thread totals. `turn.failed` has no usage and
an interrupted turn may emit neither; failed-turn `token_count` persistence
remains **[nv]** (full-save §4.5).

For each family/arm, price every attempt using the pre-run dated provider list
price for its actual model/cache tier, including failed/interrupted/retry
usage and the enclosing coordinator/launch overhead. Do not double-count
parent/child copies or cached-input/reasoning subsets. Divide each arm's total
by its tasks passing their frozen checks, then compare B/A, retaining the
matched-task breakdown as well. Include the blind/strict/control attempts
attributed to that arm; do not exclude their usage to make the guardrail pass.
Keep the separately tagged capability phase and its cost in the complete
experiment account; it never counts as an organic successful task. Record
root/coordinator attribution before the run; unresolved usage stays unknown.
A zero successful-task denominator
or missing usage yields an undefined/unknown estimate, not zero.
List-price estimates are never billed cost; report provider plan quota
separately when available. Prometheus cannot price this run until G1 passes.

## Baselines and targets with denominators

The following rows deliberately keep the two historical windows separate.
All figures are source-reported historical values, not newly executed results.

| Population / baseline | Tool / source | Window | Denominator | Retained value |
| --- | --- | --- | --- | --- |
| #369 Claude | child-usage.mjs --lanes-sweep; baseline README | W0 | 639 children: 597 Workflow, 42 Agent; 24,776 Bash calls | 8,325 rewrites; 24 not logged |
| #369 Codex | skill_usage.py --lanes; baseline README | W0 | 239 sessions: 132 workers, 107 config-free controls | Worker counted fetches 123/130 (94.6%); nested fetches absent |
| General-purpose | child-usage.mjs; AA §1.1 / full-save §4.3 | WAA, selected session | 193 children; 18,923 tool calls | MCP 356/18,923 (1.9%); MCP children 19.2%, non-ctx children 6.2%; first-prompt median 39,729 |
| Evidence-reviewer | child-usage.mjs; AA §1.1 / full-save §4.3 | WAA, selected session | 19 children; 1,349 tool calls | MCP 49.1%; MCP children 100%, non-ctx 0%; prompt median 17,721 |
| Default workflow type | child-usage.mjs; AA §1.1 / full-save §4.3 | WAA, five sessions | 460 children; 15,775 tool calls | MCP 58/15,775 (0.37%); MCP children 1.1%; two qmd children; prompt median 44,590 |
| Codex workers | skill_usage.py --lanes; AA §1.2 / full-save §4.3 | WAA | 212 sessions; 5,568 tool calls | MCP 3,005/5,568 (54%); ctx in 179 sessions; prompt median 19,392 |
| Codex sub-agents | skill_usage.py --lanes; AA §1.2 / full-save §4.3 | WAA | 28 sessions; 718 tool calls | MCP 539/718 (75.1%); ctx in 27 sessions; prompt median 22,124 |
| Loaded, never called | child-usage.mjs; AA §1.1 / full-save §4.3 | WAA, selected session | Children loading each named server | socraticode 11, serena 10, qmd 10, ai-memory 10, headroom 8 |
| All-carrier M3/M5, eligible-part M-R1, M-R3, per-child tokens | PR-A extensions | PR-A's explicitly recorded baseline window | Carrier-specific bytes/results; eligible command parts; deduplicated messages | Unknown here; pending PR-A, not replaced by #369 |
| Historical host token totals | Loki api_request; full-save §4.5(a) | Roughly 00:05Z–20:40Z on 2026-09-26 (1,235 minutes) | All host sessions/projects, grouped by query_source | Context only; not a per-task baseline |
| Historical child-token sample | full-save §4.5(b) scratch computation | Transcripts modified since 00:00Z, 2026-09-26 | 326 children; 255 complete, 71 incomplete | Not a PR-A or current-run usage receipt |

Required targets are copied from AA §8.3; `preregistration.json` carries their
structured criteria and README.md carries their complete wording. The JSON also
freezes the five-opportunity minimum, three M3 exception classes, Q1's pending
strict-blind candidate, outcome rule and overturn conditions. This table makes the operational denominator explicit.

| Metric / target | Measurement tool | Window | Denominator / comparison population |
| --- | --- | --- | --- |
| M1 ≥90% per required lane | PR-A transcript tools + frozen eligibility | W, B | Eligible child-tasks in that lane; success requires an actual non-error call |
| M2 ≥90% | PR-A transcript tools | W, B | B children excluding scout and blind |
| M2b descriptive only | PR-A transcript tools; joined Loki cross-check | W, by role | MCP attempts / all tool calls; no threshold |
| M3 median ≤1 over 5,120 B | PR-A all-carrier result measurement | W, B | Non-exception results per child |
| M3 ≤20% byte share | PR-A all-carrier result measurement | W, B | Bytes in over-5,120-B non-exception results / all non-exception result bytes |
| M3 maximum 20,480 B; B over-5-KB bytes ≤A | PR-A all-carrier result measurement | W, matched B/A tasks | Each non-exception result; total non-exception bytes over threshold on identical tasks |
| M4 ≥90%; incomplete if unclassifiable >10% | PR-A fetch classes | W, researcher and Codex B | All remote fetch operations, including nested sandbox fetches and listed unknowns |
| M5 ≤10% large results; ≤20% large-result bytes; maximum 20,480 B | PR-A ctx result measurement | W, B ctx users | All ctx result counts / bytes; each ctx result for maximum |
| M6 not_logged ≤1%; all proxy calls acceptance/exception | child-usage.mjs + isolated hook_decisions | W, Claude Bash children | Bash calls for logging; proxy calls for exception classification |
| M6c ≥90%; zero wrapped exceptions | skill_usage.py + PR-A eligibility | W, Codex B/A; N only after Q2 | Eligible shell commands; excluded commands checked separately |
| M7 seeded 100%; strict equality 100%; zero ineligible encodes | TOON CLI transcript + independent JSON equality | W, B | Seeded eligible arrays; every decode; every encoding input |
| M8 ≥80% per required lane with correct answers | Transcript/source-witness joins + frozen checks | W, granted B children | Eligible symbol, catalog or prior-decision child-tasks |
| M9 reported; under five optional opportunities N/A | Native Repomix/MarkItDown returns | W | Seeded overview/conversion tasks; no acceptance gate |
| M10 N/A; explain default-role call | Transcript tools | W, all | Headroom MCP calls, reported only |
| M11 100% | Child metadata, transcripts, prompt-input, spawn arguments | W | Every required carrier/route item on every relevant launch |
| M12 zero contamination; positive control ≥1 Read injection | PR-A all-hook counter + direct transcripts | W, blind/strict lanes | Every evidence verdict; separately the one contaminated positive control |
| M13 100% own-tree, zero wrong-root | Native returned sentinels + independent fixture comparison | Capability window plus W, separately | Every applicable tool-class repetition and organic child-task |
| M14 ≥99% matched, zero duplicates, ≤2% count difference | Transcript ↔ Loki qualified-ID reconciliation | W, by arm/client/state | Executed calls; rejected calls all represented; per-run call counts |
| M15 ≤1% infrastructure errors | PR-A MCP results + error classification | W, per server | Attempted server calls; ordinary invoked-command nonzero exits excluded from the infrastructure-error numerator |
| G-Q every B task correct, B passes ≥A | Independent frozen pass/fail checks | W, matched tasks plus reported controls | Task outcomes; no self-reported pass |
| G-C B/A ≤1.10× | Transcript/rollout usage + dated model prices | W, all arm attempts including associated overhead | Total priced attempt usage / tasks passing frozen checks, separately per family/arm |
| G-T B/A ≤1.25× | Recorded native launch/completion times | W, matched arms | B vs A elapsed wall time under identical scheduling |
| G-P researcher median below general-purpose | Native first-request usage | W, B/A | First prompts of matched researcher/general-purpose children |
| G-S zero forbidden reads/escapes | Transcript and command inspection | W, all attempts | Every credential-path read and guard-escaping execution |

Natural payload M7, SocratiCode and qualified graph observations are optional;
under-five optional lanes are reported N/A, but an unqualified graph stays
blocked. M2b is descriptive. M-R1/M-R2/M-R3 stay with PR-A; the preregistration
quotes full-save §4.6 verbatim without redefining §4.1/§4.2.

## Receipt and verdict — AA §8.4 step 8, §8.5, §8.7

Retain exact native returns, exits, timestamps, hashes, failure conditions and
the private identity table. Publish only sanitized aggregate receipts with
source pointers and scope, not raw conversations, credentials, host paths or
native IDs. Distinguish this local integration measurement from unchanged
upstream tests, capability fixtures and new model runs.

Apply every required M row and every G row. A lane below five organic
opportunities or a failed positive control is **incomplete**, never a pass;
M4's >10% unknown-fetch condition is incomplete too. Otherwise a failed gate
is fail: retain it, leave defaults unchanged, repair once and rerun under the
same frozen criteria. Optional N/A is neither a required-row pass nor a block.
Use the preregistration's exact overturn conditions.

Reviews follow AA §8.7: independent Claude evidence-reviewer (Opus/max),
then GPT-6 cross-family review of retained output, then one repair round with
residuals. All-carrier baselines, M-R1's separate seven-day window, switch
receipts and these reviews are still required by full-save §4.6 before
foundation acceptance. This file authorizes no live run during PR-H's build.
