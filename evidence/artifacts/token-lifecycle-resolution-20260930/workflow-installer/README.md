# Saved-workflow installer integration checks — 2026-09-30

This is local integration evidence for the existing Claude profile adopter,
including synthetic failure and conflict controls. No provider models were
launched. Native discovery, execution, resolved model/effort and returned usage
remain separate host acceptance.

Sources:

- [Claude's native personal saved-workflow location and target-symlink rule](https://code.claude.com/docs/en/workflows#save-the-workflow-for-reuse).
- `readiness-audit.js` and `review-changes.js`: [agent-lab b31f64020ab4900cd92341cd2aa92c3d98367758](https://github.com/seathatflowsinourveins/agent-lab/tree/b31f64020ab4900cd92341cd2aa92c3d98367758/.claude/workflows).
- `layer-verdict-lane.js`: [agent-lab e070125dae03b4e44484ccb78d2d65057ad38f40](https://github.com/seathatflowsinourveins/agent-lab/blob/e070125dae03b4e44484ccb78d2d65057ad38f40/.claude/workflows/layer-verdict-lane.js), pinned by `examples/claude-native/workflows/vendored-lanes.json`.
- Source bytes are frozen by the existing `examples/claude-native/workflows/SHA256SUMS`; [source-checksums.txt](source-checksums.txt) retains the returned integrity-check output. Scripts and their manifest were unchanged.

[focused-tests.txt](focused-tests.txt) retains the test command, exit code and
returned stderr. It ran 77 tests and passed with three existing skips because PyYAML was
absent. The skipped tests check YAML parsing and skill-preload eligibility; no
test was deleted, skipped or weakened for this adapter. New checks use actual
saved-script bytes in disposable homes and cover clean installation, readback,
unchanged reuse, default-profile inclusion, corrupt/missing checksum entries,
target conflicts and symlinks, personal dotfiles symlinks, competing creation,
write/readback failure rollback, recovery and scoped removal. The installer
never overwrites workflow targets, so backup of a reviewed conflict remains
with its owner. Removal preserves edited/custom entries and target symlinks.

Discovery correction: `adoption/skills/lifecycle.md` was absent from the isolated
checkout snapshot. Its active-checkout version was read alongside
`adoption/lifecycle.md`; this did not change installer ownership or scope.
