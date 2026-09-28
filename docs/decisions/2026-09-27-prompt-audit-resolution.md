# Decision: resolve the 2026-09-27 prompt audit by cross-family convergence (2026-09-27)

**Decided by:** the user's request of 2026-09-27 ("please resolute with convergence practice, gpt6 runtime workers sota
harnesses in your end"), which followed a `/claude-api prompt-audit` run at `c8362c02`. One coordinator session
carried it out under an approved plan. The judgment packet was frozen at `origin/main@55fc8d17`. The edits were
verified on `b26add90` and then rebased onto later `main` commits for merge. The inputs, returns, controls and usage
are retained in
[`evidence/artifacts/prompt-audit-20260927/`](../../evidence/artifacts/prompt-audit-20260927/).

**Scope:** 13 items:
- the audit's four findings (F1-F4) and six flags (X5-X10);
- three defects found while planning (N1-N3).

The edits land in two pull requests:
- **`lane:foundation`:** the landscape-sweep templates, their test, two READMEs and the anti-pattern log.
- **`lane:shared`:** `AGENTS.md`. It needs the trading lane's acknowledgement.

This unit edited no permission text (X5, X8) and no vendored workflow script (X6, X10). F4 rewords one prohibition
in the trading section of `AGENTS.md` without weakening it: "future experiments must not call it" becomes "no
experiment may present it", which covers every experiment. The unit claims no change in model behavior.

## Decision

| Item | Location | Round 1 (GPT-6 / Claude) | Adjudication | Result |
| --- | --- | --- | --- | --- |
| F1 | `AGENTS.md:36` | agree / amend | 4 of 4 for the amendment | Applied in the `lane:shared` pull request, pending the trading lane's acknowledgement. Role dispatch covers new or ad-hoc stages. Only the scripts vendored in the workflows directory keep their reviewed routing, byte-identical to agent-lab, as that README states in its opening paragraph and in the Workflow contract's "Dispatch by role" bullet (lines 9-10 and 219 at `55fc8d17`). |
| F2 | `templates.json`, 11 all-caps scope words | reject / agree | 4 of 4 for reject | Kept. No source shows that the capitals misdirect the current models (`sources.json` not found, Q1 and Q3), so lowercasing would change style, not behavior. |
| F3, X7 | `templates.json` `facts` | agree, agree / amend, amend | 4 of 4 for the amendment | Applied. One sentence after "Default to refuted=true when uncertain." names the exceptions for unknown fields, maintenance and licenses. |
| F4 | `AGENTS.md:73-74` | agree / agree | not needed | Applied in the `lane:shared` pull request, pending the trading lane's acknowledgement. The inspected 2021 control segment is described in current-state wording. |
| X5 | `AGENTS.md:3` and `examples/claude-native/CLAUDE.md:5` | agree / agree | not needed | Recorded, not edited. The broader rule covers the narrower one. |
| X6 | the shared worker packet | agree / agree | not needed | No change. The packet is vendored and test-pinned, so a fix belongs in agent-lab. |
| X8 | "after the current foundation work" | agree / agree | not needed | Recorded, not edited. This is permission text. |
| X9 | `CLAUDE.md:3-4` | amend / amend | split, 2 and 2 | No edit. The user decides (see below). |
| X10 | `review-changes.js:72`, `readiness-audit.js:96` | agree / agree | not needed | No change. The scripts are vendored and each emphasis is reasoned. |
| N1 | landscape-sweep `README.md:192-195` and `:435-439`, and lines 17-19 of the 2026-09-26 run's evidence `README.md` | agree / amend | 4 of 4 for the amendment | Applied. The text now points at `PROMPTS_SHA256_CURRENT`, names the ledger entry as the run's registered record and dates the claim that went stale. |
| N2 | `docs/harness-defaults.md`, the anti-pattern log | agree / agree | not needed | Applied. The blank line is gone, and the log check rejects a split table. |
| N3 | the same log | amend / amend | 4 of 4 for one lane's rows | Applied. Four dated rows were added. |

## Method

- **Frozen packet.** Before either lane ran, a script extracted from `55fc8d17` each item's excerpts, `git blame`
  dates, proposed text and test constraints. It wrote them to `packet.md` (sha256 `0e6b6430…7877`).
  - The retained copy redacts one Claude Code session URL that the packet quoted from a commit message (line 288),
    so its sha256 is `8d994d2e…4c9c`. Both adjudication inputs, which quote the same line, are redacted the same
    way. The lanes judged the unredacted texts.
  - One `stack-researcher` gathered the shared primary sources into `sources.json`: S1-S14, plus seven searches that
    found nothing, recorded as not found.
- **Round 1.** Two lanes judged the same packet against the same schema, and neither saw the other's answer:
  - **GPT-6:** one job of the packaged runner `tools/sota-convergence/landscape-sweep/codex_call.sh`. It ran
    `codex-cli 0.157.1`, `gpt-6-astra` at effort `max`, with a read-only sandbox, live web search and
    `--ignore-user-config`. A probe with `build_args.PROBE_PROMPT` passed first: exit 0, no usage limit hit.
  - **Claude:** one `evidence-reviewer` (frontmatter `model: opus`, `effort: max`), with read-only tools and no web
    access.
- **Rule.**
  - Both lanes agree: apply the proposal. Both reject: keep the text.
  - Anything else goes to one adjudication round. Each family judged the six split units twice, with the two returns
    anonymized and shown A/B, then B/A (`adjudication/mapping.json`).
  - A unit is applied only when all four adjudications choose the same return. Otherwise it stays unchanged, and
    both positions are recorded, because a split stays pending
    ([`tools/sota-convergence/README.md`](../../tools/sota-convergence/README.md)).
  - X5 and X8 were fixed as no-edit in advance.
- **Adjudicators.** GPT-6 ran as two runner jobs, and Claude as two `evidence-reviewer` calls.
  - The role table's `blind-adjudicator` was not used. Its input contract is a layer-verdict winner set, and its leak
    rule rejects any model name. These returns quote model names as subject matter; for example, the landscape-sweep
    `README.md:41` names "claude-opus-5-5".
  - The returns were blinded only by instruction and by a separate directory holding the anonymized inputs. Nothing
    enforced it.
- **Prompts.** The prompts as sent named host paths, so they are retained only as sanitized headers and briefs,
  with how each prompt was assembled (`prompts/construction.json`). Before sanitizing, each GPT-6 job's recorded
  `prompt_sha256` was checked against the prompt file sent on the host, and all four matched.
- **Application.** Each chosen return's text was applied exactly as written, and every replaced string matched once.
  - One addition: the new facts-refuter test also asserts the license phrase, as the approved plan required for X7.
    The adjudicated resolution listed only three phrases.
  - One qualifier: the second N3 row counts "the fifth 2026-09-27 row" at `55fc8d17`. After the rebase, the rows
    #438 and #439 added above it moved that row down, so the row now says "(at `55fc8d17`)". Its meaning is unchanged.
- **Review.** Before the repair round, one `evidence-reviewer` read both diffs, and one read-only GPT-6 `codex exec`
  per head read each diff, on the unpushed first heads (`review/`). One repair round fixed the supported findings:
  the redacted session URL, the retained prompt provenance, a README line citation, the pending status of F1 and F4
  here, the wording of F4's prohibition, the facts stage's run frequency, the usage note, the N3 row qualifier, and
  controls re-run on the committed heads with their provenance.

## Sources read (2026-09-27)

| Source | Version | What it settled |
| --- | --- | --- |
| S1 [Anthropic prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) | web page | It ties the advice to dial back aggressive language to Opus 4.5 and 4.6 (F2) |
| S2 [Prompting Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5.md) | web page | "If you need Claude to apply an instruction broadly, state the scope explicitly" (F4) |
| S5 [Claude Code best practices](https://code.claude.com/docs/en/best-practices.md) | web page | Emphasize only the one line Claude keeps skipping, because "If you emphasize many lines, none of them stands out" (F2, X10) |
| S6 [Claude Code commands](https://code.claude.com/docs/en/commands.md) | web page | "A command is only recognized at the start of your message" (X9) |
| S7 [Claude Code skills](https://code.claude.com/docs/en/skills.md) | web page | The Skill tool reaches only a few built-in commands, `/init` and `/security-review` among them (X9) |
| S8 [Claude Code memory](https://code.claude.com/docs/en/memory.md) | web page | A subdirectory's CLAUDE.md loads when Claude reads files there (X5) |
| S9 [OpenAI GPT-5 prompting guide](https://github.com/openai/openai-cookbook/blob/6dc6324fb9ed780b32b787f23fad336e9f1eff15/examples/gpt-5/gpt-5_prompting_guide.ipynb) | `6dc6324f` | Cursor found a capitalized "Be THOROUGH" instruction counterproductive with GPT-5 (F2) |
| S10 [OpenAI: Using GPT-6](https://developers.openai.com/api/docs/guides/latest-model.md) | web page | GPT-6 Astra is more sensitive to instructions in files such as `AGENTS.md`; audit them (X5, F2) |
| S11 [GFM spec](https://github.github.com/gfm/) | 0.29-gfm | "The table is broken at the first empty line" (N2, N3) |
| S12-S14 [OpenSSF Scorecard](https://github.com/ossf/scorecard/tree/f92023a3f77879f96e0c9c1305f289d755be4bb6) `docs/checks.md`, `checks/evaluation/maintained.go`, `checker/check_result.go` | `f92023a3` | The Maintained check, and what an unknown result means (F3) |
| T1-T3 (adjudication supplement): Claude Code [plugins](https://code.claude.com/docs/en/plugins.md) and [MCP](https://code.claude.com/docs/en/mcp.md) pages, GFM 4.10 | fetched 2026-09-27 | A plugin can hold skills, agents, hooks and MCP servers; MCP tools are deferred; a pipe inside a cell is escaped (X9, N3) |
| Not found | none | An Anthropic statement on all-caps wording for the 5.x models; OpenAI guidance on it beyond S9; a statement on whether the model can invoke `/mcp` or `/context` |

## Checks

Each check was run on the base first, and on the base it fails. The `controls/` files are in the evidence directory.
Each one starts with what it shows, which files came from the base (origin/main), the blob id of each tested file
and the command, and it ends with the exit code.

- **N2.** On a split-table mutant:
  - the base's check returns `[]` (`n2-1`);
  - the new check reports one error (`n2-2`).

  The new check fails on the base page (`n2-3`, `FAILED (failures=1)`). With the blank line removed, its three
  tests pass (`n2-4`).
- **F3 and X7.**
  - The new test fails on the base templates with "'a null upstream_now field means unknown' not found" (`f3x7-1`),
    and passes on the converged templates (`f3x7-2`).
  - On the converged templates, the base's pin test fails with `11fcd523… != f64eec22…` (`f3x7-3`), which shows the
    change detector reacts.
  - `PROMPTS_SHA256_CURRENT` is now `11fcd52312b9…0107`, and `PROMPTS_SHA256_20260926` is kept.
- **Affected modules.**
  - `tests.test_landscape_sweep_harness` and `tests.test_adoption_docs_consistency`: 160 tests OK, 4 skipped
    (`pr1-modules-after`, verbose, with the skip reasons).
    Shellcheck and a bash 3.2 binary are absent, `CONTEXT_MODE_SECURITY_JS` is unset, and one profile-table check found
    no profile whose coverage differs between the pinned release and HEAD.
  - `tests.test_install_claude_profile` on the `AGENTS.md` change: 58 OK, 3 skipped, each because this host has no
    PyYAML (`pr2-install-profile-after`, verbose).
- **CI-equivalent list:** every local step of CI's `validate` job passed on both heads except the full unittest run.
  There the same two tests fail on both heads and on the unmodified base (`env-1`). One creates its temporary
  directory with `dir="/tmp"`. The other starts a runner child without `TMPDIR`, and that child refuses `/tmp` as
  its scratch root. This host has a stray `/tmp/.git` directory, so both checks count `/tmp` as inside a repository.
  Each pull request lists the commands under "Local commands run".

## Measured results

Exact counts come from `count_files` in [`tools/token-report/token_manifest.py`](../../tools/token-report/token_manifest.py)
(gpt-tokenizer 3.4.0, `o200k_base`). They count the files themselves, not Claude's tokenizer and not billed usage.

| File | Loaded | Tokens | Words | Lines |
| --- | --- | ---: | ---: | ---: |
| `AGENTS.md` | Claude (via `@AGENTS.md`) and Codex sessions in this repository | 2,374 → 2,401 (+27) | 1,477 → 1,495 | 103 → 103 |
| `tools/sota-convergence/landscape-sweep/templates.json` | the `facts` key: the Claude refute-facts stage, once per layer and round that has proposals | 2,239 → 2,305 (+66) | 1,413 → 1,466 | 8 → 8 |
| `CLAUDE.md` | Claude sessions in this repository | 30, unchanged (X9 split) | 18 | 4 |

Provider usage is recorded in `usage.json`, once per job or agent. The coordinator session's own usage is not
included.
- GPT-6 runner (`input_tokens` includes the cached tokens, and `output_tokens` includes reasoning):

| Job | Input (cached) | Output (reasoning) | Wall time |
| --- | ---: | ---: | --- |
| probe | 79,781 (42,624) | 702 (491) | 38 s |
| round 1 | 1,579,412 (1,432,448) | 24,440 (14,080) | 12 min 50 s |
| adjudication A/B | 1,358,260 (1,233,536) | 18,359 (8,270) | 9 min 58 s |
| adjudication B/A | 873,686 (762,368) | 13,187 (4,945) | 7 min 15 s |

- Claude subagents, from their transcripts, deduplicated per API call. The Anthropic fields are disjoint.

| Agent | Calls | Input | Cache write | Cache read | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| three `Explore` agents (planning) | 172 | 344 | 521,174 | 21,987,846 | 56,071 |
| `stack-researcher` (sources) | 22 | 46 | 122,916 | 1,738,821 | 61,720 |
| `evidence-reviewer`, round 1 | 53 | 110 | 564,261 | 9,049,321 | 158,874 |
| `evidence-reviewer`, adjudication A/B | 27 | 56 | 467,011 | 3,972,567 | 109,885 |
| `evidence-reviewer`, adjudication B/A | 39 | 80 | 247,961 | 6,214,764 | 105,940 |
| `evidence-reviewer`, review of both diffs | 80 | 162 | 295,706 | 14,973,449 | 115,650 |

- GPT-6 reviews: each ran as one `codex exec` call, whose own "tokens used" totals were 139,158 (PR-1) and 103,290
  (PR-2), with no breakdown by category (`review/README.md`).

## Alternatives considered

- **Apply the audit's patch as proposed, with one family's judgment.** Rejected, because the lanes found defects in
  five of the proposals:
  - N3's second row had an unescaped pipe inside backticks, so the log's shape test would have split it into six
    cells and failed.
  - F1's "Saved scripts keep their reviewed routing" widened the README's exemption to every saved workflow, such as
    `landscape-sweep/sweep.js`.
  - The combined facts sentence exempted only unverifiable facts. A null `upstream_now` field judged false would
    still be refuted: the retained run refuted anomalyco/opencode and alpacahq/cli on exactly that, at
    `evidence/artifacts/landscape-sweep-20260926/returns.json` lines 2218 and 17006.
  - N1 left the evidence README's stale claim in place and called that README the registered record, when the
    registered record is the ledger entry.
  - N3's rows misplaced both the blank line and the exemption.
- **Adjudicate with `blind-adjudicator`.** Not used; the reasons are under Method.
- **A fixture A/B of the facts template.** Not run:
  - live `gh api` answers make fixtures unstable;
  - `common` is already in the same prompt;
  - the sweep's mandatory smoke exercises the real stage.
- **Lowercase the capitals anyway.** Rejected under the packet's rule to judge wording by whether the model follows
  it as intended, not by style.

## Comparison that would overturn it

- **F3 and X7:** the next landscape-sweep smoke or run.
  - If the facts refuter still refutes a proposal only for a null `upstream_now` field, an unverifiable commit or
    activity fact, or a license discrepancy, the sentence failed.
  - If fabricated `upstream_now` values start passing the facts gate, the exception is too broad.
- **F2:** either of these reopens it:
  - an interleaved A/B of the discover and fit prompts, with and without the capitals, on the same client versions,
    that shows a difference in scope adherence;
  - a vendor statement on all-caps wording for the current models.
- **F1:** a saved workflow outside the vendored directory that should keep unrouted stages. Broaden the README's rule
  first, then this line.
- **X9:** the user's choice between the two texts below, or a client release that lets the model invoke `/mcp` or
  `/context`.
- **N2 and N3:** a GitHub rendering of the log that differs from the GFM spec. No rendering was observed.

## Limitations and residuals

- **X9 is for the user.** Both families agree that `CLAUDE.md:3-4` tells the model to run commands it cannot type.
  They differ on the fallback.
  - GPT-6 lane:

    ```text
    Before claiming a plugin or MCP server is active, verify the relevant component in this
    session: tools (including deferred tools via ToolSearch), skills, agents or hooks.
    Distinguish listed availability from successful execution. Use available read-only
    diagnostics first; if the claim remains unresolved, ask for the relevant `/plugin`,
    `/mcp` or `/context` output. Invoke a command through Skill only if the installed
    client exposes it there.
    ```

  - Claude lane:

    ```text
    Before claiming a plugin or MCP server is active, confirm that its tools, skills or hook output are
    present in this session (ToolSearch loads a deferred tool). `/mcp` and `/context` are user-typed commands:
    when your session cannot settle the claim, report it as unconfirmed and name the command that would.
    ```

  - In both orders, each family's adjudications chose that family's own lane.
  - This split is not a general preference for one's own lane: the GPT-6 adjudications chose the Claude lane's
    return on four units, and both Claude adjudications chose the GPT-6 lane's reject on F2.
- **X8:** "after the current foundation work" is undefined in eight places, and only the user can define or close it.
- **X5:** the portable template's top rule differs from the host's user-level file. That is the operator's call.
- **X6 and X10:** any change belongs upstream in agent-lab.
- **F3 and X7:**
  - A verified but stale activity value still refutes a proposal. For example, eslazarev/purged-cross-validation was
    refuted when same-day upstream activity overtook the snapshot's `pushed_at` and latest release (`returns.json`
    line 15198). A blanket exemption would let a fabricated `upstream_now` through.
  - The phrase "(the selection principles)" also covers unknown fields in general, while `common` states its pending
    rule only for the commit fact.
  - The retained refutations ran on Sonnet. The facts role has run on Opus since 2026-09-27 (landscape-sweep
    `README.md:60`).
- **N1:** some dated records still say the packaged templates reproduce the 2026-09-26 hash and are left unchanged:
  - the hash-chained ledger note at `catalogs/saturation/ledger.json:2846`;
  - the lane-limit text in that run's `lanes.json` and `catalogs/sota-convergence/manifest-20260926.json`;
  - item 1 under "Lane limits" in that run's evidence `README.md`. It copies the same text, and the README introduces
    that list as the limits passed with `--limit`. The corrected, dated statement is at the top of the same README.
- **N3:**
  - The third row records a mistake that F1 fixes in the `lane:shared` pull request, which waits for the trading
    lane's acknowledgement.
- **Evidence classes:** source review, local checks and retained model judgments. No sweep ran for this unit, and no
  model-behavior claim is made.
