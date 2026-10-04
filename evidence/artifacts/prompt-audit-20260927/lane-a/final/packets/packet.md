# Judgment packet: prompt-audit lane A, final round: X5a and X5c (base 8315274f)

You are an independent reviewer. Two proposed changes to this repository's instruction templates are below, each
with every co-change it needs. Judge each on its merits: verify the evidence against the original files, check the
primary sources provided, research further where a claim depends on current official documentation, and decide
whether the proposed change is right.

Where things are (all read-only):
- `base/`: the repository at main 8315274f, a plain copy without git history (each line's last change is given
  below);
- `proposed/`: the same copy with this packet's complete proposal applied; it differs from `base/` in exactly four
  files: `adoption/templates/codex.AGENTS.template.md`, `examples/claude-native/CLAUDE.md`, `manifests/evidence.json`, `tests/test_codex_worker_lane.py`;
- `proposal.diff`: the unified diff between them.

Rules:
- Verify, do not trust: excerpts below are copies; the files under `base/` and `proposed/` are the original source.
- A proposal that another file, test or fixture would contradict or break is wrong; say which, with file:line.
- Licenses and incumbency are never selection criteria.
- Judge wording on whether the target models (Claude Code and Codex sessions that load these files) will follow it as
  intended, not on style.
- These items carry the operator's own 2026-09-28 wording of the top rule into the repository's two templates of it.
  The operator's rule itself is not under review. Judge whether each proposed text carries that wording correctly and
  keeps the file's tested obligations and its existing meaning, and whether the co-changes are complete and correct.
- Every `sources` entry names a file:line or URL and quotes the text that supports your verdict.

Verdicts per item: `agree` = apply the proposed change exactly (line 3 and its co-changes); `amend` = apply your
`resolution_text` as line 3 instead, with the same co-changes recomputed for it by the same procedure; `reject` = keep
the current text and make no change. `resolution_text` is empty unless you amend. `confidence` is 0..1.

Convergence rule, fixed before either lane runs: an item is applied when both lanes agree, or when both give the same
amendment. Both reject: the current text stays. Anything else goes to one blind adjudication in both presentation
orders by two adjudicators, and a text is applied only when all four adjudications choose it. This is the final
round for both items: if it does not converge, the current text stays and both positions are recorded.

The operator's own user-level instruction file (`~/.claude/CLAUDE.md`, not in this repository; last modified
2026-09-28 07:34Z) opens with this top rule, verbatim:

```text
**Top rule: research convergence first; current upstream SOTA is the source of truth.** Before any action, research maintained SOTA repositories, installable skills and published references with the installed research and skill-discovery skills, and record what you found. Then install the best-evidenced source directly, or build only from a cited reference implementation, and name that source (repository, pin, file or paper) for every action. With no SOTA source, stop and report instead of writing one. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one. Stars, installs and popularity guide discovery; they are not evidence.
```

The operator's direction for this pass (2026-09-28, verbatim): "please resolute cleanly with the sota repos
convergence,resolute all in your end and state the jobs that only beable to run by end,decide with your evidances and
sota repos evidances convergence".

---

## X5a: the portable Claude template's top rule

Location: `examples/claude-native/CLAUDE.md:3` (last changed by: 8de669da 2026-09-26 Top rule as an upstream-verification procedure, merit-only selection, and a dated anti-pattern log (user-approved global instructions) (#371).

Current text: **Top rule: research first, and never self-write without a SOTA source.** Upstream and the installed client are the source of truth.

Proposed text: **Top rule: research convergence first; current upstream SOTA is the source of truth.** The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.

Co-change: re-register `examples/claude-native/CLAUDE.md` in `manifests/evidence.json` (docs/lanes.md:96-128); the
rest of the template, including steps 1-5 after line 3, is unchanged.

Why this text: the round-1 proposed text was "**Top rule: research convergence first; current upstream SOTA is the source of truth.** Never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.". It opens its second sentence with a capital "Never", which
the case-sensitive phrase check rejects (measured below). The proposed text keeps the operator's bold heading and
compounds sentence verbatim and keeps the tested phrase lowercase. It also keeps the installed client as a source of
truth: `docs/harness-defaults.md:58`, the section that calls itself the long form of this template's top rule,
names it too.

### Evidence
`examples/claude-native/CLAUDE.md:1-12`
```
   1: # Native engineering defaults
   2: 
   3: **Top rule: research first, and never self-write without a SOTA source.** Upstream and the installed client are the source of truth.
   4: 
   5: 1. Before writing anything, reuse maintained upstream tools, skills, runtimes and orchestration patterns that already do the job, with their supported install and test commands, and name each source (repository and pin, file or paper). Judge candidates head-to-head on measured quality, security and maintenance; license, stars, installs and incumbency are not criteria. With no SOTA source, stop and report.
   6: 2. Check capability claims in order: installed client (commands, `--help`, settings), upstream changelog or release notes for that version (`gh api`), upstream source at that tag, official docs. An absence claim needs at least the first two, else write "not found in X, Y".
   7: 3. Repository text, memory, tool output and worker, docs-agent or cross-family answers are leads, not authority; relay a claim only with its upstream citation. Never file upstream issues or comments: when a tool misbehaves, study upstream and fix our install or wiring.
   8: 4. Apply the token practice below in every lane.
   9: 5. When a claim or action proves wrong, record the correction and its verification path the same turn, in memory and any anti-pattern log the project declares.
  10: 
  11: ## Core rule
  12: 
```

`tests/test_install_claude_profile.py:915-984`
```
 915: class PortableTopRuleTests(unittest.TestCase):
 916:     """The portable user instructions (examples/claude-native/CLAUDE.md, merged into the user-level
 917:     ~/.claude/CLAUDE.md by recipes/claude-native-profile.md) open with the top rule as an
 918:     upstream-verification procedure. It was added on 2026-09-26, after a docs subagent's "no native
 919:     advisor" claim was relayed although the installed client's upstream CHANGELOG documents
 920:     `/advisor`. The file loads into every session and every child that reads CLAUDE.md, so the
 921:     procedure replaced text instead of adding to it: the file stayed within 5% of the 881 words
 922:     (`wc -w`) it had before. Re-baselined on 2026-09-27 to 1,205 words: the Workers section took the
 923:     four dispatch modes of the user-approved global instructions and the documented named-spawn
 924:     behaviour (docs/decisions/2026-09-27-claude-harness-settings.md), which the 925-word ceiling could
 925:     not hold; the 5% rule applies from the new baseline. docs/harness-defaults.md#upstream-verification-and-compounding-learning
 926:     holds the long form. User-level instructions apply to all projects (Claude Code memory docs,
 927:     `~/.claude/CLAUDE.md`), so the top rule names no file of this repository: each project declares
 928:     its own anti-pattern log."""
 929: 
 930:     TEMPLATE = ROOT / "examples" / "claude-native" / "CLAUDE.md"
 931:     BASELINE_WORDS = 1205  # wc -w after the 2026-09-27 Workers section (881 at dde28cc2, before the procedure)
 932:     # Upstream as the source of truth and reuse, the check order and the absence wording, worker
 933:     # answers as leads, the token practice in every lane, and recording a proven mistake.
 934:     PROCEDURE_PHRASES = (
 935:         "never self-write without a SOTA source",
 936:         "source of truth",
 937:         "orchestration patterns",
 938:         "installed client",
 939:         "upstream changelog or release notes",
 940:         "upstream source at that tag",
 941:         "official docs",
 942:         "absence claim needs at least the first two",
 943:         '"not found in X, Y"',
 944:         "leads, not authority",
 945:         "upstream citation",
 946:         "token practice below in every lane",
 947:         "same turn",
 948:         "anti-pattern log",
 949:     )
 950:     # A relative path such as docs/harness-defaults.md; one that exists here is absent from other projects.
 951:     RELATIVE_PATH = re.compile(r"[\w.-]+(?:/[\w.-]+)+")
 952: 
 953:     @staticmethod
 954:     def top_rule(text: str) -> str:
 955:         """The text from the bold top rule to the first section heading."""
 956:         start = text.find("**Top rule:")
 957:         end = text.find("\n## ", start)
 958:         return text[start:end] if 0 <= start < end else ""
 959: 
 960:     @classmethod
 961:     def ceiling(cls) -> int:
 962:         return int(cls.BASELINE_WORDS * 1.05)
 963: 
 964:     @classmethod
 965:     def errors(cls, text: str) -> list[str]:
 966:         rule = cls.top_rule(text)
 967:         errors = [f"the top rule lacks {phrase!r}" for phrase in cls.PROCEDURE_PHRASES if phrase not in rule]
 968:         errors += [f"the top rule names this repository's {path}, which other projects lack"
 969:                    for path in dict.fromkeys(cls.RELATIVE_PATH.findall(rule)) if (ROOT / path).exists()]
 970:         words = len(text.split())  # the same whitespace-separated count as `wc -w`
 971:         if words > cls.ceiling():
 972:             errors.append(f"{words} words, over {cls.ceiling()} ({cls.BASELINE_WORDS} + 5%)")
 973:         return errors
 974: 
 975:     def test_the_template_states_the_procedure_within_the_word_budget(self):
 976:         self.assertEqual(self.errors(self.TEMPLATE.read_text(encoding="utf-8")), [])
 977: 
 978:     def test_the_check_rejects_a_missing_step_a_repository_path_and_a_padded_template(self):
 979:         text = self.TEMPLATE.read_text(encoding="utf-8")
 980:         self.assertEqual(len(self.errors(text.replace("upstream citation", "citation"))), 1)
 981:         self.assertEqual(len(self.errors(text.replace("same turn", "same turn (docs/harness-defaults.md)"))), 1)
 982:         padded = text + " word" * max(1, self.ceiling() + 1 - len(text.split()))
 983:         self.assertEqual(len(self.errors(padded)), 1)
 984:         self.assertEqual(len(self.errors("# Native engineering defaults\n\nNo rule.\n")), len(self.PROCEDURE_PHRASES))
```

`docs/harness-defaults.md:7-7`
```
   7: Decide by evidence and research convergence: a choice stands when current primary sources (native help, official docs, maintained upstream) and reproduced results on the actual change agree, and it carries a dated record naming the alternatives and the comparison that would overturn it. Agreement, recency, stars and extra tooling are not evidence. The defaults below apply this rule under the top rule in [`AGENTS.md`](../AGENTS.md): research first, and never self-write without a SOTA source. The portable user-level instructions ([`examples/claude-native/CLAUDE.md`](../examples/claude-native/CLAUDE.md)) state that top rule as the five-step procedure spelled out in [Upstream verification and compounding learning](#upstream-verification-and-compounding-learning), followed by the same core sentence; agent-lab `AGENTS.md` adopted the core sentence in agent-lab PR #16 (2026-09-23).
```

`docs/harness-defaults.md:56-60`
```
  56: ## Upstream verification and compounding learning
  57: 
  58: This is the long form of the top rule's five steps in the portable instructions ([`examples/claude-native/CLAUDE.md`](../examples/claude-native/CLAUDE.md)). This section and that procedure form changed after `v2026.09.26.2`; a host at that tag has the earlier text. Upstream repositories, their changelogs and release notes, and the installed client are the source of truth. Documentation pages, docs agents, `--help` output and memory lag or omit capabilities, so they are leads.
  59: 
  60: ### Check a capability claim in order
```

`recipes/claude-native-profile.md:79-84`
```
  79: ## Small persistent contract; selected upstream skills
  80: 
  81: Merge the [short instruction example](../examples/claude-native/CLAUDE.md) into
  82: the user's existing `~/.claude/CLAUDE.md`, preserving independent preferences and
  83: managed imports. Since the [2026-09-26 cleanup](../docs/decisions/2026-09-26-harness-rules-cleanup.md)
  84: the example states each rule once under section headings, so replace an earlier
```

---

## X5c: the Codex user-instructions template's top rule

Location: `adoption/templates/codex.AGENTS.template.md:3` (last changed by:
50b9579f 2026-09-27 PR-D: Codex worker lane: Codex's own config writer, RTK text inline with exceptions, max-effort stack-worker profile (#389)).

Current text: Top rule: never self-write without a SOTA source; upstream and the installed client are the source of truth.

Proposed text: Top rule: research convergence first; current upstream SOTA is the source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.

Co-changes, all in `proposal.diff`:
- `tests/test_codex_worker_lane.py`: `TOP_RULE_SHA256` (:47) set to the sha256 of the proposed top-rule block, the
  word count at :210 from 120 to 144 and the :45 comment to match. Both values were computed with the test module's
  own `template_segments()` on the proposed template, not copied from elsewhere.
- `manifests/evidence.json`: the template and the test file re-registered (docs/lanes.md:96-128).
- Host step, outside the repository: a Codex home that installed the lane block keeps the old line until
  `tools/adoption/apply_codex_lane.py` is re-run there (dry run, then `--apply`) after the change merges.

Why the co-changes: `tests/test_codex_worker_lane.py:209-210` pin the staged top-rule block's sha256 and word count,
reproducing the 2026-09-26 staged block. Replacing line 3 alone fails that test (measured below).

### Evidence
`adoption/templates/codex.AGENTS.template.md:1-9`
```
   1: <!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
   2: <!-- native-agent-stack:top-rule -->
   3: Top rule: never self-write without a SOTA source; upstream and the installed client are the source of truth.
   4: Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
   5: Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
   6: Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
   7: Process large output outside the model.
   8: When a claim proves wrong, record the correction and its verification path that turn.
   9: 
```

`tests/test_codex_worker_lane.py:40-50`
```
  40: import prove_codex_lane as prove  # noqa: E402
  41: from scripts import adoption_status  # noqa: E402
  42: 
  43: TEMPLATES = ROOT / "adoption" / "templates"
  44: FIXTURES = ROOT / "tests" / "fixtures" / "codex-worker-lane"
  45: # The staged top-rule block (120 words by `wc -w`, marker line included) and rtk-ai/rtk v0.50.0
  46: # hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec), both byte for byte.
  47: TOP_RULE_SHA256 = "476b73c52ecc64bdf5152fe4b5188aef8d22db6f3f8816789a0842abe2841311"
  48: RTK_AWARENESS_SHA256 = "278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc"
  49: UPSTREAM_MARKER = "<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->\n"
  50: 
```

`tests/test_codex_worker_lane.py:183-212`
```
 183: 
 184: 
 185: def template_segments() -> tuple[str, str, str]:
 186:     """(top-rule block, upstream awareness text, exceptions block) of the AGENTS template."""
 187:     text = (TEMPLATES / "codex.AGENTS.template.md").read_text(encoding="utf-8")
 188:     body = text.split("\n", 1)[1]  # after the begin marker line
 189:     top, rest = body.split("\n" + UPSTREAM_MARKER, 1)
 190:     upstream, exceptions = rest.split("\n<!-- native-agent-stack:rtk-exceptions -->\n", 1)
 191:     return top, upstream, exceptions
 192: 
 193: 
 194: class TemplateTests(unittest.TestCase):
 195:     def test_agents_template_is_one_managed_block(self):
 196:         text = (TEMPLATES / "codex.AGENTS.template.md").read_text(encoding="utf-8")
 197:         self.assertTrue(text.startswith(lane.BLOCK_BEGIN))
 198:         self.assertTrue(text.endswith(lane.BLOCK_END + "\n"))
 199:         self.assertEqual(text.count(lane.BLOCK_BEGIN), 1)
 200:         self.assertEqual(text.count(lane.TOP_RULE_MARKER), 1)
 201:         self.assertEqual(text.count(lane.EXCEPTIONS_MARKER), 1)
 202:         self.assertEqual(lane.agents_block(), text)
 203:         # Codex expands no @ reference (codex-rs/core/src/agents_md.rs at rust-v0.157.1): the text is inline.
 204:         self.assertFalse([line for line in text.splitlines() if line.startswith("@")])
 205:         self.assertLess(len(text.encode("utf-8")), 8192)  # far under Codex's 32 KiB project_doc_max_bytes
 206: 
 207:     def test_top_rule_and_upstream_text_are_verbatim(self):
 208:         top, upstream, _ = template_segments()
 209:         self.assertEqual(hashlib.sha256(top.encode("utf-8")).hexdigest(), TOP_RULE_SHA256)
 210:         self.assertEqual(len(top.split()), 120)
 211:         self.assertEqual(hashlib.sha256(upstream.encode("utf-8")).hexdigest(), RTK_AWARENESS_SHA256)
 212: 
```

`tools/adoption/apply_codex_lane.py:12-15`
```
  12:                 timeout option, so a server it registered has none). No other key is sent.
  13:   AGENTS.md     the managed block of adoption/templates/codex.AGENTS.template.md (the top rule, rtk-ai/rtk
  14:                 v0.50.0's awareness text verbatim, this catalog's exceptions), inserted or replaced between its
  15:                 begin and end markers; every other line is kept. Hash-guarded atomic write.
```

`evidence/artifacts/codex-worker-lane-20260926/scripts/assemble_agents.py.txt:1-6`
```
   1: # As run on 2026-09-26 (paths masked); a record, not a maintained tool.
   2: """Assemble adoption/templates/codex.AGENTS.template.md from its three verified sources (scratch build step).
   3: 
   4: 1. the staged top-rule block (120 words by wc -w, marker line included), byte for byte;
   5: 2. rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, fetched with gh api at the tag, byte for byte;
   6: 3. this catalog's exceptions block.
```

`docs/decisions/2026-09-26-codex-worker-lane.md:57-60`
```
  57: 3. **`AGENTS.md` carries the text itself.** Codex reads one global file: `AGENTS.override.md` when it has text,
  58:    else `AGENTS.md` (the Codex AGENTS.md guide, read 2026-09-26). The block has three parts:
  59:    - the top rule (120 words, marker `native-agent-stack:top-rule`);
  60:    - rtk-ai/rtk v0.50.0's `hooks/rtk-awareness-full.md`, verbatim (tag commit `1d87b8e7`, sha256 `278274ef…`,
```

---

## Registration procedure (both items)
`docs/lanes.md:96-128`
```
  96: Put every shared hot-file edit in the branch's last commit, and rebase right
  97: before merge. Never hand-merge `manifests/evidence.json`: take `main`'s copy
  98: and re-register your own files.
  99: 
 100: ```sh
 101: git fetch origin
 102: git diff --name-only --diff-filter=AM origin/main...HEAD  # files you added or changed
 103: git diff origin/main...HEAD -- manifests/evidence.json     # entries you added
 104: git rebase origin/main
 105: git checkout origin/main -- manifests/evidence.json
 106: python3 -c 'import sys; from pathlib import Path; sys.path.insert(0, "scripts"); import host_receipts
 107: for p in sys.argv[1:]: host_receipts.register_file(Path("."), p)' <files to register>
 108: python3 scripts/component_matrix.py --write
 109: python3 scripts/new_host_grand_list.py --write
 110: python3 scripts/validate.py
 111: ```
 112: 
 113: - Take both listings before the rebase. The checkout drops everything your
 114:   branch added to `manifests/evidence.json`, so re-add your own `receipts[]`
 115:   and `convergence_records[]` entries from the second listing.
 116: - `<files to register>` means each file in the first listing that `main`'s
 117:   manifest already lists, each new file under `evidence/` and any other new
 118:   file your branch registered. Every tracked evidence file is listed today;
 119:   `scripts/validate.py` enforces it for `evidence/receipts/` and
 120:   `evidence/artifacts/`, and `scripts/host_receipts.py validate` for
 121:   `evidence/hosts/`. Never pass `manifests/evidence.json` itself or the four
 122:   generated reports above; their `--write` commands re-register them. Remove
 123:   the entry of a file your branch deleted; `scripts/validate.py` reports it as
 124:   `file missing`.
 125: - If the rebase stops on `manifests/evidence.json`, run the commands after
 126:   `git rebase` at that point, `git add` the results and run
 127:   `git rebase --continue`. Otherwise fold the results into the last commit
 128:   with `git commit --amend`. Push with `git push --force-with-lease`.
```

---

## Measured results

Run by the coordinator on 2026-09-28 in one worktree of main 8315274f, at the stages each entry names; its final
state is the four files in `proposed/`. Test runs set TMPDIR to a private directory; the worktree path is shown as
`<worktree>`.

- X5a failing control: line 3 set to the round-1 proposed text (quoted under X5a), which opens its second sentence with a capital 'Never'.
  Command (run from the worktree root): `python3 -B -m unittest tests.test_install_claude_profile.PortableTopRuleTests`
  Exit code: 1. Output lines:
  ```
  FAIL: test_the_check_rejects_a_missing_step_a_repository_path_and_a_padded_template (tests.test_install_claude_profile.PortableTopRuleTests.test_the_check_rejects_a_missing_step_a_repository_path_and_a_padded_template)
  AssertionError: 2 != 1
  FAIL: test_the_template_states_the_procedure_within_the_word_budget (tests.test_install_claude_profile.PortableTopRuleTests.test_the_template_states_the_procedure_within_the_word_budget)
  AssertionError: Lists differ: ["the top rule lacks 'never self-write without a SOTA source'"] != []
  Ran 2 tests in 0.001s
  FAILED (failures=2)
  ```
- X5a proposed text in line 3.
  Command (run from the worktree root): `python3 -B -m unittest tests.test_install_claude_profile.PortableTopRuleTests`
  Exit code: 0. Output lines:
  ```
  Ran 2 tests in 0.001s
  OK
  ```
- X5c failing control: the proposed line 3 with tests/test_codex_worker_lane.py at the base (no re-pin).
  Command (run from the worktree root): `python3 -B -m unittest tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim`
  Exit code: 1. Output lines:
  ```
  FAIL: test_top_rule_and_upstream_text_are_verbatim (tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim)
  AssertionError: '71a852be0b5ebd2c3610e2d9952e01f4009939c49a9ac691d0f1e4e3f798ca7f' != '476b73c52ecc64bdf5152fe4b5188aef8d22db6f3f8816789a0842abe2841311'
  Ran 1 test in 0.001s
  FAILED (failures=1)
  ```
- X5c proposed line 3 with the re-pinned test.
  Command (run from the worktree root): `python3 -B -m unittest tests.test_codex_worker_lane.TemplateTests.test_top_rule_and_upstream_text_are_verbatim`
  Exit code: 0. Output lines:
  ```
  Ran 1 test in 0.000s
  OK
  ```
- Registration control 1: both X5c files edited, manifest not yet re-registered.
  Command (run from the worktree root): `python3 scripts/validate.py`
  Exit code: 1. Output lines:
  ```
  Publication validation failed:
  adoption/templates/codex.AGENTS.template.md: SHA-256 mismatch
  adoption/templates/codex.AGENTS.template.md: byte count mismatch
  tests/test_codex_worker_lane.py: SHA-256 mismatch
  ```
- Registration control 2: X5c files registered, X5a's template edited but not yet re-registered.
  Command (run from the worktree root): `python3 scripts/validate.py`
  Exit code: 1. Output lines:
  ```
  Publication validation failed:
  examples/claude-native/CLAUDE.md: SHA-256 mismatch
  examples/claude-native/CLAUDE.md: byte count mismatch
  ```
- After registering all three changed files (scripts/host_receipts.py register_file; then scripts/component_matrix.py --write and scripts/new_host_grand_list.py --write, which changed nothing).
  Command (run from the worktree root): `python3 scripts/validate.py`
  Exit code: 0. Output lines:
  ```
  {"components": 69, "hashed_files": 7478, "profiles": 4, "receipts": 159, "status": "passed"}
  Integrity and scope checks only; no live provider or GPU execution.
  ```
- The complete proposal (root/proposed): the test modules that read either template or the pin.
  Command (run from the worktree root): `python3 -B -m unittest tests.test_install_claude_profile tests.test_codex_worker_lane tests.test_codex_agents tests.test_codex_lane tests.test_landscape_sweep_harness tests.test_adoption_docs_consistency`
  Exit code: 0. Output lines:
  ```
  Ran 353 tests in 55.314s
  OK (skipped=15)
  ```

---

## The complete proposal (`proposal.diff`)

```diff
diff --git a/adoption/templates/codex.AGENTS.template.md b/adoption/templates/codex.AGENTS.template.md
index f87a0420..0b171677 100644
--- a/adoption/templates/codex.AGENTS.template.md
+++ b/adoption/templates/codex.AGENTS.template.md
@@ -1,6 +1,6 @@
 <!-- native-agent-stack:codex-user-instructions:begin (adoption/templates/codex.AGENTS.template.md) -->
 <!-- native-agent-stack:top-rule -->
-Top rule: never self-write without a SOTA source; upstream and the installed client are the source of truth.
+Top rule: research convergence first; current upstream SOTA is the source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
 Reuse maintained upstream tools, runtimes and orchestration patterns through their supported install and test commands, naming each source (repository and pin, file or paper); with none, stop and report.
 Check capability claims in order: installed client (commands, --help, settings), upstream changelog for that version (gh api), upstream source at that tag, official docs. Absence claims need the first two, else say "not found in X, Y".
 Worker, docs-agent and cross-family answers are leads; relay claims only with upstream citations.
diff --git a/examples/claude-native/CLAUDE.md b/examples/claude-native/CLAUDE.md
index 8819b8a5..ae1b420d 100644
--- a/examples/claude-native/CLAUDE.md
+++ b/examples/claude-native/CLAUDE.md
@@ -1,6 +1,6 @@
 # Native engineering defaults
 
-**Top rule: research first, and never self-write without a SOTA source.** Upstream and the installed client are the source of truth.
+**Top rule: research convergence first; current upstream SOTA is the source of truth.** The installed client is also a source of truth; never self-write without a SOTA source. The ecosystem compounds: each choice adopts the current best converged practice and is replaced when the live landscape converges on a better-evidenced one.
 
 1. Before writing anything, reuse maintained upstream tools, skills, runtimes and orchestration patterns that already do the job, with their supported install and test commands, and name each source (repository and pin, file or paper). Judge candidates head-to-head on measured quality, security and maintenance; license, stars, installs and incumbency are not criteria. With no SOTA source, stop and report.
 2. Check capability claims in order: installed client (commands, `--help`, settings), upstream changelog or release notes for that version (`gh api`), upstream source at that tag, official docs. An absence claim needs at least the first two, else write "not found in X, Y".
diff --git a/manifests/evidence.json b/manifests/evidence.json
index 065bddd7..8f37bee8 100644
--- a/manifests/evidence.json
+++ b/manifests/evidence.json
@@ -3747,8 +3747,8 @@
     },
     {
       "path": "adoption/templates/codex.AGENTS.template.md",
-      "sha256": "7ce4fbc38f1994746c21d7dc5b9d9367d6c7c3b02ee4d725ea859e54ab93f313",
-      "bytes": 3151
+      "sha256": "f001536d81cc840774e0ec2086c8c6ed3ed91ab58a2c74822588079074b57d09",
+      "bytes": 3323
     },
     {
       "path": "adoption/templates/codex.config.template.toml",
@@ -38708,8 +38708,8 @@
     },
     {
       "path": "examples/claude-native/CLAUDE.md",
-      "sha256": "bd9cd167681b637aed3ea4d70c07e561ea64a30862c07a6bc3a06565f9426dd0",
-      "bytes": 8480
+      "sha256": "a31b3551bb9be77f91a3ff841768bb30ef90d61a9870a657044df3b4e98f663a",
+      "bytes": 8680
     },
     {
       "path": "examples/claude-native/agents/blind-adjudicator.md",
@@ -39823,7 +39823,7 @@
     },
     {
       "path": "tests/test_codex_worker_lane.py",
-      "sha256": "3338942353fbcf0464e2437969c81da6d3e8a02baee87fdba07fc98fcd5d3cbf",
+      "sha256": "51e9378b64832313343c12255ec46fd3b6d6b4d04331bd86f4eae9d4325dc24e",
       "bytes": 95109
     },
     {
diff --git a/tests/test_codex_worker_lane.py b/tests/test_codex_worker_lane.py
index 3b4e2ac7..442c0f03 100644
--- a/tests/test_codex_worker_lane.py
+++ b/tests/test_codex_worker_lane.py
@@ -42,9 +42,9 @@ from scripts import adoption_status  # noqa: E402
 
 TEMPLATES = ROOT / "adoption" / "templates"
 FIXTURES = ROOT / "tests" / "fixtures" / "codex-worker-lane"
-# The staged top-rule block (120 words by `wc -w`, marker line included) and rtk-ai/rtk v0.50.0
+# The staged top-rule block (144 words by `wc -w`, marker line included) and rtk-ai/rtk v0.50.0
 # hooks/rtk-awareness-full.md (tag commit 1d87b8e719ce0a50c223cd93ca64dd16921f9aec), both byte for byte.
-TOP_RULE_SHA256 = "476b73c52ecc64bdf5152fe4b5188aef8d22db6f3f8816789a0842abe2841311"
+TOP_RULE_SHA256 = "71a852be0b5ebd2c3610e2d9952e01f4009939c49a9ac691d0f1e4e3f798ca7f"
 RTK_AWARENESS_SHA256 = "278274ef3d08c858d4247cc91419c4d74ef922b95719e987b22e896aef10e1fc"
 UPSTREAM_MARKER = "<!-- native-agent-stack:rtk-upstream rtk-ai/rtk v0.50.0 hooks/rtk-awareness-full.md, verbatim -->\n"
 
@@ -207,7 +207,7 @@ class TemplateTests(unittest.TestCase):
     def test_top_rule_and_upstream_text_are_verbatim(self):
         top, upstream, _ = template_segments()
         self.assertEqual(hashlib.sha256(top.encode("utf-8")).hexdigest(), TOP_RULE_SHA256)
-        self.assertEqual(len(top.split()), 120)
+        self.assertEqual(len(top.split()), 144)
         self.assertEqual(hashlib.sha256(upstream.encode("utf-8")).hexdigest(), RTK_AWARENESS_SHA256)
 
     def test_exceptions_name_every_raw_sensitive_form(self):
```

---

## Primary sources

This round's questions are internal to the repository: its tests, pins, manifest and the two templates. How each
template reaches a session is recorded in the excerpts above: `recipes/claude-native-profile.md:79-84` for the
portable template, and `docs/decisions/2026-09-26-codex-worker-lane.md:57-58` for the Codex block, which cites the
Codex AGENTS.md guide as read on 2026-09-26. A lane with web access may re-check the current guides and cite them.
