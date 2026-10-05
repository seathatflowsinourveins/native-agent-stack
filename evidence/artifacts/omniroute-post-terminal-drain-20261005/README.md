# Why a client that closes right after the terminal event left no call_logs and no usage_history row, and the drain patch, 2026-10-05

Evidence for the update of 2026-10-05 (evening) in [`docs/decisions/2026-10-05-omniroute-gateway-composition.md`](../../../docs/decisions/2026-10-05-omniroute-gateway-composition.md). The patch is tested in a scratch tree built from public refs;
its build, review and deployment are tracked in the decision record. Host paths are masked (`DRAIN_DIR`, `REPO_WORKTREE`); the metadata-only reads of the gateway store name no credential, connection or body.

| File | What it is | Class |
| --- | --- | --- |
| `checks/pre-patch-repro-20128.txt` | the reproduction on NativeStack's 20128 (PR 15167 head `f5d8e150b`): a raw streaming client that reads to the end is logged, one that closes at the line with `response.completed` is not (twice), one that closes 0.5 s later is, and a native `codex exec -p omniroute` turn leaves no row; rows read with `mode=ro` (timestamp, path, status, model, token counts) | `local_integration` (our clients, the live gateway's metadata) |
| `checks/source-lines.txt` | the upstream lines that cause and bound the drop, verbatim and line-numbered at `0585aba55`, and the same files at release/v3.8.52 | `source_review` |
| `patches/drain-after-terminal.patch` | the patch as `git format-patch` (sha256 `d8eab39308cc9142426ae6f44513a09bb58c7c4cc773f00c912c26c0da09ac5e`): `cancel()` drains the upstream tail when the client already has the terminal event (the reference implementation is upstream's `drainCompletedToolHandoff`), plus the test file `tests/unit/stream-terminal-seen-client-disconnect.test.ts` | our change, cited glue |
| `checks/drain-prototype-results.txt` | the prototype's progress log (byte for byte) and per-test lines: baseline of 236 stream-related test files, the new test on the unpatched tree (negative control), on the patched tree, the same files again, and the call-log, usage-history and chat-pipeline tests | `local_integration` (upstream test runner on a tree built from public refs) |
| `scripts/drain-prototype.sh.txt`, `scripts/build-drain.sh.txt`, `scripts/stream-close-repro.py.txt`, `scripts/native-exec-compare.py.txt` | the prototype, the build, the raw-client reproduction and the native `codex exec` comparison as they ran, with `.txt` appended and host paths masked | our tools |

Rerun the prototype: `DRAIN_DIR=<directory with the test file> EV=<evidence/artifacts/omniroute-wire-effort-20261005 of this repository> scripts/drain-prototype.sh.txt` needs a bare mirror of OmniRoute (v3.8.51 and PR 15167's head) at the path the script names.
The reproduction scripts talk to a running gateway on 20128 with the documented loopback placeholder key.

Limits: the 1 failing test of the 236 stream-related files (`repository provider asset manifest covers the audited 141-file snapshot`) fails identically before and after the patch and was not investigated; the live acceptance after deployment, the build
record and the cross-family reads are added to this folder and to the decision record as they happen.
