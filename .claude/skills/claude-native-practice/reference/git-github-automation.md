# GitHub automation (`git-github-automation`)

Client 2.1.295, checked 2026-10-09. Index: [slots.md](slots.md).

## github-action

**Status:** default. **Default:** anthropics/claude-code-action at commit 2dca132ff0e0c4094ce6048b422c6915a071210b (v1.0.247)

- **Route:** Workload identity federation only; dispatch-only or variable-gated jobs; explicit `--model` and `--effort`; read-only tools with `--restricted`; `ACTIONS_STEP_DEBUG` pinned false and debug settings refused before any token; `execution_file` never published; WIF inputs include the optional `anthropic_oidc_audience`; cost levers are `--max-turns`, job timeouts and concurrency controls (`--max-budget-usd` caps a client-side estimate)
- **Alternatives, ranked:** 1. Managed Claude Code Review (GitHub App)
- **Rejected:** anthropics/claude-code-security-review (no commit since 2026-02-11); Mutable action refs; Run-time plugin installation in the action
- **Evidence:** github-actions-A1 to A10 (L3 requirement rows); action.json R1-R8
- **Notes:** Converged in all three selections (both families and the owner's sweep). Main moves from v1.0.245 when #892 lands. Rejected route, recorded: the subscription OAuth token (cheaper, but a long-lived token tied to one person's subscription); WIF spend is API billing.
- **Supersedes:** M45 (adopted on main); Action-pinning topic
- **Overturn when:** A new action release changes authentication or output defaults, or a hosted run fails a requirement row.

## pr-review-pre-cue

**Status:** default. **Default:** pr-review-toolkit pre-cue (pr-test-analyzer and silent-failure-hunter): locally in J8 and in Actions through #909

- **Route:** Runs before a landing cue; findings at confidence 80 or above go to the lane
- **Alternatives, ranked:** 1. Native `/code-review` at max effort (paired same-delta run owed, J7 class D)
- **Rejected:** Ultrareview as an automated default (user-triggered and billed; the owner's option for high-stakes PRs)
- **Evidence:** Measured: at or above 80, defects both designated reads missed on #892 (9), #894 (6), #895 (7), #896 (3) and trading #11 (2); $3.3-5.5 per run (J8 defects record)
- **Notes:** Ultrareview from a script runs as `claude ultrareview <PR#> --json`; `claude -p '/code-review ultra'` exits without findings.
- **Supersedes:** M42; M31
- **Overturn when:** The paired same-delta run shows `/code-review max` matching or beating the toolkit on confirmed findings at equal quality.
