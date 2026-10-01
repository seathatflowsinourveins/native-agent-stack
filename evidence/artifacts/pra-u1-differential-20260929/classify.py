"""Classify the differences of differential.mjs (counts only).

    python3 classify.py --repo <checkout> --diffs <name>=<file.jsonl> [<name>=<file.jsonl> ...] [--no-run <name> ...] [--out <counts.json>]

Each row of a diffs file is one input whose old and new readings differ, with a minimal witness of the same lane-difference signature
(differential.mjs --reduce or --reduce-text). Who is right is decided on the INPUT ITSELF, not on its witness:

  run corpora (the seeded fuzz inputs, the covering commands): the input runs under REAL bash with logging stub executables (the oracle of
      tests/test_command_position_oracle.py: env -i, a PATH of logging stubs, a temporary HOME, a 5 second limit, three attempts when a pipe
      race or a timeout leaves no answer). The reading equal to the run is right:
        old defect     the run equals the new reading and not the old one
        new limit      the run equals the old reading and not the new one (a shape the grammar or the static reading does not follow)
        neither        neither equals the run: a static reading a run cannot show (control flow, a script that expands)
      The witness then names the mechanism (which review finding the old defect repeats, which grammar limit the new one is).
  --no-run corpora (real commands, which must not be run): lane differences are classified by the mechanism of the witness alone, an
      argument and not a run; the number of such classifications is reported apart.

Where only the number of remote lanes or unresolved programs differs (no run can show either), the class is the mechanism: a parse error
(ERROR subtrees are skipped), an unquoted ssh or eval word list, a shell string operand, `rtk proxy time`, an array, a case pattern.
The row count of each class is reported; `unexplained` must be 0.
"""
import argparse
import collections
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--diffs", nargs="+", required=True)
parser.add_argument("--no-run", nargs="*", default=[])
parser.add_argument("--out")
parser.add_argument("--samples", type=int, default=0, help="print this many witnesses of each catch-all class to stderr (a check for the reader; never for --no-run corpora)")
args = parser.parse_args()
sys.dont_write_bytecode = True
sys.path.insert(0, args.repo)
from tests import test_command_position_oracle as oracle  # noqa: E402

rows = []
for spec in args.diffs:
    name, path = spec.split("=", 1)
    for line in open(path):
        row = json.loads(line)
        row["corpus"] = name
        row.setdefault("witness", row["text"])
        row.setdefault("witness_old", row["old"])
        row.setdefault("witness_new", row["new"])
        row.setdefault("witness_error", row["error"])
        row.setdefault("witness_new_programs", [])
        rows.append(row)

tmp = tempfile.TemporaryDirectory(prefix="classify-")
home = Path(tmp.name)
bin_dir = oracle.make_stubs(home)


def normal(tokens):
    """The tokens a stub logs: rtk logs `rtk_proxy` with no help mark."""
    return collections.Counter("rtk_proxy" if t == "rtk_proxy!" else t for t in tokens)


truth = {}


def run(text):
    if text not in truth:
        truth[text] = None
        for _ in range(3):
            ran = oracle.run_real([text], bin_dir, home)[0]
            if ran is not None:
                truth[text] = normal(ran.elements())
                break
    return truth[text]


SHELL_STRING = re.compile(r"(?:^|[\s;&|(){}`\"'/])(?:ba|da|z|k|)sh\s+-[A-Za-z]*c(?=[\s'\"])")
LEADING_HEREDOC = re.compile(r"(?:^|[\n;&|({])\s*[0-9]*<<-?\s*[A-Za-z'\"\\]")
INPUT_REDIRECT = re.compile(r"(?<![<0-9&])<(?![<(&])")
UNKNOWN_WRAPPER = re.compile(r"\b(?:setsid|bwrap|flock|ionice|taskset|unshare|watch|parallel|find|doas|su|script|systemd-run|chroot)\b")
CASE = re.compile(r"\bcase\b.*\bin\b", re.S)
SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}


def old_defect(w):
    """Which review finding an old-code defect repeats, by the shape of the witness."""
    if re.search(r"\beval\b", w):
        return "eval words were not read (pivot D4(c))"
    if SHELL_STRING.search(w) or re.search(r"(?:ba|da|z|k|)sh\s+[-+]\S*(?:\s+\S+)?\s+-[A-Za-z]*c\b", w):
        return "GPT-6 1: a shell string that is not read by a shell (options before -c, -n)"
    if "=(" in w:
        return "GPT-6 2: array elements read as commands"
    if '"' in w and "\\" in w:
        return "GPT-6 3: double-quote backslashes"
    if "<<" in w:
        return "GPT-6 4/5: here-document delimiter or owner"
    if "$((" in w:
        return "GPT-6 6: arithmetic substitutions"
    if re.search(r"rtk proxy\s+(?:command|exec|time)\b", w):
        return "GPT-6 7: rtk proxy runs no shell"
    if re.search(r"\b(?:env|nice|nohup|stdbuf|timeout|xargs|sudo|exec)\b[^;&|\n]*\b(?:command|exec|eval)\b", w):
        return "oracle class 5: a builtin after a wrapper that is an executable read as a wrapper"
    if re.search(r"\(\)|function |\[\[.*\(", w):
        return "Claude R4: parentheses outside command position"
    if re.search(r"(?:^|[\n;&|({])\s*!\s+!", w):
        return "oracle class 1: a doubled negation"
    if "`" in w:
        return "oracle class 2: escaped nested backquotes"
    if re.search(r"\btime\b", w):
        return "oracle class 4: time before an assignment or a negation"
    if re.search(r"[0-9]?[<>]&?[^\s]*\s+\S", w):
        return "oracle class 3: words after a redirection's target"
    if CASE.search(w):
        return "a case pattern read as a command"
    if "<(" in w:
        return "a process substitution's neighbours read as commands"
    if re.match(r"\s*(?:[0-9]*[<>][^\s]*\s+)?(?:if|then|do|elif|while|until)\b", w):
        return "a reserved word after a redirection or in a word position read as syntax"
    if re.search(r"(?:^|[\s;&|(])\{[^\s{}]", w):
        return "a `{` glued to a word is a word, not the start of a group"
    return "other old-code defect"


def by_mechanism(row):
    """Differences no run can show: the number of remote lanes and of unresolved programs."""
    w, old, new = row["witness"], row["witness_old"], row["witness_new"]
    if old["remote"] != new["remote"]:
        return "remote lanes: unquoted ssh words are read (pivot D4(d))" if "ssh" in w else "unexplained"
    if row["witness_error"]:
        return "unresolved programs: ill-formed text is skipped (pivot D2, parse_errors)"
    if re.search(r"\beval\b", w):
        return "unresolved programs: eval words are read (pivot D4(c))"
    if SHELL_STRING.search(w):
        if SHELLS & set(row["witness_new_programs"]):
            return "unresolved programs: a shell string operand is read (pivot D3/D4(a))"
        return "unresolved programs: the old reading read a shell string that no shell runs (GPT-6 1)"
    if re.search(r"rtk proxy\s+time\b", w):
        return "unresolved programs: `rtk proxy time` is unresolved (pivot D4(e))"
    if re.search(r"\b(?:env|nice|nohup|stdbuf|timeout|xargs|sudo|exec)\b[^;&|\n]*\btime\b", w):
        return "unresolved programs: `time` after a wrapper that is an executable is unresolved (exec semantics)"
    if re.search(r"\b(?:env|nice|nohup|stdbuf|timeout|xargs|sudo|exec)\b[^;&|\n]*\b(?:command|exec|eval)\b", w):
        return "unresolved programs: a builtin after a wrapper that is an executable names no program (exec semantics)"
    if re.search(r"rtk\s+(?:-\S+\s+)*proxy\s+[\"']?[$`]", w):
        return "unresolved programs: a proxied program named by an expansion (Claude R5)"
    if re.search(r"(?:^|[\s;&|(){}])(?:ba|da|z|k|)sh\s*<<-?\s*[A-Za-z_][A-Za-z_0-9]*\n[^\n]*\\\$", w):
        return "unresolved programs: an unquoted heredoc's escaped $ reaches the shell that reads it as an expansion (pivot D7)"
    if re.search(r"\\\\\$(?![A-Za-z_{(0-9?@*#!$-])", w):
        return "unresolved programs: a $ that ends a word expands nothing and is literal (old reading: an expansion)"
    if "=(" in w or "+=(" in w or re.search(r"[A-Za-z_][A-Za-z0-9_]*\[.*\]\+?=", w):
        return "unresolved programs: array elements and subscripted assignments are not commands (GPT-6 2)"
    if CASE.search(w):
        return "unresolved programs: a case pattern is not a command (the old reading counted it)"
    if "<(" in w:
        return "unresolved programs: process substitution words (Claude R4 family)"
    if re.search(r"\btime\s+(?:-p\s+)?(?:!\s+)?[A-Za-z_][A-Za-z0-9_]*=", w):
        return "unresolved programs: `time` then an assignment (oracle class 4)"
    if "`" in w:
        return "mechanism not isolated: the unresolved count differs in backquoted text with no lane involved"
    return "unexplained"


DELIMITER = re.compile(r"<<(-?)[ \t]*(?:'([^']*)'|\"([^\"]*)\"|\\?([A-Za-z0-9_][A-Za-z0-9_-]*))")


def early_heredoc_end(w):
    """A body line the grammar takes for the delimiter and bash does not: a line that only begins with it, or an indented one for a plain `<<`."""
    m = DELIMITER.search(w)
    if not m:
        return False
    strip, delimiter = m.group(1) == "-", m.group(2) or m.group(3) or m.group(4)
    for line in w[m.end():].split("\n")[1:]:
        bash_ends = (line.lstrip("\t") if strip else line) == delimiter
        grammar_ends = line.strip().startswith(delimiter)
        if bash_ends:
            return False
        if grammar_ends:
            return True
    return False


def odd_backquotes_in_unquoted_body(w):
    """An unquoted here-document delimiter whose body holds an unterminated backquote: bash expands the body first and rejects it at run time."""
    m = re.search(r"<<-?[ \t]*([A-Za-z0-9_][A-Za-z0-9_-]*)[ \t]*\n", w)
    if not m:
        return False
    count, backslashes = 0, 0
    for ch in w[m.end():]:
        if ch == "\\":
            backslashes += 1
            continue
        if ch == "`" and backslashes % 2 == 0:
            count += 1
        backslashes = 0
    return count % 2 == 1


def missing_reason(view):
    """Why the new reading misses a lane that the run ran, by the shape of a witness (a heuristic label)."""
    w = view["witness"]
    if LEADING_HEREDOC.search(w):
        return "new limit: a here-document operator that begins a statement (grammar)"
    if early_heredoc_end(w):
        return "new limit: a here-document the grammar ends at a line bash does not read as its delimiter"
    if view["witness_error"]:
        return "new limit: text the grammar reports as an error (its subtree is skipped)"
    if "\\\n" in w:
        return "new limit: a word joined to a redirection target by a line continuation"
    if UNKNOWN_WRAPPER.search(w):
        return "new limit: an unknown wrapper or launcher runs the lane"
    if INPUT_REDIRECT.search(w):
        return "static reading: a command whose input redirection fails is not run"
    return None


FUNCTION = re.compile(r"\bfunction\b|\(\)\s*[({]")


def extra_reason(view, witness_ran):
    """Why the new reading counts a lane that the run did not run. Tried in this order: a function definition (its body counts where it is defined:
    documented); a here-document operator that begins a statement or a heredoc the grammar ends early (the grammar reads body text as commands); an
    unquoted heredoc body with an unterminated backquote (bash rejects the expansion at run time); a word joined to a redirection target by a line
    continuation; a text with an ERROR (the valid part of a script bash rejects as a whole is read: pivot D2); a witness whose own run equals the new
    reading (the reading is right on the smallest text that shows the difference; the full input's run stops before that lane)."""
    w = view["witness"]
    if FUNCTION.search(w):
        return "static reading: a function body counts where it is defined, called or not (documented)"
    if LEADING_HEREDOC.search(w):
        return "new limit: a here-document operator that begins a statement (grammar)"
    if early_heredoc_end(w):
        return "new limit: a here-document the grammar ends at a line bash does not read as its delimiter"
    if odd_backquotes_in_unquoted_body(w):
        return "static reading: the body of an unquoted heredoc holds an unterminated backquote, which bash rejects at run time"
    if "\\\n" in w:
        return "new limit: a word joined to a redirection target by a line continuation"
    if view["witness_error"]:
        return "static reading: the valid part of a script that bash rejects as a whole is read (pivot D2)"
    if witness_ran is not None and witness_ran == normal(view["witness_new"]["lanes"]):
        return "the new reading equals the run of the minimal witness; the full input's run does not reach that lane"
    return None


def ddmin(units, keep):
    n = 2
    while len(units) >= 2:
        size = -(-len(units) // n)
        reduced = False
        for start in range(0, len(units), size):
            rest = units[:start] + units[start + size:]
            if rest and keep("".join(rest)):
                units, n, reduced = rest, max(n - 1, 2), True
                break
        if not reduced:
            if n >= len(units):
                break
            n = min(len(units), n * 2)
    return units


def reduce_against_run(text, ran):
    """A second minimal witness for the rows the first one does not explain: the smallest text (lines, then words) that is accepted by bash -n and
    keeps the SAME discrepancy between the new reading and the run (the same lanes missed and the same lanes over-counted)."""
    def signature(tokens, ran_now):
        new_now = normal(tokens)
        return (sorted((ran_now - new_now).elements()), sorted((new_now - ran_now).elements()))
    want = signature(oracle.read_lanes([text])[0]["tokens"], ran)

    def keep(candidate):
        if subprocess.run(["bash", "-n"], input=candidate, text=True, capture_output=True).returncode:
            return False
        ran_now = oracle.run_real([candidate], bin_dir, home)[0]
        if ran_now is None:
            return False
        got = oracle.read_lanes([candidate])[0]
        return signature(got["tokens"], normal(ran_now.elements())) == want
    lines = ddmin(re.findall(r"[^\n]*\n|[^\n]+", text), keep)
    words = ddmin(re.findall(r"^\s+|\S+\s*", "".join(lines)), keep)
    witness = "".join(words)
    got = oracle.read_lanes([witness])[0]
    return {"witness": witness, "witness_error": got["error"], "witness_new": {"lanes": got["tokens"]}}


def old_lanes_of(row):
    return row["witness_old"]["lanes"]


counts = collections.defaultdict(collections.Counter)
by_argument = collections.Counter()
second = collections.Counter()
kinds = {}
for row in rows:
    old, new = normal(row["old"]["lanes"]), normal(row["new"]["lanes"])
    if row["old"]["lanes"] == row["new"]["lanes"]:
        kind = by_mechanism(row)
    elif row["corpus"] in args.no_run:
        by_argument[row["corpus"]] += 1
        w = row["witness"]
        if UNKNOWN_WRAPPER.search(w):
            kind = "new limit: an unknown wrapper or launcher runs the lane"
        elif SHELL_STRING.search(w) and not SHELLS & set(row["witness_new_programs"]):
            kind = "old defect: GPT-6 1: a shell string that is not read by a shell"
        else:
            operand = re.search(r"\b(?:ba|da|z|k|)sh\s+-[A-Za-z]*c\s+'([^']*)'", w)
            if operand and subprocess.run(["bash", "-n"], input=operand.group(1), text=True, capture_output=True).returncode:
                kind = "old defect: a shell string that bash rejects as a syntax error read as commands"
            elif "<(" in w:
                kind = "old defect: a process substitution's neighbours read as commands"
            elif CASE.search(w):
                kind = "old defect: a case pattern read as a command"
            elif not old_lanes_of(row) and SHELLS & set(row["witness_new_programs"]) and re.search(r"&&|\|\|", w):
                kind = "old defect: a shell string with nested quoting was not read by the old reading (its lanes count; every side of && and || counts)"
            else:
                kind = "unexplained"
    else:
        ran = run(row["text"])
        if ran is None:
            ran = run(row["witness"])
        if ran is None:
            kind = "unexplained"
        elif new == ran:
            kind = "old defect: " + old_defect(row["witness"])
        else:
            # the new reading differs from the run: what it misses (a lane that ran) and what it over-counts (a lane that did not run)
            def reasons_of(view):
                out = []
                if ran - new:
                    out.append(missing_reason(view))
                if new - ran:
                    out.append(extra_reason(view, run(view["witness"])))
                return out
            view = {"witness": row["witness"], "witness_error": row["witness_error"], "witness_new": row["witness_new"]}
            reasons = reasons_of(view)
            if None in reasons:
                # the witness of the old/new difference does not show why the new reading differs from the run: reduce against the run instead
                second[row["corpus"]] += 1
                reasons = reasons_of(reduce_against_run(row["text"], ran))
            if None in reasons:
                kind = "unexplained"
            else:
                kind = ("neither reading equals the full run; " if old != ran else "") + " + ".join(dict.fromkeys(reasons))
    kinds[id(row)] = kind
    counts[row["corpus"]][kind] += 1

report = {name: dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))) for name, c in counts.items()}
report["mechanism_not_isolated"] = sum(n for c in counts.values() for k, n in c.items() if k.startswith("mechanism not isolated"))
report["other_old_code_defect"] = sum(n for c in counts.values() for k, n in c.items() if k.endswith("other old-code defect"))
report["classified_by_argument_not_by_run"] = dict(by_argument)
report["reduced_again_against_the_run"] = dict(second)
report["unexplained"] = sum(c["unexplained"] for c in counts.values())
print(json.dumps(report, indent=1))
if args.out:
    json.dump(report, open(args.out, "w"), indent=1)
if args.samples:
    shown = collections.Counter()
    for row in rows:
        kind = kinds[id(row)]
        if row["corpus"] not in args.no_run and (kind.startswith(("static reading", "the new reading equals", "neither", "mechanism not isolated")) or "static reading" in kind or "the new reading equals" in kind or kind.endswith("other old-code defect")) and shown[kind] < args.samples:
            shown[kind] += 1
            print("SAMPLE", kind[:60], "| text:", json.dumps(row["text"])[:150], "| witness:", json.dumps(row["witness"])[:90], "| old", row["old"]["lanes"], "new", row["new"]["lanes"], file=sys.stderr)
for row in rows:
    if kinds[id(row)] == "unexplained":
        print("UNEXPLAINED", row["corpus"], json.dumps(row["witness"])[:120], row["witness_old"], row["witness_new"], row["witness_error"], file=sys.stderr)
