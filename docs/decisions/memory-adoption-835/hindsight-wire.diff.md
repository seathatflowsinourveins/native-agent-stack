# Hindsight WIRE: CC application packet

Recorded 2026-10-09. `applied=false`; `status=OUTSTANDING`. This packet records
an unapplied client-wiring addition for the accepted `trading-research` job.
The existing API service, bank, data, native MCP registrations and 15-tool
allowlist are dependencies preserved by this addition. The CLI and skill
installs, client smokes, fresh-session organic checks and follow-ups below
have **not been executed**. This is a proposed selection, with no KEEP claim.

The source pin is `vectorize-io/hindsight@5fc4ce20917b916240cef27c212c387a177f115b`
(v0.10.2), including its portable vendor skill at
`hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md`.
The CLI release pin is v0.10.2. The unchanged skill uses explicit recall,
retain and reflect; it does not install session-lifecycle hooks [H1,H2].
The native Claude Code plugin has automatic recall/retention hooks [H6].
The selected route is the vendor's manual Skills + existing bank MCP route,
scoped to CC-admitted research consumers. Coding event capture remains in
the ai-memory slot [L1].

## Proposed client delta and its own inverse

| Target | Proposed delta | Wiring inverse |
| --- | --- | --- |
| `$HOME/.local/opt/hindsight-cli/0.10.2/bin/hindsight` | Install v0.10.2 through the pinned vendor installer using its supported version/install-directory variables [H3,H4]. No existing binary is overwritten. | Remove this binary only if the application ledger proves it was newly created by this transaction; remove the now-empty `bin`/version directories. |
| `$HOME/.claude/skills/hindsight-memory/SKILL.md` | Place the unchanged pinned vendor skill in Claude Code's manual user skill root, after CC restricts eligibility to the named research roles [H1,H2,H8]. | Remove only the added byte-matching skill file and its now-empty directory. If a preexisting path exists, restore its exact preimage instead of deleting it. |
| `$HOME/.agents/skills/hindsight-memory/SKILL.md` | Place the same unchanged skill in Codex's documented user skill root [C1]. | Apply the same transaction-specific preimage restoration. |
| Existing `hindsight` MCP entries in both clients | Reuse `http://127.0.0.1:8888/mcp/trading-research/`, which selects the bank through the URL [H5,L1]. | No registration mutation is part of this delta. Retain the existing entries. |

The user roots above are exact, reviewable targets. Their installation would
make the skill discoverable beyond a single project; root discovery alone
does not establish role isolation. **CC mapping of those roots to admitted
research-role launches is OUTSTANDING and blocks applying the addition.**
If the host's supported launch policy cannot isolate those user roots, CC
selects the supported project alternative:
`<CC-research-project>/.claude/skills/hindsight-memory/SKILL.md` and
`<CC-research-project>/.agents/skills/hindsight-memory/SKILL.md` [C1,H8].
The research-project root is unverified and its selection is OUTSTANDING.
No particular blueprint directory is inferred.

## Numbered application and evidence steps

Every row has `applied=false`, `executed=false`, `status=OUTSTANDING`.
The stable step ids, rather than the number of shell lines, define the ten
outstanding steps in this packet.

1. **HW-01 — CC scope and transaction review: OUTSTANDING.** Bind the owner
   lane `memory-h2h` and each admitted named research consumer to its complete
   registry-history role row. `wsl-architecture-design` is a named Claude
   consumer in the pinned record, with research-route eligibility still
   OUTSTANDING. CC chooses isolated user roots or an explicit research project,
   reviews this diff, and records application targets/preimages. A native
   launch requires measured Windows available memory of at least 12 GiB.
   Existing matching skill/binary paths are preserved; the additions below
   require absent destinations. Preimage backups cover touched skill files,
   not credential-bearing client configuration or environment files.

2. **HW-02 — pinned CLI install and version: OUTSTANDING.** The following is
   ready for CC application after HW-01. `get-cli` supports
   `HINDSIGHT_CLI_VERSION` and `HINDSIGHT_INSTALL_DIR` [H3]. The version variable
   belongs on the installer process, so it reaches `bash` rather than only a
   downloader in a pipeline. Its release download resolves to
   `releases/download/v0.10.2/hindsight-<vendor-detected-platform>`.

   ```bash
   memory835_stage=$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/hindsight-wire-835-review
   memory835_cli_root=$HOME/.local/opt/hindsight-cli/0.10.2
   test ! -e "$memory835_cli_root/bin/hindsight"
   mkdir -p "$memory835_stage"
   curl -fsSL https://raw.githubusercontent.com/vectorize-io/hindsight/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/static/get-cli -o "$memory835_stage/get-cli"
   printf '%s  %s\n' ed7489a0287d51e1a3bb045b506c806118131b401c8e229e4ae2e714efa9ee4a "$memory835_stage/get-cli" | sha256sum --check --status
   HINDSIGHT_CLI_VERSION=0.10.2 HINDSIGHT_INSTALL_DIR="$memory835_cli_root/bin" bash "$memory835_stage/get-cli"
   "$memory835_cli_root/bin/hindsight" --version
   ```

   Expected version is 0.10.2. This research verified installer source bytes
   and version selection, not a downloaded release binary or host installation.
   The dedicated path avoids changing a shell profile or replacing an existing
   CLI. CC records the created binary's hash in the application ledger.

3. **HW-03 — Claude manual skill route: OUTSTANDING.** Reuse the existing
   bank-specific HTTP registration [L1]. Fetch the vendor skill unchanged,
   verify its byte hash, then install only the CC-reviewed destination. This
   exact user-root form remains gated by HW-01:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/vectorize-io/hindsight/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md -o "$memory835_stage/hindsight-memory.SKILL.md"
   printf '%s  %s\n' 736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e "$memory835_stage/hindsight-memory.SKILL.md" | sha256sum --check --status
   test ! -e $HOME/.claude/skills/hindsight-memory
   mkdir -p $HOME/.claude/skills/hindsight-memory
   install -m 0644 "$memory835_stage/hindsight-memory.SKILL.md" $HOME/.claude/skills/hindsight-memory/SKILL.md
   ```

4. **HW-04 — Codex manual skill route: OUTSTANDING.** Codex's exact user
   root is `$HOME/.agents/skills`; the supported project root is
   `<CC-research-project>/.agents/skills` [C1]. Reuse the accepted bank-specific
   native registration [L1]. For CC-admitted isolated user-root launches:

   ```bash
   test ! -e $HOME/.agents/skills/hindsight-memory
   mkdir -p $HOME/.agents/skills/hindsight-memory
   install -m 0644 "$memory835_stage/hindsight-memory.SKILL.md" $HOME/.agents/skills/hindsight-memory/SKILL.md
   ```

   The portable plugin's `mcp.json` hardcodes the Cloud URL. Merely setting
   `HINDSIGHT_MCP_URL` cannot redirect that manifest. The documented self-hosted
   replacement and bank URL semantics support the accepted local registration
   [H1,H5]. Neither portable Cloud auth nor an invented configuration field is
   required by this selected manual route.

5. **HW-05 — client-wiring inverse review: OUTSTANDING.** Before application,
   attach the concrete preimage/created-path ledger. On rollback, compare each
   created file to its recorded application hash. Remove only unchanged new
   files; restore exact preimages for replacements, and escalate intervening
   modifications to CC. For the absent-path application above, the skill inverse
   is `rm -- <recorded-added-SKILL.md>` followed by `rmdir -- <recorded-added-skill-directory>`;
   the CLI inverse is `rm -- <recorded-added-binary>` followed by `rmdir` for
   recorded-created empty directories. Paths come from the ledger, including a
   project alternative if selected. This unwires the addition while preserving
   existing service/bank/data/registrations/allowlist. The service-retirement
   inverse in the recipe is a different operation and is not applied here [L1].

6. **HW-06 — Claude vendor-tool smoke: OUTSTANDING.** In one new eligible
   Claude Code research session, invoke the vendor single-bank `get_bank`
   through the configured `hindsight` connection, and verify the selected bank
   is `trading-research` [H5,L1]. Record native MCP success, client/session,
   complete owning-lane role binding and timestamp. A ready launch form, run
   from the CC-selected research scope, is:

   ```bash
   claude --print --output-format json 'Perform a connection smoke with the configured hindsight get_bank tool. Report whether it selects trading-research. Do not retain, change, or delete anything.'
   ```

   Installed `claude --help` confirms `--print` and `--output-format`.
   This provider-backed session was not launched. Its result is a smoke, not
   organic adoption evidence.

7. **HW-07 — Codex vendor-tool smoke: OUTSTANDING.** Run the same single-bank
   vendor `get_bank` smoke in one new eligible native Codex session:

   ```bash
   codex exec --json 'Perform a connection smoke with the configured hindsight get_bank tool. Report whether it selects trading-research. Do not retain, change, or delete anything.'
   ```

   Installed `codex exec --help` confirms this launch form. Record the same
   evidence fields as HW-06. Neither launch uses a resumed/forked session or
   changes the bank. Hindsight's upstream full `hindsight-cli/smoke-test.sh`
   creates/writes/deletes a separate temporary bank and performs model work;
   it has not been executed [H7]. The per-client smoke above exercises the
   vendor MCP `get_bank` surface without adding test memories.

8. **HW-08 — Claude organic fresh-session retain AND recall: OUTSTANDING.**
   After application, an ordinary admitted research task must produce a real
   hypothesis/experiment record and retain it through the loaded vendor route.
   Record the original source hash, experiment tags, stored world/experience
   record and native retain completion. A different fresh Claude session must
   recover that experiment to complete a real follow-up task, without naming
   memory tools or supplying the record in the prompt. Native evidence must
   establish a useful result, original source byte equality, the same complete
   role-row binding, `types=[world,experience]` and `tags_match=all_strict` [L1,H5].
   Use vendor `sync_retain` when an organic workflow needs immediate visibility;
   it waits for storage before the receiver recalls [H5]. Any explicitly
   requested probe remains a probe. Zero execution is recorded here.

9. **HW-09 — Codex organic fresh-session retain AND recall: OUTSTANDING.**
   Apply HW-08 independently to an ordinary admitted Codex research task and
   a different fresh Codex receiver session. Also bind the cross-client
   Claude-to-Codex and Codex-to-Claude handoffs when those are real follow-up
   work. Preserve each source/receiver hash, tags, role row, useful task outcome
   and latency. Prior accepted native round-trip receipts remain historical
   exercised integration; they do not establish these new organic sessions [L1].

10. **HW-10 — +24 h per-role follow-up: OUTSTANDING.** Start the window from
    the recorded application/fresh-session evidence time, not this proposal's
    timestamp. Re-read organic useful outcomes separately from setup/smoke
    calls for every owning-lane and named-consumer row in the adoption record.
    Hindsight's owner is `memory-h2h`; the currently named Claude consumer is
    `wsl-architecture-design`, whose admitted research scope must first be
    resolved by CC. Cover both eligible native clients and every additional
    CC-admitted research consumer with its complete registry-history row.
    The other tool owners (`codex-token-parity` and `overlap-token`) and each
    named consumer require their own stage-4 follow-ups in the live-host
    record; Hindsight exposure to them is not inferred. Pin/hash the follow-up
    producer snapshot and registry mapping, report every unobserved role
    explicitly, and promote KEEP only where stage 3 or 4 has organic evidence.

## Shipped vendor smoke harness for HW-06 and HW-07

The pinned vendor harness is also recorded as **OUTSTANDING** for one invocation
from each eligible client session, in addition to the bank-specific native MCP
connection check. This supplies the shipped upstream smoke command without
claiming it has run:

```bash
curl -fsSL https://raw.githubusercontent.com/vectorize-io/hindsight/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-cli/smoke-test.sh -o "$memory835_stage/hindsight-cli-smoke-test.sh"
printf '%s  %s\n' c57a3506017164997bd45b88bf9d87cfeec69b511fcf90bd50c8f20278593848 "$memory835_stage/hindsight-cli-smoke-test.sh" | sha256sum --check --status
HINDSIGHT_API_URL=http://127.0.0.1:8888 HINDSIGHT_CLI="$memory835_cli_root/bin/hindsight" bash "$memory835_stage/hindsight-cli-smoke-test.sh"
```

H7 owns its separately named `cli-smoke-test-<timestamp>` bank, performs
retain/recall/reflect and management operations, and cleans up that scratch
bank. CC reviews that mutation/provider-work scope before invoking it. It
must not be retargeted to the retained `trading-research` bank. Record separate
Claude/Codex invocation results; both are vendor smokes, never organic evidence.

## Primary-source bindings and verification limits

| Id | Source | Retrieved byte SHA-256 |
| --- | --- | --- |
| H1 | `vectorize-io/hindsight@5fc4ce20917b916240cef27c212c387a177f115b:hindsight-integrations/agent-plugin/README.md`, especially Skills + MCP, self-hosting and lifecycle boundaries | `9be844948ece7b09fa192e5e6e770b73d94fe10142f10bc85759a4e6af84211b` |
| H2 | Same pin, `hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md` | `736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e` |
| H3 | Same pin, `hindsight-docs/static/get-cli`, supported install directory at line 9 and version selection at lines 174-179 | `ed7489a0287d51e1a3bb045b506c806118131b401c8e229e4ae2e714efa9ee4a` |
| H4 | Same pin, `hindsight-docs/docs/sdks/cli.mdx`, vendor installer command at lines 12-16 | `8cabf147cf2027f80197df1de1ab81863518d8bec855395d20c610e4f3a7a888` |
| H5 | Same pin, `hindsight-docs/docs/developer/mcp-server.md`, per-bank URL, get_bank, sync_retain and recall parameters | `73d9513ad29acbd40fc02f95fe1a84cadb4b9958b6e82a4b8fb77df515716f11` |
| H6 | Same pin, `hindsight-integrations/claude-code/README.md`, native plugin install, roots and automatic hooks | `c56dfca50d045cf513faffcaeae6858ced8cf6dc78ed68140cf9c1171bc2e0d7` |
| H7 | Same pin, `hindsight-cli/smoke-test.sh` | `c57a3506017164997bd45b88bf9d87cfeec69b511fcf90bd50c8f20278593848` |
| H8 | Official Claude Code skill-root documentation, fetched 2026-10-09: <https://code.claude.com/docs/en/skills>, manual personal/project skill locations | Live documentation, not a version-pinned artifact |
| C1 | Official OpenAI Codex skill-root documentation, fetched 2026-10-09: <https://developers.openai.com/codex/skills> | Live documentation, not a version-pinned artifact |
| L1 | `recipes/hindsight-research-memory.md` and its linked accepted sanitized receipts; `manifests/landscape.json#/research_memory_jobs/0` | Existing pinned repository evidence, reused rather than rerun |

Installed client help establishes supported launch/registration options.
The official documentation search tool was unavailable; C1 was fetched
directly through the installed context-mode fetch tool. C1 documents current
skill discovery; a version-pinned Codex loader-source verification remains
unexecuted. No credentials or environment-file values were read. Source
verification does not establish host application, useful recall quality,
role-bound PSS, strategy results, stage-3 organic use or stage-4 follow-up.
