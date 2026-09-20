# Run-ledger application

Use the exact local commands and prerequisites in `project-contract.json` and
`README.md`. Restore `uv.lock` and `pnpm-lock.yaml`; do not replace PostgreSQL
with SQLite or use a shared database for tests. The transaction rollback test
temporarily creates a constraint in the dedicated test database.

Generate `openapi.json` and `app/api.generated.ts` with `make schema` after API
changes. Keep types derived from the native FastAPI schema. `make run` runs the
two owned loopback application processes in the foreground; the operator owns
the dedicated database lifecycle. Keep account stores and real research data
outside this unauthenticated synthetic local fixture. No model/provider calls
or deployment follow from these commands.

Project-readiness inspected the enclosing public worktree. Its installer writes
worktree-root guidance and actions, so this bounded application retains the
reviewable nested contract for the coordinator to integrate without modifying
the enclosing repository's native actions.
