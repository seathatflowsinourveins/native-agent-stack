# B13 frozen preparation, held pending native prerequisites

No model or container job has run. This directory is tooling/configuration,
outside dated execution evidence. It defines the trial inputs and acceptance;
it contains no custom runner. Cases are in `cases.json`, and native Promptfoo
configuration preparation is `promptfoo.codex.json`.

## Native harnesses and unchanged comparator

- Claude: the installed native `claude plugin eval <plugin> --ablation with-without --judge-model opus --runs 3`, under the shared Claude session lock. Freeze the installed client's exact supported argv before execution.
- Native paired review/grading: Anthropic skill-creator at `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4:skills/skill-creator`, using grader, analyzer, aggregate_benchmark.py and the static native viewer. This is a hook trial, so both arms keep the same selected skill catalog; the treatment difference is only the hook.
- Codex: Promptfoo 0.123.1's native `openai:codex-sdk` provider. Its installed schema supports model, model_provider, cli_env, cli_config, working_dir and inherit_process_env. The provider passes config.model to threadOptions unchanged, preserving `cx/gpt-6.1-sol` (unlike Harbor's slash stripping).
- Separate unchanged prompt-only comparator: `alex-macra/claude-codex-skills-assembly@aba8bedadd83998cd2004838683ee41eaa449c1f:hooks/skill-activation.py`. Use its supported catalog/routing overlay in a separate owned root; do not modify its executable, run its bundled guard installer, or mix its counters into the two-arm aggregate.

At the native Codex pin `a956835d020762cb2b570053af06f643a11c0ecc`,
`codex-rs/core/config.schema.json:definitions/SkillsConfig/bundled` references
`BundledSkillsConfig/enabled` (boolean, default true, closed object). The
preparation's `cli_config.skills.bundled.enabled: false` is supported source
configuration. Equal instruction/context bounds and bundled isolation still
need an actual catalog control; a schema field is not proof of discovery absence.

No active settings or trust stores are copied. The config's `@RUN_DIR@` and
`@CODEX_BIN@` are explicit preparation locators, not executable defaults.
The authorized owner resolves only these locations after prerequisites, retains
the exact final configuration/hash, and uses upstream `promptfoo eval -c` with
cache disabled and concurrency one. There is no proposed trust bypass flag.

## Before any benchmark

1. Qualify the native keyless 21128 route with a fresh answer. The Harbor source option is not authentication acceptance, and native Harbor 0.24 is not currently the installed 0.23. Currency/isolated qualification precedes a Harbor smoke. Source details are in the dated S9 decision.
2. The Codex SDK hook trust/apply ticket remains unresolved. Inspect native hook discovery and run a trusted positive hook-firing control. Retain an untrusted/skipped control separately; a skipped treatment cannot be called zero gain.
3. Stage equal owned project inputs in both arms: the parent S1 workflow manifest with python_regex triggers, its central manifest and selected pinned skill folders, and identical native role files. Read-only and action scope must match. Skill availability/listings remain identical; hook-off omits only the proposed hook groups. Do not copy account, credential, auth or active configuration files.
4. Freeze actual fixture bytes and hashes after staging the supplied synthetic fixtures identically in both arms. Preserve the seven case prompts/polarities and negative log-fetch/list/summarize/status cases. The instruction case stages fixtures/instructions at the working root; do not copy its deliberately stale instructions over a real checkout. No expected answer is put in the executor prompt. Parent S1/role/skill staging and final per-arm hashes remain pending; this preparation claims no run-ready fixture hash.
5. Freeze client/provider/model/effort, task oracle, repetitions (three per case/arm), native output and counter capture. Use Opus/max for paired judgments and Sol/max for the Codex arm; retain requested and actual identities separately.

## Required observations and acceptance

For each native event/client, retain actual firing or a declared inapplicable
channel. Claude child positives require the native role's explicit Skill grant.
They also require an accepted active S1 caller route; current inert Skill-grant
previews do not count as delivery or a positive firing control.
Blind/unknown/Skill-less children are negatives. Codex SubagentStart remains
pending the S10 capability contract; do not count a Claude role filename as proof
or report a zero-denominator role load rate as passed.

Inspect actual native instruction loads/Skill calls/rollout reads using existing
native histories and the maintained census tools. Output mentioning a skill is
not invocation evidence. Score artifact correctness and the response format
separately against the frozen fixture oracle. Native Promptfoo's is-json
assertion checks format only; it is not the correctness or load-rate bar.
Concrete fixture oracles are the mock-export cause (CI), R1/R2 handled and R3
left informational (review), and pnpm scripts plus preserved generated/external
boundaries (instructions). Read-only cases return exactly the supplied check,
thread, excerpt or PR-state data. These are local synthetic fixtures;
they are not production logs or unchanged upstream tests.

B13 passes only when each exercised client has an actual treatment firing
positive control, measured positive load-rate gain above zero, adjacent-negative
false-hint rate at most 10%, and no task pass-rate regression. Keep passing and
failing conditions, unavailable prerequisites, failed attempts and unknown usage.
Never sum overlapping parent/child or cache/provider subsets. Native skill-creator
grading/analyzer/comparator and review outputs stay identifiable as native harness
operations; local fixture assertions stay local integration evidence.

The stateless ambiguity is preregistered: fetch-only PostToolUse events are
silent because their payload lacks original user intent. The full negative
set remains in the score; it is not excluded to improve the reported gain.
A measured alternative can overturn this choice and the held prototype. No
production hook registration occurs before B13 and command-center ACK.
