# NativeStack2604 rc5 SPY follow-up — 2026-10-06

The unchanged `one_zero` harness at ecfa112764c664d35377dd66b8cfcb67e5a94d60
ran on the installed NautilusTrader2.0.0rc5 runtime after the owner staged all
five frozen LEAN inputs. Manifest verification exited0. No provider acquisition,
broker connection, order, credential access or runtime reinstall occurred.

The final replay exited0 at04:41:27–04:41:30Z; comparison exited1 at04:41:47Z.
The returned comparator reports **FAIL**, complete=true,135PASS/1FAIL and zero
skips. Its106execution checks all pass; those are a subset of135, not an
additional count. The replay processed725bars, produced2fills, observed zero
engine-error lines in either run and two equal economic records. Native end cash
is90734.08USD, including428.64USD distributions.

The remaining failure is
`precondition_review.no_prior_replay_ran_the_reviewed_harness#35`.
The committed history contains two recorded prior replays with identical reviewed
harness hashes; only one was qualifying. The unchanged comparator deliberately
rejects any matching prior replay (compare.py:814–817). Existing deviation
acceptance handles the earlier first-v2-before-review condition and does not
waive this check. Economic agreement therefore remains distinct from a complete
preregistration PASS.

| Case | Current evidence |
| --- | --- |
| SPY one_zero | Runnable: replay0, comparator1, full FAIL;135PASS/1FAIL;106execution PASS; about3s replay and less than1s comparison |
| SPY one_stress, two_zero, two_stress, four_zero, four_stress | Blocked: no mapping yet; no new mapping or execution |
| AAPL baseline, fee_slippage_stress | Blocked: input absent under5f's retained-input ruling; no substitute acquisition |
| Runtime acceptance | Prior native24/24PASS retained; not a new post-reboot acceptance run |

The route is a **launcher-equivalent vector**, rather than an invocation of
launch.py. It adds the runtime acceptance's managed `.python` read-only mount
beside `.venv`, retaining new network/process/user namespaces, clearenv,
read-only runtime/repository/data and one owned persistent writable output.
The final environment uses the five values documented in spy-parity/README.md:97–99.
Native observations show only loopback, read-only mounts and isolated Python.
The exact vector with named private-root substitutions and original argv hashes
is in `spy-one_zero-launcher-equivalent-20261006T044147Z.json`.

An initial replay exited0 at04:40:32–04:40:35Z, and comparison exited1 at
04:40:52–04:40:53Z with134PASS/2FAIL. Its runtime-acceptance environment added
HOME, XDG_CACHE_HOME, MPLBACKEND, UV_OFFLINE and GIT_OPTIONAL_LOCKS; the pinned
comparator rejects these additional names. That result, its returned failing
checks and original output hashes are retained in the execution receipt. The
fresh final output corrects only this route mismatch. No harness, predicate,
mapping, preregistration, tolerance or history byte changed.

Committed replay history remains an unchanged source snapshot. It excludes these
two new attempts, which are retained separately under the receipts-only scope;
it is not an exhaustive updated history. This limitation must remain visible
before any later replay or owner adjudication. The original24-check runtime
receipt, input/mapping blockers and frozen case contract remain unchanged.

The native receipt, verdict and stdout published beside this note are byte-for-
byte returned primary outputs. Full private outputs from both attempts stay in
the owned worktree's ignored `.runtime/j2-sim-rc5-20261005/` directory. An empty
output-directory locator mistake beside the staged input root was corrected
with rmdir before native execution; final outputs use only the owned worktree.

Sources: nautechsystems/nautilus_trader atv2.0.0rc5
(1b0a49d2792a9432a3aca3fcb617ce7a630d905e); spy-parity/run.py,
compare.py, README.md, PREREGISTRATION-v2.md and replay-history-v2.json at
ecfa112764c664d35377dd66b8cfcb67e5a94d60; runtime-2604/
accept-trading-2604.sh:88–100 at the same pin; owner-staged LEAN985ef30
bytes bound by acceptance-plan.md:64–74. Owner routing and native execution are
separate from any later strategy, broker or architecture qualification.
