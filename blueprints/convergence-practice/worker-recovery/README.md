# Native child cancellation and crash continuation

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

The next specific unresolved condition is the native child's command-contract
mismatch under the existing permissions. The combined native containment/resume
gate remains open. Neither fixture claims host/user-manager crash recovery,
remote provider cancellation, billing cessation or independent-host restoration.
