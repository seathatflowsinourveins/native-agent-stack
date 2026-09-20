# Native workflow security qualification

The public CI now installs **zizmor 1.30.1** from a SHA-256-locked official PyPI
wheel and analyzes workflows offline. It adds no persistent service or account.
The Linux x86_64 wheel passed the [exact-head CI run](ci-acceptance.json),
including all 404 tests with 40 explicit optional-profile skips. It is isolated
to GitHub's disposable Ubuntu runner; its
[lock](../../../.github/requirements-ci.lock) is not a portable Mac install recipe.

The [source review](../../../catalogs/convergence-practice/architecture-wave/zizmorcore__zizmor.json)
records the release commit, README and MIT license identity. The
[native observation](observation.json) records the separately tested Mac binary.
The current workflow has no findings under the regular persona. The deliberately
unsafe fixture returns exit 14 with `template-injection`, `unpinned-uses` and
`artipacked`. The fixture is inert text outside `.github`; it is never executed.

Replay with the selected native executable available:

The later [native Linux receipt](../../../evidence/receipts/native-linux-zizmor-20260920.json)
closes the executable gap on its recorded source Linux/WSL host with upstream
`uv tool install zizmor==1.30.1` in an isolated tool environment. Importing that
receipt does not qualify macOS, VelaNext or another host. The workflow-directory scan returned exit 0
and no findings; the unchanged inert fixture returned exit 14 with all three
diagnostics above. Both exact native acceptance tests passed with no skips.
The installed binary was independently hashed; this follow-up did not repeat
the CI wheel archive verification or execute any workflow.

Run the direct upstream command from either client's native shell, choosing an
owned cache directory:

```sh
uv tool install zizmor==1.30.1
env -u GH_TOKEN -u GITHUB_TOKEN -u ZIZMOR_GITHUB_TOKEN \
  zizmor --offline --no-config --no-ignores --no-progress \
  --persona regular --strict-collection --format json \
  --cache-dir "$OWNED_CACHE" "$PROJECT_ROOT/.github/workflows"
```

Install once; subsequent workflow edits need only the relevant scan. Acceptance
can be replayed with the repository's native fixture tests:

```sh
python3 -m unittest -v tests.test_workflow_security
python3 scripts/validate_convergence.py blueprints/convergence-practice/ci-security/experiment.json --root . --json
```

The tests skip explicitly if zizmor is absent locally. CI installs the exact
wheel first and fails if installation or analysis fails. Offline regular analysis
does not cover all vulnerabilities, online advisories, secrets or supply-chain
provenance. Pedantic analysis also reports missing job names and concurrency
limits in the existing workflow; those advisory findings are outside this
adopted regular-persona gate. The wheel checksum is integrity evidence, not a
signature-verification claim. Changing versions requires source review, a new
wheel hash and replay of both accepted and rejected cases.

Rollback removes the selected CI analyzer step, lock and its tests together;
the existing evidence and catalog validation remain the baseline. Public CI
results qualify that runner only; another host must run its own acceptance.

The original accepted workflow bytes are retained in `qualified-workflow.yml.txt`.
The historical experiment references that immutable copy; current CI validates
every convergence record registered in the evidence manifest with
`python3 scripts/validate_convergence.py --all-recorded --json`. This checks
declared hashes and scope without rerunning native commands or model trials.

Every contract is explicitly listed in `manifests/evidence.json` under
`convergence_records`. Discovery also rejects undeclared canonical experiment
paths or tagged records. Missing/misspelled `kind` fields are validated instead
of silently excluding a declared experiment.
