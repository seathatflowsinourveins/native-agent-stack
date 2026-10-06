# hcom relaxation: native-checker probe receipt (2026-10-06)

This folder retains the probe behind
[the hcom relaxation decision](../../../docs/decisions/2026-10-06-hcom-relaxation.md).
The probe ran at 13:11:32Z. The evidence class is **synthetic**: the real
installed `codex-cli 0.160.1` and `jq 1.8.1` ran on frozen fixtures. It is not a
native hcom run, a cross-client E2E or host acceptance.

| File | What it is |
|---|---|
| `hcom.rules` | Synthetic upstream-format rules (sha256 `2a667dcb60c745ea954cba620b066a118b6721e6c8c3fda150b35e5e6eb86ada`). It is what `build_codex_rules` writes for the prefix `["hcom"]` at aannoo/hcom@2c5f343b2f9ec4bf2acf49c0431860e7c2ae578b: `src/hooks/codex.rs:1538-1563`, over `SAFE_HCOM_COMMANDS` (`src/hooks/common.rs:52-72`) and `HCOM_TOOL_NAMES` (`src/hooks/codex.rs:569-576`). No `hcom codex` launch wrote it. |
| `probe-receipt.json` | The actual results: every argv, environment (sanitized), UTC start and finish time, exit code, stdout and stderr. |

The receipt has two parts.

**Native-checker probes**
- `codex execpolicy check --pretty` over `hcom.rules` alone gives `allow` for `hcom send @luna -- hi` and for `hcom term inject luna hi`, and no decision for `hcom kill luna`.
- With the retired plan file added, the result for `hcom term inject` is `forbidden`. That file is `../token-stack-fresh-session-e2e-20261004/fixtures/hcom-deny.rules`, sha256 `ac6254ee…`, the same bytes as the plan's `config/hcom-deny.rules` at ecfa11276.
- The checker exits 0 for every decision and reports the decision in its JSON.

**After-sign-in runs**
- The agent-messaging after_sign_in program is taken from `install-plan.json` (program sha256 `5205ab90…`). `check_plan.py` keeps it byte-equal to `accept.sh`.
- It ran as `bash -euo pipefail -c` in 8 scratch homes, and every exit code matched its expectation:
  - 78 with no rules file;
  - 0 with `hcom.rules` only;
  - 78 with the retired `hcom-deny.rules` beside it;
  - 0 when `HCOM_DIR` is custom and `CODEX_HOME` is unset;
  - 78 when the rules exist only under `$HOME/.codex` while `HCOM_DIR` points elsewhere;
  - 0 when an explicit `CODEX_HOME` is set;
  - 78 when the 52 retired Claude hcom deny entries remain;
  - 0 with only the 134 deny entries of the Claude settings template.

**Isolation and sanitization**
- Every run had a scratch `HOME` under `env -i`, so no client home, rules directory or settings file of the host was read or written.
- Scratch paths read `<scratch>` and the checkout reads `<checkout root>`.
- The stderr lines are codex's own notice that it would not create PATH helper binaries under `/tmp`.

**Version note.** The plan targets Codex 0.160.0, and the probe used the installed 0.160.1. rust-v0.160.1 is rust-v0.160.0 plus two commits that touch no exec-policy file; its release notes describe a Windows remote-MCP environment backport (`gh api repos/openai/codex/compare/rust-v0.160.0...rust-v0.160.1`, read 2026-10-06). So the rules loading cited at rust-v0.160.0 (`codex-rs/core/src/exec_policy.rs:662-700`, `:1121-1170`) applies to the binary that ran.

**Reproduce.** From the checkout root, run each argv recorded in the receipt with `env -i HOME=<an empty directory> PATH="$PATH"`. For the after-sign-in runs, lay out each scenario's files under a scratch directory and run the recorded program there.
