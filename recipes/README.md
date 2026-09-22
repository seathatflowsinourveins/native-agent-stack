# Portable native recipes

This guide contains the shared native recipes. The [adoption recipe map](../adoption/manifest.json) covers all 68 selected components in [the stack manifest](../manifests/stack.json), including specialist observability, research, application and recovery guides. Start with [new-machine adoption](../adoption/README.md) for ordered CPU-first setup. The [September 21 upgrade recipe](native-upgrades-20260921.md) supplies current candidate paths, returned results and rollback for ccusage, Repomix, OpenResearch and Worktrunk. These are not a universal installer, and a help/version command is not functional acceptance. Historical host results remain in [the evidence manifest](../manifests/evidence.json).

The examples target Linux/WSL x86_64. Use a current native Node.js 24, npm, Python 3.13, uv, Git and GitHub CLI as applicable. GPU serving additionally requires a compatible NVIDIA driver and enough free device memory. Desktop's Linux runtime and native Codex can have different configuration homes: run each client's own supported setup in its intended home, without copying authentication files between them.

## Recipe index

| Recipe | Scope |
| --- | --- |
| [Native Claude profile](claude-native-profile.md) | Terminal entry, small persistent instructions, selected skills and new-PC checks for native Claude Code |
| [Native Claude Ultracode](claude-native-ultracode.md) | Workflow profile, task-matched worker models and effort, concurrency cap, sessions, messaging and dashboards |
| [Claude/Codex cooperation lanes](claude-codex-cooperation-lanes.md) | Explicit cross-family review, live-session messaging and the Codex agent-role registration |
| [Claude/Codex foreground review](claude-codex-foreground-review.md) | The accepted foreground `/codex:review` path from a dedicated checkout |
| [Native upgrades (2026-09-21)](native-upgrades-20260921.md) | Dated upgrade commands, including Worktrunk worktree creation and removal |
| [Tavily](tavily.md) | Tavily CLI installation, sign-in and returned results |
| [SOTA convergence practice](sota-convergence-practice.md) | Reproducible dated repository-convergence recipe (`tools/sota-convergence/`): when to rerun, the six commands, evidence classes, the never-promote rule, and the cross-family review/PR/CI step. |

## Paths, pins and installation conventions

Set these in the current shell, replacing the project path with this clone's absolute path:

```sh
STACK_HOME="$HOME/.local/share/native-agent-stack"
PROJECT_ROOT=/absolute/path/to/native-agent-stack
MODEL_DIRECTORY="$STACK_HOME/models/nemotron-3-embed-1b-c0c9fea"
MCPORTER_CONFIG="$STACK_HOME/config/mcporter.json"
QDRANT_CONFIG="$STACK_HOME/config/qdrant.yaml"
QMD_INDEX=native-stack-docs
QMD_COLLECTION=native-stack-docs
mkdir -p "$STACK_HOME/tools" "$STACK_HOME/downloads" "$STACK_HOME/bin" "$STACK_HOME/config" "$STACK_HOME/state" "$STACK_HOME/output"
cd "$PROJECT_ROOT"
```

Each npm command below installs into a separate prefix. Invoke its executable from that prefix's `bin/`, or add only the selected prefix to the current shell's PATH. A direct symlink into `$STACK_HOME/bin` is also suitable if that name is unused. Preserve existing commands and rollback prefixes; do not replace Node, npm or an account's default model. npm lockfiles and registry integrity belong with their prefix. Review package lifecycle scripts before permitting them; native packages such as ast-grep and agent-browser may need their upstream native-binary setup. `--ignore-scripts` is appropriate only where explicitly shown below.

The `.example` files in [examples](../examples/) are inactive. Replace every `/ABSOLUTE/...` placeholder before selectively merging a file. **JSON and TOML do not expand shell variables.** The service templates also use literal absolute paths; there is no implicit `${STACK_HOME}` substitution in `ExecStart`. Keep private paths, local receipts and authentication out of commits.

### Official release archives

For an archive entry in the catalog, use its linked release and the following native workflow. `ASSET` must be the actual Linux x86_64 asset selected from that release; never substitute a similarly named third-party binary. This deliberately requires choosing an asset for the target OS rather than downloading all platforms.

```sh
REPOSITORY=rtk-ai/rtk
RELEASE=v0.49.0
ASSET=rtk-x86_64-unknown-linux-musl.tar.gz
PREFIX="$STACK_HOME/tools/rtk-0.49.0"
gh release view "$RELEASE" --repo "$REPOSITORY" --json tagName,assets
mkdir -p "$PREFIX" "$STACK_HOME/downloads/rtk-0.49.0"
gh release download "$RELEASE" --repo "$REPOSITORY" --pattern "$ASSET" --dir "$STACK_HOME/downloads/rtk-0.49.0"
gh release download "$RELEASE" --repo "$REPOSITORY" --pattern checksums.txt --dir "$STACK_HOME/downloads/rtk-0.49.0"
# In the download directory, check the exact asset against the publisher's checksum.
# Inspect archive members before extracting into the empty versioned prefix.
cd "$STACK_HOME/downloads/rtk-0.49.0"
sha256sum --check --ignore-missing checksums.txt
tar -tf "$ASSET"
tar -xf "$ASSET" -C "$PREFIX"
cd "$PROJECT_ROOT"
```

Do not treat a checksum file containing no matching asset as success. Archive filenames/checksum formats vary by publisher; the RTK example is exact for RTK, not a universal release script. Preserve bundled licenses and third-party notices. Four recorded archive hashes provide additional fixed references:

| Repository / release | Linux x86_64 asset | SHA-256 |
| --- | --- | --- |
| openai/codex / rust-v0.155.1 | `codex-package-x86_64-unknown-linux-musl.tar.gz` | `a65b895c6ac1a73629bbe4b864640c86133e94a43b4d67b3103044e1a306d5a2` |
| Wilfred/difftastic / 0.71.0 | `difft-0.71.0-x86_64-unknown-linux-gnu.tar.gz` | `61aea5394a53c56f144637cf39b3a0c0dafa27769731745e5851ff276e6478da` |
| gitleaks/gitleaks / v8.30.1 | `gitleaks_8.30.1_linux_x64.tar.gz` | `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |
| qdrant/qdrant / v1.19.1 | `qdrant-x86_64-unknown-linux-musl.tar.gz` | `70a40529e2ebe0a2787d574d3a2e28437cfe94f26f24fa419f6ac57b4ae817c9` |

Keep the **complete Codex package**, including its code-mode host and resources. Qdrant's binary archive may omit its license: retain the unmodified [v1.19.1 upstream LICENSE](https://github.com/qdrant/qdrant/blob/v1.19.1/LICENSE) beside the binary.

## Component catalog: install and check

Commands assume the selected upstream executable is on the current shell's PATH. Workflow labels link to the concrete sequences below. A catalog entry's profile comes from the manifest; no optional provider campaign is implied.

| Component ID / pin | Pinned upstream installation | Native reproduction and scope |
| --- | --- | --- |
| `affaan-m/ECC` · `dd6ee538aee0f548d4a6b520118f875431fd749e` | `git clone https://github.com/affaan-m/ECC.git "$STACK_HOME/tools/ECC"`, then `git -C "$STACK_HOME/tools/ECC" checkout --detach dd6ee538aee0f548d4a6b520118f875431fd749e` | Optional reference: read only `skills/search-first/SKILL.md` or `skills/iterative-retrieval/SKILL.md` when useful. `git rev-parse HEAD` verifies the source pin, not a runtime. Do not install the whole catalog. |
| `agent-browser` · `0.38.1` | `npm install --global --prefix "$STACK_HOME/tools/agent-browser-0.38.1" agent-browser@0.38.1`; upstream `agent-browser install` downloads its browser; `--with-deps` additionally installs OS dependencies | [Browser workflow](#browser-workflow). Official skill content: `agent-browser skills get core`; load on demand. |
| `agentsview` · `0.43.0` | Official [kenn-io/agentsview v0.43.0](https://github.com/kenn-io/agentsview/releases/tag/v0.43.0) archive; select the host asset through `gh release view v0.43.0 --repo kenn-io/agentsview --json assets`, then the archive procedure | [History workflow](#history-and-usage). Explicit authorized archive scope is required; a blank archive is not evidence of zero historical usage. |
| `ai-memory` · `2.3.2` | Official [akitaonrails/ai-memory v2.3.2](https://github.com/akitaonrails/ai-memory/releases/tag/v2.3.2) archive; `gh release view v2.3.2 --repo akitaonrails/ai-memory --json assets`; retain its native hooks and packaging files | [Memory setup and workflow](#project-memory). Back up existing data privately before replacing a running version; native status/search and direct MCP passed for this update. Earlier model receipts retain their original scope. |
| `ast-grep` · `0.45.3` | `npm install --global --prefix "$STACK_HOME/tools/ast-grep-0.45.3" @ast-grep/cli@0.45.3` | `ast-grep run --lang javascript --pattern 'function $NAME($$$ARGS) { $$$BODY }' --json=compact --stdin < evidence/artifacts/usage-report.source.txt`. `--stdin` is intentional because this JavaScript fixture has a `.txt` suffix. |
| `ccusage` · `20.0.24` | [Qualified isolated-prefix installation](native-upgrades-20260921.md#installation) with explicit candidate executable | [History and usage](#history-and-usage). Read existing logs; never manufacture provider usage by replaying a receipt. |
| `claude-code` · `2.1.278` | Download the [official native installer](https://code.claude.com/docs/en/setup) with `curl -fsSL https://claude.ai/install.sh -o "$STACK_HOME/downloads/claude-install.sh"`; inspect it, then `bash "$STACK_HOME/downloads/claude-install.sh" 2.1.278` | `claude --version` verifies installation. A real [native client pass](#native-client-acceptance) requires the user's normal signed-in account. Native auto-update can subsequently change this installed version. |
| `claude-hud` · `0.8.0` | `claude plugin marketplace add jarrodwatts/claude-hud@v0.8.0 --scope user`; `claude plugin install claude-hud@claude-hud --scope user --json` | Optional: run `/claude-hud:setup` inside a fresh Claude session. Preserve any existing statusline before choosing the documented integration. A representative input render validates formatting only, not live context or savings. |
| `codebase-memory-mcp` · `0.11.0` | Official [DeusData/codebase-memory-mcp v0.11.0](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0), asset `codebase-memory-mcp-linux-amd64.tar.gz`; recorded SHA-256 `032b33c1833919a2d1de67ff6367fa6ea46aee8689c86ef223c88fae3b6e4536` | [Static code graph](#static-code-graph). Invoke the binary directly; its all-client auto-installer is unnecessary. |
| `codex` · `0.155.1` | Official [openai/codex rust-v0.155.1](https://github.com/openai/codex/releases/tag/rust-v0.155.1), complete package and hash above. Supported package-manager alternative: `npm install --global --prefix "$STACK_HOME/tools/codex-0.155.1" @openai/codex@0.155.1` | `codex --version`, then [native client acceptance](#native-client-acceptance). Preserve the existing account, model, approval policy and sandbox settings. |
| `codex-for-claude` · `1.0.6` / `db52e28f4d9ded852ab3942cea316258ae4ef346` | `claude plugin marketplace add openai/codex-plugin-cc@v1.0.6 --scope user`; `claude plugin install codex@openai-codex --scope user --json` | Optional: `/codex:setup` and `/codex:status` inside Claude. [Bridge scope](#optional-codex-for-claude). A status handshake does not consume a Codex model task or prove one completed. |
| `context-hub` · `0.1.4` | `npm install --global --prefix "$STACK_HOME/tools/context-hub-0.1.4" @aisuite/chub@0.1.4` | `chub search 'python pytest' --json`; choose an actual returned ID, then `chub get "$DOC_ID" --lang py -o "$STACK_HOME/output/api-doc.md"`. Public registry/download access occurs; do not send feedback or annotations automatically. |
| `context-mode` · `1.0.169` | Native plugin source pinned to `6f0cc6841c687e754059f36714a11233fda1a02b`; [client setup](#native-context-mode-and-hooks). The npm `context-mode@1.0.169` release is a different source revision and is not a substitute for full plugin evidence. | [Retained Context Mode workflow](#retained-context-mode). Read `ctx_stats` as a connection-level estimate, never exact provider savings. |
| `davila7/claude-code-templates` · `c840d6f626be7ba418da60aeb0f2080413562451` | `git clone https://github.com/davila7/claude-code-templates.git "$STACK_HOME/tools/claude-code-templates"`, then `git -C "$STACK_HOME/tools/claude-code-templates" checkout --detach c840d6f626be7ba418da60aeb0f2080413562451` | Optional reference: read `cli-tool/components/skills/productivity/concise-planning/SKILL.md` for a matching task. No all-agent pack installation or runtime E2E is implied. |
| `difftastic` · `0.71.0` | Official [Wilfred/difftastic 0.71.0](https://github.com/Wilfred/difftastic/releases/tag/0.71.0), archive/hash above | `difft --exit-code --color never fixtures/before.py fixtures/after.py`. Exit **1** means differences with this flag; inspect the diff rather than treating it as a failed installation. |
| `gitleaks` · `8.30.1` | Official [gitleaks/gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), archive/hash above | `gitleaks git --redact=100 --no-banner --no-color --report-format json --report-path "$STACK_HOME/output/gitleaks.json" "$PROJECT_ROOT"`. Exit 0 means no matches in the scanned scope; distinguish detection from operational errors. |
| `headroom` · `0.37.0` | `uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'` | [Upstream MCP compression and retrieval](#headroom-native-compression-and-recovery). The earlier local exact-recovery guard remains separate; no automatic agent-traffic interception. |
| `huggingface-hub-native` · `1.32.0` | `uv tool install huggingface-hub==1.32.0` | `hf --version`; [revision-pinned model download](#local-semantic-code-search). Authentication, if needed, uses native `hf auth login`; never publish credentials. |
| `markitdown` · `0.1.7` | `uv tool install markitdown==0.1.7` | `markitdown fixtures/greeting.html -o "$STACK_HOME/output/greeting.md"`; inspect the greeting in the result. This uses the base HTML converter; PDF/Office extras are separate decisions. |
| `mcp-inspector` · `2.7.0` | `npm install --global --prefix "$STACK_HOME/tools/mcp-inspector-2.7.0" @modelcontextprotocol/inspector@2.7.0` | `mcp-inspector --cli --config "$PROJECT_ROOT/.mcp.json" --server socraticode --method tools/list --format json --stored-auth-only --cwd "$PROJECT_ROOT"`. Handshake/schema discovery only; follow with a selected tool call for functionality. |
| `mcporter` · `0.13.13` | `npm install --global --prefix "$STACK_HOME/tools/mcporter-0.13.13" mcporter@0.13.13` | `mcporter --config "$MCPORTER_CONFIG" list socraticode --brief --no-oauth`, then [local semantic search](#local-semantic-code-search) or [Context Mode](#retained-context-mode). Node >=24 is required. |
| `openresearch` · `0.2.7` | Official [alphaXiv/OpenResearch v0.2.7](https://github.com/alphaXiv/OpenResearch/releases/tag/v0.2.7), asset `openresearch-cli-x86_64-unknown-linux-musl.tar.xz`; [qualified archive and rollback](native-upgrades-20260921.md) | `orx --no-telemetry discover keyword 'agent memory' --published-after 2026-06-21 --published-before 2026-09-19 --limit 3`; retrieve only a selected result with `orx --no-telemetry paper "$PAPER_ID" --full`. Public literature access, not a model-quality ranking. |
| `playwright-cli` · `0.1.21` | `npm install --global --prefix "$STACK_HOME/tools/playwright-cli-0.1.21" @playwright/cli@0.1.21`; bundled Playwright `1.64.0-alpha-1789764292000` | Optional alternative to agent-browser. `playwright-cli --help` checks installation only; consult its native skill for the chosen browser workflow. Historical installation evidence is Windows-scoped, not a claimed Linux browser E2E. |
| `promptfoo` · `0.123.1` | `npm install --global --prefix "$STACK_HOME/tools/promptfoo-0.123.1" promptfoo@0.123.1` | `PROMPTFOO_DISABLE_TELEMETRY=1 promptfoo eval --config "$EVAL_CONFIG" --no-cache --no-table --no-progress-bar --no-share --no-write --output "$EVAL_RESULT"`. The retained native fixture used a local echo provider and passed two exact assertions with zero model tokens. Select the intended provider/data explicitly; no paid default is supplied. |
| `qdrant` · `1.19.1` | Official [qdrant/qdrant v1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1), archive/hash above; retain Apache-2.0 license | `qdrant --config-path "$QDRANT_CONFIG" --disable-telemetry`; [loopback service and RAG](#local-semantic-code-search). Persistent data paths are separate from the versioned binary. |
| `qmd` · `2.8.3` | `npm install --global --prefix "$STACK_HOME/tools/qmd-2.8.3" @tobilu/qmd@2.8.3` | [Document workflow](#documents-and-selected-artifacts). BM25 `search` uses no model weights; native dependencies can still occupy substantial disk. `query`/`embed` are separate model-enabled choices. |
| `repomix` · `1.18.1` | [Qualified isolated-prefix installation](native-upgrades-20260921.md#installation) with explicit candidate executable | `repomix "$PROJECT_ROOT" --include 'fixtures/before.py,fixtures/after.py' --style xml --parsable-style --compress --token-count-encoding o200k_base --output "$STACK_HOME/output/selected-code.xml"`. Explicit two-file artifact; compression omits details, so read originals before editing. |
| `rtk` · `0.49.0` | Official [rtk-ai/rtk v0.49.0](https://github.com/rtk-ai/rtk/releases/tag/v0.49.0), asset `rtk-x86_64-unknown-linux-musl.tar.gz`, `checksums.txt`; exact archive procedure above | In this clone, `rtk git log -6`; use `rtk proxy git log -6` for raw recovery. [Native hooks](#native-context-mode-and-hooks) keep Codex explicit at this stable pin. Counters estimate savings. |
| `sandbox-runtime` · `0.0.77` | `npm install --global --prefix "$STACK_HOME/tools/sandbox-runtime-0.0.77" --ignore-scripts @anthropic-ai/sandbox-runtime@0.0.77` | [Isolation workflow](#on-demand-isolation). Linux requires bubblewrap, socat and ripgrep. Package metadata establishes the pin; the CLI can report a fallback version. |
| `serena` · `c6fbd1c5932df2494ffa0020af5a9fbe80b82143` | Native pinned execution: `uvx --from git+https://github.com/oraios/serena@c6fbd1c5932df2494ffa0020af5a9fbe80b82143 serena start-mcp-server --context codex --project-from-cwd` | [Client MCP setup](#native-project-mcp). Upstream declares `2.0.0.dev0`; the commit is the identity. Language-server support varies by project; a handshake alone does not prove every language. |
| `shanraisshan/claude-code-best-practice` · `15969ed2471a177d938c889255d2f23f07e4742a` | `git clone https://github.com/shanraisshan/claude-code-best-practice.git "$STACK_HOME/tools/claude-code-best-practice"`, then `git -C "$STACK_HOME/tools/claude-code-best-practice" checkout --detach 15969ed2471a177d938c889255d2f23f07e4742a` | Optional reference: read selected README guidance; verify advice against current native docs. No runtime or bulk plugin installation. |
| `shellcheck` · `0.11.0` | Official [koalaman/shellcheck v0.11.0](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0), asset `shellcheck-v0.11.0.linux.x86_64.tar.xz`; archive procedure | `shellcheck --norc --format=json1 fixtures/example.sh`; inspect all diagnostics. Static shell analysis is not a product test suite. |
| `socraticode` · `1.14.0` | `npm install --global --prefix "$STACK_HOME/tools/socraticode-1.14.0" --ignore-scripts socraticode@1.14.0` | [Local semantic code search](#local-semantic-code-search). Source `2218f25153d0f3f4a76ee240a5643dbc873e80be`; AGPL-3.0-only with upstream commercial alternative. This profile uses external local services, not Docker or a cloud key. |
| `toon` · `4.1.1` | `npm install --global --prefix "$STACK_HOME/tools/toon-4.1.1" @toon-format/cli@4.1.1` | `toon fixtures/records.json --stats -o "$STACK_HOME/output/records.toon"`; `toon "$STACK_HOME/output/records.toon" --decode --strict -o "$STACK_HOME/output/records.recovered.json"`. Compare decoded JSON values to the original, including numeric precision. Token estimates are not provider billing. |
| `vllm` · `0.25.0` | `uv venv --python 3.13 "$STACK_HOME/tools/vllm-0.25.0"`; `uv pip install --python "$STACK_HOME/tools/vllm-0.25.0/bin/python" vllm==0.25.0` | [Pinned local GPU embedding service](#local-semantic-code-search). Latest observed 0.29.0 resolved and installed but failed GPU startup under WSL with unavailable UVA; 0.25.0 was restored and real search passed. Do not label 0.25.0 latest or 0.29.0 ready. |
| `worktrunk` · `0.79.0` | Official [max-sixty/worktrunk v0.79.0](https://github.com/max-sixty/worktrunk/releases/tag/v0.79.0); [qualified archive and rollback](native-upgrades-20260921.md) | `wt list --format json`; for an actual owned writing task, `wt switch --create "$BRANCH" --base "$BASE_REF" --no-cd --no-hooks --format json`. The retained disposable lifecycle verified selection and `wt remove "$BRANCH" --foreground --no-hooks --format json`, leaving only the original worktree. |

## Native context mode and hooks

The native plugin source pin below declares 1.0.169. Full plugin hooks and the older npm release's MCP-only behavior are distinct. Both [Codex's marketplace CLI](https://github.com/openai/codex) and [Claude's plugin mechanism](https://code.claude.com/docs/en/plugins) support a pinned Git source:

```sh
codex plugin marketplace add mksglu/context-mode --ref 6f0cc6841c687e754059f36714a11233fda1a02b --json
codex plugin add context-mode@context-mode --json
codex features enable hooks
codex features enable plugin_hooks

claude plugin marketplace add mksglu/context-mode@6f0cc6841c687e754059f36714a11233fda1a02b --scope user
claude plugin install context-mode@context-mode --scope user --json
```

Back up the affected settings privately first; preserve unrelated hooks and plugin entries. In **each actual Codex runtime/home**, open a fresh native session and use `/hooks` to inspect and trust the exact installed definitions. Project trust and hook-definition trust are separate. Do not write trust databases by hand or add bypass flags. Reopen a Desktop task after supported configuration changes: an existing task's tool catalog does not automatically hot-load new servers. Claude's `/context-mode:ctx-doctor` checks its own native integration.

Context Mode's upstream `start.mjs` can maintain its own dependencies/cache-heal hooks and check the npm registry. Native installation is not a promise of offline-only startup. Keep native plugin version/provenance receipts and review changes before upgrading.

RTK 0.49.0 supplies a supported Claude hook and explicit Codex instructions. Install global awareness once in each intended client profile, preserving its existing native home:

```sh
rtk init --global --auto-patch --no-trust-filters
rtk init --global --codex
rtk init --global --show
rtk init --global --codex --show
```

Run the Codex form separately under each intended `CODEX_HOME`; an inherited Desktop home must not be mistaken for the native CLI home. The installer writes `RTK.md` and its global instruction reference. Claude's command installs awareness and preserves an existing matching hook; `--no-trust-filters` avoids expanding trusted project filters during this setup. Fresh sessions consume these instructions. Setup is not a prerequisite to repeat at every startup.

The Codex form at this pin writes instructions, not an automatic command-rewriting hook; do not combine `--codex` with `--auto-patch`. The prior automatic candidate did not establish reliable runtime rewriting and is not an active recipe. For raw-sensitive Git/history operations, use explicit commands or RTK's supported exclusions rather than treating compressed output as a complete record. Inspect generated hook changes alongside existing Context Mode hooks. Verify the result with one useful native task and its actual tool output.

## Native project MCP

Merge [codex-mcp.toml.example](../examples/codex-mcp.toml.example) into the project's `.codex/config.toml` and [claude-mcp.json.example](../examples/claude-mcp.json.example) into `.mcp.json`. They contain only server entries; there are no model, account, approval or sandbox overrides. Replace paths with installed upstream executables. Serena's context is `codex` for Codex and `claude-code` for Claude. Start clients in the selected project so `--project-from-cwd` resolves correctly.

Native CLI registration is also supported. For a server that needs no environment map, these examples add a **separate** named server rather than replacing an existing one:

```sh
# Codex registration uses the selected native configuration home.
codex mcp add ai-memory --url http://127.0.0.1:49374/mcp
# Claude project scope writes .mcp.json in the current project.
claude mcp add --transport http --scope project ai-memory http://127.0.0.1:49374/mcp
```

Use either a selective project merge or CLI registration, not duplicate entries. Review normal client MCP consent when prompted. For full stdio tool inspection without an LLM or interactive OAuth:

```sh
mcp-inspector --cli --config "$PROJECT_ROOT/.mcp.json" --server socraticode \
  --method tools/list --format json --stored-auth-only --cwd "$PROJECT_ROOT"
```

Do not turn a successful tool listing into a functional-search claim. The sequences below call actual tools.

For Serena, after its native project setup has enabled the fixture's Python language server, a bounded symbol request is:

```sh
mcp-inspector --cli --config "$PROJECT_ROOT/.mcp.json" --server serena \
  --method tools/call --tool-name get_symbols_overview \
  --tool-args-json '{"relative_path":"fixtures/before.py","depth":1}' \
  --format json --stored-auth-only --cwd "$PROJECT_ROOT"
```

The expected source symbol is `greeting`. A language-server setup error is a missing prerequisite, not an empty-symbol success; consult the pinned Serena project setup before adding another indexer for that language.

## Local semantic code search

Use [qdrant.yaml.example](../examples/qdrant.yaml.example) and the service templates only after replacing absolute paths and creating their state directories. They bind to loopback, disable Qdrant telemetry and gRPC, and keep storage outside binary prefixes. The service port is **16333**, the embedding endpoint **8231**. Loopback limits exposure; it is not authorization against another local user. Add Qdrant's supported API-key protection if that is part of the host's threat model, and keep that key private.

The model is [NVIDIA Nemotron-3-Embed-1B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16), released July 16, 2026, under OpenMDW-1.1. Pin the revision and retain model license/config files:

```sh
hf download nvidia/Nemotron-3-Embed-1B-BF16 \
  --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 \
  --local-dir "$MODEL_DIRECTORY" --max-workers 2 --json

qdrant --config-path "$QDRANT_CONFIG" --disable-telemetry
# In a second terminal, or via the reviewed user unit:
"$STACK_HOME/tools/vllm-0.25.0/bin/vllm" serve "$MODEL_DIRECTORY" \
  --served-model-name nvidia/Nemotron-3-Embed-1B-BF16 \
  --host 127.0.0.1 --port 8231 --max-model-len 4096 --max-num-seqs 4 \
  --gpu-memory-utilization 0.16 --enforce-eager --no-enable-log-requests
```

This is a roughly 2.3 GB pinned model download, not a metadata-only check. vLLM selects its native pooling/embedding implementation without `trust_remote_code`. Queries use `query: ` and documents `passage: `, including the trailing spaces. SocratiCode's supported `lmstudio` provider is the generic OpenAI-compatible local adapter pointing to vLLM here; LM Studio itself is not installed. These settings do not change Claude/Codex generation models.

The [MCPorter example](../examples/mcporter.json.example) pins one project working directory, sets `imports: []`, and retains the SocratiCode connection so its upstream watcher stays alive. Edit only the corresponding absolute paths, then save a local copy at `$MCPORTER_CONFIG`. The MCPorter daemon is shared per OS user; do not restart it without checking for other users' connections/active calls.

```sh
curl --fail --silent --show-error http://127.0.0.1:16333/healthz
curl --fail --silent --show-error http://127.0.0.1:8231/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"nvidia/Nemotron-3-Embed-1B-BF16","input":["query: how are native tools scoped to one project?"]}' \
  -o "$STACK_HOME/output/embedding.json"

mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_health --args '{}' --output text --no-oauth
INDEX_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"projectPath":sys.argv[1]}))' "$PROJECT_ROOT")
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_index --args "$INDEX_ARGS" --output text --no-oauth
# Indexing is asynchronous. Check status and wait until completion before searching.
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_status --args "$INDEX_ARGS" --output text --no-oauth
# Run the following search only after status reports the index is complete.
SEARCH_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"projectPath":sys.argv[1],"query":"read a greeting from the browser fixture","limit":3}))' "$PROJECT_ROOT")
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_search --args "$SEARCH_ARGS" --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call socraticode.codebase_watch --args '{"action":"status"}' --output text --no-oauth
```

Acceptance means a finite 2048-value embedding, successful native health/index results, and a relevant returned file that can be checked against source. Scores are relevance signals, not benchmark rankings. A watcher status alone does not prove add/change/delete propagation. To validate freshness, make one owned disposable source-file change, observe native index payload changes without search-triggered catch-up, then remove it. Avoid indexing unrelated directories or implicitly adding external artifacts.

**Compatibility exception:** vLLM 0.29.0 was the latest observed release. A clean resolver, installation and CLI help succeeded, but real WSL GPU startup failed with `RuntimeError: UVA is not available`. The working 0.25.0 recipe was restored; direct semantic search subsequently passed. Keep the 0.25.0 source pin `702f4814fe54fabff350d43cb753ae3e47c0c276` and rollback environment. Do not override dependencies or patch upstream just to claim the newest version is active.

## Project memory

ai-memory is the shared durable-memory lane; routine hook observations are not complete transcripts. Initialize the data directory, then edit its config **before starting hooks or the service**:

```sh
ai-memory init
```

Use the relevant fields from [ai-memory-config.toml.example](../examples/ai-memory-config.toml.example) in the default data directory's `config.toml`. The selected semantic-memory profile uses upstream `embedding_provider="local"`: checksum-pinned MiniLM, 384 dimensions, about 87 MiB downloaded once, with inference inside ai-memory. Use `none` for a deliberately FTS-only profile. Leave the LLM provider and reranker unset; literal `llm_provider="none"` is invalid. Historical transcript backfill, assistant capture and session-end LLM consolidation remain disabled. Embedding backfill is separate: an enabled server embeds existing latest pages across its configured store, so inspect that store's scope first. Keep one data directory/config shared by service and native hooks; choosing a different server config alone does not redirect hook fallback storage. See the [qualified memory/RAG workflow](../docs/memory-rag-native-practice.md) for native returns, recovery and interface boundaries.

For a text-only clean-install trial, explicitly set `embedding_provider="none"`
or the supported `AI_MEMORY_EMBEDDING_PROVIDER=none` in that owned service's
environment. An unset embedding provider can select the local default and start
a model download; it is not a text-only opt-out. Verify the resulting startup
log and store before treating a no-model-download trial as passed. This does not
change the accepted semantic profile above or disable an existing user's service.

After reviewing scope, copy [ai-memory-project.toml.example](../examples/ai-memory-project.toml.example) to **only this project's** `.ai-memory.toml`. It names both workspace and project and excludes selected sensitive paths. Exclusions cover recognized file tools; they do not sanitize arbitrary shell output by path. Start the upstream service directly:

```sh
ai-memory serve --transport http --enable-web --bind 127.0.0.1:49374 --workspace local --project native-agent-stack
```

The upstream `packaging/systemd/ai-memory-user.service` can be adapted into a user unit, preserving the same data/config location. Do not use `--force` to take over another active instance. Register MCP using the project examples or native registration above, then install the native hooks in allowlist mode:

```sh
ai-memory install-hooks --agent claude-code --server-url http://127.0.0.1:49374 \
  --capture-mode allowlist --no-capture-prompts --apply
ai-memory install-hooks --agent codex --server-url http://127.0.0.1:49374 \
  --capture-mode allowlist --apply
```

These hook installers are global additions gated by the project marker. They preserve a shared capture mode; back up the affected files and inspect the generated merge. Codex uses its selected `CODEX_HOME/hooks.json`; Claude uses its native settings. Review exact Codex hook definitions via `/hooks` afterward. Upstream can disable Claude prompt capture here; Codex prompt capture has no corresponding disable flag at this pin. Bounded sanitized observations and heuristic handoffs still have storage/prompt overhead. Do not describe this profile as zero capture.

For native routing, `ai-memory install-instructions --target AGENTS.md` updates the managed block and skills; read its help and preview the intended destinations first. Preserve non-managed content, keep canonical project rules in AGENTS/CLAUDE, and do not duplicate those rules as durable pages.

A deliberate durable-memory demonstration is appropriate only for an actual decision the operator wants retained. The following optional example creates a demo decision under an explicit path; it is not routine automatic logging:

```sh
ai-memory write-page --workspace local --project native-agent-stack \
  --path decisions/local-retrieval-demo.md --kind decision \
  --body 'The demo uses a local embedding endpoint to exercise retrieval without a cloud embedding API.'
ai-memory search 'local embedding endpoint' --workspace local --project native-agent-stack --json
ai-memory read-page --workspace local --project native-agent-stack \
  --path decisions/local-retrieval-demo.md --json
```

Static HTTP clients pass `workspace` and `project` together on every scoped MCP call. Namespace selection is not user authorization, and a shared mutable active-project pointer is not safe scope isolation. Session-aware upstream clients may derive scope natively; do not assume every bridge supports it.

## Supplemental native task and inspection tools

The September 20 additions use upstream programs in the same native shell for
Codex and Claude. Install once in the selected prefix and keep its executable
directory on each client's PATH. Use these tools when their task applies; startup
does not require another installation or acceptance campaign. The
[dated receipt](../evidence/receipts/upstream-native-tools-20260920.json) records
the tested scope and retained failures on the source Linux/WSL host. These
portable recipes do not establish installation or acceptance on macOS, VelaNext
or another host; a selected host needs its own relevant check. These tools have
no verified cumulative token-savings counters.

### Beads task dependencies

Install the upstream npm package in an owned prefix:

```sh
npm install --prefix "$STACK_HOME/tools/beads-1.3.0" @beads/bd@1.3.0
"$STACK_HOME/tools/beads-1.3.0/node_modules/.bin/bd" version
```

The package's postinstall downloads the upstream release. If the package manager
reports that it withheld that specific script, inspect the upstream package and
use its supported per-package approval before
`npm rebuild @beads/bd --foreground-scripts` in the prefix. Do not disable script
protection globally.
The tested release archive `beads_1.3.0_linux_amd64.tar.gz` has SHA-256
`2f92b904ecf35b607e44dc5c39229173af69c54f1183e8d709f1773540cdcf3b`.

For a selected project that needs persistent dependency and claim state, set
`BEADS_DIR` to its owned task directory and run from that project's Git root:

```sh
export BEADS_DIR="$PROJECT_ROOT/.beads"
bd init --stealth --skip-agents --skip-hooks --non-interactive --prefix work
bd create "Complete the selected task" --type task --json
bd ready --json
bd update "$RETURNED_TASK_ID" --claim --json
bd show "$RETURNED_TASK_ID" --json
bd close "$RETURNED_TASK_ID" --reason "Acceptance recorded" --json
```

Use actual returned IDs. `bd dep add "$DEPENDENT_ID" "$PREDECESSOR_ID" --json`
keeps the dependent out of `bd ready` until its predecessor closes. The tested
initialization uses embedded Dolt and changes only the selected task directory
and Git exclusion state; it skips generated agent instructions and hooks.
ai-memory remains the shared durable knowledge and handoff layer.

### Agent Skills reference validator

Install the official source and its locked environment:

```sh
git clone https://github.com/agentskills/agentskills.git "$STACK_HOME/tools/agentskills"
git -C "$STACK_HOME/tools/agentskills" checkout --detach 69ef37e9424c0a7ea9dd2293b559e43ec8176379
cd "$STACK_HOME/tools/agentskills/skills-ref"
uv sync --locked
uv run skills-ref validate "$SKILL_DIRECTORY"
uv run skills-ref read-properties "$SKILL_DIRECTORY"
uv run skills-ref to-prompt "$SKILL_DIRECTORY"
```

The pin packages skills-ref 0.1.0. Upstream labels this a reference/demo
implementation. Its portable-format validation does not certify native Codex or
Claude extensions, loaded-tool behavior, or production client semantics. Use it
on the skill being edited, alongside that client's own validation where needed.

### otel-tui telemetry inspection

Download the official v0.7.5 Linux asset and checksum file:

```sh
gh release download v0.7.5 --repo ymtdzzz/otel-tui \
  -p otel-tui_Linux_x86_64.tar.gz -p otel-tui_0.7.5_checksums.txt \
  --dir "$STACK_HOME/downloads/otel-tui-0.7.5"
```

Verify the matching checksum using the archive procedure above, then install
the extracted `otel-tui` in the owned native prefix. The tested archive SHA-256
is `dd10bfa12b6713a2d51d7a094644ff61a2467856fc93d3acecfe741a124ca896`.
`otel-tui --version` reports the pin.

For a deliberate local diagnostic session, choose unused loopback ports:

```sh
otel-tui --host 127.0.0.1 --grpc 14317 --http 14318
```

Configure only the selected producer to send OTLP to that endpoint. For an
existing compatible export, use
`otel-tui --host 127.0.0.1 --from-json-file "$OTEL_JSON"`.
Close the owned session after inspection. This is an on-demand
viewer; it does not replace the existing collector/backends or install global
client telemetry settings.

## Focused jCodeMunch retrieval

Install the pinned upstream server with `uv tool install jcodemunch-mcp==1.108.319`.
The retained upstream license is **Dual-Use License 1.1**; the bounded local
acceptance does not establish eligibility for commercial deployment. Keep its
default six-tool `counter` surface. The following upstream registration commands
are for the intended native CLI profile; preserve its existing configuration home:

```sh
codex mcp add jcodemunch \
  --env "CODE_INDEX_PATH=$HOME/.code-index" --env JCODEMUNCH_SHARE_SAVINGS=0 \
  -- jcodemunch-mcp
claude mcp add jcodemunch --scope local --transport stdio \
  --env "CODE_INDEX_PATH=$HOME/.code-index" --env JCODEMUNCH_SHARE_SAVINGS=0 \
  -- jcodemunch-mcp
```

The tested Codex adoption stored the equivalent server entry in the selected
project's `.codex/config.toml`; the CLI command above adds it to the chosen native
CLI configuration. Claude's `local` scope applies to the current project.
Register once. Use only explicitly selected code directories, with AI/paid
summaries, savings sharing, watchers, cross-repository defaults and external
context providers disabled. Do not index conversations, credentials or every
project merely because the server is available.

The upstream default index root is intentional: in this release, source retrieval
records its estimate there even when a custom index root was requested. Reading
stats from a different root can therefore show a misleading zero. Keep the
existing default ledger; the native estimate includes repeated reads.

The six-tool surface exposes actions through `order`. Select actual local scope
and returned repository/symbol IDs for these tool arguments:

```json
{"action":"index_folder","args":{"path":"/absolute/selected/project/src","use_ai_summaries":false,"extra_ignore_patterns":["*.json","*.jsonl","*.md","*.html","*.txt","**/__pycache__/**"],"follow_symlinks":false,"context_providers":false},"allow_state_change":true}
```

```json
{"action":"search_symbols","args":{"repo":"RETURNED_REPOSITORY_ID","query":"requested_function","kind":"function","max_results":1}}
```

```json
{"action":"get_symbol_source","args":{"repo":"RETURNED_REPOSITORY_ID","symbol_id":"RETURNED_SYMBOL_ID"}}
```

Read the actual upstream report without importing a historical receipt:

```sh
mcporter call --stdio jcodemunch-mcp \
  --env "CODE_INDEX_PATH=$HOME/.code-index" --env JCODEMUNCH_SHARE_SAVINGS=0 \
  --name jcodemunch --tool order \
  --args '{"action":"get_session_stats","args":{}}' --output json --no-oauth
```

The [direct receipt](../evidence/receipts/native-jcodemunch-20260920.json) verifies
exact source fidelity. Complete search-plus-source responses used 861 tokens
against a 5,476-token whole file, saving 4,615 artifact tokens; an already-known
601-token function extraction was 260 tokens cheaper than the MCP sequence.
Index-plus-retrieval used 1,332 tokens. Choose the useful lane for the task rather
than sending known exact code through another retrieval layer. The native
bytes/4 ledger and advertised schema-size estimates are separate heuristics.

## Headroom native compression and recovery

Install once with the upstream MCP extra:

```sh
uv tool install --python 3.13 'headroom-ai[mcp]==0.37.0'
headroom mcp serve --proxy-url http://127.0.0.1:1
```

The tested direct MCP fixture used that unreachable loopback proxy address and
the server's local compression path. Within one live MCP session, call
`headroom_compress` with `{"content":"selected content"}`, then
`headroom_retrieve` with the returned `hash`; `headroom_stats` accepts `{}`.
Verify exact original-content recovery and required failure details before
using a summary. There is no upstream `headroom compress` CLI subcommand.

The [receipt](../evidence/receipts/native-headroom-mcp-20260920.json) records
36,625 compact-JSON baseline tokens versus a 19,714-token summary, with exact
full retrieval and the critical failure retained. Retrieving the complete
original consumes its original content again. A separate local guarded request
used 26,529 versus 191 tokens with exact run-expansion recovery. These are owned
synthetic fixtures, not production traffic or provider savings.

`headroom savings --json` returns the real selected ledger. Its global ledger
remained zero; an explicitly isolated fixture ledger reported one call and
36,719 estimated saved tokens. Never merge that fixture result into the global
total. The upstream report's hard maximum window is 30 days. Keep the existing
guard lane and original artifacts; no automatic interception or model rerouting
is part of this recipe.

## Retained Context Mode

If a Codex plugin's bundled server starts in its cache directory, selected
project files may be outside that server's root. The tested project-scoped
repair preserves the enabled plugin and its hooks, disables only that bundled
server, and registers the installed upstream `context-mode` command with the
explicit project directory. Replace both absolute paths in the selected
project's `.codex/config.toml`:

```toml
[plugins."context-mode@context-mode".mcp_servers.context-mode]
enabled = false

[mcp_servers.context-mode]
command = "context-mode"
cwd = "/absolute/project"
startup_timeout_sec = 60

[mcp_servers.context-mode.env]
CONTEXT_MODE_PLATFORM = "codex"
CONTEXT_MODE_PROJECT_DIR = "/absolute/project"
```

This uses the supported [bundled MCP server policy](https://developers.openai.com/plugins/build/plugins#bundled-mcp-servers-and-lifecycle-hooks).
No plugin-cache edits or broader file allowlist are needed. A fresh native
session reads the configuration; an existing process retains its loaded server
connection. Both native clients completed the bounded project-file and symbol
task in the [new client receipt](../evidence/receipts/native-token-focus-clients-20260920.json).

Point the Context Mode entry in the MCPorter example at the actual installed plugin's upstream `start.mjs`, using the intended runtime's configuration home. The path must come from that runtime's plugin inventory. This preserves native startup behavior instead of inserting a replacement server.

```sh
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_stats --args '{}' --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_index \
  path="$PROJECT_ROOT/fixtures/rag-note.md" source=portable-rag-note --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_search \
  --args '{"queries":["local code retrieval"],"source":"portable-rag-note","limit":1}' --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call context-mode.ctx_stats --args '{}' --output text --no-oauth
```

Check that the returned passage matches the source. A fresh MCP connection may reset statistics; record before/after on the same retained connection. Upstream statistics estimate avoided context from bytes and include prior calls in that connection. They are neither a tokenizer count nor provider billing, and should not be attributed solely to the last indexed file.

## Static code graph

The MCPorter example limits the native codebase-memory server to `CBM_ALLOWED_ROOT=/ABSOLUTE/PROJECT_ROOT`. Its native database/daemon is persistent outside the repository; the allowlist does not make index data ephemeral. No automatic all-client installation is needed.

```sh
mcporter --config "$MCPORTER_CONFIG" list codebase-memory --schema --no-oauth
GRAPH_ARGS=$(python3 -c 'import json,sys; print(json.dumps({"repo_path":sys.argv[1],"name":"native-stack-demo","mode":"fast","persistence":False}))' "$PROJECT_ROOT")
mcporter --config "$MCPORTER_CONFIG" call codebase-memory.index_repository --args "$GRAPH_ARGS" --output text --no-oauth
mcporter --config "$MCPORTER_CONFIG" call codebase-memory.search_graph \
  --args '{"project":"native-stack-demo","name_pattern":"^greeting$","file_pattern":"fixtures/","limit":5,"format":"json"}' --output text --no-oauth
```

The explicit project name makes the following search reproducible; verify the index response accepted it before searching. Check that `greeting` resolves to the public Python fixture and that line ranges match source. Fast mode exercises static indexing without optional semantic enrichment. `persistence:false` avoids a repository-local graph snapshot, but the native server still retains its database. For call tracing, choose a returned fully qualified function with real edges and the discovered `trace_path` schema; an empty leaf function does not prove call-graph coverage. Use explicit `index_repository` after changes when freshness matters; native polling does not make every query an atomic view of disk.

## Documents and selected artifacts

QMD uses a deliberately small Markdown collection. This example indexes public fixture notes, without a model download:

```sh
qmd --index "$QMD_INDEX" collection add "$PROJECT_ROOT/fixtures" --name "$QMD_COLLECTION" --mask '**/*.md'
qmd --index "$QMD_INDEX" update
qmd --index "$QMD_INDEX" search 'local code' -c "$QMD_COLLECTION" -n 2 --json
# Copy an actual returned qmd:// document ID, optionally with a bounded line range.
qmd --index "$QMD_INDEX" get "$QMD_DOCUMENT_ID"
```

Use ast-grep/Serena/rg for exact code, SocratiCode for conceptual code retrieval, and scoped QMD for Markdown. Select one useful lane for an artifact instead of sending it through every compressor. TOON needs a value-preserving decode; Repomix compression needs original-source recovery. Exact local tokenizer counts require the named tokenizer, identical source bytes and scope; they still do not establish provider savings. Do not silently drop errors or recovery paths in filtered outputs.

## Browser workflow

Keep identical launch options for the same owned browser session. The public [agent-browser config](../examples/agent-browser.json) enables the local HTML fixture; do not reuse file access for an unrelated remote browsing task by default.

```sh
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session open "file://${PROJECT_ROOT}/fixtures/greeting.html"
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session snapshot -i -c --json
# Set NAME_REF and BUTTON_REF to the actual refs returned by that snapshot.
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session fill "$NAME_REF" Native
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session click "$BUTTON_REF"
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session get text '#status'
agent-browser --config examples/agent-browser.json --namespace native-stack --session selected-owned-session close
```

Check for the actual `Hello, Native!` result and use returned element refs, never fabricated ones. Close only this owned session. The official skill is available through `agent-browser skills get core`; persistent skill installation is optional and should select only the matching skill, not a browser plugin catalog.

## History and usage

Set `AGENTSVIEW_DATA_DIR` to a dedicated archive directory and merge [agentsview.toml.example](../examples/agentsview.toml.example) into that directory's `config.toml` before any sync. Its explicit cwd allowlist and selected session directories prevent unrelated default histories from being imported. Point directories only at authorized native session logs, not authentication stores. Preserve private archive permissions.

```sh
AGENTSVIEW_DATA_DIR="$STACK_HOME/state/selected-history" AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 AGENTSVIEW_NO_DAEMON=1 agentsview sync
AGENTSVIEW_DATA_DIR="$STACK_HOME/state/selected-history" AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 \
  agentsview serve --host 127.0.0.1 --port 17384 --no-sync --no-browser --no-update-check --background
AGENTSVIEW_DATA_DIR="$STACK_HOME/state/selected-history" AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 agentsview projects
AGENTSVIEW_DATA_DIR="$STACK_HOME/state/selected-history" AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 \
  agentsview session search 'selected task' --fts --project "$HISTORY_PROJECT_ID" --limit 3 --json
AGENTSVIEW_DATA_DIR="$STACK_HOME/state/selected-history" AGENTSVIEW_TELEMETRY_ENABLED=0 AGENTSVIEW_DISABLE_UPDATE_CHECK=1 agentsview daemon stop

# Select one native source home for this invocation; do not export it globally.
CODEX_HOME="$SELECTED_CODEX_HOME" ccusage codex daily --offline --no-cost --json --timezone UTC --config /dev/null
```

Choose an available loopback port and start/stop only the daemon belonging to this dedicated archive. The query commands require the service; the sync command above runs explicitly without it. Use the project ID returned by the archive. Empty results, unreadable logs and parser failure are distinct outcomes. Native and Desktop roots can overlap or contain copied sessions: deduplicate by stable session identity and retain per-root scope before combining totals. Cached input is a subset of input, reasoning output a subset of output; do not add either subset again to provider totals. Local estimates and model subscription usage remain separate.

## On-demand isolation

Replace paths in [sandbox-policy.json.example](../examples/sandbox-policy.json.example) with a dedicated owned fixture directory. Create `allowed/`, `blocked/` and `write-protected/`; place harmless marker text in `blocked/marker.txt` and `write-protected/marker.txt`. The denied read and denied write paths must be separate.

```sh
SANDBOX_POLICY="$STACK_HOME/config/sandbox-policy.json"
FIXTURE_ROOT="$STACK_HOME/state/sandbox-fixture"
mkdir -p "$FIXTURE_ROOT/allowed" "$FIXTURE_ROOT/blocked" "$FIXTURE_ROOT/write-protected"
printf '%s\n' 'harmless fixture' > "$FIXTURE_ROOT/blocked/marker.txt"
printf '%s\n' 'original fixture' > "$FIXTURE_ROOT/write-protected/marker.txt"
env -i HOME="$HOME" PATH="$PATH" srt --settings "$SANDBOX_POLICY" -- sh -c 'printf allowed > "$1"' sh "$FIXTURE_ROOT/allowed/result.txt"
env -i HOME="$HOME" PATH="$PATH" srt --settings "$SANDBOX_POLICY" -- cat "$FIXTURE_ROOT/blocked/marker.txt"
env -i HOME="$HOME" PATH="$PATH" srt --settings "$SANDBOX_POLICY" -- sh -c 'printf changed > "$1"' sh "$FIXTURE_ROOT/write-protected/marker.txt"
```

Check exit status **and host files** independently: the allowed write should exist; blocked read/write should fail and leave protected host bytes unchanged. When a path is both read- and write-denied, upstream masking can allow a write to an ephemeral private mount with exit 0 while leaving the host untouched. That is host protection, not command denial. These operations do not prove network isolation or global protection of every client command. Do not pass a normal shell's secret environment into a fixture test.

The later [network fixture](../evidence/receipts/native-sandbox-network-20260920.json)
separately verified the HTTP proxy path. Three scoped policies used the same
owned IPv4 loopback server: allow its exact `host:port`, deny that same endpoint
explicitly, and use an empty allowlist. The allowed request returned the exact
fixture with exit 0; both denied cases returned proxy HTTP 403 and curl exit 22,
with no additional request reaching the server. The upstream listener can race
an immediate client, so the accepted native command uses bounded retries:

```sh
srt --debug --settings "$SCOPED_SANDBOX_POLICY" curl \
  --silent --show-error --fail --max-time 10 \
  --retry 2 --retry-connrefused --retry-delay 1 --noproxy "" \
  "$OWNED_LOOPBACK_URL"
```

Record initial connection failures and verify the destination's request count.
This fixture did not change global policy or enable weaker isolation. It does
not establish TLS, SOCKS, IPv6, DNS-rebinding, remote-host or escape coverage.

## Optional Codex for Claude

The official bridge runs the existing native Codex app-server. It does not require copying auth or choosing an extra API provider. Keep its stop-review gate OFF unless explicitly adopting that workflow; upstream companion setup supports `setup --disable-review-gate --json --cwd "$PROJECT_ROOT"`. Resolve `scripts/codex-companion.mjs` from the installed plugin directory and invoke it with native Node.

If the intended integration is explicit review only, append the supported Claude permission rule `Agent(codex:codex-rescue)` to existing `permissions.deny` rather than replacing that list. This blocks the plugin's proactive Sonnet rescue agent, including explicit calls to that agent; it does not change native Codex defaults. Preserve all other hooks, plugin settings and statusline configuration.

`/codex:status` and companion `status --json` inspect readiness. `/codex:review --wait` is an actual provider operation requiring account readiness and task authorization; stop when an unchanged quota error occurs. A companion task backend may use the label `rescue` without invoking the Claude Sonnet agent. Report actual native tool reads and provider usage from the returned session, not the label.

## Native client acceptance

After normal sign-in and native hook/MCP review, open a **fresh** client in the selected project. One small task can read a public fixture through an appropriate installed tool and report a verifiable result. Preserve account/model defaults; do not add blanket permissions or hook-trust bypasses merely to make an acceptance run pass.

```sh
codex exec -C "$PROJECT_ROOT" --json - < fixtures/native-gap-prompt.txt
claude -p --output-format stream-json --verbose --max-turns 14 < fixtures/native-gap-prompt.txt
```

The included prompt is a portable replay template, not the original private run prompt. These commands use provider capacity. Run only when an actual native client check is intended; a quota error is a stopped attempt, not functional success. Keep transcripts and raw provider records private. Publish only sanitized result fields, precise scope and observed usage, with cached/reasoning subsets explained. A completed CLI/bridge workflow proves that path; it does not prove automatic tool discovery or hooks in a previously open Desktop task.

## User service templates and lifecycle

The Qdrant and vLLM `.service.example` files are optional native systemd user-unit templates. After replacing every absolute placeholder, reviewing paths and creating state directories, copy selected units to `~/.config/systemd/user/` without the `.example` suffix and run `systemctl --user daemon-reload`. Start only the units you selected. Enabling a user unit is a separate decision to start it with the user manager; it does not keep a stopped WSL host alive. The templates deliberately have no automatic restart loop while diagnosing GPU startup.

Keep the previous model environment and binary prefix until real health/search acceptance passes. Stop only owned services or MCP connections. Preserve Qdrant/model data during a binary rollback. No recipe installs a replacement agent harness, custom proxy, global prompt pack or an invented always-running orchestration job.
