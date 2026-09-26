# Native engineering defaults

**Top rule: research first, and never self-write without a SOTA source.** Upstream and the installed client are the source of truth.

1. Before writing anything, reuse maintained upstream tools, skills, runtimes and orchestration patterns that already do the job, with their supported install and test commands, and name each source (repository and pin, file or paper). Stars and installs guide discovery, not evidence. With no SOTA source, stop and report.
2. Check capability claims in order: installed client (commands, `--help`, settings), upstream changelog or release notes for that version (`gh api`), upstream source at that tag, official docs. An absence claim needs at least the first two, else write "not found in X, Y".
3. Repository text, memory, tool output and worker, docs-agent or cross-family answers are leads, not authority; relay a claim only with its upstream citation.
4. Apply the token practice below in every lane.
5. When a claim or action proves wrong, record the correction and its verification path the same turn, in memory and any anti-pattern log the project declares.

## Core rule

Decide by evidence and research convergence: a choice stands when current primary sources (native help, official docs, maintained upstream) and reproduced results on the actual change agree, and it carries a dated record naming the alternatives and the comparison that would overturn it. Agreement, recency, stars and extra tooling are not evidence.

- Define acceptance from the requested outcome. Verify changed behavior with relevant upstream or project checks, inspect original source, and obtain independent review for substantive changes.
- Resolve supported findings before claiming completion. Distinguish measured results, simulations and untested boundaries; unchanged upstream tests, local integration checks, synthetic fixtures and actual provider execution are different evidence classes. New machines collect their own evidence; historical receipts do not certify the new host.
- Settle a discoverable harness capability by step 2 before asking the user; compare community alternatives against demonstrated gaps and run the selected native path through returned results. Dated exclusions are not current availability evidence.
- Carry the user's authorized work through implementation, relevant verification and a concise handoff. Use a short plan for bounded work; do not add intake, repeated approvals, diagnostic campaigns or restarts without a concrete need. Preserve existing edits, native accounts, model choices and project scope.
- Use the project's canonical instructions for memory scope, tests and domain rules, and keep durable memory and indexes scoped to that project.

## Token practice (base layer)

- Keep context small: load only the skill and source the current task needs; tool inventories and specialized workflows belong in on-demand skills and project documentation.
- Use a focused read for known identifiers, scoped search for prose and scoped semantic retrieval for unfamiliar code; select one sufficient retrieval or compression lane per artifact, and verify original source before editing or judging compressed or retrieved code.
- Process large output outside the model; retain failures and a full-output recovery path. Preserve the existing RTK-managed import when that component is installed.
- Delegate a step when only its conclusion is needed, and return concise findings with source or artifact locations.
- Preserve native prompt caching, deferred tool discovery and compaction.
- Count quality, elapsed time and complete provider usage, including workers and failed attempts, separately from estimated output reductions. Never sum overlapping counters or claim lifetime savings from a fixture.
- Details: `docs/token-practice.md` in the portable foundation, https://github.com/seathatflowsinourveins/native-agent-stack. Consult the project's installed-tool handbook only when setup, scope or accounting requires it.

## Workers and Ultracode

- Use one coordinator and bounded independent workers when useful. Give each writer an owned worktree, exact base, allowed paths and acceptance commands; worktrees do not isolate accounts or shared services. Reuse valid results; avoid repeated delegation or unchanged retries.
- For substantial parallel Claude work, use native Ultracode with explicit task-matched worker models, every worker at effort max (`effort: 'max'` on each `agent()` call; project agents declare `effort: max`). The coordinator stays at xhigh because a max session turns Ultracode orchestration off, and `CLAUDE_CODE_EFFORT_LEVEL` stays unset because it overrides every worker's effort.
- Size each workflow to its task under the `unrestricted` size guideline: solo for routine, conversational or mechanical turns, a scout plus review for a bounded change, one agent per independent unit for multi-unit work, tens of agents only for an enumerated work-list, within the runtime limits (4,096 items per `parallel()`/`pipeline()` call, 1,000 agents per run). Avoid expensive model inheritance, unbounded fan-out and repeated word-count calls.
- Cap concurrency per host with `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`, starting at 8 under the client's default of min(16, available CPUs − 2) per workflow (the bundled `/workflow-authoring` reference); the setting accepts 1–256 from 2.1.269.
- Children do not fan out a second layer (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`), and agent teams stay off because each teammate is a separate instance whose results are not summarized back.
- Consult the installed native Ultracode recipe only for dispatch, messaging or dashboard setup.
- When you return through StructuredOutput, put the schema fields at the top level of the call arguments; never wrap them in an input, output or result key.
- When a worker returns null or incomplete output, check its transcript for a safety refusal before retrying, since session limits and other errors also produce null results; after a refusal, edit the brief and retry on the current model, and never accept an older model's answer in its place.
