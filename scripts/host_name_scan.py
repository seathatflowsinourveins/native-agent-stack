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
from collections.abc import Iterable
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
             environment: dict[str, str] | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, cwd=root, capture_output=True, text=True,
                              encoding="utf-8", errors="strict", timeout=timeout, env=environment)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        raise HostNameScanError("host-name source unavailable") from None


def host_names(root: Path) -> tuple[str, ...]:
    """Collect private user/host sources; the synthetic override replaces all."""
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
        hostname = _command(["uname", "-n"], root=root)
        if hostname.returncode or not hostname.stdout.strip():
            raise HostNameScanError("host-name source unavailable")
        names = [identity.stdout.strip()]
        # WSL can expose its public distro/project label as the Linux hostname.
        # Exclude that hostname source only; coincident private sources remain.
        if hostname.stdout.strip().casefold() != os.environ.get("WSL_DISTRO_NAME", "").casefold():
            names.append(hostname.stdout.strip())
        windows = shutil.which("powershell.exe")
        if windows is None and "WSL_DISTRO_NAME" in os.environ:
            installed_windows = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
            if installed_windows.is_file():
                windows = str(installed_windows)
        windows_profiles: list[str] = []
        if windows:
            # Native Windows sources also work when C: is not mounted at /mnt/c.
            # No environment dump, account data, or authentication store is read.
            collected = _command([windows, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                "$ErrorActionPreference='Stop'; "
                "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
                "@{computer=$env:COMPUTERNAME; profiles=@(Get-CimInstance Win32_UserProfile "
                "-ErrorAction Stop | Where-Object { -not $_.Special } | "
                "ForEach-Object { Split-Path -Leaf $_.LocalPath })} | ConvertTo-Json -Compress"],
                root=root, timeout=30)
            try:
                result = json.loads(collected.stdout.lstrip("\ufeff"))
                if collected.returncode or not isinstance(result, dict):
                    raise ValueError
                windows_profiles = result["profiles"]
                if not isinstance(windows_profiles, list) or \
                        any(not isinstance(name, str) for name in windows_profiles):
                    raise ValueError
                names.append(result["computer"])
            except (ValueError, TypeError, KeyError):
                raise HostNameScanError("host-name source unavailable") from None
        elif "WSL_DISTRO_NAME" in os.environ:
            raise HostNameScanError("Windows host-name source unavailable")
        try:
            profiles = list(PROFILE_ROOT.iterdir())
        except FileNotFoundError:
            names.extend(name for name in windows_profiles
                         if isinstance(name, str) and name.casefold() not in SYSTEM_PROFILE_DIRECTORIES)
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
            local, separator, domain = email.stdout.strip().rpartition("@")
            # GitHub documents these no-reply addresses as public commit
            # identities. Other coincident id/profile/host sources stay active.
            if separator and domain.casefold() != "users.noreply.github.com":
                names.append(local)
            elif not separator:
                names.append(domain)
    if any(not isinstance(name, str) or not name or len(name) > 512
           or any(ord(char) < 32 or ord(char) == 127
                  or 0xD800 <= ord(char) <= 0xDFFF for char in name)
           for name in names):
        raise HostNameScanError("invalid host-name source")
    return tuple(dict.fromkeys(names))


def _config(names: tuple[str, ...], *, framed: bool = True) -> str:
    # Go regexp.QuoteMeta's metacharacter set; quote literals, never parse them.
    special = r"\.+*?()|[]{}^$"
    frame_filter = (
        # Admit only original-content records. At an artificial cut, the native
        # Unicode boundary rule sees an alphanumeric guard. These additional
        # native filters discard matches that consume that guard itself.
        '!filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`(?:^|\n)[\x1e\x1f][^\x1e\x1f]*$`]) || '
        'filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`(?:^|\n)\x1ex?$`]) || '
        'filter.matchesAny(finding["fragment_raw"][finding["match_end_idx"]:], '
        r'[`^x?\x1e(?:\n|$)`]) || ')
    boundary_filter = (
        '(filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`[\p{L}\p{N}]$`]) && '
        '!filter.matchesAny(finding["fragment_raw"][:finding["match_start_idx"]], '
        r'[`\\[nrt]$`])) || '
        'filter.matchesAny(finding["fragment_raw"][finding["match_end_idx"]:], '
        r'[`^[\p{L}\p{N}]`])')
    lines = ['title = "Runtime host-local names"']
    for index, name in enumerate(names):
        literal = "".join("\\" + char if char in special else char for char in name)
        lines.extend(("[[rules]]", f'id = "host-name-{index}"',
                      'description = "host-local name"',
                      "regex = " + json.dumps("(?i)(" + literal + ")", ensure_ascii=False),
                      "secretGroup = 1", "filter = " + json.dumps(
                          (frame_filter if framed else "") + boundary_filter)))
    return "\n".join(lines) + "\n"


def scan_paths(paths: list[Path], *, root: Path,
               names: tuple[str, ...] | None = None) -> list[tuple[Path, int]]:
    """Return only caller-held paths and native numeric lines, never native text."""
    names = host_names(root) if names is None else names
    def entries():
        for path in paths:
            if path.name.casefold() in {".env", ".credentials.json", "auth.json"}:
                raise HostNameScanError("host-name input is a private authentication file")
            if path.is_symlink():
                raise HostNameScanError("host-name input is a symbolic link")
            try:
                raw = path.read_bytes()
            except OSError:
                raise HostNameScanError("host-name input unreadable") from None
            yield path, raw.decode("utf-8", errors="surrogateescape").translate(INVALID_UTF8_BYTES)
    return _scan_entries(entries(), root=root, names=names)


def _scan_entries(entries: Iterable[tuple[Path, str]], *, root: Path,
                  names: tuple[str, ...]) -> list[tuple[Path, int]]:
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
    # A percent/Unicode encoding is wider than its decoded literal. Keep a
    # complete single encoded literal plus neighbors across artificial cuts.
    # Refuse an oversized source instead of silently clipping its overlap.
    encoded_width = max(max(len(name.encode("utf-8")) * 3, len(name) * 6) for name in names)
    if encoded_width >= 4094:
        raise HostNameScanError("host-name source exceeds native framing capacity")
    overlap = encoded_width + 2
    step = 4096 - overlap
    for path, text in entries:
        # Go's regexp treats malformed UTF-8 as replacement runes. Preserve
        # valid UTF-8 literals in mixed binary input instead of using Latin-1.
        # Raw data must not impersonate framing markers. Replacement preserves
        # the original line and Unicode neighbor boundary without hiding names.
        text = text.translate({0x1E: 0xFFFD, 0x1F: 0xFFFD})
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
             "--max-decode-depth", "5", "--max-archive-depth", "0",
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


def scan_history(remote_oid: str, local_oid: str, *, root: Path,
                 names: tuple[str, ...]) -> list[tuple[Path, int]]:
    """Use native git mode for pushed diffs and scan author/committer fields."""
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", local_oid) or \
            not re.fullmatch(r"[0-9a-f]{" + str(len(local_oid)) + r"}", remote_oid):
        raise HostNameScanError("invalid pushed history range")
    revisions = ([local_oid, "--not", "--remotes"] if set(remote_oid) == {"0"}
                 else [remote_oid + ".." + local_oid])
    commits = _command(["git", "rev-list", *revisions], root=root)
    if commits.returncode:
        raise HostNameScanError("pushed history unavailable")
    allowed = set(commits.stdout.splitlines())
    if not allowed:
        return []
    # Refuse credential-file paths before the native scanner can read blobs.
    changed = _command(["git", "log", "--name-only", "--format=", "-z", "--no-renames",
                        *revisions, "--"], root=root)
    if changed.returncode or any(Path(name.strip()).name.casefold() in {
            ".env", ".credentials.json", "auth.json"}
            for name in changed.stdout.split("\0") if name.strip()):
        raise HostNameScanError("pushed history contains unavailable or private inputs")
    binary = shutil.which("betterleaks")
    if binary is None:
        raise HostNameScanError("Betterleaks 1.9.0 is required for host-name scan")
    version = _command([binary, "version"], root=root, environment={})
    if version.returncode or version.stdout.strip() not in (PIN, "betterleaks version " + PIN):
        raise HostNameScanError("Betterleaks 1.9.0 is required for host-name scan")
    try:
        completed = subprocess.run(
            [binary, "git", "--no-banner", "--no-color", "--log-level", "error",
             "--redact=100", "--report-format", "json", "--report-path", "-",
             "--ignore-gitleaks-allow", "--gitleaks-ignore-path", os.devnull,
             "--max-decode-depth", "5", "--max-archive-depth", "0",
             "--max-target-megabytes", "0", "--git-workers", "0",
             "--log-opts=--full-history --no-renames " + " ".join(revisions), str(root)],
            cwd=root, env={"BETTERLEAKS_CONFIG_TOML": _config(names, framed=False),
                           "PATH": os.defpath}, capture_output=True,
            text=True, encoding="utf-8", errors="strict", timeout=120)
        report = json.loads(completed.stdout)
        if report is None and completed.returncode == 0:
            report = []
        if completed.returncode not in (0, 1) or not isinstance(report, list) or \
                bool(report) != (completed.returncode == 1):
            raise ValueError
        findings = set()
        for item in report:
            if not isinstance(item, dict) or item.get("RuleID") not in {
                    f"host-name-{index}" for index in range(len(names))}:
                raise ValueError
            commit, filename, line = item.get("Commit"), item.get("File"), item.get("StartLine")
            if commit not in allowed or not isinstance(filename, str) or \
                    not filename or type(line) is not int or line < 1:
                raise ValueError
            path = Path(filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError
            findings.add((root / "git-history" / commit / path, line))
    except (OSError, UnicodeError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        raise HostNameScanError("host-name history scanner returned an invalid result") from None
    # NUL separators preserve identities without putting them in shell
    # arguments, diagnostics or persistent files. Locators alone are returned.
    metadata = _command(["git", "log", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00",
                         *revisions, "--"], root=root)
    if metadata.returncode:
        raise HostNameScanError("pushed identity metadata unavailable")
    fields = metadata.stdout.split("\0")
    entries = []
    while len(fields) >= 5:
        commit, *identities = fields[:5]
        commit = commit.strip()
        fields = fields[5:]
        if commit not in allowed:
            raise HostNameScanError("invalid pushed identity metadata")
        entries.append((root / "git-metadata" / commit, "\n".join(identities)))
    if any(field.strip() for field in fields):
        raise HostNameScanError("invalid pushed identity metadata")
    findings.update(_scan_entries(entries, root=root, names=names))
    return sorted(findings, key=lambda finding: (str(finding[0]), finding[1]))
