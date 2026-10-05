# Official upstream releases; never rebuild shipped functionality

Date: 2026-10-05. Status: accepted instruction change for bounded job 072; no runtime selection or installation change.

## User instruction

The user's words at 2026-10-05T04:26:41Z, verbatim:

> not rebuilt,self built ,always using thesota rpeos upstream clean install etc it should reflect within our harness rules across new wsl and ours, including the trading lane, using the sota upstream especially the org repos like https://github.com/alpacahq and other sota repos ,never rebuilt that is already sota ,and always find sota referneces, platfroms, trading engines,rutnimes and beyond as clean install practice or referneces

## Decision and purpose

Carry the user's official-upstream rule into the existing-host, portable, scaffold and new-WSL instructions, including the trading lane. This serves the north-star action of building the research harness for US-equities research, historical simulation and independently qualified broker paper operation using maintained upstream components.

Add this exact sentence after the source-naming sentence in the root top rule, and after the corresponding upstream reuse/source-naming sentence in the client and scaffold surfaces:

> Prefer the maintainer's own organization repositories (the vendor's GitHub org, such as alpacahq for Alpaca) and their clean releases, and never rebuild, fork or wrap what an upstream already ships.

The trading clause names the vendor-owned SDK, optional MCP server, engine and official IBKR API distribution. An upstream adapter is reused when shipped; glue is limited to a demonstrated upstream gap and cites its source at a pin. Release discovery is evidence for the instruction, not an upgrade directive. `catalogs/us-equities/runtime-target.json` and `manifests/evidence.json` remain under their lane/coordinator ownership.

Alternatives considered: retain only the previous cited-reference implementation rule; prefer community forks or local wrappers despite an upstream release providing the capability; adopt the explicit vendor-organization and clean-release rule. Adopt the last alternative because it directly implements the user's instruction and the sources below already provide maintained native products and installation paths. No new runtime, dependency, adapter or runner is needed for this change.

The bounded builder uses the requested GPT Sol at max pin. The installed `writing-for-agents` skill guides instruction placement and lossless pruning; `search-first` was read and its inline workflow used for the existing rules, generators and official sources. This documentation task requires no package installation or new research runner. The scoped ai-memory query (`pin_first=true`, `limit=2`) returned `MCP tool call requires approval, but approval policy is never`; canonical repository files and current primary sources supplied the evidence instead.

## Instruction surfaces and bindings

| Surface | Change and binding |
| --- | --- |
| `AGENTS.md` | Exact sentence immediately after "and name that source (repository, pin, file or paper) for every action."; `StandingRuleSurfacesTests` binds its wording. |
| `examples/claude-native/CLAUDE.md` | Exact sentence in the numbered upstream source procedure; `PortableTopRuleTests` and `StandingRuleSurfacesTests` bind the portable rule. |
| `adoption/templates/codex.AGENTS.template.md` | Exact sentence after upstream reuse, plus only the six budget compressions below; `TemplateTests` binds the block hash, word count and byte budget. |
| `adoption/scaffold/AGENTS.md` | Exact sentence; `ScaffoldContentTests` binds the whole top-rule block byte for byte to the Codex template. |
| `blueprints/us-equities/AGENTS.md` | Short source clause with official repository/distribution links, the upstream-adapter requirement, the pinned-glue limit and a pointer to this verification. |
| `adoption/new-wsl/claude-user-instructions.md` and `adoption/new-wsl/codex-user-instructions.md` | Regenerated with `python3 tools/adoption/new_wsl_client_config.py --write-blocks`; its `--check` verifies the manifest-filtered source instructions. |
| `docs/decisions/2026-10-02-new-wsl-client-configuration.md` | Append the dated current dropped-unit projection printed by `--check --markdown`; `RecordTests` also binds this surface to the generator output. Earlier snapshots retain their original counts. |
| `docs/new-wsl-handbook.md` and `docs/new-wsl-handbook.json` | Regenerated with `python3 scripts/build_new_wsl_handbook.py --write`; the builder's source metadata determines whether their bytes change. |

The existing test bindings are updated for the exact added sentence and the new Codex block hash/count. No test budget is relaxed. `adoption/scaffold/CLAUDE.md` already imports `AGENTS.md`, and `adoption/bootstrap.md` points to the scaffold rather than repeating the rule; neither needs another copy.

## Codex byte budget and every compression

At base `4c897418fe35a030a1188ae447eaf31c893f8eff`, the Codex template is 8,187 bytes. The exact sentence and its newline add 199 bytes. Six wording-only compressions save 196 bytes, yielding **8,190 bytes**. This meets the requested 8,192-byte ceiling and the existing test's stricter `< 8192` assertion. The staged block including session lanes moves from 827 to 822 whitespace-separated words; its SHA-256 is `819e63e9e6c2e90eca91a788f4f0b33c382271ebff9d7a99f6cc45b6d45bb54f`.

All compressions are after `<!-- native-agent-stack:session-lanes -->`, outside the top-rule block shared with the scaffold. The complete RTK upstream text and exceptions block stay byte-identical to the base. This also keeps this job away from the RTK exceptions edits in open [PR #709](https://github.com/seathatflowsinourveins/native-agent-stack/pull/709), whose template and test changes still need normal coordinator reconciliation at integration.

| Compression | Before → after | Bytes saved; preserved meaning |
| --- | --- | --- |
| Large output | "Run large command output through …, passing `cwd` as your working directory …" → "Run large command output via …; set `cwd` to your working directory …" | 8; both context-mode entry points and the writer's owned-worktree requirement remain. |
| Semble | "Where the `semble` MCP server is connected, use its `search` tool for conceptual or natural-language code questions, with the absolute repository path and no `content` argument (a per-call `content` overrides the code default); `find_related` returns only embedding-similar chunks, so callers, implementations and references come from Serena." → "If `semble` MCP is connected, use `search` for conceptual/natural-language code queries with the absolute repo path; omit `content`, which overrides the code default per call. `find_related` gives embedding-similar chunks only; get callers, implementations and references from Serena." | 58; connection condition, query modality, absolute path, content override, similarity limitation and Serena reference ownership remain. |
| Long commands | "Run a long command with `yield_time_ms` 30000; while a `session_id` comes back, poll it with `write_stdin` (empty `chars`) until the process exits, then read the output." → "Long commands: set `yield_time_ms` 30000; while a `session_id` returns, poll `write_stdin` (empty `chars`) until exit, then read output." | 33; timing, empty-input polling and reading only after exit remain. |
| GPT Researcher | "Web research: where the stack installs GPT Researcher, run … as a long command (it stops after 1,500 s); ask short, unseeded current-month queries and treat the report as leads whose facts you re-read from primary sources." → "Web research: if the stack installs GPT Researcher, run … as a long command (stops at 1,500 s); use short, unseeded current-month queries; reports are leads: re-read facts in primary sources." | 31; the literal command, install condition, time limit, query constraints and primary-source reread remain. |
| Claude courier | "To message a Claude Code session, run as one long command: set `msg` through a quoted heredoc (`msg=$(cat <<'MSG'`, then the text, `MSG` and `)` on lines of their own), then …" → "Message Claude Code in one long command: set `msg` via a quoted heredoc (`msg=$(cat <<'MSG'`, text, `MSG`, `)` each on its own line), then …" | 35; one-command execution, quoted heredoc, separate lines and the entire literal courier pipeline remain. |
| Queued delivery | "Codex receives queued messages between turns, never mid-turn; expect up to about 20 s delay when it is idle." → "Codex receives queued messages only between turns; idle delay is up to ~20 s." | 31; between-turn delivery, exclusion of mid-turn delivery and approximate idle-delay bound remain. |

## Official sources and current releases

Verified on 2026-10-05 with the GitHub API and the official IBKR download page. GitHub repository metadata returned the expected `full_name` and `archived: false` for all three named repositories. These are source and release observations, not native SDK, engine, broker or model execution receipts.

| Source | Current release observation and source pin |
| --- | --- |
| [alpacahq/alpaca-py](https://github.com/alpacahq/alpaca-py) | [v0.44.0](https://github.com/alpacahq/alpaca-py/releases/tag/v0.44.0), published 2026-08-11T10:11:55Z; GitHub `releases/latest` returned non-draft, non-prerelease. Tag commit `cc4cb3b7ba50ae250e621983c2779047fb16bb28`; [pinned README installation](https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/README.md#installation) uses the maintained `alpaca-py` package. |
| [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) | [v2.3.2](https://github.com/alpacahq/alpaca-mcp-server/releases/tag/v2.3.2), published 2026-09-15T14:13:25Z; GitHub `releases/latest` returned non-draft, non-prerelease. Tag commit `9b0c72beda5579de088413ce9c3720456cde8f5f`; [pinned README](https://github.com/alpacahq/alpaca-mcp-server/blob/9b0c72beda5579de088413ce9c3720456cde8f5f/README.md) documents the vendor's MCP server and native setup. Use only where an MCP is needed. |
| [nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | GitHub `releases/latest` returned stable [v1.231.0](https://github.com/nautechsystems/nautilus_trader/releases/tag/v1.231.0), published 2026-08-02T18:53:49Z. The release list also returned newer [v2.0.0rc6](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc6), published 2026-10-05T03:03:18Z, explicitly a prerelease; its annotated tag resolves to commit `7b766f8825b2539c5b2ac1375e9d97b41c509edb`. [Pinned IBKR integration documentation](https://github.com/nautechsystems/nautilus_trader/blob/7b766f8825b2539c5b2ac1375e9d97b41c509edb/docs/integrations/interactive_brokers.md) says the adapter is included in the Python package. The trading lane's selected [v2.0.0rc5](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc5) stays its selection. |
| [Official IBKR API page](https://www.interactivebrokers.com/en/trading/ib-api.php) and [TWS API distribution](https://interactivebrokers.github.io/) | The distribution page labels Stable as API 1050, released 2026-09-09, and Latest as API 1051, released 2026-09-30. The Mac/Linux clean distribution filenames are [twsapi_macunix.1050.02.zip](https://interactivebrokers.github.io/downloads/twsapi_macunix.1050.02.zip) and [twsapi_macunix.1051.01.zip](https://interactivebrokers.github.io/downloads/twsapi_macunix.1051.01.zip); Windows equivalents are `TWS API Install 1050.02.msi` and `TWS API Install 1051.01.msi`. These download versions are observed sources, not new runtime pins. |

Verification paths: `gh api repos/{repository}`, `gh api repos/{repository}/releases/latest`, `gh api 'repos/nautechsystems/nautilus_trader/releases?per_page=5'`, `gh api repos/{repository}/git/ref/tags/{tag}`, the annotated Nautilus tag object, and original README/integration files at those tags. Official IBKR HTML was fetched directly and its release labels and download links inspected. A guessed pre-2.0 adapter path returned HTTP 404; the tag's Git tree showed the current `python/nautilus_trader/adapters/interactive_brokers/` and `docs/integrations/interactive_brokers.md` paths, which were then read successfully. No absence claim was inferred from the failed path.

## Acceptance and completeness

The prescribed suites exercise local structural bindings, synthetic installation fixtures and local integration behavior. Their totals are not vendor SDK or broker acceptance. Actual returned results follow; full outputs are retained in the task's external TMPDIR. The coordinator owns registry/evidence reconciliation and the commit. The commit message is in `.bounded-job-072/msg-1.txt`.

The first complete suite run returned exit 1: 488 tests in 147.662 s, one failure and 16 skips. `RecordTests.test_the_record_holds_the_tables_the_tool_prints` exposed one more bound surface: the current new-WSL decision projection still counted 65 Codex lines after the new sentence increased the source to 66. Its isolated native unittest reproduced exit 1 (one test, 0.053 s). The repair appends the generator's current 58/58 Claude and 66/66 Codex projection in a new dated addendum rather than rewriting historical projections; the isolated test then returned exit 0 (one test, 0.054 s). The first suite output and focused red/green results remain retained outside the checkout. This direct metadata assertion supplies the diagnosis loop; no new instrumentation, runtime or test runner is needed.

| Command | Exit | Returned result and boundary |
| --- | --- | --- |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | Both instruction carriers written; zero units dropped from either source. |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | `check passed`; the existing MCP Inspector manifest/install-plan warnings remain outside this instruction change. |
| `python3 scripts/build_new_wsl_handbook.py --write` | 0 | Status `written`; both handbook outputs are byte-identical to the base. |
| `python3 tools/adoption/new_wsl_client_config.py --check --markdown` | 0 | Current dropped-unit projection is Claude 58/58 lines and Codex 66/66 lines, zero units dropped; copied into the new dated addendum. |
| `python3 -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_scaffold_repo tests.test_new_wsl_client_config tests.test_new_wsl_handbook tests.test_stack_lifecycle` | 0 | Final run: `Ran 488 tests in 141.976s`; `OK (skipped=16)`. No native provider or broker acceptance is claimed. |
| `python3 scripts/validate.py` | 1 | Expected registry drift only: SHA-256 and byte-count mismatches for nine changed registered files, 18 entries total. The coordinator's `manifests/evidence.json` is untouched. |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 8,190 bytes. |
| `git diff --check` | 0 | No whitespace errors. |

Completeness check: the rule reaches repository, both client templates, scaffold, both manifest-filtered new-WSL instruction carriers and the trading lane. The review includes SDK, MCP, engine/native adapter and API-distribution source classes. Discovery distinguishes stable from prerelease and installation/source evidence from execution. It leaves host credentials, runtime selections and the evidence registry untouched. The next trading landscape sweep should compare rc6 and API 1051 compatibility against its selected pins rather than treating this documentation update as adoption.

## Overturn condition

Revisit a named source when the vendor supersedes it, stops maintaining it or publishes a better native distribution. Replace its citation only after official release/source review and the lane's applicable native compatibility checks establish the successor. Glue must shrink or disappear when upstream ships its capability. A documented, pinned missing capability can justify limited glue; it does not overturn the prohibition on duplicating shipped functionality. Relaxing the user's never-rebuild/fork/wrap rule itself requires a new explicit user instruction, not popularity or a community-wrapper preference.
