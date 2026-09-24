# Gap wave 2 — foundation/web-research (2026-09-23)

Unit `gap-wave-2` for layer `foundation/web-research`, worktree
`~/code/nas-wt-g2-web-research`, branch
`claude/g2-web-research-20260923`, base `origin/main` `41d39b3`.

Gap list source: crosswalk PR #85 at main `92bb279`
(`foundation/web-research` entry, 7 gaps, indices 0-6).

**Fix round (2026-09-23, ~01:45-02:00 UTC):** an independent Opus review of
the first pass found two `settled` outcomes that did not meet their own
next_check criteria, an isolation breach left in place, and several
wording/evidence-retention issues. This README and the affected receipts
were revised in place; see each receipt's `*_fix_round*` fields and the
"Fix round changes" section below for exactly what changed and why. Nothing
was deleted from the original `results` blocks — corrections and new
evidence were added alongside them.

## Outcomes (post-fix-round)

| gap | outcome | one-line note |
|---|---|---|
| 0 | **advanced** (was settled) | Both tools complete the shared loopback tasks; agent-browser fails a missing selector in 3ms vs Playwright's script-configured 2000ms timeout. Downgraded because tokens were never measured, "Playwright CLI" was actually a hand-written library script (caret-pinned, not exact), the two timings aren't like-for-like (launch time in/out of the clock differently), the 2000ms number is an artifact of the script's own timeout argument, and the two tools' `success` booleans used inconsistent meanings on the failing task. |
| 1 | settled | Reran the desktop-cli-workflows agent-browser fixture with `agent-browser --version` (0.38.1) and `uname -srm` in the same log; all steps exit 0. (Unchanged outcome; only a redaction disclosure was added — see below.) |
| 2 | advanced | SIGKILL'd the agent-browser daemon mid-session: it auto-relaunches but does not restore prior page state, and (per the original, non-retained observation) orphaned Chrome child processes. Added a retained-log Playwright SIGKILL control this round: 0 orphaned Chrome processes and a clean stateless rerun. Site sample corrected from a claimed 5/5 to 4/5 clear passes + 1 indeterminate (httpstat.us/200) per tool; noted the Wikipedia:Random URL is not a fixed sample. |
| 3 | deferred | Requires live, billed Tavily Search calls; this unit's hard rules forbid paid API usage. Owner: outside this unit's authorization. |
| 4 | deferred | Same reason as gap 3 (gold-labelled Tavily benchmark needs paid API calls). |
| 5 | advanced | Ran OpenResearch's official v0.2.9 musl release binary against real/gibberish discovery queries and valid/missing/malformed paper ids; found a discovery-quality *observation* (gibberish queries return unrelated real papers with no "no match" signal — softened from "defect"). **Fix round: `cargo test` was actually run** (rustup/cargo installed in this unit's own cache prefix, source cloned at tag v0.2.9, `cargo test --locked` → 914 passed, 0 failed, 3 ignored), correcting the earlier claim that not running it was "judged to exceed the time-box" (it had simply not been attempted). |
| 6 | **advanced** (was settled) | Crawl4AI 0.9.3 and Browser Use 0.13.10, explicitly re-pinned this round, both pass on the loopback fixture and example.com, each with a real quirk (Crawl4AI anti-bot false positive; Browser Use title accessor returning the URL). **Fix round: Browser Use now also fills `#name` and clicks `#greet`** (not just navigates), verified via a CDP readback of `#status`. Cua Driver and Firecrawl MCP were probed this round (installability + why full execution isn't possible/complete here) rather than left untouched; both remain functionally untested. |

## Fix round changes (by finding)

1. **Gap 6 downgraded settled → advanced.** Cua Driver and Firecrawl MCP
   remain untested (now with concrete infrastructure/timeout reasons
   recorded instead of a bare "out of scope"); Browser Use now performs
   fill+click, not just navigation; both installs were re-run with an
   explicit version pin (`crawl4ai==0.9.3`, `browser-use==0.13.10`).
2. **Gap 0 downgraded settled → advanced.** Tokens still aren't measured
   (the gap's own criterion); "Playwright CLI" was a hand-written script
   against the `playwright` library (caret range, not pinned); the
   840ms-vs-18ms/3ms-vs-2000ms numbers reflect launch-timing placement and
   an explicit `{ timeout: 2000 }}` in the script, not tool defaults; the
   `success` field meant different things for the two tools on the failing
   task. See `outcome_detail` and `limits` in the gap-0 receipt.
3. **Isolation breach fixed, not just flagged.** `~/.cache/ms-playwright`
   (658MB) and `~/.crawl4ai/` were confirmed (via `stat`) to have been
   created during this run's time window and were removed after the fix
   round's re-checks completed. They are no longer present on this host.
4. **Gap 2 site tally corrected.** httpstat.us/200 returning a "404 Not
   Found" page is now counted as indeterminate, not a pass, for both tools
   (4/5 + 1 indeterminate, not 5/5). The Wikipedia:Random URL is noted as
   not a fixed/repeatable sample. A retained-log Playwright SIGKILL control
   was added since a real kill test was possible even though Playwright has
   no daemon; the original agent-browser daemon-kill PIDs/counts are kept
   but flagged as having no retained raw log.
5. **Gap 5 wording and evidence fixed.** "Judged to exceed the time-box" is
   corrected to "not attempted" for the original pass; `cargo test` was
   then actually run this round (see gap 5 receipt `cargo_test_fix_round`).
   The "ambiguous paper id" case is now described accurately as a malformed
   string, not a true ambiguity case. "Defect" language for the gibberish
   query softened to "quality observation."
6. **Commands are now reproducible.** `scripts/` in this directory holds
   the actual driver scripts used (`pw_tasks.mjs`, `pw_sites.mjs`,
   `pw_kill_test.mjs`, `crawl4ai_test.py`, `browseruse_test.py`,
   `browseruse_fillclick_test.py`, `package.json`) and a reconstructed
   `agent_browser_tasks.sh` for gap 0 (the original ad hoc agent-browser
   commands were not saved verbatim; this is noted in that receipt's
   limits, not presented as a byte-identical replay). `raw/` holds the
   retained raw result/log files referenced by the receipts.
7. **Preregistration timestamps relabelled.** Gaps 0, 1, 2, 5 and 6 had
   `written_at` identical to `checked_at`; each now carries an explicit
   `preregistration.written_late: true` plus a note, rather than silently
   implying strict before-run drafting.
8. **Tavily-key sentence corrected.** The old sentence below calling
   `~/.config/typesafe/agent-lab.env` "the Tavily key" was wrong — it is
   documented in this project's `AGENTS.md` as `TYPESAFE_API_KEY`, a
   different, unrelated service scope, and this unit never opened the file
   to know its contents either way. See the corrected isolation note below
   and the gap-3 receipt, which already had the accurate wording.
9. **Gap 1 redaction disclosed.** The `full_log_excerpt`'s `file://` path
   was privacy-redacted from the raw log's real absolute path; this is now
   stated explicitly in the receipt rather than presented as a verbatim
   quote.

## Receipts

Each `<gap_index>-<slug>.json` file follows the required schema: `id`,
`gap_index`, `gap_text_sha256`, `preregistration`, `commands` (exact where
retained; reconstructed and labelled where not), `results`
(quoted/embedded excerpts), `outcome`, `evidence_class`, `limits`,
`checked_at`. `results.json` maps gap_index to outcome and receipt
filename. `scripts/` and `raw/` hold committed, reproducible driver
scripts and raw outputs referenced from the receipts.

All executed checks are `evidence_class: local_integration` (this host's
actual tool runs against local fixtures, public sites, and — for gap 5 —
an actual `cargo test` run from source) except gaps 3-4, which are
`source_review` (not executed, deferred) since no run occurred.

## Isolation notes

- All installs went into `~/.cache/gap-wave2-20260923/web-research/`
  (uv venvs for crawl4ai, browser-use and a cua-computer install
  feasibility probe; an isolated `PLAYWRIGHT_BROWSERS_PATH` for the ad hoc
  Playwright scripts; the OpenResearch release binary; and, added this fix
  round, a cache-prefix `RUSTUP_HOME`/`CARGO_HOME` rust toolchain plus a
  cloned OpenResearch source tree for `cargo test`).
- `crawl4ai-setup`'s own Playwright download went to the default
  `~/.cache/ms-playwright` (658MB) and its local sqlite state to
  `~/.crawl4ai/` during the original run — outside the required prefix.
  **Fix round:** confirmed via `stat` that both were created during this
  unit's run window (not present before it) and removed both directories;
  they are no longer on this host. This is recorded as a breach that was
  corrected, not as something that never happened.
- Used loopback ports (`127.0.0.1:8317` for a `python3 -m http.server`
  serving `fixtures/`), stopped after use, including the fix round's
  reuse of the same port for the Browser Use fill/click and Playwright
  kill-recovery re-checks.
- Used a namespaced agent-browser daemon (`--namespace gapwave2test` /
  `gapwave2sites`) for the crash-recovery and site-compat checks; all
  daemon and Chrome child processes it and the kill test spawned were
  closed/pkilled after use; verified no stray processes remain. The fix
  round's Playwright SIGKILL control (`pw_kill_test.mjs`) left one
  leftover node+Chromium tree running (because that ad hoc script omits
  `browser.close()`) after a non-killed rerun; this was noticed and
  manually cleaned up, and is called out in the gap-2 receipt as a script
  artifact, not a kill-recovery finding.
- rustup/cargo (fix round) were installed with `--no-modify-path` into a
  cache-prefix `RUSTUP_HOME`/`CARGO_HOME`, never added to the default
  `~/.cargo`, and never touched the shell's persistent `PATH`/profile.
- No broker/paper/gate/IBKR contact of any kind.
- No paid API calls. Tavily gaps remain deferred instead of run. Browser
  Use was exercised only via its low-level CDP event API (navigate, fill,
  click, one JS readback), never its LLM agent loop. Firecrawl MCP's
  keyless free-tier `--help` and one attempted (timed-out, non-functional)
  tool call used no credential. Cua Driver's package install pulled no
  paid dependency and no cloud key was supplied.
- No credential files were read. A key exists at
  `~/.config/typesafe/agent-lab.env` for a different, unrelated service
  scope (`TYPESAFE_API_KEY` per this project's `AGENTS.md`) and was not
  opened or used by this unit.
- Did not touch `catalogs/landscape/*.json`, `catalogs/sota-convergence/*`,
  `catalogs/us-equities/gates-*.json`, `docs/grand-catalog-handbook.md`, or
  `evidence/artifacts/layer-verdicts-*`.
- Did not reference `~/codex-ecosystem/state/model-comparison-20260922/`
  or `~/.config/model-cmp/`.

## Remaining risks / not fully closed

- Gap 0 and gap 2's tool comparisons remain narrow, single-run,
  loopback/small-sample observations; neither establishes a general
  "better tool" claim, and the fix round's corrections make that explicit
  rather than resolving it.
- Gap 5's discovery-quality finding is a single-probe observation, not a
  benchmark; `cargo test` passing does not qualify the live discovery/paper
  HTTP behavior (a unit-test suite would not be expected to cover that).
- Gap 6's Cua Driver and Firecrawl MCP remain functionally untested after
  this round; the reasons (VM/cloud-key requirement; a timed-out protocol
  call) are now concrete rather than "out of scope," but neither tool has
  been shown to work end to end from this unit's evidence.
- Gaps 3-4 (Tavily hit-rate and gold-labelled benchmark) are still
  deferred; they need an explicit paid-API authorization decision from the
  coordinator, not further work from this unit.

## Coordinator note (2026-09-23): captured package.json

The probe's `scripts/package.json` (a floating `playwright ^1.63.0`, with no lockfile) is retained as `scripts/package.json.captured`, bytes unchanged. It records the probe environment and is not a project the catalog installs, so it no longer needs an OSV exclusion (PR #132 review).
