# Adopt the native stack on another machine

Start from a reviewed checkout, select capabilities, and record new local evidence. Historical receipts describe the authoring host; a clone does not inherit its logins, service state, tool discovery or acceptance.

For a single ordered new-machine walkthrough, use [the bootstrap page](bootstrap.md). It links each step to this reference's profiles below and to the per-platform page: [Linux/WSL2 x86_64](platforms/linux-wsl2.md) (accepted) and [macOS arm64](platforms/macos-arm64.md) (drafted, not accepted). Render native client configs for a selected host with [`tools/adoption/render_config.py`](../tools/adoption/render_config.py) and its [templates](templates/).

Use the [grand catalog handbook](../docs/grand-catalog-handbook.md) to connect
repository quality, native runtime review, profile selection and the current
[clean-install evidence](../blueprints/catalog-clean-install/README.md).

For daily Codex use, environment setup, reload decisions and the complete 24-repository token workflow, use the [session handbook](../docs/token-session-handbook.md). It maps native integration and upstream commands to the task that needs each capability.

The initial target is **Linux/WSL2 x86_64**. The SDK was recreated in a new prefix on the existing host with **Python 3.13.15 and uv 0.12.17**. A second physical machine, macOS, Windows-native and ARM are not accepted by that result. See [the receipt](receipt.json) and [SDK lock/replay](sdk/README.md).

## Choose a small starting profile

These adoption profiles select from the existing component catalog; they do not redefine its historical `core` profile.

| Adoption profile | Selects | Next native acceptance |
| --- | --- | --- |
| `foundation-cpu` | Codex, Claude Code, Context Mode, RTK, QMD BM25, explicitly scoped ai-memory, MCPorter | Native client setup; one useful context/document call and scoped memory retrieval |
| `research-runtime` | Historical hash-locked SDK/DuckDB, Dagu and LEAN comparison lane | Reproduce the retained comparison; this profile does not override the Nautilus destination |
| `trading-nautilus` | Selected pinned Nautilus engine and separate Alpaca boundary | Reproduce the bounded engine check; qualify SPY/LEAN parity and each broker independently |
| `observability` | Collector, Prometheus, Loki, Grafana, Alertmanager, ntfy | Native config validation, actual task/event delivery, matching usage categories |
| `semantic-rag` | HF, vLLM, Qdrant, SocratiCode | Hardware-compatible model serving, explicit project index and real retrieval/watcher behavior |
| `recovery` | Restic plus selected ai-memory/Qdrant application state | Isolated restore, logical comparison, independent key/destination, then explicit consumer cutover |

The [reference manifest](manifest.json) maps **every selected component ID** to its native guide, including optional components outside these starting profiles. The [offline HTML setup guide](../docs/ecosystem/index.html) generates current counts and embeds these recipes alongside layer/profile selection, scoped acceptance and measured baseline choices. The [lifecycle guide](lifecycle.md) covers ownership, restart, recovery and rollback. The [portability comparison](research.md) explains why native uv is the required dependency tool and other environment managers remain optional.

The [latest acceptance recipes](../blueprints/us-equities/acceptance-wave/README.md)
reuse that SDK for synthetic temporal data and offline Alpaca request models, plus
the existing LEAN build for fee/slippage sensitivity. They require new local
acceptance on a destination host and do not enable broker access.

## Ordered adoption

1. Clone this repository and select a reviewed Git commit. Read `AGENTS.md`; Claude's `CLAUDE.md` imports the same instructions. Record `git rev-parse HEAD` privately. Inspect upstream installers, version pins and checksums in the selected recipes.
2. Run the two portable integrity validators below. Choose explicit installation/project paths. Install only the selected native tools through their recipe links, preserving existing client settings.
3. Run the nonmutating prerequisite report. It reports executable presence, platform compatibility and recipe references. It never logs in, edits client configuration, starts services, executes catalog commands or certifies functional acceptance.
4. Recreate the SDK only for the research profile using the [transitive lock](sdk/README.md). Run useful local fixtures before any model request. Base tests can skip DuckDB-dependent checks; the locked SDK acceptance must retain test and skip counts.
5. Register selected plugins/MCP tools through each client's native commands. Resolve template placeholders deliberately. JSON/TOML strings do not generally expand shell variables. Select the memory workspace/project pair and explicit QMD/code-RAG project scope.
6. Use native sign-in on the target host. Then verify the actual client's tool discovery and one bounded useful call. Treat Linux Codex, Linux Claude and Desktop as separate client scopes. No authentication store is copied.
7. Add observability, GPU RAG or state recovery only if selected. Keep per-host results private using the [example state](host-state.example.json); every initial status is unknown or unselected. Publish only sanitized evidence when updating this reference repository.

From the checkout root:

```sh
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
"$PYTHON_BIN" scripts/adoption_status.py --profile foundation-cpu --json
# Or select the supported interpreter through native uv:
uv run --no-project --python 3.13 python scripts/adoption_status.py --profile foundation-cpu --json
# After the SDK recipe, use that environment to check research prerequisites:
"$SDK_ENV/bin/python" scripts/adoption_status.py --profile research-runtime --json
```

A prerequisite report exits 0 when the selected prerequisites are present, 2 when they are missing, unsupported or malformed. It does not probe accounts or services. Resolve failures through the mapped native recipes; running the report repeatedly cannot install anything.

Set `PYTHON_BIN` to the selected Python 3.13 interpreter. Dedicated native installations may deliberately be absent from `PATH`; use a session-local `PATH` containing only the selected installation directories when running the report. The accepted Dagu and .NET installs use explicit paths in their recipes. Missing command discovery does not mean those binaries are absent from disk.

For Loki on Linux x86-64, the report checks `loki` first, then the upstream archive's
`loki-linux-amd64` basename on that same `PATH`, following [Grafana's manual installation](https://grafana.com/docs/loki/latest/setup/install/local/).
It neither renames the binary nor executes it; executable presence still does not
establish its version, configuration or service health. Other platforms do not use
this Linux x86-64 fallback.

The [dated discovery check](../evidence/artifacts/native-claude-coop-20260921/loki-discovery.json)
retains actual before/after/absent-path reports: the old checker missed the
installed upstream basename, the corrected checker found it, and omitting its
directory still failed. These are local integration results, not a new Loki
service-health or model E2E claim.

For native account readiness, select explicit `NATIVE_CODEX_HOME`, `NATIVE_CODEX_BIN`, `RESEARCH_WORKSPACE` and a new private receipt filename; then use [the worker inspect command](../blueprints/us-equities/workers/README.md). If sign-in is needed:

```sh
CODEX_HOME="$NATIVE_CODEX_HOME" "$NATIVE_CODEX_BIN" login --device-auth
claude auth login
```

These are interactive account operations, separate from setup checks. Complete them through the provider's native UI. The September 19 initial SDK account-limit RPC returned **authentication required**. Native device sign-in then succeeded and a fresh readiness check passed. The subsequent [real paired acceptance](paired/README.md) completed Astra and Claude inference; initial failures remain dated evidence. New hosts still need their own sign-in and allowance.

## Native verification tiers

| Tier | Evidence required | Boundary |
| --- | --- | --- |
| Repository integrity | Both validators pass against the checked-out bytes | No installed-runtime claim |
| Prerequisites | Selected executable presence and supported platform/Python | No version, configuration, account or live-service claim |
| Native local behavior | Useful fixture result from selected upstream tools | No model-mediated or GPU claim |
| Client activation | Actual discovered tool plus a scoped call and relevant hook evidence | Each client and project checked separately |
| Native model task | Complete native result, terminal status and usage | Account readiness first; retain failures without repeated unchanged retries |
| Operational acceptance | Selected pipeline delivery, restore, or scheduled-run recovery | Per capability; a version/help check cannot substitute |

For Context Mode use the installed native plugin's doctor and actual tools; the existing [Desktop restart receipt](../observability/desktop-restart.md) proves direct tools on the original host. New hosts must verify their own loaded catalog. Current official Claude documentation distinguishes settings/hooks that reload live from startup-only choices; use native `/status` and hook views. For Codex startup/MCP registration changes, use a fresh relevant client/task and verify discovery. No blanket restart is needed for a documentation or QMD-index refresh. [Activation details](../docs/activation.md).

## Recovery and hosting

Transfer public configuration templates and explicitly selected private **application data** through the [native recovery guide](../blueprints/us-equities/state-recovery/README.md). Keep backup passwords/keys independently recoverable and outside Git. On a new machine restore into isolated locations, compare logical records, validate service compatibility, and only then select consumer endpoints. The existing same-host restore does not prove independent disaster recovery.

[Dagu hosting](../blueprints/us-equities/hosting/README.md) is the accepted manual local research lane. A user service starts only the selected local runtime; it cannot keep a stopped WSL VM running. Paid hosting, unattended schedules and broker orders remain separate operational choices. DeerFlow/ACP and OmniRoute have their own [blueprint evidence](../blueprints/us-equities/README.md); a routed text response does not prove native tools, hooks or model-session parity.

## Continue in a future session

Start with the [current 20-layer research queue](../catalogs/landscape/research-state.json)
and [continuation guide](../docs/landscape-continuation.md). They connect each
current selection to its evidence, next useful comparison and bounded stopping
rule. The [deployment comparison](../docs/hosting-container-practice.md) keeps
Docker/Compose and Podman conditional on a demonstrated requirement.

After the native observability services are accepted on the new host, install the
[grand dashboard and progress emitter](../observability/grand-dashboard/README.md)
using explicit checkout/config/data paths. Its native user timer refreshes public
checkpoint metadata automatically while the Linux/WSL user manager runs. It does
not transfer credentials or make another machine's historical results local E2E.
The current [seventeen-requirement map](../blueprints/us-equities/convergence-program/coverage.md)
and [program plan](../blueprints/us-equities/convergence-program/plan.json) identify
the next concrete acceptance without reloading the entire repository catalog.

Load `AGENTS.md`, this guide, then [the small continuation map](manifest.json). Follow [the update protocol](update.md) and only the layer needed for the task. Open gates remain in [the convergence ledger](../catalogs/us-equities/convergence-review.json); a new checkout cannot clear them. Distinguish latest upstream metadata from the compatible version actually accepted locally.

Primary references: [uv locking and synchronization](https://docs.astral.sh/uv/pip/compile/), [official Codex SDK](https://learn.chatgpt.com/docs/codex-sdk), [Codex authentication](https://learn.chatgpt.com/docs/auth), [Claude authentication](https://code.claude.com/docs/en/authentication), [Claude settings](https://code.claude.com/docs/en/settings).
