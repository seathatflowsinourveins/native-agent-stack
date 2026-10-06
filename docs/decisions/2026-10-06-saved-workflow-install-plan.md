# Saved native workflow installation plan — 2026-10-06

State: PREPARED, command-center apply only. No workflow, agent, settings or
permission file is changed by this plan.

## Source and target

Follow `native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a:examples/claude-native/workflows/README.md:41–68`
and its unchanged SHA256SUMS. Native lane provenance additionally names
`agent-lab@e070125dae03b4e44484ccb78d2d65057ad38f40`.

The command center's requested personal installation target is
`~/.claude/workflows/`; if CLAUDE_CONFIG_DIR is set, use its `workflows/`
subdirectory. [Official workflow documentation](https://code.claude.com/docs/en/workflows#save-the-workflow-for-reuse),
checked2026-10-06, explicitly supports this location. Project
`.claude/workflows/` remains the README's Adopt1 target and overrides a personal
workflow with the same name. Do not assume the absence of a project directory
means personal workflows are unsupported.

Before applying, the command center selects the destination profile and checks
same-name personal files without overwriting them until differences are reviewed.
Use only qualified repository projects with the required role definitions and
contract bindings; availability across projects is not universal acceptance.

## Exact source payload

Copy these files from `examples/claude-native/workflows/` to the selected
workflow directory. Preserve upstream script bytes; no wrapper or rewrite.
The14 current source digests match the pinned SHA256SUMS.

| File | Source SHA256 |
| --- | --- |
| check-syntax.mjs | ca62177687420fe22e03d0510a18e4f32b5d150e0156f6651c48367c3da506e1 |
| child-usage.mjs | 3e5189342734135e88a2295c1c2152275d9e26c0c7731ed5cbc8905bbccd98a4 |
| codex-cross-review.mjs | cd303779df6521c804070a319aa04c86ed2d6fe1c099c537836f037dec5f4e8b |
| layer-verdict-lane.js | fd77b74945e9d2bd0b26b7822aabcde00e7e650c327da16d852fdbfd5984c0d6 |
| readiness-audit.js | 1d3d816cc219a252760a471a3b68a979057e2c417c429d6c094df4c474e612bb |
| review-changes.js | bb298f9ab63a6d43173d2c4f87ab31d00dd79184e961dc84d69cbef3966bce0b |
| test-child-usage.mjs | 4f45b0f613d9d73fbd75792ed6a9b2cfad50ab98d3e3dcd54cd6b53791e32674 |
| test-codex-envelope.mjs | 2617c081f606268ed20a6e00f6472495fad950db433ca3afbb44ea970aaac446 |
| test-contract-mutations.mjs | cfc4908cea1f53da4e269a10cb5ebb6a4311f9bc477e61c62e245452719eede3 |
| test-envelope.mjs | 6a71109f5021e65d5be6cf1ca9d7b765eda6a5d175cbde3cff662a996f99825d |
| test-usage-receipts.mjs | 2ed3323db76d0104327a0c0bb35f00cf6a05018bdd9f49982b0c279cf2540871 |
| contract.config.json | 2e73ed523e115e6a1f55a4cc992bf052e157d9cdd85aeb09cf4ef93d3f996771 |
| shell-parser.pin.json | 961f4555c9067f17ae5fc2666d20ee797fbd2cd7abcbff80aa4963e912bf64d0 |
| vendored-lanes.json | 452712bf2eeee0ad158a061cc6a9291d305aaf9e01d9564aca7b428e1d4ee83e |

Retain SHA256SUMS as source provenance. The deployed contract.config.json hash
will differ after its documented path configuration; report both separately.
Do not install a tests-only subset or omit JSON support files. child-usage.mjs:633
uses shell-parser.pin.json, and codex-cross-review.mjs:20 locates the official
openai-codex plugin's codex-companion.mjs. Verify those selected dependencies
before their features run. The pinned parser packages are conditional; this plan
does not install them or claim native CLI-lane parsing.

## Preserve agents and bind the contract

Adopt1 also names `examples/claude-native/agents/`. Its nine same-name definitions
match the existing owned project's definitions by SHA256: blind-adjudicator,
blind-lane-reviewer, evidence-reviewer, isolated-builder, security-reviewer,
semantic-evidence-reviewer, source-scout, stack-researcher and stack-verifier.
Preserve those project definitions. That comparison does not qualify the personal
destination: test-envelope.mjs:14 resolves the sibling agents/ directory, so the
command center must compare and qualify the corresponding personal agents before
a personal install is accepted. Add only reviewed missing definitions; never
overwrite a different user agent or the five Gate A pinned role bodies. Tool
grants remain the command center's separate reviewed plan.

For the personal workflow target, bind contract paths relative to the workflow
directory, following Adopt2 and test-contract-mutations.mjs:126, which rejects
absolute bindings. Compute those paths for the actual selected PROJECT and
CLAUDE_CONFIG_DIR; do not copy the project-relative example blindly. It must set
the project settings carrier, active instructions containing the required sizing
and effort rule, contract document, routing document and task record. Configure
new usage receipts in durable owned state; do not write new runs into historical
published evidence. The unchanged example's historical receipt-binding check
remains structural reference evidence and cannot become fresh acceptance by
pointing at an old receipt. Record any omitted optional check explicitly.

For a default personal root and PROJECT at ~/code/native-agent-stack, settings
can resolve as ../../code/native-agent-stack/.claude/settings.json, instructions
as ../../code/native-agent-stack/AGENTS.md, and contract_doc/routing_doc as
../../code/native-agent-stack/examples/claude-native/workflows/README.md. These
are relative-path candidates, not qualified settings or instruction content.
The selected instruction carrier still needs the required sizing/effort rules.
Configure the new durable receipts and actual task record in the same relative
form, then run the unchanged contract checks. Destination agents, dependencies,
permissions and bindings remain pending command-center qualification.

The command center handles the Workflow permission source and existing settings
merge. `examples/claude-native/ultracode.settings.json` enables workflow support,
but is not permission-mode approval. No lane changes client settings, permissions,
role bodies or hooks. Preserve the applicable model/effort pins and explicit21128
gateway flags for repository workers, with both model-free preflights before
dispatch. Fresh Claude sessions use the shared lock and paper-window constraints.

## Acceptance after the command center applies

Follow Adopt4: fresh native session or supported reload, then invoke the selected
saved workflow by name with explicit arguments. Retain source/destination hashes,
actual discovery, contract-check output, native run result and complete/unknown
usage separately. Run the vendored checks appropriate to the configured contract
outside the paper window. No installation, workflow discovery or execution is
claimed by preparing this plan. The command center supplies the apply/readback
and decides closure from actual evidence.
