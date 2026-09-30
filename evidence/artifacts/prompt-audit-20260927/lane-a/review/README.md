# Review round on the unpushed head (2026-09-28)

One review round ran on the unpushed head `b4472998` (base `eb678281`), followed by one repair round and one re-check
of that repair by the same Claude reviewer. Host paths in the published copies are replaced by placeholders, as
elsewhere in this directory.

- **GPT-6:** one `codex exec -s read-only -m gpt-6-astra -c model_reasoning_effort=max -c web_search=live --json`
  call (codex-cli 0.157.1) with `gpt6-prompt.txt`. Answer: `gpt6-review.md`, changes-needed, 5 findings. Usage:
  `gpt6-usage.json`.
- **Claude:** one `evidence-reviewer` (Opus 5.5, effort max) with `claude-brief.txt`. Answer: `claude-review.md`,
  changes-needed, 8 findings. Usage: `claude-usage.json`.

## Repair, finding by finding

| Finding | Repair |
| --- | --- |
| GPT-6 1: three Claude subagent ids in six places | The packager masks them in every copy it cleans (`../final/adjudication/edit_package_7.py`). Its refusal fires only on a copy published byte for byte, so the control is the scanner's count: 6 before the repair (`exposure-scan-before.txt`), 0 after (`exposure-scan-after.txt`). Both runs used the scanner's source copy, which has the host's user name where the published copy has `<user>`. The re-check found the ids still in the unpushed content commit, so the repair was folded into that commit before the first push |
| GPT-6 2, Claude 1: the packets' bases | The record names each round's base. The two templates and the test have the same blobs at `46184751`, `8315274f`, `eb678281` and `4a610e18` |
| GPT-6 3: "S1 and X5b are applied" | The README says they go to #444 |
| GPT-6 4: the print-mode row had no retained evidence | The row moved to #444, with the receipts of the run it describes |
| GPT-6 5, Claude 6: the scan and note descriptions | The README and both adjudications' `sent-sha256.json` notes are corrected. `hash-match.json` (from `hash_match_report.py`) compares every frozen or sent hash with its published copy; after the re-check it also covers `final/frozen-a2.sha256`. `placeholder-check.json` (from `placeholder_check.py`) shows that each of the 16 differing copies is its original after the packager's replacements. Its failing run is `placeholder-check-control.txt` |
| Claude 2: the sentence saying the old lines called only upstream a source of truth | Removed from the record |
| Claude 3: attempt 1's GPT-6 usage | Published as `../adjudication/attempt1/gpt6-usage.json`, read from the runner's event log without reading the returns |
| Claude 4: `verify_lane_a.py` had no failing run | `verify-negative-control.txt`: run with this directory copied into a clean worktree of `main` before this change, it reports both template lines as mismatches and exits 1. The pin check passes there, because the base template and its pin agree |
| Claude 5: the evidence class of `controls/` | Relabelled structural validation |
| Claude 7: precision | The record now says three things: the final lane round, not an adjudication, settled X5a; the probes' exact output tokens; and the host step as the `--apply` command the dry run prints |
| Claude 8: row 2's wording | The row now says the judges made the read as their second command, and that real runs stay clean apart from their own work directories. `rtk-read-facts.json` (from `rtk_read_facts.py`) shows the round-1 probe and lane made the same read before attempt 2 was dispatched |

## Re-check

The same `evidence-reviewer` was resumed once with the repair list and the command results (`claude-recheck.md`). It
found every finding repaired in the working tree, and four open items:

| Item | Resolution |
| --- | --- |
| The subagent ids were still in the unpushed content commit, so a repair commit on top would leave them reachable (blocking) | The repair was folded into the content commit before the first push. `git log -p` of the pushed range finds no id |
| The record still called the RTK read the Codex runtime's own startup read | The record now says each GPT-6 judge ran it as its second command, as in the anti-pattern row |
| `final/frozen-a2.sha256` was missing from the hash report, and two of its files differ | The report covers both frozen lists. The README names all 16 differing files, and `placeholder-check.json` checks each one |
| The packager's refusal cannot fire on cleaned copies | The README and the table above say so. The scanner's count is the control |

Usage (`claude-recheck-usage.json`, from `recheck_usage.py`, counting only the calls after the re-check request):
21 API calls and one advisor call; input 46, cache write 327,735, cache read 6,262,303, output 30,954. These are
disjoint counters and are not added. No second GPT-6 round was run.

## Not repaired, recorded

- **Plugin-skill self-test.** Its failing run on the plugin-skill read was not retained. Only the passing run after
  the fix is, in `../final/adjudication/audit-selftest-final.json`.
- **Freeze timing.** The frozen hash lists' write times are not retained. `dispatched-final.txt` records only the
  dispatch time.
- **Line 7 of `docs/harness-defaults.md`.** It restates the repository top rule's old heading, and it changes with
  X5b in #444.

## Other runs

- **Full unit suite on `b4472998`:** 6,881 tests. The only failures were the two host failures that also fail on
  unmodified `main`. Run alone in a clean worktree of `origin/main` at `4a610e18`, the same two tests fail the same way
  (`main-host-failures.txt`).
