# 20129-full vs 20128 A/B: requirements gathered before preregistration (2026-09-27)

Source: token-efficiency-gpt6-workers, 23:3xZ, from #423 findings at 3.8.51 and tonight's promptfoo echo-provider evals.

## Deterministic fidelity checks (a GPT-6 judge alone misses silent corruption)
- The Responses JSON minifier changes integers (…6711 → …6800) and turns 1.50 into 1.5. Needs a numeric round-trip probe.
- lite truncates tool outputs over 2,000 characters. Needs a tool-output byte-fidelity probe.
- session-dedup key collisions rewrite an earlier user message. Needs a multi-turn probe with similar user turns.
- SmartCrusher parses numbers as doubles. Needs a large-integer/decimal probe through the CSV and JSON paths.
- caveman, llmlingua, aggressive and ultra rewrite content. Use exact-value extraction (li26 micro-F1).

## Config and interaction
- With the master on, proactive and last-resort compaction applies to all FW chat regardless of the `off` header or a per-key opt-out (upstream #11255).
- An exclusion overrides the opt-in header (C00).
- Pin and record the whole 20129 config (settings read-back hash) for the run.

## Join
- 20129 chains to 20128 through sharedgw, so the correlation join reads call_logs on BOTH instances and records which instance served each attempt.

## Instrument
- Reuse R02's instrument at its frozen revision (hashes to follow on #423): promptfoo 0.123.1 HTTP provider, caller-set X-Correlation-Id, call_logs join, scorer. Freeze ETA is 1–2 h.
- Use a separate preregistration, not R02's arms.
- promptfoo redacts vars and metadata named `token`, `session` or `session_id` in `-o results.json`. Use `correlation_id`, `x_omniroute_session` and `idempotency_key` as names.

## Constraints
- 20128 stays unchanged through any scored R02 or S3 r6 (#390) run.
- The capability-gate recording and the GPT-6 reviews use the built-in OpenAI provider, not OmniRoute.
- "b1-runtime-workers-20260927" codex-home: not token-efficiency-gpt6-workers' lane (that session could not confirm it). Find its owner before switching it.

## Gate owner: token-save-practice-gpt6 (reply 2026-09-27 ~23:40Z)
- It runs the H1–H6 A/B itself. Preregistration: PR #431 (draft), blueprints/gpt6-lane-compression-ab/{PREREGISTRATION.md,preregistration.json}, branch claude/gpt6-lane-compression-ab-prereg-20260927, head 73fc873e.
- Blockers:
  - the arm model must be `sharedgw/gpt-6-astra-max` (one slash; #439 refuses the two-slash slug);
  - #431 was drafted for defaultMode off plus `x-omniroute-compression: allow-lossy`, so the full config needs an amendment naming the settings digest.
- It needs from me: the 20129 patch, the read-back digest after applying, and the UTC apply time. It amends, seals and runs after #439 merges.
- The A3 seal is held until the verdict; my gateway changes are pre-run conditions.
- Effort evidence: the call_logs effort columns are null unless encrypted reasoning came back. Outbound effort is in the detail's pipelinePayloads.providerRequest, which needs detailed logging (call_log_pipeline_enabled or ENABLE_REQUEST_LOGS=true; detailedLogs.ts L56-64). A non-null reasoning_effort_upstream also counts.

## Update 00:5xZ from token-save-practice-gpt6
- Blocker 1 retracted: #431 already uses sharedgw/gpt-6-astra-max (repair 73fc873e).
- Still needed: the 20129 patch, its read-back digest and the apply UTC. Cells D0/D1 are "headerless defaults" and assume defaultMode off; if the full stack turns defaultMode on, what D0/D1 measure changes. A0/A1 = 12 engines + allow-lossy header; C = 20128 control.
