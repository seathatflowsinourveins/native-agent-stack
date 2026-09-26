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
`pipe`, `read` and `dh_compute`, and a keyring read in inline interpreter
code), checks the command that `kernel_keyring.py exec` or `tvly-keyring`
starts with every rule above, and blocks that command when it names the
injected variable or dumps the environment it inherits. It is not a
security boundary. A process that imports a loader, or a renamed or
obfuscated path, passes; see docs/secret-storage.md "Threat model" for the
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
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SOURCERS = {".", "source"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
COPIERS = {"cp", "scp", "rsync"}
REDIRECT_OUT = re.compile(r"^\d*(?:>|>>|>\||&>|&>>)$")
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
# Inline code that reads a payload: the operation's name, libkeyutils' and python-keyutils' readers,
# this repository's keyring module, a raw keyctl system call (x86_64 250, aarch64 219) with
# operation 11 (KEYCTL_READ), or keyctl(1) run as a subprocess. Checked only when the command runs an
# interpreter (INTERPRETER), so a commit message or a code search that mentions KEYCTL_READ passes.
KEYRING_READ_CODE = re.compile(
    r"\bKEYCTL_READ\b|\bkeyctl_read(?:_alloc)?\s*\(|\bkeyutils\s*\.\s*read_key\b"
    r"|\b(?:import|from)\s+(?:scripts\s*\.\s*)?kernel_keyring\b"
    r"|\bsyscall\s*\(\s*(?:[\w.]*c_u?(?:long|int)\s*\(\s*)?(?:250|219)\b[^;\n]{0,40}?\b11\b"
    r"|\bkeyctl[\"',\s]+(?:print|pipe|read|dh_compute)\b")
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


def strip_prefix(words: list[str]) -> list[str]:
    index = 0
    while index < len(words):
        word = words[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word == "$":
            index += 1
        elif word in WRAPPERS:
            index += 1
        elif word == "timeout":
            index += 2
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


def keyring_exec(words: list[str]) -> tuple[str | None, list[str], bool] | None:
    """(injected variable, started command, variable spelled in the command) for a keyring exec.

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
            return (variable if variable and ENV_NAME.fullmatch(variable) else None,
                    arguments[separator + 1:], True)
        if name in KEYRING_WRAPPERS and (position == 0 or program_of(words) in SHELLS):
            variable, target = KEYRING_WRAPPERS[name]
            return variable, [target, *words[position + 1:]], False
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
    (tavily-cli 0.1.8 commands/auth.py); `tvly auth --json` and `tvly --json auth` print no key."""
    positional = [w for w in words[1:] if not w.startswith("-")]
    return program_of(words) == "tvly" and positional[:1] == ["auth"] \
        and "--json" not in words[1:] and "--help" not in words[1:]


def keyring_reason(command: str, words_list: list[list[str]]) -> str | None:
    """Payload reads in inline code, and what a keyring exec's command does with the key it inherits."""
    if any(INTERPRETER.fullmatch(program_of(words)) for words in words_list) and KEYRING_READ_CODE.search(command):
        return "keyring_payload_read"
    started = [parsed for parsed in map(keyring_exec, words_list) if parsed is not None]
    # Each `kernel_keyring.py exec` spells its variable once; any further mention names it, whether
    # in the started command, in code piped into it or in a here-document it reads.
    for variable in {variable for variable, _command, _spelled in started if variable}:
        spelled = sum(1 for other, _command, is_spelled in started if other == variable and is_spelled)
        if len(re.findall(rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])", command)) > spelled:
            return "keyring_variable_reference"
    for _variable, started_command, _spelled in started:
        inner = expand(shlex.join(started_command)) if started_command else []
        # A dump in program position, or env or printenv as another program's argument, which is how a
        # launcher the guard does not model (find -exec, stdbuf, watch ...) would run it.
        if any(dumps_after_source(words) or any(program_of([word]) in ENVIRONMENT_PRINTERS for word in words[1:])
               for words in inner):
            return "environment_dump_in_keyring_exec"
        programs = {program_of(words) for words in inner}
        if (any(INTERPRETER.fullmatch(program) for program in programs) or programs & AWKS) \
                and KEYRING_ENVIRONMENT_ACCESS.search(command):
            return "environment_dump_in_keyring_exec"
        if (programs & JQS and JQ_ENVIRONMENT.search(command)) \
                or (programs & SHELLS and SHELL_INDIRECTION.search(command)):
            return "environment_dump_in_keyring_exec"
    return None


def segment_reason(words: list[str]) -> str | None:
    program = program_of(words)
    if is_environment_dump(words):
        return "environment_dump"
    if prints_helper_credential(words) or tvly_prints_key(words):
        return "native_token_print"
    if program == "keyctl" and next((w for w in words[1:] if not w.startswith("-")), None) in KEYCTL_PAYLOAD_COMMANDS:
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
    for pattern, reason in STORE_PATHS:
        if pattern.search(command):
            return reason
    if PROC_WORD.search(command) and re.search(r"\benviron\b", command):
        return "process_environment"
    if SECRET_EXPANSION.search(command) or SECRET_LOOKUP.search(command):
        return "secret_variable_reference"
    words_list = expand(command)
    reason = keyring_reason(command, words_list)
    if reason:
        return reason
    if any(sources_credential_file(words) for words in words_list):
        if "xtrace" in command or re.search(r"\bSHELLOPTS=", command) \
                or any(traces(words) for words in words_list):
            return "trace_while_sourcing"
        if ENVIRONMENT_ACCESS.search(command) or any(dumps_after_source(words) for words in words_list):
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
