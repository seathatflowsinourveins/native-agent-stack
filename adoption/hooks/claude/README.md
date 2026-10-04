# Claude Code user-scope hooks of this catalog

`tools/adoption/install_claude_profile.py --only guard` copies the default files below to `~/.claude/hooks/`, each
checked against `SHA256SUMS`, and `adoption/templates/claude.settings.template.json` registers them:

| File | Event | What it does |
| --- | --- | --- |
| `effort-default-guard.py` | SessionStart | effort self-heal |
| `currency-due-notice.py` | SessionStart | the stack-currency due line |
| `../../../scripts/hooks/secret_path_guard.py` | PreToolUse (Bash) | the secret-path guard |

## Held out of the default: the token-lane carriers

The token-lane carriers are this repository's own adaptation, not a feature of an upstream tool, and they add context to
every request. The owner's clean-install directive of 2026-10-04 holds them out of the default until the command
center's A/B on the frozen Harbor setup, at the operating point, decides
([decision](../../../docs/decisions/2026-10-04-claude-template-holds-out-token-lane-carriers.md)). They stay in the
repository, byte-pinned in `SHA256SUMS`:

- the SubagentStart hook `token-lanes-subagent-start.py`, its default block `token-lanes-block.md` and the five role
  blocks `token-lanes-block.<role>.md` (builder, researcher, reviewer, scout, verifier);
- the SessionStart hook `token-lanes-session-start.py` and its block `token-lanes-block.main.md`.

The template registers neither hook, `install_claude_profile.py` copies none of these files unless `--hook NAME` names
it, and `apply_claude_settings.py` removes a live hook entry whose command equals, exactly (no trimming), one of the carrier
commands this repository shipped (`SHIPPED_CARRIER_COMMANDS`, as shipped or with the placeholder replaced by the text
`render_config.py` writes there). The renderer substitutes the `HOME` it is given as written, so that text may be any spelling of
the home (a trailing slash, a `.` or `..` segment, a doubled slash, a symlink alias); it counts when it is an absolute path with no
control character, quote, `$`, backtick or backslash whose realpath is the realpath of the settings file's home. The home is the
one the settings file belongs to: its resolved path must be `<home>/.claude/settings.json`, and for any other path nothing is
removed. Any other hook, including one that wraps, chains or
edits a carrier command, is the host's and is kept, so a host that applied an older template ends up clean unless it edited the
entry itself.

### Opt in on one host

```sh
python3 tools/adoption/install_claude_profile.py --only guard \
  --hook token-lanes-subagent-start.py --hook token-lanes-block.md --hook token-lanes-block.builder.md \
  --hook token-lanes-block.researcher.md --hook token-lanes-block.reviewer.md --hook token-lanes-block.scout.md \
  --hook token-lanes-block.verifier.md --hook token-lanes-session-start.py --hook token-lanes-block.main.md
python3 tools/adoption/apply_claude_settings.py --template adoption/hooks/claude/held-out-hook-entries.json
```

The second command merges the two hook entries of `held-out-hook-entries.json` (the command runs the file through
`$HOME`, which the hook shell expands, so the file needs no rendering). From then on, apply the default template with
`--keep-held-out-hooks`, or its next run removes the entries again. To opt out, apply the default template without the
flag; the files in `~/.claude/hooks/` stay and are harmless.
