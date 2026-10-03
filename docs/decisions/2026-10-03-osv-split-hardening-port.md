# OSV split-scan hardening port (2026-10-03)

North-star action: keep the foundation dependency gate reliable for the research
stack without widening historical archive exceptions to active inputs.

Port the review-7 policy fixes from native-agent-stack PR #555, pinned head
`8c263acebe7396c09d66d9d4f70bf144e1c4cdd3`, onto the existing three-scan shell and
recording-double harness at base `cac8700ba914950266272347468bff7ad630a4bf`.
Keep #622's status propagation and the retired WSL partition intact. The source
and executions are bound in
[`osv-split-hardening-port-20261003.json`](../../evidence/receipts/osv-split-hardening-port-20261003.json).

The existing harness misses a second `--config`, and the policy accepts an
`ID` alias beside `id` and an npm regex override. The pre-edit R1 and R4 controls
survive. R2's omission and R3's dropped SARIF statuses are already caught; retain
those checks. Extend this harness with eleven contract mutations, an inline
duplicate-config variant, and an assertion that every scanner invocation has
exactly one config option in either spelling. OSV's tagged configuration docs
also document `--config=path`; counting both forms closes the same duplicate
option gap. Keep tests that execute the
step outside its own preflight classes to avoid recursive execution.

The maintained sources are
[OSV-Scanner v2.6.0 configuration](https://github.com/google/osv-scanner/blob/v2.6.0/docs/configuration.md),
[`Manager.Get`](https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/manager.go),
[`ShouldIgnore` and override matching](https://github.com/google/osv-scanner/blob/v2.6.0/internal/config/config.go),
and its [go.mod](https://github.com/google/osv-scanner/blob/v2.6.0/go.mod), which
pins [BurntSushi/toml v1.6.0 decode.go](https://github.com/BurntSushi/toml/blob/v1.6.0/decode.go).
OSV's tag resolves to `e840a6e8adb14b7777c78e26cfbf6e2abc1d1fc6` and the TOML
tag to `52534926c55b4cd85b05aee90569dd0668b8cf30`. An explicit OSV config reaches
every input; an ecosystem-less override reaches every ecosystem. TOML struct
field matching ignores key case, and `id`/`ID` can target the same field; source
does not establish which value wins. Rejecting ecosystem `NPM` is defensive
project policy: OSV's native ecosystem comparison is case-sensitive.

The later macOS and WSL uploads use their own `!cancelled()` guards, following
[GitHub's status-check functions](https://docs.github.com/en/actions/reference/workflows-and-actions/expressions#status-check-functions)
(reviewed docs revision `b32e08ff7345b996e5bb059bfd5bfc11d08bcc36`). This permits
each later report after an earlier upload fails.

Alternatives: retaining name-only checks misses regex and unrestricted overrides;
replacing main's harness with #555's two-scan runner loses the current WSL and
preflight coverage; relying only on OSV's undecoded-key check misses recognized
case aliases. Retain the native scanner for scan acceptance and the repository
harness for caller policy, with evidence classes separate.

Overturn this decision when a maintained OSV revision rejects case aliases and
scopes explicit overrides to exact paths, with native controls showing the
same boundaries, or a smaller harness detects all eleven contract mutations
and the inline duplicate-config variant without
re-entering the preflight. Removing an archive requires its config, inventory
key, policy row, scan, SARIF report, upload, exact `jq -e` assignment and both
non-empty guards to be removed together.

Completeness critic: configuration scope, parser key matching, package regex and
ecosystem filters, upload failure paths, primary/SARIF errors, PR behavior,
inventory omissions and guard removal are covered. The unchanged four-case
historical verifier still describes two groups; its actual returned output and
limits must remain visible beside the separate current three-scan native run.
Hosted uploads, exact-head CI and independent Opus review belong to the
coordinator under the sandbox addendum.

The builder correction log is retained in the new receipt and
`evidence/artifacts/osv-split-hardening-port-20261003/builder-attempts.json`.
It distinguishes the reported historical verifier hash from the helper's actual
hash and records the two observation/import failures before their repairs.
Exact native Git blob reads and the subsequent returned command outputs verify
the corrections; missing original timestamps and usage remain unknown.
