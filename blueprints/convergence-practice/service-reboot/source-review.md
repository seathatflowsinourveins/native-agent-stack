# Upstream reuse and acceptance boundaries

Reviewed September 20, 2026, before any VM trial. The initial protocol is retained
in [plan-initial.json](plan-initial.json); the current plan adds an unchanged
upstream-test prerequisite and explicitly distinguishes the synthetic workload.
Neither plan has a native execution receipt yet.

## Reuse decision

The selected runtime is upstream QEMU, the official Ubuntu cloud image,
Canonical's `cloud-localds`, OpenSSH, systemd and the accepted Dagu executable.
The custom Python code is experiment orchestration and evidence collection; it
does not emulate boot, replace the systemd scheduler, edit Dagu state, or execute
workflow steps instead of Dagu.

Two established VM automation paths were checked before retaining this glue:

| Candidate | Pinned upstream evidence | Fit for this exact experiment |
| --- | --- | --- |
| Lima | [hostagent at d85078f](https://github.com/lima-vm/lima/blob/d85078f54346e5e3ff0b253931a32f30d46dfa02/pkg/hostagent/hostagent.go), [default template](https://github.com/lima-vm/lima/blob/d85078f54346e5e3ff0b253931a32f30d46dfa02/templates/default.yaml) | Provides native VM lifecycle and configurable mounts. The inspected hostagent establishes SSH control and uses SSH-backed requirements and forwarding. This experiment must rule out a postboot SSH login as the source of user-manager startup. Reconfiguring or disabling that agent would need a separate qualification and additional integration. No assertion is made that Lima cannot support another arrangement. |
| vmactions/ubuntu-vm | [README at cc2c039](https://github.com/vmactions/ubuntu-vm/blob/cc2c039c64b223597aac46e0cacc57242f0bd126/README.md), [action definition](https://github.com/vmactions/ubuntu-vm/blob/cc2c039c64b223597aac46e0cacc57242f0bd126/action.yml) | Uses prepared VM images and SSH/source synchronization. Its documented default forwards `GITHUB_*` environment and syncs the source tree; `sync: no` exists. An adaptation would still need to verify image provenance, eliminate runner-state forwarding, and expose this experiment's serial-before-SSH gate. It is not selected for this narrowly isolated proof. |

These are source-review decisions, not comparative benchmarks. Direct supported
QEMU drive/serial/network options and the standard cloud-init seed are the smaller
auditable integration for this selected acceptance condition. Reopen the choice
if an upstream harness exposes the same observation contract directly.

## Primary native coverage: unchanged Dagu tests

The hosted workflow first downloads the exact Dagu source archive for
`58fed633d58c1dd1319091fdb2c2f6158ecfa053`, checks SHA-256
`8f4b1095a88bb037b582f8b5e337360b1702879f1abb9cfc319643ef1a775746`,
and invokes its **unmodified**
[retry_test.go](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/cmd/retry_test.go)
using Go 1.27.0 from upstream [go.mod](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/go.mod):

```sh
go test -count=1 -run '^TestRetryCommand($|_)' -timeout 12m -v ./internal/cmd
```

This is a bounded selection from the native Go suite, not the full Dagu E2E
suite. It includes upstream file-path/name retries, queued retry identities,
explicit working-directory preservation for `--step`, the built-executable
environment-restoration case, and invalid downstream-without-step rejection.
The upstream [CI](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/.github/workflows/ci.yaml)
uses Go tests through `make test-coverage`; this trial uses `go test` directly
for only the named existing tests. Source hashes, actual Go version, command,
complete native output and exit status are retained. Go module checksum
verification remains enabled. No upstream test or expected output is rewritten.

This suite establishes its selected upstream semantics only. The official tests
do not claim this project's kernel-reboot acceptance. The guest trial remains
required after the upstream prerequisite passes, using the separately pinned
release binary; that binary is not silently replaced by the test build.

## Additional synthetic integration assertions

The existing planner and its **12-test synthetic project oracle** are unchanged
inputs for checkpoint continuity. They are not official Dagu tests. The authored
`tests/test_service_reboot.py` cases verify the local evidence contract and failure
rejection; fabricated records in those tests are not native execution evidence.

| Integration assertion | Primary source basis | Required native observation |
| --- | --- | --- |
| Same writable disk across kernel reboot | [QEMU drive and serial options](https://www.qemu.org/docs/master/system/invocation.html) | Changed guest boot ID, same QEMU process start identity, disk inode, guest filesystem UUID and machine identity. |
| User manager starts at boot without login | [systemd v255 loginctl](https://github.com/systemd/systemd/blob/v255/man/loginctl.xml), [timer clocks](https://github.com/systemd/systemd/blob/v255/man/systemd.timer.xml) | Explicit linger; enabled user timer; read-only serial completion and active user manager before the first postboot SSH. |
| Native same-run selected-step retry | [pinned retry command implementation](https://github.com/dagucloud/dagu/blob/58fed633d58c1dd1319091fdb2c2f6158ecfa053/internal/cmd/retry.go), upstream tests above | Original run ID in complete before/after native histories, final native `succeeded`, original checkpoint and claim bytes. |
| Authentic disposable image | [Ubuntu verification procedure](https://ubuntu.com/docs/public-images/public-images-how-to/verify-image-checksum/), [NoCloud](https://github.com/canonical/cloud-init/blob/main/doc/rtd/reference/datasources/nocloud.rst) | Pinned official signed checksum, matching signer fingerprint and image bytes, frozen seed. |
| One local effect and unchanged project workload | Existing [job fixture](../job-recovery/fixture.py) | Original synthetic oracle passes before/after, exclusive claim count one, one exclusive `completed.json`. This is local application behavior, not an upstream or distributed guarantee. |

All sources and original logs remain inspectable. Local green checks do not
promote the protocol into an accepted reboot capability.
