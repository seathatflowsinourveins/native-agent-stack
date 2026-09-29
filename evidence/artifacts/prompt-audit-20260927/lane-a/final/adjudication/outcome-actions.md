# Lane A final X5c adjudication: the action for every outcome (fixed before dispatch)

Worktree: `.hold3/wt-x5` (branch `claude/template-user-level-sync-20260928` at 8315274f). At dispatch it holds X5a as
proposed and X5c as the amending return's text, both measured and registered.

- All four judgments valid and choosing the packet's proposal (mapping `g`): run `apply_x5c_variant.py proposal
  --pin`; register the template and the test (`register_files.py`); run `scripts/component_matrix.py --write` and
  `scripts/new_host_grand_list.py --write`; `scripts/validate.py` and the targeted test modules must pass.
- All four judgments valid and choosing the amendment (mapping `c`): keep the worktree as it is (already registered,
  validated and tested).
- Anything else (a split, any `neither`, any void, leak or malformed return, or a judge that did not return): X5c
  keeps the current text. Run `git restore adoption/templates/codex.AGENTS.template.md
  tests/test_codex_worker_lane.py manifests/evidence.json` in the worktree, register
  `examples/claude-native/CLAUDE.md` only, run both generators, then `scripts/validate.py` and the targeted test
  modules must pass, and `git diff --stat` must show only `examples/claude-native/CLAUDE.md` and
  `manifests/evidence.json`.
- X5a is applied in every case (both lanes agreed).
- No commit, memory write or pull-request edit that pairs a family with an X5c position is made while judges run.
