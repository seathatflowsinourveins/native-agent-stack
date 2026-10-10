# Landing scripts

The command center (CC) lands pull requests with three files kept here, so the repository holds the one copy and its tests:
`uet_land.sh` (the private trading repository), `nas_land.sh` (this repository) and `codex_gate.py` (the Codex review gate that
both call). They merge pull requests. No workflow runs them: the CC runs them from a clone of this repository, and CI runs
their tests.

## What each does

**`uet_land.sh <pr> <read-head-prefix>`** lands a pull request of `seathatflowsinourveins/us-equities-trading` by squash
merge. In order: the `trading-cc-read` commit status and its record (below); each file in `VERDICT_FILES` (and `GATES_DONE`
when such a file states a landing gate); the head is the read head or a pure rebase of it; a draft is marked ready and
`codex_gate.py` must report the latest review finished (polled for up to 20 minutes); when Codex reports its usage limit,
`GPT_VERDICT` (the co-op's verdict naming the read head) stands in for it; the branch is updated by rebase and its change must
equal the read change; CI is complete with nothing failing and `ci-gate` reported; open review threads stop it (exit 8); the
merge is pinned to the head with `--match-head-commit`.

**`nas_land.sh <pr> <read-head-prefix> <verdict-file>...`** does the same for `seathatflowsinourveins/native-agent-stack`,
with the verdict files as arguments (at least one) and these differences: `manifests/evidence.json` is left out of the change
identity (CI arbitrates the registry), a BEHIND branch is updated server-side (merge method), the aggregate `validate` check
must have succeeded at the head (the latest run per check name counts), and just before the merge the head is merged into the
current `origin/main` in a temporary worktree under `/var/tmp` where `scripts/validate.py` must exit 0 (exit 10 otherwise).

**`codex_gate.py <owner/repo> <pr>`** prints one status line about the connector's review and exits 0 (a review finished at or
after the latest trigger and none is running), 3 (running, or none finished since the latest trigger: poll again), 4 (the latest
review ended other than Completed), or 5 (Codex is unavailable: a usage-limit or account notice since the trigger, or no
connector activity for 10 minutes). A trigger is the pull request's creation, a ready-for-review event, or a comment by anyone but
the connector that starts with `@codex review` or `@codex security review`; a push is not a trigger. Any completion evidence
since the trigger (a Completed row, a connector review, a +1 reaction, its no-findings comment) gives 0 even when a later row
says Cancelled; a Running row always gives 3.

## Variables

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `LANDING_UET_REPO` | `$HOME/code/us-equities-trading` | `uet_land.sh` | clone of the trading repository: fetches, `rev-parse`, change identity (the path must not contain whitespace) |
| `LANDING_NAS_REPO` | `$HOME/code/native-agent-stack` | `nas_land.sh` | clone of this repository, used the same way (no whitespace) |
| `LANDING_COORD` | `${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/coordination` | both | coordination tree; a status description `PASS: trading-cc/reads/<record>.md` names `$LANDING_COORD/trading-cc/reads/<record>.md` |
| `LANDING_GATE` | `codex_gate.py` in the directory of the script, symlinks resolved (`readlink -f "$0"`) | both | the Codex gate; it works through a symlink or a wrapper that `exec`s the real path, and not when the script is read from a pipe or a process substitution (set this variable then) |
| `VERDICT_FILES` | none | `uet_land.sh` | space-separated verdict files that each must name the read head |
| `GATES_DONE` | none | both | receipt naming the read head; required when a verdict file states a landing gate |
| `GPT_VERDICT` | none | `uet_land.sh` | the co-op's verdict file accepted instead of Codex when `codex_gate.py` exits 5 |

The scripts also need `gh` 2.48.0 or later (`gh api --paginate --slurp`; authenticated for the repository), `git` 2.39.0 or
later (`git patch-id --verbatim`), `jq`, `python3` 3.7 or later, GNU `grep`, `sha256sum` and `readlink -f`. They run under
`set -u`, so `HOME` must be set whenever a default above is used.
`nas_land.sh` also needs a git committer identity: its validation merge (`git merge --no-commit`) refuses to start without
one, and the script then reports exit 10, "does not merge cleanly".

## Exit codes

From the script headers. `uet_land.sh`: 2 verdict gate, 3 head moved, 4 change differs, 5 CI failed, 6 timeout, 7 merge failed,
8 blocked, 9 Codex review running, not finished since its latest trigger, or ended other than Completed (`codex_gate.py`).
`nas_land.sh`: 2 verdict gate, 3 head moved, 5 CI failing, 6 timeout, 7 merge failed, 8 blocked by policy, 9 as above, 10 the
merge onto current `origin/main` fails `scripts/validate.py` or does not merge cleanly. Its header omits one code it also uses:
4 when `update-branch` is refused or the change differs after it. `codex_gate.py`: 0, 3, 4 and 5 as above.

## The record convention

A record (append-only, many heads) is accepted for a head when the last line that gives a verdict for it carries PASS or ACK. End
every section that gives or changes a verdict with a line of its own:

```
Verdict: PASS at <head8>
```

(or `ACK`, or `CHANGES_REQUESTED`; `Gate line: PASS at <head8>` is the same). A verdict file is accepted by its line 1 in the Astra
layout `... <head>...: ACK|PASS`, or by its last `Gate line:`/`Verdict:` line naming the head with PASS or ACK;
CHANGES_REQUESTED on line 1 or as that last word rejects, and a PASS or ACK anywhere else counts for nothing. The
`trading-cc-read` description must be exactly `PASS: trading-cc/reads/<record>.md` or `ACK: trading-cc/reads/<record>.md`.

## Provenance and digests

The files were moved from the CC's tools directory on 2026-10-10 and are the live copies with only host literals changed:
three lines per shell script (the repository default and `COORD` on one line, the record path, the gate path), the same line
counts, and `codex_gate.py` byte for byte. Expanding the three expressions to the CC host's paths gives the live digests below.

| File | Before correction #136 | Live copy, after #136 | Here |
| --- | --- | --- | --- |
| `uet_land.sh` | `b794e3a46772c0a598dff9eee972ad449e5d63f0c81b60b9db1d5cb4944747bb` (115 lines) | `97f6a9929f9551e48a31eb4907e8c1852fc758a0060d6be7b41a83a7d254800b` (193 lines) | `93e9f8323eb35f03e052e43394293c43789acc824b658aba66b0ff63b962f656` (193 lines) |
| `nas_land.sh` | `2fefe070b95229de3dcad14052cf5c031b70c202bf4a34f4452e6e0cb5832936` (135 lines) | `10dfdbc2560d339ce1fd707d9dc7f1b672e6420eaca41670a80cf923f74046b7` (204 lines) | `7249ce4d8838b151efe5dd69e60e64153135028bd886d0e6f2bc2174a9bae2cb` (204 lines) |
| `codex_gate.py` | (unchanged) | `31524d2871cde79ecb2c5b9bc56b6175ce9fafab9ad4d2e2e3eb3594e1cb2422` (108 lines) | the same |

Corrections the scripts carry: #118 (every gate before the merge, in order), #121 (a verdict file that states a landing gate needs
a receipt), #122 and #123 (a Codex review must have finished; uet#40 and uet#47 merged while one was running), and #136
(verdict and record acceptance, change identity and the CI line: the three loose decision points the shared
`# >>> land-gate-fns` block replaced). The block is identical in both scripts, apart from `lg_ci_state`, which only
`uet_land.sh` has.

## Known gaps, left as they were

The files are the live copies with host literals replaced, so these stay until a change with its own tests fixes them:

- `uet_land.sh`'s CI line counts the check-run conclusions FAILURE, CANCELLED and TIMED_OUT as failing. GitHub's schema also
  lists ACTION_REQUIRED, STARTUP_FAILURE and STALE (`nas_land.sh` counts `action_required`); in `uet_land.sh` a check that ends
  that way is neither running nor failing, so it does not stop a landing by itself (`ci-gate` must still be SUCCESS).
- `U` and `G` are expanded unquoted: a clone path with whitespace breaks both scripts.
- `nas_land.sh`'s header leaves out exit code 4, and its validation merge needs a git identity (above).

## Tests

`tests/test_landing_scripts.py` is correction #136's regression: it cuts each decision site out of the script text (the same
start and end lines the correction's harness used) and runs it in bash with a fake `gh`, against synthetic verdict files,
records, scratch repositories and rollups; it runs `codex_gate.py` on canned API data; and it runs both scripts end to end with
a fake `gh`, `python3` and `sleep`, including the gate path through a symlink and a wrapper. It is offline, needs `jq`, and is
Linux-only. A script edit that moves a decision site fails the module instead of leaving it untested.
