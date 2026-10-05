# Decision: bounded harness startup context (2026-10-05)

Keep common rules at startup and move client-specific or task-specific reference
behind a trigger and pointer. Preserve each relocated passage verbatim. Use native
skill visibility and RTK installation, with fixed byte ceilings for the repository's
rendered startup files. This serves the foundation's north-star action: carry complex
systems work and US-equities research through reproducible native workflows with
enough context for the actual task.

The user's October 5 requirement is a maintained harness that stays aligned with
upstream research convergence and avoids bloat. Bounded builder job 075 authorizes
these repository changes at `2e681ae5c8f7dfd5d92c7ee9f7b8205ed077f710`.
The coordinator owns host re-rendering and the commit. Standing delegation,
`manifests/stack.json` and `manifests/evidence.json` are outside this edit.

## Measurement and scope

The October 5 read-only harness audit measured real transcripts and rollouts on two
hosts. It reported approximately 88 KB and 78 KB of Claude startup context and 41 KB
and 48 KB of Codex startup context. Those are historical host totals, including
skill listings, memory, hook output and other surfaces; its token estimates use
bytes divided by four. There is no new after-host measurement in this job.

The exact comparison below measures UTF-8 bytes at the job's base and in the trimmed
working tree. It follows the audit's renderer/carrier discovery; it is not a replay
of those host totals. Claude's scope is the rendered user block, repository
`CLAUDE.md` and the repository `AGENTS.md` that it imports. Codex's scope is its
rendered user block and repository `AGENTS.md`. The existing managed-block merger
includes marker bytes. Count each repository file once.

| File or rendered client scope | Before bytes | After bytes |
| --- | ---: | ---: |
| `AGENTS.md` | 13,986 | 10,101 |
| Repository `CLAUDE.md` | 766 | 766 |
| `examples/claude-native/CLAUDE.md` | 13,776 | 10,830 |
| `adoption/templates/codex.AGENTS.template.md` | 8,190 | 8,091 |
| Claude rendered startup scope | 28,794 | 21,963 |
| Codex rendered startup scope | 22,176 | 18,192 |

The Claude and Codex carriers in `adoption/new-wsl/` equal their respective source
templates at this revision. The scoped reductions are 6,831 bytes and 3,984 bytes.
They establish an instruction-file reduction, not a model-quality, token-usage or
billing result. Native RTK's imported awareness file, host text outside the managed
block, MEMORY.md, plugin injections, skill/agent listings, MCP instructions and
client built-in prompts are separate measurement surfaces.

## Verbatim moves

Source line numbers refer to the job's base. Passage bytes exclude the separating
newline; this explains the audit's one-byte differences for individual lines.
Each source retains a one-line task pointer, and each passage exists byte-for-byte
at its destination. Common substrings can share their canonical passage.

| From | Destination | Passage bytes |
| --- | --- | ---: |
| `AGENTS.md:38`, Codex routing and pinned launches | `adoption/templates/codex.AGENTS.template.md` | 868 |
| `AGENTS.md:39`, Claude effort and Ultracode rules | `docs/decisions/2026-09-29-max-default-effort.md` | 1,564 |
| `AGENTS.md:53`, trading north star and linked rules | `blueprints/us-equities/AGENTS.md` | 1,352 |
| `AGENTS.md:33`, QMD catalog lookup | `docs/token-session-handbook.md#catalog-lookup` | 499 |
| `AGENTS.md:49`, dashboard checkpoint | `observability/grand-dashboard/README.md#checkpoint-and-observation-rules` | 294 |
| `AGENTS.md:50`, Grafana observation and Dagu authentication | Same dashboard section | 239 |
| `AGENTS.md:51`, generated ecosystem HTML | `docs/token-session-handbook.md#offline-ecosystem-guide` | 282 |
| Portable Claude `CLAUDE.md:48`, duplicate Codex routing | Canonical Codex template above | 782 |
| Portable Claude `CLAUDE.md:45`, named teammate mechanics | `examples/claude-native/workflows/README.md#native-workflow-mechanics-relocated-2026-10-05` | 385 |
| Portable Claude `CLAUDE.md:50`, effort, inheritance, limits and concurrency | Same workflow section | 1,668 |
| Portable Claude `CLAUDE.md:55`, messaging, StructuredOutput and incomplete returns | Same workflow section | 872 |

The portable Claude file retains its solo, subagent, workflow and team dispatch
rules. The relocated workflow details remain explicitly dated, with the existing
source references in that workflow guide. The trading file now carries the original
north star and paper authorization rather than instructing readers to return to
the root for them. The root and portable Claude pointers lead to the single Codex
routing source; generated carriers are projections of it.

## Native defaults and corrected claims

Remove the `skillListingBudgetFraction: 0.05` override and its map matcher. Upstream
defaults to 1% of context. Use native `name-only` visibility for nine specialized
audit/triage skills selected from the audit's listing concern and
`adoption/skills/manifest.json`: `security-best-practices`, `security-threat-model`,
`codeql`, `supply-chain-risk-auditor`, `agentic-actions-auditor`, `sarif-parsing`,
`fp-check`, `variant-analysis` and `security-audit`. Their names stay listed and
invocable; all skill entries, pins, statuses and Codex enablement stay in place.
The manifest's listed-description sum changes from 9,484 to 5,357 Unicode code
points, a manifest calculation rather than a live skill-listing byte measurement.
No new skill-usage report was run. Native `/skill-doctor` is the follow-up for
per-host costs and invocation frequency. Plugin skills ignore `skillOverrides`,
so that native setting is limited to skills exposed through the supported local
skill paths. [Claude skills documentation](https://code.claude.com/docs/en/skills)
defines the default, visibility states, plugin limitation and usage report.

The root skill-discovery instruction now names installed `find-skills` or Skills
CLI `find`, and installed `skill-creator`, while distinguishing Codex's bundled
copy from Claude's selected Anthropic copy. Check actual client exposure, including
user-only invocation, and follow `adoption/skills/lifecycle.md` when a capability
is missing. The audit found that one host did not have Claude's copy installed;
the new wording does not assume installation. The official
[skill-creator integration](https://code.claude.com/docs/en/skills#run-evals-with-skill-creator)
names Claude's maintained plugin.

Our own startup hooks stay within one line of at most 160 characters. Upstream
plugins may provide their documented native injection blocks, whose bytes must be
measured separately. Context Mode's selected `v1.0.169` README documents its
SessionStart routing injection; using an earlier `v1.0.65` discovery lead here
would have cited the wrong selected pin. This correction is recorded with the
verification path in the harness anti-pattern log.
[Context Mode source](https://github.com/mksglu/context-mode/blob/v1.0.169/README.md)
and [Claude plugin hooks](https://code.claude.com/docs/en/plugins-reference#hooks)
support this distinction. Startup remains free of our audits, trials and network
checks.

RTK uses its native 0.51.0 global installer default: RTK.md plus an `@RTK.md` import.
The client-config map previously installed its hook without wiring that native
instruction-file initialization. The existing apply tool now calls
`rtk init -g --no-patch` before adopting the Claude block, then checks both files.
`--no-patch` leaves settings to the map's hook configuration; RTK itself writes
its awareness file and import. This closes an integration gap without a local RTK
renderer. Two executions of the actual installed binary in an isolated temporary
home each exited 0, wrote a 452-byte RTK.md and retained exactly one import. That
is native installation evidence, not a provider or model run.
[RTK 0.51.0 installer source](https://github.com/rtk-ai/rtk/blob/e001f773f80b22b7dc4c7a79521b30e35aaef026/src/hooks/init/claude.rs#L305)
and [README](https://github.com/rtk-ai/rtk/blob/v0.51.0/README.md) document the layout.

The Codex inline RTK excerpt removes the two blanket assurances that every prefix
is safe and that behavior/exit status never changes. Its existing command-form
exceptions remain explicit, directing callers to native execution or `rtk proxy`.
The excerpt marker says it is qualified, and the unchanged upstream full-awareness
source is retained in `tests/fixtures/codex-worker-lane/rtk-awareness-full.md`
(SHA-256 `278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc`).
The status checker compares all remaining awareness content while allowing only
those two exact omissions; a bare import or missing command guidance still fails.
Existing Codex role projections, their checksums and the scaffold top block follow
the canonical correction. Their role and delegation text stays unchanged.
[RTK awareness source](https://github.com/rtk-ai/rtk/blob/v0.51.0/hooks/rtk-awareness-full.md)
is the cited original; the dated anti-pattern log records the corrected claim.

## Fixed byte budget and review procedure

`tests.test_install_claude_profile.PortableTopRuleTests` measures the rendered
managed blocks and repository files above, instead of raising a word baseline
whenever text is added. Freeze the trimmed sizes plus 5% rounded upward:

| Client | Trimmed bytes | Fixed ceiling | Headroom |
| --- | ---: | ---: | ---: |
| Claude | 21,963 | 23,062 | 1,099 |
| Codex | 18,192 | 19,102 | 910 |

The ceilings are constants, not a calculation from current file size at test
runtime. Boundary controls exercise growth in every loaded file and a multibyte
character. Keep the separate 8,192-byte Codex template test. A future change first
tries a task pointer, existing native skill or maintained upstream feature. If a
ceiling must change, add a dated decision with old/new rendered bytes, the required
behavior, alternatives, primary sources and the comparison that would overturn
it. Change the constant in the same reviewed diff; do not silently re-baseline it.
Regenerate carriers and run these tests after the decision.

The local gate fills a specific native automation gap. Installed Claude 2.1.289's
`claude doctor --help` exits 0 and lists only `-h, --help`; no machine-readable
prompt-audit CLI form is found there or in the reviewed changelog through 2.1.289.
The upstream 2.1.283 changelog introduces the interactive `/doctor prompt-audit`
slash command. Keep using that native audit for semantic review; this byte test
does not reproduce it.
[Upstream Claude changelog](https://github.com/anthropics/claude-code/blob/v2.1.289/CHANGELOG.md)
and [memory documentation](https://code.claude.com/docs/en/memory) are the source
checks. Claude recommends concise instruction files, warns that conflicting rules
may be chosen arbitrarily, and loads imported files at launch. Codex concatenates
project instruction files and imposes a configurable project-document limit;
the client-specific byte scope follows its native loader, not Claude imports.
[Codex AGENTS guide](https://developers.openai.com/codex/guides/agents-md) and
[installed-version loader source](https://github.com/openai/codex/blob/rust-v0.159.3/codex-rs/core/src/agents_md.rs)
support this distinction.

## Freshness, alternatives and overturn conditions

The existing upstream-surface watch previously observed versioned setting and tool
surfaces, without watching these instruction documents. Extend its existing bounded
fetch/cache path, rather than adding a watcher or runner. Three enabled dispositions
track the exact memory, skills and Codex AGENTS guide URLs cited above. Their reviewed
body digests and the carrier for this audit are in
`catalogs/foundation/upstream-surface-dispositions.json`. A body change reopens its
row in `unreviewed` even when its name was already reviewed. Writing a surface
baseline cannot clear it. Re-read the primary document and repeat this audit before
changing the reviewed digest. Offline replay preserves the cached observation date;
a required missing source fails the watch. Request Markdown where supported; an
HTML response's markup changes can also trigger review. See
`docs/upstream-surface-watch.md` for this existing tool's native operation.

The alternatives were retaining the inline rules and rising word baseline,
deleting/rephrasing rules to save bytes, and adding a separate prompt-audit runner.
Verbatim disclosure, native settings/installers and a narrow gate preserve the
behavior while bounding the owned surface. Overturn this choice when:

- An upstream machine-readable audit supplies the same rendered-file byte contract;
  adopt it and remove the redundant local gate.
- A document watch or client update changes file discovery, imports, skill listing
  or native RTK initialization; verify the new source and remeasure before adoption.
- A native usage report or task comparison shows a selected audit skill loses
  required matching; restore that skill's description through a dated listing
  decision, keeping the upstream fraction default unless evidence overturns it.
- Real task evidence shows a relocated rule is not reached through its pointer;
  sharpen the trigger or restore only the required common instruction, with a
  dated byte comparison and quality evidence.

## Completeness review and evidence limits

This bounded review covers both clients' repository-owned instruction surfaces,
skill visibility, RTK layout and the three upstream document classes. It preserves
workflow dispatch, trading authorization and each moved rule. The next coordinator
sweep should measure the remaining host surfaces: standing delegation, MEMORY.md,
upstream hook output, imported native RTK text, skill/agent listings and MCP
instructions. Key the skill follow-up by lifecycle task (audit, triage, scan and
threat-model work), then use native `/skill-doctor` and upstream skill evals where
behavioral comparison is needed. Avoid treating smaller files as proof of better
research or agent output. No new model or billing experiment was performed.

A scoped ai-memory query with `pin_first=true, limit=2` was attempted; the installed
tool required approval while this builder's approval policy is never. The exact
audit, current repository sources and canonical upstream sources supplied the
evidence instead. Initial `.md` Claude documentation URLs returned 403 and two
guessed source paths returned 404; canonical document URLs and tag source paths
resolved those leads. Failed check attempts and the original source snapshots are
retained outside the checkout in the authorized builder temporary directory.
Compact move and byte measurements are in `.bounded-job-075/`. They remain
separate from upstream execution and live-provider acceptance.

## Acceptance (resumed completion)

Only the seven requested test modules were run for resumed acceptance:
`tests.test_install_claude_profile`, `tests.test_codex_worker_lane`,
`tests.test_scaffold_repo`, `tests.test_new_wsl_client_config`,
`tests.test_new_wsl_handbook`, `tests.test_managed_block` and
`tests.test_upstream_surface_watch`.

| Command | Exit | Returned result |
| --- | ---: | --- |
| `python3 tools/adoption/new_wsl_client_config.py --write-blocks` | 0 | Carriers regenerated |
| `python3 tools/adoption/new_wsl_client_config.py --check` | 0 | Current; two existing MCP_AUTO_OPEN_ENABLED manifest/install-plan warnings |
| `python3 scripts/build_new_wsl_handbook.py --write` | 0 | JSON and Markdown regenerated |
| `python3 -m unittest` with the seven modules above | 0 | Ran 645 tests in 152.325s; OK (skipped=22) |
| `python3 scripts/validate.py` | 1 | Registry drift only: 79 SHA-256/byte-count mismatches; no other findings |
| `wc -c adoption/templates/codex.AGENTS.template.md` | 0 | 8,091 bytes, below 8,192 |
| `git diff --check` | 0 | No whitespace errors |

All eleven preserved passages were read back at their destinations and compared
with the original snapshots. The three requested file byte comparisons remain
13,986 to 10,101, 13,776 to 10,830 and 8,190 to 8,091. These checks are local
integration and synthetic-fixture evidence, alongside the separate native RTK
installation execution recorded above. They are not unchanged upstream test runs.

Earlier acceptance attempts exposed stale RTK marker/checksum/location assertions,
synthetic native-install coverage gaps for alternate temporary homes, and a moved
README citation. Corrected projections and read-back assertions preserve the
source contracts; the citation now names the actual `otel.environment` line.
Raw-source examples and temporary paths initially triggered publication scanning
while stored in the checkout; preserving those originals outside it resolved that
storage error. Failed logs remain retained as failed attempts. Protected stack and
evidence manifests are unchanged, and no commit or host re-render was performed.
The coordinator's commit message is `.bounded-job-075/msg.txt`.
