# SOTA refresh 2026-09-23 -- unit pins-mem

Qualifies the newest upstream releases (resolved live via `gh api .../releases/latest`
at 2026-09-23T00:2x-00:4x UTC) of five components named in the task, against whatever
receipt or usage record establishes the current pin. All installs are isolated
under `$HOME/.cache/sota-refresh-20260923/pins-mem/`; the live production
ai-memory service (pid 365, `$HOME/.local/share/ai-memory`, port 49374) was
never stopped, replaced or its data reconfigured by the fix-round run.

## Fix round (this revision)

An independent Opus review of the first pass found five issues, resolved as follows:

1. **Blocker -- ai-memory isolation actually failed.** The first pass's CLI client
   commands defaulted to `AI_MEMORY_SERVER_URL=http://127.0.0.1:49374` (the live
   service's port); only the isolated `serve`'s own bind was changed, not the
   client target. Every write/search/read/status result in the first receipt
   therefore came from the live 2.3.2 service, and it wrote a real stray page
   (`agent-lab/agent-lab/canary/test.md`, commit `9f9a01c`) into the live store.
   **Fixed**: re-ran the entire check with `AI_MEMORY_SERVER_URL` explicitly
   exported to the isolated server's port, `AI_MEMORY_EMBEDDING_PROVIDER=none`,
   and an explicit `--workspace/--project` distinct from the live scope; verified
   by direct filesystem/git-log inspection that no new content landed in the live
   store this time. **The stray page from the first pass was NOT deleted by this
   unit** -- removing it was a destructive live-store change that needed the
   coordinator's or user's decision; see `ai-memory.json`'s
   `fix_round.stray_live_page_unresolved` for the exact path. **Update**: the
   coordinator subsequently deleted it via `memory_delete_page` on 2026-09-23
   (wiki checkpoints ea02e38 -> e2fadf4); per the #81 finding this is a
   wiki-level delete, not byte-level erasure, and the page and its history
   remain in the wiki git history and the live store's SQLite WAL (see
   `ai-memory.json`'s `fix_round.coordinator_followup_deletion`).
2. **Major -- acceptance ref too narrow, no handoff check.** Broadened
   `acceptance_check_ref` to include both the retained maintenance receipt and
   the retained lifecycle-probe receipt/commands, and added an isolated,
   read-only `ai-memory handoffs` invocation as the "handoff" leg the task named.
3. **Major -- markitdown reproduced the wrong fixture.** Re-ran markitdown 0.1.8
   against `fixtures/greeting.html`, the exact upstream-directive fixture the
   retained receipt names by path (results.json:4553), in addition to (not
   instead of) the non-identical README check.
4. **Major -- undisclosed secret exposure and incomplete gitleaks.** Disclosed
   (in `ai-memory.json`'s `fix_round.secret_exposure_disclosure`) that this
   session incidentally viewed the live instance's `token_pepper` while
   diagnosing the isolation bug, and did not rotate it (that decision belongs to
   the user). Re-ran gitleaks on this worktree after the fix round: 397 commits
   scanned, no leaks found (the first pass's lock contention was transient).
5. **Minor -- undisclosed model download; imprecise "empty" restore claim.**
   The fix-round ai-memory run set `AI_MEMORY_EMBEDDING_PROVIDER=none` up front,
   so no embedding model was downloaded this time (confirmed via
   `status.providers.embedding.status == "disabled"` and a 46.57 KiB backup vs.
   the first pass's 120.89 MiB one); the first pass's undisclosed download is
   called out explicitly in `ai-memory.json` for the record.
6. **Minor -- preregistration timestamps looked reconstructed.** `mteb.json`'s
   install was re-run through `ecosystem-bounded-run` (the first pass used a
   plain `uv pip install`) with real, distinct wall-clock timestamps. The
   `pageindex.json` and `repomix.json` preregistration notes are now labelled
   `LATE, not prior` rather than implying they preceded execution.

| component | from_pin | resolved newest release | verdict | evidence_class | receipt |
|---|---|---|---|---|---|
| ai-memory | 2.3.2 | v2.4.0 (2026-09-21T23:45:13Z) | not_comparable | native_proven | [ai-memory.json](./ai-memory.json) |
| repomix | 1.18.0 (per task) / 1.18.1 (actual current pin) | v1.18.1 (2026-09-21T08:34:49Z) | qualified | native_proven | [repomix.json](./repomix.json) |
| markitdown | 0.1.7 | v0.1.8 (2026-09-21T21:22:51Z) | qualified | native_proven | [markitdown.json](./markitdown.json) |
| pageindex | 0.2.18 | v0.2.19 (2026-09-21T04:49:29Z) | not_comparable | source_review | [pageindex.json](./pageindex.json) |
| mteb | 2.21.0 | 2.21.6 (2026-09-21T22:39:20Z) | not_comparable | source_review | [mteb.json](./mteb.json) |

## Key findings

- **repomix is already current.** `scripts/native_token_ci.py` pins repomix at
  `1.18.1`, and the retained receipt
  `evidence/artifacts/full-stack-convergence-20260921/ccusage-repomix-upgrades.json`
  already tested that exact version (148/148 upstream tests passing) before this
  wave started. `gh api` confirms 1.18.1 is still the newest release. This unit's
  isolated install re-verified the version string only and reused the retained
  test result rather than re-running an unchanged check.

- **markitdown 0.1.8 qualifies.** Isolated `uv` venv install; `--version` reports
  `0.1.8`. The primary reproduction leg is `markitdown fixtures/greeting.html`,
  the exact upstream-directive fixture the retained receipt names by path
  (results.json:4553, same 474-byte input) -- exit 0, expected text extracted.
  The README.md conversion (21363 bytes on this worktree's README vs. 2191 bytes
  on the original fixture) is kept only as a secondary, non-identical-fixture
  check for the >=100-byte assertion class; it is not the fixture reproduction
  that establishes the `qualified` verdict (see `markitdown.json`'s `limits`).

- **pageindex and mteb have no retained functional baseline to reproduce.**
  `rg` over `evidence/`, `blueprints/`, `catalogs/` found only catalog citations
  and (for pageindex) an explicit audit note that it is "source review only"
  (`docs/grand-catalog-handbook.md:1641`). Both verdicts are `not_comparable`:
  this unit confirmed the newest release via `gh api`, installed the new version
  isolated, and verified `import` succeeds, but there is no prior native
  evaluation run in this repository's evidence to compare against -- so this is
  not a "qualified" reproduction of prior behavior, and it is not a regression
  either. Running a real MTEB evaluation task or a PageIndex document-tree build
  was out of scope: both would require downloading external model/dataset assets
  or a paid API, beyond what any retained receipt exercises.

- **ai-memory 2.4.0 is `not_comparable`, not `qualified`, and the true finding is
  a client-scoping gotcha, not a server regression.** The first pass's "`status`
  bypasses `--data-dir`" claim was WRONG: it was caused by this unit's own client
  commands never setting `AI_MEMORY_SERVER_URL`, so every command (including the
  ones this unit thought were isolated) silently talked to the live service on
  the default port `127.0.0.1:49374` -- which also means the first pass's canary
  write landed in the LIVE store, not the isolated one (a real isolation failure,
  corrected in this revision; see "Fix round" above and `ai-memory.json`). With
  `AI_MEMORY_SERVER_URL` correctly exported to the isolated server's own port,
  write/search/read-page/handoffs(list)/status/backup -- the six legs this
  fix round actually ran -- ALL correctly operate against only the isolated
  data directory (re-verified by direct filesystem inspection of both the
  isolated dir and the live store). Update, delete and a server restart were
  NOT exercised in this rerun, so this does not cover the retained
  lifecycle-probe's full write/read/update/delete/restart lifecycle -- see
  `ai-memory.json`'s `limits` for that gap. This exactly matches documented,
  pre-existing 2.3.2 behavior (the retained probe already works around it by
  setting `AI_MEMORY_SERVER_URL`), so there is no 2.4.0-specific status
  regression.
  - `restore` still refused, this time correctly diagnosed: a host-wide (not
    data-dir-scoped) running-process safety check
    (`refusing to restore: 1 other ai-memory process(es) running (pids: [365])`)
    prevents restore while the live service is up, matching the retained
    lifecycle-probe receipt's own recorded restore limitation exactly. `--force`
    does not override this guard. Not exercisable end-to-end without stopping
    the live service, which the isolation contract forbids.
  - The MCP-facing check ("configured direct MCP memory_status") was not
    attempted at all, per the isolation instruction to never touch the live
    store or MCP.
  - **From the first pass:** a stray canary page was left in the live store
    (`agent-lab/agent-lab/canary/test.md`, commit `9f9a01c`); this unit's own
    diagnostic commands also incidentally viewed the live instance's
    `token_pepper`. Neither was corrected by this unit -- both required an
    owner decision (see `ai-memory.json`'s `fix_round` block). **Status:** the
    stray page was subsequently deleted by the coordinator via
    `memory_delete_page` on 2026-09-23 (wiki checkpoints ea02e38 -> e2fadf4;
    per the #81 finding this is wiki-level, not byte-level erasure -- the page
    and its history remain in the wiki git history and the live store's SQLite
    WAL). The `token_pepper` exposure has been reported to the user for a
    rotation decision; the value itself is not reproduced anywhere in this
    evidence directory and was not rotated by this unit.

## Isolation and containment

- All package/binary installs live under
  `$HOME/.cache/sota-refresh-20260923/pins-mem/` (venvs, npm prefix,
  extracted ai-memory binary). Nothing was installed onto PATH or over an
  existing binary; no `~/.config`, `~/.local/share/ai-memory`, `~/.headroom`,
  systemd unit or shell profile was modified.
- The only server processes started by this unit were `ai-memory serve`
  instances bound to loopback: port 58217 in the first pass, and port 58317
  in the fix round (`ai-memory.json`'s `isolation.server`), each on its own
  isolated data dir. Both were killed at the end of their respective runs;
  both ports are confirmed freed.
- `pip`/`uv pip` installs for markitdown, mteb and pageindex ran through
  `$HOME/codex-ecosystem/bin/ecosystem-bounded-run` where noted in the
  per-component receipts' `commands` field.
- No broker contact and no paid API call. This is NOT a "no credential read"
  run: while diagnosing the isolation bug, this unit's own commands
  incidentally displayed the live production ai-memory instance's
  `[auth] token_pepper` in plaintext (see `ai-memory.json`'s
  `fix_round.secret_exposure_disclosure`); it was viewed but not modified,
  copied elsewhere, or rotated, and rotation is left to the user/coordinator.
  PageIndex's `PageIndexCloudClient` and mteb's full evaluation-task path were
  left untouched for the unrelated reason of avoiding paid-API/external-dataset
  use (see the pageindex/mteb receipts' `limits`).

## Verdict legend

`qualified` = a retained functional check reproduced successfully at the new
version. `not_comparable` = either no retained functional baseline exists to
compare against, or the retained checks could not be safely/completely re-run
in isolation on this host (see limits in each receipt). `regression` and
`blocked` were not needed for any of the five components in this run.
