# Offline verification, 2026-09-27

These are local structural and synthetic-fixture checks. They do not install or
import OpenHands, execute its upstream test suite, run an image, call the gateway,
read its live database, or qualify native MCP/skills behavior.

The implementation references are the immutable upstream links in
[README.md](../README.md); the integration contract is the user's 2026-09-27
OpenHands builder request. The fixture oracle uses CPython's public unittest
runner interfaces. No benchmark or token-saving claim is made.

From the checkout root, the initial and final command was:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_runtime_worker_openhands.py -v
```

| Run | Exit | Returned result | Output |
| --- | --- | --- | --- |
| Initial contract, before any recipe files existed | 1 | `Ran 6 tests`; `FAILED (failures=2, errors=4)` | [fail-first.txt](fail-first.txt) |
| Final contract and synthetic controls | 0 | `Ran 19 tests in 0.546s`; `OK` | [unit-pass.txt](unit-pass.txt) |

The final run redirected stdout and stderr to a temporary file; the command's
own exit code was observed before retaining that file unchanged. Initial failure
outputs replace only private filesystem prefixes with placeholders. Expanded
negative controls retain their actual results in [expanded-tests.txt](expanded-tests.txt),
[serena-red.txt](serena-red.txt) and [receipt-red.txt](receipt-red.txt).

The final suite covers an empty result, wrong solution, test deletion/skipping,
extra files, symlinks, missing or late failing-test observations, restricted
gateway columns using a synthetic SQLite database, observation-only tool/skill
counts, incomplete native summaries and cleanup failures. Positive controls use
an explicitly local repair and synthetic events; they are not model transcripts.

Additional checks returned exit 0:

```sh
bash -n blueprints/runtime-workers/openhands/install.sh blueprints/runtime-workers/openhands/install-container.sh blueprints/runtime-workers/openhands/run-e2e.sh
git diff --check
```

Python AST parsing of 10 files, JSON parsing of 8 files, both requirement-file
SHA256 checks and relative Markdown target checks passed. These checks do not
execute the SDK. `git diff --check` cannot cover these untracked additions;
direct syntax, content and repository publication checks provide their evidence.

Publication validation uses the repository's unchanged command:

```sh
python3 scripts/validate.py
```

Its initial failure is retained in [publication-first.txt](publication-first.txt).
The corrected run's returned output and exit code are in
[publication-pass.txt](publication-pass.txt). This validates integrity and scope,
not host/provider execution. Only this recipe and its named unit test were added;
no shared manifest, index, catalog, Git metadata or other checkout was changed.
