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

This unit edited no permission text (X8) and no vendored workflow script (X6, X10). F4 rewords one prohibition
in the trading section of `AGENTS.md` without weakening it: "future experiments must not call it" becomes "no
experiment may present it", which covers every experiment. Round 1 claimed no change in model behavior. Round 3
(2026-09-28) measured one, for X9 only, in headless runs.

Round 3 decided X9 and took up X5 again as X5a-c, with a new item, S1. It records why the plan's rule not to edit X5
no longer holds (see the round-3 addendum).

## Decision

| Item | Location | Round 1 (GPT-6 / Claude) | Adjudication | Result |
| --- | --- | --- | --- | --- |
| F1 | `AGENTS.md:36` | agree / amend | 4 of 4 for the amendment | Applied in the `lane:shared` pull request, pending the trading lane's acknowledgement. Role dispatch covers new or ad-hoc stages. Only the scripts vendored in the workflows directory keep their reviewed routing, byte-identical to agent-lab, as that README states in its opening paragraph and in the Workflow contract's "Dispatch by role" bullet (lines 9-10 and 219 at `55fc8d17`). |
| F2 | `templates.json`, 11 all-caps scope words | reject / agree | 4 of 4 for reject | Kept. No source shows that the capitals misdirect the current models (`sources.json` not found, Q1 and Q3), so lowercasing would change style, not behavior. |
| F3, X7 | `templates.json` `facts` | agree, agree / amend, amend | 4 of 4 for the amendment | Applied. One sentence after "Default to refuted=true when uncertain." names the exceptions for unknown fields, maintenance and licenses. |
| F4 | `AGENTS.md:73-74` | agree / agree | not needed | Applied in the `lane:shared` pull request, pending the trading lane's acknowledgement. The inspected 2021 control segment is described in current-state wording. |
| X5 | `AGENTS.md:3` and `examples/claude-native/CLAUDE.md:5` | agree / agree | not needed | Round 1 recorded it without an edit: the broader rule covers the narrower one. Round 3 took it up again as X5a-c after the operator's user-level top rule changed on 2026-09-28. X5b (`AGENTS.md:3`) is applied here, pending the trading lane's acknowledgement. X5a and X5c are applied in #458 (round-3 addendum, lane A). |
| X6 | the shared worker packet | agree / agree | not needed | No change. The packet is vendored and test-pinned, so a fix belongs in agent-lab. |
| X8 | "after the current foundation work" | agree / agree | not needed | Recorded, not edited. This is permission text. |
| X9 | `CLAUDE.md:3-4` | amend / amend | split, 2 and 2; round 3: 4 of 4 for the GPT-6 lane's text | Applied on 2026-09-28. Rounds 1 and 2 split 2 and 2. Round 3 ran the comparison that round 2 named, and all four blind judgments then chose the same text (round-3 addendum). |
| X10 | `review-changes.js:72`, `readiness-audit.js:96` | agree / agree | not needed | No change. The scripts are vendored and each emphasis is reasoned. |
| N1 | landscape-sweep `README.md:192-195` and `:435-439`, and lines 17-19 of the 2026-09-26 run's evidence `README.md` | agree / amend | 4 of 4 for the amendment | Applied. The text now points at `PROMPTS_SHA256_CURRENT`, names the ledger entry as the run's registered record and dates the claim that went stale. |
| N2 | `docs/harness-defaults.md`, the anti-pattern log | agree / agree | not needed | Applied. The blank line is gone, and the log check rejects a split table. |
| N3 | the same log | amend / amend | 4 of 4 for one lane's rows | Applied. Four dated rows were added. |
| S1 | `AGENTS.md:37` (round 3) | lane A: agree / agree | not needed | Applied here, pending the trading lane's acknowledgement. Each PR description is built from the pull-request template, whose `sota-sources` check is required. |

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
| `AGENTS.md` | Claude (via `@AGENTS.md`) and Codex sessions in this repository | 2,374 → 2,401 (+27); round 3's S1 and X5b: → 2,484 (+83), `controls/token-counts-r3-after.txt` | 1,477 → 1,495; → 1,549 | 103 → 103 |
| `tools/sota-convergence/landscape-sweep/templates.json` | the `facts` key: the Claude refute-facts stage, once per layer and round that has proposals | 2,239 → 2,305 (+66) | 1,413 → 1,466 | 8 → 8 |
| `CLAUDE.md` | Claude sessions in this repository | round 3's X9: 30 → 96 (+66) at `f508ffba`; 96 → 162 (+66) on `main` at `eb678281` and at `fb14dedf`, whose `CLAUDE.md` also holds the `## Compact Instructions` section (#453); `controls/token-counts-r3-*.txt` | 18 → 65; 62 → 109 | 4 → 8; 11 → 15 |

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
- **X9:** any of these reopens it:
  - the interactive half of round 3's comparison, which only the user can run, with the same preregistered cases and
    metrics, showing fewer wrong or more correct statuses under the Claude lane's text;
  - the same comparison on another session model or effort level, or on a plugin installed from a marketplace;
  - a client release that lets the model invoke `/mcp` or `/context`.
- **N2 and N3:** a GitHub rendering of the log that differs from the GFM spec. No rendering was observed.
- **S1:** a change to the `sota-sources` check's heading rule or to the pull-request template. The sentence follows
  the check.
- **X5b:** the operator rewords the user-level top rule again. The line follows it.

## Limitations and residuals

- **X9 is applied; its interactive half is the user's.** Rounds 1 and 2 split. Round 3's comparison and blind
  judgment chose the GPT-6 lane's text unanimously (round-3 addendum). The comparison ran headless only, and an
  interactive run, which only the user can make, is its overturn condition. The two texts were:
  - GPT-6 lane, now `CLAUDE.md:3-8`:

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

  - In rounds 1 and 2, each family's adjudications chose that family's own lane, in both orders. In round 3, both
    Claude judgments chose the GPT-6 lane's text.
  - The earlier split was not a general preference for one's own lane: the GPT-6 adjudications chose the Claude
    lane's return on four units, and both Claude adjudications chose the GPT-6 lane's reject on F2.
- **X8:** "after the current foundation work" is undefined in eight places, and only the user can define or close it.
- **X5:** resolved in round 3 (lane A). The one remaining step is on hosts: a Codex home that installed the lane
  block keeps the old line until `tools/adoption/apply_codex_lane.py` is run there again after #458 merges (a dry
  run, then the `--apply` command it prints, with its `--expect-*` hashes). On this workstation it ran after #458
  merged. The dry run planned only the managed `AGENTS.md` block, `--apply` wrote it and read it back, and
  `tools/adoption/prove_codex_lane.py` passed 7 of 7. Each other host that installed the lane needs its own run.
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

## Addendum (2026-09-28): X9's second round

After round 1 split on X9, the user asked to "proceed with research convergence". The method above provides one
adjudication round, so this second round goes beyond it. It keeps the same rule: a text is applied only when all four
judgments choose it. The evidence is in
[`evidence/artifacts/prompt-audit-20260927/x9-round2/`](../../evidence/artifacts/prompt-audit-20260927/x9-round2/).

### New evidence given to both families

- **The installed client's own responses** (Claude Code 2.1.283):
  - the Skill tool refuses `context` and `mcp` and tells the model to ask the user to run them (C1, C2);
  - a headless session's command list has `mcp` and `context` but not `plugin` (C4).
- **An executed comparison of the three texts** (the current line and the two returns): 36 headless `claude -p` runs
  of Claude Code 2.1.283 through promptfoo 0.123.1.
  - K1-K3: 27 runs on Opus 5.5 (02:23-02:36Z), preregistered before the first counted run, on three questions a
    session can settle from its own tools.
  - K4: 9 runs on Sonnet 5 (02:55-03:03Z), preregistered after attempt 1 was voided, meant as a claim the session
    cannot settle. It was added to exercise the fallback, which K1-K3 never did. Of the three returns seen from
    attempt 1, the Claude return called the fallback decisive, and both GPT-6 returns held that coverage outweighs
    it. The packet disclosed this origin but said the returns seen had named the fallback as the difference that
    decides.
- **38 dated sources** with verbatim quotes, and 5 recorded searches that found nothing.
- **The packet misstated K4's model.** It said every run used the host's default model, Opus 5.5, gave K4 the "Same
  harness", and listed Sonnet as untested. Why K4 ran on Sonnet 5 is not recorded. Both Claude judgments cite that
  scope. The outcome stands, because a split means no edit either way.

| Text | K1-K3 correct | Successful MCP call, K1 and K3 | Asked the user (K1-K4) | K4 status given | K4 runs that read settings files | Cost, K1-K3 (Opus 5.5) | Cost, K4 (Sonnet 5) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-6 lane's text | 9 of 9 | 6 of 6 | 0 of 12 | 2 of 3 | 3 of 3 | $2.45 | $0.82 |
| Claude lane's text | 9 of 9 | 6 of 6 | 0 of 12 | 3 of 3 | 2 of 3 | $2.07 | $0.40 |
| current line | 9 of 9 | 3 of 6 | 0 of 12 | 3 of 3 | 3 of 3 | $1.77 | $0.65 |

- The MCP-call column counts K1's calls to its target server and K3's calls to any server. K2's target does not
  exist, so no K2 run has one.
- `settings-reads.json` lists the settings file names each run's commands named: every K2 run, the K4 runs in the
  table and one K3 run.
- No run called the Skill tool for a built-in command, and no K4 answer gave a wrong status. The GPT-6 lane's text
  gave a K4 status in 2 of 3 runs because one run's final result was a reply to a background-command notification.
- K4's premise did not hold. Seven of nine answers cited the plugin's commands from the session's own skill list
  (`k4/skill-list-mentions.json` keeps those sentences). The skills page says "Custom commands have been merged into
  skills." (`sources-supplement.json`). So the fallback on which the two texts differ was never exercised.
- Cost is the client's estimate and descriptive only: the runs went in one fixed order and share a cached prompt
  prefix.

### Attempt 1 was void

- Its judges read a repository root at `ed3cd96c`, which holds this record, and this record names the lanes.
- Nothing kept a judge out of the coordinator's work directory. One GPT-6 judgment read both. One Claude judgment read
  this record, and the other's searches returned a line of each text from it (the evidence README explains that
  judgment's self-test hits).
- The void was recorded before any Claude choice was seen (`attempt1/void.json`). The attempt-2 audit, run on
  these transcripts, marks all four void (`attempt1/audit-selftest.json`).
- The rules for attempt 2 were recorded before any attempt-2 judge started:
  - attempt 2 is final;
  - any void judgment makes the round a split.

### Attempt 2, blind

- **Root:** a plain export of `ba1700ad`, which predates this record. None of its 7,935 files holds a string that maps
  a text to a lane. `isolation-receipt.json` gives the times of the steps before dispatch: the worktrees removed,
  the attempt-1 files and the work directory moved away, the root scanned, then the GPT-6 judges started.
- **Judges:** two families, each judging in the orders A/B and B/A:
  - two GPT-6 jobs of the packaged runner (gpt-6-astra at effort max, `-s read-only` per `codex_job.py:434` at
    `ba1700ad`, with explicit read limits);
  - two `blind-adjudicator` agents (Read, Glob and Grep only).
- **Audit:** `void_patterns.py`, applied to every command, output, search, tool result, advisor result and injected
  context. It was hashed with the audit and tally scripts before any return was read.
  - No judgment had a voiding hit.
  - No judge opened a path outside its input, its packet and the root.

| Judgment | Choice | Confidence |
| --- | --- | ---: |
| GPT-6, A/B | GPT-6 lane's text | 0.86 |
| GPT-6, B/A | GPT-6 lane's text | 0.88 |
| Claude, A/B | Claude lane's text | 0.58 |
| Claude, B/A | Claude lane's text | 0.60 |

**Decision:** split, no edit. `CLAUDE.md` stays at 30 tokens.

**Where the families agree:**
- All four rejected keeping the current line. The two Claude judgments give the reason: the client refuses the
  commands it names (C1, C2). Both GPT-6 judgments cite C1 and C2. All eight judgments across both rounds reject
  the current line.
- `/plugin` is a real interactive command. Its absence from the headless list does not contradict the GPT-6 lane's
  text.
- K1-K3 tie on the primary metric, and K4 did not exercise the fallback.

**Where they differ:**
- **GPT-6: the verification standard decides.**
  - Its text separates listed availability from successful execution. Tools can be listed from the discovery cache
    before a server connects.
  - Its text also covers plugin agents.
  - It grants that the Claude lane's text has the clearer fallback for unattended runs.
- **Claude: the fallback decides.**
  - "Report it as unconfirmed and name the command" gives a status whether or not anyone can answer.
  - `CLAUDE.md` also loads in headless runs and workflow children.
  - It grants that the GPT-6 lane's text covers more, but the runs did not show that coverage changing behavior.
- **Family alignment.** Each family chose its own lane's text in both orders, blind and audit-clean.
  - That is two judgments per family on one unit, so it is recorded as a fact about X9, not as a general bias.
  - The round-1 note above covers all units and still stands.
  - The confidence gap is descriptive.

**Comparison that would decide it:** a preregistered comparison of the two texts in headless and interactive
sessions, on two cases:
- a component that nothing in the session lists, such as a plugin with hooks only. This tests the fallback.
- an MCP server whose tools are listed but which is not connected: a failed server, or tools loaded from the
  discovery cache. This tests the listed-versus-executed clause.

**Usage** (`usage.json`; each counter is kept separate; the coordinator session is not included):

| Job | Input (cached) | Output (reasoning) | Wall time |
| --- | ---: | ---: | --- |
| GPT-6, A/B | 361,404 (282,624) | 6,398 (4,652) | 3 min 28 s |
| GPT-6, B/A | 453,960 (366,592) | 6,756 (5,240) | 3 min 50 s |

| Agent | Calls | Input | Cache write | Cache read | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| `blind-adjudicator`, A/B | 8 | 20 | 124,928 | 621,147 | 64,422 |
| `blind-adjudicator`, B/A | 11 | 24 | 107,000 | 777,846 | 53,580 |

- The Claude judges made 2 and 1 server-side advisor calls. The advisor's own usage is not in these fields.
- `usage.json` also holds the usage of the void attempt 1 and of the 36 comparison runs. Its attempt-1 buckets
  include the round's source research (a `stack-researcher` agent, 73 API calls) and the GPT-6 runner probe.

**Limits:**
- The runs were headless, and each case ran on one model: K1-K3 on Opus 5.5, the host's default, and K4 on
  Sonnet 5. Interactive sessions and other effort levels were not tested.
- The K2 and K4 runs read client settings files under `bypassPermissions`, the host's default permission mode. The
  evidence keeps the file names, the K1-K3 answers' first 240 characters, each K4 answer's first sentence and the K4
  sentences that cite the plugin's commands. The K4 answer heads quote client configuration, so every published
  copy withholds them, including the packets as sent to the judges.
- The fallback remains untested.

**Anti-pattern log:** three dated rows in `docs/harness-defaults.md` record this round's proven mistakes:
- a model scope taken from the preregistration instead of each run's recorded model;
- a check that reported a mismatch and still exited 0;
- judge inputs published with answer text that quotes client configuration.

## Addendum (2026-09-28): round 3

The user's direction of 2026-09-28 started a third round: "please resolute cleanly with the sota repos
convergence,resolute all in your end and state the jobs that only beable to run by end,decide with your evidances and
sota repos evidances convergence". The round ran the comparison that the second round named for X9. It also took up
X5 again, with a new item, S1. For X5, this direction and the user's own user-level file supersede the plan's rule
that X5 is not edited; that file's top rule changed on 2026-09-28. X8 stays with the user. The evidence is in
[`x9-round3/`](../../evidence/artifacts/prompt-audit-20260927/x9-round3/) and
[`lane-a/`](../../evidence/artifacts/prompt-audit-20260927/lane-a/).

### X9: the comparison the second round named

**Preregistration.** `prereg-r3.json` was frozen before the first counted run, with its sha256 in
`prereg-r3.sha256`. It asks which lane text makes a Claude Code session claim a plugin or MCP server status that its
own run contradicts less often. It tests the two cases the second round named:
- **K5:** `workspace-guard`, a plugin with one `SessionStart` hook and nothing else. The hook writes one line to its
  state file and prints nothing, so nothing in the session names the plugin. The plugin is active in every run.
- **K6:** `ticket-tracker`, a stdio MCP server built on the official MCP Python SDK 2.2.0, with two tools. It answers
  `initialize` and `tools/list`, then ends itself 1 s after its first `tools/list`. It fails every tool call and
  refuses to start again, so its tools stay listed while it is not connected.

The decision rule was fixed before the runs:
1. The per-arm table goes into a blind judgment of the two texts, done as in round 2's attempt 2. A text is applied
   when all four judgments choose it. Four "neither" keep the line.
2. Otherwise the metrics decide, in this order: fewer wrong statuses, more correct statuses, fewer non-answers, fewer
   o200k tokens.

The current line ran as a control, not as a candidate.

**Runs.** 30 headless runs (2 cases × 3 texts × 5 runs) between 08:14:47 and 08:31:10Z.
- Client: Claude Code 2.1.283 on `claude-opus-5-5[1m]`. The model was pinned with `--model` and checked in each
  run's init event.
- Permission mode `bypassPermissions`, at most 10 turns.
- All 30 runs were included. The deterministic graders pass 33 labelled answers written before the first counted run.

| Text | Wrong status | Correct status (K5 + K6) | Non-answers | Named a command | Runs that read settings files | Cost (client's estimate) | o200k tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-6 lane's text | 0 | 10 (5 + 5) | 0 | 7 | 7 | $2.44 | 96 |
| Claude lane's text | 0 | 8 (3 + 5) | 0 | 8 | 5 | $1.99 | 72 |
| current line (control) | 0 | 10 (5 + 5) | 0 | 10 | 5 | $1.98 | 30 |

- The Claude lane's text missed twice on K5. Both runs answered "unconfirmed", as that text's fallback directs, so
  they count as neither correct nor wrong.
- On K6, every text gave the correct status in 5 of 5 runs. Every K6 run called the target tool, and every call
  failed, by design.
- No run called the Skill tool for a built-in command, and no run asked the user anything.

**Probes (uncounted, before freezing).** Four runs of the current line, recorded in `probe/facts.json`:
- **p1:** the fixture plugin and server loaded, and the server showed as connected with its two tools at init.
- **p3:** told to call no tool, the session found no text that named the plugin, although its hook ran.
- **p2:** Claude Code 2.1.283 started the stdio server again for a tool call after the server had ended. The MCP docs
  say stdio servers are not reconnected automatically (`mcp.md` L363). The fixture was then changed to refuse a
  restart.
- **p4:** with the changed fixture, both restart attempts were refused. The call's error was `MCP server
  "ticket-tracker" is not connected`.

**Changed after freezing, before any judge started.** Both files are published twice: a frozen copy with the
preregistered hash, and the copy as run.
- **`make_x9_round3.py`.** As first written, it withheld every K5 status sentence, because every K5 run read
  settings files.
  - It now withholds a status sentence only when the sentence quotes client configuration or names a settings file.
  - It still withholds an answer head whenever its run read settings files.
  - It adds, for each K5 run, a list of what that run's commands consulted. This list was observed, not
    preregistered.
- **`check_orders_r3.py`.** It was copied from round 2's revised check, but the copy gained a comma in its clause
  pattern. So it cut per-text clauses at commas and reported a false difference between the two orders.
  - The pattern is now round 2's again.
  - The check then reported the same evidence in both orders, and its negative control still exits 1.

The three texts match round 2's published arms byte for byte.

**Judgment.** It followed round 2's attempt-2 procedure:
- The root was a plain export of `ba1700ad`. None of its 7,935 files maps a text to a lane.
- The judges were two GPT-6 runner jobs (gpt-6-astra, effort max, read-only) and two `blind-adjudicator` agents, each
  family judging in both orders.
- `void_patterns_r3.py` was hashed before any return was read. No judgment had a voiding hit, and no judge opened a
  path outside its input, its packet and the root.
- `isolation-receipt.json` records the steps before dispatch. The GPT-6 judges' first start, at 08:37:36Z, failed
  because their work directory did not exist yet. They started at 08:37:41Z.

| Judgment | Choice | Confidence |
| --- | --- | ---: |
| GPT-6, A/B | GPT-6 lane's text | 0.91 |
| GPT-6, B/A | GPT-6 lane's text | 0.90 |
| Claude, A/B | GPT-6 lane's text | 0.60 |
| Claude, B/A | GPT-6 lane's text | 0.60 |

**Decision: applied under step 1 of the rule, unanimously.**
- `CLAUDE.md` lines 3-8 now hold the GPT-6 lane's text, quoted under Limitations and residuals. The file grows by 66
  o200k tokens: from 30 to 96 at `f508ffba`, and from 96 to 162 on `main` at `eb678281` and again at `fb14dedf`, whose
  `CLAUDE.md` also holds #453's `## Compact Instructions` section after these lines (`controls/token-counts-r3-*.txt`).
- Step 2 was not needed. It would have chosen the same text on correct statuses, 10 to 8.

The judges' reasons, in brief:
- **Both families:** the current line names commands the client refuses to run for the model (C1, C2). The two texts
  tie on wrong statuses, and the whole difference is in K5.
- **GPT-6:** the text's coverage and its separation of listed availability from successful execution, together with
  the measured K5 result, outweigh the other text's clearer fallback for unattended runs.
- **Claude:** the preregistered order ranks this text first, and its five K5 runs did what its "Use available
  read-only diagnostics first" asks. The gap is 2 runs of 5, in headless runs only.

**Limits:**
- The runs were headless, on one model (Opus 5.5), under `bypassPermissions`. The five K5 affirmations under the
  applied text followed Bash reads of the process command line and the fixture's hook state file. A session in
  another permission mode may need approval for those reads.
- Each text ran 5 times per case. The difference is the output of a decision rule, not a significance claim.
- The plugin was loaded with `--plugin-dir`, not installed from a marketplace. No MCP server's tools came from the
  discovery cache without a process. The fixture excludes a server that Claude Code restarts successfully (p2).
- Interactive sessions were not tested. That is the setting where a user can answer a request to run a command. Only
  the user can run those sessions, and they are this decision's overturn condition.

**Usage** (`usage.json`; each counter is kept separate; the coordinator session is not included):

| Job | Input (cached) | Output (reasoning) | Wall time |
| --- | ---: | ---: | --- |
| GPT-6, A/B | 493,758 (402,048) | 6,004 (4,254) | 3 min 28 s |
| GPT-6, B/A | 449,411 (349,696) | 6,526 (4,912) | 3 min 35 s |

| Agent or runs | Calls | Input | Cache write | Cache read | Output |
| --- | ---: | ---: | ---: | ---: | ---: |
| comparison, GPT-6 lane's text | 10 runs | 104 | 161,824 | 2,416,575 | 33,112 |
| comparison, Claude lane's text | 10 runs | 94 | 137,010 | 2,127,386 | 23,361 |
| comparison, current line | 10 runs | 86 | 144,559 | 1,913,987 | 22,170 |
| `blind-adjudicator`, A/B | 14 | 30 | 126,988 | 1,189,561 | 51,047 |
| `blind-adjudicator`, B/A | 14 | 30 | 125,278 | 1,145,903 | 55,650 |
| `stack-researcher` (sources for X9 and lane A) | 85 | 172 | 223,017 | 10,880,165 | 84,381 |

- The four probes cost $1.00 in total by the client's estimate: $0.36, $0.31, $0.28 and $0.05.
- The two judges and the researcher each made one server-side advisor call.

### Lane A: S1 and the top rule's three copies

Lane A judged four items from one frozen packet (`lane-a/round1/packet.md`, sha256 in `packet.sha256`) in two
independent lanes: GPT-6 (`gpt-6-astra`, effort max, read-only) through the packaged runner, and Claude through an
`evidence-reviewer` (`lane-a/round1/claude-usage.json`). The convergence rule was round 1's.

| Item | Location | Lane A (GPT-6 / Claude) | Later rounds | Result |
| --- | --- | --- | --- | --- |
| S1 | `AGENTS.md:37` | agree 0.97 / agree 0.80 | not needed | Applied here |
| X5b | `AGENTS.md:3` | agree 0.99 / agree 0.85 | not needed | Applied here |
| X5a | `examples/claude-native/CLAUDE.md:3` | amend / amend, two different texts | final round: agree / agree | Applied in #458 |
| X5c | `adoption/templates/codex.AGENTS.template.md:3` | reject / agree | final round: agree / amend; blind adjudication: 4 of 4 for the amendment | Applied in #458, with its pin |

- **S1.** The added sentence tells each session to build a PR description from `.github/pull_request_template.md`.
  The required `sota-sources` check fails a description without a non-empty `## SOTA sources` or `### SOTA sources`
  section. `lane-a/round1/facts-s1.json` records the live ruleset's required checks and #410, whose description had
  no such heading and whose check failed. Both lanes tested the check's heading rule (`validate.yml:335-336` at `f508ffba`, `:544-545` on
  this base) on variants of the heading. The GPT-6 lane reports running the workflow's script. The Claude lane reports replicating
  its two lines in Node, a synthetic check, not a CI run.
- **X5b.** The line is the operator's 2026-09-28 paragraph, byte for byte (`lane-a/round1/user-level-top-rule.txt`).
  Every obligation of the old line stays, verbatim. "Never self-write without a SOTA source" leaves the heading, while
  "With no SOTA source, stop and report instead of writing one" keeps its force. No test reads line 3; the
  consistency tests read the link on line 5 and the dispatch pointer. One co-change follows it:
  `docs/harness-defaults.md:7` restated the old heading ("research first, and never self-write without a SOTA
  source") and now restates the new one. No test reads that sentence.
- **X5a and X5c** change `lane:foundation` files, so they land in #458. Its decision record,
  [`2026-09-28-top-rule-templates.md`](2026-09-28-top-rule-templates.md), holds the adjudication attempts, the final
  round, the checks and the usage. Both templates keep "The installed client is also a source of truth; never
  self-write without a SOTA source", which the portable template's phrase check requires.
- **Tokens.** S1 and X5b take `AGENTS.md` from 2,401 to 2,484 o200k tokens (Measured results).
- **Usage.** Lane A's first round is in `lane-a/round1/claude-usage.json` and `gpt6.runner.json`. Later rounds are in
  their own directories and in #458's record.

### AN-13: a headless `/doctor prompt-audit` run

The 2026-09-28 community sweep left AN-13, the operator's `/doctor` prompt-audit run, open with the prompt-audit owner
([`2026-09-28-community-sweep.md`](2026-09-28-community-sweep.md)). It ran headless twice, on `main` at `eb678281`
with this pull request's and #458's changes applied. The facts of both runs are in
`evidence/artifacts/prompt-audit-20260927/an13/`, and its README gives each finding's disposition. The report text is
not published, because it quotes the user-level instruction file and names installed plugins and skills.

- **First run.** Exit 0, but the result was an interim note. After print mode's default 600 s wait, the client stopped
  the four background agents the skill had started. The dated row in `docs/harness-defaults.md` records the mistake.
- **Rerun.** It set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` and returned the full report with exit 0. The report has
  no high-confidence item, six medium findings, three low-confidence flags and four plugin findings. Nothing was
  edited from it:
  - **M1:** the broad trigger of the top rule at `AGENTS.md:3`. It follows the user-level paragraph that X5b copies,
    so it waits for the user's decision on that paragraph (M2).
  - **M3 and M4:** the other user-level findings are the user's decisions. M4, on a vendored skill, also needs a
    native before-and-after comparison.
  - **M5:** `blueprints/convergence-practice/application-delivery/AGENTS.md:15-18`, a single-family candidate. It
    needs a second-family lane before any edit.
  - **The rest:** the low-confidence and plugin findings are recorded flags.
- **Usage.** The client reported $22.74 for the first run and $13.97 for the rerun, both at list prices. Both usage
  blocks are in `an13-runs.json`, where they overlap and are never added.
