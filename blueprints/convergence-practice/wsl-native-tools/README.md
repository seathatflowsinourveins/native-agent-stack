# Native WSL quality and worktree tools

The [current WSL receipt](receipt-wsl-hardened.json) qualifies project-local **gitleaks 8.30.1**
and **Worktrunk 0.78.0** on Linux x86_64, WSL2 kernel 6.18.33.2, Python 3.13.15
and Git 2.55.0. This is a synthetic tool check, with no model or provider calls.
It does not qualify another host or install a global command, shell integration,
Git hook, service or account configuration.

| Native check | Observed result |
| --- | --- |
| Default gitleaks rules, generated inert secret | Exit 1, exactly one `github-pat` finding, fully redacted |
| Default gitleaks rules, clean directory | Exit 0, no findings |
| Worktrunk create/list | Two owned worktrees at the same frozen main commit |
| Clean removal | Exit 0, foreground removal without force |
| Modified and untracked files | Removal exit 1; both byte sequences and registration preserved |
| Restore fixture-authored changes, remove again | Exit 0 without force; only primary fixture and main branch remain |
| Project hooks | Explicit `--no-hooks`; no hook marker created |

Both synthetic native attempts passed all criteria in [plan.json](plan.json).
Twenty offline tests also pass on both [WSL](offline-wsl-hardened-tests.txt) and
[macOS](offline-macos-hardened-tests.txt). The tests reject altered assets, unsafe archive
members, checksum mismatches, leaked report/log values, false positives, extra
worktrees, changed dirty data and reused destinations. They also verify that a
failed native command retains its exit code and logs, a timeout retains redacted
partial logs with a null exit, and changed installation metadata cannot authorize
a changed binary. Mac unit tests do not
establish native Mac tool acceptance. [Prior diagnostics](prior-attempts.json)
retain metadata-access and initial test-harness failures, plus the single review's
two corrected guard findings. The [original runner](executed-run-v1.py),
[native receipt](receipt-wsl.json) and original 15-test logs remain unchanged.
Its receipt's `run.py` hash identifies those preserved original source bytes;
the current runner has its own frozen hash in the revised receipt.

## Reproduce in a new owned prefix

Review [pins.json](pins.json) and [source-review.json](source-review.json) first.
The installer supports Linux x86_64 only, refuses any existing destination,
and verifies archives before extraction. Each archive matches its official
GitHub asset digest and publisher checksum. Packaged licenses match the exact
pinned upstream source bytes: gitleaks MIT, Worktrunk MIT OR Apache-2.0.
The optional attestation lookups returned HTTP 404; no independently verified
signature or attestation is claimed.

```sh
python3 blueprints/convergence-practice/wsl-native-tools/install.py \
  --prefix "$NEW_PRIVATE_PREFIX"
python3 blueprints/convergence-practice/wsl-native-tools/run.py \
  --prefix "$NEW_PRIVATE_PREFIX" --work "$NEW_PRIVATE_PREFIX/attempt-1"
python3 -m unittest discover -s tests -p test_wsl_native_tools.py -v
```

The runner freezes hashes of its inputs before executing the tools. It binds
installation metadata to the frozen component/version/source/archive pins,
derives executable hashes from the verified release archives and requires the
actual native versions to match. It uses
an empty child environment with explicit owned Worktrunk user/system config,
owned XDG locations, disabled user/system Git config, and disabled Git hooks.
It creates a disposable repository with no remote. It explicitly disables
Worktrunk hooks, directory switching and background removal; list collection
must report CI and model summaries disabled. It never passes force removal,
process reaping or command-execution options.

The only cleanup edits restore the exact bytes this runner changed and unlink
its verified synthetic untracked file. Worktrunk then removes the clean trees
and their branches. If any assertion fails, the directory and logs remain for
inspection. The runner never recursively deletes its workspace. Source, primary
fixture, archives and binaries remain under the owned prefix; [installation
metadata](installation-wsl.json) identifies relative executable paths and hashes.
Retain evidence before retiring that prefix. PATH promotion and shell integration
are separate coordinator decisions.

This finding does not measure general secret coverage, scan any real repository
history, validate native worktree integration with a model client, or establish
complete hook/process isolation for arbitrary projects. The synthetic secret
was generated locally and never issued by a provider. Public receipts retain
native exits, exact input hashes and hashes of private logs; personal paths and
native account state are excluded. Whole-task agent usage remains unknown,
and no token-saving claim follows. The next useful extension is a scoped real
project scan and native-client worktree check after its owner selects the
project and reviewed configuration.
