# Definitive SOTA WSL program: finalize every layer, then build the clean runtime (2026-10-01)

**Status:** program record, opened 2026-10-01; the per-layer gap tables are appended as the assessments land.

## Decision

The definitive runtime is a new WSL 2 distro, imported from an official upstream image and bootstrapped from this
repository at a final revision, in which each layer's selected repositories are installed cleanly with their
upstream-supported commands by an LLM-native session. Gate A's token-adoption E2E re-aims at the new distro (the
user's decision of 2026-10-01 03:33Z): the measurement host is the new distro, which collects its own evidence; the
current workstation distro's Gate A freeze is lifted and keeps whatever the production program runs there; the
production composition (Codex 0.159.3, AgentRelay
13.0.0, Relaycast 8.14.0, Hindsight 0.10.2 with the 0.8.0 coding integration, NautilusTrader 2.0.0rc5) belongs in the
new distro. Each of the 32 catalog layers is finalized before its repositories are installed there, and every install
leaves a per-layer receipt registered through the hot-file protocol (`docs/lanes.md`).

## Source of the decision

The user, 2026-10-01 ~03:20Z: finalize each layer and start the definitive SOTA WSL with the full SOTA architecture for
each layer's repositories, resolving cleanly for a new advanced runtime that culminates in the final architecture
repositories with evidence for each layer, paving the way to complex projects, system building and the north star;
~03:30Z: resolve with each repository installed cleanly with upstream commands in the new WSL by an LLM-native session.
The Gate A owner's earlier ruling A (03:17Z: measure on the current distro, revert its drift, build the new distro
after the last window) is superseded by that decision; see "Gate A re-aim". WSL 2 distros still share one virtual
machine (CPU, memory, disk and network namespace), so a window needs a load check on the shared machine.

## Closure criterion per layer

A layer is final only when every item of `catalogs/landscape/research-state.json` `saturation.close_only_when` holds:

1. a selected choice, named alternatives and recoverable primary evidence;
2. the frozen candidate and source set recorded, including failed access and explicit omitted or out-of-scope reasons;
3. the required representative comparisons and target-host lifecycle checks meet preregistered acceptance, with
   missing evidence left open;
4. a second independent review finds no unresolved material gap in that bounded set;
5. a dated closure record lists residual risks, untested boundaries and exact reopening triggers.

Evidence classes follow `docs/acceptance-evidence-policy.md`: unchanged upstream tests, local integration checks,
synthetic fixtures and live provider execution are distinct; a new host collects its own evidence, and a receipt from
the workstation never certifies the new distro. Closure is therefore staged: a layer's selection is final before its
install when items 1, 2, 4 and 5 hold and the preregistered comparisons of item 3 are done; the target-host lifecycle
checks of item 3 are collected on the new distro as the install receipt, and the layer is closed only when that receipt
is registered. Workstation receipts never substitute for them.

## Phases

| Phase | Content | Gate | Owner |
| --- | --- | --- | --- |
| 0 | Merge train (the freeze-list and lane PRs); the per-layer closure assessments start in parallel | eight required checks and the owner's script check per merge | the coordinator for the train; lane owners for their PRs |
| 1 | Per-layer closure assessment (read-only, source-cited, refuted, synthesized) for the 20 foundation and 12 us-equities layers; bounded comparisons with frozen inputs where item 3 is unmet; closure records | the criterion above, with a second independent review | foundation lane (coordinator); trading lane keeps the trading decisions and records |
| 2 | WSL import recipe (upstream image, `wsl --import` or `--install --from-file`, first boot, systemd, user services, terminal profile) researched from Microsoft and Canonical sources and recorded under `adoption/` | source-cited recipe; no host change before the last Gate A window closes | foundation lane; WSL package version stays with the keys lane |
| 3 | Import the distro (the stage-1 recipe); capture the pre-install baseline; bootstrap from a final revision (`adoption/bootstrap-linux.sh --profile <id> --configure-full-profile --host <host>`); install each layer whose selection is final (items 1, 2, 4 and 5 of the criterion, with the preregistered comparisons of item 3 done) with upstream commands, collecting the target-host lifecycle checks of item 3 as the install receipt; native sign-ins on the destination; a recoverable checkpoint before stage 2 and an owned rollback | the baseline capture, `scripts/adoption_status.py --login-shell --client-wiring --pinned-versions`, `scripts/skills_status.py`, the layer receipts, `scripts/validate.py` | the LLM-native session on the new distro, under the coordinator |
| 3b | Gate A re-aimed on the new distro: the harness pilot, the re-aim amendment, the windows, the report | the Gate A owner's gates (the preregistration, the opening rules of the Claude and Codex families, the announcement of at least six hours) | Gate A owner |
| 4 | Complex projects and system building on the new runtime (general engineering) | the convergence loop of `docs/convergence-architecture.md` per project | the foundation lane and each project's owner |
| 5 | The trading north star on the new runtime | the north star's own gates (`catalogs/us-equities/runtime-target.json`) | trading lane |

## The grand HTML: the final architecture per layer, with reasons and verdicts

The user asked (2026-10-01 ~03:43Z) for the final architecture of each layer manifested into the generated ecosystem
guide with reasons and verdicts, for the new distro's Claude and Codex clients, the SOTA GPT-6 runtime workers and
SDKs, repository hosting, the rootless Docker CLI driven through the OmniRoute gateway on GPT-6.1 Sol, the token-save
practice, the foundation, memory and RAG, and beyond. The deliverable is a dated architecture topic edition of
`docs/ecosystem/` (built by `scripts/build_ecosystem.py`; precedent: the token topic's dated per-tool cards from
`docs/token-efficiency-stack.json`): one row per catalog layer with the winner repositories and pins, the reasons
(decision rationale, convergence votes, comparisons with their evidence classes), the verdict (selected, provisional,
comparison required, new host required) and the new-WSL install commands, each statement traceable to a decision
record, a receipt or a closure assessment. Its JSON source is the new-WSL install manifest. The generated page is
published as the `publish-catalog.yml` workflow artifact and, for the user, as a private page. The Codex runtime lane's
additive runtime-workers panel in the same build is referenced, not duplicated.

## Baseline, checkpoint and rollback on the new distro

Before stage 2 the session captures the pre-install inventory (`wsl.exe --version`, the distro's package list,
`scripts/adoption_status.py --json` from the clean clone, the stage-1 receipt) and the operator exports the distro
(`wsl --export <Name> <file.tar>`, Microsoft's documented backup) as the recoverable checkpoint; every later layer
install captures `adoption_status.py --json` before and after and names the checkpoint it can return to. Rollback is
`wsl --unregister <Name>` followed by `wsl --import` of the checkpoint, owned by the coordinator; no rollback touches
the current distro.

## Ownership split

- Coordinator (SOTA-defaults lane): the merge train, the per-layer closure assessments, the WSL recipe, this record,
  the single host apply (B1) re-targeted at the new distro.
- Gate A owner: the harness pilot, Amendment 4 as the re-aim amendment, the windows on the new distro and the Gate A
  report.
- Production program: the runtime composition and its isolated package, daemon and memory qualifications; no shared
  client mutation on the current distro.
- Trading lane: the 12 us-equities layers' decisions and closure records; the paper units; the north star.
- Keys lane: credentials on the new distro (`docs/secret-storage.md`, "Setting up a new host"); the WSL package.
- Memory lane: the durable-memory selection (Hindsight 0.10.2 fit target; ai-memory scopes) and its evidence.

## Gaps recorded so far

- Release and re-pin: the pinned release `v2026.09.26.2` lacks five terminal-lane files and carries older copies of
  five others (`scripts/release_due.py` lists them), so a distro that follows the pinned release misses them.
- The Windows-side terminal steps (profile fragment, `settings.json`, the login-shell proof) are outside
  `--configure-full-profile` and form the operator checklist of the new distro.
- No evidence from a fresh distro exists yet for the terminal defaults, the bootstrap or any layer.
- Zero of the 32 layer targets were confirmed on 2026-09-28; 18 layers are `on_requirement_change`, 13
  `comparison_required`, 1 `new_host_required` as of this record.

## Per-layer gap tables

Populated from the closure-assessment workflow (foundation layers first, then the us-equities layers) when it lands.

## Gate A re-aim (decided by the user, 2026-10-01 03:33Z)

The user decided: re-aim Gate A at the new WSL, with all the SOTA runtime workers and GPT-6 framework harnesses;
manifest the final winner repositories for the new WSL clean install into the native workflow and the foundation
catalog; include the seamless passwordless LLM-native workflow and the harness-convergence practice. The Gate A
owner's ruling A of ~03:17Z is superseded: the token-adoption E2E runs on the new distro after its clean install, the
current distro's drift revert is withdrawn for Gate A's sake, and the new distro's build waits only for the WSL
recipe and the winner manifest. The program gains one deliverable, the new-WSL install manifest: per layer the
selected repositories with pins, upstream install commands and evidence references, plus the runtime workers
(`blueprints/runtime-workers/`), the GPT-6 harnesses (the OmniRoute gateway, the Codex SDK lane, the sweep runner,
promptfoo, Harbor, Inspect), the key lane's passwordless practice (`docs/secret-storage.md`) and the convergence
practice (`docs/harness-defaults.md`, `docs/convergence-architecture.md`), consumed by the bootstrap and recorded
in the foundation catalog.

### Harness for the re-aimed E2E (open, 2026-10-01 03:36Z)

The Gate A owner's independent audit found that the merged top rule (`AGENTS.md:3`, recorded in
`docs/decisions/2026-09-30-rule-text-every-layer.md`: A/B and E2E use upstream harnesses, never a self-written runner)
covers the token-adoption E2E's custom runner, with no recorded exception. The owner therefore recommends path R:
re-scope the adoption E2E onto an upstream harness (Harbor or Inspect) on the new distro, with a pilot as step zero:
the Gate A owner's receipt of the 2026-09-29 Harbor E2E (`evidence/receipts/harbor-e2e-token-tools-20260930.json`,
PR #570: 308 claude-code logs scanned, 0 Agent or Task tool calls, 0 subagent directories) shows that none of the
trials spawned a subagent, so per-subagent attribution through Harbor is untested; the pilot forces subagent use and
confirms that each trial's saved session directory carries per-subagent transcripts, after which the merged Gate A
kernel serves as analysis code over those directories (analysis, not a runner). The pilot passes when, for at least
one trial that used a subagent, the saved session tree holds per-subagent transcripts and the dispatch-to-worker join (Agent tool_use ids,
the returned agent id, the child file names, the forwarded parent_tool_use_id where present, task lifecycle ids)
attributes each subagent tool call; otherwise the owner reports it and the fallback routes
(Inspect, or native OpenTelemetry) are compared before any preregistration. A source-cited feasibility read on the
pool (2026-10-01, verdict feasible with a pilot: Harbor v0.23.0 at 1e5c5c6d keeps the whole agent log tree including
subagent directories, trial.py:572-614, claude_code.py:1836 and 1058-1062; its trajectory.json is a derived view, so the
analysis reads the saved session tree; the Inspect fallback attributes subagents by prompt matching; native OTel needs
explicit settings on the Claude side while Codex 0.159.3 tool results carry agent and conversation ids) proposes an
eight-trial pilot (two SWE-bench tasks, two arms, two repetitions, the same client in both arms, two named workers
through project agents and a delegation rule, `harbor run --config`, one trial at a time, no retries) accepted only if
every trial launches both workers, keeps the child transcripts, attributes distinct per-worker canaries and reconciles
tokens and cost; the Gate A owner's record of that read is cited when it is published; the eight merged Gate A packages stay in main as
analysis tooling and the seven unfinished ones stay paused. The alternatives are A (run the custom toolchain on the new distro under a user-recorded exception to the rule) and
N (drop the adoption E2E and rely on the Harbor result); no path requires a revert on the current distro. Nothing is settled until the user answers; the install manifest therefore carries
the harness's needs under R (Harbor: rootless Docker, the egress allowlist, a native Claude OAuth token) and the Gate
A toolchain's needs only if A is chosen.

### Amendment 4 as the re-aim amendment (the Gate A owner's plan, 2026-10-01 ~03:45Z)

Amendment 4 stays the append-only dated vehicle; nothing in the sealed Amendment 3 files is edited. It is written
after the install manifest is final and (a) supersedes Amendment 3's host clauses with the new distro's baseline
(pinned clients and tool set captured at install, frozen rows re-captured there); (b) supersedes the custom runner and
kernel clauses with an upstream harness (Harbor, Inspect as fallback) unless the user records an exception for the
custom toolchain; (c) keeps the sealed question, tasks, metrics, gates and arms as the inputs ported into the harness's
task format unless it lists a change; (d) re-qualifies the Codex arms on the new runtime (Codex 0.159.3 with the
Sol/Astra routing; the SDK qualification so far covers 0.159.2 only). The Codex arms' route is decided in Amendment 4
before the announcement: either the native login, in which case the Codex window opens only if, at the preflight, the
native used percent plus 1.5 times the estimated cost is at most 90 percent, or the OmniRoute pool with the Sol/Astra
routing under the pool's launch rule (a live read first, at most 75 percent used before a run); the amendment records
the route and the preflight reading, and a change of route between arms or windows is a protocol deviation; (e) states the new host's freeze and window
rules. The current distro's Gate A freeze is lifted. Timing: after the WSL recipe and the winner manifest, the clean
install with its baseline capture, the harness task port and preregistration, a pilot, then an announcement with at
least six hours' notice: days, not hours.

Install needs for the manifest: under R, Harbor v0.23.0 (pinned), rootless Docker with subordinate id ranges widened
to 262,144, the egress allowlist, a Node v22.23.3 tarball pre-step for the arms, and the user's native Claude OAuth
token held in the key lane's per-provider 0600 store with the kernel keyring as its cache (a user action;
`docs/secret-storage.md` disallows keyring-only storage because a kernel restart loses it); under A only, Node 22.13 or later, Python 3.12 or 3.13 standard library,
the pinned shell parser (`examples/claude-native/workflows/shell-parser.pin.json`), rtk, qmd and both clients on PATH;
the toolchain opens no ports and runs no service.

### Timing estimate on the recipe basis (the Gate A owner, 2026-10-01 ~04:45Z; an estimate, not a commitment)

Critical path on the new distro: stage 1 (the PowerShell steps and the first boot, about an hour, run by the user), the
two interactive sign-ins, stage 2 (the full-profile bootstrap, one to three hours, with the subordinate id range
widened to 262,144 before the harness), a clean baseline capture and the Harbor pilot (about half a day), the re-aim
amendment or preregistration with its review (half a day to a day, overlapping), then the announcement with at least
six hours' notice. Task porting is the swing factor: the sealed 60-task table ported into harness tasks with oracle
checks is a day or more; a lighter first E2E on the 36 oracle-verified Harbor tasks with a subagent-forcing arm is about
half a day. If stage 1 starts on the morning of 2026-10-02 UTC, the earliest announcement is the morning of 10-03 and
the first window the evening of 10-03 to 10-04, with results by 10-06; the sealed port adds a day. All of it waits for
the user's answer on the harness (R, A or N) and is shaped by the Claude window and the Codex arms' route. Levers:
the user runs stage 1 and both sign-ins as soon as the recipe is readable; the lighter first E2E; the Codex arms on
the gateway. Recipe notes: the new distro's host file stays free of the current distro's ports, and a window needs a
load check on the shared WSL virtual machine, not only on the distro.

### Earlier option text (superseded)

The Gate A owner paused its builders and recommended re-aiming the token-adoption E2E (#381) at the new distro after
the clean install, since a new host collects its own evidence and the measurement toolchain is reusable. If the user
agrees, the current distro's drift revert is no longer required for Gate A's sake and the new distro's build no longer
waits for a window on the current distro; the windows then run on the new distro after its layers are installed. 

The token-efficiency layer is marked provisional until that E2E runs: what exists is the Harbor E2E of 2026-09-29 (288 trials of
short single-session tasks: context-mode x1.34, jcodemunch x1.39, the full stack x1.30 against the base arm; headroom,
rtk and serena inconclusive; MCP use 0 of 36 trials for context-mode and 1 of 36 for the full stack; receipt
`evidence/receipts/harbor-e2e-token-tools-20260930.json`, PR #570) and the accepted
14-component profile of #540 (`docs/decisions/2026-09-30-task-model-routing.md`) with jCodeMunch, codebase-memory-mcp
and ast-grep as task-appended lanes.

## Overturn

This program record is superseded if the user moves the Gate A measurement back to the current distro, if the WSL
recipe research shows that a new distro cannot be built without a host WSL package change that the keys lane has not
qualified, or if the pilot shows that neither Harbor's saved logs nor native OpenTelemetry carry per-subagent tool
calls.
