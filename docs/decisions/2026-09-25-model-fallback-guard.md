# Decision: no silent fallback to an older model; StructuredOutput fields at the top level (2026-09-25)

**Decided by:** the agent-lab token-efficiency session, from agent-lab's record
`docs/tasks/2026-09-25-quality-optimization.md`, sections G3, G4 and H1. That record is on agent-lab's default branch
`codex/native-expansion`, through agent-lab PRs #66 and #67. This change is on branch
`claude/model-fallback-guard-20260925`, based on `origin/main@ae3d3d37`.

**Scope:**
- `adoption/templates/claude.settings.template.json`. `tools/adoption/apply_claude_settings.py` merges it into a host's
  `~/.claude/settings.json`.
- `examples/claude-native/CLAUDE.md`, the portable user-level instructions.

`docs/decisions/2026-09-24-community-sweep.md` lists `switchModelsOnFlag` among "native settings without a dated
disposition". This record gives it one and covers the automatic fallback in subagents. The other settings on that list
stay open: `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS`, `--safe-mode` and fallback model chains.

## Decision

1. The settings template sets `"CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1"` in `env` and `"switchModelsOnFlag": false`.
   - When Opus 5.5's safeguards flag a request, the request ends in a refusal. It is not silently re-run on Opus 4.8.
     This holds in the main thread and in every subagent, per the Claude Code 2.1.282 client code; it was not probed.
   - A coordinator re-runs a flagged child with a rephrased brief. It never accepts an older model's answer as the
     latest model's.
2. The example user-level `CLAUDE.md` asks workers to return StructuredOutput with the schema fields at the top level
   of the call arguments, never wrapped in an `input`, `output` or `result` key.

## Evidence

### Model fallback (`source_review`: client code and official docs, not probed)

- **Incident.** On 2026-09-24, 11:39–19:29Z, six agent-lab workflow children requested `opus`, started on
  `claude-opus-5-5` and switched to `claude-opus-4-8` (222 assistant rows). No setting pinned Opus 4.8: there were no
  `ANTHROPIC_DEFAULT_*_MODEL`, `fallbackModel` or `availableModels` keys.
- **Official docs.** code.claude.com/docs/en/model-config, "Automatic model fallback" (fetched 2026-09-25): a request
  that the classifier flags is re-run on Opus 4.8, and "the session continues on the fallback model".
- **Client code (2.1.282).**
  - `UQt(e)` returns `"subagent"` for any thread other than the main one before it reads `switchModelsOnFlag`. That
    setting therefore governs only the main thread, so it alone would have stopped none of the six incidents.
  - The fallback master switch `WM()` requires `!CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK`, and the switching path requires
    `WM()`.
  - The client's own description of the setting: "When safeguards flag a message, automatically switch to a different
    model to keep chatting. When off, your session will pause instead."
- **Undocumented variable.** `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK` is in the client's env-var registry but not on
  code.claude.com/docs/en/env-vars (fetched 2026-09-25).
- **Why not probed.** Deliberately tripping a safety classifier is not an acceptable test.

### StructuredOutput (`native_proven` on the WSL authoring laptop)

- **Baseline (G3).** Of agent-lab's first 3,275 workflow children, 251 had at least one StructuredOutput schema error.
- **Interleaved A/B (G4, run `wf_134a2bb7-819`).**
  - Setup: 60 Sonnet 5 children at effort max, a six-field builder-shaped schema and the same read-and-report task.
    The sentence was appended in the treatment arm only.
  - Result: 5 of 30 control children had a schema error, against 0 of 30 in the treatment arm (one-sided Fisher
    p = 0.026). All five control failures were wrapped calls.
- **Sequential check (run `wf_7d5f1165-75b`).** The rule was present only through the user-level `CLAUDE.md`: 0 of 30
  children had a schema error.

## Alternatives considered

1. **Keep the automatic switch.** Rejected. The workflow requires the latest models, and on 2026-09-24 a silent
   downgrade led a review to be recorded as "verified on 5.5" when one verifier had run on Opus 4.8.
2. **`switchModelsOnFlag: false` alone.** Insufficient, because it never reaches subagents. It is kept as the documented
   backstop: inert while the variable is set, and it governs the main thread again if a future client stops reading
   the variable.
3. **An `availableModels` allowlist without Opus 4.8.** Rejected. It restricts `/model` too, and it blocks the fallback
   only where the allowlist check applies.
4. **Only in the agent bodies (StructuredOutput).** Complementary, and it stays on the rollout's contract track for
   `adoption/agents/claude/`. The user-level file reaches every session, workflow children included.

## Comparison that would overturn it

- **Model fallback:**
  - A documented control that covers subagents. Switch to it.
  - A client release that no longer reads the variable. agent-lab's release-watch probe
    `tools/compare/effort/max-ultracode-probe.sh --check-fallback-guard` exits 3 in that case.
  - A demonstrated need for Opus 4.8 answers that outweighs refusals on flagged requests.
- **StructuredOutput:** a same-version interleaved A/B, run the G4 way, that shows no reduction, or a client version
  that fixes the wrapping. Then remove the sentence.

The fallback variable is undocumented, so that part stays keep-but-compare and is re-checked on each Claude Code update.
The StructuredOutput sentence is adopted.
