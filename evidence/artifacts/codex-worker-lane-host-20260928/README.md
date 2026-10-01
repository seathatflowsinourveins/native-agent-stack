# Codex worker lane on the workstation, 2026-09-28

#458 changed the top-rule line of the lane's managed `AGENTS.md` block (X5c, in
[`2026-09-28-top-rule-templates.md`](../../../docs/decisions/2026-09-28-top-rule-templates.md)). A Codex home that
installed the block keeps the old line until the lane is applied there again. On this workstation, the coordinator
applied it after #458 merged. It then ran the two non-mutating checks again, with their exit codes and times kept.

## Records

| Record | When (UTC) | Evidence class | Retained observation |
| --- | --- | --- | --- |
| [apply-run/dry-run.txt](apply-run/dry-run.txt) | file written 12:14:54 | Local integration: real Codex home inspected; private-copy rehearsal | Every precondition ok, no Codex process; the only planned write is the managed `AGENTS.md` block; rehearsal passed |
| [apply-run/apply.txt](apply-run/apply.txt) | run record 12:15:14, file written 12:15:19 | Local integration on the real Codex home | `config.toml` and `AGENTS.md` written and read back; the stack-worker profile in place; a private recovery record kept |
| [apply-run/prove.txt](apply-run/prove.txt) | file written 12:15:33 | Local integration on the real Codex home | 7 pass, 0 fail |
| [recheck/dry-run.txt](recheck/dry-run.txt) | 13:30:57 to 13:31:14, exit 0 | Local integration: real Codex home inspected; private-copy rehearsal | "AGENTS.md: block already in place"; nothing to send to `config.toml`; rehearsal passed |
| [recheck/prove.txt](recheck/prove.txt) | 13:31:14 to 13:31:22, exit 0 | Local integration on the real Codex home | 7 pass, 0 fail |

- The first three ran from a worktree of `main` at `fb14dedf`, the merge of #458.
- The recheck ran from #444's worktree at `0779e91a`, whose `tools/adoption/` is unchanged from `fb14dedf`.
- `recheck/runs.json` holds each recheck command's argument vector, revision, times and exit code, and
  `codex_lane_receipt.py` wrote it.
- The first three outputs kept no exit codes or times. Their times are file modification times, and the run record's
  name gives the apply's start. That gap is why the recheck exists.

## Retention and sanitization

This follows [#406's receipt](../codex-worker-lane-host-20260927/README.md#retention-and-sanitization), through
`codex_lane_receipt.py`:
- the home prefix is written as `~`;
- private file hashes, config version tokens and the run directory's name are written as placeholders;
- the public pinned launcher hash is kept.

The raw outputs stay private.

## What is not claimed

- These are the integration runner's own observations, not unchanged upstream tests.
- `prove_codex_lane.py` ran without `--live`, so no worker made a model call.
- Neither run accepts another host. Each other host that installed the lane needs its own dry run and apply.
- For the sources behind the lane itself (codex-cli 0.157.1, context-mode 1.0.169, rtk 0.50.0), see #406's receipt
  and [`2026-09-26-codex-worker-lane.md`](../../../docs/decisions/2026-09-26-codex-worker-lane.md).
