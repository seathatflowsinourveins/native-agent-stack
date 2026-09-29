"""Outgoing-text guard for the OpenHands resolver: resolver plan section 3.

No text reaches GitHub (a PR title or body, a review or a comment) unless it
passes these checks in order, each failing closed:
1. the attempt's session key, held in memory only (SessionKey never renders it),
   in its plain, case-folded, separator-stripped, hex and base64 forms;
2. scripts/validate.py's own PRIVATE_CONTENT patterns (token shapes, private keys,
   home paths, local session identifiers), and its scan_file_for_private_content
   on the exact file gh will read (the brief's reuse of `validate.py --scan-file`);
3. the registered host paths and the host user name as a whole word (AGENTS.md
   evidence rules);
4. extra scanners, such as gitleaks with the repository's configuration (plan
   section 3); a scanner error counts as a finding;
5. for model-authored text only: no GitHub closing keyword with an issue
   reference and no @mention. Keywords and syntax: docs.github.com "Linking a pull
   request to an issue" (fetched 2026-09-28): close, closes, closed, fix, fixes,
   fixed, resolve, resolves, resolved, optionally followed by a colon, in any case.
Model-authored text is rendered inert as well: inside a fenced code block or a
code span longer than any backtick run it contains (CommonMark 0.31.2 sections
4.5 and 6.1), so it renders no link, image or HTML.
The checks are a local composition of those sources; a determined encoder can
still hide a value in a form not listed in step 1.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]


def _load_validate():
    """Load this checkout's scripts/validate.py (the importlib source-file recipe)."""
    name = "openhands_resolver_validate"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_validate = _load_validate()
PRIVATE_CONTENT = _validate.PRIVATE_CONTENT
scan_file_for_private_content = _validate.scan_file_for_private_content

MIN_KEY_LENGTH = 16
BODY_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
CLOSING = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[ \t]*:?[ \t]*"
    r"(?:#[0-9]+|GH-[0-9]+|[\w.-]+/[\w.-]+#[0-9]+|https?://github\.com/[\w.-]+/[\w.-]+/(?:issues|pull)/[0-9]+)",
    re.IGNORECASE)
# A GitHub login is alphanumeric with single inner hyphens, at most 39 characters;
# "@org/team" names a team. An @ after a word character (an e-mail address) is not one.
MENTION = re.compile(r"(?<![\w.@/`-])@[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}(?:/[A-Za-z0-9_.-]+)?")
LINE_BREAKS = re.compile(r"\r\n|[\r  \x85]")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


class GuardRefused(Exception):
    """Text that must not be posted. The message is the reason code alone, never the text."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _fold(text):
    return re.sub(r"[^0-9a-z]", "", text.lower())


def _compact(text):
    return re.sub(r"\s+", "", text)


class SessionKey:
    """The attempt's session key, in memory only: repr, str and pickling never expose it."""

    __slots__ = ("_plain", "_forms")

    def __init__(self, value):
        if not isinstance(value, str) or len(value) < MIN_KEY_LENGTH or CONTROL.search(value) or "\n" in value:
            raise ValueError("a session key must be one line of at least 16 characters")
        raw = value.encode("utf-8")
        forms = {value, raw.hex()}
        folded = _fold(value)
        if len(folded) >= 12:
            forms.add(folded)
        for encode in (base64.b64encode, base64.urlsafe_b64encode):
            for offset in range(3):
                encoded = encode(b"\0" * offset + raw).decode("ascii")
                middle = encoded[4 if offset else 0:-4]
                if len(middle) >= 12:
                    forms.add(middle)
        self._plain = value
        self._forms = tuple(sorted(forms))

    def found_in(self, text):
        views = (text, text.lower(), _compact(text), _compact(text).lower(), _fold(text))
        return any(form in view for form in self._forms for view in views)

    def __repr__(self):
        return "SessionKey(<redacted>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("a SessionKey cannot be pickled")


def _canonical_private_dir(path):
    if not isinstance(path, str) or not path.startswith("/") or os.path.realpath(path) != path:
        raise ValueError("the guard directory must be an absolute canonical path")
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.geteuid():
        raise ValueError("the guard directory must be a 0700 directory owned by this user")
    return path


def private_directory(parent):
    """A new 0700 directory (tempfile.mkdtemp) for body files, by canonical path."""
    return _canonical_private_dir(os.path.realpath(tempfile.mkdtemp(prefix="outgoing-", dir=parent)))


def _host_path_forms(paths):
    forms = set()
    for path in paths:
        if not isinstance(path, str) or not path.startswith("/") or CONTROL.search(path):
            raise ValueError("host paths must be absolute")
        if len([part for part in path.split("/") if part]) < 2:
            raise ValueError("a host path needs at least two components")
        forms.update({path.rstrip("/"), os.path.realpath(path)})
    return tuple(sorted(forms))


class OutgoingGuard:
    """Checks outgoing text and writes approved body files that the gh harness accepts."""

    def __init__(self, *, directory, session_key, host_paths, user_name, scanners=()):
        if not isinstance(session_key, SessionKey):
            raise ValueError("session_key must be a SessionKey")
        if not isinstance(user_name, str) or not user_name or CONTROL.search(user_name):
            raise ValueError("user_name must be the host user name")
        self.directory = _canonical_private_dir(directory)
        self._key = session_key
        self._paths = _host_path_forms(host_paths)
        self._user = re.compile(rf"\b{re.escape(user_name)}\b", re.IGNORECASE)
        self._scanners = tuple(scanners)
        self._approved = {}

    def __repr__(self):
        return "OutgoingGuard(<redacted>)"

    def check(self, text, *, model_authored=False):
        """Raise GuardRefused unless `text` may be posted (steps 1-5 of the module docstring)."""
        if not isinstance(text, str):
            raise GuardRefused("not_text")
        if self._key.found_in(text):
            raise GuardRefused("session_key")
        if any(pattern.search(text) for _, pattern in PRIVATE_CONTENT):
            raise GuardRefused("private_content")
        if any(form in text for form in self._paths):
            raise GuardRefused("host_path")
        if self._user.search(text):
            raise GuardRefused("host_user_name")
        for scanner in self._scanners:
            try:
                findings = scanner(text)
            except Exception:
                raise GuardRefused("scanner_error") from None
            if findings:
                raise GuardRefused("scanner_finding")
        if model_authored:
            if CLOSING.search(text):
                raise GuardRefused("closing_keyword")
            if MENTION.search(text):
                raise GuardRefused("mention")

    def approved_text(self, text):
        try:
            self.check(text)
        except GuardRefused:
            return False
        return True

    def register(self, text, *, name):
        """Check `text`, write it to a new 0600 file, scan that exact file, and approve it by hash."""
        if not isinstance(name, str) or not BODY_NAME.fullmatch(name):
            raise ValueError("body file names are short lowercase words")
        self.check(text)
        path = os.path.join(self.directory, f"{name}.md")
        if os.path.lexists(path):
            raise GuardRefused("body_name_reused")
        data = text.encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        if scan_file_for_private_content(Path(path)):
            os.unlink(path)
            raise GuardRefused("private_content")
        self._approved[path] = hashlib.sha256(data).hexdigest()
        return path

    def approved_file(self, path):
        """True only for a registered regular file whose bytes still match their approval."""
        expected = self._approved.get(path)
        if expected is None:
            return False
        try:
            if not stat.S_ISREG(os.lstat(path).st_mode):
                return False
            with open(path, "rb") as handle:
                return hashlib.sha256(handle.read()).hexdigest() == expected
        except OSError:
            return False


LEAK_EXIT = 99
# The host's gitleaks is adoption/tools/gitleaks-guarded, which allows one scan per user: on a
# held lock it exits 75 before any scan starts, asking to "retry after it finishes" (:22-32;
# 75 is EX_TEMPFAIL in sysexits.h). Only that code is retried, within a bound.
GITLEAKS_LOCK_BUSY = 75
LOCK_RETRIES = 60
LOCK_WAIT_SECONDS = 5


def gitleaks_scanner(gitleaks, *, config, workdir, home=None, runner=subprocess.run, sleep=time.sleep):
    """A guard scanner running `gitleaks stdin` with the repository's configuration.

    gitleaks 8.30.1 `stdin --help`: --config, --redact, --no-banner, --exit-code
    (default 1 on a leak) and --ignore-gitleaks-allow. An inline gitleaks:allow
    comment in model text must not suppress a finding, so that option is always on.
    gitleaks and host launchers also exit 1 on errors, so a leak gets its own exit
    code and every other non-zero status raises (the guard counts that as a finding).
    A busy per-user lock (GITLEAKS_LOCK_BUSY) is retried up to LOCK_RETRIES times,
    LOCK_WAIT_SECONDS apart, then raises; it is never read as a clean result.
    The child gets PATH and HOME only, so GITLEAKS_CONFIG cannot replace --config,
    and runs in an empty private directory, so no .gitleaksignore there applies.
    """
    argv = [gitleaks, "stdin", "--config", config, "--no-banner", "--redact", "--ignore-gitleaks-allow",
            "--exit-code", str(LEAK_EXIT), "--log-level", "error"]
    env = {"PATH": "/usr/bin:/bin", "HOME": home or pwd.getpwuid(os.getuid()).pw_dir}

    def scan(text):
        for attempt in range(LOCK_RETRIES + 1):
            result = runner(argv, input=text, cwd=workdir, env=dict(env), capture_output=True,
                            encoding="utf-8", errors="replace", timeout=120, check=False)
            if result.returncode != GITLEAKS_LOCK_BUSY:
                break
            if attempt < LOCK_RETRIES:
                sleep(LOCK_WAIT_SECONDS)
        else:
            raise RuntimeError("gitleaks_lock_busy")
        if result.returncode == 0:
            return []
        if result.returncode == LEAK_EXIT:
            return ["gitleaks"]
        raise RuntimeError("gitleaks_failed")

    return scan


def normalize_text(text):
    """One line-break form and no C0 controls but tab and newline (U+FFFD instead)."""
    return CONTROL.sub("�", LINE_BREAKS.sub("\n", text))


def fence(text):
    """CommonMark 0.31.2 section 4.5: a closing fence must be at least as long as the
    opening one, so a fence longer than every backtick run inside cannot be closed early."""
    body = normalize_text(text).rstrip("\n")
    longest = max((len(run) for run in re.findall(r"`+", body)), default=0)
    marker = "`" * max(3, longest + 1)
    return f"{marker}text\n{body}\n{marker}"


def code_span(text):
    """CommonMark 0.31.2 section 6.1: a backtick string longer than any run inside, with
    one space of padding when the content starts or ends with a backtick, or starts and
    ends with a space (which the renderer strips once)."""
    if not isinstance(text, str) or not text or LINE_BREAKS.search(text) or "\n" in text or CONTROL.search(text):
        raise ValueError("a code span holds one non-empty line")
    ticks = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if (text[0] == "`" or text[-1] == "`" or (text[0] == " " and text[-1] == " " and text.strip(" "))) else ""
    return f"{ticks}{pad}{text}{pad}{ticks}"
