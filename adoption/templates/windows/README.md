# WSL Windows-time persistence reference

The [administrator runbook](clock-root-fix-r2.md) and
[script](clock-root-fix-r2.ps1) prepare the dated CLOCK-R2 changes. The
[decision](../../../docs/decisions/2026-10-06-clock-root-fix-round2.md) distinguishes
configuration correction from measured clock readiness. This is a reviewed-main
reference candidate; use the exact accepted commit, not an older deployed release.

The [D0 reader](../../../scripts/d0_check.py) extends the existing PHC0 census
with native, read-only Windows SCM/Registry/ScheduledTasks queries. Default mode
checks persistence before sampling the agent. A persistence failure exits
immediately with the administrator remediation. `--persistence-only` reads
Windows without a census; `--agent-only 60` retains the original census behavior.
The script accepts the original positional duration as well as `--seconds`.

The NativeStack2604 census queries its observer on UDP **3323** for both loopback
families. UDP 323 belongs to the older distribution on WSL's shared network;
an old PHC0 answer must not mask a missing native observer. Reports name the
actual `chrony_port` and use `chrony_phc0_answers`/`chrony_refs`. The installed
chronyc 4.8 `-p PORT` option selects that target ([upstream manual](https://chrony-project.org/doc/4.8/chronyc.html)).
This does not change the administrator script or persistence-only mode. The
candidate boot oneshot runs both checks with `--seconds 60`.

D0 fails if startup is delayed or not numeric 2, W32Time is not RUNNING, any
STOP/unknown trigger exists, a required read is malformed, Minutes is not 1 or
MaxTimes is not 7. START triggers, including the unidentified type-7 start path,
are recorded. SynchronizeTime's state is recorded without turning a disabled
task into an extra acceptance condition. An absent MaxTimes value uses the
documented default 7 and records its absence. A passed persistence read-back
establishes configuration, not synchronization accuracy or a new boot result.

## Co-op apply after the command-center ACK

Stage only the accepted files and enable the
[user oneshot](../systemd/clock-persistence-check.service) for the next distro
boot. Perform host staging outside the paper windows; no service or manager
restart is part of this apply. Set `CLOCK_SOURCE` to the exact reviewed checkout
and `CLOCK_HEAD` to the accepted head before these commands. `CLOCK_BACKUP` is
an existing private backup directory chosen by the co-op.

```sh
test "$(git -C "$CLOCK_SOURCE" rev-parse HEAD)" = "$CLOCK_HEAD"
git -C "$CLOCK_SOURCE" diff --quiet
git -C "$CLOCK_SOURCE" diff --cached --quiet
CLOCK_RUNTIME="$HOME/.local/lib/native-agent-stack/clock-r2"
CLOCK_UNIT="$HOME/.config/systemd/user/clock-persistence-check.service"
# Save each existing selected file, or record its absence, in CLOCK_BACKUP first.
install -d -m 700 "$CLOCK_RUNTIME"
install -m 700 "$CLOCK_SOURCE/scripts/d0_check.py" "$CLOCK_RUNTIME/d0-check.py"
install -m 600 "$CLOCK_SOURCE/adoption/templates/systemd/clock-persistence-check.service" "$CLOCK_UNIT"
python3 "$CLOCK_RUNTIME/d0-check.py" --help
systemd-analyze --user verify "$CLOCK_UNIT"
systemctl --user daemon-reload
systemctl --user enable clock-persistence-check.service  # no --now
```

This unit runs when the distro's user manager reaches `default.target`. It is
not a Windows-boot task and adds no ordering dependency to other user units.
`RemainAfterExit=yes` avoids repeat execution within that manager's lifetime.
Its `OnFailure=paper-alert@%n.service` uses the existing paper-alert receiver;
verify that dependency and its alert route before the acceptance boot. The
runtime contains no credential file and writes no Windows setting or clock.

After the attended boot, read back the enablement, exit, returned values and
actual alert receipt for any failure. Retain full output privately:

```sh
date -u
systemctl --user is-enabled clock-persistence-check.service
systemctl --user show clock-persistence-check.service -p ActiveState -p Result -p ExecMainStatus -p OnFailure
journalctl --user -u clock-persistence-check.service -b --no-pager -o cat
```

A normal first-boot run must report `passed=true` and `agent_alive=true`, with
all required Windows fields. A quick configuration-only check must leave
`agent_alive=null`. If failure occurs, observe its existing Alertmanager
API/amtool route and the named remediation; do not infer delivery merely from
`OnFailure=` being present. Host installation and the first automatic run are
pending; local fixture/parser checks do not supply that evidence.

## Rollback

After owner safe points and outside paper windows, the co-op disables this new
unit without `--now`, restores the saved unit/runtime files (or removes only
files recorded absent), and runs `daemon-reload`. Do not interrupt a running
check. Preserve its journal and clock evidence. Restore a prior enablement
state only if the backup recorded one. This reverses the Linux integration;
the administrator runbook's `start= delayed-auto` command is the separate,
explicit Windows-startup rollback. No trigger restoration/deletion, task-state
change or manager restart is added.

Sources: [systemd v259.5 service semantics](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.service.xml),
[unit ordering/OnFailure](https://github.com/systemd/systemd/blob/b3d8fc43e9cb531d958c17ef2cd93b374bc14e8a/man/systemd.unit.xml),
[SERVICE_TRIGGER actions, 2021-04-02](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-service_trigger),
and the pinned Microsoft Windows-time sources in the administrator runbook.
