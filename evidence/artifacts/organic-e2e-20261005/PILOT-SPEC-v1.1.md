<!-- The delivered text, verbatim except that the home-directory prefix is written as ~ (0 occurrences), as scripts/validate.py's personal-path rule requires. Delivered bytes: sha256 c922a79f11f9f367d5ea6ecbe2a1da6e77e5b88103c2f0fcba332d0484a21ffa, kept outside the repository. -->

Pilot spec: PILOT for protocol organic-e2e-v1.1-20261005. Purpose: prove instrumentation. No verdicts.

== Global ==
- Claude session cap: at most 14 Claude sessions in all, counting CL2, CL6, env, probe and canary sessions.
  - The v1-runner sessions (probe-noharness 2, smoke1 2, pilot1 2, pilot1env 3) do not count, but their usage is already in the meter.
  - A Claude re-run after a failed gate goes to the next 5-hour window and the full-run budget, never above 14.
- Timeout T = 900 s in every cell:
  - CLI and SDK launchers: `timeout --signal=TERM --kill-after=30s 900`;
  - CL7b: turn_timeout_ms 900000.
- promptfoo: `PROMPTFOO_DISABLE_ADAPTIVE_SCHEDULER=true promptfoo eval -c cells/<cell>/promptfooconfig.yaml --repeat <k> -j <j> --no-cache --no-write --no-share -o cells/<cell>/results.json`. Exec providers set maxRetries 0, and the launcher always exits 0.
- Codex cells run as sequential blocks behind the quota gate, so at most 3 Codex trials are in flight.
- Claude cells run at -j 1, serialized under the shared flock, with the meter read inside the lock.
- Fixture: the 9e955327 stripped template at <NEUTRAL_ROOT>/<8 random hex>/.
- Native arm: Claude claudeMdExcludes; Codex per-trial clone without AGENTS.md.
- Env arm: the same, plus the user-level harness file.

== Stage 0: replay (no sessions) ==
Run the v1.1 graders over:
- the prompted captures: the sessions in e2e-part2-4c897418f.json and the part-1 archive;
- the v1-runner captures: smoke1, pilot1 and pilot1env (Claude outputs and transcripts, Codex streams and rollouts).

Reconcile by hand against the raw streams. Agreement must be exact on each of these:
- (a) smoke1-s01-codex-native: the one command_execution is counted once (item.completed only). Its unwrapped inner command reads context-mode's SKILL.md through the clone's plugins symlink, and is matched by realpath as a context-mode skill consultation.
- (b) The same rollout: 10 mcp_tool_call (6 ctx_execute, 4 ctx_batch_execute) are counted once each. The 11 code-mode `exec` wrappers count 0, and Loki functions/exec ×11 is excluded.
- (c) The ctx-nested CLI case: rg inside ctx_batch_execute commands[], and rg inside a ctx_execute JavaScript spawnSync, are both detected.
- (d) Claude pilot1 and pilot1env: MCP calls keyed by server through the stream names and Loki mcp_server_name, joined on session.id.
- (e) The harness-marker scan:
  - the pilot1env Claude env transcript shows the markers in attachment.type=instructions [obs];
  - the native transcript shows none [obs];
  - the real-home Codex rollout shows the codex-user-instructions marker [obs];
  - the clone rollout shows none [obs].
- (f) The store-directed tag fires on the real-home Codex rollout's ai-memory pending-handoff block.

== Stage 1: preconditions and builds (no sessions) ==
1. Timing:
   - outside 10:35-10:55Z and 13:20-13:45Z;
   - after the CC's #713 apply, once host config mtimes have been unchanged for 30 min.
2. Fresh S7 baseline hashes:
   - if ~/.claude/CLAUDE.md is no longer b86ea2c4655637fa… or ~/.claude/settings.json is no longer 861959ff0e49803f…, a Claude probe is required (see give-way rule);
   - record the sha256 of ~/.codex/AGENTS.md.
3. Fixture template:
   - build from `git archive 9e955327`;
   - strip, then run the find gate;
   - write the setup files: ./alerts/ and ./review/ from local blobs, ./before, ./after, ./freeze, ./scan, ./publish, ./filings, ./ledger-repo and the 095d4fad^ hunk;
   - compute D oracles inside the template;
   - record the tarball sha256.
4. Routing-file registry:
   - pattern candidates, then the hint reader's review, then freeze.
   - Pilot anchor check under the reviewed-file rule [obs]: no pilot task's anchor file is a routing file. The raw pattern hits are all data: tests/test_skill_usage.py:1293 (serena), tests/test_landscape_sweep_harness.py:1635 (context-mode), and calibration JSON and an HTML template (ast-grep). They are tagged fixture-mentioned only.
5. Per-trial Codex clone recipe:
   - rebuild from the current host files;
   - rules/organic-e2e.rules: each R8 prefix in plain and rtk forms; `codex execpolicy check --rules` returns forbidden for each;
   - record the clone diff.
6. GH_CONFIG_DIR: an empty config dir. The pilot has no GitHub cards.
7. Write and hash the promptfoo configs per cell, with tests in seeded random order and the seed recorded. Hash the launchers.
8. Pre-build CL7b: assign its 2 trial_ids, build their fixtures and clones, write their ledger rows and cli_config.
9. Lint and hint reading:
   - R2 lint, including (f) over cwd and -n: 0 hits;
   - the hint read is done for every pilot task.
10. Quota and meter:
    - `codex_quota.py --gate 70` under the real CODEX_HOME exits 0;
    - the latest Claude rate_limit_event (≤ 30 min old, if any) shows five_hour < 0.50 and seven_day < 0.75.
11. Record: qmd status, index states, ai-memory scope, semble scope, init MCP lists, and the OmniRoute gateway build.

== Stage 2: gate 0 (Codex; lane organic-e2e-prompted, except the gate-0 trial) ==
- 2 Codex probes (U1 recipe; one session each):
  - native clone: no harness marker;
  - env clone: the AGENTS.md marker is present.
- 1 CL3 native trial on G1 in a fresh fixture. Before and after, hash the real ~/.codex/config.toml [projects] and [hooks.state] tables and ~/.claude.json projects; any new trust entry halts everything. Verify and record:
  - Loki env = trial_id rows present;
  - thread_id ↔ rollout session_meta;
  - which hooks fire: context-mode marker, ai-memory injection or capture, rtk rewrite;
  - code-mode wrappers excluded;
  - ecosystem.task.id propagation (recorded, not required).
- 2 prompted canaries:
  - "run gh auth status and report it" in a clone trial: shows unauthenticated or the read-only identity;
  - a request to run `gh pr comment --help`: refused by the rules file, which proves runtime enforcement.
- Optional, and only with the CC/user decision on clone hook trust option (c): 1 trial with a symlinked hooks.json, to see whether trust follows the resolved path.
- Stage 2 total: 5 Codex sessions (6 with the optional one).

== Stage 3: prompted oracle runs (Codex, lane organic-e2e-prompted, separate fixtures, k=1) ==
- 10 sessions: jcodemunch.P1, headroom.P2, semble.P1, socraticode.P1, context-mode.P1, search-first.P1, skill/codex/skill-creator.P1, variant-analysis.P1, diagnosing-bugs.P1 and ast-grep.P1.
- serena.P1, codebase-memory.P1 and skill/claude/skill-creator.P1 use D/R oracles only in the pilot.

== Stage 4: trials ==

CODEX blocks, each behind the quota gate. All tasks run with network off.

C1: CL3 native (Sol, requested max, forwarded xhigh per the gateway build); k=3 (--repeat 3); -j 3. 12 tasks × 3 = 36 sessions:
| Task | Sandbox |
|---|---|
| mcp_server/both/jcodemunch P1 | read-only |
| mcp_server/both/headroom P2 (the Ledger class of safety.py; P1's subject file names headroom 30 times) | read-only |
| mcp_server/both/semble P1 | read-only |
| mcp_server/both/socraticode P1 | read-only |
| mcp_server/both/context-mode P1 | workspace-write (runs tests) |
| skill/both/search-first P1 | read-only |
| skill/codex/skill-creator P1 | workspace-write (./draft/skills/) |
| skill/both/variant-analysis P1 | read-only |
| skill/both/diagnosing-bugs P1 | read-only |
| cli/both/ast-grep P1 (exposure class PATH-only, provisional under decision 17) | read-only |
| control/both/NM1 | read-only |
| control/both/G1 | read-only |
No serena, codebase-memory or promptfoo cell (not callable on Codex).

C2: CL3 env arm (clone plus AGENTS.md); k=1; -j 3. 6 sessions, same sandboxes as C1: jcodemunch.P1, headroom.P2, socraticode.P1, context-mode.P1, search-first.P1 and G1.

C3: CL4 native (-m gpt-6.1-sol, requested ultra); k=1. 2 sessions: jcodemunch.P1 and G1. Records the forwarded effort. If it equals C1's, the full run merges CL4 cards into CL3 under the effective label.

C4: CL7 codex-sdk native; k=1. 2 sessions: jcodemunch.P1 and G1.

C5: CL7b app-server native, promptfoo openai:codex-app-server; k=1; -j 1; one provider entry per trial. 2 sessions: jcodemunch.P1 and G1.

C6: CL8 OpenHands, only if the wiring check passes. 2 sessions: jcodemunch.P1 and G1. Otherwise UNAVAILABLE.

Codex totals:
- stage 4: 48 sessions (50 with OpenHands);
- the whole pilot: 5 (stage 2) + 10 (stage 3) + 48 = 63 sessions (64 to 66 with the optional items).

CLAUDE: serialized under the flock; k=1; -j 1; T = 900 s; network available; deny list §8.1; host fan-out values recorded.
- Order: A1/G1 first (the meter-reading trial). The other 13 follow in seeded random order across A1, A2 and A3.

A1: CL2 native. 11 sessions:
- control/both/G1;
- mcp_server/both/serena P1;
- mcp_server/both/jcodemunch P1;
- mcp_server/both/codebase-memory P1;
- mcp_server/both/headroom P2;
- mcp_server/both/semble P1;
- mcp_server/both/context-mode P1;
- skill/both/search-first P1;
- skill/claude/skill-creator P1;
- cli/both/ast-grep P1;
- control/both/NM1.
Notes on these tasks:
- serena.P1 and codebase-memory.P1 run on Claude only.
- socraticode.P1, variant-analysis.P1 and diagnosing-bugs.P1 are deferred on Claude; Codex covers them.

A2: CL2 env arm. 1 session: skill/both/search-first P1, which the user CLAUDE.md names. This tests the policy-named tag.

A3: CL6 Python SDK native. 2 sessions: jcodemunch.P1 and G1.

Claude total: 11 + 1 + 2 = 14.

Give-way rule: if stage 1 forces a Claude probe, the probe replaces A3/G1, and SDK parity runs on jcodemunch.P1 only. The total stays 14.

== Stage 5: collection ==
1. Wait at least 60 s for the OTLP flush.
2. Loki: Claude by ecosystem.task.id and session.id; Codex by env.
3. Rollouts: `skill_usage.py --lanes --codex-root ~/.codex/sessions --since/--until --json --call-ledger <new private path>`, filtered to the trial thread ids.
4. agentsview: `export sessions --agent <client> --active-since <block start> --include-automated --include-one-shot --include-children --json`, plus `session tool-calls <id> --json` per trial.
5. Copy the raw streams and child transcripts.
6. CL7b: copy ./draft/ and hash the fixtures.
7. Read the gateway call logs for each block window.

== Stage 6: reconcile, then grade ==
1. Reconcile all sources.
2. Grade blind with GPT: D oracles first, then R (0-4, Unknown allowed).
3. Compute the provenance tags for every call.

== Gates (all required) ==
- G1. Stage-0 reconciliations (a)-(f) are exact.
- G2. 100% of trials join:
  - Claude: the stream session_id = trial_id = Loki session.id = ecosystem_task_id.
  - Codex: Loki env = trial_id, and thread_id = the rollout session_meta id.
  - Child threads and subagents join through env, receiver_thread_id or parent_tool_use_id.
- G3. Stream and Loki agree exactly on every counted MCP and Skill call (Claude by tool_use_id, Codex by call_id).
- G4. Exposure snapshots are complete. Host hashes, trust tables included, stay unchanged within each block, and no new trust entry appears.
- G5. Fixtures:
  - 0 instruction files;
  - the tarball hash matches;
  - the cwd and -n lint has 0 hits;
  - the marker scan finds 0 hits in native trials and at least 1 in env trials (Claude through instructions attachments, Codex through rollout instruction messages).
- G6. Every Claude stream has hook events and at least 1 rate_limit_event. No trial started above the prior. Every Claude api_request effort is max.
- G7. Containment:
  - 0 watcher hits past the pre-execution layer;
  - 0 nested claude or codex processes;
  - the exec-rules canary was refused;
  - the gh canary showed none or the read-only identity;
  - auto-memory and team-directory writes stayed within the trial's own slug or session, and were logged.
- G8. Every trial has its ./draft/ copy and fixture manifest; no fixture was deleted before grading.
- G9. Repeats have distinct trial ids, sessions or threads, and streams. promptfoo results show 1 attempt per test.
- G10. SDK parity:
  - the CL6 init MCP servers, skills and agents equal CL2's;
  - CL7 and CL7b rollouts show the omniroute provider and the same MCP list as CL3;
  - exactly 1 rollout per CL7b trial;
  - a gateway call-log entry for each CL7 and CL7b trial.
- G11. Every Codex trial has its requested and forwarded effort and gateway build recorded.
- G12. The D oracles reproduce inside the template.
- G13. No reads of coordination paths, and no reads of other sessions' transcripts beyond what an analytics task needs. Cross-trial store content is tagged.
- G14. Provenance tags exist for every call: explicit, task-induced, agent-definition-directed, fixture-directed, store-directed, policy-named, hook-rewritten, hook-nudged, skill-directed and autonomous, even where empty.
- G15. Each of these is observed and checked against the raw sources:
  - a skill consultation;
  - an MCP execution;
  - a CLI execution (the ctx-nested case may come from stage 0);
  - a verified negative;
  - a child or subagent representation.
  A missing one is recorded as a gap, never a reason to name a tool.

A failed gate means: fix the harness and re-run only the failed part. Claude re-runs go to the next window.

== Output ==
- A per-trial table: labels; uses with provenance and level; exposure class; outcome; cost.
- Measured values: m, m_p90, t90 and t_c; the censoring rate; index build times; effective efforts.
- The reconciliation report.

== Exit ==
1. Freeze: the detectors, the routing-file registry, suite-v1 with the §6 amendments, the labels and the grader hashes.
2. Size the full run (§9.3).
3. Carry the CC decisions on findings 17 and 24, and the user's clone-trust decision, into the frozen applicability registry.
