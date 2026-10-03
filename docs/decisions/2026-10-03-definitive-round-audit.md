# Decision: a clean-room, two-family audit of the definitive manifest on 43 slots, with a deep-dive dossier of every candidate (2026-10-03)

Lane: foundation. North-star action served: the new WSL's install record rests on picks that two model families reach
independently, from the candidates' upstream code and README, without the instruction files that name candidates.

Status: a record. It changes no row of the definitive manifest. Contests go to the manifest's owner, the pin conflict
goes to the user, and the memory result goes to the head-to-head (#526).

## Decision

`evidence/artifacts/new-wsl-definitive-round-20261002/` records a clean-room round over the 43 foundation slots that
#591 left open. It compares each slot with the definitive manifest at #602's merge commit (`675bdd51`, pinned by
sha256).

**Method.**
- Every one of the 177 candidates got a dossier written from its upstream README and code at its release tag. Sonnet 5.5
  wrote it at max; Opus 5.5 verified it at max against 5 cited claims, with at most one repair.
  - 176 dossiers pass verification. One still fails after its repair, and the judges saw that verdict.
- Both families then decided every unit in two seeded candidate orders, and a critic followed each family's deciders:
  - Claude Opus 5.5 at max, through `claude -p --safe-mode --restricted --strict-mcp-config`;
  - GPT-6 Astra at max, through `codex exec` with an isolated `CODEX_HOME` on the OmniRoute gateway.
- Probes show that no instruction file reached either family (`clean-room.json`).
- Slots where the families differed, or where one family was undetermined, went to four adjudicators: one per family, in
  both A/B orders.

**Preregistration.** The plan was frozen before the first dossier and amended four times.
- Amendments 1 to 3 came before any decision: the runner's prompt fix, the retargeting to an audit of #602, and the
  re-verification of 13 dossiers that lost their verification to usage-limit stops.
- Amendment 4 came after the results. It is a defect fix in the comparison script, described under Limits.
- Every amendment is hashed, and `freeze.py --check` verifies the chain.

**Round outcome** (`selection.json`): 35 definitive slots (34 where the families agreed and 1 adjudicated four of
four), 7 left to measurement and 1 user-pin conflict. The contamination audit of the raw returns has 0 hits.

## Result against the definitive manifest

From `audit-of-manifest.json`, at #602. The same verdicts hold against main after #620 (`cfd08b85…`): no slot's
verdict, state or pick differs. #620 adds five rows the round does not cover.

| Verdict | Slots |
| --- | --- |
| Agree | 22: zizmor, attest, Syft, Dependabot, actionlint, Serena, Ubuntu 26.04.1, QMD, git, gh, Worktrunk, difftastic, Compose, Trail of Bits skills, sandbox-runtime, OTel Collector, Prometheus, Inspect AI, Harbor, mise, Restic, betterleaks |
| Contest | 7. #602 installs nothing; both families picked github/codeql-action (findings publication), claude-code-action (GitHub-side agent review), sem (agent structural diff), Phoenix (route qualification), promptfoo (CI regression gate), chezmoi (dotfiles) and trufflehog (credential verification) |
| Nominates | 4 split rows. Loki (events store), Grafana (dashboards), SocratiCode (code search) and agent-browser (browser interaction) go to those rows' named measurements and settle nothing by themselves |
| Cross-check | Memory. All four adjudicators chose ai-memory. The head-to-head (#526) stands; this is a nomination for it, not a decision |
| Pin agree | Deep-research harness: gpt-researcher, adjudicated four of four, which is one of the two pinned harnesses |
| Pin conflict | Agent runtime worker. Both families picked openai/codex over the pinned OpenHands software-agent-sdk. The pin stays until the user decides |
| Not settled | 7. Client-native LSP (plugin or none), GPT gateway (OmniRoute or none; the pin stands unconfirmed), document ingestion (MinerU), local model server (#598's gate stands), workflow engine (Prefect or Dagu), usage meter (agent-console or ccusage) and page-text extraction (trafilatura or none) |

**How to read the contests.** Every contested slot asked "which single tool does this job, or none?", and "none" was
allowed in each.
- Both families judged that a tool beats "none" for the job as the slot states it, and the critics cited upstream code
  for the capability.
- #602 resolved the same rows on job ownership: another installed tool already owns the job, or the layer's requirement
  does not ask for it. Inspect AI owns prompt evaluation, mise and the bootstrap own configuration, and difftastic owns
  structural diffs.
- The round's judges saw the sibling slots of their unit but did not weigh overlap with the rest of the installed stack.
- So the contests are clean-room picks for whoever keeps these jobs as slots. They are not evidence that the jobs need
  owners. Whether they do is the manifest owner's call.

## Limits

- **Unequal live web evidence.** Both families had the same dossiers and source clones.
  - The Claude judges ran 117 web searches through Claude Code's WebSearch tool, which uses a helper model (Haiku 4.5).
  - The GPT judges' 157 searches through the gateway came back empty, except 2 in adjudication. The gateway has no
    credentialed search provider (the Mac gateway record, Limits).
  - Agreement rests on the shared evidence. Where the families differed, this asymmetry is one possible factor
    (`run-notes.json`).
- **Amendment 4 came after the results.** The comparison script treated `installs_nothing_extra` as a "none" pick. That
  contradicts amendment 2's rule text, under which a row's pick is the repository it names.
  - The fix turned build provenance (attest) and dependency updates (Dependabot) from contest into agree.
  - The pre-fix output is kept as `audit-of-manifest.before-amendment-4.json`.
- **Adjudicator anonymity.** The returns were shown as A and B in both orders. Their text can still carry family signals,
  such as contender names that coincide with the families; the returns were not audited one by one.
- **Evidence class.** These are model judgments on source review. Nothing was installed or measured.
- **Usage** (`run-notes.json`) is a lower bound. Attempts lost at usage-limit stops are not counted.

## Alternatives

- **Publish a separate architecture from the round.** Rejected in amendment 2. #602 is the install record and has one
  owner.
- **Re-run the GPT half after configuring a search provider.** Not done: it needs a credential the user holds. It would
  remove the web-evidence asymmetry and is the first step if a contest is pursued.
- **Treat the contests as overturns.** Rejected: they answer a different question than #602's job-ownership rule.

## Overturn

- If the manifest's owner keeps any of the seven jobs as its own slot, the round's pick for that slot is the clean-room
  candidate.
- If the user drops the agent-runtime-worker pin, Codex is the two-family pick.
- If the head-to-head (#526) runs, ai-memory is the round's nomination.
- A re-run with working GPT web search, or with the job-overlap question asked, replaces this audit for the slots it
  covers.

## SOTA sources

- The candidates' upstream repositories at the release tags recorded in each dossier.
- `claude -p` (Claude Code), with its `--safe-mode`, `--restricted` and `--strict-mcp-config` flags.
- `codex exec` of [openai/codex](https://github.com/openai/codex), through [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute).
- #591's criteria and decision rule, byte-identical; the definitive manifest at #602 and at #620.
