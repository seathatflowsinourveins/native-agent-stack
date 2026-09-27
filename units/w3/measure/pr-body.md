## Summary

PR-A of the #381 token-adoption E2E. The branch extends the existing WP4
transcript tools with the preregistered measurement kernel: M3/M5 result
sizes, M4 fetch routing, RTK part eligibility for M-R1/M-R3/M6c, hook-context
claims versus insertion, MCP attempt states and per-message provider usage.
The Claude lane (`child-usage.mjs`) and the Codex lane (`skill_usage.py`,
through a Node bridge) share one kernel. This is measurement tooling: full
PR-A acceptance (M1, M15 and the other items under Residuals) and any E2E
savings claim remain open.

The last round (fixup3, 2026-09-27) repairs the four findings of the Opus
verification of fixup2 (verdict `block`): M4 heredoc resolution (D1, high),
the workflow checksum file (D2), offset-exact possible-fetch accounting (D3)
and this body (D4). It also adopts the verifier's recommendation 6: raw
`curl`/`wget`/`gh api` misses now count as possible fetches, like
`HTTP_SCRIPT` misses, so a parser false negative on these patterns cannot
raise the M4 lower bound.

## Changes

Whole branch (15 files, base `341ba641`):

- `examples/claude-native/workflows/child-usage.mjs`: the kernel. M3/M5 count
  UTF-8 content bytes per carrier (text blocks without wrappers), minus
  witnessed exceptions from a digest-bound private sidecar. M4 counts
  confirmed remote fetches per carrier, including nested ctx and Codex
  sandbox fetches, and reports `routed_share`, `fetch_mentions_unconfirmed`
  and `routed_share_lower_bound`. `rtk_parts` replays native
  `rtk hook check` (RTK 0.50.0) per simple part for M-R1 coverage; the
  deterministic M-R3/M6c zero counter is separate from advisory log/find
  review, and proxy parts are outside eligibility. Hook-context claims,
  inserted context, MCP states and per-message usage are reported
  separately. A sweep reports main transcripts apart from the child
  population, which stays comparable with the #369 receipt.
- `tools/skill-usage/skill_usage.py`: the Codex adapter onto the same kernel.
  Function, custom and local-shell calls pair with their outputs; code-mode
  nested operations stay out of context bytes; MCP state falls back to the
  native item status; Codex measurements omit the Claude `usage` object.
- `tests/test_token_measurement.py` and `tests/test_skill_usage.py`: synthetic
  controls for both lanes.
- `examples/claude-native/workflows/test-child-usage.mjs`: one assertion now
  treats stdout-only hook context as a claim, never proof of insertion.
- `examples/claude-native/workflows/README.md` and `tools/skill-usage/README.md`:
  counter definitions, the gate reading and the limits.
- `examples/claude-native/workflows/SHA256SUMS`: checksums of the changed
  workflow files.
- `manifests/evidence.json`: coordinator registration of the branch files
  (hot file; this round's content changes need re-registration).
- `units/w3/measure/`: builder commit handoffs (`commit-*.txt`), dated
  receipts (`fixup-receipt.md`, `fixup2-receipt.md`) and this body.

This round (fixup3):

- **D1.** A heredoc body is source only when the simple command that contains
  its `<<` operator runs stdin as source. That command is the text between
  the nearest control operators around the operator, with quotes removed and
  redirections and their targets dropped. `bash <<'EOF' 2>&1 | tail -n 5`,
  `bash <<'EOF' > log.txt`, `&&`/`;` suffixes and `python3 - <<'EOF' | tail`
  therefore keep their executed bodies. Shells follow POSIX sh STDIN and
  bash(1): `-c` or a script operand leaves stdin as data, `-s` keeps it, a
  shell's `-` equals `--`, `-o`/`+o`/`-O`/`+O` take a name,
  `--rcfile`/`--init-file` take a file, and `-n` reads without executing.
  `ssh` runs stdin in the remote login shell when no remote command follows
  the destination, or when the remote command reads stdin as source; `-n`,
  `-f`, `-N`, `-s`, `-W`, `-O`, `-G`, `-V` and `-Q` never do. A `<<` inside
  quotes, a comment or `$(( ))` opens no heredoc, and one inside a quoted
  string that a shell runs is left to the quoted-string recursion. The legacy
  `fetchKind`/`lanes.fetch.bash_curl_wget` counter again follows the workflows
  README's description (heredoc bodies count under `ssh` or a shell heredoc).
  The source comment that claimed unknown option forms stayed possible
  fetches for every detector is replaced.
- **Recommendation 6.** `fetch_mentions_unconfirmed` also counts raw
  `curl`/`wget` in command position and raw `gh api` matches that
  executed-text analysis did not confirm. Both READMEs document it.
- **D3.** The executed-text analysis keeps each character's raw offset. An
  executed match confirms only the raw match at its own raw offset, anchored
  at the call name, the `curl`/`wget` word or `gh`. Matches created by
  backslash-newline joins, unescaping or quoted strings a shell runs cannot
  offset a raw miss. The exported `executedText` string API is unchanged.
- **D2.** `SHA256SUMS` is regenerated with the documented
  `sha256sum -- *.mjs *.js *.json` (13 entries; `README.md` removed).
- **D4.** This single body replaces both earlier bodies.

### M4 scope

- `routed_share = ctx_fetch_and_index / remote_fetches` uses confirmed
  fetches.
- `routed_share_lower_bound = ctx_fetch_and_index / (remote_fetches +
  fetch_mentions_unconfirmed)` treats every possible fetch as unrouted.
  **The #381 M4 >= 0.9 gate must read `routed_share_lower_bound`, computed
  from the integer counts**; reported shares are rounded to four decimals.

Possible fetches are raw `HTTP_SCRIPT` matches anywhere in the command or
code, raw `curl`/`wget` in command position (a line start, or after `;`, `&`,
`|`, `(`, a backtick or `$(`, also behind a shell keyword or wrapper) and raw
`gh api` at a line start or after a separator. They include data-only
mentions such as a heredoc that writes a script; those lower the bound
conservatively and leave M4 status `incomplete`. In neither count: a `curl`
inside a quoted string the parser does not treat as run
(`ssh -o Opt=value host 'curl ...'`, `watch 'curl ...'`), behind `xargs`,
`find -exec` or an unrecognized wrapper, or passed to a subprocess inside
interpreter code; loops, dynamic code, external scripts and aliases.

## Evidence

Classes: synthetic fixtures (static transcript analysis; no fixture command
is executed), local integration (unit and contract suites, the native RTK
hook check), and local measurement (an installed-shell probe whose heredoc
bodies only `echo`). No live provider execution and no unchanged upstream
test suite. Returned outputs are retained in the coordinator's unit notes
(`fixup3/`).

**Verifier reproduction** (verify-fixup2, "Verification gaps"). Columns are
`fetchKind`, `shell_fetch`, `unclassifiable` and
`fetch_mentions_unconfirmed`:

| Module | Rows 1-4 | Row 5 | Row 6 |
| --- | --- | --- | --- |
| `71c0a991` (before) | `null 0 0 0` | `null 0 0 1` | `null 0 1 0` |
| `e7d3c5a3` | `"fetch" 1 0 undefined` | `null 0 1 undefined` | `null 0 1 undefined` |
| fixup3 | `"fetch" 1 0 0` | `null 0 1 0` | `null 0 1 1` |

The verifier's predicted table held exactly for both earlier revisions; row 6
at `e7d3c5a3` had no prediction.

**Failing first.** The final `tests/test_token_measurement.py` run against the
`71c0a991` module returned `Ran 38 tests`, `FAILED (failures=145)`, exit 1.
All 145 subtest failures are in the five new tests (66, 36, 12, 9 and 22
subtests), and the 33 existing tests pass. The new tests are
`test_m4_heredoc_resolves_its_whole_simple_command_on_every_carrier`,
`test_m4_unexecuted_heredoc_curl_wget_and_gh_api_stay_possible_fetches`,
`test_m4_heredoc_openers_respect_quotes_comments_and_arithmetic`,
`test_m4_confirmations_trace_back_to_raw_offsets` and
`test_fetch_kind_and_legacy_lane_follow_the_heredoc_resolution`. They cover
every shape the verifier listed on all three shell carriers plus `fetchKind`
and the legacy lane counter.

**Fixup3 results:**

- `python3 -m unittest -v tests.test_token_measurement`: `Ran 38 tests`, OK,
  no skips. The RTK replay controls therefore ran (Linux, `rtk 0.50.0`).
- `python3 -m unittest tests.test_token_measurement tests.test_child_usage_suite
  tests.test_skill_usage tests.test_adoption_docs_consistency.RelativeLinkTests
  tests.test_adoption_docs_consistency.ScriptPathTests`: `Ran 143 tests`, OK,
  exit 0.
- Node suites: `test-child-usage.mjs` 92/92, `test-envelope.mjs` 254/254,
  `test-contract-mutations.mjs` 74/74; `check-syntax.mjs` and `node --check`
  exit 0.
- Differential check: old versus new `executedText` (both modes) and
  `fetchKind` over the 198 commands the covering tests feed the kernel. 171 are
  identical; the 27 that differ are exactly new D1 controls. A fuzz of 80,000
  heredoc-free inputs gave 0 mismatches. Trace integrity over 40,288 inputs
  (1,028,897 traced characters) gave 0 offset violations.
- `sha256sum --check --strict SHA256SUMS`: 13 OK, exit 0. `git diff --check`:
  exit 0.
- Installed-shell probe (GNU bash 5.2.21, dash 0.5.12). Stdin ran for
  `bash -euo pipefail`, `-oe pipefail`, `+o pipefail`, `-O extglob`,
  `+O extglob`, `--norc`, `--rcfile /dev/null`, `-s`, `-s arg`, `-`, `--`,
  `sh -e`, `dash -o nounset`, and the `2>&1 | tail -n 5` and `> log.txt`
  suffixes. It did not run for `-n`, `-s -c`, `-c cat` or a script operand,
  including one after `-`.
- `python3 scripts/validate.py`: exit 1, with SHA-256 and byte-count
  mismatches for exactly the six inventory-registered files this round
  changes: the workflows `README.md`, `SHA256SUMS` and `child-usage.mjs`,
  `tests/test_token_measurement.py`, `tools/skill-usage/README.md` and
  `units/w3/measure/pr-body.md`. The coordinator re-registers them;
  `manifests/evidence.json` was not edited.
- Full suite, `python3 -m unittest -q` with `TMPDIR=/var/tmp/claude-measure`:
  `Ran 6685 tests in 699.400s`, `FAILED (failures=2, errors=1, skipped=761)`,
  exit 1 (the 6,680 tests at `71c0a991` plus the five new ones). Two are this
  host's known environment failures for a worktree under `/tmp`:
  `test_order_throughput` `test_cli_refuses_live_base_url_from_env_file_without_network`
  (`credential_file_permissions:worktree`) and `test_gpt6_family_tiering_20260926`
  `test_sigterm_records_the_running_call_as_interrupted_without_counting_it`
  (the temporary directory must lie outside every repository). The third,
  `test_catalog_freshness_propose`
  `test_general_publication_validator_passes_after_the_run`, is the same
  publication validation on the then-uncommitted changes to five registered
  files. There is no other failure. Only this body's text changed after the
  run.
- Pin check: in a local upstream clone of mksglu/context-mode (133 commits past
  the tag), tag `v1.0.169` resolves to
  `589d8214d56740a28b5f7bf63167743d586b0b40`. `hooks/core/routing.mjs` at the
  tag and in the installed source share blob
  `e92ab46b2faf6597789bdc5eb3a5a90460d9da3c`.

**Dated history (all 2026-09-27):**

- Build `5139fdf5` (GPT-6 builder): 117 covering tests passed.
- Repair `6b0f31a4`, after an independent review with eleven findings: 130
  covering tests, 92 Node checks and 13 workflow checksums passed.
- Fixup `e7d3c5a3`: interpreter heredocs and quoted interpreter code kept in
  the M4 denominator (`fixup-receipt.md`).
- Fixup2 `c60899f7`: ignored stdin, `fetch_mentions_unconfirmed` and
  `routed_share_lower_bound`; 133 covering tests passed
  (`fixup2-receipt.md`). The builder's own full-suite attempt, with TMPDIR
  inside the repository, returned 6,656 tests with 247 failures, 151 errors
  and 783 skips. Its retained errors included fixtures that require
  temporary state outside every repository; the complete failure inventory
  was not retained, and the run was never acceptance.
- Coordinator acceptance at `71c0a991`: `validate.sh` FAILS=0; full suite
  `Ran 6680 tests in 717.989s`, OK (skipped=761).
- Opus verification of fixup2: `block` (D1 to D4, recommendation 6).
- Fixup3: this round, results above.

## SOTA sources

- #381 contract: `evidence/artifacts/token-adoption-e2e-20260926/` README,
  RUNBOOK and `preregistration.json` M4 (all remote fetches including nested
  and unclassifiable ones, routed rate >= 0.9, unclassifiable rate <= 0.1,
  unknown excess `incomplete`). The lower bound is the requested local
  extension of that contract, not an upstream parser feature.
- mksglu/context-mode **v1.0.169** (`589d8214d56740a28b5f7bf63167743d586b0b40`):
  [heredoc stripping, routing.mjs:228-229](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L228-L229),
  [curl/wget and inline-HTTP routing, routing.mjs:727-804](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L727-L804),
  the mandated [detector reference, routing.mjs:788-795](https://github.com/mksglu/context-mode/blob/v1.0.169/hooks/core/routing.mjs#L788-L795),
  and [UTF-8 accounting, extract.ts:1060-1069](https://github.com/mksglu/context-mode/blob/v1.0.169/src/session/extract.ts#L1060-L1069).
- Shell and ssh semantics:
  [POSIX.1-2024 sh](https://pubs.opengroup.org/onlinepubs/9799919799/utilities/sh.html)
  OPTIONS, OPERANDS and STDIN;
  GNU bash 5.2 bash(1) OPTIONS, ARGUMENTS, DEFINITIONS, RESERVED WORDS,
  QUOTING, COMMENTS, REDIRECTION, Here Documents and ARITHMETIC EVALUATION
  (the installed 5.2.21 manual page; the GNU online manual timed out on
  2026-09-27); [OpenSSH ssh(1)](https://man.openbsd.org/ssh), which the
  installed OpenSSH 9.6p1 manual page matches.
- Interpreter entrypoints:
  [Python 3.13 interface options](https://docs.python.org/3.13/using/cmdline.html#interface-options)
  and [Node v24.21.0 stdin](https://nodejs.org/docs/v24.21.0/api/cli.html#-).
- rtk-ai/rtk **v0.50.0** (`1d87b8e719ce0a50c223cd93ca64dd16921f9aec`):
  [hook check](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/main.rs#L2940-L2952),
  [lexer](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/lexer.rs#L488-L526)
  and [consumer rules](https://github.com/rtk-ai/rtk/blob/v0.50.0/src/discover/registry.rs#L1087-L1494).
  These identify the reference implementation, not the installed binary build.
- openai/codex **rust-v0.157.1**:
  [calls and outputs](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/protocol/src/models.rs#L1060-L1165),
  [code-mode emission](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/tests/suite/code_mode.rs#L721-L760)
  and [MCP item status](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/app-server-protocol/src/protocol/v2/item.rs#L333-L352).
- ccusage **v20.0.24** (`ecb676cce27cb5dd0090c7804a5cecc35e8ba805`):
  [Claude per-message deduplication](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/claude/src/daily.rs#L410-L523)
  and [Codex baseline deltas](https://github.com/ccusage/ccusage/blob/v20.0.24/rust/adapters/codex/src/parser.rs#L153-L350).

## Residuals and not done

- **M1 per-lane eligibility:** attempt, load and insertion counters do not
  compute successful opportunities among eligible tasks separately for every
  required lane (`RUNBOOK.md:564`).
- **M15 infrastructure errors:** MCP attempt states do not separate
  infrastructure errors from invoked-command nonzero exits or establish the
  per-server error ceiling (`RUNBOOK.md:582`).
- **Other PR-A items:** CLI lane counters and mcporter downstream attribution;
  JSON/uniform-tabular classification; final-return quality classification;
  a private native-ID ledger for rejected, cancelled and unfinished execution;
  Codex inherited-versus-injected markers, custom-role grouping, spawn fork
  metadata and provider-verified routes; frozen historical baselines, task
  identity joins, matched A/B comparisons and actual E2E acceptance.
- **M4 static limits:** see M4 scope. Shapes the heredoc resolution still
  leaves as data count only through the raw patterns: `sudo -u user bash`,
  `docker exec`/`kubectl exec` and other unrecognized wrappers,
  `{ ...; } <<EOF`, a backslash-newline continuation before the opener,
  `<<\EOF` and `$'...'` quoting, Python `-W`/`-X` or Node `--input-type`
  before stdin, and zsh- or ksh-specific options. The Python shift-syntax and
  Node comment-apostrophe misses remain possible fetches.
- **Python mirror:** `tools/skill-usage/skill_usage.py:690-726` still cites
  the removed `programOf`. Its legacy Codex `fetch_kind` now differs from the
  Claude lane on `-c`, `-n`, `ssh -n`, `bash - script.sh` and a `<<` inside
  quotes or comments. M4 itself is unaffected, because the Codex lane uses the
  Node kernel.
- **Code mode:** the outer Codex code-mode `exec` code
  (`skill_usage.py:957`) is not scanned for fetches.
- RTK binary-hash attestation, live provider/E2E measurement, semantic
  sidecar witness review and ambiguous interleaved or resumed code-mode
  associations remain outside this branch. The shared sandbox bucket does
  not establish exclusive context-mode use.
- **Publication:** this round changes six registered files; the coordinator
  re-registers them in `manifests/evidence.json` and regenerates reports.
  The base `341ba641` is behind main `364f4d94`, so the hot file follows the
  `docs/lanes.md` protocol at merge.

## Recommended lane label

`lane:foundation`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
