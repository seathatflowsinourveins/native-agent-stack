# Graphiti 0.30.2 install recipe and acceptance checks

This directory installs the official [graphiti-core 0.30.2](https://pypi.org/project/graphiti-core/0.30.2/) wheel by version and sha256, constrained to the dependency set that upstream CI locks, and holds the checks that accept such an install. It corrects the earlier unconstrained recipe (`pip install graphiti-core`) in [`manifests/candidates.json`](../../manifests/candidates.json) and the [foundation-memory catalog](../../catalogs/us-equities/foundation-memory.json). Graphiti stays a deferred candidate there; nothing here installs it into a managed stack.

## Why the install is constrained

- graphiti-core 0.30.2 imports `httpx` at the top of its base LLM client ([`graphiti_core/llm_client/client.py` L23](https://github.com/getzep/graphiti/blob/v0.30.2/graphiti_core/llm_client/client.py#L23)) but does not declare it, and it declares `openai>=1.91.0` with no upper bound ([`pyproject.toml`](https://github.com/getzep/graphiti/blob/v0.30.2/pyproject.toml#L13-L21)).
- openai 3.0.0 and later require `httpx2` instead of `httpx` ([openai-python v3.0.0](https://github.com/openai/openai-python/releases/tag/v3.0.0)). An unconstrained install therefore resolves openai 3.x without `httpx`: the install succeeds and `import graphiti_core` fails. Upstream tracks this as [getzep/graphiti#1893](https://github.com/getzep/graphiti/issues/1893) (open; PRs #1894 and #1895 await review).
- CI at the release commit [`eaa41286`](https://github.com/getzep/graphiti/commit/eaa4128681bc53487138a4bbc22d58336ebe70d2) (tag `v0.30.2`) ran openai 2.32.0 with httpx 0.28.1 on CPython 3.10.21: unit tests 382 passed and 11 skipped, database tests 81 passed and 13 skipped against FalkorDB v4.20.4 ([run 34275941924](https://github.com/getzep/graphiti/actions/runs/34275941924)).

[`graphiti-0.30.2.constraints.txt`](graphiti-0.30.2.constraints.txt) is `uv export` of the [`uv.lock`](https://github.com/getzep/graphiti/blob/86f1c941bea7bf53fa45fe4e08c03244b4990eee/uv.lock) at getzep/graphiti main [`86f1c941`](https://github.com/getzep/graphiti/commit/86f1c941bea7bf53fa45fe4e08c03244b4990eee) (blob `97ae57efc2e1916a0df8b148a5754a7f0f377e2c`), with hashes; with uv 0.12.22 the file is byte-reproducible (sha256 `e3026f265a36e8c5c0dfc787146e5162dfa722e4606bfc0dd99658c0cb4ea870`). Its runtime set is the v0.30.2 tag lock's set plus three upstream security bumps: anyio 4.12.1 to 4.15.1 and typing-extensions 4.15.0 to 4.16.0 ([`acddbf0`](https://github.com/getzep/graphiti/commit/acddbf0), #1936), and urllib3 2.7.0 to 2.8.0 (`86f1c94`, #1972). The tag lock's anyio 4.12.1 and urllib3 2.7.0 carry one critical, two high and two medium advisories. Commit [`ea4ac0f3`](https://github.com/getzep/graphiti/commit/ea4ac0f34ee8), whose `graphiti_core/` is identical to v0.30.2, passed its database suite (81 passed, 13 skipped) and unit suite (472 passed, 11 skipped) with anyio 4.15.1, typing-extensions 4.16.0, urllib3 2.7.0, openai 2.32.0 and httpx 0.28.1 against FalkorDB v4.20.7 ([run 36497025023](https://github.com/getzep/graphiti/actions/runs/36497025023)). No single upstream run combines the v0.30.2 code with urllib3 2.8.0, which graphiti reaches only through posthog and requests.

The three bumped releases cleared the 24-hour gate long ago (anyio 4.15.1 on 2026-09-05, typing-extensions 4.16.0 on 2026-07-02, urllib3 2.8.0 on 2026-09-15); the lock commit, from 2026-10-07T19:12Z, is only where the pins come from. If the gate is also applied to lock commits, `86f1c94` clears it at 2026-10-08T19:12Z; the same file comes from exporting `ea4ac0f34ee8` (lock blob `75017c17`) and replacing its urllib3 entry with urllib3 2.8.0 and its two PyPI hashes, which are the ones in this file.

[`requirements.txt`](requirements.txt) names the wheel by its sha256 (`97674a49514130db175faecf23221ce9338240be3cbe13a7e23e5a5033892b9f`, [PyPI](https://pypi.org/pypi/graphiti-core/0.30.2/json)). In hash-checking mode every dependency must take its hash from the constraints file: a changed anyio hash fails the install with `Hash mismatch`, and an entry removed from the constraints fails it too. `--no-build` keeps uv from building any of the source distributions the constraints also list.

## Install and accept

Set `GRAPHITI_ENV` to a new, dedicated environment path and `OUT` to a new results directory. Keep Graphiti in an interpreter of its own: the selected recipe keeps upstream's CI-locked openai 2.32.0, and the [SDK lane](../../adoption/sdk/accepted-constraints.txt) pins openai 3.16.2. From the repository root:

```sh
uv venv --python 3.13 --no-python-downloads "$GRAPHITI_ENV"
uv pip install --python "$GRAPHITI_ENV/bin/python" --require-hashes --no-build \
  -r tools/graphiti-smoke/requirements.txt \
  -c tools/graphiti-smoke/graphiti-0.30.2.constraints.txt
uv pip check --python "$GRAPHITI_ENV/bin/python"
uv pip freeze --python "$GRAPHITI_ENV/bin/python" > "$OUT/freeze.txt"
diff tools/graphiti-smoke/expected-freeze.txt "$OUT/freeze.txt"
"$GRAPHITI_ENV/bin/python" -I tools/graphiti-smoke/smoke.py
uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -s pypi -r "$OUT/freeze.txt"
uvx --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -s osv -r "$OUT/freeze.txt"
```

Accept the environment only when every command exits 0.

- [`expected-freeze.txt`](expected-freeze.txt) is the 31-package set this install produced with CPython 3.13 on macOS arm64. The constraints also pin async-timeout, colorama, exceptiongroup and numpy 2.2.6 behind environment markers that CPython 3.13 on macOS does not select.
- [`smoke.py`](smoke.py) is a local integration check, not an upstream test. It imports `graphiti_core`, constructs the OpenAI, generic OpenAI-compatible, Azure, embedder and reranker clients and a `Graphiti` object on an unreachable Neo4j URI with dummy credentials, requires the openai SDK methods, exceptions and types graphiti uses, and requires graphiti's base retry predicate to retry a raw `httpx` 503. It makes no network or model call, prints JSON and exits 0 only when all 9 checks pass (2 when the import fails, 1 otherwise). Relative to the copy the decision reviewed, its docstring is reworded (gitleaks 8.30.1, the version CI pins, flagged the old wording as a generic API key) and the SDK-surface and retry-predicate checks now fail on a wrong value; before, they could fail only on an exception.
- [pip-audit](https://github.com/pypa/pip-audit) 2.10.1 (PyPA; wheel sha256 `99ef3f600a317c1945f1e89e227ef26e1c2d618429b8bd3fa6f4f7c440c4611a`) audits the freeze against PyPI's vulnerability data and against OSV. `uvx` pins its version, not its hash, and resolves pip-audit's own dependencies at run time. Do not substitute GitHub's `/advisories` `affects` filter: it matches package names exactly as the advisory database spells them, and the database keeps pip names in mixed spellings. On 2026-10-07 `affects=pillow@8.0.0` returned 21 advisories and `Pillow@8.0.0` another 23, and `jupyter_server@1.0.0` returned two that `jupyter-server@1.0.0` does not.
- [`security-scan.yml`](../../.github/workflows/security-scan.yml) scans all three committed pin files with the pinned OSV-Scanner on every pull request ([`.github/osv-scanner-lockfiles.json`](../../.github/osv-scanner-lockfiles.json)).

A Neo4j-only lane installs `graphiti-core==0.30.2` (the same wheel hash) against the export without `--extra falkordb` (sha256 `f022aa26b062d0e593dbea647449d72d92da80fe535e2de35062d3059bb5c2c4`) and freezes 29 packages; that variant is not committed here.

## Recorded rerun, 2026-10-07

macOS 27.0.1 arm64, CPython 3.13.15, uv 0.12.22, pip-audit 2.10.1, OSV-Scanner 2.6.0, in throwaway environments. These are this host's results, recorded in the pull request; no receipt is committed and the catalog evidence level stays `source_review`.

| Check | Result |
| --- | --- |
| Fresh fetch of `86f1c941`; `git rev-parse HEAD:uv.lock` | `97ae57ef…` |
| `uv export … --no-header` | exit 0; sha256 `e3026f26…`, the value the decision's re-check recorded |
| Hashed install with `--no-build`, empty cache | exit 0, 31 packages |
| `uv pip check` | exit 0 |
| `diff` against `expected-freeze.txt` | exit 0 |
| `smoke.py` | exit 0, 9 of 9 |
| pip-audit `-s pypi` and `-s osv` over the freeze | exit 0 each, `No known vulnerabilities found` |
| OSV-Scanner over the three committed pin files and the freeze, repository config | exit 0, no issues |

Controls that must fail, and did:

| Control | Result |
| --- | --- |
| Constraints with both anyio hashes zeroed | install exit 1, `Hash mismatch for anyio==4.15.1` |
| Constraints without the `distro` entry | install exit 1, `all requirements must be pinned upfront with ==, but found: distro` |
| Unconstrained `uv pip install 'graphiti-core[falkordb]==0.30.2'` | resolved openai 3.26.0, httpx2 2.13.1 and no httpx; smoke exit 2, `ModuleNotFoundError: No module named 'httpx'` |
| `smoke.py` under an interpreter without graphiti | exit 2 |
| `smoke.py` with `AsyncResponses.parse` removed | exit 1; only the SDK-surface check fails |
| `smoke.py` with graphiti's base retry predicate returning `False` | exit 1; only the retry-predicate check fails |
| pip-audit over `pyjwt==2.13.0` | exit 1 each: 14 findings with `-s pypi`, 28 with `-s osv` |
| OSV-Scanner over `anyio==4.12.1` and `urllib3==2.7.0` | exit 1 with GHSA-82r6-8w77-94w6, GHSA-5p39-cfhj-2xmp, GHSA-vxq7-64xx-v4gw, GHSA-8988-9cw3-xx77 and GHSA-gh4c-6fx4-qh6g |

## FalkorDB server

Pin `falkordb/falkordb:v4.20.7@sha256:13996aa523f0dd283f6bd6df6620b094dcea525452417c4d6ef9bef15dc9998d` (arm64 image `sha256:530e7c95e4dbad97a4f5acbec2094b01247ffac0212bc54a14865e320879c9d7`). [v4.20.7](https://github.com/FalkorDB/FalkorDB/releases/tag/v4.20.7) (2026-09-24) moves Redis to 8.10.2 for CVE-2026-85091 ([GHSA-g5fp-32jq-cfw2](https://github.com/advisories/GHSA-g5fp-32jq-cfw2)), and graphiti CI ran it with code identical to v0.30.2. Keep `falkordb/falkordb:v4.20.4@sha256:adbddd418916c25618564ff8597a919b08bc76452ebeb74eb985c38d7281df62` for rollback only. Skip v4.22.0, which no graphiti CI is known to have run, and 6.x: graphiti-core 0.30.2 fails index creation there until a release contains [`7d9be0d`](https://github.com/getzep/graphiti/commit/7d9be0d) (#1963). FalkorDB has no 5.x line.

No live FalkorDB or Neo4j run is recorded. `FalkorDriver` connects when it is constructed, so a live integration smoke against the pinned server, in each client that uses Graphiti, comes before adoption. Upstream CI ran amd64 Linux; the arm64 image is not CI-evidenced.

## MCP server lane: deferred

No option is released, CI-evidenced and free of advisories at once:

- The official `zepai/knowledge-graph-mcp:1.1.0` image (`sha256:a2536b6d59b4afb359a13aeaa4a9d2f4db195af14231168efda6a3d166228956`) regenerates its lock at build time and ships graphiti-core 0.30.1, openai 3.6.0, httpx 0.28.1 and httpx2 2.12.0. Its linux/amd64 install set has 18 advisories (1 critical, 7 high), and no CI ran on that set. The package set of the `1.1.0-standalone` variant (`sha256:52d619bc3c45527dd5e6c5c413f3024f50d79fa672c81f4b384eb04bff85ca84`) was not audited.
- Running the `mcp-v1.1.0` lock from source is a self-build while an official image exists; it carries graphiti-core 0.30.1 and openai 2.43.0, with 21 advisories (2 critical, 9 high).
- main's MCP lock (mcp 2.2.0, graphiti-core 0.30.2, openai 2.43.0) has no advisories but is unreleased, and its live tests at `86f1c94` failed against FalkorDB 6.0.1.

The upstream `mcp_server` commands (`uv sync`, and `docker compose up`, which pulls `zepai/knowledge-graph-mcp:latest` beside a local build section) stay unrun. If the lane is needed before the next MCP release, the coordinator decides whether to accept the official image by digest, with a written risk acceptance.

## When to change this

1. A graphiti-core release after 0.30.2 fixes #1893 or locks openai 3.x with green CI at its tag: after the 24-hour gate, move the wheel hash, the constraints export (from that release's lock), the expected freeze and the FalkorDB pin together. A release containing #1963 makes FalkorDB 6.0.1 eligible.
2. An advisory hits an installed package: bump it within openai 2.32.0's bounds (anyio<5, httpx<1, pydantic<3, typing-extensions<5), preferring upstream's next lock commit, then rerun the smoke and pip-audit. Move to openai 3.x with an explicit `httpx==0.28.1` only if openai 2.32.0 or httpx 0.28.1 is itself hit with no fix on its line, or if Graphiti must share an interpreter with openai 3.x, and gate that move on graphiti's unit suite passing under openai 3.x.
3. An advisory hits FalkorDB v4.20.7: take the next 4.20.x patch after 24 hours and rerun graphiti v0.30.2's database suite against it.
4. Maintainers choose a direction on #1893, #1894 or #1895: follow it at their next release.

To regenerate the constraints, check out getzep/graphiti at the chosen commit, confirm `git rev-parse HEAD:uv.lock`, and run from the repository root:

```sh
uv export --project "$GRAPHITI_SRC" --frozen --no-emit-project --no-dev --extra falkordb \
  --format requirements.txt --no-header -o tools/graphiti-smoke/graphiti-0.30.2.constraints.txt
```

Not verified here: graphiti's suites on CPython 3.13 (upstream CI used 3.10.21), graphiti under openai 3.x beyond import and offline construction, and whether CVE-2026-85091 is reachable through FalkorDB.
