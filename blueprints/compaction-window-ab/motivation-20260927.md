# Claude child token diagnosis, session-01, 2026-09-27 (measured from native transcripts)

Supplied historical motivation, copied on 2026-09-27. Native session/run labels
were replaced with local ordinals; no personal paths were present. Measurements
are preserved as supplied, not independently remeasured during this draft.

Population: 52 workflow children, 7 runs (run-01, run-02, run-03, run-04, run-05, run-06, run-07).
Provider usage (child-usage.mjs by_resolved_model): input+cache_write 11,639,727; cache_read 398,038,533; output 3,672,138. Requests 4,781 (avg context/request ~83K).
Top children: build 258 req, maxctx 936,520, cache_read 93.2M; research:agentmemory 283 req 69.6M; research:hindsight 247 req 65.3M (Hindsight researched by 3 Claude lanes across 3 workflows: 65.3M+44.0M+33.8M).
Containment (M3 shape): 588 tool results >5,120 B = 69% of 9.45 MB result bytes (target <=20%); big results by tool: Read, Bash, and ctx_execute/ctx_search printing large output.
Transcript bytes by kind: thinking 12.65 MB (2,083 blocks, effort max); tool_result 10.12 MB; tool_use 2.93 MB; per-call hook_success attachments ~4.0 MB (PreToolUse/PostToolUse Bash and context-mode); total_tokens_reminder 1.40 MB; first-prompt snapshots/instructions/skill listing ~5.8 MB.
Native levers verified in official docs (code.claude.com model-config, fetched 2026-09-27): Opus 4.7+ and Sonnet 5 run a native 1M window and auto-compact at ~967K by default; CLAUDE_CODE_AUTO_COMPACT_WINDOW (plain token count) or the auto-compact window setting lowers it; CLAUDE_CODE_DISABLE_1M_CONTEXT=1 holds sessions at 200K. Weekly limit is seat-based, shared across models (costs doc).
Wasted: stopped-and-relaunched S3 arms run (run-04) 36.4M cache reads; GPT-6 wrapper stages dispatched as source-scout never ran (role conflict).
