# Lane A: S1 and the top rule's three copies (2026-09-28)

Lane A is one part of the third round of the 2026-09-27 prompt audit. It had four items:

- **S1** (`AGENTS.md:37`): build each PR description from the template, whose `sota-sources` check is required.
- **X5a** (`examples/claude-native/CLAUDE.md:3`): the portable Claude template's top rule.
- **X5b** (`AGENTS.md:3`): this repository's top rule.
- **X5c** (`adoption/templates/codex.AGENTS.template.md:3`): the Codex template's top rule.

X5a to X5c carry the operator's 2026-09-28 wording of the top rule, from the operator's user-level instruction file, into the repository's three copies of it.

**Outcomes**

- **S1 and X5b:** both lanes agreed in round 1. They change `AGENTS.md`, a shared hot file, so they go to #444 (`lane:shared`), which needs the trading lane's acknowledgement before merge.
- **X5a:** in round 1 each lane proposed a different amendment. Adjudication attempt 1 was void because its input broke the adjudicator's contract. Attempt 2 applied nothing, because both GPT-6 judgments were void on an audit pattern. In the final round both lanes agreed with the proposed text, so it is applied.
- **X5c:** in round 1 one lane rejected the change and the other agreed. Attempts 1 and 2 went as for X5a. The final round split again: the GPT-6 lane agreed with the proposed text, and the Claude lane amended it to keep the installed client as a source of truth. The final blind adjudication chose the amendment in all four judgments:
  - GPT-6: confidence 0.94 and 0.91;
  - Claude: 0.75 and 0.78;
  - no audit hit voided a judgment.

  The amendment is applied with its co-changes: `TOP_RULE_SHA256` is `ce957fd8…` and the word count is 153.

The decision record is [`docs/decisions/2026-09-28-top-rule-templates.md`](../../../../docs/decisions/2026-09-28-top-rule-templates.md).

## Layout

| Path | What it is | Evidence class |
| --- | --- | --- |
| `round1/` | Round 1: the frozen packet, both lanes' prompts and returns, the GPT-6 runner record, the tally, the proposals, the S1 facts and the builder | retained model judgments |
| `adjudication/attempt1/` | Attempt 1's void record and builder, and its two GPT-6 jobs' usage, read from the runner's event log without reading the returns (`gpt6-usage.json`, `attempt1_usage.py`) | coordinator record |
| `adjudication/attempt2/` | Attempt 2, with the inputs, packets, prompts and schemas as sent (hashes in `sent-sha256.json`); also the mapping, the four judgments with runner records and usage, the audit, the judge actions, the tally and the scripts | retained model judgments |
| `controls/` | Trial controls for both X5c texts and X5a: commands, exit codes and the output lines each printed, plus the scripts that set each text. The checks are the pin and phrase tests and the manifest check | structural validation |
| `final/` | The final round: the packet, prompts, schema, proposal diff, probe and lane records, lane audit and tally; also the builder, audit, self-test, root scan and tally scripts | retained model judgments |
| `final/adjudication/` | The X5c adjudication. Sent files: inputs, packet, prompts and schema (hashes in `sent-sha256.json`). Results: the amendment diff, the probe, the four judgments with runner records and usage, the audit, the tally and the mapping. Fixed before dispatch: the withheld-files check, the frozen hash list (`frozen-final.sha256`) and the outcome actions. Every script, including the `edit_*.py` changes made before dispatch and while packaging | retained model judgments |
| `final/adjudication/token-counts-*.txt` | o200k counts of both templates before and after (`tools/token-report/token_manifest.py count_files`, gpt-tokenizer 3.4.0) | exact counts of the files, not billed usage |
| `review/` | The review round on the unpushed head and its repair: both reviews with their prompts and usage, and the repair's controls (see its README) | retained model judgments; coordinator record |
| `verify_lane_a.py` | Recomputes the published outcomes and checks the repository's texts and pin | protocol |
| `exposure_scan_dir.py` | The count-only scan run on this directory before its first push | protocol |

**Not published:**
- the lanes' and judges' session transcripts and Codex event logs, which carry the host's injected context and home paths;
- attempt 1's two GPT-6 returns, which were never read;
- whole test logs (only the output lines each check printed are kept).

Published copies of scripts and records use placeholders in place of these:
- host paths;
- the session id;
- the user name;
- installed plugin and skill names;
- Claude subagent ids (`<agent-id-1>` to `<agent-id-3>`), which name transcript files in the host's project store. The review round found them unmasked. The packager now masks them in every copy it cleans (`edit_package_7.py`). Its refusal can fire only on a copy published byte for byte, so the control is the scanner's count: 6 before the repair, 0 after.

Hashes in `final/frozen-a2.sha256`, `final/adjudication/frozen-final.sha256` and each `sent-sha256.json` are of the files as frozen or sent. `review/hash-match.json` compares every listed file with its published copy. Sixteen published files differ:
- the ten judge and lane prompts (host paths);
- `build_lane_a2.py`, `build_adjudication_final.py` and `audit-selftest-final.json` (host paths and the other placeholders above);
- `audit_selftest_a2.py`, `audit_selftest_final.py` and `void_patterns_final.py` (subagent ids, masked in the review repair, besides any other placeholders).

`review/placeholder-check.json` shows that each of the sixteen is its original after the packager's replacements and nothing else. For each one, the coordinator found the original by its frozen or sent hash, applied the packager's own `clean()`, and compared the result with the published copy. Its failing run, on a copy of this directory with one line planted in a prompt, is `review/placeholder-check-control.txt`. The originals stay private, so only the host can repeat this check.

Every input, packet, schema, diff and other frozen record matches byte for byte.

## Checks you can repeat

- `python3 verify_lane_a.py` recomputes three things and exits 0 when they all hold:
  - the final round's lane tally;
  - the X5c adjudication tally, from the four published judgments, the mapping and the audit;
  - the repository's two template lines and the Codex template's pin, read with the test module's own `template_segments()`.
  `review/verify-negative-control.txt` is its failing run. With this directory copied into a clean worktree of `main` before this change, it reports both template lines as mismatches and exits 1.
- `python3 exposure_scan_dir.py .` exits 1 by design and lists 21 files. Every match falls into one of three kinds:
  - **Pattern literals:**
    - the scanner's own patterns;
    - the leak checks in the input builders;
    - the void patterns;
    - the two root scans' configuration pattern;
    - the packaging script's replacements and its `edit_*.py` changes.
  - **Synthetic cases** in the audit self-tests.
  - **The `<user>` placeholder**, which the published scanner's own pattern matches wherever a file names it. This includes the README and the review prompts.

  It finds no Claude subagent id: there were 6 before the review repair and none after (`review/exposure-scan-before.txt`, `review/exposure-scan-after.txt`). Nine files name a settings file, and none holds a settings file's contents:
  - six quote `AGENTS.md:35` ("This repository commits `.claude/settings.json` with Ultracode on") as the packet quoted it;
  - the two reviews name the file in their findings;
  - this README quotes the same line.
- `python3 review/hash_match_report.py .` compares every file in the two `frozen-*.sha256` lists and in each `sent-sha256.json` with its published copy (`review/hash-match.json`).

## Limits on blindness

- **Capability hint.** One X5c return says it could not compute a hash; the other says it ran the tests. That capability difference may hint at a reviewer's family. The returns were not edited.
- **Withheld records.** The adjudication root withheld the earlier rounds' records (the 2026-09-27 decision record and this evidence directory's earlier files), which name reviewers. As a result, `scripts/validate.py` in those copies reports 44 missing files and nothing else (`withheld-check.json`).
- **What the judges were told.** They were told as a neutral fact that X5a is applied, because the amendment's argument refers to it.
