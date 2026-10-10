# Local Claude review worker

A command-center-owned service that reviews essential pull request heads with Claude Code headless (`claude -p`) on a
stored Anthropic API key, and posts the commit status `claude-review/local`. The record of the decision, its
measurements and its open boundaries is
[docs/decisions/2026-10-09-claude-review-worker.md](../../docs/decisions/2026-10-09-claude-review-worker.md).

| File | What it is |
| --- | --- |
| `worker.py` | One tick: select heads, review at most two, record, post. `worker.py select` lists what a tick would review and spends nothing. |
| `essential-paths.json` | The repositories, which heads count as essential, their visibility and the main-branch rules files that go into the prompt. The command center approves changes to it. |
| `probes.py` | The sandbox and fence probes: `offline` (no key, no model call; a loopback stand-in for the API plays the model) and `live` (three paid runs). |
| `systemd/claude-review-worker.service`, `.timer` | One tick at minutes 07, 22, 37 and 52 of every hour. |

## What a tick does

1. Takes the tick lock (`$CLAUDE_REVIEW_STATE/worker.lock`); a second tick, or a probe, waits its turn by stopping.
2. Checks it can run at all, before any key is read: the ledger is named, the pinned binary exists, bubblewrap starts
   the binary in the sandbox, node, srt and socat are the pinned ones, and a keyless check through srt and bubblewrap
   shows the network boundary closed (only `lo`, the API reachable through srt's proxy, `example.com` refused, no
   direct route, and nothing reaching a listener on the host's loopback).
3. Settles anything a stopped tick left open: an open `CRW` debit becomes an unknown settle at 11 USD, an attempt
   still marked `started` becomes `interrupted` (counted, not final), and the stopped run's leftover scratch (its
   CLAUDE_CONFIG_DIR, an archive) is deleted.
4. Lists the open pull requests of each repository with `gh api --paginate` (pages of 100), keeps same-repository heads
   targeting `main` whose author is not a bot (drafts included), newest update first.
   - For `native-agent-stack` it keeps a head only when a changed file matches an essential path (cached per head).
     The essential paths include the gate itself: this tool, the credential inventory and schema, the hooks,
     `.gitleaks.toml` and the agent instruction files.
   - A head with nothing to review (already in main, or an empty diff) is skipped without a status and never selected
     again.
5. Posts any stored result not posted yet for a head that is still current (see Posting).
6. Reviews at most two heads, one after another, each only while the day's ledger rows leave room for its 11 USD bound
   under the 55 USD ceiling.

A review:
1. refreshes the repository's detached worktree of `origin/main` under the state directory;
2. fetches `refs/pull/<n>/head` and checks it is the selected commit;
3. reads the head's size from git. Over 40,000 files or 600,000,000 bytes nothing is extracted, and the head is refused
   before any debit with status `error`, final;
4. exports the head with `git archive` into `pr-head/`. Links and special files are never written, any link left is
   removed, and the head's own `export-ignore` and `export-subst` are overridden by `info/attributes`;
5. writes the diff from the merge base and its `--stat` into a separate input directory.

A diff over 250,000 bytes is refused before any debit: the status is `error`, the description names the size and asks
for a paths-limited review, and the attempt is final.

The review process is started as `credential_run.py <key> -- env … node <srt>/dist/cli.js --settings <run>/srt.json --
bwrap … /opt/claude-review/claude -p …`. The runner reads the key store outside the sandbox and passes the key in the
environment, never in argv. srt (Anthropic's sandbox runtime, `@anthropic-ai/sandbox-runtime` 0.0.79) is the network
boundary: its own bubblewrap layer gives the run a network namespace with only `lo`, and its proxy on the host,
reached through a bound unix socket, passes `api.anthropic.com` and refuses everything else. srt gets a private
directory per run under `$XDG_RUNTIME_DIR/claude-review-worker/` (its settings, TMPDIR, HOME and an empty working
directory), deleted after the run. The inner bubblewrap is the filesystem fence. It has a new root:
`/usr` and `/etc` read-only, `/proc`, `/dev`, an empty `/tmp`, an empty home at `/review/home`, the main worktree at
`/review/main` and the input directory at `/review/input` (both read-only), a fresh `CLAUDE_CONFIG_DIR` at
`/review/config` (writable, deleted after the run) and the pinned binary. There is no `/home`, so the gh login, the key
store and every other host file are absent. No CLAUDE.md memory of any kind is loaded: every session runs with
`CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` (the instruction fence). The flags and settings are listed in `claude_flags()` and
`review_settings()` in `worker.py`, each checked against `claude --help` of 2.1.296.

A trading head (every `us-equities-trading` head, and a `native-agent-stack` head that changes one of its
`trading_paths`) gets the upstream-alignment rule in its prompt. Every claim or fix about external behaviour must cite
an upstream pin (`~/code/upstream/<owner>/<repo>@<sha>:path:line`) or a vendor documentation URL, and the reviewer
reports `[upstream]` findings for an uncited claim, a pin that does not support its claim, or code that deviates from
the cited behaviour. The pinned files the diff cites are exported from the local mirrors' git objects into the input
directory as data. The citation labels come from the pull request, so they go to the data file
`upstream-citations.txt` and never into the prompt's instructions. For any other citation, and for every URL, the
prompt says the check covers citation presence only.

## Install (command center)

0. Install srt from its pinned npm tarball (sha256
   `5a730e4367c264ccc4b592af01dab038a6c39db7c184efbd132841688fa854f1`), without its install scripts, and check that
   socat is installed. Node is the host's mise install (`~/.local/share/mise/installs/node/24.21.0/bin/node`, at least
   22.12). The worker checks the version and npm's recorded integrity of the install on every tick.

   ```sh
   npm pack @anthropic-ai/sandbox-runtime@0.0.79   # then compare sha256sum of the .tgz with the value above
   npm install --prefix ~/.local/share/claude-review-worker/srt --ignore-scripts ./anthropic-ai-sandbox-runtime-0.0.79.tgz
   ```
1. Run the offline probes, then the live probes.
   - The offline checks cover the sandbox, the client's start, main's project settings, the run's config directory
     and the L checks. The L checks drive the exact invocation against a loopback stand-in for the Messages API, which
     plays the model with fixed tool calls (credential files, `/proc` and `/dev/fd`, links in main, a planted gh login)
     and shows what would reach a model. They are where the permission layer is measured.
   - The live mode needs a key and makes three paid runs, debited in the ledger: two short facts arms (the
     planted-fact check with its control arm), and one review of the probe head (no MCP server, no secret-like value
     echoed, and the planted uncited upstream claim flagged).
   - The live mode makes no tool-call checks. The Opus 5.5 safeguard refused that arm, and whether a call is denied is
     decided by the client, not the model.

   ```sh
   CLAUDE_REVIEW_STATE=~/.local/state/native-agent-stack/claude-review-worker \
     python3 -I tools/claude-review-worker/probes.py offline
   API_ACTIONS_LEDGER=<ledger path> python3 -I tools/claude-review-worker/probes.py live
   ```

   Each prints PASS or FAIL per check and writes `probes/<UTC stamp>/receipt.json` under the state directory. Enable
   nothing while a check fails.
2. Create `~/.config/claude-review-worker.env` (mode 0600). It holds no key:

   ```sh
   API_ACTIONS_LEDGER=/path/to/api-actions-ledger.jsonl   # required; nothing is spent without it
   CLAUDE_REVIEW_POST=0                                    # 1 posts statuses and comments; 0 writes everything, posts nothing
   # CLAUDE_REVIEW_KEYS=anthropic-api-4,anthropic-api-3,anthropic-api-2   # api-4 is the one key; the spares only on credit exhaustion, logged as a warning
   # CLAUDE_BIN=~/.local/share/claude/versions/2.1.296                  # the pinned native binary
   # CLAUDE_REVIEW_STATE=~/.local/state/native-agent-stack/claude-review-worker
   # CLAUDE_REVIEW_TIMEOUT_SECONDS=2700
   # CLAUDE_REVIEW_UPSTREAM=~/code/upstream   # the local upstream mirrors, read as git objects only
   # CLAUDE_REVIEW_SRT=~/.local/share/claude-review-worker/srt          # the npm prefix of the srt install
   # CLAUDE_REVIEW_NODE=~/.local/share/mise/installs/node/24.21.0/bin/node
   # PATH=...   # only if gh and git are not under the unit's PATH (the mise shims, /usr/local/bin, /usr/bin, /bin)
   ```
3. Install the units from the live clone `~/code/native-agent-stack-live`, a detached worktree of `origin/main` that the
   service refreshes before every tick (`ExecStartPre`: `git fetch`, then `git switch --detach origin/main`; a failure
   stops the tick). The service header has the exact `sed`, `cp` and `systemd-analyze verify` lines. Then keep the
   user manager running without a login session and start the timer:

   ```sh
   loginctl enable-linger "$USER"
   systemctl --user daemon-reload
   systemctl --user enable --now claude-review-worker.timer
   ```
4. Watch the first ticks with `CLAUDE_REVIEW_POST=0`, then set it to `1`. The first tick after that posts the stored
   result of every current head once.

## Operate

- Logs: `journalctl --user -u claude-review-worker.service`; one JSON line per tick in `ticks.jsonl` under the state
  directory (skips, such as no room under the ceiling, are logged there and in the journal).
- What the next tick would review: `python3 -I tools/claude-review-worker/worker.py select` (API reads only).
- Run one tick now: `systemctl --user start claude-review-worker.service`.
- State directory (`CLAUDE_REVIEW_STATE`, mode 0700):
  - `attempts/<owner__repo>/pr<n>-<sha>.json`: the authoritative attempt markers;
  - `reports/<owner__repo>/pr<n>-<sha>/attempt<k>/`: `prompt.txt`, `stream-<try>.jsonl` (the masked stream),
    `report.md`, `verdict.json`, `numbers.json`, `status.json`, `comment.md` (private repository only) and
    `receipt.json` (run id, keys, ledger refs, cost, client version, binary sha256, stop class, posting state);
  - `repos/`, `work/`: the bare clones and the main worktrees; `essential/`: the per-head path decisions;
    `skipped/`: heads with nothing to review.
- Review a head again: move its attempt marker out of `attempts/`; the next tick treats the head as new.
- A head refused for its diff size or its own size needs a paths-limited review by other means (for example the
  `paths` input of `claude-pr-review.yml`); the worker has no paths option.

## Posting

Posting uses the ambient `gh` login in this process; the sandboxed process never sees it.

- The pull request is read just before the status and again before the comment. If its head is no longer the reviewed
  commit, or it is closed, nothing more is posted for that review (`superseded` in the attempt marker). If the head
  moves after both were posted, the comment gets a superseded line.
- Each post is marked `sending` before it and `posted` after it. A retry first looks on GitHub for the commit's latest
  `claude-review/local` status and for the attempt's comment (a hidden marker line), by the same login, so a lost
  reply or a stopped tick never posts twice.

- Both repositories: `POST /repos/{owner}/{repo}/statuses/{sha}` with `state`, `context` (`claude-review/local`) and a
  `description` of at most 140 characters built from parsed fields only, for example
  `Claude local review: CHANGES (P1 0, P2 3, P3 1)`. No `target_url`.
- `us-equities-trading` only, and only when the configuration and the API both say private: one comment with the
  verdict, the counts and the findings.
  - The findings are the only model text, and they sit inside one fenced code block. Every backtick in them is replaced
    so the fence cannot be closed, which means no image, link, HTML or `#N` reference renders.
  - They are sanitized first: absolute paths under the review's working and input directories become relative,
    secret-like values are omitted, and every `@` gets a zero-width space after it.
  - The comment is refused when it still names the home directory or the user name (both read at run time). It is cut
    at 60,000 characters.
- Status mapping:
  - PASS with no P1 and no P2 is `success`;
  - CHANGES, BLOCKING, or any P1 or P2 is `failure`;
  - a refusal, a bounds failure or a missing verdict is `error`;
  - a budget stop is `error`, whatever it found.

## Inverse

```sh
systemctl --user disable --now claude-review-worker.timer
rm ~/.config/systemd/user/claude-review-worker.service ~/.config/systemd/user/claude-review-worker.timer
systemctl --user daemon-reload
rm ~/.config/claude-review-worker.env
rm -r ~/.local/share/claude-review-worker/srt
```

The state directory can then be deleted; its ledger rows stay in the shared ledger. Posted statuses cannot be deleted
through the API; a later status with the same context replaces them, and the command center's landing scripts stop
requiring `claude-review/local` when the worker is retired. Posted comments can be deleted by hand.
