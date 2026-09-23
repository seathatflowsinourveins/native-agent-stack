# Gap wave 2: us-equities / evaluation-experiments

Checks for the eight open gaps of this layer (crosswalk indices 0-5, 7, 8 at main
92bb279, crosswalk PR #85), run on 2026-09-23 on this Linux x86_64/WSL host.
Preregistrations are in `prereg/`. They were committed in 20fbeb6 before any
check ran. Each receipt quotes its results from `raw/`, which holds sanitized
copies of the raw outputs. `raw/MANIFEST.json` lists the original and published
sha256 of every copy. `results.json` is generated from the receipts by
`build_receipts.py`. The helper scripts are in
`blueprints/gap-wave2-20260923/us-equities__evaluation-experiments/`.

| Gap | Outcome | Receipt | What was executed |
|---:|---|---|---|
| 0 | settled | `0-promptfoo-inspect-two-arm.json` | Contract check 6/6. Both arms ran the frozen 8-case pack with zero provider calls under `unshare -rn`: promptfoo 0.123.1 with the echo exact-text baseline, and a frozen inspect-ai 0.3.266 mockllm task using the same `gate.cjs` and assertions. Concurrency was 1, retries were bounded, a C3 error was injected, and each arm was interrupted with SIGINT and resumed natively. |
| 1 | settled | `1-five-package-installs.json` | Separate uv venvs for inspect-ai 0.3.266, mlflow 3.16.1, river 0.26.1, mteb 2.21.0 (CPU torch) and arize-phoenix 20.14.0. Each ran a snippet or minimal local run: an mteb STSBenchmark score of 0.8203, and a loopback round trip of one OTLP span through phoenix. |
| 2 | settled | `2-matched-promptfoo-inspect-comparison.json` | The gap-0 run is the matched comparison. Scorer reproducibility tied, and resume success tied. inspect-ai led on two properties: it keeps the retried error in its final log, and its gate source hashes matched the frozen bytes for 8/8 cases (promptfoo 6/8, because it compacts the JSON-valued sources of C1 and C2). |
| 3 | settled | `3-inspect-fixture-authored-frozen.json` | The inspect task was authored and hash-frozen in commit 11d1e6c before it was scored. `inspect eval` then exited 0 with 8 scored samples. |
| 4 | advanced | `4-arb-trace2code-host-rerun.json` | ARB v0.2.1 trace2code rerun: per-sample details byte-identical to the Darwin arm64 receipt, 101/101 gold ranks equal, 15/15 upstream tests passed. The remaining clauses are about scope: code retrieval, not financial documents, answer quality or trading. |
| 5 | advanced | `5-fixture-abstention-bootstrap.json` | Added 8 unanswerable queries (frozen in commit 2dbd582) and applied a leave-one-out abstention policy. Paired bootstrap CIs gave no default-promotion claim. The remaining clause: the fixture is still source-authored over 15 documents. |
| 7 | settled | `7-river-delayed-progressive-validation.json` | river `iter_progressive_val_score` with each label released at its t+6 open, on the hash-verified LEAN SPY daily stream. The run emitted a validation report, and the causality probe counted 0 violations for the delayed run versus 1,797 for the immediate control. |
| 8 | advanced | `8-research-evaluation-mlflow-binding.json` | Fix round 1. The unchanged `evaluate.py` ran inside an MLflow run with a temporary sqlite store. `search_runs` read all 16 params and all 19 metrics back with 0 mismatches, and both negative probes were detected. The ledger, stdout and all 21 selection hashes equal the 2026-09-19 receipt. The remaining clause: the evaluation logic is still project-local code. |

## Isolation and downloads

The checks were set up to stay isolated. Only three points were checked afterwards:
- The zero provider calls: every arm ran under `unshare -rn`, and a detection control is retained.
- The stopped loopback servers: `ss` showed zero listeners.
- The frozen input hashes.

The other isolation statements describe how the checks were built, and nothing monitored them:
- Installs, venvs and data were kept under `$HOME/.cache/gap-wave2-20260923/evaluation-experiments/`.
- Heavy jobs ran through `ecosystem-bounded-run`.
- Promptfoo and inspect used temporary config and home directories.
- The scripts unset provider API keys and reference no credential file.
- The scripts write to no PATH directory and do not write `~/.config`.
- This unit made no broker contact, called no paid API and ran no Claude fan-out.

Network downloads:
- uv wheels into an isolated cache: 2.3 GB on disk after unpacking. The largest is torch 2.14.0+cpu at 187.2 MiB.
- all-MiniLM-L6-v2 and the STSBenchmark data: 90 MB.
- CPython 3.14.7: 112 MB.
- The ARB v2_trace2code archive: 37.5 MiB, plus a git clone of the upstream repository.

## Independent review

A round-1 review by Codex (`codex exec --sandbox read-only --ephemeral`) is retained at `raw/review-codex-round1.md`. It raised one major finding and four minor ones:
- **Gap 8 readback (major).** The readback did not compare the logged exit-code metric. Resolved by fix round 1: its preregistration is `prereg/8-*-fix1.json` (commit b874a51), and the rerun is `raw/8/readback-fix1.json`. Gap 8 is now marked advanced, for its project-local clause.
- **Private-cache dependency.** Receipt generation read a file from the private cache. It now uses the original hashes in `raw/MANIFEST.json`.
- **Misleading field name.** A receipt 3 field had a misleading name and was renamed.
- **Blanket absence claims.** They are now labelled as design statements, not monitored absences.
- **Temp path.** A leftover `/tmp` tempfile path is now sanitized.

The review also noted that the ARB per-sample detail files behind receipt 4 were compared only by hash and were not published. A follow-up pass (no new check was run) published them:
- `raw/4/lexical-details.jsonl` and `raw/4/bm25-details.jsonl` are the unmodified outputs of the executed rerun. Their sha256 values equal the Darwin arm64 receipt's `native_details_sha256` values.
- Because the repository `.gitignore` excludes `*.jsonl`, they were force-added, like the existing tracked `actions.jsonl` fixtures.
- Receipt 4 now lists them in `raw_outputs`.
- Rebuilding the receipts refreshed every `checked_at` field. No other receipt field changed.

## Limits

- The gap 0, 2 and 3 arms use a deterministic baseline, so they measure harness behaviour, not model quality.
- The catalog cards under `catalogs/us-equities/` still describe these workflows as prospective. Updating them is left to the coordinator.
- Some helper scripts were edited after they ran. Each edit changes only text, so the publication validator does not flag it:
  - The shell scripts spell the cache root as `${HOME}`, not as the host path.
  - `run_two_arm.sh` splits the quoting around the per-run `home` paths.
  - `compare_two_arm.py` builds those paths from components.
  - `collect_raw.py` uses a glob and derives the home pattern from `Path.home()`.

  After these edits, `compare_two_arm.py` was rerun and reproduced its output byte for byte. `collect_raw.py` then gained the review fixes (a `/tmp` sanitizer and the fix-round files) and regenerated `raw/` in its current form. `run_two_arm.sh` was checked with `bash -n` only. `mlflow_bind.py` is the fix-round version that was executed. `install_venvs.sh` and `install_mteb.sh` are path-sanitized copies of the executed cache scripts.
- For superseded attempts, see each receipt's `superseded_attempts` field, `first_attempt_note` field or limits. Failed first attempts are kept where their output survived: `raw/1/phoenix-attempt1-*` and `raw/8/attempt1-*`.
