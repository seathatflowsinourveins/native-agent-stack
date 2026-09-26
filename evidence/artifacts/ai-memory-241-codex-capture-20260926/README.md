# ai-memory 2.4.1: real Codex capture after the hook trust (2026-09-26)

On host `nativestack-5975wx-20260925`, the user trusted the 7 rewritten Codex ai-memory hook
commands in Codex `/hooks` on 2026-09-26. The 2.4.1 cutover had left that step pending
(`evidence/receipts/ai-memory-241-qualification-20260925.json`, `limitations[0]`).
Codex skips new or changed hooks until they are trusted
([Codex hooks documentation](https://developers.openai.com/codex/hooks)). A capture through
the production 2.4.1 service is therefore the observable result of the trust.
This directory retains one probe's output, produced directly for this addendum.

## Files

- `capture.txt`: the probe that produced this addendum's result, run from the repository
  checkout. It records:
  - the start and end time;
  - `codex --version` (`codex-cli 0.157.1`) and `ai-memory --version` (`ai-memory 2.4.1`);
  - how many `~/.codex/hooks.json` commands point at `tools/ai-memory-2.4.1` (7) and how
    many point at any other ai-memory prefix (0);
  - the exact `codex exec` command, its exit code and final output line;
  - the read-only store count from `codex_capture_count.py`.
- `capture-attempt1-untrusted-dir.txt`: the first attempt, kept as a failed attempt. It ran
  from a scratch directory outside any git repository. Codex exited 1 before starting a
  session; its stderr said "Not inside a trusted directory and --skip-git-repo-check was not
  specified.", and 0 Codex sessions wrote observations. Codex's directory trust caused this;
  the hooks were not involved.
- `codex-stderr-hook-lines.txt`: the Codex version banner and every `hook:` line from the
  successful probe's stderr. It shows SessionStart, UserPromptSubmit, PreToolUse,
  PostToolUse and Stop, each started and completed. The session id, workdir and model
  metadata lines are not retained.
- `codex_capture_count.py`: the read-only SQLite query (`mode=ro`) over the production store.
  It counts, per observation kind, the observations whose session has
  `agent_kind = 'codex'` and that were created at or after the probe start. It also prints
  the store's schema version.

## Result

The store reported schema V67 and 1 Codex session. That session wrote one observation of
each of six kinds: `session-start`, `user-prompt`, `pre-tool-use`, `post-tool-use`, `stop`
and `session-end`. The probe asked Codex to run one shell command. It exited 0 with the
expected output line.

## Scope

- This is one short `codex exec` session in read-only sandbox mode. The seventh trusted
  hook, PreCompact, was not exercised, because the session never compacted.
- The probe counts observations by kind; it does not inspect their content. Capture of prompt
  text follows the allowlist mode configured at the cutover and is not re-verified here.
- The Codex CLI here is 0.157.1, which another session switched to on 2026-09-26. It is not
  the Codex version that ran during the 2.4.1 qualification.
- This is not a new qualification of ai-memory 2.4.1, and it does not change the ledger
  winner pin. It closes only the pending Codex-capture limitation of the 2.4.1 receipt on
  this host.
