# Native workflow routing

Read [manifest.json](manifest.json) for the task's existing skills, role and native
delivery channels. [routing.md](routing.md) is generated for review. Pins stay in
the referenced stores; this directory is a routing layer.

Generate repository artifacts with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tools/adoption/render_workflow.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/adoption/render_workflow.py --check
python3 scripts/validate.py
```

The renderer reuses native Claude frontmatter and path rules. It requires the same
maintained PyYAML reader used by the role tests; CI provisions checksum-locked
official wheels. It registers no host hooks, clients or services.

Local validation needs the same reader. In an owned tool environment on the
covered Linux/macOS Python lines, use the upstream-supported pip command:

```sh
python3 -m pip install --only-binary=:all: --require-hashes -r .github/requirements-validation.txt
```

The shared checksum lock covers Linux x86_64 and macOS x86_64/arm64, Python
3.12-3.14. The Linux and macOS validator jobs provision it; the catalog
freshness/publisher prerequisite landed in
[PR642](https://github.com/seathatflowsinourveins/native-agent-stack/pull/642).
Each PyYAML bump refreshes all nine platform hashes from the release's PyPI JSON.
No host install is performed by the renderer.

Pending dependencies have inert routes. Their proposed roles and rules remain
under `pending-agents/` and `pending-rules/`, outside active registries. Activate a
mapping only after its source-store entry and Tier B record exist. A fresh render
and the required checks then become the reviewable change.

The finite generated-name set is checked across active and passive directories.
When retiring or holding a route, remove its obsolete owned files in that reviewed
change; rendering refuses stale files and never deletes unknown files. Identical
shared variants remain while any eligible row needs them. Files are staged and
replaced atomically one at a time, not as an atomic batch. After a later-write
failure, rerender and --check recover/verify the complete set.

Skill-grant variants are passive definitions until a native caller demonstrably
delivers the selected row's imperative packet. Unedited workflow scripts do not
consume this manifest merely because the definition validates.

The routing hook is held for the upstream A/B and command-center ACK. Existing
native descriptions remain available; a proposed channel or frontmatter grant is
not organic-use or end-to-end acceptance. See the
[routing source record](../../docs/decisions/2026-10-06-sota-workflow-manifest.md)
and its [acceptance amendment](../../docs/decisions/2026-10-06-skill-row-acceptance-amendment.md).
Skill rows use upstream choice evidence, lifecycle installation, one real-use
smoke per consuming client and native organic counters. S1's skill-used assertions
gate no row and are not run as a campaign; S9's hook A/B-before-live hold remains.

The [before/after role tables](role-tool-measurements.md) retain the observed
counter scope and pending native measurement gate. Missing per-role attribution
is unknown, and newly granted tools are not counted as invocations.

Sources: [Claude native subagents](https://code.claude.com/docs/en/sub-agents),
[path-scoped rules](https://code.claude.com/docs/en/memory#path-specific-rules), and
`native-agent-stack@ecfa1127:tests/test_install_claude_profile.py:1289-1346`.
