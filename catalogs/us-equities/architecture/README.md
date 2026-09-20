# Source-reviewed architecture wave — September 19, 2026

Current routing is maintained in the [runtime target](../runtime-target.json) and
[execution acceptance plan](../../../blueprints/us-equities/engine-nautilus/acceptance-plan.md):
NautilusTrader 2.0.0rc5 is selected, with native IBKR integration and a separate
Alpaca adapter. LEAN remains the accepted historical comparison. This dated review
preserves its original findings; it does not establish equity/paper acceptance.

This wave refreshes public-star coverage, inspects current primary source, and
tests the selected architecture with native model critics and an offline SDK
probe. It does not identify a timeless, exhaustive or universally highest-quality
stack. The result is a defensible selection with explicit alternatives and gates.

Start with the [roles and architecture](../../../blueprints/us-equities/architecture/README.md),
[authoritative decision union](../decision-index.json), and
[native review evidence](../../../blueprints/us-equities/architecture/receipt.json).
The earlier four layer catalogs still provide the detailed baseline cards;
these follow-ups are indexed as separate dated source-review decisions.

## Research coverage and depth

| Lane | Coverage | Retained evidence |
| --- | --- | --- |
| Foundation and workers | 15 repositories in two waves; 76 selected source/config/test files; four discovery lists | [Decisions](foundation.json), [source hashes](foundation-sources.json) |
| Trading and evaluation | 15 repositories in two waves; 81 selected source/config/test/license files plus three maintained list sources | [Decisions](trading.json), [source hashes](trading-sources.json) |
| Cross-layer discovery and governance | All 337 public stars refreshed, no identity delta; 12 complete pinned list snapshots; 10 candidates with 40 selected files | [Decisions](coverage.json), [coverage accounting](coverage-accounting.json) |
| Official Alpaca ecosystem | 94 public organization repositories enumerated; five current SDK/MCP READMEs and three Python source/config files examined; eight selected dispositions | [Decisions and constraints](alpaca.json), [organization metadata](alpaca-organization.json) |

Counts overlap across lanes. They must not be added into a claim of unique
deep-reviewed repositories. The 12-list scan extracted **7,028 normalized GitHub
repository links**: 85 already in the historical grand index, four selected for
this lane's source review, and **6,939 discovery-only/unassessed**. Link extraction
is not identity verification, quality review or installation. Six further
governance candidates came from capability-led research. Metadata labels 67 of
the 337 stars with unknown/unclassified licenses; that is not license clearance.

The discovery ledger includes pinned versions of
[awesome-quant](https://github.com/wilsonfreitas/awesome-quant),
[awesome-opensource-data-engineering](https://github.com/gunnarmorling/awesome-opensource-data-engineering),
[awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps),
[awesome-ai-agents](https://github.com/e2b-dev/awesome-ai-agents),
[awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers),
[awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills),
[awesome-mac](https://github.com/jaywcjlove/awesome-mac),
[Awesome-Linux-Software](https://github.com/luong-komorebi/Awesome-Linux-Software),
[Awesome-AI-Memory](https://github.com/IAAR-Shanghai/Awesome-AI-Memory),
[awesome-fintech](https://github.com/jplock/awesome-fintech),
[awesome-data-engineering](https://github.com/igorbarinov/awesome-data-engineering),
and [awesome-software-supply-chain-security](https://github.com/bureado/awesome-software-supply-chain-security).
Other lane-specific lists and rejected stale leads are recorded in their manifests.
Two truncated GitHub README responses were recovered with pinned raw bytes and
size checks; partial API text was not counted as complete coverage.

## Quality evaluation

We inspect each finalist's fit, source/license, maintenance, concrete code and
tests, upstream native workflow, dependency/security boundary, platform support
and reproducibility. These are evidence dimensions, not a fabricated weighted
leaderboard. A current release or a large star count cannot compensate for a
missing execution/data contract. Reading test code does not mean its tests ran.

Each decision is retain, conditional/investigate, omit from this default, or a
historical/discovery reference. A source-reviewed command is prospective until a
native receipt proves its scoped behavior. An accepted WSL receipt is not macOS
acceptance, hosted-product entitlement or proof of strategy performance.

Consequential findings include:

- LEAN remains the accepted baseline; default equity fill quantity realism needs
  separate calibration. PyBroker's Commons Clause and IID bootstrap assumptions
  prevent treating it as an unrestricted statistical upgrade. A reviewed
  FinRL-Trading execution path substitutes fallback symbols/prices/positions;
  it is rejected as an execution foundation.
- DeerFlow already includes LangGraph. Its stable release and main branch differ;
  adding a parallel orchestration owner creates work without proving value.
  OpenHands source and README disagree on minimum Node versions.
- Current Claude SDK package-registry and GitHub release versions differ.
  Source freshness is recorded separately from the accepted native environment.
  macOS MLX/Metal is a distinct backend acceptance, not CUDA parity.
- Marquez's default lacks authentication; DataHub adds substantial operating
  requirements; Soda Core v4 has an Elastic license boundary; harden-runner has
  telemetry/tier considerations. None is silently installed as a mandatory layer.
- Alpaca's installed Python request class drops advanced routing fields in the
  observed offline probe. API-rate marketing does not establish executed-trade
  throughput or account/data entitlement.

## Continue without losing evidence

Future agents should read the architecture and current open gates before adding
tools. Refresh a source because a decision depends on it; preserve its repository
identity, commit, file hashes, observed version, native command and limitation.
Register a new decision supplement in the central index rather than leaving it
outside validation. Archive superseded observations as dated evidence; do not
rewrite a historical failure as success or carry an old account failure forward
after a newer accepted run.

```sh
gh api --paginate 'users/seathatflowsinourveins/starred?per_page=100'
gh api --paginate 'orgs/alpacahq/repos?per_page=100&type=public'
python3 scripts/catalog_decisions.py --check
python3 scripts/validate_catalogs.py
python3 scripts/validate.py
```

Only public repository metadata is published. Native account identity, tokens,
session/process identifiers and complete conversation streams remain private.
