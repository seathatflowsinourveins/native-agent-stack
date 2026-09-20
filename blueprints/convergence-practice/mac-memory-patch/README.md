# Mac ai-memory patch qualification

The September 20, 2026 functional trial passed **56 checks across 36 native tool
calls** on macOS 26.5.1 arm64. It populated a synthetic store with **2.3.1**, opened
that same store with **2.3.2**, then restarted 2.3.2 and verified persistence.
All three owned processes exited normally with code 0. [Receipt](receipt.json),
[selected native facts](native-facts.json) and [experiment](experiment.json) retain
this scope. Production promotion remains a separate coordinator-owned decision.

The trial verified exact scoped bodies, FTS positives, empty cross-scope queries,
not-found cross-scope reads, reserved Git-path rejection, a five-byte Unicode path
component, updated-page persistence and absence of the superseded marker. SQLite
integrity and populated V62 page windows passed before and after. Sessions,
observations, workstream events/native sessions and embedding rows remained zero;
no model files appeared. The cold 2.3.1 synthetic snapshot remained byte-identical.
The four accepted client tools were available; all 23 tool names matched across
versions. No client policy or global registration was changed.

## Distribution, security assessment and failed attempt

The official Mac arm64 archive, SHA-256 sidecar, executable and bundled MIT license
match [pins.json](pins.json). `file` reported native arm64 Mach-O, and
`codesign --verify --strict` passed. The signature is ad-hoc, with no Developer ID
team; Gatekeeper assessment rejected it with exit 3. Actual `--version` and server
execution were allowed without quarantine removal, re-signing, protection changes
or bypassing an execution denial. These are separate observed facts.

The [first receipt](receipt-attempt-1.json) records a failed stronger sandbox
precondition. Its Python probe, then native `true`, `nc` and `touch` diagnostics,
aborted with signal 6 before reporting combined guard results. A minimal
network-denying profile executed `true`, establishing only framework availability.
**OS filesystem/network confinement was not established.** No ai-memory process
started in that first attempt. Its [oracle](oracle.json), [runner](run.py) and
[diagnostics](prior-attempts.json) remain unchanged.

The coordinator explicitly redirected attempt 2 to the original functional scope:
a separate synthetic store, explicit no-model/no-capture settings and no production
or global changes. Its new [oracle](oracle-functional.json) and
[runner](run-functional.py) were frozen before execution. It makes no stronger
sandbox claim and does not convert the first attempt into a pass.

## Reproduce the functional scope

Select the already-reviewed exact 2.3.1 binary and a new private prefix outside
the checkout. The runner verifies both binaries and all distribution hashes. It
refuses to overwrite an attempt and never promotes a binary or changes a service.

```sh
python3 blueprints/convergence-practice/mac-memory-patch/run-functional.py \
  --prefix "$REVIEWED_PRIVATE_PREFIX" \
  --old-binary "$REVIEWED_231_BINARY" \
  --attempt attempt-2-functional
```

[config.toml](config.toml) disables embeddings, startup history backfill, assistant
capture, session-end consolidation, managed-run autowiring, general maintenance
and automatic improvement scheduling. LLM providers and reranker remain unset.
Each native process receives only `HOME`, `LANG`, `PATH` and its owned `TMPDIR`;
`HOME` retains the real home path and is never repurposed. Data and config paths
are explicit. Provider credentials are not forwarded. This configuration and
empty runtime tables are evidence of the selected behavior, not an independent
network-traffic audit.

The exact argument structure is retained in the receipt:

```text
<versioned-binary> --data-dir <attempt>/data --config <attempt>/frozen/config.toml
serve --transport stdio --no-watcher --workspace mac-patch-synthetic --project alpha
```

Retain frozen inputs, raw protocol logs and the cold synthetic baseline privately.
Published facts contain only the public synthetic requests and relevant native
outcomes. No real memory content, credentials, personal paths or account state are
published. Production backup/restore, real copied-state acceptance, LaunchAgent
switching, embedding acceptance and native-client reconnection remain separate.
The source Linux/WSL receipt is not Mac proof.

## Offline verification

```sh
python3 blueprints/convergence-practice/mac-memory-patch/audit.py
python3 -m unittest discover -s blueprints/convergence-practice/mac-memory-patch -p 'test_*.py' -v
python3 scripts/validate_convergence.py blueprints/convergence-practice/mac-memory-patch/experiment.json --root . --json
```

The independent facts checker requires expected rejection reasons; a database
error cannot masquerade as a successful negative-scope check. Tests also reject
scope leakage, missing calls, wrong restart bodies, captured observations, forced
cleanup, changed frozen inputs and relabelled Gatekeeper results.

Both repository validators passed. The 493-test repository suite passed with 49
skips using an owned temporary directory without symlink ancestors. The first run
using macOS's symlinked system temporary directory produced 12 failures and 33
errors; that result and its path-related diagnosis are retained in
[prior-attempts.json](prior-attempts.json). No assertion was weakened.
