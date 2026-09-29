# Roadmap record: the ecosystem's next moves, current architecture, recorded targets and gaps (2026-09-28)

**Status:** a dated roadmap. It **decides nothing new and changes no authority.** Every owner, gate and user decision below is quoted from an existing record, a PR or a peer's own statement. Moves become work only when their owner takes them.

**Requested by:** the user, on 2026-09-28: "what is the next moves for our ecosystem evolve? grand roadmap, current architecture, and the sota convergenced one, gaps".

**Snapshot:**
- origin/main `83229e24`, read at about 22:00Z on 2026-09-28;
- 29 open PRs, 20 of them `CONFLICTING`;
- paper units `paper-ext-20260928-chain4` and `incentive-monitor-20260928` active at that time.

Recheck drift before acting on any line here. Known drift at publication: #425 (the OpenHands recipe) merged at 22:57Z as `f6e5a038`, so 28 PRs remain open.

## Method

- **Workflow.** A read-only Ultracode run, `wf_04132aa1-bf4`, with 25 children, all `claude-opus-5-5` at effort `max`. Its `child-usage.mjs` status is `complete`. Provider-returned usage was 5,333 input, 712,312 output, 219.4M cache-read and 5.6M cache-write tokens. Advisor usage is outside these counters (see `examples/claude-native/workflows/README.md`).
- **Mapping.** Six `stack-researcher` mappers covered the 20 foundation and 12 us-equities layers. They took current state from what is installed and merged, not from the catalogs. Two more mappers covered gate/PR state and the architecture tiers.
- **Checks.**
  - Each map had one adversarial refuter: `evidence-reviewer`, or `stack-verifier` for the gate/PR map.
  - A completeness critic raised 6 items, and each got a `stack-researcher` follow-up (8 mappers + 8 refuters + 1 critic + 6 follow-ups + 1 synthesis + 1 order review = 25 children).
  - One synthesis followed, then an `evidence-reviewer` refutation of the move order. It returned 13 corrections (`ordering_ok: false`), and all are applied here.
  - Owner acceptances came back from peers over SendMessage after the run.
  - The run's journal and `child-usage.mjs` output are session-local and are not retained in this repository. Every claim below rests on its cited repository path, PR or command, not on the run itself.
- **Evidence classes** follow `docs/acceptance-evidence-policy.md`: LA = live acceptance, IC = our integration check, UT = unchanged upstream tests, SR = source review.
- **Deliberately not done: no live landscape sweep.** On 2026-09-27 the user held the full 32-layer sweep until Gate A and Gate B pass, so upstream currency here is as recorded. The latest sweep is `catalogs/sota-convergence/manifest-20260926.json`.

## Verdict

The foundation is broad and runs, but **none of the 32 layer targets is confirmed**:
- `manifest-20260926.json` records `components_confirmed: 0`;
- 64 pins lag upstream, across 33 components, all `not_individually_reviewed`.

The recorded targets are the 2026-09-22 verdict winners (`catalogs/sota-convergence/layer-verdicts-20260922.json`), amended by later user decisions. The 2026-09-26 sweep is a degraded candidate ledger:
- 71 of its 287 candidates carry a `gpt-6-astra` fit vote whose reasoning reads only "missing";
- 27 are `refuted*` with no refuting vote other than that missing one (both counts computed from the manifest's `adversarial_verification.votes`);
- `tools/sota-convergence/lane_packets.py` (lines 420-429) leaves every refuted repository out of `manifest_newcomers`, which withholds 23 of those 27 from the next wave (a mapping-run count).

So the converged architecture is a hypothesis awaiting its confirming comparisons.

There are four critical paths:
1. **The paper lane** (the north star): receipt, then #362, then the #215 guard, then a regular-hours series.
2. **Gate A:** the full #432 Residuals, then a dated window W, then the #381 run.
3. **Gate B:** an exploratory #425 OpenHands run may inform a written criterion; the criterion is frozen before the measured acceptance run.
4. **The 32-layer wave**, which confirms targets.

## Current architecture (installed and merged)

| Tier | What runs now | Health |
| --- | --- | --- |
| Adoption and hosts | `adoption/manifest.json` release `v2026.09.26.2`; `manifests/stack.json` with 69 components (header dated 2026-09-20); linux-wsl2 acceptance is historical; macOS is `drafted_not_accepted` (`adoption/manifest.json:30-33`) | partial |
| Clients and models | Claude Code 2.1.284 and codex-cli 0.157.1. Codex has integration-level qualification against a fake provider (`codex-01571-qualification-20260926`): no live model call, no resume fixture. OmniRoute pools GPT-6 for gateway-routed lanes (`docs/decisions/2026-09-27-omniroute-account-pool.md`); its gateway owner reports a rebuild of both gateways on `release/v3.8.51` `81c9b6da` in progress | partial |
| Instructions, skills, agents | `AGENTS.md` is canonical; the skills trial, with its review due 2026-10-25 (`adoption/skills/manifest.json:28`); role agents dispatched by the role table. The SubagentStart token-lanes carrier's four blocks still advertise jCodeMunch `route(task, repo?, execute?)` (`adoption/hooks/claude/token-lanes-block*.md`), which missed 6 of 6 in the 2026-09-27 smoke | partial |
| Orchestration | one coordinator with owned worktrees; Ultracode at spawn depth 1; the Codex stack-worker lane re-applied in #444; cross-family `codex exec` review. Gate B has no written criterion, and #425-#428 are recipes | gated |
| Token and context | RTK hook, Context Mode, jCodeMunch, Serena, QMD, Headroom on demand, ccusage, and Loki invoke-rate series. #381 is frozen but not executed (`evidence/artifacts/token-adoption-e2e-20260926/README.md:875-879`), and net provider savings are unmeasured | gated |
| Retrieval and memory | ai-memory 2.4.1 hooks; QMD (the MCP server reported 29 unembedded documents on 2026-09-28); SocratiCode 1.15.0 with Qdrant and vLLM embeddings (#446, UT). There is no memory winner: S3 (#390) is draft r6 | partial |
| Evidence and evaluation | `manifests/evidence.json`; `scripts/validate.py` and `validate_convergence.py` check structure and declared consistency, not truth; blind cross-family adjudication; the promptfoo capability gate. There is no mutation-detection rate | partial |
| CI and GitHub | the main ruleset matches `.github/main-ruleset.json` (squash, linear, 8 required checks, 0 approvals); the agent-branch ruleset from #465; the actionlint successor and betterleaks run as non-required trials | partial |
| Hosting, scheduling, observation | systemd user units run the OTel Collector, Prometheus, Loki, Grafana, Alertmanager and ntfy; Dagu 2.16.6 (2.17.2 held). `manifests/stack.json` has no component row for rootless Docker or `hindsight-live` (component-id search at `83229e24`; Docker has only a conditional source-review entry in `catalogs/landscape/hosting-practice.json:10-19`), and the 20129 gateway unit has no template or receipt of its own; its owner adds them with the rebuild receipt. Restic evidence is synthetic, there is no GPU telemetry, and the dashboard checkpoint is from 10:33Z | partial |
| Trading | NautilusTrader 2.0.0rc5 destination with the LEAN oracle (`catalogs/us-equities/runtime-target.json`); alpaca-py adapter; DuckDB/Parquet, EdgarTools, pandera. The Alpaca paper gates bind older engine hashes, IBKR is not established, and SPY parity covers one case. **No tested rule has an edge:** 0 of 768 v1 rule-exits (`blueprints/us-equities/mover-early-entry/README.md:16-40`) | partial |

## Recorded target per layer (none confirmed)

| Layer | Recorded target | Evidence | What would confirm it |
| --- | --- | --- | --- |
| native-clients | claude-code + codex (09-22 pins 2.1.278 and 0.155.1; the installed clients run ahead) | IC | the native-recovery fixtures and the same-prompt task, re-run at the installed pins |
| instructions-skills | ECC plus trial skills (the lanes disagreed) | IC | a frozen skill-arm case set with a negative control; the 2026-10-25 re-record |
| workers | claude-code + worktrunk | IC | Gate A arms A, A0 and B, which settle the role table |
| isolation | worktrunk + sandbox-runtime | IC | a hostile-code or VM task where a challenger passes every trial |
| mcp-surfaces | mcporter + mcp-inspector | IC | re-runs at the served versions; mcpc lifecycle comparison |
| code-navigation | Serena; jCodeMunch as a measured tradeoff | IC | a sealed question set across the protocol's six arms (`layer-verdicts-20260922.json:452-459`) |
| document-retrieval | QMD BM25, MarkItDown, Poppler | IC | a sealed corpus: recall@k, MRR, BM25 vs hybrid |
| semantic-rag | SocratiCode + Qdrant + vLLM embeddings | IC/UT | blinded conceptual questions; freshness and leakage |
| durable-memory | none; S3 decides, with ai-memory as the reference arm | none | S3 frozen and run per host (Holm, +5 pp) |
| web-research | free native lanes first | none | a 30-query frozen bake-off |
| token-efficiency | RTK, Headroom, ccusage | IC | Gate A per-row results |
| quality-evaluation | promptfoo, playwright-test, project tests | SR | mutmut vs cosmic-ray; promptfoo vs inspect_ai |
| ci-supply-chain | syft + zizmor within the 8-check ruleset | IC | actionlint-successor parity; freshness on every CI pin |
| secrets-credentials | per-provider 0600 files, pointer variables, gitleaks | IC | gitleaks vs betterleaks on a seeded corpus, both hosts |
| git-github-automation | worktrunk, gh, difftastic | SR | sem vs difftastic; the M42 seeded-defect review comparison |
| scheduling-supervision | Dagu 2.16.6 + systemd user units | IC | job-recovery re-run; the frozen 2.16.6 vs 2.17.2 comparison |
| hosting-services | the FastAPI/Next.js/PostgreSQL plan | IC | `make verify` on the current lock |
| recovery-portability | Restic + uv lock | IC/UT | a real-state restore with native query equality |
| observation-inference | OTel, Prometheus, Loki; llama.cpp Qwen3.8-27B C2 | IC | a fresh task reconciled with Prometheus; a GPU exporter trial |
| agent-sdks | codex as incumbent, not a comparison winner | LA | a re-preregistered sealed three-arm workers comparison |
| market-data-reference | alpaca-py, edgartools, exchange-calendars | LA | the Linux alpaca-history fixture; asof re-collection |
| identity-provenance | DVC, provisional | SR/IC | DVC vs Iceberg on the point-in-time fixture |
| storage-compute | DuckDB + pandera | IC (the verdict's local receipt, `layer-verdicts-20260922.json:8310-8316`); UT added later by #331's upstream duckdb-python and pandera suites | the verdict's four checks (`layer-verdicts-20260922.json:8126`) |
| data-quality-orchestration | Dagu + pandera | IC | the Temporal same-fixture overturn |
| research-factors-ml | edgartools, markitdown, qmd, vllm; skfolio as a splitter | IC | a frozen point-in-time study (Mover v3, or #463 candidate 1) |
| evaluation-experiments | inspect-ai (no `stack.json` row) | SR (`layer-verdicts-20260922.json:5965-5967`) | a real study logged to MLflow and recovered |
| backtesting-engine | the Nautilus rc5 destination, the LEAN oracle | IC | further SPY cases with `compare.py` and the tolerances unchanged |
| execution-broker | the Alpaca adapter (paper, older engines); IBKR | LA/none | native faults and a series on current main; IBKR steps 2-4 |
| portfolio-risk | skfolio 1.2.9 as the WalkForward splitter (the 09-22 winner, `layer-verdicts-20260922.json:7164-7167`); DSR/PBO implemented from the papers | IC (recorded `native_proven`, linux-wsl2 only) | the verdict's recorded overturn checks (`layer-verdicts-20260922.json:7160`), starting with the 12-test `test_research_evaluation.py` run |
| agents-models-workers | codex SDK, gpt-6-astra, Opus; Qwen C2 conditional | IC | the catalyst-extraction gate (F1 ≥ 0.9x Opus) |
| observability-hosting | the Prometheus/Loki/Grafana/ntfy set | IC | broker-path alerts on a real paper series |
| security-supply-chain | gitleaks + syft | IC | cargo-audit and osv on the rc5 `Cargo.lock` |

## Gaps, ranked

1. **PAPER-REC.** The paper activity after the pc-20260928 401 window has no receipt.
   - #463's 19:00Z comment records that series as `not_started`.
   - Later keyring-launched `ext-20260928` units ran merged `3058b237` code from a volatile session worktree.
   - Main records only the file credential route (`docs/secret-storage.md`).
2. **PAPER-215.** Issue #215 is open: one sparse required quote freezes `AlpacaPaperTransport`, which stops exits and recovery. Whether it reproduces on the current `transport.py` is unverified.
3. **PAPER-ENGINE.** The Alpaca paper gates bind older engine hashes (`catalogs/us-equities/gates-20260922.json:219`), and #362 (ledger schema v2) is unmerged.
4. **GATE-A.** #381 is frozen but not executed. #432's full Residuals list is unbuilt (README:875-879), and W has no dates. The recorded owner (`native-agent-stack-a9`, `docs/decisions/2026-09-28-delegated-decisions.md`) was not live on 2026-09-28 evening, and `native-agent-stack-10` is auditing the area.
5. **RES-COVERAGE.** The mover set covers 498 of 594 events (83.8%), against the 95% bar (#463). No asof re-collection exists.
6. **RES-PIT.** `catalyst.py` parses no 8-K Item and has no historical ticker→CIK map, and its availability rule makes every historical filing ineligible (`blueprints/us-equities/mover-v3/README.md:198,559`); `pit-news-filings` is not established (`catalogs/us-equities/gates-20260922.json:153-168`).
7. **RES-EDGE.** No rule has an edge. The Mover v3 freeze (#360) waits on its cross-family pre-outcome review.
8. **PAPER-IBKR.** `ibkr-local-acceptance` sits in the live rung, so `scripts/trading_gates.py --check` reports paper readiness with no IBKR evidence.
9. **GATE-B.** No pass criterion or owner is written anywhere on main (`docs/decisions/2026-09-25-skills-trial-and-usage.md:517,664,770` only mention it). No runtime worker has run.
10. **SWEEP-TRUST.** 0 of 32 layers are confirmed. Of the 27 absence-refuted candidates, `manifest_newcomers` withholds 23; the other 4 are already ledger candidates.
11. **SEC-FLOOR.** There is no OS-level credential floor. The sandbox profile is unmeasured: `docs/decisions/2026-09-24-secret-storage.md:91-95` defers it, and its re-check is due 2026-10-11 (`catalogs/foundation/manifest.json:254`). Codex `inherit=none` is not applied.
12. **Medium gaps:**
    - RES-INCENTIVE: forward-protocol v2 has no PR.
    - GATEWAY: build SHAs and server secrets are unrecorded.
    - CARRIER: `route(execute)` is still in four blocks.
    - MEMORY: S3 is unfrozen.
    - CATALYST-GATE: never run.
    - SPY-PARITY: one case.
    - RES-DELIST: no point-in-time delisting map.
    - UNRECORDED-SVC: rootless Docker, `hindsight-live` and the 20129 unit.
    - QMD-SCOPE: `AGENTS.md` names two collections, the carrier four.
    - CODEX-MCP: the 1 s grace drops serena and codebase-memory.
    - SECRET-SCAN: betterleaks triage is untested.
    - QUALITY: no mutation rate; M28 and M42 have not run.
    - MAC: Stage 2.
    - GOVERNANCE: no dated calendar.

## Roadmap

Owners appear only where a record or the owner itself names them:
- the trading lane is the session that `coordination.md` calls `native-agent-stack-84`. That session was not in `ListAgents` at about 22:00Z, and no live peer took the lane, so the trading moves below have no live owner until the user or a session takes them;
- the gateway owner is `token-save-practice-e2e-status`;
- "unassigned" means nobody has taken the move.

### Now (0-48 hours)

| Move | Owner | Depends on | Moves |
| --- | --- | --- | --- |
| P-NOW-1: a sanitized `ext-20260928` receipt (below), then the paper rows in `state.json` | trading lane | none | paper: first recorded filled series, if fills exist |
| P-NOW-2: #362, the Claude re-check of `20a32965..1afd7522` and five body corrections; merge after chain4, the monitor and any chained trial exit, with `systemctl` states recorded at merge | trading lane | no active paper unit | engine gate rebinding |
| P-NOW-3: #215 on post-#362 main. #362 edits `transport.py`, the #215 fix site. Needs a failing-first test, then a fix or a freeze-time fresh-quote guard | trading lane | P-NOW-2 | precondition for the next series |
| R-NOW-1: freeze `plan.json`, then re-fetch the 96 missed events (`feed=sip`, raw, asof the event date); totals only | trading lane | a working data key | coverage 83.8% → ≥95% |
| R-NOW-2: add a SOTA sources section to #463 (its only failing required check) and land it | trading lane | none | research record |
| F-NOW-1: PR-A, the **full** #432 Residuals list, or a dated amendment naming the dropped items; plus the regenerated baseline and the Codex collector join | Gate A owner (see gap 4) | none | foundation only |
| F-NOW-2: the W record (below) | Gate A owner | peers' agreement | foundation only |

The P-NOW-1 receipt records:
- per-unit code sha256;
- orders and fills reconciled to broker activities;
- failures;
- the credential route by name only, with no account fingerprints or wrapper locations.

It also carries the matching `docs/secret-storage.md` amendment for that route.

The F-NOW-2 W record keeps the recorded conditions (`delegated-decisions.md:99-103`): no carrier or instruction change during the run, a live Codex capacity check, and an earliest time set by the running paper lane and the OmniRoute A/B. Two further items are **proposals only**, each needing its own dated amendment by the Gate A owner:
- whether paper runs may overlap W;
- an end before the 2026-10-25 skills review.

The record also gives dispositions for #434-#437 and #417.

**Live risk.** `paper-ext-20260928-chain4` runs after hours on sparse quotes without the #215 guard. The trading owner or the user confirms that the account is flat after the session ends.

### This week

| Move | Owner | Depends on | Moves |
| --- | --- | --- | --- |
| P-WK-1: a regular-hours mover series from post-#362 main, with the #215 guard and one writer per account; same-day receipt | trading lane | P-NOW-2, P-NOW-3 | paper: filled entries 0 → ≥1 |
| P-WK-2: native-faults re-run on post-#362 main; gate rebound to the current hashes | trading lane | P-NOW-2 | paper: fault gate bound to the current engine |
| P-WK-3: re-rung the trading gates after or inside #295, handling the three ladder gates in the same change | trading lane | user ladder ruling; #295 | honest per-broker readiness |
| R-WK-1: an as-known ticker→CIK map with a preregistered availability rule and an index-completeness control | trading lane | none | Mover v3 H2 preconditions 0 → 1 of 4 |
| R-WK-2: #360, the cross-family pre-outcome review, then the F12 dry run, then the Mover v3 core freeze | trading lane | review capacity | frozen protocols +1 |
| R-WK-3: a normalized news table (DuckDB to zstd Parquet, id dedupe, pandera gate, mutated-copy control) | trading lane | none | queryable news table 0 → 1 |
| F-WK-1: execute Gate A in W after a live capacity check (arms A, A0, B; usage counted once) | Gate A owner | F-NOW-1, F-NOW-2 | foundation only (gates the sweep) |
| F-WK-2: a dated Gate B draft (below), frozen before any measured acceptance run | unassigned; the gateway owner offers to draft it after the resolver's live Stage B | an exploratory OpenHands run (#425) may inform the draft; it does not count as the acceptance run | foundation only |
| F-WK-3: the gateway record (below) | gateway owner, accepted | the rebuild | foundation only |
| F-WK-4: land #415, then rebase #320; land #409; rebase and land #392, #420, #423 and #430 (lane:shared) | PR owners | outside W | foundation only |

The F-WK-2 Gate B draft needs three arms, a pass rule and an owner, for the user to confirm:
- native Codex;
- OmniRoute GPT-6;
- OpenHands via OmniRoute, which the user decided on 2026-09-28 (#425).

The F-WK-3 gateway record goes in the rebuild's receipt PR:
- per-unit `BUILD_SHA` and unit descriptions;
- the user's R02 freeze release;
- #445's admissible values, re-derived on the new build;
- afterwards, the server secrets moved into the credential inventory and the secret-path guard, with a failing-first test.

### Next two weeks

| Move | Owner | Depends on | Moves |
| --- | --- | --- | --- |
| P-2W-1: IBKR. Rebase #280 and run `acceptance-plan.md` steps 2-4 on NautilusTrader 1.231.0 with ibapi 10.45.1 (step 1 passed 2026-09-23). The keep-but-compare arm is the first released 2.0.x containing nautilus_trader#5041, not rc5 (#280) | trading lane | user IB Gateway 2FA sign-in | paper-qualified brokers 1/2 → 2/2 |
| P-2W-2: freeze incentive forward-protocol v2 | trading lane | an isolated paper account | forward sessions 0/20 → first |
| R-2W-1: point-in-time delisting ticker map for 1,236 Form 25 rows; a Linux credential route for the fixture | trading lane | R-WK-1 | pre-2020 delisting measured |
| R-2W-2: freeze the SPY `one_stress` stage and run it against the oracle | trading lane | stage decision | parity cases 1 → 2 |
| R-2W-3: minute SIP pilot | trading lane | key route | pilot receipt |
| R-2W-4: catalyst-extraction acceptance gate | unassigned | frontier-label capacity; GPU window | gate runs 0 → 1 |
| F-2W-1: #425 (the recipe merged at 2026-09-28T22:57Z as `f6e5a038`, after this snapshot), then this host's own install and live receipts; receipt 8 counts as historical only, since reuse needs matching inputs (`AGENTS.md:16`) and historical receipts are reference evidence (`AGENTS.md:42`). Its network-containment evidence gates the #431 amendment and seal | gateway owner, accepted | none | foundation only |
| F-2W-2: S3 freeze: runner and adapters, the r6 re-review, the section 9 bundle review, control-pin reconciliation. No Gate B dependency: #390 r6 fixes the LLM route by the user's direction | unassigned | none | foundation only |
| F-2W-3: stop `lane_packets.manifest_newcomers` withholding the 23 absence-refuted candidates, following `saturation_ledger`'s absence rule | `ecosystem-roadmap-2026` (claimed 2026-09-28) | none | sweep preparation |
| F-2W-4: measure the sandbox trial profile before 2026-10-11; apply Codex `inherit=none` and re-run its canary on 0.157.1 | unassigned | user decision to adopt | foundation only |
| F-2W-5: rows and receipts for the 20129 unit (gateway owner, with the rebuild receipt), rootless Docker and `hindsight-live`, or dated retirement | split | none | foundation only |
| F-2W-6: the #410 repair round; #392 | Mac coordinator | a Mac session | foundation only |

### Later

- **F-LT-1: the 32-layer verdict wave** on the Gate B route, after both gates pass. It re-votes the 27 absence-refuted candidates and folds in the bake-offs. Its target is `components_confirmed > 0`; issue #173 says a person starts it.
- **R-LT-1: preregistration** for #463 candidate 1 (news-aligned continuation), after R-WK-1, R-WK-3, an Item parser and an availability rule.
- **P-LT-1: a 1x ladder run**, after the user's ladder ruling and P-WK-2.
- **F-LT-2: S3 runs** on both hosts, then the Mac Stage 2 cutover.
- **F-LT-3: three bounded trials:** mutation (mutmut vs cosmic-ray), betterleaks on a seeded corpus, and a real-state Restic restore.
- **F-LT-4: GPU telemetry.** A GPU exporter trial and a free-VRAM alert, before long local-inference runs.

## PR triage (29 open at 83229e24)

- **Land:** #415, #409.
- **Finish:**
  - #463;
  - #362, after the paper units quiesce;
  - #360;
  - #390;
  - #431, after #425's containment evidence;
  - #410;
  - #416, after Gate A;
  - #358, re-run its cancelled validate;
  - #205, drop `fills.py` and land the trial records.
- **Rebase, then land:**
  - #437;
  - #436 (validate-macos fails);
  - #435 (extend it to all four carrier blocks);
  - #434 (`native-agent-stack-79` plans to supersede it with a rebased PR on a new branch, with a 2026-09-28 model addendum);
  - #430, #423, #420, #417, #392;
  - #320, after #415.
- **Park:**
  - #445, re-derived on the rebuilt gateway;
  - #426, #427 and #428, behind the Gate B criterion and #425;
  - #295 (live scope; split out any paper check);
  - #280, until the IBKR sign-in;
  - #216, after the wave.

## User-only actions

These follow the stop rule in `AGENTS.md`: native sign-in, operating-system consent, or an unresolved material decision.

1. Sign in to IB Gateway for the IBKR paper account, with the second factor.
2. Provide an isolated Alpaca paper account for the incentive study, or explicitly reassign one.
3. Rule on the ladder: are the rungs required paper gates, and how is `needs_attention` scoped?
4. Resolve the Mac paper account that trial C left not flat (#205, #215).
5. Confirm the Gate B criterion once it is drafted.
6. Decide on paid historical data, only if asof re-collection stays below 95% (`docs/paper-lane-policy.md:17-18`).
7. Grant Apple Container consent on the Mac for S3.
8. Choose an off-host backup destination and key custody.
9. Start the 32-layer wave after both gates pass, or delegate it.

## Calendar (dated items already recorded)

| Date | Item | Source |
| --- | --- | --- |
| 2026-10-06 | replace codex-plugin-cc if it is still stale | `docs/decisions/2026-09-27-claude-harness-settings.md:190` |
| 2026-10-11 | sandbox profile re-check (gap `claude-code-sandbox-profile`) | `catalogs/foundation/manifest.json:254` |
| 2026-10-21 | DuckDB v2.0 planned (tentative), which makes the Quack multi-writer protocol stable | `catalogs/sota-convergence/manifest-20260926.json:13185,13192` |
| 2026-10-25 | skills-trial review | `adoption/skills/manifest.json:28` |

Decision rights stay as recorded:
- the user's delegations: `docs/decisions/2026-09-28-delegated-decisions.md:5-8`;
- the stop rule: `AGENTS.md`;
- the paper-lane policy: `docs/paper-lane-policy.md`;
- the shared-path acknowledgement: `docs/lanes.md:145-150`.

## Alternatives considered

- **Run the 32-layer sweep now to refresh the targets.** Rejected: the user gated it on Gate A and Gate B on 2026-09-27.
- **Read the 2026-09-26 manifest as the target.** Rejected: that ledger is degraded (27 candidates were refuted by absence alone), so the 09-22 verdicts remain the recorded targets.
- **Use the catalogs as the current architecture.** Rejected: `catalogs/foundation/manifest.json` is dated 2026-09-21 and predates the gateway, the token lanes and the paper reopening. This record uses what is installed and merged.

## Comparison that would overturn it

- **The ext-20260928 receipt** shows no fills, or 401s on the keyring route: the paper moves wait on the credential route again.
- **#215** does not reproduce on the post-#362 transport: drop the guard move and cite the fixing commit.
- **Gate A** fails a required row: token-practice fixes and a re-run come before Gate B and the wave.
- **The Gate B criterion** needs no runtime-worker run: #425-#428 leave the critical path.
- **asof re-collection** reaches 95%: the paid-data decision drops.
- **Main** moves past `83229e24` with changes to sealed carrier or role-body files: re-derive Gate A's seal and re-check these citations.

## Limitations and residuals

- **Evidence class.** This is a synthesis of recorded evidence, checked by adversarial refutation. It is not a new acceptance run, and it runs no model or broker trial.
- **Currency.** Upstream currency is as of the 2026-09-26 sweep.
- **Peer statements.** Owner acceptances are quoted as the peers stated them:
  - the gateway owner accepted F-2W-1 and F-WK-3;
  - it takes the 20129 row;
  - it will offer the Gate B draft after its resolver's live Stage B.

  Nothing else was claimed.
- **Snapshot age.** The PR, gate and systemd states are a 2026-09-28 22:00Z snapshot. Paper-unit and PR states change within hours.

## Updates

### 2026-09-29, main `cf3fb72e`

- **Gate A owner.** `native-agent-stack-2d` takes Gate A (#381) as F-NOW-1 and F-NOW-2, from 2026-09-29. Its message says this was "on the user's direct instruction". It is quoted as the peer stated it and not independently verified. This fills the "Gate A owner" cells above.
  - `docs/decisions/2026-09-28-delegated-decisions.md` still records `native-agent-stack-a9`, which was not live; this update does not edit that record.
  - The same peer relays the user's order: stage the 32-layer wave and prove the token stack end to end first, then run the full waves. It stages Phase C only after the E2E work is moving.
- **F-2W-3 is done.** #471 merged as `cf3fb72e`. `lane_packets --manifest-newcomers` now carries the 23 candidates that were refuted only by a missing vote. That review was one GPT-6 round, with both findings repaired.
- **Paper accounts: measured, not user-gated.** Two Alpaca paper pairs are held in the kernel keyring (`scripts/kernel_keyring.py`). A read-only check through the keyring wrapper at 2026-09-29T00:3xZ returned HTTP 200 on both accounts, with 0 positions, 0 open orders, status `ACTIVE` and `trading_blocked` false. Both `paper-ext-20260928-chain4` and `incentive-monitor-20260928` were inactive by then (the monitor's result was `success`). Several items in "User-only actions" above change as a result:
  - The credential route is the keyring. What remains is the `docs/secret-storage.md` amendment, which is work, not a user action.
  - The incentive study needs one of the two accounts assigned to it (item 2 above). That is an assignment decision for the trading lane, not a new account.
  - The ladder ruling (item 3) and the Gate B criterion (item 5) are owner decisions made with evidence under the user's delegation (`2026-09-28-delegated-decisions.md:3`), and recorded.
  - The 32-layer wave (item 9) waits only on Gate A and Gate B, per the user's order relayed above.
  - Still the user's: the IBKR Gateway 2FA sign-in; Apple Container consent on the Mac (whose role is under discussion); purchases and off-host key custody; and the Mac account from trial C, which only a Mac session can check.
- **The trading lane is still unowned.** `native-agent-stack-2d`, `native-agent-stack-d8` and `native-agent-stack-79` each said they hold no trading lane, so P-NOW-1, P-NOW-2 and P-NOW-3 have no owner. With both paper units inactive, #362's merge condition ("no active paper unit") is met. #362 still needs its Claude re-check and five body corrections.
- **Post-merge corrections** from the skills-trial and integrity owner are in the #469 comment [5880981981](https://github.com/seathatflowsinourveins/native-agent-stack/pull/469#issuecomment-5880981981). They cover the actionlint swap (under F-LT-1), the betterleaks contract, M5b and M5c on Gates A and B, and F-2W-4 owned by the foundation coordinator.
