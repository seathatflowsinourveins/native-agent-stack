# Decision: no silent fallback to an older model; StructuredOutput fields at the top level (2026-09-25)

**Decided by:** the agent-lab token-efficiency session, from agent-lab's record
`docs/tasks/2026-09-25-quality-optimization.md`, sections G3, G4, H1 and H2. That record is on agent-lab's default
branch `codex/native-expansion`, through agent-lab PRs #66 and #67. This change is on branch
`claude/model-fallback-guard-20260925`, rebased onto `origin/main@5abd17e4`.

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
  `adoption/agents/claude/source-scout.md`, `blind-judge.md`, `blind-lane-reviewer.md` and `blind-adjudicator.md`.
  For those four agents, the StructuredOutput sentence has to be in the agent body. That change is on the rollout's
  contract track for `adoption/agents/claude/`, and until it lands a new host's `source-scout` children do not get the
  rule.
- **Built-in agents.** Several of Claude Code's built-in agents also omit the user file, among them Explore and Plan.
  Their bodies cannot be edited. The rule reaches them only through a custom agent of the same name, as agent-lab does
  for Explore at project level, and the contract-track change does not cover them.

## Decision

1. The settings template sets `"CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK": "1"` in `env` and `"switchModelsOnFlag": false`.
   - When Opus 5.5's or a Fable model's safeguards flag a request, the request is not re-run on an older model.
     Without the guard, a cybersecurity flag re-runs it on Opus 4.8 and a biology flag re-runs it on Opus 5. This holds
     in the main thread and in every subagent, per the Claude Code 2.1.282 client code; it was not probed.
   - The request ends in a refusal. The exception is a server-armed silent-retry lane, which retries on the refusing
     model itself (see Evidence).
2. The example user-level `CLAUDE.md` gets two sentences.
   - Workers return StructuredOutput with the schema fields at the top level of the call arguments, never wrapped in an
     `input`, `output` or `result` key.
   - When a worker returns null or incomplete output, the coordinator first checks the worker's transcript for a
     safety refusal, because session limits and other errors also produce null results. After a refusal it edits the
     brief and retries on the current model, the documented pause option, and never accepts an older model's answer
     in its place.
3. **Template precedence.**
   - Applying the template sets both keys whatever the host had, as it already does for `model` and `effortLevel`. A
     re-apply resets a host that set `switchModelsOnFlag: true` or the variable to `"0"`.
   - While the variable is set, `/config` omits the "Switch models when a message is flagged" row. The client adds that
     row only when `MQt()`, which returns `WM()`, is true (`...MQt()?[{id:"switchModelsOnFlag",…}]:[]`).
   - A host that wants the automatic switch sets `switchModelsOnFlag` to `true` and the variable to `"0"` in its
     rendered template before applying it. The client parses the variable as a boolean (`M.bool`). Removing the two
     keys is not enough on a host that already applied them, because the merge keeps keys that the template no longer
     mentions.

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
  - `UQt(e)` returns `"subagent"` for any thread other than the main one before it reads `switchModelsOnFlag`, so a
    subagent's fallback runs without asking.
  - None of the setting's other reads stops a subagent's fallback either:
    - `wpo()` suppresses the fallback, but only on the main thread when no dialog can be shown;
    - the server lane, `apo()`;
    - `Spo()`;
    - a telemetry reason in `zDn()`;
    - the main thread's one-time preference question.
  - The setting alone therefore would have stopped none of the six incidents.
  - `WM()` is `!CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK && …`. Fallback target selection, `aHn()`, picks a target only
    when `WM()` is true.
  - The request handler runs on `(WM()||me)`, where `me` is a silent-retry attempt. That lane is armed by the server:
    `Vpe()` checks the model configuration (`convolute_arcades`) or a response header (`x-cc-tender-quilt`), and
    `Pbr()` then returns the refusing model itself. With the variable set, the only remaining retry is therefore on
    the same model, never on an older one.
  - The setting's own description in the client: "When safeguards flag a message, automatically switch to a different
    model to keep chatting. When off, your session will pause instead."
- **Undocumented variable.** `CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK` is in the client's env-var registry but not on
  code.claude.com/docs/en/env-vars (fetched 2026-09-25). `switchModelsOnFlag` is documented.
- **Why not probed.** Deliberately tripping a safety classifier is not an acceptable test.

### StructuredOutput (`native_proven` on the WSL authoring laptop)

- **Baseline (G3).**
  - Of agent-lab's first 3,275 workflow children (cut at 2026-09-24T03:24:08Z), 251 had at least one StructuredOutput
    schema error.
  - Among Sonnet children started before 2026-09-25T14:44:03Z, 54 of 266 `source-scout` children had one (20.3%).
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
2. **`switchModelsOnFlag: false` alone.** Insufficient, because it cannot stop a subagent's fallback. It is kept as the documented
   backstop: inert while the variable is set, and it governs the main thread again if a future client stops reading
   the variable.
3. **An `availableModels` allowlist that excludes Opus 4.8 and Opus 5.** The docs say an excluded fallback target does
   not run, so the flagged request ends with a refusal ("Restrict model selection"). This is documented, and the docs
   do not limit it to the main session. It is rejected for this profile for two reasons:
   - The family alias `opus` is a wildcard over Opus versions. Excluding older ones takes version prefixes or full IDs
     such as `claude-opus-5-5`, which disable that family's wildcard. The next Opus release would then stay excluded
     until someone edits the list, which works against always running the latest model.
   - It also restricts the `/model` picker.
4. **The StructuredOutput rule in agent bodies only.** This is required for the `omitClaudeMd` agents listed under
   Scope and stays on the rollout's track. The user-level file covers the other agents and workflow children.

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
The natural home is `scripts/adoption_status.py --client-wiring`, merged in #264, but it does not check the variable
yet. Until it does, a host can check its installed client by hand:

```sh
grep -a -c '!.\{1,4\}\.CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK&&' "$(readlink -f ~/.local/bin/claude)"
```

A count of 0 means the variable is no longer read in that form. Re-check the client code before relying on the guard.

The StructuredOutput sentence is adopted.
