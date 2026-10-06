# Tier A skill-state recording (2026-10-06)

Status: draft implementation for review. No host activation, backfill, hook trust
or Tier B adoption is authorized by this record.

The recorder serves sourced complex-system work by recording the native skill
state available to a lifecycle or workflow owner. Filesystem observation, source
review, local fixtures and native-client acceptance remain separate evidence
classes. An observed folder is neither a historical installation date nor proof
that a model discovered or invoked its skill.

## Maintained sources and demonstrated gap

- [Claude's unchanged audit example](https://code.claude.com/docs/en/hooks-guide#audit-configuration-changes)
  provides a command-hook metadata log. Deduplication across installer routes,
  clients and retained profile views is the demonstrated local integration gap.
- [Claude hooks](https://code.claude.com/docs/en/hooks) define ConfigChange,
  SessionStart watchPaths, FileChanged, InstructionsLoaded and asynchronous
  command behavior. [Codex hooks](https://developers.openai.com/codex/hooks) define
  background commands and independent hook trust.
- `openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:codex-rs/hooks/schema/generated/{post-tool-use,session-start}.command.input.schema.json`
  supplies the native Codex input formats. InstructionsLoaded is a Claude audit
  channel here; no Codex event or effective runtime policy is fabricated.
- [Claude's configuration-root override](https://code.claude.com/docs/en/env-vars)
  and [Codex's state location](https://developers.openai.com/codex/config-advanced#config-and-state-locations)
  identify public root locators. At the Codex pin,
  `codex-rs/utils/home-dir/src/lib.rs:13-49` selects CODEX_HOME,
  `codex-rs/ext/skills/src/host_roots.rs:103-112` preserves HOME/.agents skills and
  derives the system cache from the config folder, and
  `codex-rs/core-plugins/src/store.rs:87-94` derives its plugin cache.
- [Codex global AGENTS sources](https://developers.openai.com/codex/guides/agents-md)
  use the selected Codex home; [Claude memory](https://code.claude.com/docs/en/memory)
  documents plain instruction files and rules. Unsupported instruction roots
  receive unknown scope, rather than a guessed body hash.
- Python's maintained [flock](https://docs.python.org/3/library/fcntl.html#fcntl.flock),
  [open/descriptor metadata](https://docs.python.org/3/library/os.html#os.open)
  and [atomic replacement](https://docs.python.org/3/library/os.html#os.replace)
  provide the local state primitives. They do not confer native-client acceptance.

## Selected observation contract

Only safe SKILL bytes and selected public lock identity fields are read.
Supporting files contribute stat metadata only; bytecode and dependency caches
are excluded. Source, activation and usage remain unknown where evidence is
absent. Settings, authentication stores and transcript bodies are never read.

The recorder honors only the named public CLAUDE_CONFIG_DIR/CODEX_HOME path
overrides, preserving shared HOME/.agents and project scope. Relative or
redirected roots remain unsupported observations with no default-profile
fallback. Aliases may reach only explicitly trusted canonical skill roots.
Native-profile and project views are retained separately; switching views cannot
claim physical removals from the old view. Canonical shared-root observations
deduplicate alias changes across profile views. A canonical locator hash and
the current SKILL hash bind one file identity; a same-named skill in another
profile cannot substitute for it.

A nonblocking lock surrounds the pending journal, deduplicated ledger appends
and next snapshot. The order is pending journal, append plus fsync, then snapshot.
An unchanged call reads no SKILL body or public lock and launches no status
process. A changed call invokes only S4's metadata-only status mode with selected
public roots and a bounded subprocess timeout, never a fresh client or model.
Instruction audit retains only sanitized locators and hashes, with no body or
permission/decision output.

Every managed file uses required O_NOFOLLOW/O_NONBLOCK flags and fstat regular
validation before flock or content. Special files and fdopen failures close the
descriptor. Atomic staging opens without O_TRUNC, then truncates only a verified
regular descriptor. Error logging is terminal best-effort and the hook returns
zero. Trusted/cooperating state directories remain a requirement; final-component
no-follow is not an ancestor sandbox. Regular-file and fsync latency is unbounded,
and this journal is not a power-loss durability guarantee.

## Alternatives, checks and overturn conditions

Native inventory alone lacks a retained transition history. Re-running a client
or full content tree on every tool event introduces unnecessary hot-path work
and unsafe representation/acceptance confusion. The selected approach uses the
upstream metadata audit plus state stamps, scoped identities and a journal; it
never replaces the clients' own discovery or the repository's install lifecycle.

Focused repository fixtures must retain failure and recovery controls for
descriptor/FIFO poisoning, profile switching, same-name distinct hashes, shared
aliases, add/remove/add, bytecode exclusion and unknown sources. They are local
integration checks. Earlier committed test receipts remain historical inputs;
source repairs need new test/validation receipts rather than amended passing
results. No unexecuted fixture is reported as a pass.

Activation needs the command center's ACK, user-controlled Codex hook trust,
fresh native hook-firing controls, supported schema/event checks and isolated
upstream installation/removal observations. Unchanged-process p95 must be at
most 250 ms with no body/lock/status work; changed observation remains asynchronous
and its filesystem limitations stay disclosed. S4 must consume the exact ledger
identity and report metadata rather than model readiness. A missing event, unsafe
read, false transition, duplicate identity, journal failure or latency regression
overturns the proposal before host application.
