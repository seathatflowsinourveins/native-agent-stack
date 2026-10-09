"""Host-local deny-name checks through Betterleaks 1.9.0's native rules.

Upstream: betterleaks/betterleaks@81aff7a638638aae3a659845d089043e1d8fe9ac,
docs/config.md (Expr match filters), cmd/root.go and cmd/stdin.go.
Candidates and generated TOML live only in process memory. Native diagnostics
can contain config values even with --redact; never forward them or an exception.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path


OVERRIDE = "NATIVE_AGENT_HOST_NAMES_JSON"
PROFILE_ROOT = Path("/mnt/c/Users")
PIN = "1.9.0"
INVALID_UTF8_BYTES = dict.fromkeys(range(0xDC80, 0xDD00), 0xFFFD)
# Microsoft defines these as a shared folder, template, or compatibility
# junction, not a personal profile. Id/email sources are never filtered by it.
SYSTEM_PROFILE_DIRECTORIES = frozenset({"all users", "default", "default user", "public"})


class HostNameScanError(Exception):
    """A value-free failure message safe to show to the caller."""


def _command(argv: list[str], *, root: Path,
             environment: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=10, env=environment)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise HostNameScanError("host-name source unavailable") from None


def host_names(root: Path) -> tuple[str, ...]:
    """Collect the three designated sources; the synthetic override replaces all."""
    if OVERRIDE in os.environ:
        try:
            names = json.loads(os.environ[OVERRIDE])
        except (ValueError, TypeError):
            raise HostNameScanError("invalid synthetic name override") from None
        if not isinstance(names, list) or not names:
            raise HostNameScanError("invalid synthetic name override")
    else:
        identity = _command(["id", "-un"], root=root)
        if identity.returncode or not identity.stdout.strip():
            raise HostNameScanError("host-name source unavailable")
        names = [identity.stdout.strip()]
        try:
            profiles = list(PROFILE_ROOT.iterdir())
        except FileNotFoundError:
            # The optional Windows profile source is absent on non-WSL hosts.
            profiles = []
        except OSError:
            raise HostNameScanError("host-name source unavailable") from None
        try:
            names.extend(path.name for path in profiles
                         if path.name.casefold() not in SYSTEM_PROFILE_DIRECTORIES
                         and stat.S_ISDIR(path.stat().st_mode))
        except OSError:
            raise HostNameScanError("host-name source unavailable") from None
        email = _command(["git", "config", "--get", "user.email"], root=root)
        if email.returncode not in (0, 1):
            raise HostNameScanError("host-name source unavailable")
        if email.returncode == 0 and email.stdout.strip():
            names.append(email.stdout.strip().partition("@")[0])
    if any(not isinstance(name, str) or not name or len(name) > 512
           or any(ord(char) < 32 or ord(char) == 127
                  or 0xD800 <= ord(char) <= 0xDFFF for char in name)
           for name in names):
        raise HostNameScanError("invalid host-name source")
    return tuple(dict.fromkeys(names))


def _config(names: tuple[str, ...]) -> str:
    # Go regexp.QuoteMeta's metacharacter set; quote literals, never parse them.
    special = r"\.+*?()|[]{}^$"
    boundary_filter = (
        # Admit only original-content records. At an artificial cut, the native
        # Unicode boundary rule sees an alphanumeric guard. These additional
        # native filters discard matches that consume that guard itself.
        '!filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`(?:^|\n)[\x1e\x1f][^\n]*$`]) || '
        'filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`(?:^|\n)\x1ex?$`]) || '
        'filter.matchesAny(finding["fragment_raw"][finding["match_end_idx"]:], '
        r'[`^x?\x1e(?:\n|$)`]) || '
        'filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`[\p{L}\p{N}]$`]) || '
        'filter.matchesAny(finding["fragment_raw"][finding["match_end_idx"]:], '
        r'[`^[\p{L}\p{N}]`])')
    lines = ['title = "Runtime host-local names"']
    for index, name in enumerate(names):
        literal = "".join("\\" + char if char in special else char for char in name)
        lines.extend(("[[rules]]", f'id = "host-name-{index}"',
                      'description = "host-local name"',
                      "regex = " + json.dumps("(?i)(" + literal + ")", ensure_ascii=False),
                      "secretGroup = 1", "filter = " + json.dumps(boundary_filter)))
    return "\n".join(lines) + "\n"


def scan_paths(paths: list[Path], *, root: Path,
               names: tuple[str, ...] | None = None) -> list[tuple[Path, int]]:
    """Return only caller-held paths and native numeric lines, never native text."""
    names = host_names(root) if names is None else names
    binary = shutil.which("betterleaks")
    if binary is None:
        raise HostNameScanError("Betterleaks 1.9.0 is required for host-name scan")
    version = _command([binary, "version"], root=root, environment={})
    if version.returncode or version.stdout.strip() not in (PIN, "betterleaks version " + PIN):
        raise HostNameScanError("Betterleaks 1.9.0 is required for host-name scan")
    # Upstream sources/file.go reads 100KB + up to 25KB of lookahead to a
    # double-newline boundary. Each record stays below 25KB even in UTF-8.
    # The overlap contains the longest literal and both Unicode neighbors;
    # native filters keep complete matches and reject artificial edge matches.
    # A text-only prefix also keeps filetype's initial magic probe off input.
    parts: list[str] = ["#" * 1024 + "\n\n"]
    origins: dict[int, tuple[Path, int]] = {}
    line = 3
    overlap = max(map(len, names)) + 2
    step = 4096 - overlap
    for path in paths:
        if path.name.casefold() in {".env", ".credentials.json", "auth.json"}:
            raise HostNameScanError("host-name input is a private authentication file")
        if path.is_symlink():
            raise HostNameScanError("host-name input is a symbolic link")
        try:
            raw = path.read_bytes()
        except OSError:
            raise HostNameScanError("host-name input unreadable") from None
        # Go's regexp treats malformed UTF-8 as replacement runes. Preserve
        # valid UTF-8 literals in mixed binary input instead of using Latin-1.
        text = raw.decode("utf-8", errors="surrogateescape").translate(INVALID_UTF8_BYTES)
        for original_line, text_line in enumerate(text.split("\n"), 1):
            for start in range(0, max(1, len(text_line)), step):
                end = min(start + 4096, len(text_line))
                prefix = "\x1ex" if start else "\x1f"
                suffix = "x\x1e" if end < len(text_line) else "\x1f"
                origins[line] = (path, original_line)
                parts.append(prefix + text_line[start:end] + suffix + "\n\n")
                line += 2
                if end == len(text_line):
                    break
    # stdin needs only its inline config. Do not inherit competing config,
    # logging overrides, synthetic source values or unrelated credentials.
    environment = {"BETTERLEAKS_CONFIG_TOML": _config(names)}
    try:
        completed = subprocess.run(
            [binary, "stdin", "--no-banner", "--no-color", "--log-level", "error",
             "--redact=100", "--report-format", "json", "--report-path", "-",
             "--ignore-gitleaks-allow", "--gitleaks-ignore-path", os.devnull,
             "--max-decode-depth", "0", "--max-archive-depth", "0",
             "--max-target-megabytes", "0"],
            input="".join(parts), cwd=root, env=environment, capture_output=True,
            text=True, encoding="utf-8", errors="strict", timeout=120)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise HostNameScanError("host-name scanner unavailable") from None
    try:
        report = json.loads(completed.stdout)
        if completed.returncode not in (0, 1) or not isinstance(report, list):
            raise ValueError
        findings: set[tuple[Path, int]] = set()
        for item in report:
            if not isinstance(item, dict) or item.get("RuleID") not in {
                    f"host-name-{index}" for index in range(len(names))}:
                raise ValueError
            found_line = item.get("StartLine")
            if type(found_line) is not int or found_line not in origins:
                raise ValueError
            findings.add(origins[found_line])
        if bool(report) != (completed.returncode == 1):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise HostNameScanError("host-name scanner returned an invalid result") from None
    return sorted(findings, key=lambda finding: (str(finding[0]), finding[1]))


def safe_locator(path: Path, line: int, *, root: Path,
                 names: tuple[str, ...] | None = None) -> str:
    """Use relative file:line locators; sanitize any candidate in the path too."""
    try:
        label = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        label = path.name
    for name in (host_names(root) if names is None else names):
        # Paths can contain a deny-name even when file bytes do not.
        label = re.sub(re.escape(name), "<host-name>", label, flags=re.IGNORECASE)
    label = "".join(char if char.isprintable() else "?" for char in label)
    return f"{label}:{line}"
