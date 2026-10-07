# Skills hygiene and native discovery — 2026-10-06

Status: draft source reconciliation and command-center application plans. No
client configuration, installation, retirement or native-bar closure is implied.

This unit supplies reliable skill and workflow discovery for the US-equities
research and historical-simulation north star, as defined in
`native-agent-stack@0d5e6506:blueprints/us-equities/AGENTS.md#trading-north-star`.
It changes foundation source records; research and numeric/risk/order state keep
their existing boundaries.

## Sources and scope

- `native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a:adoption/skills/lifecycle.md`,
  held selection at:77–86 and retirement tombstones at:292–300; central manifest
  browser row and budget at `adoption/skills/manifest.json:535,676`.
- `native-agent-stack@0d5e6506:catalogs/landscape/skills-lifecycle.json:171`;
  its browser incumbent conflicts with the central held selection.
- [Claude context-window documentation](https://code.claude.com/docs/en/context-window#what-survives-compaction),
  including its [Markdown simulation source](https://code.claude.com/docs/en/context-window.md),
  checked2026-10-06: the startup skill-description listing is discarded by
  compaction; previously invoked bodies have separate retention caps.
- [Claude native skills](https://code.claude.com/docs/en/skills) and
  [saved workflows](https://code.claude.com/docs/en/workflows), checked2026-10-06.
- `native-agent-stack@0d5e6506:examples/claude-native/workflows/README.md:41–68`
  and `SHA256SUMS`; the unchanged lane provenance records
  `agent-lab@e070125dae03b4e44484ccb78d2d65057ad38f40` in `vendored-lanes.json:4`.
- `opendatalab/MinerU@c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93:skills/mineru`
  and its [pinned license](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/LICENSE.md).
- `huggingface/huggingface_hub@bd4a76030582d118e28dc9ad6c7a5911ea76176b`
  v2.1.1, vendor-generated hf-cli; registration is owned by draft
  [#792](https://github.com/seathatflowsinourveins/native-agent-stack/pull/792).

The user/command-center190307Z rule requires upstream choice evidence, a clean
lifecycle install, one real-use smoke per client that has a skill, and organic
native counters. Smoke remains smoke. S1 skill-used assertions gate no row and
are not a campaign. These source and metadata checks establish no new model run.

## C7: accept upstream compaction behavior

Accept the documented behavior and use `/skills` when skill discovery is needed
after compaction. An earlier invoked body being restored does not establish
that the complete description catalog was restored. No new compact hook is
proposed or installed. A160-character pointer hook was considered; there is no
current demonstrated gap requiring it beyond the supported discovery command.

This choice uses upstream evidence, not a benchmark. Revisit it if upstream
changes the description-list behavior or real work demonstrates discovery loss
that `/skills` cannot resolve. A future hook remains client configuration owned
by the command center and subject to its separate authorization.

## C12: prepare the supported saved-workflow install

The [exact installation plan](2026-10-06-saved-workflow-install-plan.md) prepares
the14 unchanged payload files for the command center. Upstream supports project
and personal workflow directories; a project same-name workflow takes priority.
The plan preserves existing matching agents, role bodies and permissions. No
workflow was copied or run. Global availability alone does not qualify every
project's role definitions, contract paths or permission source.

## C13: reconcile source status and retain the host gates

The browser landscape now has no installed incumbent and an explicit held
browser-tool gap. The central agent-browser pin remains held and budgeted:
`vercel-labs/agent-browser@d01253d9db28d75080e36da3c1c31ef89454731e`.
Selected source, installation and model invocation are different states.

hf-cli's installed33972-byte source observation matches #792; its exact digest is
`5fa67d3f5b5e071d026c13a029544220f077d9651ed96f5e4ed546981e2c19c5`.
Use #792's registration rather than duplicate its manifest writer. A18 keeps
the repository cap10500; #792's earlier proposal to drop it must be corrected
before publication. This source PR does not import that proposal.

MinerU's installed SKILL matches the retained vendor pin:37708bytes,
589description characters, digest
`dec330a3549d232fed44db2b0c9bc0b64505a11d2526008ddf044b3f94681d96`,
skill tree `38d108595980854f65640d46ab27ecea002b549d`. Full installed-tree
identity and source implicit-policy files were not qualified by this check.
The [registration plan](../../evidence/artifacts/skills-hygiene-20261006/mineru-registration.json)
is inert and outside the active skills store. Its license is Apache2.0-based
with upstream additional commercial and attribution terms, not an unqualified
Apache2.0 declaration. License/source review and cumulative capacity precede
active lifecycle registration.

| Manifest set | Claude description characters | Repository cap10500 |
| --- | ---: | --- |
| Main | 9484 | within |
| Main + MinerU | 10073 | within |
| Main + hf-cli | 10492 | within |
| Main + both | 11081 | 581over |
| Both + pending native-stack-research | 11234 | 734over |

Keep descriptions and the cap unchanged. These sums include held entries and
are repository metadata, not fresh host visibility or a native client budget.
A18 allows a future15000 proposal only after actual both-client evidence and
the command center's decision. Source plans do not deploy unqualified entries
to manufacture that evidence. The installed folder alone does not prove a clean
lifecycle install or the real-use smoke/counters required for closure.

The command center's private host checklist covers the project-local Dagu copy,
override names/policy, and the agent backup. Dagu is outside the global roots;
its selected project SKILL is untracked by Git and its provenance remains
unqualified. Keep it until the owner decides its source and intended scope;
do not delete, move, duplicate or register it from this lead. Seven missing-skill
override entries/six off are a reported lead whose identities are unverified.
Preserve retirement off tombstones; absence of a folder does not justify removing
one. An agent backup exists, but its loader effect has not been tested. The
command center decides preservation outside discovery roots after checking its
intended retention. This PR makes none of those host changes.

## Evidence limits and completeness inputs

Source review, selected-folder/hash observation and metadata consistency remain
separate from unchanged upstream tests, native model discovery and organic use.
The retained doctor reports MinerU under userSettings with2uses; those tracker
counts are not per-role organic evidence. No new smoke, skill A/B or campaign ran.

Next sweep inputs: held versus installed incumbents; generated native skills
missing from the central store; plugin/user-only discovery and cost scopes;
retired-name override tombstones; project-local versus global visibility;
support-file dependencies of saved workflows; license terms outside SKILL
frontmatter; and cross-PR cumulative budgets. Never classify an unattributed or
unobserved use as zero. Host operations and final native-bar closure remain
pending the command center's evidence and application.
