# Native skills readiness checks — 2026-10-05

This package records the lane's assigned readiness-roadmap jobs after the
stopped lifecycle sweep. Its purpose is to qualify the native skill tools used
by complex-system and north-star research workers. It selects and installs no
new production skill and changes no client configuration.

| Job | Result and evidence | Claim boundary |
| --- | --- | --- |
| Trail of Bits | [Native upstream validation](trailofbits-upstream-tests.json): self-test, frontmatter, email, metadata and both Codex versions pass; Claude strict marketplace validation fails on a reserved plugin name | Unchanged upstream checks at `82fe8226`; Claude installation/loading is stopped, and no model behavior is measured |
| Skills CLI | [Native upstream suite](discovery-upstream-tests.json): frozen install, build, format and type-check pass; the repaired Linux/Node24 test run has 874 passes, 1 failure, 0 skips | Suite remains failed at `7407f389`; initial missing-PATH attempt and persistent upstream mock failure are retained |
| Engineering process | [Pinned source review](engineering-upstream-tests.json): behavioral suite unavailable in checked sources; metadata checker exists | Source review at `d81f3a18`, under acceptance-evidence-policy lines 37–38; no new test, install or model pass |
| Skill authoring | [Fresh Codex creation](codex-authoring.json) passes native valid/invalid structural controls; [Claude paired execution](claude-authoring.json) reports 13/15 versus 12/15 assertions, rejects the wrong-answer control and generates its native aggregate/viewer | Synthetic fixture with five asset-prefix failures; no quality-uplift, Codex paired A/B, candidate adoption or production acceptance claim |
| MinerU / Dagu | Await completion of #719 | Owner/merge dependency; neither follow-up has started |

[Returned-output index](returned-output-index.json) retains each private raw
stdout/stderr SHA-256 and the corresponding public file hash. Public copies
replace owned scratch and personal home paths and normalize endings to one
final LF. Three trailing-space sites in build stdout are trimmed and declared.
Empty native
streams are explicitly identified by `raw_bytes: 0`. These transformations
are declared per file. Raw conversations and machine configuration stay private.
The original commands ran sequentially before 10:35Z, in cache scratch outside
Git and `/tmp`. Source clones remained clean. Exact per-step UTC times were not
separately captured for jobs 1–2; their coordination-clock intervals are retained
without reconstructing timestamps from file metadata.

No custom runner, fork, patched test or masked failure is used. The native CI
build in the Skills CLI scratch clone is a test prerequisite. The Trail of Bits
helpers use isolated homes; its latest-Claude CI dependency resolved to 2.1.289,
where the plugin name is rejected before marketplace installation. Codex CI
0.146.0 and the additional installed 0.160.0 helper run remain separate checks.

The sources are the unchanged
[Trail of Bits workflow at 82fe8226](https://github.com/trailofbits/skills/blob/82fe8226252622fa807643bdca1710901198553a/.github/workflows/validate.yml#L31),
[Skills CLI workflow at 7407f389](https://github.com/vercel-labs/skills/blob/7407f3893ad4dceab546ac002c3ef806e4000c73/.github/workflows/ci.yml#L35),
[engineering package at d81f3a18](https://github.com/mattpocock/skills/blob/d81f3a183412e71a5b1e84ca21bc1a35eea03a60/package.json#L11),
and the pinned
[Claude creator workflow](https://github.com/anthropics/skills/blob/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/skill-creator/SKILL.md#L163).
The fresh Codex leg reuses the byte-identical official
[rust-v0.160.0 creator](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md).

The [independent Claude review](claude-authoring-review.json) checks exact
native transcript copies, model/effort records, prompt parity, skill isolation,
Write payloads and timing notifications. Five answers keep the format prefix
where the frozen oracle expects the identifier alone. That ambiguity and one
repetition per case prevent an uplift conclusion. Native metadata placeholders
and fallback tool/error counts stay separate from actual task observations.
Native advisor rate-limit errors in two with-skill runs add a runtime confound;
opaque advisor contributions remain unqualified.

The first analyzer/critic workflow was interrupted after the completed
benchmark. Its record is preserved; [foreground completion](claude-authoring-completion.json)
records only the missing analysis stages. Both the interrupted attempt and
the historical dispatch-annotation gap remain disclosed. Raw conversation
streams and the static viewer stay in private owned scratch; the public
receipt retains actual bounded results, commands and raw hashes.

The completion report also redacts private session identifiers and encoded
home paths. Original returned reports and their hashes stay private; the
completion receipt separately lists the actual sanitized public hashes.
Native test results, source review, synthetic fixtures, structural validation
and fresh model execution retain their separate evidence classes.
