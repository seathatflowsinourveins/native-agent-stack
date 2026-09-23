# SOTA refresh 2026-09-23 -- unit pins-mem

Qualifies the newest upstream releases (resolved live via `gh api .../releases/latest`
at 2026-09-23T00:2x UTC) of five components named in the task, against whatever
receipt or usage record establishes the current pin. All installs are isolated
under `$HOME/.cache/sota-refresh-20260923/pins-mem/`; the live production
ai-memory service (pid 365, `$HOME/.local/share/ai-memory`, port 49374) was
never stopped, replaced or reconfigured.

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
  `0.1.8`; the retained conversion functional check (convert a local Markdown/HTML
  file, assert >=100 bytes of output) reproduces cleanly (21363 bytes on this
  worktree's README vs. 2191 bytes on the original fixture -- different file,
  same passing assertion class).

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

- **ai-memory 2.4.0 is `not_comparable`, not `qualified`, and surfaced a real
  isolation-boundary finding.** The isolated binary (checksum-verified against
  the published release) correctly writes/searches/reads/backs up data only in
  its own isolated data directory (verified by direct filesystem inspection, not
  just command output) using its own loopback server on port 58217. Two of the
  five checks the retained 2.3.1->2.3.2 receipt recorded could not be completed:
  - `status --json` ignored `--data-dir` and the isolated `config.toml`'s `bind`
    override, instead querying the live production server's HTTP endpoint on the
    hardcoded default `127.0.0.1:49374` and returning its live counters. This was
    discovered while diagnosing an unexpected result, not intentionally probed;
    no writes touched the live store (independently confirmed: the live wiki
    directory has no trace of the isolated run's canary page). This is reported
    as a genuine behavior finding for 2.4.0, not exploited further.
  - `restore` refused with a host-wide (not data-dir-scoped) running-process
    safety check (`refusing to restore: 2 other ai-memory process(es) running
    (pids: [365, <this unit's isolated serve pid>])`), which correctly prevented
    a restore while the live service was up, but also means restore could not be
    exercised end-to-end in this run without stopping the live service --
    disallowed by the isolation contract.
  - The MCP-facing check ("configured direct MCP memory_status") was not
    attempted at all, per the isolation instruction to never touch the live
    store or MCP.

## Isolation and containment

- All package/binary installs live under
  `$HOME/.cache/sota-refresh-20260923/pins-mem/` (venvs, npm prefix,
  extracted ai-memory binary). Nothing was installed onto PATH or over an
  existing binary; no `~/.config`, `~/.local/share/ai-memory`, `~/.headroom`,
  systemd unit or shell profile was modified.
- The only process started by this unit (`ai-memory serve` bound to loopback
  port 58217, isolated data dir) was killed at the end of the run; the port is
  confirmed freed.
- `pip`/`uv pip` installs for markitdown, mteb and pageindex ran through
  `$HOME/codex-ecosystem/bin/ecosystem-bounded-run` where noted in the
  per-component receipts' `commands` field.
- No broker contact, no paid API call, no credential read. PageIndex's
  `PageIndexCloudClient` and mteb's full evaluation-task path were left
  untouched for exactly this reason (see the pageindex/mteb receipts' `limits`).

## Verdict legend

`qualified` = a retained functional check reproduced successfully at the new
version. `not_comparable` = either no retained functional baseline exists to
compare against, or the retained checks could not be safely/completely re-run
in isolation on this host (see limits in each receipt). `regression` and
`blocked` were not needed for any of the five components in this run.
