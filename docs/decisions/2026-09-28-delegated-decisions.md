# Decision: delegated coordination decisions: M1/M2, M3, M4, the #444 trading-lane acknowledgement and Gate A ownership (2026-09-28)

**Decision practice (2026-09-28):** resolve the named coordination items through primary-source research, independent refutation and the declared two-family rule; [Claude Code's best practices](https://code.claude.com/docs/en/best-practices) supply the behavior-validation basis. The delegation is a dated trigger.

The decisions covered the open items from the 2026-09-28 status report:
- the user-level instruction findings M1/M2, M3 and M4 from the AN-13 `/doctor prompt-audit` run;
- the trading-lane acknowledgement that `lane:shared` PR #444 needed (`docs/lanes.md:146-150`);
- ownership of Gate A, the #381 token-adoption E2E.

Each item went through these steps:
1. **Primary-source research.** Workflow `wf_811a77e9-a4e` ran one `stack-researcher` (Opus, max) per item. An `evidence-reviewer` (Opus, max) then tried to refute each recommendation. All five came back `upheld: false`, each with amendments, and this record applies them.
2. **A second family** where the item changes an instruction. GPT-6 `gpt-6-astra` at effort max ran through `codex exec -s read-only` on a frozen packet, and an independent Claude `evidence-reviewer` lane read the same packet.
3. **One objection round with the live peer sessions**, through SendMessage: `resolve-prompt-audit-findings` (owner of #444 and #460), `cloudflare-security-audit-sota-review` (owner of the skills trial), `token-save-practice-e2e-status` and `native-agent-stack-84` (the trading lane).

The returned lane output is in
[`evidence/artifacts/delegated-decisions-20260928/`](../../evidence/artifacts/delegated-decisions-20260928/README.md). The peer positions, the #444 acknowledgement and the Gate A liveness observations are quoted in its [`coordination.md`](../../evidence/artifacts/delegated-decisions-20260928/coordination.md).

## Decision

| Item | Decision | Two-family result | Peers | Executed by |
| --- | --- | --- | --- | --- |
| M1/M2, top-rule trigger (`~/.claude/CLAUDE.md:5`, copied at `AGENTS.md:3`) | **Keep verbatim.** No edit to either file. | GPT-6: "DECISION: keep". Claude lane: "DECISION: keep". The refuter rejected the narrowing. | No position on the merits; the #444/#460 owner: "no objection" to keep ([coordination](../../evidence/artifacts/delegated-decisions-20260928/coordination.md)) | (no change) |
| M3, model line (`~/.claude/CLAUDE.md:40`) | **Change** "Opus 5.5 at effort max for …" to "The latest Opus at effort max for …". The portable copy `examples/claude-native/CLAUDE.md:41` changes to "the latest Opus" to match. | GPT-6 and the Claude lane each returned "DECISION: latest-opus" with the identical line | The #444/#460 owner had no objection to the earlier "keep"; the change to "latest Opus" was sent as a correction, with no reply by 16:25Z ([coordination](../../evidence/artifacts/delegated-decisions-20260928/coordination.md)) | This coordinator: host edit with backup and read-back, and the portable copy in this PR |
| M4, the `verification-before-completion` trial skill | **Remove now** under the skills trial's in-force rule (`docs/decisions/2026-09-25-skills-trial-and-usage.md:284-286`). That covers the listing, the builder preload and the host install. | GPT-6: "VERDICT: conflict", "Disposition: remove now". Claude: the refuter flagged the untested rule, and the coordinator and the trial owner each found the conflict on a full read. | Trial owner: "yes, it triggers :284-286", and it will apply the removal. #460's owner: no objection. | The skills-trial owner, in one PR carrying #381 Amendment 3 |
| #444, trading-lane acknowledgement | **The live trading session acknowledges**, as `docs/lanes.md:149` requires. No acknowledgement is made on the delegation, and there is no lanes.md change. | n/a | #444's owner required the trading lane's own acknowledgement naming F4. The trading session posted it. | `native-agent-stack-84`, comment on #444 at 2026-09-28T16:04:57Z, reviewing F4 at head `eb12630a` |
| Gate A, #381 ownership | **This coordinator session owns Gate A** from 2026-09-28. | n/a | `token-save-practice-e2e-status` declined and asked this session to take it | This session; see "Gate A plan" |

## Evidence by item

### M1/M2: keep the top rule's trigger

- Anthropic's guidance for the running model uses the same construction. [Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5) says the model "tends to get to work quickly". Its sample sentence begins "Before taking any action, explore broadly with tool calls". So "any action" is not a defect for this model.
- Keep the research trigger's scope while evaluating its behavior against [Claude Code's best practices](https://code.claude.com/docs/en/best-practices) and the [prompt-audit rubric at 33375500](https://github.com/anthropics/skills/blob/33375500bcea98d610eb30ce10ac4e59b89c390d/skills/claude-api/shared/prompt-audit.md). The recorded harm was under-application: self-written strategy arms.
- No retained record shows over-application. The trivial-step case is only a hypothetical in the audit's own return (`evidence/artifacts/prompt-audit-20260927/round1/claude.json:148`).
- The [Claude Code best practices](https://code.claude.com/docs/en/best-practices) say to review CLAUDE.md "when things go wrong" and to "test changes by observing whether Claude's behavior actually shifts". Neither wording has been behavior-tested.
- Decided wording stays verbatim (`docs/decisions/2026-09-26-harness-rules-cleanup.md:15-16`). `AGENTS.md:3` is carried by #444.

### M3: "The latest Opus"

- Anthropic's prompt-audit rubric (`anthropics/skills@33375500bcea98d610eb30ce10ac4e59b89c390d:skills/claude-api/shared/prompt-audit.md:127-141`) covers CLAUDE.md. It lists version numbers as volatile specifics that "nothing re-checks", and says "pinned model names silently degrade after the next release" and "State the current rule".
- The repository's rule is the latest model: "The workflow requires the latest models" (`docs/decisions/2026-09-25-model-fallback-guard.md:119-120`). The same record rejected a version-pinned allowlist because "The next Opus release would then stay excluded until someone edits the list" (`:127-129`).
- A bare "Opus" would drop that constraint. The [model-config](https://code.claude.com/docs/en/model-config) alias definition governs the setting value, not the wording of an instruction, and what the alias resolves to depends on the provider. The refuter and both lanes rejected bare "Opus" on this ground.
- The wording controls no runtime. Whether a run followed the rule is shown only by the model ID the run itself recorded (`docs/decisions/2026-09-25-model-fallback-guard.md:68-70` records children that requested `opus` and switched to `claude-opus-4-8`, and `:119-120` a review recorded as "verified on 5.5" after that switch).
- The dated policy and evidence at `docs/decisions/2026-09-27-claude-harness-settings.md:10-14` retain the Opus role bindings under the [native subagent model contract](https://code.claude.com/docs/en/sub-agents); preserved audit artifacts carry the original executed inputs.
- The coordinator row at `examples/claude-native/workflows/README.md:486` also names "Opus 5.5" and is asserted by `test-contract-mutations.mjs:92`. It belongs to the model-currency lane (#434) and is unchanged here.

### M4: remove the trial skill

- **The rule.** The in-force rule at `docs/decisions/2026-09-25-skills-trial-and-usage.md:284-286` reads: a trial skill that "gives instructions that conflict with CLAUDE.md/AGENTS.md once actually read in full → remove it immediately, not at the trial window's end".
- **The conflict.** The pinned skill (obra/superpowers@8ca22dba, `SKILL.md` sha256 `2befe7fc…`; the upstream path has not changed since, so there is nothing to re-pin to) conflicts with `AGENTS.md:16` ("Reuse passing evidence when its inputs still match and run only checks needed for a concrete gap"). The conflicting lines:
  - L20: "If you haven't run the verification command in this message, you cannot claim it passes";
  - L28: "Execute the FULL command (fresh, complete)";
  - L42: "Previous run" listed as Not Sufficient for "Tests pass".
- **GPT-6's case.** Tests passed earlier and their inputs are unchanged. Reporting the result without re-running violates the skill; re-running only to satisfy the message boundary violates AGENTS.
- **What held.** GPT-6 judged the broad triggers at L108-114 compatible with `AGENTS.md:15`. The skill's principle (evidence before claims) stays carried by `AGENTS.md`, [`docs/acceptance-evidence-policy.md`](../acceptance-evidence-policy.md) and the token-lanes evidence sentence.
- **Supersedes.** This overrides the deferral to the 2026-10-25 with/without comparison. #460's M4 record, merged at `8d8f79cd`, names exactly this overturn: "a two-family judgment finds that the skill's instructions conflict with CLAUDE.md or AGENTS.md once read in full. The skills trial's rule then removes it now" ([`2026-09-28-an13-m4-m5.md:240-242`](2026-09-28-an13-m4-m5.md)). Its limitations (`:251-258`) record that its lanes did not test that rule. Its two-family rejection covered the prompt-audit rewrite, not the trial rule.
- **Scope, per the trial owner's source check at `3058b237`.** The removal changes these together:
  - the manifest row, which becomes excluded;
  - the template `skillOverrides` entry and the budget;
  - the three `isolated-builder.md` copies;
  - the landscape-sweep `TEMPLATE_SKILLS` and `templates.json`;
  - `test-envelope.mjs:505` and `test-contract-mutations.mjs:70-73`;
  - the prose at `examples/claude-native/workflows/README.md:19,81`, `recipes/claude-native-ultracode.md:156`, `adoption/bootstrap.md:346-347`, `catalogs/foundation/practice-references.json:73` and `docs/community-native-practice.md:190`;
  - an evidence sentence added to `adoption/hooks/claude/token-lanes-block.builder.md`. #456 left it out only because it duplicated the preload.
  The host uninstall is the upstream `skills remove verification-before-completion -g -y`, run after merge, because `install_skills.py` has no remove mode.
  **Dated note, 2026-09-28 (after #464 merged at `c0966da2`):**
  - This unscoped form is the complete one. Its one precondition is to assert first that no other agent holds a same-named copy, because without `-a` skills 1.7.0 targets every agent (`dist/cli.mjs` L6834-6838).
  - An agent-scoped `-a claude-code codex` does not remove the skill. A remaining detected universal agent resolves to the canonical `.agents/skills` directory (`getAgentBaseDir` L2214, `isUniversalAgent` L2180). That sets `isStillUsed`, which keeps the canonical folder and its lock entry (L6883-6907).
  - The skills-trial owner found this during the uninstall. It was re-read from the `skills@1.7.0` npm package.
- **#381 Amendment 3.** The #381 role-body table pins `isolated-builder.md` at `57452a64…`, and main still equals it. The removal therefore lands with a dated pre-execution Amendment 3 in the same PR, authorised by the Gate A owner.

### #444: acknowledgement from the live trading lane

- `docs/lanes.md:149` requires "the other lane's acknowledgement, as a comment or review on the PR". #444's owner would not accept an acknowledgement made on a delegation, and required one that names F4 explicitly.
- A trading-lane session, `native-agent-stack-84`, went live on 2026-09-28. It reviewed the F4 hunk (`AGENTS.md:73-74`, the 2021-holdout wording) and posted the acknowledgement with no objection, finding the prohibition widened, not weakened.
- #446 had already merged on the user's own per-PR instruction, recorded on that PR.
- Still open: #417 and #430 are also `lane:shared` and waiting for the same acknowledgement. #430 is itself a `docs/lanes.md` edit. They go to the trading lane through their owners.

### Gate A: ownership

- No live session holds Gate A:
  - the recorded owner `token-stack-e2e-proof` is not in the `ListAgents` output of 2026-09-28;
  - the ai-memory handoff list holds no Gate A handoff;
  - no Lane B coordination ledger is recorded in the repository or named by a peer (outside directories were not searched).
- `docs/lanes.md:155` limits handoffs to a live owner. The E2E status peer declined, because it is busy with OmniRoute and the OpenHands PRs.

## Gate A plan (public part)

The private specification copies, retained inputs and host paths stay out of this record ([RUNBOOK](../../evidence/artifacts/token-adoption-e2e-20260926/RUNBOOK.md) freeze rules).

0. **Preflight (read-only).**
   - **Done:** the `RUNBOOK.md:23-30` frozen input `/summary/needs_host/macos-arm64` gives sha256 `6899e551b2bea3918b47cba1b41e27e59d8f5cb12a681f98cc77f73d66a2a2c1`, 6,552 bytes and 60 records at `c7b78854`, `27bf3108` and `3058b237`. It matches `preregistration.json` `tasks[9].frozen_input`.
   - **Done:** the AA and full-save specifications were copied from a session scratch directory to a private 0700 state directory, with sha256 `d744ef01…` (AA) and `560d6432…` (full-save).
   - **Open:** the retained 150-entry history report. The source receipts pin its bytes: #296 `/tools/2` `baseline_sha256` `82e92492…` at 891,615 bytes, and #343 `/tools/6` `baseline_sha256` `5939b545…`. It is recovered only if a regeneration at the original revision matches those digests. Otherwise launch stays blocked (README "missing retained history report also blocks launch").
   - **Open:** the six original command identities for `tests.test_host_requests`.
1. **The PR-A continuation:** publication of the sanitized, regenerated post-fix baseline, which is a merge-before-run gate (README:417-420), then the M-R1 freeze.
2. **Amendment 3 lands with M4.** The seal then re-derives all six token-lanes block hashes and the five role-body hashes at the execution revision.
3. **The Codex half of the collector join**, proved before the RUNBOOK queries (RUNBOOK:485-491).
4. **A sealed window W** agreed with the live peers. It needs:
   - no carrier or instruction change during the run;
   - #444 merged or held;
   - a live Codex capacity check (the dashboard's "blocked until 2026-09-30" is a recorded reset, not a gate).
   The paper lane and the OmniRoute A/B that were running on 2026-09-28 set W's earliest time.

## Alternatives considered

- **M1/M2, adopt the narrowing.** "Before you write, build, install or adopt anything … for each such step." Rejected by both lanes and the refuter: there is no recorded harm or behavior test establishing that narrower trigger, and the cited Opus 5.5 guidance uses "any action". The declared rule-carrier scope stays intact.
- **M3, keep "Opus 5.5".** It pins a release that nothing re-checks. **Bare "Opus":** drops "latest".
- **M4, keep until 2026-10-25** (the peers' first position, and #460's): it did not test the in-force rule. **Keep, with a recorded reading that reconciles the two texts:** GPT-6 found that this would override the skill's explicit freshness requirement. **Edit the vendored text:** self-writing without an upstream source.
- **#444, acknowledge on the delegation, or amend lanes.md with a parked-lane rule:** unnecessary once a trading session was live. The amendment would itself be `lane:shared`.
- **Gate A, assign `token-save-practice-e2e-status`:** it declined.

## Comparison that would overturn it

- **M1/M2.** Adopt the narrowing, with `AGENTS.md:3` changed in the same edit through #444's owner, if a retained paired behavior test meets both conditions:
  - **Setup:** Claude Code 2.1.283 on the latest Opus, the line as the only difference, at least 20 fixed mixed tasks per arm, scored blind by a non-Claude judge.
  - **Result:** research precedes at least 20% of read-only steps under the current line, and the narrowed line keeps full sourcing on write, build, install and adopt steps.
- **M3.** Put a version back if a paired dispatch test (at least 20 worker runs per wording; one-sided Fisher exact test, p < 0.05) shows "The latest Opus" resolving to the newest Opus less often than a numeric pin.
- **M4.** Re-trial the skill if upstream drops the freshness mandate, meaning "Previous run" is no longer Not Sufficient, on the watched path `skills/verification-before-completion` of obra/superpowers `dev` or `main`.
- **Gate A.** Hand it back if `token-stack-e2e-proof` returns live holding in-flight Gate A state.

## Limitations and residuals

- These are judgments on supplied evidence: two families reading the same frozen packets. No behavior test was run for any wording.
- The M3 host read-back ran on `claude-sonnet-5` and shows the loaded text, not a changed dispatch.
- The Claude side of M4 is the refuter's flag plus two full readings (coordinator, trial owner), not one lane on the frozen packet.
- The GPT-6 model is the pinned request, because the Codex event stream carries no model field.
- The trading acknowledgement covers F4 at `eb12630a`. If #444 is rebased, its owner re-verifies F4 byte for byte.
- `examples/claude-native/workflows/README.md:486` ("Opus 5.5" in the coordinator row) is left to #434.
