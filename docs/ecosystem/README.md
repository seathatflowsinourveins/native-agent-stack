# Offline ecosystem manifest

**Build `index.html` first, then open it (not `template.html`).** `index.html`
is generated and gitignored, not committed (see
[the decision record](../decisions/2026-09-23-generated-explorer-sorted-manifest.md));
a fresh checkout has no `index.html` until you run
`python3 scripts/build_ecosystem.py --write` from the repository root, or
download the built copy from a `publish-catalog.yml` run's
`*-explorer` artifact. The template is the build source and contains no
catalog data. Opening it now shows a link to the sibling index instead of
inactive catalog controls. Keep the checkout's directory layout when using
that link; a copied standalone template cannot find a missing index.

The generated index is one self-contained file:
the styles, application script and public search data are embedded. The page
makes no background requests and needs no server, account, package install or
external font. Source links navigate only when selected. The file is not
committed to Git, so GitHub does not render or serve it from this repository;
build it locally with `python3 scripts/build_ecosystem.py --write`, or download
a copy from a `publish-catalog.yml` run's `*-explorer` workflow artifact (kept
7 days). The same file can be served by an existing static host, but this
change does not configure GitHub Pages or paid hosting.

If the catalog cannot initialize, its opening screen remains visible with links
to this guide and the manifest. Enable JavaScript for the interactive views. For
missing or damaged embedded data, download a fresh generated `index.html`, or run
the rebuild command below from a complete checkout. The index does not redirect,
fetch missing data, or depend on the template being beside it. A standalone copy
still works offline; the guide and manifest links require the checkout layout.

The views connect a layered ecosystem map, foundation and trading capabilities,
current choices and alternatives, the repository explorer, selected-stack setup,
token-efficiency evidence, the new-WSL final architecture, and dated source
provenance. Every
current public index identity and the existing 342-star snapshot are retained. The separate
current-integrations lane makes newly observed Tavily setup searchable without
silently enlarging the canonical index or accepted component manifest. Stars and
awesome lists remain discovery signals. Layer tags are navigation heuristics,
not adoption decisions or quality scores.

The broad-universe research and adaptive-paper cards open complete embedded
reports without network access. Their recorded receipts are also available in
the selected components' returned-results viewer. These are dated research and
runtime records: the September 21 scan is not a live quote feed, and none of the
15 broad-universe signal/horizon checks established a strategy for promotion.
Optional public-source links resolve after publication; local reading does not
depend on those links.

## Use the setup and efficiency views

**Choices & alternatives** covers all 20 foundation layers and 12 trading
research layers. Each card states the requirement, current choice, named candidate
outcomes, linked evidence, limitations and the comparison that would reopen the
decision. Search across layers/candidates or filter by catalog and outcome.
The 152 original domain candidate cards remain expandable with their historical
dates and recommendations. The current interpretation stays visibly separate.
Download the complete joined comparison JSON from this view. Fresh upstream
metadata is linked separately; release recency does not establish superiority.
The [landscape manifest](../../catalogs/landscape/manifest.json) drives this view,
and `python3 scripts/landscape.py` checks coverage and reference integrity.

**Convergence by layer** appears when the generated
[component evidence matrix](../../catalogs/landscape/component-evidence-matrix.json)
is present. For every layer it shows the layer state, the in-use and converged
counts, the true/false/unknown counts of its three factors, the comparability
columns and any unresolved manifest rows, with the frozen definitions and their
source dates. The counts are layer-component rows: a component in several layers
counts once per layer, so the catalog and overall sums are not distinct
components. Next to the unresolved rows it lists both sides of the
verdict-to-manifest join: recorded winners without a row in the newest sweep
manifest, layers missing from that manifest and manifest layers without a
matrix row. The page types no number of its own: the build rejects a matrix
whose summary disagrees with its layer rows, and
`python3 scripts/component_matrix.py --write` regenerates it.

**Selected stack & setup** includes every component in `manifests/stack.json`,
with layer and adoption-profile filters, the selected version, native command
examples and a button that opens its complete recipe inside the HTML. Recipe
Markdown is embedded once per document and displayed as escaped text in expandable
sections, so its commands and surrounding conditions remain available offline.
The setup, update and portable token-report guides are also embedded. When present,
`adoption/lifecycle.md` supplies the lifecycle continuation guide.

The selected manifest joins `adoption/manifest.json` to the dated
`blueprints/token-native-focus/saturation-audit.json` by component identity.
Every component needs a recipe and exactly one canonical catalog repository;
unknown profile components or receipt references fail the build. A missing audit
row or a different audited version remains visible and never becomes accepted.
Lifecycle stages, client integration, functional scope and artifact baselines
retain their source qualifications. Current acceptance on a new PC is unknown.

Each component also links directly to its attached public command/result bundles.
These open inside the page, with the official component repositories, execution
scope, returned files, hashes and exact downloads. Components without a selected
bundle display that coverage gap. Dated acceptance remains separate from running
all 68 selected components in a particular session.

**Token efficiency** displays the recorded artifact comparisons, including
negative differences, and the public receipts' sanitized upstream returned fields.
The optional `selection_policy` in the presentation manifest records each task's
chosen representation and quality check. A choice can keep a larger original when
the task needs all of its content. The page never optimizes by token count alone,
sums overlapping savings, runs commands or imports private client state.

For fresh complete upstream stdout/stderr and cumulative observations on another
PC, use the embedded portable token-report guide. That private per-host report is
separate from this deterministic public catalog and from Grafana's live monitoring
dashboard. Dated counter-confirmation receipts are embedded when registered in
`manifests/evidence.json`; absence is not a zero counter.

The generator selects explicit receipt families across their registered dates,
including native returned results, memory/RAG alignment, HF model qualification,
dashboard data/access and full-stack convergence. Those additional families must
have an execution evidence kind and canonical selected component identities.
A matching receipt name or component selection does not establish execution.
Native-client results and dashboard results remain separately scoped in the
complete receipt; neither proves the entire stack ran.

Only a selected native receipt's `public_artifacts` are attached offline. Each
entry must declare a repository-relative `evidence/artifacts/` path, exact byte
count and SHA-256. UTF-8 JSON, Markdown and text are displayed as escaped text;
PNG screenshots are embedded as image bytes. Downloads preserve the complete
artifact. The build rejects changed hashes, symlinks, private/outside paths,
unsupported formats, files over 2 MiB and bundles over 16 MiB. It never follows
arbitrary raw-log references. Publication review must establish that the declared
public files are suitable for sharing; the hash check establishes byte identity.
Receipts without public attachments say so explicitly.

**Final architecture** (tab 05) appears when the dated edition
[`catalogs/foundation/new-wsl-architecture-20261001.json`](../../catalogs/foundation/new-wsl-architecture-20261001.json)
is present; without it the tab stays hidden. It is the install manifest for a
new WSL distribution: one row per layer of both catalogs (the 20 foundation
layers and the 12 us-equities layers of the research state) plus `cross:` rows
for the distribution itself, runtime workers, the GPT-6 harnesses, the
credential practice and the convergence practice. The header shows the edition
date, its base commit, scope, the verdict rules verbatim, what each verdict and
evidence class means, the five closure items of
[the research state](../../catalogs/landscape/research-state.json) and the
edition's sources, and states how many rows are closed. One table per catalog
lists each row's winners at their pin of record, verdict, evidence class,
reasons and install command; expanding a row shows the closure items with what
is missing, the winners' pin locators, install and acceptance commands and
upstream currency, the alternatives, the ordered new-host steps and the gates.

The build validates the edition before it renders: every `layer_id` is a known
catalog layer or a `cross:` id, a layer being identified by its catalog and id; a
winner's `component_id` must be a `manifests/stack.json` component, and when the
stack's recorded version differs from the edition's pin the build still passes,
the page notes the drift on that winner and the `--check` JSON lists it under
`architecture_pin_drift`; a winner may carry a short `role` (at most 120
characters), shown beside its name; repositories and currency links pass the
public HTTPS gate; each cited `source_path` must be a repository file, which is
hashed into the page's inputs and linked at the publication ref; a source not yet
on main is cited as a `pending_source` with its pull request and is linked, not
hashed, until its file exists, when it is hashed and labelled as landed after the
edition's base; verdicts and evidence classes come from fixed enums; a row is
`closed` if and only if all five closure items are `met`, so a closed row names
nothing missing and an open row's `missing` names each item that is not met in
its own `cN:` segment and no met item; a row with a winner whose acceptance is
`none_recorded` is `none_recorded`, and otherwise its class is one that a
winner's acceptance carries; and the edition's `close_only_when_sha256` must
match the research state's five closure texts. A catalog layer without a row is
listed as a gap rather than failing the build. The record of this edition is
[`docs/decisions/2026-10-01-new-wsl-architecture-edition.md`](../decisions/2026-10-01-new-wsl-architecture-edition.md).

## Rebuild and check

From the repository root, using Python 3.10 or newer and its standard library:

```sh
python3 scripts/build_ecosystem.py --write
python3 scripts/build_ecosystem.py --check
python3 scripts/validate.py
python3 scripts/validate_catalogs.py
python3 -m unittest
```

Some existing data tests intentionally refuse symlinked paths and private output
inside Git. On macOS, set `TMPDIR` to a resolved temporary directory outside any
checkout before running the full suite. Optional native SDK/data tests retain
their normal dependency-based skips.

The curated layer map, policy summaries and links live in [manifest.json](manifest.json).
The presentation lives in [template.html](template.html). The generator reads only
explicit public files inside this repository; source paths cannot escape it or
follow symlinks. It resolves the decision index's typed pointers and embeds input
hashes. Unknown receipts, unresolved source pointers and duplicate or
noncanonical repository identities fail the build.
Source text is JSON-escaped and rendered with DOM text nodes; navigable source
URLs use credential-free HTTPS. A restrictive content security policy permits
only the exact embedded application script and denies background connections.

The generated page is deterministic. It does not use current wall time, Git status,
network responses, personal catalogs or live credentials. `index.html` is not
committed and `manifests/evidence.json` carries no entry for it, so there is no
committed-file comparison or hash-list cycle to avoid; `--check` instead builds
the page twice into separate temporary directories, requires the two builds to
be byte-identical, and reports `input_sha256` (over every input path/content
the build actually read) and `output_sha256` (of the built HTML). The evidence
manifest's `/receipts` section keeps its own canonical JSON hash; all other
input hashes identify exact file bytes. Run `--check` after changing a source
to confirm the build is still deterministic; there is no publication hash
manifest entry to update afterward.

Existing source-record links use the recorded immutable public base commit.
New files in `docs/ecosystem/` did not exist at that base; their links use public
`main` after publication, as do the lifecycle guide, selected additional receipt
families and their public artifacts, while their exact bytes are embedded or
hash-listed. This prevents new results linking to an older commit that lacks them.
The page makes this distinction explicit. This does not turn a moving branch
link into an immutable source pin; upstream review records retain exact commits.

## Evidence boundaries

The explorer joins useful native execution only from explicitly linked
`native_cli_e2e` or `native_model_e2e` receipts. A historical version inventory,
catalog decision, source review or component pin does not become useful execution.
The two retrieval replay highlights are separately identified as recorded
evaluations, with their own denominators and limits. Current acceptance on the
browser's host stays unknown: a static HTML file probes no accounts or services.

The [dated primary-source review](source-review.json) records native Claude Code
features, existing retrieval and memory options, and local inference gates. That
review installed nothing and left ai-memory 2.3.2 as a candidate. The later
[maintenance receipt](../../evidence/receipts/native-ai-memory-maintenance-20260920.json)
records its bounded update on the source Linux/WSL host after a private backup.
Importing that receipt does not upgrade or qualify macOS, VelaNext or another host.

The [Tavily receipt](tavily-receipt.json) records CLI 0.1.8, eight official skills
at a full source commit, native authentication and one three-result search.
Subsequent fresh native Codex CLI prompt rendering and Claude initialization
discovered all eight skills without model calls. Existing desktop hot reload remains
unverified; extract, crawl and deep research were not accepted by that search. The [readiness observation](readiness-observation.json)
records a separate existing WSL environment's native sign-ins and 75 offline worker
checks. A subsequent [standalone native Claude receipt](legacy-worker-receipt.json)
retains an initial turn-cap failure and a revised accepted task with 57 actual
tests, zero source product edits and complete worker cleanup. The native client
reported 11 turns under the revised 12-turn bound; effective effort is unknown.
The changed prompt and bound prevent a matched efficiency comparison. Native
usage and list-price estimates are retained without summing them into savings or
account billing. This proves one standalone task, not delegated owner/peer
integration, Codex inference or general acceptance on another host. These public
records omit account identifiers, personal paths and private project topology.

Token efficiency is a core operating policy across native clients, skills,
subagents and workers: keep cache and compaction, retrieve scoped sources, disclose
instructions progressively, retain paths and failures in bounded outputs, and
write scoped memory only with explicit intent. Automatic history capture stays
off. Avoid duplicate MCP services and bulk instruction packs. Claim token or cost
savings only with matched complete usage and comparable task quality; native
cache counts and selected-artifact reductions are distinct measurements.

Tests cover source confinement, unresolved and duplicate identities, execution
boundaries, source/URL escaping, new-integration counts, input hashes, changed
documents and generated-file tampering. Browser review covers searching, combined
filters, dialogs, keyboard exit, small screens and the absence of external asset
requests. Repository validation remains an integrity check, not a new native run.

The [cross-layer native acceptance](../../blueprints/convergence-practice/layer-acceptance.md)
adds Mac application/PDF/container proofs and VelaNext recovery/quality tools.
Repository identities still resolve to immutable content revisions; current-host
readiness requires that host’s own recorded acceptance.
