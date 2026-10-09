# Sweep commit references in the code-search token rule

The pinned gitleaks 8.30.1 `sourcegraph-access-token` rule accepts a legacy bare 40-hex form as well as modern `sgp_` forms. A scanner comparison in the sweep records activates that rule on unrelated public Git commit references. Five git-mode findings remain in commit-source descriptions and retained notes; the directory scan is independently clean.

Gitleaks v8.30.1 defaults to recursive decode depth 5; [detect/codec](https://github.com/gitleaks/gitleaks/tree/v8.30.1/detect/codec) restores Unicode and percent spelling before detection runs again, which is why JSON re-encoding could not remove these matches while preserving the parsed records.

The change retains `extend.useDefault = true` and all existing rules and exceptions. One additional allowlist applies only to `sourcegraph-access-token`, with `condition = "AND"`: the path must match one of the two sweep-record families and the decoded line must match one of the two public commit-reference contexts. The exact path families are:

- `^catalogs/sota-convergence/manifest-[0-9]{8}-[a-z-]+\.json$`
- `^evidence/artifacts/landscape-sweep-[0-9]{8}-[a-z-]+/returns\.json$`

The line conditions cover a GitHub commit URL with its branch/date maintenance description, and a GitHub API commit-check result with its returned identifier and date. The native regression cases require modern token forms to remain detectable, including on a line containing a commit reference. The exception does not extend to other rules or paths, and `.gitleaksignore` remains unchanged.

Path and line restrictions both matter: a line-target condition cannot identify which hexadecimal value matched, and Go's RE2 syntax has no lookahead. These path families contain public research records; the same line in an application file remains a finding.

## SOTA sources

- [gitleaks/gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/tree/v8.30.1), `config/gitleaks.toml`: the inherited legacy/modern token rule and keywords.
- [config/allowlist.go](https://github.com/gitleaks/gitleaks/blob/v8.30.1/config/allowlist.go) and [config/config.go](https://github.com/gitleaks/gitleaks/blob/v8.30.1/config/config.go): native path/regex conditions and extension behavior.
- [detect/detect.go](https://github.com/gitleaks/gitleaks/blob/v8.30.1/detect/detect.go) and [detect/codec](https://github.com/gitleaks/gitleaks/tree/v8.30.1/detect/codec): fragment keyword filtering, recursive reconstruction and mapped finding context.

The regression suite in `tests/test_gitleaks_record_commit_context.py` uses the actual pinned binary against synthetic Git repositories, with native recursive decoding and redaction. Its fixtures cover the five observed record shapes, legacy token-like text without commit context, commit-reference text outside the allowed paths, and modern token forms across paths and encodings. Validation results are recorded after those native runs; no matched values are included in this decision.

The new module passed all five tests through gitleaks 8.30.1 with no skips. Its upstream-default control first detects all five synthetic record shapes; the scoped policy then exempts them. Bare identifiers without commit context and commit-reference lines outside the permitted paths remain findings. Modern candidates remain findings in plaintext, Unicode and percent spelling, including on the same line as a commit reference; native finding columns cover the modern candidate itself. Native recursive decoding is retained throughout.
