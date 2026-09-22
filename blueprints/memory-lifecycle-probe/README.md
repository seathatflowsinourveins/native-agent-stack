# Tiny synthetic memory lifecycle probe — 2026-09-21

Both installed ai-memory 2.3.2 and pinned Basic Memory 0.23.2 returned the three
frozen lexical facts, reflected an overwrite, and removed a deleted note from
search. ai-memory retained the results across an owned server restart. Basic
Memory retained them after its native full text-index rebuild. **28/28 content
checks passed across 41 completed CLI invocations and two owned server
lifecycles in the accepted evidence.** This is a small synthetic lifecycle check, not a semantic-quality,
production-readiness, performance, or overall product ranking.

## Outcome and important failed attempt

| Capability | ai-memory | Basic Memory |
| --- | --- | --- |
| Three native writes and lexical searches/full reads | Passed | Passed |
| Update returned new fact; old keyword absent | Passed | Passed |
| Delete acknowledged; deleted keyword absent | Passed | Passed |
| Fresh-process persistence | Passed, including server restart | Passed, separate native CLI invocation per operation |
| Native recovery-related command | Backup succeeded; restore/reindex untested | Full text-only reindex succeeded, 2 observed/2 indexed |

**The first ai-memory attempt failed the no-model-download constraint.** An
unset embedding provider selects a default local model and starts a background
fetch. The mistake was found in the retained server log after the servers were
stopped. Inspection of its owned `models/` directory found zero files after
stopping. Network byte transfer was not measured, so this is not evidence of
zero downloaded bytes. Content assertions from that run do not make it an
accepted run. Publication copies of the commands, server logs and initial probe
code remain under `attempt-1-default-embedding/`. Exact originals, including
both backup archives, are retained privately; original/public hashes are
recorded in `provenance.json`.

The documented opt-out was then confirmed in pinned upstream documentation and
source. One corrected ai-memory run used a new empty store and explicit
`AI_MEMORY_EMBEDDING_PROVIDER=none`. Both corrected server logs report vector
search disabled, neither contains a model fetch, and no model files were found
in that store. The original Basic Memory lane already used the supported
`BASIC_MEMORY_SEMANTIC_SEARCH_ENABLED=false` setting and was reused unchanged;
its passing evidence was not rerun. Network egress was not instrumented.

ai-memory's native `restore` and `reindex` both enumerate **all** same-name
processes before acting, rather than checking only the selected data directory.
Those commands were not run because this assignment prohibited inspecting
active service state. The process guard was not bypassed. Basic Memory's full
reindex is not a demonstration of restoring a lost database. These are unequal
recovery checks and do not support a comparative recovery winner.

## Frozen input and isolation

`corpus.json` contains three public fictional notes, three literal keywords,
the expected facts, one replacement and one deletion. The probe hashes that
file before the first native write; the same unchanged file is used for both
tools and the corrected run. No real project content or memory tools were read.

Each child process receives a constructed environment containing only PATH,
LANG, NO_COLOR and the explicit tool controls shown in `commands.json`.
No account credentials are inherited. Neither hooks nor agent integrations are
installed. All candidate packages, configuration, databases, notes and caches
are under `/tmp/memory-lifecycle-probe-20260921-scratch`. ai-memory page commands
are HTTP clients: the probe starts only its own server on an allocated loopback
port, supplies that URL explicitly, uses `--no-watcher`, and terminates and waits
for its own server processes. It never reads process lists or signals other
processes. Explicit workspace/project names are used for ai-memory; Basic
Memory uses an explicit local project and `--local` on each tool command.

## Pins and primary source

- ai-memory: installed binary reports 2.3.2; its binary SHA-256 is in
  `identity.json` (its machine-specific executable path is replaced with a
  placeholder in this publication). Source inspected at tag v2.3.2, commit
  `353841d91618d20b110b208de284a74d0b960379`. The binary was not rebuilt to prove
  equivalence with that source.
- Basic Memory: installed from clean source checkout
  `3bf2d523c0a941f71cb144a5502e7557dd025d69`, reports 0.23.2, Python 3.12.3.
  `uv pip install` resolved dependencies at installation time; it did not use
  upstream's uv.lock. Complete resolved package pins and installation output
  are retained.
- [ai-memory embedding opt-out](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/docs/local-embeddings.md#L9-L22)
  and [provider resolution](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/config.rs#L1533-L1541).
- [ai-memory process guard](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/process_guard.rs),
  [reindex](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/commands/reindex.rs),
  and [restore](https://github.com/akitaonrails/ai-memory/blob/353841d91618d20b110b208de284a74d0b960379/crates/ai-memory-cli/src/commands/restore.rs).
- [Basic Memory config and store isolation](https://github.com/basicmachines-co/basic-memory/blob/3bf2d523c0a941f71cb144a5502e7557dd025d69/src/basic_memory/config_models.py#L72-L88),
  [semantic setting](https://github.com/basicmachines-co/basic-memory/blob/3bf2d523c0a941f71cb144a5502e7557dd025d69/src/basic_memory/config_models.py#L251-L255),
  and [native CLI tools](https://github.com/basicmachines-co/basic-memory/blob/3bf2d523c0a941f71cb144a5502e7557dd025d69/src/basic_memory/cli/commands/tool.py).

## Evidence and replay boundaries

Evidence is in `../../evidence/artifacts/memory-lifecycle-probe-20260921/`:

- `commands.json`: command arrays, constructed environment, stdin,
  exit codes, measured per-process durations, and returned outputs. Personal
  executable paths are replaced with `<AI_MEMORY_BIN>` and generated UUIDs with
  stable synthetic labels; all other JSON payload values are retained. It
  combines the accepted original Basic Memory lane and corrected ai-memory lane.
- `verification.json`: fact checks against the frozen corpus, including zero
  results for removed/replaced keywords.
- `isolation-observations.json`: attempted-download failure and corrected run
  observations, with unmeasured boundaries.
- `identity.json`, package freeze, native help, install output and server logs
  retain provenance and diagnostics. Backup archives are withheld; each
  `ai-backup.inventory.json` publishes its original SHA-256, size, member
  inventory and bounded inspection result, including config/SQLite bytes and
  decompressed loose Git objects. The two unsupported help
  attempts (`bm db --help`, `bm sync --help`, exit 2) are retained; the actual
  native command is `bm reindex`.
- `provenance.json`: original/public SHA-256 pairs and per-file transformations.
  Personal executable paths were replaced, public drivers now require an
  explicit `AI_MEMORY_BIN`, and literal trailing spaces/tabs were removed from
  publication text, with exactly one final newline. Escaped whitespace inside
  JSON output values was retained.
  Eight generated UUIDs in command results and backup inventory paths were
  replaced consistently with `SYNTHETIC-ID-001` through `SYNTHETIC-ID-008`.
  Original archive/member hashes, facts, exit codes and timings are unchanged.
  Public drivers are sanitized examples, not byte-identical executed scripts;
  both executed-original script hashes are recorded. Exact originals remain
  outside the repository in a private directory. No memory operations were
  rerun for this publication cleanup.
- `SHA256SUMS`: public artifact and blueprint hashes, excluding itself.

Run `python3 blueprints/memory-lifecycle-probe/verify.py` from this worktree to
recheck the receipts without touching a memory store. `probe.py` is a sanitized
copy of the one-off corrected run driver requiring `AI_MEMORY_BIN`; it reuses
the retained Basic Memory commands and
refuses to reuse an existing corrected ai-memory store. It is not an installed
harness or a general-purpose runner. Provision commands are in `identity.json`.
For a new experiment use a fresh owned prefix, review current native controls,
and rerun both tools with the frozen input; do not overwrite this evidence.

No latency summary is promoted: recorded durations include different process
startup and server architectures, were collected once, and are not comparable
steady-state retrieval benchmarks. No concurrency, crash recovery, semantic
retrieval, graph quality, TTL, handoff, hooks or real agent E2E was tested.
Deletion checks concern current lexical search results; they do not establish
erasure from earlier page versions, Git history, logs or retained backups.
