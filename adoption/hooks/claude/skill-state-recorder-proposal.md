# Proposed skill-state recorder and instruction audit

This is a PR-only integration proposal for round-2 S3. It registers no hook,
changes no permission or client setting, and runs no host backfill. The command
center owns activation after review; Codex hook trust remains `needs_user`.

The maintained starting point is Claude's [Audit configuration changes
example](https://code.claude.com/docs/en/hooks-guide#audit-configuration-changes):
a command hook appends timestamp/source/file metadata. The demonstrated gap is
deduplicating state changes across clients and installer routes. The local
[recorder](../../../tools/adoption/skill_state_recorder.py) adds that observation
only; it never installs, retires, approves, blocks, or injects context.

Native interfaces:

- [Claude hook reference](https://code.claude.com/docs/en/hooks): ConfigChange,
  FileChanged, SessionStart watchPaths, InstructionsLoaded and async commands.
- [Codex background hooks and trust](https://developers.openai.com/codex/hooks).
- `openai/codex@a956835d020762cb2b570053af06f643a11c0ecc`:
  [PostToolUse input](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/hooks/schema/generated/post-tool-use.command.input.schema.json),
  [SessionStart input](https://github.com/openai/codex/blob/a956835d020762cb2b570053af06f643a11c0ecc/codex-rs/hooks/schema/generated/session-start.command.input.schema.json).
- [Python's POSIX flock](https://docs.python.org/3/library/fcntl.html#fcntl.flock).

## Observation contract

The command reads native hook JSON from stdin. It ignores tool arguments,
responses, transcript paths and unknown payload fields. It checks the public
global `.agents/.skill-lock.json`, project `skills-lock.json`, global/client/project
skill directories, and both clients' plugin caches. ConfigChange is a signal;
the recorder never reads settings.json, config.toml or authentication stores.

Only SKILL.md bytes and selected public lock fields are read. Rows contain
sanitized locators, hashes, bytes, safe names, and nullable source metadata.
Supporting files contribute stat metadata only, without content reads. This is
not a Git tree/content integrity check. `__pycache__` and `*.pyc` are excluded,
as are authentication/key/environment files and irrelevant dependency folders.
Native client listing, activation and usage remain unknown.

All state changes are under one nonblocking POSIX flock. The cache stores file
and directory stat stamps; an unchanged call reads neither SKILL bodies nor the
public lock and invokes no status process. Changes produce one row per changed
canonical skill identity; global Claude symlink aliases do not produce duplicate
identities. Distinct plugin/version paths retain distinct `state_key` values.
Project state is separated from global state, so visiting another project does
not declare the previous project's skills removed.

A pending journal precedes ledger appends. Recovery checks recorded IDs before
retrying append and commits the next snapshot afterward. Add/remove/add remains
three real transitions. A first scan emits `observed`, which does not claim a
historical install date. No audit-log backfill is implemented here.

Lock contention, malformed input, scan limits, status failure and unexpected
observer errors fail open. Error rows retain only error type/stage/exit code,
never exception text or hook payloads. Stdout stays empty and the command returns
zero. If configured state itself is unavailable, no error row can be guaranteed.
The timer and later triggers provide an eventual-observation backstop after
contention; this is not an atomic transaction with an upstream installer.

The ledger interface for S4 is `schema_version: 1`, `kind: skill_state_change`:

```json
{
  "id": "<deduplicated transition hash>",
  "occurred_at_utc": "<observation time>",
  "skill_name": "example",
  "scope": "home_agents",
  "state_key": "<canonical-path hash>",
  "action": "add",
  "event": "added",
  "source": {"repository": null, "ref": null, "tree_sha": null, "status": "unknown"},
  "before": null,
  "after": {
    "skill_md_sha256": "<actual hash>",
    "skill_md_bytes": 100,
    "frontmatter_sha256": "<header hash>",
    "folder_fingerprint": "<stat-only fingerprint>",
    "locator": "<home>/.agents/skills/example/SKILL.md"
  },
  "usage": "unknown"
}
```

`action` is observed/add/change/remove; `event` is
observed/added/changed/removed. `scope` names home_agents, home_claude, home_codex,
project_agents, project_claude, claude_plugin or codex_plugin. Removal has
`after: null`. Full snapshots also declare the fingerprint method. A lock's
`skillFolderHash` is source metadata, not independently reconstructed integrity.
Missing refs stay null; no HEAD or installation provenance is invented.

Only after a detected change, the recorder invokes:

```sh
python3 scripts/skills_status.py --metadata-only --ledger <state>/ledger.jsonl --json
```

This S4 interface must exist before activation. Its output is discarded; a
nonzero exit or timeout is an observer error, never a blocking hook result.
The two-second timeout bounds that process. No native client or model job is
started. Full live-catalog checks remain outside the hot path.

## Passive registration proposals

Use the reviewed checkout's absolute recorder path in each command below. Keep
existing hook arrays intact and append these groups at the end. In particular,
Codex trust keys include group/handler indices: inserting earlier groups would
invalidate existing trust. These snippets are never merged by this script.

Claude addition, with `<RECORDER>` replaced by that absolute path:

```json
{
  "hooks": {
    "ConfigChange": [{"matcher":"skills|user_settings","hooks":[{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}],
    "SessionStart": [{"hooks":[{"type":"command","command":"python3 <RECORDER> --mode watch-paths","timeout":1},{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}],
    "FileChanged": [{"hooks":[{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}],
    "PostToolUse": [{"matcher":"Bash|mcp__plugin_context-mode_context-mode__ctx_upgrade","hooks":[{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}],
    "InstructionsLoaded": [{"hooks":[{"type":"command","command":"python3 <RECORDER> --mode instructions","async":true,"timeout":10}]}]
  }
}
```

The tiny synchronous watch-path command returns only Claude's native
`watchPaths` for the public lock, without a scan or ledger mutation. Omit the
FileChanged matcher so it handles dynamic paths without watching a literal `*`.
InstructionsLoaded is audit-only; Claude discards its decision output. The logger
retains an allowed instruction file's hash and sanitized locator, never its body.
Unsupported/external paths get a null hash and unknown scope. The native event
does not certify that a named skill was subsequently invoked.

Codex addition:

```json
{
  "hooks": {
    "PostToolUse": [{"matcher":"Bash","hooks":[{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}],
    "SessionStart": [{"hooks":[{"type":"command","command":"python3 <RECORDER>","async":true,"timeout":10}]}]
  }
}
```

**Trust is needs_user.** New/changed non-managed Codex hooks are skipped until
trusted. This PR chooses no bypass flag or managed-policy route and copies no
trust/auth/configuration stores. The user can review through `/hooks` after
the command center appends the groups. A fresh sandbox's empty trust state must
never be mistaken for a failed hook treatment.

The existing daily currency timer can later invoke the same recorder with empty
stdin (`CurrencyTimer`). Timer registration, host apply, sign-in and historical
hf-cli/mineru backfill remain the command center's separate steps.

## Required acceptance and limits

Local tests use only owned temporary fixtures outside shared tmpfs. They check
canonical aliases, concurrent deduplication, add/remove/add, source unknowns,
bytecode exclusion, malformed/error fail-open behavior, crash recovery, safe
instruction hashing and the metadata-only status boundary. They are integration
fixtures, not upstream client acceptance.

Before activation, independently verify:

1. Both native hook schemas accept the append-only configuration and its exact
   installed client versions support the events. A trusted positive control
   produces an actual ledger row in each fresh client; keep the untrusted/skipped
   Codex control separately.
2. Upstream add/remove in an authorized isolated home yields one add and one
   remove row, even with concurrent native triggers. Inspect the actual lock,
   folders and ledger, and retain failed attempts.
3. With a representative frozen inventory, unchanged hook process latency is
   p95 at most 250 ms, with zero body/lock reads and zero status launches. Changed
   scans are asynchronous and bounded by the ten-second hook timeout; metadata
   status is bounded to two seconds. Retain actual timing samples before claiming
   this bound passed.
4. Every ordinary recorder/audit invocation exits zero, prints no context or
   decision fields, and reads no authentication file. The watch-path command's
   sole output is native watch registration.

Stat fingerprints can miss changes whose metadata is deliberately restored.
They do not prove all supporting bytes match a pin, plugin activation, native
skill reads, model efficacy, provider identity or usage. Preserve those unknowns.
The manifest reconciler and command center decide what to adopt or retire.

Rollback removes only the newly appended hook groups after matching their exact
reviewed definitions. Do not shift surviving Codex indices. Preserve the ledger
as history; it is an observation log, not configuration or authority.
