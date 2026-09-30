# Repository work

**Top rule: research convergence first; current upstream SOTA is the source of truth.** Before any action, research maintained SOTA repositories, installable skills and published references, and record what you found: invoke `search-first` before custom code or a tool choice, when no listed skill fits the task, discover skills with `find-skills` (`npx skills find`), verify or A/B one with `skill-creator`; every manifest skill stays listed for model invocation in both clients. Then install the best-evidenced source directly, or build only from a cited reference implementation, and name that source (repository, pin, file or paper) for every action; A/B and E2E use upstream harnesses (promptfoo, `skill-creator`'s paired benchmark, Harbor or Inspect), never a self-written runner. With no SOTA source, stop and report instead of writing one. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. Stars, installs and popularity guide discovery; they are not evidence.

Check capability claims in the order given in [Upstream verification and compounding learning](docs/harness-defaults.md#upstream-verification-and-compounding-learning), and record each proven mistake in its anti-pattern log.

This is a portable reference stack with evidence, native recipes and examples for building complex systems, projects and the north-star R&D; each unit names the north-star action it serves. The two maintained catalogs start at `catalogs/README.md`: `catalogs/foundation/manifest.json` for general native harness layers and `catalogs/us-equities/README.md` for the separate trading architecture. Catalog inclusion does not install, accept or authorize a candidate, and the complete research catalog is not an instruction to install every alternative or start every optional service; a default is a recommendation with an explicit adoption status.

## Evidence and completion

- Apply `docs/harness-defaults.md` when building or changing a harness: supported upstream installation, capability-specific evidence, bounded workers, scoped state and recoverable lifecycle acceptance.
- Use upstream executables and supported integration formats, with the supported installation and native test commands of the selected upstream revision.
- Follow `docs/acceptance-evidence-policy.md`: distinguish unchanged upstream tests from our integration checks and synthetic fixtures; retain actual returned output and independent observation. Do not promote locally authored tests or generated summaries into upstream acceptance.
- Keep historical host execution, reproducible artifact checks and live provider/GPU acceptance distinct; metadata, pinned source review and native execution are different evidence levels. Never describe a version check or recorded receipt replay as a new model run.
- Carry authorized setup, fixes, checks and documentation through useful completion, without intake, brainstorming or a separate planning approval for bounded work. Recorded limitations are context, not automatic new approval steps. Stop only for necessary native sign-in, operating system consent or an unresolved material decision, and continue independent work.
- Reuse passing evidence when its inputs still match and run only checks needed for a concrete gap; for a native tool gap, consult `docs/token-native-saturation.md` and its component matrix.
- Run `python3 scripts/validate.py` before committing changed evidence or manifests.
- For general engineering and ecosystem changes, start with `docs/convergence-architecture.md`. New convergence claims use `scripts/validate_convergence.py` with a scoped experiment record. Preserve failed attempts and failed conditions with their usage, and keep unknown usage unknown; the checker verifies declared consistency, not truth. End every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class) whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.

## Token practice (base layer)

Read `docs/token-practice.md` on demand for the selected context lane, native counter scopes and measured comparisons.

- Load only the layer, capability, recipe or guide the current task needs; never preload the full catalog or the generated HTML guide into the startup instructions, a session or every worker.
- Match available skill descriptions to the task; read each selected `SKILL.md` before acting. For installation, activation, updates or recovery, use `adoption/skills/lifecycle.md`.
- Choose the cheapest measured representation that meets the task's information contract. Known-source reads, compact JSON and full-original reads remain valid defaults when an extra retrieval or compression step is larger or inadequate.
- For one tool's adoption, read its row (by `component_id`) in `docs/token-efficiency-stack.json`, which `scripts/build_ecosystem.py` renders; its card is a dated snapshot, and the current lane list is the SubagentStart carrier block `adoption/hooks/claude/token-lanes-block.md`.
- Delegate a step when only its conclusion is needed, and return concise findings with source or artifact locations.
- Keep client accounts, model routes, native caching, tool discovery and compaction intact. No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed (`docs/decisions/2026-09-30-session-currency-notice.md`).
- Count once: never sum cumulative snapshots, overlapping artifact reductions or provider/cache subset counters, and keep native counter snapshots, exact artifact comparisons, cache reuse and complete provider usage separate.
- Read `docs/token-session-handbook.md` on demand for Codex session environment, MCP reload or another PC. Use `tools/token-report/README.md` for a new host's lifetime JSON/HTML manifest, and keep its private state outside the checkout.
- For catalog lookup on a host that adopted the named QMD index, refresh changed files with `qmd --index native-agent-stack-catalog update`, followed by `qmd --index native-agent-stack-catalog embed` where that index carries embeddings, then use scoped `query`, `search` and `get` from `us-equities-catalog`, `us-equities-foundation`, `foundation-adoption` or `foundation-docs`; `catalogs/us-equities/native-workflows.md` documents explicit setup for other checkouts. Do not index unrelated folders.

## Workers, effort and lanes

- One coordinator integrates. Writing workers need separate worktrees and bounded file ownership.
- Codex CLI, the second native client, defaults to `gpt-6.1-sol / ultra` for the coordinator and `gpt-6.1-sol / max` for primary workers. Preserve explicit model choices and selected role definitions. Astra/ultra coordinates a complex workflow that needs Astra; Astra/max takes a single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair). Record the trigger (dispatch contract: `docs/decisions/2026-09-30-sol-primary-quality-defaults.md`). Cross-family research, review and sweep votes run through the OmniRoute gateway.
- This repository commits `.claude/settings.json` with Ultracode on and `effortLevel: xhigh`, the saved fallback for any model. A terminal session started through the ecosystem `claude` launcher runs the coordinator at `max` (the launcher adds `--effort max` only when nothing chose an effort and the client is 2.1.284 or newer; `claude --effort xhigh` opts out). On Claude Code 2.1.284 Ultracode stays on at any effort level and the `ultracode` setting sets none, so a `max` session keeps its workflow orchestration on; the `max` default rests on the user's requirement, not on a measured gain here. Headless `-p` runs pass `--effort` per call site, and `CLAUDE_CODE_EFFORT_LEVEL` stays unset at every scope (any value overrides every child's effort). Pass `effort: 'max'` with an explicit task-matched `model` on every ad-hoc workflow `agent()` call: a stage that names no effort runs at its agent's frontmatter effort, else at the effort the session was given explicitly (`--effort`, `/effort`, the model picker), else at its model's saved level or default, and one that names no model takes its definition's model, else `CLAUDE_CODE_SUBAGENT_MODEL` (`opus`), else the lead's. `opus` takes judgment; `sonnet` (Sonnet 5.5) takes fan-out units that an executable oracle or a later Opus stage checks (`examples/claude-native/workflows/README.md`, "Sonnet 5.5 fan-out units"). Probes and overturn conditions: `docs/decisions/2026-09-29-max-default-effort.md`, `docs/decisions/2026-09-29-sonnet-5-5-dispatch.md` and `docs/decisions/2026-09-23-max-effort-default.md`.
- Dispatch each new or ad-hoc workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call. The saved scripts vendored in that directory keep their reviewed routing, byte-identical to agent-lab.
- Until the trading lane moves to its own repository, `docs/lanes.md` assigns foundation, trading and shared paths, gives the protocol for shared hot files such as `manifests/evidence.json`, and requires one `lane:*` label per PR. Build each PR description from `.github/pull_request_template.md`: the required `sota-sources` check fails a PR whose description lacks a non-empty `## SOTA sources` or `### SOTA sources` section (exact, case-sensitive heading). Hand off to a live session that owns an area instead of editing it.

## Hosts, credentials and records

- For a new machine or resumed ecosystem task, read `adoption/manifest.json` and `adoption/update.md` first and follow only the selected profile's native recipes. `adoption/lifecycle.md` defines owned installation, restart, recovery and cleanup; use the nonmutating `scripts/adoption_status.py` for prerequisites.
- Component pins remain in `manifests/stack.json`; general foundation limitations remain in `catalogs/foundation/manifest.json`, and trading limitations in `catalogs/us-equities/runtime-target.json` and its linked domain receipts. Historical receipts are reference evidence, never a new host's passed status.
- Keep host paths and native sign-ins private, and do not fetch private state or authentication stores. Credentials follow `docs/secret-storage.md` (per-provider 0600 files outside every worktree, native sign-ins left native); check them with the value-free `scripts/credential_status.py`, and never read, print or copy a credential value.
- Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration.
- Keep the public grand-dashboard checkpoint current when accepted work changes a lane, worker or gate. Its timer publishes bounded metadata; emitter freshness is distinct from checkpoint age and process liveness. Read `observability/grand-dashboard/README.md` only when operating that feature.
- Normal local observation uses Grafana anonymous Viewer on loopback; native model clients retain their own sign-ins. Keep Dagu operator authentication distinct from the passwordless observation path; auth:none is not a global Viewer role.
- The offline consolidated layer/setup guide `docs/ecosystem/index.html` is generated, not committed: build it with `python3 scripts/build_ecosystem.py --write`, or download it from a `publish-catalog.yml` workflow artifact (7-day retention, `workflow_dispatch`/`v*`-tag runs only).

## Trading north star

The north star is US-equities research and historical simulation with the selected
NautilusTrader 2.0.0rc5/IBKR destination and a separate Alpaca adapter path, followed
by independently qualified paper operation for each broker. Current selections
are in `catalogs/us-equities/runtime-target.json`; dated LEAN/Alpaca receipts remain
comparison evidence rather than overriding that destination.
Read `catalogs/us-equities/README.md` for selection and `blueprints/us-equities/north-star.md`
for boundaries. The native worker policy applies to workers launched by its example,
not automatically to unrelated SDKs or projects. Keep models in research and
deterministic code in numeric/risk/order state.
The user has explicitly authorized broker-specific paper-trading E2E after the
current foundation work. Follow `docs/paper-lane-policy.md`: proceed through native
paper readiness and measured acceptance without repeated human approval. Missing
live credentials or live configuration do not gate paper; live trading and paid
hosting remain separate scopes.

Trading-lane rules for research waves, data readiness and experiments live in `blueprints/us-equities/AGENTS.md`; read it before any trading research wave, experiment, data acquisition, strategy-gate change or registration of a decision array under `catalogs/us-equities/`.
