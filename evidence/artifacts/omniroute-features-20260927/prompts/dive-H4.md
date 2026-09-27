SHARED CONTEXT (OmniRoute gateway feature resolution, 2026-09-27)
- Gateway: OmniRoute source build, systemd --user unit omniroute.service, loopback http://127.0.0.1:20128, keyless, login off (user decision). BUILD_SHA dd6e9607e = release/v3.8.51 a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3 + PR #14904 (Request/Proxy fix) + PR #13788 (/v1/alpha/search).
- Source checkout at that exact tree (read-only): ~/.local/share/codex-ecosystem/sources/omniroute-a58000c7-pr14904 . It is indexed in the codebase-memory MCP server as project "omniroute-dd6e9607e" (use search_graph / get_code_snippet / trace_path for symbols; read exact lines with sed -n in the shell). Cite as https://github.com/diegosouzapw/OmniRoute/blob/a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3/<path>#Lx-Ly (the alpha-search route exists only locally; cite it as local).
- Redacted live GET snapshot of the gateway: $SCRATCH/omniroute-phase0/gateway-snapshot.json ; API route list: .../omniroute-phase0/api-routes.txt ; dashboard pages: .../omniroute-phase0/dashboard-pages.txt (same directory).
- Repository records: ~/code/native-agent-stack/docs/decisions/2026-09-27-omniroute-account-pool.md and ~/code/native-agent-stack/evidence/artifacts/omniroute-gateway-20260927/.
- Traffic classes. CX = native Codex CLI 0.157.1 -> POST /v1/responses (wire_api responses), model cx/gpt-6-astra at effort max (judgment) or cx/gpt-6-sol at medium (mechanical extraction); native passthrough; prompt-cache continuity from sessionAffinityTtlMs=14400000 + providerStrategies.codex round-robin sticky 1 over 4 Codex OAuth accounts. FW = OpenAI-compatible /v1/chat/completions from runtime frameworks: the S3 memory lane (cognee, Hindsight and similar, GPT-6 for extraction/graph building/consolidation/reranking with json_object, strict json_schema and tool calls; embeddings stay local), the landscape sweep, later DeerFlow/GPT Researcher/trading research runtimes (paper only). SEARCH = Codex web.run -> /v1/alpha/search; /v1/search.
- Measured split: output ~1.2% of tokens (117,065 output vs 9,419,199 input over 122 recent rows); ~94% of input is prompt-cache reads (24h 91,426,944 of 97,094,617). Compression saved 0 (all requests skipped as 'excluded'); semantic cache 0 entries.
- USER DECISION: every feature is resolved; the default path stays byte-identical; beneficial features become reachable per lane (header, combo model name or provider block) and a lane adopts them only after its own measured A/B. Quality first: GPT-6 max-effort workers must not be degraded.
- States: ON-GLOBAL (lossless, prefix-neutral, verified, safe for every lane), ON-OPT-IN (configured and reachable, selected per lane), OFF-BY-EVIDENCE (quality/security/cache reason from source), N/A (no consumer or no provider connected).
- RULES: read-only. Gateway: HTTP GET only (you may not be able to reach it from the sandbox; then use the snapshot). Never POST/PUT/PATCH/DELETE, never restart anything. Never read ~/.local/share/omniroute/server.env, storage.sqlite or any auth store; never print emails, tokens, keys or connection UUIDs. No Tavily. Every source claim cites file:line at the pin; live observations are marked as such; anything not verified goes to 'unverified'. For network lookups (GitHub issues/PRs/API) use the context-mode MCP fetch-and-index tool; the shell has no network. Process large outputs with context-mode ctx_execute instead of printing them. Keep every text field dense.


TASK: deep-dive and resolve 5 gateway features. Return one item object per feature, with the feature's id.
- S02 | OmniRoute MCP server (45 omniroute_* tools; stdio/sse/streamable-http; mcpEnabled=false)
  Focus: What the tools expose; benefit to our lanes vs tool-schema token cost and the repo rule of no GPT-6 usage narration in context; security on keyless loopback; proposed state.
- S03 | A2A server (a2aEnabled=false)
  Focus: Skills exposed; any consumer here; security; proposed state.
- S05 | Middleware hooks (/api/middleware/hooks), guardrails, prompt-injection guard, vision bridge
  Focus: Keyless loopback: any local process can register hooks (decision record 5); guardrails that inspect or rewrite prompts (src/lib/guardrails) and their defaults; do any run on CX/FW by default and change bodies; proposed state.
- S06 | Outbound network features: telemetry phone-home, cloud sync, auto-update, remote mode, tunnels
  Focus: Flags and settings that send data off-host or open non-loopback exposure (docs REMOTE-MODE.md, tunnels, cloud sync, update checks); defaults on this host; privacy on a private workstation; proposed state.
- S07 | Gateway memory / skills / context features (built-in memory, skills injection, system prompt injection)
  Focus: Repo rules: no gateway chaining, and OmniRoute memory does not replace ai-memory (docs/foundation-stack.md L20 in the repo). Which features exist, their defaults, whether any injects content into CX/FW prompts; proposed state.

For each feature:
- Read the implementation at the pin (codebase-memory project omniroute-dd6e9607e; sed -n for exact lines), the upstream docs in the checkout (docs/), the live value in the snapshot, and upstream issue/PR state (fetch https://api.github.com/repos/diegosouzapw/OmniRoute/... with context-mode).
- Judge quality, prompt-cache and token effects against the measured split.
- Propose exactly one resolution state, and the exact config that reaches it under the user decision.
Return only the JSON object.