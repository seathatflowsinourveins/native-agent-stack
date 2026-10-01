# Decision: read shell text for the CLI lanes with the tree-sitter-bash parser (2026-09-29)

**Decided by:** the coordinator of the #381 Gate A measurement work (the "U1 pivot" brief of 2026-09-29), after two independent
reviews of the scanner-based lane reading (`3cb7c4f6`): a cross-family GPT-6 read-only review that reproduced 13 defects
(11 P2, 2 P3) and a Claude evidence review that traced 9 more (R1 to R9). The unit was built on branch
`claude/pra-u1-cmdpos-2d-20260928` and closed in its last stage, whose acceptance checks are the oracle test and the
differential below. Checked on GNU bash 5.2.21, dash, Node 24.21.0, tree-sitter-bash 0.25.1, web-tree-sitter 0.27.0 and
rtk 0.50.0. A repair round on the independent verification and review of head `33dcfd24` (2026-09-29) evaluated the first overturn
condition below (it had been stated, not measured), found the tree walk quadratic in the width of a node (GPT-6 #9 had been fixed
for the M4 scanners only) and made it linear, and re-verified the parser pins and the M4 fixtures under real bash and dash; the
evidence README, "Round 2", lists what was and was not run again.

**Scope:** the command-position layer of `examples/claude-native/workflows/child-usage.mjs` (`commandInvocations` and what U1
built on it), its pin `shell-parser.pin.json`, the Codex adapter in `tools/skill-usage/skill_usage.py`, the oracle test
`tests/test_command_position_oracle.py`, the two READMEs and the differential in
`evidence/artifacts/pra-u1-differential-20260929`. It does not change the M4 fetch detection (`executedText`,
`executedTrace`, `fetchKind`), which is mandated to mirror context-mode's routing detector, and it does not adopt the parser
into `manifests/stack.json` or the bootstrap scripts (a shared-hot-file follow-up, below).

## Problem

The 15-commit U1 branch counted CLI lanes with hand-written character scanners over the shell text. The GPT-6 review found the
long tail of that approach in one round: arguments read as commands (`echo bash -c 'qmd search x'`, array elements,
`cat <<'END-JSON'`), quoting rules misread (double-quote backslashes, numeric or hyphenated heredoc delimiters), lost owners
(`env -u X bash <<'EOF'`), a lost substitution (`$(( $(qmd count) + 1 ))`), `rtk proxy` treated as a shell, a quadratic scan and a
name-shaped string that reached the output. Nine of the thirteen were scanner defects. The repository's top rule is to adopt the
best-evidenced upstream source rather than write one.

## Alternatives

| Alternative | Evidence at 2026-09-29 | Disqualifier |
| --- | --- | --- |
| Keep patching the scanners | 13 defects in one review round, 9 in the layer itself; a linear scanner still needs every quoting, heredoc and expansion rule of bash | Measured: it did not converge |
| `sh-syntax` 0.7.0 (mvdan/sh in WebAssembly) | Its JSON AST exposes only positions for interface-typed nodes: `Cmd` and `Word.Parts` came back as `{Pos,End}` | No usable structure without a second walk of the source |
| `mvdan-sh` 0.10.1 (GopherJS) | Last release 2025-04; about 80 ms per parse in its own benchmark | Stale and slow (2,000 tree-sitter parses of a compound command took 52 ms in the coordinator's prototype) |
| `bash-parser` | Last release 2022 | Stale |
| `shell-quote` | A tokenizer with no structure | Cannot separate a command from an argument |
| **tree-sitter-bash 0.25.1 with web-tree-sitter 0.27.0** | The grammar of openai/codex rust-v0.157.1 for the same job (`codex-rs/shell-command/src/bash.rs`, `tree-sitter-bash = "0.25"` at `codex-rs/Cargo.toml:522`); v0.25.1 released 2025-12-02, repository pushed 2026-09-13, not archived; web-tree-sitter 0.27.0 released 2026-08-30 | Chosen; its limits are measured below |

The disqualifiers of the rejected alternatives are the coordinator's measurements as written in the pivot brief; they were not re-measured. The
chosen one's facts were read again in the repair round on the review of head `33dcfd24` (2026-09-29): both npm integrity values and `gitHead`s from
the registry, the sha256 of the six installed files, the tag commits from the GitHub API (`v0.27.0` is an annotated tag whose commit is `6070dbfe`;
`v0.25.1` points at `a06c2e44`) and that neither repository is archived (`tree-sitter-bash` pushed 2026-09-13), each equal to
`shell-parser.pin.json`.

## Decision

1. **The lane reading walks the tree-sitter-bash tree.** Every `command` node counts wherever it sits; array elements, `case`
   patterns, `[[ ]]` operands, function names and the words of non-lane programs never do; ERROR subtrees are skipped and the
   call counts once in `parse_errors` (the valid parts still count; Codex rejects a tree with an error whole,
   `bash.rs:140`). The option tables, runner maps and the mcporter grammar of U1 are unchanged and now operate on word values.
2. **Provisioned, pinned and fail-closed.** Nothing is vendored. `loadShellParser()` verifies the sha256 of six files and
   both npm integrity values against `shell-parser.pin.json` before it loads, imports a private copy of the hashed bytes and
   returns `{ ok, ... }`. With no verified parser `commandInvocations` returns `null`, no lane is counted from any scanner and
   `cli_lanes` is `parser_unavailable`. On CI the lane tests skip and only the fail-closed tests run: CI proves the gate, not lane counts.
3. **What the parser reads wrongly is repaired, and each repair is gated by real bash.** Each class was found by the oracle or
   the differential and has a failing-first test: a `!` read as a command name, escaped nested backquotes,
   words folded into a redirection's target, `time` before an assignment or `!`, an assignment after a doubled negation, a
   heredoc with no delimiter line (closed one delimiter per round), words the grammar cuts in two (`a=$x/$y-$z`, glued to an
   assignment or between arguments), a line that begins with a backslash, and the commands the grammar joins to the previous
   one. Their frequency on this host's real commands is in the README (each is rare).
4. **Names are a closed vocabulary.** `program` is set only for a lane executable or a name the reading interprets (wrappers,
   shells, `eval`, `ssh`, `rtk`); an mcporter server key is one of the stack's own servers or `(other)`, `(http)`, `(stdio)`,
   `(unresolved)`. `manifests/stack.json:280`, `:407`, `:629` and `:966` name `codebase-memory`, `context-mode` and
   `socraticode`; `jcodemunch`, `serena`, `qmd`, `headroom` and `ai-memory` are the coordinator's list in the pivot brief. Before
   this, the scanner reading emitted a name outside that vocabulary for 135,707 of 136,361 real commands (`cd`, `git`, a path, a host), and the new reading for 0.
5. **M4 stays text-based.** It mirrors context-mode v1.0.169 `hooks/core/routing.mjs:788-795` and the #381 gate is defined on
   that detector's reading. The two readings of "what runs" can therefore differ on odd inputs (README, "M4 stays text-based").
6. **The pin follows the npm tarball, not the tag commit.** The npm package was published from `80132668`, one commit before the
   tag commit `a06c2e44` ("Regenerate parser for 0.25.1"); the pinned `.wasm` is the tarball's file, the one `npm install` of
   the pinned version yields, integrity-pinned. A difference between it and a grammar built from the tag commit would be a
   limit of this pin, not something to file upstream.

## Evidence

Every number below is a count from `evidence/artifacts/pra-u1-differential-20260929/counts.json`. Round 1's were run on the kernel with sha256 prefix
`a9126a77fd7f`; the shape, identity, scaling and re-run counts of the repair round ("Round 2" in the evidence README) were run on the kernel `119ce9764447`, which
reads every input alike (scripts and a counts-only README are in that directory).

- **Oracle** (`tests/test_command_position_oracle.py`): 163 of 163 probes, 28 of 28 recovery probes, 456 of 456 and 463 of 463 generated
  commands (fixed seeds) each read the lanes real bash 5.2 ran under stub executables. Over fresh seeds the base and the extended generator ran
  23,894 and 26,767 commands (32,399 and 36,765 lane runs): 0 lane differences, 2 commands whose lanes
  agree with the run but whose tree has a parse error, and 1 first-run differences that a rerun showed to be SIGPIPE races of the run. The extended
  generator against the kernel before this stage's repairs, on seeds 100 to 579: 2,527 lane differences and 0 parse-error-only differences
  in 26,864 commands. Tables: the evidence README.
- **Differential** against the scanner reading of `0c421c66` on 339 covering commands (338 read the same), the 728 commands of the
  current test tables of at most 5,000 characters (661 read the same), three seeded corpora (a token-soup corpus of 40,000 strings, 4,397
  of them accepted by `bash -n`, 4,104 of those read the same; a heredoc corpus and a lane-aware corpus of 20,000 strings each) and this host's 136,361
  distinct real commands (136,248 read the same, 113 differ: 105 in the count of unresolved programs only, 8 in a lane).
  Every difference is classified: by a run of real bash where a lane differs in a corpus that can be run, by the mechanism of its minimal witness where only the
  counts of unresolved programs or remote lanes differ, and by argument alone for the 8 real commands whose lanes differ (real commands are never run).
  Unexplained: 0 in the seeded and covering corpora, 0 in the real commands. Differences whose mechanism was not isolated (an unresolved-program
  count that differs in backquoted text with no lane involved): 9 in the seeded corpora, 0 in the real commands. Of the 8 real lane differences, 7 are old-code defects (`bash -c` as an argument, a case pattern, a process
  substitution's neighbour, a shell string with nested quoting) and 1 is a new limit (an unknown launcher before a shell string).
- **Time.** The first version of this layer was quadratic in the width of a node: the parse is linear, but `node.child(i)` and `fieldNameForChild(i)` cost O(i) per
  call in web-tree-sitter 0.27.0 (tree-sitter `lib/src/node.c:139-171` and `:689-`) and `node.parent` O(depth) (`:547-558`), so `'(('.repeat(n) + 'qmd'` (64,003 characters) took
  7.4 s and GPT-6 finding 9 was fixed for the M4 scanners only. The reading now uses a cursor for a node of more than 16 children (upstream's advice for visiting many nodes,
  `docs/src/using-parsers/4-walking-trees.md:1-4`) and carries the parent's type: the same text takes 63 ms, and every shape measured grows by at most 2.34 per doubling except two whose
  parse itself is quadratic (a run of unclosed `a=(` and of `<<`: 12.6 and 23.2 s at 64,000 characters; this host's largest command has 49,096 characters and at most
  71 heredoc operators). `commandInvocations` and `cli_lanes` records are identical between the two kernels on 217,428 inputs, and the differential totals
  re-run to round 1's on all 6 corpora (evidence README, "Round 2").
- **M4 is unchanged** by the layer: complete `m4` objects, `executedText` in both modes and `fetchKind` of the kernel before the walker and this one
  were compared on 151,221 inputs of the same corpora: 0 differences.

## What would overturn it

- **A grammar limit that loses or invents a lane call in 0.1% or more of a host's lane-bearing commands**: a construct children
  commonly emit that tree-sitter-bash misparses so that a lane call is lost or invented. Evaluated on this host on 2026-09-29 over
  its 136,361 distinct real commands (`shapes.overturn_1` in `counts.json`, from `shape-counts.mjs`), the result is an upper bound of
  5 of 6,527 lane-bearing commands (0.077%), against a threshold of 7 commands (0.1%): **not met**, by 2 commands.
  - The denominator is the commands in which the reading reads a lane invocation (6,527), the smaller of the two counts and so the
    stricter one; 14,210 commands hold a lane word (a whole word equal to a lane executable's name), most of them as data. A lane hidden
    under a skipped ERROR subtree is not among the 6,527, which is why the scan also finds lane words without the parser.
  - A grammar limit is a parse error the reading met (247 commands, 11 of them only in a script the reading read again) or a heredoc the
    grammar ends early (2, both among the 247). The shapes the grammar reads wrongly and the reading repairs are not limits: a word cut
    after an assignment (4,837 commands, 37 with a lane word after the cut), words folded into a redirection (500, 1 with a lane word)
    and `time` before an assignment or `!` (12). Each repair is gated by real bash (the oracle: 0 lane differences over 50,661
    fresh-seed commands), so none loses or invents a call. Counted as limits they would give at most 38 commands (0.58%) and flip the
    verdict, so the boundary is the repair, not the frequency.
  - 31 of the 247 hold a lane word (0.475% of 6,527, above the threshold: the screen counts data, so it is not the criterion). Of
    the 31, 4 read a lane from the valid parts of their tree and count toward the bound, because a lane read from a tree with an error
    could be invented. In the other 27 the reading reads none: 13 have the lane word after plain words (`echo qmd`: an argument,
    whatever the tree makes of it), 13 have it where a command name could stand but the tree puts it in a comment, a heredoc body, a
    string or an assignment value, and 1 has it there inside an ERROR node (a comment in a heredoc body under a skipped subtree),
    which counts toward the bound. The bound is 4 + 1 = 5 (the one heredoc ended early with a lane word is among them).
  - The scanner reading of `0c421c66`, which needs no parser, reads no lane that the tree reading lacks in any of the 247.
  - What the bound does not cover: a misparse with no ERROR node is measured by the oracle and the differential instead (above), and
    the 27 are classified from the text and the tree as given, before the reading's heredoc repairs. Real commands are never run, so
    the classification is an argument, not a run.
  - The margin is 2 commands: run `shape-counts.mjs` again at each pin update and on any new host.
- Upstream archiving or forking the grammar, or Codex replacing it (both checked at each pin update).
- A maintained parser that exposes bash semantics natively (heredoc ownership, expansion order, wrapper resolution) and beats
  the oracle and differential above on the same corpora.

## Limitations and residuals

- The static limits and the grammar limits, with their measured counts, are listed in the workflows README ("The static reading
  cannot see"); the ones that hide a lane are an unknown wrapper (1 real command) and a command string that is a
  substitution's output (`bash -c "$(cat <<'EOF' ...)"`: 5). Text the grammar reports as an error (247 commands) hides what is
  under it, but only 31 of the 247 name a lane and none is confirmed to hide a call (above).
- **Parse cost.** A run of unclosed array assignments or of here-document operators makes tree-sitter-bash's own parse quadratic (see the evidence above); the reading cannot change
  that. A parse budget that marks a text over a limit unresolved, instead of parsing it, is a follow-up: it needs a threshold, a state in the report and a test, and no real command reaches one.
- **Follow-up outside this change:** adopt the parser in `manifests/stack.json` and the bootstrap scripts and add a CI step that
  installs it (shared hot files), so that CI proves lane counts as well as the gate.
- The Python mirror of M4 (`executed_text` in `skill_usage.py`) keeps the earlier reading and disagrees with the kernel in both
  directions on three shapes (tools README); it is a historical comparison field.
- `unresolved_programs` has no oracle (a run cannot show an unknown program): its differences are classified by mechanism, not
  by a run.

## SOTA sources

- openai/codex `rust-v0.157.1` (36650394c5b38c2990ccf2a3457165ca3e9d9726): `codex-rs/shell-command/src/bash.rs:13`, `:124`, `:140`, `:162`; `codex-rs/Cargo.toml:522`; the exec header's exit code is an `i32`: `codex-rs/core/src/tools/context.rs:389`, `:535`.
- tree-sitter/tree-sitter-bash `v0.25.1` (tag commit a06c2e4415e9bc0346c6b86d401879ffb44058f7, npm gitHead 801326684a26ffc4e749bb016c50c6c30bdfa345): `grammar.js:528-540` (`file_redirect` takes `repeat1` destination), `src/node-types.json`.
- tree-sitter/tree-sitter `v0.27.0` (6070dbfefd326bd735e5683eb128cc1b57dad0c0): web-tree-sitter; the cost of `node.child(i)`, `fieldNameForChild(i)` and `node.parent`: `lib/src/node.c:139-171`, `:547-558`, `:689-`; the cursor: `docs/src/using-parsers/4-walking-trees.md:1-4`, `lib/binding_web/src/tree_cursor.ts:58,75,184,234`.
- openclaw/mcporter `v0.14.1` (93e0916cafe2d624b94271e31b75ca681a016514): `src/cli.ts:137-145`, `src/cli/flag-utils.ts:34-41`, `src/cli/help-output.ts:200-210`; a flag written with `=` is not a global, server or ad-hoc flag: `src/cli/cli-factory.ts:19`, `src/cli/flag-utils.ts:12`, `src/cli/call-arguments.ts:63,115,120-121,333`, `src/cli/ephemeral-flags.ts:30` (the installed 0.14.1 binary reads them the same way).
- rtk-ai/rtk `1d87b8e7`: `src/main.rs:68-90`, `:3008-3066`; `src/core/utils.rs:615-632`.
- mksglu/context-mode `v1.0.169`: `hooks/core/routing.mjs:788-795`.
- POSIX.1-2024 XCU 2.6.3 (command substitution), 2.7.4 (here-document), 2.9.1 to 2.9.4; bash(1) 5.2 SHELL GRAMMAR (Pipelines), Here Documents, REDIRECTION, QUOTING; OpenSSH ssh(1) 9.6p1.
