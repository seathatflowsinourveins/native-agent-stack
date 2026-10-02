# Selected SDK useful-work acceptance preparation

Status: source/oracle preparation; target execution and architecture acceptance pending.
North-star action served: qualify the runtime workers that perform bounded research and engineering tasks before relying on their work in the US-equities research stack.

The existing [selected acceptance plan](https://github.com/seathatflowsinourveins/native-agent-stack/blob/fc303db44d52c0d08f9d568866bec76c411fd3aa/evidence/artifacts/new-wsl-install-plan-20261002/accept.sh) runs supported interfaces but discards application stdout at line 52. Its stage status cannot prove the answer, produced file, tool outcome or native usage. This preparation supplies explicit useful-work and evidence requirements alongside those interfaces. The existing runtimes remain responsible for execution.

## Selected sources and boundaries

| Lane | Selected source | Prepared acceptance boundary |
| --- | --- | --- |
| Claude Agent SDK | `anthropics/claude-agent-sdk-python` v0.2.163, `1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7` | The existing arithmetic query remains a connectivity smoke. The [Quickstart fixture and local regression oracle](claude-quickstart/README.md) prepare a separate native tool task. |
| Codex TypeScript SDK | `openai/codex` rust-v0.160.0, `a956835d020762cb2b570053af06f643a11c0ecc` | Bind the documented diagnosis example to a frozen failing condition and inspect returned items/final response/usage. Adapting the Quickstart fixture to this lane requires independent review; no model-quality equivalence is inferred. |
| OpenHands SDK | `OpenHands/software-agent-sdk` v1.50.1, `1e1390acc8788346ba4804c34323284009bf3f5e` | Run the unchanged `01_hello_world.py` only after readiness. Its three project facts must be independently verified against the assigned source revision. |

The live WSL builder owns destination installations/configuration. Existing native CLI qualification stays with its assigned owner. This unit owns only new source/oracle artifacts. No target entry, provider run, route selection or configuration mutation is authorized by this document alone. The user's existing task authorization and the actual builder handoff govern execution.

## Required result retention

Before a run, freeze the SDK/source revision, assigned workspace and source hashes, native executable, selected model/provider route identity, permission/sandbox settings, exact task, supported command and verifier. Record only value-free credential readiness. Keep each attempt's original permitted task output in a private destination before processing it. Export a sanitized bounded receipt containing exact process status, task result, independently observed artifact hashes and native counters. Do not export initialization/account/authentication data or raw conversations.

- **Claude:** the tagged [`ResultMessage`](https://github.com/anthropics/claude-agent-sdk-python/blob/1ef6d8c71bb0e44a6b33fe61497864f21e17fdb7/src/claude_agent_sdk/types.py#L1340) supplies `subtype`, `is_error`, `num_turns`, `result`, optional `usage`, `model_usage`, cost, errors and `api_error_status`. Require a successful result without a reported error plus independently passing task checks. Retain parent/child tool observations where returned. Missing fields remain null. Do not add top-level usage to per-model usage.
- **Codex:** tagged [`Turn`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/typescript/src/thread.ts#L10) exposes `items`, `finalResponse` and nullable `usage`. Preserve native streamed terminal/failure events and tool results where used. [`Usage`](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/sdk/typescript/src/events.ts#L21) carries input, cached input, cache-write input, output and reasoning-output counters. Retain their original names; do not invent disjoint totals or count cache/reasoning subsets again.
- **OpenHands:** the unchanged hello-world task prints a completion line but not a complete metrics record. Its [`13_get_llm_metrics.py`](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/examples/01_standalone_sdk/13_get_llm_metrics.py#L80) demonstrates native `llm.metrics.model_dump()` and `accumulated_cost`; [`ConversationStats`](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/openhands-sdk/openhands/sdk/conversation/conversation_stats.py#L13) tracks per-LLM metrics. A future capture extension must use these supported interfaces, preserve its exact diff and be labeled an integration adaptation. The unchanged example alone leaves unreturned usage unknown.

Keep every failed, timed-out or skipped attempt and the reason. Preserve original terminal status separately from the verifier's status. Do not rerun successful matching evidence or broaden to unselected MCP/provider integrations. Resume, recovery, tool permission enforcement, worker-role dispatch and full target-host lifecycle need their own scoped acceptance; this useful-task preparation closes none of those gates.

## OpenHands fact oracle

The upstream [hello-world example](https://github.com/OpenHands/software-agent-sdk/blob/1e1390acc8788346ba4804c34323284009bf3f5e/examples/01_standalone_sdk/01_hello_world.py) asks for three facts about the current project and writes `FACTS.txt`. Freeze the assigned repository/revision and a source allow-list before execution. The independent verifier must read that exact resulting file, identify three distinct factual claims and attach a source path, content hash and supporting location to each. Reject missing/empty output, unsupported claims and facts from a different repository. Record extra claims and their correctness rather than silently dropping them.

Preselecting three arbitrary facts and requiring the unchanged open-ended prompt to return those exact facts would change its semantic contract. This rubric permits any three supported project facts; the actual source allow-list and grading result must be frozen/retained for the selected run. An independent reviewer must accept this rubric before target execution. It is a local semantic integration check, not an upstream test or comparative benchmark.

## Review and execution gates

The consequential cross-runtime acceptance review was assigned to the required Astra/Max role. That agent failed at the account usage limit before returning a judgment; no acceptance is inferred. The assigned fixture worker also failed before writing files. The coordinator prepared the source fixture and local checks; a separate reviewer must inspect them. The [resolution envelope](../../blueprints/convergence-practice/clean-resolution-20261002/README.md) retains the broader open work.

A future comparative claim must use the repository's selected upstream evaluation harness with preregistered tasks and scoring. No comparative or token-saving claim is made here, and this directory introduces no model runner.
