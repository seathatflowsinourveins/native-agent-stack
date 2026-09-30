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
are never taken for arguments, and a number is a redirection's descriptor only
where it touches the operator (`set 1>out`, not `set 1 > out`). Segment identities retain that
descriptor metadata. If the original text contains the internal marker byte \x01,
the existing conservative fallback may also count separated numbers as descriptors:
`set 1 > out; echo \x01` is refused. An internal error blocks the command
(`guard_error`), because only exit 2 blocks; a hook that outlasts its timeout does not, so every raw-text rule
takes time linear in the text (four STORE_PATHS patterns that backtracked on a repeated literal are LinearScan
rules since 2026-09-30; before, a claim here that every scan read a text once was not true of them), a text with
no quote and no backslash is split without shlex's per-character word building, a command of more than 200,000
characters is refused (`command_too_large`), and check() reads a command's words, in both readings, inside one
work budget (WORK_LIMITS: characters passed to shlex at their storage width, texts read, words emitted,
launched-command reads) and raises WorkBudgetExceeded when it is gone, which main() refuses (`command_too_complex`);
see docs/secret-storage.md, "An internal error blocks; a timeout does not". It is not a security boundary. A process
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
import unicodedata


class LinearScan:
    """A text rule whose regular expression backtracks on a repeated prefix, answered by a scan that reads the text a bounded number of
    times: search(text) is True exactly when re.search(pattern, text) finds a match (tests/test_secret_path_guard.py compares the two on
    generated texts). Four STORE_PATHS patterns have an unbounded run after a literal that a text can repeat, and the regular expression
    engine reads that run again from every repeat: 102,016 characters of `XDG_CONFIG_HOME:-` took 11.9 s, 54,000 of `HF_HOME:-` 13 to 14 s
    and 80,000 of `/proc` 13 to 15 s (third verification review, 2026-09-29), past a hook timeout of 10 s that fails open, before any work
    budget was charged. Each scan below reads only the runs of the text that the pattern cannot cross and that hold its literal, once each,
    and searches them for literals."""
    __slots__ = ("pattern", "_scan")

    def __init__(self, pattern: str, scan) -> None:
        self.pattern = pattern
        self._scan = scan

    def search(self, text: str) -> bool:
        return self._scan(text)


# A `${NAME:-default}` default (`[^}\s]*`) cannot cross a `}` or a blank, so a match that has one lies in one run of neither, plus the `}`
# that ends the run (DEFAULT_RUN_END finds that end). A path in `/proc/(?:[^/\s]+/)*environ` cannot cross a blank or `//` (its components are
# not empty), so a match lies in one run of neither, which ends at a blank or at the first slash of a `//` (PATH_RUN_END).
DEFAULT_RUN_END = re.compile(r"[}\s]")
PATH_RUN_END = re.compile(r"\s|//")
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
    in the text, since the character after a run is a `}` or a blank, which ends a word as the end of the run does. Only the runs that
    hold a head are read: from the first head, to the end of its run (the next `}` or blank), then from the next head after that run."""
    if plain.search(text):
        return True
    start = text.find(head)
    while start >= 0:
        found = DEFAULT_RUN_END.search(text, start)
        end = found.start() if found else len(text)
        if tail.search(text, start + len(head), end) or (text.startswith("}", end) and tail.match(text, end + 1)):
            return True
        start = text.find(head, end)
    return False


def proc_environ_scan(text: str) -> bool:
    """/proc/(?:[^/\\s]+/)*environ\\b: a `/proc/` and, at or after its last slash in the same path run, `/environ` ending a word. Within a
    run every component is non-empty and blank-free, so any `/environ` after the first `/proc/` of the run completes a match. A path run
    ends at a blank or at the first slash of a `//`, and only the runs that hold a `/proc/` are read (one that a `//` cuts short of its
    last slash holds none)."""
    start = text.find("/proc/")
    while start >= 0:
        found = PATH_RUN_END.search(text, start)
        end = found.start() if found else len(text)
        if end >= start + 6 and ENVIRON_TAIL.search(text, start + 5, end):
            return True
        start = text.find("/proc/", max(end, start + 1))
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
# B(T), the reading of dc33b48a that decides first (read_command), keeps these names. K4 (2026-09-30, contract-v2 section 6.5) adds Claude
# Code's long-lived OAuth token (inventory id claude-oauth-token, injected per command by tools/credentials/credential_run.py) and its
# messaging token; SECRET_NAMES and the patterns below carry every name, and k4_names_and_stores() reads the added two where B did not.
BASE_SECRET_NAMES = SECRET_NAMES
BASE_SECRET_NAME = SECRET_NAME
BASE_SECRET_EXPANSION = SECRET_EXPANSION
BASE_SECRET_LOOKUP = SECRET_LOOKUP
SECRET_NAMES += ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_MESSAGING_TOKEN")
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
# K4 (2026-09-30, contract-v2 section 6.5) adds both entire OmniRoute data trees, ~/.local/share/omniroute (the 20128 gateway) and
# ~/.local/share/omniroute-fw (20129): the directory, a slash or glob in it (also `omniroute*`) and every descendant (db_backups/,
# services/), under any home spelling, and literal $XDG_DATA_HOME/omniroute[-fw] (the ${XDG_DATA_HOME:-...} default form is a recorded
# residual). The data-directory name needs its boundary, so omniroute-notes is no store. B(T) keeps dc33b48a's pattern.
BASE_HOME_CREDENTIAL_STORE = HOME_CREDENTIAL_STORE
K4_NEW_STORE = re.compile(r"(?:^|[/=])\.local/share/omniroute(?:-fw)?(?:[/*?\[]|$)|\$\{?XDG_DATA_HOME\}?/omniroute(?:-fw)?(?:[/*?\[]|$)")
HOME_CREDENTIAL_STORE = re.compile(BASE_HOME_CREDENTIAL_STORE.pattern + "|" + K4_NEW_STORE.pattern)
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
# A number (or bash's `{name}`) that touches the redirection operator after it is that operator's descriptor (`2>/dev/null`, `{fd}>out`);
# one that stands apart is a word (`set 1 > out` sets a positional parameter), and so is a quoted one (Bash Reference Manual,
# "Redirections": the descriptor number precedes the operator). shlex splits `1>out` and `1 > out` alike, so lex() marks each number that
# touches its operator before it splits the text (TOUCHING_DESCRIPTOR, DESCRIPTOR_MARK) and hands it back as a Descriptor, which equals the
# plain number, so every rule that does not ask reads it as before (third verification review, 2026-09-29: the dump rule of `set` read
# `set 1 > out` and `set 3 < input` as `set` with a redirection). A text that holds the mark character itself gets no mark, and there every
# number before an operator counts as its descriptor, the reading before this change.
DESCRIPTOR_MARK = "\x01"
TOUCHING_DESCRIPTOR = re.compile(r"(?<![^ \t\r\n;&|()<>])([0-9]+|\{[A-Za-z_][A-Za-z0-9_]*\})(?=[<>])")
DESCRIPTOR_WORD = re.compile(r"[0-9]+|\{[A-Za-z_][A-Za-z0-9_]*\}")
BACKQUOTE_ESCAPE = re.compile(r"\\([$`\\\"])")


class Descriptor(str):
    """A word that is a redirection's descriptor because it touches the operator after it (see DESCRIPTOR_MARK). It is the number itself for
    every comparison; redirection_width(..., touching_only=True) asks for it by type."""
    __slots__ = ()


def unmark(token: str) -> str:
    """A token of a text that lex() marked, without its marks: a touching descriptor comes back as a Descriptor, any other token as written
    (a mark inside a quoted word is removed)."""
    if DESCRIPTOR_MARK not in token:
        return token
    if token.endswith(DESCRIPTOR_MARK) and DESCRIPTOR_WORD.fullmatch(token[:-1]):
        return Descriptor(token[:-1])
    return token.replace(DESCRIPTOR_MARK, "")
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
# here-document) spends 34% of `characters`, 1% of `words` and `texts` and under 1% of `reads` with both readings (measured 2026-09-30), so
# the limits leave ordinary work far inside them, and 1,000 random mixes of the adversarial shapes at 199,000 characters took about a
# second at most, 0.93 to 1.07 s over runs at load averages of 7 to 23, this version and the guard of 6c4f63d7 alike (the slowest is one
# quoted word of two-byte characters, which shlex reads a character at a time; the median mix fell from 0.24 s to 0.17 s).
WORK_LIMITS = {
    "characters": 400_000,  # characters passed to shlex, each at its storage width (storage_width), over every reading and nesting level
    "texts": 10_000,  # texts read: the command, each double-quoted substitution body, each `sh -c` or `eval` string, each keyring read
    "words": 1_000_000,  # words in the segments that reading emits, each segment counted with one more (a list of words copied)
    "reads": 500,  # commands read again from the words of a keyring exec (the started command, each launched program inside it)
}
# Both readings of a command (this version's and, when it allows the command, the prior reading of c26800f3) spend from the same budget: the
# prior reading counts its texts, its segments' words and its keyring reads the same way, and costs no characters for a text this reading
# has tokenized already (lex() keeps the words), so a command that both read spends each counter once for each reading.
# What check() has spent so far (None outside a check() call, where nothing is counted): start_work() and stop_work() bracket a call.
_work: dict[str, int] | None = None
# The words lex() has read in this check() call, by text and mode (None outside a call): the prior reading tokenizes the command as the
# guard at c26800f3 did, which is this version's legacy reading of the same text, so it costs no second pass (see lex()).
_lexed: dict[tuple[str, bool], list[str]] | None = None
# K4 (2026-09-30, contract-v2 with amendments A1-A13). read_command() first computes B(T), the verdict of the guard at dc33b48a: its names,
# stores, walks and string-tuple segment identity, with _baseline True. Only for a command B allows does it add the K4 tightenings
# (k4_tightenings), with _baseline False: a K4 walk that also reads a runner's started command, the `sh -c`/`eval` text before a keyring or
# runner unwrap, and descriptor metadata in every segment identity (D-ID). _k4_cache holds this check()'s K4 scans by text and mode, and
# _k4_state what B's reading saw that a K4 walk would read differently (a segment dropped as a string duplicate of one whose descriptors differ,
# and whether lex() marked any descriptor at all); both are None outside a check() call. _code_derived is True while a command derived from
# interpreter code (a shell-out or a literal read as shell text) is read, where `keyctl list` is left to the keyring-code rule (section 7.2).
_baseline = True
_k4_cache: dict | None = None
_k4_state: dict | None = None
_code_derived = False
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
    "gateway_credential_route": "local gateway management API requests require an exact allowlist match; use the operator's user terminal for other management operations",
    "manager_environment_write": "a manager/activation environment reaches multiple processes; systemctl --user show-environment can expose it; scope a key to one runner command",
    "keyring_store_literal": "typed literals persist in transcripts/history; use the hidden prompt or documented dynamic input",
    "ps_personality_selector": "a ps personality can change environment-display flags; agent commands cannot select it",
    "canary_user_terminal_required": "canary_proof.py comparison/user-run belong in the user terminal; a pty is not authorization",
    "interpreter_environment_unclassified": "environment access could not be classified; use an explicit single non-secret key or a separately reviewed script",
    "environment_dump_in_credential_run": "credential_run.py gives the started command keys; masking is a second layer; use a client that consumes its environment without printing it",
    "credential_run_usage": "there are no value-returning subcommands; use --check or ID -- COMMAND; see docs/secret-storage.md",
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
    global _work, _lexed, _k4_cache, _k4_state
    _work = dict.fromkeys(WORK_LIMITS, 0)
    _lexed = {}
    _k4_cache = {}
    _k4_state = {"descriptors": False, "collision": False, "depth": 0}
    return _work


def stop_work() -> None:
    """End the budget: outside a check() call nothing is counted, so a direct call to lex() or expand() (a test, a tool) has no limit."""
    global _work, _lexed, _k4_cache, _k4_state
    _work = None
    _lexed = None
    _k4_cache = None
    _k4_state = None


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
    # a Descriptor holds no backquote and keeps its type (str.replace would return a plain str)
    return [token.replace(PROTECTED_BACKQUOTE, "`") if PROTECTED_BACKQUOTE in token else token for token in tokens] if protected else tokens


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
    marked = DESCRIPTOR_MARK not in text and TOUCHING_DESCRIPTOR.search(text) is not None
    source = TOUCHING_DESCRIPTOR.sub(lambda found: found.group(1) + DESCRIPTOR_MARK, text) if marked else text
    if "'" not in source and '"' not in source and "\\" not in source:
        tokens = SHLEX_PLAIN.findall(source.partition("#")[0] if legacy else source)  # what shlex gives, in linear time (see SHLEX_PLAIN)
    else:
        try:
            lexer = shlex.shlex(source, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            if not legacy:
                lexer.commenters = ""
            tokens = list(lexer)
        except ValueError:
            tokens = re.findall(r"[;&|()<>]+|[^\s;&|()<>]+", source)
    if marked:
        tokens = [unmark(token) for token in tokens]
    elif DESCRIPTOR_MARK in text:  # no mark could be set: every number before an operator is its descriptor
        tokens = [Descriptor(token) if DESCRIPTOR_WORD.fullmatch(token) and REDIRECTION.match(tokens[at + 1]) else token
                  for at, token in enumerate(tokens[:-1])] + tokens[-1:]
    if _k4_state is not None and (marked or DESCRIPTOR_MARK in text):
        _k4_state["descriptors"] = True  # some word may be a Descriptor: a segment identity without that metadata can collide (D-ID)
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


def redirection_width(words: list[str], index: int, touching_only: bool = False) -> int:
    """How many words the redirection at words[index] takes (operator and target, with a descriptor
    number before it and the `-` of `<<- EOF`), or 0 when it starts none. A digit before an operator is
    read as its descriptor, since shlex splits `2>` and `2 >` alike; with `touching_only`, only one that
    touched the operator in the text (a Descriptor, see DESCRIPTOR_MARK), so `1 > out` is the word 1 and a redirection."""
    word = words[index]
    # A descriptor before the operator: a number, or bash's named form `{varname}` (`{fd}>file`).
    if (word.isdigit() or re.fullmatch(r"\{[A-Za-z_][A-Za-z0-9_]*\}", word)) and index + 1 < len(words) \
            and REDIRECTION.match(words[index + 1]) and (not touching_only or isinstance(word, Descriptor)):
        return 1 + redirection_width(words, index + 1, touching_only)
    if not REDIRECTION.match(word):
        return 0
    return 3 if word == "<<" and words[index + 1:index + 2] == ["-"] else 2


def command_arguments(words: list[str], touching_only: bool = False) -> list[str]:
    """words[1:] without redirections, so a redirection's target (`tvly auth > --json` writes to a
    file named --json) or a here-document delimiter is never taken for an argument. `touching_only` as in
    redirection_width."""
    result, index = [], 1
    while index < len(words):
        width = redirection_width(words, index, touching_only)
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
        if any(assignment.partition("=")[0] in (BASE_SECRET_NAMES if _baseline else SECRET_NAMES) for assignment in assignments):
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
    readings of one text, a command that stands twice in a script) gets the same verdict twice, so the second copy only adds work.
    Segments are the same by segment_identity(): their words for B(T), their words and which of them are descriptors for K4 (D-ID)."""
    seen: dict[tuple, list[str]] = {}
    result = []
    for words in segments:
        key = segment_identity(words)
        kept = seen.get(key)
        if kept is None:
            seen[key] = words
            result.append(words)
        else:
            note_identity_collision(kept, words)
    return result


def segment_identity(words: list[str]) -> tuple:
    """The identity under which segments (and started commands) are deduplicated. B(T) keeps the string tuple of dc33b48a, in which the
    positional word "0" of `set 0 < /dev/null` and the descriptor "0" of `set 0</dev/null` are equal; the K4 reading (D-ID, contract-v2 section 3)
    adds each word's descriptor metadata, so the two segments stay distinct and each is read."""
    if _baseline:
        return tuple(words)
    return tuple((str(word), isinstance(word, Descriptor)) for word in words)


def descriptor_positions(words: list[str]) -> tuple[int, ...]:
    """The positions of the words that are descriptors (Descriptor), the metadata D-ID adds to a segment's identity."""
    return tuple(at for at, word in enumerate(words) if isinstance(word, Descriptor))


def note_identity_collision(kept: list[str], dropped: list[str]) -> None:
    """Record, while B(T) reads a command, that a string-tuple deduplication dropped a segment whose descriptors differ from the one it kept:
    only then can the K4 walk (metadata identity) read a segment that B did not, so only then does k4_tightenings walk the command again.
    Nothing is compared unless lex() marked some descriptor in this check() (no Descriptor exists otherwise)."""
    if _k4_state is not None and _baseline and _k4_state["descriptors"] and not _k4_state["collision"] \
            and descriptor_positions(kept) != descriptor_positions(dropped):
        _k4_state["collision"] = True


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
    seen: dict[tuple, list[str]] = {}

    def emit(segment: list[str]) -> None:
        spend("words", len(segment) + 1)
        result.append(segment)

    readings = [tokenize(command, comments, protected=protected, ansi_c=ansi_c)]
    if "#" in command or protected or comments or ansi_c:
        readings.append(tokenize(command, legacy=True))
    for reading, tokens in enumerate(readings):
        for raw in segments(tokens):
            key = segment_identity(raw)
            if reading:
                kept = seen.get(key)
                if kept is not None:
                    note_identity_collision(kept, raw)
                    continue
            else:
                seen.setdefault(key, raw)
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
                # The K4 walk (RUN-START, contract-v2 section 4) reads a shell's `-c` string or an eval's text before any keyring or
                # runner unwrap, so an argument shaped like a runner or keyring start cannot hide the real shell program
                # (`bash -c 'printenv' kernel_keyring.py exec n X -- true`), and it follows a runner's started command. B(T) keeps
                # dc33b48a's order below.
                if not _baseline and depth < MAX_DEPTH:
                    if program in SHELLS:
                        inline = shell_parts(words)[1]
                        if inline is not None:
                            result.extend(expand(inline, depth + 1))
                    elif program == "eval" and len(words) > 1:
                        result.extend(expand(" ".join(words[1:]), depth + 1))
                if not _baseline:
                    runner = k4_runner_start(words)
                    if runner is not None:
                        keyring_at = next((at for at, word in enumerate(words)
                            if word.rsplit('/', 1)[-1] == KEYRING_SCRIPT
                            and words[at + 1:at + 2] == ['exec']), len(words))
                        if runner[0] < keyring_at:
                            spend("reads", 1)
                            words = strip_prefix(runner[2])
                            continue
                started = keyring_exec(words)
                if started is not None:
                    words = strip_prefix(started[1])
                    continue
                if _baseline and depth < MAX_DEPTH:
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
                following = words[position + 1]
                if following.startswith("-") and "/" not in following:
                    continue  # an option word is no assignment, redirection or launcher name, and no reader: the walk would stop on it
                start = prefix_end(words, position + 1, ends=ends)
                if program_of(words[start:start + 1]) in READERS:
                    return words[1:]
    return None


def is_env_file_word(word: str) -> bool:
    return bool(ENV_FILE_WORD.search(word)) and not word.endswith(".example")


def is_environment_dump(words: list[str]) -> bool:
    """Whether the command prints the environment or every shell variable. A redirection is no argument: `set < FILE` and `set > FILE`
    still print every variable, where `set a b` sets positional parameters (command_arguments drops the redirections). A number is a
    redirection's descriptor here only when it touches the operator (`set 1>out`, `set 2>/dev/null` print every variable), and an argument
    when it stands apart (`set 1 > out` and `set 3 < input` set positional parameters: third verification review, 2026-09-29)."""
    program = program_of(words)
    if program == "printenv":
        return True
    if program == "env":
        return env_command_start(words) is None
    if program == "ps":
        return ps_shows_environment(words)
    if program not in {"set", "export", "declare", "typeset"}:
        return False
    arguments = command_arguments(words, touching_only=True)
    if program in {"set", "export"} and (not arguments or arguments == ["-p"]):
        return True
    return program in {"declare", "typeset"} and all(w.startswith("-") for w in arguments) \
        and (not arguments or any(set(w[1:]) & set("xp") for w in arguments))


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
    return arguments[at] in KEYCTL_LIST_COMMANDS and not _code_derived


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
                found.extend(expand(shlex.join(words[position:]) if _baseline else k4_join(words[position:])))
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
            or any((BASE_HOME_CREDENTIAL_STORE if _baseline else HOME_CREDENTIAL_STORE).search(w) for w in search_paths(words, arguments)):
        return "credential_file_read"
    if any(HF_HOME_ROOT.search(w) for w in arguments):
        return "native_store_path"
    if any(is_env_file_word(w) for w in arguments):
        return "dotenv_read"
    if any((BASE_SECRET_NAME if _baseline else SECRET_NAME).search(w) for w in arguments):
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
                following = words[position + 1]
                if following.startswith("-") and "/" not in following:
                    continue  # as in reader_arguments: the walk would stop on an option word, which is no reader
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
            or any((BASE_HOME_CREDENTIAL_STORE if _baseline else HOME_CREDENTIAL_STORE).search(w) for w in search_paths(words, arguments)):
        return "credential_file_read"
    if any(HF_HOME_ROOT.search(w) for w in arguments):
        return "native_store_path"
    if any(is_env_file_word(w) for w in arguments):
        return "dotenv_read"
    if any((BASE_SECRET_NAME if _baseline else SECRET_NAME).search(w) for w in arguments):
        return "secret_name_search"
    return None


def prior_reading(command: str, texts: tuple[str, str], words_list: list[list[str]] | None = None) -> str | None:
    """The verdict of c26800f3 on a command whose text rules (shared, run first by read_command) found nothing. `words_list` is the
    command's prior_expand() when the caller already has it (read_command keeps it for the K4 tightenings)."""
    if words_list is None:
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


def read_command(command: str, top: bool = True) -> str | None:
    """The reason to refuse command inside the current work budget. First B(T), the verdict of the guard at dc33b48a, unchanged: its
    whole-text rules, then this version's reading of the words and, when that allows, the reading of c26800f3, with dc33b48a's names,
    stores and segment identity (_baseline True). A command B refuses keeps B's reason. Only a command B allows gets the K4 tightenings
    (k4_tightenings), each of which can only refuse.

    The one loosening (L1, contract-v2 section 7.1) is form F: a top-level Python or Node program on stdin through exactly one quoted
    here-document that ends the command (k4_form_f). For F, the two word readings read the command with the body emptied (amendment A5:
    the operator line directly followed by its terminator line, and texts of that masked command), while the whole-text rules and the
    keyring-code rule still read the original text, body included, and the body is read as Python or JavaScript code by the K4 CODE rules
    instead of as shell lines. Nothing else is ever masked: a here-document of any other shape keeps both readings of every line.

    `top` is False for a text the K4 rules derive (a post-terminator tail, a literal or a shell-out read as shell text): such a text never
    qualifies as form F and is read through this same budget, never through a fresh check()."""
    global _baseline
    previous = _baseline
    _baseline = True
    try:
        # The shell removes a backslash-newline before it splits words, so the rules read the joined command.
        # Each text pattern also reads it without quoting: `sh -c 'echo $GH_TO''KEN'` hands the inner shell
        # `echo $GH_TOKEN`. (Where quoting does end a name, as in `"$GH_TO"KEN`, that errs toward blocking.)
        joined = command.replace("\\\n", "")
        texts = (joined, unquoted(joined))
        reason = base_text_reason(texts)
        if reason:
            return reason
        form = k4_form_f(command) if top else None
        if form is None:
            word_text, word_texts = joined, texts
        else:
            masked = command[:form.body_start] + command[form.body_end:]
            k4_charge(masked, 2)
            word_text = masked.replace("\\\n", "")
            word_texts = (word_text, unquoted(word_text))
        # Two readings of the words, and a command either refuses is refused (see "The prior reading" above): this version's first, so its
        # reasons stand, and the reading of c26800f3 when this one allows the command.
        current = expand(word_text)
        reason = current_reading(word_text, word_texts, current)
        if reason:
            return reason
        prior = prior_expand(word_text)
        reason = prior_reading(word_text, word_texts, prior)
        if reason:
            return reason
        if form is not None:
            # Retained inside F: keyring code (KEYCTL_READ, keyctl print ...) in the body, which the masked readings did not see.
            k4_charge(joined, 2)
            reason = keyring_reason(texts, current)
            if reason:
                return reason
        return k4_tightenings(K4Reading(command, joined, texts, form, word_text, word_texts, current, prior))
    finally:
        _baseline = previous


def base_text_reason(texts: tuple[str, str]) -> str | None:
    """The whole-text rules of dc33b48a, run first on the joined command and its unquoted() text, with dc33b48a's secret names."""
    for text in texts:
        for pattern, reason in STORE_PATHS:
            if pattern.search(text):
                return reason
        if PROC_WORD.search(text) and re.search(r"\benviron\b", text):
            return "process_environment"
        if BASE_SECRET_EXPANSION.search(text) or BASE_SECRET_LOOKUP.search(text):
            return "secret_variable_reference"
    return None


def current_reading(command: str, texts: tuple[str, str], words_list: list[list[str]] | None = None,
                    known: set[tuple] | None = None) -> str | None:
    """The verdict of this version's reading of the words of a command whose text rules found nothing. `words_list` is the command's
    expand() when the caller already has it. With `known` (the K4 walk, k4_walk_reason), the per-segment rules skip the segments whose
    identity is in it, which B(T) has read already."""
    if words_list is None:
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
        if known is not None and segment_identity(words) in known:
            continue
        reason = segment_reason(words)
        if reason:
            return reason
    return None


# ------------------------------------------------------------------------------------------------------------------------------------------
# K4 (contract-v2, 2026-09-30, with the coordinator's amendments A1-A13): the tightenings of a command B(T) allows, and form F.
# ------------------------------------------------------------------------------------------------------------------------------------------
# The literal each K4 rule needs before it can refuse: a runner, keyring or canary basename, a gateway port, a selector or new secret name, a
# data-tree name, a manager verb, a here-document operator, an environment source. Quote removal never splits these literals (they hold no
# quote or backslash) and every word of a command is made of its unquoted() characters in order, so one scan of the unquoted text tells which
# rules can apply at all: an ordinary command pays one charged pass for K4, and a rule whose literal is absent does no work.
K4_ANCHOR = re.compile(r"<<|CLAUDE_CODE_|omniroute|credential_run\.py|kernel_keyring\.py|tvly-keyring|2012[89]|environment|environ"
                       r"|process|PS_PERSONALITY|CMD_ENV|I_WANT_A_BROKEN_PS|canary_proof\.py")
K4_ANCHOR_KEYS = {"20128": ("2012",), "20129": ("2012",), "environment": ("environment", "environ")}
# A K4 walk differs from B's only where a runner or keyring start (or tvly-keyring) can hide a shell string or start a command, or where a
# string-tuple deduplication dropped a segment with other descriptors (note_identity_collision).
K4_REWALK_ANCHORS = frozenset({"credential_run.py", "kernel_keyring.py", "tvly-keyring"})
K4_SELECTORS = frozenset({"PS_PERSONALITY", "CMD_ENV", "I_WANT_A_BROKEN_PS"})
K4_ENVIRONMENT_ANCHORS = frozenset({"environ", "process"})
K4_PYTHON = re.compile(r"\A(?:python(?:3|[0-9]+\.[0-9]+)?|pypy3?)\Z")
K4_IDENTIFIER = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*\Z")
K4_QUOTES = re.compile(r"[\"'\\]")
# The two Claude Code secret names K4 adds (contract-v2 section 6.5); SECRET_NAMES holds them, BASE_SECRET_NAMES (B's) does not. The added
# data trees are OmniRoute's two local data directories, at their root, a slash or glob in them, or any descendant (db_backups/, services/).
K4_NEW_NAMES = ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_MESSAGING_TOKEN")
K4_NEW_NAME = re.compile(r"\b(?:" + "|".join(K4_NEW_NAMES) + r")\b")
K4_NEW_NAME_TEXT = re.compile(r"\$\{?!?(?:" + "|".join(K4_NEW_NAMES) + r")\b"
                              r"|(?:environ|getenv|process\.env|ENV\[)[^;\n]{0,40}\b(?:" + "|".join(K4_NEW_NAMES) + r")\b")


def k4_charge(text: str, passes: int = 1) -> None:
    """Charge the work budget before a new linear scan of text: max(1, ceil(len(text) / 32)) character units a pass (contract-v2 section 1,
    invariant 5). No K4 scan reads a text before its charge."""
    spend("characters", max(1, (len(text) + 31) // 32) * passes)


def k4_word_charge(words: list[str]) -> None:
    """Charge a pass over a list of words: its words (and one), and its characters as k4_charge() does."""
    spend("words", len(words) + 1)
    spend("characters", max(1, (sum(map(len, words)) + 31) // 32))


def k4_anchors(unquoted_text: str) -> frozenset[str]:
    """The K4 anchors (K4_ANCHOR) that occur in a command's unquoted text: one charged pass."""
    k4_charge(unquoted_text)
    found: set[str] = set()
    for match in K4_ANCHOR.finditer(unquoted_text):
        literal = match.group()
        found.update(K4_ANCHOR_KEYS.get(literal, (literal,)))
    return frozenset(found)


class K4Reading:
    """What read_command() hands the K4 tightenings of one command that B(T) allows: the command as written, its joined text and texts, form F
    (or None), the text the two word readings read (the masked command inside F) with its texts, and the segments of B's two readings."""
    __slots__ = ("command", "joined", "texts", "form", "word_text", "word_texts", "current", "prior", "anchors", "units")

    def __init__(self, command, joined, texts, form, word_text, word_texts, current, prior):
        self.command, self.joined, self.texts, self.form = command, joined, texts, form
        self.word_text, self.word_texts, self.current, self.prior = word_text, word_texts, current, prior
        self.anchors: frozenset[str] = frozenset()
        self.units: list | None = None


def k4_tightenings(r: K4Reading) -> str | None:
    """The K4 rules for a command B(T) allows, in the deterministic order of contract-v2 section 3, step 4: (a) the added secret names and
    data stores; (b) the runner's keyring-equivalent rules, then every existing rule on what only the K4 walk reads (a runner's started
    command, a shell string read before a keyring or runner unwrap, a segment B dropped as a string duplicate of one with other descriptors:
    D-ID, at the environment-dump position of this reading); (c) runner usage and secret-name mentions; (d) gateway requests; (e) manager
    environment writes; (f) literal keyring stores; (g) ps personality selectors; (h) the canary gate; (i) interpreter code, SHELL-LITERAL,
    SHELL-OUT, then WHOLE-ENV; (j) post-terminator tails. Every rule only refuses. Runs with _baseline False (read_command restores it)."""
    global _baseline
    _baseline = False
    anchors = r.anchors = k4_anchors(r.texts[1])
    collision = _k4_state is not None and _k4_state["collision"]
    rewalk = collision or bool(anchors & K4_REWALK_ANCHORS)
    walked = expand(r.word_text) if rewalk else r.current
    segments = unique_segments(walked + r.prior)
    runner = "credential_run.py" in anchors
    return (k4_names_and_stores(r, segments)
            or (k4_runner_environment(r.texts, walked) if runner else None)
            or (k4_walk_reason(r, walked) if rewalk else None)
            or (k4_runner_usage_reason(r.word_text, segments) if runner else None)
            or (k4_gateway_reason(r, segments) if anchors & {"2012", "omniroute"} else None)
            or (k4_manager_reason(segments) if "environment" in anchors else None)
            or (k4_store_reason(r.word_text) if "kernel_keyring.py" in anchors else None)
            or (k4_ps_reason(r.word_text) if anchors & K4_SELECTORS else None)
            or (k4_canary_reason(segments) if "canary_proof.py" in anchors else None)
            or k4_interpreter_reason(r, segments)
            or (k4_tail_reason(r.command) if "<<" in anchors else None))


def k4_walk_reason(r: K4Reading, walked: list[list[str]]) -> str | None:
    """Tier (b): this version's reading (keyring rules, sourcing rules and each segment's rules) of the K4 walk, whose segments B's walk did
    not read. The K4 walk reads what B's reads and more, so a segment B read (same identity with its descriptors) is not read again."""
    known = {segment_identity(words) for words in r.current}
    return current_reading(r.word_text, r.word_texts, walked, known)


def k4_names_and_stores(r: K4Reading, segments: list[list[str]]) -> str | None:
    """Tier (a): the two added secret names in the whole-text expansion and lookup rules, and in the segment rules of dc33b48a that read
    names (a search's or reader's arguments, a systemd-run -E/--setenv/-p Environment= name); the two OmniRoute data trees as a reader's,
    copy's or search's operand (credential_file_read). Only the added names and trees are read here: B(T) has read every other one."""
    names, stores = "CLAUDE_CODE_" in r.anchors, "omniroute" in r.anchors
    if names:
        k4_charge(r.joined, 2)
        if any(K4_NEW_NAME_TEXT.search(text) for text in r.texts):
            return "secret_variable_reference"
    if not (names or stores):
        return None
    for words in segments:
        k4_word_charge(words)
        if any("CLAUDE_CODE_" in word or "omniroute" in word for word in words):
            reason = k4_names_stores_segment(words, names, stores)
            if reason:
                return reason
    return None


def k4_names_stores_segment(words: list[str], names: bool, stores: bool) -> str | None:
    program = program_of(words)
    if names and program == "systemd-run" and any(name in K4_NEW_NAMES for name in systemd_run_variables(words)):
        return "secret_variable_on_command_line"
    readings = [reader_arguments(words)]
    if program == "find":
        readings.append(prior_reader_arguments(words))  # the prior reading walks a find action's prefix as c26800f3 did
    for arguments in readings:
        if arguments is None:
            continue
        if stores and any(K4_NEW_STORE.search(word) for word in search_paths(words, arguments)):
            return "credential_file_read"
        if names and any(K4_NEW_NAME.search(word) for word in arguments):
            return "secret_name_search"
    return None


def systemd_run_variables(words: list[str]) -> list[str]:
    """The variable names a systemd-run command line sets for its unit (-E/--setenv NAME[=VALUE], -p/--property Environment=...), as
    systemd_run_sets_secret() reads them."""
    found: list[str] = []
    for name, value in wrapper_options(words, 1, "systemd-run")[0]:
        if value is None:
            continue
        if name in {"-E", "--setenv"}:
            found.append(value.partition("=")[0])
        elif name in {"-p", "--property"} and value.lower().startswith("environment="):
            found.extend(assignment.partition("=")[0] for assignment in environment_assignments(value.partition("=")[2]))
    return found


class K4Word(str):
    """Quote-removed word with literal/offset provenance, never shell evaluated."""
    __slots__ = ("start", "end", "literal", "origins")

    def __new__(cls, value, start, end, literal, origins):
        word = super().__new__(cls, value)
        word.start, word.end = start, end
        word.literal, word.origins = literal, tuple(origins)
        return word


class K4Descriptor(K4Word, Descriptor):
    """A touching descriptor with the original K4 quote/offset provenance."""


def k4_shell_words(text: str, origins=None) -> list[K4Word]:
    """Small quote/provenance scanner supplementing K3's shell walker.

    Source: scan_shell/lex at dc33b48a and Bash 5.2.21 word quoting.
    It does not grant shell-syntax exceptions. Unknown expansion stays dynamic.
    """
    key = ('shell-words', text, tuple(origins) if origins is not None else None)
    if _k4_cache is not None and key in _k4_cache:
        return _k4_cache[key]
    k4_charge(text)
    spend("texts", 1)
    result, at, size = [], 0, len(text)
    origin = (lambda index: origins[index]) if origins is not None else (lambda index: index)
    while at < size:
        if text[at] in ' \t\r':
            at += 1
            continue
        if text[at] == '#':
            after = text.find('\n', at)
            at = size if after < 0 else after
            continue
        start = at
        if text[at] in ';&|()<>\n':
            if text[at] == '\n':
                at += 1
            else:
                while at < size and text[at] in ';&|()<>':
                    at += 1
            value = ';' if text[start:at] == '\n' else text[start:at]
            result.append(K4Word(value, start, at, True, [origin(i) for i in range(start, at)]))
            continue
        value, locations, quote, literal = [], [], '', True
        while at < size:
            ch = text[at]
            if not quote and ch in ' \t\r\n;&|()<>':
                break
            if ch == '\\' and quote != "'":
                if at + 1 < size:
                    at += 1
                    if text[at] != '\n':
                        value.append(text[at]); locations.append(origin(at))
                    at += 1
                    continue
                literal = False
            if ch in "'\"" and (not quote or quote == ch):
                quote = ch if not quote else ''
                at += 1
                continue
            if quote != "'" and ch in '$`':
                literal = False
            value.append(ch); locations.append(origin(at))
            at += 1
        value = ''.join(value)
        touching = (at < size and text[at] in '<>' and text[start:at] == value
                    and (value.isascii() and value.isdigit() or value.startswith('{') and value.endswith('}')
                         and K4_IDENTIFIER.fullmatch(value[1:-1])))
        cls = K4Descriptor if touching else K4Word
        result.append(cls(value, start, at, literal and not quote, locations))
    spend("words", len(result) + 1)
    if _k4_cache is not None:
        _k4_cache[key] = result
    return result


# Interpreter options (contract-v2 section 7.4; RUN-POSITION, section 4), from the installed CLIs' help read 2026-09-30: Python 3.13.15
# (`python3 --help`: -c and -m end the options, -W and -X take a value, --check-hash-based-pycs takes one, the other one-letter options
# are flags) and Node v24.21.0 (`node --help`: the options shown with `=...` take a value, also as the next word; -e/--eval and -p/--print
# take the code; every other option is a flag, and V8's own options take a value only after `=`).
K4_PY_FLAGS = frozenset("bBdEhiIOPqsSuvVx?")
K4_PY_LONG_VALUE = frozenset({"--check-hash-based-pycs"})
K4_PY_LONG_FLAGS = frozenset({"--help", "--help-env", "--help-xoptions", "--help-all", "--version"})
K4_NODE_SHORT_FLAGS = frozenset("chiv")
K4_NODE_SHORT_VALUE = frozenset("rC")
K4_NODE_VALUE = frozenset({
    "--allow-fs-read", "--allow-fs-write", "--build-snapshot-config", "--conditions", "--cpu-prof-dir", "--cpu-prof-interval",
    "--cpu-prof-name", "--diagnostic-dir", "--disable-proto", "--disable-warning", "--dns-result-order", "--env-file",
    "--env-file-if-exists", "--experimental-config-file", "--loader", "--experimental-loader", "--experimental-package-map",
    "--experimental-sea-config", "--experimental-test-tag-filter", "--heap-prof-dir", "--heap-prof-interval", "--heap-prof-name",
    "--heapsnapshot-near-heap-limit", "--heapsnapshot-signal", "--icu-data-dir", "--import", "--input-type", "--debug-port",
    "--inspect-port", "--inspect-publish-uid", "--localstorage-file", "--max-http-header-size", "--max-old-space-size-percentage",
    "--network-family-autoselection-attempt-timeout", "--openssl-config", "--redirect-warnings", "--report-directory", "--report-dir",
    "--report-filename", "--report-signal", "--require", "--run", "--secure-heap", "--secure-heap-min", "--snapshot-blob",
    "--test-concurrency", "--test-coverage-branches", "--test-coverage-exclude", "--test-coverage-functions", "--test-coverage-include",
    "--test-coverage-lines", "--test-global-setup", "--test-isolation", "--experimental-test-isolation", "--test-name-pattern",
    "--test-random-seed", "--test-reporter", "--test-reporter-destination", "--test-rerun-failures", "--test-shard",
    "--test-skip-pattern", "--test-timeout", "--title", "--tls-cipher-list", "--tls-keylog", "--trace-event-categories",
    "--trace-event-file-pattern", "--trace-require-module", "--unhandled-rejections", "--use-largepages", "--v8-pool-size",
    "--watch-kill-signal", "--watch-path"})


def k4_program_operand(words: list[str]) -> tuple[str, int, str | None, bool]:
    """(kind, index, code, certain) of a Python or Node command line: where its program comes from, read as the interpreter reads its own
    options and never run. kind is 'script' (words[index] is the script), 'stdin' (explicit `-` or no operand: the program is read from
    stdin), 'inline' (-c CODE, -e/--eval CODE, attached -cCODE or -eCODE, a cluster ending in c: -Ic, -ISc), 'print' (Node's -p/--print:
    evaluate and print), 'module' (-m) or 'other' (neither interpreter). `--` ends the options (the script follows) and so do a script and
    `-`, so a later word named -c is the script's argument. `certain` is False when an unknown option stood before the operand: its arity is
    unknown, so a visible environment source among the words fails closed (k4_code_units)."""
    k4_word_charge(words)
    program = program_of(words)
    python = bool(K4_PYTHON.fullmatch(program))
    if not python and program not in {"node", "nodejs"}:
        return "other", 0, None, True
    certain = True
    at = 1
    while at < len(words):
        after = skip_redirections(words, at)
        if after != at:
            at = after
            continue
        word = words[at]
        following = words[at + 1] if at + 1 < len(words) else None
        if word == "--":
            return "script", at + 1, None, certain
        if word == "-":
            return "stdin", at, None, certain
        if not word.startswith("-"):
            return "script", at, None, certain
        if python:
            if word.startswith("--"):
                name, equals, _value = word.partition("=")
                if name in K4_PY_LONG_VALUE:
                    at += 0 if equals else 1
                elif name not in K4_PY_LONG_FLAGS:
                    certain = False
            else:
                for position in range(1, len(word)):
                    option = word[position]
                    if option in "cm":
                        code = word[position + 1:] or following
                        return ("inline" if option == "c" else "module"), at, code, certain
                    if option in "WX":
                        at += 0 if position + 1 < len(word) else 1
                        break
                    if option not in K4_PY_FLAGS:
                        certain = False
        else:
            name, equals, value = word.partition("=")
            if name in {"-e", "--eval", "-p", "--print"}:
                return ("inline" if name in {"-e", "--eval"} else "print"), at, value if equals else following, certain
            if not word.startswith("--"):
                letters = word[1:]
                if letters[0] in "ep":
                    if set(letters) <= {"e", "p"}:  # -pe, -ep: print what the next word evaluates to
                        return ("print" if "p" in letters else "inline"), at, following, certain
                    return ("print" if letters[0] == "p" else "inline"), at, letters[1:], certain
                if letters[0] in K4_NODE_SHORT_VALUE:
                    at += 0 if len(letters) > 1 else 1
                elif not set(letters) <= K4_NODE_SHORT_FLAGS:
                    certain = False
            elif name in K4_NODE_VALUE:
                at += 0 if equals else 1
        at += 1
    return "stdin", at, None, certain


def k4_script_position(words: list[str], script: str, uv: bool = False) -> int | None:
    """Index of `script` (a basename) as the command itself or as the script operand of python/python3/pythonX.Y/pypy/pypy3 (options read
    as k4_program_operand reads them), or with `uv`, of `uv run [options] [python ...] SCRIPT`; None when words do not invoke it (a mention
    in `git add`, `sed`, `echo`, `python3 -m py_compile ...`)."""
    k4_word_charge(words)
    if not words:
        return None
    if program_of(words) == script:
        return 0
    if uv and program_of(words) == "uv" and words[1:2] == ["run"]:
        at = 2
        while at < len(words) and words[at].startswith("-"):
            at += 1
        nested = k4_script_position(words[at:], script)
        return at + nested if nested is not None else None
    if K4_PYTHON.fullmatch(program_of(words)):
        kind, at, _code, _certain = k4_program_operand(words)
        if kind == "script" and at < len(words) and words[at].rsplit("/", 1)[-1] == script:
            return at
    return None


def k4_runner_start(words: list[str]):
    """(index, runner arguments, started command) of the first word whose basename is credential_run.py that a later `--` follows, at any
    position of words (RUN-START, contract-v2 section 4: any path, any launcher, `uv run python ...`), or None. Input redirections among the
    runner's own arguments are read with the command it starts, as keyring_exec() does."""
    k4_word_charge(words)
    for at, word in enumerate(words):
        if word.rsplit('/', 1)[-1] == 'credential_run.py':
            end = next((i for i in range(at + 1, len(words)) if words[i] == '--'), None)
            if end is None:
                return None
            moved, index = [], at + 1
            while index < end:
                after = skip_redirections(words, index, moved)
                index = after if after != index else index + 1
            return at, words[at + 1:end], words[end + 1:] + moved
    return None


def k4_join(words: list[str]) -> str:
    """shlex.join with descriptor adjacency preserved in derived shell text."""
    k4_word_charge(words)
    parts, join_next = [], False
    for word in words:
        if parts and not join_next:
            parts.append(' ')
        parts.append(str(word) if isinstance(word, Descriptor) or REDIRECTION.fullmatch(word) else shlex.quote(word))
        join_next = isinstance(word, Descriptor)
    return ''.join(parts)


def k4_runner_mentions(command: str) -> bool:
    """Whole-text names, with only invocation-owned --only value spans exempt.

    Offset sets make membership constant time. An --only in a mention, another
    command, or after the first -- never grants a permission.
    """
    k4_charge(command, 3)
    exempt, pending, seen = set(), [(command, None, 0)], set()
    while pending:
        text, origins, depth = pending.pop()
        tokens = k4_shell_words(text, origins)
        for raw in segments(tokens):
            words = strip_prefix(raw)
            _entries, start, _moved = launcher_chain(words)
            words = words[start:]
            scan = words
            while scan:
                parsed = k4_runner_start(scan)
                at = parsed[0] if parsed else k4_script_position(scan, 'credential_run.py')
                if at is None:
                    break
                end = next((i for i in range(at + 1, len(scan)) if scan[i] == '--'), len(scan))
                own = command_arguments(scan[at:end], touching_only=True)
                for i, value in enumerate(own[1:], 1):
                    if own[i - 1] == '--only' and value in SECRET_NAMES and getattr(value, 'literal', False):
                        exempt.add(value.origins[0])
                scan = scan[end + 1:]
            if depth < MAX_DEPTH and program_of(words) in SHELLS:
                inline = shell_parts(words)[1]
                if isinstance(inline, K4Word):
                    key = (str(inline), inline.origins)
                    if key not in seen:
                        seen.add(key)
                        pending.append((str(inline), inline.origins, depth + 1))
    if any(found.start() not in exempt for found in SECRET_NAME.finditer(command)):
        return True
    plain, offsets = [], []
    for at, ch in enumerate(command):
        if ch not in "\"'\\":
            plain.append(ch); offsets.append(at)
    return any(offsets[found.start()] not in exempt for found in SECRET_NAME.finditer(''.join(plain)))


def k4_runner_environment(texts: tuple[str, str], words_list: list[list[str]]) -> str | None:
    """RUN-ENV (contract-v2 section 4, tier b): what the command a credential_run.py start runs does with the keys it inherits, read as
    keyring_reason() reads a keyring exec's command. The started command and the commands among its arguments that an unmodelled launcher
    runs (launched_commands: watch, flock, find -exec, time -f) are read again (one `reads` each); an environment dump among them refuses as
    environment_dump_in_credential_run, a manager dump as service_manager_environment, and an inner interpreter or awk with environment access
    anywhere in the whole text (piped code, here-document bodies), jq with `env`, or a shell with `${!...}` as environment_dump_in_credential_run.
    `texts` are the whole command's texts, form F's body included. Raw /proc/*/environ, secret expansion, pointer and native-token rules keep
    their own reasons (B(T) and the K4 walk read them first)."""
    starts = [parsed for words in words_list if (parsed := k4_runner_start(words)) is not None]
    answers: dict[re.Pattern[str], bool] = {}

    def found(pattern: re.Pattern[str]) -> bool:
        if pattern not in answers:
            k4_charge(texts[0], 2)
            answers[pattern] = any(pattern.search(text) for text in texts)
        return answers[pattern]

    for started in unique_segments([item[2] for item in starts]):
        spend("reads", 1)
        inner = expand(k4_join(started)) if started else []
        inner = unique_segments(inner + launched_commands(inner))
        if any(dumps_after_source(words) for words in inner):
            return "environment_dump_in_credential_run"
        if any(program_of(words) == "systemctl" and systemctl_reason(words) for words in inner):
            return "service_manager_environment"
        programs = {program_of(words) for words in inner}
        if (any(INTERPRETER.fullmatch(program) for program in programs) or programs & AWKS) and found(KEYRING_ENVIRONMENT_ACCESS):
            return "environment_dump_in_credential_run"
        if (programs & JQS and found(JQ_ENVIRONMENT)) or (programs & SHELLS and found(SHELL_INDIRECTION)):
            return "environment_dump_in_credential_run"
    return None


K4_RUNNER_VALUE_COMMANDS = frozenset({"get", "print", "list", "token"})


def k4_runner_usage_reason(text: str, segments: list[list[str]]) -> str | None:
    """RUN-USAGE and RUN-MENTION (contract-v2 section 4, tier c). The runner as the command itself or as a Python interpreter's script
    operand is an invocation: its first argument -h/--help passes; no argument, a value-returning subcommand (get, print, list, token, which
    the runner does not have) or none of `--`, --check, -h, --help refuses as credential_run_usage (the runner parser at
    tools/credentials/credential_run.py:1039-1070 accepts ID, repeated --only NAME, --check, help and `-- COMMAND`). For an invocation or a
    start, any whole secret-name mention in the text refuses as secret_variable_reference, except the value of that invocation's own
    `--only NAME` before its first `--` (k4_runner_mentions)."""
    invocations = [words[at:] for words in segments if (at := k4_script_position(words, "credential_run.py")) is not None]
    for invocation in invocations:
        arguments = command_arguments(invocation)
        if arguments[:1] in (["-h"], ["--help"]):
            continue
        if not arguments or arguments[0] in K4_RUNNER_VALUE_COMMANDS or not {"--", "--check", "-h", "--help"} & set(arguments):
            return "credential_run_usage"
    if (invocations or any(k4_runner_start(words) is not None for words in segments)) and k4_runner_mentions(text):
        return "secret_variable_reference"
    return None


K4_VARIABLE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?")
K4_ECHO_FLAGS = re.compile(r"\A-[neE]+\Z")


def k4_visible_words(raw: list[str]) -> list[str]:
    """The command a raw segment of k4_shell_words() runs, walked as command_segments() walks it (assignments, output redirections and
    launchers stripped, rtk, runner and keyring starts followed, the earlier start first), keeping the original K4Word objects so that their
    quote provenance and offsets survive the walk."""
    k4_word_charge(raw)
    words = strip_prefix(raw)
    while words:
        _entries, start, moved = launcher_chain(words)
        if start:
            words = words[start:] + moved
            continue
        if program_of(words) == 'rtk':
            words = strip_prefix(rtk_command(words))
            continue
        runner = k4_runner_start(words)
        keyring = keyring_exec(words)
        keyring_at = next((at for at, word in enumerate(words)
            if word.rsplit('/', 1)[-1] == KEYRING_SCRIPT and words[at + 1:at + 2] == ['exec']), len(words))
        if runner is not None and runner[0] < keyring_at:
            spend('reads', 1)
            words = strip_prefix(runner[2])
        elif keyring is not None:
            spend('reads', 1)
            words = strip_prefix(keyring[1])
        else:
            break
        k4_word_charge(words)
    return words


def k4_manager_reason(words_list: list[list[str]]) -> str | None:
    """MANAGER (contract-v2 section 6.1, tier e): a write to a service manager's or D-Bus activation environment, which every later unit or
    activated service inherits and `systemctl --user show-environment` prints. `systemctl [options] import-environment` with no names (the
    whole caller environment) or with a secret name, `set-environment` setting a secret name, and `dbus-update-activation-environment` with
    --all or a secret name or NAME=value operand refuse as manager_environment_write. Names are exact (the part before the first `=`), so a
    value that mentions a name (`set-environment LABEL=TAVILY_API_KEY`) and unset-environment do not. Sources: systemd v255
    src/systemctl/systemctl-set-environment.c and systemctl(1); D-Bus 1.14.10 dbus-update-activation-environment(1)."""
    for words in words_list:
        k4_word_charge(words)
        program = program_of(words)
        if program == 'systemctl':
            positional, _properties = systemctl_call(words)
            if not positional:
                continue
            verb, names = positional[0], positional[1:]
            if verb == 'import-environment' and not names:
                return 'manager_environment_write'
            if verb in {'import-environment', 'set-environment'} and any(name.partition('=')[0] in SECRET_NAMES for name in names):
                return 'manager_environment_write'
        elif program == 'dbus-update-activation-environment':
            args = command_arguments(words)
            if '--all' in args or any(name.partition('=')[0] in SECRET_NAMES for name in args if not name.startswith('-')):
                return 'manager_environment_write'
    return None


def k4_literal(word: str, assigned: set[str]) -> bool:
    """Whether a word's value is statically literal (STORE-LITERAL, contract-v2 section 6.2): no active expansion by its quote and escape
    provenance (a single-quoted or escaped `$` is literal, a double-quoted or bare `$V` is not), or only expansions of variables that the
    same command assigns a nonempty literal value (rule 5)."""
    k4_charge(word)
    if getattr(word, "literal", False):
        return True
    if "`" in word:
        return False
    found = list(K4_VARIABLE.finditer(word))
    if not found or any(match[1] not in assigned for match in found):
        return False
    return "$" not in K4_VARIABLE.sub("", word)


def k4_store_reason(command: str) -> str | None:
    """STORE-LITERAL (tier f) over the command, the bodies of its double-quoted substitutions and the strings a shell -c or eval runs (to
    MAX_SUBSTITUTION_NESTING levels): these texts keep the quotes that expand() has removed, which the literal provenance needs."""
    pending, seen, cursor = [(command, 0)], set(), 0
    while cursor < len(pending):
        text, depth = pending[cursor]
        cursor += 1
        if text in seen:
            continue
        seen.add(text)
        reason = k4_store_text(text)
        if reason:
            return reason
        if depth >= MAX_SUBSTITUTION_NESTING:
            continue
        k4_charge(text)
        pending.extend((body, depth + 1) for body in scan_shell(text)[0])
        for raw in segments(k4_shell_words(text)):
            words = k4_visible_words(raw)
            if program_of(words) in SHELLS:
                inline = shell_parts(words)[1]
                if inline is not None:
                    pending.append((str(inline), depth + 1))
            elif program_of(words) == "eval":
                pending.append((" ".join(words[1:]), depth + 1))
    return None


def k4_store_text(command: str) -> str | None:
    """The five STORE-LITERAL triggers in one text. A segment whose walked command is `kernel_keyring.py store` refuses as
    keyring_store_literal when it has (1) more than one argument after `store` (--replace and redirections aside: a name and a value), (2)
    a here-string with a literal target or any here-document, or when the stage piped into it (a newline after `|` continues the pipeline,
    a `;` does not) is (3) echo with a literal operand or printf with a literal format holding no `%` or a literal argument, or has (4) its
    own here-document or literal here-string; (5) a `$V` counts as literal when the command assigns V a nonempty literal value (V=...,
    export/declare/local/readonly/typeset). Dynamic feeds (`echo "$K"`, `<<< "$K"`, `cat "$KEYFILE"`, the hidden prompt) pass."""
    k4_charge(command)
    tokens = k4_shell_words(command)
    assigned = set()
    for raw in segments(tokens):
        assignment_mode = True
        declaration = bool(raw and raw[0] in {'export', 'declare', 'local', 'readonly', 'typeset'})
        for index, word in enumerate(raw):
            if declaration and (index == 0 or word.startswith('-')):
                continue
            name, equal, value = word.partition('=')
            if equal and K4_IDENTIFIER.fullmatch(name) and (assignment_mode or declaration):
                if value and word.literal:
                    assigned.add(name)
            elif not declaration:
                assignment_mode = False
    stages, raw, previous, separator = [], [], None, None
    for token in tokens:
        if token in SEPARATORS or set(token) <= set(';&|()'):
            if raw:
                stages.append((raw, previous if separator in {'|', '|&'} else None))
                previous, raw = raw, []
            # LF immediately after a pipe continues that pipeline.
            if not (token == ';' and command[token.start:token.end] == '\n' and separator in {'|', '|&'}):
                separator = str(token)
        else:
            raw.append(token)
    if raw:
        stages.append((raw, previous if separator in {'|', '|&'} else None))
    for stage, producer in stages:
        words = k4_visible_words(stage)
        store = next((at for at, word in enumerate(words)
            if word.rsplit('/', 1)[-1] == KEYRING_SCRIPT and words[at + 1:at + 2] == ['store']), None)
        if store is None:
            continue
        arguments = [word for word in command_arguments([words[store], *words[store + 2:]], touching_only=True) if word != '--replace']
        if len(arguments) > 1:
            return 'keyring_store_literal'
        if k4_literal_input(words, assigned):
            return 'keyring_store_literal'
        if producer is None:
            continue
        source = k4_visible_words(producer)
        if k4_literal_input(source, assigned):
            return 'keyring_store_literal'
        program, args = program_of(source), command_arguments(source, touching_only=True)
        at = 0
        if program == 'echo':
            while at < len(args) and K4_ECHO_FLAGS.fullmatch(args[at]):
                at += 1
            if any(k4_literal(word, assigned) for word in args[at:]):
                return 'keyring_store_literal'
        elif program == 'printf':
            if args[:1] == ['-v']:
                at = 2
            if args[at:at + 1] == ['--']:
                at += 1
            if at < len(args) and ((k4_literal(args[at], assigned) and '%' not in args[at])
                    or any(k4_literal(word, assigned) for word in args[at + 1:])):
                return 'keyring_store_literal'
    return None


def k4_literal_input(words: list[str], assigned: set[str]) -> bool:
    k4_word_charge(words)
    for at, word in enumerate(words):
        if word in {'<<', '<<-'}:
            return True
        if word == '<<<' and at + 1 < len(words) and k4_literal(words[at + 1], assigned):
            return True
    return False


def k4_ps_reason(command: str) -> str | None:
    """PS-SELECTOR (contract-v2 section 6.3, tier g): a ps personality selector (PS_PERSONALITY, CMD_ENV, I_WANT_A_BROKEN_PS) that the same
    command sets or passes before an actual ps runs: an assignment prefix (read before prefix_end strips it), `env NAME=VALUE` (an empty
    value too), or export/declare/typeset of the name earlier in the command. A procps personality can make ps show every environment, so
    ps_personality_selector refuses it. Order matters (ps before the export passes), a selector is never taken back, and the marker follows
    the command into nested shells (a copy), eval (the same shell) and substitutions. A selector inherited from outside the command is a
    residual."""
    k4_charge(command, 3)
    # An eval updates its caller's shell; shell -c and substitutions inherit a
    # copy. Explicit iterator frames keep both execution order and linear work.
    pending = [(iter(segments(k4_shell_words(command))), set(), 0, command)]
    while pending:
        iterator, active, depth, text = pending[-1]
        raw = next(iterator, None)
        if raw is None:
            pending.pop()
            continue
        if raw:
            words = k4_visible_words(raw)
            program = program_of(words)
            if program in {'export', 'declare', 'typeset'}:
                active.update(word.partition('=')[0] for word in command_arguments(words)
                    if not word.startswith('-') and word.partition('=')[0] in K4_SELECTORS)
            program_at = next((i for i, word in enumerate(raw) if words and word is words[0]), len(raw))
            prefix = {word.partition('=')[0] for word in raw[:program_at]
                      if '=' in word and word.partition('=')[0] in K4_SELECTORS}
            if not words:
                active.update(prefix)
            selected = active | prefix
            if program == 'ps' and selected:
                return 'ps_personality_selector'
            if depth < MAX_SUBSTITUTION_NESTING:
                if program in SHELLS:
                    inline = shell_parts(words)[1]
                    if inline is not None:
                        nested = str(inline)
                        pending.append((iter(segments(k4_shell_words(nested))), set(selected), depth + 1, nested))
                elif program == 'eval':
                    nested = ' '.join(words[1:])
                    pending.append((iter(segments(k4_shell_words(nested))), active, depth + 1, nested))
                for word in raw:
                    if isinstance(word, K4Word) and not word.literal:
                        source = text[word.start:word.end]
                        k4_charge(source)
                        pending.extend((iter(segments(k4_shell_words(body))), set(selected), depth + 1, body)
                                       for body in scan_shell(source)[0])
    return None


def k4_canary_reason(words_list: list[list[str]]) -> str | None:
    """CANARY (contract-v2 section 6.4, tier h): an actual invocation of canary_proof.py (the command itself, a Python interpreter's script
    operand, `uv run [python ...] SCRIPT`, any launcher, shell string, substitution, keyring or runner start, and a `script -c` string)
    with `--user-run` (also `--user-run=VALUE`), `--phase comparison` or `--phase=comparison` among its arguments, at any position, even
    after an apparent `--`, refuses as canary_user_terminal_required: the comparison and the user run belong in the user's own terminal
    (canary-final.md section 4, lines 242-262; Q5 of the canary adjudications). A program that only names the file (echo, printf, git,
    sed, cat, rg, grep, python -m py_compile) is a mention; any other program that holds the script's basename is read conservatively as
    an invocation. The canary parser itself is not read (it was not present at dc33b48a)."""
    pending = [(words, 0) for words in words_list]
    cursor = 0
    while cursor < len(pending):
        words, depth = pending[cursor]; cursor += 1
        k4_word_charge(words)
        at = k4_script_position(words, 'canary_proof.py', uv=True)
        program = program_of(words)
        if at is None and program not in {'echo', 'printf', 'git', 'sed', 'cat', 'rg', 'grep'} \
                and not K4_PYTHON.fullmatch(program):
            at = next((i for i, word in enumerate(words) if word.rsplit('/', 1)[-1] == 'canary_proof.py'), None)
        if at is not None:
            args = command_arguments(words[at:])
            for i, word in enumerate(args):
                if word == '--user-run' or word.startswith('--user-run=') or word == '--phase=comparison' \
                        or (word == '--phase' and args[i + 1:i + 2] == ['comparison']):
                    return 'canary_user_terminal_required'
        if program == 'script' and depth < MAX_DEPTH:
            args = command_arguments(words)
            for i, word in enumerate(args):
                if word in {'-c', '--command'} and i + 1 < len(args):
                    pending.extend((inner, depth + 1) for inner in expand(args[i + 1]))
                elif word.startswith('--command='):
                    pending.extend((inner, depth + 1) for inner in expand(word.partition('=')[2]))
                elif word.startswith('-') and not word.startswith('--') and 'c' in word[1:]:
                    position = word.index('c', 1)
                    value = word[position + 1:] or (args[i + 1] if i + 1 < len(args) else '')
                    pending.extend((inner, depth + 1) for inner in expand(value))
    return None


K4_HD = re.compile(r"<<(-?)[ \t]*(?:([\"'])([A-Za-z_][A-Za-z0-9_]*)\2|([A-Za-z_][A-Za-z0-9_]*))(?=$|[ \t])")
K4_F_EXEC = re.compile(r"\A(?:[A-Za-z0-9_.~/-]*/)?(python(?:3|[0-9]+\.[0-9]+)?|pypy|nodejs|node)\Z")
K4_F_FLAG = re.compile(r"\A-[BbdEIOPqsSuv]+\Z")
K4_F_PLAIN = re.compile(r"[A-Za-z0-9_./:=,+@%~-]+")
K4_F_VARIABLE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
K4_F_DIGITS = re.compile(r"\A[0-9]+\Z")
K4_F_GREP = re.compile(r"\A-[inEFvwxco]+\Z")
# An interpreter word of a here-document's operator line (section 7.2: a PY/JS basename, any path; both languages apply when both occur).
K4_REGION_WORD = re.compile(r"(?<![A-Za-z0-9_.-])(?:python[0-9.]*|pypy[0-9.]*|nodejs|node)(?![A-Za-z0-9_.-])")
# A here-document operator (not part of a here-string's `<<<`) and the blanks after it; its word follows (k4_delimiter_word).
K4_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)[ \t]*")
K4_EXACT_DELIMITER = re.compile(r"'[A-Za-z_][A-Za-z0-9_]*'|\"[A-Za-z_][A-Za-z0-9_]*\"")
K4_WORD_END = frozenset(" \t\n;&|()<>")


class K4Region:
    """One here-document of a command, found lexically on every line (a body is also searched, so an operator that bash would take for
    body text still opens a region: that errs toward reading more). `languages` holds "py" and/or "js" when its logical operator line
    (backslash-newlines followed) has an interpreter word; `operator` is the offset of its `<<`; the body runs from the line after the
    logical line to the first later line equal to the delimiter (after leading tabs for `<<-`), bodies on one line in turn, or to the end;
    `cut` is where the text after that terminator line starts (None without a terminator line and a newline after it); `exact` is True when
    the delimiter word is exactly one quoted identifier, ended by a blank, a line end or a shell metacharacter."""
    __slots__ = ("languages", "operator", "line_end", "body_start", "body_end", "cut", "exact")

    def __init__(self, languages, operator, line_end, body_start, body_end, cut, exact):
        self.languages, self.operator, self.line_end = languages, operator, line_end
        self.body_start, self.body_end, self.cut, self.exact = body_start, body_end, cut, exact


def k4_delimiter_word(text: str, at: int) -> tuple[str, bool] | None:
    """(delimiter, exact) of the here-document word that starts at text[at]: the shell word up to a blank, a line end or a metacharacter
    outside quotes, its quotes removed (bash: "the result of quote removal on word"); exact when the word is one quoted identifier. None
    when no word follows or a quote is left open."""
    start, size, parts = at, len(text), []
    while at < size and text[at] not in K4_WORD_END:
        char = text[at]
        if char == "'":
            end = text.find("'", at + 1)
            if end < 0:
                return None
            parts.append(text[at + 1:end])
            at = end + 1
        elif char == '"':
            end = at + 1
            while end < size and text[end] != '"':
                end += 2 if text[end] == "\\" else 1
            if end >= size:
                return None
            parts.append(text[at + 1:end])
            at = end + 1
        elif char == "\\":
            parts.append(text[at + 1:at + 2])
            at += 2
        elif text.startswith("$'", at):
            end = ansi_c_end(text, at + 2)
            if end < 0:
                return None
            parts.append(text[at + 2:end - 1])
            at = end
        else:
            parts.append(char)
            at += 1
    if at == start:
        return None
    return "".join(parts), bool(K4_EXACT_DELIMITER.fullmatch(text, start, at))


def k4_regions(command: str) -> list[K4Region]:
    """The here-documents of command (K4Region), for the CODE rules (section 7.2, amendment A7: each interpreter here-document is one
    region, to its first exact terminator line or to the end) and for TAIL-READ (section 7.5). Found on the original text, before
    backslash-newline joining; lexical, so it tightens only and never qualifies form F (k4_form_f reads F on its own)."""
    key = ("regions", command)
    if _k4_cache is not None and key in _k4_cache:
        return _k4_cache[key]
    k4_charge(command, 4)  # the line split and index, the operator search, the unquoted() and language scan of operator lines
    lines = command.split("\n")
    offsets, offset = [], 0
    by_text: dict[str, list[int]] = {}
    for number, line in enumerate(lines):
        offsets.append(offset)
        by_text.setdefault(line, []).append(number)
        offset += len(line) + 1
    by_stripped: dict[str, list[int]] | None = None
    regions: list[K4Region] = []
    number = 0
    while number < len(lines):
        first = number
        while lines[number].endswith("\\") and number + 1 < len(lines):
            number += 1
        last = number
        number += 1
        start, end = offsets[first], offsets[last] + len(lines[last])
        if "<<" not in command[start:end]:
            continue
        logical = command[start:end]
        languages = frozenset("js" if word.startswith("node") else "py" for word in K4_REGION_WORD.findall(unquoted(logical)))
        body_line = last + 1
        for match in K4_HEREDOC.finditer(logical):
            word = k4_delimiter_word(logical, match.end())
            if word is None:
                continue
            delimiter, exact = word
            if match.group(1):
                if by_stripped is None:
                    by_stripped = {}
                    for index, line in enumerate(lines):
                        by_stripped.setdefault(line.lstrip("\t"), []).append(index)
                candidates = by_stripped.get(delimiter, [])
            else:
                candidates = by_text.get(delimiter, [])
            found = bisect.bisect_left(candidates, body_line)
            body_start = offsets[body_line] if body_line < len(lines) else len(command)
            if found == len(candidates):
                regions.append(K4Region(languages, start + match.start(), end, body_start, len(command), None, exact))
                body_line = len(lines)
                continue
            term = candidates[found]
            cut = offsets[term] + len(lines[term]) + 1
            regions.append(K4Region(languages, start + match.start(), end, body_start, offsets[term],
                                    cut if cut <= len(command) else None, exact))
            body_line = term + 1
    spend("words", len(regions) + 1)
    if _k4_cache is not None:
        _k4_cache[key] = regions
    return regions


# The text that reopens each shell construct scan_shell() tracks (k4_resume_contexts).
K4_OPENERS = {"dq": '"', "sub": "$(", "bt": "`", "param": "${", "arith": "$(("}


def k4_resume_contexts(command: str, regions: list[K4Region]) -> dict[int, str]:
    """For each here-document whose operator bash reads as one (outside quotes, comments and parameter expansions, as scan_shell() reads a
    text): the openers of the constructs still open at the end of its operator line, which is where bash resumes after the terminator
    (`git commit -m "$(cat <<'EOF'` resumes inside `"$(`). The scan jumps over the body of every such here-document, so no quote in a body
    changes a later context. Keyed by the region's `operator`; one charged pass."""
    k4_charge(command)
    operators = {region.operator for region in regions}
    by_line_end: dict[int, list[K4Region]] = {}
    for region in regions:
        by_line_end.setdefault(region.line_end, []).append(region)
    real: set[int] = set()
    contexts: dict[int, str] = {}
    stack: list[list] = []  # [kind, parentheses] as in scan_shell
    at, size, construct_end = 0, len(command), -1
    while at < size:
        kind = stack[-1][0] if stack else "cmd"
        char = command[at]
        if char == "\n" and at in by_line_end and kind in {"cmd", "sub", "bt"}:
            resumed = [region for region in by_line_end[at] if region.operator in real]
            if resumed:
                prefix = "".join(K4_OPENERS[frame[0]] for frame in stack)
                for region in resumed:
                    contexts[region.operator] = prefix
                last = max(resumed, key=lambda region: region.body_end)
                if last.cut is None:
                    break
                at = last.cut
                continue
        if char == "<" and at in operators and kind in {"cmd", "sub", "bt"}:
            real.add(at)
            at += 2
            continue
        if char == "\\":
            at += 2
            construct_end = at
        elif char == "'" and kind != "dq":
            closing = command.find("'", at + 1)
            at = size if closing < 0 else closing + 1
            construct_end = at
        elif char == '"':
            if kind == "dq":
                stack.pop()
            else:
                stack.append(["dq", 0])
            at += 1
            construct_end = at
        elif char == "`":
            if kind == "bt":
                stack.pop()
            else:
                stack.append(["bt", 0])
            at += 1
            construct_end = at
        elif char == "$":
            if command.startswith("$((", at):
                stack.append(["arith", 0])
                at += 3
            elif command.startswith("$(", at):
                stack.append(["sub", 1])
                at += 2
            elif command.startswith("${", at):
                stack.append(["param", 0])
                at += 2
            elif command.startswith("$'", at) and kind != "dq":
                closing = ansi_c_end(command, at + 2)
                at = size if closing < 0 else closing
                construct_end = at
            else:
                at += 1
        elif char == "}" and kind == "param":
            stack.pop()
            at += 1
            construct_end = at
        elif char == "#" and kind in {"cmd", "sub", "bt"} and (at == 0 or (at != construct_end and command[at - 1] in COMMENT_BREAK)):
            closing = command.find("\n", at)
            at = size if closing < 0 else closing
        elif char == "(" and kind in {"sub", "arith"}:
            stack[-1][1] += 1
            at += 1
        elif char == ")" and kind in {"sub", "arith"}:
            if stack[-1][1] > (1 if kind == "sub" else 0):
                stack[-1][1] -= 1
            elif kind == "sub" or command.startswith("))", at):
                stack.pop()
                at += 1 if kind == "sub" else 2
                construct_end = at
                continue
            at += 1
        else:
            at += 1
    return contexts


def k4_f_arg(text: str, at: int) -> int | None:
    """One finite ARG from the contract. Consumes each piece by index."""
    # Caller charges the complete header/tail before this bounded subscan.
    start, size = at, len(text)
    while at < size:
        char = text[at]
        if char == "'":
            end = text.find("'", at + 1)
            if end < 0 or '\r' in text[at:end] or '\n' in text[at:end]:
                return None
            at = end + 1
        elif char == '"':
            at += 1
            while at < size and text[at] != '"':
                if text[at] in '`\\!\r\n':
                    return None
                if text[at] == '$':
                    found = K4_F_VARIABLE.match(text, at)
                    if found is None:
                        return None
                    at = found.end()
                else:
                    at += 1
            if at == size:
                return None
            at += 1
        elif char == '$':
            found = K4_F_VARIABLE.match(text, at)
            if found is None:
                return None
            at = found.end()
        elif found := K4_F_PLAIN.match(text, at):
            at = found.end()
        else:
            break
    return at if at > start else None


def k4_f_tail(tail: str) -> bool:
    k4_charge(tail, 2)
    at, size = 0, len(tail)
    while at < size and tail[at] in ' \t':
        at += 1
    while at < size and tail[at] != '|':
        special = next((token for token in ('2>&1', '1>&2', '>&2') if tail.startswith(token, at)), None)
        if special:
            at += len(special)
        else:
            if tail[at] in '12&':
                at += 1
            if not tail.startswith('>', at):
                return False
            at += 2 if tail.startswith('>>', at) else 1
            while at < size and tail[at] in ' \t':
                at += 1
            after = k4_f_arg(tail, at)
            if after is None:
                return False
            at = after
        while at < size and tail[at] in ' \t':
            at += 1
    if at == size:
        return True
    tokens = k4_shell_words(tail[at:])
    if tokens and tail[at + tokens[-1].end:].strip(' \t'):
        return False
    cursor = 0
    options = {'wc': {'-l', '-c', '-w', '-m'}, 'sort': {'-n', '-r', '-u', '-h', '-V'},
               'uniq': {'-c', '-d', '-u'}, 'head': {'-q'}, 'tail': {'-q'}}
    while cursor < len(tokens):
        if tail[at + tokens[cursor].start:at + tokens[cursor].end] != '|' or cursor + 1 == len(tokens):
            return False
        cursor += 1
        program = tokens[cursor]
        if tail[at + program.start:at + program.end] != program:
            return False
        if program not in options and program != 'grep':
            return False
        cursor += 1
        pattern = False
        while cursor < len(tokens) and tokens[cursor] != '|':
            token = tokens[cursor]
            if token.start <= tokens[cursor - 1].end:
                return False
            raw = tail[at + token.start:at + token.end]
            if program == 'grep':
                if pattern:
                    return False
                if not K4_F_GREP.fullmatch(raw):
                    if k4_f_arg(raw, 0) != len(raw):
                        return False
                    pattern = True
            elif raw in options[program]:
                pass
            elif program in {'head', 'tail'} and raw.startswith('-') and K4_F_DIGITS.fullmatch(raw[1:]):
                pass
            elif program in {'head', 'tail'} and raw in {'-n', '-c'}:
                cursor += 1
                if cursor >= len(tokens) or tokens[cursor].start <= token.end \
                        or not K4_F_DIGITS.fullmatch(tail[at + tokens[cursor].start:at + tokens[cursor].end]):
                    return False
            else:
                return False
            cursor += 1
        if program == 'grep' and not pattern:
            return False
    return True


def k4_f_header(line: str) -> tuple[str, str] | None:
    """(language, delimiter) when line is an operator line OL of form F (contract-v2 section 7.1), else None:

        OL := BL* [ "cd" BL+ ARG BL* "&&" BL* ] INTERP BL* "<<" BL* QIDENT [ BL+ TAIL ] BL*

    with INTERP a Python (PY: flags from [BbdEIOPqsSuv], then optionally `-` and arguments) or Node program (JS: optionally
    --input-type=module|commonjs, then optionally `-` and arguments) reading its program on stdin, QIDENT one quoted identifier as the
    whole delimiter word (at least one blank before any nonempty tail: `<<'PY'2>/dev/null` delimits at PY2 and is no F), and TAIL only
    output redirections and the head/tail/wc/sort/uniq/grep filters. Read by index with a small scanner; no backtracking pattern."""
    k4_charge(line, 3)
    if '\r' in line:
        return None
    operator = line.find('<<')
    match = K4_HD.match(line, operator) if operator >= 0 else None
    if not match or not match[2] or match[1]:
        return None
    # K4_HD requires a complete delimiter word and BL+ before any tail.
    if not k4_f_tail(line[match.end():]):
        return None
    source = line[:operator]
    words = k4_shell_words(source)
    if not words:
        return None
    if source[words[-1].end:].strip(' \t'):
        return None
    at = 0
    if words[0] == 'cd':
        if len(words) < 4 or source[words[0].start:words[0].end] != 'cd' \
                or words[1].start <= words[0].end or source[words[2].start:words[2].end] != '&&':
            return None
        arg = source[words[1].start:words[1].end]
        if k4_f_arg(arg, 0) != len(arg):
            return None
        at = 3
    executable = source[words[at].start:words[at].end]
    found = K4_F_EXEC.fullmatch(executable)
    if found is None:
        return None
    language = 'js' if found[1] in {'node', 'nodejs'} else 'py'
    at += 1
    stdin, js_option = False, False
    while at < len(words):
        word = words[at]
        if word.start <= words[at - 1].end:
            return None
        raw = source[word.start:word.end]
        if stdin:
            if k4_f_arg(raw, 0) != len(raw):
                return None
        elif raw == '-':
            stdin = True
        elif language == 'py' and K4_F_FLAG.fullmatch(raw):
            pass
        elif language == 'js' and not js_option and raw in {'--input-type=module', '--input-type=commonjs'}:
            js_option = True
        else:
            return None
        at += 1
    return language, match[3]


class K4Form:
    """Form F of a command: its language ("py" or "js"), delimiter, and the body span (body_start: after the operator line's newline;
    body_end: the start of the terminator line)."""
    __slots__ = ("language", "delimiter", "body_start", "body_end")

    def __init__(self, language, delimiter, body_start, body_end):
        self.language, self.delimiter, self.body_start, self.body_end = language, delimiter, body_start, body_end


def k4_form_f(command: str) -> K4Form | None:
    """Form F, the single loosening (L1, contract-v2 section 7.1), on the original top-level text before backslash-newline joining, or None.
    All of: (1) exactly one `<<` in the whole text, overlapping occurrences counted (`<<<` holds two, a shift in the body counts); (2) line 0
    (split at LF only) is a complete operator line without CR (k4_f_header); (3) the first later line exactly equal to the delimiter,
    untrimmed and whatever the language's quote state, is the terminator; (4) the text ends with that line or its one final LF. Anything
    else (a launcher, assignment, shell consumer, -c/-m or a script, an input redirection, another pipe program, a separator after the
    operator, `<<-`, an unquoted, backslash or ANSI-C delimiter, a second `<<`, no terminator, trailing text, a leading line) is no F."""
    k4_charge(command)
    first = command.find("<<")
    if first < 0 or command.find("<<", first + 1) >= 0:
        return None
    newline = command.find("\n")
    if newline < first:
        return None
    header = k4_f_header(command[:newline])
    if header is None:
        return None
    language, delimiter = header
    k4_charge(command)
    at = newline + 1
    while True:
        end = command.find("\n", at)
        if (command[at:end] if end >= 0 else command[at:]) == delimiter:
            break
        if end < 0:
            return None
        at = end + 1
    finish = at + len(delimiter)
    if finish != len(command) and not (finish + 1 == len(command) and command[finish] == "\n"):
        return None
    return K4Form(language, delimiter, newline + 1, at)


def k4_tail_reason(command: str) -> str | None:
    """TAIL-READ (contract-v2 section 7.5, tier j). After the first terminator line of each here-document whose delimiter word is exactly one
    quoted identifier, the following text is read again as a command of its own, in addition to B and through the same budget: a quote in a
    body cannot then hide a later command from the shell reading (a Python body line that opens a triple-quoted string, then the terminator
    PY, then printenv, then the string's closing line). Each read starts where bash resumes, in the constructs still open on the operator line (k4_resume_contexts: `)"` after a
    `"$(cat <<'EOF'` body is read as `"$()"`), and runs to the next such cut, where the next read starts; together the reads cover the text
    after the first cut once, and equal reads are read once (k4_derived), so four thousand `"$(cat <<'EOF' ... EOF)"` messages cost two reads.
    Bodies are never masked from B, and no body is exempt: this only refuses."""
    regions = [region for region in k4_regions(command) if region.exact and region.cut is not None and region.cut < len(command)]
    if not regions:
        return None
    contexts = k4_resume_contexts(command, k4_regions(command))
    starts: dict[int, set[str]] = {}
    for region in regions:
        starts.setdefault(region.cut, set()).add(contexts.get(region.operator, ""))
    cuts = sorted(starts)
    k4_charge(command[cuts[0]:])  # the pieces cut and compared below
    for index, cut in enumerate(cuts):
        piece = command[cut:cuts[index + 1] if index + 1 < len(cuts) else len(command)]
        for prefix in sorted(starts[cut]):
            reason = k4_derived(prefix + piece)
            if reason:
                return reason
    return None


K4_CODE_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
K4_CODE_ESCAPE = re.compile(r"\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|[0-7]{1,3}|.)", re.S)
# Output and serialization calls (WHOLE-ENV, section 7.3), by their terminal name, qualified or not: Python print/pprint/pp/pformat,
# repr/str/ascii/format, json/yaml/toml dumps, file and stream writes, csv rows, logging methods, click echo/secho, socket and HTTP sends;
# JavaScript console methods, JSON.stringify, String, util.inspect/format, stream and fs writes, send/end/fetch. Object.keys/values/entries
# and getOwnPropertyNames enumerate, which counts the same.
K4_OUTPUT = frozenset({
    "print", "pprint", "pp", "pformat", "repr", "str", "ascii", "format", "dumps", "dump", "safe_dump", "dump_all", "safe_dump_all",
    "write", "writelines", "writerow", "writerows", "writeSync", "info", "warning", "warn", "error", "critical", "exception", "debug",
    "log", "echo", "secho", "send", "sendall", "sendto", "post", "put", "patch", "request", "urlopen", "stringify", "String",
    "inspect", "writeFile", "writeFileSync", "appendFile", "appendFileSync", "end", "fetch", "dir", "table", "trace", "dirxml",
    "group", "groupCollapsed", "assert", "timeLog", "keys", "values", "entries", "getOwnPropertyNames"})
# Where a slash starts a JavaScript regular-expression literal rather than a division: after one of these tokens, or at the start.
K4_JS_REGEX_AFTER = frozenset({"(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^",
                               "==", "!=", "<=", ">=", "=>", "...", "return", "typeof", "case", "do", "else", "in", "of", "new",
                               "delete", "void", "throw", "yield", "await"})


class K4CodeToken:
    __slots__ = ('kind', 'value', 'start', 'end', 'quote', 'prefix', 'newline')

    def __init__(self, kind, value, start, end, quote='', prefix='', newline=False):
        self.kind, self.value, self.start, self.end = kind, value, start, end
        self.quote, self.prefix, self.newline = quote, prefix, newline


def k4_unescape(content: str, raw: bool = False) -> str:
    k4_charge(content)
    if raw:
        return content
    def replace(found):
        value = found[0][1:]
        if value.startswith(('x', 'u')) and len(value) > 1:
            return chr(int(value[1:], 16))
        if value and value[0] in '01234567':
            return chr(int(value, 8))
        return {'n': '\n', 'r': '\r', 't': '\t', '\n': '', '\\': '\\', "'": "'", '"': '"', '`': '`'}.get(value, found[0])
    return K4_CODE_ESCAPE.sub(replace, content)


def k4_code_tokens(code: str, language: str):
    """(tokens, literals, uncertain, escaped) of Python ("py") or JavaScript ("js") code (CODE, contract-v2 section 7.2): one linear pass,
    never executed, imported or parsed as a program. States: Python `#` comments, JavaScript `//` and `/* */` comments (a quote in a comment
    delimits nothing), Python single, double and triple-quoted strings with r/b/u/f prefixes, JavaScript single, double and template strings,
    JavaScript regular-expression literals (after an operator, keyword or opening bracket), escapes, and interpolation: a Python f-string
    replacement field (nested format fields too) and a JavaScript `${...}` field are code, pushed on an explicit frame stack and emitted
    between `interp` bracket tokens, while `{{`/`}}` and literal chunks stay string data. `uncertain` when the text ends inside a string,
    comment or field; `escaped` when JavaScript has a backslash outside strings (an identifier escape such as `\\u0065nv`)."""
    key = ('code-tokens', language, code)
    if _k4_cache is not None and key in _k4_cache:
        return _k4_cache[key]
    k4_charge(code)
    spend('texts', 1)
    tokens, literals, frames = [], [], [('code', False, 0)]
    at, size, uncertain, newline, escaped = 0, len(code), False, False, False

    def emit(kind, value, first, last, quote='', prefix=''):
        nonlocal newline
        token = K4CodeToken(kind, value, first, last, quote, prefix, newline)
        newline = False
        tokens.append(token)
        if kind == 'string':
            literals.append(token)

    while at < size:
        frame = frames[-1]
        if frame[0] == 'string':
            _kind, quote, prefix, first, chunk, interpolated = frame
            if code.startswith(quote, at):
                content = k4_unescape(code[chunk:at], 'r' in prefix)
                emit('string', content, first if not interpolated else chunk, at + len(quote), quote,
                     prefix + ('-part' if interpolated else ''))
                at += len(quote)
                frames.pop()
                continue
            if code[at] == '\\':
                at = min(size, at + 2)
                continue
            fstring = language == 'py' and 'f' in prefix
            template = language == 'js' and quote == '`'
            if fstring and code[at:at + 2] in {'{{', '}}'}:
                at += 2
                continue
            width = 1 if fstring and code[at] == '{' else 2 if template and code.startswith('${', at) else 0
            if width:
                if at > chunk:
                    emit('string', k4_unescape(code[chunk:at], 'r' in prefix), chunk, at, quote, prefix + '-part')
                frames[-1] = ('string', quote, prefix, first, at + width, True)
                emit('interp', '(', at, at + width)
                frames.append(('code', True, 0))
                at += width
                continue
            at += 1
            continue
        _kind, interpolation, braces = frame
        char = code[at]
        if interpolation and char == '}' and braces == 0:
            emit('interp', ')', at, at + 1)
            frames.pop()
            parent = frames[-1]
            frames[-1] = (*parent[:4], at + 1, True)
            at += 1
            continue
        if char in ' \t\r\n':
            newline |= char == '\n'
            at += 1
            continue
        if (language == 'py' and char == '#') or (language == 'js' and code.startswith('//', at)):
            end = code.find('\n', at)
            at = size if end < 0 else end
            continue
        if language == 'js' and code.startswith('/*', at):
            end = code.find('*/', at + 2)
            if end < 0:
                uncertain = True
                at = size
            else:
                newline |= '\n' in code[at:end]
                at = end + 2
            continue
        if language == 'js' and char == '/' and (not tokens or (tokens[-1].kind != 'string' and tokens[-1].value in K4_JS_REGEX_AFTER)):
            end, klass = at + 1, False
            while end < size and code[end] != '\n':
                if code[end] == '\\':
                    end += 2
                    continue
                if code[end] == '/' and not klass:
                    break
                klass = (klass or code[end] == '[') and code[end] != ']'
                end += 1
            if end < size and code[end] == '/':
                end += 1
                while end < size and code[end].isalpha():
                    end += 1
                emit('regex', code[at:end], at, end)
                at = end
                continue
        if language == 'js' and char == '\\':
            escaped = True
        first, prefix = at, ''
        found = K4_CODE_IDENT.match(code, at)
        if found:
            value, end = found[0], found.end()
            if language == 'py' and 1 <= len(value) <= 3 and set(value.lower()) <= set('rbuf') \
                    and end < size and code[end] in "'\"":
                prefix, at, char = value.lower(), end, code[end]
            else:
                emit('id', value, at, end)
                at = end
                continue
        if char in "'\"" or (language == 'js' and char == '`'):
            quote = char * 3 if language == 'py' and code.startswith(char * 3, at) else char
            at += len(quote)
            frames.append(('string', quote, prefix, first, at, False))
            continue
        if interpolation:
            if char == '{':
                frames[-1] = ('code', True, braces + 1)
            elif char == '}':
                frames[-1] = ('code', True, braces - 1)
        operator = next((op for op in ('...', '**', '=>', '==', '!=', '<=', '>=', ':=') if code.startswith(op, at)), char)
        emit('punct', operator, at, at + len(operator))
        at += len(operator)
    uncertain |= len(frames) > 1
    if frames[-1][0] == 'string':
        frame = frames[-1]
        emit('string', code[frame[4]:], frame[3], size, frame[1], frame[2] + '-unfinished')
    spend('words', len(tokens) + 1)
    result = (tokens, literals, uncertain, escaped)
    if _k4_cache is not None:
        _k4_cache[key] = result
    return result


def k4_code_structure(tokens: list[K4CodeToken]):
    """O(1) output membership at every token; frames restore an integer, never
    search ancestors. Bracket pairs also support finite call argument parsing.
    """
    spend('words', len(tokens) + 1)
    pairs, calls, output, iteration = {}, [], [], []
    stack, current, out, iterating = [], None, 0, False
    for at, token in enumerate(tokens):
        value = token.value
        if (token.newline and not stack) or value == ';':
            iterating = False
        if value == 'for':
            iterating = True
        calls.append(current); output.append(bool(out)); iteration.append(iterating)
        if value in {'(', '[', '{'} and token.kind != 'string':
            name = tokens[at - 1].value if at and tokens[at - 1].kind == 'id' and value == '(' else None
            stack.append((at, value, current, out, iterating))
            if name:
                current = at
                out += name in K4_OUTPUT
        elif value in {')', ']', '}'} and token.kind != 'string' and stack:
            opening, _char, current, out, previous_iter = stack.pop()
            pairs[opening] = at; pairs[at] = opening
            iterating = previous_iter
        elif value == ':':
            iterating = False
    return pairs, calls, output, iteration


def k4_leading_literals(tokens, opening, pairs):
    """Finite literal strings/lists before the first other argument."""
    spend('words', 1)
    close = pairs.get(opening, opening)
    at, values, argv = opening + 1, [], False
    while at < close:
        token = tokens[at]
        if token.kind == 'string' and '-part' not in token.prefix and '-unfinished' not in token.prefix:
            values.append(token.value); at += 1
            while at < close and tokens[at].kind == 'string' and '-part' not in tokens[at].prefix:
                values[-1] += tokens[at].value; at += 1
        elif token.value in {'[', '('} and token.kind != 'string':
            end = pairs.get(at)
            if end is None:
                break
            item = at + 1
            items = []
            while item < end:
                if tokens[item].kind != 'string' or '-part' in tokens[item].prefix:
                    break
                items.append(tokens[item].value); item += 1
                while item < end and tokens[item].kind == 'string' and '-part' not in tokens[item].prefix:
                    items[-1] += tokens[item].value; item += 1
                if item < end and tokens[item].value == ',':
                    item += 1
                elif item != end:
                    break
            if item != end:
                break
            values.extend(items); argv = True; at = end + 1
        else:
            break
        if at < close and tokens[at].value == ',':
            at += 1
        else:
            break
    spend('words', len(values) + 1)
    return values, argv or len(values) > 1


# Derived readings (a tail, a literal or a shell-out read as a command) nest through read_command(); deeper than this they are refused as
# an exhausted texts budget (command_too_complex) rather than read without end.
K4_DERIVED_DEPTH = 8


def k4_derived(text: str, code: bool = False) -> str | None:
    """The verdict of read_command(text, top=False) inside the current budget: B(T) of the derived text, then its own K4 tightenings, never a
    fresh check() and never form F. Equal texts are read once per check() (the cache key holds the mode). `code` marks a command derived
    from interpreter code, where `keyctl list` is left to the keyring-code rule (section 7.2)."""
    global _code_derived
    key = ("derived", code, text)
    if _k4_cache is not None and key in _k4_cache:
        return _k4_cache[key]
    k4_charge(text)
    spend("texts", 1)
    if _k4_state is not None:
        if _k4_state["depth"] >= K4_DERIVED_DEPTH:
            raise WorkBudgetExceeded("texts")
        _k4_state["depth"] += 1
    old = _code_derived
    _code_derived = code
    try:
        reason = read_command(text, top=False)
    finally:
        _code_derived = old
        if _k4_state is not None:
            _k4_state["depth"] -= 1
    if _k4_cache is not None:
        _k4_cache[key] = reason
    return reason


def k4_shell_literals(unit: "K4CodeUnit") -> str | None:
    """SHELL-LITERAL (contract-v2 section 7.2, here-document regions only): a string literal read as shell text, the reason of that reading
    kept. Three branches: a literal standing alone between line or separator boundaries (after a line start, `(`, `;`, `&` or `|`, before
    a line end, `)`, `;`, `&` or `|`, blanks aside) is read as a command; the `$(...)` and backquote bodies of a double-quoted literal are
    read as the base reads them in double quotes; a multiline literal and a JavaScript template chunk are read as shell text. Comments are
    no literals (the lexer skips them), and an interpolation is code, read by the other CODE rules, never merged into a literal."""
    code = unit.code
    tokens, literals, _uncertain, _escaped = k4_code_tokens(code, unit.language)
    k4_charge(code)
    for token in literals:
        content = token.value
        before, after = token.start - 1, token.end
        while before >= 0 and code[before] in " \t":
            before -= 1
        while after < len(code) and code[after] in " \t":
            after += 1
        standalone = (before < 0 or code[before] in "\n(;&|") and (after == len(code) or code[after] in "\n);&|")
        if standalone or "\n" in content or token.quote == "`":
            reason = k4_derived(content, code=True)
            if reason:
                return reason
        if token.quote.startswith('"') and ("$" in content or "`" in content):
            k4_charge(content)
            for body in scan_shell('"' + content + '"')[0]:
                reason = k4_derived(body, code=True)
                if reason:
                    return reason
    return None


# Shell-out functions whose leading string or argv list is a command line (section 7.2, SHELL-OUT): Python os/subprocess/asyncio/pty and
# the exec/spawn families (Python's built-in exec is excluded), JavaScript child_process. Qualified names count (os.system, cp.execSync).
K4_PY_SHELLOUT = frozenset({"system", "popen", "Popen", "run", "call", "check_call", "check_output", "getoutput", "getstatusoutput",
                            "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "execl", "execle",
                            "execlp", "execlpe", "execv", "execve", "execvp", "execvpe", "posix_spawn", "posix_spawnp",
                            "create_subprocess_shell", "create_subprocess_exec", "startfile"})
K4_JS_SHELLOUT = frozenset({"exec", "execSync", "execFile", "execFileSync", "spawn", "spawnSync"})
# The exec*/spawn* forms whose first argument is the program path and whose next ones (or list) are the argv, argv[0] included.
K4_PATH_FIRST = re.compile(r"(?:exec|spawn)[lv]p?e?|posix_spawnp?")


def k4_shellouts(unit: "K4CodeUnit") -> str | None:
    """SHELL-OUT (contract-v2 section 7.2, here-document regions only): the finite leading sequence of literal strings and literal
    string-list items of a shell-out call (comments and line breaks between tokens skipped) is read as a command: one string as shell text,
    several or a list through shlex.join (for the exec/spawn families also without the program path). Every rule applies to that command,
    and literal env/printenv/set handed to a subprocess are environment_dump. `keyctl list` in a derived command stays with the keyring-code
    rule. A call whose command was read and allowed is recorded in unit.permitted, where WHOLE-ENV admits an environment copy passed as its
    env= option. Indirect or computed shell-outs (`f = os.system; f("print" "env")`, `run('print' + 'env')`) are residuals."""
    tokens, _literals, _uncertain, _escaped = k4_code_tokens(unit.code, unit.language)
    pairs = k4_code_structure(tokens)[0]
    spend("words", len(tokens) + 1)
    names = K4_PY_SHELLOUT if unit.language == "py" else K4_JS_SHELLOUT
    for at, token in enumerate(tokens[:-1]):
        if token.kind != "id" or token.value not in names or tokens[at + 1].value != "(":
            continue
        values, argv = k4_leading_literals(tokens, at + 1, pairs)
        if not values:
            continue
        texts = [shlex.join(values) if argv else values[0]]
        if argv and len(values) > 1 and K4_PATH_FIRST.fullmatch(token.value):
            texts.append(shlex.join(values[1:]))
        for text in texts:
            reason = k4_derived(text, code=True)
            if reason:
                return reason
        unit.permitted.add(at + 1)
    return None


# Python's environment sources and the names reflective access uses; a string naming one of these is a source in getattr() or a subscript.
K4_PY_SOURCES = frozenset({"environ", "environb"})
K4_JS_PROCESS_MODULES = frozenset({"process", "node:process"})


def k4_whole_environment(unit: "K4CodeUnit", tokens: list, structure) -> str | None:
    """WHOLE-ENV (contract-v2 section 7.3 with amendment A6), a lexical classification of every recognizable environment source in the
    unit's code: Python os.environ, os.environb and names imported from os (also `as` aliases), JavaScript process.env, process['env'] and
    process["env"]. Each occurrence is: an exact single-key lookup, index, get/pop/setdefault with a literal key, or a fixed JS property
    (process.env.HOME, not a method call): safe, unless the key is a secret name (secret_variable_reference); inside an output or
    serialization call at any depth or across lines (print, repr, str, format, json/yaml dumps, write*, logging, echo, network calls, console
    methods, JSON.stringify, String, inspect ...), or iterated (for headers, comprehensions, .items/.keys/.values, Object.keys/values/entries):
    environment_dump; the binding of a copy (NAME = os.environ.copy(), NAME = dict(os.environ), NAME = {...process.env}) whose every later use
    is a literal non-secret lookup or update or the env= option of a permitted literal subprocess call: safe (its output or iteration is
    environment_dump); anything else, including dynamic keys, reflective access that names a source (getattr(x, 'environ'), `x['environ']`,
    `__import__('os').environ`, `o.environ`, a bare `process`, require('process')): interpreter_environment_unclassified. Output context is an
    integer carried on the bracket stack (k4_code_structure), read in O(1) per token."""
    pairs, calls, output, iteration = structure
    values = [token.value for token in tokens]
    kinds = [token.kind for token in tokens]
    size = len(tokens)
    spend("words", size + 1)
    language = unit.language
    imported: set[str] = set()
    definitions: set[int] = set()
    aliases: dict[str, int] = {}
    visited = 0
    at = 0
    while at < size:
        value, kind = values[at], kinds[at]
        if kind == "string":
            if language == "py" and value in K4_PY_SOURCES and (calls[at] is not None and at and values[calls[at] - 1] == "getattr"
                                                              or at and values[at - 1] == "[" and values[at + 1:at + 2] == ["]"]):
                return "interpreter_environment_unclassified"
            if language == "js" and value in K4_JS_PROCESS_MODULES:
                return "interpreter_environment_unclassified"
            at += 1
            continue
        if kind != "id":
            at += 1
            continue
        start = end = None
        if language == "py":
            if value == "from" and values[at + 1:at + 3] == ["os", "import"]:
                cursor = at + 3
                while cursor < size and not (tokens[cursor].newline and cursor > at + 3) and values[cursor] != ";":
                    if values[cursor] in K4_PY_SOURCES:
                        definitions.add(cursor)
                        if values[cursor + 1:cursor + 2] == ["as"] and cursor + 2 < size:
                            imported.add(values[cursor + 2])
                            definitions.add(cursor + 2)
                        else:
                            imported.add(values[cursor])
                    cursor += 1
                at = cursor
                continue
            if at in definitions:
                at += 1
                continue
            if value in K4_PY_SOURCES:
                if at >= 2 and values[at - 1] == "." and values[at - 2] == "os" and kinds[at - 2] == "id" \
                        and not (at >= 3 and values[at - 3] == "."):
                    start, end = at - 2, at + 1
                elif value in imported and not (at and values[at - 1] == "."):
                    start, end = at, at + 1
                else:
                    return "interpreter_environment_unclassified"
            elif value in imported and not (at and values[at - 1] == "."):
                start, end = at, at + 1
        elif value == "process":
            dotted = at and values[at - 1] == "."
            if values[at + 1:at + 3] == [".", "env"]:
                start, end = at, at + 3
            elif at + 3 < size and values[at + 1] == "[" and kinds[at + 2] == "string" and values[at + 2] == "env" \
                    and values[at + 3] == "]":
                start, end = at, at + 4
            elif dotted or (values[at + 1:at + 2] == ["."] and at + 2 < size and kinds[at + 2] == "id"):
                at += 1
                continue  # another property of process (process.argv), or some object's own `process` member
            else:
                return "interpreter_environment_unclassified"
        if start is None:
            at += 1
            continue
        visited += 1
        reason = k4_environment_use(tokens, values, start, end, pairs, calls, output, iteration, language, aliases, definitions,
                                    unit.permitted)
        if reason:
            return reason
        at = end
    for at, token in enumerate(tokens):
        if kinds[at] != "id" or token.value not in aliases or at in definitions or at < aliases[token.value]:
            continue
        if at and values[at - 1] == ".":
            continue  # a member of some object, not the binding
        if k4_single_key(tokens, at + 1, pairs, language) is not None:
            continue
        if output[at] or iteration[at]:
            return "environment_dump"
        if calls[at] in unit.permitted and (values[max(0, at - 2):at] in (["env", "="], ["env", ":"])
                                            or (values[at + 1:at + 2] in (["="], [":"]) and token.value == "env")):
            continue  # the env= / env: option of a permitted literal subprocess call (the option name itself is no use either)
        return "interpreter_environment_unclassified"
    if _k4_cache is not None:
        _k4_cache[("environment-visits", language, unit.code)] = visited
    return None


def k4_environment_use(tokens, values, start, end, pairs, calls, output, iteration, language, aliases, definitions, permitted):
    """The classification of one environment source occurrence tokens[start:end] (k4_whole_environment)."""
    single = k4_single_key(tokens, end, pairs, language)
    if single is not None:
        return "secret_variable_reference" if single in SECRET_NAMES else None
    following = values[end:end + 2]
    if following[:1] == ["["] or following in (["." , "get"], [".", "pop"], [".", "setdefault"]):
        return "interpreter_environment_unclassified"
    if output[start] or iteration[start] or following in ([".", "items"], [".", "keys"], [".", "values"]):
        return "environment_dump"
    first, last, copy = start, end, False
    if language == "py" and values[end:end + 4] == [".", "copy", "(", ")"]:
        last, copy = end + 4, True
    elif language == "py" and start >= 2 and values[start - 2:start] == ["dict", "("] and values[end:end + 1] == [")"]:
        first, last, copy = start - 2, end + 1, True
    elif language == "js" and start >= 2 and values[start - 2:start] == ["{", "..."] and values[end:end + 1] == ["}"]:
        first, last, copy = start - 2, end + 1, True
    size = len(tokens)
    if copy and first >= 2 and values[first - 1] == "=" and tokens[first - 2].kind == "id" and calls[first - 2] is None \
            and (first < 3 or values[first - 3] != ".") and (last == size or tokens[last].newline or values[last] == ";"):
        aliases.setdefault(values[first - 2], first - 2)
        definitions.add(first - 2)
        return None
    return "interpreter_environment_unclassified"


def k4_single_key(tokens, end, pairs, language):
    """The literal key of an exact single-key access right after an environment source or copy (tokens[end:]): `[ 'KEY' ]`, Python
    .get/.pop/.setdefault('KEY'[, ...]), or a fixed JavaScript property `.KEY` that is not called; None otherwise."""
    spend("words", 1)
    size = len(tokens)
    if end + 2 < size and tokens[end].value == "[" and tokens[end + 1].kind == "string" and "-" not in tokens[end + 1].prefix \
            and tokens[end + 2].value == "]":
        return tokens[end + 1].value
    if end + 1 < size and tokens[end].value == ".":
        method = tokens[end + 1].value
        if language == "js" and tokens[end + 1].kind == "id" and not (end + 2 < size and tokens[end + 2].value == "("):
            return method
        if language == "py" and method in {"get", "pop", "setdefault"} and end + 4 < size \
                and tokens[end + 2].value == "(" and tokens[end + 3].kind == "string" and "-" not in tokens[end + 3].prefix \
                and end + 2 in pairs and tokens[end + 4].value in {",", ")"}:
            return tokens[end + 3].value
    return None


class K4CodeUnit:
    """One piece of interpreter code the CODE rules read: a here-document region's body (kind "region", also with its backslash-newlines
    joined), inline -c/-e code (kind "inline"; a here-string fed to an interpreter's stdin is inline code too), Node's -p/--print code (kind
    "print": its value is printed, so it is read inside console.log(...)), or the words of an interpreter command line whose options could
    not all be read (kind "uncertain": only a visible environment source or gateway URL in them matters). `permitted` holds the calls whose
    shell-out command was read and allowed (k4_shellouts)."""
    __slots__ = ("language", "code", "kind", "permitted")

    def __init__(self, language: str, code: str, kind: str):
        self.language, self.code, self.kind, self.permitted = language, code, kind, set()


def k4_code_units(r: K4Reading, segments: list[list[str]]) -> list[K4CodeUnit]:
    """The interpreter code of the command (K4CodeUnit), read once per K4 reading: every here-document region with a PY/JS operator line
    (section 7.2, amendment A7; the F body is one), and every Python or Node command among the segments of both readings (launchers, runner
    and keyring starts walked) with inline code (section 7.4)."""
    if r.units is not None:
        return r.units
    units: list[K4CodeUnit] = []
    seen: set[tuple[str, str, str]] = set()

    def add(language: str, code: str, kind: str) -> None:
        if (language, code, kind) not in seen:
            seen.add((language, code, kind))
            units.append(K4CodeUnit(language, code, kind))

    if "<<" in r.anchors:
        for region in k4_regions(r.command):
            if region.languages and region.body_end > region.body_start:
                body = r.command[region.body_start:region.body_end]
                k4_charge(body)
                for language in sorted(region.languages):
                    add(language, body, "region")
                    add(language, body.replace("\\\n", ""), "region")
    for words in segments:
        program = program_of(words)
        if program == "uv" and words[1:2] == ["run"]:
            at = next((at for at, word in enumerate(words) if at > 1 and (K4_PYTHON.fullmatch(program_of([word]))
                                                                        or program_of([word]) in {"node", "nodejs"})), None)
            if at is None:
                continue
            words, program = words[at:], program_of(words[at:])
        if not (K4_PYTHON.fullmatch(program) or program in {"node", "nodejs"}):
            continue
        language = "py" if K4_PYTHON.fullmatch(program) else "js"
        kind, at, code, certain = k4_program_operand(words)
        if kind in {"inline", "print"} and code is not None:
            add(language, str(code), kind)
        elif kind == "stdin":
            for index, word in enumerate(words[:-1]):
                if word == "<<<":
                    add(language, str(words[index + 1]), "inline")
        if not certain:
            add(language, " ".join(words[1:]), "uncertain")
    r.units = units
    return units


# What makes a code unit worth an environment reading: a visible source name, or (JavaScript) an identifier escape that could spell one.
K4_ENV_HINT = re.compile(r"environ|process|\\u")
K4_ENV_VISIBLE = re.compile(r"\benvironb?\b|\bprocess\b")


def k4_unit_environment_reason(unit: K4CodeUnit) -> str | None:
    """WHOLE-ENV for one code unit (section 7.3; INLINE-ENV, section 7.4, reads -c/-e code the same way). Python code is read after NFKC
    normalization, as Python reads identifiers (a fullwidth `ｏｓ.ｅｎｖｉｒｏｎ` is os.environ). A unit whose lexing ended inside a string,
    comment or interpolation, or JavaScript with an identifier escape, fails closed when it shows a source (interpreter_environment_unclassified);
    an uncertain command line fails closed when its words do."""
    code = unit.code
    if unit.kind == "print":
        code = "console.log(" + code + "\n)"
    if unit.language == "py" and not code.isascii():
        k4_charge(code)
        normalized = unicodedata.normalize("NFKC", code)
        if normalized != code:
            code, unit = normalized, K4CodeUnit("py", normalized, unit.kind)  # the permitted calls of the original tokens do not carry over
    k4_charge(code)
    if not K4_ENV_HINT.search(code):
        return None
    if unit.kind == "uncertain":
        return "interpreter_environment_unclassified" if K4_ENV_VISIBLE.search(code) else None
    tokens, _literals, uncertain, escaped = k4_code_tokens(code, unit.language)
    if escaped or (uncertain and K4_ENV_VISIBLE.search(code)):
        return "interpreter_environment_unclassified"
    return k4_whole_environment(unit, tokens, k4_code_structure(tokens))


def k4_interpreter_reason(r: K4Reading, segments: list[list[str]]) -> str | None:
    """Tier (i): the CODE rules on every code unit, in the order SHELL-LITERAL, SHELL-OUT (both on here-document regions only; inline code
    keeps the deferred shell-out reading of section 7.4), then WHOLE-ENV on regions and inline code."""
    units = k4_code_units(r, segments)
    if not units:
        return None
    regions = [unit for unit in units if unit.kind == "region"]
    for unit in regions:
        reason = k4_shell_literals(unit)
        if reason:
            return reason
    for unit in regions:
        reason = k4_shellouts(unit)
        if reason:
            return reason
    for unit in units:
        reason = k4_unit_environment_reason(unit)
        if reason:
            return reason
    return None


def k4_gateway_reason(r: K4Reading, segments: list[list[str]]) -> str | None:
    """Tier (d): gateway requests (GW, contract-v2 section 5) in shell commands of both readings (k4_gateway_shell), and, when a gateway
    port shows, in interpreter code (k4_gateway_code): region bodies, inline code, and the words of a command line whose options could not
    all be read."""
    reason = k4_gateway_shell(segments)
    if reason or "2012" not in r.anchors:
        return reason
    for unit in k4_code_units(r, segments):
        k4_charge(unit.code)
        if "2012" not in unit.code:
            continue
        if unit.kind == "uncertain":
            if any(k4_gateway_url(word, unresolved=True) for word in unit.code.split()):
                return "gateway_credential_route"
            continue
        code = "console.log(" + unit.code + "\n)" if unit.kind == "print" else unit.code
        tokens, _literals, _uncertain, _escaped = k4_code_tokens(code, unit.language)
        reason = k4_gateway_code(code, tokens, k4_code_structure(tokens), unit.language)
        if reason:
            return reason
    return None


K4_GW_HEAD = re.compile(r"^(?:http://)?(?:(?P<user>[^/\s@?#]+)@)?(?P<host>127\.0\.0\.1|localhost|\[::1\]|10\.0\.2\.2|host\.docker\.internal):(?P<port>20128|20129)(?P<rest>(?:[/\\?#].*)?)$", re.I | re.S)
K4_GW_ID = re.compile(r"\A[A-Za-z0-9-]{1,64}\Z")
K4_GW_NUMBER = re.compile(r"\A[0-9]{1,5}\Z")
K4_GW_METHOD = re.compile(r"\A[A-Z]+\Z")
K4_GW_ENCODE_DATA = re.compile(r"\A[A-Za-z0-9_-]+=[A-Za-z0-9_.~-]*\Z")
K4_GW_ROWS = {
    ('GET', '/api/health'): ((20128, 20129), 'none', False),
    ('GET', '/api/settings/compression'): ((20128, 20129), 'none', False),
    ('GET', '/api/context/combos'): ((20128, 20129), 'none', False),
    ('GET', '/api/model-capability-overrides'): ((20128, 20129), 'none', False),
    ('GET', '/api/resilience'): ((20128, 20129), 'none', False),
    ('GET', '/api/settings/feature-flags'): ((20128, 20129), 'none', False),
    ('GET', '/api/cache'): ((20128, 20129), 'none', False),
    ('GET', '/api/analytics/compression'): ((20128, 20129), 'analytics', False),
    ('GET', '/api/usage/call-logs'): ((20128, 20129), 'logs', False),
    ('GET', '/api/usage/provider-limits'): ((20128,), 'none', True),
    ('POST', '/api/usage/provider-limits'): ((20128,), 'none', True),
    ('POST', '/api/compression/preview'): ((20129,), 'none', False),
}
# curl 8.5.0 (`curl --help all` and curl(1), read 2026-09-30): the transport and output options the documented replay uses and a few more
# that change no URL, method or body; every other option is unknown, and an unknown option in an operation with a covered management URL
# refuses (it could be a request-target override, a config file, a proxy, --netrc ...).
K4_CURL_VALUE = frozenset({'--max-time', '--connect-timeout', '--output', '--dump-header', '--header', '--user-agent',
    '--retry', '--retry-delay', '--retry-max-time', '--write-out', '--referer', '--range', '--limit-rate', '--speed-limit',
    '--speed-time', '--cacert', '--capath', '--continue-at', '--trace-ascii', '--stderr'})
K4_CURL_FLAGS = frozenset({'--silent', '--show-error', '--fail', '--fail-with-body', '--insecure', '--compressed',
    '--no-progress-meter', '--verbose', '--no-buffer', '--include', '--progress-bar', '--http1.1', '--http1.0', '--http2',
    '--ipv4', '--ipv6', '--globoff', '--no-keepalive', '--raw', '--remote-name', '--remote-header-name', '--create-dirs'})
K4_CURL_DATA = frozenset({'--data', '--data-ascii', '--data-binary', '--data-raw', '--data-urlencode', '--json'})
K4_CURL_FORM = frozenset({'--form', '--form-string'})
K4_CURL_SHORT_VALUE = {'X': '--request', 'd': '--data', 'F': '--form', 'T': '--upload-file',
                       'o': '--output', 'm': '--max-time', 'H': '--header', 'A': '--user-agent', 'D': '--dump-header',
                       'w': '--write-out', 'e': '--referer', 'r': '--range', 'Y': '--speed-limit', 'y': '--speed-time',
                       'C': '--continue-at'}
K4_CURL_SHORT_FLAGS = frozenset("sSfkvNi#46gOJ")
# curl's URL globbing (curl(1) "URL"): {a,b} sets and [1-9], [a-z] ranges with an optional :step, expanded (to K4_CURL_GLOBS URLs) before
# the matrix reads them, so `http://127.0.0.1:2012[8-9]/api/settings` is the two requests it makes; -g/--globoff turns globbing off.
K4_CURL_GLOB = re.compile(r"\{([^{}]*)\}|\[([^\[\]]*)\]")
K4_CURL_RANGE = re.compile(r"\A(?:([0-9]+)-([0-9]+)|([A-Za-z])-([A-Za-z]))(?::([0-9]+))?\Z")
K4_CURL_GLOBS = 256
K4_GW_HOST_NAMES = ("127.0.0.1", "localhost", "::1", "10.0.2.2", "host.docker.internal")


def k4_curl_expansions(url: str) -> list[str] | None:
    """The URLs curl's globbing makes of url (K4_CURL_GLOB), or None when there are more than K4_CURL_GLOBS or a range is unreadable.
    The IPv6 host literal [::1] is no range."""
    k4_charge(url)
    pieces, last = [""], 0
    for match in K4_CURL_GLOB.finditer(url):
        if match.group(2) is not None and ":" in match.group(2) and not K4_CURL_RANGE.fullmatch(match.group(2)):
            continue  # an IPv6 literal such as [::1]
        if match.group(1) is not None:
            options = match.group(1).split(",")
        else:
            found = K4_CURL_RANGE.fullmatch(match.group(2))
            if found is None:
                return None
            step = int(found.group(5) or 1)
            if found.group(1) is not None:
                low, high = int(found.group(1)), int(found.group(2))
                width = len(found.group(1)) if found.group(1).startswith("0") else 0
                if step < 1 or high < low or (high - low) // step >= K4_CURL_GLOBS:
                    return None
                options = [str(number).zfill(width) for number in range(low, high + 1, step)]
            else:
                low, high = ord(found.group(3)), ord(found.group(4))
                if step < 1 or high < low:
                    return None
                options = [chr(code) for code in range(low, high + 1, step)]
        literal = url[last:match.start()]
        pieces = [piece + literal + option for piece in pieces for option in options]
        if len(pieces) > K4_CURL_GLOBS:
            return None
        last = match.end()
    return [piece + url[last:] for piece in pieces]


def k4_gateway_url(url: str, method='GET', body=False, additions=(), unresolved=False) -> bool:
    """Whether one request is a covered management request the frozen matrix (contract-v2 section 5.1, K4_GW_ROWS) does not permit.
    Covered: scheme http (a scheme-less client operand is http, amendment A11), host 127.0.0.1, localhost, [::1], 10.0.2.2 or
    host.docker.internal (ASCII case folded), port 20128 or 20129. Under /api/ every request refuses unless its effective method, complete
    path (exact segments; <id> a single [A-Za-z0-9-]{1,64} segment of the call-logs route), query (none; exactly since=all on analytics;
    limit=D and/or offset=D, D of 1 to 5 ASCII digits, once each, joined by one `&`, on call-logs) and body condition (none on provider-limits)
    match a row. Management targeting is evident when the path, dot and slash segments resolved and percent escapes decoded, reaches /api;
    such a target with userinfo, a fragment, a percent escape, a backslash, a dot segment, a repeated slash, whitespace, `$` or a backquote,
    a bare `?`, or an unresolved request (`unresolved`) never matches a row. Nothing here opens a file or sends a request."""
    k4_charge(url, 4)
    found = K4_GW_HEAD.fullmatch(url)
    if found is None:
        return False
    rest = found['rest']
    path = rest.split('?', 1)[0].split('#', 1)[0]
    normalized = []
    decoded = re.sub(r"%([0-9A-Fa-f]{2})", lambda escape: chr(int(escape.group(1), 16)), path) if "%" in path else path
    for part in decoded.replace('\\', '/').split('/'):
        if part == '..':
            if normalized:
                normalized.pop()
        elif part and part != '.':
            normalized.append(part)
    evident = path.startswith('/api/') or path == '/api' or '/api/' in path \
        or bool(normalized and normalized[0] == 'api')
    if not evident:
        return False
    if unresolved or found['user'] or '#' in rest or '%' in rest or '\\' in rest \
            or '$' in rest or '`' in rest or any(char.isspace() for char in rest) \
            or '//' in path or any(part in {'.', '..'} for part in path.split('/')):
        return True
    query = rest.partition('?')[2] if '?' in rest else None
    if query == '':
        return True
    if additions:
        if any(not isinstance(item, str) or any(char in item for char in '$`@%\r\n') for item in additions):
            return True
        query = '&'.join(([query] if query is not None else []) + list(additions))
    row = K4_GW_ROWS.get((method, path))
    if row is None and method == 'GET' and path.startswith('/api/usage/call-logs/') \
            and K4_GW_ID.fullmatch(path[len('/api/usage/call-logs/'):]):
        row = ((20128, 20129), 'none', False)
    if row is None or int(found['port']) not in row[0] or (row[2] and body):
        return True
    if query is None:
        return False
    if row[1] == 'analytics':
        return query != 'since=all'
    if row[1] != 'logs':
        return True
    used = set()
    for item in query.split('&'):
        name, equals, value = item.partition('=')
        if not equals or name not in {'limit', 'offset'} or name in used or not K4_GW_NUMBER.fullmatch(value):
            return True
        used.add(name)
    return not used


def k4_curl_requests(words: list[str]) -> bool:
    """Whether a curl command line makes a refused covered request (contract-v2 section 5.3). Each operation (--next or -: starts the next
    one) starts at GET: -X/--request set the wire method (the last wins), -d/--data* and --json and -F/--form* imply POST, -T/--upload-file
    PUT, -I/--head HEAD; -G/--get moves literal data into the query (GET, or HEAD with -I) and --no-get/--no-head clear them; short clusters
    take an option's value from the rest of the word or the next word (-sXPOST, -sIdx). Every URL of the operation (positional or --url,
    each glob expansion) is its own request under all of the operation's options; unknown options, conflicting modes, dynamic or file-read
    query data and an unreadable glob leave the operation unresolved, and an unresolved covered management request refuses."""
    k4_word_charge(words)
    args = command_arguments(words, touching_only=True)
    at = 0
    while at < len(args):
        urls, data, method = [], [], None
        head = get = form = upload = unknown = options_done = globoff = False
        while at < len(args):
            word = args[at]; at += 1
            if not options_done and word in {'--next', '-:'}:
                break
            if word == '--' and not options_done:
                options_done = True
                continue
            if options_done or not word.startswith('-') or word == '-':
                urls.append(word)
                continue
            opts = []
            if word.startswith('--'):
                option, equals, value = word.partition('=')
                takes = option in K4_CURL_VALUE | K4_CURL_DATA | K4_CURL_FORM | {'--request', '--upload-file', '--url'}
                if takes and not equals:
                    if at == len(args):
                        unknown = True
                        continue
                    value = args[at]; at += 1
                if equals and not takes:
                    unknown = True
                opts.append((option, value))
            else:
                offset = 1
                while offset < len(word):
                    letter = word[offset]; offset += 1
                    if letter in K4_CURL_SHORT_VALUE:
                        option = K4_CURL_SHORT_VALUE[letter]
                        value = word[offset:]
                        if not value:
                            if at == len(args):
                                unknown = True
                            else:
                                value = args[at]; at += 1
                        opts.append((option, value))
                        break
                    opts.append(({'I': '--head', 'G': '--get'}.get(letter, '-' + letter), ''))
            for option, value in opts:
                if option == '--request':
                    method = value
                    unknown |= not bool(K4_GW_METHOD.fullmatch(value))
                elif option == '--url':
                    urls.append(value)
                elif option in K4_CURL_DATA:
                    data.append((option, value))
                elif option in K4_CURL_FORM:
                    form = True
                elif option == '--upload-file':
                    upload = True
                elif option in {'--head', '--no-head'}:
                    head = option == '--head'
                elif option in {'--get', '--no-get'}:
                    get = option == '--get'
                elif option in {'--globoff', '-g'}:
                    globoff = True
                elif option not in K4_CURL_VALUE | K4_CURL_FLAGS \
                        and not (len(option) == 2 and option[0] == '-' and option[1] in K4_CURL_SHORT_FLAGS):
                    unknown = True
        unknown |= bool((upload and (data or form or head or get)) or (form and (data or head or get)) or (head and data and not get))
        additions = []
        if get:
            for option, value in data:
                if option == '--json' or (option == '--data-urlencode' and not K4_GW_ENCODE_DATA.fullmatch(value)) \
                        or any(char in value for char in '@$`%'):
                    unknown = True
                additions.append(value)
        body = bool(form or upload or (data and not get))
        effective = method if method is not None else 'HEAD' if head else 'PUT' if upload else 'POST' if body else 'GET'
        for url in urls:
            targets = [url]
            if not globoff and ('{' in url or '[' in url):
                targets = k4_curl_expansions(url)
                if targets is None:
                    lowered = url.lower()
                    if '/' in url and ('2012' in url or any(name in lowered for name in K4_GW_HOST_NAMES)):
                        return True  # an unreadable glob over what could be a covered management URL
                    continue
            for target in targets:
                if k4_gateway_url(target, effective, body, additions, unknown):
                    return True
    return False


def k4_wget_requests(words: list[str]) -> bool:
    """wget (section 5.3): GET by default; --method METHOD (last wins), --post-data/--post-file imply POST, --body-data/--body-file mark a
    body and need an explicit method; conflicting sources, a post option with a method other than POST, and unknown options leave the
    request unresolved. The options apply to every URL; -qO- is output syntax."""
    k4_word_charge(words)
    args, at, urls = command_arguments(words, touching_only=True), 0, []
    method, post, body, unknown = None, 0, 0, False
    ordinary_values = {'--output-document', '--output-file', '--timeout', '--connect-timeout', '--read-timeout', '--header', '--user-agent'}
    while at < len(args):
        word = args[at]; at += 1
        if word.startswith('--'):
            option, equals, value = word.partition('=')
            takes = option in ordinary_values | {'--method', '--post-data', '--post-file', '--body-data', '--body-file'}
            if takes and not equals:
                if at == len(args):
                    unknown = True
                    continue
                value = args[at]; at += 1
            if option == '--method':
                method = value
                unknown |= not K4_GW_METHOD.fullmatch(value)
            elif option in {'--post-data', '--post-file'}:
                post += 1
            elif option in {'--body-data', '--body-file'}:
                body += 1
            elif option not in ordinary_values | {'--quiet', '--no-verbose'}:
                unknown = True
        elif word.startswith('-') and word != '-':
            offset = 1
            while offset < len(word):
                letter = word[offset]; offset += 1
                if letter in 'OoTU':
                    if offset == len(word):
                        if at < len(args):
                            at += 1
                        else:
                            unknown = True
                    break
                if letter not in 'qnv':
                    unknown = True
        else:
            urls.append(word)
    unknown |= post > 1 or body > 1 or bool(post and body) or bool(body and method is None) \
        or bool(post and method is not None and method != 'POST')
    return any(k4_gateway_url(url, method or ('POST' if post else 'GET'), bool(post or body), unresolved=unknown) for url in urls)


def k4_httpie_requests(words: list[str]) -> bool:
    """httpie `http`/`https` and xh (section 5.3): a leading literal METHOD word sets the method; without one, data fields (name=value,
    name:=json) imply POST and none GET; name==value query fields join the query literally; `:20128/path` is http://localhost:20128/path for
    the `http` and `xh` binaries (the `https` binary's requests are https, never covered). Unknown options and unsupported items leave the
    request unresolved."""
    k4_word_charge(words)
    args = command_arguments(words)
    method, urls, additions = None, [], []
    body = unknown = False
    scheme = 'https' if program_of(words) == 'https' else 'http'
    for word in args:
        if word.startswith('-'):
            if word not in {'--check-status', '--ignore-stdin', '--json', '-j', '-b', '--body', '-h', '--headers', '--pretty=none'}:
                unknown = True
        elif method is None and not urls and K4_GW_METHOD.fullmatch(word):
            method = word
        elif not urls:
            if word.startswith(':'):
                word = scheme + '://localhost' + word
            elif '://' not in word:
                word = scheme + '://' + word
            urls.append(word)
        elif '==' in word:
            name, value = word.split('==', 1)
            additions.append(name + '=' + value)
        elif '=' in word:
            body = True
        elif ':' not in word:
            unknown = True
    return any(k4_gateway_url(url, method or ('POST' if body else 'GET'), body, additions, unknown) for url in urls)


def k4_gateway_cli(words: list[str]) -> bool:
    """GW-CLI (section 5.3): every actual `omniroute api ...` and `omniroute sync ...` refuses, whatever follows (help and no arguments
    too): the policy has no CLI counterpart of the HTTP matrix. Recognized global options are consumed before the subcommand is chosen; after
    an unrecognized option, any api or sync word among the arguments refuses."""
    k4_word_charge(words)
    args = command_arguments(words)
    values = {'--port', '--host', '--config', '--data-dir', '--log-level', '--base-url', '--profile'}
    at = 0
    while at < len(args):
        word = args[at]; at += 1
        if word == '--':
            break
        if not word.startswith('-'):
            return word in {'api', 'sync'}
        name, equals, _value = word.partition('=')
        if name in values and not equals:
            at += 1
        elif name not in values | {'--help', '-h', '--version', '-v', '--debug', '--verbose'}:
            # The frozen policy covers ambiguous genuine CLI invocations too.
            return any(token in {'api', 'sync'} for token in args[at:])
    return at < len(args) and args[at] in {'api', 'sync'}


def k4_gateway_shell(words_list: list[list[str]]) -> str | None:
    """GW over shell segments: curl, wget, http/https/xh and the omniroute CLI, by basename (path-qualified binaries, launchers and
    runner or keyring starts are walked into the segments). A gateway URL as an argument of any other program is a mention (amendment A11)."""
    for words in words_list:
        k4_word_charge(words)
        program = program_of(words)
        refused = ((program == 'curl' and k4_curl_requests(words))
            or (program == 'wget' and k4_wget_requests(words))
            or (program in {'http', 'https', 'xh'} and k4_httpie_requests(words))
            or (program == 'omniroute' and k4_gateway_cli(words)))
        if refused:
            return 'gateway_credential_route'
    return None


K4_IMPORT_HTTP = re.compile(r"\bfrom[ \t]+(requests|httpx|urllib\.request)[ \t]+import[ \t]+([^;\n]+)")
K4_CODE_NUMBER = re.compile(r"\A[0-9]+\Z")
K4_UNKNOWN = object()


def k4_call_parts(tokens, opening, pairs):
    """Argument ranges for one call/container, with nested delimiters skipped
    through a precomputed pair map. No request borrows another call's options.
    """
    close = pairs.get(opening, opening)
    spend('words', max(1, close - opening))
    parts, first, at = [], opening + 1, opening + 1
    while at < close:
        value = tokens[at].value
        if value == ',' and tokens[at].kind != 'string':
            if first < at:
                parts.append((first, at))
            first = at + 1
        elif tokens[at].kind != 'string' and value in {'(', '[', '{'}:
            at = pairs.get(at, at)
        at += 1
    if first < close:
        parts.append((first, close))
    return parts


def k4_code_value(tokens, span, pairs, depth=0):
    first, last = span
    spend('words', max(1, last - first))
    if first >= last or depth > 8:
        return K4_UNKNOWN
    token = tokens[first]
    if first + 1 == last:
        if token.kind == 'string' and '-part' not in token.prefix and '-unfinished' not in token.prefix:
            return token.value
        if token.value in {'None', 'null'}:
            return None
        if token.value in {'True', 'true', 'False', 'false'}:
            return token.value in {'True', 'true'}
    # The lexical scanner leaves numeric punctuation separate; only contiguous
    # ASCII digits form an exact numeric literal here.
    if all(item.kind == 'punct' and item.value.isascii() and item.value.isdigit() for item in tokens[first:last]):
        return int(''.join(item.value for item in tokens[first:last]))
    if token.value in {'[', '('} and pairs.get(first) == last - 1:
        values = [k4_code_value(tokens, part, pairs, depth + 1) for part in k4_call_parts(tokens, first, pairs)]
        return K4_UNKNOWN if any(value is K4_UNKNOWN for value in values) else values
    if token.value == '{' and pairs.get(first) == last - 1:
        result = {}
        for key_at, end in k4_call_parts(tokens, first, pairs):
            if key_at + 2 > end or tokens[key_at].kind not in {'id', 'string'} or tokens[key_at + 1].value != ':':
                return K4_UNKNOWN
            key = tokens[key_at].value
            if key in result:
                return K4_UNKNOWN
            value = k4_code_value(tokens, (key_at + 2, end), pairs, depth + 1)
            if value is K4_UNKNOWN:
                return K4_UNKNOWN
            result[key] = value
        return result
    return K4_UNKNOWN


def k4_call_values(tokens, opening, pairs):
    positional, keywords, unknown = [], {}, False
    for first, last in k4_call_parts(tokens, opening, pairs):
        if first + 1 < last and tokens[first].kind == 'id' and tokens[first + 1].value == '=':
            name = tokens[first].value
            if name in keywords:
                unknown = True
            keywords[name] = k4_code_value(tokens, (first + 2, last), pairs)
            unknown |= keywords[name] is K4_UNKNOWN
        elif tokens[first].value == '**':
            unknown = True
        else:
            value = k4_code_value(tokens, (first, last), pairs)
            positional.append(value)
            unknown |= value is K4_UNKNOWN
    return positional, keywords, unknown


def k4_query_values(value):
    if value is None:
        return [], False
    if isinstance(value, str):
        k4_charge(value)
        return [value], False
    pairs = list(value.items()) if isinstance(value, dict) else value
    if not isinstance(pairs, list):
        return [], True
    spend('words', len(pairs) + 1)
    parts = []
    for item in pairs:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            return [], True
        name, number = item
        if not isinstance(name, str) or not isinstance(number, (str, int)) or isinstance(number, bool):
            return [], True
        parts.append(name + '=' + str(number))
    return parts, False


def k4_gateway_code(code, tokens, structure, language):
    k4_charge(code, 6)
    pairs, calls, _output, _iteration = structure
    targets = [(at, token) for at, token in enumerate(tokens) if token.kind == 'string'
        and ('20128' in token.value or '20129' in token.value) and k4_gateway_url(token.value, unresolved=True)]
    if not targets:
        if 'HTTPConnection' in code and '/api/' in code and ('20128' in code or '20129' in code) \
                and any(host in code for host in ('127.0.0.1', 'localhost', '::1', '10.0.2.2', 'host.docker.internal')):
            return 'gateway_credential_route'
        return None
    imports = {}
    if language == 'py':
        for match in K4_IMPORT_HTTP.finditer(code):
            for name in match[2].split(','):
                name = name.strip()
                if K4_IDENTIFIER.fullmatch(name):
                    imports[name] = match[1]
    assigned, request_bindings = set(), {}
    for at, token in enumerate(tokens[:-2]):
        if token.kind == 'id' and tokens[at + 1].value == '=' and calls[at] is None:
            assigned.add(token.value)
            next_at = at + 2
            # A simple Request binding may be used by a later urlopen in the
            # same code region; any second assignment invalidates its identity.
            if token.value in request_bindings:
                request_bindings[token.value] = None
            else:
                cursor = next_at
                while cursor < len(tokens) and tokens[cursor].value != '(' and not tokens[cursor].newline:
                    cursor += 1
                request_bindings[token.value] = cursor if cursor < len(tokens) and cursor and tokens[cursor - 1].value == 'Request' else None
    for token_at, token in targets:
        opening = calls[token_at]
        if opening is None or '-part' in token.prefix or '-unfinished' in token.prefix:
            return 'gateway_credential_route'
        name = tokens[opening - 1].value if opening else ''
        receiver = tokens[opening - 3].value if opening >= 3 and tokens[opening - 2].value == '.' else None
        positional, keywords, unknown = k4_call_values(tokens, opening, pairs)
        method, body, additions = None, False, []
        url = None
        if language == 'js' and name == 'fetch' and receiver is None and name not in assigned:
            if not positional:
                unknown = True
            else:
                url = positional[0]
            options = positional[1] if len(positional) > 1 else {}
            if len(positional) > 2 or keywords or not isinstance(options, dict):
                unknown = True
            else:
                method = options.get('method', 'GET')
                body = options.get('body') is not None
        elif language == 'py' and name in {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'request'} \
                and ((receiver in {'requests', 'httpx'} and receiver not in assigned
                      and (opening < 4 or tokens[opening - 4].value != '.'))
                     or (receiver is None and imports.get(name) in {'requests', 'httpx'} and name not in assigned)):
            if name == 'request':
                method = keywords.get('method', positional[0] if positional else K4_UNKNOWN)
                url = keywords.get('url', positional[1] if len(positional) > 1 else K4_UNKNOWN)
                unknown |= ('method' in keywords and bool(positional)) or ('url' in keywords and len(positional) > 1)
                unknown |= len(positional) > 2
            else:
                method = name.upper()
                url = keywords.get('url', positional[0] if positional else K4_UNKNOWN)
                unknown |= ('url' in keywords and bool(positional)) or len(positional) > 1
                unknown |= 'method' in keywords and keywords['method'] != method
            body = any(key in keywords and keywords[key] is not None for key in ('data', 'json', 'files', 'content'))
            additions, query_unknown = k4_query_values(keywords.get('params'))
            unknown |= query_unknown
        elif language == 'py' and name in {'Request', 'urlopen'} \
                and (receiver == 'request' or (receiver is None and imports.get(name) == 'urllib.request')):
            url = keywords.get('url', keywords.get('fullurl', positional[0] if positional else K4_UNKNOWN))
            body = keywords.get('data', positional[1] if len(positional) > 1 else None) is not None
            explicit = keywords.get('method') if name == 'Request' else None
            if name == 'Request':
                # Fold the outer urlopen data into the Request's body status,
                # for both an inline constructor and a proven simple binding.
                outer = calls[opening]
                consumers = []
                if outer is not None and tokens[outer - 1].value == 'urlopen':
                    consumers.append(outer)
                bindings = {binding for binding, target in request_bindings.items() if target == opening}
                if bindings:
                    for at, item in enumerate(tokens[:-2]):
                        if item.value == 'urlopen' and tokens[at + 1].value == '(' and tokens[at + 2].value in bindings:
                            consumers.append(at + 1)
                for consumer in consumers:
                    parts = k4_call_parts(tokens, consumer, pairs)
                    for first, last in parts[1:]:
                        if tokens[first].value == 'data' and first + 1 < last and tokens[first + 1].value == '=':
                            first += 2
                        value = k4_code_value(tokens, (first, last), pairs)
                        unknown |= value is K4_UNKNOWN
                        body |= value is not None
            method = explicit if explicit is not None else 'POST' if body else 'GET'
        else:
            unknown = True
        unknown |= not isinstance(method, str) or not isinstance(url, str) or url != token.value
        if k4_gateway_url(token.value, method, body, additions, unknown):
            return 'gateway_credential_route'
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
