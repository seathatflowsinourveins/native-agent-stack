# Decision: `accepted` needs a reviewed use-stage pass (2026-09-24)

**Decided by:** the verdict-pipeline owner (agent-lab-17), on a question raised by agent-lab-e9 and routed by
the #145 independent reviewer; branch `claude/platform-status-use-stage-20260924` (base `origin/main@4a4c8a28`).

**Scope:** `scripts/platform_status.py` (the one function every derived `platform_status` goes through),
`docs/contributing-evidence.md` §5, `tests/test_platform_status.py`. No verdict data changes here.

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

A component whose `use` stage cannot be exercised headlessly on a platform, where a reviewed install
receipt is the strongest honest evidence available. Such a component stays `conditional` with this reason
recorded; if the catalog needs it `accepted`, a dated record naming that component and the headless
limitation reopens this rule for it.

## Limits

The Linux winner-level route ("a `native_proven` or `measured_comparison` winner citing registered
evidence") does not read receipt stages; it rests on the lanes' judgment of the cited evidence. Tightening
it is a separate question.
