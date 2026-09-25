# Decision: no silent fallback to an older model; StructuredOutput fields at the top level (2026-09-25)

**Decided by:** the agent-lab token-efficiency session, from agent-lab's record
`docs/tasks/2026-09-25-quality-optimization.md`, sections G3, G4, H1 and H2. That record is on agent-lab's default
branch `codex/native-expansion`, through agent-lab PRs #66 and #67. This change is on branch
`claude/model-fallback-guard-20260925`, based on `origin/main@ae3d3d37`.

**Scope:**
- `adoption/templates/claude.settings.template.json`. `tools/adoption/apply_claude_settings.py` merges it into a
  host's `~/.claude/settings.json`.
- `examples/claude-native/CLAUDE.md`, the portable user-level instructions.

`docs/decisions/2026-09-24-community-sweep.md` lists `switchModelsOnFlag` among "native settings without a dated
disposition". This record gives it one and covers the content-based fallback in subagents. The other settings on that
list stay open: `CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS`, `--safe-mode` and fallback model chains.

**Not covered:**
- **The ultracode recipe alone.** The portable ultracode settings file, `examples/claude-native/ultracode.settings.json`,
  does not carry the variable. A host that adopts only `recipes/claude-native-ultracode.md` therefore stays unguarded,
  although all six incidents below were workflow children. Changing that file also changes the recipe's embedded copy
  and the workflow contract configuration, so it is left to that recipe's owner.
- **Agents that skip the user file.** The user-level file does not reach agents that set `omitClaudeMd: true`:
  `adoption/agents/claude/source-scout.md`, `blind-judge.md`, `blind-lane-reviewer.md` and `blind-adjudicator.md`. It
  does not reach Claude Code's built-in Explore either. For those agents, the StructuredOutput sentence has to be in the
  agent body. That change is on the rollout's contract track for `adoption/agents/claude/`, and until it lands a new
  host's `source-scout` children do not get the rule.

## Decision

1. The settings template sets `"CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1"` in `env` and `"switchModelsOnFlag": false`.
   - When Opus 5.5's or a Fable model's safeguards flag a request, the request is not re-run on an older model.
     Without the guard, a cybersecurity flag re-runs it on Opus 4.8 and a biology flag re-runs it on Opus 5. This holds
     in the main thread and in every subagent, per the Claude Code 2.1.282 client code; it was not probed.
   - The request ends in a refusal. The exception is a client experiment arm that silently retries on the refusing
     model itself (see Evidence).
2. The example user-level `CLAUDE.md` gets two sentences.
   - Workers return StructuredOutput with the schema fields at the top level of the call arguments, never wrapped in an
     `input`, `output` or `result` key.
   - A worker that returns null or incomplete output may have been stopped by a safety flag. The coordinator edits the
     brief and retries on the current model, the documented pause option, and never accepts an older model's answer
     in its place.
3. **Template precedence.**
   - Applying the template sets both keys whatever the host had, as it already does for `model` and `effortLevel`. A
     re-apply resets a host that set `switchModelsOnFlag: true` or the variable to `"0"`.
   - While the variable is set, `/config` hides the "Switch models when a message is flagged" toggle, because the
     client's `MQt()` returns `WM()`.
   - A host that wants the automatic switch removes both keys from its rendered template before applying it.

## Evidence

### Model fallback (`source_review`: client code and official docs, not probed)

- **Incident.** On 2026-09-24, 11:39–19:29Z, six agent-lab workflow children requested `opus`, started on
  `claude-opus-5-5` and switched to `claude-opus-4-8` (222 assistant rows). No setting pinned Opus 4.8: there were no
  `ANTHROPIC_DEFAULT_*_MODEL`, `fallbackModel` or `availableModels` keys.
- **Official docs.** code.claude.com/docs/en/model-config, "Automatic model fallback" (fetched 2026-09-25):
  - "Fable 5.1, Fable 5, and Opus 5.5: biology-flagged requests re-run on Opus 5, and cybersecurity-flagged requests
    re-run on Opus 4.8."
  - "After a fallback, the session continues on the fallback model."
  - With `switchModelsOnFlag` set to `false`, "a flagged request then pauses the session with two options: switch to
    the fallback model, or edit the prompt and retry on the current model."
- **Client code (2.1.282).**
  - `UQt(e)` returns `"subagent"` for any thread other than the main one before it reads `switchModelsOnFlag`. The
    ask-first path, `wpo()`, requires `e.isMainThread`. The setting therefore governs only the main thread, and it
    alone would have stopped none of the six incidents.
  - `WM()` is `!CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK && …`. Fallback target selection, `aHn()`, picks a target only
    when `WM()` is true.
  - The request handler runs on `(WM()||me)`, where `me` is a silent-retry attempt. That lane is armed by `Pbr()`,
    which checks an experiment flag (`fRt()`) and returns the refusing model itself. With the variable set, the only
    remaining retry is therefore on the same model, never on an older one.
  - The setting's own description in the client: "When safeguards flag a message, automatically switch to a different
    model to keep chatting. When off, your session will pause instead."
- **Undocumented variable.** `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK` is in the client's env-var registry but not on
  code.claude.com/docs/en/env-vars (fetched 2026-09-25). `switchModelsOnFlag` is documented.
- **Why not probed.** Deliberately tripping a safety classifier is not an acceptable test.

### StructuredOutput (`native_proven` on the WSL authoring laptop)

- **Baseline (G3).** Of agent-lab's first 3,275 workflow children, 251 had at least one StructuredOutput schema error.
  `source-scout` had 54 of 266 (20.3%).
- **Interleaved A/B (G4, run `wf_134a2bb7-819`).**
  - Setup: 60 Sonnet 5 children at effort max, a six-field builder-shaped schema and the same read-and-report task.
    The sentence was appended in the treatment arm only.
  - Result: 5 of 30 control children had a schema error, against 0 of 30 in the treatment arm (one-sided Fisher
    p = 0.026). All five control failures were wrapped calls.
- **Sequential check (run `wf_7d5f1165-75b`).** The rule was present only through the user-level `CLAUDE.md`: 0 of 30
  children had a schema error.
- **Where the output is.** The captured prompts, results and analysis scripts are in the authoring host's local
  archive, `codex-ecosystem/state/schema-topfield-20260925/`, not in this repository.
- **Limits of the result.** It covers Sonnet 5 on Claude Code 2.1.282 only. G3 shows the Sonnet error rate moving with
  the client version: 26–37% on 2.1.278–2.1.280, 3–6% on 2.1.281 and 32% on 2.1.282.

## Alternatives considered

1. **Keep the automatic switch.** Rejected. The workflow requires the latest models, and on 2026-09-24 a silent
   downgrade led a review to be recorded as "verified on 5.5" when one verifier had run on Opus 4.8.
2. **`switchModelsOnFlag: false` alone.** Insufficient, because it never reaches subagents. It is kept as the documented
   backstop: inert while the variable is set, and it governs the main thread again if a future client stops reading
   the variable.
3. **An `availableModels` allowlist that excludes Opus 4.8 and Opus 5.** The docs say an excluded fallback target does
   not run, so the flagged request ends with a refusal ("Restrict model selection"), and this would be documented and
   subagent-wide. It is rejected for this profile for two reasons:
   - The family alias `opus` is a wildcard over Opus versions. Excluding older ones takes version prefixes or full IDs
     such as `claude-opus-5-5`, which disable that family's wildcard. The next Opus release would then stay excluded
     until someone edits the list, which works against always running the latest model.
   - It also restricts the `/model` picker.
4. **The StructuredOutput rule in agent bodies only.** This is required for the `omitClaudeMd` agents listed under
   Scope and stays on the rollout's track. The user-level file covers every other session and workflow child.

## Comparison that would overturn it

- **Model fallback:**
  - A documented control that stops the content-based fallback in subagents without a version-pinned allowlist.
    Switch to it.
  - A client release that no longer reads the variable in `WM()`, or that widens the silent-retry lane to other
    models.
  - A demonstrated need for older-model answers that outweighs refusals on flagged requests.
- **StructuredOutput:** a same-version interleaved A/B, run the G4 way, that shows no reduction, or a client version
  that fixes the wrapping. Then remove the sentence.

## Watch

The fallback variable is undocumented, so that part stays keep-but-compare, and the template sets
`"autoUpdatesChannel": "latest"`. Re-check it after each Claude Code update on each host. agent-lab's release-watch
probe, `tools/compare/effort/max-ultracode-probe.sh --check-fallback-guard`, exits 3 when the installed client no longer
reads the variable. That probe checks only the `WM()` read; it does not detect a widened silent-retry lane.

This catalog has no automated counterpart yet, so a host that follows only the catalog is not watched until one exists.
The natural home is the adoption status check's client-wiring report. Until then, a host can check its installed
client by hand:

```sh
grep -a -c '!.\{1,4\}\.CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK&&' "$(readlink -f ~/.local/bin/claude)"
```

A count of 0 means the variable is no longer read in that form. Re-check the client code before relying on the guard.

The StructuredOutput sentence is adopted.
