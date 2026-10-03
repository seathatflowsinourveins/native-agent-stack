# Inactive historical WSL retrieval lock

The September 20 WSL retrieval record is incomplete historical evidence. Its
experiment remains `defer`, with no qualification runs. Its immutable lock pins
QMD 2.8.3 → fast-glob 3.3.3 → micromatch 4.0.8 → braces 3.0.3.

The [advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) describes stack
exhaustion from attacker-controlled deeply nested brace patterns. At the
2026-10-03 source refresh the advisory was Unreviewed, the
[official registry](https://registry.npmjs.org/braces) still listed 3.0.3 as latest,
and [upstream PR 72](https://github.com/micromatch/braces/pull/72) remained open.
This decision does not declare the package safe or determine deployed QMD exposure.

The current `run.py` refuses QMD mode immediately after argument parsing, before
platform checks, umask, directory creation, copying or subprocess launch. An
independent read-only archive preflight then checks the current recorder hash,
strict metadata, immutable inputs and expiry before any recorder mode proceeds.
Removing only the QMD refusal still fails this second barrier before effects.
Offline historical audit remains available. The original future recorder is preserved
byte-exact as `run-future-before-archive-20261002.py.txt`, SHA256
`be852ce99501f5bc4567b846b90fb0e91d91de77b0eafbd3b72bb4484a2f7d12`.
Both previously executed runner archives, all receipts, historical verification,
experiment, pins, package manifests and lock remain unchanged.

The versioned `archive-policy-20261002.json` permits exactly one historical
evaluation attribution: unchanged `experiment.json` SHA256
`a029dc2d8de56dd387202e5bffc341ad9d0a163e93f7bc01954b932f4ecf0244`,
JSON pointer `/frozen_inputs/evaluation/3`, original `run.py`/`be852…` pair, to the
inert snapshot with the same bytes. It separately binds the current guarded
recorder. `validate_convergence.py` reports this mapping explicitly; all other
artifact pairs keep normal strict actual-file verification. No general hash
mismatch or missing-file fallback is introduced.

Production `scripts/wsl_retrieval_archive.py` validates the exact policy, original
experiment and all its artifact fingerprints, guard fingerprint/early refusal,
canonical paths without symlinks, immutable lock, scanner configuration and
inventory scope before any exception scan. The WSL lock is scanned alone under
`.github/osv-scanner-frozen-wsl-retrieval.toml`; ordinary locks and the existing
macOS artifact retain their own scans. All partitions, exit statuses and SARIF
reports remain visible. The original required OSV finding is retained in owner
evidence; a passing scoped scan is an archival exception, not a patched package.

The owner is the repository Foundation/security lane through
[issue 384](https://github.com/seathatflowsinourveins/native-agent-stack/issues/384).
The exception starts at **2026-10-03T00:00:00Z** and expires at
**2026-11-02T00:00:00Z**. Expiry, policy/scope/hash drift or guard removal fails
closed. There is no automatic renewal or activation override. Future runnable
retrieval requires a separate normally scanned qualified source and lock; this
archive cannot supply its installation recipe or native qualification.

Arbitrary manual execution or copying of historical text/locks outside these
repository controls is outside this decision. Native Claude convergence selected
this option conditionally; acceptance still requires guard/mutation/path/expiry
checks, ordinary-versus-scoped scanner controls and exact-head required CI. No
native retrieval, model, service, unsafe benchmark or host promotion follows.
At source handoff, actual ordinary/scoped scanner controls and exact-head required
CI remain pending owner acceptance.

At the 2026-10-03T01:25:06Z owner acceptance checkpoint, 193 affected tests
passed with two documented skips, and nine portable-default tests passed.
The bounded independent source review found no material issues. Actual pinned
OSV-Scanner 2.6.0 controls returned exit1 for both the original historical lock
and an unrelated ordinary copy, retaining GHSA-vfj7-8cjw-p6xm. The guarded
isolated archive returned exit0 with one filtered vulnerability. An exhaustive
50/1/1 inventory partition produced three retained SARIF reports and exit0 for
each scan; the production archive preflight passed. GitHub workflow execution
and fresh exact-head required CI remain pending at this checkpoint. The
[publication receipt](../../evidence/receipts/north-star-publication-security-convergence-20261002.json)
preserves digests, the native review timeout and word-limit failure, actual
same-host peer acknowledgement and the acceptance limits.
