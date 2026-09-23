# SOTA refresh 2026-09-23 — unit pins-tools

Qualifies the newest upstream releases for five pinned tools against retained
receipts where one exists, run natively on this host under an isolated cache
prefix (`$HOME/.cache/sota-refresh-20260923/pins-tools/`; nothing was
installed onto PATH, `~/.config`, or any live service).

This is the fix round after an independent Opus review of the first pass.
Every finding below was investigated and resolved by re-running the affected
checks with corrected commands and honest, verbatim evidence; see "Fix round
changes" for what changed and why. A second independent re-review then found
five more findings (one major, four minor) in that fix round itself, all
about timestamp accuracy, citation line numbers and raw-output storage, not
about the underlying checks; see "Re-review fix round" below for what
changed in response.

| component | from | to | published_at | verdict | evidence class | receipt |
|---|---|---|---|---|---|---|
| mcporter | 0.13.13 | v0.14.0 | 2026-09-22T09:54:57Z | qualified | native_proven | [mcporter.json](mcporter.json) |
| agentsview | v0.43.0 | v0.44.0 | 2026-09-21T13:56:12Z | qualified | native_proven | [agentsview.json](agentsview.json) |
| openresearch | v0.2.7 | v0.2.8 | 2026-09-22T03:20:42Z | qualified | native_proven | [openresearch.json](openresearch.json) |
| langgraph | 1.2.11 | 1.2.12 | 2026-09-21T14:43:28Z | qualified | local_integration | [langgraph.json](langgraph.json) |
| opensandbox | server v0.2.3 | release-1.1.0 | 2026-09-21T07:46:25Z | blocked | native_proven (partial offline surface); functional core blocked | [opensandbox.json](opensandbox.json) |

## Fix round changes

- **langgraph (major)**: `smoke_test.py` is now stored in this repository at
  [langgraph-smoke-test/smoke_test.py](langgraph-smoke-test/smoke_test.py)
  (sha256 `8405ef4086b1ab134658027ed156d9a62a8a3b454a7ad39584a162945bfae646`,
  listed in `manifests/evidence.json`), not only in the unit's `.cache/`
  prefix. Full raw stdout for each venv (starting at `langgraph version:
  ...`, matching the script's actual print order) plus each run's exit code
  is recorded at
  [langgraph-smoke-test/out_1.2.11.txt](langgraph-smoke-test/out_1.2.11.txt)
  and
  [langgraph-smoke-test/out_1.2.12.txt](langgraph-smoke-test/out_1.2.12.txt)
  and quoted verbatim (not edited) in `langgraph.json`. The test now also
  builds a second, checkpointed graph using
  `langgraph.checkpoint.memory.InMemorySaver` -- the exact import this
  repository's own catalog names
  (`catalogs/us-equities/agents-operations.json` id=langgraph,
  `catalogs/us-equities/architecture/foundation.json` acceptance_gate) -- and
  exercises an `interrupt()` / `Command(resume=...)` pause-and-resume cycle
  on a single `thread_id`, checking `get_state()` and
  `get_state_history()`. Both venvs pass identically except that 1.2.12's
  `Interrupt` repr gained a `response_schema=None` field. `acceptance_check_ref`
  now cites the exact catalog lines and states plainly which catalog-named
  gaps (persistent non-memory checkpointer, `LANGGRAPH_STRICT_MSGPACK`,
  upstream `uv sync --frozen --group test --no-dev`) this receipt still does
  not close.
- **opensandbox (major)**: this repository's own catalog
  (`catalogs/us-equities/agents-operations.json` id=opensandbox) already
  lists an offline `opensandbox-server --help` command and a
  `pip install opensandbox` SDK-import command as its native_workflow
  surface, explicitly noting "help/import is not isolation proof" -- i.e.
  these were always meant to be run without Docker, the same way
  openresearch/agentsview's version-help checks run without a search key.
  The fix round actually runs both at release-1.1.0 (`opensandbox-server`
  0.2.3 vs 1.1.0 via `uvx`, `opensandbox` SDK 0.1.16 vs 1.1.0 via `uv pip
  install` + `import opensandbox`) and records full output, exit codes and a
  diff: the server `--help` gained a `migrate-snapshots` subcommand matching
  the release's PostgreSQL snapshot-store feature; the SDK's importable name
  set is identical. The overall verdict stays `blocked` because the
  component's actual function (sandbox creation/isolation) still cannot be
  exercised on this host, but the receipt no longer claims "no offline
  surface exists" -- it names and runs the one the catalog already
  specified, then still blocks on the functional core.
- **opensandbox (minor, preregistration timing/attribution)**: the
  preregistration text no longer states the Docker-absence conclusion before
  it was checked; the `which docker podman docker-compose` and `test -S
  /var/run/docker.sock` commands are now listed with their exact exit codes
  (all 1/absent) recorded in `results`, run before the conclusion is drawn.
  The release-notes quote is now correctly attributed and separated:
  `release_notes_excerpt` is the GitHub release body itself (`gh api
  .../releases/latest --jq '.body'`), and the Docker requirement is
  separately attributed to `README.md` at the resolved commit
  `b1a29cf93a823a95913f7943010febb3f29de05c` (tag `release-1.1.0`), lines
  166-169, fetched via `raw.githubusercontent.com`.
- **mcporter (minor)**: the receipt no longer claims the 0.14.0 `list`
  output "matched retained 0.13.13 receipt byte-for-byte aside from version
  string." It now says plainly that per-server timings are not deterministic
  (the retained receipt shows socraticode at 0.2s; this unit's own re-run of
  0.13.13 in the same session shows 0.4s, and 0.14.0 shows 0.5s) and that the
  byte-identical claim applies only to server names, tool counts and
  health/error text against the retained receipt, plus a full byte-for-byte
  comparison against a same-session 0.13.13 re-run. `mcporter --help` is now
  an actual listed command for both versions, with exit codes recorded and a
  `diff`/sha256 confirming the full --help output (not just a prose summary)
  is byte-identical between 0.13.13 and 0.14.0.
- **agentsview / openresearch (minor, exit codes and pipefail)**: all
  `--help | head -1` pipelines are now run as `bash -o pipefail -c '...; rc=$?;
  ...; exit $rc'`, matching the retained receipts' own command shape, and
  every command's exit code is recorded in `results` (previously none were).
  `old_0_43_0_version`/`old_0_2_7_version` now have matching `--version`
  commands listed in `commands`. openresearch's `discover_subcommand_tree`
  narrative is replaced with a real `orx discover --help` capture from both
  versions, sha256-hashed and diffed (identical), and the preregistration no
  longer claims this will be "byte-identical to the retained pin's output"
  since the retained receipt (`evidence/artifacts/claude-upstream-checks-20260921/results.json`
  id=openresearch) only captured `--version` and the first `--help` line,
  never `discover --help`; the receipt now says plainly this is a
  same-session v0.2.7-vs-v0.2.8 comparison, not a retained-receipt
  comparison. agentsview's full `--help` body diff (beyond line 1) is also
  now recorded and shows 0.44.0 adds `clickhouse`, `export conversations`,
  `export range` and `insight` subcommands plus new environment variables --
  new functional surface not exercised by this version-help-scoped receipt,
  called out explicitly in `limits`.

## Re-review fix round

- **Timestamps (major)**: the fix round's first attempt set `written_at` and
  `checked_at` to values later than both the actual runs and the commit that
  recorded them (e.g. commit 7bec2c3 at `2026-09-22T20:38:37-04:00` but
  `checked_at` values of `01:45Z`-`02:20Z`, which is in the future relative
  to that commit and to the review clock). All five receipts now set
  `written_at`/`checked_at` from the actual file mtimes of the commands' raw
  outputs (recorded alongside each field as a `*_note` explaining the exact
  file and mtime used), and label the preregistration text as written
  alongside the receipt after the run (LATE / same-round), not strictly
  prior to it. The same pattern in the original 2ab0819 commit (checked_at
  ahead of its own commit timestamp) is superseded by these corrected
  values.
- **mcporter same-session comparison (minor)**: dropped the false claim that
  "only the version string in the banner line differs between the two runs
  made in this session" -- the same-session 0.13.13 re-run and 0.14.0 run
  also differ in the non-deterministic socraticode timing (0.4s vs 0.5s).
  The receipt now says plainly that names, counts and health text match and
  timings are not comparable, with no byte-for-byte claim for the `list`
  output (the `--help` byte-for-byte claim, which is backed by a stored
  diff/sha256, is unaffected and unchanged).
- **langgraph docstring (minor)**: `smoke_test.py`'s module docstring
  incorrectly said the test doesn't cover interrupts even though it now
  calls `interrupt()`/`Command(resume=...)`; corrected, and
  `manifests/evidence.json` re-hashed for the changed file.
- **langgraph citations (minor)**: `catalogs/us-equities/agents-operations.json`
  line references corrected from :262-263 to :253-254 (the actual
  `InMemorySaver` import command lines; :262 is a limitation, not a
  command), and `catalogs/us-equities/architecture/foundation.json` from
  :851-859 to :850 for the `acceptance_gate` field (the `uv sync --frozen
  --group test --no-dev` upstream command is correctly at :859, unchanged).
- **Raw-output storage (minor)**: the `mp_old_help.txt`/`mp_new_help.txt`
  (mcporter), `av_old_help.txt` (agentsview) and `orx_old_discover.txt`
  (openresearch) captures that the receipts hash and diff against were left
  in `/tmp` after the fix round instead of the cache prefix; they are now
  copied into `$HOME/.cache/sota-refresh-20260923/pins-tools/{mcporter,agentsview,openresearch}/`
  with their original mtimes preserved (sha256 values unchanged and
  re-verified against the receipts). `av_new_help.txt` and
  `orx_new_discover.txt` (the newer-version captures) were never written to
  disk by the original run and could not be recovered; each affected receipt
  now discloses this as a limitation rather than implying both sides of the
  diff are stored. For opensandbox, the `README.md` the Docker requirement
  is quoted from was re-fetched at the exact cited commit
  (`b1a29cf93a823a95913f7943010febb3f29de05c`) and stored at
  `$HOME/.cache/sota-refresh-20260923/pins-tools/opensandbox/opensandbox_readme.md`
  (sha256 `ab78736660038f0f08365302d511c10b01c48af9678d71dd5844abf09e8b026b`);
  `grep -n` against that file confirms 'Requirements:' at line 166 and the
  two quoted bullets at lines 168-169, exactly as cited.

## Notes (carried from the original pass, still accurate)

- **mcporter**: installed the npm package `mcporter@0.14.0` into an isolated
  prefix (no linux_x86_64 GitHub-release binary exists for this version; the
  project ships as an npm package plus darwin tarballs). Ran `list` against a
  **copy** of `$HOME/codex-ecosystem/config/mcporter.json` (never the
  live file). That config copy carries only a loopback baseUrl and local
  command paths, no stored secrets.
- **agentsview**: downloaded the linux_amd64 release tarball, verified its
  sha256 against the release's published `SHA256SUMS`, and compared
  `--version`/`--help` to the retained version-help receipt; matched on the
  scope the retained receipt covers (line 1).
- **openresearch**: downloaded the musl linux CLI tarball, verified its
  sha256 against the release's `.sha256` sidecar, and compared
  `--version`/`--help`/`discover --help` (offline, no key needed) between
  0.2.7 and 0.2.8; matched. Functional search subcommands
  (`discover keyword/embedding/openalex/biorxiv`, `paper`, `login`) need a
  stored alphaXiv/OpenAlex account or key this unit was not given, so they
  were not run and are recorded as not attempted, not as passing.
- **langgraph**: no retained repository receipt exercises langgraph's
  runtime behavior (only source_review shortlist mentions). Built two
  `uv`-managed venvs (system Python's `venv` module could not run
  `ensurepip` without `apt install python3.12-venv`, which was out of scope
  for an unprivileged unit-owned install; `uv venv` avoided that dependency)
  and ran an extended build/compile/invoke/stream + checkpointer
  pause-resume smoke test on 1.2.11 and 1.2.12; both passed identically
  (exit 0) aside from a minor `Interrupt` repr addition in 1.2.12. Labeled
  `local_integration`, not `native_proven`, since there is no retained
  receipt to re-run for comparison, and the upstream `uv sync --frozen
  --group test --no-dev` test suite was not run.
- **opensandbox**: the upstream README states Docker is required for local
  execution (or Kubernetes for cluster execution); this host has neither
  Docker, Podman, docker-compose, nor a docker.sock (all checked, all
  absent/exit 1), and provisioning a container runtime is host-level
  infrastructure outside a unit-owned cache-prefix install. The catalog's
  own offline help/import surface was run and matched (see above); the
  overall verdict remains `blocked` for the component's actual function. No
  credential or broker contact was needed to reach this determination.

## Isolation

All installs live under `$HOME/.cache/sota-refresh-20260923/pins-tools/`
(npm prefix, extracted release tarballs, four `uv` venvs: two for the
langgraph graph smoke test, two for the opensandbox SDK import check). No
binary on PATH was replaced, no live config was edited, no systemd unit or
shell profile was touched, and no long-running process was left behind (no
daemons/servers were started for any of these five checks).
