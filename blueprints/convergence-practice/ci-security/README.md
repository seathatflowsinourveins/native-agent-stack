# Native workflow security qualification

The public CI now installs **zizmor 1.30.1** from a SHA-256-locked official PyPI
wheel and analyzes workflows offline. It adds no persistent service or account.
The Linux x86_64 wheel is isolated to GitHub's disposable Ubuntu runner; its
[lock](../../../.github/requirements-ci.lock) is not a portable Mac install recipe.

The [source review](../../../catalogs/convergence-practice/architecture-wave/zizmorcore__zizmor.json)
records the release commit, README and MIT license identity. The
[native observation](observation.json) records the separately tested Mac binary.
The current workflow has no findings under the regular persona. The deliberately
unsafe fixture returns exit 14 with `template-injection`, `unpinned-uses` and
`artipacked`. The fixture is inert text outside `.github`; it is never executed.

Replay with the selected native executable available:

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
