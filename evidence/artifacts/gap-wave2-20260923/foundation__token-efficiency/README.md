# Gap wave 2 — foundation / token-efficiency (2026-09-23)

Unit: gap-wave-2, layer `foundation/token-efficiency`. Worktree
`$HOME/code/nas-wt-g2-token-efficiency`, branch
`claude/g2-token-efficiency-20260923`, base `origin/main 41d39b3`.

Six gaps carried forward from the crosswalk (PR #85, main 92bb279). Per-gap
receipts are in this directory; `results.json` maps `gap_index` to outcome and
receipt path. **Fix round (2026-09-23, second pass):** an independent Opus
review found seven major and several minor issues in the first pass (a
misread result, an undisclosed live-credential read, an out-of-order
preregistration, imprecise/unsafe commands, and three skipped `next_check`
runs recorded as "advanced" or "not_settled" without being attempted). All
affected receipts were corrected, some with partial re-runs; see each receipt's
`fix_round_disclosure` field for what changed and why.

Outcomes below are generated into `results.json` from the receipts by
`tools/gen_results.py`. They reflect the 2026-09-23 reconciliation round (see
"Reconciliation"). Cited raw outputs are under `raw/`, indexed with source and
committed sha256 in `raw/raw-manifest.json`, which also lists outputs that were
never retained.

| gap_index | text (short) | outcome | note |
| --- | --- | --- | --- |
| 0 | matched on/off native-task baseline | deferred | needs several repeated fresh-session Claude on/off runs measured with `ccusage claude session --json`; blocked by the wave's reservation of the shared Claude account (one bounded call allowed). Only the counter's basic function was checked; raw output in `raw/gap0/` |
| 1 | Headroom real-session interception | not_settled | the interception half was runnable (one ephemeral `codex exec -c openai_base_url=...` call through a loopback proxy with an isolated workspace) and was not run; the recorded credential blocker is contradicted by Headroom 0.38.0 source |
| 2 | RTK/lite gateway preview semantic checks | advanced | rtk (OmniRoute 3.8.50 internal engine, default parameters) still drops required values while reporting `validation.valid=true` on two new fixtures. Not yet done: lite on eligible content, the prior record's other modes, the "RTK 0.49.0" clause |
| 3 | ccusage attempt/child coverage | not_settled | no retried child, no raw-JSONL recompute; the sonnet difference between child-usage.mjs and ccusage is confounded by a still-running workflow read sequentially |
| 4 | Context Mode paired-session causality | not_settled | Claude arms blocked by the account reservation; Codex arms had no named blocker and were not attempted |
| 5 | Headroom pin 0.37.0 stale vs 0.38.0 | not_settled | only the 0.38.0 arm was run, on a deleted fixture with no retained output; the 0.37.0 arm was executable (installs present) and not run. The gap keeps its 2026-09-22 advanced_by_receipt status |

## Scope notes

- No broker/paper/IBKR/gate work touched (none of these six gaps required it).
- No SPY/LEAN parity or dividend-sim work touched (not applicable to this layer's gap list).
- Did not modify `catalogs/**/*.json`, `docs/grand-catalog-handbook.md`, or
  `evidence/artifacts/layer-verdicts-*` per the hard rules.
- Isolation, fix round: gap 2's corrected re-run set `HOME` (not just `DATA_DIR`)
  to a scratch directory before starting the isolated OmniRoute instance, so by
  construction the default data dir resolved under the scratch HOME. The
  unchanged mtime of `~/.omniroute/.env` shows only that it was not written; the
  startup log that would show which `.env` files were read was not retained. The first pass's isolated instance had read that live file's
  `STORAGE_ENCRYPTION_KEY` and made outbound Arena/OpenRouter syncs; this is
  disclosed in gap 2's receipt as a defect in the superseded run, not repeated.
  The throwaway dashboard password used in the corrected run is not recorded
  anywhere in this repository. The stale, live-key-encrypted scratch data
  directory left over from the first pass was deleted.
- Gap 1's receipt discloses that an earlier `headroom doctor` call in this
  unit's first pass did contact the live `~/.headroom` store for an online
  update check (visible via `update_check.json`'s mtime); this fix round's own
  commands for gap 1 only ran `stat` on that store (a read).
- The fix round recorded no write to live `~/.headroom` or `~/.omniroute`, a
  memory/Qdrant store, or a systemd unit. The only write probe was file mtimes,
  which detect writes but not reads, and the stat outputs were not saved. The
  first pass's read of the live `~/.omniroute/.env` is disclosed above. No
  broker or paid-API credential was read. Gap 1 checked only that
  `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are unset in the shell; that output
  was not saved, and it does not show that no such credential exists elsewhere.
- Did not open or reference the sealed model-comparison audit paths named in
  the hard rules for this run.

## Reconciliation (2026-09-23)

The latest independent review returned `fix_required` with eight findings. No
new check was run in this round. Claims were matched to evidence already on
disk: file mtimes, commit times, the two ccusage snapshots in the
coordinator scratchpad, the wf_f4b0c001-b52 journal, and the installed
Headroom 0.38.0 source.

1. **Gap 1 deferral contradicted by Headroom source (major): supported.**
   `headroom/proxy/auth_policy.py` treats `codex-cli/` and `claude-code/`
   user agents as subscription clients and OAuth bearer tokens as
   `AuthMode.OAUTH`. `headroom/cli/wrap.py:3046-3051` documents routing
   ChatGPT-plan Codex by overriding `openai_base_url`. `cli/proxy.py:1658-1659`
   shows client routing with no key. I re-read all three from the installed
   tree. Changes: deferred became **not_settled** with the real reason (a
   runnable one-call interception check was not run). The paraphrased
   `proxy_help` is replaced by source citations and marked not retained. The
   "Claude excluded" claim is corrected, since one bounded call was allowed.
2. **Gap 3 next_check not executed and confounded (major): supported and
   confirmed.** Snapshot a (`raw/gap3/...snapshot-a.json`, 01:56:16Z) shows
   wf_f4b0c001-b52 lastActivity 3 s before the snapshot. Snapshot b
   (`raw/gap0/...snapshot-b.json`, 02:02:06Z) shows its sonnet counters still
   growing. The journal went from 27 to 37 lines, last written at 02:23:55Z.
   Changes: advanced became **not_settled**. The "not perfectly reliable"
   conclusion is withdrawn. The fix-round disclosure that claimed the
   next_check was executed is corrected. The ccusage output is committed. The
   child-usage.mjs output was never saved, and that is disclosed.
3. **Gap 2 "settled" overstated; lite misreported; preregistration misstates
   the original (major): supported.** The prior record
   (`evidence/receipts/foundation-native-20260920.json` preview_comparisons)
   has one 447-token fixture with lite failing (447->444). The rerun's lite
   call was a 46-token no-op. Changes: settled became **advanced**, scoped to
   rtk. Lite is reported as not comparable. A per-check table against the
   prior record is added. The unexercised "RTK 0.49.0" clause is named. The
   preregistration text is kept, with a `correction` field added.
4. **Gap 2 isolation evidence weaker than claimed (minor): supported.** The
   scratch tree is empty and no log is committed. Changes: the server-log
   quote is marked not retained. The mtime claim is narrowed to "not
   written". The unrecorded startup sync jobs are disclosed.
5. **Gap 5 missing 0.37.0 arm, placeholder generator, deleted fixture,
   timestamp attribution (minor): supported.** Both 0.37.0 install paths
   exist. Changes: advanced became **not_settled**, because this wave closed no
   open clause and its outputs are not retained. The generator is marked
   unrecorded. The update_check.json mtime (01:44:37Z) is attributed to the
   first pass, before commit 0699663 at 01:49:24Z, consistent with receipt 1.
6. **Gap 4 self-contradiction and Codex half (minor): supported.** Changes:
   the placeholder grep "command" is removed. Deferred became **not_settled**,
   because the Codex arm had no named blocker.
7. **Gap 0 checked_at predates the fix round; editorial text in a JSON
   excerpt (minor): supported, and worse than reported.** The excerpt mixed
   values from snapshots a and b. Changes: the excerpt is replaced with
   snapshot b's values, snapshot b is committed, and `checked_at` is null with
   bounds. The time-box is withdrawn as a deferral reason. The account
   reservation remains the blocker, so gap 0 stays **deferred**.
8. **Host username in the Claude project slug (minor): supported.** Changes:
   host paths are now written as `$HOME` and the slug as `$HOME_SLUG` in the
   receipts, README and raw files. UUID session ids in the raw ccusage files
   are pseudonymized as `session-<sha256 prefix>`. The source sha256 of each
   raw file is kept in `raw/raw-manifest.json`.

Timestamps (all receipts). First-pass commit 0699663 (01:49:24Z) carries
first-pass times up to 01:57Z. Fix-round commit f796901 (02:06:06Z) carries
fix-round times up to 02:22Z. Both sets are impossible, so every `written_at`
and `checked_at` is now null, with a note giving the bounds that surviving
files and commits support. Gap 2's preregistration cannot be shown to precede
its results; the raw responses were in the worktree by 01:59:09Z.


### Reconciliation, pass 2 (2026-09-23)

The review's eight findings were written against fix-round commit f796901
and were addressed in commit 1903ade (above). This pass re-read every receipt
against the findings and made no new check. For each finding, the state
after 1903ade and any further change:

1. Gap 1 (major): the outcome is not_settled with the real reason. The
   paraphrased `proxy_help` is withdrawn. No further change.
2. Gap 3 (major): the outcome is not_settled with the confound stated. The
   ccusage command's note wrongly claimed it "verifies the exact next_check
   command form"; that was gap 0's next_check. The note now says the committed
   `raw/gap3/` file is the unfiltered output, so the recorded `jq` pipe is not
   the exact command that saved it.
3. Gap 2 "settled" (major): the outcome is advanced, scoped to rtk. Lite is
   reported as not comparable. No further change.
4. Gap 2 isolation (minor): the last command's parenthetical still said the
   unchanged mtime confirmed "the live store was never opened". It is narrowed
   to "not written", because mtime cannot detect a read.
5. Gap 5 (minor): not_settled. No further change.
6. Gap 4 (minor): not_settled. The placeholder command is removed. No further
   change.
7. Gap 0 (minor): deferred, with `checked_at` null. The only blocker is the
   wave brief's reservation of the shared Claude account. No isolated
   alternative makes it executable: a temp HOME or a loopback instance does
   not create a second account, and a Codex-only arm is not measured by
   `ccusage claude session`. The brief text is not on disk in this repository
   or in the coordinator scratchpad. The only other trace is the review quoting
   the same wave rule ("one bounded single-call check is allowed").
8. Host username (minor): an `rg` for the host username over this layer directory returns
   nothing. Each committed raw file matches its `raw/raw-manifest.json`
   sha256.

The README scope notes also said that "gap 1 confirms no such credential is
present in this environment". Gap 1 only saw that two environment variables
were unset in one shell, and did not save that output. The note is narrowed
to that. `results.json` is regenerated by `tools/gen_results.py`, and the
outcomes are unchanged from 1903ade.
