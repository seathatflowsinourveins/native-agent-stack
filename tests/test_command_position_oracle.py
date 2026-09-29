"""Command-position oracle (U1 pivot D10): the lanes REAL bash runs equal the lanes commandInvocations reads.

A deterministic generator (fixed seeds) composes shell constructs around the lane executables; every generated command runs
under real bash 5.2 with `env -i`, a PATH that holds only logging stubs and symlinks to the real env, timeout, nice, nohup, stdbuf,
xargs, cat, bash, sh and dash, a temporary HOME and working directory and a 5 second limit, its output discarded. The stubs are the only
lane executables (no sudo, ssh, curl or wget exists there at all). The multiset of stub names that ran is compared with the lane
invocations the kernel reads from the same text (child-usage.mjs commandInvocations, which needs the pinned tree-sitter-bash install).

The claim covers the classes the generator produces. Shapes whose static reading differs from a run by design are left out of it,
not out of the report: an alias, a function that is never called or a variable program (no static reading exists), a branch or
loop body that the run does not reach (`true || x`, the untaken side of if/else or case, a loop that runs zero or twice), `exec`
(it ends the shell), `sudo` and `ssh` (no real executable exists here), a pipe that feeds a script to a shell (`cat <<EOF | bash`),
a heredoc attached to a compound command, several heredocs on one command, and the shapes tree-sitter-bash 0.25.1 misparses
(a heredoc operator followed by `;` or `&`, or by a redirection and a pipe on its line).
The hand-written probes below hold every finding of the two U1 reviews that concerns command position; their expected
values are the runs of real bash, not what this kernel says.
"""
import collections
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "examples/claude-native/workflows/child-usage.mjs"
PARSER_DIR = Path(os.environ.get("CHILD_USAGE_SHELL_PARSER") or Path.home() / ".local/share/codex-ecosystem/tools/tree-sitter-bash-0.25.1")
LANES = ["qmd", "toon", "repomix", "markitdown", "headroom", "jcodemunch-mcp", "codebase-memory-mcp", "ai-memory", "serena", "context-mode"]
SERVERS = ["codebase-memory", "context-mode", "socraticode", "serena", "qmd", "headroom", "jcodemunch", "ai-memory"]
REAL = ["env", "timeout", "nice", "nohup", "stdbuf", "xargs", "cat", "bash", "sh", "dash"]
SEEDS = range(1, 9)
PER_SEED = 60


def sq(text):
    """`text` as one single-quoted shell word."""
    return "'" + text.replace("'", "'\\''") + "'"


# A token per lane executable run: its name, `!` after it when an argument before `--` is --version or --help (mcporter: a version
# token only as the command, a help token anywhere: openclaw/mcporter@93e0916c src/cli.ts:137-145, src/cli/flag-utils.ts:34-41), and
# for mcporter its operation (and the server before the first dot of a call). A plain `rtk` is not a lane and is not counted. rtk logs `rtk_proxy` when it is asked to proxy, then runs its argv with execvp
# (rtk-ai/rtk@1d87b8e7 src/main.rs:68-90 global flags before the subcommand, :3008-3066 proxy: no shell, stdin inherited; one argument
# with blanks is split first).
STUB = """#!/bin/sh
t={name}
for a in "$@"; do case "$a" in --) break;; --version|--help) t="$t!";; esac; done
printf '%s\\n' "$t" >> "$STUB_LOG"
"""
MCPORTER = """#!/bin/sh
case "$1" in --version|-v|-V|help|-h|--help) printf 'mcporter!\\n' >> "$STUB_LOG"; exit 0;; esac
for a in "$@"; do case "$a" in --help|-h|help) printf 'mcporter!\\n' >> "$STUB_LOG"; exit 0;; esac; done
case "$1" in call) s=${2%%.*}; printf 'mcporter:call@%s\\n' "$s" >> "$STUB_LOG";; *) printf 'mcporter:%s\\n' "$1" >> "$STUB_LOG";; esac
"""
RTK = """#!/bin/sh
while :; do case "$1" in -v|-vv|-vvv|--verbose|--ultra-compact|--skip-env) shift;; *) break;; esac; done
if [ "$1" = proxy ]; then
  printf 'rtk_proxy\\n' >> "$STUB_LOG"; shift
  if [ $# -eq 1 ]; then set -f; set -- $1; fi
  exec "$@"
fi
printf 'rtk\\n' >> "$STUB_LOG"
"""


def make_stubs(root):
    bin_dir = root / "bin"
    bin_dir.mkdir()
    for name in LANES:
        (bin_dir / name).write_text(STUB.format(name=name))
    (bin_dir / "mcporter").write_text(MCPORTER)
    (bin_dir / "rtk").write_text(RTK)
    for name in LANES + ["mcporter", "rtk"]:
        (bin_dir / name).chmod(0o755)
    for name in REAL:
        for directory in ("/usr/bin", "/bin"):
            if os.path.exists(os.path.join(directory, name)):
                os.symlink(os.path.join(directory, name), bin_dir / name)
                break
    return bin_dir


# ---------------------------------------------------------------------------------------------------------------- the probes
# (name, command). `\n` in a Python string is a real newline, as in the review files.
PROBES = [
    # GPT-6 #1 shell strings: the first operand after the options is the script; -n and -D read it without running it; `--` and `-`
    # end the options (so -c after them is a file name); everything after the script is data (bash(1) OPTIONS, ARGUMENTS).
    ("g1 echo data", "echo bash -c 'qmd search x'"),
    ("g1 positional", "bash -c ':' qmd search x"),
    ("g1 -n", "bash -n -c 'qmd search x'"),
    ("g1 -nc", "bash -nc 'qmd search x'"),
    ("g1 -cn", "bash -cn 'qmd search x'"),
    ("g1 -D", "bash -D -c 'qmd search x'"),
    ("g1 --", "bash -- -c 'qmd search x'"),
    ("g1 -", "bash - -c 'qmd search x'"),
    ("g1 -ec", "bash -ec 'qmd search x'"),
    ("g1 -c -e", "bash -c -e 'qmd search x'"),
    ("g1 -o", "bash -o pipefail -c 'qmd search x'"),
    ("g1 -O", "bash -O extglob -c 'qmd search x'"),
    ("g1 +e", "bash +e -c 'qmd search x'"),
    ("g1 --norc", "bash --norc -c 'qmd search x'"),
    ("g1 --rcfile", "bash --rcfile /dev/null -c 'qmd search x'"),
    ("g1 $0", "bash -c 'qmd status \"$0\"' toon"),
    ("g1 -s", "bash -s -c 'qmd search x'"),
    ("g1 sh -n", "sh -n -c 'qmd search x'"),
    ("g1 sh -c", "sh -c 'qmd search x'"),
    ("g1 dash -c", "dash -c 'qmd search x'"),
    ("g1 expansion", 'bash -c "qmd get $HOME"'),
    ("g1 substitution", 'bash -c "cd $(pwd) && qmd get x"'),
    ("g1 escaped expansion", 'bash -c "qmd get \\$HOME"'),
    # GPT-6 #2 arrays
    ("g2 array", "a=( qmd )"),
    ("g2 array two", "tools=(qmd toon)"),
    ("g2 declare", "declare -a x=(qmd toon)"),
    ("g2 substitution", "a=( $(qmd list) )"),
    # GPT-6 #3 the double-quote backslash rule and unquoted escapes
    ("g3 kept backslash", 'qmd "--he\\lp"'),
    ("g3 help in quotes", 'qmd "--help"'),
    ("g3 name", '"q\\md" status'),
    ("g3 unquoted escape", "q\\md status"),
    ("g3 quoted name", '"qmd" status'),
    ("g3 empty quotes", 'q""md status'),
    ("g3 proxy word", 'rtk "pro\\xy" echo ok'),
    ("g3 proxy quoted", 'rtk "proxy" qmd status'),
    # GPT-6 #4 heredoc delimiters: any word ends a heredoc
    ("g4 hyphen data", "cat <<'END-JSON'\nrtk proxy qmd status\nEND-JSON"),
    ("g4 numeric data", "cat <<123\nqmd status\n123"),
    ("g4 hyphen shell", "bash <<'END-X'\nqmd status\nEND-X"),
    ("g4 numeric shell", "bash <<123\nqmd status\n123"),
    ("g4 backslash delimiter", "cat <<\\EOF\n$(qmd a)\nEOF"),
    ("g4 double-quoted delimiter", 'cat <<"EOF"\n$(qmd a)\nEOF'),
    ("g4 unquoted body", "cat <<EOF\n$(qmd a)\nEOF"),
    ("g4 escaped body", "cat <<EOF\nx \\$(qmd a)\nEOF"),
    ("g4 quoted body", "cat <<'EOF'\n$(qmd a)\nEOF"),
    ("g4 strip tabs", "bash <<-EOF\n\tqmd status\n\tEOF"),
    # GPT-6 #5 the shell that reads a heredoc is found through the wrappers
    ("g5 env -u", "env -u UNUSED bash <<'EOF'\nqmd status\nEOF"),
    ("g5 timeout -k", "timeout -k 1 5 bash <<'EOF'\nqmd status\nEOF"),
    ("g5 nice", "nice -n 5 bash <<'EOF'\nqmd status\nEOF"),
    ("g5 nohup", "nohup bash <<'EOF'\nqmd status\nEOF"),
    ("g5 stdbuf", "stdbuf -oL bash <<'EOF'\nqmd status\nEOF"),
    ("g5 rtk proxy", "rtk proxy bash <<'EOF'\nqmd status\nEOF"),
    ("g5 -s", "bash -s <<'EOF'\nqmd status\nEOF"),
    ("g5 -", "bash - <<'EOF'\nqmd status\nEOF"),
    ("g5 -s operand", "bash -s /dev/null <<'EOF'\nqmd status\nEOF"),
    ("g5 file operand", "bash /dev/null <<'EOF'\nqmd status\nEOF"),
    ("g5 -c with heredoc", "bash -c 'cat' <<'EOF'\nqmd status\nEOF"),
    ("g5 herestring", "bash <<< 'qmd status'"),
    ("g5 herestring data", "cat <<< 'qmd status'"),
    ("g5 herestring -c", "bash -c 'cat' <<< 'qmd status'"),
    ("g5 list owner", "true && bash <<'EOF'\nqmd status\nEOF"),
    ("g5 pipeline owner", "echo x | bash <<'EOF'\nqmd status\nEOF"),
    ("g5 negated owner", "! bash <<'EOF'\nqmd status\nEOF"),
    ("g5 fd 3", "bash 3<<'EOF'\nqmd status\nEOF"),
    ("g5 after operator", "bash <<'EOF' && toon after\nqmd status\nEOF"),
    ("g5 pipe after operator", "cat <<'EOF' | cat\nqmd status\nEOF"),
    ("g5 redirect before", "bash > /dev/null <<'EOF'\nqmd status\nEOF"),
    ("g5 redirect after", "bash <<'EOF' > /dev/null\nqmd status\nEOF"),
    ("g5 unquoted mix", "bash <<EOF\nqmd status \\$(toon x)\nEOF"),
    # GPT-6 #6 arithmetic
    ("g6 arithmetic", "echo $(( $(qmd count) + 1 ))"),
    ("g6 quoted", 'echo "$(( $(qmd count) + 1 ))"'),
    ("g6 assignment", "x=$(( $(qmd a) + $(toon b) ))"),
    # GPT-6 #7 rtk proxy runs its argument with execvp
    ("g7 command", "rtk proxy command qmd status"),
    ("g7 exec", "rtk proxy exec qmd status"),
    ("g7 env", "rtk proxy env qmd status"),
    ("g7 plain", "rtk proxy qmd status"),
    ("g7 one argument", "rtk proxy 'qmd status'"),
    ("g7 bash -c", "rtk proxy bash -c 'qmd status'"),
    ("g7 options", "rtk --ultra-compact proxy qmd status"),
    # Claude review R4: function bodies are commands, parentheses outside command position are not
    ("r4 function keyword", "function f { qmd get a; }; f"),
    ("r4 subshell body", "f() ( qmd get a ); f"),
    ("r4 function name", "qmd() { :; }"),
    ("r4 test regex", "[[ x =~ ^(qmd|toon)$ ]]"),
    ("r4 case pattern", "case qmd in qmd) : ;; esac"),
    # wrappers, runners, mcporter, version and help
    ("wrap timeout", "timeout -k 5 60 qmd search x"),
    ("wrap env S", 'env -S "qmd search x"'),
    ("wrap env assignment", "env A=1 B=2 toon f.json"),
    ("wrap command", "command qmd status"),
    ("wrap xargs", "echo a | xargs qmd get"),
    ("lane version", "qmd --version"),
    ("lane help", "toon --help"),
    ("lane after dashdash", "qmd search -- --help"),
    ("mcporter call", "mcporter call codebase-memory.search_graph --args '{}'"),
    ("mcporter list", "mcporter list socraticode --brief"),
    ("mcporter version", "mcporter --version"),
    ("substitution", "x=$(qmd get a); echo \"$(toon b)\" `repomix`"),
    ("data words", "echo qmd 'toon status' \"repomix\"; grep qmd /dev/null; : qmd"),
    ("eval", 'eval "qmd status"'),
    ("eval words", "eval qmd status"),
    ("nested shells", "bash -c \"sh -c 'qmd status'\""),
]

# ------------------------------------------------------------------------------------------------------------- the generator
QUOTES = [lambda w: w, lambda w: "'" + w + "'", lambda w: '"' + w + '"', lambda w: w[0] + '""' + w[1:], lambda w: "\\" + w]


class Generator:
    """Random shell commands built from the constructs above. Every statement it returns exits 0 and runs each lane it names exactly
    once; `posix` marks the text as fit for dash (sh -c). A statement that ends in a heredoc terminator line is closed on a line of its
    own, since nothing may follow a terminator on it."""

    def __init__(self, seed):
        self.rnd = random.Random(seed)
        self.delimiters = set()
        self.serial = 0

    def pick(self, *options):
        return self.rnd.choice(options)

    def word(self):
        return self.pick("x", "a.json", "search", "status", "get", "-n", "--flag", "v1")

    def delimiter(self):
        self.serial += 1
        text = self.rnd.choice(["EOF%d", "END-%d", "%d", "Z_%d"]) % self.serial
        self.delimiters.add(text)
        return text

    def ends_heredoc(self, text):
        return text.split("\n")[-1].lstrip("\t") in self.delimiters

    def end(self, text):
        """`text` as a terminated statement, ready for a closing keyword."""
        return text + ("\n" if self.ends_heredoc(text) else "; ")

    def then(self, first, operator, second):
        return first + ("\n" if self.ends_heredoc(first) else " " + operator + " ") + second

    def lane(self):
        r = self.rnd
        name = r.choice(LANES)
        forms = [
            lambda: name + " " + self.word(),
            lambda: name,
            lambda: r.choice(QUOTES)(name) + " " + self.word(),
            lambda: name + " " + r.choice(["--version", "--help"]),
            lambda: "mcporter call " + r.choice(SERVERS) + ".tool --args '{}'",
            lambda: "mcporter list " + r.choice(SERVERS),
            lambda: "rtk proxy " + name + " " + self.word(),
            lambda: "rtk proxy " + sq(name + " " + self.word()),
            lambda: "rtk --ultra-compact proxy " + name,
            lambda: "env -u U " + name + " " + self.word(),
            lambda: "env A=1 " + name,
            lambda: "timeout 5 " + name,
            lambda: "timeout -k 1 5 " + name + " " + self.word(),
            lambda: "nice -n 5 " + name,
            lambda: "nohup " + name,
            lambda: "stdbuf -oL " + name,
            lambda: "command " + name,
            lambda: "echo a | xargs " + name + " " + self.word(),
            lambda: "env -S " + sq(name + " " + self.word()),
        ]
        return r.choice(forms)()

    def data(self):
        delimiter = self.delimiter()
        return self.pick("echo qmd", "echo 'toon status'", 'echo "repomix"', ": qmd", "cat <<'" + delimiter + "'\nqmd status\n" + delimiter, "a=( qmd toon )",
                         "case x in qmd) : ;; esac", "echo bash -c 'qmd x'", "bash -n -c 'qmd x'", "bash -c ':' qmd x")

    def statement(self, depth, posix=False):
        r = self.rnd
        if depth <= 0 or r.random() < 0.28:
            return self.lane() if r.random() < 0.85 else self.data()
        inner = lambda: self.statement(depth - 1, posix)
        forms = [
            lambda: self.then(inner(), "&&", inner()),
            lambda: self.then(inner(), ";", inner()),
            lambda: inner() + "\n" + inner(),
            lambda: self.then(inner(), "|", inner()),
            lambda: self.then("false", "||", inner()),
            lambda: self.negated(self.lane()),
            lambda: self.negated(self.heredoc_owner(depth, posix)),
            lambda: "( " + self.end(inner()) + ")",
            lambda: "{ " + self.end(inner()) + "}",
            lambda: "if " + self.end(inner()) + "then " + self.end(inner()) + "fi",
            lambda: "for i in a; do " + self.end(inner()) + "done",
            lambda: self.case_branch(inner()),
            lambda: "echo $(" + self.lane() + ")",
            lambda: "v=$(" + self.lane() + ")",
            lambda: 'echo "$(' + self.lane() + ')"',
            lambda: "echo `" + self.lane() + "`",
            lambda: "echo $(echo $(" + self.lane() + "))",
            lambda: "f() { " + self.end(inner()) + "}; f",
            lambda: self.heredoc_owner(depth, posix),
            lambda: self.shell_string(depth, posix),
            lambda: "eval " + sq(inner()),
        ]
        if not posix:
            forms += [
                lambda: "echo $(( $(" + self.lane() + ") + 1 ))",
                lambda: "a=( $(" + self.lane() + ") )",
                lambda: "cat <(" + self.lane() + ")",
                lambda: "bash <<< " + sq(inner()),
                lambda: self.then("(( 1 + 1 ))", ";", inner()),
                lambda: self.then("[[ -n x ]]", "&&", inner()),
            ]
        return r.choice(forms)()

    def negated(self, text):
        """`! command` exits 1 (`!` binds to one pipeline): `! command || :` exits 0, and a heredoc terminator line is followed by a line of its own."""
        return "! " + text + "\n:" if self.ends_heredoc(text) else "! " + text + " || :"

    def case_branch(self, text):
        return "case x in x) " + text + ("\n" if self.ends_heredoc(text) else " ") + ";; esac"

    def heredoc_owner(self, depth, posix):
        r = self.rnd
        body = self.statement(depth - 1, True)
        delimiter = self.delimiter()
        wrapper = r.choice(["", "env -u U ", "timeout -k 1 5 ", "nice -n 5 ", "nohup ", "stdbuf -oL "])
        shell = r.choice(["bash", "sh", "dash", "bash -s", "bash -e", "bash -o pipefail", "sh -e"])
        form = r.choice(["quoted", "quoted", "strip", "unquoted-data", "data-substitution"])
        if form == "quoted":
            return wrapper + shell + " <<'" + delimiter + "'\n" + body + "\n" + delimiter
        if form == "strip":
            return wrapper + shell + " <<-" + delimiter + "\n" + "".join("\t" + line + "\n" for line in body.split("\n")) + "\t" + delimiter
        if form == "unquoted-data":
            return "cat <<" + delimiter + "\nplain text\n" + delimiter
        return "cat <<" + delimiter + "\nbefore $(" + self.lane() + ") after\n" + delimiter

    def shell_string(self, depth, posix):
        r = self.rnd
        shell = "sh" if posix else r.choice(["bash", "sh", "dash"])
        body = self.statement(depth - 1, posix or shell != "bash")
        flags = r.choice(["-c", "-c", "-ec", "-o pipefail -c", "--norc -c"]) if shell == "bash" else "-c"
        wrapper = r.choice(["", "", "env -u U ", "timeout 5 ", "rtk proxy "])
        quote = r.choice([sq, lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'])
        return wrapper + shell + " " + flags + " " + quote(body)


def generate():
    seen, commands = set(), []
    for seed in SEEDS:
        generator = Generator(seed)
        for _ in range(PER_SEED):
            command = generator.statement(generator.rnd.choice([1, 2, 2, 3]))
            if command not in seen:
                seen.add(command)
                commands.append(command)
    return commands


# --------------------------------------------------------------------------------------------------------------------- the runs
def run_real(commands, bin_dir, home):
    """Lane tokens each command really ran (the stubs' log), one Counter per command."""
    runs = []
    for command in commands:
        log = home / "log"
        log.write_text("")
        text = command + ("\nwait" if "&" in command.replace("&&", "") else "")
        env = {"PATH": str(bin_dir), "HOME": str(home), "STUB_LOG": str(log), "TMPDIR": str(home)}
        try:
            subprocess.run([shutil.which("bash"), "-c", text], env=env, cwd=home, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=5, check=False, start_new_session=True)
        except subprocess.TimeoutExpired:
            runs.append(None)
            continue
        ran = collections.Counter(log.read_text().split())
        del ran["rtk"]  # an rtk that is not proxying is no lane
        runs.append(ran)
    return runs


READER = """
import {readFileSync} from 'node:fs'
import * as cu from %s
const commands = JSON.parse(readFileSync(0, 'utf8'))
await cu.loadShellParser()
const token = (i) => i.lane === 'mcporter' ? (i.excluded ? 'mcporter!' : 'mcporter:' + i.op + (i.op === 'call' ? '@' + i.server : '')) : i.lane + (i.excluded ? '!' : '')
process.stdout.write(JSON.stringify(commands.map((c) => {
  const found = cu.commandInvocations(c)
  return { tokens: found.filter((i) => i.lane && !i.remote && !i.unresolved).map(token), unresolved: found.filter((i) => i.unresolved).length, error: cu.withShellTree(c, (root) => root.hasError) }
})))
"""


def read_lanes(commands):
    p = subprocess.run(["node", "--input-type=module", "-e", READER % json.dumps(MODULE.as_uri())], input=json.dumps(commands),
                       text=True, capture_output=True, check=False)
    if p.returncode:
        raise AssertionError(p.stderr[:800])
    return json.loads(p.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
@unittest.skipUnless(shutil.which("bash"), "bash is not installed")
@unittest.skipUnless((PARSER_DIR / "package-lock.json").is_file(), "no tree-sitter-bash install at the default directory or CHILD_USAGE_SHELL_PARSER")
class CommandPositionOracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="oracle-")
        cls.home = Path(cls.tmp.name)
        cls.bin = make_stubs(cls.home)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def agree(self, commands):
        truth, read = run_real(commands, self.bin, self.home), read_lanes(commands)
        wrong, agreed, ran = [], 0, 0
        for command, real, seen in zip(commands, truth, read):
            if real is None:
                self.fail("a generated command timed out under real bash: " + repr(command))
            ran += sum(real.values())
            if collections.Counter(seen["tokens"]) == real and not seen["error"]:
                agreed += 1
            else:
                wrong.append((command, dict(real), seen["tokens"], seen["error"]))
        return agreed, ran, wrong

    def test_probes_read_what_real_bash_runs(self):
        commands = [command for _, command in PROBES]
        agreed, ran, wrong = self.agree(commands)
        names = {command: name for name, command in PROBES}
        self.assertEqual(wrong, [], "\n".join("%s: %r ran %s, read %s (parse error: %s)" % (names[c], c, r, s, e) for c, r, s, e in wrong))
        print("oracle probes: %d of %d agree (%d lane runs)" % (agreed, len(commands), ran))

    def test_generated_commands_read_what_real_bash_runs(self):
        commands = generate()
        self.assertGreater(len(commands), 300)
        agreed, ran, wrong = self.agree(commands)
        self.assertEqual(wrong, [], "%d of %d differ; first:\n" % (len(wrong), len(commands))
                         + "\n".join("%r ran %s, read %s (parse error: %s)" % w for w in wrong[:12]))
        self.assertGreater(ran, len(commands))  # the commands run lanes, so an empty reading cannot agree by accident
        print("oracle generated: %d of %d agree (%d lane runs)" % (agreed, len(commands), ran))


if __name__ == "__main__":
    unittest.main()
