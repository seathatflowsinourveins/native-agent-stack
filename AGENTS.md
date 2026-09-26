# Repository work

**Top rule: research first, and never self-write without a SOTA source.** Before any action, research maintained SOTA repositories, installable skills and published references with the installed research and skill-discovery skills, and record what you found. Then install the best-evidenced source directly, or build only from a cited reference implementation, and name that source (repository, pin, file or paper) for every action. Stars, installs and popularity guide discovery; they are not evidence. With no SOTA source, stop and report instead of writing one.

This is a portable reference stack with evidence, native recipes and examples. The two maintained catalogs start at `catalogs/README.md`: `catalogs/foundation/manifest.json` for general native harness layers and `catalogs/us-equities/README.md` for the separate trading architecture. Catalog inclusion does not install, accept or authorize a candidate, and the complete research catalog is not an instruction to install every alternative or start every optional service; a default is a recommendation with an explicit adoption status.

## Evidence and completion

- Apply `docs/harness-defaults.md` when building or changing a harness: supported upstream installation, capability-specific evidence, bounded workers, scoped state and recoverable lifecycle acceptance.
- Use upstream executables and supported integration formats, with the supported installation and native test commands of the selected upstream revision.
- Follow `docs/acceptance-evidence-policy.md`: distinguish unchanged upstream tests from our integration checks and synthetic fixtures; retain actual returned output and independent observation. Do not promote locally authored tests or generated summaries into upstream acceptance.
- Keep historical host execution, reproducible artifact checks and live provider/GPU acceptance distinct; metadata, pinned source review and native execution are different evidence levels. Never describe a version check or recorded receipt replay as a new model run.
- Carry authorized setup, fixes, checks and documentation through useful completion. Use a short internal plan; do not add intake, brainstorming or separate planning approval to bounded work. Recorded limitations are context, not automatic new approval steps. Stop only for necessary native sign-in, operating system consent or an unresolved material decision, and continue independent work.
- Reuse passing evidence when its inputs still match and run only checks needed for a concrete gap; for a native tool gap, consult `docs/token-native-saturation.md` and its component matrix.
- Run `python3 scripts/validate.py` before committing changed evidence or manifests.
- For general engineering and ecosystem changes, start with `docs/convergence-architecture.md`. New convergence claims use `scripts/validate_convergence.py` with a scoped experiment record. Preserve failed attempts and failed conditions with their usage, and keep unknown usage unknown; the checker verifies declared consistency, not truth.

## Token practice (base layer)

Read `docs/token-practice.md` on demand for the selected context lane, native counter scopes and measured comparisons.

- Load only the layer, capability, recipe or guide the current task needs; never preload the full catalog or the generated HTML guide into the startup instructions, a session or every worker.
- Choose the cheapest measured representation that meets the task's information contract. Known-source reads, compact JSON and full-original reads remain valid defaults when an extra retrieval or compression step is larger or inadequate.
- Keep client accounts, model routes, native caching and tool discovery intact. Do not rerun the full audit or model trials at startup.
- Count once: never sum cumulative snapshots, overlapping artifact reductions or provider/cache subset counters, and keep native counter snapshots, exact artifact comparisons, cache reuse and complete provider usage separate.
- Read `docs/token-session-handbook.md` on demand for Codex session environment, MCP reload or another PC. Use `tools/token-report/README.md` for a new host's lifetime JSON/HTML manifest, and keep its private state outside the checkout.
- For catalog lookup on a host that adopted the named QMD index, refresh changed files with `qmd --index native-agent-stack-catalog update`, then use scoped `search` and `get` from `us-equities-catalog` or `us-equities-foundation`; `catalogs/us-equities/native-workflows.md` documents explicit setup for other checkouts. Do not index unrelated folders.

## Workers, effort and lanes

- One coordinator integrates. Writing workers need separate worktrees and bounded file ownership.
- This repository commits `.claude/settings.json` with Ultracode on. The Claude coordinator stays at `xhigh` under Ultracode, because a `max` session turns its workflow orchestration off, and never sets `CLAUDE_CODE_EFFORT_LEVEL` (any value overrides every child's effort). Pass `effort: 'max'` with an explicit task-matched `model` on every ad-hoc workflow `agent()` call: a stage without its own `effort` inherits the coordinator's `xhigh` unless its agent's frontmatter sets one. Probes and overturn conditions: `docs/decisions/2026-09-23-max-effort-default.md`.
- Until the trading lane moves to its own repository, `docs/lanes.md` assigns foundation, trading and shared paths, gives the protocol for shared hot files such as `manifests/evidence.json`, and requires one `lane:*` label per PR. Hand off to a live session that owns an area instead of editing it.

## Hosts, credentials and records

- For a new machine or resumed ecosystem task, read `adoption/manifest.json` and `adoption/update.md` first and follow only the selected profile's native recipes. `adoption/lifecycle.md` defines owned installation, restart, recovery and cleanup; use the nonmutating `scripts/adoption_status.py` for prerequisites.
- Component pins remain in `manifests/stack.json`; general foundation limitations remain in `catalogs/foundation/manifest.json`, and trading limitations in `catalogs/us-equities/runtime-target.json` and its linked domain receipts. Historical receipts are reference evidence, never a new host's passed status.
- Keep host paths and native sign-ins private, and do not fetch private state or authentication stores. Credentials follow `docs/secret-storage.md` (per-provider 0600 files outside every worktree, native sign-ins left native); check them with the value-free `scripts/credential_status.py`, and never read, print or copy a credential value.
- Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration.
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

For architecture or research waves, read `blueprints/us-equities/architecture/README.md`
and the matching source-review supplement. `catalogs/us-equities/decision-index.json`
is the validated repository union; register new decision arrays explicitly with
`scripts/catalog_decisions.py --write --supplement PATH.json#/collection`.

Keep the public grand-dashboard checkpoint current when accepted work changes a
lane, worker or gate. Its timer publishes bounded metadata; emitter freshness is
distinct from checkpoint age and process liveness.
Read `observability/grand-dashboard/README.md` only when operating that feature.
Normal local observation uses Grafana anonymous Viewer on loopback; native model
clients retain their own sign-ins. Keep Dagu operator authentication distinct from
the passwordless observation path; auth:none is not a global Viewer role.

The simulation-research wave adopts isolated EdgarTools and skfolio
recipes. Read `blueprints/us-equities/simulation-research/README.md` for current
results and remaining data gates. Its 2021 control segment is now inspected;
future experiments must not call it a fresh untouched holdout. Native filing
parsing, live SEC access and historical information availability are separate
claims. Keep provider identities local and preserve acquisition refusals.
`blueprints/us-equities/catalyst-provenance/access-resolution.md` records successful native
SEC access and real-index compatibility. Keep its monitored contact private;
bounded streaming diagnostics must bypass the upstream cache after closing clients.

`blueprints/us-equities/data-readiness/README.md` links the
September 20 catalyst-dataset and corporate-action wave. Retained source bytes,
native parser behavior, materialized data integrity and actual historical
availability are separate claims. Read that plan and the matching receipt before
repeating acquisition or advancing a strategy gate.

`blueprints/us-equities/authenticated-data/README.md` records native
Alpaca AAPL acceptance. Continue with `blueprints/us-equities/identity-readiness/README.md`
for the symbol-mapping/observation gate. A request's symbol-asof date, current asset
UUID/status and newly captured historical values are not original availability or
historical universe membership. Reuse retained anchored runs before refetching;
new hosts must establish their own permitted observations and acceptance.

For the catalyst-convergence wave, read `blueprints/us-equities/catalyst-convergence/README.md`
and its plan on demand. The frozen daily/intraday protocol is in
`blueprints/us-equities/catalyst-experiment/protocol.json`; lifecycle evidence is in
`blueprints/us-equities/lifecycle-sample/native-receipt.json`. Local observation
availability cannot substitute for original historical publication/revisions.
Native research efficiency also requires both semantic quality and the frozen
output contract. The selected direction is daily/intraday
catalyst research, including historical +200% mover discovery. Preserve as-known
candidate universes and source revisions; the current synthetic temporal fixture
and fixed LEAN schedule are not an accepted historical strategy dataset.
