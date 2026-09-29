# Terminal experience acceptance scripts (2026-09-28)

The probes behind [the decision](../../../docs/decisions/2026-09-28-terminal-experience.md) and its
[receipt](../../receipts/terminal-experience-20260928.json). They are read-only or write only to the system temporary
directory; none of them edits a settings file and none writes into this folder. `alert_probe.py` deletes its private payload
directory, also when interrupted or failing; `color_capture.py` deletes its throwaway configuration directory when it finishes;
`validate_fragment.py` keeps a downloaded copy of the schema there as a cache. Each was run on the workstation the receipt names.

| Script | What it measures | How it was run |
| --- | --- | --- |
| `wt_tab_titles.ps1` | Windows Terminal tab titles through UI Automation: counts of tabs, tabs still showing the static profile title, distinct dynamic titles and the largest duplicate group. Never prints a title | `powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File <path>` |
| `wt_tab_sentinels.ps1` | The same read, plus the raw name of tabs whose title starts with `trial-` or is `title-trial-ok` (trial sentinels carry no session content), and a SHA-256 prefix of the sorted names | same |
| `color_capture.py` | The colour classes Claude Code emits: runs `claude --bare` for 7 s in a pty with a throwaway `CLAUDE_CONFIG_DIR` (deleted afterwards) and a dummy API key and counts `38;2`, `48;2`, `38;5`, `48;5` and basic SGR sequences, once with `COLORTERM` unset and once with `truecolor` | `python3 color_capture.py` (needs `claude` on `PATH`) |
| `alert_probe.py` | Whether a pending `AskUserQuestion` (`ask`) or plan approval (`plan`) raises a Notification event and a bare BEL byte, and how long after the dialog opens. Drives a real short session from an already-trusted directory with `--setting-sources user` plus an observer hook overlay, sends no keys while waiting, and never accepts a workspace-trust dialog. `ask` runs in the user's own default permission mode and prints the mode read from the on-screen footer (`--permission-mode` forces one); `plan` runs in plan mode. `--control` runs the same setup with every hook disabled and detects the dialog from its on-screen text (0 BEL bytes expected, which attributes the BEL to the hook; the Notification count is not observable in that mode). `--selftest` checks the BEL byte counter, which models the pinned Windows Terminal output parser, against 22 cases, and the private-directory cleanup after an interruption and a failure | `python3 -B alert_probe.py ask`, `... plan`, `... ask --control`, `... plan --control`, `... ask --permission-mode default`, `... --selftest` |
| `validate_fragment.py` | Every profile of a Windows Terminal fragment against `doc/cascadia/profiles.schema.json` at tag `v1.24.11911.0`, with the draft the schema declares (2020-12); the schema is cached in the system temporary directory (needs `gh`) | `uv run --no-project --with jsonschema python validate_fragment.py <fragment.json>` |
| `fragment_check_mutants.py` | Negative controls for the host repository's `checks/check-terminal-profiles.py`: nine single-defect mutants of the fragment (title suppression, a loud sound, a relative `bellSound`, an AI `bellStyle` without `taskbar`, `bellStyle` `all` and a `notification` list on static profiles, `audible` on a static profile, no `COLORTERM` key, `COLORTERM` in the command line) must each fail exactly one rule, the expected one (eight distinct rules), and the unmutated fragment must pass in fixture mode. Needs `~/code/nativestack-practice`; writes only to a temporary directory | `python3 -B fragment_check_mutants.py` |
| `wav_levels.py` | Peak and RMS level (dBFS) and duration of candidate Windows notification sounds | `python3 wav_levels.py` |

Not retained: the observer hooks' raw Notification payloads (they carry session identifiers and paths; `alert_probe.py`
writes them to a private temporary directory and deletes it before it exits), the tab titles of live sessions, and the
trial profiles' identifiers. The counts and timings are in the receipt. Run scripts with `python3 -B` (or set
`PYTHONDONTWRITEBYTECODE=1`) so no `__pycache__` appears here.
