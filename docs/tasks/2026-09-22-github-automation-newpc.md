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
2. **`macos-embedding-backend`** — llama.cpp Metal `llama-server --embedding
   --port 8232` (a distinct port from the Linux profile's 2048-dim Nemotron
   RAG endpoint at 8231, so the two are never conflated as one embedding
   space) serving embeddinggemma-300M-Q8_0 (768 dims, matching QMD's own
   internal AST-chunk index model on the existing Linux host, not the
   port-8231 Nemotron RAG endpoint) as the 24 GB default; Nemotron-3-Embed-1B
   (2048 dims, matching the Linux 8231 endpoint) gated behind an open "does a
   GGUF exist upstream" question and a 48 GB machine. Alternatives
   considered: MLX and LM Studio, both without a measured comparison on this
   project's retrieval workload. Overturn the 24 GB default only on a
   measured recall/MRR comparison favoring Nemotron **and** available memory
   headroom.
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
- `python3 scripts/adoption_status.py --json` (`native_proven`, exit 2 on this
  host, `status: prerequisites_missing`): the `foundation-cpu` profile itself
  reports `prerequisites_present` (all its commands and recipe paths are
  present); the overall report is `prerequisites_missing` because
  `adoption/manifest.json` `supported_platforms` pins Python `3.13` and this
  host runs `3.12.3` -- a pre-existing mismatch unrelated to this unit's
  changes (confirmed by running the same command at base commit `5cfed34`
  before any of this unit's edits, same result). `--profile
  macos-arm64-foundation --json` also exits 2, correctly reporting `brew`,
  `llama-server` and `launchctl` all absent on this Linux host -- the expected
  outcome for a macOS-only profile checked from Linux, not a bug in the new
  profile.

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
  coordinator's step, not this unit's. **This is an unresolved merge gate,
  not only a documentation limitation**: `.github/workflows/validate.yml` and
  `publish-catalog.yml` both run `python3 scripts/build_ecosystem.py --check`,
  and on this branch that check currently fails -- three new decision ids
  (`new-pc-bootstrap-ci`, `macos-embedding-backend`, `agent-lab-hosting`) and
  the new `macos-arm64-foundation` adoption profile are absent from the
  committed `docs/ecosystem/index.html` until the coordinator regenerates it
  after merging every unit. `scripts/build_ecosystem.py --check` was
  deliberately not run by this unit (its owned paths exclude
  `docs/ecosystem/*` and `--write`), but the coordinator must regenerate the
  explorer before or as part of merging this branch, or CI's validate job
  will fail on the integration branch.
- `new-pc-bootstrap-ci` hosted execution and the macOS embedding acceptance
  test both remain pending; see the two decisions' `next_gap` fields for their
  exact overturn conditions.
