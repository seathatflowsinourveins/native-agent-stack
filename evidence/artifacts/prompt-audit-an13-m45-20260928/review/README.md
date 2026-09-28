# Review of this change's first head (2026-09-28)

One review per family ran on `31ab17f7`, the change's first head, while it was still local. That head was pushed
unchanged to open the pull request, and one repair round followed both returns. The returns are kept as written,
with the worktree path written as `<worktree>`. `final_text.py` took the Claude return from the agent's transcript,
which is not published.

| Reviewer | Prompt | Return | Usage |
| --- | --- | --- | --- |
| GPT-6: `codex exec --json -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live" -o gpt6-review.md "<prompt>" < /dev/null`, run in the worktree, 14:48:54Z to 15:03:54Z | `gpt6-prompt.txt` | `gpt6-review.md`: changes-needed, 4 should-fix and 2 nits | `gpt6-usage.json`, from `gpt6_review_usage.py`: input 1,514,589 (1,376,000 cached), output 27,157 (12,292 reasoning) |
| Claude: one `evidence-reviewer` agent (Opus 5.5), given the coordinator's command results | `claude-brief.txt` | `claude-review.md`: changes-needed, 6 should-fix and 3 nits | `claude-usage.json`, from `review_usage.py`: 47 API calls and 1 advisor call; input 96, cache write 247,252, cache read 6,475,741, output 115,571 |

The three helper scripts are copies of #444's, from `evidence/artifacts/prompt-audit-20260927/review-444/`.

## Findings and what happened to them

| Finding | Disposition |
| --- | --- |
| GPT-6 1 and Claude 6: the record says both lanes checked the hashes, but the Claude lane says it did not check the installed copy | Fixed. U1 records the hashes; the GPT-6 lane checked them itself; the Claude lane relied on U1 |
| GPT-6 2 and Claude 3: the rule is cited to `docs/convergence-architecture.md`, which does not state it | Fixed. The record cites `2026-09-27-prompt-audit-resolution.md:54-60`, "Rule". Those lines do not say that a void judgment does not count, so the record cites that rule to the lane-A template's `outcome-actions.md:9-12` and `tools/sota-convergence/README.md:1503-1505` |
| GPT-6 3 and Claude 7: no retained file supports the freeze time 14:21:23Z | Fixed. The record says the package keeps no timestamped record of the freeze, and that the file's modification time is not a receipt. It keeps only what the files show |
| GPT-6 4 and Claude 5: the judges' inputs held only the two texts, not the lanes' reasons or sources | Fixed. The record lists what the inputs and the shared packet held |
| GPT-6 5 and Claude 4: `receipt.json:88` names the validator, not the installer, and the adjudication packet stated that premise to all four judges | Fixed in the record. `AGENTS.md:15-16` is cited for the installer. A limitation says the packet's round-1 summary stated the wrong premise; the Claude B/A judgment repeated it, the A/B judgment read the receipt correctly; a new round's packet must drop it; this round's outcome is unaffected. The packet itself is unchanged, since it is the evidence as sent |
| GPT-6 6: `sha256sum -c round1/packet.sha256` fails from the package directory | Fixed. The record runs it in `round1/` |
| Claude 1: the round adapted X9 round 3's audit instead of the lane-A template the log names, and the template already covers both false positives | Fixed. The anti-pattern row and the record's Checks now say so, and the row's rule starts every judge audit from the template |
| Claude 2: the row's "Where enforced" cited `audit-control-m45.json`, whose pass condition cannot fail on this mistake | Fixed. The record calls that file a reproduction after the fact. `reproduce_template_checks_m45.py` ran the template's self-test payloads and root scan with this round's audit and patterns. Both fail: the two payloads come back void, and MAPPING matches 8 paths and the text of 242 of the 8,223 files at `9f8db582` (`adjudication/template-checks-m45.json`). The row names those checks |
| Claude 8: the README's reason for withholding the hit windows did not match the recorded hits | Fixed. `publish_windows_m45.py` publishes the eight windows with host details replaced (`adjudication/audit-m45-windows.json`), the evidence that the hits are false positives |
| Claude 9a: "the packet's first source" for U1, which is the eleventh entry | Fixed: "Source U1" |
| Claude 9b: D2 deletes and adds nothing | Fixed: "D1 replaces … with one sentence, and D2 deletes …" |
| Claude 9c: the trigger-list point is the Claude lane's alone | Fixed: attributed to the Claude lane |
| Claude 9d: the packets do quote "Claude responds well…" and name OpenAI's guide, so "no model names" overstates the builder's check | Fixed: "none of its leak words (model ids and lane attributions)", with the two quotes named |
| Claude 9e: the audit labels all four hits MAPPING | Fixed: "four hits of the MAPPING pattern, from two of its alternatives" |
| Claude 9f: both valid GPT-6 judgments chose position B | Fixed: the record says the GPT-6 pair disagrees only across presentation orders |
| Claude 9g: "no web access" for the Claude lane, whose role grants Context Mode execution | Fixed. The record says the role has no web tool and the brief said it had no shell or web access. `tool-counts.json`, from `tool_counts_m45.py`, shows that the lane and both Claude judges called only Read, Glob, Grep and one advisor each |
| Claude, not checked: the unpublished transcripts, hit windows, the Claude lane's Context Mode use | The windows and tool counts are now published. The transcripts stay unpublished: they carry the host's session context |

No second review round was run. The repairs had no independent review.
