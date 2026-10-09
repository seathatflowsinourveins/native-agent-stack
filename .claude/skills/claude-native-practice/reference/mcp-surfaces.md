# MCP (`mcp-surfaces`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## mcp-config-tool-search

**Status:** default. **Default:** Native MCP configuration with tool search at its default (tools deferred), default output caps and `alwaysLoad` unset

- **Route:** User-scope registrations; `alwaysLoad: true` only for a small server used on every turn; `ENABLE_TOOL_SEARCH=true` behind a non-first-party base URL
- **Alternatives, ranked:** 1. modelcontextprotocol/inspector 2.10.1 for inspection (overlap with mcporter to resolve)
- **Rejected:** `ENABLE_TOOL_SEARCH=auto:N`; Disabling tool search; Raising `MAX_MCP_OUTPUT_TOKENS` globally
- **Evidence:** mcp.md tool search and output limits; mcp-O2, O3, O4, O5, O6, O7
- **Notes:** Registrations drift between host and template (qmd stdio versus HTTP, ports, a server key): G6b. Verified: on user-scope registrations `alwaysLoad: true` loads every tool of that server upfront (the per-tool opt-out works only for --mcp-config, SDK and plugin servers); image results stay under MAX_MCP_OUTPUT_TOKENS; the upfront fallback behind a non-first-party base URL dates from 2.1.70.
- **Supersedes:** topic: MCP tool loading (native deferral converged)
- **Overturn when:** A measured context or quality gap from deferral, or a release changes tool-search defaults.
- **Primary sources** (read 2026-10-09; 6 of 9 practices the refuters kept, measured first; fetch time and sha256 of the bytes read in the record's reading file):
  - [Introducing advanced tool use on the Claude Developer Platform \ Anthropic](https://www.anthropic.com/engineering/advanced-tool-use) (2025-11-24 (page reads "Published Nov 24, 2025"; JSON-LD datePublished 2025-11-24T00:00:00.000Z); measured; agrees): Defer MCP and other tool definitions and let the model find them on demand through a search tool, instead of loading every definition upfront. Anthropic reports this cuts context use and raises tool-selection accuracy on large tool libraries.
  - [Introducing advanced tool use on the Claude Developer Platform \ Anthropic](https://www.anthropic.com/engineering/advanced-tool-use) (2025-11-24 (page reads "Published Nov 24, 2025"; JSON-LD datePublished 2025-11-24T00:00:00.000Z); asserted; extends): Search matches tool names and descriptions, so give tools clear, distinct, descriptive definitions. Also tell the model in its system prompt which capability areas exist and that it should search for them.
  - [Code execution with MCP: building more efficient AI agents \ Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp) (2025-11-04; asserted; extends): Give a tool-discovery tool a detail-level parameter (name only, name and description, full schema), so the agent pulls only as much definition as it needs.
  - [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (2025-09-29; asserted; extends): Curate a minimal, non-overlapping and token-efficient tool set, because tools whose functions overlap create ambiguous decision points the agent cannot resolve any better than a human engineer.
  - [Plugins](https://developers.openai.com/codex/plugins) (unknown; asserted; not-covered): The source describes MCP servers as the tool layer that defines tools, returns structured data and acts on external systems, with custom UI optional.
  - [Lessons from building Claude Code: Prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) (2026-04-30; asserted; agrees): Rather than removing rarely used tools to save context, send stable name-only stubs marked for deferred loading and let the model load full schemas through tool search, so the prefix stays identical.

## mcp-shared-servers

**Status:** trial. **Default:** One vendor-native Streamable HTTP service per heavy MCP server, admitted one server at a time after a PSS before/after and tool-surface parity check

- **Route:** Registered with `claude mcp add --transport http --scope user`; stdio stays for servers without an HTTP mode
- **Alternatives, ranked:** 1. smart-mcp-proxy/mcpproxy-go (first trial alternative); 2. 1mcp-app/agent
- **Rejected:** A proxy in front of a server that already speaks HTTP, without a measured advantage; `claude mcp serve` as a pooling mechanism
- **Evidence:** mcp.md HTTP transport; docs/decisions/2026-10-08-qmd-shared-mcp.md (QMD pilot); Baseline RSS per group: serena plus pyright 5.7 GiB, chrome-devtools 2.6, context-mode 2.6, qmd 2.0
- **Notes:** Measurement owed: serena with pyright in three arms (per-session stdio, one native HTTP instance, behind mcpproxy-go): PSS, process-exporter RSS, latency and tool parity. Adjudicated mixed (native HTTP default, mcpproxy-go first alternative); the refuter upheld it. Admission gate per server, before PSS and tool parity: binds 127.0.0.1 only; rejects an invalid Origin with 403 (MCP 2026-07-28 Streamable HTTP); authenticates where the vendor supports it, through headersHelper, never literal values in a committed template; register through adoption/mcp/claude-user.json and re-render. Servers that scope by the client's project or working directory (serena) are excluded from sharing across projects.
- **Overturn when:** The three-arm run shows the proxy ahead on memory, latency or reliability on our servers.
