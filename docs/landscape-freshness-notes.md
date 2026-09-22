# Upstream freshness and new public candidate — 2026-09-21

The [public upstream snapshot](../catalogs/landscape/upstream-snapshot.json)
checks all **68 selected components** against their recorded GitHub repositories.
All 68 returned public repository metadata; none was archived or disabled.
The observation ended at **2026-09-21 22:40:29 UTC**. This is source metadata and a
bounded new-candidate review, not a new installation, benchmark or proof that the
selections are universally best.

Retain the currently qualified component pins. Five newer stable releases merit
review against a demonstrated task gap, but this snapshot establishes no reason
to replace accepted behavior merely because a release is newer.

## Release differences that need interpretation

| Component | Selected version | Observed stable release | Disposition and acceptance needed |
| --- | --- | --- | --- |
| AgentsView | 0.43.0 | [v0.44.0](https://github.com/kenn-io/agentsview/releases/tag/v0.44.0) | Retain; compare scoped history retrieval, privacy boundaries and recovery before changing. |
| MarkItDown | 0.1.7 | [v0.1.8](https://github.com/microsoft/markitdown/releases/tag/v0.1.8) | Retain; compare required document formats and information preservation on representative inputs. |
| vLLM | 0.25.0 | [v0.29.0](https://github.com/vllm-project/vllm/releases/tag/v0.29.0) | Retain; require target GPU/model compatibility and native quality, latency, memory and recovery evidence. |
| Dagu | 2.16.6 | [v2.17.0](https://github.com/dagucloud/dagu/releases/tag/v2.17.0) | Retain; qualify the needed scheduler change with execution, failure/restart behavior and authentication scope. |
| skfolio | 1.2.9 | [v1.3.0](https://github.com/skfolio/skfolio/releases/tag/v1.3.0) | Retain; compare required estimator/API behavior and temporal research contracts before upgrading. |

These are proposed acceptance comparisons, not trials that ran in this audit.
Release bodies and security advisories were not reviewed. Existing acceptance
is linked by each selected component in [the stack manifest](../manifests/stack.json).

Several apparent differences are different distribution channels:

- Serena, llama.cpp and NautilusTrader deliberately use development/prerelease
  revisions. GitHub's latest-stable endpoint excludes prereleases.
- ECC, Claude Code Templates and LEAN are selected by source revision. LEAN's
  returned stable release is dated 2017, whereas the retained selected commit
  is from September 2026; the endpoint is not a useful upgrade ordering for it.
- systemd is an Ubuntu distribution package; an upstream tag does not establish
  a supported replacement for that package.
- Five latest-stable endpoints returned 404: Claude Code Best Practice,
  skills-ref, PostgreSQL, the Poppler GitHub mirror and Tavily CLI. Their
  default-branch source commits are captured as metadata only. A 404 here does
  not prove abandonment or absence of packages/tags on another release channel.

The Headroom GitHub API redirects the recorded `chopratejas/headroom` identity to
[headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom). The
snapshot retains both. A canonical-URL correction is appropriate manifest
maintenance; it does not justify a functional replacement.

PostgreSQL and Poppler use 64-character **archive SHA-256 digests** in their
selected `source_pin` fields. The first attempt incorrectly treated each digest
as a commit ref; both failures are retained and their semantics corrected in the
snapshot. Neither archive was downloaded or rehashed. Poppler's primary source
is [its freedesktop GitLab repository](https://gitlab.freedesktop.org/poppler/poppler);
the selected GitHub identity is a mirror.

## Current public stars: 343, with one addition

The native public user-star endpoint returned **343 repositories**, compared
with the preserved [342-repository audit](../catalogs/us-equities/star-audit.json).
There was one addition, no removals, no duplicates and no private-flagged rows.
The snapshot retains every current public repository URL, query timestamps,
command results and an identity-set hash. Seven explicit 50-item pages reproduce
the initial four-page identity-delta observation. Historical audit dates remain
unchanged.

The addition is [trycua/cua](https://github.com/trycua/cua), reviewed at
[`9bbfa7dd3e27ca7f1861ede70aaca390174493f9`](https://github.com/trycua/cua/tree/9bbfa7dd3e27ca7f1861ede70aaca390174493f9).
Its disposition is **targeted candidate; conditional, source review only**.

The pinned [root README](https://github.com/trycua/cua/blob/9bbfa7dd3e27ca7f1861ede70aaca390174493f9/README.md)
describes a modular computer-use stack: a native application driver, isolated
cloud desktops, local Apple-Silicon VMs, models and benchmarks. The
[Driver README](https://github.com/trycua/cua/blob/9bbfa7dd3e27ca7f1861ede70aaca390174493f9/libs/cua-driver/README.md)
documents agent-facing MCP/CLI interfaces and separate application SDKs.
The [first-app tutorial](https://github.com/trycua/cua/blob/9bbfa7dd3e27ca7f1861ede70aaca390174493f9/docs/content/docs/tutorials/drive-your-first-app.mdx)
explicitly covers macOS, Windows and Linux. Therefore a blanket claim that Cua
fails this stack's platform requirement would be unsupported. Its
[root license](https://github.com/trycua/cua/blob/9bbfa7dd3e27ca7f1861ede70aaca390174493f9/LICENSE.md)
is MIT; artifact-specific model/data and dependency terms were not audited.

Cua may fill a future native-desktop task gap beyond browser DOM interaction.
The existing agent-browser/native UI defaults remain selected because this
screen supplied no representative same-task comparison showing a Cua advantage.
It has not failed a fair behavioral trial, and it is not dismissed as generally
inferior. A future trial should run the upstream tutorial and a representative
multi-application task on the target OS, then compare correctness, focus
behavior, permission attribution, recovery and operational cost. Its cloud and
model components are separate adoption decisions.

This review read selected README sections, the complete root license and the
first tutorial segment. The initially guessed `LICENSE` path returned 404;
root enumeration identified `LICENSE.md`, which was read successfully. The
failed path is preserved. No Cua installation, desktop action, cloud resource,
model call or upstream test was performed.

## Reproduction and evidence boundary

The selected-repository query template is `gh api {endpoint}`, using native
GitHub CLI 2.101.0 with at most four concurrent public requests. Each record
retains the exact endpoint, start/end time, exit status, selected returned fields,
and raw-stdout SHA-256. Nonzero errors are retained; unchanged failed queries
were not retried. Source refs and release tags are resolved to commit SHAs when
available. Authentication state, tokens and machine paths are not included.

The snapshot contains 262 native API command receipts: 245 selected-component
queries, one initial paginated star query, seven complete-identity page queries
and nine new-candidate source queries. Eight commands returned nonzero: five
latest-stable 404s, two mistaken archive-digest commit lookups, and the initial
Cua license-path 404. Full API bodies are not bundled; retained hashes identify
the observed bodies but cannot reconstruct them.

The scoped consistency check verifies 68 exact selected IDs/versions/pins,
343 distinct current star URLs, the identity-set hash and the recorded delta.
Repository validation verifies local references and evidence structure. Those
checks do not convert metadata or documentation into native execution evidence.
