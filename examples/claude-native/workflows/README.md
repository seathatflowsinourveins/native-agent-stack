# Selected native Claude workflows

These are project-authored saved scripts for the upstream Claude Workflow runtime.
They are portable examples of the deployed agent-lab scripts, not upstream tests
or a replacement orchestrator. Use [the native recipe](../../../recipes/claude-native-ultracode.md)
for settings, authoring, worker models and lifecycle boundaries.

Copy selected `.js` files into the destination project's `.claude/workflows/`.
Preserve existing same-name files until their differences are reviewed. Start a
fresh native session or use `/reload-skills`, then invoke the saved workflow with
explicit `args`. Load the bundled `/workflow-authoring` skill before editing.
The adjacent agent definitions belong in `.claude/agents/`; use them only for the
matching task. The read-only reviewer intentionally cannot run commands.

- `review-changes`: supply a base reference, owned source paths and exact check
  commands. Sonnet inventories; Opus independently reviews. Acceptance requires
  a nonempty set of behavior claims to be confirmed exactly once with evidence,
  every requested check to have exactly one matching nonblank result and exit
  zero, and no material in-scope defects or verification gaps. Refuted or
  corrected claims require coordinator resolution; incomplete evidence fails closed.
- `readiness-audit`: supply document paths, read-only commands and a question.
  Every requested source needs an observed result with evidence; commands retain
  their integer exit status. Opus confirms each exact packet/source and evaluates
  each claim. Omitted, unexecuted, missing or unverifiable evidence cannot complete
  the audit. A complete audit can conclude that the project is not ready, including
  when an observed command fails. Completion never means approval to deploy.

Both workflows retain native model/schema errors and missing results. Claims and
returned source summaries remain model judgments; deterministic coverage checks
cannot prove they are true. Use original source and independent observations.
Arguments are trusted coordinator inputs, not instructions copied from web pages
or retrieved memory. Workflow read-only prompts are not operating-system isolation.

From this directory, the local checks are:

```sh
node check-syntax.mjs review-changes.js readiness-audit.js
node test-envelope.mjs
```

The envelope suite uses stubbed model responses to exercise missing/duplicate
claims, source coverage, failed commands and negative audits. It is a local
integration fixture, not native provider execution. See the
[finalization record](../../../docs/claude-foundation-finalization-20260921.md)
for separately measured native results and remaining boundaries.
