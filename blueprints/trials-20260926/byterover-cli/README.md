# ByteRover CLI trial (2026-09-26)

**Measured result:** the offline store/retrieve path (`brv vc` into the context
tree, then BM25 `brv search`) works with no LLM and no account, with positive,
negative and deliberately-wrong controls; the upstream suite at the pinned tag
passes. The LLM-mediated path (`brv curate`, escalated `brv query`) was **not
evaluated end to end on this host**: the observed request totals (12,351 and
11,192 tokens) exceeded the host llama.cpp context of 8192. The licence is the
Elastic License 2.0. The layer decision is not made here (see
[Verdict](#verdict)).

Machine-readable record: [`results-20260926.json`](results-20260926.json).
Every retained file, with sha256, evidence class and sanitization:
[`retained-outputs.json`](retained-outputs.json). Pinned source lines behind the
findings: [`source-review.json`](source-review.json). Batch rules (evidence
classes, why there are no host receipts, host cleanup): [`../README.md`](../README.md).

## What it is

[ByteRover CLI](https://github.com/campfirein/byterover-cli) (`brv`, formerly
Cipher) keeps a per-project "context tree" of curated knowledge for coding
agents: a git-like version-control layer (`brv vc`, isomorphic-git), BM25 search,
an LLM agent loop (`curate`, `query`) over 20 selectable providers including any
OpenAI-compatible endpoint, a background daemon, an MCP server (`brv mcp`) and an
optional paid cloud backend.

## Pins

| Pin | Value | Verified by |
| --- | --- | --- |
| npm `byterover-cli` | `3.16.1`, `dist.integrity` `sha512-uI6zETcy…MKmDTcw==`, `dist.shasum` `dfb0b176…d28678` | `npm view`, and the sha512 of each downloaded tarball in every reproduction run |
| Git tag | `v3.16.1` = `1f4609c18ca735810860b3ba9178cae2dd8a67b0` | fresh tag clone, `git rev-parse` |

See [`../provenance/run-20260926T045856Z/verify-pins.log`](../provenance/run-20260926T045856Z/verify-pins.log)
and each run's `00-npm-view.stdout` / `02-tarball-integrity.stdout`.

## Results

| Check | Evidence class | Exit | Result | Retained |
| --- | --- | --- | --- | --- |
| Upstream suite at the tag (`npm ci`, `npm test` = `mocha --forbid-only "test/**/*.test.ts"`) | upstream test | 0 | **8340 passing, 16 pending, 0 failing**; a second run from a fresh `mktemp` clone gave the same. Each run left about 125 directories in `/tmp` (finding 5) | [excerpt](native-outputs/npm-test-tag-v3.16.1-excerpt.log), [rerun](native-outputs/npm-test-self-contained-rerun.log) |
| Offline store/retrieve, self-contained ([script](reproduction/reproduce-vc-search.sh)) | upstream native operation + local integration check | 0 | `brv vc` committed two notes; `brv search "rate limiter"` → exactly `auth/notes.md` (score 0.76), `"invoices"` → exactly `billing/notes.md` (0.66), `"zzznonexistentxyz123"` → `totalFound 0`; every JSON had `success: true`, `status: completed`. [`check_search.py`](reproduction/check_search.py) passed the three real expectations and **failed** the two deliberately wrong ones (wrong path, `--total 10`). The autoupdate hook never ran (no `lastrun` in the workspace cache directory) | [run-20260926T1131Z](reproduction/run-20260926T1131Z/) (current script); the same results from the earlier versions in [run-20260926T0454Z](reproduction/run-20260926T0454Z/) and [run-20260926T0424Z](reproduction/run-20260926T0424Z/) |
| Isolation and cleanup of run-20260926T1131Z | independent observation + local integration check | – | the host ByteRover paths (the five known ones plus update-notifier's file) were absent before and after. The dedicated `TMPDIR` kept only `node-compile-cache`, Node's default compile-cache directory, which npm 11 enables at startup (`source-review.json#npm-compile-cache`). The script recorded its daemon, whose process group and session equal its pid, and the agent the daemon forked. It sent SIGTERM to the daemon only, and both were gone 5.41 s later. No process list was read. The 10:04Z `/tmp` inventory shows no ByteRover directory born during the two earlier runs | [host-state-observation.txt](reproduction/run-20260926T1131Z/host-state-observation.txt), [owned processes](reproduction/run-20260926T1131Z/80-owned-processes.stdout), [stop](reproduction/run-20260926T1131Z/90-stop.stdout), [inventory](../host-cleanup-20260926/remaining-host-state/host-state-inventory.txt) |
| Cleanup scope of both script versions, each inside a private user and PID namespace ([probe](reproduction/restart-scope-probe.sh)) | local integration check | 0 | the probe ran four decoy sleepers whose only link to ByteRover is one argument. The 0454Z version's `brv restart` **killed three of them** with SIGKILL (wait status 137): `…/bin/brv`, `…/brv-server.js` and `…/agent-process.js`. It spared the control (`…/worker.js`). The current version spared all four and stopped only its own daemon and agent. Both passed every search check, and neither left a process in the namespace | [probe-20260926](reproduction/restart-scope-probe-20260926/) |
| [`owned_processes.py`](reproduction/owned_processes.py), the current cleanup, against fake processes ([check](reproduction/owned_processes_check.py)) | local integration check | 0 | all five expectations held: graceful stop, SIGKILL after 10 s for processes that ignore SIGTERM, a daemon file naming a foreign process refused, an unreadable file refused, a reused pid left alone | [output](native-outputs/owned-processes-check-20260926T110019Z.txt) |
| Local LLM `curate` through the connected local provider (`openai-compatible`, host llama.cpp) | upstream native operation | 0 (JSON: `success: false`) | the local server rejected the request: `request (12351 tokens) exceeds the available context size (8192 tokens)`; nothing curated | [JSON](native-outputs/curate-context-error.ndjson), [task record](native-outputs/task-records/01-curate-context-error.json) |
| Key handling of the first pass's connection recipe | local integration check | 0 | [`connect-local-llm.sh`](local-integration/connect-local-llm.sh) is **unsafe as run**: it passed the key in curl's `-H` argument and in `brv providers connect --api-key`, where any local user can read it. The check used a random dummy value and a loopback listener it started itself, with nothing sent to the llama.cpp service. The first-pass curl form exposed the value in curl's command line. [`connect-local-llm-safe.sh`](local-integration/connect-local-llm-safe.sh) delivered the same header from standard input, and the value appeared in no command line or environment of its three processes | [check](local-integration/credential-argv-probe.py), [output](native-outputs/credential-argv-probe-20260926T111651Z.txt) |
| `query` | upstream native operation | 0 | a natural-language phrasing was answered by the LLM-free tier-2 path with no match (12 ms, 10 ms); a keyword phrasing escalated to the LLM and failed the same way at 11,192 tokens | [task records](native-outputs/task-records/) |
| Host llama.cpp context | host service observation | 0 | `n_ctx` 8192 (service setting), `n_ctx_train` 262144 | [/v1/models](native-outputs/llamacpp-v1-models.json) |
| Background autoupdate | upstream native operation | – | the first `brv --version` spawned a detached `brv update --autoupdate` (01:26:47Z) that waited an hour and reported "not updatable" | [log](native-outputs/oclif-autoupdate.log) |

The current script replaces two earlier versions. Each earlier run is kept with the
exact script it used, and both gave the same search results.
`run-20260926T0424Z` left `XDG_CACHE_HOME` at the host default, so each `brv`
call touched `~/.cache/brv/lastrun`. `run-20260926T0454Z` redirected the cache
directory and set `BRV_DISABLE_AUTOUPDATE=1`. **Both versions end with `brv
restart`, which is unsafe on a shared host** ([below](#brv-restart-in-earlier-runs)).
The current version stops only the processes it recorded and checks that the
autoupdate hook never ran. It also records the dependency versions npm actually
installed: `@oclif/core` 4.14.0 and `@oclif/plugin-update` 4.8.0
([`05-npm-ls.stdout`](reproduction/run-20260926T1131Z/05-npm-ls.stdout)). A global
tarball install resolves `package.json`'s ranges and ignores the tag's lock file,
which pins 4.5.4 and 4.7.19. The source review quotes the installed versions'
autoupdate and cache-directory lines too.

## Findings

1. **Exit codes do not report task failure** (`search`, `curate`, `query`). A
   failed task appears only in the JSON (`success: false`,
   `status: error`), so checks must read the JSON. `check_search.py` requires
   `success: true`, `status: completed`, an exact `totalFound`, the exact first
   path and excerpt text. (`source-review.json#search-task-semantics`,
   `#curate-task-error-exit`.)
2. **Observed request totals, not a fixed overhead.** 12,351 (curate) and
   11,192 (query) tokens are totals for those requests on this project and
   model. The system prompt includes variable project context (working
   directory, git state, file tree, `.brv` structure), so the size depends on
   the project and input (`#prompt-environment-context`).
3. **Background self-update is on by default.** The bundled
   `@oclif/plugin-update` hook touches the cache directory on every command and
   spawns `brv update --autoupdate` when its debounce allows (S3 release host,
   1-day debounce); `BRV_DISABLE_AUTOUPDATE=1` disables it, `NO_UPDATE_NOTIFIER`
   does not (`#oclif-autoupdate-hook`, `#autoupdate-config`; for 4.8.0, the version the
   reproduction installed, `#oclif-autoupdate-hook-4.8.0-*`).
4. **Persistent host state in five places:** `$XDG_CONFIG_HOME/brv`,
   `$XDG_DATA_HOME/brv` (projects, logs, an AES-256-GCM encrypted provider
   keychain), `$XDG_STATE_HOME/brv`, `$XDG_CACHE_HOME/brv`, and update-notifier's
   `~/.config/configstore/update-notifier-byterover-cli.json`. The upstream
   suite registers its temporary directories as projects in the real data
   directory (`#xdg-*-path`, `#provider-keychain`).
5. **The upstream suite leaves its temporary directories behind.** Tests such
   as `consolidate.test.ts` create `<os.tmpdir()>/brv-*-test-*` directories
   before each test, and their `afterEach` only restores the stubs. Other tests
   use the fixed `/tmp/brv-test-blobs` and `/tmp/brv-test-storage`, and the
   tool-output processor writes to `<os.tmpdir()>/byterover-tool-outputs`
   (`#suite-tmpdir-*`, `#suite-fixed-tmp-paths`, `#tool-output-temp-dir`). Each
   run on this host left about 125 directories. Four runs left 498 of them plus
   the three fixed ones: the first pass's two runs and the receipt recorder's
   dry run and recorded run. They are still on the host
   ([`../README.md`](../README.md#host-state)).
6. **`brv restart` stops processes host-wide.** On Linux it reads the command
   line of every process in `/proc`. It sends SIGKILL to each one containing
   `bin/brv`, `byterover-cli/bin/run.js`, `brv-server.js` or `agent-process.js`,
   sparing only itself and its ancestors, whatever the other process's install,
   data directory or session (`#restart-*`). Redirecting the data directory
   changes only which daemon gets the SIGTERM. The probe above shows it killing
   three decoys that shared nothing with the trial but one argument. To stop one
   install's daemon, send SIGTERM to the pid in that data directory's
   `daemon.json`. The daemon is spawned detached (`#transport-client-detached-spawn`)
   and stops the agents it forked (`#daemon-agent-fork`).
7. **A provider key enters ByteRover only as an argument or at a prompt.**
   `brv providers connect --api-key` takes it as a process argument. The CLI
   wizard's prompt for `openai-compatible` is a plain input prompt that echoes
   the key; only other providers get the masked one. The web UI's provider flow
   uses a password field, `openai-compatible` included. There is no stdin, file
   or environment option (`#connect-*`, `#webui-*`). The safe recipe therefore
   uses the web UI for the key and gives curl its header on standard input
   (`#curl-header-from-stdin`).

## `brv restart` in earlier runs

Three commands in this trial ran `brv restart` on the shared workstation:

| When (UTC, 2026-09-26) | Run by | Install and data directory |
| --- | --- | --- |
| 04:26:07Z, at exit | `run-20260926T0424Z` cleanup | the run's mktemp install and data directory |
| 04:53:45Z-04:53:53Z | host cleanup ([`../host-cleanup-20260926/`](../host-cleanup-20260926/)) | the first pass's host install and default data directory |
| 04:56:31Z, at exit | `run-20260926T0454Z` cleanup | the run's mktemp install and data directory |

Each one could send SIGKILL to any process of the same user in this WSL
distribution whose command line contained `bin/brv`, `byterover-cli/bin/run.js`,
`brv-server.js` or `agent-process.js`. That covers every other ByteRover CLI,
TUI or MCP client, daemon or agent, whatever its install or data directory, and
any unrelated program with such an argument (finding 6). The daemon each one
stopped with SIGTERM was its own: the run's own data directory, or for the host
cleanup, the daemon its preceding `brv providers disconnect` had started
(`Stopping daemon (PID …)` in each `90-restart.stdout` and in
`../host-cleanup-20260926/cleanup-apply.log`).

What the retained records show about other ByteRover processes at those times:

- Both first-pass daemons had ended earlier ([daemon logs](native-outputs/)). The
  01:29Z daemon got a SIGTERM at 01:44:20Z whose sender is not recorded, so a
  `brv restart` by the first pass then cannot be excluded either. The 03:08Z
  daemon stopped on its idle timeout at 03:53:56Z. The default data directory,
  listed at 04:53:41Z, held no daemon log or heartbeat newer than 03:53Z. So no
  daemon using this user's default data directory ran between 03:53:56Z and
  04:53:41Z.
- The host cleanup's process listings at 04:53:28Z and 04:53:41Z, 4 s before
  its restart, show no `brv-server`, `agent-process` or autoupdate process in
  this distribution. They did not look for ByteRover clients (`bin/brv`,
  `byterover-cli/bin/run.js`) or for unrelated programs with a matching
  argument.
- No process listing exists for 04:26Z or 04:56Z. The check after the 0454Z run
  (`host-state-observation.txt`, 04:56:43Z) found no ByteRover process, but a
  process the restart had killed would be absent as well.

Whether another session's process was hit **cannot be ruled out**. Nothing
retained covers ByteRover clients at any of the three times, daemons with
another data directory at 04:26Z or 04:56Z, or unrelated programs with a
matching argument. The current reproduction does not call `brv restart`.

## Licence

`LICENSE` at the tag is the **Elastic License 2.0 (ELv2)**; `package.json`
declares `Elastic-2.0`. Its Limitations section forbids providing the software
to third parties as a hosted or managed service, circumventing license-key
functionality, and removing licensing notices (`#license-file`,
`#license-field`).

## Not evaluated

- **LLM-mediated store and retrieve end to end.** Every attempt exceeded the
  host llama.cpp context of 8192 tokens. Raising it means reconfiguring the
  shared host service, which this trial may not do, and no cloud provider is
  used on this host. The provider connection itself worked: the requests reached
  the local server and came back with its error.
- **Published benchmark numbers** (README: LoCoMo 96.1%, LongMemEval-S 92.8%):
  no runnable harness ships with the repository; at the tag only the README and
  `paper/` mention either benchmark (`#readme-benchmark-claims`).
- `brv swarm` (interactive onboarding only), ByteRover Cloud (account
  required), `brv mcp` and `brv webui` (not invoked; no client configuration was
  changed). Each daemon the first pass started also started ByteRover's web UI
  server on port 7700 and stopped it with the daemon.
- **Outbound network traffic** was not measured. Source review names the update
  paths (finding 3 and update-notifier); the first pass's statement that nothing
  calls home was a source search, not an observation.
- **The safe connection recipe against the host llama.cpp service.** Its curl
  step was checked only with a dummy value against a local listener. Its
  ByteRover step, key entry in the web UI's password field, rests on source
  review.

## Withdrawn receipts

The first pass's two receipts are kept byte-for-byte in
[`withdrawn-host-receipts/`](withdrawn-host-receipts/). `scripts/host_receipts.py
validate` rejects `component_id` `byterover-cli`, which is neither a
`manifests/stack.json` component nor a landscape winner
([`../README.md`](../README.md#why-there-are-no-host-receipts)). The use receipt's
check also discarded `brv`'s output and grepped for `"totalFound":1`, which
matches `10` and any path ([the withdrawn check](local-integration/withdrawn-grep-use-check.sh));
the reproduction runs above replace it.

## Host state

The first pass left the npm install under
`~/.local/share/codex-ecosystem/tools/byterover-cli-3.16.1`, its bin symlink, and
all ByteRover state above, and its results file said only the install remained.
All of it was removed on 2026-09-26 at 04:53Z with ByteRover's own lifecycle
commands (`brv providers disconnect openai-compatible`, `brv logout`,
`brv restart`), then `npm uninstall --global --prefix … byterover-cli`, then the
literal state paths; credential files were never read. That `brv restart`
scanned every process in this distribution, not just this install's
([above](#brv-restart-in-earlier-runs)). A later cleanup should send SIGTERM to
the pid in the data directory's `daemon.json` instead. Record:
[`../host-cleanup-20260926/`](../host-cleanup-20260926/). ByteRover's task
records, logs and autoupdate log were copied here (sanitized) before the removal.

That cleanup did not look in `/tmp`. The upstream suite's 501 leftover entries
there (finding 5) are still on the host, together with their removal command;
see [`../README.md`](../README.md#host-state). The first pass's
`trial-byterover` scratch tree was deleted by the first polish pass.

## Corrections to the first pass

- `search`'s exit code does not reflect success (finding 1).
- "~11-12k fixed tokens before user content" is replaced by the observed totals
  (finding 2).
- The telemetry row was a source search labelled as native evidence; it is now
  source review, and outbound traffic is recorded as unmeasured.
- "Only the install and its symlink remain" was false; the full state was
  found and removed.

## Verdict

- **Measured:** the offline context-tree store and BM25 retrieve work without an
  LLM or account and pass discriminating controls; the upstream suite passes
  (8340 / 16 pending / 0 failing). The LLM path was not evaluated end to end: the
  observed request totals exceeded the host's 8192-token llama.cpp context.
- **Facts:** Elastic License 2.0 with the limitations quoted above; exit codes
  do not report task failure; background autoupdate is on by default; the
  upstream unit suite leaves about 125 directories in `/tmp` per run; `brv
  restart` sends SIGKILL to matching ByteRover processes host-wide, not just its
  own install's (finding 6); a provider key goes in only as an argument or at a
  prompt, and the CLI's `openai-compatible` prompt is unmasked (finding 7).
- **Blockers:** the LLM path needs a local model served with more context than
  the shared host service (or a cloud provider); the published benchmark numbers
  have no runnable harness in the repository.
- **Layer decision:** not made here. The foundation durable-memory layer is
  re-recorded by its own verdict wave
  (`tools/sota-convergence/record_verdicts.py`).
- **Re-trial trigger:** a local OpenAI-compatible model served with enough
  context for the observed totals, then `curate` followed by `query` with a
  JSON-reading check and a deliberately wrong expectation.
