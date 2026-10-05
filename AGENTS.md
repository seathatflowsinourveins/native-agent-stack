# Repository work

**Top rule: research convergence first; current upstream SOTA is the source of truth.** Before any action, research maintained SOTA repositories, installable skills and published references, and record what you found. A coordinator, not a delegated child, invokes `search-first` before custom code or a tool choice; when no skill fits, use installed `find-skills` or Skills CLI `find` and `skill-creator` for verification or A/B; check client exposure and the skills lifecycle. Then install the best-evidenced source directly, or build only from a cited reference implementation, and name that source (repository, pin, file or paper) for every action. Prefer the maintainer's own organization repositories (the vendor's GitHub org, such as alpacahq for Alpaca) and their clean releases, and never rebuild or fork what an upstream already ships; glue only fills a demonstrated gap, cited at a pin. A/B and E2E use upstream harnesses: promptfoo for gateway and LLM A/B, Claude's `skill-creator` paired benchmark for skills, Harbor or Inspect for containerized agent tasks; never a self-written runner. With no SOTA source, stop and report instead of writing one. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. Stars, installs and popularity guide discovery; they are not evidence.

Prompts fix the objective, scope and authorization; improve the approach from current evidence.

Check capability claims in the order given in [Upstream verification and compounding learning](docs/harness-defaults.md#upstream-verification-and-compounding-learning), and record each proven mistake in its anti-pattern log.

To choose among maintained candidates for a documented gap, apply `docs/decisions/2026-10-04-repository-quality-rule.md`.

This is a portable reference stack with evidence, native recipes and examples. The harness exists to build complex systems, projects and the north-star R&D; each coordinator unit names the north-star action it serves. The two maintained catalogs start at `catalogs/README.md`: `catalogs/foundation/manifest.json` for general native harness layers and `catalogs/us-equities/README.md` for the separate trading architecture. Catalog inclusion does not install, accept or authorize a candidate, and the complete research catalog is not an instruction to install every alternative or start every optional service; a default is a recommendation with an explicit adoption status.

## Evidence and completion

- Apply `docs/harness-defaults.md` when building or changing a harness: supported upstream installation, capability-specific evidence, bounded workers, scoped state and recoverable lifecycle acceptance.
- Use upstream executables and supported integration formats, with the supported installation and native test commands of the selected upstream revision.
- Follow `docs/acceptance-evidence-policy.md`: distinguish unchanged upstream tests from our integration checks and synthetic fixtures; retain actual returned output and independent observation. Do not promote locally authored tests or generated summaries into upstream acceptance.
- Keep historical host execution, reproducible artifact checks and live provider/GPU acceptance distinct; metadata, pinned source review and native execution are different evidence levels. Never describe a version check or recorded receipt replay as a new model run.
- Carry authorized setup, fixes, checks and documentation through useful completion, without intake, brainstorming or a separate planning approval for bounded work. Recorded limitations are context, not automatic new approval steps. Stop only for necessary native sign-in, operating system consent or a material decision that a cross-family review leaves unresolved, and continue independent work.
- Reuse passing evidence when its inputs still match and run only checks needed for a concrete gap; for a native tool gap, consult `docs/token-native-saturation.md` and its component matrix.
- Run `python3 scripts/validate.py` before committing changed evidence or manifests.
- For general engineering and ecosystem changes, start with `docs/convergence-architecture.md`. New convergence claims use `scripts/validate_convergence.py` with a scoped experiment record. Preserve failed attempts and failed conditions with their usage, and keep unknown usage unknown; the checker verifies declared consistency, not truth. A coordinator ends every substantive research or adoption unit with a completeness critic (missed modality, source or candidate class) whose findings feed that layer's next landscape sweep; the skills sweep is keyed by lifecycle task.

## Token practice (base layer)

Read `docs/token-practice.md` on demand for the selected context lane, native counter scopes and measured comparisons.

- Load only the layer, capability, recipe or guide the current task needs; never preload the full catalog or the generated HTML guide into the startup instructions, a session or every worker.
- Bound discovery to task-filtered names, descriptions and source locators; load only selected tool schemas. For maintained decisions, and before describing deployed architecture after compaction/resume, query scoped ai-memory with `pin_first=true, limit=2` when supported by the installed schema. Check relevance; retry without pin priority or widen if needed, then read the relevant exact path and verify current canonical sources.
- Match available skill descriptions to the task; read each selected `SKILL.md` before acting. For installation, activation, updates or recovery, use `adoption/skills/lifecycle.md`.
- Choose the cheapest measured representation that meets the task's information contract. Known-source reads, compact JSON and full-original reads remain valid defaults when an extra retrieval or compression step is larger or inadequate.
- For one tool's adoption, read its row (by `component_id`) in `docs/token-efficiency-stack.json`, which `scripts/build_ecosystem.py` renders; its card is a dated snapshot, and the current lane list is the SubagentStart carrier block `adoption/hooks/claude/token-lanes-block.md`.
- Delegate a step when only its conclusion is needed, and return concise findings with source or artifact locations.
- Keep client accounts, model routes, native caching, tool discovery and compaction intact. No audits, trials or network at startup; the daily currency timer's one read-only due-file line is allowed (`docs/decisions/2026-09-30-session-currency-notice.md`).
- Count once: never sum cumulative snapshots, overlapping artifact reductions or provider/cache subset counters, and keep native counter snapshots, exact artifact comparisons, cache reuse and complete provider usage separate.
- Read `docs/token-session-handbook.md` on demand for Codex session environment, MCP reload or another PC. Use `tools/token-report/README.md` for a new host's lifetime JSON/HTML manifest, and keep its private state outside the checkout.
- For catalog lookup and QMD index refresh, read `docs/token-session-handbook.md#catalog-lookup`.

## Workers, effort and lanes

- One coordinator integrates. Writing workers need separate worktrees and bounded file ownership.
- Codex CLI is the second native client. For unpinned work, `gpt-6.1-sol` at ultra coordinates and at max runs workers; `gpt-6-astra` at ultra coordinates a complex workflow that needs Astra, and at max takes a single consequential judgment (conflicting primary evidence, consequential architecture, complex changes across systems, or a failure unresolved after one bounded Sol repair). Where a launch pins the model and effort (`-m`, `-c model_reasoning_effort`), children inherit that pin and a spawn call names neither. Preserve explicit model choices and role definitions; a coordinator records the trigger and acceptance result. Cross-family research, review and sweep votes run through the OmniRoute gateway; a coordinator, never a delegated child, starts a cross-family lane. The dispatch contract is `docs/decisions/2026-09-30-sol-primary-quality-defaults.md`.
- For Claude effort, Ultracode and child-model rules, read `docs/decisions/2026-09-29-max-default-effort.md`.
- Dispatch each new or ad-hoc workflow `agent()` stage by role: take its `agentType` from the role table in `examples/claude-native/workflows/README.md#dispatch-by-role-2026-09-26`, and give a `general-purpose` or omitted `agentType` a `// dispatch: <reason>` comment beside the call. The saved scripts vendored in that directory keep their reviewed routing, byte-identical to agent-lab.
- Until the trading lane moves to its own repository, `docs/lanes.md` assigns foundation, trading and shared paths, gives the protocol for shared hot files such as `manifests/evidence.json`, and requires one `lane:*` label per PR. Build each PR description from `.github/pull_request_template.md`: the required `sota-sources` check fails a PR whose description lacks a non-empty `## SOTA sources` or `### SOTA sources` section (exact, case-sensitive heading). Hand off to a live session that owns an area instead of editing it.

## Hosts, credentials and records

- For a new machine or resumed ecosystem task, read `adoption/manifest.json` and `adoption/update.md` first and follow only the selected profile's native recipes. `adoption/lifecycle.md` defines owned installation, restart, recovery and cleanup; use the nonmutating `scripts/adoption_status.py` for prerequisites.
- Component pins remain in `manifests/stack.json`; general foundation limitations remain in `catalogs/foundation/manifest.json`, and trading limitations in `catalogs/us-equities/runtime-target.json` and its linked domain receipts. Historical receipts are reference evidence, never a new host's passed status.
- Keep host paths and native sign-ins private, and do not fetch private state or authentication stores. Credentials follow `docs/secret-storage.md` (per-provider 0600 files outside every worktree, native sign-ins left native); check them with the value-free `scripts/credential_status.py`, and never read, print or copy a credential value.
- Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration.
- When accepted work changes a lane, worker or gate, follow `observability/grand-dashboard/README.md#checkpoint-and-observation-rules`.
- For local observation or operator authentication, read `observability/grand-dashboard/README.md#checkpoint-and-observation-rules`.
- For the generated offline ecosystem guide, read `docs/token-session-handbook.md#offline-ecosystem-guide`.

Before trading research, experiments, data acquisition, strategy-gate changes, decision registration, paper or broker operation, or naming a coordinator unit's north-star action, read `blueprints/us-equities/AGENTS.md` for the north star, rules and broker-specific paper authorization.
