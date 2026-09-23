# Native Claude and Codex foundation finalization — September 21, 2026

The selected foundation now has one navigable map for all sixteen layers:
Foundation explorer (`ecosystem/index.html#foundation`; generated with
`python3 scripts/build_ecosystem.py --write`, not committed -- download it
from a `publish-catalog.yml` release artifact otherwise),
[operator surfaces](../catalogs/foundation/surfaces.json),
[capability decisions](../catalogs/foundation/decisions.json) and
[canonical repository pins](../manifests/stack.json).
The map covers 61 foundation components through 46 decisions: 42 accepted within
their stated scope, three partial optional capabilities and one source review.
The broader stack has 68 components, including domain-specific components.

Every layer exposes upstream repositories, current recorded pins, its selected
native terminal/CLI or web dashboard, and installation/lifecycle runbooks. The
24 surfaces distinguish upstream UIs from local integration panels, generated
snapshots, retained HTML exports and account-dependent hosted analytics. Local
links are labelled **This PC** and never start services or make background calls.
Use [the installation map](../catalogs/foundation/README.md) for native setup.

## Decisions and source review

Retain native Claude Code 2.1.278 and the existing first-party account, model
selection, permissions, caching, compaction and MCP configuration. The persisted
workflow profile, small advisory graph size and per-run concurrency three match
the current [official workflow](https://code.claude.com/docs/en/workflows) and
[settings](https://code.claude.com/docs/en/settings-reference) documentation.
Use the selected native runtime and its `/workflows`/session interfaces for
orchestration. The existing official companion remains a separately qualified
cross-family lane; its earlier interrupted Codex-in-Workflow trial is retained
as a limitation, not relabelled successful.

Reused the existing upstream installation and evidence rather than installing
another orchestrator or dashboard framework. Earlier alternatives and selection
reasons remain in [native Ultracode](native-ultracode-20260921.md),
[community practice](community-native-practice.md) and the capability decisions.
A replacement requires a demonstrated gap and a comparable native result.
The concrete missing capability here was the explorer's repository/dashboard
join; the existing static renderer now supplies it without a new service.

Repomix is installed at 1.18.1 and its existing pinned package agrees. The stack
manifest incorrectly linked release 1.18.0; the link now points to the verified
[1.18.1 release](https://github.com/yamadashy/repomix/releases/tag/v1.18.1).
The foundation guide's older counts were corrected. No version upgrade was
necessary to resolve either discrepancy.

## Codex ecosystem

Native Codex 0.155.1 is signed in through ChatGPT. The existing
`gpt-6-astra` / `ultra` defaults, permissions and hooks remain intact. Project
orchestration is enabled with three concurrent children and four configured
roles. Fourteen project skills and thirteen personal skills were present in the
inspected roots. All five scoped MCP entries are enabled: Context Mode,
jCodeMunch, Serena, ai-memory and SocratiCode. The four stdio launch commands
resolve, and the HTTP ai-memory configuration is recognized.

The installed format agrees with official
[custom agent](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)
and [project configuration](https://learn.chatgpt.com/docs/config-file/config-advanced#project-config-files-codexconfigtoml)
guidance. The read-only audit found no missing setup that justified a reinstall.
`codex doctor --json` exited zero with nineteen passing checks and one retained
history-inventory warning: 49 rollout files versus 20 database rows, with 29
missing rows. No duplicate paths, stale rows, archive mismatches or scan errors
were reported. No unsupported history-database repair was attempted. This check
establishes configuration and account readiness; earlier scoped native evidence
is reused, and no new Codex model or MCP E2E result is claimed here.

## Corrected workflow acceptance

The deployed `review-changes` previously accepted some reviews with refuted,
unverifiable or omitted verdicts and verification gaps. It now requires exact
one-to-one, nonblank evidenced confirmation for every inventory claim, successful
returned results for each requested check, and no reported defects or gaps.
Corrected/refuted claims require coordinator resolution before acceptance.
An empty behavior inventory cannot pass this change-review workflow. Each
requested check needs exactly one matching nonblank result; blank or duplicate
command evidence fails closed.

The deployed `readiness-audit` previously called an audit complete when a reader
or verifier silently omitted a requested source. Each document/command now needs
an observed result and independent confirmation of its exact packet/source key;
commands preserve their integer exit code. Missing sources, omitted verdicts,
duplicates and empty evidence fail closed. A complete audit can establish that
the project is not ready, including after an observed command failure.

The [portable workflow scripts](../examples/claude-native/workflows/README.md)
matched the selected deployed scripts at that time; they and the agent definitions
were later replaced by byte-identical copies of the deployed files, with project
bindings in a sibling config (superseded by the
[lean routing guide](ultracode-token-routing-20260921.md)). These scripts
and tests are locally authored
extensions using the upstream runtime, not upstream acceptance tests. Read-only
prompts do not supply operating-system isolation. Original source and actual
command observations still determine whether model judgments are supported.

## Verification and limits

Independent review reproduced the missing-command hole after the initial fix,
then verified its correction. The final 91 local VM assertions cover omissions,
duplicates, unverifiable judgments, source coverage and negative audits. Two
saved-script syntax checks and the unchanged bridge's seven assertions passed.
The VM fixtures replace model calls and do not prove native provider execution.
The first actual native review rejected an incorrectly supplied syntax-check
path and identified the remaining empty-inventory/blank-check gaps. It also
corrected the inventory worker's transcription of 67 passing assertions as 68.
Those failures were preserved, the supported code findings were fixed, and the
later qualification uses full repository-relative syntax-check paths. The
readiness prompt now reserves missing-source reporting for unavailable evidence
and places independently established additional facts in its readiness verdict.

A second native review returned both checks successfully but rejected corrected
inventory citations and another miscount (76 versus the observed 81 assertions).
Its blank-exit status criticism did not establish false acceptance: an unknown
exit remains incomplete, while an observed nonzero exit is rejected. A generic
diagnostic message is a reporting limitation. These observations were retained;
the gate was not weakened to obtain a positive model verdict.

The first native readiness run confirmed all eight substantive claims but
remained incomplete because each reader included the other packet's source.
Both the unexpected reader entries and the verifier's mismatched confirmations
were rejected. Each reader now receives a schema with only its assigned source
identifiers and exact source count, alongside explicit packet scope. The fixture
prints a deterministic pass/fail summary for workers to quote. The final receipt distinguishes these actual failed
returns, local corrections and subsequent native qualification.

The final native readiness run completed with six confirmed claims, two exact
source confirmations, and no unread sources, missing sources or evidence issues.
Both Sonnet readers and the Opus verifier completed; the runtime loaded the exact
deployed script. The result establishes the declared workflow settings and
Node v24.21.0 for this environment. It is one valid document/command packet shape;
local schema assertions do not establish upstream rejection of every invalid
shape, and file reads do not prove effective settings in every running session.
The command reader recovered from one structured-output formatting error. A
verifier lookup encountered an absent optional settings file and then checked
the existing files successfully. Independent inspection retained both errors
and confirmed the final result against all three original worker transcripts.

The explorer's 39 local integration tests passed independently. Rendered desktop
and 390px mobile inspection showed all sixteen layers, correct Qdrant and Workers
filter results, no horizontal overflow and no browser errors. Retained images:
[desktop](../evidence/artifacts/claude-foundation-finalization-20260921/workers-desktop.png)
and [mobile](../evidence/artifacts/claude-foundation-finalization-20260921/workers-mobile.png).
Fourteen documented dashboard pages returned HTTP 200 in the read-only audit;
those responses establish transport only. Earlier native/rendered evidence is
reused at its original scope.

Final catalog validation passed for 68 stack components, 127 receipts and 1,415
hashed files; foundation and repository-catalog structure checks also passed.
The generated explorer matched its inputs. A final browser reload confirmed
the added Codex surface and embedded setup guide, with the Workers filter still
showing eight capabilities and no overflow at desktop or 390px mobile width.
Native token-report refresh returned no collection issues; native counters,
artifact comparisons and cumulative provider usage retain separate scopes.
Concurrent published foundation R&D and foreground Codex review records were
preserved during integration; their separate evidence and next-work boundaries
remain visible in the same explorer.

Native workflow qualification and final integrity results are recorded in the
[execution receipt](../evidence/receipts/claude-foundation-finalization-20260921.json).
The bundled `/workflow-authoring` command was loaded in the native qualification
session before its review. The initial local edit was based on original source
and current official documentation; it did not initially load that bundled
reference, and no retrospective procedural claim is made.

Active local telemetry and dashboards remain distinct from historical app
fixtures. FastAPI/Next.js/PostgreSQL have scoped application evidence; no public
cloud deployment is asserted. Apple Container evidence is macOS-specific.
OmniRoute is an optional Windows route; direct native-client usage does not pass
through it. Hosted Context Mode Insight access is separate from local plugin
installation. Physical-PC reboot, new-host installation, all optional SDKs and
whole-task causal savings are not established by this finalization.

This is a dated, evidence-qualified selection of current practice. Repository
popularity or a clean manifest cannot establish a universal best stack.
