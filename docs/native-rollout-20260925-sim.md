# W1 sim track (2026-09-25): fresh side-by-side simulation roots

Three new, side-by-side tool roots were built next to the existing ones (none of
which were modified): `adaptive-paper-r20260925`, `nautilus-2.0.0rc5-r20260925`,
and `lean-985ef30-r20260925`. Frozen-data backtests were re-run on the new
Nautilus and LEAN roots and compared against their existing recorded oracles.
Per-component receipts are in [`evidence/artifacts/native-rollout-20260925/sim/`](../evidence/artifacts/native-rollout-20260925/sim/).

## Environment builds

| Component | Method | Result |
| --- | --- | --- |
| `adaptive-paper-r20260925` | Read the live `adaptive-paper-20260921` venv's exact versions read-only (`uv pip freeze`), pinned them in `requirements.in`, generated a hash lock with `uv pip compile --generate-hashes`, then `uv venv` + `uv pip sync --require-hashes` | 21/21 packages identical to the live venv; lock sha256 `bfc47abf3406fdf8d1aec1dcffadf386251adb7e7ba67d9fb54ca611376e3c66` |
| `nautilus-2.0.0rc5-r20260925` | Replicated the exact recorded recipe in `evidence/receipts/native-nautilus-v2-20260920.json` (`uv venv` + `uv pip install --pre nautilus_trader==2.0.0rc5 numpy pandas`) | 5/5 packages identical; freeze output byte-identical to the recorded `freeze.stdout` sha256 |
| `lean-985ef30-r20260925` | See below | See below |

The live `adaptive-paper-20260921` venv and every existing tool root were read
from but never written to.

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
runs, exactly as the source blueprint documents; an identity-excluded economic
hash (fills/cash/position-PnL fields only) was byte-identical between the two
runs for both cases. See `evidence/artifacts/native-rollout-20260925/sim/equity-replay.json`.

## LEAN historical simulation (new root) — blocked

`lean-985ef30-r20260925` was cloned from `QuantConnect/Lean`, checked out at the
pinned commit, and had the recorded three-package-reference remediation
applied and verified (`git diff` matches the recorded patch exactly; locked
NuGet restore completed). The solution's `dotnet build` did not complete:
across four independent attempts with four different mitigations (capping
MSBuild's restore node fan-out that had triggered an `OutOfMemoryException`
under the bounded-run cgroup; a dedicated `TMPDIR` with analyzers disabled;
isolating `Common/QuantConnect.csproj` alone with the terminal logger
explicitly disabled and stdin closed), the build reproducibly stalls
compiling `QuantConnect.Common` — near-zero cgroup CPU time over many minutes
of wall time, with no OOM, no cgroup CPU throttling, and no disk-wait state.
The existing `tools/lean-985ef30` and `tools/lean-985ef30-remediation` roots
(left untouched by this track) already have a working build from a prior wave
(2026-09-19), before this host's most recent reboot (2026-09-22) — consistent
with an environment/kernel-level regression on this host rather than a defect
in the pinned source or the recorded remediation. The six-scenario replay
could not be run on the new root; see
`evidence/artifacts/native-rollout-20260925/sim/{lean,historical-simulation}.json`
for the full attempt log, diagnostic evidence, and the frozen oracle verified
directly from `blueprints/us-equities/historical-simulation/receipt.json`
(six scenarios, four artifact hashes each — 24 recorded hashes, not the nine
the task brief's paraphrase named; corrected here from the file itself).

## Scope and limitations

- Frozen/cached data only; no Alpaca or other market-data API call was made by
  this track. No paper or live order was placed. No systemd unit or existing
  tool root was started, stopped, or modified.
- These are environment-construction and frozen-backtest reproduction checks,
  not a new strategy, profitability claim, or broker acceptance.
- Raw run logs and private argv/paths stay under the private run directory;
  this document and the linked receipts report sanitized aggregates and hashes
  only, with `${STACK_HOME}`/`${PRIVATE_STATE}`/`${PRIVATE_RUN_DIR}` placeholders
  for host paths.
