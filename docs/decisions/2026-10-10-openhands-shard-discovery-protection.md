# OpenHands shard discovery protection

The native suite runner in `validate.yml` delegates to unittest discovery through
`python3 scripts/validate_shards.py run`. The resolver's trusted push gate did not recognise
that call. Removing the unrelated macOS workflow at #957 head
`7df900f7dd6f24b20e3d9e54cfd21aba318d75e8` therefore left 258 of 321 `tests/*.py` files
without a protection rule. Main `a30c2188e4423f05a7448e5f7a3bcfd858e0f5b8` still covered
them through a workflow's incidental `tests/` mention.

Recognise the existing shard runner in `_unittest_runs` as discovery from `.` with pattern
`test*.py`, and let `derive_ci_protected` use its existing package traversal and rule
precedence. The stronger `ci_discovered` expectation retains protection for a future module.
This follows the shipped wrapper rather than adding a runner or another discovery algorithm.

Primary sources are this repository at `a30c2188e4423f05a7448e5f7a3bcfd858e0f5b8`,
[`scripts/validate_shards.py:94-96`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a30c2188e4423f05a7448e5f7a3bcfd858e0f5b8/scripts/validate_shards.py#L94-L96)
and [`186-197`](https://github.com/seathatflowsinourveins/native-agent-stack/blob/a30c2188e4423f05a7448e5f7a3bcfd858e0f5b8/scripts/validate_shards.py#L186-L197),
plus `python/cpython@v3.12.3`,
[`Lib/unittest/loader.py:229-233`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/loader.py#L229-L233),
[`344-374`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/loader.py#L344-L374) and
[`419-444`](https://github.com/python/cpython/blob/v3.12.3/Lib/unittest/loader.py#L419-L444).
The maintained stdlib API already owns discovery; no dependency or upstream fork is needed.

The new repository-tree regression isolates the real shard suite step and injects a new test
module. It fails with `(None, None)` on main's old gate and on the exact #957 gate/tree,
then passes with `ci_discovered` after the fix. Replaying the fixed gate on either real tree
protects all 321 test files. The three required modules pass all 389 tests on Python 3.13.16;
the separate MemoryTree regression refuses any subprocess and rejects non-run subcommands.

Correct discovery also removes exactly eight `tests/test_catalogs.py` locations from live
advisory import tracing, because the existing contract excludes test modules from gate-script
imports. Keep the historical monitoring receipt unchanged. Assert this specific correction,
all remaining script counts and every recorded shape. Measurements and evidence classes are
in [the dated receipt](../../blueprints/runtime-workers/openhands/evidence/shard-discovery-protection-20261010.json).

Revisit the mapping if the maintained wrapper changes its discovery root, filename pattern,
package traversal or run subcommand. Such a change must update the pinned source citation and
reproduce the expected protected set with the native loader and the repository regression.
