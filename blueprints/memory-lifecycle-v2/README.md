# Memory lifecycle v2 -- restart, real-time TTL and multi-project acceptance

Native **ai-memory 2.3.2** (the durable-memory landscape winner pin) and **ai-memory 2.4.0** (the
current upstream release, reviewed but not adopted -- see
`docs/decisions/2026-09-25-ai-memory-2-4-0-release-review.md`) each independently completed
**69 phase-"pre" + 16 phase-"post" = 85 MCP tool calls**, with **all 72 phase-"pre" checks and
all 17 phase-"post" checks passing on both binaries**. Each binary ran against its own fresh,
empty, disposable store; no store was opened by both binaries. [The preregistration](PREREGISTRATION.md),
written and hashed before either binary ran, names every check and its pass bar.
[The results](results-20260925.json) retain per-binary, per-phase counts, durations, binary
and preregistration hashes, the exact expected-error payloads, and the sweep/status evidence.

This is a FOUNDATION blueprint (general native-harness acceptance), separate from
[`blueprints/us-equities/memory-lifecycle/`](../us-equities/memory-lifecycle/) (v1, a
trading-path blueprint, unmodified by this work). v2 reuses v1's bubblewrap isolation recipe
and `run.py`/`exercise.py`/`analyze.py` split by attribution, extended to two sequential
native server processes sharing one disposable store, and a larger fixture.

## What v2 adds

v1 (23/23 checks over 31 calls against ai-memory 2.3.1, `passed_scoped_acceptance`)
explicitly did not exercise service restart durability, a TTL crossing in real time, scoped
retrieval under more than two projects, or upgrade behaviour --
[`catalogs/us-equities/convergence-review.json`](../../catalogs/us-equities/convergence-review.json)
(`id: memory-lifecycle`) and
[`catalogs/landscape/foundation.json`](../../catalogs/landscape/foundation.json)'s
`durable-memory` `open_gaps` name exactly these as still open. This run adds, each as
preregistered checks with an explicit pass bar (PREREGISTRATION.md section 4):

- **TTL crossing in real time.** A page whose `expires_at` is 4 real seconds out is queried
  and found before expiry; the run then sleeps on the actual wall clock (not simulated) past
  expiry plus a 2.5s safety margin; ordinary search then hides it while `include_expired` and
  a direct read still surface it (not yet swept); an explicit `memory_forget_sweep` then
  removes it entirely, alongside a v1-style already-past-expiry page, while an unrelated
  durable (non-expiring) control page is unaffected throughout.
- **Scoped retrieval under 4 projects / 2 workspaces.** `alpha`, `beta`, `gamma` share one
  workspace; `delta` sits in a second workspace. All 12 ordered cross-project queries return
  zero hits; each project finds only its own term. The documented `scopes` (explicit
  multi-project list) and `global` (every project in every workspace) query modes are each
  exercised against the behaviour their own live `tools/list` schema documents.
- **Restart durability.** The native stdio server process is stopped (fully exits --
  `serve --help` documents a single-instance data-dir lock, so this design never overlaps two
  servers on one store) and a NEW server process for the SAME binary starts against the same
  disposable `--data-dir`. Durable pages, a live (undeleted) supersession chain, and an
  already-completed deletion are all re-checked read-only against the new process, byte-equal
  or same-`page_id` to their phase-"pre" values. One additional write+read-back after restart
  confirms the new process is fully live, not just serving frozen state.
- **v1 regression.** v1's project routing/isolation, supersession/`as_of`,
  already-past-expiry+pinned, far-future, invalid-expiry and explicit-delete checks are all
  reproduced here (new fixture terms, same shape), so a regression in either binary would show
  up alongside the new checks, not just in the original.

**Upgrade behaviour** is qualified by running the identical, unmodified check suite against
both binaries, each against its own fresh store -- not by migrating one store between them.
2.4.0 migrates forward any store it opens, and that migration is one-way
(`docs/decisions/2026-09-25-ai-memory-2-4-0-release-review.md`: an older binary refuses a
migrated store with `DataSchemaAhead`); opening one store with both binaries is explicitly out
of scope (PREREGISTRATION.md section 5), not attempted here.

## Isolation and commands

Same bubblewrap recipe as v1: `bwrap --unshare-all --clearenv --die-with-parent --new-session
--cap-drop ALL`, only the selected binary, system runtime and driver script mounted read-only,
plus a fresh output directory read-write. `embedding_provider = "none"`, no LLM, watcher,
backfill, autowire, maintenance and auto-improve scheduling all off, matching v1's explicit
embedding opt-out. Every fixture name (`alpha`/`beta`/`gamma`/`delta`,
`lifecycle-v2`/`lifecycle-v2-secondary`, and every page term such as `Marigoldpixel`) is
invented for this run; none is real project or account data.

```sh
python3 blueprints/memory-lifecycle-v2/run.py \
  --binary ~/.local/share/codex-ecosystem/tools/ai-memory-2.3.2/ai-memory \
  --out "$NEW_PRIVATE_RUN_DIRECTORY_A"
python3 blueprints/memory-lifecycle-v2/run.py \
  --binary ~/.local/share/codex-ecosystem/tools/ai-memory-2.4.0/ai-memory \
  --out "$NEW_PRIVATE_RUN_DIRECTORY_B"
```

Each invocation runs bubblewrap TWICE, strictly sequentially: phase "pre" (the 69-call
fixture, ending with a small handoff file of page ids and captured `as_of` instants -- written
to a harness-only mount, never into the ai-memory data directory itself) and, only after that
process has fully exited, phase "post" (16 read-mostly calls against a brand-new server
process pointed at the SAME `--data-dir`). `run.py` rejects a non-fresh output directory and
an output under the binary's own install directory, verifies the binary's own sha256 is
unchanged before and after EACH phase, and fails closed on a non-zero exit, a timeout, or an
unexpected tool-call count.

To inspect the artifact checks without rerunning either server:

```sh
python3 -c "
import json, sys
sys.path.insert(0, 'blueprints/memory-lifecycle-v2')
import analyze
pre = json.load(open('PRIVATE_RUN_DIR/phase-pre/outcomes.json'))
post = json.load(open('PRIVATE_RUN_DIR/phase-post/outcomes.json'))
handoff = json.load(open('PRIVATE_RUN_DIR/handoff/fixture-state.json'))
print(analyze.summarize_pre(pre)['passed'], analyze.summarize_post(post, handoff)['passed'])
"
```

## Results

| | ai-memory 2.3.2 (landscape winner pin) | ai-memory 2.4.0 (official upstream release) |
|---|---|---|
| binary sha256 (measured; unchanged before/after both phases) | `93eeb299...cfed0` | `360b9dff...246344` |
| negotiated `initialize` protocolVersion (client requests `2025-03-26`) | `2024-11-05` | `2025-03-26` |
| advertised MCP tools | 23 | 23 |
| phase "pre": tool calls / checks passed | 69 / 72 of 72 | 69 / 72 of 72 |
| phase "pre" duration | 7.340s (includes a real ~6.5s TTL wait) | 7.402s (same) |
| phase "post" (restart): tool calls / checks passed | 16 / 17 of 17 | 16 / 17 of 17 |
| phase "post" duration | 0.211s | 0.266s |
| `memory_forget_sweep` (both the near-future and the v1-style already-past page) | previewed then deleted, exactly 2 entries, `hard_deleted` counter stayed `0` (a separate counter, not interchangeable with the sweep's own `deleted` flags -- same finding as v1) | identical |
| default-scoped `memory_status` for the `alpha` project, stable across restart | `pages_latest=4`, `pages_all=5` | identical, plus a new `evidence_rows=0` field (2.4.0 only, informational) |

Full per-check detail (the `itemized_checks` block: every named check and its boolean, per binary and phase), exact expected-error payloads, and six cross-binary observations
(including the confirmed live shape of a `global=true` response -- results arrive in a
separate `global_hits` array with `workspace_name`/`project_name` per hit, not in `hits` --
and a scope-error JSON-RPC code note consistent with v1's own prior finding that this
classification has been in flux) are in [`results-20260925.json`](results-20260925.json).

## Limitations

Everything v1 already scoped out still applies here (tenant authorization; secure erasure
from Git checkpoints, logs or backups; market/valid-time semantics; retrieval ranking,
embeddings or LLM answer synthesis -- `embedding_provider` stayed `"none"` throughout; macOS
or Windows execution). In addition, specific to this run:

- Store migration -- one store opened by both binaries -- is explicitly not exercised. "Same
  checks pass on both binaries" is this run's whole upgrade-behaviour claim; it is not a claim
  that a 2.3.2 store migrates cleanly into 2.4.0, or that a migrated store still works with
  2.3.2 (which the release-review doc's own trial already found it does not).
- The 2.4.0 release tarball's sha256 is recorded as supplied, peer-verified evidence, not
  re-fetched or independently re-verified over the network by this run (the run's sandbox has
  no network egress by design). Only the installed binary file's own sha256 was independently
  measured here, before and after each phase, for both binaries.
- Concurrent multi-client access to one server process is not exercised.
- Pin note, added later on 2026-09-25: production on the workstation moved to 2.4.0 in a separate, user-approved window, and the pin-move PR takes `manifests/stack.json` and the Linux bootstrap pins to 2.4.0. The durable-memory landscape winner pin stays 2.3.2 until a verdict wave. Where this page says "pin", it means that landscape winner pin.
- This does not change the repository's adopted ai-memory pin (stays 2.3.2 per
  `manifests/stack.json`); it is independent comparison evidence for that decision, not a
  replacement for it.
- Linux/WSL2 bubblewrap only, matching v1.

PREREGISTRATION.md section 5 has the complete, exact list this run committed to before either
binary ran.

Page ids from the disposable stores appear as 8-hex prefixes followed by an ellipsis; the full ids stay in the private run directories, which are not published.
