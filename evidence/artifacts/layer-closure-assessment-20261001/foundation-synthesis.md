# Foundation closure synthesis (2026-10-01; input: foundation.json in this folder, repository revision 3361b342)

I found no foundation layer that is final for install. c2 is partial in all 20 layers. c4 is unmet in 17 and partial in 3 (instructions-skills, isolation, ci-supply-chain). c5 is partial in 19 and unmet in durable-memory. c1 is met in 9. All 20 refuter verdicts are `corrected`.

The input is dated 2026-10-01T03:50Z at root 3361b342. Statements marked "(checked)" come from my read-only spot checks of the worktree at 3361b342. Everything else comes from the named layer's assessment.

### 1. Ranking

**How the table is sorted:**
- **Gap score:** c1 + c2 + c4 + c5, scoring met 0, partial 1, unmet 2.
- **c3 is added only where a comparison is required.** That means the five layers research-state.json marks `comparison_required`: workers, document-retrieval, durable-memory, token-efficiency and quality-evaluation (checked).
- **Ties:** fewer unmet items first, then current pins, then a c1 fix that needs no new run. The remaining order within a tie is my judgement.
- **`distance` doesn't separate layers.** It is 4 wherever c1 is met and 5 wherever c1 is partial.
- **Install column** is `upstream_install_command_recorded`. No layer is rated `no`.
- **Next unit** is the assessor's, condensed and tagged by where it runs: [src] source-only, [cur] current NativeStack distro, [new] new distro, [TBD] host undecided.

| # | layer | score | distance | c1 | c2 | c3 | c4 | c5 | single blocking item | install | next unit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ci-supply-chain | 3 | 4 | met | partial | partial | partial | partial | c2: candidate set not re-recorded (tools in use, 09-26/29 survivors, 09-30 verdicts) | partial | [cur] fresh zizmor 1.30.1 + Syft 1.52.0 install, then the preregistered metric |
| 2 | isolation | 3 | 4 | met | partial | unmet | partial | partial | c2: no disposition for boxlite, microsandbox, brig, OpenSandbox, Lima, nsjail; bubblewrap omission open | partial | [new] clean-install receipt per winner via scripts/host_receipts.py |
| 3 | instructions-skills | 4 | 5 | partial | partial | partial | partial | partial | c1: verdict at stale pins (ECC dd6ee538 vs c70874fa); skills-ref unclassified | partial | [new] install-and-discovery receipt via the manifest-driven path |
| 4 | native-clients | 4 | 4 | met | partial | partial | unmet | partial | c2: ten sweep proposals not folded in; four contested campaign proposals not adjudicated | partial | [new] bootstrap foundation-cpu from main, sign in, rerun both recovery fixtures |
| 5 | mcp-surfaces | 4 | 4 | met | partial | partial | unmet | partial | c2: no consolidated set at served pins (55 of 59 registry sections unexamined) | yes | [new] receipts at mcporter 0.14.1 / Inspector 2.8.0 + daemon lifecycle fixture |
| 6 | observation-inference | 4 | 4 | met | partial | partial | unmet | partial | c2: 09-26 survivors have no disposition; eight proposals lack the fit vote | partial | [new] systemd user manager, then install/configure at current pins |
| 7 | scheduling-supervision | 4 | 4 | met | partial | partial | unmet | partial | c3: Dagu 2.16.6 failed the preregistered 150 s SIGKILL case, which Temporal passed | partial | [cur] two use-stage receipts reusing the verified Dagu binary |
| 8 | secrets-credentials | 5 | 5 | partial | partial | partial | unmet | partial | c1: alternatives omit betterleaks; 09-24/09-29 decision records not linked | yes | [new] gitleaks receipt per docs/secret-storage.md:326-427 |
| 9 | git-github-automation | 5 | 5 | partial | partial | partial | unmet | partial | c1: gh verdict pin `unpinned` (installed 2.101.0); no in-layer alternatives | partial | [src] re-record the verdict from existing evidence |
| 10 | semantic-rag | 5 | 5 | partial | partial | partial | unmet | partial | c1: winners 1.14.0/0.25.0 vs installed 1.15.0/0.30.0 | yes | [new] hardware_profile.py, then bootstrap with --allow-unpinned |
| 11 | hosting-services | 5 | 5 | partial | partial | partial | unmet | partial | c1: Next.js winner 16.3.5 vs lock 16.3.6 | partial | [cur] task-owned prefix; one upstream install command per prerequisite |
| 12 | code-navigation | 5 | 5 | partial | partial | partial | unmet | partial | c1: no public Serena find_referencing_symbols receipt | yes | [new] recorded upstream commands into the ecosystem prefix |
| 13 | recovery-portability | 5 | 5 | partial | partial | unmet | unmet | partial | c1: uv winner `unpinned` blocks every uv receipt | partial | [src→cur] bind the uv pin, then clean-install receipts |
| 14 | web-research | 5 | 5 | partial | partial | unmet | unmet | partial | c1: selection predates the 09-26 free-native-lanes decision | partial | [TBD] receipts for the three winners after identifying the host |
| 15 | agent-sdks | 5 | 5 | partial | partial | unmet | unmet | partial | c1: the Python SDK half rests on a private prompt and sealed receipts | partial | [src] move the SDK pins to the CLI pin and recompile the lock |
| 16 | quality-evaluation | 6 | 5 | partial | partial | partial | unmet | partial | c3: comparison on fresh independently labelled cases (TypeSafe arm, C4-blind label) | partial | [new] install-and-control receipt for both winners |
| 17 | document-retrieval | 6 | 4 | met | partial | unmet | unmet | partial | c3: sealed-corpus retrieval and layout/OCR comparison never run | partial | [TBD] name the host; markitdown 0.1.8 use receipt |
| 18 | workers | 6 | 4 | met | partial | unmet | unmet | partial | c3: preregistered arms (foundation.json:938-951) never run | partial | [new] workers-layer receipt at recorded pins |
| 19 | token-efficiency | 7 | 5 | partial | partial | unmet | unmet | partial | c3: repeated counterbalanced matched comparison at equal correctness | yes | [TBD] settle the release-tag gate, then profile receipts |
| 20 | durable-memory | 7 | 4 | met | partial | unmet | unmet | unmet | c3: preregistered comparison on a host named in a new amendment | yes | [new] foundation-cpu bootstrap from origin/main + disposable-store round trip |

### 2. Cross-layer patterns

**A. No second review (c4: 17 unmet, 3 partial).** The reviews on record are lane adjudications or per-gap receipts, and every one names open gaps. Representative texts:
- workers: "The existing adjudication only chose between the two lanes' winner sets, and the record still carries 10 open gaps."
- observation-inference: "The existing reviews covered only the winner selection and individual gap receipts, while the record still holds eleven open gaps and eight contested candidates."
- durable-memory: "Every review on record names material gaps that are still open."

**Unit:** one cross-family review per layer over the re-frozen set. It lists the target-host checks as declared install-receipt items, so c4 can pass before install.

**B. No closure record (c5: 19 partial, 1 unmet).** Only the 2026-09-22 verdict rows exist. They are verdicts, not closures, and they predate the later sweeps, host receipts and campaign.
- isolation: "only a dated verdict that is explicitly not saturated. That verdict predates the 09-26 and 09-29 sweeps, the 09-24/25 host receipts and the worktrunk v0.80.0 release."
- ci-supply-chain asks for "A dated layer closure record, registered through research-state closure_refs".

**Unit:** one dated closure-record template. It carries the bound pins, residual risks, untested boundaries, reopening triggers and the pending install checks. Each layer's record is registered in research-state.json `closure_refs`, which scripts/landscape.py:1319 reads (checked). It is issued in two stages: "final for install", then "closed".

**C. Candidate set not frozen (c2: 20 partial).** The layer candidate lists were checked on 2026-09-22 and never took in the 09-23, 09-26 and 09-29 sweeps. Several refutations rest only on a missing vote. The 09-30 campaign statuses exist only in a host-private file.
- native-clients: the layer record "does not fold in the proposals from the 09-23, 09-26 and 09-29 sweeps: opencode, gemini-cli, codex-acp, maka, prime-agent, jcode, goose, pi, hermes-agent and claude-agent-acp".
- scheduling-supervision: "Ten swept repositories have no omission record in the layer entry".
- mcp-surfaces: "55 of 59 registry sections unexamined".

**Unit:** a generated frozen candidate-set file per layer. Its sources are foundation.json `candidates`/`alternatives`, the proposals and refutations in catalogs/saturation/ledger.json, and a published campaign receipt. Each entry gets a disposition or omission reason, plus the failed-access entries. A check fails on any proposal without a disposition.

**D. Verdict pins don't match installed pins.** c1 is partial in 11 layers, and the winner pin differs from the installed pin in 14.
- recovery-portability: uv `unpinned` "blocks every uv host receipt".
- semantic-rag: installed versions "are refused without --allow-unbound-version".
- git-github-automation: "Reconcile gh's verdict pin to 2.101.0".

scripts/host_receipts.py:882-892 rejects `unpinned` and refuses any version that matches no winner pin (checked). Any new-distro receipt collected before a re-record would therefore not count.

**Unit:** one verdict re-record pass through tools/sota-convergence/record_verdicts.py, at pins decided first.

**E. No fresh-distro evidence (c3).** adoption/manifest.json:51 still says "second-machine acceptance pending" (cited by native-clients, semantic-rag and mcp-surfaces; checked). Under the staged rule this is the install receipt. Only the `comparison_required` layers need comparisons first.

**F. Profiles cannot install the selections.** In 16 layers at least one selected component is in no profile, has no Linux pin, or sits behind a profile that exits 3. The exceptions are native-clients, instructions-skills, durable-memory and token-efficiency.

**Unit:** profile and pins coverage, accepted when each profile bootstraps without --allow-unpinned.

### 3. Program units, in dependency order

U8 and U9 run in parallel with U3–U7, but must finish before U10.

| # | unit | layers | action | acceptance | where | owner lane |
|---|---|---|---|---|---|---|
| U1 | Program decisions | all 20 | Decide: (a) which record defines "comparison required" (see §6); (b) whether c2 needs a saturation candidate; (c) target host: new distro vs nativestack-5975wx-20260925; (d) install revision: a new tag at main, or bootstrap from main | dated decision record with overturn conditions; scripts/validate.py passes | source-only | coordinator / foundation |
| U2 | Pin-currency triage | 15 with `pin_is_latest: no` | For every pin in §4: hold with a reason, or move after qualification, once per shared component; Next.js first | every behind pin has a dated hold or a qualification receipt | holds source-only; moves need a run on the current host | foundation; memory (ai-memory, SocratiCode, hf hub); trading (Dagu recipe, SDK requirements) |
| U3 | Publish or drop campaign verdicts; rerun missing votes | 12 citing the private list; 8 refuted-by-absence (isolation, document-retrieval, semantic-rag, durable-memory, web-research, token-efficiency, recovery-portability, observation-inference) | sanitized receipt at a main commit; rerun missing discovery/fit votes | every cited status resolves to a committed file; no proposal decided by a `{missing: true}` vote | source-only (model calls) | foundation |
| U4 | Re-record pass (c1 + c2) | all 20 (c1 fix in 11) | One record_verdicts.py pass per layer: winners at U2 pins, alternatives, the candidate-set file from U3 + ledger, failed access, line references | host_receipts.py accepts each installed version without --allow-unbound-version; candidate-set check passes | source-only | foundation (stack.json edits go through the shared hot-file protocol) |
| U5 | Preregistered comparisons | 5 `comparison_required`; 10 if U1(a) adds `keep_but_compare` | run the frozen arms; keep failures and complete usage | preregistered metric met and independently reviewed | current or named host, not the install receipt | Gate A (workers, token-efficiency); memory (durable-memory); foundation (document-retrieval, quality-evaluation) |
| U6 | Second independent review | all 20 | one cross-family review per layer over the U4/U5 output | no unresolved material gap except the declared install checks | source-only | foundation; memory and keys for their layers |
| U7 | Stage-1 closure record | all 20 | write the template now; per-layer dated record after U6, registered in `closure_refs` | landscape checks pass; the layer is "final for install" | source-only | foundation (landscape owners) |
| U8 | Profile and pins coverage | 16 (pattern F) | Add selections to profiles and adoption/pins-linux-x86_64.json; script the prose-only installs; provision CPython 3.13.15, procps and srt prerequisites; fix the `orx`/`openresearch` id mismatch | each profile bootstraps on the hosted runner without --allow-unpinned; adoption_status.py clean | source-only | foundation; trading for the research-runtime profile and blueprints/us-equities recipes |
| U9 | Port and service-unit map for the shared WSL VM | durable-memory, quality-evaluation, scheduling-supervision, observation-inference, semantic-rag | Assign: ai-memory port 49374; 15432/18080/18081 vs ntfy; Dagu scheduler unit; systemd=true + linger; Collector unit; vLLM unit | committed map; on the new distro, no port conflicts and units survive restart | decide now; verify on the new distro | foundation; memory |
| U10 | Install receipts (the host part of c3) | all 20 | Bootstrap from the U1(d) revision; native sign-ins and the 0600 store; lifecycle stages via host_receipts.py with negative controls; append to the U7 record | receipts bind to the winner pins and pass the host checks; independent receipt review; layer closed | new distro | foundation; memory, keys and trading for their layers |

Owner lanes follow docs/lanes.md path ownership: blueprints/us-equities and the research-runtime profile belong to trading. Gate A owns the workers and token-efficiency comparisons per docs/decisions/2026-09-28-ecosystem-roadmap.md:67,75 (checked). Shared winners make one move serve several layers:
- worktrunk wins in workers, isolation and git-github-automation.
- claude-code wins in native-clients and workers.
- codex wins in native-clients and agent-sdks.

### 4. Selected pins behind the latest release

| layer | component | recorded pin | latest | source (as given) |
|---|---|---|---|---|
| native-clients, workers | claude-code | 2.1.284 floor (auto-updates) | v2.1.286 | https://github.com/anthropics/claude-code/releases/latest ; https://github.com/anthropics/claude-code/releases |
| native-clients, agent-sdks | codex CLI | 0.159.2 | rust-v0.159.3 | https://github.com/openai/codex/releases ; https://api.github.com/repos/openai/codex/releases/latest |
| agent-sdks | openai-codex + openai-codex-cli-bin | 0.154.0 | 0.159.3 | https://pypi.org/pypi/openai-codex/json |
| workers, isolation, git-github-automation | worktrunk | 0.79.0 | v0.80.0 | https://github.com/max-sixty/worktrunk/releases (/releases/latest in git-github-automation) |
| isolation | sandbox-runtime | 0.0.77 | v0.0.78 (one assessor read) | https://github.com/anthropics/sandbox-runtime/releases ; https://registry.npmjs.org/@anthropic-ai/sandbox-runtime |
| code-navigation | jcodemunch-mcp | 1.108.319 | v1.108.320 | https://github.com/jgravelle/jcodemunch-mcp/releases |
| semantic-rag | SocratiCode | 1.15.0 | v1.16.0 | https://github.com/giancarloerra/SocratiCode/releases/latest |
| semantic-rag | huggingface_hub | 1.32.0 | v2.0.0 (major) | https://github.com/huggingface/huggingface_hub/releases/latest |
| durable-memory | ai-memory | 2.4.1 | v2.5.0 | https://github.com/akitaonrails/ai-memory/releases ; https://api.github.com/repos/akitaonrails/ai-memory/releases?per_page=8 |
| web-research | OpenResearch | 0.2.7 | v0.2.14 | https://github.com/alphaXiv/OpenResearch/releases |
| token-efficiency | headroom | 0.37.0 (deliberate hold) | v0.39.1 | https://github.com/headroomlabs-ai/headroom/releases |
| scheduling-supervision | Dagu | 2.16.6 | v2.18.1 | https://api.github.com/repos/dagucloud/dagu/releases/latest |
| hosting-services | FastAPI | 0.141.1 | 0.142.2 | https://github.com/fastapi/fastapi/releases |
| hosting-services | Next.js | 16.3.5 / 16.3.6 | v16.3.8 (High fix GHSA-cjq9-62q9-8jv4) | https://github.com/vercel/next.js/releases |
| recovery-portability | uv | 0.12.17 | 0.12.21 | https://api.github.com/repos/astral-sh/uv/releases/latest |
| observation-inference | otelcol-contrib | 0.161.0 | v0.162.0 | https://api.github.com/repos/open-telemetry/opentelemetry-collector-releases/releases/latest |
| mcp-surfaces | MCP Inspector | 2.8.0 served | 2.9.0 | https://api.github.com/repos/modelcontextprotocol/inspector/releases/latest |
| git-github-automation | gh | 2.101.0 | v2.102.0 | https://github.com/cli/cli/releases/latest |

**Verdict-record pins that lag even though the installed pin is current:**
- rtk 0.49.0 and ccusage 20.0.24 (token-efficiency)
- markitdown 0.1.7 (document-retrieval)
- vLLM 0.25.0 (semantic-rag)
- mcporter 0.13.13 and Inspector 2.7.0 (mcp-surfaces)
- Prometheus 3.14.0 (observation-inference)
- ECC dd6ee538, an ancestor of c70874fa (instructions-skills)

Profile components that are not winners are also behind: Grafana and AgentsView (observation-inference), and Beads (workers).

**`pin_is_latest: unknown`:** none. All 20 layers recorded `yes` (5) or `no` (15). Some component-level checks are softer than that:
- systemd is pinned to an Ubuntu package (255.4-1ubuntu8.17). The assessment compared it with upstream v262 but did not check the Ubuntu 24.04 update candidate (scheduling-supervision).
- tavily-cli's latest version was inferred from PyPI `urls` (web-research).
- Serena is pinned to a main commit, with main 35 commits ahead and no newer release (code-navigation).
- Most "latest" values rest on a single assessor read that the refuter did not repeat.

### 5. Install-readiness gaps (the 14 `partial` layers)

| kind | layer: missing step (condensed) |
|---|---|
| No upstream install command recorded | isolation: no command for srt prerequisites (bubblewrap, socat, ripgrep); no apparmor userns check. document-retrieval: poppler has no Linux pin or bootstrap path, and recipe_map points to the Mac recipe. web-research: OpenResearch is a procedure only; agent-browser's browser download is unscripted; the Tavily installer resolves an unpinned version. quality-evaluation: no retained run of the promptfoo command; Chrome for Testing and seven .deb extractions are prose. ci-supply-chain: two zizmor methods, neither canonical. scheduling-supervision: the Dagu recipe lacks extraction and placement. hosting-services: pnpm, gcc/make/perl, bison/flex/m4, Chrome libraries and Chrome for Testing are prose or missing. recovery-portability, agent-sdks: nothing provisions CPython 3.13.15; restic has no literal command; the worker isolation launch exists only as a gap-wave2 helper. observation-inference: the repo-authored install.py is not an upstream command; the Collector unit placeholders are filled by hand. git-github-automation: the worktrunk recipe is prose and the scripted installer is not linked. instructions-skills: TypeSafe/OpenAI skills point to unpinned npx calls. |
| Recipe exists, not in an adoption profile | workers: Worktrunk (recipe_map only). isolation: worktrunk and srt (no pins or npm integrity). document-retrieval: context-hub. web-research: all three winners, and pin id `orx` vs component_id `openresearch` would fail closed. quality-evaluation: promptfoo and playwright-test. ci-supply-chain: zizmor, syft and attest. scheduling-supervision: the research-runtime profile exits 3 (nine of eleven ids unpinned). hosting-services: all four components. recovery-portability: restic and qdrant unpinned. observation-inference: no entries in pins-linux. agent-sdks: only reachable through the research-runtime detour. git-github-automation: worktrunk, difftastic and codex-for-claude. |
| Native sign-in or user step | native-clients: codex login + Claude device flow; daemon_auto_start=false. workers, isolation, scheduling-supervision, ci-supply-chain: signed-in gh for release downloads. instructions-skills: installs only through install_skills.py --skills-bin. web-research: Tavily key from the 0600 store. recovery-portability: sign-ins, client rebinding and a recoverable restic key. observation-inference: manual exporter settings merge. agent-sdks: interactive codex login. git-github-automation: marketplace install, /codex:setup, sudo for apt. hosting-services: unrecorded whether the WSL sandbox blocks pnpm, initdb or a loopback database. |
| Service/port decision on the shared WSL VM | quality-evaluation: ports 15432/18080/18081, and ntfy holds 18080. scheduling-supervision: the unit runs `dagu server`, not the scheduler; systemd=true and enable-linger are untested on a cold boot. observation-inference: a systemd user manager is required and the units don't enable lingering. |
| Pin/recipe drift | native-clients: recipes/README.md:86 still installs claude-code 2.1.278. workers: the bootstrap keeps an existing ≥2.1.284 launcher without hashing it. instructions-skills: the recipe and the manifest give different ECC refs. observation-inference: acceptance scripts are hard-wired to Prometheus 3.14.0. |

The six layers rated `yes` still have missing steps:
- durable-memory: port 49374 is held by another distro on the shared network namespace, and no Linux service unit is committed.
- semantic-rag: the bootstrap exits 3 without --allow-unpinned.
- code-navigation, mcp-surfaces, secrets-credentials: components outside every profile.
- token-efficiency: the Context Mode plugin needs a hand-written marketplace.json.

### 6. Contradictions and surprises

**Your decisions**
- **A selected winner failed its own preregistered case (scheduling-supervision).**
  - Dagu 2.16.6 failed the 150 s SIGKILL recovery case. Temporal passed it in 15.1 s.
  - Dagu recovered (about 182 s) only in a post-hoc variant labelled a deviation (evidence/artifacts/gap-wave2-20260923/foundation__scheduling-supervision/6-executed-challenger-comparison.json:32-33,40; checked).
  - c1 is still rated met. I'd treat this layer as a reopen candidate, not as nearly closed.
- **The repo's two records disagree on which layers need a comparison (checked).** research-state marks 5 layers `comparison_required`; foundation.json marks 9 `keep_but_compare`.
  - quality-evaluation is `comparison_required` but marked `retain`.
  - semantic-rag, scheduling-supervision, recovery-portability, observation-inference and secrets-credentials are `keep_but_compare` without `comparison_required`.
  - U1(a) has to pick one.
- **Is "frozen" (c2) the same as saturation? (checked)**
  - isolation, ci-supply-chain, token-efficiency, recovery-portability, observation-inference and secrets-credentials read "frozen" as needing three clean sweeps at least 7 days apart (the ledger's K=3, min_gap_days=7).
  - scripts/saturation_ledger.py:28-30 calls a saturation candidate "only an input to closure". recipes/saturation-sweep.md:180, by contrast, ties `closure_refs` to reaching that candidate.
  - If clean sweeps are required, closure is at least 14 days away, and every sweep so far has had survivors.
- **The assessors' next units mostly come last under the staged rule.** 18 of 20 next units collect host receipts; only git-github-automation and agent-sdks start source-only.
  - Four target the current NativeStack distro, not a new one: ci-supply-chain, scheduling-supervision, hosting-services and recovery-portability.
  - Some c4 texts wait for new-host receipts, which inverts the staged order. instructions-skills: "After the comparison and the new-host receipt". hosting-services: after "the new-host receipts are closed".
- **durable-memory has an open operator decision.** The live-store isolation breach is recorded as "unresolved; needs an operator decision".

**Record contradictions**
- **Manifest selection differs from the foundation.json winners.**
  - token-efficiency: catalogs/foundation/manifest.json:104 adds jCodeMunch and omits ccusage (checked).
  - ci-supply-chain: manifest :122 names seven tools against three winners (checked).
  - native-clients: manifest :23 adopts an OmniRoute gateway that no verdict selects.
  - MCPorter is `selected` at foundation.json:84 and `out_of_scope` at :156 (checked).
  - Selected-versus-alternative conflicts also exist in workers (Codex), web-research (Playwright CLI), observation-inference (six profile tools), document-retrieval (Context Hub), instructions-skills (skills-ref) and hosting-services (React).
- **Practices, not repositories.** Seven layers select a practice with no pin: instructions-skills, code-navigation (ripgrep is pinned only in a blueprint), web-research (evidence class "none"), quality-evaluation, recovery-portability, mcp-surfaces and secrets-credentials.
- **Unpinned winners in the record.** uv (foundation.json:4045), gh (:5085), actions/attest (:3224) (all checked), plus the TypeSafe and OpenAI skills in instructions-skills.

**Install path and evidence**
- **The release tag installs older pins.** Bootstrap step 0 checks out v2026.09.26.2 (checked). That installs codex 0.155.1 and claude-code 2.1.281 and predates ccusage 20.0.26.
- **Evidence outside the repository.** 12 assessments cite the host-private 09-30 campaign list by line number. The native-clients and agent-sdks prompts are also private.

**Upstream and version signals**
- **Upstream signals on selected components.**
  - gitleaks is "feature complete", with security patches only and focus moved to Betterleaks (secrets-credentials).
  - Context Hub has had no default-branch commit since 2026-07-01 (document-retrieval).
  - Next.js 16.3.8 fixes a High-severity issue above both recorded pins (hosting-services).
- **Version skew.** agent-sdks runs SDK 0.154.0 against CLI 0.159.2. semantic-rag's embeddings unit example still names vllm-0.25.0.

**Cited files.** I found no missing repository file among the cited paths at 3361b342. I did not re-check line numbers; several assessments report drifted line references themselves.

**What I did not verify:** I re-fetched no upstream releases, so every "latest" value is the assessments'. The tie order and the owner lanes are my inference.

Token tools: Context Mode `ctx_execute`, used to parse the 616 KB input and run the path checks without loading the raw JSON; Grep and Read for spot checks.
