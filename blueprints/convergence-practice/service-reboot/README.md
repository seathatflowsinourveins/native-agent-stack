# Owned guest user-service reboot acceptance

The [third hosted run](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35540304328)
passed and was independently verified. The [native receipt](../../../evidence/receipts/native-service-reboot-20260920.json)
links actual upstream test output, native retry/history, serial observations,
journal timing and cleanup. It qualifies one orderly disposable guest reboot.
Exactly one checkpoint execution and one completed effect survived; the observer
finished before the first postboot SSH. This does not qualify a physical PC or
production workload. The original protocol and both failed attempts remain below.
The [first hosted attempt](prior-attempts.json) passed the unchanged upstream
Dagu tests but failed before guest boot because QEMU8.2.2 rejected `serial` on
the qcow2 backend. Its original freeze, launcher, error, cleanup and plan remain
retained in [attempt-1](attempt-1/). The launcher correction places the serial
on an explicit `virtio-blk-pci` device connected to the same named disk backend;
mandatory native device-help validation runs before the next guest launch.
Local regression tests do not establish that the guest can reboot or recover.
The [second hosted attempt](attempt-2/publication.json) performed a real reboot
and automatically completed the native Dagu retry, but the observer's serial
write failed with `EIO`. The required live postboot observation and final host
audit were missing, so that attempt remains failed. Its journal places the
observer before serial-getty on the second boot; systemd's getty can hang up
other users of the same terminal. The correction assigns the observer a dedicated
`ttyS1` serial port and retains the `ttyS0` boot console separately. It does not
change the workload, acceptance criteria or deadline. Retrospective diagnostic
success cannot substitute for the required pre-login observation.
The manual-only `Native owned guest service reboot` workflow is the execution
entry point; the coordinator dispatches it after reviewing the frozen patch.
Its first job runs unchanged upstream Dagu native retry tests from the pinned
source archive; the guest job requires that prerequisite to pass. The bounded
[upstream reuse review and assertion map](source-review.md) explains the official
coverage and why this experiment uses direct QEMU/cloud-init integration.

The trial creates one disposable Ubuntu 24.04 guest on a standard hosted Ubuntu
runner. It verifies the dated official cloud image against the pinned SHA-256,
Ubuntu's signed checksum list and cloud-image signing fingerprint. Dagu 2.16.6
reuses the previously accepted archive and executable hashes. QEMU runs under
TCG with a loopback SSH forward, restricted guest networking, a task-only public
payload and an ephemeral key. Runner credentials, repositories, native account
stores, host shares and provider credentials are never mounted in the guest.

The guest has an explicitly lingering task user and an enabled systemd user
timer. `native-reboot.timer` is the scheduler. Its service uses supported native
Dagu `start`, `history` and selected-step `retry --step finalize` commands. The
existing Dagu history-server example is not used and is not a scheduler.
The user service relies on the disposable guest and owned account boundary;
it does not claim a user-namespace filesystem sandbox.

Before the reboot, the unchanged project planner and original synthetic 12-test oracle
produce the unchanged job fixture's exclusive checkpoint claim and durable
checkpoint with execution count one. The native finalizer publishes its waiting
marker. A read-only system observer reports that durable state to the serial
port. The runner then requests **only that guest's orderly kernel reboot** over
SSH. The same QEMU process and writable disk remain in place throughout.

After boot, linger starts the user manager and its enabled timer. The service
checks the changed boot ID, persistent guest identity and frozen source hashes,
then invokes Dagu's selected-step retry with the original native run ID. It
requires native success, unchanged checkpoint/claim bytes, all original 12
tests passing again, and exactly one exclusive local `completed.json` effect.
The observer reports completion and active user-manager/linger state on the
dedicated `ttyS1` serial channel; `boot-serial.log` retains the `ttyS0` console.
**No post-reboot SSH probe or login occurs until that observation.** SSH then
collects the original before/after native histories, task logs and journal.
The guest explicitly enables persistent journaling before workload startup and
retains the journal's boot list alongside both boots' service output.

The driver freezes source, plan, runtime, image, seed, workload and oracle hashes
before launching the VM. The guest freezes its Python runtime and native
configuration before starting Dagu. A separate host audit checks the retained
native history, serial records, original source hashes, count and oracle logs.
The QEMU process identity includes its Linux process start time; the disk inode,
filesystem UUID, machine-ID hash and disk token establish the scoped continuity.

Failure is terminal for that attempt. A failed-only, bounded diagnostic SSH path
may collect available task logs after writing `failure.json`; it can never turn
that attempt into a pass. Failed SSH output and timeouts are preserved. Cleanup
retires only the owned QEMU process and removes its staged disks and private key.
The workflow retains reports on both success and failure. Both archive paths
exclude Dagu's generated authentication directory; native histories and task
artifacts remain included. The second attempt's original diagnostic archive is
kept private because it included a generated fixture key; the public projection
records the original artifact identity, hashes, explicit selection and substitutions.
Its 30-minute bound
includes installation and the driver's 1,200-second deadline; failure diagnostics
and cleanup have an additional bound of 80 seconds.

Additional local synthetic integration verification, without a VM, installation
or model (these are not official Dagu tests or native reboot acceptance):

```sh
python3 -m unittest tests.test_service_reboot tests.test_job_recovery -v
python3 scripts/validate.py
```

The frozen [plan](plan.json) records the reviewed primary sources and exact pins.
[Ubuntu's verification procedure](https://ubuntu.com/docs/public-images/public-images-how-to/verify-image-checksum/)
provides the image signature trust anchor. [QEMU's invocation reference](https://www.qemu.org/docs/master/system/invocation.html)
documents persistent drives, acceleration and loopback forwarding. The supported
[NoCloud seed format](https://github.com/canonical/cloud-init/blob/main/doc/rtd/reference/datasources/nocloud.rst),
[systemd linger](https://github.com/systemd/systemd/blob/v255/man/loginctl.xml),
[user timer clocks](https://github.com/systemd/systemd/blob/v255/man/systemd.timer.xml)
and [pinned Dagu retry implementation](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/cmd/retry.go)
were inspected for these specific interfaces.

Acceptance would cover this orderly guest reboot only. It would not qualify an
existing desktop, physical PC, power loss, native model/session recovery,
provider or broker operations, arbitrary production workloads, or distributed
exactly-once effects. This no-model fixture makes no token-savings claim.
