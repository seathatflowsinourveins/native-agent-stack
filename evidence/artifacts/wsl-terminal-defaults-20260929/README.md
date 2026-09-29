# Repository-carried terminal defaults: acceptance scripts (2026-09-29)

The checks behind the "Repository-carried defaults" section of [the terminal decision](../../../docs/decisions/2026-09-28-terminal-experience.md)
and its [receipt](../../receipts/wsl-terminal-defaults-20260929.json). Each takes the checkout to test as its argument, is read-only apart from a
private temporary directory it removes, and prints booleans, counts and generic names only. Run them with `python3 -B` so no `__pycache__` appears
here. Each was run on the workstation the receipt names.

| Script | What it measures | How it was run |
| --- | --- | --- |
| `overlay_noop_check.py` | Whether merging `adoption/templates/claude.settings.linux-wsl2.overlay.json` into the live `~/.claude/settings.json` with the repository's own merge tool (`--dry-run`) would change it. On a host that already carries the decision's values the answer must be no; on a new host it names the top-level keys the merge would change. Because the merge de-duplicates hooks by command anywhere in the event, it also checks that exactly one Notification group holds the bell command and that its matcher equals the overlay's (a catch-all group or an older matcher merges to itself) | `python3 -B overlay_noop_check.py <checkout>` |
| `codex_tui_strict_check.py` | The shared Codex template rendered for the example host and loaded by the installed Codex under `--strict-config`, with three controls: a wrong type for `notifications` and an unknown top-level key (both must be refused) and an unknown key inside `[tui]`, which Codex does not refuse (so the repository's test pins the `[tui]` setting names). The run stops at authentication after the configuration loads | `TMPDIR=<private dir> python3 -B codex_tui_strict_check.py <checkout>` (needs `codex`) |
| `login_shell_bash_truth.py` | The static `scripts/adoption_status.py --login-shell` model against the real bash login search: every combination of `~/.bash_profile`, `~/.bash_login` and `~/.profile` over eight states (absent, empty, content, directory, dangling symlink, symlink to a file, `/dev/null`, unreadable), each run through `bash -l`, a FIFO case (bash blocks at open), three stat-error cases (a symlink loop, `HOME` being a regular file, a `HOME` the user cannot search: each ends the search in bash and is called unusable by the model), plus a negative control (a model that takes an empty file as absent) that must disagree with bash somewhere | `python3 -B login_shell_bash_truth.py <checkout>` (needs `bash`) |
| `claude_binary_notification_scan.py` | Which installed Claude Code releases know the notification literals the overlay relies on: counts of `notifications_disabled`, `terminalSequence` and the two `worker_permission_prompt` call sites in each binary of the native install (or in the file given), so the overlay's whole matcher can be said to be live on a release. A binary in another distro without Python is counted with `grep -a -c` instead. Read-only | `python3 -B claude_binary_notification_scan.py [<binary>]` |

The Windows Terminal settings patch and the second distro's overlay merge were host operations on private files (byte-safe edit with a backup, and a
merge of a copy with the repository's own tool, written back atomically after a backup in that distro); their read-back is recorded as values in the
receipt and the scripts are not retained. The host practice repository (no remote) holds the profile check and its controls; the receipt records their
results and its commit.
