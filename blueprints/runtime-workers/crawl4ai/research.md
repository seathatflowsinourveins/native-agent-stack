# Crawl4AI v0.9.4 source review — 2026-09-27

Status: recipe construction only, `lane:foundation`. No installation, image pull,
service startup or model call is authorized in this builder worktree.

Research used the installed search-first and find-skills workflows, the
context-mode fetch/index/search tools, and a bounded read-only research worker.
The user prescribed the offline test seams. The test was written before this
directory existed, following the installed TDD workflow.

1. Installed-client preflight: `command -v crwl` returned no executable. Native
   capability verification is pending; this is not an assertion of absence.
2. [Official release](https://github.com/unclecode/crawl4ai/releases/tag/v0.9.4)
   prescribes `pip install crawl4ai==0.9.4` and `unclecode/crawl4ai:0.9.4`.
3. Pinned source inspected: `pyproject.toml`, `uv.lock`, `crawl4ai/async_configs.py`,
   `crawl4ai/utils.py`, `crawl4ai/extraction_strategy.py`,
   `crawl4ai/async_webcrawler.py`, `deploy/docker/` and the official extraction
   example. The README records precise source anchors for the resulting recipe.
4. Official tag documentation inspected: `docs/md_v2/core/fit-markdown.md` and
   Docker/LLM extraction documentation. PruningContentFilterLXML is the maintained
   pruning class at this tag; the older BeautifulSoup class is deprecated.

Skill discovery checked the skills.sh leaderboard, then its public
`/api/search?q=crawl4ai&limit=5` endpoint. It returned
`brettdavies/crawl4ai-skill` and `lancelin111/crawl4ai-skill`, among others.
These are discovery leads, not evidence of framework skill loading. The pinned
repository tree had no SKILL.md; the adopted skill manifest was inspected.
The complete tree also contains the official `docs/md_v2/assets/crawl4ai-skill.zip`,
SHA256 `a0014632d6f16ede6477a4d4eb4635c7bfc37f03a08c95f9a4ff52a09ae66091`.
Its embedded SKILL.md is dated 2025-01-19, version 0.7.4, and is guidance for a
calling agent; it is not a framework skill loader. No skill installation is
proposed inside this crawler runtime. Native client
verification remains pending; the reviewed API is an MCP server, not an agent
harness that loads the stack's MCP servers or SKILL.md files.

The selected sources meet this task through native AsyncWebCrawler,
LLMExtractionStrategy and the authenticated upstream Docker API/MCP server.
Alternative frameworks and third-party scraping skills do not close a demonstrated
gap for the user-selected crawler. Popularity was not used as acceptance evidence.

## Round 2 source selection (before implementation)

The supplied evaluation reports select **Promptfoo 0.123.1** for W8d, with
Crawl4AI v0.9.4's extraction regression as runner-up. The installed Promptfoo
reports 0.123.1 and its `eval --help` exposes `--assertions`, `--model-outputs`,
`--no-cache`, `--no-share` and `--no-write`. No installation was performed.
The installed search-first workflow delegated bounded read-only source research;
find-skills checked the skills.sh leaderboard and public search endpoint again.
The search returned `brettdavies/crawl4ai-skill` and
`lancelin111/crawl4ai-skill`; these remain caller guidance, not evidence that
Crawl4AI loads skills. No new skill is selected for this runtime.

The exact implementation references for this round are:

- [Promptfoo installation at 0.123.1](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/installation.md):
  documented npm install, scoped with npm's `--prefix`; requires Node >=22.22.0.
- [Standalone output grading](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/configuration/expected-outputs/index.md#running-assertions-directly-on-outputs):
  transport the retained native output as a JSON string array; Promptfoo's
  unchanged [JSON](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/assertions/json.ts)
  and [equals](https://github.com/promptfoo/promptfoo/blob/0.123.1/src/assertions/equals.ts)
  assertions own the verdict. No Python/JavaScript custom scorer is needed.
  This is an upstream grader on our frozen fixture, not an unchanged upstream
  test or a new model execution when replaying outputs.
- The report's [HTTP-provider mapping](https://github.com/promptfoo/promptfoo/blob/0.123.1/site/docs/providers/http.md)
  cannot safely carry LLM extraction through this server revision's untrusted
  configuration loader. Preserve native Python extraction and use the documented
  standalone grader. [Server](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/server.py#L514-L520)
  and [API](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/deploy/docker/api.py#L688-L689)
  are the transport boundary; this limitation is not silently patched.
- [Crawl4AI utils.py](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/crawl4ai/utils.py#L1825-L1837)
  merges `extra_args` after its `json_object`/temperature defaults.
  [Extraction](https://github.com/unclecode/crawl4ai/blob/133e1d92e37885dfccc03ea2e3687d06c98b7ceb/crawl4ai/extraction_strategy.py#L685-L741)
  reads message content, so use a strict `json_schema` override with every object
  closed, retain JSON in the user instruction, and preserve per-conversation
  session/fresh logical-call headers. The gateway owner's cognee 1.6.1 observation
  supplied by the user is the compatibility input; this builder does not repeat it.
- [Docker Compose services](https://docs.docker.com/reference/compose-file/services/)
  and [networks](https://docs.docker.com/reference/compose-file/networks/) provide
  explicit names and owner labels. Bind mounts are directories, not Docker volume
  objects. The user's 3730..3799 range constrains published host listeners.
- Skill installation, if a calling agent needs it, follows the coordinator's
  `tools/adoption/install_skills.py` with the specified manifest/project/universal
  options. The current file lacks the new project/agent options; that calling-agent
  operation stays pending the separate PR. No loader is added to Crawl4AI.

Round 2 tests use the user-specified seams: output transport and upstream verdict
controls, gateway request options, host port validation, resource ownership,
receipt provenance, and the documented conditional skills installation command.
They remain local integration checks; the upstream assertions are executed
unchanged. Research scratch and test state are outside the repository.

## Round-3 source selection (2026-09-27)

All four supplied review/common inputs were read before repairs. Reviews are
leads, not upstream evidence. The installed search-first, find-skills, tdd and
verification-before-completion instructions were read; no worker was spawned
and no skill installed. The skills.sh leaderboard exposed existing testing and
verification skills. The already installed skills cover this repair; the
official Crawl4AI 0.7.4 skill archive remains unsuitable as a runtime loader.

The selected runtime stays unclecode/crawl4ai@133e1d92e37885dfccc03ea2e3687d06c98b7ceb
(v0.9.4). Read-only `gh api repos/unclecode/crawl4ai/releases/tags/v0.9.4`
returned the release's native pip/Docker commands and published_at
2026-09-23T12:14:55Z. The builder has no installed Crawl4AI or Docker executable;
runtime capability claims therefore stay at source-evidence level. Installed
Claude returned 2.1.283 and its add-json help lists stdio/SSE/HTTP/WebSocket and
local/user/project scope. Installed npm returned 11.19.0. Direct shell GitHub
network access failed; read-only GitHub/registry research succeeded through the
available Context Mode research tool. No gateway was queried.

| Integration behavior | Verified source (repository@pin, file:line) | Choice |
| --- | --- | --- |
| Gateway arguments and hidden drop_params | unclecode/crawl4ai@133e1d92 `crawl4ai/utils.py:1820-1837`; unclecode-litellm@1.81.13 verified wheel `litellm/main.py:1435-1459`, `litellm/utils.py:3925-3942,4677-4689` | Use native extra_args plus allowed_openai_params, not a patched runtime. Wheel SHA256 is `5e1fbedbed92333b48e7371e0bacf86d1288020451bf34351703c3b159591399`. |
| Correlation headers | Same verified wheel `litellm/llms/openai/openai.py:741-790`; encode/httpx@0.28.1 `docs/advanced/event-hooks.md:1-52` | Inject the supported native client, with a synchronous response hook; keep only correlation IDs in memory. |
| Conditional effort evidence | diegosouzapw/OmniRoute@a58000c7685f4091c7a6fd8ddf3ebce7d2ec67c3 `src/lib/usage/callLogs.ts:642-653` | Zero reasoning and missing effort are distinct. Never infer wire omission from null. |
| Compression delta | Same OmniRoute pin `src/app/api/analytics/compression/route.ts:13-24`, `src/lib/db/compressionAnalytics.ts:613-617` | Read cumulative all-time counters before/after engines-on; keep separate from provider usage. |
| Async native REST jobs | unclecode/crawl4ai@133e1d92 `deploy/docker/job.py:60-64,114-149`, `api.py:485-605,813-819,997-1078` | Supported POST/poll fallback with fixed non-LLM payload, native verdict and private result. |
| SSE MCP registration | Same Crawl4AI pin `deploy/docker/mcp_bridge.py:39-82,241-253`, `docs/md_v2/core/self-hosting.md:404-419`; anthropics/claude-code@v2.1.283 `CHANGELOG.md:5048,6971` plus installed add-json help and official MCP docs | Explicit SSE and dynamic headersHelper. Host connection/auth remains unmeasured. |
| Detached lifecycle and serialization | python/cpython@v3.12.12 `Lib/subprocess.py:506-570,749-815`, `Modules/fcntlmodule.c:273-328` | Thin local start/wait/result wrapper and nonblocking host file lock. No new runtime/orchestrator. |
| Grader dependency closure | promptfoo/promptfoo@0.123.1 `package.json:5,48-55`; npm/cli@v11.19.0 `docs/lib/content/commands/npm-ci.md:15-24` | Metadata-only lock generation; npm ci --ignore-scripts. No grader/assertion modifications. |
| Container hardening | compose-spec/compose-spec@914ec15d1fa498969c0df5c1d672306db3256089 `05-services.md:171-180,1839-1841,1955-1965,2029-2053`; Crawl4AI@133e1d92 `Dockerfile:180-209`, `deploy/docker/entrypoint.sh:8-39` and `supervisord.conf:8-32` | Supported capabilities, no-new-privileges, read-only root and tmpfs; native workers retain appuser. |
| Rootless host loopback | moby/moby@v28.5.1 `contrib/dockerd-rootless.sh:127-130,147-162` | Daemon-wide disable-host-loopback is the verified mechanism. Per-container port enforcement was not found in the reviewed mechanism; installed Docker is unavailable. Retain explicit residual risk, without an unsupported absence claim or daemon mutation. |

The npm lock is a local derived artifact with 942 registry entries, each carrying
SHA512 integrity, bound by pins.json. Resolution command (metadata only):

```bash
rtk env PYTHONDONTWRITEBYTECODE=1 TMPDIR="$PWD/.round3/tmp" npm install --package-lock-only --ignore-scripts --prefix "$PWD/blueprints/runtime-workers/crawl4ai/grader" --cache "$PWD/.round3/npm" --no-audit --no-fund
```

Returned output: `up to date in 25s`, exit 0. No node_modules directory was
created. The cache and all test scratch were removed before final validation.

## Recorded corrections / anti-pattern log

| Date | Proven mistake or unsafe assumption | Evidence and correction |
| --- | --- | --- |
| 2026-09-27, round 3 | Assuming `reasoning_effort` survives Crawl4AI's `drop_params=True` for an unknown GPT-6 slug | The verified unclecode-litellm 1.81.13 wheel, `utils.py:3925-3942,4677-4689`, extends supported parameters with `allowed_openai_params`. The request regression failed before adding that override and explicit max/max effort. Null effort is conditional evidence, not proof of omission: OmniRoute@a58000c7 `callLogs.ts:642-653`. |
| 2026-09-27, round 3 | Carrying the review's two-slash route and both-gateways usage assumption forward | The user's common requirements supersede the review: use `sharedgw/gpt-6-astra-max` and 20129's entry database for engines-on. Request, correlation-filter and separate-entry-database tests verify this local contract; host model-name/header observations remain pending. |
| 2026-09-27, round 3 | Treating every POST /md as an MCP tool invocation | The native bridge (`mcp_bridge.py:39-82` at 133e1d92) and direct probe share the route. The repaired receipt reports the combined route count and no inferred tool name; authenticated SSE and native CallToolRequest observations remain separate. |
| 2026-09-27, round 3 | Probing Promptfoo version before setting private log paths | The initial version probe returned 0.123.1 but reported EROFS while attempting default log rotation. No file was changed. Subsequent executions use the existing grader's per-test private config/log/cache environment; final verification checks the absence of worktree caches. |
| 2026-09-27, round 3 | Running publication validation while temporary npm metadata and grader test directories existed | The intermediate validator returned exit 1 with cache/publication-text and disappearing-test-file errors. Those temporary artifacts were removed; final validation runs only after tests and scratch cleanup. This was a builder sequencing error, not a repository waiver. |
| 2026-09-27, round 3 | Looking for the image definition at deploy/docker/Dockerfile and an API symbol beyond the file's length | Read-only GitHub API returned no valid file at that Dockerfile path. The pinned file is root `Dockerfile:180-209`; actual job status is `deploy/docker/api.py:485-605,997-1078` (1078 lines). The malformed read was discarded and the real sources were re-read. |
| 2026-09-27, round 3 | Retaining chmod-after-chown while removing CAP_FOWNER | The new ownership regression failed on the missing bootstrap ownership phase. Startup now takes only dedicated mount roots with CAP_CHOWN, chmods while their owner, then gives them to appuser. Runtime startup/restart remains a host check. |
| 2026-09-27, round 3 | Trying to replace one verification file with delete and add in a single apply_patch call | apply_patch rejected the duplicate target before mutation. A single update patch succeeded; final diff and publication checks cover the resulting file. |
| 2026-09-27, round 3 | Allowing receipt construction to raise again after configuration loading already failed | The damaged-config test raised from make_receipt in finally. The fallback now writes the stable minimal setup receipt and exits 2. A separate poll-failure regression verifies that losing evidence after REST enqueue exits 4, not a negative task verdict. |
| 2026-09-27 | Letting the local extraction checker own the verdict | Round 1's `check.py` computed equality itself. The round-2 adapter contract failed against that behavior. It now only transports bytes; unchanged Promptfoo 0.123.1 assertions returned 0/100/100 for correct/wrong-price/malformed controls. Tests also refuse missing/modified reports and changed input bytes. |
| 2026-09-27 | Assuming a grader's echoed output is byte-identical to its input file | Native Promptfoo's positive control succeeded, but the first receipt observation rejected it because the echoed response omitted the input's final newline (413 versus 414 characters). Preserve the exact input/report hashes and account for outer whitespace in the transport-binding check; the upstream verdict still owns product equality. `test_upstream_grader_controls_and_type_strictness` failed on the positive observation before correction. |
| 2026-09-27 | Letting a forbidden-data substring match the grader's name | The old privacy test rejected the harmless `promptfoo` harness name because it searched for `prompt` anywhere. Test forbidden JSON keys and planted private-value markers, while retaining the exact allowed gateway columns. The focused receipt suite first failed on this substring. |
| 2026-09-27 | Testing host port validation behind an unrelated scratch-location refusal | The assigned external research scratch has a Git ancestor. The first host-parser fixture hit the private-state location guard before it exercised ports. Substitute only the location policy in this unit fixture; the focused port test then failed because 3710 was accepted, and passes with 3730..3799. Production location guards remain intact. |
| 2026-09-27 | Assuming a SQLite transaction context closes its connection | Python 3.13 exposed an unclosed-connection ResourceWarning during local receipt checks. The [Python 3.12 documentation](https://docs.python.org/3.12/library/sqlite3.html#how-to-use-the-connection-context-manager) explicitly requires `contextlib.closing` for lifecycle closure; both the read-only receipt connection and synthetic fixture connections now use it. |
| 2026-09-27 | Running a CLI help probe before scoping its writable state | The installed Promptfoo version/help probes attempted to rotate default log files and received EROFS. Every grading/version subprocess now gets private `PROMPTFOO_CONFIG_DIR`, `PROMPTFOO_LOG_DIR` and `PROMPTFOO_CACHE_PATH` plus disabled telemetry/update; no default logs were changed. |
| 2026-09-27 | Treating a tag's lockfile as compatible without checking its metadata | `uv.lock` SHA256 `c672410c737e3085cae56d948854596284b7ac55066a97d9241d91913e3bb8e9` lists `litellm>=1.53.1`; v0.9.4 `pyproject.toml` and release wheel require `unclecode-litellm==1.81.13`. Use a derived hash lock from release metadata, label it local, and do not claim `uv sync --locked` acceptance. |
| 2026-09-27 | Assuming every uv lock entry has a version | The read-only research probe raised `KeyError: 'version'` on the editable root. Corrected the probe to inspect source and optional version separately. No install was attempted. |
| 2026-09-27 | Treating omission of temperature in caller config as omission on the wire | `crawl4ai/utils.py:1825` injects 0.01. Override through upstream `extra_args` with `temperature=None`; verify omission in the pinned LiteLLM transport and leave live wire behavior a host check. |
| 2026-09-27 | Binding only the container interface would break its MCP proxy | `deploy/docker/server.py:1183-1190` calls loopback internally. Preserve an explicit loopback listener alongside the container-interface listener through Gunicorn's supported repeatable bind option. |
| 2026-09-27 | Combining equivalent uv flags | `uv pip compile --only-binary :all: --no-build` exited 2 because the flags conflict. Removed `--no-build`; `--only-binary :all:` already excludes source builds. |
| 2026-09-27 | Assuming the shell's research channel has network access | The first corrected uv compile exited 2 after DNS failures. The same metadata-only command through context-mode succeeded with caches inside this recipe. Nothing was installed. |
| 2026-09-27 | Treating an upstream test as authoritative over its implementation | `tests/mcp/test_mcp_sse.py` points at `/mcp`; the live tag implementation serves `/mcp/sse` and requires initialization/auth. The fixture probe follows `mcp_bridge.py:241-256` plus the official MCP SDK transport. |
| 2026-09-27 | Assuming host-owned secret mounts are readable by the image's appuser | Independent review and registry config confirmed `User=appuser`. Rootless Docker maps host-owned 0600 files to container root. Startup now runs as container root, reads secrets privately, initializes only dedicated state mounts, and native supervisor runs Redis/Gunicorn as appuser. |
| 2026-09-27 | Counting a GET at a WebSocket path as WebSocket auth evidence | The initial probe only made a GET; review caught it. The corrected probe performs an actual unauthenticated WebSocket upgrade and requires 401/403 handshake refusal. |
| 2026-09-27 | Accepting one correct gateway row for three logical calls | Review found an `any()` effort gate. The corrected receipt requires exactly three matching-model successful rows, all with expected upstream effort. Retries/concurrent same-model rows fail qualification for review. |
| 2026-09-27 | Embedding the image account's home path in a portable config | `python3 scripts/validate.py` rejected the initial Compose browser path as a possible personal home path. The wrapper now resolves the image's appuser home through its account database and sets the browser path dynamically, preserving the upstream layout without a committed absolute home path. |
| 2026-09-27 | Leaving the previous failed condition present in a negative control | Offline review found the empty-result control still active when testing missing native logs, and missing logs still active for wrong effort. Each control now restores other passing inputs and asserts those independent gates remain passing. |

## Dependency and browser artifact resolution

The locally derived wheel lock uses the official release requirement and
`uv 0.12.17`'s supported requirements compilation, without installing:

The command below records the historical round-1 invocation. Do not reuse its
in-repository cache argument: round-2 research and verification use only the
coordinator's assigned external scratch directory.

```
uv pip compile blueprints/runtime-workers/crawl4ai/requirements.in \
  --python-version 3.12 --python-platform x86_64-manylinux_2_35 \
  --generate-hashes --only-binary :all: --exclude-newer 2026-09-27T00:00:00Z \
  --cache-dir blueprints/runtime-workers/crawl4ai/.research/uv-cache \
  --output-file blueprints/runtime-workers/crawl4ai/requirements.lock --no-header --quiet
```

The resolver returned exit 0 without output. PyPI hashes are enforced at install
with `uv pip sync --require-hashes --only-binary :all:`; no source build or
unhashed build dependencies are permitted. This is our derived lock, not the
stale upstream `uv.lock`. Read [uv's supported workflow](https://docs.astral.sh/uv/pip/compile/).

Playwright 1.63.0's PyPI wheel hash was checked before reading its bundled
`driver/package/browsers.json` and `driver/package/lib/coreBundle.js`.
The bundle maps headless Chromium to revision 1243 / browser 153.0.8010.12,
`builds/cft/153.0.8010.12/linux64/chrome-headless-shell-linux64.zip`, and ffmpeg
to `builds/ffmpeg/1011/ffmpeg-linux.zip` (lines 32652-32660, 32911-32923,
33016-33029). Download URL override is at 33650-33675. Both CDN responses were
streamed into SHA256 during research; no archive was installed/extracted.
These are measured hashes of upstream HTTPS bytes, not upstream signed checksums.
`browser-artifacts.json` freezes the digests and byte counts. At install a
loopback-only, verified local mirror feeds the unchanged Playwright install
command, preventing that command from fetching unchecked browser archives.

The hash-verified `unclecode-litellm` 1.81.13 wheel exposes the native `extra_headers`
path. `litellm/utils.py`'s `base_pre_process_non_default_params` at 3588-3600
excludes values equal to their defaults; `pre_process_non_default_params` at
3649-3654 supplies the chat parameter defaults (temperature=None).
`get_optional_params` uses that filtering before mapping OpenAI parameters;
`get_standard_openai_params` at 9008-9013 also excludes None. This is source
evidence for overriding Crawl4AI's hidden temperature default, not a live wire
observation. Actual omission, effort routing, session affinity and header retention
remain host checks.

## Independent review

A bounded read-only research worker reviewed deployment, install state, receipt
scope and the frozen E2E. Findings about mapped container ownership, repeat-install
permissions, WebSocket auth controls, working-directory use, complete input hashes,
timestamp normalization, per-page effort checks and unconditional cleanup were
resolved in the recipe. The upstream container LLM-control gap and WebSocket
message-shape concern are retained as limitations in README.md. Review agreement
is not host acceptance. The coordinator independently re-read the relevant
upstream source and rehashed registry metadata/provenance before recording pins.

## Fail-first evidence

Before this directory existed:

```
python3 -m unittest discover -s tests -p test_runtime_worker_crawl4ai.py
exit 1
Ran 6 tests in 0.003s
FAILED (failures=3, errors=3)
```

The failures were missing recipe/check/fixture files and the errors were missing
worker configuration and installer. The command's actual returned output was
observed in the builder session. The compact record omits private absolute paths
from tracebacks. These are local structural checks, not unchanged upstream tests.
