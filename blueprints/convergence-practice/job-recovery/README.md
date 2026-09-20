# Local job checkpoint and retry

This finite no-model fixture qualifies Dagu's selected-step retry around an
already accepted deterministic artifact. It does not resume a Claude or Codex
session. The unchanged [accepted planner](../native-worker/accepted/planner.py)
and [12-test visible oracle](../native-worker/seed/test_planner.py) are copied
from repository base `6001677f83c9519bb9ceb8fc5c2e7b3771b94860`.

[plan.json](plan.json) fixes acceptance before execution. The runner creates a
new private directory, private `DAGU_HOME`, minimal configuration and environment;
it writes source, oracle, runner, plan, workflow and binary hashes before invoking
Dagu. It starts no server, scheduler, account session or model. It refuses to
reuse an output directory; failed runs and native logs stay in that directory.

```sh
python3 blueprints/convergence-practice/job-recovery/run.py \
  --dagu /absolute/path/to/reviewed/dagu \
  --work /absolute/path/to/a-new-private-directory
```

Use the reviewed Dagu 2.16.6 executable, whose source tag resolves to
[`58fed633d58c1dd1319091fdb2c2f6158ecfa053`](https://github.com/dagucloud/dagu/tree/58fed633d58c1dd1319091fdb2c2f6158ecfa053).
Its GPL-3.0 license remains upstream; the fixture copies no Dagu implementation.
Only standard-library Python and the existing executable are required. This
runner uses POSIX process inspection. Separate Mac and WSL2 observations are
retained; one host's acceptance does not establish the other host's result.

The checkpoint claims its execution exclusively, runs all 12 tests, then stores
the exact source hashes and count one. The final step publishes a ready marker
and waits, with a 60-second deadline. The runner issues native `dagu stop`, checks
native history for `aborted`, and checks observed process identities have exited.
A separate release file then permits native `dagu retry --step finalize` under
the same run ID. The completed checkpoint must be unchanged, all 12 tests pass
again in finalization, and native history must report `succeeded`.

The aborted attempt remains preserved even when native start returns exit zero.
Raw histories, generated IDs, process IDs and personal paths remain private;
public results retain their hashes and sanitized observations. A hash establishes
retained byte identity, not independent truth or an exhaustive process audit.

This is local explicit checkpoint reuse, with no external side effects. It does
not qualify in-flight native-agent resume, provider cancellation, disconnect or
host restart recovery, a fresh-host restore, exactly-once external effects, or
general worker recovery. The next decision-changing test is a separately scoped
native-agent interruption and handoff reconciliation, with its account and
session boundaries declared in advance. No token-saving claim follows.

## Recorded results

| Host | Python | Native recovery | Oracle checks | Checkpoint executions |
| --- | --- | --- | --- | --- |
| macOS arm64, Darwin 25.5.0 | 3.14.7 | aborted → selected-step retry → succeeded | 12 before, 12 after | 1 |
| WSL2 Linux x86_64, kernel 6.18.33.2 | 3.13.15 | aborted → selected-step retry → succeeded | 12 before, 12 after | 1 |

Both runs retained the same checkpoint hash, `59cb2038939b9cd2840eeaed6618634cad75ffe0f9a3b689a44f420f7847a1d0`,
with no observed owned processes remaining. Each host also passed all seven
fixture regression tests. [Mac evidence](receipt-macos.json) and
[WSL evidence](receipt-wsl.json) retain actual platform versions, frozen input
hashes, native command exit codes and hashes of private native logs.
[Prior attempts](prior-attempts.json) retain the first schema failure before job
execution, the initial native success and why the final Mac variant was repeated.
The first explicit top-level DAG name was rejected by this release; the final
workflow derives its name from its filename. No oracle or acceptance rule changed.

On WSL, Dagu was absent. The official Linux amd64 release was placed only in the
new qualification directory at `tools/dagu/2.16.6/dagu`; its archive matched both
GitHub's asset digest and the publisher's checksum. The archive's license matched
the pinned upstream GPL-3.0 text. [Installation evidence](installation-wsl.json)
records these hashes and the scoped rollback. Nothing was added to global PATH,
services or shared configuration. The original Mac plan and executable/oracle
bytes were reused unchanged for the separately authorized WSL platform check.

The [Mac experiment](experiment-macos.json) and
[WSL experiment](experiment-wsl.json) use the public convergence contract. These
records establish this bounded local procedure only; raw process identifiers and
personal paths are excluded from publication.

Regression checks, without Dagu or a model:

```sh
python3 -m unittest discover -s tests -p test_job_recovery.py -v
```
