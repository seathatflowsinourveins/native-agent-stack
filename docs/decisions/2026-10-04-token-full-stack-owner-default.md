# The token-efficiency stack installs by default on the new WSL: the owner's decision (2026-10-04)

> Note for the command center: session `wsl-architecture-design` may replace the text of this record, but keep its path.
> `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json` hashes this file (`wave3.records.decision_record`)
> and the manifest's assembler checks that it quotes the owner's words and names every slot the batch changes, so a new
> text needs that sha256 updated and the manifest, its tables and the handbook regenerated.

## Decision

The owner decided on 2026-10-04 that the full token-efficiency stack installs cleanly on the new WSL distribution and is
the default that every future session launches and invokes. The definitive manifest records the decision as a third
batch of the layer-consensus record, `wave3` in `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`,
under amendment 4 of the manifest's decision rule (below):

- ten rows are added, of the new row kind `owner_decision`: `command-output`, `output-compression`, `code-index`,
  `code-graph`, `repo-packing`, `structured-data`, `doc-conversion`, `api-docs`, `trace-viewer` and
  `token-lane-carriers`;
- three rows whose decided default installs nothing get an owner default: `context-supply` (context-mode, whose wave-2
  interim the owner default replaces), `ccusage` and `session-analytics` (agentsview);
- the `code-search` interim installs both arms of its frozen confirmatory, semble and SocratiCode, until that
  confirmatory removes one.

Each row keeps one pin and its own removal check, the one-default-per-slot shape of the 2026-10-01 record. No row is
definitive, a blind result, a consensus or a measurement. The fields an owner default replaces, and the interim it drops,
stay on the row under `overturned`. Net provider savings stay unmeasured (`adoption/manifest.json`, `policy`,
`net_provider_savings`): nothing here claims a saving, and components are kept or pruned later by measured evidence.

The batch owes no family acknowledgement, because its authority is the owner's decision and not a direct consensus. The
two families' reviews of these rows are not on record yet; each row says so (`claude` and `gpt`: not judged).

This record changes repository files only. Nothing is installed on any host by it. The install plan
(`evidence/artifacts/new-wsl-install-plan-20261002`) gains one install and one acceptance function per new or changed row,
which run only on the destination distribution (NativeStack2604) when the plan runs there. The client configuration
(`tools/adoption/new_wsl_client_config.py`, `adoption/new-wsl/client-config-map.json`) wires what the rows install; that
part belongs to session `wsl-architecture-design`.

## The owner's order

The order, verbatim, as the harness relayed it to the command-center session `wsl-architecture-design` on 2026-10-04;
the same first sentence reached session `native-agent-stack-99` directly, and the coordination brief of that session
relays the whole text:

> WE NEED TO ENABLE FULL SOTA STACKS FOR THE TOKEN EFFICIENCY REPOS INSTALL CLEANLY MAKE SURETHEY LIVE SEAMLESSLY AS OUR NATIVE WORKFLWO FOR FUTURE SESSION DEFAULT TO LAUNCH AND INVOKE ,CLENA RESOLUTE AND REPORT THE MAIN SESSION WHEN READY with real new session launched e2e monitor invoke rate and upstream commands e2e with using of the sota related full lifecycle skills, the token save is essential layer make sure we are monitored token use and sota token save repos invoke rate with new session launched e2e m keep resolute untill the upstream are fully resoluted and live within our native workflow including ultracode subagent,experimental agent team in our wsl with upstream commands for showing the real saved and sota resoluted practices upstream clean installed

Earlier in the same turn, to session `native-agent-stack-99`:

> for the sota features form changelogs, make sure we enabled all latest sota ones into our wsl and new wsl and keep maitnaced updated latest sota aligned

The record reads the order this way: the token-efficiency repositories are the core rows of
`docs/token-efficiency-stack.json` with RTK, context-mode and the token-lane carriers, wanted on both NativeStack and
NativeStack2604 and live by default. This record covers NativeStack2604's gates. The workstation's upgrades are the
command center's. "Latest" does not move a pin here: each pin is the one `manifests/stack.json` and
`adoption/pins-linux-x86_64.json` record at `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`. A newer upstream release needs
its own qualification.

## Authority

- The 2026-10-01 record's own overturn clause
  ([`2026-10-01-new-wsl-definitive-defaults.md`](2026-10-01-new-wsl-definitive-defaults.md), section Overturn, lines
  591-592 at `f77a35eb`): "For the rule: the user asks again for arms on the clean install". The owner now asks for the
  token components on the clean install.
- The layer consensus's amendment 3 (`consensus.json` line 400 at `f77a35eb`, `wave2.interim_rule`): "The authority is
  the owner's dated decision, as the record that relays it states it, or a direct consensus with both families'
  acknowledgements on record." This record is the record that relays the owner's decision. Amendment 4 makes the same
  authority hold for a row's default, not only for an interim beside it.

## Amendment 4 of the manifest's decision rule

The rule text, verbatim from `wave3.owner_rule`. The assembler appends it to the manifest's `decision_rule`, after
amendment 3. It is unrelated to the "Amendment 4" of the Gate A E2E plan that the catalog edition of 2026-10-01 names as
not yet written.

> Amendment 4 (wave 3, 2026-10-04): on the owner's dated decision, as the record that relays it states it, a batch may add rows of kind owner_decision and give a row whose decided default installs nothing an owner default. An owner row or an owner default names what it installs and at which pin, the job it owns and the comparison that would remove it; that comparison reports to the owner and removes nothing by itself. The fields an owner default replaces, and an interim it drops, stay recorded on the row under overturned. Neither is definitive, a blind result, a consensus or a measurement, and no other installed row may own its job; its label starts with 'owner decision' and names its authority. The relaying record is hashed in the batch, quotes the owner's words and names every slot the batch changes. The install plan installs it as the row's owner, and the client configuration wires what it installs.

Its exception to the no-install rule, verbatim from `wave3.no_install_rule_exception`:

> Amendment 4 makes a second exception to the no-install rule: an owner row or an owner default installs on the owner's decision before measured evidence shows a gain; net provider savings stay unmeasured, and the decision it replaces stays recorded beside it.

## What it overturns

Line numbers are at `f77a35eb2bf30bc4bf6f3b4ee51bc9ce5397b4c5`.

| Where | What stood | What replaces it |
| --- | --- | --- |
| `evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json:1537-1601` | `context-supply`: "No context-supply layer: the usage meter only", definitive, `installs_nothing_extra` true (:1544), with context-mode 1.0.169 as its wave-2 interim (:1557-1600) | the owner default context-mode 1.0.169; the interim is dropped and kept under `overturned.interim` |
| `definitive-manifest.json:1497-1536` | `ccusage`: resolved as not installed (:1513-1514), covered by the two clients and the collector | the owner default ccusage 20.0.26, a read-only meter |
| `definitive-manifest.json:1961-1994` | `session-analytics`: resolved as not installed, agentsview the named challenger of an unrun measurement | the owner default agentsview 0.43.0, local archive only |
| `docs/decisions/2026-10-01-new-wsl-definitive-defaults.md:79`, `:159`, `:163-171`, `:305-318` | the lean base: no context-supply layer, ccusage the meter, the interim table | the regenerated tables; the prose stays as dated history |
| `evidence/artifacts/new-wsl-layer-consensus-20261002/wave2-records.json:151` | the wave-2 code-search ruling's change 7: "The destination keeps that carrier not_wired" | the `token-lane-carriers` row; its reason (the carrier names tools the destination does not install) no longer holds |
| `catalogs/foundation/new-wsl-architecture-20261001.json:734` | the token-efficiency layer's verdict `comparison_required` | unchanged as a dated edition; its notes point to this record |

The 2026-10-01 record's own summary of the decision round, that "no challenger shows a gain on that metric with an
interval that excludes zero" (lines 305-318), stays true and stays recorded. The owner's decision does not claim the
opposite. It installs the components and leaves the gain to be measured.

## The rows

The pins are those of `manifests/stack.json` and `adoption/pins-linux-x86_64.json` at `f77a35eb`. The install commands
are those of `docs/token-efficiency-stack.json` (`upstream_commands.install`) and `recipes/README.md`, parameterized for
the install plan's ecosystem prefix (`${ECO_ROOT:-$HOME/.local/share/codex-ecosystem}`, the prefix the client templates
name). Release archives go through the plan's checksum-verified download (`fetch_verified`) instead of
`gh release download`, so the plan needs no GitHub sign-in; the digest is the one the release publishes.

### Rows added (`owner_decision`)

| Slot | Layer | Default and pin | Repository | Job |
| --- | --- | --- | --- | --- |
| `command-output` | token-efficiency | RTK 0.50.0, asset `rtk-x86_64-unknown-linux-musl.tar.gz`, sha256 `bc2b8902b0d9c796c82ef45f16ae2307e17757afeca5ee156235a3dc7bda5f89` | https://github.com/rtk-ai/rtk | condensing supported shell command output before it enters an agent's context, with raw recovery |
| `output-compression` | token-efficiency | Headroom 0.37.0, `headroom-ai[mcp]==0.37.0`, MCP server only | https://github.com/headroomlabs-ai/headroom | on-demand compression and exact retrieval of selected content through an MCP server, with no proxy interception |
| `code-index` | token-efficiency | jcodemunch-mcp 1.108.319 (source `8f7b34abe16fb459e0bf1c04747d584216dfe32e`) | https://github.com/jgravelle/jcodemunch-mcp | an explicitly scoped code index with exact symbol retrieval through an MCP surface |
| `code-graph` | token-efficiency | codebase-memory-mcp 0.11.0, asset `codebase-memory-mcp-linux-amd64.tar.gz`, sha256 `032b33c1833919a2d1de67ff6367fa6ea46aee8689c86ef223c88fae3b6e4536` | https://github.com/DeusData/codebase-memory-mcp | a persistent static code graph with call tracing, built only on an explicit index_repository call |
| `repo-packing` | token-efficiency | Repomix 1.18.1, npm tarball sha256 `d4d278310b33f245d4abbc7f757cc3815ff362f6d69225692f837c7dcee83c8f` | https://github.com/yamadashy/repomix | explicit packing of selected repository files into one artifact, with optional structural compression |
| `structured-data` | token-efficiency | TOON 4.1.1 (`@toon-format/cli`), npm tarball sha256 `93ec1d3f44a608332d6f1fa811adda4237983841baec9b165e40252f20d83ca6` | https://github.com/toon-format/toon | compact encoding of uniform flat JSON arrays, kept only when a strict decode is value-equal |
| `doc-conversion` | token-efficiency | MarkItDown 0.1.8, sdist sha256 `17188ad827ea79fc264c7b1ca8cf5a242a16278d84cc32f2edc475dbe92812ed` | https://github.com/microsoft/markitdown | conversion of HTML and other supported source documents to Markdown for agent context |
| `api-docs` | token-efficiency | Context Hub 0.1.4 (`@aisuite/chub`), npm tarball sha256 `ca9fb94a21d3b5ae3025923ded305dd11f189626da5adab48a8b947bc523888f` | https://github.com/andrewyng/context-hub | retrieval of curated third-party developer documentation |
| `trace-viewer` | token-efficiency | otel-tui 0.7.5, asset `otel-tui_Linux_x86_64.tar.gz`, sha256 `dd10bfa12b6713a2d51d7a094644ff61a2467856fc93d3acecfe741a124ca896` | https://github.com/ymtdzzz/otel-tui | an on-demand terminal viewer of OTLP traces, metrics and logs on loopback ports |
| `token-lane-carriers` | token-efficiency | the token-lanes SubagentStart block (`adoption/hooks/claude/token-lanes-subagent-start.py` and its role blocks) and a SessionStart main-session block | https://github.com/seathatflowsinourveins/native-agent-stack | naming the installed token tools to each main session and subagent when it starts |

### Owner defaults on rows that installed nothing

| Slot | Layer | Owner default and pin | Repository | What it replaces |
| --- | --- | --- | --- | --- |
| `context-supply` | token-efficiency | context-mode 1.0.169: the Claude Code plugin at the reviewed commit `6f0cc6841c687e754059f36714a11233fda1a02b` (or a descendant whose compare lists only `stats.json`), the Codex plugin at `--ref 6f0cc684`, the Codex server from the npm tarball (sha256 `09c41e4cf77b21566c76b8ea2fdbd7f3d823055fee2f02c2166fd5bb575daf2c`) | https://github.com/mksglu/context-mode | the definitive no-install default and the wave-2 interim; the interim's configuration and its five acceptance gates carry over |
| `ccusage` | token-efficiency | ccusage 20.0.26, npm tarball sha256 `b8d59c191f357d5e847c109f306cf522e60496fc9219be2ab72d201fd59eb1f2` | https://github.com/ccusage/ccusage | not installed, covered by the two clients and the collector |
| `session-analytics` | observation-inference | agentsview 0.43.0, asset `agentsview_0.43.0_linux_amd64.tar.gz`, sha256 `4520c6698772d2db7220212abf58d7d58c0966d7435f0a5ab134371f874df6d9` | https://github.com/kenn-io/agentsview | not installed, agentsview the named challenger of a measurement that has not run |

The job of each of the three rows stays as the rounds named it.

### The code-search interim

The `code-search` row stays a split row of the decision round, with its interim. The interim's default becomes
"semble 0.6.1 + SocratiCode 1.15.0" (semble from https://github.com/MinishLab/semble at the wave-2 pins; SocratiCode
from https://github.com/giancarloerra/SocratiCode: npm
`socraticode@1.15.0` installed with `--ignore-scripts --before=2026-09-24T12:00:00Z`, tarball sha256
`f1ec039e58013863c6e736d1c17876386b9fec1daf9abf72960fcc51c3e364d1`, source
`f6191f076a42405f0d5508139f3a8b505cfef93a`). The two arms are the ones the slot's frozen confirmatory compares, so the
confirmatory still decides: it removes the arm it does not select, or both if it selects ColGREP or nothing. The
interim's install gate (the wave-2 acknowledgements) stays as it is. SocratiCode needs a Qdrant store and an embedding
endpoint that no row of the new distribution installs (the client template's `QDRANT_URL` and `EMBED_URL`). Until the
client configuration names both, the installed package serves nothing, and its open acceptance gate says so.

## Usage rules from measured limits

These limits stay as rules of use; none removes a row.

- TOON only for uniform arrays of flat records; compact JSON otherwise. Pull request #627 (an open draft at head
  `083c9f5428a8e422701180fa58fe69677f9fcd06`, not accepted on main) reports that "TOON's uniform artifact scope passes,
  but its three BOM string roundtrips fail", and `recipes/README.md` records that 4.1.1 strips a leading U+FEFF on decode
  (open toon-format/toon#339). Keep the original JSON unless the strict decode is value-equal.
- ccusage is a meter, never a saving. Native finalized accounting stays authoritative: the same pull request reports that
  "the supplemental ccusage run omits 653,816 tokens across three natural-compaction records". Reports stay token-only
  (`--no-cost`) unless every model is priced (`recipes/README.md`, the ccusage row).
- RTK stays at 0.50.0. Its v0.51.0 release (2026-10-02, read from the GitHub release page on 2026-10-04) lists a breaking
  change: "callers that relied on implicit shell expansion in positional arguments must pass the script explicitly". A
  move is its own qualification. At 0.50.0, never run `rtk init --global --codex` (`docs/token-session-handbook.md:373`).
- Headroom runs as an MCP server only, `headroom mcp serve --proxy-url http://127.0.0.1:1`, a dead proxy URL that reroutes
  no model traffic, with its offline variables set (`docs/decisions/2026-09-25-codex-mcp-scope.md:73-74`,
  `adoption/templates/codex.config.template.toml`). The `[mcp]` extra, not `[all]`.
- codebase-memory-mcp indexes only on an explicit `index_repository` call; never run its `install` subcommand, which edits
  client configurations (`docs/decisions/2026-09-25-codex-mcp-scope.md:74-76`).
- jcodemunch-mcp is registered per project, never at user scope (`docs/token-session-handbook.md:108`), and indexes only
  the selected code.
- agentsview reads a local archive only: an owned data directory, telemetry and the update check off
  (`AGENTSVIEW_TELEMETRY_ENABLED=0`, `AGENTSVIEW_DISABLE_UPDATE_CHECK=1`, the use commands of
  `docs/token-efficiency-stack.json`). A blank archive is not evidence of zero usage.
- Context Hub runs with telemetry and feedback off (`recipes/README.md`, Context Hub opt-out).
- MarkItDown gets the input type (`-x html` or `-m text/html`); only the base converter is installed.

## Overlaps this decision keeps

The assembler's one-owner-per-job check compares job texts. These overlaps are real and are named here rather than
worded around:

- context-mode, RTK and Headroom split the 2026-10-01 context-supply job three ways (local execution and indexed
  retrieval with session hooks; command output; MCP-side compression). Whether they stack or duplicate is what the
  F-token ablation measures.
- MarkItDown (`doc-conversion`) and MinerU (`mineru`, "document parsing to text") both turn documents into text.
- jcodemunch-mcp (`code-index`) and codebase-memory-mcp (`code-graph`) overlap Serena's symbols and references, and the
  two code-search arms overlap each other until the confirmatory decides.
- otel-tui (`trace-viewer`) sits beside Phoenix (`phoenix`, not installed) and Grafana (a measurement row).

## Alternatives and the comparison that removes each component

| Alternative | Why not now | What would bring it back |
| --- | --- | --- |
| The lean base: no token tool (the 2026-10-01 default) | the owner asked for the components on the clean install | an F-token result that the full stack does no better than the lean base, reported to the owner |
| context-mode as an interim only (wave 2) | the interim waits for the wave-2 acknowledgements, and the owner wants the stack live by default | the owner withdrawing this decision |
| One composite context-supply default naming every tool | one row would carry many pins and one removal check | none: each component keeps its own pin and check |

Each component is removed, or kept, by two measurements, whose results go to the owner and remove nothing by themselves:

1. The A/B ablation arms of the Gate A multi-agent E2E on the new distribution: F-token (the full token stack, the lean
   base, and the stack with each component removed in turn) and F-memory (the memory layer the same way). A component
   whose removal leaves raw tool-output tokens entering context and task success unchanged within the run's preregistered
   intervals is a candidate to remove.
2. The fresh-session invocation census: real new sessions of both clients, a main session and subagents, counting each
   token tool's invocations through the clients' own records. A component that the census shows uninvoked is pruned or
   its carrier rewired.

Neither is preregistered by this record; each run freezes its own thresholds before it starts.

## Differences from the plan of record

The coordination plan of session `native-agent-stack-99` (scout leads of 2026-10-04) was checked against the files at
`f77a35eb`. Where they differ, the files decide:

- jcodemunch-mcp's pin is 1.108.319 (`manifests/stack.json`), not 1.108.327: that pin is not on main.
- `session-analytics` already exists (observation-inference, not installed), so agentsview is its owner default, not an
  added row.
- The plan named the owner rows "definitive, state owner-decision". The manifest reserves `definitive` for a default
  both families agreed on, and its tests and the handbook require `definitive` exactly when the state is `definitive`.
  The rows are therefore resolved and not definitive, and the replaced decisions are kept under `overturned`.
- SocratiCode stays out of the profile's default install: the profile's validator refuses a default install for an arm
  of a split slot's comparison (`scripts/new_wsl_profile.py`, `validate_default_installs`), and semble is not a default
  install there either. Both arms install through the install plan's `code-search` slot.
- The catalog edition of 2026-10-01 has no `context-supply` row. Its token-efficiency layer row (line 734) gets the
  pointer, in its notes, because the edition's schema admits no new field (`scripts/build_ecosystem.py`,
  `ARCHITECTURE_ROW_FIELDS`).

## Where the change lands

- `evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json`: the `wave3` batch.
- `evidence/artifacts/new-wsl-definitive-defaults-20261001/assemble_manifest.py`: folds every wave batch in order and
  applies an owner batch; `definitive-manifest.json` and the 2026-10-01 record's tables are regenerated.
- `evidence/artifacts/new-wsl-install-plan-20261002/`: the rows, functions and checks of the new and changed slots;
  `interim_acknowledged` reads every wave batch, and `context-supply` no longer calls it.
- `adoption/new-wsl-profile.json`: RTK and Headroom picked and installed by default, ccusage's install and acceptance,
  and rows for context-mode, jcodemunch-mcp, codebase-memory-mcp, Repomix and TOON.
- `catalogs/foundation/new-wsl-architecture-20261001.json`: a pointer in the token-efficiency row's notes.
- `scripts/build_new_wsl_handbook.py` and the generated handbook: every wave batch's rows are counted.

Not here: the client configuration and its map, the token-session handbook and the workstation.

## Evidence class

Source review and repository integration checks only. The pins and digests are read from the repository's pin records
and, for the four release archives, from the GitHub release pages on 2026-10-04. No command in the new install or
acceptance functions has run on any distribution. The repository's tests that this change updates are its own
integration checks, not upstream acceptance.

## Overturn

- For a row: its removal check reports a result, or the owner withdraws the row. A result removes nothing by itself.
- For the batch: the owner withdraws this decision, or asks for the lean base again.
