One review round on the first local heads (PR-1 `99bcd4f8`, PR-2 `d3d8095b`, neither pushed yet), before the repair round.

- GPT-6: `codex exec -s read-only -m gpt-6-astra -c model_reasoning_effort="max" -c web_search="live"` per head (codex-cli 0.157.1), prompts `gpt6-pr1-prompt.txt` and `gpt6-pr2-prompt.txt`, answers `gpt6-review-pr1.md` and `gpt6-review-pr2.md`. Its own "tokens used" totals: PR-1 139,158, PR-2 103,290 (not broken down by category).
- Claude: one `evidence-reviewer` over both diffs, brief `claude-brief.txt`, answer `claude-review.md`; usage under `review-both-prs` in `../usage.json`.
