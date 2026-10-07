# Skills fold metadata ceiling — 2026-10-07

## Decision

The repository ceiling for the on-listed skill-description sum is 10,645 characters for the command-center-ruled consolidation of #719, #792, #793, #794 and #817 into #795. Both `budget.claude_on_cap` and its existing `trial.on_description_char_cap` metadata mirror carry that value. The measured central union contains 27 selected entries: Claude on-listed descriptions total 10,645; 26 Codex-eligible entries total 10,326, including the held browser. These are manifest sums, not fresh host visibility or model use.

This bounded amendment extends the September 30 decision without rewriting its decided text or observations. It preserves the pinned descriptions and all selected skill identities. The user's Claude `skillListingBudgetFraction: 0.05` and Codex `[skills] max_context_tokens = 6000` stay unchanged. No client configuration is applied by this PR.

## Evidence and alternatives

The existing 10,500 repository guard is 145 characters below the compatible union of the directly authorized native-stack-research and hf-cli registrations. The installer independently recomputes the sums while preserving policy. The September 30 decision derives approximately four characters per token from the documented default and fallback; on a 200,000-token window, the unchanged 0.05 fraction therefore implies approximately 40,000 listing characters. This is that decision's inference, not a newly measured native renderer rate or proof that all descriptions reach either model.

Alternatives considered were the previous 10,500 ceiling with one authorized listing made inert, and a larger 15,000 ceiling for six further installs. A26 chooses the exact measured union, avoiding an unreviewed allowance for additional growth. A18 continues to govern the separate 15,000 proposal and its required fresh measurements. No description is shortened to fit a guard.

Overturn condition: a fresh native catalog read on either client showing a dropped or truncated description at this sum lowers the ceiling or retires a skill through the normal lifecycle and a dated decision. New additions must obtain their own disposition; tests bind this ceiling and both measured sums to prevent unreviewed growth. Manifest eligibility, SDK catalog availability, integration smokes and native organic observations retain separate evidence scopes.

## Sources

- `native-agent-stack@d9eb68750311d5f888adec140723da174f9fe10c:docs/decisions/2026-09-30-skills-llm-native-listing.md:167-176`: the earlier repository ceiling and the explicitly inferred listing allowance; its original text remains unchanged.
- `native-agent-stack@876010fbadfcb2b6846f9aa97f0841e829a81ff4:adoption/skills/manifest.json`: #719's authorized research registration; `native-agent-stack@ae17e43dea30d747b1742ffbfcd847495b526a65:adoption/skills/manifest.json`: #792's authorized hf-cli registration.
- `native-agent-stack@ae17e43dea30d747b1742ffbfcd847495b526a65:tools/adoption/install_skills.py:218`: native budget refresh preserves policy while recomputing sums; `adoption/skills/lifecycle.md` lists both policy fields.
- Claude's [official settings reference](https://code.claude.com/docs/en/settings), and `openai/codex@d27764b82f7118f674371e6d6e76271d9d606edb:codex-rs/ext/skills/src/render.rs`: native listing settings are distinct from the repository guard.
- Direct FOLDS-RULED CC review023012Z and co-op A26 at 2026-10-07T04:20:17Z, retained in the lane coordination record; command-center delta read and ACK remain the publication gate.

## Limits

The snapshot is the consolidated central manifest; it includes held metadata and does not establish installation, rendered prompt visibility or organic invocation. The local pre-amendment budget test failed with `10645 not less than or equal to 10500`; that failed condition remains retained. No historical receipt, native result, frozen benchmark case or earlier decision is altered.
