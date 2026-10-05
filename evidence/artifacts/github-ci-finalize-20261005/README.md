# GitHub CI returned-output archive — 2026-10-05

Source: native gh 2.102.0 explicit REST GET operations, following
[cli/cli v2.102.0 API source](https://github.com/cli/cli/blob/v2.102.0/pkg/cmd/api/api.go#L103)
and [GitHub workflow-run pagination](https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository).
The [decision](../../../docs/decisions/2026-10-05-github-ci-final-state.md)
and [receipt](../../receipts/github-ci-finalize-20261005.json) explain the scope.

- `runs-YYYY-MM-DD.json`: accepted page captures plus split probes. All 11 accepted partitions are below 1,000; page counts match each server total.
- `counts.json` and `durations.json`: derived counts and 58 elapsed-duration groups. Inputs remain in the page captures.
- `current-state.json`: main SHA, effective rules, classic-protection 404, ruleset, workflow registry, main checks/statuses, open PR roster and retention.
- `main-jobs.json`: latest jobs for every non-success main run and six latest successful main workflows.
- `pr-ownership.json`, `ownership-followup.json`: selected owner PR state/files, paginated remainders and merged historical repairs.
- `pr-checks.json`, `pr-checks-recovered.json`: captured open-head checks, selected legacy statuses, failed reads and one changed-condition replacement per failed read.
- `failure-log-excerpts.json`: numbered, selective sanitized native log excerpts; includes the latest gateway-idle case passing on main.
- `macos-artifact-excerpts.json`: failure traces from four native archive GETs, read in memory without extracting files.

`native_output_gzip_base64` is the exact projected stdout compressed with gzip and encoded as base64. Decode with Python's maintained [base64](https://docs.python.org/3/library/base64.html) and [gzip](https://docs.python.org/3/library/gzip.html) APIs. Its decoded SHA-256 and byte count must match `stdout_sha256` and `stdout_bytes`. Excerpt fields similarly match `excerpt_sha256`. Parse the decoded JSON afterwards. This snippet is an inspection example, not a test runner:

```python
import base64, gzip, hashlib, json
capture = json.load(open("evidence/artifacts/github-ci-finalize-20261005/runs-2026-10-05.json"))["partitions"][0]["pages"][0]
raw = gzip.decompress(base64.b64decode(capture["native_output_gzip_base64"]))
assert hashlib.sha256(raw).hexdigest() == capture["stdout_sha256"]
data = json.loads(raw)
print(data["total_count"], len(data["workflow_runs"]))
```

Census projection omits actors, author/message metadata and associated PR objects. Raw logs and archives are withheld; their hashes alone do not recover their bytes. Excerpts remove ANSI, home paths and email addresses where specified. Some selections are truncated, with that fact retained. Later calls use `<installed-gh-2.102.0>` in place of the verified installed executable path; this is the only argument redaction. Repository-root working directory resolves from the private lane status.

All six retained nonzero native calls are distinct from CI conclusions: a classic-protection 404 and five transient executable-lookup failures. Failed replacements and early collection/parser limitations are described in the receipt. GitHub registry presence includes branch-only workflows and does not prove main adoption. Historical executions remain platform observations; this archive runs no workflow, model or new acceptance test.

Decoded publication review applies the repository's `scripts/validate.py` patterns to every payload. UUID matches are public Socket SBOM links and StepSecurity job-correlation IDs returned by public checks/logs. They are retained as source identifiers; no other private-content pattern matched. The three pre-publication GETs in `current-state.json` preserve the newer main head and #714 merge separately from the original census and gate observations.
