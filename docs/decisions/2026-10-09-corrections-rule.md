# Corrections from pinned upstream evidence

Date: 2026-10-09. Status: proposed repository instruction change; co-op GPT read and CC micro required.

The owner's October 9 direction, relayed through the command center, requires a wrong claim or fix to be resolved from the pinned upstream primary source through the vendor's supported path. The correction records its citation and a regression test that fails before the fix; conflicting sources require a first-hand measurement.

## Instruction and review surfaces

The final sentence of the fourth root `AGENTS.md` philosophy bullet carries the requested rule. A compact equivalent paragraph in `blueprints/us-equities/AGENTS.md` carries it for trading work. Reversing only that sentence replacement, the appended review section and the trading insertion restores both baseline files byte-for-byte.

The `## Code Review Rules` / `### Corrections` group copies [us-equities-trading #46](https://github.com/seathatflowsinourveins/us-equities-trading/pull/46) at immutable head [`6c42c8ab1e287a160da43b48b75692b42b880a81`, AGENTS.md:139-143](https://github.com/seathatflowsinourveins/us-equities-trading/blob/6c42c8ab1e287a160da43b48b75692b42b880a81/AGENTS.md#L139). That reference is an open PR at the observed revision, not a merged acceptance result.

[Official OpenAI documentation, Customize what Codex reviews](https://developers.openai.com/codex/integrations/github/) documents the root/nested AGENTS review section and grouped checks. [Official Claude Code Review documentation](https://code.claude.com/docs/en/code-review) documents direct delivery of REVIEW.md to review agents and recommends putting the enforced rules there. The same Corrections bullet is therefore present directly in `REVIEW.md`; instruction-surface tests check parity with the root group and its pinned citation. The scoped root/nested instruction pointer remains beside it.

Root `CLAUDE.md` already imports `@AGENTS.md` and retains its original bytes. Host-wide application to user-level instruction files remains the CC's reviewed post-landing stage.

## Measured context cost

Measurements use the repository's existing `startup_files()` footprint, with reads confined to committed repository paths. Byte counts measure loaded instruction size; they do not measure tokens, model behavior, review quality or live bot deployment.

| Repository surface | Before | After | Change |
| --- | ---: | ---: | ---: |
| Root AGENTS.md | 2,331 bytes | 3,028 bytes | +697 |
| Trading AGENTS.md | 5,499 bytes | 5,778 bytes | +279 |
| REVIEW.md | absent | 611 bytes | +611 |

At the baseline, the native helper measured Claude 4,728 bytes and Codex 4,829 bytes. The root amendment and review group add 697 bytes to each: Claude 5,425 and Codex 5,526 bytes. The existing five-percent ceilings move from 4,965/5,071 to 5,697/5,803 respectively. These are a dated, explicit comparison for the requested change, not an automatically expanding budget. The fixed-budget growth regression remains required. The co-op GPT read and CC micro must review this cost along with the rule before landing.

## Validation and limits

The updated native instruction-surface guards fail against unchanged source: nine tests, five expected failures, zero errors, at 2026-10-09T22:15:15Z. They identify the missing root amendment, trading rule, root review group and directly delivered REVIEW group. The before/after suite and FULL evidence validation must pass on the final tree before publication.

The five portable instruction carriers keep their baseline content; root expectations distinguish this repository amendment from a future host-wide update. No actual user-level file, credential or private-name pattern is read or changed.

These tests establish repository text, scope, byte preservation and reviewer-surface parity. They do not establish hosted reviewer execution or behavioral compliance. Existing custom Claude Actions prompts are a separate integration and are unchanged by this instruction-only change. The designated reviews and CI remain acceptance gates.

## Alternatives and overturn

- A pointer-only REVIEW bridge follows the reference repository, but the current Claude primary source recommends direct rules. The direct group avoids relying on unmeasured reference expansion; parity tests guard drift between the two native consumers.
- Editing portable carriers or user-level files together would broaden the reviewed change. The dispatch reserves host-wide application for the CC after landing.
- A new policy renderer or helper would rebuild a native instruction mechanism. Existing AGENTS/REVIEW surfaces and the existing instruction test harness already cover the need.

Revisit the placement if official review guidance changes, if a hosted review demonstrates a delivery gap, or if the measured context cost proves unjustified. Record any correction from the appropriate pinned source and reproduce its failing case.
