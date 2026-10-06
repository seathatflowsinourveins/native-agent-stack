# Organic-invocation E2E v1.1: the command center's decisions (2026-10-06)

- **Source:** command-center item `task-ns2604-coop-20261006T105529Z`, section "Organic E2E v1.1: the CC's decisions before the pilot", sent 2026-10-06 at 10:55Z. The decisions below keep that item's numbers.
- **Confirmations:** command-center item `task-ns2604-coop-20261006T114319Z`, sent at 11:43Z, settles the five points this file had marked for confirmation. Each is recorded below as "Confirmed (CC 11:43Z)", with its point number.
- **Rulings of 12:30Z:** command-center item `task-ns2604-coop-20261006T123036Z` confirms one interpretation and extends decision 1's timing record to every cell. Both are recorded below as "Confirmed (CC 12:30Z)".
- **Structural G13 of 13:29Z:** command-center item `task-ns2604-coop-20261006T132948Z` replaces decision 3's classifier-based invalidation with a structural G13: the answer sources are hidden from every trial's mount namespace, and the command classifier becomes a diagnostic tag. It is recorded first below, and it governs wherever earlier sections describe G13's invalidation.
- **Round 5, 14:38Z, 14:42Z and 15:17Z:** three command-center items, all recorded in "Round 5" below.
  - `task-ns2604-coop-20261006T143846Z` rules on the residual channels, receipt privacy and fanotify.
  - `task-ns2604-coop-20261006T144256Z` puts Codex cells on the normal service tier.
  - `task-ns2604-coop-20261006T151719Z`, section C1, rules on the GPT read of 2044b2ab. It accepts P2-1 (bind triples) and P3 (the public receipt), and upholds P2-2 (host execution brokers) in a commit of its own. It returns the gateway's residual to the command center with this round's read-only probe.
- **Round 6, 15:57Z and 16:43Z:** two command-center items, recorded in "Round 6" below.
  - `task-ns2604-coop-20261006T155742Z`, section 2: (A) the dated Gate 0 amendment that keeps the response cache on; (B) a network namespace per trial with explicit forwards only.
  - `task-ns2604-coop-20261006T164313Z`, section 3: approves both, approves the answer-channel closure as a separate commit, and folds in the GPT read of a513616d.
- **Applies to:** PROTOCOL-v1.1.md (organic-e2e-v1.1-20261005), which stays verbatim, and PILOT-SPEC-v1.1.md. Where they differ from this file, this file governs from 2026-10-06 10:55Z.
- **Harness:** each decision's code is in `harness/`, in the commit that adds this file.
  - `CC_V11_DECISIONS` in `harness/common.py` names the item.
  - `prepare.py` writes this file's sha256 into run.json as `amendment_file_sha256`.
- **Status:** no pilot or smoke has run under these changes. The checks under Verification are synthetic or offline.

## Structural G13 (CC 13:29Z)

Item `task-ns2604-coop-20261006T132948Z` decided that a classifier of the commands a model typed cannot converge, because shell grammar always has another form: aliases, xargs, find actions, subshells, `python -c`, here-docs. So G13 is now structural. `harness/isolation.py` implements it.

1. **Every listed answer source is hidden from each trial's mount namespace.** Two components run each trial's client process tree under bubblewrap:
   - the launcher, for every CLI and SDK cell and for the prompted and gate-0 cells;
   - block.py, for CL7b, through the provider's `codex_path_override`, which points at a per-attempt wrapper.
   - **Empty tmpfs:**
     - the coordination state: every run root with its oracle runs, other trials' drafts, grades, run.json and gate0.json; the suite cards; the v1 captures;
     - the fixture cache: oracles.json, oracle-work, the templates and the tarballs.
   - **Empty tmpfs with the trial's own entries bound back:**
     - the fixtures folder `~/.cache/ws`: the trial's own fixture only;
     - the trial-files folder `~/.cache/wsr`: the trial's own prompt, settings, clone and -o file, and the run's neutral binaries;
     - the Claude projects folder: every project outside the experiment's roots, and the trial's own.
   - **A fresh per-trial folder over each per-session client store:**
     - the shared Codex sessions folder, which the clone's `sessions` alias points at;
     - Claude's file history;
     - context-mode's per-project session and content stores, for both clients (its root stays shared);
     - Claude's `/tmp/claude-<uid>` area.
     After the trial, its rollouts are published to the native sessions folder for collect.py. No isolated trial sees that folder. A failed move or publish is recorded in the exit row as `finish_error`: it costs the copy, never the trial's exit row.
   - **Unchanged:** the native home and the client configuration stay visible and writable, and the network and the environment are as before. The system runtime is read-only, as in the R2a replay's isolation.
   - **Nested sandboxes** (Codex's own, `unshare -rm`, a nested bwrap) run in a namespace below the trial's. The trial's mounts are locked there, so a nested process cannot unmount a hidden tmpfs.
   - **The wrapper:** bubblewrap 0.11.1 (`/usr/bin/bwrap`, Ubuntu 0.11.1-1ubuntu0.3, upstream containers/bubblewrap), unprivileged. Its options are read from a memfd (`--args`), so the namespace's PID 1 shows none of them.
     - Options relied on: `--args`, `--ro-bind`, `--bind`, `--bind-try`, `--dev-bind`, `--tmpfs`, `--proc`, `--unshare-pid`, `--die-with-parent`, `--chdir`, `--info-fd`.
     - Not `--new-session`: the launcher's TERM must reach the client for a graceful exit. So the launcher signals the tree below the wrapper, and kills the group only after 30 s.
   - **The item's fallback is not used.** That fallback is systemd's `InaccessiblePaths=` in a transient user unit (systemd 259, systemd.exec(5)). bwrap hosts every launch path, as the self-test's client checks show:
     - `claude --version` and `codex --version`;
     - Codex's own sandbox, nested in bwrap;
     - the CL6 and CL7 SDK imports;
     - `codex app-server --help` through the CL7b wrapper.
2. **G13 checks what was hidden** (`isolation.check`). The launched row's `isolation` receipt records:
   - the wrapper's argv, both as bwrap parses it and as a process listing shows it;
   - its mount operations;
   - the hidden list, with each path's sha256 and, for a file, its content's sha256.

   G13 passes when all of the following hold:
   - every location the item lists for the trial is in the hidden list and covered by its mount;
   - nothing is bound back into a hidden root but the trial's own entries, and nothing re-exposes a root after its tmpfs;
   - the client tree ran in a mount namespace of its own (bwrap's `--info-fd` record);
   - no process the launcher sampled in the tree was in the host's mount namespace (processes in a nested namespace are counted apart);
   - stage 1's wrapper-only self-test passed (`isolation-selftest.json`).

   Gate 0 requires that self-test and each stage-2 trial's receipt check, and a failed self-test refuses stage 1. A trial is valid only if its own check passes.
3. **Optional audit, never a gate.** A fanotify listener held by root on the hidden roots, filtered to the trial tree's pids, would corroborate the receipts.
   - An unprivileged listener (Linux 5.13 and later) may mark only inodes, not a mount or filesystem, and does not receive the pid that generated an event (fanotify_init(2), man-pages at man7.org). So the pid filter needs CAP_SYS_ADMIN.
   - The harness runs no sudo, so the audit stays a documented option.
4. **The command classifier is a diagnostic tag only.** `grade.reach` still records the categories and the answer-source reads it recognises. G13 reports them under `classifier_diagnostic`, and they never invalidate a trial.
   - **Superseded:** the two P2s of the GPT micro-check of 1f81d645 (`cc-reads-20261005/pr786/GPT-VERDICT-1f81d645f.md`, outside the repository).
     - F1: patterns and unrelated listings were taken for reads, and some content searches were missed.
     - F4: the trial's own clone's sessions alias was exempted before classification.
   - Both concern the classifier, which no longer decides validity, and the alias is now hidden structurally.
5. **The P3 of that micro-check is fixed.** The deadline and completion decisions read the launcher's unrounded offsets (`duration_exact_s`, `time_to_result_exact_s`, `common.decision_times`):
   - the hold;
   - the launcher's result-before-T rule and its censoring reason;
   - the grader's completion re-check (`effective_exit`) and its no-result list.

   The one-decimal fields are presentation only. So a result at 1799.96 s, in a session that ran 1800.02 s, is complete, not held.

**Limits:**
- Services reached over a socket run outside the namespace: the ai-memory server, MCP servers configured by URL, the OmniRoute gateway, and a user systemd or Docker daemon. A file such a service reads for a trial is not hidden by the mount namespace; R10's per-trial scoping of those stores still applies. Round 5, below, narrows this.
- `/tmp` and `/dev/shm` stay shared outside Claude's own area (made private in round 5, below).
- A setuid helper (sudo) does not work inside the user namespace.

## Round 6 (CC 15:57Z and 16:43Z)

### Gate 0 amendment, 2026-10-06 (decided by the command center, item task-ns2604-coop-20261006T155742Z, section 2 (A))

This amends round 5's gate-0 `gateway-cache` check, which passed only with the semantic cache off. The cache **stays on**, because the user's token-saving features stay on. The command center accepts the source evidence together with an observed reading per trial.

- **The source evidence, cited at the tags:**
  - OmniRoute v3.8.51 reads or stores a cached response only for a request with an explicit numeric `temperature: 0`: `src/lib/semanticCache.ts`, `isCacheableForRead` and `isCacheableForWrite`.
  - codex 0.160.x requests carry no temperature: `codex-rs/codex-api/src/common.rs`, `ResponsesApiRequest`, lines 279 to 304, identical at `rust-v0.160.0` and `rust-v0.160.1`.
  - The running gateway build (`omniroute-3.8.51-5f4b3d577-affinity-pr15167`) adds the affinity patch and upstream PR 15167. Neither touches the cache code:
    - the patch changes `src/sse/services/auth.ts` and `sessionAffinityPin.ts` (`evidence/artifacts/omniroute-wire-effort-20261005/patches/045aa81f3.patch`);
    - the PR's file list names no cache file.
- **The per-trial reading (fail closed).** Every trial records GET `/api/cache` before and after it: the launcher for every cell, and `block.py` for CL7b. A trial is **void** when either of these holds (`common.gateway_cache_window`, applied by G13):
  - either reading shows a hit;
  - the database or memory entry count changed between the readings.

  A missing reading, a failed one, or one without its counts voids it too.
- **Gate 0's check** (`grade.gateway_cache_gate`) needs all of the following, or fails:
  - stage 1's reading, with 0 hits and its entry counts;
  - a gateway build that starts `omniroute-3.8.51-`;
  - Codex `codex-cli 0.160.0` or `0.160.1`, the versions the evidence was read at.

### A network namespace per trial, explicit forwards only (item 155742Z (B), approved at 16:43Z)

Each trial runs with `--unshare-net`. Its only routes out are the forwards below, each with its reason (`isolation.NET_FORWARDS`). The pattern is Anthropic's sandbox-runtime (anthropics/sandbox-runtime, tag v0.0.78, `README.md`):
- line 108: on Linux, bubblewrap with network namespace isolation;
- line 124: the sandboxed process's network namespace is removed, so all traffic goes through proxies on the host, reached over Unix sockets bound into the sandbox;
- line 365: an allowlist entry may be an IP literal;
- line 553: socat bridges the proxies.

Inside the namespace, socat listens on each forward's usual loopback port (`isolation.NET_PRELUDE`, which fails closed if the listeners are not ready). Outside, `netfilter.py` serves the sockets, which are bound read-only inside the private runtime folder.

| Forward | Client | Inside | Rule | Reason |
| --- | --- | --- | --- | --- |
| gateway | Codex | 127.0.0.1:21128 | HTTP: `/v1/...` only | Codex's model API (the omniroute profile's base URL). `/api`, the dashboard and the call logs share the port, so the filter is by path. |
| otlp | both | 127.0.0.1:21318 | HTTP: POST `/v1/logs`, `/v1/metrics`, `/v1/traces` | both clients' telemetry export, which the grader's joins read. A receiver serves no reads. |
| ai-memory | both | 127.0.0.1:29374 | HTTP: `/mcp`; POST `/hook` and `/hook/batch`, GET `/handoff`, each naming the trial's own scope | ai-memory stays in the treatment (CC 14:38Z). The web interface, `/admin` and the other routes stay out. |
| model-egress | Claude | 127.0.0.1:3128 (`HTTPS_PROXY`, set for Claude trials only) | CONNECT to `api.anthropic.com:443` and `platform.claude.com:443` | Claude Code's model API and OAuth token refresh (the installed 2.1.291 binary's `BASE_API_URL` and `TOKEN_URL`). |

- **The HTTP filter** admits one request per connection. The request goes upstream with `Connection: close`, and nothing the client sends after its body is relayed. It must be in plain form: no percent-encoding, dot segment or doubled slash in the path, no Upgrade, and one body framing.
- **The CONNECT proxy** tunnels only to the listed host and port pairs. TLS stays end to end.
- **The access log** keeps forward, method, path, decision and status, and never a query, header or body. The only header kept is the gateway's `X-OmniRoute-Request-Id` (below).
- **A login on the management routes is rejected**, as the user's rule is passwordless and frictionless. The path filter replaces it.
- **G13 requires all of the following:**
  - the receipt's network record equal to the plan's for the client: forwards, rules, allowlists, environment and scope;
  - a network namespace of the trial's own (`--info-fd`), distinct from the host's;
  - the record that its forwards ran.
- **What a trial can no longer reach:** every other service on the host's loopback (Dagu, Serena, hcom, the codebase-memory daemon, agentsview, Loki, Grafana and the rest), and the internet except Claude's two model hosts. That includes web tools, `gh`, npm (chrome-devtools' `npx`) and socraticode's Qdrant and embedding servers. This is a treatment boundary for the CC: any further forward is added to `NET_FORWARDS` with its reason.

### The GPT read of a513616d (CHANGES_REQUESTED), folded in (item 164313Z)

- **P1, the call-log detail GET.** The command guard permits it through its id exception (`scripts/hooks/secret_path_guard.py:4657-4658`). Under the CC's interim rule, `common.gateway_calls_for_trial` replaces the thread scan:
  - It runs on the coordinator side after the trial (`collect.py`), never inside a trial.
  - It requests a detail **only** for list rows whose id or correlation id is one of the `X-OmniRoute-Request-Id` values the trial's own responses carried. The gateway forward records those values (OmniRoute v3.8.51 `src/shared/constants/headers.ts`).
  - It keeps only model, status, received and forwarded effort and tier, and the cache source. No body enters a receipt.
  - That the header value is the call log's id or correlation id is read from source, not yet observed. With no match, nothing is requested and G11 stays failed.
  - A test checks that a foreign id is never requested.
- **P2, closure evidence.** Gate 0 (`network-closure`) and G13 require the stage-1 self-test's verified denials (`grade.closure_evidence`, 13 required probes). These cover:
  - `/api/health`, the call logs and the dashboard refused by the filter;
  - the dot-segment and percent-encoded detours;
  - ai-memory's web interface and another scope's handoff;
  - no gateway port for Claude;
  - the local listeners;
  - direct egress, and egress to an unlisted host.

  A missing probe, a failed one or any access fails. Payload-flag counts alone never establish closure.
- **P2, G11 fails closed.**
  - G11 needs the recorded launch tier `default`, and for every gateway call a forwarded tier of `default` or none (OmniRoute then forwards the upstream default) (`grade.tier_evidence`).
  - A missing or unrecognized tier fails, and the call ids are reported. Nulls stay null.
- **P2, ai-memory page detection.** Transport envelopes are normalized apart from content (`grade.mcp_payloads`). Pages are recognized by each tool's response contract (`grade.pages_returned`):
  - `memory_query`: hits;
  - `memory_read_page`: one page with a body;
  - the listing tools: their items;
  - the briefing, handoff and message tools: their text.

  Validity and G13 share one predicate (`grade.ai_memory_invalidates`).

### The answer-channel closure (item 164313Z, section 3 (c); a separate, droppable commit)

The round-6 completeness check found stores outside the hidden roots that hold other sessions' or other trials' content, all readable from a trial, and found the home folder writable, so a trial could leave content for a later one.
- **The home folder is a temporary overlay** (`--overlay-src ~ --tmp-overlay ~`, bubblewrap 0.11.1). A trial reads it and may write it, but nothing it writes there outlives it.
- **What still reaches the host** goes only through explicit binds:
  - the trial's own fixture, clone, -o file and transcripts (its own Claude project), and its private stores;
  - Claude Code's credentials file, which is written back because an OAuth refresh rotates the stored token. A refresh kept only in the overlay would leave the host's login with a spent token.
- **Projects outside the experiment** are now bound back read-only.
- **Closed stores, each an empty tmpfs in the namespace** (`isolation.CLOSED_STORES`):
  - ai-memory's store and hook spool (`~/.local/share/ai-memory`): every scope's database, pages and spooled events. A trial's hooks spool into the empty folder, and its events still reach the server through the ai-memory forward.
  - agentsview's archive of every session on the host (`~/.agentsview`).
  - codebase-memory's project indexes, jcodemunch's index and Serena's logs.
  - Claude's plans, tasks and paste cache.
  - Codex's own folder: its history, session index, logs, and memories, goals and queue databases (and its login). The entries a trial's clone links to come back as temporary overlays: packages (the codex binary), skills, plugins, cache and context-mode. The clone's sessions and context-mode stores stay the trial's private folders.
- **Closed file:** Claude's prompt history is an empty private file in the namespace.
- **G13** lists every closure, so a receipt without the overlay, a closed store's tmpfs or the private history file fails.
- **A negative test per channel** (`test_isolation.ChannelClosure`): a real file the host holds in each channel is gone in the namespace (ENOENT), or empty for the history. Home writes do not outlive the trial. A project outside the experiment cannot be written.

## Round 5 (CC 14:38Z, 14:42Z and 15:17Z)

### The gateway's response cache: not confirmed off

The 14:38Z item asked for a read-only confirmation that OmniRoute on 21128 has no response or semantic cache enabled that could serve one trial's output to another. It is **not confirmed**: the semantic cache is on. By source, it cannot answer a Codex trial.
- **Readings at 14:56Z and 15:30Z** (GET `/api/cache`, named keys only): `semanticCacheEnabled: true`. The semantic cache had 0 hits, 0 misses, 0 database entries and 0 memory entries. The idempotency window was 5,000 ms, with 0 active keys.
- **The semantic cache is OmniRoute v3.8.51's only response cache.** A hit is logged with `cacheSource: "semantic"` (`open-sse/handlers/chatCore/semanticCache.ts`).
- **It cannot answer a Codex trial, by source:**
  - v3.8.51 reads a cached response only for a request with an explicit numeric `temperature: 0`, and stores one only for such a request. The `semanticCacheRequireZeroTemp` switch does not change that (`src/lib/semanticCache.ts`, `isCacheableForRead` and `isCacheableForWrite`; `checkSemanticCache` calls the first before any lookup).
  - codex-cli 0.160.0's Responses request has no temperature field (`codex-rs/codex-api/src/common.rs`, `ResponsesApiRequest`, lines 279 to 304 at rust-v0.160.0).
  - This is source evidence, not an observed run. The per-trial checks below would catch a hit.
  - The switch itself read `true` in the read the correction below describes.
- **The other caches cannot serve another trial's output:**
  - The idempotency window is keyed only by a client's `Idempotency-Key` or `X-Request-Id` header, never by the request body (`src/lib/idempotencyLayer.ts`).
  - The provider-side prompt cache reuses input prefixes and never returns a stored output.
- **Correction:** I read `/api/settings` and `/api/settings/cache-config` through script files. Neither route is on the repository command guard's allowlist (`scripts/hooks/secret_path_guard.py`, `K4_GW_ROWS`), and both also return decrypted secrets. A script file hides the URL from the guard, so those reads went around its policy. Only cache keys and key names were printed, and nothing was stored. The harness now reads only the allowlisted GET `/api/cache`.
- **In the harness:**
  - run.json records the stage-1 reading.
  - Gate 0's `gateway-cache` check passes only while the semantic cache is off.
  - Each Codex trial's launched and exit rows record the hit counts.
  - G13 fails a trial during which the cache counted a hit, or whose call logs show a `cacheSource: "semantic"` response.
- **The decision this needs:** either the co-op switches the semantic cache off on 21128 (a gateway setting), or the CC accepts the source evidence by a ruling, with an amendment that relaxes the gate-0 check.

### The gateway's logs and management routes: returned to the CC (15:17Z)

The GPT read of 2044b2ab named the gateway's log and dashboard APIs as a channel. A trial needs the gateway for inference, and its logs can return other trials' payloads. The retained probe `evidence/artifacts/omniroute-gateway-20260927/scripts/probe_lane.py.txt` lists the logs and fetches payloads at lines 101 and 112. This round's probe is read-only. It uses only routes the repository's command guard allowlists, and changes no gateway configuration.
- **The response cache:** on, as recorded above.
- **Call-log payloads are stored.** At 15:30Z, GET `/api/usage/call-logs?limit=20` answered without credentials. Of the latest 20 rows:
  - 1 carries a stored request body and a stored response body;
  - none carries pipeline details.

  The harness keeps only these counts (`common.gateway_log_exposure`, in run.json as `gateway_logs`). It fetched no payload.
- **The APIs answer without credentials from a trial's namespace.** The stage-1 self-test asks two allowlisted routes from inside the namespace with no credentials, and discards the bodies (`isolation.gateway_reachability`, in the self-test as `gateway_from_namespace`):
  - GET `/api/health` answered 200;
  - GET `/api/usage/call-logs?limit=1` answered 200.

  The network is the host's, so the dashboard and every other management route on port 21128 are as reachable. Only those two routes were asked.
- **What this allows:** a trial could list the call logs and read another trial's stored request and response. This was not exercised on a trial's payload.
- **Minimal closure, proposed for the CC (nothing changed):**
  1. **A per-trial network namespace with explicit forwards.** Run each trial under `bwrap --unshare-net`, so its network leaves only through forwards outside the namespace for the endpoints the treatment needs: the gateway's inference path, the OTLP collector, the ai-memory server, and any other MCP server the treatment configures by URL. The upstream pattern is Anthropic's sandbox-runtime (anthropics/sandbox-runtime at v0.0.78, `README.md`):
     - on Linux it runs bubblewrap with the sandboxed process's network namespace removed (lines 108 and 124);
     - all traffic goes through proxies on the host, reached over Unix sockets bound into the sandbox, which `socat` bridges (lines 124 and 553);
     - the proxies enforce a host allowlist that may name an IP literal such as `127.0.0.1:3000` (line 365).

     socat 1.8.1.1 is installed here; passt (pasta) and slirp4netns are not.
  2. **The gateway's port needs a path rule.** `/v1` and `/api` share port 21128, so a host-and-port allowlist alone still admits the management routes. Either the forward for the gateway admits only `/v1/...`, or OmniRoute's management routes require authentication during trial runs. The second is a gateway setting the co-op owns, and the harness's own call-log reads would then go through the operator.
  3. **Until then, tags.** The grader tags a trial command that addresses the gateway's management routes (`gateway-management-api`) or any other loopback HTTP service (`local-service-http`). The tags are diagnostics.

### Other loopback services (completeness check)

The same shared network reaches every service listening on the host. At 15:47Z, 110 TCP ports listened (`ss -ltnp`: ports and process names only; none was asked anything). They include:
- **Dagu** (21080 and 21081): it runs workflows on request, an execution broker over TCP.
- **Serena's MCP servers** (24 ports, 24282 to 24305): their tools include `execute_shell_command`.
- **hcom** (30 ports): messaging between live agent sessions.
- **The codebase-memory daemon** (9749): the host's index. A trial's own codebase-memory server starts a private daemon (above), but this port stays reachable.
- **agentsview** (21808): it serves the native session folders, where finished trials' rollouts are published.
- **Loki** (21300 and 21396) and **Grafana** (21301): earlier trials' telemetry, which the grader joins.
- The other named services:
  - **ai-memory** (29374);
  - **vLLM** (28231, and 6 engine ports);
  - the OTLP collector (5 ports);
  - **Prometheus** and **Alertmanager** (21090 and 21093);
  - rootlesskit port forwards (4002, 5900 and 21633).
- **28 ports whose owner `ss` does not name for this user.** Among them are the older gateway's ports (20128 to 20134) and the WSL DNS resolver's port 53.

Their authentication was not probed. The closure is the network namespace above, which forwards only what the treatment needs.

### Bind triples, ordering and options (P2-1, accepted at 15:17Z)

G13 now checks each bind in the receipt as an exact (operation, source, destination) triple of the trial's plan (`isolation.permitted_binds`).
- **The private folder is derived.** The trial's private folder comes from its trial id (`isolation.private_dir`), never from the receipt.
  - Binding the shared `work/last` onto the trial's own `work/last` now fails.
  - So does any private store bound from the shared store, and a receipt that names another folder as its private one.
- **Kept projects:** a project outside the experiment is permitted only bound onto itself, one level under the projects folder.
- **Declared answer sources:** the inaccessible file over a declared answer source must come from the trial's private `blocked` file.
- **Ordering.** No bind of host content may come after a cover whose path is its own destination or below it. A cover is a tmpfs, a private folder or the inaccessible file, declared answer sources included. So a permitted bind in the wrong place, such as the home's own bind moved after the covers, fails.
- **Options.** The options sha256 in the receipt must be the one its operations give.
- **Negative cases** (`test_isolation.G13Check`):
  - a permitted destination from a shared source;
  - a private store from the shared store;
  - a receipt naming another private folder;
  - a declared source bound from itself, and its parent bound back after the cover;
  - the home's bind after the covers;
  - options that differ from the operations.

### The normal service tier (14:42Z)

- **Every Codex cell sets `service_tier=default` explicitly:**
  - CL3, CL4 and the prompted cells: `-c service_tier=default` on the line;
  - CL7: the runner's `configOverrides`;
  - CL7b: the provider's `cli_config`.
- **Checks:**
  - Stage 1 checks every cell kind and refuses the run if any lacks it (`service_tier_check` in run.json).
  - The launcher and block.py refuse a launch without it, and record the tier in each Codex trial's launched row.
  - G11 reports the tiers and fails on any other.
- **The client setting does not decide the effective tier through OmniRoute.** codex-cli 0.160.0 omits `service_tier` from the request when it is `default` (`protocol/src/openai_models.rs`, `service_tier_for_request`, and its test `service_tier_for_request_omits_explicit_default_tier`). OmniRoute v3.8.51 then decides the outbound tier: a request's own tier first, else its global Codex mode (`codexServiceTier`, "priority" when enabled without a tier), else the connection's default (`src/lib/providers/codexFastTier.ts`).
- **The effective tier is the forwarded one.** The call-log join keeps the tier the gateway forwarded (pipeline details, on only for pilot runs), and G11 fails on a forwarded `priority`.
- **Unread:** the gateway's `codexServiceTier` value lives in `/api/settings`, which the guard does not allowlist. So it is unread here: the operator can read it in a terminal, or the pilot's pipeline details show it.

### ai-memory: one scope per trial

- **Kept in the treatment, scoped per trial.** ai-memory stays in the treatment, with workspace `organic-e2e` and project `<trial_id>`.
- **How the scope reaches the trial.** ai-memory 2.5.2 documents one carrier for both its lifecycle hooks and static MCP clients: the `.ai-memory.toml` marker (`docs/marker-file.md` at v2.5.2).
  - Hooks walk up from the cwd to the first marker.
  - A static client passes the marker's workspace and project on every project-scoped call.
  - The hook has no flag or environment variable for the scope (`ai-memory hook --help`).
- **Where the marker lives.** The wrapper binds a per-trial marker at `~/.cache/ws/.ai-memory.toml`. That file exists only in the trial's namespace, above its fixture: the fixture is unchanged, and no other trial or host process sees it.
  - The self-test reads it back in the namespace.
  - ai-memory's own `hook --check-capture`, run from the fixture in the namespace, reports `marker_present: true` and `admits_capture: true`.
  - That command reports the marker, not the scope values a hook would send. The values sent are as documented, not observed.
- **The grader checks every ai-memory call** (Claude's `mcp__ai-memory__*` calls and Codex's `ai-memory` MCP items):
  - A `global=true` query, or a write to the `_global` scope, is a tag (`ai-memory-global`).
  - A call that returned a page of another trial's scope makes the trial invalid and fails G13. Another trial's scope is `organic-e2e/<another trial>`, or a project named after another trial's fixture folder (hook captures from before this round).
  - A call with no explicit scope reads the server's active-project pointer, which every other session's hooks move. Its pages carry no scope (an implicit `memory_query` returns `id`, `path`, `title`, `snippet` and `rank` only). So such a call that returned pages is unverifiable, and is counted the same way.
- **Re-grade of smoke-20261006c:** one Codex env trial made a global query and an implicit query that returned pages. Under this rule that trial would be invalid on this count alone.
- **Why files alone cannot close it.** Masking files cannot close ai-memory: its server answers over HTTP from outside the namespace. The closure is the one the 14:38Z item ruled: the per-trial scope, plus the grader's invalidation of any trial that received another scope's page or an unverifiable one.
- **R2 lint:** the marker's `organic-e2e` hits checks e and f, with the same tokens the OTel lane tag already carries in every launch line. It is a disclosed residue, which the item's scope name requires.

### Private /tmp, /var/tmp, /dev/shm and IPC

- **Each trial gets an empty tmpfs** over `/tmp`, `/var/tmp` and `/dev/shm`. `/dev` stays the host's (`--dev-bind`), with only `/dev/shm` replaced.
- **And an IPC namespace of its own** (`--unshare-ipc`), the extension the GPT read proposed: no System V IPC object or POSIX message queue passes between trials.
  - bwrap's `--info-fd` record then names the IPC namespace.
  - G13 fails a trial without one, or one that shared the host's.
- **What stays bound in:**
  - Claude's area, `/tmp/claude-<uid>`, is bound into the private `/tmp` from the trial's own folder.
  - The X11 socket folder is bound back when it exists. It holds sockets only.
- **Sockets found in the host's `/tmp`:**
  - Grafana's plugin sockets, which no trial tool uses.
  - Chrome's singleton sockets. A trial's browser starts its own, unshared.
  - The codebase-memory MCP daemon's socket (`/tmp/cbm-daemon-<uid>`). Under the wrapper, `codebase-memory-mcp` started its own daemon in the private `/tmp` and listed its 17 tools. Its index is then the trial's own: the host daemon's indexes, other trials' fixtures among them, are out of reach. Its tools are unchanged.

### Host services, receipts, the CL7b census, fanotify

- **Host services are tagged, as diagnostics:**
  - `systemctl` or `journalctl` with `--user`, and `systemd-run`: `user-systemd`;
  - `docker`, `docker-compose` and `podman`: `docker`;
  - a Windows program (`*.exe`, or a path under `/mnt/c/Windows/`): `wsl-interop`;
  - direct HTTP to the ai-memory server's port: `ai-memory-http`;
  - the gateway's `/api` routes: `gateway-management-api`;
  - any other loopback HTTP service: `local-service-http`.
- **Receipt privacy (the 14:38Z ruling, and P3 accepted at 15:17Z).** A published receipt (`isolation.public_receipt`, which the grade embeds) carries:
  - only the count and the sha256 of the sorted names of the projects bound back;
  - every other string through `public_text`: the home path becomes `~`, a project folder name becomes its hash, and so does any other token that carries the home path in Claude's slug form (`-home-<user>-...`), wherever it sits (argv, operations, the visible argv, the hidden list).

  The exact mount operations stay private:
  - the raw receipt is in the run's ledger, appended with mode 0600;
  - CL7b's options file is 0600 in the trial's 0700 private folder;
  - the self-test's own report is written 0600.
- **CL7b's census.** The verification gap the read noted is closed: block.py samples the tree of CL7b's wrapper while the eval runs, as the launcher does for the other cells (`isolation.AppServerCensus`).
  - Every 2 s it reads bwrap's namespace record and records the mount namespace of the child and each descendant.
  - It skips a child that started before the census, so a reused pid is never sampled, and the wrapper removes an earlier attempt's record first.
  - The exit row's `isolation_runtime.tree` carries it, and G13 reads it as it reads the launcher's.
- **The sampling limit, stated.** Both censuses sample every 2 s, so a process that starts and ends between two samples is not seen. The namespace record and the locked mounts do not depend on the census: a process below bwrap cannot join the host's mount namespace, which needs CAP_SYS_ADMIN in the user namespace that owns it (setns(2)).
- **fanotify** stays a documented optional audit and is never a gate. There is no sudo.

**Residual channels after round 5:**
- **Services on the host's loopback**, reached over the shared network:
  - the gateway's management routes, whose call logs keep payloads and answer without credentials (returned to the CC above);
  - the execution brokers and stores listed under "Other loopback services";
  - the ai-memory server (checked by scope).

  The proposed closure is a per-trial network namespace with explicit forwards.
- **Host execution brokers over local sockets** (the user manager, the session bus, rootless Docker, WSL interop): unreachable since P2-2's commit, below, and still tagged.
- **ai-memory's `_global` scope:** its pages carry no trial ownership, so a page another trial wrote there is not caught (a write to it is tagged).
- **The Windows drives** (`/mnt/c`, `/mnt/e`, `/mnt/f`, `/mnt/z`) are visible read-only. They hold no hidden root, but a copy of one there, such as a backup, would not be hidden. They were not searched.

### Host execution brokers: unreachable (P2-2, upheld at 15:17Z, in its own commit)

**The finding.** `/run/user/$UID` stayed visible and writable in round 4, so a process outside the namespace could be asked to read a hidden answer:
- `systemd-run --user --pipe --wait cat <answer>` has the user manager run the command and return its output (systemd-run(1));
- rootless Docker's socket was reachable the same way, through a container that mounts the host's view;
- **WSL interop**, found this round, does the same. A Windows program started from the trial runs outside its namespace and reads the distribution through `\\wsl.localhost\<distro>`:
  - `cmd.exe` ran from a bwrap namespace and named that path;
  - with `/run/WSL` hidden, it failed (`UtilConnectUnix ... connect failed 2`).

**The closure** (`harness/isolation.py`):
- **Empty private folders.** Each trial gets an empty private runtime folder, a tmpfs over `/run/user/$UID` with mode 0700 (`--perms 0700 --tmpfs`), as XDG_RUNTIME_DIR must be. It also gets an empty `/run/WSL`.
- **No broker socket in the namespace:** not the user manager's (`systemd/private`), the session bus's (`bus`), rootless Docker's (`docker.sock`), the ssh-agent's or the gpg-agent's.
- **Nothing is passed through.** The evidence:
  - every launch path's client starts with the empty folder (the self-test's 7 client checks);
  - neither native client launches an MCP server through Docker;
  - Codex keeps MCP OAuth credentials in files (`mcp_oauth_credentials_store = "file"`), and no Secret Service runs on this host;
  - no suite task names Docker, systemd or a Windows program.

  `RUNTIME_PASS_THROUGH` would name any later pass-through, each with its reason.
- **The system bus stays visible.** An unprivileged `systemd-run` against the system manager needs polkit's admin authentication, which a trial cannot give: `org.freedesktop.systemd1.manage-units` is `auth_admin`, or `auth_admin_keep` when active (`/usr/share/polkit-1/actions/org.freedesktop.systemd1.policy`, systemd 259).
- **G13** lists the runtime folder and `/run/WSL`:
  - a receipt without their tmpfs fails;
  - binding the host's runtime folder in is a bind outside the plan.

**Negative tests** (`test_isolation.HostBrokers`). Each attempts, inside a trial's namespace, the connection a trial would make, and expects it to fail. Each runs only where the broker exists on the host:
- `systemd-run --user --pipe --wait true` fails: "Failed to connect to user scope bus via local transport: No such file or directory";
- Docker's `/_ping` over `docker.sock` (`curl --unix-socket`) exits 7, and `docker -H unix://... version` fails;
- WSL interop (`cmd.exe /c ver`) fails;
- the runtime folder is 0700 and empty, and a write there never reaches the host's;
- the ssh-agent's socket is absent.

Each test first checks that the socket is absent. On a harness that binds the host's folder in, it fails there, before contacting any broker.

**Self-test probes** (`isolation.host_broker_probes`, a stage-1 pass condition):
- Outside, the sockets exist, and the user manager and Docker answer read-only queries: `systemctl --user is-system-running` gave `degraded`, and Docker's `/_ping` gave `OK`.
- Inside, all five sockets (the user manager, the session bus, Docker, the ssh-agent and WSL interop) are absent, and each attempt fails.
- A broker whose socket is present inside is never contacted: the probe fails closed.

The tags stay, as diagnostics. As the 15:17Z item ruled, tags alone do not close this, since validity is structural.

## Confirmed (CC 11:43Z)

Item `task-ns2604-coop-20261006T114319Z` confirms the five points, with three additions the harness now implements:

1. **The no-result hold applies to every Claude cell,** not only claude-env. One rule for all Claude cells keeps the arms symmetric.
   - The launcher's `holds_cell()` depends only on the client and the deadline evidence: the elapsed time and when the result arrived (see the 87f9f1d7 fixes below).
   - It never depends on the cell, arm, kind (CLI or SDK) or stage.
2. **gh counts as PATH-only.** It is also reported in its own "vendor-skill surface" stratum: a tool reached through a client vendor's official skills repository. `CLI_VENDOR_SKILL_SURFACES` holds gh through openai/skills@49f948fa (gh-fix-ci, gh-address-comments). Such trials stay out of OIR and are counted per item as `n_vendor_skill_surface` and `used_vendor_skill_surface`, with a use rate and its Wilson interval.
3. **The answer-source list stands as written.** Two classes are added, and the principle is set: reading a source is legitimate work; reading an oracle's output is not. A host checkout's copy of an oracle input stays a tag.
   - Grader expected-output files outside oracles.json:
     - everything under the coordination state directory (run roots with run.json's oracles_reproduce, grades and gate0.json; the suite cards; prompted and stage-0 outputs);
     - the whole fixture cache (oracle-work/ beside oracles.json);
     - any published file of this experiment other than its sources (the harness, the protocol, the pilot spec, these notes, a README), such as a later grade or receipt in the repository;
     - any path that `prepare.py --answer-source-path` declares.
   - Earlier smoke or pilot receipts holding graded outputs: the v1 and v1.1 smoke and pilot captures all sit under the coordination state directory (or, for the U1 probe, the fixture cache), so they are covered. A later published one is covered by the rule above.
   - Another trial of the same task now also matches by trial id, which covers its Claude transcript and its trial-root answer file as well as its fixture.
   - The 2026-10-04 foundation E2E receipts in the repository (`evidence/artifacts/ns2604-e2e-20261004/`) grade another E2E, and three suite tasks use their `slots.json` and `summary.json` as input, so reading them stays legitimate source work.
4. **The re-baseline cost holds** because the Codex trials in flight form one Codex cell, the arm's concurrency unit, while Claude adds one trial.
   - The pilot runs one Codex cell at a time; stage 2 and stage 3 cells, and stage 4's Codex blocks, run one after another.
   - `rebaseline_cost_ok()` checks the bound at every re-run, CL7b included: at most one Claude trial and one Codex cell. If the Codex re-runs ever spanned two cells, it falls back to one trial per arm. Past either bound, the run stops.
   - G4 reports the cost (`rebaseline_cost`).
5. **0.15 of a window per trial is the starting default.**
   - After the first stage-4 Claude block that yields an organic trial with two meter readings, `pilot.py` recalibrates it to the measured p90 per trial, per window (`meter_calibration()`: nearest rank, account-wide deltas, at least the meter's 0.01 resolution). It writes the result to `meter-calibration.json` in the run root, with the value it replaced.
   - Left out of the calibration:
     - a trial with fewer than two in-stream readings (its first reading is also its last, so its delta would be a false 0);
     - a window whose `resetsAt` differs between the two readings (it rolled over mid-trial).
   - The operator step is `grade.py meter-calibration --run-root <root> [--write]`.
   - The value each trial started with is recorded in its ledger rows (`expected_usage`, `meter_expected_usage`) and in the grade (`meter_expected_usage`, with the calibration and the current p90).
   - On smoke-20261006c's three organic Claude trials, the p90 would be 0.06 (five-hour) and 0.01 (seven-day).

## Confirmed (CC 12:30Z)

Item `task-ns2604-coop-20261006T123036Z`:

- **(a) The 2026-10-04 foundation E2E receipts stay sources.** Confirmed; no code change.
  - The files in `evidence/artifacts/ns2604-e2e-20261004/` grade another E2E, and three suite tasks read `slots.json` and `summary.json` as input.
  - A file there would become an answer source only if it held a graded output of this experiment's own trials. None does today.
- **(b) The final-turn time and the result-event time are recorded for every cell,** Codex included (CL3, CL4, CL7, CL7b and the prompted and gate-0 cells), so the comparison keeps one schema across arms. In a Codex cell the two normally coincide.
  - **Launcher Codex cells:** the final turn ends with the last `agent_message` that no tool item follows, and the result event is `turn.completed` (or `turn.failed`). Both are recorded in the exit row's `final_turn_end_s`, `final_turn_end_at`, `time_to_result_s` and `result_event` fields, as for Claude.
  - **CL7b and runs prepared earlier:** CL7b has no launcher. For it, and for runs prepared before this ruling, the grader reads both times from the main rollout's own timestamps (`codex_turn_times`: the last `AgentMessage` with no tool item after it, and `task_complete`).
  - **Grade report:** it lists both times for every launched trial (`completion_times`). It also checks that every Codex trial carries both (`timing_record`, which lists any Codex trial missing either).
  - **Smoke-20261006c:** all 11 Codex trials carry both times in the read-only re-grade. The two times sit 0.1 to 0.4 s apart in most, with a few seconds between them in two of the 11 (8.4 s and 3.4 s).

## Fixes from the GPT micro-check of 87f9f1d7 (2026-10-06)

That check requested changes for four P2s (`cc-reads-20261005/pr786/GPT-VERDICT-87f9f1d72.md`, outside the repository). Each is fixed.

Findings 1 and 4 tune the command classifier. The GPT micro-check of 1f81d645 found both still partial, and the structural G13 of 13:29Z supersedes them (see the first section): the classifier described here is now a diagnostic tag. Findings 2 and 3 stand.

1. **Filename-only operations invalidated trials.**
   - Access is now judged from each command's arguments and each tool's output mode.
   - **Content access:**
     - a program that prints content or runs code over it;
     - grep or rg printing matching lines;
     - find (every `-exec`, `-execdir`, `-ok` or `-okdir` action) or xargs running such a program, judged by that program's own arguments (`find ... -exec grep -l` and `xargs grep -l` return names only). xargs options are read as the installed GNU findutils xargs 4.10.0 `--help` lists them, so `-i`, `-l`, `-e` and `--replace` take no separate word;
     - git show, cat-file, blame, diff and grep, including after global options such as `git -C <dir>`;
     - tar or unzip to stdout;
     - an input redirection;
     - the Read tool, and the Grep tool in content mode.
   - **Names or metadata only, so a tag:** ls, find, stat, file, realpath, wc, git ls-files and status, rg --files, grep or rg with -l, -L, -c or -q, cp, mv and rsync, Glob, and the Grep tool's default `files_with_matches` and `count` modes.
   - **A filter fed by a pipe:** when it names no file (`ls <dir> | head -n 5`, `... | sort -r`, `... | grep x`), it reads the previous command's output, not a file, so it is no read.
   - Only successful content access that returned content can make an answer source invalidate a trial.
2. **CL7b repetitions shared one attempt.** Chosen: the smaller correct change, which is to reject a CL7b repeat above 1 until each repetition gets its own attempt.
   - `block.py` refuses such a block, and `prepare.py` refuses `--repeat-override` above 1 while `codex-app-server` is among the cells. Nothing is written in either case.
   - The pilot's CL7b repeat is 1, and a re-run is a new block, which gets a fresh attempt.
3. **The hold missed a timeout that needed SIGKILL.**
   - The hold now reads the evidence (`deadline_without_result`): the session ran to T or past it with no result event before T, however it ended. That includes the timeout's SIGKILL after its grace (rc 137, now censored as `timeout_killed`) and a launcher kill at or after T.
   - A session that fails or is killed before T is still `killed` and does not hold its cell.
   - The grade's `no_result_trials` uses the same rule.
4. **Same-task Codex transcripts stayed tags.**
   - The grader now maps each Codex trial to its thread ids (`codex_threads_by_trial`): the thread collect.py joined, plus every collected rollout, main and child, whose file name ends with its thread id.
   - A successful content read of a same-task trial's rollout is an answer source (`same-task transcript`), whichever copy it reads: the native original under `~/.codex/sessions`, a clone's alias of it, or a collected copy.
   - A glob or directory-wide read (`cat ~/.codex/sessions/.../*.jsonl`, `rg` over `~/.claude/projects`) names no id in its input. For such a successful content read, the content it returned is scanned for same-task trial and thread ids (`answer_source_evidence: returned content`).
   - The scan runs only when the read itself reaches a transcript, a store or another G13 location. That is judged from:
     - its operands;
     - the directory of an earlier `cd` in the same command;
     - for a read whose operand comes from another command (a loop variable, `{}`, a command substitution, xargs), every path the command names;
     - for an interpreter whose program comes from a heredoc (`python3 - <<'PY'`), the whole command text.
   - A listing beside an unrelated read (`ls ~/.codex/sessions/... && cat notes.md`) is therefore not scanned, and neither is a listing piped into a filter.
   - **Known limits:** a script file run by an interpreter (`python3 x.py`) and a `cd` from an earlier call are not followed. Their returned content is not scanned, though the reasons judged from the input still apply.
   - Other tasks' transcripts stay tags.

## Fixes from the GPT first-pass read of 5aa2bfdc (2026-10-06)

That read requested changes for seven P2 findings (`cc-reads-20261005/pr786/GPT-VERDICT-5aa2bfdc9.md`, outside the repository). Each is fixed in the harness:

1. **Clone hook-trust changes passed G4.**
   - A hook or project trust change in the trial's own clone (`CLONE_TRUST_KEYS`) is now persistent on its own (`s7_persistent_change` reports `clone_trust_changed`). The launcher stops the run for it, and no re-baseline absorbs it.
   - G4 fails on it for every launched trial (`clone_trust_changed_trials`), re-baselined ones included.
   - CL7b compares its clone's trust before and after each attempt (`clone_trust_view`) and stops the run on a change.
2. **Concurrent exits could stop an accepted re-baseline.**
   - `try_rebaseline` now judges the change again inside the lock, against the baseline in force at that moment. An exit whose change another exit already absorbed gets `absorbed` and is re-run without a STOP. The launcher then refreshes its S7 judgement against that baseline.
   - Only an additional change, a refused key or a new trust entry stops the run.
3. **A resume counted interrupted attempts as done.**
   - An attempt now counts toward its test's repeat only when its last exit is terminal and not carried forward, or while it is still running.
   - On resume, `reconcile_orphans()` gives an attempt that launched without an exit, and whose processes have ended, an `interrupted` exit, and carries it forward.
   - A launcher failure after the launch row writes `launcher_error_after_launch`, also carried forward.
   - Launch rows are never removed, so the Claude session cap still counts every actual launch.
4. **CL7b rate limits were consumed.**
   - The block keeps a sanitized class of the provider's own error (`classify_provider_error`; never its text).
   - A CL7b rate-limit error marks the attempt `rate_limited`, sets STOP.codex as a Codex launcher trial's limit error does, and is carried forward.
   - The block's account-wide gateway counts never mark a trial on their own.
5. **CL7b re-runs reused the first attempt's identity.**
   - Every CL7b attempt after the one stage 1 built gets its own trial id, fixture, clone and provider config, under the same test ref (`allocate_app_server_attempt`), with its own ledger rows.
   - Attempts are counted per trial id, so a carried attempt never suppresses a later one, and G10 reads the re-run, not the carried attempt.
6. **G13 invalidated mentions and failed reads.**
   - The reach classifier now keeps each call's status, access type and returned content (`call_access`).
   - Only a successful read that returned content can make an answer source invalidate a trial. A path that is mentioned, listed, written, or read without success stays a tag (`answer_source_mentions`).
   - That is the 11:43Z principle: reading the oracle's output is what invalidates.
7. **G11 passed with no forwarded effort.**
   - `g11_trial_ok` requires an observed, nonempty forwarded-effort value.
   - Pipeline exposure is reported apart, and the calls with no value are listed (`gateway_calls_missing_forwarded_effort`).

## 1. Censoring (finding 3)

**Decision:**
- T rises to 1,800 s.
- Each cell records two times: the model's final turn end and the result event.
- A cell is complete only when its result event arrives. A final turn alone is not completion, because background Workflows may still be running.
- If claude-env still gives no result by 1,800 s, the cause is diagnosed before the pilot goes on. A background workflow that never ends is one example.

**Harness:**
- **`common.py`:**
  - `T_SECONDS = 1800`. The protocol's 900 s stays as `PROTOCOL_T_SECONDS`, for runs prepared without a completion record.
  - `CLAUDE_COMPLETION_DEFAULT = "complete-at-result"`.
- **`prepare.py`:**
  - These are the stage-1 defaults, and run.json records this decision as their amendment.
  - Another policy or T needs its own `--amendment-ref`.
  - T applies to every cell, including CL7b's turn timeout.
- **`launcher.py` completion rule (unchanged):** a result event before T completes the trial. A result written at or after T, on the timeout's SIGTERM, censors as `timeout_after_result`.
- **`launcher.py` records per trial (Claude since decision 1, Codex since the 12:30Z ruling):**
  - `final_turn_end_s` and `final_turn_end_at`: the main thread's last assistant text with no later tool call or tool result. Claude Code 2.1.291 leaves `stop_reason` unset on stream-json assistant events, so the content decides.
  - `time_to_result_s`, and the result event's own fields.
- **`launcher.py` when a Claude trial has no result before T:**
  - It writes a `no_result_diagnosis` with:
    - whether the final turn ended;
    - the last main-thread event;
    - open tool calls, by name;
    - background-task counts and types;
    - the processes at the last poll.
  - It writes `HOLD.<cell>`. Later trials of that cell are refused as `held_for_diagnosis` and carried forward until the operator removes the flag.
  - `block.py` refuses the cell's blocks too, so pilot.py's Claude chain stops at that cell's next test until the flag is gone.
- **`grade.py`:**
  - For runs whose launcher predates this decision, it reads the same two times from the stream.
  - The grade lists them as `completion_times` and `no_result_trials`.
- **Confirmed (CC 11:43Z), point 1:** the hold applies to every Claude cell, not only claude-env (`holds_cell()`).
  - Since the 87f9f1d7 micro-check, the rule reads the evidence, not the exit code: the session reached T with no result event before T. A timeout that needed SIGKILL therefore holds the cell too.
- **Confirmed (CC 12:30Z), (b):** the two times are recorded for every cell, Codex included (see that section).

**Offline re-grade of smoke-20261006c:**
- claude-native's final turn ended at 578.7 s, and its result event reports duration_ms 575,920. The result arrived at 900.7 s.
- claude-env never ended its final turn: its last main-thread event was a tool call. It gave no result.

## 2. Exposure (finding 17)

**Decision:**
- A CLI counts as exposed when its own upstream installer has put its native surface in place: a hook, a skill or an instruction file, as `rtk init -g` does.
- Presence on PATH alone does not count.

**Harness:**
- **`common.py` `CLI_NATIVE_SURFACES`** lists:
  - mineru: MinerU's own skill, opendatalab/MinerU `skills/mineru` at c221cc41, installed through the supported `--manifest` route (docs/decisions/2026-10-04-2604-e2e-fix-wave-g3-code-docs.md);
  - worktrunk: Worktrunk's own Claude and Codex plugins.
- **`grade.py` `cli_exposure()`** checks each trial's own listing: the Claude init's plugins and skills, and the Codex rollout's `world_state` skills catalog.
- **OIR:** a CLI target that is only on PATH is not exposed.
  - Its trials are counted in `not_exposed_path_only`, never as misses.
  - The item has no OIR of its own.
- **PATH-only under this rule:** every other CLI item, including:
  - gh: its skills gh-fix-ci and gh-address-comments come from openai/skills, not from gh's installer;
  - rtk on Codex: `rtk init -g` registers a hook that the per-trial clone leaves untrusted (§12.3), and Codex does not expand the `@RTK.md` line (§2.2).
  - On Claude, rtk is the hook item hook/claude/rtk, not a CLI item.
- **Confirmed (CC 11:43Z), point 2:** gh is PATH-only. Its trials are also reported in the vendor-skill surface stratum.

## 3. G13 host-checkout reads

**Decision:**
- Tag them; never deny them, because a deny changes the treatment.
- The primary analysis reports tagged trials separately.
- A trial is invalid only if it reads the task's gold or a fixture answer source.

**Harness (`grade.py`):**
- Every G13 reach category is a tag (`tagged`).
- These answer sources invalidate the trial:
  - the coordination category: run roots with the oracle runs and other trials' drafts, the suite cards, and the fixture cache with `oracles.json`;
  - the fixture or Claude transcript of another trial of the same task.
- G13 passes when no trial read an answer source. It also lists the tagged trials and their categories.
- OIR is reported per stratum (`oir_untagged` and `oir_tagged`, each with its Wilson interval) beside the pooled `oir`.
- **Confirmed (CC 11:43Z), point 3:** the list stands, with grader expected-output files outside oracles.json and earlier graded smoke or pilot receipts added (see the section above). A host checkout's copy of an oracle input stays a tag.
  - `answer_source_reasons()` names each reason: harness store, experiment output, declared grader output, same-task fixture or same-task trial.

**Offline re-grade of smoke-20261006c:**
- G13 now passes; it failed under the old rule.
- 3 trials are tagged: host-checkout 3, user-harness-file 1.
- No trial read an answer source.

**Superseded at 13:29Z** (item `task-ns2604-coop-20261006T132948Z`, the first section above). The tags stay, but answer-source reads no longer invalidate a trial; they are a diagnostic. G13 now checks that the wrapper hid every listed answer source. Under that rule the same re-grade fails G13 for want of receipts.

## 4. chrome-devtools

**Decision:** log it with a watcher only; no pre-execution deny.

**Harness:**
- The behaviour is unchanged. The watcher logs every chrome-devtools MCP call in both clients as a hit that does not halt the trial, and `grade.py`'s comment cites this decision.
- The harness adds no pre-execution rule for the server.

## 5. G10

**Decision:** the gateway entry is confirmed as best-effort. Record that call logs undercount clients that exit fast.

**Harness:**
- The G10 gate records this as `gateway_entry`.
- A missing entry stays a gap, never the gate, as at 9835f66c.

## 6. The §9.1 meter guard, amended

**Decision:**
- Compare the trial's expected usage with the remaining headroom.
- Don't require a quiet account: under the standing rule, limits never gate work.
- Mark any trial that hits a rate limit, and re-run it.

**Harness:**
- **Start rule:** start when expected usage ≤ 1.0 − utilization in both windows.
  - It is checked inside the lock and again on the trial's own first in-stream reading.
  - A window whose `resetsAt` has passed counts as fresh, so a reading taken before its own reset no longer blocks starts for up to 30 minutes.
- **Removed:** the 0.50/0.75 prior, the 0.80/0.85 kill thresholds and the +0.15 rise guard. All three read the account-wide meter.
- **Expected usage:** run.json `claude_meter.expected_usage`, set by `prepare.py --claude-expected-usage`.
  - The default is 0.15, the protocol's own per-trial fan-out bound.
  - The grade reports each trial's account-wide meter delta. The protocol's after-pilot rule uses m_p90.
  - **Confirmed (CC 11:43Z), point 5:** 0.15 is the starting default, recalibrated after the first pilot block to the measured p90 per trial and recorded per trial (see the section above).
- **Short of headroom:** the trial writes DEFER.claude with the window's reset time. pilot.py clears the flag on resume once the newest reading leaves headroom.
- **Rate limits:**
  - A Claude trial that receives a rejected `rate_limit_event`, or an error result naming a limit, is stopped and marked `rate_limited`.
  - It is carried forward and re-run, and DEFER.claude waits for headroom.
- **Codex (§9.2, not part of this decision):**
  - A limit error in a trial stream still stops the Codex chain (STOP.codex).
  - The trial is now marked `rate_limited` and carried forward, so the resume re-runs it.

## 7. In-run re-baseline

**Decision:** adopt it if it costs at most one extra cell per arm.

**Harness:**
- **One in-run re-baseline per run** (`REBASELINES_PER_RUN = 1`).
  - The first persistent S7 change becomes the run's new baseline: `s7/baseline-r1.json`, logged in `rebaselines.jsonl`. It can be found at a launcher trial's exit, or at a block's start when no block was running.
  - **Never absorbed** (`REBASELINE_REFUSED_S7_KEYS`):
    - the arm-defining files, ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md (§2.2);
    - ~/.claude/settings.json, whose hash the native arm's probe rests on (§2.1: a change needs a new probe);
    - every trust-bearing key: Codex `hooks_state`, the Codex project table and trusted set, the Claude trusted set, the trust fields of existing Claude projects, and removed projects;
    - a newly trusted project.
- **Cost:** the trials running at that moment are carried forward and re-run (`host_change_rebaselined`).
  - The Claude chain runs one trial at a time.
  - A Codex block runs up to its `-j` trials at once: 3 for codex-native and codex-env in the pilot, 2 for the SDK cells. So one re-baseline can re-run one Claude trial plus up to `-j` trials of the Codex cell in flight.
  - A CL7b trial, which has no launcher, is re-run when a re-baseline falls inside its eval.
  - A change found between blocks costs no trial.
- **What still stops the run, as before:**
  - any further persistent change;
  - a refused key;
  - a persistent change found at a block's end that no launcher absorbed. CL7b has no launcher, and a change after a block's last trial exits is seen only at the block's end; `block.py` writes STOP.
- **G4:** it lists re-baselined trials and the re-baseline instead of failing on them.
- **Confirmed (CC 11:43Z), point 4:** the cost holds, because the Codex trials in flight form one Codex cell, the arm's concurrency unit, and Claude adds one trial. `rebaseline_cost_ok()` enforces it, with one trial per arm as the fallback cap. Past it, the run stops.

## 8. RP4 (G11)

**Decision:**
- Enable the gateway's pipeline details only for the pilot runs.
- Keep only the effort fields in receipts.
- Then disable the pipeline details again.
- This is a host change, and the co-op applies it.

**Harness:**
- It never switches the gateway.
- From the pipeline details it keeps only `providerRequest.reasoning.effort` and `providerRequest.reasoning_effort` (`forwarded_effort`). It stores none of the rest of the payload.
- `prepare.py --gateway-pipeline-details on|off` records the operator's statement in run.json.
- The grade's G11 entry adds what the call logs showed: on, partly on, off or no calls.

**Offline re-grade of smoke-20261006c:** off (127 calls, none with pipeline details), so G11 still fails there.

## Not in this change

- **Decision 9:** Codex standalone web search returns 404 through the gateway (`/v1/alpha/search`). The fix is to the co-op's host profile wiring; neither this file nor the harness changes host configuration.
- **The `ack` row:** the item asks for one in the command-center ledger. That row is the co-op's to append.

## Verification (offline; no pilot or smoke)

- **The answer-channel closure commit:** the focused module passes 87 of 87 tests, client starts included.
  - **Red run.** On the round-6 commit without it, exactly its 11 closure tests are red (9 fail, 2 error), and the other 76 pass.
  - **Stage-1 self-test** with the overlay and the closed stores:
    - 79 probes hidden, all with ENOENT, 30 of them in the closed stores;
    - Claude's history reads 0 bytes inside;
    - home writes stay in the namespace, and a kept project is not writable;
    - 18 of 18 network expectations are met, and all 7 client checks pass.
- **Round 6** (the Gate 0 amendment, the network namespace and the GPT read of a513616d): the focused module passes 76 of 76 tests, client starts included.
  - **Red run.** The same tests on the round-5 head a513616d: 4 fail and 16 error, one of them the network class's set-up, whose 4 tests do not run.
  - **Stage-1 self-test** (`isolation.py selftest --clients`, no model call):
    - 49 probes hidden, all with ENOENT, and 7 of 7 client checks pass;
    - 18 of 18 network expectations are met, over 10 sampled local listeners;
    - the IPC and network namespaces are distinct from the host's;
    - the broker sockets are absent, and the runtime folder holds only the forwards' socket folder;
    - no home path or home slug is in the report.
  - **Read-only re-grade of smoke-20261006c.** The run root is unchanged, and no gate's pass changes against its 10:48Z grade. G13's closure evidence is missing, since that run predates the probes. G11's tier evidence fails for its 11 Codex trials, as it fails closed.
- **P2-2's commit** (host execution brokers): the focused module passes 59 of 59 tests, client starts included.
  - **Red runs** of the same 59 tests:
    - on the harness without P2-2 (round 5's first commit), exactly P2-2's 8 checks are red: 7 fail and 1 errors, because the self-test report has no broker probes. The other 51 pass;
    - on round 4 (2044b2ab), 17 fail and 17 error.
  - **Stage-1 self-test with the private runtime folder:**
    - 49 probes hidden, all with ENOENT, and all 7 client checks pass;
    - the five broker sockets are absent inside, and each attempt failed;
    - the folder is 0700 and empty.
- **Round 5 (the 14:38Z, 14:42Z and 15:17Z items, without P2-2's commit):** the focused module (`nice -n 19 python3 -B -m unittest test_isolation`) passes 52 of 52 tests, client starts included.
  - **Red run.** The same 52 tests on the harness at 2044b2ab (round 4): 11 fail and 16 error, and the remaining 25 pass. The harness was exported with `tools/skill-usage`, which the grader loads.
  - **Checks the new tests add:**
    - private `/tmp`, `/var/tmp`, `/dev/shm` and IPC;
    - the ai-memory marker and the grader's scope rules, unverifiable pages included;
    - the gateway readings from allowlisted routes only;
    - the normal tier on every Codex launch path;
    - the bind-triple, ordering and options negatives;
    - the public receipt and the private modes;
    - CL7b's census on a wrapper run as promptfoo runs it;
    - the diagnostic tags.
  - **Stage-1 self-test** (`isolation.py selftest --clients`, no model call):
    - 49 probes hidden, all with ENOENT, and all 7 client checks pass;
    - the IPC namespaces differ from the host's;
    - the gateway's two allowlisted routes answered 200 from the namespace, with no credentials;
    - no home path or home slug is in the report.
  - **Read-only re-grade of smoke-20261006c** with this grader: the run root is unchanged (modification times before and after), and no gate's pass changes against its 10:48Z grade. G13 now lists the Codex env trial's unverifiable ai-memory page.
  - **Static checks:** every harness module parses and imports.
- **The structural G13 and the P3 (13:29Z item):** `harness/test_isolation.py`, the harness's own focused module (`nice -n 19 python3 -B -m unittest -v test_isolation`), passes 26 of 26 tests on this harness. On the harness at 1f81d645, 3 of its 20 runnable tests fail and 16 error: there is no isolation module, and the decisions read the rounded fields. It covers:
  - in a synthetic trial's namespace (claude-like and codex-like), `cat` on a real file in each hidden location fails with ENOENT. The same files read outside the wrapper. The test fails if any is readable inside. The locations are:
    - this run's sibling trial's -o answer, settings, prompt, clone history, promptfoo output and fixture draft;
    - another run root, the v1 captures, the suite cards, the fixture cache's oracles.json and the command-center ledger;
    - another trial's fixture, its files and its Claude transcript;
    - a real Codex rollout, also through the clone's own sessions alias;
    - Claude's file history, context-mode's stores and Claude's /tmp area;
  - the trial's own fixture, prompt, settings, clone and neutral binaries, the native home's client configuration, and a Claude project outside the experiment stay readable;
  - writes to the shared sessions alias and to the -o folder land in the trial's own folders, and PID 1's argv shows no option or hidden path;
  - the receipt's hidden list, with path and content sha256s;
  - G13 failing on a missing location, a tmpfs left out, another fixture or an experiment's project bound back, the home re-bound after the tmpfs, a tree outside the namespace, and a missing receipt;
  - a nested `unshare -rm` that cannot unmount a hidden tmpfs and is counted apart, never as outside;
  - the launcher's wrapped run recording the namespace, and its kill reaching the client's TERM handler;
  - the client start checks;
  - finish() moving the -o file and publishing rollouts (into a temporary sessions folder), and CL7b's runtime record read back from the wrapper's info file;
  - the self-test report and the receipt serialising as plain JSON, as prepare.py and the ledger write them;
  - the P3 decisions on 1800.02 s and 1799.96 s.
- **The stage-1 self-test on this host** (`isolation.py selftest --clients`, no model call): 43 probes are hidden, all with ENOENT, and all 7 client checks pass. An S7 snapshot before and after it is equal, with no new trust.
- **Scratch suites of rounds 1 to 3:** they were kept outside the repository and were lost when the host restarted at 13:47Z. They were not re-run in round 4, so their results below are as reported when they ran.
- **Static checks:** every harness module parses (`ast.parse`) and imports. A stdlib `symtable` check found no undefined global names.
- **Synthetic checks:** 95 checks of the decision helpers, all passing. The script is kept outside the repository.
  - They cover headroom and resets, rate-limit hits, completion reasons, the hold flag, exposure, answer sources, effort-only fields, the re-baseline bound, each refused key class, the absorbed concurrent exit and the CL7b re-run rule.
  - 36 of them cover the 11:43Z confirmations:
    - the evidence-based hold rule on every Claude cell of the run of record;
    - the vendor-skill stratum and its counting;
    - each answer-source reason, and that sources and oracle inputs stay tags;
    - the re-baseline cost bound and its fallback;
    - the p90 calibration with its single-reading and rollover exclusions, the pilot hook and per-window headroom.
  - Eight of the checks run on smoke-20261006c's own streams and rollout, and one reads its run.json.
- **Red-green checks for the seven P2 findings:** 10 checks, kept outside the repository.
  - On the harness at 536487a4 all 10 fail; on this one all 10 pass.
  - They cover: the clone trust change (judgement, CL7b view, grader); the absorbed concurrent exit; the orphan reconciliation and counting; the CL7b rate-limit class; the fresh CL7b attempt and its counting; mentions, failed and empty reads; and G11's forwarded-effort value.
- **Red-green checks for the 87f9f1d7 micro-check and the 12:30Z timing ruling:** 12 checks in two scripts, kept outside the repository.
  - On the harness at 87f9f1d7 all 12 fail.
  - At feebace4, the first push of this round, 7 of 12 pass. The two checks of the first review fail (find or xargs with grep -l, `git -C`, and glob or directory-wide reads), and so do the three of the second review.
  - At 1c04fc79, the second push, 9 of 12 pass. The three checks of the second review fail: piped and sequenced listings, xargs options and multi-action find, and everyday commands.
  - On this one all 12 pass.
  - They cover:
    - filename-only operations against content reads (ls, find, stat, realpath, rg --files and -l, git ls-files, wc, Grep's name modes, cat, head, rg, Read, Grep content mode, xargs cat);
    - find -exec grep -l and xargs grep -l as tags, and `git -C <dir> show` and find -exec cat as content reads;
    - a glob or directory-wide read of transcripts as an answer source only when its returned content names a same-task trial or thread;
    - listings piped into head, sort, grep, awk or tr, or written beside an unrelated read, as tags even when the listing names a same-task id;
    - against those, reads through `cd`, a find action's `sh -c`, a loop, a command substitution, xargs, `$HOME`, an input redirection or a heredoc program;
    - xargs `-i`, `-l`, `-e`, `--replace` and `--process-slot-var`, and a find command with several actions;
    - the CL7b repeat rejection;
    - a real `timeout --kill-after` SIGKILL (rc 137) holding a Claude cell while a kill before T does not;
    - same-task Codex rollouts (native, clone alias, collected child) against another task's;
    - both Codex times from a real `printf` event stream through the launcher, and from a rollout;
    - and, on smoke-20261006c read-only, all 11 Codex trials carrying both times.
- **Operator step:** `grade.py meter-calibration` ran read-only on smoke-20261006c and wrote nothing in the run root. Its `--write` form was exercised on a copy of the ledger.
- **Re-grade:** a read-only re-grade of smoke-20261006c with this `grade.py`, with its output kept outside the run root, which it left unchanged.
  - Every gate matches the 10:48Z grade. Under round 3's classifier rule G13 had passed. Under the structural G13 it fails again, now for want of receipts: smoke-20261006c was prepared before the wrapper existed.
  - None of its 16 launched trials is valid, for the same reason.
  - The classifier's diagnostic still tags three trials (host-checkout 3, user-harness-file 1) and finds no answer-source read.
- **Not yet run live:**
  - the launcher's final-turn and hold paths;
  - the headroom start rule and rate-limit re-runs;
  - the in-run re-baseline with its cost check and in-lock reconciliation;
  - the pilot's meter recalibration and orphan reconciliation;
  - CL7b's fresh attempts, clone trust comparison and rate-limit marking;
  - the launcher's Codex timing record.

  The first pilot or smoke under these commits will be the first time they execute.
