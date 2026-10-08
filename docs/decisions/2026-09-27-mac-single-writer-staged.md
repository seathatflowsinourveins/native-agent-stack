# Decision: native-agent-stack becomes the Mac's single writer, in two stages (2026-09-27)

**Record 2026-09-27:** native-agent-stack takes the Mac's global setup in two stages, preserving running services until the measured cutover. Memory discovery includes [rohitg00/agentmemory at `2d38dafe`](https://github.com/rohitg00/agentmemory/blob/2d38dafede67d0d4ed920cde94d2106e98825b8a/README.md), [vectorize-io/hindsight at `f8950b0c`](https://github.com/vectorize-io/hindsight/blob/f8950b0c07d9e34c76493dba802bb309f0ce60fd/README.md), starred repositories, research-convergence and awesome lists. [Native cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging) supplies coordination without transferring host authority. Branch `claude/mac-single-writer-staged-20260927`, based on `origin/main@6e53809e`.

**Scope:** this record, and step 0 of the macOS section of [`docs/next-host-stages.md`](../next-host-stages.md). Lane: `lane:foundation`.
- It does not change [`adoption/host-roles.json`](../../adoption/host-roles.json). The Mac's `model-hosting` role waits for the #379 measurements.
- It does not change `adoption/bootstrap-macos.sh`.
- It changes no service on any host.

## Context

- The 2026-09-24 state assigned agent-ecosystem's foundation-lane setup session sole ownership of the Mac's global state and shared services (dated item agent-ecosystem#28). Existing writer ownership appears in two places:
  - [`foundation-alignment.json`](../../evidence/artifacts/host-upgrade-20260924/foundation-alignment.json), whose `scope` and open item 1 keep this repository's duplicate launchd bootstrap inactive;
  - `docs/next-host-stages.md` step 0.
- As a result, this repository's Claude and Codex client layer has never run on a Mac:
  - the stack agents, guard hooks and MCP servers (`tools/adoption/install_claude_profile.py`);
  - the rendered settings (`tools/adoption/render_config.py`, `tools/adoption/apply_claude_settings.py`);
  - the pinned skills, plugins and workflows.

  The macOS platform profile is still `drafted_not_accepted` ([`adoption/manifest.json`](../../adoption/manifest.json)).
- The current Mac, `mac-coordinator-64gb-20260925`, has 5 `use` receipts: ai-memory, qdrant, qmd, restic and socraticode. They were recorded against the agent-ecosystem installs, not a pinned install from this repository.
- The workstation and the Mac should share one source of truth: the same pins, receipts, CI and acceptance rules ([`docs/acceptance-evidence-policy.md`](../acceptance-evidence-policy.md)).

## Decision

1. **Single writer.** native-agent-stack is the single writer of the Mac's global Claude Code and Codex state, and later of its foundation services. This supersedes the 2026-09-24 rule for this Mac. agent-ecosystem#28 gets a notice.
2. **Stage 1: the client layer, now.** Host request [#382](https://github.com/seathatflowsinourveins/native-agent-stack/issues/382) covers:
   - agents, guard hooks, MCP, settings, skills, plugins and workflows;
   - the full token-efficiency practice ([#276](https://github.com/seathatflowsinourveins/native-agent-stack/issues/276));
   - Codex with `daemon_auto_start` and the daemon updater off.

   Constraints:
   - Stage 1 starts, stops, replaces or duplicates **no** running service: the `local.agent-ecosystem.*` Qdrant and ai-memory launchd agents, and Ollama.
   - Memory hooks either point at the running ai-memory or stay off.
   - `~/.claude` and `~/.codex` are backed up before any write.
3. **Stage 2: services, later.** Qdrant, the memory service and the embedding runtime move to this repository's recipes only after both of these exist:
   - the capacity and parity measurements of [#379](https://github.com/seathatflowsinourveins/native-agent-stack/issues/379);
   - the memory-layer head-to-head below.

   The move is a cold-copy cutover with a rehearsed rollback, the pattern of the workstation's ai-memory cutovers ([`2026-09-25-workstation-sota-refresh.md`](2026-09-25-workstation-sota-refresh.md)).
4. **Memory is decided on merit, not carried over.**
   - The durable-memory layer on the Mac, and on the workstation, is chosen by a preregistered head-to-head (S3). Candidates are the union of:
     - the user's starred repositories ([`catalogs/convergence-practice/public-starred.json`](../../catalogs/convergence-practice/public-starred.json));
     - the research-convergence durable-memory layer ([`catalogs/sota-convergence/manifest-20260926.json`](../../catalogs/sota-convergence/manifest-20260926.json));
     - the memory-stack catalog ([`catalogs/foundation/memory-stack-20260925.json`](../../catalogs/foundation/memory-stack-20260925.json));
     - awesome-list discovery.
   - The winner supersedes ai-memory, which stays the reference arm, not a default.
   - The evidence so far, on the Mac only: agentmemory at 0.821 recall_all@5, against ai-memory's production configuration at 0.570 and plain BM25 at 0.747 ([`evidence/artifacts/memory-stack-20260925/experiment.json`](../../evidence/artifacts/memory-stack-20260925/experiment.json)). ai-memory with its reranker (C4) and agentmemory through its shipped hooks (D2h) have never run.
   - The head-to-head also measures:
     - injected-context tokens per session and per recall (o200k);
     - write-time LLM tokens;
     - latency, RSS and cold start.
5. **Cross-host coordination.**
   - GitHub host requests stay the durable record ([`2026-09-25-host-request-lane.md`](2026-09-25-host-request-lane.md)).
   - Claude Code Remote Control with cross-session messaging is the live channel while the setup settles ([cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), [Remote Control](https://code.claude.com/docs/en/remote-control)).
   - Messaging is not control. A message cannot approve a prompt, change configuration or run a command, and each host's own permissions apply.
   - The receiving side sets `crossSessionInbound: "accept"`. `remoteControlAtStartup: true` is valid only in user settings.

## Alternatives considered

- **Keep agent-ecosystem as the Mac's writer.** The workstation's practice and pins would be ported there, and this repository would only record receipts. Not chosen: two writers for the same practice means two sets of pins and acceptance rules, and the Mac never received this repository's layer under that arrangement.
- **A permanent split.** This repository would own the client layer and agent-ecosystem would keep the services. Not chosen as the end state: the services depend on the memory-layer verdict, which this repository runs. Stage 1 is exactly this split, as a transition.

## What would overturn this

- Stage 1 or Stage 2 cannot be installed on the Mac from this repository's pinned recipes without breaking a running service.
- A maintained agent-ecosystem release delivers the same pinned, receipted practice with less duplication.

In either case, record the failed step and its output, and return the affected layer to its previous writer.

## Sources

- Claude Code documentation: [Remote Control](https://code.claude.com/docs/en/remote-control), [cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging), [settings reference](https://code.claude.com/docs/en/settings-reference) (`crossSessionInbound`, `isolatePeerMachines`, `remoteControlAtStartup`).
- Codex daemon behaviour: [`codex-rs/app-server-daemon/README.md` at rust-v0.157.1](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/app-server-daemon/README.md), and [`evidence/receipts/codex-01571-qualification-20260926.json`](../../evidence/receipts/codex-01571-qualification-20260926.json).
- Memory candidates: [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory) (v0.9.29), [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) (v0.10.1), and the catalogs above.
