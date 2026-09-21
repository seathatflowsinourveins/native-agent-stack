# Offline ecosystem manifest

Open [index.html](index.html) locally in a browser. It is one self-contained file:
the styles, application script and public search data are embedded. The page
makes no background requests and needs no server, account, package install or
external font. Source links navigate only when selected. GitHub shows HTML source;
download the file to view it locally. The same file can be served by an existing
static host, but this change does not configure GitHub Pages or paid hosting.

The five views connect a layered ecosystem map, the canonical repository explorer,
selected-stack setup, token-efficiency evidence, and dated source provenance. Every
current public index identity and the existing 342-star snapshot are retained. The separate
current-integrations lane makes newly observed Tavily setup searchable without
silently enlarging the canonical index or accepted component manifest. Stars and
awesome lists remain discovery signals. Layer tags are navigation heuristics,
not adoption decisions or quality scores.

## Use the setup and efficiency views

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
hashes. Unknown receipts, unresolved source pointers, duplicate repository
identities, noncanonical repository URLs and stale generated bytes fail the build.
Source text is JSON-escaped and rendered with DOM text nodes; navigable source
URLs use credential-free HTTPS. A restrictive content security policy permits
only the exact embedded application script and denies background connections.

The generated page is deterministic. It does not use current wall time, Git status,
network responses, personal catalogs or live credentials. The evidence manifest's
`/receipts` section has its own canonical JSON hash; its `files` hash list is not
an input, avoiding a cycle when that list hashes the generated HTML. All other
input hashes identify exact file bytes. Run `--check` after changing a source;
update the existing publication hash manifest after regeneration.

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
