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
Hugging Face home or a home or tool credential store (anything in the SSH,
GnuPG, AWS, Azure, kube, OmniRoute, Codex shell-snapshot and OpenHands
runtime-worker secrets directories, the Docker home as a whole, the Docker,
git-credential, netrc, npm and PyPI files, and nativestack key files: every
path the settings template's Read denies cover, which on a host running RTK's
hook is how `cat` of them stays blocked after RTK rewrites it to `rtk read`),
tracing a shell while it sources a credential file, and dumping the
environment after sourcing one. Every rule
also reads the command that an `rtk` invocation runs (`rtk proxy cat F`,
`rtk read F`, `rtk run -c '...'`) and the command that `systemd-run`, `run0`,
`systemd-inhibit` or `systemd-cat` starts (their own options are skipped as
getopt reads them, and a secret variable set through `systemd-run`'s
`-E`/`--setenv` or `-p Environment=` is blocked: `-E NAME=value` is in the
process listing while it runs, `-E NAME` forwards the caller's value, and either
ends in the unit's Environment property, which any bus client can read over the
user bus), and the body
of a command substitution inside double quotes (`echo "$(printenv)"` runs
printenv; single quotes, an ANSI-C string and a `#` comment stay data). A
here-document's lines are command lines like any other, whatever its delimiter
and whatever receives it, so a commit message written through
`"$(cat <<'EOF' ... EOF)"` whose prose has a line that reads as a dump is
refused: write the text with the Write tool and pass `git commit -F FILE`
(docs/secret-storage.md). `ps -E` (macOS) and `systemctl show-environment` or a bare
`systemctl show` (a service manager's whole environment block) dump the
environment like `ps e` and `env`; `ps` is read as procps (Linux) and as macOS
read it, and as the guard at c26800f3 read it (a dashless word of its cluster
alphabet with an `e` blocks after any cluster, since a procps personality can
parse `ps -axu e` BSD-style), and any reading that shows the environment blocks
(`-C` takes a command name on one host and is a flag on the other). For a key
held in the Linux kernel keyring it blocks payload reads (`keyctl print`,
`pipe`, `read` and `dh_compute`, `keyctl list` or `rlist` on anything but an
unambiguous keyring, and a keyring read in inline interpreter code), checks
the command that `kernel_keyring.py exec` or `tvly-keyring` starts with every
rule above, and blocks that command when it names the injected variable or
dumps the environment it inherits, also behind a launcher's options
(`stdbuf -o0`) or a launcher the guard does not model (`watch`, `flock`).
The words of a command are read twice: as this version reads them and, when
that reading allows the command, as the guard at c26800f3 read them
(prior_reading); a command that either reading refuses is refused, so no command
that guard refused passes (tightening only, by construction).
A backslash-newline is joined first and every raw-text rule also reads the
command after the shell's quote removal, so a name split by quotes, a
backslash or a line continuation is still that name; redirection operands
are never taken for arguments. An internal error blocks the command (`guard_error`), because only exit 2
blocks; a hook that outlasts its timeout does not, so every scan reads a text once, a command of more than
200,000 characters is refused (`command_too_large`), and check() reads a command inside a work budget
(WORK_LIMITS: characters passed to shlex at their storage width, texts read, words emitted, launched-command
reads) and raises WorkBudgetExceeded when it is gone, which main() refuses (`command_too_complex`); see
docs/secret-storage.md, "An internal error blocks; a timeout does not". It is not a security boundary. A process
that imports a loader, a name assembled at run time, or a renamed or
obfuscated path passes; see docs/secret-storage.md "Threat model" for the
residual risk.

The same file is installed for every session on a host as
~/.claude/hooks/secret_path_guard.py by tools/adoption/install_claude_profile.py
(sha256-pinned in adoption/hooks/claude/SHA256SUMS).
"""

from __future__ import annotations

import bisect
import json
import re
import shlex
import sys


class LinearScan:
    """A text rule whose regular expression backtracks on a repeated prefix, answered by a scan that reads the text a bounded number of
    times: search(text) is True exactly when re.search(pattern, text) finds a match (tests/test_secret_path_guard.py compares the two on
    generated texts). Four STORE_PATHS patterns have an unbounded run after a literal that a text can repeat, and the regular expression
    engine reads that run again from every repeat: 102,016 characters of `XDG_CONFIG_HOME:-` took 11.9 s, 54,000 of `HF_HOME:-` 13 to 14 s
    and 80,000 of `/proc` 13 to 15 s (third verification review, 2026-09-29), past a hook timeout of 10 s that fails open, before any work
    budget was charged. Each scan below splits the text once into the runs the pattern cannot cross and searches each run for literals."""
    __slots__ = ("pattern", "_scan")

    def __init__(self, pattern: str, scan) -> None:
        self.pattern = pattern
        self._scan = scan

    def search(self, text: str) -> bool:
        return self._scan(text)


# A `${NAME:-default}` default (`[^}\s]*`) cannot cross a `}` or a blank, so a match that has one lies in one run of neither, plus the `}`
# that ends the run. A path in `/proc/(?:[^/\s]+/)*environ` cannot cross a blank or `//` (its components are not empty), so a match lies in
# one run of neither (PATH_RUN keeps a `/` only when another does not follow it).
DEFAULT_RUN = re.compile(r"[^}\s]+")
PATH_RUN = re.compile(r"(?:[^\s/]|/(?!/))+")
XDG_STORE_PLAIN = re.compile(r"XDG_CONFIG_HOME\}?/native-agent-stack(?:/|\b)")
XDG_STORE_TAIL = re.compile(r"/native-agent-stack(?:/|\b)")
HF_TOKEN_PLAIN = re.compile(r"(?:huggingface|HF_HOME)\}?[\"']?/(?:token|stored_tokens)(?![\w-])")
HF_TOKEN_TAIL = re.compile(r"[\"']?/(?:token|stored_tokens)(?![\w-])")
ENVIRON_TAIL = re.compile(r"/environ\b")
GH_STATUS_HEAD = re.compile(r"\bgh\s+auth\s+status\b")
GH_STATUS_FLAG = re.compile(r"\s-t\b")
GH_STATUS_STOP = re.compile(r"[;&|\n]")


def default_run_scan(text: str, plain: re.Pattern[str], head: str, tail: re.Pattern[str]) -> bool:
    """NAME(?::-[^}\\s]*)?\\}?TAIL, where `plain` is the pattern without the default and `head` is `NAME:-`: plain anywhere, or head in a
    run with tail after it in the same run (the default ends inside the run, and a `}` cannot come before the tail there), or head in a
    run that a `}` ends and tail right after that `}`. The first head of a run leaves the most room, and a match inside a run is a match
    in the text, since the character after a run is a `}` or a blank, which ends a word as the end of the run does."""
    if plain.search(text):
        return True
    for run in DEFAULT_RUN.finditer(text):
        start = text.find(head, run.start(), run.end())
        if start >= 0 and (tail.search(text, start + len(head), run.end())
                           or (text.startswith("}", run.end()) and tail.match(text, run.end() + 1))):
            return True
    return False


def proc_environ_scan(text: str) -> bool:
    """/proc/(?:[^/\\s]+/)*environ\\b: a `/proc/` and, at or after its last slash in the same path run, `/environ` ending a word. Within a
    run every component is non-empty and blank-free, so any `/environ` after the first `/proc/` completes a match."""
    for run in PATH_RUN.finditer(text):
        start = text.find("/proc/", run.start(), run.end())
        if start >= 0 and ENVIRON_TAIL.search(text, start + 5, run.end()):
            return True
    return False


def gh_status_token_scan(text: str) -> bool:
    """\\bgh\\s+auth\\s+status\\b[^;&|\\n]*\\s-t\\b: after some `gh auth status`, the first ` -t` flag comes no later than the first `;`, `&`,
    `|` or newline (a flag's blank may be that newline). Heads cannot overlap, nor can flags."""
    heads = [match.end() for match in GH_STATUS_HEAD.finditer(text)]
    if not heads:
        return False
    flags = [match.start() for match in GH_STATUS_FLAG.finditer(text)]
    stops = [match.start() for match in GH_STATUS_STOP.finditer(text)]
    for end in heads:
        at = bisect.bisect_left(flags, end)
        if at == len(flags):
            return False  # no flag after this head, nor after any later one
        stop = bisect.bisect_left(stops, end)
        if flags[at] <= (stops[stop] if stop < len(stops) else len(text)):
            return True
    return False


STORE_PATHS = (
    (re.compile(r"\.config/native-agent-stack(?:/|\b)"), "credential_store_path"),
    (LinearScan(r"XDG_CONFIG_HOME(?::-[^}\s]*)?\}?/native-agent-stack(?:/|\b)",
                lambda text: default_run_scan(text, XDG_STORE_PLAIN, "XDG_CONFIG_HOME:-", XDG_STORE_TAIL)), "credential_store_path"),
    (re.compile(r"\.claude/\.credentials\.json"), "native_store_path"),
    (re.compile(r"(?:\.codex|CODEX_HOME\}?)/auth\.json"), "native_store_path"),
    (re.compile(r"gh/hosts\.yml"), "native_store_path"),
    # Hugging Face token files: the default home, $XDG_CACHE_HOME/huggingface, $HF_HOME or a
    # ${HF_HOME:-...} form, a closing quote allowed before the slash; tokenizers/ and hub/ pass.
    (LinearScan(r"(?:huggingface|HF_HOME(?::-[^}\s]*)?)\}?[\"']?/(?:token|stored_tokens)(?![\w-])",
                lambda text: default_run_scan(text, HF_TOKEN_PLAIN, "HF_HOME:-", HF_TOKEN_TAIL)), "native_store_path"),
    # tavily-cli's own store (`tvly login` or `tvly init` write the key or an OAuth token there).
    (re.compile(r"\.tavily/config\.json"), "native_store_path"),
    (re.compile(r"ecosystem-grafana\.env"), "service_secret_path"),
    (re.compile(r"nativestack/generation\.key"), "service_secret_path"),
    (LinearScan(r"/proc/(?:[^/\s]+/)*environ\b", proc_environ_scan), "process_environment"),
    (re.compile(r"\bgh\s+auth\s+token\b"), "native_token_print"),
    (re.compile(r"\bhf\s+auth\s+token\b"), "native_token_print"),
    (re.compile(r"\bhuggingface-cli\s+(?:auth\s+)?token\b"), "native_token_print"),
    (re.compile(r"--show-token\b"), "native_token_print"),
    (LinearScan(r"\bgh\s+auth\s+status\b[^;&|\n]*\s-t\b", gh_status_token_scan), "native_token_print"),
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
    # The variable of the `canary-e2e` inventory entry (a disposable synthetic proof key: class test_canary, status test_only), listed
    # ahead of that entry so the inventory tie test holds when it lands; it is refused like every other name.
    "CANARY_E2E_KEY",
)
_NAMES = "|".join(SECRET_NAMES)
SECRET_NAME = re.compile(r"\b(?:" + _NAMES + r")\b")
SECRET_EXPANSION = re.compile(r"\$\{?!?(?:" + _NAMES + r")\b")
SECRET_LOOKUP = re.compile(r"(?:environ|getenv|process\.env|ENV\[)[^;\n]{0,40}\b(?:" + _NAMES + r")\b")
# Every inventory `pointer_variables` name (tests/test_secret_path_guard.py checks each), with an optional numeric suffix: a
# further paper account's pointer is PAPER_ENV_FILE_2. Without the suffix group the word boundary after PAPER_ENV_FILE failed
# before `_2`, so a reader, a redirect or a `source` on "$PAPER_ENV_FILE_2" passed while the account-1 forms were blocked.
POINTER_VARIABLE = re.compile(
    r"\$\{?(?:PAPER_ENV_FILE|ENV_FILE|SEC_CONTACT_ENV|PIT_ALPACA_ENV_PATH|PIT_SEC_ENV_PATH|HF_TOKEN_PATH)(?:_[0-9]+)?\b")
# The Hugging Face home itself (or everything in it) as a reader's operand: a recursive search or a
# copy of it includes both token files. Its subdirectories such as hub/ stay readable.
HF_HOME_ROOT = re.compile(r"(?:(?:\.cache|XDG_CACHE_HOME)\}?/huggingface\}?|^\$\{?HF_HOME\}?)(?:/\**)?$")
# Home and tool credential stores as a reader's operand (2026-09-27): every path the settings template's
# credential-store Read denies cover. That is anything in an SSH, GnuPG, AWS, Azure or kube directory, an OmniRoute
# data directory (~/.omniroute, ~/.config/omniroute, and Windows' AppData/Roaming/omniroute reached from WSL2), a
# Codex `shell_snapshots` directory, whose files record every exported value (`declare -xp`, codex-rs
# shell-command/src/shell_snapshot_exports.rs at rust-v0.157.1), or the OpenHands runtime-worker secrets directory
# (2026-09-28: `runtime-workers/openhands/secrets` in the stack's state directory, where the host driver of PR #425
# writes each attempt's agent-server session key to <run-id>-<arm>.server.env and <run-id>-<arm>.headers), each
# directory itself and a glob in it; the Docker, git-credential, netrc, npm and PyPI files, also as an option's `=`
# value; any key file in a `nativestack` directory (Read(~/.config/nativestack/*.key); STORE_PATHS blocks every
# mention of generation.key); and the Docker home itself or a glob over its top level, which reaches config.json (as
# HF_HOME_ROOT does for the Hugging Face home). On a host that runs RTK's Claude hook this rule is what stops `cat`,
# `head` and `tail -n` of those paths: rtk 0.50.0 rewrites them to `rtk read` (src/discover/rules.rs), Claude Code
# evaluates its permission rules against the rewritten command, and RTK's own deny gate loads only Bash(...) rules
# (src/hooks/permissions.rs, append_bash_rules). Only a reader, copy or search is blocked, never a mention, so
# `ssh -i`, `ssh-add`, `kubectl --kubeconfig`, `chmod`, `stat` and `ls` on the same paths still pass in every session,
# and a search's own pattern is not taken for a file it reads (search_paths). tests/test_secret_path_guard.py derives
# a reader of every template Read deny and expects a block.
HOME_CREDENTIAL_STORE = re.compile(
    r"(?:^|[/=])(?:\.ssh|\.gnupg|\.aws|\.azure|\.kube|\.omniroute|\.config/omniroute|AppData/Roaming/omniroute"
    r"|shell_snapshots|runtime-workers/openhands/secrets)(?:/|$)"
    r"|(?:^|[/=])(?:\.docker/config\.json|\.git-credentials|\.netrc|\.npmrc|\.pypirc|nativestack/[^/]*\.key)$"
    r"|(?:^|[/=])\.docker(?:/\**)?$")
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
# sudo, where a bare -h is --help; the doas(1) synopsis on man.openbsd.org; bash `help exec`) and, from
# 2026-09-29, systemd-run (below). Other options are boolean.
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
    # systemd-run(1), read 2026-09-29 from the option table of src/run/run.c at systemd v255 (getopt string
    # "+hrH:M:E:p:tPqGdSu:": the leading `+` ends the options at the first word that is no option): -H, -M, -E, -p, -u
    # and these long options take a value; --user --system --scope --no-block --wait --pty --pipe --quiet --collect
    # --same-dir --shell --slice-inherit --send-sighup --remain-after-exit --no-ask-password and the two --on-*-change
    # switches do not. The tail adds the value options of later releases, each read in run.c at the tag that first has it:
    # --capsule/-C and --background (v256), --json (v257), --job-mode (v258), --root-directory (v259), --output (v261), so a
    # newer host's `--background red cat F` still finds its command.
    "systemd-run": {
        "-u", "-p", "-E", "-H", "-M", "-C",
        "--unit", "--property", "--setenv", "--host", "--machine", "--description", "--slice", "--uid", "--gid",
        "--nice", "--working-directory", "--service-type", "--expand-environment", "--on-active", "--on-boot",
        "--on-startup", "--on-unit-active", "--on-unit-inactive", "--on-calendar", "--timer-property",
        "--path-property", "--socket-property",
        "--capsule", "--background", "--json", "--job-mode", "--output", "--root-directory"},
    # run0 (systemd 256 and later, src/run/run.c parse_argv_sudo_mode, getopt string "+hVu:g:D:" and "+hVu:g:D:i" from v258; the
    # options at v256 to v262): -u, -g, -D and the long options below take a value, everything else (--pipe --pty --pty-late
    # --via-shell --login --empower --same-root-dir --no-ask-password --slice-inherit -i -n -k -K -v) does not.
    "run0": {
        "-u", "-g", "-D",
        "--user", "--group", "--chdir", "--unit", "--property", "--description", "--slice", "--nice", "--setenv", "--background",
        "--machine", "--shell-prompt-prefix", "--lightweight", "--area"},
    # systemd-inhibit (src/login/inhibit.c, getopt string "+h") and systemd-cat (src/journal/cat.c, "+ht:p:"), systemd 255 to 262.
    "systemd-inhibit": {"--what", "--who", "--why", "--mode"},
    "systemd-cat": {"-t", "-p", "--identifier", "--priority", "--stderr-priority", "--level-prefix", "--namespace"},
    # systemctl(1), read 2026-09-29 from src/systemctl/systemctl.c at systemd v255 (getopt string "ht:p:P:alqfs:H:M:n:o:iTr.::",
    # no leading `+`, so options and the verb may come in any order): -t, -p, -P, -s, -H, -M, -n and -o take a value, and so do
    # these long options; the last line adds --capsule/-C (v256) and --kill-subgroup (v258). It is not a launcher: the table
    # only lets systemctl_call() tell a verb and its arguments from an option's value.
    "systemctl": {
        "-t", "-p", "-P", "-s", "-H", "-M", "-n", "-o", "-C",
        "--type", "--property", "--signal", "--host", "--machine", "--lines", "--output", "--boot-loader-entry",
        "--boot-loader-menu", "--check-inhibitors", "--drop-in", "--image", "--image-policy", "--job-mode", "--kill-value",
        "--kill-who", "--kill-whom", "--legend", "--message", "--preset-mode", "--reboot-argument", "--root", "--state",
        "--timestamp", "--what", "--when",
        "--capsule", "--kill-subgroup"},
}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
SOURCERS = {".", "source"}
FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
COPIERS = {"cp", "scp", "rsync"}
# RTK (rtk 0.50.0: `rtk --help` and each subcommand's --help, read 2026-09-27). `proxy`, `summary`, `err` and
# `test` run the command that follows their own flags; `run` hands its `-c`/`--command` string, or its arguments,
# to `sh -c`; `read`, `smart`, `json` and `log` read the files they name; every other subcommand runs the native
# program of the same name (`rtk grep`, `rtk rg`, `rtk find`, `rtk git`, `rtk diff`, `rtk curl`, `rtk env` ...).
# This hook runs beside RTK's Claude hook and reads the command as Claude wrote it (matching hooks run in
# parallel), so a typed `cat F` is caught before any rewrite; but agents also write rtk forms themselves (a re-run
# as `rtk proxy <command>`), so expand() reads the command an rtk invocation runs.
RTK_RUNNERS = {"proxy", "summary", "err", "test"}
RTK_RUN_FLAGS = {"--ultra-compact", "--skip-env"}
RTK_FILE_READERS = {"read", "smart", "json", "log"}
# Searches whose first positional argument is the pattern, not a file: grep(1) `grep [OPTION...] PATTERNS
# [FILE...]`, and rg(1), ag(1), ack(1), ugrep, zgrep and `git grep` share the shape, unless -e, -f, --regexp or
# --file supply the patterns. search_paths drops that argument only when nothing but clusters of these flags
# comes before it; each is a boolean flag of grep and rg, or takes a value that names no file (rg -r
# REPLACEMENT, -E ENCODING), so a file- or glob-selecting option (-f, -g, -t, --include ...) keeps every word.
SEARCHERS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "ugrep", "zgrep", "pcregrep", "pcre2grep"}
SEARCH_PLAIN_FLAGS = set("abcEFhHiIlLnNoPqrRsSUvwxz")
REDIRECT_OUT = re.compile(r"^\d*(?:>|>>|>\||&>|&>>|>&)$")
# Every redirection operator as shlex (punctuation_chars) splits it: `2>&1` is `2`, `>&`, `1`, and
# `<<-EOF` is `<<`, `-EOF`. The word after one is its file, descriptor or here-document delimiter.
REDIRECTION = re.compile(r"^\d*(?:>>?|>\||&>>?|<<<?|<>|<&|>&|<)$")
# What scan_shell() jumps to in each kind of frame (a regular expression finds the next such character). A `#` matters in command text
# only (cmd, sub, bt).
SCAN_CHARACTERS = {
    "cmd": re.compile(r"[\\'\"`$#]"),
    "bt": re.compile(r"[\\'\"`$#]"),
    "sub": re.compile(r"[\\'\"`$#()]"),
    "dq": re.compile(r"[\\\"`$]"),
    "param": re.compile(r"[\\'\"`$}]"),
    "dparam": re.compile(r"[\\\"`$}]"),
    "arith": re.compile(r"[\\'\"`$()]"),
}
# shlex reads a text one character at a time and appends each to the word it builds, which copies the word: one unquoted word of 199,000
# characters took 0.53 s in shlex alone (2026-09-30 repair round, measured on the store-path shapes of the third verification review). A
# text with no quote and no backslash is split by shlex's state machine (posix, punctuation_chars, whitespace_split; shlex.py read_token)
# exactly as SHLEX_PLAIN splits it: its four blanks end a word, a run of its punctuation characters is a word of its own, and every other
# character belongs to a word; in the legacy reading a `#` starts a comment that runs to the end of the text (lex has turned every newline
# into `;`). tests/test_secret_path_guard.py compares the two on generated texts.
SHLEX_PLAIN = re.compile(r"[();<>|&]+|[^ \t\r\n();<>|&]+")
BACKQUOTE_ESCAPE = re.compile(r"\\([$`\\\"])")
ANSI_C_TAIL = re.compile(r"\\.|'", re.S)
LINE_END = re.compile(r"\n")
BACKQUOTE_COMMENT_END = re.compile(r"[\n`]")  # a comment in a backquote body ends with it (bash cuts the body out first)
PAREN_INPUT = re.compile(r"[()]+<")  # shlex joins punctuation that touches: `$(<f)` gives the token `(<`
PROTECTED_BACKQUOTE = "\ue000"  # stands for a backquote that tokenize() must not turn into `;`
COMMENT_BREAK = " \t\n;&|()<>"  # what may precede a `#` that starts a word (blanks and the shell's metacharacters)
GIT_ARG_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "|&", ";;"}
# The letters of a dashless BSD-style ps cluster (is_ps_bsd_cluster): the flags that the guard reads, `e` and `E` among them.
PS_BSD_LETTERS = frozenset("aAcefhjlmrsStTuvwxXLnE")
# The dashless cluster as the guard at c26800f3 read it (prior_ps_shows_environment): its letters with an `e`, wherever the word stands unless
# a stand-alone value option comes right before it. Linear (its first class has no `e`, so only the last quantifier backtracks, once).
PS_BSD_CLUSTER = re.compile(r"^[aAcfhjlmrsStTuvwxXLn]*e[aAcefhjlmrsStTuvwxXLn]*$")
# The options that take a value, alone (`-u steve`, `--sort pcpu`) or as the last letter of a cluster (`-fu steve`), on procps-ng: ps(1) 4.0.4
# lists `-C cmdlist`, `-G`, `-g`, `-O`, `-o`, `-p`, `-q`, `-s`, `-t`, `-U` and `-u` (and `k` for the BSD form). macOS's ps has no `-q`, `-s`
# or `-k`, and `-C` is a flag there ("Change the way the CPU percentage is calculated"): Apple adv_cmds ps/ps.c at 60bc9ebf, PS_ARGS
# `aACcdeEfg:G:hjLlMmO:o:p:rSTt:U:u:vwx` and `case 'C': rawcpu = 1`. ps_shows_environment reads a command line with each host's table, and
# with the reading of c26800f3 besides, which takes only the word after a stand-alone value option for a value (2026-09-29 repair round).
PS_ARG_OPTIONS = {"-o", "-O", "-p", "-u", "-U", "-C", "-g", "-G", "-t", "-q", "-s", "-k",
                  "--pid", "--format", "--sort", "--ppid", "--user"}
PS_MACOS_ARG_OPTIONS = PS_ARG_OPTIONS - {"-C"}
ENV_ARG_OPTIONS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
TRACE_OPTIONS = {"xtrace", "verbose"}
MAX_DEPTH = 3
# Levels of command substitution inside double quotes that expand() reads (substitution_bodies), and the work it
# spends on them: the characters of all the bodies it reads may total SUBSTITUTION_BUDGET_FACTOR times the command's
# length plus SUBSTITUTION_BUDGET_FLOOR, so pathological nesting cannot make the guard outlast its hook timeout (a hook
# that times out does not block the call). An ordinary command nests two or three levels of bodies far shorter than it.
MAX_SUBSTITUTION_NESTING = 32
SUBSTITUTION_BUDGET_FACTOR = 4
SUBSTITUTION_BUDGET_FLOOR = 65536
# The most characters main() reads (a longer command is refused as `command_too_large`, check() itself has no such limit). A PreToolUse
# command hook that runs past its timeout does not block the call (Claude Code hooks documentation, "Timeouts", read 2026-09-29: "A
# timed-out `command`, `http`, or `mcp_tool` hook doesn't block the tool call"), this hook's timeout is 10 s, and the tokenizer costs
# about 9 microseconds a character inside quotes: measured on this host on 2026-09-29, one quoted word of 1,000,000 characters took 10.2 to
# 13.0 s (base c26800f3 and this version alike, over several runs), 600,000 took 3.8 to 4.4 s, 500,000 took 2.9 to 3.3 s and 200,000 took
# 0.6 s. The limit is set where both tokenizer readings of a command (with and without shlex's comments) and the reading of what a
# substitution prints always run inside the timeout, so no reading is skipped above some length. Refusing what cannot be read in time
# fails closed where reading it would fail open.
MAX_COMMAND_CHARACTERS = 200_000
# The cap above bounds the size of a command, not the work of reading it: the second verification review found a command of 9,645
# characters that took 13 s (a keyring exec whose started command holds 1,200 interpreter words, every suffix of them read again, up to
# 5.8 million characters through shlex) and one of 195,068 characters that took over 25 s (four-byte characters cost four times as much to
# tokenize, and the text was read at each of five nesting levels, twice each). check() therefore spends from one budget per call, counted
# in units that do not depend on the host, and raises WorkBudgetExceeded when one counter is gone, which main() turns into a refusal
# (`command_too_complex`), the same way `command_too_large` refuses a long command: a command that cannot be read in time is refused, not
# passed. Measured on this host (2026-09-29, docs/secret-storage.md): shlex costs 2 microseconds a unit inside one long quoted word and a
# tenth of that in ordinary words, a text read 15 to 60, a word of an emitted segment 0.5 to 1, and a keyring read 50 to 100 beyond its
# characters, so each counter alone holds its worst case near one second (400,000 characters: 1.1 s; 10,000 texts: 0.3 s; 1,000,000
# words: 0.2 s; 500 reads: 0.03 s). The largest real command of this repository (an 82,000-character script written through a
# here-document) spends 35% of `characters`, 1% of `words` and under 1% of `texts` and `reads`, so the limits leave ordinary work far
# inside them, and 500 random mixes of the adversarial shapes at 199,000 characters took at most 0.9 s.
WORK_LIMITS = {
    "characters": 400_000,  # characters passed to shlex, each at its storage width (storage_width), over every reading and nesting level
    "texts": 10_000,  # texts read: the command, each double-quoted substitution body, each `sh -c` or `eval` string, each keyring read
    "words": 1_000_000,  # words in the segments that reading emits, each segment counted with one more (a list of words copied)
    "reads": 500,  # commands read again from the words of a keyring exec (the started command, each launched program inside it)
}
# What check() has spent so far (None outside a check() call, where nothing is counted): start_work() and stop_work() bracket a call.
_work: dict[str, int] | None = None
# The words lex() has read in this check() call, by text and mode (None outside a call): the prior reading tokenizes the command as the
# guard at c26800f3 did, which is this version's legacy reading of the same text, so it costs no second pass (see lex()).
_lexed: dict[tuple[str, bool], list[str]] | None = None
# Launchers of the systemd family that start the command after their own options (systemd-run(1)).
SYSTEMD_LAUNCHERS = {"systemd-run", "run0", "systemd-inhibit", "systemd-cat"}
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
                                                                  "readonly", "local", "systemctl"} | {
    "systemd-run", "run0", "systemd-inhibit", "systemd-cat"}

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
    "secret_variable_on_command_line": "-E NAME=value puts the value in the systemd-run command line, which the process "
                                       "listing shows while it runs, and -E NAME forwards the caller's value; either way it "
                                       "lands in the unit's Environment property on the user bus, which any bus client reads "
                                       "(systemctl --user show -p Environment UNIT)",
    "service_manager_environment": "this prints the whole environment block that a service manager hands to every "
                                   "unit; for one unit use systemctl show -p Environment UNIT, and for the PATH a "
                                   "unit sees run systemd-run --user --pipe --wait --collect /bin/sh -c 'command -v "
                                   "node; echo \"$PATH\"'",
    "guard_error": "the guard could not read this command, so it blocks it; split it into smaller commands or "
                   "simplify its quoting, substitutions and launchers",
    "command_too_large": f"the guard cannot read a command of more than {MAX_COMMAND_CHARACTERS:,} characters before its hook "
                         "timeout, and a hook that times out blocks nothing, so it blocks the command; put the content in a "
                         "file with the Write tool and pass the path",
    "command_too_complex": "the guard cannot read this command within its work budget before its hook timeout (very long "
                           "words, many nested substitutions or many launched commands), and a hook that times out blocks "
                           "nothing, so it blocks the command; split it into smaller commands, or put the content in a file "
                           "with the Write tool and pass the path",
}


class WorkBudgetExceeded(Exception):
    """check() spent one of its work budgets (WORK_LIMITS): the command cannot be read inside the hook's timeout. args[0] names the counter.
    It is raised, not returned as a reason, so that no caller can take a command the guard could not read for one it allowed; main() turns
    it into `command_too_complex` and exit 2."""


def start_work() -> dict[str, int]:
    """Begin the work budget of one check() call: every counter at zero, and no text lexed yet. Returns the counters (they are what
    check() has spent)."""
    global _work, _lexed
    _work = dict.fromkeys(WORK_LIMITS, 0)
    _lexed = {}
    return _work


def stop_work() -> None:
    """End the budget: outside a check() call nothing is counted, so a direct call to lex() or expand() (a test, a tool) has no limit."""
    global _work, _lexed
    _work = None
    _lexed = None


def spend(kind: str, amount: int) -> None:
    """Charge amount units to the counter `kind` of the current budget and raise WorkBudgetExceeded when it passes its limit."""
    if _work is not None:
        used = _work[kind] = _work[kind] + amount
        if used > WORK_LIMITS[kind]:
            raise WorkBudgetExceeded(kind)


def storage_width(text: str) -> int:
    """Bytes CPython stores each character of text in: 1 for ASCII and Latin-1, 2 for the rest of the Basic Multilingual Plane, 4 beyond.
    shlex reads a text one character at a time and costs about 2 microseconds a character at one byte, 4 at two and 8 at four (measured
    here on 200,000 characters of one quoted word: 0.41, 0.85 and 1.70 s), so the work budget counts each character at its width."""
    if text.isascii():
        return 1
    top = ord(max(text))
    return 1 if top <= 0xFF else 2 if top <= 0xFFFF else 4


def tokenize(command: str, comments: list[tuple[int, int]] | tuple = (), legacy: bool = False,
             protected: list[int] | tuple = (), ansi_c: list[tuple[int, int]] | tuple = ()) -> list[str]:
    """The words of a command, punctuation apart. `comments` are the spans scan_shell() found to be comments and are
    removed first, and no `#` starts a comment for shlex: shlex read one anywhere (even in `$#` and `a#b`) and, since the
    lines are joined with `;` below, dropped the whole rest of the command. `protected` are the backquotes it found inside
    single-quoted and ANSI-C strings: text for the shell that string is handed to (`bash -c 'echo "`x`"'`), so they stay
    backquotes instead of becoming `;` with the others. `ansi_c` are the `$'...'` strings it found: shlex knows no ANSI-C
    quoting (it reads `$'it\\'s #\\nprintenv'` as a word, a quote that opens and a comment), so each becomes one single-quoted
    word of the same text, its `\\'` written as a quote shlex reads. `legacy` is the reading without comments, protected
    backquotes and ANSI-C words, kept because command_segments() reads both: whatever the guard read before it still reads."""
    if protected:
        marked = list(command)
        for at in protected:
            marked[at] = PROTECTED_BACKQUOTE
        command = "".join(marked)
    if comments or ansi_c:
        edits = [(first, last, "") for first, last in comments]
        edits += [(first, last, "'" + command[first + 2:last - 1].replace("\\'", "'\"'\"'") + "'") for first, last in ansi_c]
        pieces, cursor = [], 0
        for first, last, replacement in sorted(edits, key=lambda edit: edit[:2]):
            if first >= cursor:
                pieces.append(command[cursor:first])
                pieces.append(replacement)
                cursor = last
        pieces.append(command[cursor:])
        command = "".join(pieces)
    tokens = lex(command, legacy)
    return [token.replace(PROTECTED_BACKQUOTE, "`") for token in tokens] if protected else tokens


def lex(text: str, legacy: bool = False) -> list[str]:
    """The words of text, punctuation apart, once tokenize() has cut its spans out: a backquote and a newline are `;` (the lines of a
    command are joined that way), shlex reads the rest, and a text it cannot read (an unbalanced quote) is split by a regular
    expression that keeps the quotes. Without `legacy`, `#` starts no comment for shlex (scan_shell found the real ones). Every
    character passed to shlex is charged to the work budget, at its storage width, before shlex reads it. Inside a check() call each
    text is read once in each mode, and a text without a `#` reads the same in both: the prior reading asks for the command's words as
    the guard at c26800f3 read them, which is the legacy reading here, and a second pass would spend the budget of a command that fits
    it (two readings of an ASCII text of 190,000 characters and a `#` spend 380,000 of 400,000). The words come back as they were read;
    no caller changes them."""
    text = text.replace("`", " ; ").replace("\n", " ; ")
    key = (text, legacy and "#" in text)
    if _lexed is not None and key in _lexed:
        return _lexed[key]
    spend("characters", len(text) * storage_width(text))
    if "'" not in text and '"' not in text and "\\" not in text:
        tokens = SHLEX_PLAIN.findall(text.partition("#")[0] if legacy else text)  # what shlex gives, in linear time (see SHLEX_PLAIN)
    else:
        try:
            lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            if not legacy:
                lexer.commenters = ""
            tokens = list(lexer)
        except ValueError:
            tokens = re.findall(r"[;&|()<>]+|[^\s;&|()<>]+", text)
    if _lexed is not None:
        _lexed[key] = tokens
    return tokens


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


def ansi_c_end(text: str, position: int) -> int:
    """Index just past the `'` that ends the ANSI-C string whose contents start at text[position], or -1."""
    while found := ANSI_C_TAIL.search(text, position):
        if found.group() == "'":
            return found.end()
        position = found.end()
    return -1


def substitution_bodies(text: str) -> list[str]:
    """The bodies scan_shell() returns for text (see there)."""
    return scan_shell(text)[0]


def scan_shell(text: str) -> tuple[list[str], list[tuple[int, int]], list[int], list[tuple[int, int]]]:
    """(bodies, comments, protected, ansi_c) of a command text, read once the way bash reads it.

    Bodies: those of the outermost command substitutions that the shell runs inside double quotes, `$(...)` and a
    backquote pair. Inside double quotes `$` and the backquote keep their meaning and a backslash escapes only
    `$`, the backquote, `"` and `\\` (Bash Reference Manual, "Double Quotes" and "Command Substitution"); single
    quotes are data everywhere but inside double quotes, where they are ordinary characters. A `$(` body ends at its
    matching `)`, read with its own quotes and nesting ("all characters between the parentheses make up the
    command"); a backquote body ends at the first backquote not preceded by a backslash, and there a backslash before
    `$`, a backquote, `\\` or `"` is removed. An unterminated substitution runs to the end of the text, as the
    tokenizer treats a lone apostrophe as an ordinary character. Substitutions inside a returned body are not
    returned: expand() reads that body again. One inside an unquoted `$(...)` is: the tokenizer already splits that
    body's commands, but not the double-quoted words in it. `$((` opens an arithmetic expansion, which is no command
    (`$((env))` reads the variable env, a `<<` in it is a shift) but may hold real substitutions; it is one only when a
    `))` that touches closes it, and `$((printenv) )` is a substitution holding a subshell (bash tries arithmetic
    first and falls back to that). `$'...'` is an ANSI-C string, data up to the first `'` that a backslash does not
    escape (`$'it\\'s'`); inside double quotes `$'` is nothing special. Here-documents are not read as such: their
    lines are command text like any other, as the tokenizer has always read them at the top level, because bash's rules
    for where a body ends (quoted, ANSI-C and backslash forms of the delimiter, arithmetic commands that look like `<<`,
    continuation lines) are too fine to track and each slip hid executable text (two reviews found five and six of them),
    so no here-document body is data and no form of one is exempt.

    Comments: the spans, one per line, that bash ignores at the top level of text: from a `#` that starts a word,
    outside quotes and outside any double-quoted substitution, to the end of the line (`$#`, `${#x}` and `a#b` hold none;
    inside a `$(...)` body a comment also runs to the end of its line, so a `)` in it closes nothing). tokenize()
    removes them.

    ANSI-C strings: the top-level `$'...'` spans (the `$` to the closing quote), which tokenize() keeps as one word.

    One pass, each character read once: a stack of frames replaces recursion, and a regular expression jumps from one
    character that matters to the next."""
    bodies: list[str] = []
    comments: list[tuple[int, int]] = []
    protected: list[int] = []  # backquotes inside single-quoted or ANSI-C strings at the top level
    ansi_c: list[tuple[int, int]] = []
    # Frames, innermost last: [kind, start, parentheses, reported, dq, bodies_at_open]. Kinds: cmd (unquoted text),
    # sub (`$(`), bt (backquotes), dq (double quotes), param (`${`), dparam (`${` inside double quotes), arith (`$((`).
    # `dq` says whether a substitution opened here sits inside double quotes (param and arith inherit it from their
    # parent). `reported` marks a body that starts inside double quotes and is returned; `hidden` counts those on the
    # stack, so a substitution inside one is left to the next reading of that body.
    stack: list[list] = [["cmd", 0, 0, False, False, 0]]
    hidden = 0
    end = len(text)
    index = 0
    has_backquote = "`" in text
    construct_end = -1  # where the last quote, escape or substitution ended: a `#` right after it is inside a word

    def close(at: int) -> None:
        nonlocal hidden
        kind, start, _, reported = stack.pop()[:4]
        if reported:
            hidden -= 1
            body = text[start:at]
            bodies.append(BACKQUOTE_ESCAPE.sub(r"\1", body) if kind == "bt" else body)

    def protect(first: int, last: int) -> None:
        tick = text.find("`", first, last)
        while tick >= 0:
            protected.append(tick)
            tick = text.find("`", tick + 1, last)

    def open_frame(kind: str, start: int, frame: list, quoted: bool = False) -> None:
        nonlocal hidden
        reported = frame[4] and not hidden and kind in {"sub", "bt", "arith"}
        stack.append([kind, start, 1 if kind in {"sub", "bt"} else 0, reported, quoted, len(bodies)])
        if reported and kind != "arith":
            hidden += 1

    while index < end:
        frame = stack[-1]
        kind = frame[0]
        found = SCAN_CHARACTERS[kind].search(text, index)
        if found is None:
            break
        index = found.start()
        char = text[index]
        if char == "\\":
            index += 2
            construct_end = index
        elif char == '"':
            if kind == "dq":
                stack.pop()
                construct_end = index + 1
            else:
                stack.append(["dq", 0, 0, False, True, 0])
            index += 1
        elif char == "'":
            closing = text.find("'", index + 1)
            if closing >= 0 and has_backquote and not hidden:
                protect(index + 1, closing)
            index = closing + 1 if closing >= 0 else index + 1
            construct_end = index
        elif char == "`":
            if kind == "bt":
                close(index)
                construct_end = index + 1
            else:
                open_frame("bt", index + 1, frame)
            index += 1
        elif char == "$":
            following = text[index + 1:index + 2]
            if following == "(" and text.startswith("((", index + 1):
                open_frame("arith", index + 3, frame, frame[4])
                index += 3
            elif following == "(":
                open_frame("sub", index + 2, frame)
                index += 2
            elif following == "{":
                stack.append(["dparam" if frame[4] else "param", index + 2, 0, False, frame[4], 0])
                index += 2
            elif following == "'" and not frame[4] and (closing := ansi_c_end(text, index + 2)) >= 0:
                if has_backquote and not hidden:
                    protect(index + 2, closing - 1)
                if not hidden:
                    ansi_c.append((index, closing))
                index = construct_end = closing
            else:
                index += 1
        elif char == "}":
            stack.pop()
            index += 1
            construct_end = index
        elif char == "#":
            # a comment starts at a word's first character and runs to the end of the line
            if index == 0 or (index != construct_end and text[index - 1] in COMMENT_BREAK):
                closing = (BACKQUOTE_COMMENT_END if kind == "bt" else LINE_END).search(text, index)
                closing = closing.start() if closing else end
                if not hidden:
                    comments.append((index, closing))
                index = closing
            else:
                index += 1
        elif char == "(":
            frame[2] += 1
            index += 1
        else:  # ")"
            if kind == "sub":
                frame[2] -= 1
                if not frame[2]:
                    close(index)
                    construct_end = index + 1
            elif frame[2]:
                frame[2] -= 1
            elif text.startswith(")", index + 1):  # arithmetic expansion ends at a `))` that touches
                stack.pop()
                index += 1
                construct_end = index + 1
            else:  # no `))`: this was `$(` and a subshell, so read it as a substitution
                frame[0], frame[1], frame[2] = "sub", frame[1] - 1, 1
                if frame[3]:
                    hidden += 1
                    del bodies[frame[5]:]
            index += 1
    while len(stack) > 1:  # unterminated: what is left of the text
        if stack[-1][0] == "arith":
            stack.pop()
        else:
            close(end)
    return bodies, comments, protected, ansi_c


def input_redirection_segments(words: list[str]) -> list[list[str]]:
    """Segments to read in addition to `words` for an input redirection that stands where a command starts. `< FILE` alone
    (`<> FILE` too, with or without a descriptor before the operator) or after the parenthesis of `$(<FILE)` (the token
    `(<`, see PAREN_INPUT) reads FILE like `cat FILE`; a leading `< FILE cmd args` puts FILE on cmd's input as the trailing
    `cmd args < FILE` does, so the rules read it that way."""
    width = redirection_width(words, 0) if words else 0
    found = []
    if width and words[width - 2] in {"<", "<>", "<<<"}:
        if width < len(words):
            found.append(words[width:] + words[:width])
        elif words[width - 2] != "<<<":  # a here-string with no command reads nothing
            found.append(["cat", words[-1]])
    found += [["cat", words[at + 1]] for at, word in enumerate(words[:-1]) if PAREN_INPUT.fullmatch(word)]
    return found


def redirection_width(words: list[str], index: int) -> int:
    """How many words the redirection at words[index] takes (operator and target, with a descriptor
    number before it and the `-` of `<<- EOF`), or 0 when it starts none. A digit before an operator is
    read as its descriptor, since shlex splits `2>` and `2 >` alike."""
    word = words[index]
    # A descriptor before the operator: a number, or bash's named form `{varname}` (`{fd}>file`).
    if (word.isdigit() or re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", word)) and index + 1 < len(words) \
            and REDIRECTION.match(words[index + 1]):
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


def skip_redirections(words: list[str], index: int, moved: list[str] | None = None) -> int:
    """Index of the first word at or after `index` that is no redirection operator or its target. Bash takes a redirection out of the
    argument list wherever it stands, so the value of an option, the duration of timeout and the command that a launcher starts are the next
    words that are none: `env -u < FILE UNUSED cat` is `env -u UNUSED cat < FILE`. The launcher walk took the operator for the value of
    `-u`, dropped the segment that held the operand and let a credential file through (found by the verification review of 172596ed).
    Only an operator token starts a redirection here (a bare number may be a value: `nice -n 5 > out cmd`). An input redirection that is
    skipped is appended to `moved`, for the caller to read with the command that gets it, as if it stood after that command."""
    while index < len(words) and REDIRECTION.match(words[index]):
        width = 3 if words[index] == "<<" and words[index + 1:index + 2] == ["-"] else 2
        if moved is not None and words[index].lstrip("0123456789").startswith("<"):
            moved.extend(words[index:index + width])
        index += width
    return index


def wrapper_options(words: list[str], index: int, wrapper: str,
                    moved: list[str] | None = None) -> tuple[list[tuple[str, str | None]], int]:
    """A launcher's own options from words[index:], as getopt reads them, and the index of the first word after
    them: `--` ends them; in a cluster of short options (`-iu`) the first that takes a value takes the rest of the
    cluster (`-o0`) or, when it ends the cluster, the next word (`-o 0`, `nice -n 10`, `sudo -u root`). Each option
    comes back as (name, value): `--unit=x` and `--unit x` are ("--unit", "x"), `-EFOO` and `-E FOO` are ("-E", "FOO"),
    a boolean option has the value None, and so does a value option with no word left. A redirection is no option and no
    value, wherever it stands (skip_redirections); an input redirection skipped goes to `moved`."""
    value_flags = WRAPPER_VALUE_FLAGS.get(wrapper, set())
    options: list[tuple[str, str | None]] = []
    while index < len(words):
        word = words[index]
        if word == "--":
            return options, index + 1
        if wrapper in SYSTEMD_LAUNCHERS and (width := redirection_width(words, index)):
            # a redirection is no option, and options may follow it; here a number before the operator is its descriptor (for the other
            # launchers it may be a value: timeout's duration `5` reads as `5>`, so only the operator itself is skipped)
            if moved is not None and words[index + width - 2].startswith("<"):
                moved.extend(words[index + width - 2:index + width])
            index += width
            continue
        if REDIRECTION.match(word):
            index = skip_redirections(words, index, moved)
            continue
        if not word.startswith("-") or word == "-":
            return options, index
        index += 1
        if word.startswith("--"):
            name, glued, value = word.partition("=")
            if glued:
                options.append((name, value))
            elif word in value_flags:
                index = skip_redirections(words, index, moved)
                options.append((word, words[index] if index < len(words) else None))
                index += 1
            else:
                options.append((word, None))
        else:
            letters = word[1:]
            first = next((at for at, letter in enumerate(letters) if f"-{letter}" in value_flags), None)
            options.extend((f"-{letter}", None) for letter in letters[:first])
            if first is not None:
                glued = letters[first + 1:]
                if glued:
                    options.append((f"-{letters[first]}", glued))
                else:
                    index = skip_redirections(words, index, moved)
                    options.append((f"-{letters[first]}", words[index] if index < len(words) else None))
                    index += 1
    return options, index


def skip_wrapper_options(words: list[str], index: int, wrapper: str, moved: list[str] | None = None) -> int:
    """Index of the first word after a launcher's own options (wrapper_options)."""
    return wrapper_options(words, index, wrapper, moved)[1]


def strip_prefix(words: list[str]) -> list[str]:
    """The command itself: without assignments, output redirections before it (`> out cmd`), and
    launchers with their options (timeout also with its duration). A leading input redirection stays,
    for segment_reason's check of what is redirected in."""
    return words[prefix_end(words):]


def prefix_end(words: list[str], index: int = 0, moved: list[str] | None = None, ends: dict[int, int] | None = None) -> int:
    """Index of the command in words[index:], past what strip_prefix drops. It returns an index and copies
    nothing, so a chain of launchers is walked once, not once per hop. Input redirections that a launcher's options
    stand around go to `moved` (skip_redirections). `ends` (given without `moved`) keeps the answer for every position the walk
    steps on, since a walk from a position ends where the walk from its next step ends: a caller that walks from many positions of
    one list (the actions of a `find`) then walks each position once."""
    steps: list[int] = []
    while index < len(words):
        if ends is not None:
            if index in ends:
                index = ends[index]
                break
            steps.append(index)
        word = words[index]
        width = redirection_width(words, index)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word == "$":
            index += 1
        elif width and REDIRECT_OUT.match(words[index + width - 2]):
            index += width
        elif (name := word.rsplit("/", 1)[-1]) in WRAPPERS or name == "timeout":
            index = skip_wrapper_options(words, index + 1, name, moved)
            if name == "timeout":
                index += 1  # timeout's mandatory duration comes before the command
        else:
            break
    if ends is not None:
        for step in steps:
            ends[step] = index
    return index


def program_of(words: list[str]) -> str:
    return words[0].rsplit("/", 1)[-1] if words else ""


def env_command_start(words: list[str], at: int = 0, moved: list[str] | None = None) -> int | None:
    """Index of the command `env [options] [NAME=value ...] command` runs, where env is words[at], or None for a dump. A redirection
    among its words is no option and no value (skip_redirections); an input redirection skipped goes to `moved`."""
    index = at + 1
    while index < len(words):
        index = skip_redirections(words, index, moved)
        if index >= len(words):
            break
        word = words[index]
        if word in ENV_ARG_OPTIONS:
            index = skip_redirections(words, index + 1, moved) + 1
        elif word.startswith("-") or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word):
            index += 1
        else:
            return index
    return None


def systemctl_call(words: list[str]) -> tuple[list[str], list[str]]:
    """(positional words, property names) of a systemctl command: the verb comes first among the positional words, then
    what it acts on (unit names). Options may stand anywhere, as getopt permutes them (the table for value options is
    WRAPPER_VALUE_FLAGS["systemctl"]); `--` ends them; -p, --property and -P name properties, comma separated."""
    arguments = command_arguments(words)
    positional: list[str] = []
    properties: list[str] = []
    value_flags = WRAPPER_VALUE_FLAGS["systemctl"]
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            positional.extend(arguments[index:])
            break
        if not word.startswith("-") or word == "-":
            positional.append(word)
            continue
        if word.startswith("--"):
            name, glued, value = word.partition("=")
            if not glued and word in value_flags and index < len(arguments):
                value = arguments[index]
                index += 1
            if name == "--property":
                properties.extend(value.split(","))
        else:
            letters = word[1:]
            first = next((at for at, letter in enumerate(letters) if f"-{letter}" in value_flags), None)
            if first is not None:
                value = letters[first + 1:]
                if not value and index < len(arguments):
                    value = arguments[index]
                    index += 1
                if letters[first] in "pP":
                    properties.extend(value.split(","))
    return positional, properties


def systemctl_reason(words: list[str]) -> str | None:
    """service_manager_environment for the two systemctl commands that print a manager's environment: `show-environment`,
    and `show` with no unit (or job) named unless -p names other properties only, which prints the manager's own
    properties, Environment among them (systemctl(1) 255)."""
    positional, properties = systemctl_call(words)
    if positional[:1] == ["show-environment"]:
        return "service_manager_environment"
    if positional[:1] == ["show"] and len(positional) == 1 and (not properties or "Environment" in properties):
        return "service_manager_environment"
    return None


def environment_assignments(payload: str) -> list[str]:
    """The `NAME=value` items of a systemd `Environment=` value: separated by whitespace, each optionally quoted."""
    try:
        return shlex.split(payload)
    except ValueError:
        return payload.split()


def systemd_run_sets_secret(words: list[str]) -> bool:
    """Whether a systemd-run command line names a secret variable (SECRET_NAMES) among the variables it sets for
    the unit it starts, with or without a value: `-E NAME[=VALUE]`, `--setenv NAME[=VALUE]` or `-p`/`--property`
    `Environment=NAME=VALUE ...`. Where the value goes differs by form (systemd v255, read 2026-09-29). `-E NAME=VALUE` puts
    it in the command line of the systemd-run process itself (argv, which /proc/PID/cmdline and the process listing show while
    it runs) and in the transient unit's Environment property. `-E NAME` puts only the name in argv, and systemd-run takes the
    caller's own value from its environment (`strv_env_replace_strdup_passthrough`, src/basic/env-util.c:417, called for
    `case 'E'`, src/run/run.c:348): that value reaches the unit's Environment property and no argv. Both lines end in the property,
    appended to the start message over the user bus (`arg_environment`, run.c:853-866), which `systemctl --user show -p
    Environment UNIT` and any bus client read. Not the journal: the unit's description, which the manager logs as `Started
    <unit> - <description>`, defaults to the started command and its arguments after the options (`quote_command_line(arg_cmdline)`,
    run.c:1940-1951), so `-E` is not in it, while a value written after the command is (a recorded gap). The variable's NAME
    is read, not any text that spells one: `-E LABEL=APCA_API_KEY_ID` sets LABEL."""
    for name, value in wrapper_options(words, 1, "systemd-run")[0]:
        if value is None:
            continue
        if name in {"-E", "--setenv"}:
            assignments = [value]
        elif name in {"-p", "--property"} and value.lower().startswith("environment="):
            assignments = environment_assignments(value.partition("=")[2])
        else:
            continue
        if any(assignment.partition("=")[0] in SECRET_NAMES for assignment in assignments):
            return True
    return False


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
            moved: list[str] = []  # an input redirection among the script's own arguments is read with the command it starts
            index = 0
            while index < separator:
                after = skip_redirections(arguments, index, moved)
                index = after if after != index else index + 1
            return variable if variable and ENV_NAME.fullmatch(variable) else None, arguments[separator + 1:] + moved
        if name in KEYRING_WRAPPERS and (position == 0 or program_of(words) in SHELLS):
            variable, target = KEYRING_WRAPPERS[name]
            return variable, [target, *words[position + 1:]]
    return None


def rtk_command(words: list[str]) -> list[str]:
    """The command `rtk [flags] <subcommand> ...` runs, as the rules read it (see RTK_RUNNERS): empty when
    it names none. `rtk run` comes back as `sh -c <command>`, so expand() reads the inner shell too."""
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 1  # rtk's own flags (-v, --ultra-compact, --skip-env) take no value
    if index >= len(words):
        return []
    subcommand, rest = words[index], words[index + 1:]
    if subcommand in RTK_RUNNERS:
        start = 0
        while start < len(rest) and rest[start].startswith("-") and rest[start] != "--":
            start += 1
        return rest[start + 1:] if rest[start:start + 1] == ["--"] else rest[start:]
    if subcommand == "run":
        start = 0
        while start < len(rest) and rest[start] in RTK_RUN_FLAGS:
            start += 1
        if rest[start:start + 1] in (["-c"], ["--command"]) and start + 1 < len(rest):
            return ["sh", "-c", rest[start + 1]]
        if rest[start:start + 1] and rest[start].startswith("--command="):
            return ["sh", "-c", rest[start][len("--command="):]]
        return ["sh", "-c", " ".join(rest[start:])] if rest[start:] else []
    if subcommand in RTK_FILE_READERS:
        return ["cat", *rest]
    return [subcommand, *rest]


def rtk_command_start(words: list[str], at: int, moved: list[str] | None = None) -> int | None:
    """Index in words of the command that the rtk at words[at] starts, when that command is a tail of words: after a
    runner's flags (see RTK_RUNNERS) or, for the other subcommands, the subcommand itself (`rtk grep x` runs `grep x`).
    None when it names none, or for `rtk run` and the file readers, whose command rtk_command builds."""
    index = skip_redirections(words, at + 1, moved)
    while index < len(words) and words[index].startswith("-"):
        index = skip_redirections(words, index + 1, moved)
    if index >= len(words):
        return None
    subcommand = words[index]
    if subcommand in RTK_RUNNERS:
        start = skip_redirections(words, index + 1, moved)
        while start < len(words) and words[start].startswith("-") and words[start] != "--":
            start = skip_redirections(words, start + 1, moved)
        return skip_redirections(words, start + 1, moved) if words[start:start + 1] == ["--"] else start
    if subcommand == "run" or subcommand in RTK_FILE_READERS:
        return None
    return index


def launcher_chain(words: list[str]) -> tuple[list[list[str]], int, list[str]]:
    """The env, rtk and systemd-run launchers that start words, the index of the command they start, and the input
    redirections that stood among the launchers' options (a redirection is no option and no value, so the walk steps over it;
    the caller reads it with the command that gets it). A systemd-run comes back as its own words (the rule on its options
    reads them); an env or rtk that starts a command needs no segment of its own, because that command is the next one. It
    walks the chain with an index: copying the rest of the words at every hop made a chain of n launchers cost n squared,
    29 s for 20,000 `env`."""
    entries: list[list[str]] = []
    moved: list[str] = []
    at = 0
    while at < len(words):
        program = program_of(words[at:at + 1])
        if program == "env":
            start = env_command_start(words, at, moved)
            if start is None:
                break
        elif program in SYSTEMD_LAUNCHERS:
            start = skip_wrapper_options(words, at + 1, program, moved)
            entries.append(words[at:start])
        elif program == "rtk":
            start = rtk_command_start(words, at, moved)
            if start is None:
                break
        else:
            break
        at = prefix_end(words, start, moved)
    return entries, at, moved


def expand(command: str, depth: int = 0) -> list[list[str]]:
    """Command segments of the command, and of the command substitutions that the shell runs inside its double
    quotes (scan_shell: `echo "$(printenv)"` runs printenv), at any nesting up to MAX_SUBSTITUTION_NESTING and while
    the bodies read stay within SUBSTITUTION_BUDGET_FACTOR times the command's length (plus SUBSTITUTION_BUDGET_FLOOR):
    every level is read again from the start, so quotes nested n deep would otherwise cost n times the command. A segment
    that comes up more than once is returned once (identical segments get identical verdicts, and each copy would be
    analysed again)."""
    result: list[list[str]] = []
    level = [command]
    budget = SUBSTITUTION_BUDGET_FACTOR * len(command) + SUBSTITUTION_BUDGET_FLOOR
    spent = 0
    for nesting in range(MAX_SUBSTITUTION_NESTING + 1):
        following: list[str] = []
        for text in level:
            bodies, comments, protected, ansi_c = scan_shell(text)
            result.extend(command_segments(text, depth, comments, protected, ansi_c))
            following.extend(bodies)
        spent += sum(map(len, following))
        if not following or spent > budget:
            break
        level = following
    return unique_segments(result)


def unique_segments(segments: list[list[str]]) -> list[list[str]]:
    """The segments in order without a repeat: a segment that comes twice (the words as written and the words after a launcher walk, two
    readings of one text, a command that stands twice in a script) gets the same verdict twice, so the second copy only adds work."""
    seen: set[tuple[str, ...]] = set()
    result = []
    for words in segments:
        key = tuple(words)
        if key not in seen:
            seen.add(key)
            result.append(words)
    return result


def command_segments(command: str, depth: int = 0, comments: list[tuple[int, int]] | tuple = (),
                     protected: list[int] | tuple = (), ansi_c: list[tuple[int, int]] | tuple = ()) -> list[list[str]]:
    """Command segments, including those of `sh -c '...'`, `eval ...`, `env ... command`, of the
    command that a keyring exec starts, of the command an `rtk` invocation runs and of the command a
    `systemd-run` starts (each launcher's own segment stays in the result, for the rules on its options). Read twice
    when the command holds a `#` or an ANSI-C string: without its comments and with each `$'...'` one word (tokenize),
    and as shlex read it before, which dropped the rest of the command at the first `#`; the second reading adds only
    the segments the first lacks. Each text read counts one `texts` and each segment it emits its words plus one `words`
    of the work budget, so a chain of keyring execs, each emitting the rest of the words again, cannot make the copying
    quadratic. main() refuses a command long enough for two readings to outlast the hook's timeout."""
    spend("texts", 1)
    result: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def emit(segment: list[str]) -> None:
        spend("words", len(segment) + 1)
        result.append(segment)

    readings = [tokenize(command, comments, protected=protected, ansi_c=ansi_c)]
    if "#" in command or protected or comments or ansi_c:
        readings.append(tokenize(command, legacy=True))
    for reading, tokens in enumerate(readings):
        for raw in segments(tokens):
            if reading:
                if tuple(raw) in seen:
                    continue
            else:
                seen.add(tuple(raw))
            emit(raw)  # as written, before any launcher walk: a redirection is checked wherever the walk would put it
            skipped: list[str] = []
            words = raw[prefix_end(raw, 0, skipped):]
            while words:
                entries, start, moved = launcher_chain(words)
                for entry in entries:
                    emit(entry)
                if start:
                    words = words[start:]
                    if words:
                        words = words + skipped + moved  # the input redirections stepped over are read with the command that gets them
                        skipped = []
                elif skipped:
                    words = words + skipped
                    skipped = []
                if not words:
                    break
                emit(words)
                for redirected in input_redirection_segments(words):  # `$(< FILE)` is `$(cat FILE)`; zsh's `< FILE` alone reads it too
                    emit(redirected)
                program = program_of(words)
                if program == "env":
                    break  # launcher_chain walked every env that starts a command: this one prints its environment
                if program == "rtk":
                    words = strip_prefix(rtk_command(words))  # `rtk run` and the file readers
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


def is_ps_bsd_cluster(word: str) -> bool:
    """Whether word is a dashless BSD-style ps cluster that shows the environment: made only of the letters of PS_BSD_LETTERS and holding
    `e` (procps and BSD: "Show the environment after the command") or, from 2026-09-29, `E` (macOS: "-E Display the environment as
    well", Apple adv_cmds ps.1, which lists the BSD-style `e` as "Same as -E"). `ps eww` and `ps auxE` match; `ps aux` does not. A set
    test, where the regular expression `^[aAcfhjlmrsStTuvwxXLnE]*[eE][aAcefhjlmrsStTuvwxXLnE]*$` backtracked quadratically: 70,000 `E` and a
    letter that is no flag took 13 s, past a hook timeout that fails open."""
    return PS_BSD_LETTERS.issuperset(word) and ("e" in word or "E" in word)


def prior_ps_shows_environment(words: list[str]) -> bool:
    """The ps rule of the guard at c26800f3, verbatim: a dashless word that PS_BSD_CLUSTER matches shows the environment, unless it is the
    value of a stand-alone option of PS_ARG_OPTIONS right before it (`ps -u steve` passes, `ps -fu steve` does not)."""
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


def ps_reading_shows_environment(words: list[str], procps: bool) -> bool:
    """Whether one host's ps prints each process's environment for this command line, in its default personality. Both hosts read a
    dashed word as a cluster of options, and a letter that takes a value takes the rest of the word or, when it ends the cluster, the
    next word, so that word is a value and not an option or a cluster in this reading (`ps -u Eve`, `ps -fu Eve`, `ps -uEve`;
    ps_shows_environment still refuses `ps -fu steve`, which the guard at c26800f3 refused). They differ in three things. procps (`procps=True`) has `-C cmdlist`, which takes a value, has no `-E`, and reads a dashless BSD cluster wherever it
    stands (`ps -C cat e`, `ps -Ccat e`: `cat` is the command name and `e` shows the environment). macOS has `-E` (and `-e` in its
    legacy mode, see the docs), reads `-C` as a flag, and honours a dashless option string only as the first argument
    (`kludge_oldps_options(..., argv[1], ...)` in Apple adv_cmds ps/ps.c), so `ps -Ccat e` is `-C -c -a -t e`: `t` takes `e`, a tty."""
    value_options = PS_ARG_OPTIONS if procps else PS_MACOS_ARG_OPTIONS
    skip = False
    for position, word in enumerate(words[1:], 1):
        if skip:
            skip = False
        elif word in value_options:
            skip = True  # a stand-alone option that takes the next word
        elif word.startswith("-") and not word.startswith("--") and len(word) > 1:
            letters = word[1:]
            value_at = next((at for at, letter in enumerate(letters) if f"-{letter}" in value_options), None)
            if not procps and "E" in (letters if value_at is None else letters[:value_at]):
                return True
            skip = value_at == len(letters) - 1  # the cluster ends in an option that takes the next word
        elif not word.startswith("-") and is_ps_bsd_cluster(word) and (procps or position == 1):
            return True
    return False


def ps_shows_environment(words: list[str]) -> bool:
    """Whether ps prints each process's environment on either host that could run the command line (ps_reading_shows_environment), or
    the guard at c26800f3 refused it (prior_ps_shows_environment): a dashless BSD-style cluster with `e` or `E` (is_ps_bsd_cluster), or
    macOS's dashed `-E`, alone or in a cluster before the first option that takes a value (`-Ewwp 123`, where the value starts at `p`).
    A dashed `-e` is every process and passes, as does an `E` that is a value. `-C` is a flag on macOS and takes a command name on
    procps, so a dashed word with a `C` is read both ways and refused when either shows the environment: `ps -CE` and `ps -C -E`
    (macOS), `ps -Ccat e` and `ps -fCcat e` (procps), and `ps -CEmacs` too, which is friction on procps (there `Emacs` is the command
    name; write `ps -C emacs`).

    The reading of c26800f3 stays because procps has personalities that a hook cannot see (third verification review, 2026-09-29):
    with PS_PERSONALITY=old or I_WANT_A_BROKEN_PS set, on the command line or inherited from the shell, procps parses `ps -axu e`
    BSD-style, where `u` takes no value and `e` shows the environment. So a dashless word of that guard's cluster alphabet with an `e`
    is refused wherever it stands, whatever cluster comes before it (`ps -fu steve`, `ps -fo user`, `ps -ft e`, `ps -fC e`): no ps
    command that guard refused passes. Only its stand-alone value options take the next word, as they did (`ps -u steve` and
    `ps -C emacs` pass; whether a personality also reads a stand-alone `-u` BSD-style, so that `ps -u e` shows the environment, is not
    measured here, and that guard passed it too), and a numeric id or pgrep never reads as a cluster (`ps -f -U 1000`, `pgrep -u steve`)."""
    return prior_ps_shows_environment(words) or ps_reading_shows_environment(words, True) or ps_reading_shows_environment(words, False)


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
    """Arguments minus write targets: redirection targets, a copy's destination, tee's files, dd's of=."""
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
    if program == "dd":
        return [w for w in operands if not w.startswith("of=")]  # dd(1): of=FILE is written, if=FILE read
    if program in COPIERS:
        positional = [w for w in operands if not w.startswith("-")]
        # GNU cp's -t DIRECTORY / --target-directory=DIRECTORY names the destination first, so every
        # positional word is then a source (cp(1), coreutils). rsync's -t is --times and scp's -t its
        # remote mode, so only cp counts.
        target_first = program == "cp" and any(
            w == "--target-directory" or w.startswith("--target-directory=") or re.fullmatch(r"-[A-Za-z]*t.*", w)
            for w in operands)
        if len(positional) >= 2 and not target_first:
            operands.remove(positional[-1])
    return operands


def search_paths(words: list[str], arguments: list[str]) -> list[str]:
    """A search's read arguments without its pattern (see SEARCHERS); any other reader's unchanged."""
    program = program_of(words)
    if program not in SEARCHERS and not (program == "git" and git_subcommand_args(words)[0] == "grep"):
        return arguments
    if any(w in {"--regexp", "--file"} or w.startswith(("--regexp=", "--file="))
           or (re.fullmatch(r"-[^-].*", w) and set(w[1:]) & {"e", "f"}) for w in arguments):
        return arguments  # -e/-f supply the patterns, so every positional word is a file
    for position, word in enumerate(arguments):
        if word == "--":
            return arguments[:position + 1] + arguments[position + 2:]
        if word.startswith("-") and word != "-":
            if word.startswith("--") or not set(word[1:]) <= SEARCH_PLAIN_FLAGS:
                return arguments
            continue
        return arguments[:position] + arguments[position + 1:]
    return arguments


def reader_arguments(words: list[str]) -> list[str] | None:
    """Read arguments of a file reader or search, or None when the segment is neither."""
    program = program_of(words)
    if program in READERS:
        return read_operands(words)
    if program == "git":
        subcommand, rest = git_subcommand_args(words)
        return rest if subcommand == "grep" else None
    if program == "find":
        # Each action's prefix is walked by index, and each position once (prefix_end's `ends`): slicing the rest of the words for every
        # action made 49,000 `-ok` cost 3.9 s (third verification review), and a prefix that runs to the end from every action
        # (`-exec sudo` repeated) cost more than 20 s however it was sliced.
        ends: dict[int, int] = {}
        for position, word in enumerate(words[:-1]):
            if word in FIND_EXEC:
                start = prefix_end(words, position + 1, ends=ends)
                if program_of(words[start:start + 1]) in READERS:
                    return words[1:]
    return None


def is_env_file_word(word: str) -> bool:
    return bool(ENV_FILE_WORD.search(word)) and not word.endswith(".example")


def is_environment_dump(words: list[str]) -> bool:
    """Whether the command prints the environment or every shell variable. A redirection is no argument: `set < FILE` and `set > FILE`
    still print every variable, where `set a b` sets positional parameters (command_arguments drops the redirections)."""
    program = program_of(words)
    if program == "printenv":
        return True
    if program == "env":
        return env_command_start(words) is None
    arguments = command_arguments(words)
    if program in {"set", "export"} and (not arguments or arguments == ["-p"]):
        return True
    if program in {"declare", "typeset"} and all(w.startswith("-") for w in arguments) \
            and (not arguments or any(set(w[1:]) & set("xp") for w in arguments)):
        return True
    return program == "ps" and ps_shows_environment(words)


def dumps_after_source(words: list[str]) -> bool:
    """Forms that print values once a credential file is sourced, even with a name filter."""
    program = program_of(words)
    if is_environment_dump(words):
        return True
    return program in {"declare", "typeset", "export", "readonly", "local"} and any(
        w.startswith("-") and not w.startswith("--") and set(w[1:]) & set("px") for w in words[1:])


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
    # Redirection-shaped words (`{fd}>--json`, `3>x`) are never the subcommand.
    positional = [w for w in arguments if not w.startswith("-") and not re.search(r"[<>]", w)]
    if positional[:1] != ["auth"]:
        return False
    return "--json" not in arguments and "--help" not in arguments


def keyctl_reads_payload(words: list[str]) -> bool:
    """keyctl(1) with a subcommand that prints a payload, or `list`/`rlist` whose target is not an
    unambiguous keyring (KEYCTL_LIST_COMMANDS). keyctl has no options of its own before the command."""
    arguments = command_arguments(words)
    at = next((index for index, word in enumerate(arguments) if not word.startswith("-")), None)
    if at is None:
        return False
    if arguments[at] in KEYCTL_PAYLOAD_COMMANDS:
        return True
    # list and rlist print any key's payload as integers when the target is not a keyring. Target parsing
    # (descriptor digits, redirections) proved bypassable in review, and `kernel_keyring.py status`
    # answers presence, so both are blocked whatever the target.
    return arguments[at] in KEYCTL_LIST_COMMANDS


def launched_commands(words_list: list[list[str]]) -> list[list[str]]:
    """Commands among the arguments of each segment, read from every word that names a program in
    LAUNCHED_PROGRAMS or an interpreter onward and expanded like a command: how a launcher the guard
    does not model (`watch -n 5 python3 -c ...`, `flock f sh -c ...`, `find -exec`) would run them. Each such read
    is one `reads` of the work budget and its characters are counted as any other text's: 1,200 interpreter words in a row
    are 1,200 suffixes, up to 5.8 million characters through shlex, which is what the budget refuses."""
    found = []
    for words in words_list:
        for position in range(1, len(words)):
            if "://" in words[position]:
                continue  # a URL argument (`tvly extract https://.../env`) is never a program a launcher runs
            program = program_of(words[position:position + 1])
            if program in LAUNCHED_PROGRAMS or INTERPRETER.fullmatch(program):
                spend("reads", 1)
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
    the argument's own span, not subtracting a count, keeps any other mention, at any depth, visible. A mention is that span
    when it starts where the span does (the span is a mention of the name, and a mention cannot start inside another one:
    the name is made of identifier characters and a mention has none of them before it), so the spans are kept as a set of
    starts: testing each mention against every span was quadratic (12 million comparisons for 3,500 keyring execs of one
    variable, which took 268 s all told). Two scans of text for each variable (about 25 nanoseconds a character each), so
    1,000 distinct variables in a 42 KB command took 4 s: the work budget counts one unit for every 32 characters read."""
    spend("characters", len(text) // 32)
    name = rf"(?<![A-Za-z0-9_]){re.escape(variable)}(?![A-Za-z0-9_])"
    # The written text may quote the script path and each argument (`"$SP/kernel_keyring.py" exec n "V" --`).
    q = "[\"']?"
    argument_starts = {match.start(1) for match in re.finditer(
        rf"(?<![^\s/\"']){re.escape(KEYRING_SCRIPT)}{q}\s+exec\s+{q}[^\s;&|()<>\"']+{q}\s+{q}({name}){q}\s+--(?=\s|$)",
        text)}
    return any(match.start() not in argument_starts for match in re.finditer(name, text))


def keyring_reason(texts: tuple[str, str], words_list: list[list[str]]) -> str | None:
    """Payload reads in inline code, and what a keyring exec's command does with the key it inherits.
    `texts` is the command as written and unquoted(); every pattern reads both, once (the answer is kept: a scan of 200,000
    characters for each of thousands of started commands was the same scan again)."""
    answers: dict[re.Pattern[str], bool] = {}

    def found(pattern: re.Pattern[str]) -> bool:
        if pattern not in answers:
            answers[pattern] = any(pattern.search(text) for text in texts)
        return answers[pattern]

    if any(INTERPRETER.fullmatch(program_of(words)) for words in words_list) and found(KEYRING_READ_CODE):
        return "keyring_payload_read"
    started = [parsed for parsed in map(keyring_exec, words_list) if parsed is not None]
    # Any mention of an injected variable except exec's own <ENV_VAR> argument names it: in the started
    # command, in code piped into it or in a here-document it reads.
    # Both texts: unquoted() joins KK_DEMO_TO"KEN" into the name, but also merges "$KK_DEMO_TOKEN"x into another one.
    if any(mentions_injected_variable(text, variable)
           for text in texts for variable in {name for name, _ in started if name}):
        return "keyring_variable_reference"
    for started_command in unique_segments([command for _variable, command in started]):
        spend("reads", 1)
        inner = expand(shlex.join(started_command)) if started_command else []
        # The started command, and the commands among its arguments that a launcher the guard does not
        # model would run (launched_commands). The price: a one-word query `env` is blocked too.
        inner = unique_segments(inner + launched_commands(inner))
        if any(dumps_after_source(words) for words in inner):
            return "environment_dump_in_keyring_exec"
        if any(program_of(words) == "systemctl" and systemctl_reason(words) for words in inner):
            return "service_manager_environment"
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
    if program == "systemd-run" and systemd_run_sets_secret(words):
        return "secret_variable_on_command_line"
    if program == "systemctl" and systemctl_reason(words):
        return "service_manager_environment"
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
    if any(POINTER_VARIABLE.search(w) for w in arguments) \
            or any(HOME_CREDENTIAL_STORE.search(w) for w in search_paths(words, arguments)):
        return "credential_file_read"
    if any(HF_HOME_ROOT.search(w) for w in arguments):
        return "native_store_path"
    if any(is_env_file_word(w) for w in arguments):
        return "dotenv_read"
    if any(SECRET_NAME.search(w) for w in arguments):
        return "secret_name_search"
    return None


# The prior reading (2026-09-29 repair round). The guard at c26800f3 (sha256 f9be81b2..., the guard this work started from) read a command
# more simply: it walked only the wrappers in WRAPPERS, named exactly, with getopt's option values and no redirection among them, read no
# systemd launcher and no double-quoted substitution, and found a keyring exec at any position of the words it reached. Three independent
# reviews of this work found commands that it refused and the reading above lets through, each where a walk that reads more of the shell's
# syntax takes a word for something else: the value of an option of systemd-run, run0, systemd-cat or systemd-inhibit that holds the keyring
# script (`systemd-run --description kernel_keyring.py exec n X -- keyctl print 1`), a redirection operator that the old walk took for the
# value of `sudo -u`, a path-qualified wrapper whose option value was the script, the value after a clustered ps option. check() therefore
# reads a command the old way as well when the reading above allows it, and refuses what either refuses: no command that guard refused
# passes, by construction instead of by finding each walk that differs. The functions below are that guard's own and read its tables
# (every table they use is unchanged since, and SECRET_NAMES only grew); they differ from it only where no verdict changes: they spend
# from the work budget, `find -exec` is walked by index, the mentions of an injected variable use the linear test of
# mentions_injected_variable, identical started commands are read once, and a text's words come from lex(), whose legacy reading is that
# guard's tokenizer.
PRIOR_LAUNCHED_PROGRAMS = SHELLS | AWKS | JQS | ENVIRONMENT_PRINTERS | {"ps", "set", "export", "declare", "typeset", "readonly", "local"}


def prior_skip_wrapper_options(words: list[str], index: int, wrapper: str) -> int:
    """Index of the first word after a wrapper's own options, as c26800f3 read them (a redirection operator can be a value here)."""
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


def prior_prefix_end(words: list[str], index: int = 0, ends: dict[int, int] | None = None) -> int:
    """Index of the command in words[index:] as the strip_prefix of c26800f3 found it: past assignments, output redirections and the
    wrappers of WRAPPERS named exactly (timeout with its duration). `ends` as in prefix_end."""
    steps: list[int] = []
    while index < len(words):
        if ends is not None:
            if index in ends:
                index = ends[index]
                break
            steps.append(index)
        word = words[index]
        width = redirection_width(words, index)
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word == "$":
            index += 1
        elif width and REDIRECT_OUT.match(words[index + width - 2]):
            index += width
        elif word in WRAPPERS or word == "timeout":
            index = prior_skip_wrapper_options(words, index + 1, word)
            if word == "timeout":
                index += 1  # timeout's mandatory duration comes before the command
        else:
            break
    if ends is not None:
        for step in steps:
            ends[step] = index
    return index


def prior_strip_prefix(words: list[str]) -> list[str]:
    return words[prior_prefix_end(words):]


def prior_env_command_start(words: list[str]) -> int | None:
    """Index of the command `env [options] [NAME=value ...] command` runs as c26800f3 read it, or None for a dump."""
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


def prior_keyring_exec(words: list[str]) -> tuple[str | None, list[str]] | None:
    """(injected variable, started command) of the first keyring exec in words, at any position, as c26800f3 found it."""
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


def prior_expand(command: str, depth: int = 0) -> list[list[str]]:
    """The command segments that c26800f3 read: of the command, of `sh -c '...'`, `eval ...`, `env ... command`, the command that a
    keyring exec starts and the command an `rtk` invocation runs. Each text is one `texts` and each segment its words and one `words` of
    the work budget: this walk copies the rest of the words at every hop, so a long chain of env, rtk or keyring hops spends the budget
    and is refused as too complex instead of outlasting the hook."""
    spend("texts", 1)
    result: list[list[str]] = []
    for raw in segments(lex(command, legacy=True)):
        words = prior_strip_prefix(raw)
        while words:
            spend("words", len(words) + 1)
            result.append(words)
            program = program_of(words)
            if program == "env":
                start = prior_env_command_start(words)
                if start is None:
                    break
                words = prior_strip_prefix(words[start:])
                continue
            if program == "rtk":
                words = prior_strip_prefix(rtk_command(words))
                continue
            started = prior_keyring_exec(words)
            if started is not None:
                words = prior_strip_prefix(started[1])
                continue
            if depth < MAX_DEPTH:
                if program in SHELLS:
                    inline = shell_parts(words)[1]
                    if inline is not None:
                        result.extend(prior_expand(inline, depth + 1))
                elif program == "eval" and len(words) > 1:
                    result.extend(prior_expand(" ".join(words[1:]), depth + 1))
            break
    return result


def prior_reader_arguments(words: list[str]) -> list[str] | None:
    """reader_arguments as c26800f3 read a segment (its strip_prefix after a `find` action), with each action's prefix walked by index
    and each position once (see reader_arguments)."""
    program = program_of(words)
    if program in READERS:
        return read_operands(words)
    if program == "git":
        subcommand, rest = git_subcommand_args(words)
        return rest if subcommand == "grep" else None
    if program == "find":
        ends: dict[int, int] = {}
        for position, word in enumerate(words[:-1]):
            if word in FIND_EXEC:
                start = prior_prefix_end(words, position + 1, ends)
                if program_of(words[start:start + 1]) in READERS:
                    return words[1:]
    return None


def prior_is_environment_dump(words: list[str]) -> bool:
    program = program_of(words)
    if program == "printenv":
        return True
    if program == "env":
        return prior_env_command_start(words) is None
    if program in {"set", "export"} and (len(words) == 1 or words[1:] == ["-p"]):
        return True
    if program in {"declare", "typeset"} and all(w.startswith("-") for w in words[1:]) \
            and (len(words) == 1 or any(set(w[1:]) & set("xp") for w in words[1:])):
        return True
    return program == "ps" and prior_ps_shows_environment(words)


def prior_dumps_after_source(words: list[str]) -> bool:
    program = program_of(words)
    if prior_is_environment_dump(words):
        return True
    return program in {"declare", "typeset", "export", "readonly", "local"} and any(
        w.startswith("-") and not w.startswith("--") and set(w[1:]) & set("px") for w in words[1:])


def prior_launched_commands(words_list: list[list[str]]) -> list[list[str]]:
    found = []
    for words in words_list:
        for position in range(1, len(words)):
            if "://" in words[position]:
                continue  # a URL argument (`tvly extract https://.../env`) is never a program a launcher runs
            program = program_of(words[position:position + 1])
            if program in PRIOR_LAUNCHED_PROGRAMS or INTERPRETER.fullmatch(program):
                spend("reads", 1)
                found.extend(prior_expand(shlex.join(words[position:])))
    return found


def prior_keyring_reason(texts: tuple[str, str], words_list: list[list[str]]) -> str | None:
    answers: dict[re.Pattern[str], bool] = {}

    def found(pattern: re.Pattern[str]) -> bool:
        if pattern not in answers:
            answers[pattern] = any(pattern.search(text) for text in texts)
        return answers[pattern]

    if any(INTERPRETER.fullmatch(program_of(words)) for words in words_list) and found(KEYRING_READ_CODE):
        return "keyring_payload_read"
    started = [parsed for parsed in map(prior_keyring_exec, words_list) if parsed is not None]
    if any(mentions_injected_variable(text, variable)
           for text in texts for variable in {name for name, _ in started if name}):
        return "keyring_variable_reference"
    for started_command in unique_segments([command for _variable, command in started]):
        spend("reads", 1)
        inner = prior_expand(shlex.join(started_command)) if started_command else []
        inner += prior_launched_commands(inner)
        if any(prior_dumps_after_source(words) for words in inner):
            return "environment_dump_in_keyring_exec"
        programs = {program_of(words) for words in inner}
        if (any(INTERPRETER.fullmatch(program) for program in programs) or programs & AWKS) \
                and found(KEYRING_ENVIRONMENT_ACCESS):
            return "environment_dump_in_keyring_exec"
        if (programs & JQS and found(JQ_ENVIRONMENT)) or (programs & SHELLS and found(SHELL_INDIRECTION)):
            return "environment_dump_in_keyring_exec"
    return None


def prior_segment_reason(words: list[str]) -> str | None:
    program = program_of(words)
    if prior_is_environment_dump(words):
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
    arguments = prior_reader_arguments(words)
    if arguments is None:
        return None
    if any(POINTER_VARIABLE.search(w) for w in arguments) \
            or any(HOME_CREDENTIAL_STORE.search(w) for w in search_paths(words, arguments)):
        return "credential_file_read"
    if any(HF_HOME_ROOT.search(w) for w in arguments):
        return "native_store_path"
    if any(is_env_file_word(w) for w in arguments):
        return "dotenv_read"
    if any(SECRET_NAME.search(w) for w in arguments):
        return "secret_name_search"
    return None


def prior_reading(command: str, texts: tuple[str, str]) -> str | None:
    """The verdict of c26800f3 on a command whose text rules (shared, run first by read_command) found nothing."""
    words_list = prior_expand(command)
    reason = prior_keyring_reason(texts, words_list)
    if reason:
        return reason
    if any(sources_credential_file(words) for words in words_list):
        if any("xtrace" in text or re.search(r"\bSHELLOPTS=", text) for text in texts) \
                or any(traces(words) for words in words_list):
            return "trace_while_sourcing"
        if any(ENVIRONMENT_ACCESS.search(text) for text in texts) \
                or any(prior_dumps_after_source(words) for words in words_list):
            return "environment_dump_after_source"
    for words in words_list:
        reason = prior_segment_reason(words)
        if reason:
            return reason
    return None


def check(command: str) -> str | None:
    """The reason the guard blocks command, or None. It reads a command inside one work budget (WORK_LIMITS) and raises
    WorkBudgetExceeded, instead of returning a reason, when a command needs more than that to be read: main() refuses it."""
    start_work()
    try:
        return read_command(command)
    finally:
        stop_work()


def read_command(command: str) -> str | None:
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
    # Two readings of the words, and a command either refuses is refused (see "The prior reading" above): this version's first, so its
    # reasons stand, and the reading of c26800f3 when this one allows the command.
    return current_reading(command, texts) or prior_reading(command, texts)


def current_reading(command: str, texts: tuple[str, str]) -> str | None:
    """The verdict of this version's reading of the words of a command whose text rules found nothing."""
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
    if len(command) > MAX_COMMAND_CHARACTERS:
        # A hook that times out blocks nothing (see MAX_COMMAND_CHARACTERS), so what the guard cannot read in time is refused, before any
        # rule reads it. The line names no command text, as guard_error's.
        print(f"secret_path_guard: blocked (command_too_large). {HINTS['command_too_large'][0].upper()}"
              f"{HINTS['command_too_large'][1:]}.", file=sys.stderr)
        return 2
    try:
        reason = check(command)
    except WorkBudgetExceeded:
        # The command needs more work than the hook can do inside its timeout, and a hook that times out blocks nothing: refuse it, with one
        # line that names no command text (as command_too_large's), and the hint to split it or put the content in a file.
        print(f"secret_path_guard: blocked (command_too_complex). {HINTS['command_too_complex'][0].upper()}"
              f"{HINTS['command_too_complex'][1:]}.", file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 - RecursionError and MemoryError included
        # Only exit 2 blocks a PreToolUse call: an uncaught exception exits 1 and the command runs. A command the guard cannot read is
        # blocked, with one line that names no command text and no traceback.
        print(f"secret_path_guard: blocked (guard_error). {HINTS['guard_error'][0].upper()}{HINTS['guard_error'][1:]}.",
              file=sys.stderr)
        return 2
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
