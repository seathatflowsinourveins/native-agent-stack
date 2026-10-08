# Hindsight research memory

Hindsight 0.10.2 stores research hypotheses and experiment records in the
`trading-research` bank. ai-memory remains the native clients' coding memory.
The [landscape job](../manifests/landscape.json) names this role; the
[sanitized receipt](../evidence/artifacts/hindsight-research-memory-20261008/receipt.json)
records the installation, synthetic numeric round trip and later native
Claude-to-Codex round trip. These checks establish the exercised integration,
not research recall quality or trading results.

Source: [vectorize-io/hindsight v0.10.2](https://github.com/vectorize-io/hindsight/tree/5fc4ce20917b916240cef27c212c387a177f115b),
commit `5fc4ce20917b916240cef27c212c387a177f115b`. Use its
[pip installation](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/installation.md#L229):

```sh
python3.13 -m venv ~/.local/share/hindsight/venv
~/.local/share/hindsight/venv/bin/pip install hindsight-api==0.10.2 hindsight-client==0.10.2
```

The accepted host uses the vendor's documented configuration in its private
`~/.local/share/hindsight/stage.env`. The keys below have prefix
`HINDSIGHT_API_`; citations refer to the pinned
[configuration reference](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/configuration.mdx).

| Keys | Accepted values | Vendor lines |
| --- | --- | --- |
| `DATABASE_URL` | `pg0://memory-h2h-trading-research` | 26,38 |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL` | `openai-responses`, `cx/gpt-6.1-sol`, `http://127.0.0.1:21128/v1` | 277–280 |
| `LLM_API_KEY`, `LLM_DEFAULT_HEADERS` | Nonsecret placeholder for this keyless loopback gateway; JSON lane-session header | 278,305 |
| `EMBEDDINGS_PROVIDER`, `EMBEDDINGS_LOCAL_MODEL`, `EMBEDDINGS_LOCAL_FORCE_CPU` | `local`, `BAAI/bge-small-en-v1.5`, `true` | 845,849,851 |
| `RERANKER_PROVIDER`, `RERANKER_LOCAL_MODEL`, `RERANKER_LOCAL_FORCE_CPU` | `local`, `cross-encoder/ms-marco-MiniLM-L-6-v2`, `true` | 1182,1188,1191 |
| `HOST`, `PORT`, `MCP_ENABLED`, `MCP_LOCAL_BANK_ID` | `127.0.0.1`, `8888`, `true`, `trading-research` | 1529–1530,2388,2392 |
| `RETAIN_EXTRACTION_MODE` | `verbatim`; startup LLM verification enabled | 1708,1967,2487 |

The [user-unit template](../adoption/templates/systemd/hindsight-research.service)
runs the vendor CLI with that environment file. Its
[MCP drop-in](../adoption/templates/systemd/hindsight-research.service.d/10-mcp-tools.conf)
sets the vendor `HINDSIGHT_API_MCP_ENABLED_TOOLS` allowlist
([config.py:680](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/config.py#L680)).
The [immutable-source review](../evidence/artifacts/hindsight-research-memory-20261008/review-resolution.json)
records independently matched GitHub blob hashes and exact configuration
locators; `config.py:4792–4794` parses the allowlist at the same pin.
The [nonsecret allowlist environment file](../adoption/templates/systemd/hindsight-research.mcp-tools.env.template)
is copied to `~/.local/share/hindsight/mcp-tools.env`. The drop-in reads it
after the base unit's `stage.env`: systemd's later `EnvironmentFile=` values
override earlier files and all `Environment=` assignments
([systemd v259](https://github.com/systemd/systemd/blob/v259/man/systemd.exec.xml)).
It exposes 15 tools: `retain`, `sync_retain`, `recall`, `reflect`,
`list_memories`, `get_memory`, `list_tags`, `get_bank`, `list_documents`,
`get_document`, `list_operations`, `get_operation`, `list_mental_models`,
`get_mental_model` and `get_knowledge_base_tree`. Delete, clear, update and
directive tools are excluded. The host operator installs the template and
drop-in under `~/.config/systemd/user/`, then runs `daemon-reload` and
`enable --now hindsight-research.service`; stop an existing foreground
instance first. The template now orders startup after and requests
`omniroute.service`, and retries crashes with `Restart=on-failure` and
`RestartSec=5s` ([systemd v259](https://github.com/systemd/systemd/blob/v259/man/systemd.service.xml)).
Ordering establishes unit startup order, not HTTP readiness. Hindsight's
[startup verification](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-api-slim/hindsight_api/engine/memory_engine.py#L5371)
warns and continues if the gateway is unavailable. These template fixes
require a separate host-operator apply; the historical receipt preserves
the previously installed forms. This publication changes no live unit.

The bank HTTP MCP endpoint is `http://127.0.0.1:8888/mcp/trading-research/`.
The accepted host's operator registered it with the native clients:

```sh
claude mcp add --scope user --transport http hindsight http://127.0.0.1:8888/mcp/trading-research/
codex mcp add hindsight --url http://127.0.0.1:8888/mcp/trading-research/
```

Use `sync_retain` to wait for storage before a receiver recalls the record.
Research jobs pass **`types: ["world", "experience"]`** to recall verbatim
records: `observation` records are synthesized paraphrases. `verbatim`
preserves the original text while the LLM extracts metadata; automatic
consolidation can also make model calls. For experiment isolation, pass the
experiment's tags and `tags_match: "all_strict"`; this requires every tag and
excludes untagged records, while allowing additional tags
([vendor tag semantics](https://github.com/vectorize-io/hindsight/blob/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/docs/developer/api/recall.mdx#L294)).

**Recall cannot hard-filter by time. Backtest research never relies on it for
point-in-time exclusion.** The native host receipt records `/health` HTTP 200,
15 returned MCP tools and byte-equal source/receiver text; reuse that evidence
when its inputs match instead of describing a receipt read as a new run.

Inverse: remove the native clients' Hindsight registrations, run
`systemctl --user disable --now hindsight-research.service`, remove the unit
and its drop-in and allowlist environment file, then `systemctl --user daemon-reload`. The vendor foreground
start remains available with the existing private environment file. For full
retirement, stop the server before removing its venv and owned named pg0
instance; deleting that database deletes the bank. The accepted instance is
`~/.pg0/instances/memory-h2h-trading-research/`, observed at runtime and matching
[pg0-embedded 0.15.2](https://github.com/vectorize-io/pg0/blob/v0.15.2/README.md#L365).
