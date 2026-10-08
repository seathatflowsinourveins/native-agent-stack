# Decision: carry the operator's 2026-09-28 top rule into the portable and Codex templates (2026-09-28)

**2026-10-08 amendment:** the owner directly approved the tightened fourth core bullet at about 13:46Z; command-center item `task-ns2604-coop-20261008T134651Z` assigns its seven maintained surfaces and pinned tests to convergence-practice. The [dated amendment below](#2026-10-08-owner-approved-proactive-convergence-amendment) records the wording, historical evidence boundary and declared expectation changes.

**Practice (2026-09-28):** carry the tested top rule consistently in the portable Claude and Codex templates, using [Codex's native AGENTS.md discovery](https://developers.openai.com/codex/guides/agents-md) and [Claude Code's native memory hierarchy](https://code.claude.com/docs/en/memory) as the loading contracts (official documentation checked 2026-10-08). The user-level instruction carrier observed at 2026-09-28 07:34Z and the frozen audit artifacts retain the historical executed input; the maintained configuration follows:

The following maintained projection includes the owner-approved 2026-10-08 amendment. The 2026-09-28 executed wording remains in the frozen audit artifacts.

> **Top rule: research convergence first; current upstream SOTA is the source of truth.** … The ecosystem compounds: a request is a starting point, not a boundary. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record the correction.

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

The maintained X5a/X5c projections, including the approved 2026-10-08 fourth-bullet amendment (the original executed lines remain in the frozen audit artifacts):

- X5a: `**Top rule: research convergence first; current upstream SOTA is the source of truth.** The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: a request is a starting point, not a boundary. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record the correction.`
- X5c: `Top rule: research convergence first; current upstream SOTA is the source of truth. The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: a request is a starting point, not a boundary. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record the correction.`

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

## 2026-10-08 owner-approved proactive convergence amendment

**Approval and scope.** At about 13:46Z on 2026-10-08, the owner directly chose the tightened option in the command-center session. Command-center item `task-ns2604-coop-20261008T134651Z` assigns one PR to convergence-practice, with the shared hot files and evidence registry in its final commit. This replaces the fourth bullet on the six maintained instruction files and updates the three maintained quotations in this decision record. It carries the same exact wording on every live instruction surface:

- The ecosystem compounds: a request is a starting point, not a boundary. Proceed where the evidence converges, and apply or propose the related improvements the work surfaces, at a moment that keeps the current focus and any protected window intact. Each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. When a claim proves wrong, record the correction.

The coordination note `escalation-harness-rule-proactive-20261008.md` tracks the proactive-convergence amendment. The practice uses supported upstream capabilities:

- The harness researches and applies maintained practice even when a prompt omits a mechanism, while preserving evidence, focus and protected windows. Native instruction discovery carries this responsibility: [Codex 0.161.0 AGENTS loader](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/core/src/agents_md.rs).
- Use runtime event hooks for supported automation: [Claude Code hooks](https://code.claude.com/docs/en/hooks) and [Codex 0.161.0 hook discovery](https://github.com/openai/codex/blob/979011409de0a60b52f179721948e65531d26144/codex-rs/hooks/src/engine/discovery.rs). Verify each handler against the installed client and retain its action boundaries.
- Keep the shared startup core concise and disclose task detail through native rules and skills: [Claude Code memory](https://code.claude.com/docs/en/memory), [skills](https://code.claude.com/docs/en/skills) and [best practices](https://code.claude.com/docs/en/best-practices).
- Enforce configured repository conditions with [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) and run recurring work through [scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). These mechanisms do not establish successful adoption by themselves. Official documentation above was fetched 2026-10-08.

The earlier longer proposal in that note is historical context; the exact tightened text approved above governs. Apply or propose related improvements when the evidence supports them and the timing preserves the active focus and protected windows. Existing authority, credential handling, landing cues and protected-window instructions continue to govern actions.

### Adherence evidence and its boundary

The [October 7 instruction-core record](2026-10-07-instruction-core.md#alternatives) cites the historical [September 25 StructuredOutput comparison](2026-09-25-model-fallback-guard.md#evidence): its record reports 5/30 control schema errors versus 0/30 treatment errors when the schema sentence was appended, and a sequential user-level-only check reports 0/30. That is the cited rationale for retaining a broadly needed rule in the always-loaded carrier. Its measured scope is Sonnet 5 at effort max on Claude Code 2.1.282 with a six-field schema.

**Correction:** the October 7 record did not run a new adherence experiment. The earlier comparison is sentence-present/absent evidence plus a sequential carrier check, not a randomized always-loaded-versus-on-demand experiment and not a test of this proactive fourth bullet. The original captures live in an untracked authoring-host archive and were not independently re-read for this amendment. The counts above are historical reported results. No current-bullet adherence gain, new model run or efficiency improvement is claimed.

### Sources and adoption path

The coordinator applied the installed `search-first` and `writing-for-agents` skills and reused the existing instruction carriers, renderer and tests. There is no new runtime, wrapper or install.

- [ECC search-first at `2b6e839771e53096d8451a213d40dc64ec8acac0`](https://github.com/affaan-m/ECC/blob/2b6e839771e53096d8451a213d40dc64ec8acac0/skills/search-first/SKILL.md), Workflow and Decision Matrix: task-scoped source discovery before changing existing interfaces.
- [Claude Code best practices, "Write an effective CLAUDE.md"](https://code.claude.com/docs/en/best-practices#write-an-effective-claude-md), fetched 2026-10-08: the file loads every session, so broadly applicable instructions belong there and should stay concise.
- [Claude Code memory, rules organization](https://code.claude.com/docs/en/memory#organize-rules-with-clauderules), fetched 2026-10-08: every-session rules and task-specific skills have different loading roles.
- [Claude Code best practices, failure patterns](https://code.claude.com/docs/en/best-practices#avoid-common-failure-patterns), fetched 2026-10-08: unrelated work can pollute context. The approved bullet explicitly preserves focus and protected windows.
- [Official OpenAI documentation: Codex AGENTS.md loading](https://developers.openai.com/codex/guides/agents-md), fetched 2026-10-08: user and project instruction files are discovered and combined by the native client. The repository's [philosophy-only decision](2026-10-08-philosophy-only-rules.md#sota-sources) pins the reviewed loader to `openai/codex rust-v0.161.0:codex-rs/core/src/agents_md.rs`.
- Existing supported integration: `tools/adoption/new_wsl_client_config.py` F9 render, `tools/adoption/apply_codex_lane.py`, and the two existing pinned test modules. Their loaders and RTK awareness text are retained.

Alternatives considered: retain the old fourth bullet, use the earlier longer proposal, or put the proactive behavior behind an on-demand skill. The owner selected the shorter tightened wording in the core. A future owner wording change or a scoped native-harness comparison showing poorer adherence or focus would reopen it; stars, agreement and unrun tests would not.

### Complete search census and frozen files

The search was `git grep -n "The ecosystem compounds"` across **all 11,538 tracked files**, with no path exclusion, at preparation base `eb5fee4db9a494729deb29bdf38dbabac23ee643`. It found 93 matching lines in 33 files. The full live set searched and updated is:

| File | Role | Base matches |
| --- | --- | --- |
| `AGENTS.md` | Repository instruction surface | 8 |
| `adoption/scaffold/AGENTS.md` | Scaffold instruction surface | 9 |
| `adoption/templates/codex.AGENTS.template.md` | Codex template surface | 10 |
| `adoption/new-wsl/codex-user-instructions.md` | Codex F9 carrier | 10 |
| `adoption/new-wsl/claude-user-instructions.md` | Claude F9 carrier | 8 |
| `examples/claude-native/CLAUDE.md` | Portable Claude surface | 8 |
| `docs/decisions/2026-09-28-top-rule-templates.md` | Maintained core and X5a/X5c quotations | 5, 37, 38 |
| `tests/test_install_claude_profile.py` | Text expectation | 1750 |

Thus `surfaces=7` means six instruction files plus this maintained decision record; the literal test copy is a test expectation. The template hash/word-count module is also updated as declared below, although its pins did not contain the searched literal.

These **25 historical evidence files were searched and are untouched**, byte for byte at the preparation base:

- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/adjudication-inputs/x5.AB.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/adjudication-inputs/x5.BA.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/judge-actions.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/packets/x5.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/prompts/judge-AB.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/adjudication/attempt2/prompts/judge-BA.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/adjudication-inputs/x5c.AB.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/adjudication-inputs/x5c.BA.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/amendment.diff`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/gpt6.BA.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/packets/x5c.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/prompts/judge-AB.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/adjudication/prompts/judge-BA.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/claude.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/packets/packet.md`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/prompts/gpt6-prompt.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/proposal.diff`
- `evidence/artifacts/prompt-audit-20260927/lane-a/final/tally-final.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/claude-brief.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/claude.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/gpt6-prompt.txt`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/gpt6.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/packet.md`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/proposals.json`
- `evidence/artifacts/prompt-audit-20260927/lane-a/round1/user-level-top-rule.txt`

The historical audit's measured bytes, usage, adjudications and native returns above remain historical. Updating the maintained quotations does not rewrite the bytes that those past runs saw.

### Host handoff, inverse and completeness

The command center owns landing on its named cue. After landing it runs F9 to render the two user-level files, then starts a fresh session in each native client and checks that the exact new bullet appears in loaded instructions. Those host and fresh-session steps are pending; repository text equality is not a fresh-session load result. The optional promptfoo adherence A/B on two related-improvement prompts remains a separate command-center/api-credit-sota action after landing.

Inverse: revert this coordinated wording/expectation change, then re-register the affected files with the existing `register_file(root, relative_path)` helper in `scripts/host_receipts.py`, following the supported Python invocation in `docs/lanes.md`'s hot-file protocol; the command center renders the restored sources and repeats the fresh-session checks. Keep historical evidence intact in either direction.

The completeness critic found two material risks: missed portable/test copies and overstating the old schema comparison. The full census covers both extra copies; the correction above preserves the actual evidence class. The next rule/adherence sweep should use the native promptfoo harness for the current bullet and distinguish related-improvement behavior from schema-format compliance.

### Changed expectations, test by test

The owner-approved wording grows each core by 224 bytes and 37 words. The existing `template_segments()` and `startup_files()` functions supply these measurements; no new counting implementation or fixed word-count assertion was added. This declaration follows the command center's #845 rule: each changed expectation is named, and 5f separately runs main's test versions against the proposed head.

| Exact test ID | Old expectation → new expectation | Classification and reason |
| --- | --- | --- |
| `tests.test_install_claude_profile.StandingRuleSurfacesTests.test_the_portable_block_is_exactly_the_core_and_the_evidence_backed_line` | Old fourth bullet in `CORE` → exact approved fourth bullet; core 1,262 → 1,486 bytes, 183 → 220 words | Behavior changed; exact equality still binds the portable block and retained evidence-backed StructuredOutput line. |
| `tests.test_install_claude_profile.StandingRuleSurfacesTests.test_every_layer_carries_the_same_core_and_no_dropped_rule` | Old `CORE` fourth bullet → exact approved fourth bullet on all six layers | Behavior changed; the six-layer set, once-only assertion and retired-rule exclusions are retained. |
| `tests.test_install_claude_profile.StandingRuleSurfacesTests.test_the_repository_file_keeps_its_core_and_the_trading_prerequisite` | Root must start with old `CORE` → root must start with approved `CORE` | Behavior changed; the trading prerequisite remains required. |
| `tests.test_codex_worker_lane.TemplateTests.test_top_rule_is_pinned_and_rendered_rtk_is_the_unchanged_pinned_source` | `TOP_RULE_SHA256`: `2618406a99bf3414e291651c17446e159c9da5885bb8a72091dc77b35c91fb62` → `bc9f31381973206657685bd1169ff18ce1f64304c3cf287be20fec314bd2aae7` | Exact source pin changed; the native RTK segment and its pin are retained byte for byte. |
| `tests.test_install_claude_profile.PortableTopRuleTests.test_rendered_startup_files_fit_each_clients_fixed_byte_budget` | Claude fixed ceiling 4,140 → 4,610 bytes; Codex 4,246 → 4,716 bytes | Numeric ceilings relaxed for the approved text; the existing `ceil(actual startup bytes × 1.05)` procedure retains its 5% headroom. |
| `tests.test_install_claude_profile.PortableTopRuleTests.test_growth_in_any_loaded_file_crosses_the_fixed_budget` | Same two ceiling constants: 4,140/4,246 → 4,610/4,716 | Same numeric co-change; the negative growth control still crosses each fixed limit and must fail. |
| `tests.test_codex_worker_lane.TemplateTests.test_agents_template_is_one_managed_block` | Measured-size comment 2,105 → 2,329 bytes | Comment only; the 8,192-byte assertion ceiling is retained. |

The last row changes no assertion. No other expectation is changed.

| Measured representation | Base → approved text |
| --- | --- |
| Fourth bullet | 208 → 432 bytes; 32 → 69 words |
| Shared `CORE` | 1,262 → 1,486 bytes; 183 → 220 words |
| Native template top-rule segment | 1,299 → 1,523 bytes; 186 → 223 words |
| Complete Codex template | 2,105 → 2,329 bytes; 286 → 323 words |
| Claude `startup_files()` scope | 3,942 → 4,390 bytes |
| Codex `startup_files()` scope | 4,043 → 4,491 bytes |

Each startup scope loads two core copies, so it grows by 448 bytes. The 5% ceiling is recomputed from the full native scope, not by adding 224 bytes to the old limit. These are deterministic artifact measurements, not model tokens, provider usage or adherence evidence.

**Discriminating control.** After the surface edits and before updating expectations, unchanged main's `StandingRuleSurfacesTests`, `TemplateTests` and `PortableTopRuleTests` ran: 32 tests, exit 1, 12 expected failing subtests across the six expectation IDs above. This establishes that the old pins and ceilings reject the new text. The command-center/5f main-test run against the final head remains its independent landing step.
