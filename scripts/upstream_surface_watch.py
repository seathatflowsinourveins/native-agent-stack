#!/usr/bin/env python3
"""Zero-token watch for new user-switchable features of Claude Code and Codex.

The daily stack-currency timer pulls in upstream-surface-watch.service (adoption/templates/systemd/), which runs this
with --network before scripts/currency_due.py counts its result. It reads first-party, machine-readable surfaces,
diffs their names against the committed baseline catalogs/foundation/upstream-surface-baseline.json and lists the new
names that catalogs/foundation/upstream-surface-dispositions.json does not decide yet ("unreviewed"), the work list of
the resolver loop. Nothing here calls a model: every source is an HTTPS fetch, a `gh api` call or the local
`codex features list` probe. Usage, sources and exit codes: docs/upstream-surface-watch.md; why these sources and
what no maintained tool covers: docs/decisions/2026-10-04-upstream-surface-watch.md.

Sources (each URL re-read 2026-10-04):

- S1  npm dist-tags of @anthropic-ai/claude-code and @openai/codex (https://registry.npmjs.org/-/package/<name>/
      dist-tags). The watched Claude Code version is the --claude-channel tag, by default latest: the channel the
      repository's Claude settings template selects (adoption/templates/claude.settings.template.json,
      "autoUpdatesChannel": "latest").
- S2  claude:setting, the top-level keys of `interface Settings` ("auto-generated from the settings JSON schema"),
      and claude:hook, the HOOK_EVENTS tuple, from the sdk.d.ts of the @anthropic-ai/claude-agent-sdk version whose
      package.json claudeCodeVersion equals the watched version (resolved through the npm packument, read from
      https://unpkg.com/<package>@<version>/<types>). With no exact match the highest SDK version with a lower
      claudeCodeVersion is read and the run says so (versions.claude_agent_sdk.matched is false). claude:setting is
      the union with the top-level keys of the key headings of https://code.claude.com/docs/en/settings-reference.md
      (S2b), without its global-config keys (~/.claude.json) and the entries it marks removed; key_sources keeps which
      source holds each key.
- S3  claude:env, every backticked upper-case token of at least two characters (ENV_TOKEN) on
      https://code.claude.com/docs/en/env-vars.md, and claude:mod, the cc-plugin-* names on
      https://code.claude.com/docs/en/plugins/mods/overview.md.
- S4  codex:config, the key paths of the stable release's config-schema.json asset (top-level keys, nested table keys
      and features.* keys; `*` stands for a map entry and `[]` for an array item, a path is emitted only for a named
      property, and a profiles.*.<path> that repeats a root <path> is left out), found through one
      `gh api repos/openai/codex/releases/latest` call (the gh convention of
      tools/sota-convergence/github_freshness.py) and verified against the asset's published sha256 digest (a
      release without one is read unverified, and the source's digest_check and a coverage note say so); and
      codex:feature, (name, stage, enabled) from `codex features list` of the installed binary, run with an empty
      temporary CODEX_HOME and HOME, so it neither reads nor writes the host's Codex home and its enabled column is
      the binary's default.
- S5  the changelog delta, report-only text for the resolver with no classification: Claude Code CHANGELOG.md entries
      of versions newer than the baseline's, and the notes of stable Codex releases newer than the baseline's tag
      (one `gh api graphql` call for the newest 100 releases, made only when the stable tag moved past the baseline;
      the releases/latest notes stand in when it fails). It counts the entries and keeps the first 20 whose text
      starts with "Added" or "New" (or sits under a "New ..." heading) or names a setting, env var, hook, mod or
      command.

Each source has an anchor: a parse that finds no anchor, or a count outside BOUNDS, stops the run with exit 3 and
"anchor missing: <name>", so a format change cannot pass as an empty surface; so does a kind below FLOOR_PERCENT (80)
% of its baseline count ("anchor missing: <kind> below 80% of baseline"), which catches an artifact read in part, and
a real removal of more than 20% at once, which needs a reviewed re-baseline. The diff against the baseline gives
new, removed and stage_changed (codex:feature); unreviewed is the keys "surface:kind:name" of the new names that have
no row in the dispositions catalog. A kind whose source this run did not observe (no codex binary, an uncached probe)
is left out of the diff and named in coverage. --cross-check adds report-only comparisons with two third-party
trackers (amitray007/claude-code-schema release catalogs, chenrui333/codex-docs feature lifecycle); a cross-check
failure never fails the run.

With --network every fetched artifact is cached under <state-dir>/cache; without it (the default) the run reads that
cache and says so ("surface watch (cache)" and each source's origin). A --network fetch that fails falls back to the
cache, and the line says "surface watch (partial cache)" (or "(cache)" when every fetch fell back). latest.json's
generated_at is the time of the oldest data the report holds, the oldest cached fetch when any source came from the
cache, so scripts/currency_due.py never counts a report replayed or patched from an old cache as fresh; run_at is the
run's time. Unless --dry-run, a successful run writes the cache and then <state-dir>/latest.json atomically (a
temporary file in the same directory, fsync, mode 0600, os.replace); --dry-run writes nothing and creates no
directory. The default state directory is ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/surface-watch, the
directory scripts/currency_due.py reads.

  python3 scripts/upstream_surface_watch.py --network            # fetch, diff, write; one line for the journal
  python3 scripts/upstream_surface_watch.py --dry-run            # the report as text from the cache; write nothing
  python3 scripts/upstream_surface_watch.py --dry-run --json     # the latest.json document
  python3 scripts/upstream_surface_watch.py --summary            # one line, at most 160 characters
  python3 scripts/upstream_surface_watch.py --check-dispositions # validate the dispositions catalog only
  python3 scripts/upstream_surface_watch.py --paper-window-check # exit 1 inside the paper window (the service's ExecCondition)
  python3 scripts/upstream_surface_watch.py --network --write-baseline [--force]

Exit codes: 0 the run finished (new names or not); 1 the baseline or dispositions catalog is invalid, or a write
failed; 2 a usage error; 3 an anchor is missing; 4 a source could not be fetched and has no usable cache.
--paper-window-check is a condition, not a run: it exits 0 outside the paper window and 1 inside it (paper_window_active()),
which is how upstream-surface-watch.service defers the networked run while a paper session may be trading.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = "native-agent-stack"
WATCH_DIR = "surface-watch"
LATEST_FILE = "latest.json"
CACHE_DIR = "cache"
SCRIPT_PATH = "scripts/upstream_surface_watch.py"
BASELINE_PATH = "catalogs/foundation/upstream-surface-baseline.json"
DISPOSITIONS_PATH = "catalogs/foundation/upstream-surface-dispositions.json"
SCHEMA_VERSION = 1
SUMMARY_LIMIT = 160
# The shortest count text (scripts/currency_due.py uses len("1 pin behind")); a details command that leaves less room
# gives way to `cat <latest.json>`, and longer counts are cut with "..." rather than the command.
MIN_COUNTS_ROOM = len("nothing new")
XDG_POINTER = f'cat "$XDG_STATE_HOME"/{STATE_NAME}/{WATCH_DIR}/{LATEST_FILE}'
USER_AGENT = "native-agent-stack-upstream-surface-watch/1"
HTTP_TIMEOUT = 60
GH_TIMEOUT = 60  # tools/sota-convergence/github_freshness.py gh_api() default
PROBE_TIMEOUT = 60
MAX_BYTES = 32 * 1024 * 1024
ISO_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")

KINDS = ("claude:setting", "claude:hook", "claude:env", "claude:mod", "codex:config", "codex:feature")
STAGED_KIND = "codex:feature"
# Sane count bounds (observed 2026-10-04T15:03Z: 183 settings keys, the union of 173 in sdk.d.ts and 171 in the
# settings reference; 33 hook events, 407 env names, 6 mods; 1,034 Codex config paths after the 307 profiles.* mirrors
# are dropped, of which 101 are top-level and 259 lie under features., 163 of them direct features.<name> keys and the
# rest nested below them; 152 features of codex-cli 0.159.3; 411 changelog versions). A count outside its bound is a
# parser or format failure, never a surface change.
BOUNDS = {
    "claude:setting": (50, 2000),
    "claude:setting/settings-reference": (50, 2000),
    "claude:hook": (10, 300),
    "claude:env": (100, 5000),
    "claude:mod": (1, 300),
    "codex:config": (200, 50000),
    "codex:config/top-level": (30, 3000),
    "codex:config/features": (20, 5000),
    "codex:feature": (30, 5000),
    "claude:changelog/versions": (1, 100000),
}
ALLOWED_UNMATCHED_FEATURE_LINES = 3
# The second, relative guard (check_floors()): an observed kind with fewer than FLOOR_PERCENT % of the names the
# committed baseline holds for it stops the run with exit 3. The absolute BOUNDS pass a heavily under-read artifact
# (the real config-schema.json read without its definitions gives 266 of 1,341 paths, without allOf/anyOf/oneOf 553;
# env-vars.md cut at half its table 218 of 407 names), and a real removal of more than 20% at once is treated the same
# way: it needs a reviewed re-baseline (--network --write-baseline --force), which skips this guard.
FLOOR_PERCENT = 80

CLAUDE_PACKAGE = "@anthropic-ai/claude-code"
CODEX_PACKAGE = "@openai/codex"
SDK_PACKAGE = "@anthropic-ai/claude-agent-sdk"
DIST_TAGS_URL = "https://registry.npmjs.org/-/package/{package}/dist-tags"
PACKUMENT_URL = "https://registry.npmjs.org/{package}"
UNPKG_URL = "https://unpkg.com/{package}@{version}/{path}"
SETTINGS_REFERENCE_URL = "https://code.claude.com/docs/en/settings-reference.md"
SETTING_SOURCES = ("sdk.d.ts", "settings-reference.md")  # the two sources of claude:setting (key_sources order)
ENV_VARS_URL = "https://code.claude.com/docs/en/env-vars.md"
MODS_URL = "https://code.claude.com/docs/en/plugins/mods/overview.md"
CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
CODEX_LATEST_PATH = "repos/openai/codex/releases/latest"
CODEX_LATEST_URL = "https://api.github.com/" + CODEX_LATEST_PATH
CODEX_SCHEMA_ASSET = "config-schema.json"
PROFILE_MIRROR = "profiles.*."  # ConfigToml.profiles: a map of ConfigProfile, which repeats most root keys
GRAPHQL_URL = "https://api.github.com/graphql"
CODEX_RELEASES_QUERY = ("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){releases(first:100,"
                        "orderBy:{field:CREATED_AT,direction:DESC}){nodes{tagName isPrerelease isDraft publishedAt "
                        "description}}}}")
AMIT_LATEST_PATH = "repos/amitray007/claude-code-schema/releases/latest"
AMIT_LATEST_URL = "https://api.github.com/" + AMIT_LATEST_PATH
AMIT_ASSETS = ("settings.catalog.json", "environment.catalog.json")
CHENRUI_LIFECYCLE_URL = "https://raw.githubusercontent.com/chenrui333/codex-docs/main/docs/feature-flags/lifecycle.json"
DIST_TAG_NAMES = ("latest", "stable", "next", "alpha", "beta")
CHANNELS = ("latest", "stable", "next")

# S3: a backticked span that is entirely an upper-case name of at least two characters, without a trailing underscore
# (so a prefix such as `OTEL_` is not a name). The page has no machine-readable list (docs/upstream-surface-watch.md).
ENV_TOKEN = re.compile(r"[A-Z][A-Z0-9_]*[A-Z0-9]")
BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")
MOD_TOKEN = re.compile(r"\bcc-plugin-[a-z0-9]+(?:-[a-z0-9]+)*")
ENV_ANCHOR = re.compile(r"(?im)^#[ \t]+environment variables[ \t]*$")
MODS_ANCHOR = re.compile(r"(?im)^#{2,4}[ \t]+[^\n]*\bbuilt[- ]in(?:to)?\b")
SETTINGS_ANCHOR = re.compile(r"(?m)^(?:export[ \t]+)?(?:declare[ \t]+)?interface[ \t]+Settings\b[^{;]*\{")
HOOKS_ANCHOR = re.compile(r"\bHOOK_EVENTS\s*:\s*readonly\s*\[")
# S2b: the settings reference's own structure. Its title, one "### `key`" heading per documented key (a dotted one,
# such as `sandbox.enabled`, documents a key of its first segment), the `## Global config settings` section, whose
# keys belong in ~/.claude.json and not in a settings file (each also says so in its "**Scope**: `Global config`"
# bullet), and a "<Warning> Removed in vX" note that opens the entry of a removed key. Fenced code blocks hold
# example lines that start with '#', which are no headings.
REFERENCE_TITLE = re.compile(r"(?m)^ {0,3}#[ \t]+All settings(?:[ \t]+#+)?[ \t]*$")
REFERENCE_KEY = re.compile(r"`([^`\s]+)`")
REFERENCE_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*)|$)")
REFERENCE_CLOSING = re.compile(r"(?:^|[ \t]+)#+[ \t]*$")
# The index and headings currently agree exactly; allow two distinct top-level keys of editorial lag.
REFERENCE_INDEX_TOLERANCE = 2
FENCE_OPEN = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
GLOBAL_CONFIG_SECTION = "Global config settings"
GLOBAL_CONFIG_SCOPE = re.compile(r"^[ \t]*[*-][ \t]+\*\*Scope\*\*:.*`Global config`")
REMOVED_NOTE = re.compile(r"^Removed in v\d")
CHANGELOG_HEADING = re.compile(r"(?m)^##[ \t]+(\d+\.\d+\.\d+)[ \t]*$")
FEATURE_ROW = re.compile(r"^(\S+)\s+(\S.*?)\s+(true|false)\s*$")
# S5 selection (report-only): the entry starts with Added/New after an optional "[Platform] " tag, sits under a
# heading that starts with "New", or names a setting, env var, hook, mod or command.
ENTRY_TAG = re.compile(r"^(?:\[[^\]]+\]\s*)+")
ENTRY_LEAD = re.compile(r"^(?:Added|New)\b")
ENTRY_WORDS = re.compile(r"\b(?:settings?|env(?:ironment)?[ -]var(?:iable)?s?|hooks?|mods?|commands?)\b", re.I)
ENTRY_TOKENS = re.compile(r"`[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+`|`/[a-z][a-z0-9:-]*")
TITLE_LIMIT = 20
TITLE_CHARS = 200

DISPOSITIONS = ("enabled", "adopt-pending", "declined", "default-on", "not-applicable", "defer-user",
                "baseline-unreviewed")
ROW_FIELDS = ("key", "disposition", "reason", "source", "carrier", "value", "scope", "overturn", "reviewed_utc",
              "version")
CATALOG_FIELDS = {"schema_version", "generated_utc", "baseline_versions", "rules", "rows", "description"}
# key "surface:kind:name": any kind (the judged ledger spans more kinds than this watch observes), a name without
# whitespace.
ROW_KEY = re.compile(r"(?:claude|codex):[a-z][a-z0-9_-]*:\S+")
ROW_SOURCE = re.compile(r"https?://\S+|[^\s:]\S*:\d+(?:-\d+)?")
CARRIER_REQUIRED = frozenset({"enabled", "adopt-pending"})
OVERTURN_OPTIONAL = frozenset({"baseline-unreviewed"})
REASON_LIMIT = 160


class WatchError(Exception):
    exit_code = 1


class InputError(WatchError):
    """The baseline or the dispositions catalog is invalid, or a write failed (exit 1)."""

    exit_code = 1


class UsageError(WatchError):
    exit_code = 2


class AnchorMissing(WatchError):
    exit_code = 3

    def __init__(self, name: str, detail: str = ""):
        super().__init__(f"anchor missing: {name}" + (f" ({detail})" if detail else ""))


class SourceUnavailable(WatchError):
    exit_code = 4

    def __init__(self, name: str, detail: str):
        super().__init__(f"source unavailable: {name} ({detail})")


# What json can raise on a document it cannot convert: JSONDecodeError and UnicodeError are ValueErrors, an integer
# literal past the interpreter's string-conversion limit (sys.get_int_max_str_digits(), 4300 by default) raises a bare
# ValueError, and nesting past the recursion limit a RecursionError (scripts/currency_due.py read_record() catches the
# first two kinds the same way).
JSON_FAILURES = (ValueError, RecursionError)


# --------------------------------------------------------------------------- small helpers


def utc_text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version_key(text) -> tuple[int, int, int] | None:
    """(major, minor, patch) of the first X.Y.Z in ``text`` ("rust-v0.160.0" and "0.160.0" give (0, 160, 0))."""
    match = VERSION_RE.search(text) if isinstance(text, str) else None
    return tuple(int(part) for part in match.groups()) if match else None


def default_state_dir(environ=os.environ) -> Path:
    """$XDG_STATE_HOME/native-agent-stack/surface-watch, else ~/.local/state/...; a relative XDG_STATE_HOME is ignored,
    as the XDG Base Directory specification requires (scripts/currency_due.py default_state_dir() does the same)."""
    configured = environ.get("XDG_STATE_HOME") or ""
    if os.path.isabs(configured):
        return Path(configured) / STATE_NAME / WATCH_DIR
    home = environ.get("HOME") or str(Path.home())
    return Path(home) / ".local/state" / STATE_NAME / WATCH_DIR


def make_private_dirs(path: Path) -> None:
    """Create each missing component of ``path`` with mode 0700, the XDG Base Directory specification's rule for a
    destination directory that does not exist (so a first run never leaves native-agent-stack/ world-readable)."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    for directory in reversed(missing):
        with contextlib.suppress(FileExistsError):
            os.mkdir(directory, 0o700)


def write_atomic(path: Path, data: bytes, mode: int = 0o600, directory_mode: int = 0o700) -> None:
    """Replace ``path`` atomically: os.replace of a fsynced temporary file in the same directory (the pattern of
    scripts/currency_due.py write_due_file()). A failure before the rename leaves the earlier file."""
    path.parent.mkdir(mode=directory_mode, parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def notice_path(path: Path) -> str:
    """``path`` as ~/... under the home directory when the rest needs no quoting, else absolute (scripts/
    currency_due.py notice_path(); the command must run from any working directory)."""
    try:
        relative = path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)
    return "~/" + relative if relative != "." and shlex.quote(relative) == relative else str(path)


def join_command(tokens: list[str]) -> str:
    """shlex.join, except that a ~/... token stays unquoted so that the shell expands it."""
    return " ".join(token if token.startswith("~/") and shlex.quote(token[2:]) == token[2:] else shlex.quote(token)
                    for token in tokens)


def bounded(name: str, values, bound_key: str):
    """``values`` unchanged when their count is inside BOUNDS[bound_key]; otherwise AnchorMissing(name)."""
    low, high = BOUNDS[bound_key]
    if not low <= len(values) <= high:
        raise AnchorMissing(name, f"count {len(values)} outside {low}..{high}")
    return values


# --------------------------------------------------------------------------- network primitives


def http_get(url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
    """GET ``url`` (urllib follows redirects) and return the body. Raises OSError, ValueError or HTTPException.
    ``timeout`` is urllib's, for each blocking socket operation (the connect, each read), not for the whole fetch:
    the unit's TimeoutStartSec= bounds the run."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https sources
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError(f"response larger than {MAX_BYTES} bytes")
    return body


def gh_api(arguments: list[str], timeout: int = GH_TIMEOUT) -> tuple[bytes | None, str | None]:
    """One ``gh api ...`` call with tools/sota-convergence/github_freshness.py gh_api()'s handling: gh keeps its own
    stored sign-in, nothing here reads, prints or writes a token, and any failure (no gh, a timeout, a nonzero exit)
    comes back as ``(None, bounded reason)`` instead of an exception."""
    try:
        result = subprocess.run(["gh", "api", *arguments], capture_output=True, timeout=timeout,
                                stdin=subprocess.DEVNULL, check=False)
    except Exception as error:  # noqa: BLE001 - a bounded reason string, never re-raised (github_freshness.gh_api)
        return None, f"{type(error).__name__}: {error}"[:160]
    if result.returncode != 0:
        reason = result.stderr.decode("utf-8", "replace").strip()
        return None, (reason[:160] or f"gh exited {result.returncode}")
    return result.stdout, None


def probe_codex(binary: str, timeout: int = PROBE_TIMEOUT) -> tuple[bytes, str]:
    """(stdout of ``codex features list``, the first line of ``codex --version``), run with a minimal environment
    whose HOME and CODEX_HOME are an empty temporary directory: the probe reads no host configuration (so the enabled
    column is the binary's default, not this host's choice) and writes nothing into the host's Codex home."""
    with tempfile.TemporaryDirectory(prefix="surface-watch-codex-") as home:
        environment = {"PATH": os.environ.get("PATH", os.defpath), "HOME": home, "CODEX_HOME": home,
                       "LANG": "C.UTF-8", "NO_COLOR": "1", "TERM": "dumb"}
        version = subprocess.run([binary, "--version"], capture_output=True, timeout=timeout, env=environment,
                                 stdin=subprocess.DEVNULL, check=False)
        listing = subprocess.run([binary, "features", "list"], capture_output=True, timeout=timeout,
                                 env=environment, stdin=subprocess.DEVNULL, check=False)
    if listing.returncode != 0:
        raise OSError(f"codex features list exited {listing.returncode}")
    lines = version.stdout.decode("utf-8", "replace").strip().splitlines() if version.returncode == 0 else []
    return listing.stdout, (lines[0][:80] if lines else "unknown")


def gh_fetch(arguments: list[str]):
    def fetch() -> bytes:
        body, error = gh_api(arguments)
        if error is not None:
            raise OSError(error)
        return body
    return fetch


def http_fetch(url: str):
    return lambda: http_get(url)


# --------------------------------------------------------------------------- cache and fetcher


class Fetcher:
    """Each source through one call: with --network fetch it (falling back to the cache, and saying so, when the fetch
    fails), without it read the cache. A cache entry is <id>.body plus <id>.json ({source, url, version, fetched_utc,
    sha256, bytes}); a body whose sha256 does not match its record, a record for another URL and a record without a
    YYYY-MM-DDTHH:MM:SSZ fetched_utc (the time that ages a report built from it) are no cache. New entries are written
    only by commit(), after the run has succeeded and just before latest.json, so an offline run replays the run that
    wrote latest.json. Every record says whether its source is required and whether it is a report-only cross-check;
    the data of every other source ages the report (cache_use())."""

    def __init__(self, state: Path, network: bool, now_text: str):
        self.directory = state / CACHE_DIR
        self.network = network
        self.now_text = now_text
        self.records: dict[str, dict] = {}
        self.pending: list[tuple[str, bytes, dict]] = []

    def cached(self, source: str):
        try:
            meta = json.loads((self.directory / f"{source}.json").read_text(encoding="utf-8"))
            body = (self.directory / f"{source}.body").read_bytes()
        except (OSError, *JSON_FAILURES):
            return None
        if not isinstance(meta, dict) or meta.get("sha256") != sha256_hex(body):
            return None
        if not isinstance(meta.get("fetched_utc"), str) or not ISO_UTC.fullmatch(meta["fetched_utc"]):
            return None
        return body, meta

    def obtain(self, source: str, url: str, fetch, *, version: str | None = None, required: bool = True,
               digest: str | None = None, digest_expected: bool = False, cross_check: bool = False) -> bytes | None:
        """The body of ``source``. With ``digest`` the body must match that published sha256 digest; a source whose
        publisher normally gives one (``digest_expected``) and did not this time is read unverified, and its record
        says so (digest_check)."""
        flags = {"required": required, "cross_check": cross_check}
        if digest:
            flags["digest_check"] = "verified against the published sha256 digest"
        elif digest_expected:
            flags["digest_check"] = "unverified: no published sha256 digest"
        reason = None
        if self.network:
            try:
                result = fetch()
                body, observed_version = result if isinstance(result, tuple) else (result, version)
                if digest and digest != "sha256:" + sha256_hex(body):
                    raise ValueError("the sha256 does not match the published digest")
            except (OSError, ValueError, http.client.HTTPException, subprocess.SubprocessError) as error:
                reason = f"{type(error).__name__}: {error}"[:200]
            else:
                meta = {"source": source, "url": url, "version": observed_version, "fetched_utc": self.now_text,
                        "sha256": sha256_hex(body), "bytes": len(body)}
                self.pending.append((source, body, meta))
                self.records[source] = dict(meta, origin="network", **flags)
                return body
        entry = self.cached(source)
        if entry is not None:
            body, meta = entry
            if meta.get("url") != url:
                reason = (reason + "; " if reason else "") + f"the cache holds {meta.get('url')}"
            elif digest and digest != "sha256:" + sha256_hex(body):
                reason = (reason + "; " if reason else "") + "the cached body does not match the published digest"
            else:
                origin = "cache" if reason is None else f"cache; the network fetch failed: {reason}"
                self.records[source] = {"source": source, "url": url, "version": meta.get("version"),
                                        "fetched_utc": meta.get("fetched_utc"), "sha256": meta.get("sha256"),
                                        "bytes": meta.get("bytes"), "origin": origin, **flags}
                return body
        detail = reason or "no cache; run with --network"
        if required:
            raise SourceUnavailable(source, detail)
        self.records[source] = {"source": source, "url": url, "origin": "unavailable", "error": detail, **flags}
        return None

    def skip(self, source: str, url: str, why: str) -> None:
        self.records[source] = {"source": source, "url": url, "origin": "skipped", "error": why, "required": False,
                                "cross_check": False}

    def cache_use(self) -> tuple[str | None, str]:
        """(summary label, data time) of this run. The label is "cache" when every source that gave data came from
        the cache (an offline run, or --network with every fetch failing), "partial cache" when some did, else None;
        cross-checks are report-only and do not count. The data time is the oldest fetched_utc of a source that came
        from the cache, else the run's time: a report replayed or patched from the cache is as old as that cache."""
        used = [record for record in self.records.values() if not record.get("cross_check")
                and (record.get("origin") == "network" or str(record.get("origin")).startswith("cache"))]
        cached = [record for record in used if str(record.get("origin")).startswith("cache")]
        label = None
        if cached or not self.network:
            label = "cache" if len(cached) == len(used) or not self.network else "partial cache"
        return label, min([self.now_text, *(record["fetched_utc"] for record in cached)])

    def commit(self) -> None:
        for source, body, meta in self.pending:
            write_atomic(self.directory / f"{source}.body", body)
            write_atomic(self.directory / f"{source}.json", (json.dumps(meta, indent=1) + "\n").encode("utf-8"))
        self.pending.clear()


# --------------------------------------------------------------------------- TypeScript declaration parsing (S2)

IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
NUMBER = re.compile(r"\d+")
TS_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "v": "\v", "0": "\0",
              "'": "'", '"': '"', "\\": "\\"}
HEX_DIGITS = re.compile(r"[0-9a-fA-F]+")


def ts_string_value(text: str) -> str:
    """Decode TypeScript string contents by the ECMAScript StringLiteral escape grammar (no legacy octal).
    NonEscapeCharacter identity escapes are valid; malformed numeric escapes and unescaped newlines are not."""
    chars, index, size = [], 0, len(text)
    while index < size:
        char = text[index]
        index += 1
        if char != "\\":
            if char in "\r\n":
                raise ValueError("unescaped newline in string")
            chars.append(char)
            continue
        if index >= size:
            raise ValueError("unterminated string escape")
        char = text[index]
        index += 1
        if char in "\r\n\u2028\u2029":
            if char == "\r" and index < size and text[index] == "\n":
                index += 1
            continue
        if char in "xu":
            if char == "u" and index < size and text[index] == "{":
                end = text.find("}", index + 1)
                digits = text[index + 1:end] if end >= 0 else ""
                index = end + 1
            else:
                width = 2 if char == "x" else 4
                digits = text[index:index + width]
                index += width
                if len(digits) != width:
                    raise ValueError("incomplete numeric string escape")
            if HEX_DIGITS.fullmatch(digits) is None or int(digits, 16) > 0x10ffff:
                raise ValueError("invalid numeric string escape")
            chars.append(chr(int(digits, 16)))
        elif char in "123456789" or (char == "0" and index < size and text[index] in "0123456789"):
            raise ValueError("legacy numeric string escape")
        else:
            chars.append(TS_ESCAPES.get(char, char))
    # JavaScript strings hold UTF-16 code units; equivalent surrogate-pair and code-point spellings share a name.
    return "".join(chars).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def ts_tokens(text: str, start: int, newlines: bool = False):
    """(kind, value) tokens of a TypeScript declaration from ``start``: comments are skipped, a string or template
    literal is one token (escapes and nested ${...} included), identifiers may hold $ (IDENT). With ``newlines``, a
    line break outside a string (in whitespace, ending a // comment or inside a /* */ comment, as TypeScript's
    scanner counts it) yields ("nl", "")."""
    index, size = start, len(text)
    while index < size:
        char = text[index]
        if char in " \t\r\n":
            if newlines and char == "\n":
                yield "nl", ""
            index += 1
        elif text.startswith("//", index):
            end = text.find("\n", index)
            if newlines and end >= 0:
                yield "nl", ""
            index = size if end < 0 else end + 1
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise ValueError("unterminated comment")
            if newlines and "\n" in text[index:end]:
                yield "nl", ""
            index = end + 2
        elif char in "'\"":
            end = index + 1
            while end < size and text[end] != char:
                end += 2 if text[end] == "\\" else 1
            if end >= size:
                raise ValueError("unterminated string")
            yield "str", ts_string_value(text[index + 1:end])
            index = end + 1
        elif char == "`":
            end, depth = index + 1, 0
            while end < size:
                if text[end] == "\\":
                    end += 2
                    continue
                if depth == 0 and text[end] == "`":
                    break
                if text.startswith("${", end):
                    depth += 1
                    end += 2
                    continue
                if depth and text[end] == "}":
                    depth -= 1
                end += 1
            if end >= size:
                raise ValueError("unterminated template literal")
            yield "tpl", text[index + 1:end]
            index = end + 1
        elif (match := IDENT.match(text, index)) is not None:
            yield "id", match.group()
            index = match.end()
        elif (match := NUMBER.match(text, index)) is not None:
            yield "num", match.group()
            index = match.end()
        elif text.startswith("=>", index):
            yield "op", "=>"
            index += 2
        else:
            yield "op", char
            index += 1


MODIFIERS = frozenset({"readonly", "get", "set"})
# A line break ends a member only after a token that can end a type (TypeScript's parseTypeMemberSemicolon accepts a
# preceding line break once the type is complete): a name or literal that is not a type operator keyword, or a closing
# bracket. After an operator such as ':', '|', '&', '=>' or '?' the type continues on the next line.
TYPE_END_OPS = frozenset(")]}>")
TYPE_OPERATOR_WORDS = frozenset({"extends", "keyof", "typeof", "infer", "is", "asserts", "unique", "readonly", "new",
                                 "as"})


def ends_type(token) -> bool:
    if token is None:
        return False
    kind, value = token
    if kind in ("str", "num", "tpl"):
        return True
    if kind == "id":
        return value not in TYPE_OPERATOR_WORDS
    return kind == "op" and value in TYPE_END_OPS


def interface_members(text: str, start: int) -> list[str]:
    """The top-level member names of the interface body that opens just before ``start``: a member starts after the
    opening brace, after ';' or ',' at depth one, or after a line break that follows a complete type, and its name
    (an identifier, a quoted string or a number, after an optional readonly/get/set modifier) is followed by '?',
    ':', '(' or '<'. Nested object types, parameter lists, type arguments (<...>), index signatures, literals and
    construct signatures (`new (...)`, `new <T>(...)`) are skipped; `new?:` and `new:` are properties."""
    keys: list[str] = []
    depth, paren, bracket, angle = 1, 0, 0, 0
    member_start, pending, pending_kind, modifier, optional = True, None, None, False, False
    line_break, previous = False, None
    for kind, value in ts_tokens(text, start, newlines=True):
        if kind == "nl":
            line_break = True
            continue
        top = depth == 1 and paren == 0 and bracket == 0 and angle == 0
        if top and line_break and not member_start and ends_type(previous):
            member_start, pending, modifier, optional = True, None, False, False  # a newline-terminated member
        line_break = False
        if top:
            if kind == "op" and value in ";,":
                member_start, pending, modifier, optional = True, None, False, False
            elif member_start:
                if pending is None and kind == "id" and value in MODIFIERS:
                    pending, pending_kind, modifier = value, kind, True
                elif kind in ("id", "str", "num") and (pending is None or modifier):
                    pending, pending_kind, modifier = value, kind, False
                elif pending is not None and kind == "op" and value == "?":
                    optional = True
                elif pending is not None and kind == "op" and value in ":(<":
                    construct = pending == "new" and pending_kind == "id" and not optional and value in "(<"
                    if not construct:
                        keys.append(pending)
                    member_start, pending, modifier, optional = False, None, False, False
                else:
                    member_start, pending, modifier, optional = False, None, False, False
        if kind == "op":
            if value == "{":
                depth += 1
            elif value == "}":
                depth -= 1
                if depth == 0:
                    return keys
            elif value == "(":
                paren += 1
            elif value == ")":
                paren -= 1
            elif value == "[":
                bracket += 1
            elif value == "]":
                bracket -= 1
            elif value == "<":
                angle += 1
            elif value == ">" and angle:
                angle -= 1
        previous = (kind, value)
    raise ValueError("unterminated interface body")


def parse_settings_keys(text: str) -> list[str]:
    """claude:setting: the top-level keys of every column-0 ``interface Settings`` declaration (declarations merge)."""
    anchors = list(SETTINGS_ANCHOR.finditer(text))
    if not anchors:
        raise AnchorMissing("sdk.d.ts:interface Settings")
    keys: list[str] = []
    for anchor in anchors:
        try:
            keys += interface_members(text, anchor.end())
        except ValueError as error:
            raise AnchorMissing("sdk.d.ts:interface Settings", str(error)) from None
    return bounded("sdk.d.ts:interface Settings", sorted(set(keys)), "claude:setting")


def parse_hook_events(text: str) -> list[str]:
    """claude:hook: the string literals of ``HOOK_EVENTS: readonly [...]`` up to its closing bracket."""
    anchor = HOOKS_ANCHOR.search(text)
    if anchor is None:
        raise AnchorMissing("sdk.d.ts:HOOK_EVENTS")
    events: list[str] = []
    try:
        for kind, value in ts_tokens(text, anchor.end()):
            if kind == "str":
                events.append(value)
            elif kind == "op" and value == "]":
                break
            elif not (kind == "op" and value == ","):
                raise AnchorMissing("sdk.d.ts:HOOK_EVENTS", f"unexpected token {value!r}")
        else:
            raise AnchorMissing("sdk.d.ts:HOOK_EVENTS", "no closing bracket")
    except ValueError as error:
        raise AnchorMissing("sdk.d.ts:HOOK_EVENTS", str(error)) from None
    return bounded("sdk.d.ts:HOOK_EVENTS", sorted(set(events)), "claude:hook")


# --------------------------------------------------------------------------- other parsers


def load_json(body: bytes, name: str):
    try:
        return json.loads(body)
    except JSON_FAILURES:
        raise AnchorMissing(name, "not JSON") from None


def parse_dist_tags(body: bytes, package: str) -> dict[str, str]:
    """S1: {tag: version} of the npm dist-tags document, restricted to DIST_TAG_NAMES; "latest" must be a version."""
    name = f"npm-dist-tags:{package}"
    tags = load_json(body, name)
    if not isinstance(tags, dict) or not isinstance(tags.get("latest"), str) or not SEMVER_RE.fullmatch(tags["latest"]):
        raise AnchorMissing(name, "no latest version")
    return {tag: tags[tag] for tag in DIST_TAG_NAMES if isinstance(tags.get(tag), str)}


def resolve_sdk(body: bytes, claude_version: str) -> dict:
    """S2: the @anthropic-ai/claude-agent-sdk version whose package.json claudeCodeVersion equals ``claude_version``
    (the highest such version), else the highest version with the highest lower claudeCodeVersion (matched False),
    with the package's types path (package.json "types", default sdk.d.ts)."""
    name = "npm-packument:claudeCodeVersion"
    packument = load_json(body, name)
    versions = packument.get("versions") if isinstance(packument, dict) else None
    if not isinstance(versions, dict):
        raise AnchorMissing(name, "no versions")
    target = version_key(claude_version)
    candidates = []
    for sdk_version, manifest in versions.items():
        if not isinstance(manifest, dict) or not isinstance(manifest.get("claudeCodeVersion"), str):
            continue
        code_key, sdk_key = version_key(manifest["claudeCodeVersion"]), version_key(sdk_version)
        if code_key is None or sdk_key is None or "-" in sdk_version:
            continue
        candidates.append((code_key, sdk_key, sdk_version, manifest))
    if not candidates:
        raise AnchorMissing(name, "no version carries claudeCodeVersion")
    exact = [item for item in candidates if item[0] == target and item[3]["claudeCodeVersion"] == claude_version]
    pool = exact or [item for item in candidates if target is not None and item[0] < target]
    if not pool:
        raise AnchorMissing(name, f"no release for Claude Code {claude_version} or earlier")
    code_key, _, sdk_version, manifest = max(pool, key=lambda item: (item[0], item[1]))
    types = manifest.get("types") if isinstance(manifest.get("types"), str) else "sdk.d.ts"
    if not re.fullmatch(r"[A-Za-z0-9_.][A-Za-z0-9_./-]*\.d\.ts", types) or ".." in types:
        raise AnchorMissing(name, f"unexpected types path {types!r}")
    return {"version": sdk_version, "claude_code_version": manifest["claudeCodeVersion"], "matched": bool(exact),
            "types": types}


def reference_heading(line: str) -> tuple[int, str] | None:
    """CommonMark 0.31.2 section 4.2: ATX headings, including optional closing hashes and up to three spaces."""
    match = REFERENCE_HEADING.fullmatch(line)
    if match is None:
        return None
    return len(match.group(1)), REFERENCE_CLOSING.sub("", match.group(2) or "").strip(" \t")


def reference_entries(text: str) -> list[dict]:
    """[{key, section, lines}] for each ATX key heading (a backticked key) of the settings
    reference outside fenced code blocks (CommonMark fences of three or more backticks or tildes); an entry runs to the
    next heading of level 1-3 outside a fence, and section is the "## " heading above it."""
    entries, section, current, fence = [], None, None, None
    for line in text.splitlines():
        if fence is not None:
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
        elif (opening := FENCE_OPEN.match(line)) is not None:
            fence = opening.group(1)
        elif (heading := reference_heading(line)) is not None:
            level, title = heading
            if (key := REFERENCE_KEY.fullmatch(title)) is not None:
                current = {"key": key.group(1), "section": section, "lines": []}
                entries.append(current)
                continue
            if level <= 3:
                current = None
                if level == 2:
                    section = title
                continue
        if current is not None:
            current["lines"].append(line)
    return entries


def reference_index_keys(text: str) -> set[str]:
    """Independent second reading: first-column backticked keys of the Settings index, including removed/global keys.
    Fences are excluded; descriptions and scope columns cannot invent keys."""
    keys, indexed, fence = set(), False, None
    for line in text.splitlines():
        if fence is not None:
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        if (opening := FENCE_OPEN.match(line)) is not None:
            fence = opening.group(1)
        elif (heading := reference_heading(line)) is not None and heading[0] <= 2:
            indexed = heading == (2, "Settings index")
        elif indexed and line.lstrip().startswith("|"):
            first = line.split("|", 2)[1]
            keys.update(span.split(".")[0] for span in BACKTICK_SPAN.findall(first)
                        if REFERENCE_KEY.fullmatch(f"`{span}`"))
    return keys


def removed_entry(lines: list[str]) -> bool:
    """True when the entry opens with a <Warning> whose text starts "Removed in v<version>"."""
    body = [line.strip() for line in lines if line.strip()]
    if not body or not body[0].startswith("<Warning>"):
        return False
    first = body[0][len("<Warning>"):].strip() or (body[1] if len(body) > 1 else "")
    return REMOVED_NOTE.match(first) is not None


def parse_settings_reference(text: str) -> list[str]:
    """claude:setting, second source: the top-level keys of the settings reference's key headings (a dotted heading
    gives its first segment), leaving out the keys of the `## Global config settings` section or with a `Global
    config` scope (they go in ~/.claude.json, not in a settings file) and the entries the page marks removed. Both the
    title and that section are anchors: without the section the exclusion rule could not hold."""
    if REFERENCE_TITLE.search(text) is None:
        raise AnchorMissing("settings-reference.md:# All settings")
    entries = reference_entries(text)
    if not any(entry["section"] == GLOBAL_CONFIG_SECTION for entry in entries):
        raise AnchorMissing("settings-reference.md:## Global config settings", "no key heading in that section")
    heading_keys = {entry["key"].split(".")[0] for entry in entries}
    index_keys = reference_index_keys(text)
    disagreement = len(heading_keys ^ index_keys)
    if disagreement > REFERENCE_INDEX_TOLERANCE:
        raise AnchorMissing("settings-reference.md:key headings/settings index",
                            f"{disagreement} differing top-level keys, tolerance {REFERENCE_INDEX_TOLERANCE}")
    keys = {entry["key"].split(".")[0] for entry in entries
            if entry["section"] != GLOBAL_CONFIG_SECTION and not removed_entry(entry["lines"])
            and not any(GLOBAL_CONFIG_SCOPE.match(line) for line in entry["lines"])}
    return bounded("settings-reference.md:key headings", sorted(keys), "claude:setting/settings-reference")


def parse_env_names(text: str) -> list[str]:
    """claude:env: every backticked span of the env-vars page that is entirely ENV_TOKEN (page-wide, so a variable a
    later page section adds is not missed; names the page only mentions, such as the scrub list, are included)."""
    if ENV_ANCHOR.search(text) is None:
        raise AnchorMissing("env-vars.md:# Environment variables")
    names = {span for span in BACKTICK_SPAN.findall(text) if ENV_TOKEN.fullmatch(span)}
    return bounded("env-vars.md:backticked names", sorted(names), "claude:env")


def parse_mod_names(text: str) -> list[str]:
    """claude:mod: the cc-plugin-* names on the mods overview page, which must keep its built-in mods section."""
    if MODS_ANCHOR.search(text) is None:
        raise AnchorMissing("mods/overview.md:built-in mods heading")
    return bounded("mods/overview.md:cc-plugin names", sorted(set(MOD_TOKEN.findall(text))), "claude:mod")


def parse_codex_release(body: bytes) -> dict:
    """S4: tag, publication time, notes and the config-schema.json asset (its browser_download_url, never the signed
    redirect, and its published sha256 digest) of `gh api repos/openai/codex/releases/latest`."""
    name = "codex-release:config-schema.json asset"
    release = load_json(body, name)
    if not isinstance(release, dict) or not isinstance(release.get("tag_name"), str):
        raise AnchorMissing(name, "no tag_name")
    if release.get("prerelease") is True or release.get("draft") is True:
        raise AnchorMissing(name, "releases/latest returned a prerelease or draft")
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    asset = next((item for item in assets if isinstance(item, dict) and item.get("name") == CODEX_SCHEMA_ASSET), None)
    url = asset.get("browser_download_url") if asset else None
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        raise AnchorMissing(name, f"{release['tag_name']} has no {CODEX_SCHEMA_ASSET} asset")
    digest = asset.get("digest") if isinstance(asset.get("digest"), str) else None
    return {"tag": release["tag_name"], "published_at": release.get("published_at"),
            "body": release.get("body") if isinstance(release.get("body"), str) else "", "schema_url": url,
            "schema_digest": digest if digest and digest.startswith("sha256:") else None}


def flatten_codex_schema(body: bytes) -> list[str]:
    """codex:config: every named property's dotted path in the ConfigToml JSON schema, through $ref (#/definitions/
    and #/$defs/), allOf/anyOf/oneOf, map values (additionalProperties as a schema: segment `*`) and array items
    (items: the parent segment gains `[]`). A $ref already on the current path is not followed again (recursive
    definitions), a bare map or array container adds no path of its own (its key already has one), and a profile
    path that mirrors a root path (profiles.*.<path> beside <path>) is left out, so one new feature flag is one
    codex:config key (features.<name>) beside its one codex:feature key."""
    schema = load_json(body, "config-schema.json:properties")
    if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
        raise AnchorMissing("config-schema.json:properties")
    # Validate every local reference before counting, including references in otherwise unused definitions.
    # A reviewed re-baseline skips the removal floor, but must never accept an incomplete schema.
    references, anchors, pending = {}, {}, [schema]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str) and reference.startswith("#"):
                references[reference] = None
            if isinstance(node.get("$anchor"), str):
                anchors[node["$anchor"]] = node
            pending.extend(node.values())
        elif isinstance(node, list):
            pending.extend(node)
    for reference in references:
        fragment = urllib.parse.unquote(reference[1:])
        try:
            target = schema
            if fragment.startswith("/"):
                for token in fragment[1:].split("/"):
                    if re.search(r"~(?![01])", token):
                        raise ValueError("invalid JSON pointer escape")
                    token = token.replace("~1", "/").replace("~0", "~")
                    if isinstance(target, list) and re.fullmatch(r"0|[1-9][0-9]*", token):
                        target = target[int(token)]
                    else:
                        target = target[token]
            elif fragment:
                target = anchors[fragment]
        except (KeyError, IndexError, TypeError, ValueError):
            raise AnchorMissing("config-schema.json:$ref", f"unresolved local reference {reference!r}") from None
        references[reference] = target
    features = schema["properties"].get("features")
    if not isinstance(features, dict):
        raise AnchorMissing("config-schema.json:features")
    paths: set[str] = set()

    def branches(node, seen):
        found, pending = [], [(node, seen)]
        while pending:
            current, trail = pending.pop()
            if not isinstance(current, dict):
                continue
            reference = current.get("$ref")
            if isinstance(reference, str) and reference not in trail and reference in references:
                pending.append((references[reference], trail | {reference}))
            found.append((current, trail))  # a $ref's siblings (properties beside it) count too
            for combinator in ("allOf", "anyOf", "oneOf"):
                if isinstance(current.get(combinator), list):
                    pending.extend((item, trail) for item in current[combinator])
        return found

    def walk(node, prefix: list[str], seen: frozenset) -> None:
        for branch, trail in branches(node, seen):
            properties = branch.get("properties")
            if isinstance(properties, dict):
                for key, child in properties.items():
                    path = [*prefix, key]
                    paths.add(".".join(path))
                    walk(child, path, trail)
            values = branch.get("additionalProperties")
            if isinstance(values, dict) and prefix:
                walk(values, [*prefix, "*"], trail)
            items = branch.get("items")
            if isinstance(items, dict) and prefix:
                walk(items, [*prefix[:-1], prefix[-1] + "[]"], trail)

    walk(schema, [], frozenset())
    # A named profile (profiles.<name>) takes most root keys again (ConfigProfile): profiles.*.<path> repeats <path>,
    # so one new root key would be two config keys. Such mirrors are dropped; a key only a profile has stays.
    paths -= {path for path in paths if path.startswith(PROFILE_MIRROR) and path[len(PROFILE_MIRROR):] in paths}
    bounded("config-schema.json:top-level keys", [path for path in paths if "." not in path and "[]" not in path],
            "codex:config/top-level")
    bounded("config-schema.json:features", [path for path in paths if path.startswith("features.")],
            "codex:config/features")
    return bounded("config-schema.json:key paths", sorted(paths), "codex:config")


def parse_codex_features(text: str) -> dict[str, dict]:
    """codex:feature: {name: {stage, enabled}} from `codex features list` rows ("name  stage words  true|false")."""
    rows, unmatched = {}, 0
    for line in text.splitlines():
        if not line.strip():
            continue
        match = FEATURE_ROW.match(line.strip())
        if match is None:
            unmatched += 1
            continue
        rows[match.group(1)] = {"stage": " ".join(match.group(2).split()), "enabled": match.group(3) == "true"}
    if unmatched > ALLOWED_UNMATCHED_FEATURE_LINES:
        raise AnchorMissing("codex features list:rows", f"{unmatched} lines are not name/stage/enabled rows")
    bounded("codex features list:rows", rows, "codex:feature")
    return rows


def parse_changelog(text: str) -> list[tuple[str, list[str]]]:
    """S5: [(version, [entry, ...]), ...] of CHANGELOG.md's "## X.Y.Z" sections, top-level "- " bullets only."""
    headings = list(CHANGELOG_HEADING.finditer(text))
    bounded("CHANGELOG.md:## X.Y.Z headings", headings, "claude:changelog/versions")
    sections = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        entries = [line[2:].strip() for line in text[heading.end():end].splitlines() if line.startswith("- ")]
        sections.append((heading.group(1), entries))
    return sections


def note_entries(body: str) -> list[tuple[str, str]]:
    """[(heading, entry)] of a release body's top-level bullets ("- " or "* "), each with its nearest heading."""
    heading, entries = "", []
    for line in (body or "").splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        elif line.startswith(("- ", "* ")):
            entries.append((heading, line[2:].strip()))
    return entries


def selected(entry: str, heading: str = "") -> bool:
    text = ENTRY_TAG.sub("", entry)
    return bool(ENTRY_LEAD.match(text) or heading.lower().startswith("new") or ENTRY_WORDS.search(entry)
                or ENTRY_TOKENS.search(entry))


def claude_changelog_delta(text: str, baseline_version: str) -> dict:
    base = version_key(baseline_version)
    newer = [(version, entries) for version, entries in parse_changelog(text)
             if base is not None and version_key(version) > base]
    titles, matching, total = [], 0, 0
    for version, entries in newer:
        for entry in entries:
            total += 1
            if selected(entry):
                matching += 1
                if len(titles) < TITLE_LIMIT:
                    titles.append(f"{version}: {entry}"[:TITLE_CHARS])
    return {"source": CHANGELOG_URL, "baseline": baseline_version, "versions": [version for version, _ in newer],
            "entries": total, "matching": matching, "titles": titles}


def codex_notes_delta(releases: list[dict], baseline_tag: str, complete: bool, note: str | None) -> dict:
    titles, matching, total = [], 0, 0
    for release in releases:
        short = release["tag"].removeprefix("rust-v")
        for heading, entry in note_entries(release.get("body") or ""):
            total += 1
            if selected(entry, heading):
                matching += 1
                if len(titles) < TITLE_LIMIT:
                    titles.append(f"{short}: {entry}"[:TITLE_CHARS])
    delta = {"source": "https://github.com/openai/codex/releases", "baseline": baseline_tag,
             "releases": [release["tag"] for release in releases], "entries": total, "matching": matching,
             "titles": titles, "complete": complete}
    if note:
        delta["note"] = note
    return delta


def parse_release_list(body: bytes) -> list[dict] | None:
    """The stable, non-draft releases of the GraphQL list, newest first, or None when the answer has no list."""
    try:
        answer = json.loads(body)
        nodes = answer["data"]["repository"]["releases"]["nodes"]
    except (*JSON_FAILURES, KeyError, TypeError):
        return None
    if not isinstance(nodes, list):
        return None
    releases = []
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("tagName"), str) and version_key(node["tagName"]):
            releases.append({"tag": node["tagName"], "published_at": node.get("publishedAt"),
                             "body": node.get("description") if isinstance(node.get("description"), str) else "",
                             "stable": node.get("isPrerelease") is False and node.get("isDraft") is False})
    return releases


# --------------------------------------------------------------------------- baseline and dispositions


def read_json_file(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"{label} not found: {path}") from None
    except (OSError, *JSON_FAILURES) as error:
        raise InputError(f"{label} unreadable: {path} ({type(error).__name__})") from None


def validate_baseline(document) -> list[str]:
    errors = []
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        return [f"baseline: schema_version {SCHEMA_VERSION} expected"]
    kinds = document.get("kinds")
    if not isinstance(kinds, dict):
        return ["baseline: kinds must be an object"]
    for kind in KINDS:
        names = kinds.get(kind)
        if not isinstance(names, list) or not all(isinstance(name, str) and name for name in names):
            errors.append(f"baseline: kinds[{kind!r}] must be a list of names")
        elif names != sorted(set(names)):
            errors.append(f"baseline: kinds[{kind!r}] must be sorted and unique")
    pairs = (document.get("stages") or {}).get(STAGED_KIND) if isinstance(document.get("stages"), dict) else None
    if not isinstance(pairs, list) or not all(isinstance(pair, list) and len(pair) == 2
                                              and all(isinstance(part, str) for part in pair) for pair in pairs):
        errors.append(f"baseline: stages[{STAGED_KIND!r}] must be a list of [name, stage] pairs")
    for field in ("versions", "sources"):
        if not isinstance(document.get(field), dict):
            errors.append(f"baseline: {field} must be an object")
    held = (document.get("source_counts") or {}).get("claude:setting") if isinstance(
        document.get("source_counts"), dict) else None
    if not isinstance(held, dict) or set(held) != set(SETTING_SOURCES) or not all(
            isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in held.values()):
        errors.append(f"baseline: source_counts['claude:setting'] must count each of {', '.join(SETTING_SOURCES)}")
    return errors


def load_baseline(path: Path) -> dict:
    document = read_json_file(path, "baseline")
    errors = validate_baseline(document)
    if errors:
        raise InputError("; ".join(errors[:5]))
    return document


def validate_dispositions(document) -> list[str]:
    """Schema and key-uniqueness errors of the dispositions catalog (docs/upstream-surface-watch.md#dispositions);
    an empty list means valid. Linear in the rows, so the judged ledger's ~1,200 rows check well under a second."""
    if not isinstance(document, dict):
        return ["dispositions: expected a JSON object"]
    errors = [f"dispositions: unknown top-level field {key!r}" for key in sorted(set(document) - CATALOG_FIELDS)]
    if document.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"dispositions: schema_version {SCHEMA_VERSION} expected")
    if not isinstance(document.get("generated_utc"), str) or not ISO_UTC.fullmatch(document["generated_utc"]):
        errors.append("dispositions: generated_utc must be YYYY-MM-DDTHH:MM:SSZ")
    versions = document.get("baseline_versions")
    if not isinstance(versions, dict) or not versions or not all(
            isinstance(key, str) and isinstance(value, str) and value for key, value in versions.items()):
        errors.append("dispositions: baseline_versions must be a nonempty object of version strings")
    rules = document.get("rules")
    if not isinstance(rules, dict):
        errors.append("dispositions: rules must be an object")
    else:
        for value in DISPOSITIONS:
            if not isinstance(rules.get(value), str) or not rules[value].strip():
                errors.append(f"dispositions: rules[{value!r}] must document that value")
    rows = document.get("rows")
    if not isinstance(rows, list):
        return errors + ["dispositions: rows must be a list"]
    seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        label = f"rows[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{label}: expected an object")
            continue
        missing = [field for field in ROW_FIELDS if field not in row]
        unknown = sorted(set(row) - set(ROW_FIELDS))
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
        if unknown:
            errors.append(f"{label}: unknown field(s) {', '.join(unknown)}")
        key = row.get("key")
        if not isinstance(key, str) or len(key) > 300 or not ROW_KEY.fullmatch(key):
            errors.append(f"{label}: key must look like claude:setting:autoUpdatesChannel")
        elif key in seen:
            errors.append(f"{label}: duplicate key {key} (first at rows[{seen[key]}])")
        else:
            seen[key] = index
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{label}: disposition must be one of {', '.join(DISPOSITIONS)}")
        reason = row.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > REASON_LIMIT or "\n" in reason:
            errors.append(f"{label}: reason must be one line of 1-{REASON_LIMIT} characters")
        source = row.get("source")
        if not isinstance(source, str) or len(source) > 500 or not ROW_SOURCE.fullmatch(source):
            errors.append(f"{label}: source must be a URL or path:line")
        carrier = row.get("carrier")
        if carrier is not None and (not isinstance(carrier, str) or not carrier.strip() or len(carrier) > 300):
            errors.append(f"{label}: carrier must be a nonempty string or null")
        elif carrier is None and disposition in CARRIER_REQUIRED:
            errors.append(f"{label}: carrier is required for {disposition}")
        scope = row.get("scope")
        if scope is not None and (not isinstance(scope, str) or not scope.strip() or len(scope) > 80):
            errors.append(f"{label}: scope must be a short string or null")
        overturn = row.get("overturn")
        if overturn is None and disposition not in OVERTURN_OPTIONAL:
            errors.append(f"{label}: overturn is required for {disposition}")
        elif overturn is not None and (not isinstance(overturn, str) or not overturn.strip() or len(overturn) > 300):
            errors.append(f"{label}: overturn must be 1-300 characters")
        reviewed = row.get("reviewed_utc")
        if not isinstance(reviewed, str) or not ISO_UTC.fullmatch(reviewed):
            errors.append(f"{label}: reviewed_utc must be YYYY-MM-DDTHH:MM:SSZ")
        version = row.get("version")
        if not isinstance(version, str) or not version.strip() or len(version) > 80:
            errors.append(f"{label}: version must be a nonempty string")
    return errors


def load_dispositions(path: Path) -> dict:
    document = read_json_file(path, "dispositions")
    errors = validate_dispositions(document)
    if errors:
        raise InputError("; ".join(errors[:5]) + (f" (and {len(errors) - 5} more)" if len(errors) > 5 else ""))
    return document


# --------------------------------------------------------------------------- observation and diff


def observe(fetcher: Fetcher, channel: str, codex_binary: str | None) -> dict:
    """Fetch and parse S1-S4 (raising AnchorMissing or SourceUnavailable); returns names per observed kind, the
    codex feature rows and the resolved versions."""
    url = DIST_TAGS_URL.format(package=CLAUDE_PACKAGE)
    claude_tags = parse_dist_tags(fetcher.obtain("npm-claude-code-dist-tags", url, http_fetch(url)), CLAUDE_PACKAGE)
    url = DIST_TAGS_URL.format(package=CODEX_PACKAGE)
    codex_tags = parse_dist_tags(fetcher.obtain("npm-codex-dist-tags", url, http_fetch(url)), CODEX_PACKAGE)
    watched = claude_tags.get(channel)
    if not isinstance(watched, str) or not SEMVER_RE.fullmatch(watched):
        raise AnchorMissing(f"npm-dist-tags:{CLAUDE_PACKAGE}", f"no {channel} tag")

    url = PACKUMENT_URL.format(package=SDK_PACKAGE)
    sdk = resolve_sdk(fetcher.obtain("npm-claude-agent-sdk-packument", url, http_fetch(url)), watched)
    url = UNPKG_URL.format(package=SDK_PACKAGE, version=sdk["version"], path=sdk["types"])
    declarations = fetcher.obtain("claude-agent-sdk-types", url, http_fetch(url), version=sdk["version"])
    declarations = declarations.decode("utf-8", "replace")
    typed = parse_settings_keys(declarations)
    page = fetcher.obtain("claude-settings-reference-page", SETTINGS_REFERENCE_URL, http_fetch(SETTINGS_REFERENCE_URL))
    documented = parse_settings_reference(page.decode("utf-8", "replace"))
    # claude:setting is the union of both sources; key_sources keeps which source holds each key.
    key_sources = {"claude:setting": dict(zip(SETTING_SOURCES, (typed, documented)))}
    names = {"claude:setting": sorted({*typed, *documented}), "claude:hook": parse_hook_events(declarations)}
    page = fetcher.obtain("claude-env-vars-page", ENV_VARS_URL, http_fetch(ENV_VARS_URL))
    names["claude:env"] = parse_env_names(page.decode("utf-8", "replace"))
    page = fetcher.obtain("claude-mods-overview-page", MODS_URL, http_fetch(MODS_URL))
    names["claude:mod"] = parse_mod_names(page.decode("utf-8", "replace"))

    release = parse_codex_release(fetcher.obtain("github-codex-latest-release", CODEX_LATEST_URL,
                                                 gh_fetch([CODEX_LATEST_PATH])))
    schema = fetcher.obtain("codex-config-schema", release["schema_url"], http_fetch(release["schema_url"]),
                            version=release["tag"], digest=release["schema_digest"], digest_expected=True)
    names["codex:config"] = flatten_codex_schema(schema)

    features, binary_version = None, None
    probe_label = "codex features list"
    if fetcher.network and codex_binary is None:
        fetcher.skip("codex-features-list", probe_label, "no codex binary found")
    else:
        listing = fetcher.obtain("codex-features-list", probe_label,
                                 (lambda: probe_codex(codex_binary)) if codex_binary else None, required=False)
        if listing is not None:
            features = parse_codex_features(listing.decode("utf-8", "replace"))
            binary_version = fetcher.records["codex-features-list"].get("version")
            names[STAGED_KIND] = sorted(features)
    return {"names": names, "features": features, "release": release, "sdk": sdk, "claude_tags": claude_tags,
            "codex_tags": codex_tags, "watched": watched, "codex_binary": binary_version, "key_sources": key_sources}


def floor_failure(label: str, observed: int, held: int) -> AnchorMissing | None:
    if observed * 100 >= held * FLOOR_PERCENT:
        return None
    return AnchorMissing(f"{label} below {FLOOR_PERCENT}% of baseline",
                         f"count {observed}, baseline {held}: a parser or format failure, or a real removal of more "
                         f"than {100 - FLOOR_PERCENT}% at once; review it, then re-baseline with --network "
                         f"--write-baseline --force")


def check_floors(names: dict, baseline: dict, key_sources: dict | None = None) -> None:
    """AnchorMissing (exit 3) for the first observed kind, or source of a two-source kind (key_sources against the
    baseline's source_counts), whose count is below FLOOR_PERCENT % of its baseline count; an unobserved kind is not
    checked. BOUNDS stay the absolute guard inside each parser."""
    for kind in KINDS:
        if kind not in names:
            continue
        failures = [floor_failure(kind, len(names[kind]), len(baseline["kinds"].get(kind, [])))]
        held = (baseline.get("source_counts") or {}).get(kind, {})
        for source, keys in ((key_sources or {}).get(kind) or {}).items():
            if source in held:
                failures.append(floor_failure(f"{kind} from {source}", len(keys), held[source]))
        failure = next((item for item in failures if item is not None), None)
        if failure is not None:
            raise failure


def diff_surface(names: dict, features: dict | None, baseline: dict,
                 key_sources: dict | None = None) -> tuple[list, list, list]:
    """new, removed and stage_changed of the observed kinds against the baseline (an unobserved kind is skipped). A
    new name of a two-source kind carries the sources that hold it (key_sources), so a key one source lacks shows."""
    new, removed, stage_changed = [], [], []
    for kind in KINDS:
        if kind not in names:
            continue
        surface, _, short = kind.partition(":")
        before, now = set(baseline["kinds"].get(kind, [])), set(names[kind])
        holders = {source: set(keys) for source, keys in ((key_sources or {}).get(kind) or {}).items()}
        for name in sorted(now - before):
            item = {"key": f"{kind}:{name}", "surface": surface, "kind": short, "name": name}
            if kind == STAGED_KIND and features and name in features:
                item.update(features[name])
            if holders:
                item["sources"] = [source for source, keys in holders.items() if name in keys]
            new.append(item)
        removed += [{"key": f"{kind}:{name}", "surface": surface, "kind": short, "name": name}
                    for name in sorted(before - now)]
    if features is not None:
        old = {name: stage for name, stage in baseline["stages"][STAGED_KIND]}
        for name in sorted(features):
            if name in old and old[name] != features[name]["stage"]:
                stage_changed.append({"key": f"{STAGED_KIND}:{name}", "name": name, "from": old[name],
                                      "to": features[name]["stage"]})
    return new, removed, stage_changed


def codex_changelog(fetcher: Fetcher, release: dict, baseline_tag: str) -> dict:
    base, latest = version_key(baseline_tag), version_key(release["tag"])
    if base is None or latest is None or latest <= base:
        return codex_notes_delta([], baseline_tag, True, None)
    body = fetcher.obtain("github-codex-releases", GRAPHQL_URL,
                          gh_fetch(["graphql", "-f", f"query={CODEX_RELEASES_QUERY}", "-f", "owner=openai",
                                    "-f", "name=codex"]), required=False)
    listed = parse_release_list(body) if body is not None else None
    fallback = [{"tag": release["tag"], "published_at": release["published_at"], "body": release["body"]}]
    if not listed:
        return codex_notes_delta(fallback, baseline_tag, False,
                                 "the release list was not available; only the releases/latest notes are included")
    newer = [item for item in listed if item["stable"] and version_key(item["tag"]) > base]
    newer.sort(key=lambda item: version_key(item["tag"]), reverse=True)
    if release["tag"] not in {item["tag"] for item in newer}:
        newer.insert(0, fallback[0])
    reaches = any(version_key(item["tag"]) <= base for item in listed)
    return codex_notes_delta(newer, baseline_tag, reaches, None if reaches else
                             "the newest 100 releases do not reach back to the baseline tag; older notes are not "
                             "included")


# --------------------------------------------------------------------------- cross-check (report-only)


def compare_names(ours, theirs) -> dict:
    ours, theirs = set(ours), set(theirs)
    return {"ours": len(ours), "theirs": len(theirs), "common": len(ours & theirs),
            "only_ours_count": len(ours - theirs), "only_ours": sorted(ours - theirs)[:20],
            "only_theirs_count": len(theirs - ours), "only_theirs": sorted(theirs - ours)[:20]}


def cross_check_claude(fetcher: Fetcher, names: dict) -> dict:
    body = fetcher.obtain("xc-amitray-latest-release", AMIT_LATEST_URL, gh_fetch([AMIT_LATEST_PATH]), required=False,
                          cross_check=True)
    if body is None:
        return {"status": "unavailable", "error": fetcher.records["xc-amitray-latest-release"]["error"]}
    release = json.loads(body)
    assets = {item["name"]: item for item in release.get("assets", []) if isinstance(item, dict) and "name" in item}
    catalogs = {}
    for name in AMIT_ASSETS:
        asset = assets.get(name)
        if asset is None:
            return {"status": "error", "tag": release.get("tag_name"), "error": f"no {name} asset"}
        digest = asset.get("digest") if isinstance(asset.get("digest"), str) else None
        data = fetcher.obtain(f"xc-amitray-{name.split('.')[0]}", asset["browser_download_url"],
                              http_fetch(asset["browser_download_url"]), version=release.get("tag_name"),
                              required=False, digest=digest, digest_expected=True, cross_check=True)
        if data is None:
            return {"status": "unavailable", "tag": release.get("tag_name"), "error": f"{name} not fetched"}
        catalogs[name] = json.loads(data)
    settings = catalogs["settings.catalog.json"]
    environment = catalogs["environment.catalog.json"]
    setting_names = {fact["path"].split(".")[0] for fact in settings.get("facts", [])
                     if isinstance(fact, dict) and isinstance(fact.get("path"), str)}
    # configurableVariables is a list of names; supplements and providedToHooks are {name, scope, source} objects
    # (environment.catalog.json of v2.1.289, read 2026-10-04).
    env_names = {item if isinstance(item, str) else item.get("name")
                 for group in ("configurableVariables", "supplements", "providedToHooks")
                 for item in environment.get(group, [])
                 if isinstance(item, str) or (isinstance(item, dict) and isinstance(item.get("name"), str))}
    result = {"status": "compared", "repository": "https://github.com/amitray007/claude-code-schema",
              "tag": release.get("tag_name"), "claude_code_version": settings.get("claudeCodeVersion")}
    if "claude:setting" in names:
        result["claude:setting"] = compare_names(names["claude:setting"], setting_names)
    if "claude:env" in names:
        result["claude:env"] = compare_names(names["claude:env"], env_names)
    return result


def cross_check_codex(fetcher: Fetcher, features: dict | None) -> dict:
    body = fetcher.obtain("xc-chenrui-lifecycle", CHENRUI_LIFECYCLE_URL, http_fetch(CHENRUI_LIFECYCLE_URL),
                          required=False, cross_check=True)
    if body is None:
        return {"status": "unavailable", "error": fetcher.records["xc-chenrui-lifecycle"]["error"]}
    lifecycle = json.loads(body)
    theirs = {item["key"]: item for item in lifecycle.get("cli_features", [])
              if isinstance(item, dict) and isinstance(item.get("key"), str)}
    result = {"status": "compared", "repository": "https://github.com/chenrui333/codex-docs",
              "codex_cli_version": lifecycle.get("codex_cli_version")}
    if features is not None:
        result["codex:feature"] = compare_names(features, theirs)
        result["codex:feature"]["stage_differs"] = sorted(
            name for name in set(features) & set(theirs) if str(theirs[name].get("stage")) != features[name]["stage"])
    return result


def cross_check(fetcher: Fetcher, observed: dict) -> dict:
    """Report-only comparisons; any failure is recorded and never fails the run."""
    result = {}
    for label, check in (("claude", lambda: cross_check_claude(fetcher, observed["names"])),
                         ("codex", lambda: cross_check_codex(fetcher, observed["features"]))):
        try:
            result[label] = check()
        except Exception as error:  # noqa: BLE001 - report-only by design: a cross-check never fails the run
            result[label] = {"status": "error", "error": f"{type(error).__name__}: {error}"[:200]}
    return result


# --------------------------------------------------------------------------- document, summary, baseline


def details_command(root: Path, state: Path, args, needs_network: bool) -> str:
    """The command that prints this run's details from any working directory: the checkout's own copy of this script
    with --dry-run, which replays the cache, plus the options that change the result (--network when this run left no
    cache, a non-default state directory, baseline, dispositions or channel)."""
    script = root / SCRIPT_PATH
    if script.is_file():
        command = ["python3", notice_path(script), "--dry-run"]
    else:
        command = ["python3", notice_path(Path(__file__).resolve()), "--dry-run", "--root", notice_path(root)]
    if needs_network:
        command.append("--network")
    if args.state_dir is not None:
        command += ["--state-dir", notice_path(state)]
    for option, value in (("--baseline", args.baseline), ("--dispositions", args.dispositions)):
        if value is not None:
            command += [option, notice_path(value.expanduser().resolve())]
    if args.claude_channel != "latest":
        command += ["--claude-channel", args.claude_channel]
    return join_command(command)


def summary_line(counts: list[str], tail: str, candidates: list[str], label: str | None) -> str:
    """The counts and the first candidate command that leaves them MIN_COUNTS_ROOM characters, within SUMMARY_LIMIT;
    ``tail`` (the versions) is added only when it fits. ``label`` ("cache" or "partial cache", Fetcher.cache_use())
    marks a line built from cached data. No fitting candidate is a usage error (exit 2)."""
    prefix = f"surface watch ({label}): " if label else "surface watch: "
    for candidate in candidates:
        suffix = f"; details: {candidate}"
        room = SUMMARY_LIMIT - len(prefix) - len(suffix)
        if room >= MIN_COUNTS_ROOM:
            break
    else:
        raise UsageError(f"no runnable details command fits the {SUMMARY_LIMIT}-character summary line; use "
                         f"XDG_STATE_HOME or a shorter --state-dir")
    text = ", ".join(counts)
    if len(text) + len(tail) + 1 <= room:
        text = f"{text} {tail}"
    elif len(text) > room:
        text = text[:room - 3] + "..."
    return prefix + text + suffix


def key_source_coverage(key_sources: dict, baseline: dict) -> dict:
    """Per source of a two-source kind: its observed and baseline counts and the keys only it holds (the first 50), so a
    key that one source lacks is visible on every run."""
    result = {}
    for kind, sources in key_sources.items():
        held = (baseline.get("source_counts") or {}).get(kind, {})
        result[kind] = {}
        for source, keys in sources.items():
            others = set().union(*(set(other) for name, other in sources.items() if name != source))
            only = sorted(set(keys) - others)
            result[kind][source] = {"observed": len(keys), "baseline": held.get(source), "only_here_count": len(only),
                                    "only_here": only[:50]}
    return result


def build_baseline(observed: dict, fetcher: Fetcher, now_text: str, channel: str) -> dict:
    names = observed["names"]
    missing = [kind for kind in KINDS if kind not in names]
    if missing:
        raise InputError(f"--write-baseline needs every kind observed; not observed: {', '.join(missing)}")
    # A baseline made from a cached artifact would grandfather every switch added since that fetch, and the next run
    # would report nothing new: every source it records must have come from the network in this run (cross-checks are
    # report-only and not recorded).
    not_fresh = {source: str(record.get("origin"))[:120] for source, record in sorted(fetcher.records.items())
                 if not record.get("cross_check") and record.get("origin") != "network"}
    if not_fresh:
        raise SourceUnavailable(", ".join(not_fresh), "--write-baseline needs every source fetched from the network in "
                                "this run, not read from the cache: " + "; ".join(
                                    f"{source}: {origin}" for source, origin in not_fresh.items()))
    sources = {}
    for source, record in sorted(fetcher.records.items()):
        if record.get("origin") in ("skipped", "unavailable") or source.startswith("xc-"):
            continue
        entry = {"url": record["url"]} if record["url"].startswith("https://") else {"command": record["url"]}
        entry.update({"version": record.get("version"), "fetched_utc": record.get("fetched_utc"),
                      "sha256": record.get("sha256"), "bytes": record.get("bytes")})
        sources[source] = entry
    release, sdk = observed["release"], observed["sdk"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": now_text,
        "generator": "python3 scripts/upstream_surface_watch.py --network --write-baseline",
        "description": ("Names-only snapshot of the user-switchable surface of Claude Code and Codex at the versions "
                        "below: sorted names per kind, the codex:feature stages that stage_changed compares, the "
                        "per-source counts of claude:setting (the union of sdk.d.ts and settings-reference.md) that "
                        "the 80% floor compares, and per fetched artifact its URL, version, fetch time, sha256 and "
                        "size, never its content. docs/upstream-surface-watch.md."),
        "versions": {"claude_code": observed["watched"], "claude_code_channel": channel,
                     "claude_agent_sdk": sdk["version"], "claude_agent_sdk_claude_code_version":
                         sdk["claude_code_version"], "codex": release["tag"], "codex_binary": observed["codex_binary"]},
        "counts": {kind: len(names[kind]) for kind in KINDS},
        "source_counts": {kind: {source: len(keys) for source, keys in sources.items()}
                          for kind, sources in observed["key_sources"].items()},
        "sources": sources,
        "kinds": {kind: sorted(names[kind]) for kind in KINDS},
        "stages": {STAGED_KIND: [[name, observed["features"][name]["stage"]] for name in sorted(observed["features"])]},
    }


def run(args) -> tuple[dict, str]:
    root = args.root.expanduser().resolve()
    state = (args.state_dir if args.state_dir is not None else default_state_dir()).expanduser().resolve()
    if state == root or root in state.parents:
        raise UsageError(f"--state-dir must be outside the checkout ({root})")
    baseline_path = (args.baseline or root / BASELINE_PATH).expanduser().resolve()
    dispositions_path = (args.dispositions or root / DISPOSITIONS_PATH).expanduser().resolve()
    now = clock_now(args.now)
    now_text = utc_text(now)
    latest_path = state / LATEST_FILE
    command = details_command(root, state, args, args.network and args.dry_run)
    # When the command leaves the counts no room: `cat` of latest.json, then (state directory from XDG_STATE_HOME)
    # the symbolic form, as scripts/currency_due.py due_file_pointers() does. A dry run writes no file to point at.
    from_xdg = args.state_dir is None and os.path.isabs(os.environ.get("XDG_STATE_HOME") or "")
    candidates = [command] + ([] if args.dry_run else [join_command(["cat", notice_path(latest_path)])]
                              + ([XDG_POINTER] if from_xdg else []))
    # Fail before any fetch when no line can fit, with the longest prefix this run can produce (a --network run whose
    # fetch falls back to the cache says "partial cache").
    summary_line(["nothing new"], "", candidates, "partial cache" if args.network else "cache")
    if args.write_baseline and baseline_path.exists() and not args.force:
        raise UsageError(f"baseline exists: {baseline_path}; pass --force to replace it")
    dispositions = load_dispositions(dispositions_path)
    baseline = None if args.write_baseline else load_baseline(baseline_path)
    codex_binary = None
    if args.codex_bin != "none":
        codex_binary = args.codex_bin or shutil.which("codex")

    fetcher = Fetcher(state, args.network, now_text)
    observed = observe(fetcher, args.claude_channel, codex_binary)
    if baseline is not None:
        check_floors(observed["names"], baseline, observed["key_sources"])
    changelog_body = fetcher.obtain("claude-changelog", CHANGELOG_URL, http_fetch(CHANGELOG_URL))
    if args.write_baseline:
        baseline = build_baseline(observed, fetcher, now_text, args.claude_channel)
    changelog = {"claude": claude_changelog_delta(changelog_body.decode("utf-8", "replace"),
                                                  baseline["versions"]["claude_code"]),
                 "codex": codex_changelog(fetcher, observed["release"], baseline["versions"]["codex"])}
    new, removed, stage_changed = diff_surface(observed["names"], observed["features"], baseline,
                                               observed["key_sources"])
    reviewed = {row["key"] for row in dispositions["rows"]}
    unreviewed = [item["key"] for item in new if item["key"] not in reviewed]
    crossed = cross_check(fetcher, observed) if args.cross_check else None

    release, sdk = observed["release"], observed["sdk"]
    versions = {
        "claude_code": {"watched": observed["watched"], "channel": args.claude_channel,
                        "dist_tags": observed["claude_tags"], "baseline": baseline["versions"]["claude_code"]},
        "claude_agent_sdk": {"version": sdk["version"], "claude_code_version": sdk["claude_code_version"],
                             "matched": sdk["matched"]},
        "codex": {"watched": release["tag"], "published_at": release["published_at"],
                  "dist_tags": observed["codex_tags"], "baseline": baseline["versions"]["codex"]},
        "codex_binary": {"version": observed["codex_binary"], "baseline": baseline["versions"].get("codex_binary")},
    }
    notes = []
    if not sdk["matched"]:
        notes.append(f"no {SDK_PACKAGE} release names Claude Code {observed['watched']}; settings and hooks are read "
                     f"from {sdk['version']} (claudeCodeVersion {sdk['claude_code_version']})")
    npm_codex = observed["codex_tags"].get("latest")
    if version_key(npm_codex) != version_key(release["tag"]):
        notes.append(f"npm {CODEX_PACKAGE} latest {npm_codex} differs from the GitHub stable release {release['tag']}")
    if not release["schema_digest"]:
        notes.append(f"GitHub published no sha256 digest for the {CODEX_SCHEMA_ASSET} asset of {release['tag']}; "
                     f"the schema was read unverified")
    label, data_time = fetcher.cache_use()
    from_cache = sorted(source for source, record in fetcher.records.items()
                        if not record.get("cross_check") and str(record.get("origin")).startswith("cache"))
    if args.network and from_cache:
        notes.append(f"{len(from_cache)} source(s) came from the cache after a failed fetch, so generated_at is the "
                     f"oldest cached fetch time, not the run time (run_at)")
    not_observed = {kind: fetcher.records.get("codex-features-list", {}).get("error", "not observed")
                    for kind in KINDS if kind not in observed["names"]}
    coverage = {
        "mode": "network" if args.network else "offline: read the cached fetches in the state directory",
        "from_cache": from_cache,
        "sources": [fetcher.records[source] for source in sorted(fetcher.records)],
        "kinds_observed": [kind for kind in KINDS if kind in observed["names"]],
        "kinds_not_observed": not_observed,
        "counts": {kind: {"observed": len(observed["names"][kind]) if kind in observed["names"] else None,
                          "baseline": len(baseline["kinds"].get(kind, [])),
                          "new": sum(1 for item in new if item["key"].startswith(kind + ":")),
                          "removed": sum(1 for item in removed if item["key"].startswith(kind + ":"))}
                   for kind in KINDS},
        "key_sources": key_source_coverage(observed["key_sources"], baseline),
        "dispositions_rows": len(dispositions["rows"]),
        "notes": notes,
    }
    counts = ([f"{len(unreviewed)} unreviewed of {len(new)} new"] if new else ["nothing new"])
    if removed:
        counts.append(f"{len(removed)} removed")
    if stage_changed:
        counts.append(f"{len(stage_changed)} stage change" + ("" if len(stage_changed) == 1 else "s"))
    tail = f"(Claude Code {observed['watched']}, Codex {release['tag'].removeprefix('rust-v')})"
    # generated_at is the time of the oldest data the report holds (scripts/currency_due.py ages the report by it):
    # the run's time when every source came from the network, else the oldest cached fetch. run_at is the run's time.
    document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": data_time,
        "run_at": now_text,
        "versions": versions,
        "new": new,
        "removed": removed,
        "stage_changed": stage_changed,
        "changelog": changelog,
        "unreviewed": unreviewed,
        "coverage": coverage,
        "cross_check": crossed,
        "summary_line": summary_line(counts, tail, candidates, label),
    }
    action = "dry run: wrote nothing"
    if not args.dry_run:
        try:
            earlier = read_if_present(latest_path)
            make_private_dirs(state)
            fetcher.commit()
            write_atomic(latest_path, (json.dumps(document, indent=1) + "\n").encode("utf-8"))
        except OSError as error:
            raise InputError(f"write failed: {type(error).__name__}: {error}") from None
        if args.write_baseline:
            # Last, so that no failed write leaves a baseline that this run's report and cache do not match. The report
            # just written was built against the new baseline and says "nothing new": beside the old baseline it would
            # hide every switch that baseline was meant to report, so a failure here puts the earlier report back.
            try:
                write_atomic(baseline_path, (json.dumps(baseline, indent=1) + "\n").encode("utf-8"), mode=0o644,
                             directory_mode=0o755)
            except OSError as error:
                raise InputError(f"write failed: {type(error).__name__}: {error}; the baseline was not replaced and "
                                 f"{restore_report(latest_path, earlier)}") from None
        action = f"wrote {latest_path}" + (f" and {baseline_path}" if args.write_baseline else "")
    return document, action


def read_if_present(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def restore_report(path: Path, earlier: bytes | None) -> str:
    """Put back the report that a failed --write-baseline run replaced, and say so. When it cannot be put back (a full
    filesystem fails a rewrite, not an unlink), or there was none, remove the report of this run instead: it was built
    against the baseline that was not replaced and says "nothing new", so scripts/currency_due.py would read it as a
    fresh report with nothing unreviewed and clear the notice that the earlier report earned. A lost report is an
    incomplete check there. A report that can be neither put back nor removed is named for the operator."""
    failure = None
    if earlier is not None:
        try:
            write_atomic(path, earlier)
            return "the earlier report was restored"
        except OSError as error:
            failure = f"the earlier report could not be restored ({type(error).__name__}: {error})"
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        return (f"{failure} and " if failure else "") + (
            f"the report of this run could not be removed ({type(error).__name__}: {error}); delete {path} by hand: "
            f"it says \"nothing new\" against a baseline that was not replaced")
    return (f"{failure}, so " if failure else "") + "the report of this run was removed"


def render_text(document: dict, action: str) -> str:
    lines = [document["summary_line"]]
    coverage = document["coverage"]
    for kind, count in coverage["counts"].items():
        observed = "not observed" if count["observed"] is None else str(count["observed"])
        lines.append(f"  {kind}: {observed} (baseline {count['baseline']}), {count['new']} new, "
                     f"{count['removed']} removed")
        for source, held in coverage["key_sources"].get(kind, {}).items():
            lines.append(f"    from {source}: {held['observed']} (baseline {held['baseline']}), "
                         f"{held['only_here_count']} only here" + (
                             f": {', '.join(held['only_here'][:12])}" if held["only_here"] else ""))
    unreviewed = set(document["unreviewed"])
    for item in document["new"][:40]:
        lines.append(f"  new: {item['key']}" + (" (unreviewed)" if item["key"] in unreviewed else "") + (
            f" (from {' and '.join(item['sources'])})" if item.get("sources") else ""))
    for item in document["removed"][:40]:
        lines.append(f"  removed: {item['key']}")
    for item in document["stage_changed"]:
        lines.append(f"  stage: {item['key']}: {item['from']} -> {item['to']}")
    claude, codex = document["changelog"]["claude"], document["changelog"]["codex"]
    lines.append(f"  changelog: Claude Code {claude['entries']} entries in {len(claude['versions'])} version(s) newer "
                 f"than {claude['baseline']}; Codex {codex['entries']} entries in {len(codex['releases'])} stable "
                 f"release(s) newer than {codex['baseline']}")
    lines += [f"    {title}" for title in (claude["titles"] + codex["titles"])[:TITLE_LIMIT]]
    lines.append(f"coverage: {coverage['mode']}")
    if document["generated_at"] != document["run_at"]:
        lines.append(f"  data as of {document['generated_at']} (the oldest cached fetch); run at {document['run_at']}")
    for record in coverage["sources"]:
        lines.append(f"  {record['source']}: {record['origin']}" + (
            f", fetched {record['fetched_utc']}" if record.get("fetched_utc") else "") + (
            f", version {record['version']}" if record.get("version") else "") + (
            f", {record['digest_check']}" if record.get("digest_check") else ""))
    for kind, why in coverage["kinds_not_observed"].items():
        lines.append(f"  not observed: {kind}: {why}")
    lines += [f"  note: {note}" for note in coverage["notes"]]
    if document["cross_check"] is not None:
        for label, result in document["cross_check"].items():
            lines.append(f"  cross-check {label}: {result.get('status')}" + (
                f" ({result['error']})" if result.get("error") else ""))
    lines.append(action)
    return "\n".join(lines)


# The paper window. The paper lane trades US equities, whose regular session is 09:30-16:00 America/New_York on weekdays
# (https://www.nyse.com/markets/hours-calendars); the window adds 30 minutes on each side for an entry or a flatten that
# runs a little early or late. A holiday inside it is deferred too: a deferral costs one day, a run that overlaps a paper
# session costs a measurement or a network slot. The Persistent=true catch-up of stack-currency.timer is the case it
# guards: it can start the watch within 15 minutes of WSL starting, which can be during the session.
PAPER_WINDOW_ZONE = "America/New_York"
PAPER_WINDOW_OPENS = 9 * 60            # 09:00, minutes after midnight in PAPER_WINDOW_ZONE
PAPER_WINDOW_CLOSES = 16 * 60 + 30     # 16:30, exclusive


def paper_window_active(now: datetime) -> bool:
    """True from 09:00 to 16:30 America/New_York (the end exclusive) on a weekday. ``now`` must be timezone-aware."""
    local = now.astimezone(ZoneInfo(PAPER_WINDOW_ZONE))
    return local.weekday() < 5 and PAPER_WINDOW_OPENS <= local.hour * 60 + local.minute < PAPER_WINDOW_CLOSES


def clock_now(text: str | None) -> datetime:
    """The --now value as a UTC time (UsageError when it is not YYYY-MM-DDTHH:MM:SSZ), or the clock."""
    if text is None:
        return datetime.now(timezone.utc).replace(microsecond=0)
    if not ISO_UTC.fullmatch(text):
        raise UsageError(f"--now must look like 2026-10-04T00:00:00Z, got {text!r}")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def paper_window_check(args) -> int:
    """The service's ExecCondition: 1 (the unit is skipped, not failed: systemd.service(5), ExecCondition=) inside the
    paper window, 0 outside it, 2 on a usage error. It reads no state and makes no request."""
    try:
        now = clock_now(args.now)
    except UsageError as error:
        print(f"upstream_surface_watch.py: {error}", file=sys.stderr)
        return error.exit_code
    try:
        inside = paper_window_active(now)
    except (ZoneInfoNotFoundError, ValueError) as error:   # no tz database: run the watch rather than never run it
        print(f"upstream_surface_watch.py: cannot tell the paper window ({type(error).__name__}: {error}); not deferring",
              file=sys.stderr)
        return 0
    if inside:
        print(f"upstream_surface_watch.py: {utc_text(now)} is inside the paper window (weekdays 09:00-16:30 "
              f"{PAPER_WINDOW_ZONE}): the watch is deferred to the next run", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="the checkout whose catalogs are read (default: this)")
    parser.add_argument("--state-dir", type=Path,
                        help="cache and latest.json, outside the checkout (default: "
                             "$XDG_STATE_HOME/native-agent-stack/surface-watch, else ~/.local/state/...)")
    parser.add_argument("--baseline", type=Path, help=f"default: <root>/{BASELINE_PATH}")
    parser.add_argument("--dispositions", type=Path, help=f"default: <root>/{DISPOSITIONS_PATH}")
    parser.add_argument("--network", action="store_true",
                        help="fetch the sources (default off: replay the cache in the state directory)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing, not even the cache")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="print the latest.json document")
    output.add_argument("--summary", action="store_true", help="print only the one-line summary")
    parser.add_argument("--write-baseline", action="store_true",
                        help="write the baseline from this run's network fetches (needs --network; refuses to replace one "
                             "without --force)")
    parser.add_argument("--force", action="store_true", help="let --write-baseline replace an existing baseline")
    parser.add_argument("--check-dispositions", action="store_true",
                        help="validate the dispositions catalog (schema, key uniqueness) and exit; no fetch")
    parser.add_argument("--cross-check", action="store_true",
                        help="add report-only comparisons with amitray007/claude-code-schema and chenrui333/codex-docs")
    parser.add_argument("--claude-channel", choices=CHANNELS, default="latest",
                        help="the npm dist-tag of @anthropic-ai/claude-code under watch (default latest)")
    parser.add_argument("--codex-bin", help="the codex executable to probe (default: codex on PATH; none skips it)")
    parser.add_argument("--now", help="evaluate at this UTC time (YYYY-MM-DDTHH:MM:SSZ); default: the clock")
    parser.add_argument("--paper-window-check", action="store_true",
                        help="exit 1 inside the paper window (weekdays 09:00-16:30 America/New_York), else 0; "
                             "the watch service's ExecCondition (no fetch, no state)")
    return parser


def check_dispositions(args) -> int:
    root = args.root.expanduser().resolve()
    path = (args.dispositions or root / DISPOSITIONS_PATH).expanduser().resolve()
    try:
        document = read_json_file(path, "dispositions")
    except InputError as error:
        print(f"upstream_surface_watch.py: {error}", file=sys.stderr)
        return 1
    errors = validate_dispositions(document)
    if errors:
        for error in errors[:50]:
            print(f"upstream_surface_watch.py: {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"upstream_surface_watch.py: ... and {len(errors) - 50} more", file=sys.stderr)
        return 1
    print(f"{path.name}: valid, {len(document['rows'])} rows, {len(DISPOSITIONS)} documented dispositions")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.paper_window_check:
        if args.write_baseline or args.network or args.cross_check or args.check_dispositions:
            parser.error("--paper-window-check is a condition only; drop the other mode options")
        return paper_window_check(args)
    if args.check_dispositions:
        if args.write_baseline or args.network or args.cross_check:
            parser.error("--check-dispositions validates the catalog only; drop the other mode options")
        return check_dispositions(args)
    if args.write_baseline and args.dry_run:
        parser.error("--write-baseline writes the baseline; it cannot be combined with --dry-run")
    if args.write_baseline and not args.network:
        parser.error("--write-baseline builds the baseline from this run's fetches, never from the cache; add --network")
    if args.force and not args.write_baseline:
        parser.error("--force only applies to --write-baseline")
    try:
        document, action = run(args)
    except WatchError as error:
        print(f"upstream_surface_watch.py: {error}", file=sys.stderr)
        return error.exit_code
    if args.json:
        print(json.dumps(document, indent=1))
    elif args.summary:
        print(document["summary_line"])
    elif args.dry_run:
        print(render_text(document, action))
    else:
        print(f"{document['summary_line']} ({action})")  # one line for the journal, as scripts/currency_due.py
    return 0


if __name__ == "__main__":
    sys.exit(main())
