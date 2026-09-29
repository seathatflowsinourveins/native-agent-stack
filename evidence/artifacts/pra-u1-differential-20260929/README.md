# Command-position differential (U1 pivot, 2026-09-29)

Counts only. No command text, transcript id, host name, URL or path is committed here: the inputs of the differential are this host's
own commands (private, mode 0600, in a scratch directory outside every checkout) and generated shell texts, and every table below is a number.
`counts.json` is the machine-readable record of the run; the tables are rendered from it.

Kernel under test: `examples/claude-native/workflows/child-usage.mjs`, sha256 prefix `a9126a77fd7f` (the full value is in `counts.json`),
with the verified tree-sitter-bash 0.25.1 install of `shell-parser.pin.json`.

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
| `m4-identity.mjs` | `executedText` (both modes), `fetchKind` and the complete `m4` object of two kernels on a corpus |
| `oracle-scale.py` | the oracle's generators over fresh seeds against real bash |
| `repeat-oracle.sh` | repeats the committed oracle module N times (stability of the fixed seeds) |
| `shape-counts.mjs` | how many real commands hold each shape the reading has to know about |
| `timing.mjs` | the cost of each reading of a call |
| `states-count.mjs` | the not-executed and interrupted shapes in Claude Code transcripts |
| `real-commands.mjs` | extracts the private corpus of real commands from the local transcripts |
| `capture-covering.py` | the shell texts the covering test tables feed the kernel |

Run it (the parser and bash must be installed; the work directory must stay outside every checkout because it holds command text):

```sh
node evidence/artifacts/pra-u1-differential-20260929/real-commands.mjs "$WORK/real.json"
python3 evidence/artifacts/pra-u1-differential-20260929/capture-covering.py --repo . --out "$WORK/covering.json"
python3 evidence/artifacts/pra-u1-differential-20260929/run-differential.py --repo . --old <0c421c66 kernel> --pre-ast <f1ed98ac kernel> \
  --work "$WORK" --real "$WORK/real.json" --covering current_tests="$WORK/covering.json" \
  --pre-repair-kernel <2bad7320 kernel> --marks-before <11d7e0bd kernel> --marks-after <9a4e9f97 kernel>
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

## Limits of this evidence

- The real commands are one host's Bash tool calls (2026-09 transcripts), deduplicated; they are not a sample of any population.
- The seeded corpora are random token soups; their differences show which mechanisms exist, not how often they occur in practice.
- The run of real bash is GNU bash 5.2.21 under stub executables: it shows which lane executables ran, not what they did. `sudo`, `ssh`, `curl` and `wget`
  do not exist there, so shapes that need them are left out of the generators, not out of the claim.
- Covering commands longer than 5,000 characters (the inputs of the linear-time tests, up to 768,000 characters) are left out of the comparison: the old
  scanner is quadratic on them and takes minutes. The new reading's time on them is the subject of `test-child-usage.mjs`.
- The unresolved-program and remote-lane counts have no oracle.
