# Native Harbor one-task keyless prerequisite outline

Source preparation only. No container, image pull/build, install, test or model
request has run. Installed Harbor remains 0.23. The currency owner or an explicitly
authorized isolated qualification must first provide native Harbor 0.24 at
`harbor-framework/harbor@b53b8134e1241686dca7759af188f987ecc48e8b`.
The command center selects the final invocation after inspecting this outline.

Use the unchanged upstream
[`examples/tasks/hello-world`](https://github.com/harbor-framework/harbor/tree/b53b8134e1241686dca7759af188f987ecc48e8b/examples/tasks/hello-world)
in an owned task copy. Keep its instruction, task.toml, Dockerfile, verifier,
solution and canary intact. The verifier checks /app/hello.txt and reports native
reward. Add only the supported task networking overlay below. Additional smoke
intent is supplied through the native `--extra-instruction` option, not a new
runner or edited verifier.

## Source-backed native inputs

Harbor `src/harbor/cli/jobs.py:603-611` accepts repeatable
`--agent-kwarg`/`--ak key=value`; lines 653-661 accept `--agent-env`/`--ae`.
`codex.py:1536-1554` accepts an inline JSON native config. Options version and
reasoning_effort pin CLI 0.160.0/max. Use a custom provider, not only
OPENAI_BASE_URL: Codex at `a956835d020762cb2b570053af06f643a11c0ecc` requires
Responses protocol and permits keyless custom providers with no credential fields.

Proposed command, not executed (owned locations and nonce must be frozen):

```sh
rtk proxy harbor run --path '<OWNED_UNCHANGED_HELLO_TASK>' --agent codex --model 'gpt-6.1-sol' \
  --agent-kwarg version=0.160.0 --agent-kwarg reasoning_effort=max \
  --agent-kwarg 'config={"model_provider":"omniroute","model_providers":{"omniroute":{"name":"OmniRoute","base_url":"http://127.0.0.1:21128/v1","wire_api":"responses","requires_openai_auth":false}}}' \
  --agent-env OPENAI_API_KEY= --agent-env CODEX_AUTH_JSON_PATH= --agent-env CODEX_FORCE_AUTH_JSON=0 \
  --jobs-dir '<OWNED_JOB_DIR>' \
  --extra-instruction 'Complete the original task unchanged. Also create /app/smoke-nonce.txt containing exactly <FROZEN_NONCE>, and include that exact nonce in your final response.'
```

**Model-route gate:** Harbor strips slash prefixes (`codex.py:1668`). The gateway
metadata lists namespaced cx/codex/cxa Sol IDs; it does not list the bare ID above.
That metadata proves neither acceptance nor rejection of the bare alias. This
command is a proposed discriminating bare-alias prerequisite only, not an approved
model substitution. Record its actual result. If it fails, preserve it and ask
the command center for an upstream-supported path; do not patch model parsing,
invent flags, insert dummy keys, or call a different model silently. Promptfoo's
SDK preserving a namespaced ID is separate source support, not Harbor acceptance.

Explicit empty agent env entries override inherited entries (base.py:258-264),
so no native account/auth file is selected. Harbor still generates an empty
sandbox auth.json (`codex.py:1718-1723`). Declare that upstream behavior. No host
auth/configuration or credential file is copied, and no existing key value is
read or placed in this preparation.

## Existing rootless daemon and task networking

Proposed additional `environment/docker-compose.yaml` in the owned task copy:

```yaml
services:
  main:
    network_mode: host
```

Harbor respects task networking at `docker.py:358-417`. Its TOML environment
network policy is separately `public`; `host` is not a valid policy enum.
The root reported existing Engine/Client 29.8.2 and rootlesskit 3.1.0 metadata.
Docker documents the former host-mode RootlessKit namespace limitation as ending
at 29.5. This version prerequisite does not prove actual 21128 reachability.
Use only the existing rootless daemon; no rootful dockerd, sudo, restart,
sysconfig change or gateway exposure is authorized by this outline.

## Independent oracle and evidence boundaries

Freeze task/config/extra-instruction hashes and a new non-secret nonce before the
one run. Keep native stdout/stderr, job/trial result, actual installed CLI/version,
native trajectory and returned artifacts privately. Retain failures without
altering the original input. Inspect independently:

1. Native unchanged verifier result and /app/hello.txt content.
2. Actual nonce file and final assistant response both contain the frozen nonce;
   no stale/cached answer or pre-created output may satisfy this control.
3. Native trajectory shows a fresh model turn and the relevant write; distinguish
   requested model/effort from actual served identity and unknown values.
4. Correlated gateway request/native endpoint observation identifies 21128 and
   Responses traffic. No credentials or payloads enter public evidence. A models
   list or open socket alone is not a fresh-answer/protocol result.

The hello-world test is unchanged upstream-example execution. Extra instruction
and nonce observation are a declared synthetic smoke fixture. Source capability,
reported engine metadata, native verifier/answer, model identity and container
loopback are separate evidence levels. B13 remains held until the applicable
auth/protocol/route and SDK trust controls have actual passing results.
