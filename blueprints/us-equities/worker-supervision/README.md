# Transient worker supervision

The existing Linux/WSL2 user service manager terminated a disposable parent,
child and grandchild after a runtime deadline. All three ignored SIGTERM. The
native result was `timeout`, the main process died from SIGKILL, and all three
original PID/starttime identities were absent. An explicitly launched fresh
service then succeeded. [Receipt](receipt.json) preserves the native results.

This adds a process-lifecycle acceptance to the earlier Dagu completed-history
restart checks. It does not establish interrupted workflow resume, model-provider
cancellation, exactly-once external effects, or automatic adoption by existing
workers. The three-process [fixture](fixture.py) performs no network or model work.

## Native commands

Use the already installed distribution tools. Prerequisites are a running user
service manager and cgroup v2; this host reported systemd `255.4-1ubuntu8.17`.
No systemd installation, upgrade, persistent unit, timer or enablement is needed.

```sh
systemctl --user --version
systemctl --user is-system-running
stat -fc %T /sys/fs/cgroup
```

Set `STACK_REPO` to this checkout. Create an empty private fixture directory and
a unique transient unit name. Keep native output private: it includes local
process and invocation identifiers. Start the native command in the background
so its cgroup can be inspected while active. `$PRIVATE_RUN` is a fresh directory
owned by the operator; `$FIXTURE_DATA` is an empty child directory.

```sh
umask 077
systemd-run --user --wait --unit="$UNIT" \
  --property=Type=exec \
  --property=RuntimeMaxSec=4s --property=TimeoutStopSec=1s \
  --property=KillMode=control-group --property=SendSIGKILL=yes \
  --property=Restart=no --property=MemoryAccounting=yes \
  --property=MemoryMax=64M --property=TasksAccounting=yes \
  --property=TasksMax=16 --property=CPUAccounting=yes \
  --property=CPUQuota=25% --property=NoNewPrivileges=yes \
  --property=UMask=0077 \
  /usr/bin/env -i PATH=/usr/bin:/bin /usr/bin/python3 \
  "$STACK_REPO/blueprints/us-equities/worker-supervision/fixture.py" \
  "$FIXTURE_DATA" >"$PRIVATE_RUN/deadline.stdout" \
  2>"$PRIVATE_RUN/deadline.stderr" &
SUPERVISION_LAUNCHER=$!
systemctl --user show "$UNIT.service" \
  --property=Type,ActiveState,SubState,Result,ControlGroup,RuntimeMaxUSec,TimeoutStopUSec,KillMode,SendSIGKILL,Restart,NRestarts,MemoryMax,TasksMax,CPUQuotaPerSecUSec,NoNewPrivileges
wait "$SUPERVISION_LAUNCHER"
```

The last command is expected to return **1** for this timeout fixture; preserve
that failure. The actual observer waited for all three role records before the
active inspection, read `cgroup.procs`, `memory.max`, `pids.max` and `cpu.max`
under the returned cgroup, then checked each saved PID with its `/proc` starttime
after completion. A reused numeric PID would not count as the original process.
The observer and exact private argument arrays are retained by receipt hash.

```sh
systemctl --user show "$UNIT.service" \
  --property=Result,ExecMainCode,ExecMainStatus,ActiveState,SubState,NRestarts
journalctl --user -u "$UNIT.service" --no-pager -o short-iso-precise
systemd-run --user --wait --unit="$UNIT-fresh" \
  --property=Type=exec --property=RuntimeMaxSec=4s \
  --property=TimeoutStopSec=1s --property=KillMode=control-group \
  --property=Restart=no /usr/bin/env -i /usr/bin/true
# Clear only this disposable unit's recorded failed state after retaining evidence.
systemctl --user reset-failed "$UNIT.service"
```

## Direct result

```text
Finished with result: timeout
Main processes terminated with: code=killed/status=KILL
Service runtime: 5.374s
CPU time consumed: 21ms
Memory peak: 8.9M
Memory swap peak: 0B

Result=timeout
ExecMainCode=2
ExecMainStatus=9
NRestarts=0
memory.max=67108864
pids.max=16
cpu.max=25000 100000

Fresh run:
Finished with result: success
Main processes terminated with: code=exited/status=0
Service runtime: 2ms
```

Native cgroup inspection found exactly three processes while active and zero
after termination; the cgroup directory had been removed. The observed resource
values prove limit configuration, not behavior under CPU saturation, excessive
process creation or memory exhaustion. The fresh run proves that another unit
can start successfully; unfinished application state was not resumed.

## Upstream semantics and next adoption gate

The pinned systemd v255 sources document
[runtime/stop deadlines](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.service.xml),
[whole-cgroup termination](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.kill.xml),
[transient services and waiting](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd-run.xml),
and [resource controls](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.resource-control.xml).
Current upstream release metadata and source hashes are in the
[hosting review](../../../catalogs/us-equities/convergence-program/hosting.json).
The v255 source describes the baseline semantics; the Ubuntu package carries
distribution patches. No current-upstream-version execution is inferred.

Before wrapping a real research worker, select limits from actual workload
measurements, propagate cancellation to the native client, preserve partial
receipts, and reconcile provider usage after interruption. A local kill cannot
guarantee that a remote request stopped or that billing stopped. Use a separate
reviewed sandbox profile for filesystem/network isolation. WSL shutdown and
macOS lifecycle acceptance remain separate host tests.
