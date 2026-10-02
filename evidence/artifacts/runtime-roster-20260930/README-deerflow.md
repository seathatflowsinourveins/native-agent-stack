# DeerFlow bounded native qualification — 2026-09-30

The fresh private backend install passed 309 unchanged upstream unit tests. The separately installed GAIA grader passed its eight unchanged scorer unit tests. The backend dependency checker still exits 1 for the explicit upstream WebSocket override, so this record is partial native qualification. Actual sanitized returned output and all exits are in [deerflow-native.json](deerflow-native.json).

The selected source remains **bytedance/deer-flow v2.1.0**, commit `345f08be00c8a9495079b732a39b46aa9af1584e`. The current release API returned v2.1.0; the downloaded archive and both recipe lockfile hashes matched [pins.json](../../../blueprints/runtime-workers/deerflow/pins.json). Source byte comparison after execution found no changes in any of its 2,964 originally shipped regular files.

| Check | Native command / selection | Exit | Returned result |
| --- | --- | ---: | --- |
| Backend installation | `rtk uv sync --locked --python 3.13` in the pinned backend | 0 | Installed 227 packages |
| Backend unit subset | `rtk uv run --no-sync python -m pytest -m "not live" tests/test_model_factory.py tests/test_mcp_client_config.py tests/test_client.py -q` | 0 | 309 passed, 1 warning in 8.84s |
| Installed CLI | `rtk uv run --no-sync deerflow --help` | 0 | Native terminal-workbench options returned |
| Backend dependencies | `rtk uv pip check --python <backend-venv>/bin/python` | 1 | langgraph-sdk requires websockets >=14,<16; 16.0 installed |
| Grader installation | Existing `recipe.py:install_grader` helper into a fresh prefix | 0 | Exact inspect-ai 0.3.271 / inspect-evals 0.22.0; pip check found no broken requirements |
| Grader scorer subset | `rtk uv run --no-sync python -m pytest tests/gaia/test_scorer.py -q` in the pinned Inspect Evals source | 0 | 8 passed, 1 warning in 0.22s |
| Grader dependencies with dev runners | `rtk uv pip check --python <grader>/bin/python` | 0 | 110 installed packages compatible |

Upstream supports the locked backend installation in [backend/Makefile:5–6](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/Makefile#L5-L6) and the non-live pytest lane in [Makefile:22–29](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/Makefile#L22-L29). The metadata incompatibility comes from the unchanged [explicit WebSocket override](https://github.com/bytedance/deer-flow/blob/345f08be00c8a9495079b732a39b46aa9af1584e/backend/pyproject.toml#L91-L106). Its explanation is source evidence; the failed dependency check remains recorded.

GAIA uses **UKGovernmentBEIS/inspect_evals v0.22.0**, commit `41c72eaa2b807ce43f35fac6f3f399318adc7e9d`, and its original [tests/gaia/test_scorer.py](https://github.com/UKGovernmentBEIS/inspect_evals/blob/41c72eaa2b807ce43f35fac6f3f399318adc7e9d/tests/gaia/test_scorer.py). The [GAIA README](https://github.com/UKGovernmentBEIS/inspect_evals/blob/41c72eaa2b807ce43f35fac6f3f399318adc7e9d/src/inspect_evals/gaia/README.md#L14-L26) supplies the install method; the existing recipe supplies the unchanged wheel-only hash lock. Native pytest runner versions came from the same source's [dev dependencies](https://github.com/UKGovernmentBEIS/inspect_evals/blob/41c72eaa2b807ce43f35fac6f3f399318adc7e9d/pyproject.toml#L421-L440) and [uv.lock](https://github.com/UKGovernmentBEIS/inspect_evals/blob/41c72eaa2b807ce43f35fac6f3f399318adc7e9d/uv.lock). The recipe's Inspect AI 0.3.271 differs from the source lock's 0.3.263; the source lock was preserved, not synced in full.

The installed grader scorer bytes matched the pinned scorer source. Independent archive comparison confirmed all 3,973 originally shipped Inspect Evals regular files unchanged. Both native pytest commands also ran before their required test dependencies existed and returned exit 1 (“No module named pytest”); those prerequisite controls and their later passing runs are retained separately.

These are upstream unit tests, including their upstream mocks and synthetic scorer targets. Other backend suites, live APIs, Docker services, server lifecycle, MCP connections, native worker skill discovery, gated GAIA data and model execution were not exercised. Provider usage is unknown. Local archive/hash observations and the local grader installer remain distinct from the upstream pytest results.

Installation, tests, installed help and dependency checks used a newly created private prefix, fresh HOME/XDG/cache/state paths and an explicit environment without provider credential variables. Grader tests set `HF_HUB_OFFLINE=1`, `HF_DATASETS_OFFLINE=1` and `UV_PROJECT_ENVIRONMENT=<grader>`. Raw returned streams remain private; this public receipt substitutes paths, strips color and labels every output projection. No global configuration or service activation occurred.

One recorder correction is retained: the archive extraction originally recorded a shortened relative archive argument; it now names the actual absolute argument with a private-path placeholder. The original private record hash and verification path are in the receipt. No test was replayed.
