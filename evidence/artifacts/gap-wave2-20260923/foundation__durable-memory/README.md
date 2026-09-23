# Gap wave 2: foundation/durable-memory (2026-09-23)

Unit: gap-wave-2, layer `foundation/durable-memory`. Crosswalk index at main
`92bb279` (crosswalk PR #85). Worktree
`/home/example/code/nas-wt-g2-durable-memory`, branch
`claude/g2-durable-memory-20260923`, base `origin/main` `41d39b3`.

11 gaps were assigned for this layer (indices 0, 1, 2, 5, 6, 8, 9, 11, 12, 13,
14). Each gap has a receipt next to this file named `<gap_index>-<slug>.json`.
`results.json` maps each gap index to its outcome and receipt. The table below
and `results.json` are both generated from the receipts by `raw/gen_results.py`
(run it from the repository root; a rerun must leave both files unchanged).

**Note on paths:** `scripts/validate.py` rejects this host's real per-user home
directory. Receipt command strings therefore show it as `/home/example` or
`$HOME`, and the raw outputs under `raw/` use `$HOME`. They are not
byte-for-byte the strings that ran. `raw/INDEX.json` lists every
transformation and the sha256 of each source before redaction.

## Operator escalation: live-store isolation breach (unresolved)

During gap 11's first-pass check (2026-09-23T01:13:46Z) this unit broke its
isolation rule and changed the live ai-memory store under
`$HOME/.local/share/ai-memory`. Every subcommand after `init` reached the live
service on `127.0.0.1:49374` instead of the disposable `--data-dir`. As a
result:

- `write-page` added a synthetic page (`scratch/ttl-probe.md`, workspace
  `disposable-ws`, project `disposable-proj`) to the live store (pages 120 ->
  121).
- `forget-sweep` ran on it without `--dry-run`. It evicted nothing.
- `backup` wrote a 130 MiB tarball of live content into the cache directory,
  which was later shredded.
- `compact --confirm` ran a VACUUM on the live 223.7 MiB database while the
  service was running (15.8 MiB reclaimed).
- `purge-project --confirm` logically deleted the synthetic project.

What is still in the live store, from the raw output: the full page body,
including the synthetic marker token, is committed in the live wiki's git
history (`bb0b205`), and the purge commit `4be633d` does not remove it. Whether
the token is still present in the live database file has not been measured.
The earlier "13 matches" counted lines containing the path substring
`ttl-probe`, not the token (see Reconciliation, finding 4).

This branch cannot fix any of this, and nobody has authorized rewriting live
history. **The store operator (the user) has to decide** whether to rewrite
or gc the live wiki history and whether to compact the database file again.
Do not merge this branch as if the unit had followed its isolation rules.
The fix round's read-only follow-ups also sent `ai-memory status` CLI calls to
the live service (transcript calls [7], [13] and [50]). These break the rule
that every ai-memory call targets an isolated server. They recorded no change,
but they are listed here as rule breaks.

## Outcomes

<!-- outcome-table:start (generated from receipts by gen_results.py) -->
| gap | outcome | evidence_class | receipt |
|---|---|---|---|
| 0 | deferred | source_review | `0-no-benchmark-run.json` |
| 1 | not_settled | source_review | `1-auto-improve-not-rerun.json` |
| 2 | not_settled | source_review | `2-restore-reindex-source-review.json` |
| 5 | covered_elsewhere | source_review | `5-stale-pin-covered-elsewhere.json` |
| 6 | deferred | source_review | `6-token-savings-deferred.json` |
| 8 | not_settled | source_review | `8-autonomous-learning-not-rerun.json` |
| 9 | deferred | source_review | `9-matched-comparison-not-run.json` |
| 11 | not_settled | local_integration | `11-ttl-forget-sweep-live-store-incident.json` |
| 12 | not_settled | local_integration | `12-live-client-rebind-deferred.json` |
| 13 | covered_elsewhere | source_review | `13-stale-pin-covered-elsewhere.json` |
| 14 | advanced | local_integration | `14-network-bytes-not-measured.json` |
<!-- outcome-table:end -->

- **0, 6, 9 deferred.** 0: building a labelled recall/MRR set and a second
  memory server does not fit the assignment's 20-minute time-box. 6: paired
  native Claude sessions are more than the single bounded Claude call allowed
  while the account is reserved. 9 is the composite of 0 and 6.
- **1, 2, 8, 11, 12 not_settled.** Receipts 1, 2 and 8 did not run their
  checks, and the blockers they named do not hold (see Reconciliation). 11 ran
  on the live store by accident and learned nothing new. 12(b) caught no torn
  state, and 12(a) did not run.
- **14 advanced.** A disposable instance ran with the embedding opt-out and no
  network device. That setup cannot detect an attempted egress, and the
  separate byte-delta or connect-trace arm has not been run.
- **5, 13 covered_elsewhere.** Routed by the assignment to the
  sota-refresh-20260923 units. The cited directory is missing from this
  branch. It exists on origin/main `5dcf451`
  (`evidence/artifacts/sota-refresh-20260923/pins-mem/ai-memory.json`).

## Raw outputs

`raw/` holds the unit workers' tool results, copied verbatim from their
session transcripts, plus the two probe scripts. Only the redactions listed in
`raw/INDEX.json` were applied. `INDEX.json` gives, for each file, the
transcript call indices, call and result timestamps, the gaps that cite it, the
sha256 of the source before redaction and the sha256 of the committed file.
The disposable data dirs and the gap-11 backup were deleted at the time
(transcript calls [13], [29], [51] and first-pass [16]), so no database or
backup file is left to commit. The first-pass home-wide `find` for
sota-refresh was RTK-filtered, and its recall hash does not resolve to that
output, so it is not used.

## Reconciliation (2026-09-23, third pass, no new checks)

The second independent review returned `fix_required` with seven findings.
This pass ran no check and made no ai-memory call. Every change is an edit
that makes a claim match files already on disk. The on-disk sources are the
fix-round and first-pass transcripts (committed as `raw/`), the probe scripts,
this branch's files and a read of origin/main. Timestamps in every receipt
now come from transcript tool-call times. The old shared value
`2026-09-23T01:20:00Z` came after the first-pass commit (01:19:05Z) and matched
no recorded event. Every preregistration is now labelled `late: true`,
because the transcripts contain no preregistration written before its run.
Receipts 6 and 9 ran no command, so their `checked_at` is `null` with a note.

1. **Gap 14 overclaimed settled (major): supported, now `advanced`.** The raw
   run covers only the `unshare -rn` arm. In a namespace that has only `lo`,
   a connect() to a non-loopback address fails before any byte is counted, so
   the probe could not have detected the attempted model download that caused
   the gap. The receipt now states that detection limit. The 3299 bytes on
   `lo` cover `status`, `write-page` and a 0.5 s sleep, not a single
   write-page call; the text is corrected. Two things remain: a byte delta or
   a `strace -f -e trace=connect` trace with a network device present, and
   the full synthetic comparison sequence.
2. **Fix-round timestamps (major): supported.** Gap 14 was `late: false` at
   01:20:00Z. It is now `written_at` 01:30:40Z (the transcript's Write of the
   receipt), `late: true`, and `checked_at` 01:23:12Z (the run). For gap 12,
   the claim that half (b) was "preregistered and executed together" is
   withdrawn: the text was written at 01:30:10Z, after the 01:27:41Z run. The
   same correction is applied to every other receipt.
3. **Gap 2's blocker is invalid (major): supported, deferred -> `not_settled`.**
   The next_check's own `unshare --pid --fork --mount-proc` gives the process
   guard a private process table. The fix round had already run
   `unshare -rn` successfully. The origin/main peer receipt
   `sota-refresh-20260923/pins-mem/ai-memory.json` records restore refusing
   with `pids: [365]` (the live service) when run without a PID namespace.
   That is the failure a PID namespace removes. The receipt's command is also
   corrected to the `sed` read that actually ran; `grep -n` was not run.
   README item 4 of the old follow-ups, which asked the coordinator to decide,
   is dropped because the next_check already answers it.
4. **Gap 11 residue grep, outcome and TTL claim (major): supported, advanced
   -> `not_settled`.** (a) `grep -c ttl-probe` counted lines holding the path
   substring, so "token present 13 times" is withdrawn and the token's
   presence in the live database file is recorded as unmeasured. (b) The
   receipt's own criteria required a disposable store, and nothing new about
   TTL or erasure was learned. One detail of the review is not supported by
   the raw output: the backup was grepped before it was shredded. The
   first-pass `zgrep -al` printed the tarball path, so the token was in it.
   That only shows the backup was taken while the page was live, so the
   outcome does not change. (c) "TTL not exercisable" is corrected: the CLI
   lacks `--expires-at`, but MCP/HTTP `memory_write_page` accepts `expires_at`
   (this project's AGENTS.md says to set it).
5. **Live-store breach needs escalation (major): supported.** It cannot be
   fixed in this branch. It is now the first section of this README and is
   repeated in the handoff limits for the coordinator to raise with the
   user. See "Operator escalation" above.
6. **Gap 1 command[1] output (minor): partly supported.** The recorded
   command (`serve --help | grep -i llm`) was not the command that ran. It is
   replaced with the real command (`env | grep ...; ai-memory --help | grep
   ...; ai-memory auto-improve --help`) and its real output. The claim that
   the two serve log lines did not come from gap 14's check is not supported:
   they are in gap 14's raw `serve.log` tail
   (`raw/fix-round-gap14-netns-probe.txt`). They also match
   `memory-lifecycle-probe-20260921/ai-server-1.log` word for word. The
   receipt now cites the gap-14 raw output and records the match.
7. **Unrecorded claims in gaps 12 and 14 (minor): mostly supported.** For
   gap 12(b), "every attempt" becomes one data-producing attempt (call [27]).
   Calls [19] and [20] produced no output, and call [26] was a single-write
   smoke test. "Post-write snapshot" becomes "source dir read directly". Gap
   14's before/after live status reads did happen (calls [7] and [13]), and
   they are now recorded with raw output and marked as rule breaks. One part
   of the finding is not supported: the claim that AI_MEMORY_SERVER_URL was
   set only on the serve process. Both runs `export`ed it inside the namespace
   shell (raw script and call [27]); only the receipts' paraphrased commands
   suggested otherwise, and they are corrected. The gap-12(a) deferral is
   weak, as the finding says: a temporary `--mcp-config` with
   `--strict-mcp-config` needs no `~/.config` edit, and one bounded Claude call
   was allowed. Gap 12 stays `not_settled`.

This pass also made three changes that the review did not ask for:

- **Gaps 1 and 8: deferred -> `not_settled`.** Their blocker ("no LLM
  provider is configured on this host; configuring one needs credentials or a
  paid API") is contradicted by the live status output in
  `raw/first-pass-gap11-ttl-probe-incident.txt`: `llm: codex/gpt-5.6-luna ok`.
  That is a native Codex provider, and the assignment allowed Codex-account
  calls. Only the worker's shell lacked `AI_MEMORY_LLM_PROVIDER`.
- **Gaps 5 and 13.** "Does not exist on this host" is corrected to "missing
  from this branch; present on origin/main `5dcf451`". The recorded command
  is corrected to the find that actually ran.
- **Gap 11 command[11].** It merged `sessions: 179` from call [7] into a
  later status excerpt. It now quotes calls [13] and [50] separately.

### Fourth pass (2026-09-23, no new checks)

The coordinator re-sent the second review's seven findings. All seven were
already addressed by the third pass above; this pass re-checked that against
the files on disk and changed only traceability:

- The generator `gen_results.py` had stayed in the session scratchpad. It is
  now committed as `raw/gen_results.py`. Rerunning it left `results.json` and
  the outcome table byte-identical, and every receipt's `outcome` equals its
  `results.json` entry.
- Every `raw/INDEX.json` committed sha256 matches its file. Every receipt's
  preregistration is `late: true` with a `written_at` taken from a transcript
  time; receipts 6 and 9 keep `checked_at: null` with a note.
- No outcome changed. No ai-memory call was made in this pass.

## Remaining work

1. Operator decision on the live-store residue (see Operator escalation).
2. Gap 14: a byte delta or connect trace with a network device present, plus
   the full synthetic comparison.
3. Gap 2: restore and reindex under
   `unshare -rn --pid --fork --mount-proc`, on a disposable dir with its own
   port.
4. Gap 11: the whole next_check on a disposable instance, with `expires_at`
   set through MCP/HTTP and the token grepped with
   `grep -a -o TOKEN | wc -l` across wiki, wiki/.git, sqlite, WAL and backup.
5. Gap 12: (a) one bounded `claude -p --mcp-config <temp>
   --strict-mcp-config` call against a restored instance; (b) snapshots
   taken while writes are in flight.
6. Gaps 1 and 8: a disposable auto-improve run with the native codex
   provider, plus independent grading. This needs a coordinator decision on
   whether a read-only copy of the live store is allowed; a variant using
   synthetic sessions needs none.
7. Gaps 0, 6 and 9 stay deferred for the reasons in their receipts.

## Store end state (coordinator note, 2026-09-23)

The probe's write-page and purge-project (wiki commits bb0b205 and 4be633d) recreated the disposable-ws scope manifest in the live store. Peer session finalize-llm-harness-catalogs removed it after a backup (wiki commit fb584c3) and kept the probe commits in history as an audit trail. The history includes the synthetic token XYZZY-ttl-erasure-1790126026, which is not a secret. It is left in history deliberately, and rewriting the memory store's git history is the user's decision. The manifest has since reappeared through lifecycle-only session entries (wiki commits 0cf8d87 and b560174), from a session whose working directory maps to that workspace. This is reported to the user as a store-hygiene item. The receipts' limits already disclose that the fix round's `ai-memory status` calls reached the live service.

The synthetic erasure-probe marker value is redacted in the committed raw captures `raw/fix-round-gap11-posthoc-residue.txt` and `raw/first-pass-gap11-ttl-probe-incident.txt` (it matched the generic-api-key secret-scan rule). It is a synthetic marker, not a credential; sha256 of the original value: 0483a9795cafe64e686d839325cbbdb012b526c47a71aa9f2cc6b2e87751f871.

## Coordinator note (2026-09-23): privacy sweep

The catalog rule is: "Evidence belongs in compact sanitized receipts; no raw conversations, tokens, personal paths or machine-specific active client configuration." The PR #132 review found the host username, Claude transcript and plugin-data locations, worktree names and the active session environment in conversation-derived raw files, and the username in several command outputs.

Host username replaced by `<user>` (`-home-<name>-` project slugs become `-home-<user>-`). Raw command outputs are otherwise unchanged; metadata files also had the text changes listed under "Pins updated":

- `raw/INDEX.json`: 2 replacement(s), sha256 `152917ac72c0...` -> `1eb0de1a893b...`
- `raw/fix-round-final-live-status.txt`: 1 replacement(s), sha256 `d9ae981d1b4e...` -> `359553face27...`
- `raw/fix-round-gap12b-attempts.txt`: 1 replacement(s), sha256 `584e2884bbde...` -> `2b03437ee567...`

Pins updated: `raw/INDEX.json` (`sha256` and `bytes` of the two status captures, and its `transformations` text; its own two occurrences are redacted too). `source_sha256_before_redaction` is unchanged.

## Coordinator note (2026-09-23): privacy sweep, second pass

Moved out of the repository: every remaining conversation-derived record (transcript extracts and transcript tool-call/tool-result captures). Each file is kept byte for byte in host-local, owner-only storage (directories 0700, files 0600) outside the repository and is not published. Every reference keeps its relative name and sha256 and is marked not published with a `retention` note; the receipts' own published fields (`cmd`, `exit`, `output_excerpt`, and `output_sha256` where present) remain the published support:

- `raw/first-pass-gap11-ttl-probe-incident.txt`: sha256 `8b92cf37e9dc...`, 12063 bytes
- `raw/fix-round-live-status-before-gap14.txt`: sha256 `6ac97f4ee171...`, 4346 bytes
- `raw/fix-round-gap14-netns-probe.txt`: sha256 `9bb03430c78e...`, 11545 bytes
- `raw/fix-round-gap1-env-and-help.txt`: sha256 `21ab5e333071...`, 1484 bytes
- `raw/fix-round-gap5-13-find.txt`: sha256 `e53c7624eff9...`, 444 bytes
- `raw/fix-round-gap11-posthoc-residue.txt`: sha256 `b0b1381a37ea...`, 3064 bytes
- `raw/fix-round-gap12b-attempts.txt`: sha256 `2b03437ee567...`, 15578 bytes
- `raw/fix-round-gap0-gap8-grep.txt`: sha256 `b1e1213162d2...`, 2125 bytes
- `raw/fix-round-final-live-status.txt`: sha256 `359553face27...`, 1161 bytes

Pins updated: `raw/INDEX.json` (each moved entry is marked `published: false`), and every receipt command whose `raw` names a moved capture (`raw_published: false`, `raw_retention`). Two `INDEX.json` pins were already stale before this sweep: `raw/first-pass-gap11-ttl-probe-incident.txt` and `raw/fix-round-gap11-posthoc-residue.txt` had been changed by the secret-scan marker redaction after `INDEX.json` was written. Their `sha256` and `bytes` now match the retained files.
