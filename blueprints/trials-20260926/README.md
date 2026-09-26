# P1 trial batch (2026-09-26)

Native trials of the three P1 candidates from the 2026-09-26 SOTA-gap audit on
the workstation `nativestack-5975wx-20260925` (`linux-wsl2-x86_64`). The trials'
own processes were meant to run on CPU, and model calls went to the host's local
OpenAI-compatible endpoints. There is one exception: three first-pass ColPali
runs had no device pin, and their timings indicate the GPU (`colpali/` finding
5). The ten P2/P3 candidates of the same audit are registered in
`manifests/candidates.json` without trials (#315).

| Trial | Measured | Blockers | Folder |
| --- | --- | --- | --- |
| MIRIX `v0.1.6` (+ `main@8cb06a62`) | No memory persisted through the documented add/retrieve path against local endpoints at either pin; upstream suite at the tag: 88 passed, 1 failed, 88 skipped, 16 errors | F1 (v0.1.6), F2 (both pins), F3/F5 (main quick start); upstream eval harness needs a cloud key and is main-only | [`mirix/`](mirix/) |
| ByteRover CLI `3.16.1` | Offline store/retrieve (`brv vc` + BM25 `brv search`) works with no LLM or account, with discriminating controls; upstream suite 8340 passing / 16 pending / 0 failing; LLM path not evaluated end to end: observed request totals 12,351 and 11,192 tokens exceeded the host llama.cpp context of 8192. `brv restart` sends SIGKILL to matching ByteRover processes host-wide; the earlier reproduction runs and the host cleanup ran it (`byterover-cli/README.md#brv-restart-in-earlier-runs`). Licence: Elastic License 2.0 | LLM path needs more context than the shared host service provides; published benchmark numbers have no runnable harness | [`byterover-cli/`](byterover-cli/) |
| ColPali / ViDoRe (`colpali-engine` 0.3.13 + `vidore-benchmark` 5.0.0) | `colpali-v1.3` nDCG@5 0.89682 vs random control 0.19678 on a 12-image TabFQuAD slice, CPU, reproduced self-contained | `colqwen2.5-v0.2` not evaluated: the 5.0.0 CLI registers no ColQwen2.5 retriever, the documented 5.0.0 Python API path is untried, and its processor at the pinned Hub revision does not load within colpali-engine 0.3.13's transformers range; PyPI-latest colpali-engine does not co-install with vidore-benchmark 5.0.0; CPU throughput | [`colpali/`](colpali/) |

**Layer decisions are not made here.** Each trial records measured results,
facts and blockers. Adoption into a layer is decided when that layer is
re-recorded by its own verdict wave (`tools/sota-convergence/record_verdicts.py`,
see `docs/contributing-evidence.md` section 4). The candidate rows in
`manifests/candidates.json` carry the trial status and point here.

Each trial folder has a `README.md`, a machine-readable `results-20260926.json`,
a `retained-outputs.json` manifest (every retained file with its evidence class,
the private original's sha256 and size, the published sha256 and size, and every
sanitization rule applied), a `source-review.json` of pinned upstream source
lines, and the retained files themselves. This folder's own
[`retained-outputs.json`](retained-outputs.json) covers the pin checks and the
host cleanup.

## Evidence classes

`upstream_test`, `upstream_native_operation`, `local_integration`,
`independent_observation` and `structural_validation` are the classes of
`docs/acceptance-evidence-policy.md`; the other labels name the remaining kinds
of retained file in this batch:

| Label | Meaning here |
| --- | --- |
| `upstream_test` | An unchanged upstream test suite at the pinned revision, run with its documented command |
| `upstream_native_operation` | Output of the upstream tool's own commands, logs or stored records |
| `local_integration` | Output of our own glue around upstream (wrappers, checkers, reproduction steps); its pass/fail rule is ours, never an upstream test |
| `local_integration_source` | Source of that glue |
| `source_review` | Pinned upstream source lines (commit, path, lines, blob id, file sha256); inspection, not execution |
| `registry_observation` | PyPI, npm or Hugging Face Hub API responses |
| `host_service_observation` | A read-only query of a host service |
| `independent_observation` | A separate-method check of host state around a run |
| `structural_validation` | This repository's validators |
| `withdrawn_host_receipt` | A first-pass host receipt removed from `evidence/hosts/`, kept byte-for-byte |
| `skipped_receipt_spec` | A first-pass receipt spec never recorded because its dry run failed |

## Why there are no host receipts

`docs/contributing-evidence.md` (section 3, step 3) accepts a receipt's
`--component-id` only when it is a `manifests/stack.json` component or a
`catalogs/landscape/*.json` winner, and `scripts/host_receipts.py validate`
rejects any other id. None of `mirix`, `byterover-cli`, `colpali-engine` or
`vidore-benchmark` is either; making one a stack component or a winner is the
verdict wave's decision, not a trial's. The first pass had recorded eight such
receipts on an older base; restored into a copy of the current tree, the
validator rejects exactly those eight
([`withdrawn-host-receipts-validate.txt`](withdrawn-host-receipts-validate.txt)).
They were therefore not re-recorded. They are kept byte-for-byte under each
trial's `withdrawn-host-receipts/` with the reason, and the evidence they
pointed at is retained as sanitized native output here instead. Their commands
also depended on `/tmp/nas-*` symlinks into this session's scratch directory;
nothing retained here depends on scratch state.

The two MIRIX v0.1.6 attempts that the first pass's recorder skipped because
they failed (the use quickstart and the pinned-tag pytest: 1 failed, 16 errors)
cannot be fail receipts for the same reason. They are preserved in
[`mirix/skipped-receipt-specs.json`](mirix/skipped-receipt-specs.json) together
with the retained outputs of the same commands.

## Pins

[`provenance/verify-pins.sh`](provenance/verify-pins.sh) re-verifies every source
and artifact pin the trials cite: fresh tag clones (`git rev-parse`), commits
fetched by id, PyPI-reported and downloaded sha256, npm `dist.integrity` and
`dist.shasum`, Hub revisions and the Hub config fields behind the colqwen2.5
finding; two deliberately wrong expectations must fail.
[`provenance/run-20260926T045856Z/`](provenance/run-20260926T045856Z/verify-pins.log)
met every expectation. The first run
([`run-20260926T045833Z-attempt1/`](provenance/run-20260926T045833Z-attempt1/), kept
with the script it used) had a verifier defect: its Hub field rows passed with
empty values because it did not follow the Hub's redirect or fail on an
unparsable file.

[`provenance/source_excerpts.py`](provenance/source_excerpts.py) produced each
trial's `source-review.json` from fresh fetches of the named commits.

## Host state

### Removed by the port (2026-09-26 04:53Z, [`host-cleanup-20260926/`](host-cleanup-20260926/))

The script asserted each literal target first (plan mode, no changes), then:

| Target | How |
| --- | --- |
| ByteRover stored local-provider key | `brv providers disconnect openai-compatible --format json` (exit 0), then `brv logout` and `brv restart` (exit 0); credential files were only stat-ed, never read. That `brv restart` scanned every process in this WSL distribution and sends SIGKILL to any ByteRover client, daemon or agent it finds, from any install; whether another session's process was hit cannot be ruled out ([`byterover-cli/README.md#brv-restart-in-earlier-runs`](byterover-cli/README.md#brv-restart-in-earlier-runs)) |
| `~/.local/share/codex-ecosystem/tools/byterover-cli-3.16.1` | `npm uninstall --global --prefix <that prefix> byterover-cli` (exit 0, 778 packages), then the emptied directories |
| `~/.local/share/codex-ecosystem/bin/brv` | symlink removed after asserting it pointed into that prefix |
| `~/.config/brv`, `~/.local/share/brv`, `~/.local/state/brv`, `~/.cache/brv` | removed (ByteRover's documented XDG locations; config, projects, encrypted provider keychain, logs, cache). Their task records, logs and autoupdate log were copied into `byterover-cli/` first |
| `~/.config/configstore/update-notifier-byterover-cli.json` and the then-empty `~/.config/configstore` (created during the trial) | removed |
| `/tmp/nas-mirix-trial`, `/tmp/nas-colpali-trial` | symlinks removed after asserting they pointed into the trial scratch directories |
| Three MIRIX trial servers still running from the first pass (ports 18531, 18000, 18533, bound to all interfaces) | `SIGTERM` to the three literal PIDs after asserting their command lines and working directories; all exited, ports closed |

After the cleanup, a self-contained ByteRover reproduction ran with every
ByteRover path redirected into its workspace; the host paths above were absent
before and after it
([`byterover-cli/reproduction/run-20260926T0454Z/host-state-observation.txt`](byterover-cli/reproduction/run-20260926T0454Z/host-state-observation.txt)).
That run also ended with `brv restart`. The current reproduction
([`byterover-cli/reproduction/run-20260926T1131Z/`](byterover-cli/reproduction/run-20260926T1131Z/))
stops only the daemon and agent it recorded, and the host paths were again absent
before and after it.

### Removed by the first polish pass (2026-09-26 06:39Z, [`first-pass-scratch-trees/`](host-cleanup-20260926/first-pass-scratch-trees/))

Session scratch directories are not removed automatically. At 06:39Z this
session's scratch root still held the directories of 12 other sessions from
2026-09-24 and 2026-09-25. The first pass's own working trees in this session's
scratch directory were therefore deleted. Before the deletion, the facts that
retained evidence still needed were captured from them: the PostgreSQL and
pgvector versions bundled with pgserver, the mirix 0.1.7 wheel listing, the
attribution of `~/.cache/mteb` and the pgserver runtime directory, and the trees'
sizes. The script asserted each literal target first (a real directory resolving
to itself, used by no process; plan mode), then deleted it and checked it was
gone.

| Target | Apparent size before |
| --- | --- |
| `<scratch>/trial-colpali` | 31,053,661,034 bytes: Hugging Face cache 15.1 GB, three venvs 19.6 GB |
| `<scratch>/trial-mirix` | 985,386,322 bytes: two venvs, and an 85 MB PostgreSQL data directory |
| `<scratch>/trial-byterover` | 19,121,145 bytes |
| `<scratch>/exec` (the receipt recorder's working directory) | 54,849 bytes |

Its post-deletion inventory
([`host-state-inventory.txt`](host-cleanup-20260926/first-pass-scratch-trees/host-state-inventory.txt))
missed two things. One is the ByteRover suite's `/tmp` residue. The other is the
hf_xet log in the table below.

### Still on the host

This is the batch's host state as of the final inventory
([`remaining-host-state/host-state-inventory.txt`](host-cleanup-20260926/remaining-host-state/host-state-inventory.txt),
taken by the read-only
[`inventory-remaining.sh`](host-cleanup-20260926/remaining-host-state/inventory-remaining.sh)).
Everything here is trial-owned. The polish passes may change only this session's
scratch directory, so the paths outside it were inventoried, not deleted.
Removing them needs the coordinator's approval. None of the commands below has
been run.

| Path | Size | Origin (evidence) | Removal |
| --- | --- | --- | --- |
| `~/.cache/huggingface/hub`: `models--vidore--colpali-v1.3`, `models--vidore--colpaligemma-3b-pt-448-base` and their `.locks` entries (11 lock files) | 5,962,852,003 bytes (113 MB + 5.85 GB) | The first pass's unpinned-device ColPali runs (no `HF_HOME`) created the whole `hub` directory at 02:43:55Z; `hf cache ls` lists exactly these two repositories | `hf cache rm model/vidore/colpali-v1.3 model/vidore/colpaligemma-3b-pt-448-base --dry-run`, then with `--yes` (the host's `hf` is 1.32.0). Then `rm -r -- ~/.cache/huggingface/hub/.locks/models--vidore--colpali-v1.3 ~/.cache/huggingface/hub/.locks/models--vidore--colpaligemma-3b-pt-448-base` and `rmdir ~/.cache/huggingface/hub/.locks ~/.cache/huggingface/hub`, which fails safely if anything else has appeared there |
| `~/.cache/huggingface/xet/logs/xet_20260925T224355622-0400_3896841.log` | 197,286 bytes | hf_xet's log of that download: born 02:43:55Z in the same second as `hub`; 4 of its lines name vidore. The `xet` directory itself dates from 2026-09-24 and is not trial-owned | `rm -- <that file>` |
| `~/.cache/huggingface/datasets`: `local-tabfquad-subset/` and `_home_<user>_.cache_huggingface_datasets_local-tabfquad-subset_default_0.0.0_151538e80d111958.lock` | 10,907,450 bytes | The `datasets` cache of the local 12-row slice; the directory was created at 02:14:42Z | `rm -r --` the two literal entries, then `rmdir ~/.cache/huggingface/datasets` |
| `~/.cache/mteb` (empty) | 0 | Created at 01:29:06Z when the first pass's ColPali venv first imported mteb 2.21.8, whose import builds its default result cache ([attribution](host-cleanup-20260926/first-pass-scratch-trees/host-state-attribution.txt)) | `rmdir ~/.cache/mteb` |
| `~/.mirix` | 344,628 bytes (config, SQLite database, `tmp/`) | MIRIX's default `mirix_dir` (`mirix/source-review.json#host-state-mirix-dir`), created at 01:30:29Z | no uninstall command: `rm -r -- ~/.mirix` |
| `/run/user/<uid>/python_PostgresServer` (`.lockfile` and the empty socket directory `2dcf3c6d23`) | 0 | pgserver 0.1.4's runtime directory, created at 01:29:36Z; `2dcf3c6d23` is pgserver's hash of the deleted trial cluster's path and inode ([attribution](host-cleanup-20260926/first-pass-scratch-trees/host-state-attribution.txt)) | `rm -r -- /run/user/$(id -u)/python_PostgresServer`. This is tmpfs, cleared when the user's last session ends |
| `/tmp`: 498 directories `brv-consolidate-test-*` (112), `brv-synthesize-test-*` (115), `brv-undo-test-*` (103), `brv-prune-test-*` (96), `migrate-fm-*` (44), `brv-path-test-*` (12), `brv-projdir-test-*` (12), `folder-pack-executor-*` (4); plus `brv-test-blobs`, `brv-test-storage` and `byterover-tool-outputs` (22 files) | about 480 KB | ByteRover 3.16.1's unchanged upstream unit tests create these under `os.tmpdir()` and never remove them; for example, `consolidate.test.ts`'s `afterEach` only restores stubs (`byterover-cli/source-review.json#suite-tmpdir-*`, `#suite-fixed-tmp-paths`, `#tool-output-temp-dir`). They were born in four clusters, one per suite run: the first pass's run at 01:35Z, its self-contained rerun at 01:45-01:46Z, and the receipt recorder's dry run at 03:04Z and recorded run at 03:07-03:08Z | List first: `find /tmp -mindepth 1 -maxdepth 1 -user "$(id -u)" \( -name 'brv-consolidate-test-*' -o -name 'brv-synthesize-test-*' -o -name 'brv-undo-test-*' -o -name 'brv-prune-test-*' -o -name 'brv-path-test-*' -o -name 'brv-projdir-test-*' -o -name 'migrate-fm-*' -o -name 'folder-pack-executor-*' -o -name brv-test-blobs -o -name brv-test-storage -o -name byterover-tool-outputs \) -print`, which must print exactly these 501 entries. Then run the same command with `-exec rm -r -- {} +` in place of `-print` |

In this session's scratch directory (`<scratch>`), these remain:

| Path | Size | What | Removal |
| --- | --- | --- | --- |
| `<scratch>/wt-trials` | 117,860,321 bytes | The first pass's git worktree (branch `claude/p1-trials-mirix-byterover-colpali-20260926`, 11 uncommitted entries), the unmerged work this change supersedes | `git worktree remove --force` and deletion of the branch. That is the coordinator's call, because these passes may not run git worktree commands |
| `<scratch>/trials-2` | 193,239,378 bytes | The port's working tree: private originals of its retained outputs, reproduction staging and pinned source checkouts | `rm -r` of the literal directory once this change is merged; nothing removes it automatically |
| `<scratch>/trials-pol` | 33,951,472 bytes | The polish passes' working tree: private originals of their outputs, the probe's private `HF_HOME`, and the regenerated source reviews | the same |
| `<scratch>/wt-trials2` | 135,766,227 bytes | This change's worktree | after integration |

Shared caches keep entries the trials downloaded (`~/.npm`, `~/.cache/uv`). They
are content-addressed caches used by other work and were left as they are.

## Differences from the unmerged first pass

The first pass (on an older `main`) wrote the three trial READMEs and results
files, eight host receipts, and three candidate rows. This port keeps its
measurements and fixes what the program review, the GPT-6 cross-family review
of ByteRover and the coordinator found: receipts withdrawn (above); verdicts
restated as measured results and blockers without incumbency reasons; the
skipped MIRIX attempts preserved; host state cleaned; a leaked UUID removed;
the ColPali `reviewed_commit` identified and verified; the ColPali duration gap
explained (the short runs were GPU-indicated, finding 5 in `colpali/`); the
ByteRover grep check, exit-code claim, fixed-token claim and telemetry label
corrected; and several first-pass statements corrected against the retained
outputs (listed in each trial's README).

## Polish passes

Two polish passes applied an independent review of the port:

- **Committability.** A registered evidence file matched the `*.jsonl` ignore
  rule, so a commit would have left it out while local validation still passed.
  It is now `byterover-cli/native-outputs/curate-context-error.ndjson`.
  `scripts/validate.py` now rejects any hash-listed file that Git ignores and
  does not track; the regression test is in `tests/test_validate.py`.
- **colqwen2.5.** The blocker is restated to match what was measured: the CLI
  registry has no ColQwen2.5 retriever; the documented Python API was not tried;
  the processor-load failure was traced, by a probe and by pinned source, to the
  Hub's chat-template file and transformers' double `.jinja` suffix. The
  re-trial trigger now includes the Python API.
- **Host state.** The record above lists what actually remains. That includes
  state the port's record missed: the pgserver runtime directory,
  `~/.cache/mteb`, the hf_xet log and the ByteRover suite's `/tmp` residue. The
  first pass's scratch trees were deleted.
- **Numbers.** Per-batch CPU times replace tqdm's smoothed rates. The peak RSS
  is 42.7 GB, because GNU time reports KiB. The unsupported "killed by
  `timeout 1700`" ending was withdrawn.
- **Evidence classes and sanitization.** The npm registry response, our tarball
  digest and our GNU time reports now carry their correct classes. The
  maintained reproduction and provenance sources now have records. A user name
  inside an underscore-encoded cache path was redacted.
- **Claims.** "CPU only" was corrected. The PostgreSQL 16.2 and pgvector 0.6.2
  versions and the "mirix 0.1.7 is a REST client only" statement now cite
  captures made before the first pass's trees were deleted. The uncited
  "753 of 899" main-suite count was removed.
