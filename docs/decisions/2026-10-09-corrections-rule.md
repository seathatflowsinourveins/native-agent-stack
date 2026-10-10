# Corrections from pinned upstream evidence

Date: 2026-10-09. Status: proposed repository instruction change; co-op GPT read and CC micro required.

The owner's October 9 direction, relayed through the command center, requires a wrong claim or fix to be resolved from the pinned upstream primary source through the vendor's supported path. The correction records its citation and a regression test that fails before the fix; conflicting sources require a first-hand measurement.

## Instruction and review surfaces

The final sentence of the fourth root `AGENTS.md` philosophy bullet carries the requested rule. A compact equivalent paragraph in `blueprints/us-equities/AGENTS.md` carries it for trading work. Reversing only that sentence replacement, the appended review section and the trading insertion restores both baseline files byte-for-byte.

The `## Code Review Rules` / `### Corrections` group copies [us-equities-trading #46](https://github.com/seathatflowsinourveins/us-equities-trading/pull/46) at immutable head [`6c42c8ab1e287a160da43b48b75692b42b880a81`, AGENTS.md:139-143](https://github.com/seathatflowsinourveins/us-equities-trading/blob/6c42c8ab1e287a160da43b48b75692b42b880a81/AGENTS.md#L139). That reference is an open PR at the observed revision, not a merged acceptance result.

[Official OpenAI documentation, Customize what Codex reviews](https://developers.openai.com/codex/integrations/github/) documents the root/nested AGENTS review section and grouped checks. [Official Claude Code Review documentation](https://code.claude.com/docs/en/code-review) documents direct delivery of REVIEW.md to review agents and recommends putting the enforced rules there. The same Corrections bullet is therefore present directly in `REVIEW.md`; instruction-surface tests check parity with the root group and its pinned citation. The scoped root/nested instruction pointer remains beside it.

The co-op rechecked those two official documentation pages on 2026-10-09 at about 23:01Z and confirmed the existing placement. This source check supports the native file/heading contract; it does not establish hosted reviewer execution.

Root `CLAUDE.md` already imports `@AGENTS.md` and retains its original bytes. Host-wide application to user-level instruction files remains the CC's reviewed post-landing stage.

The common amended core also belongs in the three versioned sources: `examples/claude-native/CLAUDE.md`, `adoption/templates/codex.AGENTS.template.md` and `adoption/scaffold/AGENTS.md`. The two committed new-WSL carriers are regenerated with `python3 tools/adoption/new_wsl_client_config.py --write-blocks`. The native [block producer at accepted 7cf7a7f9, lines 733-735](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7cf7a7f9fa75a75e15f3b08bab3ecce3b9edaa0f/tools/adoption/new_wsl_client_config.py#L733) reads repository sources; its write-blocks branch at :2752-2771 writes only the two committed carriers. The native [scaffold producer at the same pin, lines 154-169](https://github.com/seathatflowsinourveins/native-agent-stack/blob/7cf7a7f9fa75a75e15f3b08bab3ecce3b9edaa0f/tools/adoption/scaffold_repo.py#L154) returns the scaffold source bytes and caller-supplied project config. Updating these repository inputs and outputs applies no actual user-level file.

## Measured context cost

Measurements use the repository's existing `startup_files()` footprint, with reads confined to committed repository paths. Byte counts measure loaded instruction size; they do not measure tokens, model behavior, review quality or live bot deployment.

| Repository surface | Before | After | Change |
| --- | ---: | ---: | ---: |
| Root AGENTS.md | 2,331 bytes | 3,028 bytes | +697 |
| Trading AGENTS.md | 5,499 bytes | 5,778 bytes | +279 |
| REVIEW.md | absent | 611 bytes | +611 |
| Claude source and committed new-WSL carrier, each | 1,811 bytes | 2,036 bytes | +225 |
| Codex template and committed new-WSL carrier, each | 2,498 bytes | 2,723 bytes | +225 |
| Scaffold AGENTS.md | 2,465 bytes | 2,690 bytes | +225 |

At the baseline, the native helper measured Claude 4,728 bytes and Codex 4,829 bytes. The first head's root-only amendment and review group added 697 bytes to each, measuring 5,425/5,526, but left the generated user block stale. The all-surface correction adds 225 bytes to each user block; the native helper now measures Claude 5,650 and Codex 5,751 bytes, a total increase of 922 over the baseline. Fixed ceilings at five percent above these measured totals, rounded up, are 5,933/6,039. These are a dated, explicit comparison for the requested change, not an automatically expanding budget. The fixed-budget growth regression remains required. The co-op GPT read and CC micro must review this cost along with the rule before landing.

## Validation and limits

The initial native guards failed against unchanged source: nine tests, five expected failures, zero errors, at 2026-10-09T22:15:15Z. Those guards covered root/trading/review placement but incorrectly permitted a split between the root core and portable carriers.

The designated GPT read identified that defect at `7cf7a7f9`. Treating versioned repository carriers as deferred user-level application was incorrect. The standing-rule assertion now requires the same amended core once on every layer. A new regression executes the real Claude, Codex and scaffold producers. At the accepted head, all three outputs returned old sentence count 1/new count 0, and ten standing tests failed with nine assertion failures and no errors at 23:07:49Z. After source replacement and supported regeneration, the three outputs return old count 0/new count 1/common-core count 1; the focused twenty-test instruction-surface run passes at 23:10:48Z. The full installer, scaffold and new-WSL modules and FULL validation must pass on the final tree before publication.

The existing scaffold whitespace-drift fixture targets the amended `measure first-hand.` ending, replacing its now-absent legacy ending. The drift detector is unchanged, and the targeted fixture still rejects an added space before the newline.

The next designated micro found a separate live checksum consumer: `tests/test_codex_worker_lane.py` still pinned the pre-amendment top-rule bytes. Its native [`template_segments()` helper at `fad389cc`, lines 422-429](https://github.com/seathatflowsinourveins/native-agent-stack/blob/fad389cc710eca096fef037c2600d488428a85fb/tests/test_codex_worker_lane.py#L422) extracts the rendered top-rule segment separately from RTK. Recomputing SHA256 through that helper yields 1,917 UTF-8 bytes and `ae8f16bedb8cabc753114c4b8fbce3ef8e835ac50ea36aefb870671bf1ae8023`. The live `TOP_RULE_SHA256` constant now pins that authorized amendment; the historical consolidation record and sealed test-impact artifact retain their prior digest. The complete hash/RTK assertion and all RTK constants remain unchanged. The targeted test reproduced the old expectation's failure at 2026-10-10T00:11:49Z, passed after the calculated pin update at 00:13:11Z, and the full native module passed 123 tests with 12 opt-in skips at 00:14:45Z. FULL validation and genuine current-main merge verification remain publication gates for this fix.

All five repository carriers now carry the amended sentence; each differs from the accepted head only by that exact replacement. Actual user-level files remain the CC's separate post-landing application. No actual user-level file, credential or private-name pattern is read or changed.

These tests establish repository text, scope, byte preservation and reviewer-surface parity. They do not establish hosted reviewer execution or behavioral compliance. Existing custom Claude Actions prompts are a separate integration and are unchanged by this instruction-only change. The designated reviews and CI remain acceptance gates.

## Alternatives and overturn

- A pointer-only REVIEW bridge follows the reference repository, but the current Claude primary source recommends direct rules. The direct group avoids relying on unmeasured reference expansion; parity tests guard drift between the two native consumers.
- Deferring repository carriers together with actual user-level files leaves new hosts and scaffolded projects on the old rule. Rejected after the designated read reproduced the stale native outputs; repository sources and generated carriers are updated together, while host-wide application remains with the CC after landing.
- A new policy renderer or helper would rebuild a native instruction mechanism. Existing AGENTS/REVIEW surfaces and the existing instruction test harness already cover the need.

Revisit the placement if official review guidance changes, if a hosted review demonstrates a delivery gap, or if the measured context cost proves unjustified. Record any correction from the appropriate pinned source and reproduce its failing case.
