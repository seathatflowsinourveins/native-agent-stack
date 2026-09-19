# Stack inventory

Snapshot: September 19, 2026. The 36 entries below are adopted tools, integrations or selected references; the profile and receipt specify how each is used. No single row implies every client invoked every command.

| Component | Version/pin | Role | Profile |
| --- | --- | --- | --- |
| [affaan-m/ECC](https://github.com/affaan-m/ECC) | dd6ee538aee0f548d4a6b520118f875431fd749e | Selective on-demand community guidance | optional |
| [agent-browser](https://github.com/vercel-labs/agent-browser/releases/tag/v0.38.1) | 0.38.1 | Local native browser snapshot/ref interaction | core |
| [agentsview](https://github.com/kenn-io/agentsview/releases/tag/v0.43.0) | 0.43.0 | Scoped historical Codex/Claude transcript lexical search | supporting |
| [ai-memory](https://github.com/akitaonrails/ai-memory) | 2.3.1 | Shared scoped Markdown decisions and automatic heuristic cross-client handoffs | core |
| [ast-grep](https://github.com/ast-grep/ast-grep/releases/tag/0.45.3) | 0.45.3 | Structural source search | supporting |
| [ccusage](https://github.com/ccusage/ccusage) | 20.0.23 | Read existing native provider usage logs | supporting |
| [claude-code](https://github.com/anthropics/claude-code) | 2.1.278 | Native subscription coding client | core |
| [claude-hud](https://github.com/jarrodwatts/claude-hud/releases/tag/v0.8.0) | 0.8.0 | Claude statusline rendering | optional |
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.11.0) | 0.11.0 | Persistent static code graph and call tracing | core |
| [codex](https://github.com/openai/codex) | 0.155.1 | Native subscription coding client | core |
| [codex-for-claude](https://github.com/openai/codex-plugin-cc/tree/v1.0.6) | 1.0.6 @ db52e28f4d9ded852ab3942cea316258ae4ef346 | Official Claude plugin and native Codex companion delegation | optional |
| [context-hub](https://github.com/andrewyng/context-hub) | 0.1.4 | Retrieve selected curated developer documentation | supporting |
| [context-mode](https://github.com/mksglu/context-mode) | 1.0.169 | Local execution, file processing, indexed retrieval, native context hooks | core |
| [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | c840d6f626be7ba418da60aeb0f2080413562451 | Selective on-demand community guidance | optional |
| [difftastic](https://github.com/Wilfred/difftastic/releases/tag/0.71.0) | 0.71.0 | Syntax-aware source difference review | supporting |
| [gitleaks](https://github.com/gitleaks/gitleaks) | 8.30.1 | Redacted Git history secret detection | supporting |
| [headroom](https://github.com/chopratejas/headroom) | 0.37.0 | Optional guarded offline compression of supported artifacts | supporting |
| [huggingface-hub-native](https://github.com/huggingface/huggingface_hub) | 1.32.0 | Native authenticated model discovery and revision-pinned downloads | core |
| [markitdown](https://github.com/microsoft/markitdown/releases/tag/v0.1.7) | 0.1.7 | Convert supported source documents to readable Markdown | supporting |
| [mcp-inspector](https://github.com/modelcontextprotocol/inspector) | 2.7.0 | Upstream direct stdio tool inspection/calls | supporting |
| [mcporter](https://github.com/openclaw/mcporter/tree/v0.13.13) | 0.13.13 | Native CLI bridge with persistent MCP daemon connection | core |
| [openresearch](https://github.com/alphaXiv/OpenResearch) | 0.2.4 | Selected public literature discovery and extracted paper retrieval | supporting |
| [playwright-cli](https://github.com/microsoft/playwright-cli) | 0.1.21; Playwright 1.64.0-alpha-1789764292000 | Browser workflow instructions from installed official CLI | optional |
| [promptfoo](https://github.com/promptfoo/promptfoo) | 0.123.1 | Explicit evaluation configuration/fixtures | optional |
| [qdrant](https://github.com/qdrant/qdrant) | 1.19.1 | Local persistent vector and payload storage | core |
| [qmd](https://github.com/tobi/qmd/releases/tag/v2.8.3) | 2.8.3 | Local lexical retrieval over selected documentation | core |
| [repomix](https://github.com/yamadashy/repomix/releases/tag/v1.18.0) | 1.18.0 | Explicit repository packing and structural compression | supporting |
| [rtk](https://github.com/rtk-ai/rtk/releases/tag/v0.49.0) | 0.49.0 | Compact supported command outputs, retain failure/raw recovery | core |
| [sandbox-runtime](https://github.com/anthropics/sandbox-runtime) | 0.0.77 | On-demand OS isolation for selected native commands | supporting |
| [serena](https://github.com/oraios/serena) | 2.0.0.dev0 @ c6fbd1c5932df2494ffa0020af5a9fbe80b82143 | Language-server symbol and reference retrieval | core |
| [shanraisshan/claude-code-best-practice](https://github.com/shanraisshan/claude-code-best-practice) | 15969ed2471a177d938c889255d2f23f07e4742a | Selective on-demand community guidance | optional |
| [shellcheck](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0) | 0.11.0 | Static shell review | supporting |
| [socraticode](https://github.com/giancarloerra/SocratiCode) | 1.14.0 | Automatically refreshed semantic code retrieval and native code graph | core |
| [toon](https://github.com/toon-format/toon/releases/tag/v4.1.1) | 4.1.1 | Compact suitable structured data with explicit decode | supporting |
| [vllm](https://github.com/vllm-project/vllm) | 0.25.0 | Native GPU serving for pinned recent local embeddings | core |
| [worktrunk](https://github.com/max-sixty/worktrunk) | 0.78.0 | Native Git worktree convenience CLI | optional |

The machine-readable [stack manifest](../manifests/stack.json) maps every component to evidence and upstream commands. [Candidate decisions](../manifests/candidates.json) retain researched alternatives and requirements. Read [evidence boundaries](evidence.md) before interpreting savings or E2E claims.
