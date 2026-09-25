# W1 sim track (2026-09-25): fresh side-by-side simulation roots

Three new, side-by-side tool roots were built next to the existing ones:
`adaptive-paper-r20260925`, `nautilus-2.0.0rc5-r20260925`, and
`lean-985ef30-r20260925`. Frozen-data backtests were re-run on the new Nautilus
and LEAN roots and compared against their existing recorded oracles; both
backtests exit 0 and match their oracle on every economic/behavioral field (see
the LEAN section below for the two hash fields that do not, and why). The
Nautilus/equity-replay backtest ran four times total across this track's rounds
(twice before, twice again after this round's venv-relink fix below); LEAN ran
twice. Per-component receipts are in
[`evidence/artifacts/native-rollout-20260925/sim/`](../evidence/artifacts/native-rollout-20260925/sim/).

This document was corrected across three fix rounds: round 1 (an earlier draft
claimed the LEAN backtest had run when it had not; see "LEAN build blocker and
its fix"); round 2 (found and fixed an undisclosed entanglement between the
two new Python roots and the live paper venv, see "Hardlink entanglement
incident and fix" below, and corrected several evidence gaps in the
per-component receipts); and round 3 (found that round 2's own fix for the
entanglement had an undisclosed side effect of its own -- a second live-venv
metadata change and an under-disclosed cache write, both in "Hardlink
entanglement incident and fix" below -- corrected the equity-replay economic
hash from an asserted-but-untested claim to a checked-in, reproducible script,
corrected round-attribution and evidentiary-overclaim issues in the LEAN
receipt, and retained raw acceptance-command output for the first time; see
"Scope and limitations" and "Acceptance commands" below). See each receipt in
`evidence/artifacts/native-rollout-20260925/sim/` for full detail.

## Environment builds

| Component | Method | Result |
| --- | --- | --- |
| `adaptive-paper-r20260925` | Read the live `adaptive-paper-20260921` venv's exact versions read-only (`uv pip freeze`), pinned them in `requirements.in`, generated a hash lock with `uv pip compile --generate-hashes`, then `uv venv` + `uv pip sync --require-hashes` | 21/21 packages identical to the live venv; lock sha256 `bfc47abf3406fdf8d1aec1dcffadf386251adb7e7ba67d9fb54ca611376e3c66` |
| `nautilus-2.0.0rc5-r20260925` | Replicated the exact recorded recipe in `evidence/receipts/native-nautilus-v2-20260920.json` (`uv venv` + `uv pip install --pre nautilus_trader==2.0.0rc5 numpy pandas`) | 5/5 packages identical; freeze output byte-identical to the recorded `freeze.stdout` sha256 |
| `lean-985ef30-r20260925` | Clone + checkout + recorded remediation, then `dotnet build` (see below) | Build succeeded on attempt 7 of this track's history (0 errors, 7730 warnings, 795 assemblies) |

Correction (round 2): the claim that every existing tool root was "read
from but never written to" does not hold at the filesystem-metadata level, and
round 2 found and disclosed two such cases in addition to the previously
disclosed `.git/index` touch (round 3 found a further nit in the first case
below and two further metadata/cache events round 2's own fix caused; see
"Scope and limitations"):

- Round 1's `git status --short` inside the existing
  `tools/lean-985ef30-remediation` root refreshed that root's `.git/index`
  mtime **and the containing `.git` directory entry's own mtime** (a
  stat-cache write, no tracked content changed; round 3 corrected "only
  .git/index" to include the directory entry, independently re-verified via
  `stat`); see
  `evidence/artifacts/native-rollout-20260925/sim/lean.json`'s
  `existing_roots_read_only_touch` for the detail.
- **New, disclosed round 2:** the original (pre-fix) builds of
  `adaptive-paper-r20260925` and `nautilus-2.0.0rc5-r20260925` used `uv`'s
  Linux default `--link-mode hardlink`, which hardlinked thousands of their
  site-packages files to the same cache-backed inodes already used by the
  **forbidden** live venv `tools/adaptive-paper-20260921`. This changed that
  live venv's own files' `nlink`/`ctime` (not their byte content). See
  "Hardlink entanglement incident and fix" below.
- **New, disclosed round 2:** LEAN attempt 7's (round 1) `dotnet build` (see below)
  ran with `${DOTNET_ROOT}` pointed at the existing, shared SDK root
  `tools/dotnet-equity10` (used by earlier tracks, SDK 10.0.401) and
  transiently created and removed an entry under that root's `metadata/`
  directory (confirmed by `stat`: `metadata/` mtime moved to 0.26s before
  attempt 7's build started, and the directory is empty again now). Same
  category as the `.git/index` case: a transient, non-content-modifying touch,
  now disclosed in `lean.json`'s `existing_roots_read_only_touch`.

Round 2 re-verified the live venv's package set still matches exactly
(21/21, byte-identical versions) and, separately, that its file **content** is
byte-for-byte unchanged (round 3 independently re-confirmed the same, plus a
second metadata event round 2's own fix caused -- see below and "Scope and
limitations").

### Hardlink entanglement incident and fix

Round 2 found that the original builds of `adaptive-paper-r20260925`
(21 packages) and `nautilus-2.0.0rc5-r20260925` (5 packages) did not pass `uv`
a `--link-mode`, so `uv` 0.12.17's Linux default (hardlink from the shared
`~/.cache/uv` content-addressed cache) made most of their installed files
hardlinks to the same inodes already used by the **forbidden** live paper venv
`tools/adaptive-paper-20260921` (directly for `adaptive-paper-r20260925`, and
for `nautilus-2.0.0rc5-r20260925` via all 5 packages it shares with the live
venv's package set -- `nautilus-trader`, `numpy`, `pandas`, `six`,
`python-dateutil` -- **round 3 correction:** round 2's own text here and in
`nautilus.json` named only the 4 indirect dependencies, omitting that
`nautilus-trader` itself is installed at the identical pinned version in both
places and so was hardlinked too; see `nautilus.json`'s
`root_cause_package_accounting_round3` for the corrected, independently
re-derived breakdown):

| Root | Shared-inode files (before fix) | Total site-packages files |
| --- | ---: | ---: |
| `adaptive-paper-r20260925` | 3631 | 3703 |
| `nautilus-2.0.0rc5-r20260925` | 2575 | 2593 |

This did not change the live venv's file **content** (verified: byte-for-byte
identical), but it did change that venv's files' `nlink`/`ctime` (a new
hardlink was created to the same inode), and, more importantly, it meant any
future in-place write to a file in either new root would have mutated the
identical bytes at the same path in the live paper-trading venv. No such write
occurred, but the risk was real until fixed.

**Fix:** both new roots were removed and rebuilt from the same, byte-identical
lock/install commands using `uv ... --link-mode copy` (copies file content
instead of hardlinking from the cache). No new wheel **download** was needed
(the local `uv` cache was already warm from the original builds), but this was
not a no-network, no-cache-write operation, contrary to what round 2 recorded
here: `uv pip sync` still revalidated PyPI's simple-index cache entry for every
locked package. After the rebuild: 0 shared inodes with the live venv for
either root; `installed-freeze.txt` regenerated and reverified byte-identical
to the original recorded hash for both roots; and the equity-replay backtest
(below) was re-run twice more against the fixed `nautilus-2.0.0rc5-r20260925`
and still reproduced the oracle's `account.csv` hashes exactly, confirming the
relink did not change runtime behavior. Full detail, including the exact
`os.lstat` inode measurements before and after, is in `adaptive-paper.json`
and `nautilus.json`'s `hardlink_entanglement_incident`.

**Round 3 correction (two gaps in round 2's own fix, found by review, both
independently reproduced with the checked-in scripts in this directory):**

1. **Round 2's own remediation changed the live venv's metadata a second
   time**, and round 2's "Live venv unchanged" acceptance check (`find
   -newermt`, mtime-only) could not see it. Removing a hardlink decrements
   `nlink` and updates `ctime` on the shared inode -- exactly the class of
   change the *original* hardlink-creation incident above already disclosed,
   but round 2's own `rm -rf`-and-rebuild caused a *second*, separate
   occurrence of it (opposite direction: `nlink` going back down) that round 2
   did not disclose. `python3 evidence/artifacts/native-rollout-20260925/sim/live_venv_ctime_report.py
   ${STACK_HOME}/adaptive-paper-20260921/lib/python3.12/site-packages
   2026-09-25T08:00:00+00:00 --exclude-substring __pycache__` (exit 0, output
   sha256 `fb3e9f68...`, retained in the private run dir) finds 3,631 of 3,696
   live-venv files with `ctime` at or after the fix window and 0 of those with
   `mtime` also changed -- i.e. `find -newermt` genuinely returns 0 matches
   here, which is why round 2's check passed while missing the change.
   Content is unaffected: `python3 evidence/artifacts/native-rollout-20260925/sim/verify_live_venv_content.py
   ${STACK_HOME}/adaptive-paper-20260921` (exit 0, output sha256 `d45b74b0...`)
   re-hashes every live-venv file against its own pip/uv `RECORD` sha256
   (written at the live venv's original 2026-09-19 install, predating this
   track): 3,678/3,678 verify, 0 mismatches, 0 missing. See
   `adaptive-paper.json`'s `round3_cache_and_metadata_correction` and
   `nautilus.json`'s `measured_after_fix.live_venv_second_metadata_change_round3`
   for the full, independently-reproduced detail (including why 1,056 of the
   3,631 files show a different final `ctime` than the other 2,575 -- two
   separate `rm -rf` events, 26 seconds apart, one per new root).
2. **The already-incurred write to the shared `~/.cache/uv`** (outside this
   track's declared allowed host paths) is not merely "unchanged by this fix"
   as round 2 said: this fix's own `uv pip sync --link-mode copy` rewrote 22
   cache entries (21 `simple-v25/pypi/<pkg>.rkyv` index files for
   `adaptive-paper-r20260925`'s 21 locked packages, plus the containing
   directory's own mtime) at 2026-09-25T09:10:26Z, independently reproduced
   this round from `~/.cache/uv`'s own file mtimes. The `nautilus-2.0.0rc5-r20260925`
   install 26 seconds later wrote 0 cache entries, so that root's
   no-additional-write note is unaffected. See "Scope and limitations" below
   for the combined, corrected disclosure.

## Equity replay (NautilusTrader 2.0.0rc5, new root)

Ran `blueprints/us-equities/engine-nautilus/equity-replay/launch.py` twice
(independent fresh processes) against the same retained authenticated AAPL
Alpaca acquisition already on disk (receipt `a59c6ed7...`); no new Alpaca
request was made. Both runs exited 0 and matched the frozen oracle in
`blueprints/us-equities/engine-nautilus/equity-replay/receipt.json` on every
field, verified directly from that file (not assumed from a paraphrase):

| Case | Filled orders | Closed positions | Fees | Realized PnL | Ending cash |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 10 | 5 | $0.00 | -$133.40 | $99,866.60 |
| Fee/slippage stress | 10 | 5 | $10.00 | -$144.40 | $99,855.60 |

`account.csv` was byte-identical between the two runs (and matches the
original 2026-09-21 receipt's own recorded hash exactly). `fills.csv`/
`positions.csv` differ only in generated order/position identities across
runs, exactly as the source blueprint documents; the identity-excluded economic
hash (fills/cash/position-PnL fields, read from the CSVs via `csv.DictReader`,
matching receipt.json's own documented encoding) was byte-identical between the
two runs and reproduces the original receipt's recorded `economic_repeat_sha256`
exactly. An earlier fix round's draft of this receipt computed that hash from
`reports.json` instead of the CSVs, which is economically equivalent but not
byte-identical to the oracle's own encoding, so it recorded a different hash
even though the results matched.

Correction (round 2): `equity-replay.json`'s `repository_checks` still
literally described the superseded (`reports.json`-based) computation, even
though the receipt's own `economic_hash_encoding` documented the corrected
(CSV-based) method used to produce the recorded values -- an internal
contradiction, now fixed by restating the CSV-based method in
`repository_checks` directly. Round 2 independently reverified the simpler,
fully-reproducible `account.csv` hashes from scratch (`sha256sum`, matches
exactly), and confirmed the recorded `economic_repeat_sha256` values are
internally consistent with `blueprints/us-equities/engine-nautilus/equity-replay/receipt.json`'s
own recorded value read directly from that file, but reported it did **not**
manage to reconstruct the exact byte-for-byte fill-dict field selection from
`economic_hash_encoding`'s prose alone -- several plausible 9-field
reconstructions were tried and, it said, did not reproduce the recorded hash.

**Round 3 correction: that negative claim was false, not merely incomplete.**
Round 2's own tried field set used fills.csv's `type` column (the order type,
e.g. `MARKET`/`LIMIT`) where the oracle's own receipt.json documents
`instrument_id` as the ninth field
(`economic_repeat_fields: instrument_id, side, quantity, filled_qty, avg_px,
commissions, status, ts_init, ts_last`, plus `account total` and
`position realized_pnl`). Using the oracle's own field list exactly reproduces
`economic_repeat_sha256` on the first try, for every retained run. This is now
a checked-in, reproducible script rather than an asserted-then-abandoned
attempt:
`python3 evidence/artifacts/native-rollout-20260925/sim/economic_hash_recompute.py <run-1..4 native dirs>`
(exit 0, output sha256 `d2215845...`, retained in the private run dir) --
8 of 8 case results (4 runs x {baseline, fee_slippage_stress}) match the
oracle's `8f81042a...`/`2b975634...` exactly. See
`equity-replay.json`'s `repository_checks` (current, corrected entry) and
`repository_checks_round2_economic_repeat_sha256_attempt_superseded` (round
2's own attempt, kept as historical record of the mistake, not as a current
claim).

`nautilus-2.0.0rc5-r20260925` was rebuilt in place by round 2 (see
"Hardlink entanglement incident and fix" above); two more independent runs
(`run-3`, `run-4`) were executed against the corrected root afterward and both
reproduced the same oracle-matching `account.csv` hashes. See
`evidence/artifacts/native-rollout-20260925/sim/equity-replay.json`.

## LEAN historical simulation (new root)

`lean-985ef30-r20260925` was cloned from `QuantConnect/Lean`, checked out at the
pinned commit, and had the recorded three-package-reference remediation applied
and verified (`git diff` matches the recorded patch exactly; locked NuGet
restore completed). The six-scenario historical-simulation replay then ran
twice (independent fresh processes) and matched the frozen oracle in
`blueprints/us-equities/historical-simulation/receipt.json` on every
economic/behavioral field -- `native_end_equity_usd`, fees, dividends, fill/
margin-call counts, and `max_observed_drawdown` to full decimal precision --
with 0 mismatches, for both runs. Of the 24 recorded artifact hashes, 12
(`events_sha256`, `audit_sha256` for all 6 cases) matched the oracle and each
other exactly; the other 12 (`summary_sha256`, `native_result_sha256`) did not,
because LEAN writes a wall-clock `StartTime`/`EndTime`, a `Used RAM (MB)`
measurement, and (per closed trade -- **0** to 4 per case depending on fill
count: `over_limit`'s single order is rejected unfilled, so it closes none;
corrected round 3 from "1 to 4", which silently excluded that case)
a generated `closedTrades[].id` GUID into those two files -- confirmed by a
full structural diff of both runs' results, which differ in nothing else at
all. Round 2 added the actual per-run, per-case output sha256 values for
all four hash types to `historical-simulation.json`'s `results_per_case`
(independently recomputed from the retained private-run-dir files); the prior
receipt recorded only pass/fail booleans with no hash value to bind them to.

Correction (round 2; the headline claim above is corrected round 3 -- see
"0 to 4 per case" above): the prior comparison was run-vs-run only for the
non-economic diff and omitted the oracle's own engine-identity fields. Compared
directly against the oracle's own retained input-hash manifest (byte-verified
as genuinely the oracle's file): the oracle mounted 1476 input files to this
round's 1467 -- 9 files that exist only in the oracle, all stale smoke-test
output left in its engine tree from an unrelated earlier run, not a data
difference (`Data/` is byte-identical). Of the 1467 files in common, 40 (20
`.dll` + 20 `.pdb`, all engine binaries) have different hashes, because
`lean-985ef30-r20260925` is a fresh build of the same pinned source and is not
byte-for-byte reproducible against the oracle's own compiled binaries -- never
claimed, but not previously stated either. The oracle's `engine.launcher_sha256`
(`e5bf96c8...`) likewise differs from this round's `QuantConnect.Lean.Launcher.dll`
(`cb3f1f67...`) for the same reason. Comparing the oracle's own retained
`HistoricalSimulationAlgorithm.json` against this round's `run-1` for the
`one_zero` case directly (not run-vs-run) finds exactly 5 differing leaves:
`StartTime`, `EndTime`, `Used RAM (MB)`, one `closedTrades[0].id`, and
`serverStatistics.'Up Time'` -- the last of which the prior draft did not
mention because it had only compared run-1 against run-2 (where it happens to
agree), not against the oracle. None of this changes the economic/behavioral
acceptance (still 0 mismatches on every field in the oracle table). See
`evidence/artifacts/native-rollout-20260925/sim/{lean,historical-simulation}.json`
for the full attempt log, diagnostic evidence, the frozen oracle verified
directly from the source file (24 recorded hashes, not the nine the task
brief's paraphrase named; corrected from the file itself), the corrected
oracle table transcribed from `receipt.json`'s exact values rather than the
README's rounded display table, and `historical-simulation.json`'s
`oracle_engine_identity_comparison` for the detail above.

### LEAN build blocker and its fix

Building the full solution reproducibly hung compiling `QuantConnect.Common`
across five independent attempts (attempts 1-4 from this track's initial build
session, attempt 5 from round 1's fix session -- **round attribution corrected
round 3**: this paragraph previously said "four from a prior fix round, one
from this one" and "until this round explicitly added and ruled it out" below,
worded as if attempt 5 belonged to whichever round last edited this doc; by
round 2's own rewrite of this section, that had become stale, since round 2
ran no LEAN build attempt at all -- see lean.json's `claim` and
`build_attempts_evidence_summary` for the corrected, timestamp-based
attribution), each testing a different mitigation: MSBuild node count, build-server/
`VBCSCompiler` persistence (`--disable-build-servers`, present in the existing
accepted recipe but absent from every hung attempt until round 1's attempt 5
added and ruled it out), a dedicated `TMPDIR`, disabled analyzers, and an
isolated single-project build with the terminal logger and stdin disabled.
Every hung attempt showed the identical signature: near-zero cgroup CPU time
over many minutes of wall time, dozens of threads sleeping on `futex_do_wait`
and exactly one running, no OOM, no cgroup CPU throttling, and no disk-wait
state -- indistinguishable from a deadlock by inspection alone. Precisely
measuring attempt 5's cgroup/proc CPU accounting (rather than judging by
inspection, as the prior four attempts had) still showed the same near-zero
signature, ruling out `--disable-build-servers` as the fix.

Setting `DOTNET_PROCESSOR_COUNT=2` -- which caps the .NET runtime's own
GC-heap and thread-pool sizing independent of any MSBuild flag -- resolved the
hang on both an isolated single-project probe (49.61s, 0 errors) and the full
solution (5:47.10, 0 errors, 7730 warnings -- matching
`blueprints/us-equities/engine/resolution.md`'s own recorded warning count for
this exact source-plus-remediation graph exactly, an independent cross-check).
The working hypothesis: this host's `dotnet`/MSBuild/`csc` processes default
their GC-heap/thread-pool sizing to the visible processor count (24), and under
concurrent load from other lanes sharing the same host (observed: another
lane's `vllm` process near 100% of one core, plus several unrelated busy-loop
processes, load average ~10.7 of 24 cores at the time), the resulting large
number of futex-synchronized threads could not get scheduled fairly enough to
make forward progress -- a near-live-lock under contention, not a hard
deadlock, OOM, or MSBuild/build-server mechanism. This is a single successful
reproduction path plus five independently reproduced hangs without it, not a
swept threshold; see `lean.json`'s limitations. **Round 3 caveat:** neither
attempt 6's nor attempt 7's retained wrapper log actually contains the string
`DOTNET_PROCESSOR_COUNT` (`grep -c`, independently re-run round 3, 0 matches
in both, and in attempt 5's log) -- the logs verify build success and its
specific warning/error/timing content, not the invoking environment. That
`DOTNET_PROCESSOR_COUNT=2` was the differentiating variable rests on the
operator's own command-construction record (consistent across attempts 6-7,
absent from 1-5), not on anything checkable from the log bytes; see
`lean.json`'s `root_cause_evidentiary_basis` for the full correction.

**Evidence-retention gap (still open):** attempts 1-4, and attempt 5's specific
cgroup/proc measurements quoted above, have **no retained wrapper log, output
file, or sha256 anywhere** -- confirmed by round 2 with `find` across
the private run directory and the new root, and independently re-confirmed
round 3 (`ls -la` of the private run dir's `lean-build-run-*` directories:
only `-5`, `-6`, `-7` exist). They are operator-observed prose
carried over from earlier rounds' sessions and are not independently
re-verifiable from anything this receipt or the repository retains. Round 2
hashed every artifact that **is** retained (attempts 5's 90-byte wrapper log,
6's 92,476-byte log, and 7's 7,330,462-byte log, plus an independent live
re-hash of `QuantConnect.Lean.Launcher.dll` from disk, matching `lean.json`
exactly) and made each attempt's evidentiary status explicit in
`lean.json`'s `build_attempts[].artifact_status` instead of leaving it
implicit. **Round 3 found one more instance of the same issue one level up**:
`root_cause`, `diagnostic_evidence`, and `root_cause_evidentiary_basis`
themselves still stated the exclusions and attempt-5's figures as fact without
this same caveat inline (the caveat lived only in this doc and in
`build_attempts[].artifact_status`), and `root_cause_evidentiary_basis`
additionally claimed attempts 6/7's retained logs proved
`DOTNET_PROCESSOR_COUNT=2` was set, which `grep -c DOTNET_PROCESSOR_COUNT`
against all three retained logs disproves (0 matches in each, round 3). Both
are now fixed inline in `lean.json`. No fresh reproduction was attempted to
backfill attempts 1-4's missing measurements, in round 2 or round 3, because
doing so risked the working `lean-985ef30-r20260925` root that the
historical-simulation backtest above depends on, and would only add a new
data point rather than retroactively produce artifacts for the specific
historical attempts the finding is about; see `lean.json`'s
`build_attempts_evidence_summary` for the full reasoning, extended round 3.
This is the one review finding no fix round has fully closed.

## Scope and limitations

- Frozen/cached data only; no Alpaca or other market-data API call was made by
  this track. No paper or live order was placed. No systemd unit was modified
  (re-verified round 3: fresh `systemctl --user show` for all 5 FAILED units
  is byte-identical to the pre-round snapshot). No existing tool root's
  tracked/versioned content was modified, but these transient or
  metadata-only touches of existing/forbidden roots are now disclosed rather
  than assumed away:
  - the read-only `.git/index` **and containing `.git` directory entry**
    touch in `tools/lean-985ef30-remediation` (round 1; round 3 corrected
    "only .git/index" to include the directory entry itself, independently
    re-verified via `stat`);
  - the `tools/dotnet-equity10` `metadata/` transient create/delete from LEAN
    attempt 7 (round 1);
  - the live-venv `nlink`/`ctime` change from the original hardlink
    entanglement incident (round 2's build); **and, undisclosed until round
    3: a second, separate live-venv `nlink`/`ctime` change from round 2's own
    fix for that incident** (removing the hardlinks it had just created also
    changes the shared inode's metadata) -- see "Hardlink entanglement
    incident and fix" above for the independently-reproduced counts.
  None of these changed tracked file content (RECORD-hash-reverified for the
  live venv, round 3).
  - **Also newly disclosed, round 3:** `/tmp/claude-1000-adaptive-paper-requirements.{lock,in}.bak`
    -- round 2's relink fix moved `requirements.lock`/`requirements.in` out to
    `/tmp` (outside this track's allowed host paths) and back during the
    rebuild, per `venv-relink-fix/adaptive-paper.log`; both files were moved
    back before the sync ran and no `.bak` residue remains (confirmed:
    neither path exists on disk now). Transient, not a current write, but not
    previously mentioned in this document.
  - **Withdrawn, round 3:** the two live-venv `__pycache__` `.pyc` files
    (`pandas/core/reshape/reshape.cpython-312.pyc`,
    `pandas/core/methods/to_dict.cpython-312.pyc`, 05:14:03Z/05:23:02Z) were
    previously attributed to "an unidentified concurrent process/lane, not
    this track". Round 3 found both timestamps fall inside round 1's own
    session window (commit 1fac653b at 05:03:46Z to commit 23429d9a at
    05:50:40Z), specifically the ~26-minute gap before LEAN attempt 5 started
    (05:29:28Z) -- exactly when round 1's own equity-replay oracle-hash
    exploration most plausibly ran (per `23429d9a`'s commit message and
    `equity-replay.json`'s `repository_checks` history: DataFrame `to_dict()`/
    reshape-family calls are consistent with that kind of CSV exploration).
    "Not this track" is unsupported by this timing and is withdrawn; the
    exact command remains unidentified (no interactive-shell history is
    retained for round 1's session), so this is an open item, not a resolved
    one either way. See `adaptive-paper.json`'s `pyc_attribution_correction`.
- These are environment-construction and frozen-backtest reproduction checks,
  not a new strategy, profitability claim, or broker acceptance.
- Raw run logs and private argv/paths stay under the private run directory;
  this document and the linked receipts report sanitized aggregates and hashes
  only, with `${STACK_HOME}`/`${PRIVATE_STATE}`/`${PRIVATE_RUN_DIR}` placeholders
  for host paths.
- `dotnet` invocations in round 1 used the isolated `DOTNET_CLI_HOME`/
  `NUGET_PACKAGES`/`TMPDIR` under the new root plus
  `DOTNET_CLI_TELEMETRY_OPTOUT=1`/`DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1`/
  `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`/`DOTNET_NOLOGO=1` throughout,
  matching `blueprints/us-equities/engine/resolution.md`'s recipe; an earlier
  session's bare `dotnet --help`/`--version` probes (before this env was
  applied) already wrote first-use sentinels and a dev certificate to the
  shared `~/.dotnet` profile and are not undone by this track (outside its
  allowed host paths to remove; recorded as a deviation).
- The default user `uv` cache `~/.cache/uv` (outside this track's declared
  allowed host paths) was written by the original `adaptive-paper-r20260925`
  build **and again by round 2's own `--link-mode copy` fix** -- round 3
  correction: round 2's fix was not the no-write operation its own text
  claimed. `uv pip sync` revalidated the PyPI simple-index cache entry for
  every one of the 21 locked packages even though no wheel re-download was
  needed, rewriting 22 entries (21 `.rkyv` files plus the containing
  directory's mtime) at 2026-09-25T09:10:26Z, independently reproduced round 3
  from `~/.cache/uv`'s own file mtimes. `UV_CACHE_DIR` was not pointed at an
  allowed path for either build (that would not remove the already-incurred
  write, only avoid a marginal addition, at the cost of a full re-download).
  Recorded as an incomplete-coverage scope note, not resolved.

## Acceptance commands

Round 2's table below is kept as the historical record of what it ran; round
2's own text claimed these commands' raw output "closes the previously-flagged
verification gap", but the private run dir held nothing retained for any of
them (validate.py, the systemctl comparison, the containerized suite, or the
direct re-run) -- review caught this twice. Separately, the round-3 review's
own recheck reported the systemctl comparison and the live-venv freeze/
content comparison as "not run", reasoning that `sim.md` names no unit(s)
and gives no literal freeze command -- **that reasoning does not hold**:
`sim.md`'s "Literal acceptance re-run" paragraph names all 5 units and the
exact `systemctl --user show ...` and `uv pip freeze ...` command lines
verbatim (read directly from the file, not assumed). **Round 3 re-ran every
literal acceptance command in that paragraph raw via `rtk proxy`, this time
with output actually redirected into
`${PRIVATE_RUN_DIR}/sim/round3-acceptance-recheck/` and hashed**, including
both commands the review's recheck had skipped.

| Command | Exit | Result | Raw output retained (round 3) |
| --- | --- | --- | --- |
| `rtk proxy python3 scripts/validate.py` | 0 (after this round's manifest re-pin; listed in deviations) | `{"components": 69, "hashed_files": 5346, "profiles": 4, "receipts": 145, "status": "passed"}` (3 new files this round -- `economic_hash_recompute.py`, `live_venv_ctime_report.py`, `verify_live_venv_content.py` -- registered in `manifests/evidence.json`'s `files[]`; the 5 modified receipts' `sha256`/`bytes` also re-pinned; only these 8 entries touched, listed in deviations) | `round3-acceptance-recheck/validate.txt` (sha256 `2c0ff66e...`) |
| `systemctl --user show adaptive-paper-rung1x-20260923-ladder2.service ibkr-paper-post-20260923.service incentive-forward@1330.service mover-daily-scan-0925.service mover-rth-trial-20260924.service -p Id,ActiveState,SubState,Result,ExecMainStartTimestamp,ExecMainExitTimestamp` (`sim.md`'s literal command) | 0 | Byte-identical to `${PRIVATE_RUN_DIR}/../snapshot/failed-units.txt` for all 5 units, once the snapshot's own trailing blank line is normalized (`diff` on the first 34 lines: exit 0; both hash to `c6948953...`) | `round3-acceptance-recheck/systemctl-show.txt` |
| `rtk proxy uv --no-config pip freeze --python tools/adaptive-paper-20260921/bin/python` (`sim.md`'s literal live-venv freeze check) | 0 | sha256 `5233376f1e6264f3617ed20159521261f4d74753f562355cc6db1b5ecdd1f013` -- byte-identical to `adaptive-paper.json`'s own `installed-freeze.txt` hash for the new root; package set unaffected | `round3-acceptance-recheck/live-venv-freeze.txt` |
| Live venv per-file sha256 vs. "a pre-run manifest" (`sim.md`'s literal wording) | n/a | No pre-run manifest of the live venv's per-file hashes exists anywhere in the repo or private state (confirmed by search); round 2's own `a9970b71...` aggregate was a mid-track checkpoint, not a pre-run one, and is not independently reproducible (round 3 tried 64 plausible encodings, none matched). Substituted the best available equivalent that genuinely predates this track: pip/uv's own per-file `RECORD` sha256, written at the live venv's 2026-09-19 install -- `verify_live_venv_content.py`: 3678/3678 verify, 0 mismatches, 0 missing | `round3-acceptance-recheck/live-venv-record-verify.txt` |
| Live venv metadata (ctime-aware, replacing round 2's mtime-only `find -newermt`) | n/a (report) | 3,631 of 3,696 files ctime-changed since the fix window, 0 of those mtime-changed -- round 2's `nlink`/`ctime` disclosure gap (major finding) is real; see "Hardlink entanglement incident and fix" above | `round3-acceptance-recheck/live-venv-ctime-report.txt` |
| `python3 economic_hash_recompute.py` against all 4 retained equity-replay runs | 0 | 8/8 case results match the oracle's `economic_repeat_sha256` -- round 2's "did not reproduce" claim is corrected, not merely softened | `round3-acceptance-recheck/economic-hash-recompute.txt` |
| `ecosystem-bounded-run python3 -m unittest discover -s tests` (containerized, `ECOSYSTEM_JOB_SECONDS=1800`) | 1 | 4720 tests, **9** failures (all in `test_adoption_bootstrap_macos.py`/`test_adoption_launchd.py`), 516 skipped, 0 errors, 273.012s -- same signature as round 2's and the review's own recheck figures. Round 3 ran this twice: the first run (while this round's own file edits were still landing) transiently showed a **10th** failure, `tests.test_catalog_freshness_propose.RebuildExplorerSubprocessTests.test_general_publication_validator_passes_after_the_run` -- self-diagnosed as an artifact of editing the manifest while this containerized run was reading the same live worktree (its own traceback showed exactly the pre-re-pin `scripts/validate.py` errors this round had already produced and then fixed); re-run alone on the stable, edited-complete worktree, it passes (exit 0, `round3-acceptance-recheck/unittest-freshness-propose-retest.txt`). The second, clean run (no concurrent edits, retained below) reproduces exactly the known 9-failure signature and nothing else. | `round3-acceptance-recheck/unittest-full-containerized-final.txt` (sha256 `7d5e364d...`); first (transient 10-failure) run kept for the record at `round3-acceptance-recheck/unittest-full-containerized.txt` (sha256 `343c45e0...`) |
| `rtk proxy python3 -m unittest tests.test_adoption_bootstrap_macos tests.test_adoption_launchd -v` (direct, no containment) | 0 | 186 tests, **0 failures** (skipped=3), 50.883s -- confirms the 9 containerized failures are a containment/signal-timing artifact (`_common.md`'s documented carve-out), not a regression; independently re-run and retained round 3, same result as round 2's figures | `round3-acceptance-recheck/unittest-direct.txt` |
| Base-vs-HEAD comparison for the failing modules | n/a | `git diff 57fb6d89 HEAD -- tests/` is empty: this track has never changed a test or source file under `tests/` (only JSON receipts, this doc, the manifest re-pin, and the 3 new evidence scripts below `evidence/artifacts/`), so the direct-run result above applies identically to both base and HEAD by construction; a separate checkout was not needed |  |

**Round 3 correction of round 2's original closing claim** (round 2's text
said its acceptance commands' raw output "closes the previously-flagged
verification gap ... for everything within this track's ability to check
locally"): that was already inaccurate for the reason given above (no raw
output was actually retained), and separately the round-3 review's recheck
believed two of `sim.md`'s literal commands -- the systemctl comparison and
the live-venv freeze/content comparison -- were unspecified; both are in fact
literal, copy-pasteable commands in `sim.md`'s "Literal acceptance re-run"
paragraph (see the freeze and systemctl rows above), and round 3 ran both.
Separately, `validate.py` and the two
unittest invocations are **not** "exactly" `validate`'s own commands: the
required `validate` job in `.github/workflows/validate.yml` runs about 20
steps, of which this track ran 2 (`scripts/validate.py`, `python3 -m
unittest`); `validate-macos` requires an actual macOS runner (out of reach on
this Linux WSL2 worktree, correctly noted) but most of `validate`'s other
steps are plain Linux-runnable Python (`host_receipts.py validate`,
`validate_catalogs.py`, `validate_foundation.py`, `landscape.py`,
`audit_reports.py --check`, `validate_convergence.py --all-recorded`,
`build_verdicts.py --check`, `component_matrix.py --check`,
`new_host_grand_list.py --check`, `gap_crosswalk.py build --check`,
`gap_wave_ledger.py ... --check`, `build_ecosystem.py --check`, `node --test`)
that this track neither ran nor recorded. Running all of them is a
repository-wide verification campaign outside this track's allowed paths and
this fix round's scope (most parse or check evidence far outside
`evidence/artifacts/native-rollout-20260925/sim/`), so it is not attempted
here; listed as a known, disclosed gap rather than claimed closed. The
required CI contexts themselves (`validate`, `validate-macos`, `secret-scan`,
`token-report`, `dependency-review`, `osv-scanner`, `verdict-review-gate`,
CodeQL) still have not run against this branch in an actual PR; that remains
the coordinator's/integrator's step, not something a local worktree can
produce.
