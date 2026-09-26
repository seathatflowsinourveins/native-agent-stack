# Synthetic application-state recovery across hosted jobs

This manual-only workflow composes native ai-memory, Qdrant and Restic operations.
[Hosted run35541091430](https://github.com/seathatflowsinourveins/native-agent-stack/actions/runs/35541091430)
passed on source revision `2e7b4624b85a828be11752238e2806efa420ba3c`.
Independent review reconciled the original artifacts, 144 command-stream hash
bindings, native application responses and cleanup. The
[accepted receipt](../../../evidence/receipts/native-offhost-app-state-20260920.json)
retains exact upstream commands and results: ten unchanged ai-memory tests and
four unchanged Qdrant tests passed, with no failed or skipped cases.

The fresh destination returned exact scoped memory bodies and refusal/search
results, plus all ten Qdrant points, vectors, payloads, configuration, indexes,
alias and three ranked queries. This is synthetic application recovery across
two hosted boot identities. Production data, client rebinding, cross-application
atomicity, lost-account/key recovery and physical-host disaster recovery remain
outside this acceptance. Local guard tests remain separately labelled.

The current plan's workflow hash includes the separately qualified setup-python
Action update from PR31. The accepted run retains its original execution head and
plan digest in the receipt and captured freeze records; this prospective pin
refresh does not claim a new recovery execution or rewrite historical evidence.
Changed after `v2026.09.26.2`: a second such refresh on 2026-09-26 adds
`step-security/harden-runner` in audit mode as each job's first step and exact-release
Action comments; the next dispatch is the first run with that step
([decision](../../../docs/decisions/2026-09-26-token-workflow-hardening.md)).

[plan.json](plan.json) freezes the scope, source inputs, independent query
expectations, key flow, finite deadlines and failure conditions. The workflow is
[native-offhost-app-state.yml](../../../.github/workflows/native-offhost-app-state.yml).
The source job and dependent destination job each receive a new GitHub-hosted
Ubuntu24.04 runner. The destination requires the same workflow run/head, a
different boot identity and the exact source-record checksum passed as a job
output. Independent review must reconcile both platform job records with the
returned native outputs; the wrapper's status alone is insufficient.

## Existing upstream and local building blocks

- ai-memory2.3.2 source353841d91618d20b110b208de284a74d0b960379: four unchanged
  native admin-backup tests and six archive-validation/extraction tests. The
  latter do not themselves establish a usable restored database. GNU tar and
  gzip are required so the sparse test cannot silently return without exercising
  its body. Exact commands/test names and source hashes are in
  [upstream.json](upstream.json). Rust1.95.0 and the upstream Cargo.lock are used.
- Qdrant1.19.1 source6ab21cac18ebb6f4ae29102c7f8f5cc11affd5de: unchanged
  `test_collection_snapshot_operations` and `test_full_snapshot_operations`,
  each with both upstream on-disk-vector parameters: four cases. They run
  against the verified GNU release binary, a documented adaptation of upstream
  CI's debug build. The full test checks snapshot creation/list/delete; our
  destination phase supplies full-storage restore/query evidence separately.
- The unchanged Qdrant `basic_collection_setup` seeds ten public points. The
  [frozen oracle](qdrant-oracle.json) retains every dense/sparse vector and payload,
  plus independently computed dense, Berlin-filtered and sparse query results.
  Our composition adds two payload indexes and one alias, and queries the actual
  alias after restoration. Native source/destination responses must match
  exactly. The independent fixture comparison additionally maps the documented
  dense array/map alternatives and float32 scalars; it does not omit vectors.
- The existing [Linux memory runner](../wsl-memory-maintenance/run.py) is staged
  unchanged with its pinned release/config and [corrected Linux oracle](memory-oracle.json).
  Its accepted native MCP, loopback backup client, restore and scoped-query
  operations produce the source archive. Inherited Mac/migration wording is
  removed before freezing. All old receipts remain unchanged.
- Existing [Restic installer](../wsl-restore/install.py) verifies signed release
  checksums. The [ciphertext decoder](../offhost-restore/verify.py) preserves exact
  native encrypted bytes and rejects unsafe, duplicate, extra or changed members.

The upstream tests run first and are reported separately. The cross-host fixture,
source/destination oracle, added indexes/alias and artifact guards are local
integration checks, not unchanged upstream tests.

## Key, data and execution boundaries

Both jobs independently receive the existing fixture-only Actions secret
`FOUNDATION_RESTORE_FIXTURE_20260920`. Each writes one new private0600 file;
native commands receive its path, never its value in arguments or reports.
No account credentials or existing user database are read. The temporary memory
HTTP bearer is generated by the existing fixture and is not an account credential.
The exported native archive may contain only the frozen secret-free configuration.
Proof selection permits flat native command/protocol files only, rejects nested
application/authentication state and known passwords or bearer/auth-key values.
Public streams additionally redact authentication-shaped values. A detected
credential prevents proof export and fails the job.

The source encrypts only its new native memory backup and Qdrant full snapshot.
Its exact snapshot ID, original archive hashes, ciphertext manifest and public
application oracle are frozen before upload. Native key add/remove creates
neutral public key-record labels; it does not edit encrypted repository objects.
The password is never uploaded with those objects. GitHub artifacts and Actions
secrets still share one administrative account; this is not account-loss recovery
or an independent trust-domain claim.

The destination rejects an incorrect key, performs `restic check --read-data`,
restores the exact snapshot with `--verify` into an empty target, and checks both
native archive hashes. It then uses ai-memory `restore --from` without force,
opens the restored native stdio server and repeats exact bodies, FTS, scope
negatives, obsolete-marker absence and capture-off SQLite checks. Qdrant starts
with `--storage-snapshot` and fresh storage; `storage.temp_path` is deliberately
omitted, preserving the earlier collision diagnosis. Complete points, vectors,
payloads, collection configuration, schemas, aliases and queries must match.

Application servers bind loopback. The unchanged Qdrant test helper binds all
addresses, so the upstream test and its Qdrant process run together in a new
network namespace with loopback only, after dependencies have been fetched.
This is a scoped network boundary, not a general filesystem sandbox. Child
environments exclude provider credentials; the memory config disables providers,
history capture, embeddings and background maintenance. Only owned processes
receive cleanup signals. A timeout, refusal, failed oracle or forced application
cleanup remains a failed attempt, never an unchanged retry.

## Evidence and review

Each command retains argv, working directory, timestamps, deadline, result and
complete stream hashes. Public text substitutes owned paths and runner identity;
the original synthetic streams are recoverable from a separately encrypted proof
repository. The proof contains no password file or application authentication
files. Cleanup removes the delivered password and disposable application state;
only explicitly selected ciphertext and reports are uploaded. Failed phases also
retain their reports, with sealing and cleanup attempted separately.

An independent reviewer should check platform source/destination identity, source
and binary hashes, all fourteen unchanged-test results and absence of skips,
archive/ciphertext identity, native CLI returns, real query outputs against the
fixed oracles, and cleanup. Decrypt raw proof only through the separately supplied
fixture key when needed; never publish the key or unsanitized runner metadata.

This qualifies only synthetic application usability across fresh hosted jobs.
It does not qualify production state, client rebinding, reboot, atomic multi-app
backup, long-term retention, lost-key/account recovery or provider savings. The
older private application-state receipts remain same-host evidence.

Offline checks:

```sh
python3 -m unittest tests.test_offhost_app_state -v
zizmor --offline --no-config --no-ignores --no-progress --persona regular --strict-collection --format json .github/workflows/native-offhost-app-state.yml
```
