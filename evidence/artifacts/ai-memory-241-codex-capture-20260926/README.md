# ai-memory 2.4.1: real Codex capture after the hook trust (2026-09-26)

The 2.4.1 cutover on host `nativestack-5975wx-20260925` rewrote the binary path in the 7
Codex ai-memory hook commands. It left Codex capture pending the user's trust of those
commands in Codex `/hooks` (`evidence/receipts/ai-memory-241-qualification-20260925.json`,
`limitations[0]`). The [Codex hooks documentation](https://developers.openai.com/codex/hooks)
says new or changed hooks are skipped until they are trusted. On 2026-09-26 the user reported
that they had trusted the commands. This directory keeps the probe output that shows the hooks
running and writing through production 2.4.1. The probe was produced directly for this
addendum. It does not record the trust action itself.

## Files

- `capture.txt` is the successful probe, run from the repository checkout. It holds:
  - the start and end time;
  - `codex --version` (`codex-cli 0.157.1`) and `ai-memory --version` (`ai-memory 2.4.1`);
  - how many `~/.codex/hooks.json` commands point at `tools/ai-memory-2.4.1` (7) and how many
    point at any other ai-memory prefix (0);
  - the exact `codex exec` command, its exit code (0) and its final output line;
  - the read-only store count from `codex_capture_count.py`.
- `codex-stderr-hook-lines.txt` holds the Codex version banner and every `hook:` line from
  the successful probe's stderr. The session id, workdir and model lines are left out.
- `codex-hook-events.txt` lists, for each event in `~/.codex/hooks.json` at the probe, how
  many commands point at `tools/ai-memory-2.4.1`, how many at another ai-memory prefix, and
  how many are not ai-memory commands. The seven events are SessionStart, UserPromptSubmit,
  PreToolUse, PostToolUse, PreCompact, Stop and SessionEnd, with one 2.4.1 command each.
- `capture-attempt1-untrusted-dir.txt` is the first attempt, kept as a failed attempt. It
  ran from a scratch directory. Codex exited 1, and 0 Codex sessions wrote observations.
  Its stderr was not retained, because the second attempt overwrote the scratch file.
- `capture-attempt1-repro.txt` repeats the first attempt's condition (a directory outside
  any git repository) with the complete stderr kept. Codex exited 1 with no stdout. Its
  stderr was "Reading additional input from stdin..." followed by "Not inside a trusted
  directory and --skip-git-repo-check was not specified.". 0 Codex sessions wrote
  observations. This is a reproduction; the original's stderr is not retained.
- `codex_capture_count.py` is the read-only SQLite query (`mode=ro`) over the production
  store. It counts, per observation kind, the observations created at or after the probe
  start whose session has `agent_kind = 'codex'`. It also prints the store's schema version.

## Result

The store reported schema V67 and 1 Codex session. That session wrote one observation of
each of six kinds: `session-start`, `user-prompt`, `pre-tool-use`, `post-tool-use`, `stop`
and `session-end`. The stderr lines show SessionStart, UserPromptSubmit, PreToolUse,
PostToolUse and Stop each started and completed.

## Scope

- This is one short `codex exec` session in read-only sandbox mode.
- No PreCompact observation or `hook: PreCompact` line was recorded, so the seventh hook is
  unverified. No compaction telemetry was retained.
- Observations were counted by kind only; their content, including any prompt text, was not
  inspected.
- The Codex CLI in this probe is 0.157.1, as recorded in `capture.txt`.
- This is not a new qualification of ai-memory 2.4.1, and it does not change the ledger
  winner pin. It closes only the pending Codex-capture limitation of the 2.4.1 receipt on
  this host.
