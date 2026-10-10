# Context and tokens (`token-efficiency`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## context-compaction

**Status:** default. **Default:** Native auto-compaction at the model's default window, with `/compact <focus>` at natural breaks, `/clear` between unrelated tasks and a Compact Instructions section in CLAUDE.md

- **Route:** Manual levers apply to top-level interactive sessions; `-p` workers, Workflow children and subagents compact automatically; re-inject must-keep state with a SessionStart hook matching `compact`
- **Alternatives, ranked:** 1. SessionStart(compact) hook; 2. Per-model `/autocompact` window behind a 200K gateway
- **Rejected:** A standing `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` or lowered window; Disabling auto-compaction; Fixed-percentage 'rot boundary' rules
- **Evidence:** context-window.md what survives compaction; context-token-O3, O15, O16; Measured upstream: compaction pays only on long runs (Anthropic, optimizing-for-cost-and-intelligence)
- **Notes:** No quality loss measured or claimed: this is the native default; no override is set on the host or template.
- **Supersedes:** topic: auto-compact threshold (window now saved per model); M16 (compaction retraction defect fixed in 2.1.293); M17 (SessionStart compact matcher is the documented route)
- **Overturn when:** A paired same-task run shows an earlier window keeps quality at lower cost, or a release changes compaction.

## prompt-caching

**Status:** default. **Default:** Native automatic prompt caching with the default TTL buckets and no TTL overrides

- **Route:** The subscription main conversation, `-p` workers and Agent SDK turns get the 1-hour TTL within plan usage; subagents, Workflow children, API keys, usage credits and cloud providers get 5 minutes; model switches and plugin toggles invalidate the prefix, while CLAUDE.md edits and MCP connects under deferred tool search keep it
- **Alternatives, ranked:** 1. `promptCacheTtl: 1h` scoped to API-key runs with 5-60 minute idle gaps; 2. `--exclude-dynamic-system-prompt-sections` for scripted fan-out; 3. `experimental.cacheTtl` on one subagent that idles
- **Rejected:** A global 1-hour TTL environment override; Keep-alive requests
- **Evidence:** prompt-caching.md TTL buckets; context-token-O9, O11, O12, O18; Measured here: daily prompt-cache hit 94-97.5% (ccusage)
- **Notes:** No quality loss measured or claimed: caching does not change outputs.
- **Supersedes:** R53, R59 and the 1-hour TTL topic (buckets now native); AN-23 (experimental.cacheTtl is fourth in precedence)
- **Overturn when:** A release changes the TTL buckets, or a measured cache-hit drop on a run shape we use.

## output-compression

**Status:** default (scoped). **Default:** Native output bounds and delegation: `BASH_MAX_OUTPUT_LENGTH`/`bashOutputMaxChars` (30,000 characters by default), MCP results over 25,000 tokens saved to a file, filtering hooks, and subagents for large reads

- **Route:** context-mode, rtk and headroom stay installed by owner direction; none becomes the default without a paired quality-parity run (a J7 class is requested)
- **Alternatives, ranked:** 1. headroomlabs-ai/headroom; 2. rtk-ai/rtk; 3. mksglu/context-mode
- **Rejected:** JuliusBrussee/caveman output styles; Raising `MAX_MCP_OUTPUT_TOKENS` globally
- **Evidence:** env-vars.md and settings-reference output limits; Measured usage: rtk 13.9% of 1,243.1M input tokens saved (rtk gain, all time); context-mode 32,484 Codex calls in 24 h and 743 MB kept out of context over 5 days; headroom 0 compressions (not in the request path)
- **Notes:** Token reductions are measured and quality parity is not, so no tool is the default. Usage observed on 2026-10-09 (information, not a selector): rtk 13.9% of 1,243.1M input tokens (rtk gain), context-mode 32,484 Codex calls in 24 h, headroom 0 compressions because it is not in the request path. Adjudicated: native default with headroom ranked first on its published fidelity evals; the refuter upheld it. Owed: a paired quality-parity run per mechanism (a J7 class).
- **Supersedes:** M35 (pin and proxy facts moved)
- **Overturn when:** A paired same-task run shows a tool at quality parity with a measured saving; it then becomes the default for the mechanism it covers.
