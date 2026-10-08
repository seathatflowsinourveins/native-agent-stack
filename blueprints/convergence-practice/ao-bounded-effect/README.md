# Bounded AO failure-delivery effect

CC133502Z assignment14 asks for one measured orchestration task and the AO effect against no AO. The task here delivers one failed build's information to its owning recording receiver. It runs the real AO observer, lifecycle manager and SQLite from OrchestratorInc/agent-orchestrator v0.13.5 at `c95ae361eee48d33c2f443c6d2fe69c445f548a8`, with synthetic SCM input and the vendor's recording messenger. The [receipt](../../../evidence/receipts/ao-bounded-effect-20261008.json) retains the actual returned Go output and separates unchanged upstream checks from the locally authored qualification fixture.

| Arm | Observer polls | Receiver sends | Simulated manual sends | Persisted failed check |
| --- | ---: | ---: | ---: | --- |
| AO native observer | 2 | 1 | 0 | Yes; same head and stable dedup signature |
| No AO orchestration; observer bypassed | 0 | 1 | 1 | No |
| CI policy disabled inverse | 2 | 0 | 0 | Yes; no send signature |

All arms start from independent fresh fixtures and the same input hash `cc665ee541f5eba767876e0d770209a8444c158a4c224306004b0cc98c359e47`. The two delivery arms receive the same relevant failure information. The measured effect is one automatic delivery with zero simulated manual sends under AO, versus one explicit simulated manual send with its observer bypassed. Human effort, live agent repair and provider savings remain unmeasured. The disabled-policy arm tests the native inverse separately from the bypassed control.

The maintained native source is the reference implementation; this fixture adds only the missing paired observation. It reuses `newSCMFixture`, `failingSCMObservation` and `scmMessengerSpy` from [the upstream integration harness](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/backend/internal/integration/scm_observer_test.go). That file's SHA256 is `2f55eb4194e9a73722890f0941bda596c97620d9208d5b2716bc3efa84e02767`. No production code or upstream test is patched.

Use the vendor installation from [scripts/setup-self-hosted.sh](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/scripts/setup-self-hosted.sh), with an owned `AO_HOST_INSTALL_DIR`, `AO_DATA_DIR`, `AO_RUN_FILE` and `--install-only`. Its official release asset SHA256 verification and complete resource checks pass. The daemon's native version string is `dev`; release identity is bound separately by the asset digest and source tag. The experimental install was withdrawn after native `ao stop --timeout 10s --json` returned `stopped`; no daemon or service was launched.

For the qualification, clone the clean tag `v0.13.5`, verify the exact commit and helper digest, and use Go1.27.1 as declared upstream. [Go's native overlay](https://go.dev/cmd/go/#hdr-Compile_packages_and_dependencies) maps a virtual `backend/internal/integration/cc133502z_ao_effect_test.go` to this directory's `ao_bounded_effect_test.go`. Keep the absolute-path `Replace` map in private state. From the vendor `backend` directory:

```sh
go test -overlay "$AO_OVERLAY_JSON" -count=1 -v ./internal/integration -run '^TestCC133502ZAOEffect$'
```

The vendor documents its native runner in [docs/development.md](https://github.com/OrchestratorInc/agent-orchestrator/blob/c95ae361eee48d33c2f443c6d2fe69c445f548a8/docs/development.md). Its unchanged SCM end-to-end, lifecycle CI-on/CI-off and existing-PR policy-change tests passed in the same final native invocation. The [experiment record](experiment.json) declares the scoped comparison; its validator checks declared consistency, not empirical truth.

The completeness boundary includes a recording receiver and simulated manual dispatch, rounded Go timings with fixture/cache effects, two explicit polls at one synthetic head, and one host. Live gateway/profile admission, AO-launched fast-tier forwarding, actual human baseline, coding fixes, restart/replay/persistence failures and changed-head behavior remain separate tests. The existing three-session/small-PR limits, core stop guard and CC-only landing/deployment custody stay with their current owners. N2's STOP remains latched.

The correction log records two discovery mistakes: v0.13.4 ceased to be latest at10:28:32Z, and an old service comment incorrectly described the CI policy toggle. The actual transactional implementation updates existing PRs, verified by its native regression and this inverse. The next landscape sweep checks v0.13.5's imported-profile changes and scoped gateway admission before any model-route claim.

The registry adds AO as an optional reference with this narrow trial boundary. Two historical registration envelopes bind the previously owed AO feedback and landscape records while their original payload bytes, classifications and observations remain unchanged. Registry metadata is separate from execution evidence; the envelopes carry explicit historical-only limitations and original artifact digests.
