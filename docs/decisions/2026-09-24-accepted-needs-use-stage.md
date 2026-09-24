# Decision: `accepted` needs a reviewed use-stage pass (2026-09-24)

**Decided by:** the verdict-pipeline owner (agent-lab-17), on a question raised by agent-lab-e9 and routed by
the #145 independent reviewer; branch `claude/platform-status-use-stage-20260924` (base `origin/main@4a4c8a28`).

**Scope:** `scripts/platform_status.py` (the one function every derived `platform_status` goes through),
`scripts/host_receipts.py` (what a `use` receipt must run), `scripts/component_matrix.py`,
`scripts/verdict_flip_candidates.py`, `docs/contributing-evidence.md` §2, §3 and §5, and their tests. No
verdict data changes here.

## Decision

A host receipt makes a winner `accepted` on a platform only when it is an independently reviewed
`native_proven` pass at stage `use` (with the existing pin, second-machine, review and platform-identity
conditions). The same receipt at stage `install` supports `conditional` at most, with the reason
"independently reviewed install-stage pass; accepted needs a reviewed use-stage pass". A `native_proven`
fail at either stage still blocks, as before.

## Evidence

- `QUALIFYING_STAGES = {"install", "use"}` let one reviewed install pass decide `accepted`. An install
  receipt is honest `native_proven` under `docs/contributing-evidence.md` §2 when it records a version call
  (`gitleaks version`, `dagu version`), so with #160's second-machine receipts a Linux or macOS winner could
  move from `conditional` to `accepted` on a `--version` call alone.
- A version string shows the binary resolves at the pin; it does not show the component performs its
  layer's job, which is what the catalog's `accepted` is read as meaning.
- `tests/test_platform_status.py::test_a_reviewed_install_pass_alone_is_conditional_on_either_platform`
  fails on the previous rule (both platforms `accepted`) and passes on this one (`conditional`, then
  `accepted` once a reviewed use pass is added).

## Alternatives considered

1. **Keep install as qualifying** (previous rule): rejected; `accepted` would not imply the component was
   exercised.
2. **Use only (chosen):** an install pass still counts towards `conditional`; a use pass implies the
   component was installed.
3. **Require install and use together:** rejected as extra receipts without extra evidence, since a use
   pass already implies an install.

## Comparison that would overturn it

A measured comparison showing that install evidence predicts use would overturn the rule. It needs at
least 10 winners, each with a reviewed install pass and a reviewed functional use receipt recorded on a
second physical machine, and no use receipt failing after its install passed. That result would show the
use stage adds no information and would restore install-stage acceptance. A single use fail after a
reviewed install pass keeps the rule.

For a component whose `use` stage cannot run headlessly on a platform, where a reviewed install receipt is
the strongest honest evidence, the comparison is per component. A dated record names the component, the
headless limitation, and a manual or scripted functional check whose reviewed pass stands in for `use`. It
does not reopen install-stage acceptance for other components.

## Follow-up (2026-09-24, #164 review items 1-5, and the Codex re-check of be09a5e2)

- `use` is defined in `docs/contributing-evidence.md` §2 as the component doing its job; a help or version
  call is never `use`. The control is the independent review: step 8 tells the reviewer to record
  `needs_changes` on a `use` receipt whose commands are only help or version calls, however wrapped, and a
  standing dissent withholds `accepted`.
- No status is derived from command text. be09a5e2 had `validate` reject help-only `use` receipts and the
  receipt summary count them as `install`. The Codex re-check showed that classification was neither sound
  nor complete. `sh -c 'rtk --version'`, `true && rtk -V` and `rtk help gain` passed as `use`, while
  `du -h /dev/null` was refused. Worse, counting a misread functional `use` fail as `install` let a later
  install pass stop it blocking, which promoted `conditional` to `accepted` in 44 of 82,944 synthetic
  comparisons. Both were removed. `record` keeps a narrow lint: it refuses `--stage use` only when every
  command is exactly a program and one of `--help`, `--version`, `-V`, `help` or `version`. `-h` is left
  out because `df -h` and `du -h` are functional. The lint is a documented convenience, not a control.
- The documented recording examples pass a functional `--cmd`, because the stack.json commands for
  `ccusage` and `agentsview` are `--help` calls.
- `component_matrix.build_alternative` marks an alternative `host_verified` only on a reviewed use pass.
- `QUALIFYING_STAGES` is renamed `BLOCKING_STAGES`, and `verdict_flip_candidates.py` reports
  `supporting_receipts`.

## Limits

The Linux winner-level route ("a `native_proven` or `measured_comparison` winner citing registered
evidence") does not read receipt stages; it rests on the lanes' judgment of the cited evidence. Tightening
it is a separate question.
