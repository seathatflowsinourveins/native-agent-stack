# Synthetic independent-host restore

The [accepted hosted result](../../../evidence/receipts/native-offhost-restic-20260920.json)
records run35537533416 on September20. Seven unchanged upstream tests and nine
subtests passed without skips. Native `check --read-data` checked two snapshots
and four packs without errors; both exact `restore --verify` operations returned
exit0 and verified six files each. The invalid-password case returned exit12
without restored files. An independent reviewer fetched the GitHub artifact and
matched all24 reports, executed source pins, unchanged ciphertext and both complete
path/type/size/hash/mode manifests against the frozen oracle. The
[retained native outputs](../../../evidence/artifacts/native-offhost-restore-20260920/receipt.json)
remain separate from the [upstream Go test outputs](../../../evidence/artifacts/native-offhost-restore-20260920/upstream-tests.json).
This establishes the synthetic transfer boundary only; application queries,
lost-key/account recovery and production disaster recovery remain unqualified.

The manual-only workflow first runs **seven unchanged upstream restic tests**,
then attempts an independent-host restore of the separately retained synthetic
repository. [Upstream source selection](upstream-source.json) pins restic0.19.1
commit `6aa3a516ce654808a1f28f9fa21e9b7c8e6e90bf`, Go1.25.10, test names,
bundled fixture hashes and the official CI command. Source review and local
Python checks are not execution of those Go tests.

The first [hosted attempt](attempt-1/result.json) failed before any native restic
command: a local wrapper gave its negative-key file and command output directory
the same name. Installation and namespace preflight passed, and cleanup removed
the supplied key. The corrected runner places outputs under `commands/`; its
regression executes the real workspace setup with the unchanged ciphertext.
The original plan, failed receipt and source commit remain recorded. No second
backup or password change is needed.

Local preparation is not hosted acceptance. The workflow result must pass every
native operation and independent oracle before an independent-host claim is recorded.

The earlier [WSL recovery](../wsl-restore/README.md) remains same-host evidence.
Its exact ciphertext could not be located in the bounded selected task records.
This lane therefore creates one new synthetic repository with the unchanged,
corrected WSL preparation script, fixture, transition and independent oracle.
It preserves both historical failures. The source parent is a new neutral
`/tmp/native-foundation-offhost-20260920/preparation`; no client state, personal
files, accounts or existing backups are inputs.

The [plan](plan.json) freezes source, oracle and native binary hashes before
preparation. The later [hosted plan](hosted-plan.json) preserves that plan and
records the successive reviewed hosted corrections and links the previous
hosted plan; it freezes the current sources without repeating preparation.
Native `key add --host synthetic-offhost-restore --user synthetic`
creates neutral plaintext key labels, verifies the exact snapshots through that
new key, then `key remove` removes only the automatically named key from this
new fixture repository. The password does not change. All non-key ciphertext
must remain byte-identical. Export identity is frozen **after** that explicit
native correction; original before/after manifests and raw command streams stay
private. No repository bytes are hand-edited.

`repository.json` is a Base64 text envelope of the native encrypted repository
objects, accompanied by complete path/size/SHA256 metadata. Base64 adds no
encryption. The decoder rejects duplicate, extra, missing, malformed or
path-traversing objects and refuses an existing destination. The repository's
`keys/` record contains the password-encrypted master key, **not the password**.
The task-only password remains a mode0600 private file and is provisioned
separately by the coordinator as repository Actions secret
`FOUNDATION_RESTORE_FIXTURE_20260920`. It is never committed or uploaded.

The workflow has only `workflow_dispatch`, no arbitrary inputs, read-only
repository permission, pinned checkout/upload actions, a 15-minute job limit
and 120-second native command deadlines. It installs the same pinned upstream
restic0.19.1 with the existing signed-checksum installer. No restore-source host
connection, private source path, remote backup account or native client sign-in
is available on the destination. The native commands run in new network and
mount namespaces with an explicit environment, read-only ciphertext/key mounts,
and only an owned output directory writable. Namespace or mode0600-key mapping
failure stops before secret delivery; there is no isolation fallback.

The upstream step follows restic's own `go test -cover` CI entry point with an
explicit seven-test selection, `-count=1`, JSON output and a five-minute test
deadline. It invokes `TestCheckRestoreNoLock`, `TestRestore`,
`TestCheckWithSnaphotFilter` (the upstream spelling),
`TestRestoreWithPermissionFailure`, `TestRestorer`, `TestRestorePermissions` and
`TestRestorerConsistentTimestampsAndPermissions` in `cmd/restic` and
`internal/restorer`. The original tests and fixtures run unmodified in an exact
upstream checkout. Their own temporary repositories and public test passwords
are separate from the retained transfer fixture and Actions secret. All seven
top-level Go test results must be present and pass; skips or absent tests fail
the recorder. Module hashes are checked and the source checkout must stay clean.
This step allows Go dependency downloads and is not called network-isolated.

The evidence types remain explicit: the selected Go tests are
`upstream-unmodified`; the existing Unicode/two-snapshot transfer fixture is
`local-acceptance`; decoding, namespace, cleanup and workspace regressions are
`local-harness-guard`. The local fixture was not copied from upstream. Its native
commands and wrong-password exit12 are referenced to upstream docs/source, while
the complete SHA256-and-mode oracle is locally authored. The source manifest
maps each assertion without retroactively labeling it an upstream test.

For the exact snapshot IDs frozen in `input.json`, native operations are:

```sh
restic --no-cache --no-lock --repo /repository --password-file /secret/password \
  check --read-data
restic --no-cache --no-lock --repo /repository --password-file /secret/password \
  restore "$EXACT_SNAPSHOT:$FROZEN_SOURCE_PARENT" --target /out/restore --verify
```

`--no-lock` allows these read-only operations on the immutable owned repository;
it is not a recommendation for a concurrently modified production repository.
Before the correct-key operations, a fixed unrelated password must return native
exit12 with no restored files. Each restore selects the **parent** subtree so
`fixture` itself retains mode0750. The independent Python oracle checks the
complete path set, file types, lengths, SHA256 hashes and POSIX modes, including
all seven directories and six files in each snapshot. It checks the
changed/deleted/added transition against the original frozen expected manifests,
not expected values derived from the restored result. UID/GID, timestamps,
ACLs, xattrs, sparse files and links are outside this oracle.

All ciphertext hashes are compared before and after every native operation.
Only sanitized reports are uploaded; raw stream hashes and explicit source-user
sanitization remain visible. Namespace IDs establish the observed local boundary;
the GitHub run ID, source commit and hosted-runner record establish destination
provenance. The recorder removes its newly created decoded repository, restored
files and wrong password. A separate always-run step removes the Actions-secret
file; the owned installation and public reports live until runner disposal.

This can qualify independent-host recovery of this synthetic repository with a
separately delivered available password. It cannot qualify reboot, power loss,
production disaster recovery, loss of the GitHub account, long-term retention,
lost-password recovery, Windows filesystems, native credential recovery or
independence from GitHub as the common hosting and secret-management provider.
ai-memory, Qdrant and application-query recovery remain untested here.
Git and Actions secrets are separate delivery channels within the same account,
not independent administrative trust domains.

Offline checks (no password reads or native restore):

```sh
python3 -m unittest tests.test_wsl_restore tests.test_offhost_restore -v
```

Upstream references: [exact snapshot/subfolder restoration](https://restic.readthedocs.io/en/stable/050_restore.html),
[full repository data checks](https://restic.readthedocs.io/en/stable/045_working_with_repos.html),
[native key management](https://restic.readthedocs.io/en/stable/070_encryption.html),
[password sources and exit12](https://restic.readthedocs.io/en/stable/075_scripting.html),
[GitHub-hosted fresh VMs](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners),
and [separate Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
