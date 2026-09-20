# Native child cancellation and crash continuation

The later inherited-tool trial **accepts the combined native lifecycle within its
scope**: one actual child was cancelled, continued under the same identity,
interrupted by a main-process SIGKILL, automatically contained by its owned
systemd cgroup, and resumed under the same parent and child identities to produce
one final effect. No direct wait-process cleanup was needed. The checkpoint and
all original fixture files stayed unchanged. See the
[accepted receipt](native-exact-read-receipt.json),
[independent audit](native-exact-read-independent-audit.json), and
[accepted artifacts](accepted-inherited/).

This qualifies one same-host synthetic task with a normal inherited native role.
It does not establish host/user-manager crash recovery, remote provider
cancellation, independent-host restoration, billing cessation, or general worker
reliability. The inherited tool pool is not an OS sandbox. All earlier failures
below remain evidence; the restricted Bash-only role remains unqualified.

## Prior trial: continuation after explicit cleanup

One actual native Claude background child was cancelled with `TaskStop`, resumed
with `SendMessage`, and resumed again after the owned native CLI runtime was
abruptly killed. The same parent session and child identity completed one local
final effect from an unchanged checkpoint. This is **partial lifecycle
acceptance**: the pending child wait survived the runtime crash and required an
explicit, identity-checked supervisor kill before continuation.

[Receipt](receipt.json), [independent retained-stream audit](independent-audit.json),
[original recorder outcome](recorder-outcome.json), [checkpoint](accepted/checkpoint.json),
[final effect](accepted/final.json), and [action journal](accepted/actions.jsonl).
Native raw streams, session/child identities and local process details remain
private; the receipt retains their exact hashes and sizes.

The frozen [plan](plan.json), [prompt](prompt.txt), [input](input.json),
[stage implementation](stage.py), read-only [parent control](control.py),
[executed runner](executed-runner.py.txt) and
[original test oracle](executed-test-oracle.py.txt) preceded the model call.
The [freeze record](freeze.json) binds those source bytes. Four deterministic
fixture checks passed before the run. One native attempt used two CLI invocations,
one child spawn and three runs under that same child identity in 43.012 seconds.
Native Claude Code 2.1.278 used the existing first-party subscription route,
explicit Opus5 / Ultracode, and the child's inherited model. No account, global
setting, proxy, shared-service or broker change was made.

The observed sequence was:

1. The native parent used `Agent` to start the one background writing child.
2. The child wrote the checkpoint and entered `cancel-wait`.
3. The parent used native `TaskStop`; its read-only check observed the old wait
   stopped. `SendMessage` resumed the same child into `crash-wait`.
4. The external supervisor observed that second child wait pending and sent
   SIGKILL to the owned native CLI process group. The CLI exited `-9`.
5. The pending wait survived. The supervisor verified its PID/start-time,
   command and fixture working directory, then killed that owned wait explicitly.
6. Native `--resume` reopened the same parent session. `SendMessage` resumed
   the same child, which ran `finalize`. No replacement `Agent` call occurred.

The child alone issued all four effect commands. The checkpoint bytes/hash stayed
unchanged, the journal is exactly `checkpoint`, `cancel-wait`, `crash-wait`,
`finalize`, and the final effect count is one. Frozen fixture sources remained
unchanged. Both recorded wait identities were no longer alive, both CLI processes
had exited and no process retained the fixture working directory at audit time.
These observations do not establish automatic native crash descendant containment.
The child also attempted `ls -1 && git status --porcelain` after finalization;
that extra read-only command was refused. Exact requested tool-only behavior did
not pass, even though the local effect contract did.

The original runner reported failure because it assumed exactly one native init
and result per invocation. The resumed stream contains three init and three
success results associated with recovered background-task delivery, all under the
same session/model. The independent audit checks those actual events, links child
effects to the original `Agent` call, and verifies the completed task under the
same child ID. The original failed outcome and executed source remain intact.
The current [runner](run.py) handles repeated native session/result messages;
its parser correction and unchanged effect guard are tested offline. No model
call was repeated to correct the recorder.

The initial SIGKILL prevented a terminal usage record. The resumed terminal,
repeated cumulative model and child-task views remain separate in the audit.
Do not add them together. Complete parent/child/retry consumption, billing and
coordinator/reviewer usage are unknown; there is no efficiency or savings claim.

This qualifies one same-host synthetic local-writing continuation with explicit
cleanup. Native children share their parent's CLI runtime; the SIGKILL is shared
runtime failure, not an independently addressed child OS process. Remote provider
cancellation, cessation of billing, power loss, independent-host restoration and
distributed exactly-once effects remain unqualified. The current upstream
[subagent documentation](https://code.claude.com/docs/en/sub-agents#resume-subagents)
distinguishes native `TaskStop`/`SendMessage` continuation from user-cancelled SDK
tasks; [CLI documentation](https://code.claude.com/docs/en/cli-reference) describes
same-session resumption. Those source descriptions are separate from this native
observation.

Offline checks do not call a model:

```sh
python3 -m unittest tests.test_worker_recovery
python3 blueprints/convergence-practice/worker-recovery/audit.py /private/retained-attempt
```

The audit requires the deliberately selected private streams from this frozen
attempt. To execute a new, independently authorized qualification, use a fresh
private directory outside Git and the existing native signed-in executable:

```sh
python3 blueprints/convergence-practice/worker-recovery/run.py \
  --claude /path/to/native/claude --run-dir /private/new-owned-attempt
```

The runner has one outer attempt, bounded native phases, scoped tools and no
fallback on unchanged failures. Its final `passed_pending_independent_audit`
status is provisional; inspect actual child identity, effects, source hashes,
process cleanup and unexpected tool behavior before accepting another run.

## Follow-up: deterministic cgroup containment and refused native trial

The [containment receipt](containment-receipt.json) and
[independent audit](containment-independent-audit.json) keep three results separate:

- The existing systemd 255 user manager contained an owned TERM-ignoring child
  which called `setsid`. Only the service MainPID received the deliberate SIGKILL;
  systemd stopped the descendant, removed the cgroup and recorded zero restarts.
- A no-model readiness probe under that same transient-service wrapper preserved
  Claude 2.1.278, the existing first-party account route and exact PATH/HOME.
- The one changed native child trial was **not accepted**. Its child tried
  `ls -la && python3 stage.py checkpoint`; unchanged `dontAsk` permissions refused
  that prefixed command. No checkpoint, action journal or final effect was created.
  The supervisor aborted only the owned service main process and verified cleanup.
  It did not retry, widen permissions or substitute a deterministic result for
  native child acceptance.

An initial deterministic harness attempt also refused the inherited WSL variable
`PROGRAMFILES(X86)` before starting a service. The corrected wrapper propagates
valid inherited environment names using upstream `--setenv=NAME`, so values are
not copied into its argument record. The unsupported Windows variable is omitted;
no native account/model/permission setting changes. The original process-group
survivor and earlier accepted continuation with explicit cleanup remain intact.

The frozen [changed-input plan](systemd-plan.json), [source hashes](systemd-freeze.json),
[executed service wrapper](executed-systemd-service.py.txt),
[executed runner](executed-systemd-runner.py.txt),
[executed tests](executed-systemd-test-oracle.py.txt) and
[failed recorder outcome](systemd-recorder-outcome.json) retain the trial inputs.
The current runner now recognizes a native permission refusal while waiting and
ends the attempt; this guard was checked offline without another model call.

For an explicitly authorized future qualification, use the already-running Linux
user manager and a fresh private directory. The supported option is:

```sh
python3 blueprints/convergence-practice/worker-recovery/run.py \
  --supervision systemd --claude /path/to/native/claude \
  --run-dir /private/new-owned-service-attempt
```

The wrapper uses an owned, uniquely named transient user service with `Type=exec`,
`KillMode=control-group`, `TimeoutStopSec=2s`, `SendSIGKILL=yes`, `Restart=no`, and a
300-second service deadline. `--pipe` preserves native stdin/stdout/stderr;
`--expand-environment=no` preserves literal native arguments. It creates no
persistent service/timer and never restarts the user manager. Only its own unit
is stopped or has its failed state cleared during cleanup. See the pinned
[systemd-run semantics](https://raw.githubusercontent.com/systemd/systemd/v255/man/systemd-run.xml)
and [cgroup kill semantics](https://raw.githubusercontent.com/systemd/systemd/v255/man/systemd.kill.xml).
This wrapper is not a filesystem sandbox or provider-cancellation mechanism.

The deterministic proof and retained-stream audit need no model:

```sh
python3 blueprints/convergence-practice/worker-recovery/containment_probe.py \
  --run-dir /private/new-detached-descendant-probe
python3 blueprints/convergence-practice/worker-recovery/containment_audit.py \
  /private/retained-worker-recovery-base
python3 -m unittest tests.test_worker_recovery
```

At this stage, the specific unresolved condition was the native child's command-contract
mismatch under the existing permissions. The combined native containment/resume
gate remained open. Neither fixture claims host/user-manager crash recovery,
remote provider cancellation, billing cessation or independent-host restoration.

## Follow-up: inherited native role and combined acceptance

The [normal role](native-role.json) omits its `tools` field and uses native
inheritance, including the background-worker filters. The CLI uses `--tools default`
and retains every installed hook and plugin. The task describes `stage.py` as an
already-built stateful program: invoking it through Bash does not require file
authoring or an analysis sandbox. Native model/account configuration remains
unchanged. Global settings stayed unchanged; the experiment used stricter
`dontAsk`. Invocation approvals add to existing
policy; they are not an exclusive tool or filesystem boundary.

The first [inherited-role plan](native-plan.json) failed before an effect. The
parent requested a directory listing, which the native RTK hook changed from
`ls -la <fixture>` to `rtk ls -la <fixture>`. Claude checks hook `updatedInput`
against permissions, so the experiment's `Bash(ls *)` approval did not cover the
transformed executable. RTK reads rules from settings files; it did not see that
invocation-only approval. The [diagnosis](native-rewrite-diagnosis.json) retains
the actual RTK tracking row joined to the native tool ID, a deterministic hook
input/output match and pinned upstream source references. The native account and
global permission settings were not changed.

The parent requested an Agent and Glob after that refusal, contrary to the task's
stop instruction. The recorder stopped the service. All 31 owned files,
including hidden fixture metadata, were unchanged; no child tool or stage effect
ran. This [failed receipt](native-inherited-receipt.json), its
[audit](native-inherited-independent-audit.json),
[source freeze](native-inherited-freeze.json), and
[recorder output](native-inherited-recorder-outcome.json) remain intact.

One separately authorized [changed trial](native-exact-read-plan.json) added
only `Bash(rtk ls -la <new absolute owned fixture>)` to that invocation. It did
not approve an RTK wildcard/proxy, change permission mode, or disable a hook.
The full native sequence then passed in 42.656 seconds: two CLI invocations, one
child, three runs of that same child, and the exact four-stage journal. Only the
owned service MainPID received the deliberate SIGKILL. Systemd removed the
actual pending native wait and the cgroup; there was no separate wait PID kill,
restart or remaining owned process. Native `--resume` reopened the same parent,
which used `SendMessage` to the same child for finalization.

The full inventory grew from 31 to 39 files through exactly eight expected stage
and supervisor artifacts. The 12 frozen sources and every original file,
including `.git` contents, remained unchanged. The native session listed 49 tools;
that is the parent/session surface, not a separately measured child tool list.
The only additional inspection was a parent `ToolSearch` for native control
tools. **This successful run did not request `ls`**, so the exact listing approval
is supported by the deterministic rewrite diagnosis but was not exercised by
the successful model run. This evidence cannot assign success solely to that rule.

The [frozen inputs](native-exact-read-freeze.json),
[recorder](native-exact-read-recorder-outcome.json) and
[read-only oracle](native_audit.py) retain this distinction. Initial SIGKILL
prevented a terminal usage record. Repeated native cumulative, terminal and
child-task views overlap; do not sum them. Provider list-price fields are native
estimates, not subscription bills. Complete parent/child/retry usage, billing and
savings remain unknown.

The public changed-trial plan is explicitly marked as a sanitized projection.
Its original frozen bytes and hash remain in private proof; the public copy
omits the personal active permission-default value. Acceptance and usage facts
are unchanged.

Read-only verification of the deliberately retained private runs:

```sh
python3 -m unittest tests.test_worker_recovery
python3 blueprints/convergence-practice/worker-recovery/native_audit.py \
  /private/native-inherited-attempt-1
python3 blueprints/convergence-practice/worker-recovery/native_audit.py \
  /private/native-inherited-exact-read-attempt-1
```

For a separately authorized new qualification, the portable invocation is:

```sh
python3 blueprints/convergence-practice/worker-recovery/run.py \
  --profile native-inherited-exact-read --supervision systemd \
  --claude /path/to/native/claude --run-dir /private/new-owned-attempt
```

The exact rewritten-read approval is constructed for that fresh fixture path.
The runner refuses path metacharacters, snapshots its source bytes and all owned
files before the call, and retains streams, commands and inventory afterward.
Acceptance still requires the independent oracle and review of actual calls;
the runner's passing status is provisional. These trials establish neither
universal instruction-following nor success for the earlier Bash-only contract.
