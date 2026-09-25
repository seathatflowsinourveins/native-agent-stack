# W1 sim track (2026-09-25): fresh side-by-side simulation roots

Three new, side-by-side tool roots were built next to the existing ones (none of
which were modified): `adaptive-paper-r20260925`, `nautilus-2.0.0rc5-r20260925`,
and `lean-985ef30-r20260925`. Frozen-data backtests were re-run twice each on the
new Nautilus and LEAN roots and compared against their existing recorded oracles;
both backtests now exit 0 and match their oracle on every economic/behavioral
field (see the LEAN section below for the two hash fields that do not, and why).
Per-component receipts are in [`evidence/artifacts/native-rollout-20260925/sim/`](../evidence/artifacts/native-rollout-20260925/sim/).

This document was corrected during a fix round: an earlier draft claimed both
backtests had been re-run and compared while the LEAN backtest had in fact never
executed (0 of the 2 required runs). That blocker is now resolved; see "LEAN
build blocker and its fix" below for the diagnosis and the fix that unblocked it.

## Environment builds

| Component | Method | Result |
| --- | --- | --- |
| `adaptive-paper-r20260925` | Read the live `adaptive-paper-20260921` venv's exact versions read-only (`uv pip freeze`), pinned them in `requirements.in`, generated a hash lock with `uv pip compile --generate-hashes`, then `uv venv` + `uv pip sync --require-hashes` | 21/21 packages identical to the live venv; lock sha256 `bfc47abf3406fdf8d1aec1dcffadf386251adb7e7ba67d9fb54ca611376e3c66` |
| `nautilus-2.0.0rc5-r20260925` | Replicated the exact recorded recipe in `evidence/receipts/native-nautilus-v2-20260920.json` (`uv venv` + `uv pip install --pre nautilus_trader==2.0.0rc5 numpy pandas`) | 5/5 packages identical; freeze output byte-identical to the recorded `freeze.stdout` sha256 |
| `lean-985ef30-r20260925` | Clone + checkout + recorded remediation, then `dotnet build` (see below) | Build succeeded on attempt 7 of this track's history (0 errors, 7730 warnings, 795 assemblies) |

The live `adaptive-paper-20260921` venv and every existing tool root were read
from but never written to by this fix round. An earlier fix round's `git status
--short` inside the existing `tools/lean-985ef30-remediation` root refreshed only
that root's `.git/index` mtime (a stat-cache write, no tracked content changed);
see `evidence/artifacts/native-rollout-20260925/sim/lean.json`'s
`existing_roots_read_only_touch` for the detail. This round re-verified the live
venv's package set matches exactly (21/21, byte-identical versions) as of this
session, confirming it is still unchanged.

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
even though the results matched; this is corrected in the current receipt. See
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
measurement, and one generated GUID into those two files -- confirmed by a full
structural diff of both runs' results, which differ in nothing else at all. See
`evidence/artifacts/native-rollout-20260925/sim/{lean,historical-simulation}.json`
for the full attempt log, diagnostic evidence, the frozen oracle verified
directly from the source file (24 recorded hashes, not the nine the task
brief's paraphrase named; corrected from the file itself), and the corrected
oracle table transcribed from `receipt.json`'s exact values rather than the
README's rounded display table.

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

## Scope and limitations

- Frozen/cached data only; no Alpaca or other market-data API call was made by
  this track. No paper or live order was placed. No systemd unit or existing
  tool root was intentionally modified (see the read-only `.git/index` touch
  noted above, from an earlier fix round).
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
