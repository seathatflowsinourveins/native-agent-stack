# Suite-parallelism trial, run 37109532421 (2026-10-03)

Sanitized excerpts of the preregistered trial of unittest-parallel 1.8.6 on the whole test suite (draft pull
request #646, head `1e4bb5ab7c79faa83e4cd8d04cf8dc6d33c7b0de`). Only the ubuntu-24.04 jobs ran; the run was
cancelled before any macos-15 job received a runner. The GitHub run records expire under the repository's 90-day
retention and the 18 artifacts on 2026-11-02, so these files and their hashes are the durable copy.

The receipt [`suite-parallelism-trial-20261003.json`](../../receipts/suite-parallelism-trial-20261003.json) holds
the per-run data, the sha256 and size of every original file (`data.original_files`, `data.hosted_artifacts`)
and of every file here (`data.retained_files`). The decision is recorded in
[`2026-10-03-suite-parallelism-trial-outcome.md`](../../../docs/decisions/2026-10-03-suite-parallelism-trial-outcome.md).

| File | Source | Treatment |
| --- | --- | --- |
| `preregistration-experiment.json.txt` | `blueprints/convergence-practice/macos-suite-parallelism-20261003/experiment.json` at the trial head, status `planned` | Byte copy (sha256 `305fc2fa2ddd2c0a0eba4d85d748807db87302bde59a6b6489de866bee416c08`). The `.txt` suffix keeps `scripts/validate_convergence.py --all-recorded` from reading it as an undeclared convergence record, which it rejects, and from checking its frozen-input hashes against files that exist only on the trial branch |
| `result-trimmed.json` | `result.json` of the `compare` artifact (815,073 bytes) | Trimmed: `decision_rule`, `inputs`, `id_mapping`, `controls` and `verdicts` unchanged; per run every field except the parser notes (kept as a count), the missing ids (kept once per level in `missing_id_sets`) and the mismatch records of missing ids (the others are kept in full). The S side of those dropped records, each missing id's serial outcome, is kept as counts per level and class (`s_outcome_totals`, `s_outcome_by_class`) |
| `summary.md`, `checkout-status.json` | The `compare` artifact | Byte copies |
| `crash-tail-L4-r1.txt`, `crash-tail-L4F-r1.txt`, `crash-tail-L4C-r1.txt` | `log.txt` of the first repeat of each parallel arm | Last 30 lines, sanitized |
| `log-key-lines.txt` | `log.txt` of all 20 run directories | First line, `Ran` and status lines, last line, sanitized |
| `control-logs.txt` | The eight control and crash-control runs, synthetic fixtures executed on the hosted runner | Full logs, sanitized |
| `serial-durations-S.txt` | `log.txt` of the three serial runs | The `--durations 25` tables with their `Ran` and status lines |
| `local-reproductions.txt` | This record's local reproductions: the toy modules on CPython 3.12.3 and 3.13.16, the three real modules on 3.12.3 only and the order-throughput module on both | Commands, exit codes and output, sanitized; the two toy test modules' source |

Sanitization: the runner's checkout path became `<workspace>` and any other path under the runner's home
directory became `<runner-home>`. In the local reproductions, interpreter and virtual-environment prefixes
became `<cpython-3.12.3>`, `<cpython-3.13.16>`, `<venv-3.12.3>` and `<venv-3.13.16>`. Nothing else was changed.
