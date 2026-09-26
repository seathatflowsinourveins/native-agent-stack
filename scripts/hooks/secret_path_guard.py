#!/usr/bin/env python3
"""Claude Code PreToolUse guard for Bash: block obvious credential exposure.

Reads only the hook's stdin JSON (tool_input.command). It never opens a file,
never reads the environment and never prints the command. Exit 2 blocks the
call and returns a one-line reason code on stderr (documented PreToolUse
behaviour); exit 0 lets it continue.

This is a deterministic text heuristic that stops accidental exposure:
naming a credential store, dumping the environment, echoing a secret
variable, tracing a process, printing a native token (`gh auth token`,
`hf auth token`, or through a git credential helper), reading or searching
credential files or secret variable names, reading or copying the whole
Hugging Face home, tracing a shell while it sources a
credential file, and dumping the environment after sourcing one. For a key
held in the Linux kernel keyring it blocks payload reads (`keyctl print`,
`pipe`, `read` and `dh_compute`, `keyctl list` or `rlist` on anything but an
unambiguous keyring, and a keyring read in inline interpreter code), checks
the command that `kernel_keyring.py exec` or `tvly-keyring` starts with every
rule above, and blocks that command when it names the injected variable or
dumps the environment it inherits, also behind a launcher's options
(`stdbuf -o0`) or a launcher the guard does not model (`watch`, `flock`).
A backslash-newline is joined first and every raw-text rule also reads the
command after the shell's quote removal, so a name split by quotes, a
backslash or a line continuation is still that name; redirection operands
are never taken for arguments. It is not a security boundary. A process
that imports a loader, a name assembled at run time, or a renamed or
obfuscated path passes; see docs/secret-storage.md "Threat model" for the
residual risk.

The same file is installed for every session on a host as
~/.claude/hooks/secret_path_guard.py by tools/adoption/install_claude_profile.py
(sha256-pinned in adoption/hooks/claude/SHA256SUMS).
"""

from __future__ import annotations

import json
import re
import shlex
import sys


STORE_PATHS = (
    (re.compile(r"\.config/native-agent-stack(?:/|\b)"), "credential_store_path"),
    (re.compile(r"XDG_CONFIG_HOME(?::-[^}\s]*)?\}?/native-agent-stack(?:/|\b)"), "credential_store_path"),
    (re.compile(r"\.claude/\.credentials\.json"), "native_store_path"),
    (re.compile(r"(?:\.codex|CODEX_HOME\}?)/auth\.json"), "native_store_path"),
    (re.compile(r"gh/hosts\.yml"), "native_store_path"),
    # Hugging Face token files: the default home, $XDG_CACHE_HOME/huggingface, $HF_HOME or a
    # ${HF_HOME:-...} form, a closing quote allowed before the slash; tokenizers/ and hub/ pass.
    (re.compile(r"(?:huggingface|HF_HOME(?::-[^}\s]*)?)\}?[\"']?/(?:token|stored_tokens)(?![\w-])"),
     "native_store_path"),
    # tavily-cli's own store (`tvly login` or `tvly init` write the key or an OAuth token there).
    (re.compile(r"\.tavily/config\.json"), "native_store_path"),
    (re.compile(r"ecosystem-grafana\.env"), "service_secret_path"),
    (re.compile(r"nativestack/generation\.key"), "service_secret_path"),
    (re.compile(r"/proc/(?:[^/\s]+/)*environ\b"), "process_environment"),
    (re.compile(r"\bgh\s+auth\s+token\b"), "native_token_print"),
    (re.compile(r"\bhf\s+auth\s+token\b"), "native_token_print"),
    (re.compile(r"\bhuggingface-cli\s+(?:auth\s+)?token\b"), "native_token_print"),
    (re.compile(r"--show-token\b"), "native_token_print"),
    (re.compile(r"\bgh\s+auth\s+status\b[^;&|\n]*\s-t\b"), "native_token_print"),
    (re.compile(r"\bsecurity\s+(?:find-generic-password|find-internet-password|dump-keychain)\b"), "keychain_read"),
    (re.compile(r"\bsecret-tool\s+lookup\b"), "keychain_read"),
)
# Every secret `variables` name and every `must_not_be_set` name of
# adoption/credential-inventory.json; tests/test_secret_path_guard.py fails when
# the inventory gains a name this tuple lacks, so the hook needs no file read.
SECRET_NAMES = (
    "APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
    "DATABENTO_API_KEY", "TYPESAFE_API_KEY", "OMNIROUTE_API_KEY", "MASSIVE_API_KEY",
    "GF_SECURITY_ADMIN_PASSWORD", "GF_SECURITY_SECRET_KEY",
    "GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CODEX_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "QDRANT_API_KEY",
    "PREFECT_API_KEY", "MC_API_KEY", "MSB_API_KEY", "PAPERCLIP_API_KEY",
    "TWS_USERNAME", "TWS_PASSWORD", "TWS_ACCOUNT", "IBKR_ACCOUNT_ID",
    "TAVILY_API_KEY",
)
_NAMES = "|".join(SECRET_NAMES)
SECRET_NAME = re.compile(r"\b(?:" + _NAMES + r")\b")
SECRET_EXPANSION = re.compile(r"\$\{?!?(?:" + _NAMES + r")\b")
SECRET_LOOKUP = re.compile(r"(?:environ|getenv|process\.env|ENV\[)[^;\n]{0,40}\b(?:" + _NAMES + r")\b")
POINTER_VARIABLE = re.compile(
    r"\$\{?(?:PAPER_ENV_FILE|ENV_FILE|SEC_CONTACT_ENV|PIT_ALPACA_ENV_PATH|PIT_SEC_ENV_PATH|HF_TOKEN_PATH)\b")
# The Hugging Face home itself (or everything in it) as a reader's operand: a recursive search or a
# copy of it includes both token files. Its subdirectories such as hub/ stay readable.
HF_HOME_ROOT = re.compile(r"(?:(?:\.cache|XDG_CACHE_HOME)\}?/huggingface\}?|^\$\{?HF_HOME\}?)(?:/\**)?$")
# A .env-style credential file: `.env`, `.env.local`, `.envrc`, `alpaca-paper.env`, `*.env`,
# also as the value of `--include=`/`-g` style options. `*.example` templates stay readable.
ENV_FILE_WORD = re.compile(r"(?:^|[/=])(?:\.env[^/=]*|[^/=]*\.env)$")
# Inline code that reads the whole process environment (only checked after a credential file was sourced).
ENVIRONMENT_ACCESS = re.compile(r"\benviron\b|\bgetenv\b|process\.env\b|%ENV\b|\$ENV\b|\bENV\[|\bENV\.")
PROC_WORD = re.compile(r"(?:^|[\s'\"=])/proc(?:/|\b)")
READERS = {
    "cat", "tac", "nl", "head", "tail", "less", "more", "bat", "batcat", "view", "vi", "vim", "nano",
    "grep", "egrep", "fgrep", "rg", "ag", "ack", "ugrep", "zgrep", "pcregrep", "pcre2grep",
    "zcat", "bzcat", "xzcat", "sed", "awk", "gawk", "mawk", "nawk", "perl", "cut", "sort", "uniq",
    "paste", "xxd", "od", "hexdump", "strings", "base64", "base32", "cp", "scp", "rsync", "tee",
    "diff", "cmp", "openssl", "gpg", "age", "curl", "wget", "nc", "ncat", "socat", "jq", "yq", "dd",
}
TRACERS = {"strace", "ltrace", "gdb", "bpftrace"}
WRAPPERS = {"sudo", "doas", "command", "builtin", "exec", "nohup", "time", "nice", "stdbuf",
            "xargs", "setsid", "ionice", "chronic"}
# Launcher options that take the next word as their value (getopt: a required argument, given
# separately), per launcher, so strip_prefix skips both and reaches the command; a glued `-o0` or
# `--output=L` is one word. From each tool's --help on 2026-09-26 (coreutils nice, stdbuf, timeout;
# util-linux ionice; GNU time; GNU findutils 4.9.0 xargs, whose -e, -i, -l, --eof, --replace and
# --max-lines take only a glued optional value, as `xargs --max-lines 1 echo` running `1` showed;
# sudo, where a bare -h is --help; the doas(1) synopsis on man.openbsd.org; bash `help exec`).
# Other options are boolean.
WRAPPER_VALUE_FLAGS = {
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "-P", "-u", "--class", "--classdata", "--pid", "--pgid", "--uid"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "time": {"-f", "-o", "--format", "--output"},
    "xargs": {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "--arg-file", "--delimiter", "--max-args",
              "--max-procs", "--max-chars", "--process-slot-var"},
    "sudo": {"-C", "-D", "-g", "-p", "-R", "-r", "-T", "-t", "-U", "-u", "--close-from", "--chdir", "--group",
             "--prompt", "--chroot", "--role", "--command-timeout", "--type", "--other-user", "--user"},
    "doas": {"-a", "-C", "-u"},
    "exec": {"-a"},
}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SOURCERS = {".", "source"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
COPIERS = {"cp", "scp", "rsync"}
REDIRECT_OUT = re.compile(r"^\d*(?:>|>>|>\||&>|&>>|>&)$")
# Every redirection operator as shlex (punctuation_chars) splits it: `2>&1` is `2`, `>&`, `1`, and
# `<<-EOF` is `<<`, `-EOF`. The word after one is its file, descriptor or here-document delimiter.
REDIRECTION = re.compile(r"^\d*(?:>>?|>\||&>>?|<<<?|<>|<&|>&|<)$")
GIT_ARG_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
PS_BSD_CLUSTER = re.compile(r"^[aAcfhjlmrsStTuvwxXLn]*e[aAcefhjlmrsStTuvwxXLn]*$")
PS_ARG_OPTIONS = {"-o", "-O", "-p", "-u", "-U", "-C", "-g", "-G", "-t", "-q", "-s", "-k",
                  "--pid", "--format", "--sort", "--ppid", "--user"}
ENV_ARG_OPTIONS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
TRACE_OPTIONS = {"xtrace", "verbose"}
MAX_DEPTH = 3
# The Linux kernel keyring (docs/secret-storage.md, "Memory-only option"). `kernel_keyring.py exec
# <name> <ENV_VAR> -- <command...>` puts a stored key into that command's environment only, and
# adoption/tools/tvly-keyring runs `tvly` the same way with TAVILY_API_KEY. expand() unwraps both, so
# every rule applies to the command they start; keyring_reason() also blocks that command when it
# names the injected variable or dumps the environment it inherits.
KEYRING_SCRIPT = "kernel_keyring.py"
KEYRING_WRAPPERS = {"tvly-keyring": ("TAVILY_API_KEY", "tvly")}
ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*")
# keyctl(1) subcommands that print a payload (keyutils Git, as published on man7.org on 2026-08-04):
# `print`, `pipe` and `read` output it, and `dh_compute` prints base ^ private (mod prime) computed from
# three keys' payloads, which with a private key of 1 is the base key's own payload. `request`,
# `request2` and `prequest2` print a key ID only.
KEYCTL_PAYLOAD_COMMANDS = {"print", "pipe", "read", "dh_compute"}
# `list` and `rlist` read their target with KEYCTL_READ and print it as key IDs, and "No attempt is
# made to check that the specified keyring is a keyring" (keyctl(1)): act_keyctl_list and
# act_keyctl_rlist call keyctl_read_alloc and print every four bytes as a signed integer, so on a
# `user` key they print its payload (keyutils Git master, commit c076dff2, read 2026-09-26; `show`
# reads a key only after checking that its type is keyring). They pass only on an unambiguous
# keyring: a special keyring (@t @p @s @u @us @g, or -1 to -6) or a keyring by name (`%:name`,
# `%keyring:name`). A serial, `%user:...` or @a (-7, the request_key authorisation key) can be a key.
# keyctl takes the whole command name: its lookup skips any name longer than the word typed.
KEYCTL_LIST_COMMANDS = {"list", "rlist"}
KEYCTL_KEYRING_TARGETS = {"@t", "@p", "@s", "@u", "@us", "@g", "-1", "-2", "-3", "-4", "-5", "-6"}
KEYCTL_KEYRING_NAMED = ("%:", "%keyring:")
# Inline code that reads a payload: the operation's name, libkeyutils' and python-keyutils' readers,
# this repository's keyring module, a raw keyctl system call (x86_64 250, aarch64 219) with
# operation 11 (KEYCTL_READ), or keyctl(1) run as a subprocess (`list` and `rlist` as on the command
# line: unless their target is an unambiguous keyring). Checked only when the command runs an
# interpreter (INTERPRETER), so a commit message or a code search that mentions KEYCTL_READ passes.
KEYRING_READ_CODE = re.compile(
    r"\bKEYCTL_READ\b|\bkeyctl_read(?:_alloc)?\s*\(|\bkeyutils\s*\.\s*read_key\b"
    r"|\b(?:import|from)\s+(?:scripts\s*\.\s*)?kernel_keyring\b"
    r"|\bsyscall\s*\(\s*(?:[\w.]*c_u?(?:long|int)\s*\(\s*)?(?:250|219)\b[^;\n]{0,40}?\b11\b"
    r"|\bkeyctl[\"',\s]+(?:print|pipe|read|dh_compute)\b"
    r"|\bkeyctl[\"',\s]+r?list\b(?![\"',\s]+(?:(?:@(?:us|[tpsug])|-[1-6])(?![\w-])|%(?:keyring)?:))")
# Programs that run inline code, and launchers that start one (`uv run python -c ...`).
INTERPRETER = re.compile(
    r"(?:python|pypy|perl|ruby|php|lua|tclsh)[0-9.]*|node|nodejs|deno|bun|luajit|Rscript|julia"
    r"|osascript|pwsh|powershell|uv|uvx|pipx|npx|pnpm|poetry|pdm|hatch|conda|mamba|pixi")
AWKS = {"awk", "gawk", "mawk", "nawk"}
JQS = {"jq", "gojq", "jaq", "yq"}
# Environment access in code that a keyring exec starts: ENVIRONMENT_ACCESS plus Python's environb,
# Ruby's and Julia's bare ENV, Deno.env and Bun.env, PHP's $_ENV and $_SERVER, PowerShell's env: drive,
# awk's ENVIRON, and a quoted env, printenv, set, export or declare -p handed to a subprocess.
KEYRING_ENVIRONMENT_ACCESS = re.compile(
    ENVIRONMENT_ACCESS.pattern
    + r"|\benvironb\b|\bENV\b|\b(?:Deno|Bun)\.env\b|\$_ENV\b|\$_SERVER\b|(?i:\benv:)|\bENVIRON\b"
    + r"|[\"'](?:/usr/bin/)?(?:env|printenv|set|export(?: -p)?|declare -[px])[\"']")
JQ_ENVIRONMENT = re.compile(r"(?<![\w.$])env\b|\$ENV\b")
SHELL_INDIRECTION = re.compile(r"\$\{!")
ENVIRONMENT_PRINTERS = {"env", "printenv"}
# Programs that a launcher the guard does not model (watch, flock, taskset, GNU time -f ...) may start
# from among its arguments, so a keyring exec's command is also read from each of them onward. The
# shell builtins that print variables count, since watch hands its arguments to `sh -c`.
LAUNCHED_PROGRAMS = SHELLS | AWKS | JQS | ENVIRONMENT_PRINTERS | {"ps", "set", "export", "declare", "typeset",
                                                                  "readonly", "local"}

HINTS = {
    "secret_name_search": "search repository code with the Grep tool instead of a shell search for a "
                          "secret variable name",
    "trace_while_sourcing": "shell tracing prints every assignment of a sourced credential file",
    "environment_dump_after_source": "after sourcing a credential file the environment holds its values",
    "keyring_payload_read": "a key in the kernel keyring stays in memory; check it with kernel_keyring.py "
                            "status and hand it to one command with kernel_keyring.py exec",
    "keyring_variable_reference": "the command that kernel_keyring.py exec starts holds the key in its "
                                  "environment; run a client that reads the variable itself, without naming it",
    "environment_dump_in_keyring_exec": "the command that kernel_keyring.py exec starts holds the key in "
                                        "its environment",
}


def tokenize(command: str) -> list[str]:
    text = command.replace("`", " ; ").replace("\n", " ; ")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return re.findall(r"[;&|()<>]+|[^\s;&|()<>]+", text)


def segments(tokens: list[str]) -> list[list[str]]:
    result, current = [], []
    for token in tokens:
        if token in SEPARATORS or set(token) <= set(";&|()"):
            if current:
                result.append(current)
            current = []
        else:
            current.append(token)
    if current:
        result.append(current)
    return result


def redirection_width(words: list[str], index: int) -> int:
    """How many words the redirection at words[index] takes (operator and target, with a descriptor
    number before it and the `-` of `<<- EOF`), or 0 when it starts none. A digit before an operator is
    read as its descriptor, since shlex splits `2>` and `2 >` alike."""
    word = words[index]
    if word.isdigit() and index + 1 < len(words) and REDIRECTION.match(words[index + 1]):
        return 1 + redirection_width(words, index + 1)
    if not REDIRECTION.match(word):
        return 0
    return 3 if word == "<<" and words[index + 1:index + 2] == ["-"] else 2


def command_arguments(words: list[str]) -> list[str]:
    """words[1:] without redirections, so a redirection's target (`tvly auth > --json` writes to a
    file named --json) or a here-document delimiter is never taken for an argument."""
    result, index = [], 1
    while index < len(words):
        width = redirection_width(words, index)
        if width:
            index += width
        else:
            result.append(words[index])
            index += 1
    return result


def skip_wrapper_options(words: list[str], index: int, wrapper: str) -> int:
    """Index of the first word after a launcher's own options, as getopt reads them: `--` ends them;
    in a cluster of short options (`-iu`) the first that takes a value takes the rest of the cluster
    (`-o0`) or, when it ends the cluster, the next word (`-o 0`, `nice -n 10`, `sudo -u root`)."""
    value_flags = WRAPPER_VALUE_FLAGS.get(wrapper, set())
    while index < len(words):
        word = words[index]
        if word == "--":
            return index + 1
        if not word.startswith("-") or word == "-":
            return index
        index += 1
        if word.startswith("--"):
            takes_next = word in value_flags
        else:
            letters = word[1:]
            first = next((at for at, letter in enumerate(letters) if f"-{letter}" in value_flags), None)
            takes_next = first == len(letters) - 1
        if takes_next:
            index += 1
    return index


def strip_prefix(words: list[str]) -> list[str]:
    """The command itself: without assignments, output redirections before it (`> out cmd`), and
    launchers with their options (timeout also with its duration). A leading input redirection stays,
    for segment_reason's check of what is redirected in."""
    index = 0
    while index < len(words):
        word = words[index]
        width = redirection_width(words, index)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word == "$":
            index += 1
        elif width and REDIRECT_OUT.match(words[index + width - 2]):
            index += width
        elif word in WRAPPERS or word == "timeout":
            index = skip_wrapper_options(words, index + 1, word)
            if word == "timeout":
                index += 1  # timeout's mandatory duration comes before the command
        else:
            break
    return words[index:]


def program_of(words: list[str]) -> str:
    return words[0].rsplit("/", 1)[-1] if words else ""


def env_command_start(words: list[str]) -> int | None:
    """Index of the command `env [options] [NAME=value ...] command` runs, or None for a dump."""
    index = 1
    while index < len(words):
        word = words[index]
        if word in ENV_ARG_OPTIONS:
            index += 2
        elif word.startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            index += 1
        else:
            return index
    return None


def shell_parts(words: list[str]) -> tuple[bool, str | None]:
    """(traces, inline command) for `bash [options] [-c command]`."""
    traces, inline, expect_command = False, None, False
    index = 1
    while index < len(words):
        word = words[index]
        if word in {"-o", "+o"} and index + 1 < len(words):
            traces |= word == "-o" and words[index + 1] in TRACE_OPTIONS
            index += 2
            continue
        if word in {"--verbose", "--xtrace"}:
            traces = True
        elif word.startswith("-") and not word.startswith("--") and len(word) > 1:
            letters = set(word[1:])
            traces |= bool(letters & {"x", "v"})
            expect_command |= "c" in letters
        elif not word.startswith("-"):
            if expect_command:
                inline = word
            break
        index += 1
    return traces, inline


def keyring_exec(words: list[str]) -> tuple[str | None, list[str]] | None:
    """(injected variable, started command) for a keyring exec.

    `kernel_keyring.py exec <name> <ENV_VAR> -- <command...>` is found at any position, so any path
    to the script and any launcher (python3 -I, uv run python, sudo ...) counts; the variable is None
    when it is not a literal name. `tvly-keyring <args>` starts `tvly <args>` with TAVILY_API_KEY.
    """
    for position, word in enumerate(words):
        name = word.rsplit("/", 1)[-1]
        if name == KEYRING_SCRIPT and words[position + 1:position + 2] == ["exec"]:
            arguments = words[position + 2:]
            if "--" not in arguments:
                return None  # kernel_keyring.py refuses to start anything without the separator
            separator = arguments.index("--")
            variable = arguments[separator - 1] if separator else None
            return variable if variable and ENV_NAME.fullmatch(variable) else None, arguments[separator + 1:]
        if name in KEYRING_WRAPPERS and (position == 0 or program_of(words) in SHELLS):
            variable, target = KEYRING_WRAPPERS[name]
            return variable, [target, *words[position + 1:]]
    return None


def expand(command: str, depth: int = 0) -> list[list[str]]:
    """Command segments, including those of `sh -c '...'`, `eval ...`, `env ... command` and of
    the command that a keyring exec starts."""
    result: list[list[str]] = []
    for raw in segments(tokenize(command)):
        words = strip_prefix(raw)
        while words:
            result.append(words)
            program = program_of(words)
            if program == "env":
                start = env_command_start(words)
                if start is None:
                    break
                words = strip_prefix(words[start:])
                continue
            started = keyring_exec(words)
            if started is not None:
                words = strip_prefix(started[1])
                continue
            if depth < MAX_DEPTH:
                if program in SHELLS:
                    inline = shell_parts(words)[1]
                    if inline is not None:
                        result.extend(expand(inline, depth + 1))
                elif program == "eval" and len(words) > 1:
                    result.extend(expand(" ".join(words[1:]), depth + 1))
            break
    return result


def ps_shows_environment(words: list[str]) -> bool:
    skip = False
    for word in words[1:]:
        if skip:
            skip = False
            continue
        if word in PS_ARG_OPTIONS:
            skip = True
            continue
        if not word.startswith("-") and PS_BSD_CLUSTER.match(word):
            return True
    return False


def git_subcommand_args(words: list[str]) -> tuple[str | None, list[str]]:
    index = 1
    while index < len(words):
        word = words[index]
        if word in GIT_ARG_OPTIONS:
            index += 2
        elif word.startswith("-"):
            index += 1
        else:
            return word, words[index + 1:]
    return None, []


def read_operands(words: list[str]) -> list[str]:
    """Arguments minus write targets: redirection targets, a copy's destination, tee's files."""
    program = program_of(words)
    if program == "tee":
        return []
    operands, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif REDIRECT_OUT.match(word):
            skip = True
        else:
            operands.append(word)
    if program in COPIERS:
        positional = [w for w in operands if not w.startswith("-")]
        if len(positional) >= 2:
            operands.remove(positional[-1])
    return operands


def reader_arguments(words: list[str]) -> list[str] | None:
    """Read arguments of a file reader or search, or None when the segment is neither."""
    program = program_of(words)
    if program in READERS:
        return read_operands(words)
    if program == "git":
        subcommand, rest = git_subcommand_args(words)
        return rest if subcommand == "grep" else None
    if program == "find":
        for position, word in enumerate(words[:-1]):
            if word in FIND_EXEC and program_of(strip_prefix(words[position + 1:])) in READERS:
                return words[1:]
    return None


def is_env_file_word(word: str) -> bool:
    return bool(ENV_FILE_WORD.search(word)) and not word.endswith(".example")


def is_environment_dump(words: list[str]) -> bool:
    program = program_of(words)
    if program == "printenv":
        return True
    if program == "env":
        return env_command_start(words) is None
    if program in {"set", "export"} and (len(words) == 1 or words[1:] == ["-p"]):
        return True
    if program in {"declare", "typeset"} and all(w.startswith("-") for w in words[1:]) \
            and (len(words) == 1 or any(set(w[1:]) & set("xp") for w in words[1:])):
        return True
    return program == "ps" and ps_shows_environment(words)


def dumps_after_source(words: list[str]) -> bool:
    """Forms that print values once a credential file is sourced, even with a name filter."""
    program = program_of(words)
    if is_environment_dump(words):
        return True
    return program in {"declare", "typeset", "export", "readonly", "local"} and any(
        w.startswith("-") and set(w[1:]) & set("px") for w in words[1:])


def sources_credential_file(words: list[str]) -> bool:
    return program_of(words) in SOURCERS and any(
        POINTER_VARIABLE.search(w) or is_env_file_word(w) for w in words[1:])


def traces(words: list[str]) -> bool:
    program = program_of(words)
    if program in SHELLS:
        return shell_parts(words)[0]
    if program != "set":
        return False
    args = words[1:]
    for position, word in enumerate(args):
        if word == "-o" and position + 1 < len(args) and args[position + 1] in TRACE_OPTIONS:
            return True
        if word.startswith("-") and not word.startswith("--") and set(word[1:]) & {"x", "v"}:
            return True
    return False


def prints_helper_credential(words: list[str]) -> bool:
    """`git credential fill`, a helper's `get` and `gh auth git-credential` print a stored token."""
    program = program_of(words)
    if program == "git":
        subcommand, rest = git_subcommand_args(words)
        if subcommand == "credential":
            return "fill" in rest
        return bool(subcommand and subcommand.startswith("credential-")) and "get" in rest
    if program.startswith("git-credential-"):
        return "get" in words[1:]
    if program == "gh":
        return [w for w in words[1:] if not w.startswith("-")][:2] == ["auth", "git-credential"]
    return False


def tvly_prints_key(words: list[str]) -> bool:
    """`tvly auth` without JSON output prints the key's first eight and last four characters
    (tavily-cli 0.1.8 commands/auth.py); `tvly auth --json` and `tvly --json auth` print no key.
    A redirection's target is no flag: `tvly auth > --json` prints the key into a file named --json."""
    if program_of(words) != "tvly":
        return False
    arguments = command_arguments(words)
    positional = [w for w in arguments if not w.startswith("-")]
    return positional[:1] == ["auth"] and "--json" not in arguments and "--help" not in arguments


def keyctl_reads_payload(words: list[str]) -> bool:
    """keyctl(1) with a subcommand that prints a payload, or `list`/`rlist` whose target is not an
    unambiguous keyring (KEYCTL_LIST_COMMANDS). keyctl has no options of its own before the command."""
    arguments = command_arguments(words)
    at = next((index for index, word in enumerate(arguments) if not word.startswith("-")), None)
    if at is None:
        return False
    if arguments[at] in KEYCTL_PAYLOAD_COMMANDS:
        return True
    if arguments[at] in KEYCTL_LIST_COMMANDS and at + 1 < len(arguments):
        target = arguments[at + 1]
        return not (target in KEYCTL_KEYRING_TARGETS or target.startswith(KEYCTL_KEYRING_NAMED))
    return False


def launched_commands(words_list: list[list[str]]) -> list[list[str]]:
    """Commands among the arguments of each segment, read from every word that names a program in
    LAUNCHED_PROGRAMS or an interpreter onward and expanded like a command: how a launcher the guard
    does not model (`watch -n 5 python3 -c ...`, `flock f sh -c ...`, `find -exec`) would run them."""
    found = []
    for words in words_list:
        for position in range(1, len(words)):
            if "://" in words[position]:
                continue  # a URL argument (`tvly extract https://.../env`) is never a program a launcher runs
            program = program_of(words[position:position + 1])
            if program in LAUNCHED_PROGRAMS or INTERPRETER.fullmatch(program):
                found.extend(expand(shlex.join(words[position:])))
    return found


def unquoted(command: str) -> str:
    """The command without the shell's quoting (quote characters and backslashes), so a name that
    quotes or a backslash split, such as KK_DEMO_TO"KEN" or KK_DEMO_TO\\KEN, reads as the one word the
    shell passes on. check() has already joined every backslash-newline."""
    return re.sub(r"[\"'\\]", "", command)


def mentions_injected_variable(text: str, variable: str) -> bool:
    """Whether unquoted command text names an injected variable anywhere but in the <ENV_VAR> argument
    of a `kernel_keyring.py exec <name> <ENV_VAR> --` (that argument is never a reference). Matching
    the argument's own span, not subtracting a count, keeps any other mention, at any depth, visible."""
    name = rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])"
    arguments = [match.span(1) for match in re.finditer(
        rf"(?<![^\s/]){re.escape(KEYRING_SCRIPT)}\s+exec\s+[^\s;&|()<>]+\s+({name})\s+--(?=\s|$)", text)]
    return any(not any(start <= match.start() < end for start, end in arguments)
               for match in re.finditer(name, text))


def keyring_reason(texts: tuple[str, str], words_list: list[list[str]]) -> str | None:
    """Payload reads in inline code, and what a keyring exec's command does with the key it inherits.
    `texts` is the command as written and unquoted(); every pattern reads both."""
    def found(pattern: re.Pattern[str]) -> bool:
        return any(pattern.search(text) for text in texts)

    if any(INTERPRETER.fullmatch(program_of(words)) for words in words_list) and found(KEYRING_READ_CODE):
        return "keyring_payload_read"
    started = [parsed for parsed in map(keyring_exec, words_list) if parsed is not None]
    # Any mention of an injected variable except exec's own <ENV_VAR> argument names it: in the started
    # command, in code piped into it or in a here-document it reads.
    if any(mentions_injected_variable(texts[1], variable) for variable in {name for name, _ in started if name}):
        return "keyring_variable_reference"
    for _variable, started_command in started:
        inner = expand(shlex.join(started_command)) if started_command else []
        # The started command, and the commands among its arguments that a launcher the guard does not
        # model would run (launched_commands). The price: a one-word query `env` is blocked too.
        inner += launched_commands(inner)
        if any(dumps_after_source(words) for words in inner):
            return "environment_dump_in_keyring_exec"
        programs = {program_of(words) for words in inner}
        if (any(INTERPRETER.fullmatch(program) for program in programs) or programs & AWKS) \
                and found(KEYRING_ENVIRONMENT_ACCESS):
            return "environment_dump_in_keyring_exec"
        if (programs & JQS and found(JQ_ENVIRONMENT)) or (programs & SHELLS and found(SHELL_INDIRECTION)):
            return "environment_dump_in_keyring_exec"
    return None


def segment_reason(words: list[str]) -> str | None:
    program = program_of(words)
    if is_environment_dump(words):
        return "environment_dump"
    if prints_helper_credential(words) or tvly_prints_key(words):
        return "native_token_print"
    if program == "keyctl" and keyctl_reads_payload(words):
        return "keyring_payload_read"
    if program in TRACERS:
        return "process_trace"
    if any(word in {"<", "<<<", "<>"} and position + 1 < len(words) and POINTER_VARIABLE.search(words[position + 1])
           for position, word in enumerate(words)):
        return "credential_file_read"
    arguments = reader_arguments(words)
    if arguments is None:
        return None
    if any(POINTER_VARIABLE.search(w) for w in arguments):
        return "credential_file_read"
    if any(HF_HOME_ROOT.search(w) for w in arguments):
        return "native_store_path"
    if any(is_env_file_word(w) for w in arguments):
        return "dotenv_read"
    if any(SECRET_NAME.search(w) for w in arguments):
        return "secret_name_search"
    return None


def check(command: str) -> str | None:
    # The shell removes a backslash-newline before it splits words, so the rules read the joined command.
    # Each text pattern also reads it without quoting: `sh -c 'echo $GH_TO''KEN'` hands the inner shell
    # `echo $GH_TOKEN`. (Where quoting does end a name, as in `"$GH_TO"KEN`, that errs toward blocking.)
    command = command.replace("\\\n", "")
    texts = (command, unquoted(command))
    for text in texts:
        for pattern, reason in STORE_PATHS:
            if pattern.search(text):
                return reason
        if PROC_WORD.search(text) and re.search(r"\benviron\b", text):
            return "process_environment"
        if SECRET_EXPANSION.search(text) or SECRET_LOOKUP.search(text):
            return "secret_variable_reference"
    words_list = expand(command)
    reason = keyring_reason(texts, words_list)
    if reason:
        return reason
    if any(sources_credential_file(words) for words in words_list):
        if any("xtrace" in text or re.search(r"\bSHELLOPTS=", text) for text in texts) \
                or any(traces(words) for words in words_list):
            return "trace_while_sourcing"
        if any(ENVIRONMENT_ACCESS.search(text) for text in texts) \
                or any(dumps_after_source(words) for words in words_list):
            return "environment_dump_after_source"
    for words in words_list:
        reason = segment_reason(words)
        if reason:
            return reason
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        print("secret_path_guard: unreadable hook input", file=sys.stderr)
        return 1
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0
    reason = check(command)
    if reason is None:
        return 0
    hint = HINTS.get(reason)
    print(f"secret_path_guard: blocked ({reason}). " + (f"{hint[0].upper()}{hint[1:]}. " if hint else "")
          + "Credential stores and secret variables stay out of agent commands; pass pointer variables "
          "such as --env-file \"$PAPER_ENV_FILE\" to a loader and see docs/secret-storage.md.",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
