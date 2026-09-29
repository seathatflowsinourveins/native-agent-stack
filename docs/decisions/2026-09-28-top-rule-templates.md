# Decision: carry the operator's 2026-09-28 top rule into the portable and Codex templates (2026-09-28)

**Decided by:** the user's direction of 2026-09-28: "please resolute cleanly with the sota repos convergence,resolute all in your end and state the jobs that only beable to run by end,decide with your evidances and sota repos evidances convergence". The operator's own user-level instruction file, edited 2026-09-28 07:34Z, opens with the rule being carried:

> **Top rule: research convergence first; current upstream SOTA is the source of truth.** … The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.

The decision was made in lane A of the 2026-09-27 prompt audit's third round. Each item went to two independent lanes. X5c's split was settled by a blind adjudication, and X5a's by one more lane round:

- **Lanes:** GPT-6 (`gpt-6-astra`, effort max) through the packaged Codex runner. Claude ran as an `evidence-reviewer` in round 1 and as a `blind-lane-reviewer` in the final round (`agent_type` in `lane-a/round1/claude-usage.json` and `lane-a/final/claude.json`).
- **Adjudication:** both presentation orders, judged by both families.

The evidence is retained in [`evidence/artifacts/prompt-audit-20260927/lane-a/`](../../evidence/artifacts/prompt-audit-20260927/lane-a/). Round 1 and the first two adjudication attempts were frozen at `46184751`, the head of #444 at the time. The final round and its adjudication were frozen at `8315274f`. Branch `claude/template-user-level-sync-20260928` is based on `origin/main@4a610e18`. The two templates and the test have the same blobs at `46184751`, `8315274f`, `eb678281` and `4a610e18`. `docs/harness-defaults.md` differs only at `46184751`, by #444's own log rows.

**Scope:** this pull request covers two items and the records they produced:

- **X5a:** [`examples/claude-native/CLAUDE.md:3`](../../examples/claude-native/CLAUDE.md), the portable Claude template.
- **X5c:** [`adoption/templates/codex.AGENTS.template.md:3`](../../adoption/templates/codex.AGENTS.template.md), with its pin in [`tests/test_codex_worker_lane.py`](../../tests/test_codex_worker_lane.py).
- **Anti-pattern log:** two rows in [`docs/harness-defaults.md`](../harness-defaults.md). A third row, on print mode's wait for background agents, moved to #444 with the receipts of the run it describes.
- **Evidence:** lane A's retained records.

Lane A's other two items change `AGENTS.md`, a shared hot file, and land with the prompt-audit pull request #444:

- **S1:** build each PR description from the template.
- **X5b:** this repository's own top rule.

The operator's user-level file is the operator's own and is not changed.

## Decision

| Item | Location | Round 1 (GPT-6 / Claude) | Final round (GPT-6 / Claude) | Adjudication | Result |
| --- | --- | --- | --- | --- | --- |
| X5a | `examples/claude-native/CLAUDE.md:3` | amend / amend, two different texts | agree / agree | Round 1's split: attempt 1 void, attempt 2 not applied (both GPT-6 judgments void). Final round: not needed | Applied |
| X5c | `adoption/templates/codex.AGENTS.template.md:3` | reject / agree | agree / amend | Final: 4 of 4 for the amendment (GPT-6 0.94 and 0.91, Claude 0.75 and 0.78; no voiding audit hit) | Applied, with its co-changes |

The applied lines, verbatim:

- X5a: `**Top rule: research convergence first; current upstream SOTA is the source of truth.** The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.`
- X5c: `Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.`

Why these texts. The packet asked each text to "carry that wording correctly and keep the file's tested obligations and its existing meaning". Both lines do three things:

- They keep the operator's heading sentence and compounds sentence verbatim.
- They keep the installed client as a source of truth, as the base lines did. [`docs/harness-defaults.md:58`](../harness-defaults.md#upstream-verification-and-compounding-learning), the long form of the rule, names it: "Upstream repositories, their changelogs and release notes, and the installed client are the source of truth". Its check order lists `codex --version` under "Installed client", so the clause holds for Codex sessions too.
- They keep the lowercase phrase "never self-write without a SOTA source", which the portable template's case-sensitive phrase check requires (`tests/test_install_claude_profile.py:967`).

The two templates now state the rule identically, apart from the portable template's bold heading. All four adjudicators gave the same deciding reason for X5c: the proposed alternative moved the installed client's status out of the top rule, leaving it only in line 5's check order.

## Method

1. **Round 1** (`lane-a/round1/`).
   - Both lanes judged S1 and X5a-c from one frozen packet.
   - S1 and X5b converged (agree / agree).
   - X5a split: each lane proposed a different amendment. X5c split: reject / agree.
2. **First adjudication attempts** (`lane-a/adjudication/`).
   - Attempt 1 was void before any GPT-6 result was read. Both Claude adjudicators refused an input that broke their input contract.
   - Attempt 2 applied nothing. The audit voided both GPT-6 judgments: its pattern for the Codex home matched the `rtk cat ~/.codex/RTK.md` that each GPT-6 judge ran as its second command, as the Codex home's user instructions direct. That rule had been fixed before dispatch, so it was applied as written.
3. **Final round** (`lane-a/final/`).
   - One more lane round on X5a and X5c. Each item came with its complete change, its co-changes and the measured checks.
   - The round declared itself final: without convergence, the current text stays.
   - Its void patterns were proven on real runs of both runtimes and on planted accesses before dispatch.
4. **Final X5c adjudication** (`lane-a/final/adjudication/`), anonymous A/B inputs in the blind-adjudicator's contract format.
   - **Both options measured.** The coordinator first applied and measured the amendment by the same procedure as the proposal. The judges read a root with `base/`, `proposed/` and `amended/` trees and both diffs.
   - **Records withheld.** The root left out the earlier rounds' records, because they name reviewers.
   - **Patterns and outcomes fixed before dispatch** (`frozen-final.sha256`, `outcome-actions.md`).
     - The void patterns added an injected-context check.
     - A real-run control caught a Codex plugin-skill read at startup before dispatch.
     - The mapping, the tally rule and the action for every outcome were frozen with the patterns.

## Checks

The checks are structural validation: pin, phrase and registration checks, not a behavior test. Each check that gates the change was seen failing before it passed (`lane-a/controls/controls.json`, `lane-a/review/verify-negative-control.txt`). The two test runs are regression runs of existing tests. The coordinator ran the controls in one worktree of `8315274f`.

| Check | Failing control | After |
| --- | --- | --- |
| X5a phrase check (`PortableTopRuleTests`) | round 1's text, which opens its second sentence with a capital "Never": exit 1 | the applied text: exit 0 |
| X5c pin (`TemplateTests.test_top_rule_and_upstream_text_are_verbatim`) | the applied line with the test still pinned to the other text: exit 1, `'ce957fd8…' != '71a852be…'` | re-pinned with the test module's own `template_segments()`: exit 0 |
| Publication validation (`scripts/validate.py`) | the template and test changed, not re-registered: exit 1 (SHA-256 and byte-count mismatches) | after registration: exit 0 |
| Every test module that reads either template or the pin | none (regression run) | 353 tests, OK (15 skipped) |
| `lane-a/verify_lane_a.py` | copied into a clean worktree of `main` before this change: both template lines reported as mismatches, exit 1 (`lane-a/review/verify-negative-control.txt`) | recomputes both tallies from the published returns and checks both lines and the pin in this tree: exit 0 |
| Full unit suite (`python3 -m unittest`) | none (regression run) | on `b4472998`: 6,881 tests; the only failures are the two host failures that also fail on unmodified `main` |

## Measured results

o200k counts come from `tools/token-report/token_manifest.py count_files` with gpt-tokenizer 3.4.0 (`lane-a/final/adjudication/token-counts-*.txt`).

| File | Bytes | Words (`wc -w`) | o200k tokens |
| --- | --- | --- | --- |
| `examples/claude-native/CLAUDE.md` | 8,480 → 8,680 | 1,205 → 1,235 (ceiling 1,265) | 1,719 → 1,757 |
| `adoption/templates/codex.AGENTS.template.md` | 3,151 → 3,371 (test ceiling 8,192) | 502 → 535 | 786 → 829 |

The Codex template's pinned top-rule block grows from 120 to 153 words, with `TOP_RULE_SHA256 = ce957fd8…`.

**Usage of the final round and the adjudication.** Each counter is listed on its own, never summed.

- **GPT-6 runner:** Codex counts cached input inside input, and reasoning output inside output.

  | Job | Input (of which cached) | Output (of which reasoning) |
  | --- | --- | --- |
  | Final lane | 991,091 (878,336) | 13,092 (7,682) |
  | Adjudication AB | 560,303 (473,984) | 9,590 (5,107) |
  | Adjudication BA | 557,285 (429,696) | 10,499 (6,689) |
  | Final-round probe | 93,465 (49,536) | 1,639 (1,268) |
  | Adjudication probe | 93,247 (49,536) | 1,500 (1,073) |

- **Claude:** Anthropic's input, cache-write and cache-read counters are disjoint.

  | Job | Input | Cache write | Cache read | Output |
  | --- | --- | --- | --- | --- |
  | Final lane | 106 | 177,773 | 6,393,681 | 72,777 |
  | Adjudicator AB | 42 | 111,141 | 1,566,491 | 36,988 |
  | Adjudicator BA | 38 | 127,162 | 1,695,328 | 32,006 |

  Each Claude job also made one advisor call, whose own usage is not in these counters.

Earlier usage is in the following files:
- **Round 1:** `lane-a/round1/gpt6.runner.json`, and `claude-usage.json`, which also holds attempt 1's two Claude judges.
- **Attempt 1's GPT-6 jobs:** `lane-a/adjudication/attempt1/gpt6-usage.json`, read from the runner's event log without reading the returns.
- **Attempt 2:** `lane-a/adjudication/attempt2/`.
- **The review round:** `lane-a/review/`, summarized under Review below.

## Review

One review round ran on the unpushed head `b4472998`, and one repair round followed. The records are in `lane-a/review/`.

| Reviewer | Verdict | Usage |
| --- | --- | --- |
| GPT-6: one `codex exec`, read-only, `gpt-6-astra`, effort max | changes-needed, 5 findings | input 2,263,283 (2,113,024 cached), output 26,513 (12,036 reasoning) |
| Claude: one `evidence-reviewer`, Opus 5.5, effort max | changes-needed, 8 findings | input 102, cache write 250,018, cache read 7,945,170, output 104,323; one advisor call |
| Claude re-check: the same reviewer, resumed once with the repair list | open items: 1 blocking, 3 minor | input 46, cache write 327,735, cache read 6,262,303, output 30,954; one advisor call |

**Repairs.** The repair round addressed every finding, and the re-check's open items were then resolved. `lane-a/review/README.md` maps each finding to its repair. The material ones:
- **Subagent ids.** Three were unmasked in the published audit scripts. The packager now masks and refuses them.
- **Packet bases.** The record misstated them.
- **Unsupported claims.** Two had no retained evidence:
  - the third log row, which moved to #444 with its run's receipts;
  - an evidence README's "applied" status for S1 and X5b.
- **Wrong sentence.** One sentence misread the old lines.
- **Unpublished usage.** Attempt 1's GPT-6 usage had not been published.
- **Missing failing control.** `verify_lane_a.py` had no failing run.

**Re-check.** The re-check found every finding repaired in the working tree, and four open items (`lane-a/review/claude-recheck.md`):
- **Ids in the commit (blocking).** The subagent ids were still in the unpushed content commit. The repair was folded into that commit before the first push, and `git log -p` of the pushed range finds no id.
- **Line 56.** It still called the RTK read the runtime's own startup read. It now matches the anti-pattern row.
- **A missing hash list.** `final/frozen-a2.sha256` was not in the hash report. The report now covers it. A new check shows that each of the 16 published copies that differ from their frozen or sent hashes is its original after the packager's replacements and nothing else (`lane-a/review/placeholder-check.json`, with its failing run).
- **The packager's refusal.** It fires only on copies published byte for byte. The scanner's count, 6 before and 0 after, is the control.

No second GPT-6 round was run.

## Alternatives considered

- **The packet's proposed X5c text.** It read "…current upstream SOTA is the source of truth; never self-write without a SOTA source…" and dropped the installed client from the top rule. All four adjudications rejected it. It passes every test (`proposed/` in the adjudication root). The case against it is meaning, not mechanics.
- **No edit.** This was the original plan's fixed rule for X5. It was superseded by the user's direction above and by the operator's own new top rule, which both templates exist to carry.
- **Copying the operator's whole paragraph into both templates.** Not proposed. The portable template is held to a word ceiling, 1,265 by `wc -w`, and the Codex block to a pinned size. `AGENTS.md` (X5b) carries the fuller paragraph for this repository.

## Comparison that would overturn it

- **A behavior comparison.** A preregistered comparison in which Codex or Claude sessions loading these templates follow the capability-check order or the research-first rule measurably worse than with the previous lines, for example by trusting upstream over the installed version.
- **A change to the rule itself.** The operator rewords the user-level top rule again; the templates follow it.
- **A client change.** A client release changes how `AGENTS.md` or `CLAUDE.md` is loaded or sized, such as Codex's `project_doc_max_bytes`.

## Limitations and residuals

- **No behavior test.** No behavior difference was measured. The checks are text, pin and registration checks.
- **Limits on blindness.** They are listed in the evidence README:
  - one return's stated inability to hash may hint at its family;
  - the judges were told as a neutral fact that X5a is applied.
- **Host step.** A Codex home that installed the lane block keeps the old line until `tools/adoption/apply_codex_lane.py` is run there again after this merges: a dry run, then the `--apply` command that the dry run prints, with its `--expect-*` hashes (`--apply` without them exits 2). The script refuses while Codex runs.
