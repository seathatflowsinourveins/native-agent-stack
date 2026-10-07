# Proposed Claude template-memory exclusions (2026-10-06)

Status: draft proposal for the command center's decision. Native client
acceptance is pending; this record does not authorize a host change.

## Problem and scope

The C6 observation in the peer session's improvement manifest reported an
automatic nested load of `examples/claude-native/CLAUDE.md` when reading an
example file, and the scaffold's `CLAUDE.md` importing `AGENTS.md`. Those files
are installation templates. Reading an example or scaffold source should not
add them as operating instructions for this repository.

The source of that observation is `IMPROVEMENT-MANIFEST.md`, C6, lines 136-142
(2026-10-06), held in the private coordination record. It is historical peer
evidence, not a fresh client run by this lane. This proposal supports the US
equities R&D north star by keeping template reads from adding instructions to
the foundation context. Domain instructions remain eligible to load.

## Sources and the client-map gate

At repository pin `d9eb68750311d5f888adec140723da174f9fe10c`, the `about` field
of `adoption/new-wsl/client-config-map.json:3` describes a closed world of the
client templates and new-distribution additions. The explicit inputs in
`tools/adoption/new_wsl_client_config.py:130-147` contain those templates and
additions; they do not contain the repository's `.claude/settings.json`.
Adding an unmapped template setting would fail that check. This change adds
a project setting, leaving the template map and its inputs unchanged.

Installed `claude --version` returned `2.1.292 (Claude Code)`, and its
`--help` exposes `--settings` and `--setting-sources`. The official repository's
`v2.1.292` tag resolves to
`anthropics/claude-code@fbe20e00e2851fc01506f54f98a8f0b875af3847`. Its
[`CHANGELOG.md:2784`](https://github.com/anthropics/claude-code/blob/fbe20e00e2851fc01506f54f98a8f0b875af3847/CHANGELOG.md#L2784)
records the 2.1.239 fix for exclusions through symlink paths. The pinned
source reviewed here is the changelog; the setting's contract below comes
from the vendor's documentation, not a memory-loading engine source review.

The vendor's [memory documentation, "Exclude specific CLAUDE.md files"](https://code.claude.com/docs/en/memory#exclude-specific-claude-md-files),
read 2026-10-06, documents glob matching against absolute file paths, gives
a leading `**/` example, permits the project settings layer, and states that
arrays merge across layers. Its [AGENTS.md loading rules](https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md)
describe nested native AGENTS loading and state that imports and
`claudeMdExcludes` apply to AGENTS files. These are the sources for the three
portable suffix globs. No shell or environment-variable expansion is assumed.

## Proposed change and alternatives

Add only this property to the repository's `.claude/settings.json`:

```json
{
  "claudeMdExcludes": [
    "**/examples/claude-native/CLAUDE.md",
    "**/adoption/scaffold/CLAUDE.md",
    "**/adoption/scaffold/AGENTS.md"
  ]
}
```

The scaffold AGENTS path is the import target and a possible native instruction
file, so excluding it explicitly completes the template scope. Each pattern
matches that exact suffix; it does not match root instructions, blueprints,
ordinary example files or other instruction-file names. These suffixes can
also match a similarly structured external path read while this project's
settings apply. The command center should consider that scope in its decision.

Every existing permission, hook, model and workflow setting is preserved.
No user configuration, adoption template, scaffold contents or instruction
file changes. Excluding automatic memory does not prohibit an explicit read
of the template as task data.

Alternatives were keeping the duplicate automatic loads, using private
absolute paths in a local setting, deleting the template instruction files,
or adding exclusions to the adoption settings template. The first retains
the observed overhead; private paths are not portable; deleting templates
breaks their installation role; the shared template would need a separate
client-map decision and affect other projects. A native read-back showing
that the proposed exclusions do not work, suppress required instructions,
or do not remove the nested load would overturn this proposal.

## Evidence and owner acceptance

The companion
[`receipt.json`](../../evidence/artifacts/claude-template-memory-exclusions-20261006/receipt.json)
separates source review, existing local integration tests and structural
validation. No added test mirrors the literal configuration. The existing
project permission/hook checks and Claude profile contract tests protect
the settings that this change must preserve. They cannot establish Claude's
runtime memory loading or token savings.

After the command center accepts the draft and applies its own checkout and
client route, it performs the native check in a fresh interactive Claude
session with project settings enabled:

1. Read an ordinary file under `examples/claude-native/`, then a scaffold
   source. Run `/context` and retain the native Memory files table. Neither
   template CLAUDE file nor scaffold AGENTS may appear as nested memory.
2. Read a file under a blueprint that has domain instructions. Retain the
   subsequent `/context` table showing its relevant instructions still load,
   along with the root/user operating instructions.
3. Retain a baseline from the same client and scopes without these project
   exclusions, if needed to distinguish an absent nested-load trigger from
   a working exclusion. Report actual native counters; no characters-to-token
   conversion or claimed saving is supplied by this PR.

The command center owns that acceptance and any rollback. A rollback removes
these three project exclusions through a reviewed repository change and a
fresh session; arrays merged from other settings layers must be checked
separately. This lane starts no Claude inference session and applies nothing
to the host.
