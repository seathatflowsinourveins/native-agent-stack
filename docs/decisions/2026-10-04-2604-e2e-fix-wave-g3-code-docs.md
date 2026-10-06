# G3 E2E plan repairs: code navigation and document reading

Date: 2026-10-04. Scope: bounded builder `fix-wave-g3-code-docs`, on
`PR #684's head`, for `code-navigation/serena`,
`code-navigation/structural-search` and `document-retrieval/mineru` only.

The north-star action is dependable source navigation and local document
reading while building US-equities research and historical simulation. This
change repairs installation and acceptance recipes; it performs no trading
research, target-distribution installation, provider call or GPU inference.

## Evidence and decision

The original `context-1.json` and `context-2.json`, their independent GPT
reviews, and the Opus adjudication were read from the supplied private
coordination directory. The task's `fixes.json` was absent at lookup; the
per-slot review and adjudication supply the actionable fixes. The earlier
`job-030-2604-install-repair/plan-fix.patch` and report contain no hunk for these
three slots, so no prior repair was ported. Private executor paths and raw
streams are not published here.

The bounded task stays on GPT Sol at the requested max effort. No child,
cross-family lane or additional independent review is launched by this builder;
the supplied adjudication settles the structural-search and MinerU conflicts.
The available `search-first` quick workflow supplied primary-source retrieval,
and the diagnosis workflow used the already returned E2E failures and a local
recipe checker. Reproducing the failures on the destination is outside this
job's express no-distribution-execution boundary. Scoped ai-memory retrieval
was attempted but the MCP call was refused under the installed approval policy;
canonical checkout and original upstream source were used directly.

1. **Serena uses the already selected source pin and a working Python project.**
   The install plan's PyPI 1.7.0 selection disagreed with the stack, new-host
   profile and architecture's `c6fbd1c5932df2494ffa0020af5a9fbe80b82143`
   (`2.0.0.dev0`). Align the plan to that existing pin, add Python to the
   effective local project override through upstream's YAML helpers, then
   index. The override retains other keys and languages. README initialization
   runs in an isolated `SERENA_HOME`; upstream's project health-check checks
   symbol and reference operations in the checkout. The existing F8 writer
   already registers both native MCP contexts. Add fresh-session acceptance
   that requires returned successful symbol and reference tool results from
   both clients. [Upstream initialization](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/README.md#L237),
   [project override](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/config/serena_config.py#L723),
   [atomic YAML writer](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/util/yaml.py#L214),
   [upstream health-check](https://github.com/oraios/serena/blob/c6fbd1c5932df2494ffa0020af5a9fbe80b82143/src/serena/cli.py#L957).
2. **Structural search restores the published rewrite preview.** The Opus
   adjudication rejects the review's cargo-llvm-cov source-build stage: it
   would test a different binary and introduce another toolchain. Keep the
   mise/aqua installed 0.45.3 binary, its search check and the complete
   unchanged README rewrite example. Require the replacement in output and
   exactly exit 1 on a nonmatching input. Guard that expected failure for
   `bash -e`. No apply flag is used. Client use through PATH already satisfied
   the adjudicated wiring/fresh-session bar. [Published example](https://github.com/ast-grep/ast-grep/blob/0.45.3/README.md#L84),
   [no-match exit code](https://github.com/ast-grep/ast-grep/blob/0.45.3/crates/cli/src/run.rs#L349).
3. **MinerU installs its native skill and local Standard capability.** Keep
   4.0.10's base CPU-capable ONNX plus llama.cpp option, with `needs.gpu: false`.
   Install the unchanged skill from the peeled release commit
   `c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93` through the existing pinned
   Skills CLI and repository installer. Since the shared adoption manifest is
   outside this builder's ownership, pass a scoped
   `config/mineru-skills-manifest.json` through the installer's supported
   `--manifest` option. That retains the adjudication's pinned native route
   without touching another owner's file. Disable telemetry, download and
   verify Standard models, set managed tier before managed mode, and retain
   the upstream server start/stop/status lifecycle in the row. Functional
   acceptance waits for healthy local Standard support and checks parse/read
   of the pinned upstream public PDF. Fresh sessions must return successful
   CLI tool output through each client's installed skill. [Base engines and
   CPU requirements](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L448),
   [native upstream skill](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/skills/mineru/SKILL.md),
   [supported manifest argument](https://github.com/seathatflowsinourveins/native-agent-stack/pull/684/files),
   [setup order](https://github.com/opendatalab/MinerU/blob/c221cc41bc911ad0df3eaeda97acf6a1bfe9bf93/README.md#L559).

## Alternatives and overturn conditions

- Keeping Serena 1.7.0 would keep the plan/selected-pin mismatch. A later
  source-backed selection can replace the pin after native project operations
  and fresh sessions pass. The full upstream developer suite remains a
  separate profile evidence class; the installed-tool health-check is the
  appropriate local acceptance here.
- The ast-grep source coverage stage remains an alternative for development
  of ast-grep itself. Reopen the installed-binary decision if the published
  rewrite preview fails at the selected release, or upstream replaces it with
  a maintained release-binary acceptance command.
- MinerU `[full]` is the upstream high-throughput NVIDIA alternative. Adopt
  it only with evidence for its Python wheels and available GPU resources
  beside the model server. Base Standard is documented to work on CPU with
  at least 8 GB RAM and avoids making shared VRAM an installation dependency.
  A measured failure of local Standard quality or performance on the intended
  workload would reopen this choice. Remote parsing and Flash quality are
  separately authorized choices; this recipe selects neither.
- Promoting the scoped MinerU skill entry into the shared adoption manifest
  is a later coordinator integration option. It would replace the scoped
  manifest operand after preserving the same source, tree and file hashes.

## Corrections and completeness critic

The earlier recipe's successful `serena init` did not prove symbol navigation;
the returned E2E language-server error and upstream health-check source establish
that gap. The structural-search review was correct about missing rewrite
coverage but its source-build fix was rejected by adjudication. Removing `-r`
from the published example had removed the operation the slot promises. MinerU's
successful help command is authentic upstream installation verification, while
its missing skill and local tier prevented native workflow readiness. Missing
torch is not a defect for the published base package.

The completeness pass checked installation identity, project language state,
upstream executable acceptance, both native clients, parser service readiness,
model provisioning order, returned content, telemetry and remote boundaries,
and retention of original private output. It also caught the bounded-path
conflict in the adjudication's suggested shared skills-manifest edit and uses
the already supported scoped-manifest route. The next document-layer sweep
should consider images, tables, formula fidelity and multi-page continuation;
one public PDF page does not qualify those modalities. The next navigation
sweep should exercise the target workload's additional languages and worktree
activation. These are bounded coverage limits, not claims of passed execution.

## Acceptance and remaining work

The g3 checker was run before fixing the recipes and reported nine explicit
gaps. After the row/function fixes it passes with the same 80-row inventory:
56 installed, three measurement-only and 21 excluded; 129 install commands
and 81 acceptance entries. The ordinary consistency checks remain intact.
The post-install rewrite control preserves the actual command status under
`bash -e`; native-session assertions inspect successful returned tool events,
not a model's final readiness statement. Their contracts are [Claude's native
headless CLI](https://code.claude.com/docs/en/headless), [Codex's native
noninteractive CLI](https://developers.openai.com/codex/noninteractive) and
[the pinned Codex event types](https://github.com/openai/codex/blob/rust-v0.160.0/codex-rs/exec/src/exec_events.rs#L263).

All changed recipe and manifest bytes still require the coordinator's evidence
registry update; this builder leaves `manifests/evidence.json` untouched. The
existing aggregate header prose is also left for its owner to reconcile.
No canonical stack/profile/architecture pin changes: the Serena recipe aligns
to their existing selected pin, and both other tools retain their pins. The
handbook's input sources therefore remain unchanged. Actual host installation,
model verification, parser inference and the new fresh-session stages remain
owed after this bounded plan repair. Private native JSONL and parser artifacts
are retained outside the checkout. No new user identity, privacy selection or
sign-in is requested by this recipe; the clients' existing native sign-ins are
prerequisites of their `after_sign_in` stage.

The required four-module unittest command ran with TMPDIR set to the designated
worktree directory, outside `/tmp`: 324 tests, exit 1, 84 failures and 12 errors.
The shared RTK owner manifest still names 0.50.0 while the supplied HEAD's stack
already names 0.51.0, and that HEAD's generated Codex instruction block is stale
against its unchanged RTK template. Those files are outside the g3 ownership.
A pristine HEAD archive reproduces every failure/error name from the modified
checkout; its three additional LocalModelAcceptance failures were caused by
the archive's missing `.git` preflight marker, and all six tests of that class
pass after adding that fixture marker. No new failure/error names occur in g3.
The remaining shared regeneration and RTK pin reconciliation belong to the
coordinator or their area owner.

Correction: the initial hypothesis that the changed install plan invalidated
an embedded instruction-block digest was wrong. The native writer's
`block_text` and `generate_blocks` functions filter source text; there is no
embedded plan digest. Comparing generation with the original HEAD plan and
the modified plan yields identical blocks. The only stale block differences
are the pre-existing RTK exception prose and heading. Verification path:
`tools/adoption/new_wsl_client_config.py:710,852,863`, the original HEAD plan
from `git show`, `adoption/templates/codex.AGENTS.template.md:54` and
`adoption/new-wsl/codex-user-instructions.md:54`. The earlier optional request
to refresh a generated digest therefore requires no action in this builder.

`check_plan.py`, both scripts' `bash -n`, the handbook `--check`, and
`git diff --check` pass. All 20 inner shell programs parse; twelve synthetic
native-event controls pass (four successful-return controls, eight rejection
controls for a failed tool or a model declaration alone). These controls are
locally authored assertion checks and establish no upstream or native-session
acceptance. Upstream scratch source and raw test output remain outside the
checkout so the publication scan checks the proposed public changes only.
The final publication validation is expected to exit 1 solely for the six
changed evidence files' digest/byte drift and the new skill manifest requiring
hash registration. The coordinator owns that registry update.
