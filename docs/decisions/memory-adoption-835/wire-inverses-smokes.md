# ai-memory and QMD WIRE inverses and smokes

Recorded 2026-10-09. All additions and smokes here have
`applied=false`, `executed=false`, `status=OUTSTANDING`. Existing host evidence
is reused; no installer, uninstall, provider-backed smoke or client launch
was run. The owning lane is `memory-h2h`; the pinned named Claude consumer
`wsl-architecture-design` remains a consumer with eligibility to be bound by
CC. Full registry-history role rows, rather than one hcom name, define follow-up
scope. Neither proposed WIRE is a KEEP with unresolved organic evidence.

## ai-memory v2.6.0 managed routing

Pin: `akitaonrails/ai-memory@89bd8ded3c1ab8b769cf99417d038ed0364403c8`.
The core-owned `ai-memory-routing-install` skill and `docs/install.md`
document markered instruction snippets and managed skill assets. The CLI
supports `install-instructions`, `install-skills` and concern-limited
`uninstall` [A1,A2]. Its installed help confirms the commands below.

1. **AM-01 — CC-reviewed route application: OUTSTANDING.** Preview from the
   CC-selected project with the exact installed 2.6.0 CLI before application:

   ```bash
   ai-memory install-instructions --target CLAUDE.md --compact --skills-agent claude-code --print
   ai-memory install-instructions --target AGENTS.md --compact --skills-agent agents --print
   ai-memory install-skills --scope project --agent both --print
   ```

   These are proposed preview commands; none was executed here. Preserve
   instruction and skill preimages, review the native generated diff, then
   CC can run the matching application commands:

   ```bash
   ai-memory install-instructions --target CLAUDE.md --compact --skills-agent claude-code
   ai-memory install-instructions --target AGENTS.md --compact --skills-agent agents
   ```

   Installation writes both the compact markered instruction snippet and
   matching core-owned skills; it does not require a separate duplicate
   skill install. The selected project/root is OUTSTANDING. Project Claude
   roots are `.claude/skills`; project Codex/cross-agent roots are
   `.agents/skills` [A1,A2]. Existing native MCP and capture hooks are reused.

2. **AM-02 — transaction-specific inverse: OUTSTANDING.** The supported
   upstream removal commands, first dry-run and then application by CC, are:

   ```bash
   ai-memory uninstall --only skills
   ai-memory uninstall --only instructions
   ai-memory uninstall --only skills --apply
   ai-memory uninstall --only instructions --apply
   ```

   These concern-level inverses are broader than one added file: skills removal
   visits default global/current-project roots and validates the
   `ai-memory-managed: routing-skill` marker; custom roots need manual cleanup
   [A1,A2]. Instruction removal targets ai-memory-owned blocks. CC uses these
   commands only when the reviewed plan matches the intended added artifacts.
   For this incremental addition, exact touched-file preimage restoration is
   the rollback: restore replaced instruction/skill files byte for byte and
   remove only unchanged newly created files recorded in the transaction
   ledger. Existing managed skills are preserved. No broad uninstall,
   `--purge-data`, service change or MCP/hook removal is part of this rollback.

3. **AM-03 — per-client route smoke and organic follow-up: OUTSTANDING.**
   In one new eligible Claude session and one new eligible Codex session,
   explicitly invoke the loaded core-owned retrieval skill and a read-only
   `memory_query` against a CC-selected existing project decision; verify its
   native server result and project binding. The query and expected source
   hash must be recorded before the smoke without placing the answer in the
   prompt. The smoke is a setup event, not organic use. Then collect ordinary
   fresh-session recovery of a real project decision without tool names and
   a +24 h useful-outcome follow-up for `memory-h2h` and every admitted named
   consumer. Bind complete registry-history role rows and snapshot hashes.
   No provider test (`llm-test`), page write, capture backfill or smoke was run.

## QMD v2.8.3 vendor bootstrap route

Pin: `tobi/qmd@facd35e01359e59d938bc9418e93fb9318addee3`.
The CLI's `skill install` writes the vendor bootstrap SKILL.md plus bundled
resources; `--yes` also creates the Claude skill symlink [Q1]. The bootstrap
loads version-matched runtime instructions using `qmd skill show`; clients
without bang-command expansion run that command explicitly. The full payload
is also available through `qmd skills get qmd --full`. The bootstrap and full
runtime skill are separate assets, so they do not share a byte hash [Q1,Q2].

1. **QMD-01 — CC-reviewed route selection/application: OUTSTANDING.** Reconcile
   the existing bootstrap, native `qmd` index and pending `qmdshared` HTTP
   namespace before application. Preserve the named index
   `native-agent-stack-catalog-lex`; do not merge its evidence with the `qmd`
   namespace or add a second default-index server. For a selected project
   missing the vendor skill, the supported manual route is:

   ```bash
   qmd skill install --yes
   ```

   It installs `./.agents/skills/qmd` and, where required, links
   `./.claude/skills/qmd`. The supported user-root alternative is
   `qmd skill install --global --yes`, targeting `$HOME/.agents/skills/qmd`
   and the Claude visibility link [Q1]. Existing same-name installs are
   preserved; `--force` is not proposed. Both alternative selections remain
   OUTSTANDING, and exactly one scope is chosen through CC review. The vendor
   Claude plugin alternative is `claude plugin marketplace add tobi/qmd`
   followed by `claude plugin install qmd@qmd`; its marketplace supplies
   `./skills` and `qmd mcp` [Q3]. The selected manual route reuses existing
   native MCP registrations instead of simultaneously adding the plugin's
   default-index server.

2. **QMD-02 — wiring inverse: OUTSTANDING.** `qmd skill --help` exposes show
   and install, with no skill-uninstall subcommand. Use the CC transaction
   ledger to remove only the new byte-matching `qmd` skill directory/files and
   the new Claude symlink if its target still matches the recorded target;
   restore exact preimages for a reviewed replacement. Preserve every
   preexisting bootstrap/resource, QMD binary, collection, index, shared-service
   definition and MCP registration. If the alternative vendor Claude plugin
   alone was added, installed native Claude help supports
   `claude plugin uninstall qmd@qmd --scope user --keep-data`; remove its newly
   added marketplace only if the ledger proves no other plugin depends on it.
   Existing plugin/marketplace entries are preserved.

3. **QMD-03 — per-client vendor smoke and organic follow-up: OUTSTANDING.**
   In a new eligible Claude session and a new eligible Codex session, load the
   bootstrap and retrieve the bundled runtime skill through the documented
   `qmd skills get qmd --full` route. Perform a read-only vendor index/status
   and lexical search against a CC-selected existing document:

   ```bash
   qmd --index native-agent-stack-catalog-lex status
   qmd --index native-agent-stack-catalog-lex search '<CC-existing-document-query>' --json -n 1
   ```

   CC replaces the query placeholder with a known existing document query and
   pre-records its source locator/hash. Confirm each client's retrieved source
   matches the named index and task. The vendor `status` MCP tool reports index
   health [Q4]; its native connection smoke can establish the registration
   without embedding or reindexing. Explicit skill/status/search probes remain
   setup evidence. Follow with ordinary fresh-session document recovery and
   +24 h useful-outcome evidence separately for every owning-lane and admitted
   named-consumer role row. No index update, embed, trust change, daemon launch,
   provider smoke or organic verification was executed here.

## Primary sources

| Id | Source | Retrieved byte SHA-256 |
| --- | --- | --- |
| A1 | `akitaonrails/ai-memory@89bd8ded3c1ab8b769cf99417d038ed0364403c8:crates/ai-memory-core/src/routing_skills/ai-memory-routing-install/SKILL.md` | `3188484cdb944782badb25e7749d33b7ab336d913a3a72aafb1a9e548b579614` |
| A2 | Same pin, `docs/install.md`, routing/assets and removal scope, especially lines 2358-2360 and 2370-2434 | `fb9cd6ae5ab863a220d2cde976eb1ec514d470232bdea261c3f74899b963b803` |
| Q1 | `tobi/qmd@facd35e01359e59d938bc9418e93fb9318addee3:src/cli/qmd.ts`, bootstrap/install at lines 3339-3382 and 3549-3563, skill command help | `ada93b4f9757bb7846c0d7accbe40bed4e62daf0720a7d1fb64fa763abd5e0ea` |
| Q2 | Same pin, `skills/qmd/SKILL.md` | Runtime payload, separate from vendor-generated bootstrap hash recorded in live-host JSON |
| Q3 | Same pin, `.claude-plugin/marketplace.json` and `README.md` Claude plugin section | Repository/commit/file binding; plugin route unexecuted |
| Q4 | Same pin, `skills/qmd/references/mcp-setup.md`, vendor status and MCP tools | `457814981a35f713021dffe3c4950b960e31b0a54327229a0293f9d979a5c430` |

Installed `ai-memory install-instructions --help`, `install-skills --help`,
`uninstall --help`, `qmd skill install --help` and Claude plugin uninstall
help were read without executing mutations. Source verification supports the
proposed routes and inverse scope; useful organic outcomes, role-bound PSS,
fresh-session evidence and +24 h follow-ups remain OUTSTANDING.
