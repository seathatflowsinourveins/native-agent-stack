# Owned SSH transport interruption

The corrected attempt observed a Dagu 2.16.6 job survive termination of its owned
Mac SSH client. A fresh, nonmultiplexed connection found the same native run still
running with the same durable checkpoint and effect count 1. Releasing the waiting
finalizer completed that run without native stop or retry. The unchanged planner
oracle passed all 12 tests both before and after the interruption; all 12 native
acceptance checks passed. Five observed owned processes, including the controller,
and one observed listener retired; the local SSH client was absent.

The first attempt failed because its frozen harness expected SIGTERM exit `-15`,
while native OpenSSH returned `255` with empty stderr. Its failure cleanup explicitly
stopped the job before a fresh status snapshot. One separately frozen diagnostic
repair established same-run finalizer-only retry, with the checkpoint still executed
once. That repair does **not** establish transport survival. Both the original
failure and repair are retained in [receipt-attempt-1.json](receipt-attempt-1.json)
and [prior-attempts.json](prior-attempts.json). The separately frozen corrected
attempt used a new prefix and is recorded in [receipt.json](receipt.json).

The result qualifies this specific deterministic fixture and launch arrangement.
The remote native process had a separate process session and file-backed logs;
arbitrary foreground jobs remain outside scope. This was controlled termination
of one owned SSH client, with shared multiplexing disabled. It was not a real
network outage, power loss, host restart, credential recovery, model session
recovery, or proof of distributed exactly-once external effects. No model call,
package installation, scheduler, global service, auth change or host-wide network
change was involved. The original HOME was preserved; child DAGU_HOME, temporary
directories and XDG directories belonged to the new private task prefix.

## Retained protocol and native provenance

[frozen-evidence.json](frozen-evidence.json) maps each staged name to its exact
public source bytes and pre-execution hash. Original `plan.json` and `driver.py`,
the diagnostic `repair-plan.json` and `repair.py`, and corrected
`plan-corrected.json` and `driver-corrected.py` remain distinct. The remote controller,
accepted planner, job-recovery fixture and original 12-test oracle were unchanged.
Native run IDs, process identities, generated workflow paths, help output and full
command logs remain private; public hashes establish byte identity, not independent
observation truth. Cleanup covers sampled owned identities and listeners, not an
exhaustive audit of the operating system.

The existing WSL executable was verified against the previously accepted upstream
[Dagu source revision](https://github.com/dagucloud/dagu/tree/58fed633d58c1dd1319091fdb2c2f6158ecfa053).
Its binary SHA-256 is `20de7ae94e16999ff997db0386dced9504db37c87de333837fd15b4892b98bd7`;
its GPL-3.0 license SHA-256 is
`3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986`.
Installed `version` and help for `start`, `history`, `stop`, `retry`, and `validate`
were checked before the job. The actual remote Python was 3.12.3.

The native lifecycle uses these supported forms, with task-owned values:

```text
dagu --context local --dagu-home <private-home> --config <private-config> validate <workflow>
dagu --context local --dagu-home <private-home> --config <private-config> start --run-id <owned-run> <workflow>
dagu --context local --dagu-home <private-home> --config <private-config> history --run-id <owned-run> --format json
```

Only original-attempt failure cleanup and its diagnostic repair used:

```text
dagu --context local --dagu-home <private-home> --config <private-config> stop --run-id <owned-run> <workflow>
dagu --context local --dagu-home <private-home> --config <private-config> retry --run-id <owned-run> --step finalize <workflow>
```

## Offline checks and optional reproduction

These checks read retained evidence and do not reconnect or rerun native jobs:

```sh
python3 blueprints/convergence-practice/wsl-transport-recovery/audit.py
python3 -m unittest discover -s blueprints/convergence-practice/wsl-transport-recovery -p 'test_*.py' -v
python3 scripts/validate_convergence.py blueprints/convergence-practice/wsl-transport-recovery/experiment.json --root . --json
```

A separately authorized new attempt requires an existing pinned Dagu executable,
native SSH access and new private prefixes. It refuses prefix reuse. Its transport
options are `ControlMaster=no`, `ControlPath=none`, `BatchMode=yes`, and
`ConnectTimeout=10`. It signals only the local SSH process it created:

```sh
python3 blueprints/convergence-practice/wsl-transport-recovery/driver-corrected.py \
  --host "$AUTHORIZED_HOST" --remote-prefix "$NEW_REMOTE_PREFIX" \
  --private-output "$NEW_LOCAL_PREFIX"
```

Keep evidence until accepted, then remove only task-owned prefixes. No service or
configuration rollback is needed. Fixture model usage is zero; enclosing agent
usage is unknown, and there is no token-savings claim. A stronger failure mode
needs its own frozen, separately authorized experiment.
