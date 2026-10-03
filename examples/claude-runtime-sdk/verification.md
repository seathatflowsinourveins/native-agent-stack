# Claude SDK integration verification, 2026-09-30

This record covers the source-derived runner and local checks. Live gateway
requests, provider identity, skill/tool activation, native session recovery and
framework selection require the coordinator's separate acceptance receipt.
No model run was performed by this implementation worker.

## Primary sources and installed observations

| Source | Pin and observation | Applied boundary |
| --- | --- | --- |
| [Claude Agent SDK Python](https://github.com/anthropics/claude-agent-sdk-python/tree/f2204bb956bab02907aaf3cb88eb9dead28eaa35) | `v0.2.162`, commit `f2204bb956bab02907aaf3cb88eb9dead28eaa35`; annotated tag `bd22c3a79ebee022589212c62f09bc061e225523` dereferenced through `gh api` | Official client, options, transport, skill selection and session/interrupt API |
| [SDK release](https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.162) | Published 2026-09-29; bundles Claude CLI 2.1.285; installed coordinator `claude --version` also returned 2.1.285 | A version match, not a provider/tool/skill acceptance result |
| [Native SDK source](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/client.py) | `ClaudeSDKClient.query`, `receive_response`, `interrupt` and context-manager cleanup | One SDK query; no custom model loop, retry or implicit resubmission |
| [Native skill transport](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/src/claude_agent_sdk/_internal/transport/subprocess_cli.py) | `_apply_skills_defaults`, `_build_command` and shielded cleanup | `skills="all"` or exact names; native setting sources, permission grants and local plugins |
| [OmniRoute launcher](https://github.com/diegosouzapw/OmniRoute/blob/2f42a9ac19d1a247ec9ce5473b790843724b3061/bin/cli/commands/launch.mjs#L23) | `2f42a9ac19d1a247ec9ce5473b790843724b3061`, `buildClaudeEnv`; original tracked blob also inspected in the published source checkout | Worker-process `ANTHROPIC_*` filtering, loopback root, documented keyless sentinel and gateway model discovery; fixed compaction-window override excluded |
| [Devin bridge usage and serialization](https://github.com/diegosouzapw/OmniRoute/tree/2f42a9ac19d1a247ec9ce5473b790843724b3061/open-sse/executors/devin-agentic) | Same OmniRoute pin, `types.ts::estimateTokens` and `serializer.ts::boundedToolResult` | Text-length estimates and a marked 65,536-character tool-result cap; no measured-cache or complete-provider-usage claim |
| [uv scripts](https://docs.astral.sh/uv/guides/scripts/#locking-dependencies) | Installed uv 0.12.17; `uv lock --help` reports `--script`; native lock resolved 32 packages | PEP 723 installation and `worker.py.lock`; no shared environment synchronization |

The main-model route is an advertised candidate, not an accepted replacement
for the native coordinator model. The runner rejects a non-Claude-family ID and
does not silently substitute one. Native capability configuration is distinct
from activation evidence.

## Returned checks

Raw commands and returned logs are retained in the coordinator's private owned
run prefix. Public records omit personal paths, tool inputs/outputs, prompts and
credential values. Local synthetic strings are fixtures, not copied secrets.

| Check | Evidence class | Returned result |
| --- | --- | --- |
| `uv lock --script examples/claude-runtime-sdk/worker.py --default-index https://pypi.org/simple --no-sources` | Native installation artifact | Exit 0; 32 packages resolved |
| `uv run --frozen --script examples/claude-runtime-sdk/worker.py --preflight` | Configuration only | Exit 0; pinned SDK, effort max, Claude preset/full toolset, loopback root, selected sources and skill metadata policy; no model request |
| Same preflight with `--model gpt-6.1-sol` | Discriminating configuration control | Exit 2; non-Claude family rejected, no substitution |
| `python -m unittest discover -s examples/claude-runtime-sdk/tests -v` through pinned SDK `uv run --with` | Local synthetic integration | Initial two runs: 19 tests, one failure and one error, exit 1; corrected run: 21 tests, exit 0; transport-auth extension: 24 tests, exit 0 in 0.151 seconds |
| `python examples/claude-runtime-sdk/tests/check_controls.py --disarm-route` | Synthetic fault injection | Exit 1; same route oracle selected one test and five disarmed invalid-route cases failed |
| Same route oracle without `--disarm-route` | Local integration control restored | Exit 0; one selected test passed |
| Official checkout `uv sync --extra dev --python 3.13.15`, then unchanged CI command `python -m pytest tests/ -v --cov=claude_agent_sdk --cov-report=xml` | Unchanged upstream tests; development installation via uv | Exit 0; 1,587 passed and six skipped in 28.46 seconds; Linux, CPython 3.13.15, MCP 2.2.0, AnyIO 4.15.1, pytest 9.1.1 |

The upstream run used the exact tagged source and its declared developer extra.
The test command is from the pinned
[`.github/workflows/test.yml`](https://github.com/anthropics/claude-agent-sdk-python/blob/f2204bb956bab02907aaf3cb88eb9dead28eaa35/.github/workflows/test.yml).
Five skips occurred during collection; the sixth was
`TestRecompressWheel.test_zopfli_keeps_every_member`. The native `-v` output did
not include reasons for the five collection skips. The official provider E2E,
Docker E2E and example jobs were not run. These upstream unit tests do not attest
OmniRoute acceptance. The standalone script's observed default Python was
3.14.7; that is distinct from the upstream CI-aligned 3.13.15 test environment.

## Corrections and verification paths

1. **Script locking:** the installed modern-python skill said PEP 723 scripts
   have no lockfile. Installed uv 0.12.17 `lock --help`, the official script guide
   and the returned successful native lock establish support for a script lock.
2. **Native resume argv:** the first local fixture assumed `--resume UUID`.
   Pinned `subprocess_cli.py` deliberately uses `--resume=UUID` to prevent
   dash-leading argument injection. The test now checks the actual native argv.
   The runner already passed the supported `resume` option and was unchanged.
3. **Settings-read fixture scope:** the first fixture rejected every
   `Path.read_text` call, also blocking Python's package-version metadata read.
   It now rejects reads of the supplied caller MCP configuration specifically,
   while allowing package metadata. This correction changed the test oracle.
4. **Sparse source access:** a missing local `launch.mjs` path came from the
   coordinator's sparse checkout. `rtk proxy git show HEAD:bin/cli/commands/launch.mjs`
   recovered the tracked primary blob. Missing worktree files are not evidence
   that the upstream capability is absent.
5. **Gateway login boundary:** a base URL alone does not implement the selected
   upstream launcher semantics. The runner now adopts the documented keyless
   loopback sentinel and native-auth key filtering before connecting. Native
   credentials are not carried into the gateway child by accident. The parent
   retains its first bounded failed live attempt separately, including unknown
   usage when no native usage result was returned.
6. **Synthetic session identity publication:** the first publication check
   rejected the test's literal synthetic UUID as a possible private session
   identifier. The fixture now constructs its deterministic identity with
   `uuid.uuid5`; no native session identifier was used or copied. The publication
   guard remains unchanged.

## Usage and lifecycle limits

The local suite exercises a native-client-shaped synthetic control fixture,
not a real child-process or provider cancellation claim. Timeout/interrupt and
fresh successful synthetic work remain separate from native session resume.
The unchanged upstream suite covers its own native transport lifecycle cases.

Last native usage fields and the latest model-usage snapshot stay separate;
cumulative snapshots and cache subsets are not summed. Gateway-supplied counts
must be corroborated before treating them as provider measurements or native
cache savings. A reported native list cost is not billing, and missing counters
remain unknown. Executor/advisor totals require independent reconciliation.

The publication decision remains a bounded integration trial. Full installed
skill coverage, role/subagent routing, MCP/plugin/hooks, recovery and the sealed
three-arm SDK comparison gate are not established by these tests.
