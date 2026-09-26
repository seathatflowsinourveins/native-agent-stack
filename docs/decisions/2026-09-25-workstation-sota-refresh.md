# Decision: workstation-lane SOTA refresh (2026-09-25)

**Decided by:** the coordinating Claude Code session of the workstation lane on host
`nativestack-5975wx-20260925`, from a research wave (one reviewer and one independent
refuter per unit) and a qualification wave (one implementer and one independent verifier
per unit) run on 2026-09-25 between about 17:00Z and 20:55Z. This record was written by a
writing worker on branch `claude/pins-aimemory-mcporter-20260925`.

**Inputs:** the research and qualification results are private session files
(`research-result.json` and `qualify-result.json` in the session scratchpad). They are not
published; the facts this record relies on are stated below with links to the primary
sources. Where a unit was qualified, its sanitized artifacts and receipt are in this
repository and are the evidence of record.

**Scope:** the components and models the workstation lane runs on this host. Pins move only
for Linux x86_64 and only where a unit was qualified and switched on this host.
`adoption/pins-macos-arm64.json` does not change: a Mac qualifies each version itself. The
landscape winner pins in `catalogs/landscape/foundation.json` do not change either: they
come from the sealed 2026-09-22 layer-verdict packets, so host receipts at the new versions
stay unbound (`scripts/host_receipts.py` `pin_matches`) until a new verdict wave re-records
those layers.

**Rule applied:** a newer release replaces an accepted pin only after a clean install into
a fresh prefix passes a discriminating acceptance on this host, matched against the
installed version and reviewed independently. A release being newer is not evidence.

## Summary

| Unit | Decision | Pin after this record | Evidence of record |
| --- | --- | --- | --- |
| rtk | Qualified and switched, with a host config mitigation | 0.50.0 | [`rtk-050-qualification-20260925.json`](../../evidence/receipts/rtk-050-qualification-20260925.json) (#291) |
| markitdown | Qualified and switched | 0.1.8 | [`markitdown-018-qualification-20260925.json`](../../evidence/receipts/markitdown-018-qualification-20260925.json) (#291) |
| mcporter | Qualified and switched | 0.14.1 | [`mcporter-0141-qualification-20260925.json`](../../evidence/receipts/mcporter-0141-qualification-20260925.json) |
| ai-memory | Qualified and switched to 2.4.0 (cold-copy cutover, 2026-09-25), then to 2.4.1 after its own rehearsal and cutover (2026-09-26) | 2.4.1 | [`ai-memory-241-qualification-20260925.json`](../../evidence/receipts/ai-memory-241-qualification-20260925.json); 2.4.0: [`ai-memory-240-qualification-20260925.json`](../../evidence/receipts/ai-memory-240-qualification-20260925.json) |
| socraticode | Qualified; cutover deferred to no earlier than 2026-10-01 | 1.14.0 | none published yet |
| dagu | Compared on this host with no candidate-specific failure; held by the trading lane | 2.16.6 | none published yet |
| headroom | Retained. 0.38.0 has a blocking regression; 0.39.0 fixes it and was qualified, but is not switched | 0.37.0 | [`headroom-039-qualification-20260925.json`](../../evidence/receipts/headroom-039-qualification-20260925.json) |
| qmd, qdrant, ccusage, worktrunk, vllm | Retained; already the latest stable release | unchanged | research only |
| llama.cpp | Recorded, not qualified | b11057 | research and a provenance check only |
| Generation model | Retained | Qwen3.8-27B | research only |
| Embedding model | Retained | Nemotron-3-Embed-1B | research only |
| ai-memory embedder | Evaluation only | local all-MiniLM-L6-v2 | research only |

## Qualified and switched

### rtk 0.49.0 to 0.50.0

**Decision.** 0.50.0 runs the Claude Code hook on this host, with
`~/.config/rtk/config.toml` set to `[hooks] exclude_commands = ["^git show [^ ]*:", "diff"]`.
0.49.0 stays installed for rollback.

**Evidence.** [Release v0.50.0](https://github.com/rtk-ai/rtk/releases/tag/v0.50.0)
(2026-09-24, tag commit `1d87b8e7`), [compare v0.49.0...v0.50.0](https://github.com/rtk-ai/rtk/compare/v0.49.0...v0.50.0).
The research found that the pinned 0.49.0 misreports output on the live hook path: head
windows come out wrong, and failures that report only on stderr disappear; 0.50.0 fixes
both. No published advisory affects either version: the repository's
[advisories](https://github.com/rtk-ai/rtk/security/advisories) cover 0.40.0 and older or a
separate npm package. The refuter reproduced the 0.49.0 baseline and kept the qualify
decision, but showed that the reviewed check would pass a hook that blocks every Bash call
and never checked the content of successful commands. The hash-pinned acceptance scripts
used for qualification (v2 and v3.1) gave 42/0/1 and 88/0/4 (pass/fail/note) on 0.50.0
against 34/8/1 and 79/9/4 on 0.49.0. A non-gating
differential caught a new 0.50.0 behaviour: through the hook, a large
`git show <rev>:<path>` blob is windowed to about 8 KiB, so `| tail` returns lines from
that window. The `exclude_commands` entries keep those commands, and `diff`, whose
failure exit code rtk changes in both versions (fix in
[PR #4169](https://github.com/rtk-ai/rtk/pull/4169), not yet released), out of rewriting.

**Alternatives.** Keep 0.49.0 (keeps the head-window and stderr defects on the live path);
take the 0.50.1 or 0.51.0 release candidates (prereleases; nothing needed is only there).

**Overturn when.** A later stable release fixes the blob window or the `diff` exit code
(then qualify it and drop the matching exclusion); a correctly configured 0.50.0
reproduces the 0.49.0 head-window or stderr loss; an advisory is published against 0.50.0.

**2026-09-26 correction.** A Codex post-merge review of #291 showed that
`"^git show [^ ]*:"` misses ordinary spellings: `git show --no-color HEAD:x`,
`git -C . show HEAD:x`, `git show  HEAD:x` (two spaces) and `git --no-pager show HEAD:x`
were still rewritten into the blob window. rtk tests an entry that starts with `^` as a
raw regex against each command segment
([`registry.rs:1540-1569`](https://github.com/rtk-ai/rtk/blob/1d87b8e719ce0a50c223cd93ca64dd16921f9aec/src/discover/registry.rs#L1540-L1569)).
An alternative single-regex pattern was tested that day,
`[hooks] exclude_commands = ['^git(\s+\S+)*\s+show(\s+\S+)*\s+(:\S|[^\s-]\S*:)', "diff"]`:
its [re-test](../../evidence/artifacts/sota-refresh-20260925/rtk/out/mitigation-20260926.out)
excluded 14 of 14 blob-read and `diff` spellings on 0.50.0 and 0.49.0, where the earlier
pattern excluded 8, left 8 of 8 other commands rewritten, and every executed blob tail
matched native git byte for byte. The adopted recipe is instead #318's four-entry set in
[recipes/README.md](../../recipes/README.md#native-context-mode-and-hooks), which also
routes `git branch` natively and anchors both new entries to the git subcommand position
([retained check](../../evidence/artifacts/rtk-exclude-widen-20260926/hook-check.txt)); this
host runs it. The bootstrap reminder now checks the text and asks the installed
`rtk hook check`, since rtk can ignore a TOML-valid file (a `[tracking]` table without
`history_days`, [`out/config-rejection-20260926.out`](../../evidence/artifacts/sota-refresh-20260925/rtk/out/config-rejection-20260926.out)).
Overturn: a blob-read or `git branch` spelling that the four entries miss, or a
non-blob command they wrongly exclude that loses needed savings.

### markitdown 0.1.7 to 0.1.8

**Decision.** 0.1.8 serves `bin/markitdown` on this host (base package, no extras); 0.1.7
stays installed for rollback.

**Evidence.** [Release v0.1.8](https://github.com/microsoft/markitdown/releases/tag/v0.1.8)
(2026-09-21, tag commit `b8f79c57`, signature verified by GitHub),
[compare v0.1.7...v0.1.8](https://github.com/microsoft/markitdown/compare/v0.1.7...v0.1.8).
The tag has the same tree as the head of [PR #2545](https://github.com/microsoft/markitdown/pull/2545),
whose 27 upstream CI checks passed. No GHSA, repository advisory, OSV entry or PyPI
vulnerability exists for either version; [#2452](https://github.com/microsoft/markitdown/pull/2452)
is Windows path hardening without an advisory. The refuter upheld the review and added a
re-run of the same legs against the production executable after the switch. 0.1.8 passed
10 of 10 legs
before and after the switch; its only output changes are the intended ones for `<u>`,
`<strike>`, `%2F` path escapes and `data-src` images, and all 19 committed HTML files
converted byte-identically under both versions.

**Alternatives.** Keep 0.1.7 (acceptable: there is no security driver; rejected because
0.1.8 is more faithful on the stack's HTML path at no measured cost).

**Overturn when.** A frozen set of real filings loses information against 0.1.7 beyond the
documented changes; a consumer needs Markdown with no raw HTML tags (`<u>` is now kept);
an advisory or 0.1.9 appears; the stack adopts the PDF or Office extras.

### mcporter 0.13.13 to 0.14.1

**Decision.** 0.14.1 serves `bin/mcporter` on this host; 0.13.13 stays installed for
rollback. The `manifests/stack.json` acceptance command becomes
`mcporter --config "${MCPORTER_CONFIG}" list socraticode --brief --no-oauth`, because the
targetless `list --brief` form fails on both versions.

**Evidence.** [Release v0.14.1](https://github.com/openclaw/mcporter/releases/tag/v0.14.1)
(2026-09-24, tag commit `93e0916c`),
[compare v0.13.13...v0.14.1](https://github.com/openclaw/mcporter/compare/v0.13.13...v0.14.1)
(27 commits, two releases). The tarball's sha256 matches the release digest and
`checksums.txt`, its sha512 matches npm `dist.integrity`, and its
[SLSA provenance](https://registry.npmjs.org/-/npm/v1/attestations/mcporter@0.14.1) names
`release.yml` at `refs/tags/v0.14.1`. No advisory names mcporter; the 0.14.0 hardening
([#386](https://github.com/openclaw/mcporter/pull/386), predictable Chrome preload files in
`/tmp`) is off this stack's path. The modules behind every CLI flag and output format the
stack uses are byte-identical, and the daemon protocol is 3 in both versions. The refuter
kept the qualify decision but required the retained daemon-recovery stages and bridge calls in
the acceptance, and found the `fast-uri` 3.1.0 copy bundled in
`@modelcontextprotocol/client` 2.1.0 exposed in both versions. The matched 37-step
acceptance passed 37/37 on both versions; the verifier agreed and measured one real
difference the acceptance cannot see: 0.14.x runs `ps` from `PATH`, and without it the
daemon cannot connect keep-alive servers and `mcporter daemon stop` refuses. This host's
daemon inherits a shell `PATH` that has `ps`.

**Alternatives.** Keep 0.13.13 (no advisory forces the move; rejected because 0.14.1 adds
connection cleanup on timeout and close with no measured regression); wait for 0.14.2
(main has no source change since the tag).

**Overturn when.** A 0.14.2 or later release changes call, list, output, runtime or daemon
code; the daemon protocol moves past 3; an advisory is published against 0.14.x; a
launcher without `ps` on its `PATH` has to run the daemon; an SDK release bundles
`fast-uri` 3.1.8 or later (then re-qualify for the fix).

**Correction (2026-09-26).** The cutover record was wrong on two points. It said that no
daemon ran before the switch and that the next call started a 0.14.1 daemon. On 2026-09-26 a
0.13.13 daemon was found on the production socket; its own `startedAt` is 20:09:44Z on 09-25.
According to the coordinator's session record, which is not retained, the coordinator's
pre-switch baseline call, `mcporter list socraticode`, ran through 0.13.13 in the same command
as the relink, 30 s after a precondition check had found no daemon. That call would have
started the daemon, so the precondition was stale by the time of the switch.
For about 18.8 h, 0.14.1 clients that went through the daemon reached that 0.13.13 daemon.
Its two keep-alive servers show no use after 20:09:45Z. On 2026-09-26 at 14:56Z it was
drained (0 active calls) and stopped with the native `mcporter daemon stop`. A production
call then started a 0.14.1 daemon, confirmed from the process command line. The mixed-version
daemon limitation still holds, because this retirement did not qualify mixed-version
operation. Evidence:
[`mcporter-0141-daemon-correction-20260926`](../../evidence/artifacts/mcporter-0141-daemon-correction-20260926/README.md)
and the receipt's addendum.

### ai-memory 2.3.2 to 2.4.0, then 2.4.1

**Decision.** 2.4.0 served `nativestack-memory.service` and all ai-memory hooks on this
host from the 2026-09-25 cold-copy cutover until 2026-09-26, when 2.4.1 replaced it (see the
update below). 2.4.0 and the private cold V66 copy are kept for rollback. The Codex trust
step for the 7 changed hook commands is the user's and still pending (update 2026-09-26: the
user reported trusting them, and a retained `codex exec` probe then wrote six observation kinds
through 2.4.1, with PreCompact unverified; see the receipt's addendum). Embeddings stay local all-MiniLM-L6-v2.

**Evidence.** [Release v2.4.0](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.0)
(2026-09-21, tag commit `b1b25219`, no artifact attestation, not immutable),
[compare v2.3.2...v2.4.0](https://github.com/akitaonrails/ai-memory/compare/v2.3.2...v2.4.0)
(118 commits). The upgrade moves rmcp 1.7.0 to 2.2.0, which clears
[GHSA-9pj6-vhgr-3mwh](https://github.com/advisories/GHSA-9pj6-vhgr-3mwh),
[GHSA-9g45-5xwm-f3wc](https://github.com/advisories/GHSA-9g45-5xwm-f3wc) and
[GHSA-33f5-2c5q-wgwj](https://github.com/advisories/GHSA-33f5-2c5q-wgwj) from the dependency
set; none of the three was reachable here (the service runs stateless, and the bridge and
OAuth code are unused). It adds two additive migrations, V65 and V66, which are
forward-only. In the [compare](https://github.com/akitaonrails/ai-memory/compare/v2.3.2...v2.4.0),
the hook client and installer sources (`crates/ai-memory-cli/src/commands/hook*.rs` and
`commands/install_hooks.rs`) are unchanged, so the hook rewrite is a path-only diff; `config.rs`,
`serve.rs`, `run.rs`, `reindex.rs`, `mcp_bridge.rs` and six `ai-memory-core` files did change. The refuter
kept the qualify decision but found the draft acceptance blind to Codex hook trust ("new or
changed hooks are marked for review and skipped until trusted",
[Codex hooks documentation](https://developers.openai.com/codex/hooks)) and its rollback
artifact stale; the corrected plan used an at-rest copy with the service stopped. Two
statements in the same-day [release review](2026-09-25-ai-memory-2-4-0-release-review.md)
were wrong and are corrected there: GHSA-9pj6 is not reachable in stateless mode, and 2.4.0
writes no automatic pre-migration archive for a 2.x store. The rehearsal (2.3.2 baseline
16/16, 2.4.0 19/19) and the cutover (fingerprint V64 to V66 with nothing missing, real
Claude Code capture) are in the receipt.

**Alternatives.** Keep 2.3.2 (no reachable advisory; rejected because 2.4.0 ends the
upstream support lag with a small additive change); wait for 2.5 with the
query/document-prefix support of [#859](https://github.com/akitaonrails/ai-memory/pull/859)
(unreleased, adds V67 and V68; preferred only if the same window moved memory embeddings).

**Overturn when.** A 2.4.1 appears (take it and re-run this acceptance); 2.5.0 ships #859
(re-review; required if the memory embedder moves to prefixed Nemotron); an advisory is
published against rmcp 2.2.0 or ai-memory 2.4.0; the Codex trust step or later real-client
capture fails, or the service is later run with `--http-stateful`.

**Update (2026-09-25, after the cutover).** The first overturn condition is met.
[v2.4.1](https://github.com/akitaonrails/ai-memory/releases/tag/v2.4.1) was published at
2026-09-25T21:46:32Z (tag commit `433a19f3`). It contains the #792 file-descriptor-leak fix
(`00aa6ee8`; the compare `00aa6ee8...v2.4.1` is ahead 110, behind 0) and a new forward-only
migration, `V67__managed_run_session_link`, and it does not contain #859 (the compare from
#859's merge commit `7552d4fd` to v2.4.1 has diverged, 32 commits behind). Checked with
`gh api` at about 22:35Z. 2.4.1 was then qualified and switched: on 2026-09-25 it passed a
rehearsal against production 2.4.0 on restored copies (2.4.0 arm 26/26, 2.4.1 arm 28/28, and
the #792 A/B: keepalive on 65 of 65 accepted sockets and all 60 vanished peers reclaimed,
none on 2.4.0), an independent verifier agreed, and with the user's approval the
coordinator cut production over on 2026-09-26 (stop 00:14:12Z, cold V66 copy, start
00:19:51Z, V66 to V67 with 0 pages changed and 0 observations missing, keepalive timers on
2 of 2 live sockets, real Claude Code capture). 2.4.1 is the pin; evidence:
[`ai-memory-241-qualification-20260925.json`](../../evidence/receipts/ai-memory-241-qualification-20260925.json).
The R1/A17 memory-stack rerun keeps official 2.4.0 as its isolated control build.

## Qualified, cutover deferred

### socraticode 1.15.0

**Decision.** 1.15.0 is qualified; 1.14.0 stays the pin and the production entry for
mcporter, Claude Code and Codex. The cutover needs a coordinated restart of every client
and a native Codex check after Codex usage returns on 2026-09-30, so it happens no earlier
than 2026-10-01 (the refuter's date is 2026-10-01T11:01Z, a 7-day cooldown for a release
that is not a security fix).

**Evidence.** [Release v1.15.0](https://github.com/giancarloerra/SocratiCode/releases/tag/v1.15.0)
(2026-09-24), [compare v1.14.0...v1.15.0](https://github.com/giancarloerra/SocratiCode/compare/v1.14.0...v1.15.0):
two Qdrant fixes ([#176](https://github.com/giancarloerra/SocratiCode/issues/176),
[#178](https://github.com/giancarloerra/SocratiCode/issues/178)), MCP log-message delivery
and PHP-only graph work; no index-format or profile-schema change; no advisory. The
refuter showed the first gates never ran the changed code or the graph and symbol tools;
the corrected gates did. Installed with `--ignore-scripts --before=2026-09-24T12:00:00Z`
so only socraticode changed, 1.15.0 passed every gate against a restored copy of the
production collection, matched 1.14.0's search, symbol, impact and health output, and
passed upstream's unit suite (2,475 of 2,475 tests). The verifier agreed, and recorded
that the implementer's copy of the collection used the production Qdrant's snapshot API,
which left 5 empty snapshot directories (collection data unchanged). The new
`notifications/message` stream is the change the production clients have not yet seen.

**Alternatives.** Switch now (rejected: the clients' reaction to the log stream is
unobserved and Codex cannot be checked before 2026-09-30); keep 1.14.0 indefinitely
(gives up the #176 status fix without evidence against 1.15.0).

**Overturn when.** A native Claude Code or Codex call errors on the log stream; a 1.15.x or
1.16.0 changes the index format or profile schema; upstream reports a 1.15.0 regression.

**Update (2026-09-26, mixed-version source review).** The deferral stands. The earliest
cutover time is still 2026-10-01T11:01Z, the end of the 7-day cooldown. Codex can be checked
again, so the only thing still gating the cutover is the coordinated restart.

A source review at [v1.14.0](https://github.com/giancarloerra/SocratiCode/tree/v1.14.0)
(`2218f251`) and [v1.15.0](https://github.com/giancarloerra/SocratiCode/tree/v1.15.0)
(`f6191f07`) found the cross-process coordination code byte-identical between the two tags.
This is a pinned source review, not native execution. It covers `lock.ts`, `watcher.ts`,
`indexer.ts`, `graph-inputs.ts`, `graph-analysis.ts`, `code-graph.ts`,
`symbol-graph-store.ts` and `startup.ts`.

How coordination works:
- **Locks.** They are `proper-lockfile` directories under `os.tmpdir()/socraticode-locks`
  ([lock.ts:27](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/lock.ts#L27)).
  A lock goes stale after 120 s, is refreshed every 30 s, and acquisition is not retried
  ([lock.ts:30-33](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/lock.ts#L30-L33),
  [:112](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/lock.ts#L112)).
  Servers therefore coordinate only when they share a `TMPDIR`.
- **Watcher.** Within one lock directory, the `watch` lock admits one watcher per project
  at a time, whatever its version
  ([watcher.ts:260-265](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/watcher.ts#L260-L265)).
- **Writes.** Index and graph writes that go through the `index` and `graph` locks exclude
  each other within one lock directory. An operation that cannot take the lock does not
  queue: an index run logs "Another process is already indexing this project, skipping" and
  returns
  ([indexer.ts:1052-1062](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/indexer.ts#L1052-L1062)).
  The protocol is the same in both versions, so a version difference alone lets no lock be
  taken over. Startup generation cleanup is not
  covered by these locks; see the cleanup race below.

What mixing versions does cause:
- **Graph flip-flop.** The graph rebuild check is a strict inequality on the builder's
  version
  ([graph-inputs.ts:609](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/graph-inputs.ts#L609)).
  Each version rebuilds a graph the other built, so alternating updates rebuild the graph
  every time. 1.15.0 also marks a 1.14.0 graph as STALE
  ([graph-analysis.ts:203-206](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/graph-analysis.ts#L203-L206)).
- **Cleanup race.** At startup, cleanup of old symbol-graph generations is coordinated only
  inside one process: `coordinateProject` is an in-memory promise chain
  ([symbol-graph-store.ts:843-866](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/symbol-graph-store.ts#L843-L866),
  [startup.ts:324-336](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/services/startup.ts#L324-L336)).
  A server that starts while another is building may delete that build's staging
  generation. This comes from reading the code and was not reproduced;
  `codebase_graph_build` recovers from it.
- **`codebase_stop`.** If the calling server is itself indexing, it cancels that run
  cooperatively. Otherwise it SIGTERMs the process that holds the `index` lock, which may be
  another session's server
  ([index-tools.ts:478-499](https://github.com/giancarloerra/SocratiCode/blob/v1.15.0/src/tools/index-tools.ts#L478-L499)).

Host state on 2026-09-26, from a read-only process listing by the coordinator (not retained):
ten 1.14.0 servers had this checkout as their working directory. Eight were started by
Claude Code and two by the mcporter daemon. That daemon was a leftover
0.13.13; it has since been retired and replaced, as the mcporter section records.

Cutover procedure, for use no earlier than 2026-10-01T11:01Z:
1. Point every launcher at the 1.15.0 prefix with the same environment and no `TMPDIR`
   override: the Claude Code MCP entry, `config/mcporter.json` and the Codex config.
2. Close the 1.14.0 client sessions normally, and restart the mcporter daemon with
   `mcporter daemon stop`. A normal exit releases locks. Avoid `kill -9`: it leaves the lock
   directory in place, and that directory is only removed as stale when some later
   acquisition runs at least 120 s after the last refresh
   ([proper-lockfile v4.1.2 lockfile.js:67-86](https://github.com/moxystudio/node-proper-lockfile/blob/v4.1.2/lib/lockfile.js#L67-L86)).
   Don't use `codebase_stop` to force the handover.
3. End the watch-lock holder only when no `<projectId>-index.lock` or `<projectId>-graph.lock`
   directory exists.
4. Wait until no 1.14.0 server has this checkout as its working directory. A live holder
   refreshes its lock directory every 30 s. So a `<projectId>-*.lock` directory that hasn't
   been refreshed for more than 120 s is abandoned: the next acquisition removes it as stale,
   and it doesn't block the cutover.
5. Start one 1.15.0 session. Check that the watch-lock PID runs from the 1.15.0 prefix and
   that `codebase_graph_status` reports "Built by: v1.15.0".
6. Start further sessions one at a time, and not while a graph lock is held.

## Held by the trading lane

### dagu 2.17.2

**Decision.** 2.16.6 stays the pin and the unit for `bin/dagu` and `dagu-equities.service`.
The trading lane holds the cutover: under `auth: none`, 2.17.2 serves
`GET /api/v1/artifacts` to anonymous loopback clients (200, where 2.16.6 returns 404), that
route cannot be disabled in that mode, and the lane gains nothing from 2.17.2 now.

**Evidence.** [Release v2.17.2](https://github.com/dagucloud/dagu/releases/tag/v2.17.2)
(2026-09-25, tag commit `dfb4ef22`),
[compare v2.16.6...v2.17.2](https://github.com/dagucloud/dagu/compare/v2.16.6...v2.17.2).
The only advisory fixed in the 2.17 line is
[GHSA-8wmf-6v46-5gfg](https://github.com/advisories/GHSA-8wmf-6v46-5gfg) (low, in the
OpenTelemetry exporter dependency); no dagu advisory affects 2.16.6. The refuter found
that only the durable-status fix (#2809) plausibly applies to this stack. On this host the
archive matched `checksums.txt`, and use-receipt replay, checkpoint parity, hosting rows,
cross-version history and the 403 boundary for writes matched 2.16.6. Both versions failed
the same `dagu validate` expectation, because the research DAG defined a `name:` that
did not match its file name (#283 has since renamed it, and both versions validate it),
and the unchanged upstream Go tests need a GitHub-hosted runner; the verifier agreed with
that result. The lane's [hosting README](../../blueprints/us-equities/hosting/README.md)
records the anonymous-read boundary under `auth: none` and the decision to stay on 2.16.6. Any
2.17.2 command that opens the DAG repository deletes the legacy `dags/.dag.index`, so the
binary and the unit must move together.

**Alternatives.** Switch now (rejected by the owning lane); keep 2.16.6 (chosen until the
lane has a reason to move).

**Overturn when.** The trading lane acks a cutover; `auth: none` gains a way to disable the
artifacts route, or the lane moves to authenticated serving; a 2.16.6 advisory or a needed
2.17 fix appears.

## Retained with a blocking regression

### headroom 0.37.0 (not 0.38.0, and 0.39.0 qualified but not switched)

**Decision.** Keep 0.37.0. Do not promote 0.38.0. 0.39.0 was qualified on 2026-09-25 and is
not switched (see the update below).

**Evidence.** [Release v0.38.0](https://github.com/headroomlabs-ai/headroom/releases/tag/v0.38.0)
(2026-09-21). The research recommended qualifying it; the refuter overturned that.
Upstream-confirmed [#3736](https://github.com/headroomlabs-ai/headroom/issues/3736) hits the
stack's exact MCP `headroom_compress` path for ISO-timestamped logs: 0.37.0's lossless fold
becomes a lossy 5-row sample with rewritten timestamps, and on this host the pure-Python
detector runs (no onnxruntime), which fails upstream's own regression tests at v0.38.0. The
fix, `d971f7c3` ([#3748](https://github.com/headroomlabs-ai/headroom/pull/3748)), was on
`main` and in no release when the refuter checked (17:41Z to 18:02Z). 0.38.0's security fixes are lockfile or proxy-only and do not
reach the MCP-only path; no advisory affects 0.37.0.

**Alternatives.** Qualify 0.38.0 with a waiver (rejected: a known summary regression on
the stack's own fixture type); wait (chosen).

**Overturn when.** The first release whose tag contains `d971f7c3` (then qualify it with a
check that fails on #3736); an advisory against 0.37.0's MCP, CCR or savings path (then
qualify 0.38.0 with a written waiver for the summary-only regression).

**Update (2026-09-25, after this wave).** The first overturn condition is met.
[v0.39.0](https://github.com/headroomlabs-ai/headroom/releases/tag/v0.39.0) was published at
2026-09-25T19:29:55Z (tag commit `66f42617`); the
[compare `d971f7c3...v0.39.0`](https://github.com/headroomlabs-ai/headroom/compare/d971f7c3983b05653ef1eb88539bbbbc3667eb67...v0.39.0)
reports ahead 86, behind 0, so the tag contains the fix, and its release notes list #3748
under the transforms fixes (checked with `gh api` at about 22:35Z).

**0.39.0 qualified, not switched (2026-09-25).** The verified wheel (sha256
`8c759401…`, three agreeing digests, RECORD 555/555) passed the unchanged upstream #3736 test
6 of 6 (0.37.0: 4 of 6) and the stack's MCP path over stdio with byte-exact retrieval and
cross-version store reads; an independent verifier agreed
([`headroom-039-qualification-20260925.json`](../../evidence/receipts/headroom-039-qualification-20260925.json)).
0.37.0 stays the pin, for these reasons:

- **The omission notice counts the wrong lines.** At v0.39.0 the Python shim's
  `_format_output`
  ([`headroom/transforms/log_compressor.py:461-487`](https://github.com/headroomlabs-ai/headroom/blob/v0.39.0/headroom/transforms/log_compressor.py#L461-L487))
  and the Rust `format_output`
  ([`crates/headroom-core/src/transforms/log_compressor.rs:1396-1433`](https://github.com/headroomlabs-ai/headroom/blob/v0.39.0/crates/headroom-core/src/transforms/log_compressor.rs#L1396-L1433))
  count ERROR/FAIL/WARN/INFO over all input lines and print them as
  `[{omitted} lines omitted: …]`. On the stack's fixture A, 0.39.0 printed
  `[593 lines omitted: 1 ERROR]`, although the only error-level row, the CRITICAL line, is
  among the 7 rows it kept. Checked with `gh api` at 2026-09-26T00:28Z: the Python file is the
  same blob (`0fc79887`) at v0.37.0, v0.38.0 and v0.39.0, and
  [#3635](https://github.com/headroomlabs-ai/headroom/pull/3635) (merged 2026-09-24) changed
  only the Rust file, adding a `summarize_omitted` descriptor for the retrieval marker, not
  this count. The defect reaches the stack's timestamped logs only from 0.39.0, because #3748
  now routes them to the log compressor instead of 0.37.0's lossless search fold.
- **The Rust detector still lacks the #3736 guard.** `try_detect_search` in
  [`content_detector.rs`](https://github.com/headroomlabs-ai/headroom/blob/v0.39.0/crates/headroom-core/src/transforms/content_detector.rs)
  filters matches only through `prefix_looks_like_path`, which has no timestamp-row check, so
  #3736 can recur where onnxruntime 1.24 or later (or `ORT_DYLIB_PATH`) enables the native path.
- **The rest of the stack is on 0.37.0.** #299 pins headroom 0.37.0 in the Linux bootstrap,
  and the token-efficiency lane's end-to-end counters (#296) run at 0.37.0.

The beacon defaults on in both versions (`BEACON_DEFAULT_ON = True`); its opt-out
(`HEADROOM_OFFLINE=1`, `DO_NOT_TRACK=1`) is owned by the token-efficiency lane and landed in
#303 and #304. **Overturn when** upstream counts levels over the omitted lines only, or a
measured answer-quality comparison on log inputs shows net value for 0.39.0's log routing.

## Retained, already the latest release

### qmd 2.8.3, qdrant 1.19.1, ccusage 20.0.24, worktrunk 0.79.0, vllm 0.30.0

**Decision.** Retain all five pins.

**Evidence.** Each pin is its project's newest stable release on 2026-09-25:
[qmd v2.8.3](https://github.com/tobi/qmd/releases/tag/v2.8.3),
[qdrant v1.19.1](https://github.com/qdrant/qdrant/releases/tag/v1.19.1),
[ccusage v20.0.24](https://github.com/ccusage/ccusage/releases/tag/v20.0.24),
[worktrunk v0.79.0](https://github.com/max-sixty/worktrunk/releases/tag/v0.79.0),
[vllm v0.30.0](https://github.com/vllm-project/vllm/releases/tag/v0.30.0) (the newer
`v0.30.1rc0` tag is a development marker). No published advisory leaves a pinned version
unpatched: qdrant's [GHSA-f632-vm87-2m2f](https://github.com/qdrant/qdrant/security/advisories/GHSA-f632-vm87-2m2f)
was patched in 1.15.6, and every published vLLM advisory is patched at or before 0.30.0.
The refuter kept retention, noted that this check does not exercise how the stack uses
the five, and added three follow-ups that are not pin changes:
`bin/vllm` on this host still points at the 0.25.0 prefix (rollback there reopens
advisories patched in 0.30.0); ccusage has a `v20.0.25` tag whose release run failed, so it
is unpublished; and `manifests/landscape.json` still lists stale latest-release identities.

**Alternatives.** None: no newer stable release exists.

**Overturn when.** Any of the five publishes a newer stable release, an advisory covers a
pinned version without a patch, or ccusage 20.0.25 is published.

## Recorded, not qualified

### llama.cpp b11146 (v0.5.0)

**Decision.** Record b11146; keep the manifest pin at b11057.

**Evidence.** [v0.5.0](https://github.com/ggml-org/llama.cpp/releases/tag/v0.5.0) is
nightly [b11146](https://github.com/ggml-org/llama.cpp/releases/tag/b11146) (commit
`7fe450e1`), the latest stable release, with official Ubuntu CUDA 12.8 x64 archives. The
host already runs b11146; its 64 prefix entries match the attested
`ubuntu-cuda-12.8-x64` archives with 0 differences (`gh attestation verify` passed), and
the pinned b11057 archives still verify. No advisory affects either build; b11146 adds
vendored cpp-httplib 0.57.1 hardening and a sleep-state crash fix
([#29309](https://github.com/ggml-org/llama.cpp/pull/29309)). The refuter's paired
acceptance (a freshly installed b11057 baseline, fixtures, throughput within 0.90x,
placement with `--fit off`) needs the production generation unit stopped, which this wave
did not do; no completion or throughput was measured.

**Alternatives.** Re-pin to b11146 on provenance alone (rejected: provenance is not a
runtime check); move to b11183 or later (they include a decode-path rewrite; next
candidates against this baseline).

**Overturn when.** The paired acceptance passes in an owned window (then re-pin); an
advisory or a fix for this profile's defect class lands after b11146.

## Models

### Generation: Qwen3.8-27B (retained)

**Decision.** Keep [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) for local
generation on llama.cpp.

**Evidence.** No newer model that fits this shared GPU, runs on released upstream
llama.cpp and has a permissive license shows primary-source evidence of being stronger.
Among open-weight models of 130B parameters or fewer,
[Artificial Analysis](https://artificialanalysis.ai/models/qwen3-8-27b) ranks it first
(Intelligence Index 33.7); Qwen's card leads Muse Glimmer-30B on every shared row, and
Granite 4.2 30B, Nemotron 3.5 Lightning and MiMo-V2.6-Distill-9B report lower numbers on
their own cards. The stronger Qwen3.8-Flash-Next needs about 72.6 GB or more even at its
smallest quantization and has a custom license. The research also found that the served
file (unsloth UD-Q4_K_M) differs from the manifest's ggml-org Q4_K_M pin; reconciling
that is separate work.

**Alternatives.** Muse Glimmer-30B, Ornith-1.5-35B-A3B, Granite 4.2 30B, Nemotron 3.5
Lightning, K2 Horizon, MiMo-V2.6-Distill-9B (all weaker or unsupported in released
llama.cpp); the large MoE releases (out of budget).

**Overturn when.** A permissive open-weight model released after 2026-08-14, supported by a
released llama.cpp and within the VRAM reserve, shows parity or better against
Qwen3.8-27B in primary or independent evidence (for example an Intelligence Index of at
least 33.7).

### Embeddings: Nemotron-3-Embed-1B (retained)

**Decision.** Keep [nvidia/Nemotron-3-Embed-1B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-1B-BF16)
at `c0c9fea9` on vLLM 0.30.0 for code and document retrieval.

**Evidence.** Hugging Face `main` is still `c0c9fea9`, with only a README change since the
MTEB-evaluated upload. In the official [MTEB results repository](https://github.com/embeddings-benchmark/results)
(at `1651f618`), the pin's six public RTEB(Code) tasks average nDCG@10 80.87; no open model
created or re-weighted since 2026-06 that fits the 0.16 GPU-memory budget scores higher
(F2LLM-v2-0.6B 78.96; the 1B NVFP4 variant is weaker by its own card and targets newer
GPUs). The refuter checked all 102 model/revision directories and upheld retention.

**Alternatives.** [Nemotron-3-Embed-8B-BF16](https://huggingface.co/nvidia/Nemotron-3-Embed-8B-BF16)
with FP8 (the next candidate, but only if embeddings get about 0.40 of the GPU); F2LLM-v2,
multimodal and non-commercial models (weaker, out of scope or unlicensed for this use).

**Overturn when.** Embeddings get 0.40 or more of GPU memory (then qualify the 8B); a new
model publishes an RTEB(Code) six-task mean of at least 81.9 with a usable license, a
pooling architecture vLLM serves and a footprint of about 3.9 GB or less.

## Evaluation only

### ai-memory embedder: Nemotron through openai-compat with prefixes

**Decision.** Evaluate, do not switch. Production keeps ai-memory's local
all-MiniLM-L6-v2. The candidate is Nemotron-3-Embed-1B-BF16 through ai-memory's
openai-compat embedder with the `query: ` and `passage: ` prefixes. The evaluation needs
a build of the unreleased `release/2.5` branch, which carries
[#859](https://github.com/akitaonrails/ai-memory/pull/859) (build at `47af33a7`), and the
LongMemEval-S harness whose Mac runs produced the C1 to C3 arms recorded in
[`evidence/artifacts/memory-stack-20260925/experiment.json`](../../evidence/artifacts/memory-stack-20260925/experiment.json)
and [`convergence.json`](../../evidence/artifacts/memory-stack-20260925/convergence.json)
(summarized in [`catalogs/foundation/memory-stack-20260925.json`](../../catalogs/foundation/memory-stack-20260925.json)).
That harness exists only on the Mac: [issue #274](https://github.com/seathatflowsinourveins/native-agent-stack/issues/274)
asks for it and its preregistration to be committed so that the confirmatory C3/C4 rerun can
run on this workstation, which "now owns R1" after VelaNext's retirement, and so that the
workstation can draft preregistration amendment A17 against them. #274 covers that C3/C4
rerun; the Nemotron-prefix evaluation would come after it, under its own preregistration.

**Evidence.** ai-memory's `local` provider is hard-wired to MiniLM at v2.3.2, v2.4.0 and on
`release/2.5`. At 2.4.0 the openai-compat provider can reach the stack's vLLM endpoint but
sends no prefixes, and ai-memory's config accepts unknown keys, so setting prefix keys on
2.4.0 silently produces unprefixed vectors. Nemotron's card requires the prefixes. 2.4.1, in
production since 2026-09-26, is the same here: it does not contain #859, and its `config.rs`
has no prefix keys.

**Alternatives.** Switch on 2.4.x without prefixes (only if an unprefixed arm passes the
same preregistered rule); instruction-free models such as pplx-embed-v1-0.6b (needs a
serving runtime this stack does not run) or granite-embedding-english-r2 (weaker).

**Overturn when.** The prefixed arm fails the preregistered rule (retain MiniLM); the
unprefixed arm passes (switch on the official 2.4.x release in production); 2.5.0 ships without the prefix keys or
with a different identity scheme (re-run).

## Limits

- The research and qualification results are private session files; this record states
  their facts but does not publish them. Values for the switched units come from the
  receipts and artifacts named in the summary.
- The rtk and markitdown pins and receipts landed separately in #291.
- One host (`nativestack-5975wx-20260925`, WSL2). Nothing here is macOS evidence, and no
  landscape verdict changes.
