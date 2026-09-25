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

This document was corrected during earlier fix rounds (an earlier draft claimed
the LEAN backtest had run when it had not; see "LEAN build blocker and its fix")
and during this fix round, which found and fixed an undisclosed entanglement
between the two new Python roots and the live paper venv (see "Hardlink
entanglement incident and fix" below) and corrected several evidence gaps in the
per-component receipts (listed inline below; see each receipt for full detail).

## Environment builds

| Component | Method | Result |
| --- | --- | --- |
| `adaptive-paper-r20260925` | Read the live `adaptive-paper-20260921` venv's exact versions read-only (`uv pip freeze`), pinned them in `requirements.in`, generated a hash lock with `uv pip compile --generate-hashes`, then `uv venv` + `uv pip sync --require-hashes` | 21/21 packages identical to the live venv; lock sha256 `bfc47abf3406fdf8d1aec1dcffadf386251adb7e7ba67d9fb54ca611376e3c66` |
| `nautilus-2.0.0rc5-r20260925` | Replicated the exact recorded recipe in `evidence/receipts/native-nautilus-v2-20260920.json` (`uv venv` + `uv pip install --pre nautilus_trader==2.0.0rc5 numpy pandas`) | 5/5 packages identical; freeze output byte-identical to the recorded `freeze.stdout` sha256 |
| `lean-985ef30-r20260925` | Clone + checkout + recorded remediation, then `dotnet build` (see below) | Build succeeded on attempt 7 of this track's history (0 errors, 7730 warnings, 795 assemblies) |

Correction (this fix round): the claim that every existing tool root was "read
from but never written to" does not hold at the filesystem-metadata level, and
this round found and disclosed two such cases in addition to the previously
disclosed `.git/index` touch:

- An earlier fix round's `git status --short` inside the existing
  `tools/lean-985ef30-remediation` root refreshed only that root's `.git/index`
  mtime (a stat-cache write, no tracked content changed); see
  `evidence/artifacts/native-rollout-20260925/sim/lean.json`'s
  `existing_roots_read_only_touch` for the detail.
- **New, disclosed this round:** the original (pre-fix) builds of
  `adaptive-paper-r20260925` and `nautilus-2.0.0rc5-r20260925` used `uv`'s
  Linux default `--link-mode hardlink`, which hardlinked thousands of their
  site-packages files to the same cache-backed inodes already used by the
  **forbidden** live venv `tools/adaptive-paper-20260921`. This changed that
  live venv's own files' `nlink`/`ctime` (not their byte content). See
  "Hardlink entanglement incident and fix" below.
- **New, disclosed this round:** LEAN attempt 7's `dotnet build` (see below)
  ran with `${DOTNET_ROOT}` pointed at the existing, shared SDK root
  `tools/dotnet-equity10` (used by earlier tracks, SDK 10.0.401) and
  transiently created and removed an entry under that root's `metadata/`
  directory (confirmed by `stat`: `metadata/` mtime moved to 0.26s before
  attempt 7's build started, and the directory is empty again now). Same
  category as the `.git/index` case: a transient, non-content-modifying touch,
  now disclosed in `lean.json`'s `existing_roots_read_only_touch`.

This round re-verified the live venv's package set still matches exactly
(21/21, byte-identical versions) and, separately, that its file **content** is
byte-for-byte unchanged (only the hardlinking incident's metadata was affected,
and that has now been eliminated going forward -- see below).

### Hardlink entanglement incident and fix

This fix round found that the original builds of `adaptive-paper-r20260925`
(21 packages) and `nautilus-2.0.0rc5-r20260925` (5 packages) did not pass `uv`
a `--link-mode`, so `uv` 0.12.17's Linux default (hardlink from the shared
`~/.cache/uv` content-addressed cache) made most of their installed files
hardlinks to the same inodes already used by the **forbidden** live paper venv
`tools/adaptive-paper-20260921` (directly for `adaptive-paper-r20260925`, and
indirectly for `nautilus-2.0.0rc5-r20260925` via the `numpy`/`pandas`/`six`/
`python-dateutil` versions the two package sets share):

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
instead of hardlinking from the cache). No new PyPI network access was needed
(the local `uv` cache was already warm from the original builds). After the
rebuild: 0 shared inodes with the live venv for either root; `installed-freeze.txt`
regenerated and reverified byte-identical to the original recorded hash for
both roots; and the equity-replay backtest (below) was re-run twice more
against the fixed `nautilus-2.0.0rc5-r20260925` and still reproduced the
oracle's `account.csv` hashes exactly, confirming the relink did not change
runtime behavior. Full detail, including the exact `os.lstat` inode
measurements before and after, is in `adaptive-paper.json` and `nautilus.json`'s
`hardlink_entanglement_incident`. The already-incurred write to the shared
`~/.cache/uv` (outside this track's declared allowed host paths) is unchanged
by this fix and remains a disclosed, not-undone scope note (see "Scope and
limitations").

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

Correction (this fix round): `equity-replay.json`'s `repository_checks` still
literally described the superseded (`reports.json`-based) computation, even
though the receipt's own `economic_hash_encoding` documented the corrected
(CSV-based) method used to produce the recorded values -- an internal
contradiction, now fixed by restating the CSV-based method in
`repository_checks` directly. This round independently reverified the simpler,
fully-reproducible `account.csv` hashes from scratch (`sha256sum`, matches
exactly), and confirmed the recorded `economic_repeat_sha256` values are
internally consistent with `blueprints/us-equities/engine-nautilus/equity-replay/receipt.json`'s
own recorded value read directly from that file, but did **not** manage to
reconstruct the exact byte-for-byte fill-dict field selection from
`economic_hash_encoding`'s prose alone within this round's effort -- several
plausible 9-field reconstructions were tried and did not reproduce the
recorded hash. This residual gap (the originating script is not checked into
the repository) is recorded as a limitation in `repository_checks`, not
papered over.

`nautilus-2.0.0rc5-r20260925` was rebuilt in place by this fix round (see
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
measurement, and (per closed trade -- 1 to 4 per case, depending on fill count)
a generated `closedTrades[].id` GUID into those two files -- confirmed by a
full structural diff of both runs' results, which differ in nothing else at
all. This round added the actual per-run, per-case output sha256 values for
all four hash types to `historical-simulation.json`'s `results_per_case`
(independently recomputed from the retained private-run-dir files); the prior
receipt recorded only pass/fail booleans with no hash value to bind them to.

Correction (this fix round): the prior comparison was run-vs-run only for the
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
across five independent attempts (four from a prior fix round, one from this
one), each testing a different mitigation: MSBuild node count, build-server/
`VBCSCompiler` persistence (`--disable-build-servers`, present in the existing
accepted recipe but absent from every hung attempt until this round explicitly
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
swept threshold; see `lean.json`'s limitations.

**Evidence-retention gap (still open):** attempts 1-4, and attempt 5's specific
cgroup/proc measurements quoted above, have **no retained wrapper log, output
file, or sha256 anywhere** -- confirmed by this fix round with `find` across
the private run directory and the new root. They are operator-observed prose
carried over from earlier rounds' sessions and are not independently
re-verifiable from anything this receipt or the repository retains. This round
hashed every artifact that **is** retained (attempts 5's 90-byte wrapper log,
6's 92,476-byte log, and 7's 7,330,462-byte log, plus an independent live
re-hash of `QuantConnect.Lean.Launcher.dll` from disk, matching `lean.json`
exactly) and made each attempt's evidentiary status explicit in
`lean.json`'s `build_attempts[].artifact_status` instead of leaving it
implicit. It did not attempt a fresh reproduction to backfill attempts 1-4's
missing measurements, because doing so risked the working
`lean-985ef30-r20260925` root that the historical-simulation backtest above
depends on, and would only add a new data point rather than retroactively
produce artifacts for the specific historical attempts the finding is about;
see `lean.json`'s `build_attempts_evidence_summary` for the full reasoning.
This is the one review finding this fix round did not fully close.

## Scope and limitations

- Frozen/cached data only; no Alpaca or other market-data API call was made by
  this track. No paper or live order was placed. No systemd unit was modified.
  No existing tool root's tracked/versioned content was modified, but three
  transient or metadata-only touches of existing/forbidden roots are now
  disclosed rather than assumed away: the read-only `.git/index` touch in
  `tools/lean-985ef30-remediation` (earlier round), the `tools/dotnet-equity10`
  `metadata/` transient create/delete from LEAN attempt 7 (this round), and the
  live-venv `nlink`/`ctime` change from the hardlink entanglement incident
  (this round; see above). None changed tracked file content.
- These are environment-construction and frozen-backtest reproduction checks,
  not a new strategy, profitability claim, or broker acceptance.
- Raw run logs and private argv/paths stay under the private run directory;
  this document and the linked receipts report sanitized aggregates and hashes
  only, with `${STACK_HOME}`/`${PRIVATE_STATE}`/`${PRIVATE_RUN_DIR}` placeholders
  for host paths.
- `dotnet` invocations in this round used the isolated `DOTNET_CLI_HOME`/
  `NUGET_PACKAGES`/`TMPDIR` under the new root plus
  `DOTNET_CLI_TELEMETRY_OPTOUT=1`/`DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1`/
  `DOTNET_GENERATE_ASPNET_CERTIFICATE=false`/`DOTNET_NOLOGO=1` throughout,
  matching `blueprints/us-equities/engine/resolution.md`'s recipe; an earlier
  fix round's bare `dotnet --help`/`--version` probes (before this env was
  applied) already wrote first-use sentinels and a dev certificate to the
  shared `~/.dotnet` profile and are not undone by this round (outside this
  track's allowed host paths to remove; recorded as a deviation).
- The default user `uv` cache `~/.cache/uv` (outside this track's declared
  allowed host paths) was written by the original `adaptive-paper-r20260925`
  build and is unchanged/not un-written by this round's `--link-mode copy` fix,
  which intentionally reused the already-warm cache rather than pointing
  `UV_CACHE_DIR` at an allowed path (that would not remove the already-incurred
  write, only avoid a marginal addition, at the cost of a full re-download).
  Recorded as an incomplete-coverage scope note, not resolved.

## Acceptance commands (this fix round, raw via `rtk proxy`)

| Command | Exit | Result |
| --- | --- | --- |
| `rtk proxy python3 scripts/validate.py` | 0 | `{"components": 69, "hashed_files": 5343, "profiles": 4, "receipts": 145, "status": "passed"}` after this round's mechanical re-pin of the 5 changed receipt files' `sha256`/`bytes` in `manifests/evidence.json` (only those 5 entries touched; listed in deviations) |
| `systemctl --user show <unit> --property=Result,ExecMainStartTimestamp,ExecMainExitTimestamp,Id,ActiveState,SubState` for all 5 FAILED units | n/a | Byte-identical to `${PRIVATE_RUN_DIR}/../snapshot/failed-units.txt` (the workflow harness's pre-round snapshot) for every unit (`adaptive-paper-rung1x-20260923-ladder2.service`, `ibkr-paper-post-20260923.service`, `incentive-forward@1330.service`, `mover-daily-scan-0925.service`, `mover-rth-trial-20260924.service`) |
| Live venv unchanged | n/a | Content: 0 shared-inode risk remains (see hardlink fix above); `find tools/adaptive-paper-20260921 -newermt <09:00 UTC, before this round's rebuild window>` returns 0 files, i.e. nothing under the live venv changed during or after this round. Two `__pycache__` `.pyc` files (`pandas/core/reshape/reshape.cpython-312.pyc`, `pandas/core/methods/to_dict.cpython-312.pyc`) appeared at 05:14:03Z/05:23:02Z, before this round's 09:10Z rebuild window and from an unidentified concurrent process/lane, not this track; excluded from, and noted alongside, a fresh aggregate content hash of the live venv's site-packages (excluding `__pycache__`): 3696 files, `a9970b71e486990b36ef43d5537dcc04a897ed195354cc0179d8204d5f2b9020` (path+sha256 per file, sorted, sha256 of the concatenation) -- recorded as a checkpoint for a future round to diff against; no pre-session baseline existed to compare it to. |
| `ecosystem-bounded-run python3 -m unittest discover -s tests` (containerized, `ECOSYSTEM_JOB_SECONDS=1800`) | 1 | 4720 tests, 9 failures (all in `test_adoption_bootstrap_macos.py`/`test_adoption_launchd.py`), 516 skipped, 0 errors |
| `rtk proxy python3 -m unittest tests.test_adoption_bootstrap_macos tests.test_adoption_launchd -v` (direct, no containment) | 0 | 186 tests, **0 failures** (skipped=3) -- confirms the 9 containerized failures are a containment/signal-timing artifact (`_common.md`'s documented carve-out), not a regression |
| Base-vs-HEAD comparison for the failing modules | n/a | `git diff 57fb6d89 HEAD -- tests/` is empty: this track changed no test or source file (only the 5 JSON receipts, this doc, and the manifest re-pin), so the direct-run result above applies identically to both base and HEAD by construction; a separate checkout was not needed |

This closes the previously-flagged verification gap (acceptance commands not run/recorded) for everything within this track's ability to check locally. The `validate`/`validate-macos`/`secret-scan` GitHub Actions CI job names referenced by that finding are not reproducible in this Linux WSL2 worktree (no macOS runner available); `scripts/validate.py` and the direct unittest re-run above are this environment's equivalent, and `rtk proxy python3 scripts/validate.py`/the unittest commands are exactly `validate`'s and the suite's own commands.
