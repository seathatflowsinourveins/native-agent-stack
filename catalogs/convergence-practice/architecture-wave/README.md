# September 20 architecture convergence review

The public [owned repository](own-repository.json) was reviewed at immutable
base `327d9badff0ad09ec0c1266e70b4ad361743c77f`. A fresh
[342-star identity comparison](public-star-delta.json) found no additions or
removals. That metadata check does not mean every starred implementation was
audited. The earlier pinned awesome-list coverage remains available in the
[preceding source review](../source-review.md).

This wave rechecked ten relevant upstreams at explicit source commits. The
[ledger](source-review.json) links dated repository metadata, release identity,
README/license hashes and source lines. Its depth is README, license and
supporting overview review; it is not a full security or implementation audit.
The combined index now contains **505 identities**, including all **342 stars**
and **163 beyond them**. Only zizmor is new to that union.

| Reviewed source | Result of this wave |
| --- | --- |
| [zizmor](zizmorcore__zizmor.json) | Add pinned offline CI analysis and known-unsafe acceptance; native evidence is separate from this source ledger. |
| [uv](astral-sh__uv.json) | Retain the existing locked environments and shared package cache; avoid another environment manager. |
| [Dagu](dagucloud__dagu.json) | Retain persisted workflow state; actual workload restart remains distinct from process relaunch. |
| [Inspect](UKGovernmentBEIS__inspect_ai.json) | Retain as an evaluation candidate for held-out task scoring; no provider run in this source review. |
| [ARB](eyuansu62__agent-retrieval-bench.json) | Reuse existing external failure-trace results; retrieval scores do not establish agent repair quality. |
| [QMD](tobi__qmd.json) | Retain scoped collection retrieval; an index must match the intended project and revision. |
| [Cosign](sigstore__cosign.json) | Keep signature identity and tamper rejection as a selected-artifact gate; no signature pass is inferred from checksums. |
| [Harbor](harbor-framework__harbor.json) | Defer broader execution adoption until a relevant workload and containment acceptance justify its operational cost. |
| [jCodeMunch](jgravelle__jcodemunch-mcp.json) | Reject installation in this wave because of overlap and the reviewed Dual Use license boundary. |
| [awesome-mac](jaywcjlove__awesome-mac.json) | Refresh pinned discovery coverage; list membership is not permission to install or evidence of quality. |

Three concrete gaps changed: the public protocol now has an executable evidence
validator; the clean WSL Claude role now has an observed isolated patch task;
and CI now checks workflow security with positive and negative cases. The
[architecture guide](../../../docs/convergence-architecture.md) connects those
results with native caching, bounded retrieval, task ownership, durable scoped
decisions and recovery. More tools become candidates only when a task exposes a
specific remaining gap.

Current limits remain visible: the worker fixture is small and visible to the
model, the three native usage views are not a reconciled whole-task ledger,
offline CI analysis is not exhaustive security assurance, and full independent
host/application recovery is not proved by a successful local process restart.
No automatic installation, transcript capture, broker action or universal SOTA
claim follows from this catalog refresh.
