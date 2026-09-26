# Workstation receipt repairs: controls and attempts (2026-09-26)

This directory holds the retained, sanitized evidence behind the 2026-09-26 repair receipts on
`nativestack-5975wx-20260925`. The cross-family reviews of #277 and #281 found defects in eleven receipts
dated 2026-09-25, and in one PR description. The repair took three rounds:

1. The first repair recorded twelve receipts dated 2026-09-26: a first generation for each of the eleven
   components, plus a `-2` generation for systemd after its first generation failed.
2. An independent review of that repair found seven more defects. Six further `-2` generations (DuckDB,
   pandera, Inspect, MCPorter, promptfoo and SocratiCode) each supersede one of those first generations.
3. A cross-family (GPT-6) verification of rounds 1 and 2 found that FastAPI's first generation classed a
   check of this repository's own application-delivery blueprint as `native_proven`.
   `fastapi--use--20260926-2` supersedes it with FastAPI's unchanged upstream test suite. The blueprint check
   is kept here as `local_integration` evidence.

The context-mode, LEAN and Poppler first generations stand.

| File | What it is | How it was produced |
|---|---|---|
| `discriminating-controls.txt` | 9 controls. Eight (01 to 06, 08 and 09) run a command copied from a recorded receipt. Control 07 is a standalone reproduction that no receipt contains. Controls 01 and 03 reproduce a 2026-09-25 defect; 02, 04 and 06 show a fix holding under an injected fault; 05 removes a fix's two protections and shows the command's own canary check failing; 08 and 09 re-run a fixed command unchanged; 07 reproduces the cause of a failed dry run. Each mutation is listed below. | The harness (`discriminating-controls-harness.py`) copies each command's text from the receipt JSON and applies the control's mutation. Each text substitution first checks that its anchor occurs exactly once. The harness runs the result the way `scripts/host_receipts.py record` does (`/bin/sh -c`, worktree root) and records the exit code and output. |
| `discriminating-controls-harness.py` | The harness source that produced `discriminating-controls.txt`, byte-identical to the file as run. Its paths assume the session's scratch layout (the worktree beside it), so it does not run from this directory as is. | Copied unchanged from the session's scratch directory. |
| `duckdb-tests-fast-exploration.txt` | An exploratory full run of DuckDB's upstream `tests/fast`. It explains why the DuckDB selection was not widened. | Command 2 of `data-duckdb--use--20260926-2` with three stated edits, run the way `scripts/host_receipts.py record` runs commands (the file states the edits). |
| `fastapi-blueprint-local-integration.txt` | `local_integration` evidence for the application-delivery blueprint. It is command 2 of `fastapi--use--20260926` (generation 1), re-run unchanged, and it does not qualify FastAPI. | A run through `scripts/host_receipts.py run_command` at 06:49:51Z (see round 3 below), with TMPDIR and UV_CACHE_DIR in a scratch directory. The file gives the command text's sha256, the exit code and the blueprint's git status after the run. |

Output is sanitized with `scripts/host_receipts.py sanitize()`. In addition, `<worktree>`, `<scratch>` and
`<tmp>` stand for the checkout, the session's scratch directory and `mktemp` paths.

### The nine controls

| # | Source receipt, command | Mutation | Expected, and observed |
|---|---|---|---|
| 01 | `socraticode--install--20260925`, 1 | A first line `PATH=/usr/bin:/bin; export PATH` is prepended, so socraticode is not on PATH. The command text is unchanged. | Exit 0: the `\|\| echo` fail-open the #277 review reported |
| 02 | `socraticode--install--20260926-2`, 1 | The same PATH line | Exit 1 with `SOCRATICODE_RESOLVE_FAIL` |
| 03 | `lean--use--20260925`, 2 | One substitution: the primary run's `--data-folder "$L/Lean/Data/"` becomes `--data-folder "$W/nsr-missing-data/"` | Exit 0: the fail-open the #281 review reported |
| 04 | `lean--use--20260926`, 2 | The same substitution | Exit 1 with `LEAN_BACKTEST_FAIL` |
| 05 | `mcporter--use--20260926-2`, 3 | Two substitutions, which remove both isolation protections. `run()` drops `env -i`, and with it the explicit PATH and LANG; HOME stays the temporary one. `config list` drops `--config "$d/mcporter.json"`. | Exit 1 with `MCPORTER_BRIDGE_FAIL`: the canary `MCPORTER_CONFIG` that the command itself exports is then selected |
| 06 | `fastapi--use--20260926`, 2 | One insertion after the process-group check: `sleep 2`, a message, then `exit 3` | Exit 3. After the exit, the harness finds no process left in the server's group (the EXIT trap). |
| 07 | None: the command is written in the harness | A `setsid sleep 60` group is signalled with the `/bin/sh` builtin `kill -TERM -- -PGID`, then with `/bin/kill` | The builtin exits 2 ("Illegal number") and the group keeps running; `/bin/kill` exits 0 and the group is gone |
| 08 | `promptfoo--use--20260926-2`, 2 | None: re-run with `results-2.json` present | Exit 0, and the tracked `results-2.json` has the same sha256 before and after |
| 09 | `inspect-ai--use--20260926-2`, 2 | None: re-run with `eval-log-2.json` present | Exit 0, and the tracked `eval-log-2.json` has the same sha256 before and after |

All nine were observed as expected.

## What each review defect changed

| Review defect | Change | Evidence |
|---|---|---|
| Independent review of round 1: the Inspect install source said "no persistent host install". A uv tool install of inspect-ai 0.3.266 exists (`inspect-ai--install--20260926-2`). | `inspect-ai--use--20260926-2` runs the eval from that tool install. The status line asserts that `inspect_ai` is imported from it and that `uv pip freeze` is unchanged. openai 3.19.2 comes from an ephemeral overlay: 5 packages added, 0 version changes. | Receipt command 2; control 09 |
| Independent review of round 1: the promptfoo and Inspect eval commands overwrote the tracked native report on every run. | Both write the report in a temporary directory and print its sha256. They create the tracked `results-2.json` / `eval-log-2.json` only when it is absent, by exclusive create. Otherwise they leave it unchanged and compare hashes. | Controls 08 and 09: sha256 before equals after |
| Independent review of round 1: some statements rested on output past the 400-character excerpt: the socraticode ledger, the mcporter default 0.14.1, and the pytest configfile for pandera and duckdb. | Each fact is now in the command's first-line status, and the pandera and duckdb commands fail unless the configfile is `pyproject.toml`. The promptfoo and Inspect key-absence and private-content results also moved into the status line. | The `-2` receipts' excerpts |
| Independent review of round 1: the failed first FastAPI dry run was not disclosed. | Disclosed below, with its cause reproduced. | Controls 06 and 07 |
| Independent review of round 1: the negative runs cited for the round-1 fixes had no retained output. | Re-run from the recorded commands. | Controls 01 to 06 |
| GPT-6 verification: FastAPI generation 1 classed as `native_proven` a handwritten 14-check oracle over this repository's application-delivery blueprint, which the blueprint's own `receipt.json` calls a local synthetic vertical slice, served with its database disabled. `docs/contributing-evidence.md` classes that as `local_integration`. | `fastapi--use--20260926-2` supersedes it. It binds the fastapi/fastapi 0.141.1 tag to the PyPI wheel and the blueprint's `uv.lock`. It runs the tag's unchanged `scripts/test.sh` in a temporary environment built with upstream CI's `uv sync` step, and shows the same run failing after a one-line fault in FastAPI. It serves upstream's first-steps example with `fastapi run`. The blueprint check is kept under its correct label. | Receipt commands 1 to 4; `fastapi-blueprint-local-integration.txt` |

## Review verdicts and what still counts

Independent verdicts on rounds 1 and 2 were appended by reviewer `f07a9dfb…`, an identity other than the
recorder, at 2026-09-26T06:15Z:

- The misclassified `data-pandera--use--20260925` and `data-duckdb--use--20260925` now carry `needs_changes`,
  so they no longer count toward platform status. Their upstream-test replacements,
  `data-pandera--use--20260926-2` and `data-duckdb--use--20260926-2`, carry `agree`.
- The other `-2` generations (Inspect, MCPorter, promptfoo, SocratiCode and systemd) carry `agree`. The first
  generations they supersede carry `needs_changes`.
- The context-mode, LEAN and Poppler first generations carry `agree`. So does FastAPI generation 1; that
  review predates the GPT-6 finding.
- `fastapi--use--20260926-2` carries only its recorder's self review. It cannot qualify FastAPI until an
  independent reviewer agrees.

The recorder links `--supersedes` only within one date, so no 2026-09-26 receipt can retire a 2026-09-25 one.
At this change's base (`5c1961e4`), `scripts/platform_status.py` also counts a superseded receipt that carries
an independent agree. #321, merged to main after that base, retires a receipt once a present receipt
supersedes it at the same component version. Of the receipts below, that rule retires only FastAPI
generation 1 and `mcporter--use--20260925`, each superseded on its own date.

These receipts carry an independent `agree` and a defect. Each keeps counting until an identity other than the
recorder appends `needs_changes`; the receipt's `reviews` array is the current record:

| Receipt | Defect |
|---|---|
| `lean--use--20260925` | Fails open: when the primary run or its statistics check fails, `! grep` succeeds on the missing control log and the command exits 0 (control 03). |
| `mcporter--use--20260925-3` | Says the temporary HOME keeps host MCPorter configuration from loading, but an inherited `MCPORTER_CONFIG` overrides HOME in the pinned resolver (control 05 shows the override). |
| `mcporter--use--20260925` | Generation 1 of that date. It says no host MCPorter configuration was used while MCPorter ran with the real HOME and environment. Its default reranking made QMD fetch a model over the network (per `mcporter--use--20260925-3`), which its limitations do not disclose. |
| `fastapi--use--20260925-2` | Cleanup runs `fuser -k -TERM "$PORT"/tcp`, which signals any process using that port. The claim says both pins match the stack and winner pins, but Uvicorn has neither. |
| `promptfoo--use--20260925-2` | The command deletes promptfoo's native results report, so only a custom summary remains. Its install-source limitation names an existing install; the output says ephemeral npm install. |
| `inspect-ai--use--20260925-2` | The command deletes Inspect's native eval log, so only a custom summary remains. Its install-source limitation names an existing install; another limitation says ephemeral. |
| `poppler--install--20260925` | The claimed `GOODSIG` and `VALIDSIG` results are not in the retained output excerpt. |
| `systemd--use--20260925-2` | The claimed successful result with status 0 is not in the retained excerpt. Its install-source limitation names an existing install under `~/.local/share/codex-ecosystem` for the packaged systemd. |
| `socraticode--install--20260925` | The trailing `\|\| echo` absorbs a failure anywhere in the `&&` chain, so the command exits 0 with socraticode absent from PATH (control 01). Its limitation says the build starts, but nothing starts it. |
| `context-mode--install--20260925` | Its limitation says a version call shows the build starts. The command inspects paths and metadata and never runs context-mode. |
| `fastapi--use--20260926` | Generation 1 of this date: the blueprint check above, recorded as `native_proven`. |

## Failed, discarded and exploratory attempts

- **`fastapi--use--20260926`.** The repair worker's first dry run failed before the 02:47:04Z recording:
  - `stop_server` used the `/bin/sh` (dash) builtin as `kill -TERM -- -PGID`.
  - dash rejects that operand ("Illegal number"), so no signal was sent.
  - One uvicorn server kept running after the command ended. The worker then stopped it by signalling that
    server's own process group.
  - The recorded command uses `/bin/kill`.

  That attempt's own output was not retained. Control 07 reproduces the cause on a throwaway `setsid sleep`
  group. Control 06 shows that the recorded command's EXIT trap leaves no process in the server's group.
- **`inspect-ai--use--20260926`.** A pre-recording dry run failed while the shared model server was busy: a
  240 s budget, then a parser KeyError on the incomplete log. The receipt discloses this.
- **`mcporter--use--20260926`.** A first recording at 02:45:53Z passed and was discarded before publication.
  Its command text named the temporary HOME `$d/home`, and the path beneath it matched the repository's
  home-path scan. The re-recording names it `$d/fakehome`, and the receipt discloses this.
- **`systemd--use--20260926`.** This receipt is a recorded `native_proven` fail and is kept. A journald
  attribution race hid the timer marker from `journalctl -u`. Generation `-2` passes.
- **Round 2:**
  - Every command was dry-run under `/bin/sh` in its final form before recording, and all six recordings
    passed.
  - The promptfoo and Inspect dry runs created `results-2.json` and `eval-log-2.json` in the worktree. Those
    files were moved out before recording, so each retained file is its recording's own output (its receipt
    prints `created`).
  - An earlier, interrupted pass of this repair drafted and dry-ran the same commands and recorded nothing.
  - The pandera selection was widened after a dry run showed that every importable `tests/pandas` file passes.
    The DuckDB selection was not widened; see `duckdb-tests-fast-exploration.txt`.
- **Round 3 (`fastapi--use--20260926-2`):**
  - A first recording at 06:48:21Z passed and was discarded before publication. Its command 1 status line
    printed the tag's commit after `fastapi/fastapi tag 0.141.1 ->`. gitleaks' default `generic-api-key` rule
    reads that as a credential assignment (`api`, then `->`, then a 40-hex value), so the repository's
    pre-commit hook and CI secret scan would have refused the file. The retained recording, at 09:54:25Z,
    changes only that phrase, to `resolves to commit`; commands 2 to 4 are byte-identical. It passes, and
    gitleaks with the repository's `.gitleaks.toml` finds nothing in it. The receipt discloses this.
  - Before each recording, every command was dry-run under `/bin/sh` in that recording's final form, and every
    dry run passed. Earlier dry runs of commands 2 and 3 passed pytest `-rsx` instead of `-rfEsx`, or printed
    their status lines in another order. Nothing was recorded from those forms.
  - The blueprint check was re-run at 06:49:51Z, between the two recordings. Its command comes from generation
    1, which neither recording changed. `fastapi-blueprint-local-integration.txt` is that run's output.
