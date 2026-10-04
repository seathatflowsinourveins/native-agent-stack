# Adjudication prompt (Opus, per disputed slot)

Model: `opus` (Claude Opus 5.5) at effort `max`, agent type `evidence-reviewer` (read-only), one agent per disputed slot,
in two Claude Code workflow runs on 2026-10-04 (17 slots, then 5 more after the executor statuses were corrected from the
workflow's schema-checked returns). Schema-forced return: slot_id, final_status, side, reason, fix, fix_kind, needs_user,
sources. The template below is the prompt as run, with run-specific values shown as <placeholders>.

```
Adjudicate one slot of the NativeStack2604 live E2E (date 2026-10-04). Read-only; never run anything on any WSL distribution; never read credential files or values.

Slot: <slot_id> (unit <unit>). The Sonnet executor proposed <executor_status>; the independent GPT Sol reviewer judged <reviewed_status>.

Status definitions (from the review brief): READY = present at version, its upstream acceptance passes, wired natively, and used in a fresh headless session if the slot is client-facing. PARTIAL = some of these hold. FAIL = absent or broken. BY_DESIGN = nothing to install by design. INTERIM = an explicitly held interim the plan records (for example a token tool awaiting the token-layer PR #684); an INTERIM must not hide a missing install the current plan says should exist.

Read: the executor evidence <e2e dir>/<unit>.json (this slot's record: commands, exit codes, output excerpts), the GPT review <e2e dir>/review-<unit>.json (this slot), the slot entry in <e2e dir>/units.json, and the install plan row in <host path>/code/.worktrees/native-agent-stack/c5/main-ro/evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json (origin/main).

Executor summary: <executor_summary>
Reviewer reason: <review_reason>
Reviewer fix: <fix>

Decide the status the evidence supports today, on the definitions above. Side with whichever is right, or neither. Then give the fix that would make it READY (or confirm none): exact upstream command or plan change, whether it is a repository plan change or host state, and anything that needs the user (a sign-in, an identity, a policy choice), else an empty string. Cite file:line in the evidence or plan and any upstream doc the reviewer cited.
```
