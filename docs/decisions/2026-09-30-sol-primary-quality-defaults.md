# Sol coordination, bounded workers and Astra escalation

Date: 2026-09-30. Lane: foundation. Status: implementation in progress; native
model acceptance is separate from configuration and source review.

Provenance (2026-09-30): pre-existing uncommitted changes observed in the main checkout; original author not
established; folded unchanged by unit D4 of coordinator session native-agent-stack-c5 (snapshot sha256 5de56d6d81453ed3). This
is the routing record for Codex models; the release, client-gate and gateway-effort evidence is in the
[model-currency addendum of 2026-09-30](2026-09-27-model-currency.md#addendum-2026-09-30-gpt-61-sol-released-codex-cli-01592-pinned-gpt-61-sol-at-ultra-the-interactive-default).

## Decision

The user selected GPT-6.1 Sol/Ultra for routine Codex coordination and
GPT-6.1 Sol/Max for primary workers. Select GPT-6 Astra/Ultra (proactive
delegation with the model's `xhigh` reasoning, see below) when a complex workflow
needs Astra to coordinate it, the user's 2026-09-30 selection ("astra ultra when
tasks needed suitable for complex workflow"), and GPT-6 Astra/Max, the highest
reasoning effort, for a single consequential judgment: conflicting primary
evidence, consequential architecture decisions, complex changes across systems,
or a failure unresolved after one bounded Sol repair. Explicit task
model choices take precedence over this default. Preserve Astra judgment roles
and verify the resolved role, model and effort before accepting their output.

The native user configuration sets `model = "gpt-6.1-sol"`,
`model_reasoning_effort = "ultra"`, `agents.default_subagent_model =
"gpt-6.1-sol"` and `agents.default_subagent_reasoning_effort = "max"`.
Keep three concurrent children. The bounded worker profile selects Sol/Max;
worker commands also pass their model, effort and live-search choice explicitly
because project settings outrank a profile. Astra workers substitute the model
through the same native interface.

Keep Claude's Opus judgment, Ultracode, interactive `--effort max`, saved
`xhigh` fallback and unset global effort environment override. Keep the
user-selected Fable advisor default and use Opus 5.5 advising where appropriate;
activation and usage-credit consent remain native. This decision changes
neither authentication nor permission policy.

At intake, select Astra directly for a change to a shared interface between two
or more native clients, to authorization/credential boundaries, or to a recovery
or lifecycle contract with effects across systems. Record the affected contract;
bounded configuration edits supported by one native schema remain Sol work.
Escalate when a verifier or two workers disagree on one primary
claim, when an acceptance/oracle check fails after one bounded Sol repair, or
when primary sources remain in conflict. A routing record contains the task,
selected model/effort, observable trigger (or the reason escalation was not
needed), acceptance result and actual usage if returned. Keep it with the task's
existing receipt; do not add a universal intake tool or repeatedly ask approval.
One Astra judgment resolves the bounded question; unresolved evidence is a
recorded limit, not permission to loop or broaden the task.

## Sources and capability boundaries

Installed clients inspected: Codex 0.159.2 and Claude Code 2.1.285. The native
Codex bundled model catalog advertises Sol 6.1 and Astra with Max, Ultra and
multi-agent V2. Ultra selects proactive delegation and normalizes the request
to the model's `xhigh`; Max sends `max`. Ultra is therefore an orchestration
choice, not a claim that each inference uses maximum effort.

- [openai/codex, rust-v0.159.2, model catalog](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/models-manager/models.json).
- [Effort normalization](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/protocol/src/openai_models/reasoning_effort.rs)
  and [native delegation selection](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/core/src/session/multi_agents.rs).
- [Child defaults and role application](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/core/src/agent/child_config.rs)
  and [configuration precedence](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/config/src/config_layer_source.rs).
- [anthropics/claude-code, v2.1.285, changelog](https://github.com/anthropics/claude-code/blob/v2.1.285/CHANGELOG.md)
  records the 2.1.284 separation of Ultracode and effort.
- [OpenAI Sol 6.1 guidance](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
  describes a near-Astra cost/speed tradeoff;
  [Astra guidance](https://developers.openai.com/api/docs/models/gpt-6-astra)
  identifies the highest-capability option. These descriptions do not establish
  a universal task-quality or token-saving result.
- [Claude advisor consent](https://code.claude.com/docs/en/advisor#fable-advisor-and-usage-credits)
  and [native advisor usage accounting](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool#usage-and-billing).

## Context and ownership

Use the [token practice](../token-practice.md): stable native caching, deferred
tools, code mode, automatic compaction and the cheapest sufficient context
lane per artifact. Retain originals for correctness and recovery. Request
compression is transport behavior, not a measured reduction in billed tokens.
Keep the selected shell-snapshot, daemon and experimental-context settings
until their recorded acceptance gaps close.

The [spend-attribution decision](2026-09-29-token-spend-attribution.md) assigns
role limits, selective `omitClaudeMd` and carrier narrowing to Gate A's recorded
owner, `native-agent-stack-2d`. Hand off those paths instead of inventing new
limits or editing another live owner's work. Its #381 reference is the closed
[PR-H preregistration pull request](https://github.com/seathatflowsinourveins/native-agent-stack/pull/381),
not an open Gate A issue. The
[owner handoff on active PR #528](https://github.com/seathatflowsinourveins/native-agent-stack/pull/528#issuecomment-5904600203)
preserves frozen role qualification and assigns future carrier/role trials to
that owner. PR #528 already proposes executor, advisor and combined accounting
with incomplete-iteration checks. Coordinate its upstream-first completion in
[agent-lab](https://github.com/seathatflowsinourveins/agent-lab/tree/eced71c572671fc3e381381c068d05b2a7a5bb22),
test its native script, then vendor byte-identically; do not compete with the owner.

## Evidence and acceptance

The planning baseline passed 29 render-config and 28 effort-guard checks.
Those are local integration checks; they are not provider or upstream acceptance.
Configuration readback, real model execution and independently checked task
results remain separate evidence classes.

Preserve all three failed planning peer attempts: one customized call exceeded
the context-mode RPC's 300-second response window; a second customized call
hit its native wrapper's 600-second timeout; a supplied-packet safe-mode review
hit a 180-second timeout. None returned a verdict or complete usage. Keep usage
unknown rather than estimating it, and do not attribute the failures to hooks.

A fourth diagnostic call started normally and streamed thinking, but its
180-second observer stopped it before a final result. Its usage remains unknown;
the observer did not retain a final-delta time sufficient to explain the delay.
A final supervised analytical call retained event times and returned native
Opus 5.5/max success in 163.28 seconds. Claude conditionally approved the
architecture and required observable escalation and declined-escalation records,
now specified above. Its native usage was input 2, cache creation 20,620,
cache read 3,073 and output 18,114 (including 17,648 thinking). The returned
USD 0.5278626 is native list-price metadata, not observed billing. Its recorded
one-hour cache creation is an observation, not a change to this stack's cache
policy. No tool integration or comparative model-quality claim follows.

Native `claude doctor` exited zero and warned about trailing whitespace in the
SocratiCode query/document prefixes. The accepted
[SocratiCode receipt](../../evidence/receipts/socraticode-1150-qualification-20260927.json)
and [pinned upstream README](https://github.com/giancarloerra/SocratiCode/blob/f6191f076a42405f0d5508139f3a8b505cfef93a/README.md)
record those spaces as intended for Nemotron. Removing them would change the
embedding contract and require fresh indexing; the warning establishes no
cause for the peer timeout. Native auth status reported a signed-in first-party
Claude account without a provider override; credentials were not inspected.

Require native readback of the new defaults, bounded Sol and Astra executions,
an independent Claude verdict, and appropriate deterministic acceptance before
claiming task-level quality. Count every attempt once, keep cache/provider
subsets distinct, and retain failures and unknown usage. Reopen routing when a
comparable workload demonstrates better accepted resolution or lower complete
task cost at the same acceptance bar.

## Addendum: portable generic worker default (2026-10-02)

The current generic Codex worker default follows the selected GPT-6.1 Sol/Ultra
coordinator. The portable template keeps the dynamic `CODEX_MODEL` resolution and
sets `default_subagent_reasoning_effort = "ultra"`; current Codex 0.160 supports
that effort. Explicit role and profile selections still apply after generic
defaults: the isolated builder and frozen Astra judgment roles retain their Max
settings. The September 30 decision, Max receipts and OmniRoute Sol/Max evidence
above remain historical observations without replacement.

This template change does not upgrade or qualify a host. The legacy Linux lane's
0.159.3 pin and old Mac portable 0.155.1/Astra resolution remain version-bound;
their profiles, SDK evidence, frozen qualifications and runtime bytes are
unchanged. No global configuration, account, model service or host activation is
changed by this source alignment.
