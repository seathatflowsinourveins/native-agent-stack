# Planned native browser-image qualification

This is a source-backed experiment plan, with no observations or adoption.
It follows the repository's [convergence contract](../contract-reference.md)
and preserves the existing full-image, observer and task-quality gates.

## Pinned source and comparison

Use OpenHands software-agent-sdk v1.50.0 at
`dcf401af7a9a302ef92cb7d092e1df9bb659daa5` and its unchanged
[native builder](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/build.py)
and [Dockerfile](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/Dockerfile).
The baseline is the published full image at digest
`sha256:6d91a74fd2b556107e4e15476680d1d8116eeadfc06879baf7193caa73314dfc`.
The candidate uses the builder's supported browser capability selection.
It removes the optional OpenVSCode and nested-Docker packages; retaining
Chromium and the full stage's GitHub CLI is source composition evidence.
Preservation of the selected terminal, file-editor, planner, browser and
delegation tools still needs native execution. The upstream `minimal`
composition omits browser and GitHub CLI and does not meet this plan's contract.

The [retained image triage](../../runtime-workers/openhands/evidence/image-triage-20260930.json)
records native scan exit 0 with 56 fixable high/critical matches; its command
generated a report without a severity threshold. Those findings leave image
acceptance pending. A native manifest read on September 30 returned the same
published digest. Historical findings remain historical; this plan does not
turn that identity check into a passing fresh scan. Source review corrected
the initial shorthand "failed scan" to distinguish native command exit from
the unmet acceptance rule.

The Dockerfile pins system CPython 3.13.15 and separately copies a managed
3.13 interpreter. A base-image override alone does not repair both copies.
The [CPython backport](https://github.com/python/cpython/pull/157192)
is at `b8f23e307097552eaea2604383a12ab280520d0d`; the
[3.13 release schedule](https://github.com/python/peps/blob/main/peps/pep-0719.rst)
places 3.13.16 on October 6. A scheduled release is not an available remedy
or acceptance evidence. The candidate can therefore still fail the threshold.

## Execution boundary and native commands

Before execution, the coordinator and the active measurement owner settle the
host-resource boundary and record native container/build prerequisites,
available disk and memory, selected base/snapshot identities and the owned
cleanup path. Perform one model-free build in an isolated source checkout and
existing rootless container context, using a verified Linux/amd64 builder.
The native `--arch` flag labels tags; the local `--load` path does not pass
`--platform` to Buildx. Do not change a shared gateway, account, launcher,
global setting, deployed Collector or measurement window. No build, pull,
service launch or model qualification is performed by this plan.

From the pinned SDK source, the supported proposed commands are:

```sh
rtk uv run --frozen python -m openhands.agent_server.docker.build --base-image python-node-runtime --image localhost/nas-openhands-trial --image-flavor default --target binary --custom-tags v1.50.0-browser --install-capabilities browser --install-acp-providers claude-code,codex,gemini-cli --arch amd64 --load
rtk grype docker:localhost/nas-openhands-trial:dcf401a-v1.50.0-browser-amd64 --platform linux/amd64 --only-fixed --fail-on high --output json
rtk docker run --rm --platform linux/amd64 localhost/nas-openhands-trial:dcf401a-v1.50.0-browser-amd64 --check-browser
```

Correction during source review: `--custom-tags` takes a suffix, so the bare
`:v1.50.0-browser` target first proposed in research was wrong. Native
`BuildOptions.all_tags` evaluation returned exit 0 and the corrected tag
above, following [the pinned derivation](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/docker/build.py#L581).
The image's native `--check-browser` renders `about:blank`, closes its
executor and exits 0 or 1 before server startup, following
[the pinned check](https://github.com/OpenHands/software-agent-sdk/blob/dcf401af7a9a302ef92cb7d092e1df9bb659daa5/openhands-agent-server/openhands/agent_server/__main__.py#L138).
No browser or model execution is claimed by this source check.

Use Grype 0.119.0, preserving the actual JSON and exit status. Its native
threshold failure is exit 2. Retain the candidate image identity, SBOM/database
identity and every attempt, including a failed build or scan. A passing scan
requires zero fixable high/critical findings under the exact recorded native
command; removing one optional package is insufficient.

## Predeclared quality and usage rules

A scan pass and native browser check are necessary for this image trial.
The selected tools must retain their installed native contracts and no tool
may be declared preserved from dependency metadata alone. The image remains
a candidate until these checks and recovery/cleanup evidence are retained.
This plan does not accept a provider route, whole-task quality, independent
observer, Gate A/P3 or a token-saving comparison.

Future task qualification uses the maintained
[OpenHands benchmarks](https://github.com/OpenHands/benchmarks/tree/405bae7140d7e961a75f4910a0b2e7069731db96)
and its native SWE-bench/GAIA evaluation paths. That revision pins SDK
`43376f1868ffd702746080714a59c16d3f69ec12`, so compatibility with v1.50.0
must be qualified before using it. Freeze instance IDs, dataset identities,
an explicit route and one worker with a 12-iteration cap. The GAIA
`question_scorer` is the native grading path; aggregating stored scores is
not a new grading run. Dataset access and native prerequisites stay separate
from this model-free image trial. No credential is fetched for this plan.

Laminar telemetry inside an agent process does not independently observe that
process. A future observer must have separate host ownership and controls.
[Tetragon process lifecycle](https://tetragon.io/docs/use-cases/process-lifecycle/)
is a research lead with Linux BTF/privilege prerequisites, not a selected or
installed service and not an oracle for model quality, skills or token use.

All provider and whole-task usage remains unknown. Model-free execution may
record observed native usage separately; no missing field becomes zero and
no historical cumulative receipt is added twice. Do not publish savings from
this plan. Roll back by retaining the current selection and removing only the
trial's owned image/build artifacts under the native lifecycle.

The pinned repository is MIT-licensed, and the SDK/tools/server declare
Python >=3.12. Third-party image contents retain their own licenses and
runtime compatibility requirements; this source review does not qualify
them collectively.
