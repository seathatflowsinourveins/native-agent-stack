#!/usr/bin/env python3
"""Claude Code PreToolUse guard for Bash: block obvious credential exposure.

Reads only the hook's stdin JSON (tool_input.command). It never opens a file,
never reads the environment and never prints the command. Exit 2 blocks the
call and returns a one-line reason code on stderr (documented PreToolUse
behaviour); exit 0 lets it continue.

This is a text heuristic that stops accidental exposure: naming a credential
store, dumping the environment, echoing a secret variable, tracing a process,
or printing a native token. It is not a security boundary. A process that
imports a loader, or a renamed or obfuscated path, passes; see
docs/secret-storage.md "Threat model" for the residual risk.
"""

from __future__ import annotations

import json
import re
import shlex
import sys


STORE_PATHS = (
    (re.compile(r"\.config/native-agent-stack(?:/|\b)"), "credential_store_path"),
    (re.compile(r"\.claude/\.credentials\.json"), "native_store_path"),
    (re.compile(r"(?:\.codex|CODEX_HOME\}?)/auth\.json"), "native_store_path"),
    (re.compile(r"gh/hosts\.yml"), "native_store_path"),
    (re.compile(r"ecosystem-grafana\.env"), "service_secret_path"),
    (re.compile(r"nativestack/generation\.key"), "service_secret_path"),
    (re.compile(r"/proc/[^/\s]+/environ"), "process_environment"),
    (re.compile(r"\bgh\s+auth\s+token\b"), "native_token_print"),
    (re.compile(r"--show-token\b"), "native_token_print"),
    (re.compile(r"\bgh\s+auth\s+status\b[^;&|\n]*\s-t\b"), "native_token_print"),
    (re.compile(r"\bsecurity\s+(?:find-generic-password|find-internet-password|dump-keychain)\b"), "keychain_read"),
    (re.compile(r"\bsecret-tool\s+lookup\b"), "keychain_read"),
)
SECRET_NAMES = (
    "APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY",
    "DATABENTO_API_KEY", "TYPESAFE_API_KEY", "OMNIROUTE_API_KEY",
    "GF_SECURITY_ADMIN_PASSWORD", "GF_SECURITY_SECRET_KEY",
    "GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "CODEX_API_KEY", "TWS_PASSWORD",
)
_NAMES = "|".join(SECRET_NAMES)
SECRET_EXPANSION = re.compile(r"\$\{?!?(?:" + _NAMES + r")\b")
SECRET_LOOKUP = re.compile(r"(?:environ|getenv|process\.env|ENV\[)[^;\n]{0,40}\b(?:" + _NAMES + r")\b")
POINTER_VARIABLE = re.compile(r"\$\{?(?:PAPER_ENV_FILE|ENV_FILE|SEC_CONTACT_ENV|PIT_ALPACA_ENV_PATH|PIT_SEC_ENV_PATH)\b")
READERS = {
    "cat", "tac", "nl", "head", "tail", "less", "more", "bat", "batcat", "view", "vi", "vim", "nano",
    "grep", "egrep", "fgrep", "rg", "ag", "sed", "awk", "gawk", "cut", "sort", "uniq", "paste",
    "xxd", "od", "hexdump", "strings", "base64", "base32", "cp", "scp", "rsync", "tee", "diff",
    "cmp", "openssl", "gpg", "age", "curl", "wget", "nc", "ncat", "socat", "jq", "yq", "dd",
}
TRACERS = {"strace", "ltrace", "gdb", "bpftrace"}
WRAPPERS = {"sudo", "doas", "command", "builtin", "exec", "nohup", "time", "nice", "stdbuf",
            "xargs", "setsid", "ionice", "chronic"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
DOTENV = re.compile(r"^\.env(?:\..+)?$")
PS_BSD_CLUSTER = re.compile(r"^[aAcfhjlmrsStTuvwxXLn]*e[aAcefhjlmrsStTuvwxXLn]*$")
PS_ARG_OPTIONS = {"-o", "-O", "-p", "-u", "-U", "-C", "-g", "-G", "-t", "-q", "-s", "-k",
                  "--pid", "--format", "--sort", "--ppid", "--user"}
ENV_ARG_OPTIONS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}


def tokenize(command: str) -> list[str]:
    text = command.replace("`", " ; ").replace("\n", " ; ")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return re.findall(r"[;&|()]+|[^\s;&|()]+", text)


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


def env_dumps(words: list[str]) -> bool:
    index = 1
    while index < len(words):
        word = words[index]
        if word in ENV_ARG_OPTIONS:
            index += 2
        elif word.startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            index += 1
        else:
            return False
    return True


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


def segment_reason(words: list[str], depth: int) -> str | None:
    words = strip_prefix(words)
    if not words:
        return None
    program = words[0].rsplit("/", 1)[-1]
    if program == "printenv":
        return "environment_dump"
    if program == "env" and env_dumps(words):
        return "environment_dump"
    if program in {"set", "export"} and (len(words) == 1 or words[1:] == ["-p"]):
        return "environment_dump"
    if program in {"declare", "typeset"} and all(w.startswith("-") for w in words[1:]) \
            and (len(words) == 1 or any(set(w[1:]) & set("xp") for w in words[1:])):
        return "environment_dump"
    if program == "ps" and ps_shows_environment(words):
        return "environment_dump"
    if program in TRACERS:
        return "process_trace"
    if program in READERS and any(POINTER_VARIABLE.search(w) for w in words[1:]):
        return "credential_file_read"
    if program in READERS and any(DOTENV.match(w.rsplit("/", 1)[-1]) and not w.endswith(".example")
                                  for w in words[1:]):
        return "dotenv_read"
    if program in SHELLS and depth < 3:
        for position, word in enumerate(words[:-1]):
            if word == "-c":
                return check(words[position + 1], depth + 1)
    return None


def check(command: str, depth: int = 0) -> str | None:
    for pattern, reason in STORE_PATHS:
        if pattern.search(command):
            return reason
    if SECRET_EXPANSION.search(command) or SECRET_LOOKUP.search(command):
        return "secret_variable_reference"
    for words in segments(tokenize(command)):
        reason = segment_reason(words, depth)
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
    print(f"secret_path_guard: blocked ({reason}). Credential stores and secret variables stay out of "
          "agent commands; pass pointer variables such as --env-file \"$PAPER_ENV_FILE\" to a loader "
          "and see docs/secret-storage.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
