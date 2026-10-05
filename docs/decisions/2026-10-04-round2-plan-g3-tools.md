# Round-2 plan rows: optimization, skill vetting, trajectory analysis and MCP conformance

Date: 2026-10-04. Builder: GPT Sol at max, preserving the job's explicit pin.
Status: bounded install-plan implementation; destination commands
are UNRUN. North-star action served: reproduce the foundation for complex
engineering and US-equities research and historical simulation on NativeStack2604.

The selection is the owner's repository-quality rule and the verified `wave5`
batch in [the round-2 decision](2026-10-04-final-architecture-round2.md) and
`evidence/artifacts/final-architecture-round2-20261004/verdicts.json`.
This job implements its four assigned owners and conducts no candidate trial.

## Sources and installation boundaries

- **DSPy 3.4.0**: `stanfordnlp/dspy@3.4.0:README.md:31`, tag commit
  `2413b67a4d08a476e4bc6f40b9f8f42f87711ee7`. Install the published,
  SHA-256-verified DSPy and GEPA 0.1.4 wheels into a dedicated uv project;
  DSPy's declared `gepa[dspy]==0.1.4` is `pyproject.toml:37`.
  [PyPI DSPy metadata](https://pypi.org/pypi/dspy/3.4.0/json) and
  [GEPA metadata](https://pypi.org/pypi/gepa/0.1.4/json) supply the digests.
  `astral-sh/uv@0.12.22:docs/guides/projects.md:139` supplies project dependency
  management; `docs/concepts/projects/dependencies.md:412` supplies file sources.
  Preserve the resolved `uv.lock` and installed dependency inventory privately;
  LiteLLM's open constraint is not silently converted to an unverified fixed pin.
  Acceptance uses unchanged `tests/teleprompt/test_gepa.py:632,776` and
  `tests/predict/test_predict.py:1` through upstream pytest, plus a separate
  documented LM call after provider readiness
  (`docs/docs/learn/programming/language_models.md:139,151`). Skill description
  and trigger optimization remains with skill-creator.
- **SkillSpector CLI 2.12.0**: `NVIDIA/skillspector@v2.12.0:README.md:45`, commit
  `c7958a3268d9498644b22edb75d0f051bbc8cbfc`. Use its documented `uv tool install`
  Git route at that commit, without `[mcp]`, an install hook or automatic skill
  approval. Release asset SHA-256 values are recorded separately from the Git
  installation source; [the release API](https://api.github.com/repos/NVIDIA/skillspector/releases/tags/v2.12.0)
  publishes them and supplies no signature or provenance attestation.
  CLI acceptance uses the unchanged `tests/unit/test_cli.py:17` and
  `tests/unit/test_agent_cli.py:1`; `.github/workflows/ci.yml:97` runs upstream
  pytest via `make test-ci`. Semantic acceptance is optional after the existing
  Codex native sign-in, using `SKILLSPECTOR_PROVIDER=codex_cli`
  (`src/skillspector/cli.py:560,586`), and requires reported semantic execution
  and inspection completeness. Findings remain advisory beside source review
  and skills.sh audits. The repo lock is not misrepresented as a uv-tool lock.
- **Inspect Scout 0.5.3**: `meridianlabs-ai/inspect_scout@0.5.3:docs/index.qmd:28`,
  commit `0e8fc055a3cebba1a14c11bc35856767b6405173`. Extend the existing
  Inspect AI 0.3.273 uv-tool environment, retaining its OpenAI 3.24.0 dependency,
  and include Harbor 0.23.0 there for ATIF. Do not create an `inspect-scout`
  tool environment or install another Inspect AI.
  `pyproject.toml:24` requires Inspect AI >=0.3.268; the installed owner 0.3.273
  satisfies that bound, so no owner pin moves to 0.3.276.
  `astral-sh/uv@0.12.22:docs/guides/tools.md:225,229` documents `--with` and
  `--with-executables-from`. Hash-verified Scout and Harbor wheels are used in
  that owner environment. Acceptance runs unchanged grep, Claude import and
  ATIF import tests (`tests/grep_scanner/test_grep_scanner.py:1`,
  `tests/sources/claude_code_source/test_integration.py:210`,
  `tests/sources/atif_source/test_integration.py:44`). The destination check then
  uses upstream `scout import` and `scout scan` with its own grep scanner over
  one operator-selected current Claude session containing Agent/Task and one
  selected Harbor trajectory (`src/inspect_scout/_cli/import_command.py:317`,
  `docs/db_importing.qmd:238,281`, `examples/scanner/grep_examples.py:102`).
  Its private local database may contain related same-slug Claude sessions,
  as upstream's importer documents in `sources/_claude_code/transcripts.py:76`.
  No cloud scanner or model is needed. Direct Codex-rollout import was not found
  in the tagged source list and 0.5.3 release notes; this plan uses Harbor ATIF.
- **MCP conformance**: `modelcontextprotocol/conformance@c321dd32035556e6769d3724a8ee97d87c3faaac:README.md:12,23,147`,
  npm `@modelcontextprotocol/conformance@0.2.0-alpha.11`. Invoke only on demand
  through versioned npx, verify the
  [published npm integrity](https://registry.npmjs.org/@modelcontextprotocol%2Fconformance/0.2.0-alpha.11),
  and retain the unchanged `npm ci`, `npm run check`, `npm run build`, `npm test`
  acceptance from `.github/workflows/ci.yml:33`. HTTP server and scenario-client
  checks require an operator-selected destination and, if needed, its reviewed
  expected-failures baseline (`README.md:59,79,188`). No server is registered
  in either client. Keep alpha.11 until alpha.12 becomes eligible at
  2026-10-08T12:07:36Z; eligibility does not rewrite a pinned plan automatically.
  Alpha.12's publication from a non-main branch is not cited as a main commit.
  The verdict's cooldown and harness-fix caveats remain in the row.

## Native client access and READY

All four owners are SDKs or on-demand shell CLIs. Their public invocation paths
are the existing native shell and `~/.local/bin` PATH wiring in
`adoption/new-wsl/client-config-map.json`. They require no new client setting,
MCP registration, hook or permission rule, so the map is unchanged. Both clients
can invoke the same uv project, SkillSpector executable, shared-environment
`scout` executable and pinned npx command. Source import is not a client hook.

The conformance row is selected (`installed: true`) but named-only and
`on_demand: true`: a full plan skips it, while `--only mcp-protocol-conformance`
prepares the pinned invocation and runs its upstream acceptance. It installs no
global npm executable. Tool-specific commands use user scope; the existing
wrapper's shared clean-host apt prerequisite is separate from these four
rows' own unprivileged commands; each row declares needs.sudo=false.

The non-provider upstream tests are the post-install gates. Destination gates
that depend on a provider sign-in, selected transcripts, privacy choice or HTTP
endpoint are recorded as `needs_user`, with fail-closed input guards. They are
implemented but are not reported as passed. Existing sign-ins remain native;
no credential file is read or copied.

## Alternatives and overturn

Standalone GEPA would introduce a second optimizer owner; the inherited held-out
Inspect comparison can overturn DSPy. SkillSpector's MCP/install-hook modes
would exceed its advisory CLI boundary. A separate Scout uv tool would create
a second Inspect AI, contrary to the verdict. The owner's 2026-10-03 cooldown waiver was considered but is not used here:
alpha.12 was published from a non-main branch, this row runs only when named,
and this recipe claims none of alpha.12's harness fixes. Waiting remains compatible
with the permissive waiver. The final owner decision retains the Monocle and MCP
Inspector comparisons as removal checks; this plan invents none.

Completeness critic: checked runtime isolation, upstream test entry points,
published wheel/package integrity, both native client shell paths, provider-free
operation, semantic sign-in, current-session privacy, ATIF's Harbor dependency,
direct Codex import limits and the alpha cooldown. The next lifecycle sweep must
recheck alpha.12's eligibility and fixes and Scout's direct-Codex import issue.
No new skill candidate is installed: search-first and modern-python supplied
the applicable installation guidance. Scoped ai-memory retrieval was attempted
but the tool required approval while this sandbox's approval policy is never;
current canonical files and original upstream source were used.

## Integration handoff

Corrections verified this turn: the existing checker reads each install
`run_command` from one physical line (`this PR: check_plan.py:45-54`), so the
owned multiline install quotations were replaced with equivalent single-line
shell programs after the checker exposed an unterminated-quotation error.
SkillSpector's internal metadata builder does not name the public JSON field:
`NVIDIA/skillspector@c7958a3268d9498644b22edb75d0f051bbc8cbfc:src/skillspector/nodes/report.py:1337,1350`
renders `metadata` and top-level `execution_successful`; the planned semantic
predicate now uses those exact fields.

Scout's `ScanResultsDF` inherits an error **list**, rather than a dataframe
(`meridianlabs-ai/inspect_scout@0.5.3:src/inspect_scout/_recorder/recorder.py:58,133`).
The destination predicate was corrected to `not results.errors`, and native
`scan_list` (`src/inspect_scout/_scanlist.py:7`) supplies the actual scan locations
instead of an assumption about the recorder's directory layout. Scanner names
are read from the native result mapping. The Node prerequisite declarations now
use the existing checker's individual `for slot` bootstrap form, so the
on-demand conformance row is covered when selected alone.

The coordinator owns `manifests/evidence.json`, `owners.json` synchronization,
shared row/stage counts, and the other groups' rows. This builder leaves shared
count comments unchanged and records the added rows/stages for integration.
No branch-local commit is cited and no commit is made. Host runs remain owed.

The final scoped checker reports no problem naming these four slots. Its actual
exit is 1 with four integration problems: the other groups' agent-messaging
owner/install state, playwright-cli state and the coordinator-owned `owners.json`
mirror. The starting snapshot reports seven problems. Both shell syntax checks,
the existing client-map check, handbook check and whitespace check pass.
`validate.py` exits 1 with evidence-registry hash/byte/listing drift only; the
coordinator retains registry ownership.

The required four-module native unittest suite ran 347 tests and failed the
same 15 test names as an independent source snapshot of the supplied base:
332 passed and there are no new failing test names. The remaining failures
include the other groups' pending plan rows and wave-5 expectations for counts,
owner batches, render names and the old browser split. No test or shared count
was edited to hide these integration failures. Actual returned output is kept
outside the checkout, rather than promoted to a candidate's upstream acceptance.

The exact requested `TMPDIR` was set for both native suite runs, but that
directory is read-only under this workspace-write sandbox. Python used its
external `/tmp` fallback. A write preflight returned `Read-only file system`;
no temp path was placed inside either checkout. The coordinator must provide
write access to the prescribed cache path to repeat the test under that exact
filesystem condition.


Repair 2026-10-05: Inspect AI is the only installer of its uv tool environment.
It installs Scout 0.5.3, Harbor 0.23.0 and the upstream pytest dependencies
together with its existing OpenAI SDK, and exports the scout executable. A named
trajectory-analysis run dispatches that owner first; its own commands only
prepare source, verify the scanner and record acceptance. Running inspect-ai
last preserves the same complete requirement set.

Operator DSPy runs must call `dspy.configure_cache(enable_disk_cache=False)`
before using their LM; keep GEPA log_dir and wandb/mlflow integrations off.
This prevents prompts and completions entering the default on-disk DSPy cache.
The option is native at
[stanfordnlp/dspy 3.4.0 dspy/clients/__init__.py:19](https://github.com/stanfordnlp/dspy/blob/2413b67a4d08a476e4bc6f40b9f8f42f87711ee7/dspy/clients/__init__.py#L19).
Installed-wheel upstream tests now use Python -P with pytest importlib mode and
require dspy.__file__ within the intended virtual environment. SkillSpector
acceptance also scans the pinned upstream malicious_skill fixture, requiring
nonempty findings and a nonzero fail-on-findings result alongside the safe
control. These are still unrun destination recipes.
