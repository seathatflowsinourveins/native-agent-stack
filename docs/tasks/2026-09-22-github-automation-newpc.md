# New-machine handbook and config templates (pr3-handbook)

Scope: build the ordered new-machine adoption handbook, byte-exact native
client config templates and their renderer, the Linux/macOS platform pages,
and three catalog decisions naming this work's own evidence class,
alternatives and overturn condition. Owned paths only; no `docs/ecosystem/*`
or `catalogs/sota-convergence/manifest-20260922.json` edits, no
`scripts/build_ecosystem.py --write`.

## Decisions

Each of the three new rows in
[`catalogs/foundation/decisions.json`](../../catalogs/foundation/decisions.json)
uses `selection: candidate`, `review_status: source_review`, empty
`component_ids`/`evidence_ids` and an empty `lifecycle.stage_refs`: none of the
three has a native acceptance receipt, so none can claim
`accepted_within_scope` or `partial_acceptance`.

1. **`new-pc-bootstrap-ci`** — run the render/`--check`/`adoption_status.py`
   sequence as a hosted GitHub Actions job instead of only locally.
   Alternatives considered: stay entirely manual (rejected, no independent
   regression signal), or mirror it into the existing native workflows now
   (deferred, needs its own scoped workflow and a dated CI receipt).
   Overturn only on an actual linked hosted run, not a workflow file's mere
   existence.
2. **`macos-embedding-backend`** — llama.cpp Metal `llama-server --embedding`
   serving embeddinggemma-300M-Q8_0 (768 dims, matching the existing Linux
   QMD model) as the 24 GB default; Nemotron-3-Embed-1B (2048 dims) gated
   behind an open "does a GGUF exist upstream" question and a 48 GB machine.
   Alternatives considered: MLX and LM Studio, both without a measured
   comparison on this project's retrieval workload. Overturn the 24 GB
   default only on a measured recall/MRR comparison favoring Nemotron **and**
   available memory headroom.
3. **`agent-lab-hosting`** — keep agent-lab's existing private GitHub remote
   (`origin https://github.com/seathatflowsinourveins/agent-lab.git`,
   confirmed with `git remote -v` on this host) plus minimal CI, rather than
   mirroring the full native-agent-stack CI suite into agent-lab or running
   agent-lab with no hosted checks at all. Overturn only on a hosted run
   showing the mirrored suites give equal evidence at lower cost.

## Verification

Commands below were run raw (`rtk proxy`) from
this unit's worktree root on this host, base commit `5cfed34`.
Exact exit codes and evidence classes are in
[`evidence/receipts/github-automation-newpc-20260922.json`](../../evidence/receipts/github-automation-newpc-20260922.json)
and in this unit's structured handoff. Summary:

- `scripts/validate.py`, `scripts/validate_catalogs.py`,
  `scripts/validate_foundation.py --root . --json`, `scripts/landscape.py --root .`,
  `scripts/validate_convergence.py --all-recorded --root . --json` — structural
  validators against the changed manifest/decisions/evidence files
  (`native_proven`: actually executed on this host; structural validation
  only, not execution of the catalog's other capabilities).
- `tools/adoption/render_config.py --host wsl-seath --check
  --live-codex-project <agent-lab checkout>/.codex/config.toml` — a real
  local run against this host's actual live `~/.claude/settings.json`,
  `~/.codex/config.toml` and `agent-lab/.codex/config.toml`
  (`native_proven`). `adoption/hosts/wsl-seath.json` holds this host's actual
  values and is gitignored; it is never published.
- `python3 -m unittest tests.test_render_config tests.test_adoption_contract`
  and the full `python3 -m unittest` run (`native_proven`, local integration
  tests: fixture host values, synthetic live-file diffs, no external network
  or account calls).
- `new-pc-bootstrap-ci`'s hosted-CI claim is explicitly `source_review`, not
  `native_proven`: no GitHub Actions workflow exists yet and no hosted run has
  occurred. `macos-embedding-backend` is explicitly `source_review`: no Mac
  executed `llama-server`.

## Limits

- The macOS page (`adoption/platforms/macos-arm64.md`) is drafted, not
  accepted; every command on it is unexecuted.
- `render_config.py --check` byte-identity is native evidence for this one
  Linux/WSL2 host's three live files only; it does not establish that the
  templates render byte-identically on a different host's PATH layout beyond
  what the nine placeholders parameterize (for example, a host with an
  entirely different Windows-mount ordering still needs its own
  `adoption/hosts/<host>.json` and its own `--check`).
- `docs/ecosystem/*` and `catalogs/sota-convergence/manifest-20260922.json`
  are unchanged by this unit; a full-catalog explorer rebuild is the
  coordinator's step, not this unit's.
- `new-pc-bootstrap-ci` hosted execution and the macOS embedding acceptance
  test both remain pending; see the two decisions' `next_gap` fields for their
  exact overturn conditions.
