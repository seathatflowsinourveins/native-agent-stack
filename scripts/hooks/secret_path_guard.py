#!/usr/bin/env python3
"""Claude Code PreToolUse guard for Bash: block obvious credential exposure.

Reads only the hook's stdin JSON (tool_input.command). It never opens a file,
never reads the environment and never prints the command. Exit 2 blocks the
call and returns a one-line reason code on stderr (documented PreToolUse
behaviour); exit 0 lets it continue.

This is a deterministic text heuristic that stops accidental exposure:
naming a credential store, dumping the environment, echoing a secret
variable, tracing a process, printing a native token (including through a
git credential helper), reading or searching
credential files or secret variable names, tracing a shell while it sources a
credential file, and dumping the environment after sourcing one. It is not a
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
    (re.compile(r"ecosystem-grafana\.env"), "service_secret_path"),
    (re.compile(r"nativestack/generation\.key"), "service_secret_path"),
    (re.compile(r"/proc/(?:[^/\s]+/)*environ\b"), "process_environment"),
    (re.compile(r"\bgh\s+auth\s+token\b"), "native_token_print"),
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
    "GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "CODEX_API_KEY", "OPENROUTER_API_KEY", "MISTRAL_API_KEY", "QDRANT_API_KEY",
    "PREFECT_API_KEY", "MC_API_KEY", "MSB_API_KEY", "PAPERCLIP_API_KEY",
    "TWS_USERNAME", "TWS_PASSWORD", "TWS_ACCOUNT", "IBKR_ACCOUNT_ID",
)
_NAMES = "|".join(SECRET_NAMES)
SECRET_NAME = re.compile(r"\b(?:" + _NAMES + r")\b")
SECRET_EXPANSION = re.compile(r"\$\{?!?(?:" + _NAMES + r")\b")
SECRET_LOOKUP = re.compile(r"(?:environ|getenv|process\.env|ENV\[)[^;\n]{0,40}\b(?:" + _NAMES + r")\b")
POINTER_VARIABLE = re.compile(r"\$\{?(?:PAPER_ENV_FILE|ENV_FILE|SEC_CONTACT_ENV|PIT_ALPACA_ENV_PATH|PIT_SEC_ENV_PATH)\b")
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

HINTS = {
    "secret_name_search": "search repository code with the Grep tool instead of a shell search for a "
                          "secret variable name",
    "trace_while_sourcing": "shell tracing prints every assignment of a sourced credential file",
    "environment_dump_after_source": "after sourcing a credential file the environment holds its values",
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


def expand(command: str, depth: int = 0) -> list[list[str]]:
    """Command segments, including those of `sh -c '...'`, `eval ...` and `env ... command`."""
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


def segment_reason(words: list[str]) -> str | None:
    program = program_of(words)
    if is_environment_dump(words):
        return "environment_dump"
    if prints_helper_credential(words):
        return "native_token_print"
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
