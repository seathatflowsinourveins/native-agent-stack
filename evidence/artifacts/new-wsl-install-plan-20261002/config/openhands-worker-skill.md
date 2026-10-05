---
name: native-stack-worker
description: Dispatch an authorized coding task to the installed OpenHands SDK worker in its owned workspace, and inspect the native job result.
---

Use the installed SDK 1.50.1 dispatcher for an authorized bounded coding task.
Choose a new job ID containing letters, digits, hyphens or underscores. Prepare
the job with the owned workspace and task, then wait for its native user unit:

```bash
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/new-wsl-native-stack/openhands"
python3 "$cfg/worker.py" --prepare "$job" --workspace "$owned_workspace" --task "$task"
systemctl --user start --wait "openhands-job@$job.service"
```

The dispatcher creates the per-job srt policy and permits only the named workspace
and its private state for writes. Its model route is the keyless loopback
OmniRoute gateway on 127.0.0.1:21128; native client sign-ins stay native.

Inspect `~/.local/state/native-agent-stack/runtime-workers/openhands/$job/run-report.json`
and the actual task files. Require a successful unit, `requests_to_model > 0`, and
the task's own oracle. Retain the journal on failure; prepare a new ID after a
material repair so prior failed evidence survives. A zero-request preflight is
not a completed coding task. Return the actual result and artifact locations.

Sources: [SDK example](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/examples/01_standalone_sdk/01_hello_world.py#L9),
[SDK metrics](https://github.com/OpenHands/software-agent-sdk/blob/v1.50.1/openhands-sdk/openhands/sdk/llm/utils/metrics.py#L113),
[sandbox runtime](https://github.com/anthropic-experimental/sandbox-runtime/blob/v0.0.78/README.md),
and the repository install-plan's `config/openhands-worker.py` dispatch glue.
