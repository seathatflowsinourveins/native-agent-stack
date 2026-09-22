# Same-host clean-prefix audit — 2026-09-21 America/New_York

Checkout: `dac2d1a3f880c04f6afadebe8bf3a251a64ab605`.
Scope: read-only checkout; one fresh SDK prefix on the existing Linux/WSL host. No model/API calls, broker operations, logins, client configuration, GPU/Docker/system installations, or service changes.

## Results

- Existing official uv 0.12.17 and installed CPython 3.13.15; Linux x86_64, WSL2 kernel 6.18.33.2-microsoft-standard-WSL2, glibc 2.39.
- Fresh prefix created; native uv fetched and installed all 36 distributions from public PyPI with required hashes, no builds, no cache, and configuration discovery disabled. Lock contains 867 accepted SHA256 artifact hashes.
- Lock SHA256: `f5bb7b8cf4406c5d408cce4083995cd29d4a34066f9d2aedb585837cc8536c5f`.
- Native package check passed: all 36 distributions compatible.
- Exact installed name/version set equals lock. No extra/missing/version mismatches. User-site and system-site imports disabled. Seven real package imports resolve inside the new prefix (openai_codex, openai, alpaca, exchange_calendars, duckdb, pandas, numpy). All six worker SDK symbols imported. DuckDB SQL actually returned expected value.
- Portable integrity passed: 68 components, 1454 hashed files, 4 historical catalog profiles, 128 receipts.
- Catalog integrity passed: 152 historical entries, 147 unique historical repos, 342 historical public stars, 20 models. These are validator-specific historical catalog counters, not current landscape/star-freshness counts.
- Full existing suite: 766 executed, 763 passed, 1 error, 2 skipped. The error arose because this audit's deliberately minimized process environment omitted HOME, whereas test_native_token_ci.py:101 assumes the original native HOME is available. Preserve the failure; it is an audit harness configuration error, not a package import/install failure.
- Only that failed test was rerun, with native HOME inherited unchanged and no authentication variables loaded: 1/1 passed. No passing test or package install was repeated. Do not describe the original 766-test run as wholly passing.
- Two skips: EdgarTools runtime absent (its intentionally separate recipe environment), and QEMU unavailable (hosted preflight retained separately).
- Useful data test groups passed with actual fresh-prefix packages: financial-data 16, catalyst-dataset 14, point-in-time 13, nanosecond-replay 12; total 55. These are local fixture/integration tests, not new provider data or broker E2E.
- Checkout status was empty before and after, including untracked files.

## Per-host adoption matrix

| Profile | This audit's ordinary PATH result | New host still needs |
| --- | --- | --- |
| foundation-cpu | All named commands and recipe references present | Selected native binaries and Node24/Python3.13; explicit paths; native Codex/Claude account sign-in; native plugin/MCP/hook discovery and one useful call per client/project; scoped QMD and ai-memory state. No clone transfers accounts or state. |
| research-runtime | All recipes present; dagu and dotnet not found on this PATH | Fresh SDK and data fixtures; separately pinned Dagu, .NET/physical LEAN source build and dependency patch/locks; separate skfolio and EdgarTools environments; systemd user manager and controlled paths. Native workers require account allowance; SEC/data operations require declared identity/entitlements. LEAN remains the historical comparison lane. |
| semantic-rag | All named commands and recipes present | Compatible NVIDIA driver/device/free memory; pinned model/license (~2.3GB download), vLLM0.25.0 working dependency stack, Qdrant storage/ports, retained MCPorter connection, explicit project index. Verify real embeddings/retrieval and add/change/delete watcher behavior. Presence does not prove GPU compatibility. |
| observability | All recipes present; all eight named commands absent from this PATH | Pinned native assets, Linux filesystem state/config paths, running systemd user manager, unused loopback ports, generated private Grafana credentials, native config checks, actual scrape/export/task-event/notification checks, per-client telemetry scope. A stopped WSL VM stops services. |
| recovery | Named command and recipes present | Deliberately selected private application data, independently recoverable key and destination, isolated restore, logical and query comparisons, compatible service versions, explicit endpoint/consumer cutover. Existing same-host records do not certify this destination. |
| trading-nautilus | Named commands and recipes present | Dedicated supported CPython3.12–3.14 environment and pinned Nautilus wheel/source; Bubblewrap/kernel isolation support and fixture replay; explicit broker paper endpoints/accounts/permissions and deterministic risk/reconciliation. SPY/LEAN parity, native in-flight faults/streaming and IBKR remain open despite separate AAPL diagnostic and bounded Alpaca paper smoke on the original host. |

A missing PATH command is not proof its binary is absent from disk. This audit intentionally did not search private installation trees or amend PATH. The prerequisite report never probes runtime versions, service health, accounts, GPU, hooks, or brokers; its runtime_acceptance_verified flag is false. Baseline differs is expected because the manifest keeps its historical parent publication anchor.

## Portable recipe assessment

The exercised SDK recipe works from only tracked checkout content plus the explicitly required official uv/interpreter and public package source. It does not depend on an untracked repository environment or the author's credential paths. Inspected adoption/recipe files contain no literal author home paths. Placeholders and selected native prefixes are deliberate destination inputs.

This is not a universal all-stack lock: SDK dependencies exclude separately qualified skfolio, EdgarTools, Nautilus, npm/native tools, GPU stack, and operating-system services. Those use their mapped recipes. Immutable source/artifact pins establish identity; package availability and compatible host/kernel/driver behavior remain destination checks.

Current documentation ambiguity to correct:
- blueprints/us-equities/engine-nautilus/README.md:23 says all planned stages remain unexecuted; its linked acceptance-plan.md:3–20 and catalogs/us-equities/runtime-target.json now distinguish completed AAPL/bounded Alpaca from open SPY/LEAN/broader fault/IBKR work.
- blueprints/us-equities/engine/README.md:3 still says it selects LEAN; new-machine adoption correctly identifies it as the retained historical comparator.

## Evidence

`commands.json` records exact command arguments, start times, duration, exit and hashes of each redacted transcript. `source-manifest.json` retains source/runtime hashes and environment policy. Logs 00–12 retain successes, initial failure, skips, warnings and targeted recovery. The private `replay.py` and `recover_environment.py` are audit-only orchestrators, not proposed repository tooling. No public files were edited.

Model/effort: inherited. Provider usage: unavailable.
