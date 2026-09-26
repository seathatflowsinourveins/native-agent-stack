# Token workflow hardening and discriminating fixtures (2026-09-26)

Local evidence for two changes to the native token tools workflow, recorded on host
`nativestack-5975wx-20260925` (WSL2, x86_64, CPU only) from base commit `771f25f8`:

1. [`.github/workflows/native-token-e2e.yml`](../../../.github/workflows/native-token-e2e.yml) now
   starts with `step-security/harden-runner` in audit mode, pinned to the same SHA as every other
   harden-runner step in the repository, and its `upload-artifact` comment names the exact
   release (`# v7.0.1`). Its earlier exemption was to end with "a re-run of that evidence which
   re-pins the workflow with the step in place"
   ([fix-round record](../../../docs/decisions/2026-09-22-actions-hardening-fix-round.md),
   "Integration follow-up"). The two runs below re-record the harness receipts against the new
   workflow bytes (`fb06cf92…`). They call `scripts/native_token_ci.py` directly, so no workflow
   step, harden-runner included, ran in them; the pull request's own hosted run of the job is the
   step's first execution.
2. [`scripts/native_token_ci.py`](../../../scripts/native_token_ci.py) gains inputs on which each
   tool's native behaviour differs measurably from a passthrough or a plain-text tool, and each such
   check is held against the baseline it must differ from.

The same change adds the step and exact-release comments to the two off-host recovery workflows,
refreshing only their plans' prospective bindings as on 2026-09-20; no run of those workflows is
part of this record. Decision record:
[`docs/decisions/2026-09-26-token-workflow-hardening.md`](../../../docs/decisions/2026-09-26-token-workflow-hardening.md).

**Evidence classes.** The harness runs, the controls driver, the unit tests and the mutation check are
`local_integration`: pinned upstream CLIs run on this repository's fixtures, and this repository's
checks assert on what they return. zizmor and actionlint are `local_static_analysis`. The action pin
inventory is a `documented_api_check` (read-only `gh api` calls). None of this is a hosted GitHub
Actions run; the pull request's own run of the workflow is a separate record.

| File | What it is |
| --- | --- |
| [`runs.json`](runs.json) | Every run, control, test and check below, with hashes and the wrapper's observations |
| [`final-harness-run-1.receipt.json`](final-harness-run-1.receipt.json), [`final-harness-run-2.receipt.json`](final-harness-run-2.receipt.json) | The final harness's own receipts, unchanged |
| [`controls.json`](controls.json) | The controls driver's own report, unchanged |
| [`controls_driver.py`](controls_driver.py) | The driver that ran the controls |
| [`mutation_check.py`](mutation_check.py) | The script that weakened each new check in a scratch copy and ran the unit tests |
| [`actions_latest.py`](actions_latest.py), [`actions-latest.json`](actions-latest.json) | Every pinned action's SHA against its comment tag and latest release |

## What each new check tells apart

Measured in both final runs (identical values):

| Tool | Input | Native result | What the baseline returns |
| --- | --- | --- | --- |
| RTK 0.50.0 | 12 commits, each with five body lines and two trailers | `rtk git log -12`: 2,880 bytes, one header plus three body lines and `[+2 lines omitted]` per commit, no trailers; ledger +564 estimated tokens saved | `git log -12`: 6,599 bytes, full bodies and trailers; `rtk proxy git log -12` returns it byte for byte and the ledger records 0 saved; `rtk git log` without `-N` shows the 10 newest commits |
| MarkItDown 0.1.8 | [`fixtures/markitdown-multi-element.html`](../../../fixtures/markitdown-multi-element.html) (1,231 bytes) | All 10 element checks hold (headings, pipe table, ordered and nested lists, link, emphasis, blockquote, fenced code, inline code with a decoded entity, image); script, style and comment text dropped | The raw HTML and its standard-library tag-stripped text each fail all 10 element checks and still hold the hidden text |
| ast-grep 0.45.3 | [`fixtures/ast_grep_shell_calls.py`](../../../fixtures/ast_grep_shell_calls.py) | `subprocess.run($$$, shell=True, $$$)` returns lines 8 and 12-16, the second a call spread over five lines | The closest single-line regex (`grep -n -E 'subprocess\.run\(.*shell=True'`) returns lines 8, 24 and 31: a comment and a string instead of the spread-out call |
| Repomix 1.18.1 | `fixtures/before.py`, `fixtures/after.py` with `--compress` | Each file packs as `def greeting(name)`; the body is gone | The existing check `repomix-structural-output-only` also passes on an uncompressed pack (shown by the control below) |
| TOON 4.1.1 | `fixtures/records.json` (96 bytes) | One tabular block, `items[2]{name,enabled,count}:` and two rows, 60 bytes; the encoder is bundled in the CLI, so the exact text is pinned | Other valid TOON encodings also pass the existing strict round trip (the `--delimiter \|` control below). A copied JSON file does not: TOON 4.1.1 decodes it as one key and a string, so the round trip already rejected that passthrough |

The MarkItDown checks accept the bullet, emphasis and code-block spellings markdownify may emit,
because MarkItDown's `markdownify` and `beautifulsoup4` dependencies are unpinned. The repomix check
tests only that each signature stays and each body goes, because repomix's tree-sitter packages also
resolve at installation.

## Final harness runs

Two consecutive `--install` runs of the final harness (sha256 `3021918c…`), started by the
[`clean_env_run.sh`](../native-token-ci-extension-20260926/clean_env_run.sh) wrapper of the
2026-09-26 extension record. The wrapper cleared the environment, used a `PATH` holding only the
Node 24 runtime and system directories, refused to start if any measured tool, MCPorter or uv
resolved there, and gave each run a new empty `HOME` and `TMPDIR`.

Each run: 108 commands and 42 of 42 checks passed, 25 commands and 12 checks more than the
extension record's final runs. The 25 added commands took 0.510 seconds in the first run and 0.539
in the second. One of the 12 new checks, `markitdown-element-checks-reject-raw-and-tag-stripped-html`, is a self-check of
the oracle: it runs the element checks and the hidden-text search on the committed fixture and does
not read MarkItDown's output. The other 11 assert on what a tool returned. Each receipt still
says `failed`, with one failure: codebase-memory-mcp. This round could write only inside one long
scratch directory, so `TMPDIR` could not be as short as that tool's socket address allows, and the
harness's own `require_cbm_socket_fits` refused the fixture by design, as in the extension record.
That fixture is unchanged by this change; the hosted runner's short `/tmp` exercises it.

After each run, independently of the harness: the throwaway `HOME` and `TMPDIR` were empty, no
process was left running from the run's directory, the checkout's `git status` was unchanged, and
the entry names in the account-default codebase-memory-mcp rendezvous were unchanged. Two earlier
runs had the same outcome on a harness that differed only in one comment, which wrongly said a
copied JSON file would also pass TOON's round trip; `runs.json` keeps them without their receipts.

## Controls with the real tools

[`controls_driver.py`](controls_driver.py) installs RTK, MarkItDown, ast-grep, Repomix and TOON once
with the harness's own `--install` methods and pins, then runs the harness's fixture functions in 13
arms, each with a `HOME` inside its own work directory. Each as-harness arm must pass. Each control
changes one argument, setting or input and must fail exactly the check it targets. All 13 ended as
expected on the final harness:

| Check | Control | Observed |
| --- | --- | --- |
| `rtk-long-log-compacts-every-commit` | `rtk proxy git log -12` in place of the filtered call | Failed: git's own output |
| `rtk-long-log-ledger-records-the-filter-saving` | The filtered call recorded into another run-owned ledger (`RTK_DB_PATH`) | Failed: 0 commands and 0 saved in the fixture ledger |
| `rtk-long-log-default-window-ten-newest-commits` | `rtk git log` given `-12` | Failed: 12 commits |
| `markitdown-multi-element-structure-converted` | The same HTML bytes given as a `.txt` file | Failed: MarkItDown's plain-text converter returned the HTML |
| `markitdown-script-style-and-comment-text-dropped` | The script's text copied into a paragraph of a copy of the input | Failed: the text reached the Markdown |
| `ast-grep-shell-true-calls-match-across-lines` | The pattern without its `shell=True` constraint | Failed: all four `subprocess.run` calls (8, 12-16, 20, 24) |
| `repomix-compress-keeps-signatures-drops-bodies` | The structure pack run without `--compress` | Failed, while `repomix-structural-output-only` passed |
| `toon-tabular-encoding-smaller-than-json` | The records encoded with `--delimiter \|` | Failed: `items[2\|]{name\|enabled\|count}:`, while the strict round trip passed |

**A control that found a defect.** The first controls run ended 12 of 13: the script-text control
passed the hidden-text check. MarkItDown's markdownify escapes `_` in text it keeps
(`escape_underscores` defaults to true), so the leaked `NATIVE_CI_SCRIPT_BODY` came out as
`NATIVE\_CI\_SCRIPT\_BODY` and a literal search missed it. The markers are now letters only and the
check also searches the output with backslash escapes removed; a unit test covers an escaped leak.
The second and third runs (13 of 13 each) used the harness before a docstring edit and before the
TOON comment correction, so the fourth, on the final harness, is the record. `runs.json` keeps all
four.

## Unit tests and mutation check

`tests/test_native_token_ci.py` has 32 tests (26 before). The six new tests take each oracle from an
independent source (RTK's documented compaction rule applied to the fixture messages, Python's own
parser for the ast-grep calls, the committed HTML for MarkItDown's baselines) and require each check
to reject stand-ins for passthrough and near-miss output. [`mutation_check.py`](mutation_check.py)
weakened each new check in a scratch copy of the harness: each of the 6 mutants failed exactly the
test written for it, and the unmutated copy passed.

## Static analysis and action pins

- zizmor 1.30.1, `--offline --no-config --no-ignores --persona regular --strict-collection .`: no
  findings (42 suppressed at higher personas). At `--persona pedantic` the edited workflow has the
  same two findings before and after the edit (`anonymous-definition`, `concurrency-limits`), both
  retained with reasons in `docs/github-automation-evidence.json`.
- zizmor's online audits need a GitHub token, which this round does not read. Their inputs were
  checked through `gh api` instead: every comment's tag resolves to its pinned SHA
  (`ref-version-mismatch`), each pinned SHA is its release tag's commit (`impostor-commit`), and
  the advisory database lists no advisory for any pinned version (`known-vulnerable-actions`).
- actionlint 1.7.12 (archive checksum as in `validate.yml`): exit 0, no output.
- [`actions-latest.json`](actions-latest.json): 12 of 13 actions are at their latest release. The
  exception is `github/codeql-action/upload-sarif` at v4.38.1; v4.38.2 (2026-09-24, CodeQL bundle
  2.27.1 only) is inside the 7-day Dependabot cooldown, so the weekly Monday run of 2026-09-28 skips
  it and 2026-10-05 is the first eligible one.

## Limits

- Local runs on one host; the codebase-memory-mcp fixture did not run here (above).
- RTK's byte and ledger numbers are fixture-local estimates, not provider savings.
- Dependencies of MarkItDown, Repomix, ast-grep and the npm tools resolve at installation without a
  lockfile, as the harness's own limits state; the checks tolerate formatting variants but a future
  resolution could still change an output.
- The off-host workflows' new step has not run: their next manual dispatch is its first execution.
- No workflow step ran in these local runs. The pull request's own hosted run of `native-token-tools`
  is the step's first execution there, and a separate record.
