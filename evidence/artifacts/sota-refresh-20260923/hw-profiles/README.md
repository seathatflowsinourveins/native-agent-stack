# Unit hw-profiles evidence (2026-09-23 SOTA refresh wave)

Scope: hardware-adaptive profiles for new WSL and macOS hosts
(`scripts/hardware_profile.py`, `adoption/hardware-profiles.json`,
`.github/workflows/hardware-profile-smoke.yml`, `tools/mlx-smoke/`).
Worktree `/home/example/code/nas-wt-w2-hw-profiles`,
branch `claude/w2-hw-profiles-20260923`, base `origin/main` `7407bf3`.

## Receipts

This is the fix round after an independent Opus review of the first submission
found one blocker, five major findings and eight minor findings. See
`review-findings-response.json` for the full finding-by-finding disposition.
`hardware-profile-tool.json` and `mlx-lm-hash-lock.json` are revised receipts
(same filenames, superseding the pre-review versions in git history) with a
`written_after_fix_note` disclosing they were written after implementing the
fix, not before it.

| File | Component | Verdict | Evidence class |
| --- | --- | --- | --- |
| `hardware-profile-tool.json` | `scripts/hardware_profile.py` + `adoption/hardware-profiles.json` (revised after review) | qualified | native_proven |
| `mlx-lm-hash-lock.json` | `tools/mlx-smoke/requirements.lock.txt` + the macOS job's uv sequencing (revised after review) | not_comparable | local_integration |
| `review-findings-response.json` | Disposition of all 12 review findings | qualified | source_review |
| `this-host.json` | Raw `scripts/hardware_profile.py` output for this host (re-run after the fixes; redaction now labelled) | (input to `hardware-profile-tool.json`) | native_proven |

## Summary

- Both new components are additions, not upgrades of an existing pin, so there
  is no prior receipt to diff against; `mlx-lm-hash-lock.json` is marked
  `not_comparable` for that reason rather than `qualified`/`regression`.
- `scripts/hardware_profile.py` was re-measured on this host after the review
  fixes; see `hardware-profile-tool.json`'s `preregistration`/`results` for
  the exact before/after numbers. Key change: `effective_ram_gb` now prefers
  measured `/proc/meminfo` (47.0 GB) over the `.wslconfig` configured ceiling
  (48.0 GB), which moves `embedding_semantic_rag_tier` from `full` to
  `standard`. `cpu_brand` is now actually read from `/proc/cpuinfo`
  (`Intel(R) Core(TM) Ultra 9 275HX`) rather than asserted. This host: 24
  logical cores, `.wslconfig` `memory=48GB` (confirmed by reading
  `/mnt/c/Users/example/.wslconfig` directly; only one Windows user profile
  found, no ambiguity), and an NVIDIA GeForce RTX 5090 Laptop GPU reporting
  23.9 GB VRAM via `nvidia-smi` (the brief's "24 GB" is the marketing figure;
  does not change the recommended tier, threshold `>=20GB`).
- `adoption/hardware-profiles.json` additionally records the 128 GB WSL
  workstation and 48 GB / 64 GB macOS arm64 unified-memory hosts as
  `labelled_projection` entries with inline sizing arithmetic (not
  measurements; macOS entries now scale unified memory by a labelled
  `macos_unified_gpu_working_set_fraction` of 0.6 before comparing against the
  generation-model tiers, so 48/64 GB Macs resolve to `large-32b-q4` rather
  than the earlier `unified-70b-plus`), and a `github-macos-15-arm64-runner`
  entry now marked `evidence_class: pending` (not `native_proven`) since no CI
  artifact exists yet -- this unit authored and offline-validated that
  workflow but did not execute it (no macOS host available in this
  worktree/sandbox).
- The mlx-lm pin (`0.30.2`) was independently confirmed to be uv's own
  resolver choice for `aarch64-apple-darwin` at both Python 3.12 and 3.13,
  even when unconstrained; ml-explore/mlx-lm's actual newest GitHub release is
  `v0.31.3` (`gh api repos/ml-explore/mlx-lm/releases/latest`, published
  2026-04-22), which uv does not select for this target -- recorded per the
  "qualify the newest release" instruction even though the pin does not use
  it.
- Two reproducibility/security fixes landed in the fix round (see
  `review-findings-response.json` for all 12): (1) the macOS job's uv
  install/venv/pip-install sequence no longer activates the venv or invokes
  `python3 -m uv` (a review-found blocker: uv is not importable inside an
  activated venv without system-site-packages); uv is now a standalone,
  SHA-256-verified downloaded binary invoked directly. (2) both the committed
  lock generation and the CI diff-check recompile now pass
  `--exclude-newer 2026-09-23T00:00:00Z`, so a transitive dependency
  publishing a new release cannot make the CI job's redundant-compile-and-diff
  check fail on an unrelated PR; re-verified byte-identical to the committed
  lock file at that cutoff.

## Checks run (offline / local, this host)

- `python3 -m unittest tests.test_hardware_profile -v` -- 33/33 pass (up from
  16; new coverage for `detect_nvidia_gpu`, `measure_macos`, the WSL
  RAM-source precedence, `/proc/cpuinfo` parsing and multi-`.wslconfig`
  ambiguity).
- `python3 -m unittest tests.test_workflow_hardening tests.test_workflow_security_coverage -v`
  -- pass (includes the
  `test_hardware_profile_smoke_workflow_has_no_offline_findings` case and the
  updated expected-workflow-set assertion).
- `zizmor --offline --no-config --no-ignores --no-progress --persona regular
  --strict-collection --format json .github/workflows/hardware-profile-smoke.yml`
  -- `[]` (no findings), re-run after the fix round.
- `actionlint .github/workflows/hardware-profile-smoke.yml` -- no output
  (clean), re-run after the fix round.
- `python3 -m unittest` (full suite), `python3 scripts/validate.py`,
  `python3 scripts/build_ecosystem.py --check` -- see the handoff for this
  round's exact results.

## Limits and unresolved risk

- The macOS job in `hardware-profile-smoke.yml` (measured macOS profile + MLX
  generation smoke test) has never actually executed; it is offline-validated
  (zizmor/actionlint clean, hardening tests pass) but not run-validated. It
  will run for the first time on `pull_request`/`workflow_dispatch` once this
  branch reaches a PR against a runner with `macos-15` availability. This
  round's blocker fix (no venv activation) is therefore also unexecuted;
  it is verified by static re-inspection and mlx-lm/uv's documented behavior,
  not by observing the old failure or the new success actually happen.
- `mlx-lm`'s hash-locked dependency resolution was cross-checked with
  independent `uv pip compile` invocations on this (Linux) host targeting
  `aarch64-apple-darwin`; actual installability with `--require-hashes` on
  real Apple Silicon hardware is unverified until the workflow runs.
- The `macos_unified_gpu_working_set_fraction` (0.6) and the
  `ecosystem_bounded_run` sizing constants (`max_fraction_of_ram=0.25`,
  `ceiling_max_gb=32`) are this unit's own labelled, conservative judgment
  calls responding to the review's findings, not independently re-derived
  from a cited Apple/systemd specification or a stress test at the new
  ceiling.
- The multi-`.wslconfig` ambiguity fix (`wslconfig_other_candidates`) makes
  the ambiguity visible but still auto-picks the alphabetically-first profile;
  no signal exists to determine the "right" one without invoking a Windows
  binary, which this script's read-only design avoids.
- The handbook's generated-block conflation of Codex CLI (0.155.1) and the
  Codex SDK `openai-codex` (0.154.0) at two lines inside
  `<!-- verdicts:begin -->`/`<!-- verdicts:end -->` was confirmed but left
  unfixed: those lines are inside this unit's do-not-touch generated block,
  and the underlying generator source (`catalogs/sota-convergence/manifest-*.json`)
  is also on this unit's do-not-touch list. See `review-findings-response.json`.
- No broker, paid API, or credential-gated check was needed for this unit;
  none was attempted.
- `docs/grand-catalog-handbook.md` edits are confined to the prose outside the
  `<!-- verdicts:begin -->` / `<!-- verdicts:end -->` generated block; no
  ledger, manifest, or gates JSON was modified.
