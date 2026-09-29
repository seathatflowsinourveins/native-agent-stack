# Command-position differential (U1 pivot, 2026-09-29)

Counts only. No command text, transcript id, host name, URL or path is committed here: the inputs of the differential are this host's
own commands (private, mode 0600, in a scratch directory outside every checkout) and generated shell texts, and every table below is a number.
`counts.json` is the machine-readable record of the run; the tables are rendered from it.

Kernel under test: `examples/claude-native/workflows/child-usage.mjs`, sha256 prefix `a9126a77fd7f` (the full value is in `counts.json`),
with the verified tree-sitter-bash 0.25.1 install of `shell-parser.pin.json`.

**Round 2** (the repair of the review of head `33dcfd24`, below): the kernel's walk over the tree changed and its sha256 prefix is now
`119ce9764447`; what the reading returns did not (`217,428` inputs, every record identical). Four sections of `counts.json` were produced
again by `update-round2.py` (`corpus`, `shapes`, `lanes_identity`, `scaling`) and one was added (`differential_rerun`); every other section is
round 1's, measured on `a9126a77fd7f`, and the identity check shows that it describes both kernels.

## What this compares

The CLI-lane reading of `commandInvocations` before the U1 pivot (commit `0c421c66`, character scanners, sha256 `acc7bb51...`, the "old" reading)
against the reading now (the tree-sitter-bash walker, the "new" reading), and the reading of `f1ed98ac` (before the walker) on this host's real commands.
Neither baseline is committed: `git show 0c421c66:examples/claude-native/workflows/child-usage.mjs` and the same for `f1ed98ac` recreate them.

The comparison is a projection of the reading: the local lane tokens (a lane name, `!` when the call is excluded as `--version` or `--help`, mcporter as
`mcporter:<op>@<server>` with the server key mapped through the closed vocabulary of the pivot's decision D5), the number of remote lanes, and the number of
unresolved programs. `program` names are not compared: the old reading emitted any name-shaped basename.

## Files

| file | what it does |
| --- | --- |
| `run-differential.py` | the driver: runs every step below and writes `counts.json` |
| `make-inputs.mjs` | seeded shell-text corpora (`soup`, `heredoc`, `lanes`) and their `bash -n` validity |
| `differential.mjs` | old against new on a corpus; reduces every difference to a minimal witness with the same lane-difference signature |
| `classify.py` | classifies every difference (below) |
| `m4-identity.mjs` | `executedText` (both modes), `fetchKind` and the complete `m4` object of two kernels on a corpus; with `--fields lanes` the whole `commandInvocations` and `cli_lanes` records instead |
| `oracle-scale.py` | the oracle's generators over fresh seeds against real bash |
| `repeat-oracle.sh` | repeats the committed oracle module N times (stability of the fixed seeds) |
| `shape-counts.mjs` | how many real commands hold each shape the reading has to know about, the first overturn condition (`overturn_1`) and the largest commands |
| `timing.mjs` | the cost of each reading of a call |
| `states-count.mjs` | the not-executed and interrupted shapes in Claude Code transcripts |
| `real-commands.mjs` | extracts the private corpus of real commands from the local transcripts (`--until` rebuilds an earlier corpus) |
| `scaling.mjs` | the time of `commandInvocations`, and of the parse alone, by input size for 21 shapes (round 2) |
| `update-round2.py` | round 2: the shape scan, the whole-record identity check, the scaling and the differential totals, spliced into `counts.json` |
| `capture-covering.py` | the shell texts the covering test tables feed the kernel |

Run it (the parser and bash must be installed; the work directory must stay outside every checkout because it holds command text):

```sh
node evidence/artifacts/pra-u1-differential-20260929/real-commands.mjs "$WORK/real.json"
python3 evidence/artifacts/pra-u1-differential-20260929/capture-covering.py --repo . --out "$WORK/covering.json"
python3 evidence/artifacts/pra-u1-differential-20260929/run-differential.py --repo . --old <0c421c66 kernel> --pre-ast <f1ed98ac kernel> \
  --work "$WORK" --real "$WORK/real.json" --covering current_tests="$WORK/covering.json" \
  --pre-repair-kernel <2bad7320 kernel> --marks-before <11d7e0bd kernel> --marks-after <9a4e9f97 kernel>
```

Round 2 (the corpus is rebuilt with `real-commands.mjs --until`; the baseline and the scanner are the kernels of `33dcfd24` and `0c421c66`):

```sh
node evidence/artifacts/pra-u1-differential-20260929/real-commands.mjs "$WORK/real.json" --until {corpus['until']}
python3 evidence/artifacts/pra-u1-differential-20260929/update-round2.py --repo . --scanner <0c421c66 kernel> --baseline <33dcfd24 kernel> --work "$WORK" \
  --real "$WORK/real.json" --real-until {corpus['until']} --until-reconstructed --identity NAME=PATH ... --differential NAME=INPUTS[:VALID] ...
```

## What decides each verdict

- **A lane differs, in a corpus that can be run** (the seeded corpora and the covering tables): the INPUT ITSELF runs under real bash 5.2 with logging
  stub executables (`env -i`, a `PATH` of stubs, a temporary HOME, 5 s, three attempts), and the reading equal to the run is right. This is a run, not an
  argument. The minimal witness only names the mechanism (which review finding the old defect repeats, which grammar limit the new one is): that label is a
  pattern match on the witness and is a heuristic.
- **Only the count of remote lanes or of unresolved programs differs**: no run can show either, so the class is the mechanism of the minimal witness
  (an ERROR node is skipped, `eval` words are read, a shell string operand is read, an array element is not a command, and so on). This is an argument.
- **A lane differs in the real commands**: real commands are never run, so the class is by the shape of the witness and by argument alone.
- **Catch-all classes**: where the new reading counts a lane that the full input's run does not reach, the class is admitted only when the run of the
  minimal witness equals the new reading (else it stays unexplained), or the witness defines a function (documented: a body counts where it is defined).
  `mechanism not isolated` and `other old-code defect` are reported separately in `counts.json` (`mechanism_not_isolated`, `other_old_code_defect`) and are
  not counted as explanations.

## Results

### Old reading against new reading

| corpus | inputs | bash-valid | analysed | read the same | differ | kinds of difference |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| soup | 40,000 | 4,397 | 4,397 | 4,104 | 293 | unresolved 268, lanes+unresolved 13, lanes 7, remote 5 |
| heredoc | 20,000 | 4,656 | 4,656 | 4,119 | 537 | unresolved 465, lanes 45, lanes+unresolved 22, remote 3, lanes+remote 1, lanes+remote+unresolved 1 |
| lanes | 20,000 | 4,740 | 4,740 | 4,098 | 642 | lanes 326, unresolved 201, lanes+unresolved 75, remote 35, lanes+remote+unresolved 3, remote+unresolved 2 |
| covering_current_tests | 728 | not checked | 728 | 661 | 67 | lanes 58, lanes+unresolved 4, unresolved 4, remote 1 |
| covering_stage_a_339 | 339 | not checked | 339 | 338 | 1 | unresolved 1 |
| real | 136,361 | not checked | 136,361 | 136,248 | 113 | unresolved 105, lanes 7, lanes+unresolved 1 |
| real_vs_pre_ast | 136,361 | not checked | 136,361 | 136,197 | 164 | unresolved 156, lanes 7, lanes+unresolved 1 |

`bash-valid` is the number of inputs `bash -n` accepts (only those are analysed); a corpus with no validity file is analysed whole and reads "not checked".
The real commands are not checked with `bash -n`: they ran under bash as Bash tool calls. `differ_new_parse_error` and the program-name vocabulary
counts are in `counts.json`: the old reading emitted a program name outside the closed vocabulary for 135,707 of 136,361 real commands and the new one
for 0. Against the reading of `f1ed98ac` the real commands differ in 164 (the same classes plus the shell strings and `eval` words that
the walker started to read).

### Classification of every difference

Seeded and covering corpora (verdicts by a run of the input):

| corpus | class | differences |
| --- | --- | ---: |
| soup | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 252 |
| soup | old defect: oracle class 2: escaped nested backquotes | 9 |
| soup | unresolved programs: eval words are read (pivot D4(c)) | 7 |
| soup | remote lanes: unquoted ssh words are read (pivot D4(d)) | 5 |
| soup | unresolved programs: a shell string operand is read (pivot D3/D4(a)) | 5 |
| soup | mechanism not isolated: the unresolved count differs in backquoted text with no lane involved | 3 |
| soup | new limit: text the grammar reports as an error (its subtree is skipped) | 3 |
| soup | static reading: the valid part of a script that bash rejects as a whole is read (pivot D2) | 3 |
| soup | old defect: GPT-6 1: a shell string that is not read by a shell (options before -c, -n) | 2 |
| soup | old defect: eval words were not read (pivot D4(c)) | 2 |
| soup | old defect: oracle class 3: words after a redirection's target | 1 |
| soup | unresolved programs: a proxied program named by an expansion (Claude R5) | 1 |

| corpus | class | differences |
| --- | --- | ---: |
| heredoc | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 444 |
| heredoc | old defect: GPT-6 4/5: here-document delimiter or owner | 36 |
| heredoc | new limit: a here-document operator that begins a statement (grammar) | 9 |
| heredoc | new limit: a here-document the grammar ends at a line bash does not read as its delimiter | 8 |
| heredoc | unresolved programs: an unquoted heredoc's escaped $ reaches the shell that reads it as an expansion (pivot D7) | 8 |
| heredoc | unresolved programs: eval words are read (pivot D4(c)) | 7 |
| heredoc | mechanism not isolated: the unresolved count differs in backquoted text with no lane involved | 5 |
| heredoc | new limit: text the grammar reports as an error (its subtree is skipped) | 3 |
| heredoc | old defect: eval words were not read (pivot D4(c)) | 3 |
| heredoc | old defect: oracle class 2: escaped nested backquotes | 3 |
| heredoc | remote lanes: unquoted ssh words are read (pivot D4(d)) | 3 |
| heredoc | static reading: the body of an unquoted heredoc holds an unterminated backquote, which bash rejects at run time | 3 |
| heredoc | static reading: the valid part of a script that bash rejects as a whole is read (pivot D2) | 2 |
| heredoc | neither reading equals the full run; static reading: the valid part of a script that bash rejects as a whole is read (pivot D2) | 1 |
| heredoc | old defect: GPT-6 1: a shell string that is not read by a shell (options before -c, -n) | 1 |
| heredoc | unresolved programs: a shell string operand is read (pivot D3/D4(a)) | 1 |

| corpus | class | differences |
| --- | --- | ---: |
| lanes | new limit: a here-document operator that begins a statement (grammar) | 176 |
| lanes | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 165 |
| lanes | old defect: GPT-6 4/5: here-document delimiter or owner | 58 |
| lanes | remote lanes: unquoted ssh words are read (pivot D4(d)) | 37 |
| lanes | old defect: GPT-6 1: a shell string that is not read by a shell (options before -c, -n) | 36 |
| lanes | old defect: eval words were not read (pivot D4(c)) | 21 |
| lanes | the new reading equals the run of the minimal witness; the full input's run does not reach that lane | 21 |
| lanes | unresolved programs: `time` after a wrapper that is an executable is unresolved (exec semantics) | 18 |
| lanes | static reading: the valid part of a script that bash rejects as a whole is read (pivot D2) | 13 |
| lanes | old defect: GPT-6 2: array elements read as commands | 12 |
| lanes | static reading: the body of an unquoted heredoc holds an unterminated backquote, which bash rejects at run time | 11 |
| lanes | neither reading equals the full run; static reading: the valid part of a script that bash rejects as a whole is read (pivot D2) | 10 |
| lanes | new limit: text the grammar reports as an error (its subtree is skipped) | 9 |
| lanes | neither reading equals the full run; new limit: a here-document operator that begins a statement (grammar) | 8 |
| lanes | old defect: oracle class 5: a builtin after a wrapper that is an executable read as a wrapper | 8 |
| lanes | neither reading equals the full run; new limit: text the grammar reports as an error (its subtree is skipped) | 5 |
| lanes | neither reading equals the full run; the new reading equals the run of the minimal witness; the full input's run does not reach that lane | 4 |
| lanes | old defect: oracle class 2: escaped nested backquotes | 4 |
| lanes | unresolved programs: a shell string operand is read (pivot D3/D4(a)) | 4 |
| lanes | old defect: GPT-6 3: double-quote backslashes | 3 |
| lanes | unresolved programs: `rtk proxy time` is unresolved (pivot D4(e)) | 3 |
| lanes | unresolved programs: a builtin after a wrapper that is an executable names no program (exec semantics) | 3 |
| lanes | unresolved programs: an unquoted heredoc's escaped $ reaches the shell that reads it as an expansion (pivot D7) | 3 |
| lanes | unresolved programs: eval words are read (pivot D4(c)) | 3 |
| lanes | mechanism not isolated: the unresolved count differs in backquoted text with no lane involved | 1 |
| lanes | neither reading equals the full run; new limit: a word joined to a redirection target by a line continuation | 1 |
| lanes | new limit: a word joined to a redirection target by a line continuation | 1 |
| lanes | old defect: Claude R4: parentheses outside command position | 1 |
| lanes | old defect: GPT-6 7: rtk proxy runs no shell | 1 |
| lanes | old defect: a `{` glued to a word is a word, not the start of a group | 1 |
| lanes | unresolved programs: a $ that ends a word expands nothing and is literal (old reading: an expansion) | 1 |

| corpus | class | differences |
| --- | --- | ---: |
| covering_current_tests | old defect: GPT-6 1: a shell string that is not read by a shell (options before -c, -n) | 15 |
| covering_current_tests | old defect: GPT-6 4/5: here-document delimiter or owner | 12 |
| covering_current_tests | old defect: oracle class 4: time before an assignment or a negation | 5 |
| covering_current_tests | old defect: oracle class 5: a builtin after a wrapper that is an executable read as a wrapper | 5 |
| covering_current_tests | old defect: eval words were not read (pivot D4(c)) | 4 |
| covering_current_tests | old defect: GPT-6 2: array elements read as commands | 3 |
| covering_current_tests | old defect: GPT-6 3: double-quote backslashes | 3 |
| covering_current_tests | old defect: oracle class 2: escaped nested backquotes | 3 |
| covering_current_tests | old defect: Claude R4: parentheses outside command position | 2 |
| covering_current_tests | old defect: GPT-6 6: arithmetic substitutions | 2 |
| covering_current_tests | old defect: GPT-6 7: rtk proxy runs no shell | 2 |
| covering_current_tests | old defect: oracle class 3: words after a redirection's target | 2 |
| covering_current_tests | unresolved programs: a proxied program named by an expansion (Claude R5) | 2 |
| covering_current_tests | old defect: a case pattern read as a command | 1 |
| covering_current_tests | old defect: a reserved word after a redirection or in a word position read as syntax | 1 |
| covering_current_tests | old defect: other old-code defect | 1 |
| covering_current_tests | remote lanes: unquoted ssh words are read (pivot D4(d)) | 1 |
| covering_current_tests | static reading: a function body counts where it is defined, called or not (documented) | 1 |
| covering_current_tests | unresolved programs: array elements and subscripted assignments are not commands (GPT-6 2) | 1 |
| covering_current_tests | unresolved programs: eval words are read (pivot D4(c)) | 1 |

| corpus | class | differences |
| --- | --- | ---: |
| covering_stage_a_339 | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 1 |

Unexplained: 0. Mechanism not isolated: 9. Other old-code defect: 1.

Real commands (by shape and argument):

| corpus | class | differences |
| --- | --- | ---: |
| real | unresolved programs: process substitution words (Claude R4 family) | 38 |
| real | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 29 |
| real | unresolved programs: a shell string operand is read (pivot D3/D4(a)) | 18 |
| real | unresolved programs: the old reading read a shell string that no shell runs (GPT-6 1) | 10 |
| real | unresolved programs: array elements and subscripted assignments are not commands (GPT-6 2) | 6 |
| real | old defect: GPT-6 1: a shell string that is not read by a shell | 4 |
| real | unresolved programs: `time` then an assignment (oracle class 4) | 2 |
| real | new limit: an unknown wrapper or launcher runs the lane | 1 |
| real | old defect: a case pattern read as a command | 1 |
| real | old defect: a process substitution's neighbours read as commands | 1 |
| real | old defect: a shell string with nested quoting was not read by the old reading (its lanes count; every side of && and || counts) | 1 |
| real | unresolved programs: a case pattern is not a command (the old reading counted it) | 1 |
| real | unresolved programs: eval words are read (pivot D4(c)) | 1 |

Unexplained: 0. Mechanism not isolated: 0. Other old-code defect: 0.

Real commands against the reading of `f1ed98ac`:

| corpus | class | differences |
| --- | --- | ---: |
| real_pre_ast | unresolved programs: a shell string operand is read (pivot D3/D4(a)) | 63 |
| real_pre_ast | unresolved programs: process substitution words (Claude R4 family) | 38 |
| real_pre_ast | unresolved programs: ill-formed text is skipped (pivot D2, parse_errors) | 30 |
| real_pre_ast | unresolved programs: eval words are read (pivot D4(c)) | 9 |
| real_pre_ast | unresolved programs: the old reading read a shell string that no shell runs (GPT-6 1) | 7 |
| real_pre_ast | unresolved programs: array elements and subscripted assignments are not commands (GPT-6 2) | 6 |
| real_pre_ast | old defect: GPT-6 1: a shell string that is not read by a shell | 4 |
| real_pre_ast | unresolved programs: `time` then an assignment (oracle class 4) | 2 |
| real_pre_ast | new limit: an unknown wrapper or launcher runs the lane | 1 |
| real_pre_ast | old defect: a case pattern read as a command | 1 |
| real_pre_ast | old defect: a process substitution's neighbours read as commands | 1 |
| real_pre_ast | old defect: a shell string with nested quoting was not read by the old reading (its lanes count; every side of && and || counts) | 1 |
| real_pre_ast | unresolved programs: a case pattern is not a command (the old reading counted it) | 1 |

### The oracle over fresh seeds

The committed test runs 163 of 163 probes, 28 of 28 recovery probes and 456 of 456 and 463 of 463 generated commands. The same generators over other seeds,
each command run under real bash (a first-run difference that a rerun explains is a race of the run: a pipe whose right side never reads can kill its
writer with SIGPIPE), and the extended generator against the kernel before this stage's repairs (seeds 100 to 579):

| generator | seeds | commands | lane runs | first-run differences | pipe races | lane differences | parse error, lanes agree |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| base | 7000 to 7479 | 23,894 | 32,399 | 1 | 0 | 0 | 1 |
| ext | 8000 to 8479 | 26,767 | 36,765 | 2 | 1 | 0 | 1 |
| ext_before_the_repairs | 100 to 579 | 26,864 | 36,801 | 2,527 | 0 | 2,527 | 0 |

`parse error, lanes agree` counts commands whose lanes equal the run but whose tree has an ERROR (a shell heredoc whose first body line begins with a
backslash and continues with a pipe): `parse_errors` counts those calls although the reading is right.

### M4 is unchanged by the lane layer

`executedText` (plain and inline-HTTP), `fetchKind` and the complete `m4` object of the kernel before the walker (`f1ed98ac`) and the kernel under test:

| corpus | analysed | identical | different | throws (before, after) |
| --- | ---: | ---: | ---: | --- |
| soup-432 | 4,397 | 4,397 | 0 | 0, 0 |
| heredoc-434 | 4,656 | 4,656 | 0 | 0, 0 |
| lanes-435 | 4,740 | 4,740 | 0 | 0, 0 |
| covering_current_tests | 728 | 728 | 0 | 0, 0 |
| covering_stage_a_339 | 339 | 339 | 0 | 0, 0 |
| real | 136,361 | 136,361 | 0 | 0, 0 |

Commit `9a4e9f97` (an earlier commit of this unit, no longer in the branch's history) claimed "0 differences in executedText and fetchKind over 24,489 inputs" and its
deviation list said 24,495; the harness output was not retained, so the two counts cannot be reconciled. The claim is re-run here on the same corpora with
the kernels before and after that commit (`11d7e0bd` and `9a4e9f97`), comparing `executedText` and `fetchKind`:

| corpus | analysed | identical | different |
| --- | ---: | ---: | ---: |
| soup-432 | 4,397 | 4,397 | 0 |
| heredoc-434 | 4,656 | 4,656 | 0 |
| lanes-435 | 4,740 | 4,740 | 0 |
| covering_current_tests | 728 | 728 | 0 |
| covering_stage_a_339 | 339 | 339 | 0 |
| real | 136,361 | 136,361 | 0 |

### Shapes in this host's real commands

Commands with each shape (counts of commands, not occurrences):

| shape | commands |
| --- | ---: |
| distinct commands | 136,361 |
| a parse error (an ERROR node) | 247 |
| a lane invocation | 6,527 |
| an unresolved program | 4,574 |
| an unresolved program and a lane word | 562 |
| a command named `!` | 0 |
| a backquoted body with an escaped `$`, backquote or backslash | 0 |
| words folded into a redirection's target | 500 |
|   of which a lane word among them | 1 |
| `time` before an assignment or `!` | 12 |
| a here-document operator | 15,128 |
| a heredoc the grammar ends at a line that only begins with its delimiter | 2 |
| a heredoc with no delimiter line | 0 |
| a here-document operator that begins a statement | 0 |
| two here-document operators on a line and a tree error | 2 |
| a word the grammar cut in two | 4,837 |
|   of which a lane word follows the cut | 37 |
| a shell -c whose command string is `$(cat <<DELIM ...)` | 5 |

Round 2 rebuilt this corpus (below) and reproduced every count of this table exactly; the counts of `shapes` that it added (the first overturn condition, the largest commands) are in that section.

### What a shell call costs

Milliseconds per call over this host's real commands, parser loaded:

| reading | calls | total s | mean ms | p50 ms | p99 ms | max ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| executedText plain | 136,361 | 9.7 | 0.071 | 0.055 | 0.29 | 2.2 |
| executedText inlineHttp | 136,361 | 12.66 | 0.093 | 0.064 | 0.5 | 6.3 |
| fetchKind | 136,361 | 11.06 | 0.081 | 0.063 | 0.32 | 2.6 |
| commandInvocations | 136,361 | 17.36 | 0.127 | 0.1 | 0.51 | 12.3 |
| measureTranscript (one Bash call) | 136,361 | 43.91 | 0.322 | 0.261 | 1.21 | 10.9 |

### Not-executed and interrupted calls

A count-only recount of 5,074 Claude Code transcript files (the client's project transcript store on this host), on the day of the run. It grows with every session, so a later run
gives larger numbers:

| shape | rows |
| --- | ---: |
| toolDenialKind `permission-rule` | 817 |
| toolDenialKind `user-rejected` | 50 |
| toolDenialKind `cancelled` | 1 |
| toolDenialKind `automode-unavailable` | 1 |
| content opens `The user doesn't want to proceed` | 43 |
| content opens the auto-mode classifier text | 1 |
| content opens `This agent is isolated` (no denial kind, all Bash, all is_error) | 209 |
| Bash result with `toolUseResult.interrupted` true | 0 |

## Round 2: the repair of the review of head `33dcfd24`

The stage's head was reviewed independently and verified. The review found one medium defect (the decision record's first overturn condition
was stated, not measured: `counts.json` held 247 tree errors and 6,527 lane invocations and nothing that combined them) and listed what it
could not run. The repair round measured the condition, found and fixed a quadratic walk over the tree that the review had not seen, and ran again
what a run could close. What was and was not run again:

| run again | not run again |
| --- | --- |
| the shape scan (`shapes`), now with the first overturn condition; the whole-record identity check (`lanes_identity`); the scaling (`scaling`); the differential totals (`differential_rerun`); the committed oracle module (163 of 163 probes, 28 of 28 recovery probes, 456 of 456 and 463 of 463 generated commands: `python3 -m unittest tests.test_command_position_oracle`); the M4 fixtures of the decision (D7, R1, R3, heredoc expansion, backquote anchor: 75 commands) under real bash 5.2.21 and dash with a stub `curl`; the parser pins against the npm registry, the GitHub tag refs and the installed files | the oracle over fresh seeds (50,661 commands) and the reduction of every difference to a witness with its classification (round 1's numbers stand; they describe the kernel `a9126a77fd7f`, and the identity check below shows the kernel of round 2 reads every input alike); the timing and the states (the transcript store has grown since); the covering lists (`capture-covering.py` would pick up the new fixtures) |

### The corpus

The real commands of round 1 were extracted before `real-commands.mjs` had an option for a cutoff, so the cutoff was not recorded. It is
reconstructed: `--until 2026-09-29T07:08:07Z` gives the same number of distinct shell texts (136,361) and of those with a heredoc operator
(15,128), and `shape-counts.mjs` on it reproduces all 18 counts of round 1 exactly (a parse error in 247, a lane invocation in 6,527, and so on). Every instant
from 07:08:06.392Z to just before 07:08:08.754Z gives the same texts. The store has since grown to 146,905 distinct shell texts. The rebuilt corpus is not in the
repository (it holds command text); this host's transcripts rebuild it.

### The first overturn condition

Commands with each shape (a command counts once). The tree position of a lane word is read from the tree of the text as given, before the reading's heredoc repairs.

| measure | commands |
| --- | ---: |
| the reading reads a lane invocation (the denominator: the stricter of the two counts) | 6,527 |
| a lane word anywhere in the text (found without the parser) | 14,210 |
| grammar limit: a parse error the reading met, or a heredoc the grammar ended early | 247 |
| grammar limit, the error only in a script the reading read again | 11 |
| grammar limit and a lane word (the screen) | 31 |
| grammar limit, a lane read (counts toward the bound) | 4 |
| grammar limit, a lane word and no lane read | 27 |
| ... the lane word follows plain words (an argument) | 13 |
| ... a slot the tree puts in data (comment, heredoc body, string, assignment value) | 13 |
| ... a slot anywhere else, an ERROR node included (counts toward the bound) | 1 |
| ... unplaced: the error is only in a script read again (counts toward the bound) | 0 |
| a heredoc ended early with a lane word (counts toward the bound) | 1 |
| the scanner reading of `0c421c66` reads a lane the tree reading lacks, among the grammar limits | 0 |
| **upper bound of what a grammar limit can lose or invent (the union of those that count)** | 5 |

The bound is 5 of 6,527 lane-bearing commands (0.077%) against a threshold of 7 commands (0.1%): the
condition is not met, by 2 commands. The screen that counts every lane word among the grammar limits is 31 commands
(0.475%, above the threshold), and is not the criterion: it counts data. The bound does not cover a misparse with no ERROR node
(the oracle and the differential measure those), the classification of the 27 unread commands is an argument (real commands are never run), and the repaired shapes
(a word cut after an assignment, words folded into a redirection, `time` before an assignment or `!`; the table of shapes below) are not limits because each repair is gated
by real bash: counted as limits, 37 and 1 of them hold a lane word and the verdict would flip.

### Whole lane records of the two kernels

`commandInvocations` records and `cli_lanes` objects of the kernel of round 1 (sha256 prefix `a9126a77fd7f`) and of round 2 (`119ce9764447`), compared input by input
(`m4-identity.mjs --fields lanes`; every input, none filtered by `bash -n`). Total analysed: 217,428.

| corpus | inputs | identical | different | throws (before, after) |
| --- | ---: | ---: | ---: | --- |
| real | 136,361 | 136,361 | 0 | 0, 0 |
| soup | 40,000 | 40,000 | 0 | 0, 0 |
| heredoc | 20,000 | 20,000 | 0 | 0, 0 |
| lanes | 20,000 | 20,000 | 0 | 0, 0 |
| covering_current_tests | 728 | 728 | 0 | 0, 0 |
| covering_stage_a_339 | 339 | 339 | 0 | 0, 0 |

### The differential, run again

`differential.mjs` (no reduction) of the scanner reading of `0c421c66` against the kernel of round 2 on the same corpora as round 1, compared with round 1's record
(`distinct_witnesses` needs a reduction and is not compared):

| corpus | inputs | bash-valid | same | different | equal to round 1 |
| --- | ---: | ---: | ---: | ---: | --- |
| real | 136,361 | not checked | 136,248 | 113 | yes |
| soup | 40,000 | 4,397 | 4,104 | 293 | yes |
| heredoc | 20,000 | 4,656 | 4,119 | 537 | yes |
| lanes | 20,000 | 4,740 | 4,098 | 642 | yes |
| covering_current_tests | 728 | not checked | 661 | 67 | yes |
| covering_stage_a_339 | 339 | not checked | 338 | 1 | yes |

### Time by size

Best of three runs in milliseconds at n = 2,000, 4,000, 8,000, 16,000, 32,000, a text of about 2n characters (a run over 10 s ends the row), and the largest growth from one size to the next where the
earlier time is above 5 ms (about 2 is linear, about 4 quadratic). The parse column is the parse alone (the tree is built and freed, nothing is read).

| shape | chars at n = 32,000 | round 1 kernel, ms | growth | round 2 kernel, ms | growth | parse alone (round 2), ms | growth |
| --- | ---: | --- | ---: | --- | ---: | --- | ---: |
| `unclosed_double_paren` | 64,003 | 33.5 / 123 / 483 / 1888.2 / 7442.8 | 3.94 | 5.3 / 8 / 15.8 / 27.4 / 62.7 | 2.29 | 0.9 / 1.7 / 3.3 / 6.7 / 13.6 | 2.03 |
| `unclosed_dollar_paren` | 64,003 | 8.5 / 31.3 / 119.6 / 467.9 / 1875.5 | 4.01 | 2.7 / 5.2 / 8.3 / 14.2 / 33.2 | 2.34 | 0.6 / 1.2 / 2.4 / 4.8 / 9.7 | - |
| `unclosed_dq_dollar_paren` | 64,005 | 14.3 / 53.9 / 213.2 / 834 / 3366.8 | 4.04 | 2.6 / 4.4 / 8.9 / 17.6 / 32.7 | 1.98 | 0.7 / 1.4 / 2.8 / 5.6 / 11.1 | 1.98 |
| `unclosed_arith` | 64,003 | 5.2 / 18.5 / 69.7 / 270.5 / 1067.2 | 3.95 | 1.4 / 2.7 / 5.4 / 11.2 / 22.6 | 2.07 | 0.6 / 1.2 / 2.5 / 5 / 9.9 | - |
| `backquotes` | 64,000 | 31.7 / 119.9 / 481.8 / 1886.7 / 7556 | 4.02 | 2.9 / 5.8 / 12 / 24 / 48.2 | 2.07 | 0.9 / 1.8 / 3.6 / 7.2 / 14.6 | 2.03 |
| `unclosed_brace` | 64,000 | 8.6 / 31.6 / 121.3 / 485.9 / 1885.1 | 4.01 | 1.7 / 3.4 / 6.9 / 14 / 28.9 | 2.06 | 0.7 / 1.4 / 2.8 / 5.8 / 11.5 | 1.98 |
| `unclosed_if` | 64,009 | 5 / 16.5 / 59.5 / 222.9 / 876.8 | 3.93 | 2.2 / 4.4 / 8.6 / 17.2 / 35.9 | 2.09 | 1 / 2 / 3.9 / 7.8 / 15.8 | 2.03 |
| `unclosed_case` | 64,012 | 5.4 / 19.5 / 73.4 / 283.7 / 1119.1 | 3.94 | 1.4 / 3 / 5.9 / 12.5 / 23.9 | 2.12 | 0.7 / 1.4 / 2.7 / 5.4 / 10.7 | 1.98 |
| `comments` | 64,000 | 2.4 / 8.2 / 29.8 / 113.6 / 443.9 | 3.91 | 0.8 / 1.5 / 3 / 6 / 12.7 | 2.12 | 0.4 / 0.7 / 1.4 / 2.9 / 6.1 | - |
| `words` | 64,002 | 6.8 / 12.9 / 25.4 / 51.1 / 103.6 | 2.03 | 5.8 / 11.4 / 22.6 / 46 / 91.5 | 2.04 | 2.2 / 4.2 / 8.7 / 17.2 / 34.6 | 2.01 |
| `semicolons` | 64,002 | 7 / 14.6 / 28.1 / 56.2 / 119.4 | 2.12 | 7.6 / 15.5 / 29.9 / 62.5 / 128.2 | 2.09 | 2.1 / 4.4 / 8.5 / 17.1 / 35.6 | 2.08 |
| `and_list` | 64,012 | 2.4 / 4.5 / 9.3 / 18.4 / 35.2 | 1.98 | 2.4 / 4.8 / 9.9 / 19.5 / 38.3 | 1.97 | 0.7 / 1.4 / 2.8 / 5.6 / 11.3 | 2.02 |
| `dq_substitutions` | 64,000 | 9.1 / 8.7 / 17.5 / 34.6 / 71.5 | 2.07 | 4.9 / 8.5 / 17 / 35.4 / 72 | 2.08 | 1.5 / 2.7 / 5.4 / 11.2 / 22.7 | 2.07 |
| `heredocs` | 64,008 | 3.7 / 6.8 / 13.8 / 27.2 / 50.9 | 2.03 | 4.5 / 8.2 / 16.6 / 32.9 / 64.7 | 2.02 | 0.9 / 1.7 / 3.4 / 7 / 14 | 2 |
| `shell_heredocs` | 64,008 | 4.8 / 8.7 / 15.5 / 30.6 / 57.8 | 1.97 | 9.6 / 8.7 / 17.3 / 34.3 / 67.8 | 1.99 | 0.6 / 1.1 / 2.2 / 4.6 / 9.3 | - |
| `shell_strings` | 64,008 | 2.6 / 5.2 / 10.7 / 21.3 / 45.5 | 2.14 | 2.4 / 4.7 / 9.5 / 19.4 / 40.1 | 2.07 | 0.9 / 1.8 / 3.6 / 7.3 / 15 | 2.05 |
| `pipes` | 64,003 | 11 / 22.9 / 46 / 96.2 / 198.8 | 2.09 | 11.2 / 23.3 / 46.9 / 95.4 / 197.5 | 2.08 | 7 / 14.8 / 29.5 / 60.1 / 121.8 | 2.11 |
| `redirs` | 64,017 | 4.7 / 8.4 / 16.7 / 33.5 / 66.5 | 2.01 | 4.5 / 8.5 / 17.3 / 35.4 / 70.7 | 2.05 | 0.8 / 1.7 / 3.5 / 7 / 14 | 2 |
| `assignments` | 64,003 | 5.9 / 11.3 / 23.9 / 49 / 99.2 | 2.12 | 5.5 / 10.8 / 22.3 / 46.2 / 94.7 | 2.07 | 2.6 / 5.5 / 10.6 / 21.5 / 46.2 | 2.15 |
| `unclosed_array` | 64,000 | 62.9 / 223.4 / 827.2 / 3233.2 / 12718.5 | 3.93 | 63.2 / 221.8 / 828.2 / 3199.8 / 12573.8 | 3.93 | 61.2 / 215.5 / 812.4 / 3166.4 / 12459.7 | 3.93 |
| `heredoc_operators` | 64,000 | 92.2 / 361.4 / 1439 / 5837.2 / 22971.2 | 4.06 | 91.3 / 359.6 / 1431.7 / 5725.8 / 23207.1 | 4.05 | 90.6 / 361.1 / 1427.3 / 5729.2 / 22919.7 | 4.01 |

Reading the table. The kernel of round 1 was quadratic on the 9 shapes in which the tree has one wide node (a flat run of unclosed constructs or of comments: growth 3.91 to 4.04), although
the parse of each is linear: `node.child(i)` and `node.fieldNameForChild(i)` cost O(i) per call in web-tree-sitter 0.27.0 (`lib/src/node.c`), and `node.parent` costs O(depth). GPT-6 finding 9 (`'(('.repeat(n) + 'qmd'`)
was therefore fixed for the M4 scanners only: 64,003 characters took 7.4 s. The kernel of round 2 reads a node of more than 16 children with a cursor (a step is O(1)) and carries the
parent's type: the same text takes 63 ms, and every shape but two grows by at most 2.34 per doubling. `test-child-usage.mjs` checks 9 of them at n = 8,000 to 64,000. Two shapes stay quadratic in both
kernels and in the parse alone (growth 3.93 and 4.01): a run of unclosed array assignments (`a=( `: 12.6 s at 64,000 characters) and a run of heredoc operators with no
delimiter (`<<`: 23.2 s at 64,000). That is tree-sitter-bash's own parse, which no reading changes. This host's largest real command has 49,096 characters, at most
71 heredoc operators and 12 array openers, and round 1's timing found none slower than 12.3 ms. A parse budget that marks such a text unresolved is a follow-up outside this change.
On 30,000 real commands read through both kernels the round-2 kernel took 1.03 times as long as round 1's (best of three; measured in the repair round, not recorded in `counts.json`).

## Limits of this evidence

- The real commands are one host's Bash tool calls (2026-09 transcripts), deduplicated; they are not a sample of any population.
- The seeded corpora are random token soups; their differences show which mechanisms exist, not how often they occur in practice.
- The run of real bash is GNU bash 5.2.21 under stub executables: it shows which lane executables ran, not what they did. `sudo`, `ssh`, `curl` and `wget`
  do not exist there, so shapes that need them are left out of the generators, not out of the claim.
- Covering commands longer than 5,000 characters (the inputs of the linear-time tests, up to 768,000 characters) are left out of the comparison: the old
  scanner is quadratic on them and takes minutes. The new reading's time on them is the subject of `test-child-usage.mjs`.
- The unresolved-program and remote-lane counts have no oracle.
- Round 2: the cutoff of the real corpus is reconstructed, not recorded (above). The overturn bound comes from the tree's own limits and a text screen, on one host's commands;
  the margin is 2 commands. The scaling numbers are this host's (best of three, one machine) and vary by run; a continuous-integration runner was not measured, so the suite
  checks the growth per doubling and an absolute bound of 1.5 s at 64,000 for shapes that take under 0.1 s here.
