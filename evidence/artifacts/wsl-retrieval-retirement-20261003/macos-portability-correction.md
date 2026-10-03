# Retained macOS failure and scanner shell portability correction

Prior publication head `b4a7a0c9fb81fd250b5ae5ade5fa5437e79de063`, base
`56473e4b840f0e6940c031801d866e7e9bf29baf`, had seven required passes and one
macOS failure. The original [validate-macos job111120003517](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/37093976373/job/111120003517)
ran9822tests in1696.634s: process1,12failures,1328skips. Native watcher exit1
and fetch/download exits0 are retained. Uploaded artifact
`adoption-bootstrap-full-suite-macos-37093976373-1`, id11264895096, contained
`full-suite-macos.log`1849953bytes/SHA256
`bc2914b00c2863f53e22d6f0ceab64700f1d78542b33e3f5b7fbc44c574706d6`.
Its original private log is retained; no raw runner paths or conversations
are published. Job's printed tail was insufficient for diagnosis, so this
record uses the uploaded full log, not an inferred cause from a failed badge.

Eleven failures were existing `SyntheticWorkflowInvocationTests` in
`tests/test_osv_lockfile_coverage.py`: the native macOS shell could not run
`mapfile`; it then reported unbound arrays, returning127 before the synthetic
scanner routing/status assertions could run. Its exact Bash version was not
retained by that job, so the missing builtin alone is not a version assertion.

The isolated bounded Sol/max repair changes only list loading in the actual
security workflow: `while IFS= read -r`, quoted indexed-array appends and the
original process substitutions replace the three `mapfile` commands.
Element-existence guards intentionally reject an empty group with exit1
before `nounset` array-length expansion. Every original length/inventory
check, jq selector, preflight, exact archive assignment, config, scan argument,
ordinary input, status aggregation and SARIF path is preserved. No test
assertion or skip is changed. The retained WSL lock remains at
`blueprints/convergence-practice/wsl-retrieval/package-lock.json`,82463bytes,
SHA256 `5c51ee65cc477f2c1488a38ff5cad1c0a737f81a5b61bbd70d5edc4d15bfc3bb`.
No active-input exception, relock or relocation is introduced.

The syntax follows the worker's actual installed GNU Bash5.2.21 builtin help
and official installed5.2 manual, sections read, arrays, process substitution
and shell parameter expansion. Root independently fetched the maintained
[GNU Bash5.3 source distribution](https://ftp.gnu.org/gnu/bash/bash-5.3.tar.gz),
11355854bytes/SHA256
`0d5cd86965f869a26cf64f4b71be7b96f90a3ba8b3d74e27e8e9d9d5550f31ba`,
and extracted `doc/bashref.texi`, `builtins/read.def`, `array.c` using native
tar, exit0. Relevant manual locations: while955, read5548 and read-r5629;
`doc/bashref.texi` SHA256
`f3d37d57a1061e24d266051de9bd47ffa43dc86584afea11576c535ad2be32d5`.
This is source review of supported syntax, not a new tool installation or
older-Bash/macOS execution. The worker's own nominated5.3 fetch failed1 on
DNS, and its actionlint probe failed1; those failures remain distinct from
root's successful source fetch and scoped native lint.

Original worker execution, source delta at the prior head:

```text
python3 -m unittest tests.test_osv_lockfile_coverage tests.test_wsl_retrieval tests.test_workflow_hardening tests.test_openhands_lock_binding
exit0;164tests;6.031s;2skips
bash -n (extracted real scanner step)
exit0
git diff --check
exit0
```

`macos-portability-integration.stdout.txt` preserves the164-test tool output
byte-for-byte:276bytes/SHA256
`c6a0fc5f9311456adab5889d9dec5921c006fea6533071a90d1f7c4d33d20619`.
Draft correction: the note's initially transcribed stdout digest was wrong;
root derived this digest from original worker event item10 and verified exact
copied bytes before registration. This was a publication correction, not a
rerun. Empty ordinary/frozen-macos/frozen-WSL
groups were separately run through the same recording fixture: all returned1,
no scanner call, no artifact and no stderr. These are repository integration
and synthetic checks, not unchanged upstream scanner tests or Mac acceptance.
Root's already-pinned native actionlint1.17.0 ran the changed workflow exit0,
empty output. Its official archive SHA256 remains
`620abd485a12b6ab1125b844a876414e1d5bd2af8a3125b27f82b01d0d9d6e5a`.

The twelfth macOS failure was independent of retirement: unchanged
`RunLoop.test_two_sweeps_inside_a_minute_make_one_rss_request_and_one_edgar_cycle`
returned `(0,1)` instead of `(0,2)` at test_incentive_monitor.py1781. Root
verified identical test/runtime blobs across prior head and base:
`b98d7d1de32e42f0382880bb2d8a27d22fdeeff5` and
`3a735363add2dd49ce4d47e6d193b8fd98195a57`. The test uses `--until-et23:59`
and only creates STOP on its second snapshot request, while its existing
Market.run fixture leaves datetime live. Runtime monitor.py1018/2105/2295
uses the real Eastern date/deadline and exits after writing a first sweep
when that deadline is reached. The job interval03:45:36–04:13:57UTC crosses
23:59Eastern; this is a source-supported deadline-flake inference, not an
observed per-test wall timestamp. The owning trading/monitor lane received
the failure and deterministic-clock repair lead. Root does not edit that
lane, weaken its assertion or waive its required check.

Original Linux and OSV passes belong to the prior head. A new publication
must obtain its own exact-head review, required checks and other-lane ACK.
No new OSV/provider/host/GPU trial occurred in this bounded local repair.
The earlier receipt-binding and review-environment failures remain in their
separate original records. No failed condition was deleted or silently
reclassified as acceptance.
