# Eval-tool install receipts: review and repair evidence (2026-09-26)

These are the retained, sanitized inputs behind the superseding install receipts for promptfoo 0.123.1 and inspect-ai 0.3.266 on `nativestack-5975wx-20260925`.

| File | What it is | How it was produced |
|---|---|---|
| `gpt6-cross-family-review.md` | The cross-family review of the original receipts | `codex exec -m gpt-6-astra -c model_reasoning_effort=max --sandbox read-only`, run in the unmerged change's worktree, 2026-09-26 |
| `forced-failure-results.txt` | 34 single mutations of the `-2` receipts' commands, one per step | The recorder ran each mutated command under `/bin/sh` and recorded the exit code and first output line. Every mutation fails closed with rc=1 |

What the review found in the originals:

- **Masked failures in inspect-ai:** `inspect --version` forced to exit 73 still produced command exit 0.
- **Unbacked claims:** installer commands and settings were asserted without any retained installer output.
- **Stale matrix:** the generated component matrix was out of date.

Both originals stay in `evidence/hosts/` and carry `needs_changes` independent reviews. The `-2` receipts supersede them and carry independent `agree` reviews.

Scratch paths are replaced with `<scratch>` and `<session>`. User names and home paths are sanitized with `scripts/host_receipts.py sanitize()`.
