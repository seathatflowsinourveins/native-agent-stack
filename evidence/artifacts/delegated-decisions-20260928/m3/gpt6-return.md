- **DECISION: latest-opus.** Exact text:
  > - The latest Opus at effort max for design, build, research, review, verification and synthesis.

- **Reasons:** “Latest” preserves the stated policy (4, 5); bare “Opus” loses that constraint (8). Removing the number avoids a rule becoming stale after a release (2). Repository consistency supports removing it, but does not justify dropping “latest” (3). The provider-dependent alias cannot establish compliance: an older served model remains off-policy under the recommended wording (1, 4, 5).

- **Insufficient evidence:** The missing gateway entry in (5) does not prove routing to Opus 5. The explicit-parameter requirement in (6) alone does not demonstrate how this prose changes coordinator behavior. Peer silence carries no weight (7). The packet also does not establish which release is currently latest or show that changing the wording prevents silent fallback. The independent reviewer’s argument supports preserving the constraint, not a runtime guarantee (8).

- **One measurable overturn condition:** A matched task/provider/client test, with the newest release accessible, records an older served model under this wording while the current numeric pin serves the newest. That would overturn this wording-only recommendation in favor of an explicit model-resolution and verification requirement.