# Per-tool token-stack evidence cards (2026-09-27)

- Host: `nativestack-5975wx-20260925` (the WSL2 workstation).
- Cards: 18 token-stack tools, one JSON file each in [`cards/`](cards/), with [`cards/index.json`](cards/index.json).
- Invoke-rate snapshot: [`invoke_by_tool.json`](invoke_by_tool.json).
- Verdict evidence the cards cite: [`groups/verdict-evidence.json`](groups/verdict-evidence.json),
  [`groups/final-verdict-evidence.json`](groups/final-verdict-evidence.json) and
  [`groups/g5-g6-verification.json`](groups/g5-g6-verification.json). The `groups/` path keeps the cards' own
  citations resolvable.
- Topic projection: [`project_topic.py`](project_topic.py) writes the cards into the rows of
  [`docs/token-efficiency-stack.json`](../../../docs/token-efficiency-stack.json), and `--check` confirms they match.
  The explorer (`python3 scripts/build_ecosystem.py --write`) shows them in each topic row's detail.

The cards come from the plan's per-tool evidence-card workflow. GPT-6 (`gpt-6-astra` at reasoning effort `max`,
through `codex exec`) wrote each tool group's upstream deep dive and native-adaptation assessment, reviewed an
earlier assembly of each card against its cited sources, and gave a final verdict after the coordinator edited the
assembler (see [Card-review findings in the published cards](#card-review-findings-in-the-published-cards)). Each card's
`gpt6_review.harness` records those three runs: model, effort, loaded skills, MCP calls by server, shell commands
and web searches.

A deterministic assembler built the evidence fields (`e2e_returned_results`, `adapted_performance`, `invoke_rates`)
from the retained run records, except for three values the coordinator typed into it:

- `adapted_performance.q3_fixture` (`assemble.py` lines 142-146);
- the rtk `codex_native_exec` comparison (lines 97-100);
- every `shortfall_cause` text, which the assembler copies from a hand-written `CAUSE` table in the coordinator's
  `html-report/render_page.py`. That file has changed since the assembly, so the cards are the record of the text used.

The `retracted:` labels in `eligibility` are typed text too (lines 66-69). Apart from those typed values, no model
computed or transcribed a number in these fields. The card-review findings rtk F0-F2, toon F0 and
codebase-memory-mcp F0-F1 are about these typed fields.

## What each section is, and its evidence class

| Card section | Contents | Evidence class and boundary |
| --- | --- | --- |
| `upstream` | Latest release and date, our pin, how far behind, the official install and Claude/Codex wiring, official baseline claims, limitations, changes since our pin | GPT-6 upstream source review. Every fact carries its URL. Not an installation or an execution. |
| `native_adaptation` | How this repository installs and wires the tool per client, its lane rule, each deviation from upstream and why, pending fixes | GPT-6 assessment of our recipes, templates and host wiring, with repository paths. An assessment, not acceptance. |
| `e2e_returned_results` | The upstream commands run, their returned summaries, the fidelity check, `records_total` and 10 records | Local integration: upstream native operations on this host against fixture commit `803bc351`, captured 2026-09-26T22:53:19Z. Not upstream tests. `records_total` uses the assembler's scope; see [Record counts](#record-counts). |
| `adapted_performance` | `exact_comparisons`, `native_counter`, `native_snapshot`, `shortfall_cause`, `q3_fixture` | Three different classes, never summed: exact `o200k_base` artifact comparisons per payload and lane; the tool's own counter over its fixture window; upstream retained-history estimates. None of them is provider savings. |
| `invoke_rates` | For each population (Ultracode workflow children, with and without the lanes block, Agent-tool subagents, main Claude sessions, Codex exec workers): MCP calls, CLI calls, agents invoking, agents | Transcript-derived invocation attempts from 2026-09-25T11:37:28Z to 2026-09-26T23:37:28Z. `live_otel` is a separate Loki window from 2026-09-26T22:50:00Z. Attempts, not success rates or savings. |
| `gpt6_review` | The card review's verdict, findings and dispositions (the card field `resolutions`); the final adaptation verdict with gaps and verified claims | A GPT-6 review of an earlier assembly, not acceptance. Each disposition is either an edit made in the one repair round or a deferral, whose text starts with `deferred`. The re-assembly after the review fixed some findings with no disposition, so read each finding's status in the published card in [the findings table](#card-review-findings-in-the-published-cards). |

The arm-B native rows (`invoke_rates.arm_b_native`) stay `pending` until the preregistered E2E runs.

## Per-tool summary

| Tool | Topic row | Upstream-command E2E | Records: card rule / tool's own | Exact comparisons | Card review (as recorded) | Findings now: applied / partial / open | Adaptation verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rtk | yes | pass | 57 / 43 | 3 | defects: 3 findings, 0 dispositions | 2 / 1 / 0 | adapted-with-gaps |
| toon | yes | pass | 19 / 19 | 3 | defects: 2 findings, 1 disposition | 2 / 0 / 0 | adapted-with-gaps |
| gpt-tokenizer | no (not a selected component) | partial | 65 / 45 | 0 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| context-mode | yes | pass | 84 / 64 | 2 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| headroom | yes | pass | 34 / 21 | 2 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| mcporter | yes | pass | 92 / 14 | 0 | accurate: 1 finding, 0 dispositions | 0 / 0 / 1 | adapted-sota |
| serena | yes | pass | 33 / 25 | 2 | defects: 1 finding, 0 dispositions | 1 / 0 / 0 | adapted-with-gaps |
| jcodemunch-mcp | yes | partial | 48 / 48 | 1 | defects: 1 finding, 0 dispositions | 1 / 0 / 0 | adapted-with-gaps |
| codebase-memory-mcp | yes | pass | 31 / 31 | 2 | defects: 2 findings, 1 disposition | 2 / 0 / 0 | adapted-with-gaps |
| socraticode | yes | pass | 34 / 34 | 2 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| qmd | yes | pass | 31 / 30 | 1 | defects: 4 findings, 4 dispositions (3 deferred) | 0 / 2 / 2 | adapted-with-gaps |
| ai-memory | yes | pass | 54 / 48 | 0 | defects: 4 findings, 4 dispositions (2 deferred) | 1 / 1 / 2 | adapted-with-gaps |
| repomix | yes | partial | 22 / 18 | 1 | defects: 1 finding, 0 dispositions | 0 / 1 / 0 | adapted-with-gaps |
| markitdown | yes | pass | 10 / 10 | 2 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| ast-grep | yes | pass | 27 / 27 | 2 | defects: 1 finding, 1 disposition | 1 / 0 / 0 | adapted-with-gaps |
| context-hub | yes | pass | 31 / 31 | 1 | accurate: 0 findings, 0 dispositions | none | adapted-with-gaps |
| ccusage | yes | pass | 17 / 11 | 0 | defects: 1 finding, 1 disposition | 1 / 0 / 0 | adapted-with-gaps |
| agentsview | yes | partial | 25 / 26 | 0 | defects: 2 findings, 2 dispositions | 2 / 0 / 0 | adapted-with-gaps |

The card-review column is what each card records; the explorer shows the same counts. A disposition is the repair
round's record, not the current state of the field: the findings table below gives each finding's status in the
published card. gpt-tokenizer has no topic row because it is not a selected component in
`manifests/stack.json` (`tools/token-report/token_manifest.py` pins it as the exact `o200k_base` counter). Seven
topic rows have no card: claude-hud, otel-tui, opentelemetry-collector-contrib, prometheus, loki, grafana and
omniroute.

### Record counts

The two record counts have different scopes, so they are not reconciled into one number:

- A card's `e2e_returned_results.records_total` (the card rule) counts every returned-result record whose
  `component_ids` includes the tool and names at most two components. That is the assembler's filter
  (`assemble.py`, line 105).
- The tool's own count is the `records` value of its component summary in `rr/returned-results.json`, which equals
  the length of the tool's own record file.

The two differ for 11 of the 18 tools. The QMD and ai-memory card reviews flagged this as a finding, and both
deferred it to the assembler. `groups/final-verdict-evidence.json` opened the attachments of each tool's own
records: 30 for QMD and 48 for ai-memory.

## Card-review findings in the published cards

Dated note, 2026-09-27. The GPT-6 card reviews and the one repair round read an earlier assembly of the cards, not
the published files. File modification times in the coordinator's working set show this order (UTC, 2026-09-27):

| Time | Step |
| --- | --- |
| 01:37Z to 01:57Z | The six group reviews wrote their findings. |
| 01:43Z to 02:04Z | The repair round wrote its dispositions and upstream edits. The context-sandbox group (context-mode, headroom, mcporter) has no repair output. |
| 02:09:55Z | The coordinator edited the assembler: the `assemble.py` whose hash is under [Sanitization](#sanitization). |
| 02:29Z to 03:25Z | The final-verdict runs wrote the verdicts in `gpt6_review.final_verdict`, after that edit. |
| 03:27:02Z | The assembler wrote the published cards. It copies each review file into `gpt6_review` (`assemble.py` line 164), changing only what its `clean()` rewrites (see [Sanitization](#sanitization)). |

The contents agree with that order. rtk F0 says the card cites "record codex-34", and serena F0 says the assembler
reads `panels_29_to_38`; the hashed `assemble.py` cites `codex-34-o200k-compare` (line 98) and reads `panels` first
(line 121). A finding can therefore quote field text that the published card no longer has.

A check on 2026-09-27 compared all 23 findings with the published card text. It is a local text check, not a GPT-6
run and not acceptance. 13 findings are applied, 5 partial and 5 open. F0 is the first entry of
`gpt6_review.findings`, F1 the second, and so on.

| Finding | Field | Card disposition | Status in the published card | Published text |
| --- | --- | --- | --- | --- |
| rtk F0 (medium) | `adapted_performance.exact_comparisons` | none | applied by the re-assembly | `exact_comparisons[2].payload` cites "record codex-34-o200k-compare" |
| rtk F1 (medium) | `adapted_performance.exact_comparisons[2]` | none | applied by the re-assembly | 356 → 341 tokens (-4.2%), eligibility "lossy pair: its fidelity check matched 7 of 10 commit subjects; not a measure of the AGENTS.md channel" |
| rtk F2 (medium) | `adapted_performance.shortfall_cause` | none | partial | The 16,493 skips are now "not classified by cause", and the text lists what the hook refuses. It still ends "the fix is inline text (PR-D)", a pending-fix label the finding asked to replace with verified mappings only. PR-D merged later (`50b9579f`, 2026-09-27T07:05Z); no card run verifies it. |
| toon F0 (medium) | `adapted_performance.shortfall_cause` | none | applied by the re-assembly | "our handbook's 5-record minimum is a local heuristic" |
| toon F1 (low) | `upstream.new_since_pin[1].text` | edited | applied in the repair round | "send usage accompanying invalid-argument errors to stderr while requested help remains on stdout" |
| mcporter F0 (low) | `native_adaptation.assessment` | none | open | Still "the lanes-block population", not `workflow_children_with_lanes_block` |
| serena F0 (medium) | `invoke_rates.live_otel.series` | none | applied by the re-assembly | One series: `codex_exec` → `serena`, "4" calls |
| jcodemunch-mcp F0 (medium) | `e2e_returned_results.upstream_commands[2..5].cmd` | none | applied by the re-assembly | `--config <scratch>/rr/jcodemunch-mcp/mcporter.json`, with the `rr/` segment in the HOME, CODE_INDEX_PATH and clone paths; see the note below |
| codebase-memory-mcp F0 (medium) | `adapted_performance.q3_fixture.false_positive` | none | applied by the re-assembly | "true edges range 0.38-0.95" |
| codebase-memory-mcp F1 (medium) | `q3_fixture.usage_fix`, `native_adaptation.deviations_from_upstream[0].fix`, `native_adaptation.pending_fixes[2]` | edited (the two `native_adaptation` fields) | applied, by the repair round and the re-assembly | `usage_fix`: "a 0.5 cutoff cuts recall to 7 of 12"; `pending_fixes[2]`: "from 9/12 to 7/12" |
| qmd F0 (medium) | `adapted_performance.exact_comparisons[0].payload` | deferred | partial | Eligibility "retracted: PR #343 found the answer came from the wrong document"; the payload still ends "answer verified (PASS)" |
| qmd F1 (medium) | `e2e_returned_results.fidelity.result` | deferred | open | "answer verified (PASS); verifier: agree, 2 defects" |
| qmd F2 (low) | `e2e_returned_results.records_total` | deferred | open | 31 by the card rule; the tool's own record count is 30 ([Record counts](#record-counts)) |
| qmd F3 (low) | `native_adaptation.assessment` | edited | partial | "records_total=31 (the card's own figure, with exact reconciliation against the retained record sources still open)"; the count itself waits on F2 |
| ai-memory F0 (medium) | `upstream.recommended_install.command` | edited | applied in the repair round | "cargo install --locked --git https://github.com/akitaonrails/ai-memory --tag v2.4.1 ai-memory-cli", after the mise, release-archive and source-build routes |
| ai-memory F1 (medium) | `native_adaptation.stack_entry.freshness` | deferred | open | "The 7 changed Codex hook commands await the user's /hooks re-trust."; see the note below |
| ai-memory F2 (low) | `e2e_returned_results.records_total` | deferred | open | 54 by the card rule; the tool's own record count is 48 |
| ai-memory F3 (low) | `native_adaptation.assessment` | edited | partial | "records_total=54 (the card's own figure, with exact reconciliation against the retained record sources still open)"; the count itself waits on F2 |
| repomix F0 (medium) | `adapted_performance.exact_comparisons[0].payload` | none | partial | Eligibility "retracted: the pack silently dropped a multi-line signature, so the 47-name check was a false pass"; the payload still says "all 47 function names verified (PASS)", as `groups/g5-g6-verification.json` also records |
| ast-grep F0 (medium) | `upstream.limitations[1].text` | edited | applied in the repair round | Registration "still occurs during that preliminary pass, before App::try_parse_from" |
| ccusage F0 (medium) | `native_adaptation.pending_fixes[1]` | edited | applied in the repair round | "all 5 were already dispositioned at assembly" |
| agentsview F0 (medium) | `native_adaptation.pending_fixes[4]` | edited | applied in the repair round | "all 4 were already dispositioned at assembly" |
| agentsview F1 (medium) | `native_adaptation.pending_fixes[1]` | edited | applied in the repair round | Cites the retained records `agentsview-11-projects-daemon`, `agentsview-12-projects-daemon-json`, `agentsview-15-session-list-claude-inclusive` and `agentsview-16-session-list-codex-inclusive` |

- **jcodemunch-mcp F0.** The review named `<scratch>/jcodemunch-mcp/mcporter.json` as the wrong path, the form that
  the coordinator's `html-report/savings.json` still holds. The assembler's `clean()` (`assemble.py` lines 37-38)
  rewrites `<scratch>/<name>/` to `<scratch>/rr/<name>/` in every card string, for each directory name under `rr/`.
  That corrected the command paths, and it also rewrote the finding's own text, so the published finding names
  `<scratch>/rr/jcodemunch-mcp/mcporter.json` as both the missing path and the retained one. That config file
  exists; the clone and isolated state directories are no longer on the host.
- **ai-memory F1.** The projection leaves `stack_entry` out, so this field is not in the explorer. It is a copy of the
  ai-memory entry in `manifests/stack.json`, whose `freshness` has the same sentence at `5f3a7c21`. The correction
  belongs to that manifest.

The cards stay byte copies; this table and the notes in the topic's `evidence_cards` block carry the statuses instead.

## Verdict evidence

`groups/final-verdict-evidence.json` (verified 2026-09-27T02:55:29Z) records, among other checks:

- 15 exact comparisons recounted from their content-addressed files with 30 artifact checks and 0 failures.
- The codebase-memory Q3 fixture: 9 of 12 known direct callers returned, 7 of them at confidence 0.5 or more.
- Live probes: QMD completed; Serena timed out after 240 s; ai-memory and SocratiCode calls were denied, because the
  tool call required approval and the approval policy was `never`.
- The invoke scan matches the card population rows and excluded 139 Codex negative-control sessions.

`groups/verdict-evidence.json` and `groups/g5-g6-verification.json` hold the version, release, wiring and retrieval
checks the other cards cite. Each file's `scope` field states its own boundary: all three are read-only
final-verdict verification, and `verdict-evidence.json` calls itself a locally authored summary of actual returned
checks, not a new provider run or an unchanged upstream test suite.

## Sanitization

All files are byte copies of the coordinator's working set except one. In `cards/jcodemunch-mcp.json`, the
fixture's isolated home directory `jcodemunch-mcp/state/home` is written as `jcodemunch-mcp/state/fixture-home`
at all 14 places. The repository's publication scanner otherwise flags that directory's `.code-index` path as a
personal home path.
The original SHA-256 is `a734a23d22ef5a4364a38e27a8a10606fceb529d50ae3d0a94c26a9f872f37c6`; the published file's is
`d9d51922f8500eff7d08c3cde6137b0a6b6d9166f08be676394c990bca9dd7ab`. `manifests/evidence.json` records every
file's SHA-256 and size.

The cards write private locations as `<scratch>/...` and `~/...`. The assembler's `clean()` (`assemble.py` lines
34-41) rewrites every card string, GPT-6's review text included: private paths become `<scratch>`, `<tmp>` and `~`,
`<scratch>/<name>/` becomes `<scratch>/rr/<name>/` for each directory under `rr/`, UUID-shaped strings become
`<uuid>` and the account name becomes `<user>`. The jcodemunch-mcp F0 note above shows one effect, and the review
checks in three cards (context-mode, headroom, mcporter) read `<user>` and `<tmp>` where GPT-6 named the account
and the temporary-directory prefix.

References to `<scratch>/`, `../rr/`, `../html-report/`, `../cbm-q3/` and the per-group `groups/<group>/` files
point into the coordinator's private working set, which this repository does not retain.
That includes the 711 returned-result records (`rr/returned-results.json`, SHA-256
`7688ae58c8e13e33178bfab1fa0d959fcfee1a2b54cb3bd20e2e6f263360224f`) and the assembler (`assemble.py`, SHA-256
`5a734cec0c49739ffec5fc6fbc9474559ced5f2a09fb1ec4d8dddda441ecd32c`).

## Correction to the "16 of 16" statements

This change also replaces two stale aggregate statements about the 2026-09-25 subagent run: "All 16 tools worked"
in [the token-efficiency guide](../../../docs/token-efficiency-stack.md#inside-ultracode-subagents-2026-09-25) and
"16 of 16 tools used ... with passing checks / Codex workers blocked until 2026-09-30" in the grand-dashboard gate
`token-stack-subagent-e2e`. The replacements rest on receipts already in this repository:

- QMD's pass was a wrong-document retrieval: [the receipt's own note](../token-e2e-ultracode-20260925/README.md#retained-failures-and-gaps)
  and [the Codex run](../token-e2e-codex-20260926/README.md#correction-to-296).
- Repomix's `count=47 PASS` was a false pass: [the laptop reproduction](../token-e2e-ultracode-laptop-20260926/README.md#retained-failures-and-gaps).
- ai-memory's check (`PASS base_empty=True hits=10`) compared against an empty baseline, and the receipt records no
  failing control for any check ([receipt](../token-e2e-ultracode-20260925/receipt.json), `tools[].quality_check`).
- The Codex workers ran after a re-login: 11 of 15 passed on 2026-09-26 ([the Codex run](../token-e2e-codex-20260926/README.md)).

A GPT-6 review of the two subagent receipts on 2026-09-26 found these stale statements. That review is not retained
here, because its links name a private session path; every fact above cites a retained receipt instead. The
historical receipts are unchanged. Adding their own errata is separate work.

## Re-verify

```sh
python3 evidence/artifacts/token-stack-cards-20260927/project_topic.py --check
python3 -m unittest tests.test_ecosystem_manifest.TokenTopicEditionTests
python3 scripts/build_ecosystem.py --check
```

These cards are this host's dated evidence. A new host collects its own acceptance.
