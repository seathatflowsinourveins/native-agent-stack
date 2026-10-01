# Native SDK control qualification

This bounded experiment adapts the official Codex Python SDK
[turn-controls example](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/examples/14_turn_controls/async.py),
[existing-thread example](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/examples/05_existing_thread/async.py)
and [public approval callback](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py)
at `rust-v0.159.2`, commit `ff6aec96948b70d94983af2641a6b67c94faeff5`.
It qualifies three explicit native conditions: terminal interruption after a
model response, same-thread recovery in a fresh process, and an actual declined
command approval with an absent sentinel. It is an experiment, outside the
automatic workflow and host installation paths.

[The retained receipt](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/native-controls.json)
records two native task threads and one recovery through the existing keyless
OmniRoute Responses route. Requested model `cx/gpt-6-astra-max` and effort `max`
are fixed for this dated experiment. Backend identity and remote provider
cancellation remain unknown. The interrupted attempt emitted no usage event;
the later native cumulative snapshots are partial usage evidence.

`native_controls.py` is byte-identical across the three executions.
`observe_controls.py` independently watches only the owned task processes and
sentinel. Its first version missed children spawned from another Python thread;
[that original](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/observer-before-thread-repair.py)
is retained. The repair follows the Linux kernel's
[per-thread children contract](https://www.kernel.org/doc/html/latest/filesystems/proc.html#proc-pid-task-tid-children-information-about-task-children).
Later recovery and decline each had a witnessed live child followed by its
disappearance. The first interrupted child's PID lifecycle remains unobserved.
The observer uses Linux procfs; these checks qualify this Linux/WSL host only.

Use the existing pinned SDK environment, its bundled native executable and
owned private state. The
[public plan](../../evidence/artifacts/gpt-lifecycle-convergence-20260930/native-controls-plan.json)
is a sanitized derivative of the privately retained pre-run plan. Its private
paths became placeholders after execution; it is not the original frozen bytes.
Each repetition creates fresh evidence and requires its own native acceptance.

The command shapes are:

```text
rtk timeout --signal=INT --kill-after=5s 235s rtk env PYTHONDONTWRITEBYTECODE=1 <pinned-sdk-python> examples/gpt-native-controls/native_controls.py <interrupt|recover|decline> --captures <owned-private-captures> --codex-bin <bundled-native-codex> --plan <private-plan> --deadline 210
rtk env PYTHONDONTWRITEBYTECODE=1 <pinned-sdk-python> examples/gpt-native-controls/observe_controls.py <interrupt|recover|decline> --captures <owned-private-captures> --max-seconds 240
```

Run each observer concurrently with its corresponding owned native process;
replaying its live sampler after the process exits does not reproduce that
observation. Retain original events, approvals, observer samples and exit codes
privately. Publish sanitized outcomes and hashes. Do not rerun these probes at
startup, reset working sign-ins or alter shared gateway/host settings.
