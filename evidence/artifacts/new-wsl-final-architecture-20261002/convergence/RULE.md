# How the three GPT samples and the Claude record are combined (written 2026-10-02T03:55:19Z)

Written after I had seen pull request 595's catalog (its GPT judge on the 21 frozen packets) and the 5 layers the
two-order Sol-ultra round finished before the restart, and before the other 15 layers of that round returned
(20 of 31 units had exited when this file was written; I had read none of their outputs).

Samples per foundation layer: G1 = pull request 595's blind GPT-6.1 Sol judge (`selection-gpt.json`), G2 and G3 =
order 1 and order 2 of the GPT lane's Sol-ultra round on its expanded packets, C = the Claude record (the merged
definitive manifest's defaults, which come from the blind Claude judge and critic, or from the decision round).

For each repository in a layer:
1. **Final (installed)**: in C and in at least two of G1, G2, G3.
2. **Claude only** (in C, in fewer than two GPT samples): not installed, unless it is the only owner of a job that
   the installed set leaves uncovered. That exception is decided per case from the repositories' own READMEs and
   written down with the reason.
3. **GPT only** (in at least two GPT samples, not in C): a challenger. It is installed only if one Claude critic,
   reading the GPT judges' cited sources, finds that it owns a job nothing installed covers and that the job is in
   the layer's requirement.
4. Everything else: not installed.

Unchanged by this rule: slots settled by a measurement (local model server), slots waiting for one (memory, code
search), the owner's pins (gateway, runtime workers, trading engine and brokers) and project practice rows.
A repository counts as the same across samples when its GitHub owner and name match, ignoring case.

## Amendment 1 (written 2026-10-02T04:09:12Z, before `combine.py` was run on any layer)

Reason. Pull request 595's own decision record (`docs/decisions/2026-10-01-final-catalog.md`, "Blindness, and its
limit") and its probe (`cross-family/instruction-probe.json`) show that every G1 process also received its host's
global Codex instructions, which name eight packet candidates (ai-memory, Hindsight, SocratiCode, QMD, Playwright CLI,
Ollama, Context Mode, ast-grep). The record states that agreement on the layers those tools belong to "is therefore
not independent evidence" and lists them: semantic-rag, document-retrieval, web-research, durable-memory,
token-efficiency, code-navigation and quality-evaluation. I had read the GPT review of that pull request (finding 3)
and the Codex lane's pointer to that section at 04:04Z; I had not opened the section when the rule was written.

G2 and G3 ran on this host under its own global Codex instructions (sha256 50524adf…, last changed 2026-09-30), which
name none of those eight and no other candidate except RTK (checked by a case-insensitive search of both instruction
files at 04:08Z).

Change. On those seven layers G1 is not counted. There a repository is **final** only if it is in C and in both G2
and G3; it is a **GPT-only challenger** only if it is in both G2 and G3 and not in C. On every other layer the rule is
unchanged. C carries the same kind of exposure on those layers (the Claude judges ran as workflow subagents with the
project's instructions; recorded in the merged decision record), so on those seven layers a final pick rests on the
two G samples agreeing with it, not on C alone.

What I had seen of G2 and G3 when this was written: the five layers finished before the restart (agent-sdks,
ci-supply-chain, code-navigation, cross:wsl-distro, document-retrieval), and session 80's critic verdicts for three of
them (04:03Z). Two of the seven affected layers (code-navigation, document-retrieval) are among those five, so for
those two this amendment was written with their G2 and G3 results known; for the other five it was not. 26 of 31
units had exited; I had read none of the other outputs.
