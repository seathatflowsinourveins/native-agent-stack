# Login shell contract acceptance scripts (2026-09-29)

The probes behind the "Update 2026-09-29" section of [the terminal decision](../../../docs/decisions/2026-09-28-terminal-experience.md)
and its [receipt](../../receipts/login-shell-contract-20260929.json). They are read-only or write only to the system temporary
directory; none of them edits a settings file and none writes into this folder. `scrub_placeholder_probe.py` removes its throwaway homes,
the client's per-directory state under `/tmp/claude-<uid>/` for those homes (by name), and the client's shared
`/tmp/inline-comments-buffer.jsonl` when the run created it, and it checks the real home's placeholder names before and after. Run them with
`python3 -B` so no `__pycache__` appears here. Each was run on the workstation the receipt names.

| Script | What it measures | How it was run |
| --- | --- | --- |
| `scrub_placeholder_probe.py` | What `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` leaves behind on Linux with bubblewrap: three arms in throwaway homes (no variable; the variable with a stock Ubuntu-shaped home that has only `~/.profile`; the variable with a real `~/.bash_profile` that hands off to `~/.profile`). Runs the installed native binary under `env -i` with a dummy non-credential API value; the run stops at the API-key check after the files are written, so no model call is made. In the stock-home arm it also runs the installed `claude doctor` and records whether its stale-mask-file warning names the scrub-created file. Prints counts, generic dotfile names and booleans, and whether each login `PATH` still holds `~/.local/bin`. The client also touches one absolute path outside any home, `/tmp/inline-comments-buffer.jsonl`; the script removes it only if the run created it, and reports both facts | `python3 -B scrub_placeholder_probe.py` (needs `claude` and `bwrap`) |
| `login_shell_check_controls.py` | The doctor's login-shell check (function copied from the practice repository, which has no remote) against five temporary homes: `~/.profile` only, an empty `~/.bash_profile` (the incident), a real hand-off `~/.bash_profile`, an empty `~/.bash_login`, and no startup files. With `--real-host` it also checks the running user's home, read-only | `python3 -B login_shell_check_controls.py --real-host` |
| `login_path_digest.py` | The number of entries and a SHA-256 prefix of the PATH a login shell ends up with, started the way the doctor check starts one (`env -i`, the distro default PATH, `/bin/bash -lc`). Run before and after a change to the login startup files: an unchanged digest shows the change altered nothing | `python3 -B login_path_digest.py` |
| `agents_json_probe.py` | What `claude agents --json` prints on this host: rows, kinds, statuses and field names, and whether `--cwd` and `--all` change it. Read-only, no session started; a live snapshot | `python3 -B agents_json_probe.py` |
| `landscape_refresh.py` | The dated upstream refresh: Windows Terminal releases and the two toast signals, the newest Claude Code and Codex releases, how many lines of Codex's notification, palette and config sources changed between the installed tag and the newest stable tag, the candidate notifiers' heads against the recorded pins, and the public Claude Code reports about the placeholder files. Reads only; never files or comments | `python3 -B landscape_refresh.py` (needs `gh` signed in) |

Not retained: the incident host's paths and session identifiers, and the peer probe's scratch directory. The counts, names of
generic dotfiles and booleans are in the receipt.
