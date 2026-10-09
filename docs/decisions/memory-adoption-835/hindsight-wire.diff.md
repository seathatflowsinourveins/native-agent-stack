# Hindsight WIRE: research-project CC application packet

Recorded 2026-10-09. applied=false; deployment_status=OUTSTANDING.
CC selected the unchanged vendor skill in two admitted research scopes:
us-equities-trading's project roots, and native-agent-stack's nested
blueprints/us-equities roots. CLI installation, skill landing/deployment,
client smokes, organic fresh-session checks and +24 h follow-ups remain
unexecuted. Existing API service, trading-research bank/data, native
bank-specific MCP registrations and the 15-tool allowlist are preserved.
This remains a proposed WIRE with no accepted KEEP claim.

The skill source is vectorize-io/hindsight@5fc4ce20917b916240cef27c212c387a177f115b
(v0.10.2), hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md,
SHA-256 736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e.
The selected manual Skills + existing MCP route adds no automatic lifecycle
hooks [H1,H2,H6]. Coding event capture retains the ai-memory slot [L1].

## Selected project delta and its own inverse

| Target | Reviewed addition | Wiring-specific inverse |
| --- | --- | --- |
| $HOME/.local/opt/hindsight-cli/0.10.2/bin/hindsight | CC installs the pinned release; verify its official asset digest before first execution [H3,H4,H9]. No PATH/profile change. | Remove only the unchanged transaction-created binary and empty created prefix directories recorded in the CC ledger. |
| us-equities-trading:.claude/skills/hindsight-memory/SKILL.md | Unchanged vendor skill in the research repository's Claude project root, through draft PR #15 [H2,H8]. | Revert the reviewed two-file addition through a repository PR. |
| us-equities-trading:.agents/skills/hindsight-memory/SKILL.md | Identical vendor skill in the research repository's Codex project root, through the same draft PR [H2,C1]. | The same repository revert PR reverses this addition. |
| native-agent-stack:blueprints/us-equities/.claude/skills/hindsight-memory/SKILL.md | Same unchanged skill in the CC-selected nested Claude research root, through #835's next head [H2,H8,L2]. | A reviewed native repository revert PR reverses only the two nested skill additions. |
| native-agent-stack:blueprints/us-equities/.agents/skills/hindsight-memory/SKILL.md | Same unchanged skill in the CC-selected nested Codex research root, through #835's next head [H2,C1,L2]. | The same native repository revert PR reverses this addition. |
| Existing hindsight MCP entries in both clients | Reuse http://127.0.0.1:8888/mcp/trading-research/; bank selection is implicit in the URL [H5,L1]. | Preserve those entries, the API service, bank/data and allowlist. |

User-wide and native repository-root skill targets are not selected. No skill
installation command targets them. Native sessions for the nested route start
at $HOME/code/native-agent-stack/blueprints/us-equities or below it. Trading
sessions start at $HOME/code/us-equities-trading.

Research skill draft PR: <https://github.com/seathatflowsinourveins/us-equities-trading/pull/15>
at head 650df14547daf7ac4e86d1f85f167787d94b4f24,
base a8a4e880ad5a4a69bb3ede3b856d0677055b08b8,
branch foundation/ns2604-hindsight-skill-20261009.
It carries exactly the two unchanged project SKILL.md files. Publication is
recorded separately from review/merge/runtime loading. Its reviewed landing
commit remains OUTSTANDING. The native nested additions' #835 fix head and
reviewed landing likewise remain OUTSTANDING in this packet.

## Numbered application and evidence steps

HW-01 through HW-10 remain stable record ids. Every deployment/execution below
has applied=false and execution_status=OUTSTANDING. Completed scope/source
reviews and published PR evidence are distinguished from execution.
Every Bash block begins with its own strict error/undefined-variable/pipeline
guards and defines its task variables locally. Checksum, download and absent-
destination failure terminates before dependent installer or binary execution.

1. **HW-01 — selected research scope and deployment review: OUTSTANDING.**
   scope_decision=COMPLETED: CC selected the research project's two roots and
   the two native nested blueprint roots after primary-source discovery review
   [C1,H8,L2]. trading_draft_publication=COMPLETED at PR #15/head above.
   deployment_review=OUTSTANDING: bind reviewed landings and complete
   registry-history role rows for memory-h2h and every admitted named research
   consumer. The pinned named Claude consumer is wsl-architecture-design;
   admission/session binding remains OUTSTANDING. CC starts fresh sessions in
   the admitted research cwd after skill landing and a fresh measured Windows
   available-memory gate of at least 12 GiB.

2. **HW-02 — pinned CLI install and verification before first run: OUTSTANDING.**
   installer_source_review=COMPLETED; release_digest_review=COMPLETED.
   The pinned installer supports HINDSIGHT_CLI_VERSION and HINDSIGHT_INSTALL_DIR
   [H3]. The official release metadata matches the Linux amd64 asset digest
   below [H9]. CC runs this fail-fast sequence, using the approved dedicated
   prefix without changing PATH or a shell profile:

   ~~~bash
   set -euo pipefail
   memory835_stage="$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/memory-roles-835-fix2-20261009/cli-review"
   memory835_cli_root="$HOME/.local/opt/hindsight-cli/0.10.2"
   test ! -e "$memory835_cli_root/bin/hindsight"
   mkdir -p "$memory835_stage"
   curl -fsSL https://raw.githubusercontent.com/vectorize-io/hindsight/5fc4ce20917b916240cef27c212c387a177f115b/hindsight-docs/static/get-cli -o "$memory835_stage/get-cli"
   printf '%s  %s\n' ed7489a0287d51e1a3bb045b506c806118131b401c8e229e4ae2e714efa9ee4a "$memory835_stage/get-cli" | sha256sum --check --status
   HINDSIGHT_CLI_VERSION=0.10.2 HINDSIGHT_INSTALL_DIR="$memory835_cli_root/bin" bash "$memory835_stage/get-cli"
   printf '%s  %s\n' be87c63714ff046ac8ed668465ca0c875f94e6ff0a89ed83da7eb387313197af "$memory835_cli_root/bin/hindsight" | sha256sum --check --status
   "$memory835_cli_root/bin/hindsight" --version
   ~~~

   **The installed binary hash check precedes its first execution.** The pinned
   installer tail installs and prints instructions without running the binary
   [H3]. A mismatch stops before --version and is reported to CC. Expected
   version is 0.10.2. This lane read release metadata only, downloaded no binary
   and ran no installer. CC records its installed digest and created paths.

3. **HW-03 — Claude project-skill review and landing: OUTSTANDING.**
   vendor_skill_source_review=COMPLETED. Both the research PR and #835 nested
   additions use the unchanged H2 bytes. CC verifies the appropriate reviewed
   checkout's file before its Claude smoke:

   ~~~bash
   set -euo pipefail
   memory835_research_root="$HOME/code/us-equities-trading"
   cd "$memory835_research_root"
   printf '%s  %s\n' 736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e .claude/skills/hindsight-memory/SKILL.md | sha256sum --check --status
   ~~~

   The admitted native nested route uses the same verification from
   $HOME/code/native-agent-stack/blueprints/us-equities. Project byte presence
   does not establish discovery; the native smoke records the loaded skill.

4. **HW-04 — Codex project-skill review and landing: OUTSTANDING.**
   project_discovery_review=COMPLETED at the source boundaries below [C1,L2].
   CC verifies the appropriate reviewed checkout before its Codex smoke:

   ~~~bash
   set -euo pipefail
   memory835_research_root="$HOME/code/us-equities-trading"
   cd "$memory835_research_root"
   printf '%s  %s\n' 736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e .agents/skills/hindsight-memory/SKILL.md | sha256sum --check --status
   ~~~

   The native nested verification starts from
   $HOME/code/native-agent-stack/blueprints/us-equities. The portable plugin
   manifest hardcodes Cloud, so HINDSIGHT_MCP_URL alone cannot redirect it.
   Selected project skills reuse the existing bank-specific local MCP entry;
   no Cloud manifest, invented field or automatic capture is added [H1,H5,L1].

5. **HW-05 — repository/CLI wiring inverse: OUTSTANDING.**
   inverse_definition=COMPLETED; rollback execution requires separate CC
   direction. The skill inverse is a reviewed revert PR for the exact added
   files: two project files in us-equities-trading, and two nested files in
   native-agent-stack. Bind each reviewed landing commit and restrict the
   resulting revert diff to those additions. Host skill-directory deletion
   is not an inverse for repository deployment. The CLI inverse compares its
   binary with the applied digest, removes only that unchanged transaction-
   created binary, then removes ledger-recorded empty bin/version directories.
   Preexisting files and intervening changes are preserved/referred to CC.
   The active API service, bank/data, native registrations and allowlist remain
   unchanged. The recipe's service-retirement inverse is a separate action [L1].

6. **HW-06 — Claude vendor get_bank smoke from research cwd: OUTSTANDING.**
   After reviewed skill landing and the launch gate, CC starts one fresh
   native Claude research session. For the research repository:

   ~~~bash
   set -euo pipefail
   memory835_research_root="$HOME/code/us-equities-trading"
   cd "$memory835_research_root"
   claude --print --allowedTools mcp__hindsight__get_bank --output-format json 'Perform a connection smoke with the configured hindsight get_bank tool. Report whether it selects trading-research. Do not retain, change, or delete anything.'
   ~~~

   For the CC-admitted native nested research scope, the same fresh-session
   command starts with cd "$HOME/code/native-agent-stack/blueprints/us-equities".
   Record loaded project-skill evidence, vendor get_bank success, selected bank,
   client/session, admitted role row and timestamp [H5]. Installed help supports
   the command. No session was launched; explicit smoke is not organic evidence.

7. **HW-07 — Codex vendor get_bank smoke from research cwd: OUTSTANDING.**
   CC starts a separate fresh Codex session after the same landing/gate:

   ~~~bash
   set -euo pipefail
   memory835_research_root="$HOME/code/us-equities-trading"
   cd "$memory835_research_root"
   codex exec --json 'Perform a connection smoke with the configured hindsight get_bank tool. Report whether it selects trading-research. Do not retain, change, or delete anything.'
   ~~~

   The admitted native nested scope uses the same command after
   cd "$HOME/code/native-agent-stack/blueprints/us-equities".
   Record the HW-06 evidence fields, including native skill discovery.
   Neither smoke is executed. These read-only vendor get_bank checks are the
   CC-selected rule-A client smokes; the scratch-bank harness is deferred.

8. **HW-08 — Claude organic fresh-session retain AND recall: OUTSTANDING.**
   An ordinary admitted research task produces and retains a real hypothesis/
   experiment record through the vendor skill. Record original source hash,
   experiment tags, world/experience record and retain completion. A different
   fresh Claude research session recovers it for real follow-up work, without
   tool names or the stored answer in its prompt. Evidence establishes useful
   outcome, original-source byte equality, complete role/session/time binding,
   types=[world,experience] and tags_match=all_strict [H5,L1]. Vendor sync_retain
   waits for visibility when an organic workflow needs immediate read-after-
   write. Explicit probes remain probes; zero execution is recorded here.

9. **HW-09 — Codex organic fresh-session retain AND recall: OUTSTANDING.**
   Apply HW-08 independently to an ordinary admitted Codex task and different
   fresh receiver in the selected research scope. Bind real cross-client
   handoffs when they occur. Preserve source/receiver hashes, tags, full role
   row, outcome and latency. Prior accepted round trips remain historical
   integration evidence; they do not establish these new organic sessions [L1].

10. **HW-10 — +24 h per-role follow-up: OUTSTANDING.** Anchor T0 to actual
    reviewed deployment/fresh-session evidence, not this proposal's timestamp.
    Follow every admitted research owning/consumer row through T0+24 h:
    memory-h2h, wsl-architecture-design once admitted, both eligible clients
    and any additional admitted consumers in either selected research scope.
    Pin/hash producer snapshots and full registry mappings. Separate setup/
    smoke calls from organic useful outcomes and report each unobserved role.
    Other tools' owners/consumers retain their own stage-4 follow-ups;
    Hindsight admission is not inferred. KEEP requires returned organic-result
    provenance from stage 3 or 4.

## Deferred vendor scratch-bank harness

hindsight-cli/smoke-test.sh at H7 is **DEFERRED**, executed=false.
It creates/writes/reflects on/deletes a separate temporary bank and performs
provider/model work. CC selected read-only get_bank as the sufficient
per-client rule-A smoke. The scratch-bank harness is neither a required
application command nor a hook here. It remains unexecuted and must never be
retargeted to retained trading-research data [H7,L1].

## Primary-source bindings and limits

| Id | Source | Retrieved byte SHA-256 |
| --- | --- | --- |
| H1 | vectorize-io/hindsight@5fc4ce20917b916240cef27c212c387a177f115b:hindsight-integrations/agent-plugin/README.md | 9be844948ece7b09fa192e5e6e770b73d94fe10142f10bc85759a4e6af84211b |
| H2 | Same pin, hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md | 736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e |
| H3 | Same pin, hindsight-docs/static/get-cli, version/install variables and nonexecuting installer tail | ed7489a0287d51e1a3bb045b506c806118131b401c8e229e4ae2e714efa9ee4a |
| H4 | Same pin, hindsight-docs/docs/sdks/cli.mdx | 8cabf147cf2027f80197df1de1ab81863518d8bec855395d20c610e4f3a7a888 |
| H5 | Same pin, hindsight-docs/docs/developer/mcp-server.md | 73d9513ad29acbd40fc02f95fe1a84cadb4b9958b6e82a4b8fb77df515716f11 |
| H6 | Same pin, hindsight-integrations/claude-code/README.md, unselected automatic hooks | c56dfca50d045cf513faffcaeae6858ced8cf6dc78ed68140cf9c1171bc2e0d7 |
| H7 | Same pin, hindsight-cli/smoke-test.sh, deferred scratch-bank/provider harness | c57a3506017164997bd45b88bf9d87cfeec69b511fcf90bd50c8f20278593848 |
| H8 | Official Claude Code project/nested skill discovery, fetched 2026-10-09: https://code.claude.com/docs/en/skills | Live official docs |
| C1 | Official OpenAI Codex project-skill discovery, fetched 2026-10-09: https://developers.openai.com/codex/skills | Live official docs |
| H9 | Official https://api.github.com/repos/vectorize-io/hindsight/releases/tags/v0.10.2 retrieved 2026-10-09T04:01:10Z; hindsight-linux-amd64 asset id 597888410, size 4170928, digest sha256:be87c63714ff046ac8ed668465ca0c875f94e6ff0a89ed83da7eb387313197af | 8ce08cd4cc97254733c4c0a61631b2bb6332594eb01f3ba12f3947c7e52bf5b7 |
| L1 | recipes/hindsight-research-memory.md, linked sanitized accepted receipts and manifests/landscape.json#/research_memory_jobs/0 | Existing pinned evidence reused |
| L2 | CC's 2026-10-09T04:00:02Z nested-scope decision cites anthropics/claude-code@v2.1.295:CHANGELOG.md lines 7339/4303 and skills docs; openai/codex@rust-v0.161.0:host_roots.rs lines 138-185 | Primary-source handoff reviewed by CC/L1; not independently reread by this worker |

The source handoff establishes the intended discovery boundary: Claude loads
nested skills for sessions started at/below the directory and can discover
them lazily while working on its files; the cited Codex version loads from
repository root down to the session cwd [L2]. The actual native fresh-session
loading checks remain OUTSTANDING. H9's target_commitish=main does not alone
bind a binary build to the source commit: source pin and release-asset digest
are separate evidence. No credential/config/environment values were read.
This lane downloaded no binary and ran no installer, provider or native client.
Source/PR evidence does not establish landing, runtime use, recall quality,
role-bound PSS, strategy results, organic stage 3 or follow-up stage 4.

The GPT micro read at 04c4bc278 reproduced shell fall-through using harmless
fixtures. Its saved reproduce_wire_guards.py has SHA-256
43e9adfe8f7477af078543bbef62aa9f170594897a07fd9ade9eba8cbdae1da8.
That unchanged baseline reproduced ordinary-shell overwrite/execution and
strict-shell termination. The evidence module reads the actual published
Bash blocks and tests bad download/checksum and preexisting CLI destination
failure paths in temporary fixtures, using the same downloader-substitution
method. It executes no vendor installer, real binary, provider or client.
Repository skill placement has no host install command; reviewed PR deployment
and its revert remain the selected addition/inverse.
