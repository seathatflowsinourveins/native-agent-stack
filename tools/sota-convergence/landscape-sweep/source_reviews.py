#!/usr/bin/env python3
"""Write one upstream-provenance source review per sweep survivor (network: gh api, anonymous Codeberg/Forgejo
REST GETs, and the public Hugging Face Hub API for a model repository; no model calls).

  source_reviews.py --survivors OUT/survivors.json --out evidence/artifacts/<lane> --lane <lane>
                    [--fit-models "Claude Opus 5.5 and GPT-6-Astra"] [--skills-yaml <dir>] > OUT/reviews.json

The shape follows evidence/artifacts/landscape-sweep-20260923/*.json: schema_version, id, kind, evidence_class,
repository, reviewed_commit, readme_path, license, layers, claim, observed, documentation_excerpts. A repository
surviving in several layers gets one review listing every layer. Prints [{repository, path, layers}] (make_result.py
--reviews reads it). A review is named <owner>-<repo>.json, lowercased with every other character run as "-", like
the 2026-09-23 reviews; when two reviews share that name (acme/a-b and acme-a/b, or one skill that survived at two
pins), each gets a suffix of 10 hex characters of the sha256 of its key, so no review overwrites another. A survivor
that cannot be reviewed (gh cannot read it, or a skill survivor's checks below refuse it), or whose file name already
holds a review of another repository, is reported and skipped (exit 1 after the others are written); a skill
survivor's printed list entry is then a stopped entry (below). make_result.py refuses a RESULT.json while any survivor
lacks its review, so a skipped survivor blocks the record until its cause is resolved and this script reruns, or until
the run is recorded as stopped (recipes/saturation-sweep.md section 4). `gh auth status` must already pass.
A Hugging Face model repository (https://huggingface.co/<namespace>/<name>, which a model layer can keep) is reviewed
at the commit of its default revision: the Hub's model-info endpoint /api/models/<repo_id> (the one huggingface_hub's
HfApi.model_info calls) gives the commit, the model card's license and the repository state, and the model card is
read at that commit through the documented "Resolve a file" endpoint /<repo_id>/resolve/<sha>/README.md. Both are
anonymous GETs (no token is read or sent), and the card's YAML metadata block is not excerpted. Its review is named
hf-<namespace>-<name>.json.
A skill survivor of the skills modality (owner/repo@name, a skills-* layer) is reviewed at the SKILL.md that the
manifest's pinned skills CLI installs for `npx skills@1.7.0 add owner/repo --skill <name>`, at the commit the refuters
judged: the survivor's pin, which convert.py copies with the proposal's skill_md_sha256 into survivors.json, and at no
other commit. A skill survivor gets no review, and a stopped entry {repository, layers, status: stopped, pin,
pin_lookup, reason} in the printed list instead, when it names no pin or a pin that is not a 40-hex commit, when its
skill_md_sha256 is null, when gh cannot read the pin or reads it as another commit (pin_lookup failed), or when a later
check refuses it (pin_lookup ok): no valid copy, an ambiguous copy, a copy that has no verdict when its verdict
decides the pick, other SKILL.md bytes than the judged ones, or a git tree that does not cover the bytes read.
make_result.py stops that layer: its RESULT.json cannot complete.
The SKILL.md is found in the git tree at the pin in the CLI's discovery order (cli_skill_dir; vercel-labs/skills v1.7.0
discoverSkills, README "Skill Discovery"): a folder outside the CLI's locations, such as docs/<lang>/skills/<name>, is
never taken. Like the CLI, each candidate SKILL.md is validated before the order applies, and by the CLI's own code:
skill_md.mjs runs parseSkillMd, parseFrontmatter and sanitizeMetadata of vercel-labs/skills v1.7.0 (ported line by
line) with the yaml package skills-yaml.pin.json pins, after checking the installed package's bytes and npm integrity
(skill_md_check). A copy the CLI skips (no name or description, one that is not a string, a YAML parse error) is
recorded with the CLI's own warning, so a valid later copy wins, and a skill whose every copy is invalid is refused.
A copy with no verdict is not guessed at: skill_md.mjs gives none for a line break other than LF or CRLF in the
frontmatter (the yaml package and the CLI's pattern break lines only there, libyaml, which Codex's serde_yaml uses,
also at a lone CR, U+0085, U+2028 and U+2029), none runs without node or a verified yaml install, and each SKILL.md
read must be the regular-file blob the tree lists (tree_file: a symlink, content gh does not return, or bytes that are
not that blob give none). When such a copy's verdict decides which copy the CLI takes, no review is written and the
survivor is stopped (pin_lookup ok). Symlinks change what the CLI walks (location_doubt): it reads a search location
through a symlink at or above it, which the git tree lists as one blob, and a folder whose SKILL.md is a symlink is a
skill folder only when the link's target is a file; plugin manifests behind a symlink, or without verified bytes,
leave the plugin folders unknown. Such a location, reached before the pick is decided, stops the survivor too. Only
two valid same-named folders in the first location that holds a valid one are ambiguous. A folder's name stands for the skill's name (the Agent Skills specification requires them to match,
https://agentskills.io/specification), and a copy whose name, as the CLI matches --skill against it
(getSkillDisplayName: the sanitized name, or the folder's name when that is empty), names another skill is not a copy
(filterSkills). The review records the SKILL.md's path, sha256 and size, the copies skipped on the way, the reader
(skill_md_reader: the yaml package, its integrity and the pin file's sha256), the skill folder's git tree id at the
pin (skill_folder_tree_sha: the id the CLI's lock records as skillFolderHash, verified to cover the SKILL.md and
agents/openai.yaml bytes read), its disable-model-invocation flag as Claude Code reads a boolean field (true, yes, on or
1 in any letter case, https://code.claude.com/docs/en/skills, frontmatter reference) applied to the value as the yaml
package types it, and the implicit-invocation policy Codex reads from the agents/openai.yaml beside it
(openai_yaml_policy, https://developers.openai.com/codex/skills: codex_implicit, null with unverified_reason when the
reader cannot tell), and excerpts the SKILL.md body without its frontmatter. Its repository field is
<full_name>@<name>, the survivor's identity, and it is named <owner>-<repo>-<name>.json.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import posixpath
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_common import slug  # noqa: E402

try:  # PyYAML, when installed, reads agents/openai.yaml (openai_yaml_policy); the repository does not require it
    import yaml
except ImportError:  # the subset reader then decides, or says it cannot
    yaml = None

OWNER_REPO = re.compile(r"[a-z0-9-]+/[a-z0-9._-]+")
HUB = "https://huggingface.co"
CODEBERG = "https://codeberg.org"
CODEBERG_API = f"{CODEBERG}/api/v1/"
CODEBERG_OWNER_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*")
# Forgejo v16.0.5 templates/swagger/v1_json.tmpl; deployed Codeberg responses are checked in recorded fixtures.
FORGEJO_SPEC = "https://code.forgejo.org/forgejo/forgejo/raw/tag/v16.0.5/templates/swagger/v1_json.tmpl"
CODEBERG_LAST_REQUEST = None
CODEBERG_MAX_BODY = 8 * 1024 * 1024
HUB_MODEL = re.compile(r"https://huggingface\.co/([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)/?")
# First path segments that are Hub sections, never a model repository's namespace.
HUB_SECTIONS = {"api", "blog", "buckets", "collections", "containers", "datasets", "docs", "models", "organizations",
                "papers", "settings", "spaces"}
HUB_DEFAULT_REVISION = "main"  # huggingface_hub constants.DEFAULT_REVISION
# huggingface_hub repocard.REGEX_YAML_BLOCK: the card's metadata block, which may follow leading whitespace.
CARD_METADATA = re.compile(r"^(\s*---(?:\r\n|\r|\n))([\S\s]*?)((?:\r\n|\r|\n)---[ \t]*(\r\n|\n|$))")
HEX40, HEX64 = re.compile(r"[0-9a-f]{40}"), re.compile(r"[0-9a-f]{64}")
# A skills-modality survivor: owner/repo@name (schemas/discover-skills.json skill_ref).
SKILL_REF = re.compile(r"([A-Za-z0-9-]+/[A-Za-z0-9._-]+)@([a-z0-9-]+)")
# A simple (optionally quoted) YAML mapping key and its value (the agents/openai.yaml subset reader).
YAML_KEY = re.compile(r"""(?P<key>[A-Za-z_][A-Za-z0-9_-]*|"[A-Za-z_][A-Za-z0-9_-]*"|'[A-Za-z_][A-Za-z0-9_-]*')"""
                      r"[ \t]*:(?:[ \t]+(?P<value>.*))?")
# Claude Code's boolean frontmatter fields accept true, yes, on and 1 (and false, no, off, 0) in any letter case
# (https://code.claude.com/docs/en/skills, frontmatter reference: "Boolean fields accept ...", since v2.1.218).
CLAUDE_TRUE = ("true", "yes", "on", "1")
# Whether the pinned skills CLI takes a SKILL.md is decided by skill_md.mjs, the CLI's own parseSkillMd with the yaml
# package skills-yaml.pin.json pins (skill_md_check). --skills-yaml names the install (else skill_md.mjs reads
# LANDSCAPE_SWEEP_SKILLS_YAML, then the pin's default directory under HOME); a reader that cannot run is recorded once.
SKILL_MD_READER = Path(__file__).resolve().parent / "skill_md.mjs"
SKILLS_YAML_ENV = "LANDSCAPE_SWEEP_SKILLS_YAML"
READER = {"install": None, "failure": None, "record": None}
# Git modes of a regular file; a symlink is 120000 (its blob holds the target's path).
REGULAR_FILE_MODES = ("100644", "100755")
# Codex rust-v0.157.1 (commit 36650394c5b38c2990ccf2a3457165ca3e9d9726) reads agents/openai.yaml with serde_yaml into
# {interface, dependencies, policy: {allow_implicit_invocation: Option<bool>, products}} and ignores the whole file
# when it cannot (codex-rs/ext/skills/src/loader/metadata.rs lines 27-56 and 130-139: "Fail open"), so implicit
# invocation stays allowed (codex-rs/skills/src/model.rs allows_implicit_invocation: unwrap_or(true)). Its lockfile's
# serde_yaml 0.9.34 (tag commit 2009506d33767dfc88e979d6bc0d53d09f941c94, src/de.rs) reads a bool only from a plain
# true/True/TRUE or false/False/FALSE (parse_bool, lines 932-938) and None from an empty or null/Null/NULL/~ plain
# scalar (deserialize_option, lines 1517-1558; parse_null, lines 925-930); a quoted or any other scalar is a type error.
SERDE_YAML_BOOL = {"true": True, "True": True, "TRUE": True, "false": False, "False": False, "FALSE": False}
SERDE_YAML_NULL = ("", "~", "null", "Null", "NULL")
# Codex's structs for the file (metadata.rs lines 27-56): known fields, a repeated one fails deserialization; unknown
# keys are ignored (no deny_unknown_fields).
METADATA_FIELDS, POLICY_FIELDS = ("interface", "dependencies", "policy"), ("allow_implicit_invocation", "products")
YAML_NULL_TAG, YAML_BOOL_TAG = "tag:yaml.org,2002:null", "tag:yaml.org,2002:bool"
CODEX_IGNORES = "Codex cannot deserialize the file and ignores it, so implicit invocation stays allowed"
# Without PyYAML, agents/openai.yaml is read as the plain block-mapping subset only: block mappings with plain or
# quoted identifier keys, block lists, one-line plain or quoted scalars, comments and one leading "---". A value
# starting with one of these indicators is outside it, and so is anything the subset reader does not recognize.
SUBSET_INDICATORS = {"{": "a flow mapping", "[": "a flow sequence", "&": "an anchor", "*": "an alias", "!": "a tag",
                     "|": "a block scalar", ">": "a block scalar", "%": "a directive", "?": "a complex key",
                     "@": "a reserved indicator (@)", "`": "a reserved indicator (`)"}
# vercel-labs/skills v1.7.0 src/frontmatter.ts parseFrontmatter's pattern: the frontmatter block starts the file. The
# review excerpts the body after it; what the frontmatter says is skill_md.mjs's to read.
SKILL_MD_FRONTMATTER = re.compile(r"---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)\Z")
# YAML 1.2's double-quoted escapes (c-ns-esc-char) as libyaml defines them: unsafe-libyaml 0.2.11, the libyaml port
# serde_yaml 0.9.34 parses with (tag commit a7b8d1fbd93aefbca3003dcb5fcc6a9c2297e968, src/scanner.rs lines 2195-2317:
# any other escape is "found unknown escape character"). \x, \u and \U take exactly 2, 4 and 8 hex digits (scanner.rs
# line 2341), and a surrogate or a code point beyond U+10FFFF is refused (lines 2355-2361).
YAML_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
                "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": chr(0x2028),
                "P": chr(0x2029)}
YAML_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
SURROGATE = re.compile("[\ud800-\udfff]")
# libyaml's reader accepts only these characters (unsafe-libyaml 0.2.11 src/reader.rs lines 381-395: anything else is
# "control characters are not allowed"), and it breaks lines at LF, CRLF, a lone CR, U+0085, U+2028 and U+2029
# (src/macros.rs IS_BREAK_AT, lines 253-265): openai_yaml_doubt leaves a file with any other character, or with a
# line break other than LF and CRLF, unverified.
LIBYAML_PRINTABLE = re.compile("[^\t\n\r\x20-\x7e\x85\xa0-%s%s-%s%s-%s]" % tuple(
    map(chr, (0xD7FF, 0xE000, 0xFFFD, 0x10000, 0x10FFFF))))
OTHER_LINE_BREAK = re.compile("\r(?!\n)|[\x85%s%s]" % (chr(0x2028), chr(0x2029)))
# The skills CLI adoption/skills/manifest.json pins: vercel-labs/skills v1.7.0 (tag commit
# 7407f3893ad4dceab546ac002c3ef806e4000c73). src/skills.ts SKIP_DIRS (line 10), AGENT_PROJECT_SKILL_DIRS (lines 12-43)
# and discoverSkills (lines 180-329); src/constants.ts DEFAULT_SKILL_CONTAINER_DEPTH; src/plugin-manifest.ts
# getPluginSkillPaths. Its README documents the rule ("Skill Discovery", README.md lines 412-483, and "Plugin Manifest
# Discovery", lines 485-505); where the README's list differs from the code (it names 31 folders, such as data/skills/
# and agent/skills/, that discoverSkills never searches, and omits 7 that it does: .cline, .codex, .factory, .github,
# .kilo, .kilocode and .opencode skills), this follows the code. src/blob.ts PRIORITY_PREFIXES (lines 306-342), the
# fast path for vercel, vercel-labs, heygen-com and remotion-dev repositories, lists the same locations as the code.
CLI_SKIP_DIRS = frozenset({"node_modules", ".git", "dist", "build", "__pycache__"})
CLI_AGENT_SKILL_DIRS = (
    ".agents/skills", ".claude/skills", ".cline/skills", ".codebuddy/skills", ".codex/skills", ".commandcode/skills",
    ".continue/skills", ".factory/skills", ".github/skills", ".goose/skills", ".grok/skills", ".iflow/skills",
    ".junie/skills", ".kilo/skills", ".kilocode/skills", ".kimchi/skills", ".kiro/skills", ".minimax/skills",
    ".mux/skills", ".neovate/skills", ".opencode/skills", ".openhands/skills", ".pi/skills", ".posit/assistant/skills",
    ".qoder/skills", ".roo/skills", ".trae/skills", ".windsurf/skills", ".zcode/skills", ".zencoder/skills")
CLI_CONTAINERS = ("skills", "skills/.curated", "skills/.experimental", "skills/.system", *CLI_AGENT_SKILL_DIRS)
CLI_CONTAINER_DEPTH = 3  # DEFAULT_SKILL_CONTAINER_DEPTH
CLI_FALLBACK_DEPTH = 5  # findSkillDirs(dir, depth = 0, maxDepth = 5)
PLUGIN_MANIFESTS = (".claude-plugin/marketplace.json", ".claude-plugin/plugin.json")
MISSING = object()


class GhError(RuntimeError):
    pass


class HubError(GhError):
    """The Hugging Face Hub could not answer (reported and skipped like a repository gh cannot read)."""


class CodebergError(GhError):
    """An anonymous Codeberg request failed; only explicit 404s may be optional evidence."""

    def __init__(self, message, *, status=None):
        super().__init__(message)
        self.status = status


def codeberg_url(url: str) -> str:
    """Check the origin before any request or redirect, including explicit ports and userinfo."""
    try:
        parsed = urllib.parse.urlsplit(url)
        valid = (parsed.scheme == "https" and parsed.hostname == "codeberg.org" and parsed.port in (None, 443)
                 and parsed.username is None and parsed.password is None and not parsed.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise CodebergError("only anonymous HTTPS requests to codeberg.org:443 are allowed")
    return url


def codeberg_wait():
    """At most one request start per second, including redirected requests; no automatic retries."""
    global CODEBERG_LAST_REQUEST
    if CODEBERG_LAST_REQUEST is not None:
        time.sleep(max(0, 1.0 - (time.monotonic() - CODEBERG_LAST_REQUEST)))
    CODEBERG_LAST_REQUEST = time.monotonic()


class CodebergRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        codeberg_url(newurl)
        codeberg_wait()
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def codeberg_get(path: str, *, response_headers=None):
    """Anonymous Forgejo REST v1 JSON GET; preserve only pagination headers when requested."""
    url = codeberg_url(path if "://" in path else CODEBERG_API + path.lstrip("/"))
    if not urllib.parse.urlsplit(url).path.startswith("/api/v1/"):
        raise CodebergError("Codeberg JSON requests must stay under /api/v1/")
    request = urllib.request.Request(url, headers={"User-Agent": "native-agent-stack source_reviews.py",
                                                  "Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), CodebergRedirect())
    codeberg_wait()
    try:
        with opener.open(request, timeout=60) as response:
            codeberg_url(response.geturl())
            body = response.read(CODEBERG_MAX_BODY + 1)
            if len(body) > CODEBERG_MAX_BODY:
                raise CodebergError("Codeberg JSON response exceeds the 8 MiB evidence bound")
            if response_headers is not None:
                response_headers.update({key: response.headers.get(key, "") for key in ("Link", "x-total-count")})
        return json.loads(body)
    except urllib.error.HTTPError as error:
        retry = error.headers.get("Retry-After") if error.headers else None
        raise CodebergError(f"Codeberg GET returned HTTP {error.code}"
                            + (f" (Retry-After: {retry})" if retry else ""), status=error.code) from None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
        raise CodebergError(f"Codeberg GET failed: {type(error).__name__}") from None


def codeberg_pages(path: str, *, limit=50, max_pages=20) -> list:
    """Follow same-origin Link pagination; refuse a capped listing rather than silently truncate it."""
    if not 1 <= limit <= 50 or max_pages < 1:
        raise ValueError("Codeberg pagination requires limit 1..50 and a positive page bound")
    url = CODEBERG_API + path.lstrip("/")
    separator = "&" if "?" in url else "?"
    current = f"{url}{separator}page=1&limit={limit}"
    rows, seen = [], set()
    for page in range(1, max_pages + 1):
        if current in seen:
            raise CodebergError("Codeberg pagination repeated a page")
        seen.add(current)
        headers = {}
        items = codeberg_get(current, response_headers=headers)
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise CodebergError("Codeberg collection is not a list of JSON objects")
        rows.extend(items)
        link, next_url = headers.get("Link", ""), None
        for section in urllib.request.parse_http_list(link):
            if re.search(r';\s*rel=(?:"[^"]*\bnext\b[^"]*"|next)(?:\s*;|\s*$)', section):
                match = re.match(r"\s*<([^>]+)>", section)
                if not match:
                    raise CodebergError("Codeberg pagination has an invalid next link")
                next_url = codeberg_url(urllib.parse.urljoin(current, match.group(1)))
        if next_url:
            current = next_url
        elif link or len(items) < limit:
            return rows
        else:
            current = f"{url}{separator}page={page + 1}&limit={limit}"
    raise CodebergError("Codeberg pagination exceeds the evidence page bound")


def codeberg_repo(repository: str) -> str | None:
    parsed = urllib.parse.urlsplit(str(repository or "").strip())
    if parsed.hostname != "codeberg.org":
        return None
    codeberg_url(parsed.geturl())
    full = parsed.path.strip("/")
    if parsed.query or not CODEBERG_OWNER_REPO.fullmatch(full):
        raise CodebergError("Codeberg review requires an owner/repository URL")
    return full


def codeberg_content(full: str, path: str, commit: str) -> dict:
    """Read a regular-file blob at the resolved commit, checking the API's blob identity."""
    data = codeberg_get(f"repos/{full}/contents/{urllib.parse.quote(path, safe='/')}?ref={commit}")
    if not isinstance(data, dict) or data.get("type") != "file" or data.get("encoding") != "base64":
        raise CodebergError("Codeberg contents did not return a regular base64 file")
    try:
        raw = base64.b64decode(data["content"], validate=True)
    except (KeyError, ValueError, TypeError):
        raise CodebergError("Codeberg file content is not valid base64") from None
    if data.get("path") != path or data.get("sha") != git_blob_id(raw):
        raise CodebergError("Codeberg file content does not match the pinned path/blob")
    return {**data, "text": raw.decode("utf-8", "replace"), "sha256": hashlib.sha256(raw).hexdigest()}


def codeberg_release(data: dict) -> dict:
    return {key: data.get(key) for key in ("tag_name", "name", "target_commitish", "created_at", "published_at")} | {
        "assets": [{"name": item.get("name"), "url": item.get("browser_download_url"), "size": item.get("size")}
                   for item in data.get("assets") or []]}


def codeberg_review(full: str, layers: list, lane: str, fit_models: str) -> dict:
    meta = codeberg_get(f"repos/{full}")
    full, branch = meta["full_name"], meta["default_branch"]
    if not CODEBERG_OWNER_REPO.fullmatch(full):
        raise CodebergError("Codeberg reported an invalid repository identity")
    head = codeberg_get(f"repos/{full}/branches/{urllib.parse.quote(branch, safe='')}")["commit"]
    commit = head["id"]
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise CodebergError("Codeberg reported no SHA-1 default-branch commit")
    excerpts, readme_path, license_id, license_source = [], None, "NOASSERTION", None
    try:
        readme = codeberg_content(full, "README.md", commit)
        readme_path = readme["path"]
        excerpts = excerpts_from(readme["text"], f"{readme_path}@{commit}")
    except CodebergError as error:
        if error.status != 404:
            raise
    # Forgejo's Repository schema has no license field or repository-license route. Cargo's declared SPDX
    # expression is source evidence, not an inferred classification of arbitrary LICENSE text.
    try:
        cargo = codeberg_content(full, "Cargo.toml", commit)
        package = tomllib.loads(cargo["text"]).get("package", {})
        declared = package.get("license")
        if declared == {"workspace": True}:
            declared = tomllib.loads(cargo["text"]).get("workspace", {}).get("package", {}).get("license")
        if isinstance(declared, str) and declared.strip():
            license_id = declared.strip()
            license_source = {"path": "Cargo.toml", "sha256": cargo["sha256"], "commit": commit}
    except CodebergError as error:
        if error.status != 404:
            raise
    try:
        latest = codeberg_get(f"repos/{full}/releases/latest")
        if not isinstance(latest, dict):
            raise CodebergError("Codeberg latest release is not a JSON object")
        latest = codeberg_release(latest)
    except CodebergError as error:
        if error.status != 404:
            raise
        latest = None
    releases = [codeberg_release(item) for item in codeberg_pages(f"repos/{full}/releases")]
    tags = [{"name": item.get("name"), "commit": (item.get("commit") or {}).get("sha")}
            for item in codeberg_pages(f"repos/{full}/tags")]
    description = (meta.get("description") or "").strip()
    return {"schema_version": 1, "id": f"source-review-codeberg-{review_name(full)}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"{CODEBERG}/{full}", "reviewed_commit": commit,
            "readme_path": readme_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source and documentation review of {full} at commit {commit} (license {license_id}), read from "
                      f"{readme_path or 'the repository metadata'} at that commit"
                      + (f". Repository description: \"{description}\"." if description else ".")
                      + f" Survived the {lane} facts refuter and both fit refuters ({fit_models}); "
                        "no native install, run or comparison with a winner."),
            "observed": {"stars": meta.get("stars_count"), "pushed_at": None, "updated_at": meta.get("updated_at"),
                         "head_committed_at": head.get("timestamp"), "archived": meta.get("archived"),
                         "default_branch": branch, "license_source": license_source, "latest_release": latest,
                         "releases": releases, "tags": tags, "api_spec": FORGEJO_SPEC},
            "documentation_excerpts": excerpts}


def gh(path: str) -> dict:
    done = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise GhError(f"gh api {path}: {done.stderr.strip()[:200]}")
    return json.loads(done.stdout)


def hub_get(path: str, text: bool = False):
    """An anonymous GET of a public Hugging Face Hub path: parsed JSON, or the body as text."""
    request = urllib.request.Request(f"{HUB}/{path}", headers={"User-Agent": "native-agent-stack source_reviews.py"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        return body.decode("utf-8", "replace") if text else json.loads(body)
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as error:
        # http.client.HTTPException (IncompleteRead, BadStatusLine) is not an OSError; without it one truncated
        # response would abort the whole run before any review is written.
        raise HubError(f"GET {HUB}/{path}: {error!r}") from None


def hub_model(repository: str) -> str | None:
    """<namespace>/<name> of a Hugging Face model repository URL, else None."""
    match = HUB_MODEL.fullmatch(str(repository or "").strip())
    if match and match.group(1).split("/", 1)[0].lower() not in HUB_SECTIONS:
        return match.group(1)
    return None


def repository_key(repository: str) -> str:
    """One key per repository: the lowercased owner/repo for GitHub (sweep_common.slug) and hf:<namespace>/<name>
    for a Hugging Face model, or codeberg:<owner>/<repo>, so repository URLs with and without a trailing slash get
    one review. A skill ref
    (owner/repo@name) is its own lowercased key: slug leaves it whole."""
    repo_id = hub_model(repository)
    try:
        forgejo = codeberg_repo(repository)
    except (CodebergError, ValueError):
        # Identity grouping must not abort the batch. review() reports unsafe URLs per repository,
        # so valid survivors still get their source reviews even beside a malformed Codeberg URL.
        forgejo = None
    return f"hf:{repo_id.lower()}" if repo_id else f"codeberg:{forgejo.lower()}" if forgejo else slug(repository)


def excerpts_from(text: str, source: str) -> list:
    """The first three prose paragraphs of a README (badges, tables and HTML skipped), each cut at 500 characters."""
    paragraphs = [re.sub(r"\s+", " ", part).strip() for part in re.split(r"\n\s*\n", text)]
    paragraphs = [part for part in paragraphs if len(part) > 60 and not part.startswith(("<", "[![", "![", "|"))]
    return [{"source": source, "text": part[:500]} for part in paragraphs[:3]]


def hub_license(meta: dict) -> str:
    """The model card's license (cardData.license, else a license:<id> tag); "other" keeps the card's license_name."""
    card = meta.get("cardData") if isinstance(meta.get("cardData"), dict) else {}
    value = card.get("license")
    if isinstance(value, list):
        value = " OR ".join(str(item) for item in value if item)
    if not value:
        tags = [tag[len("license:"):] for tag in meta.get("tags") or [] if isinstance(tag, str)
                and tag.startswith("license:")]
        value = tags[0] if tags else "NOASSERTION"
    if value == "other" and isinstance(card.get("license_name"), str) and card["license_name"]:
        value = f"other ({card['license_name']})"
    return str(value)


def hub_review(repo_id: str, layers: list, lane: str, fit_models: str) -> dict:
    meta = hub_get(f"api/models/{urllib.parse.quote(repo_id, safe='/')}")
    if not isinstance(meta, dict):
        raise HubError(f"{HUB}/{repo_id}: the Hub's model info is not a JSON object")
    full, commit = meta.get("id") or repo_id, meta.get("sha")
    if not (isinstance(full, str) and isinstance(commit, str) and HEX40.fullmatch(commit)):
        raise HubError(f"{HUB}/{repo_id}: the Hub reported no model id and commit")
    license_id = hub_license(meta)
    excerpts, readme_path = [], None
    try:
        card = hub_get(f"{urllib.parse.quote(full, safe='/')}/resolve/{commit}/README.md", text=True)
        readme_path = "README.md"
        metadata = CARD_METADATA.search(card)  # the model card's YAML metadata block
        excerpts = excerpts_from(card[metadata.end():] if metadata else card, f"{readme_path}@{commit}")
    except HubError:
        pass
    return {"schema_version": 1, "id": f"source-review-hf-{review_name(full)}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"{HUB}/{full}", "reviewed_commit": commit,
            "readme_path": readme_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source and documentation review of the Hugging Face model repository {full} at commit {commit} "
                      f"(license {license_id}, as its model card declares it), read from "
                      f"{readme_path or 'the repository metadata'} at that commit. Survived the {lane} facts refuter "
                      f"and both fit refuters ({fit_models}); no native install, run or comparison with a winner."),
            "observed": {"likes": meta.get("likes"), "last_modified": meta.get("lastModified"),
                         "gated": meta.get("gated"), "disabled": meta.get("disabled"),
                         "default_branch": HUB_DEFAULT_REVISION},
            "documentation_excerpts": excerpts}


def review_name(full_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", full_name.lower()).strip("-")


def unique_stems(names: dict) -> dict:
    """owner/repo -> file stem: its readable name, or, for a name two repositories share, that name plus 10 hex
    characters of the sha256 of the owner/repo."""
    groups: dict[str, list] = {}
    for key, name in names.items():
        groups.setdefault(name, []).append(key)
    stems = {key: name if len(groups[name]) == 1 else f"{name}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}"
             for key, name in names.items()}
    if len(set(stems.values())) != len(stems):
        raise ValueError(f"review file names still collide: {sorted(stems.values())}")
    return stems


# --------------------------------------------------------------------------- YAML scalars (the openai.yaml subset reader)


def strip_yaml_comment(line: str) -> str:
    """The line without its YAML comment: a # at the line start or after whitespace, outside quotes."""
    index, quote = 0, None
    while index < len(line):
        char = line[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if quote and char == quote:
            if quote == "'" and line[index + 1:index + 2] == "'":  # '' is a quote inside a single-quoted scalar
                index += 2
                continue
            quote = None
        elif not quote and char in "'\"" and (index == 0 or line[index - 1] in " \t{[,:"):
            quote = char
        elif not quote and char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index].rstrip()
        index += 1
    return line.rstrip()


def yaml_scalar(text: str) -> tuple[str, bool]:
    """(value, quoted) of a one-line YAML scalar without its comment: a quoted scalar's content, or the plain text."""
    text = strip_yaml_comment(text).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        body = text[1:-1]
        return (body.replace("''", "'") if text[0] == "'" else body.replace('\\"', '"').replace("\\\\", "\\")), True
    return text, False


def double_quoted_value(body: str) -> tuple[str | None, str | None]:
    """(value, None) of the text between the quotes of a one-line double-quoted scalar, or (None, why not): an escape
    outside YAML_ESCAPES and YAML_HEX_ESCAPES, a hex escape without its digits, a surrogate or a code point beyond
    U+10FFFF, all of which libyaml refuses."""
    out, index = [], 0
    while index < len(body):
        if body[index] != "\\":
            out.append(body[index])
            index += 1
            continue
        code = body[index + 1:index + 2]
        if code in YAML_ESCAPES and code:
            out.append(YAML_ESCAPES[code])
            index += 2
            continue
        digits = body[index + 2:index + 2 + YAML_HEX_ESCAPES.get(code, 0)]
        escape = body[index:index + 2 + len(digits)]
        if code in YAML_HEX_ESCAPES and len(digits) == YAML_HEX_ESCAPES[code] and HEX_DIGITS.issuperset(digits):
            point = int(digits, 16)
            if point <= 0x10FFFF and not 0xD800 <= point <= 0xDFFF:
                out.append(chr(point))
                index += 2 + len(digits)
                continue
            return None, (f"a double-quoted scalar with the escape {escape}, "
                          f"{'a surrogate' if point <= 0x10FFFF else 'beyond U+10FFFF'},")
        return None, f"a double-quoted scalar with the escape {escape}, which YAML 1.2 does not define,"
    return "".join(out), None


def quoted_scalar(text: str) -> tuple[str | None, str | None]:
    """(value, None) of a quoted scalar that is the whole of text (its comment stripped), or (None, why not): it must
    close on the line with nothing after it, and a double-quoted one must use YAML's escapes (double_quoted_value)."""
    end = quoted_end(text)
    if end is None:
        return None, "a quoted scalar that continues on the next line"
    if text[end:].strip():
        return None, "text after a quoted scalar"
    if text[0] == "'":
        return text[1:end - 1].replace("''", "'"), None
    return double_quoted_value(text[1:end - 1])


def claude_true(value) -> bool:
    """A Claude Code boolean frontmatter field that is true: true, yes, on or 1 in any letter case (CLAUDE_TRUE), given
    the value as the yaml package types it (skill_md_check): a boolean, a string or a number."""
    if isinstance(value, bool):
        return value
    return str(value if value is not None else "").strip().lower() in CLAUDE_TRUE


# --------------------------------------------------------------------------- SKILL.md as the skills CLI parses it


class SkillMdUnverified(GhError):
    """No verdict stands behind this SKILL.md copy (skill_md_check), so no review rests on that copy's place in the
    CLI's discovery order."""


class LocationUnverified(SkillMdUnverified):
    """What the CLI finds in a search location cannot be read from the git tree (location_doubt, plugin_manifests),
    and the location comes before the pick is decided."""


def skill_md_check(raw: bytes, path: str = "SKILL.md") -> dict:
    """skill_md.mjs's result for these SKILL.md bytes at this path in the repository: the pinned skills CLI's own
    parseSkillMd (vercel-labs/skills v1.7.0 src/skills.ts lines 80-133, with src/frontmatter.ts and src/sanitize.ts,
    ported line by line) run with the yaml package skills-yaml.pin.json pins, whose installed bytes it verifies first.
    {"verdict": "take", "name" and "description" as sanitizeMetadata records them, "display_name" (getSkillDisplayName,
    null for a root SKILL.md without a name), "license" and "disable_model_invocation" as the yaml package types them}
    or {"verdict": "skip", "reason": the warning the CLI prints}. Raises SkillMdUnverified when skill_md.mjs gives no
    verdict (a line break other than LF or CRLF in the frontmatter) and whenever it cannot run here: node is missing, or
    the yaml install is absent (not_installed) or not the pinned bytes (hash_mismatch, load_error). Such a failure is
    kept for the rest of the process, so every later copy is unverified too and nothing is guessed."""
    if READER["failure"]:
        raise SkillMdUnverified(READER["failure"])
    node = shutil.which("node")
    if not node:
        READER["failure"] = "node is not installed, so skill_md.mjs, the pinned skills CLI's parser, cannot run"
        raise SkillMdUnverified(READER["failure"])
    request = json.dumps({"items": [{"id": "0", "path": path, "base64": base64.b64encode(raw).decode()}]})
    command = [node, str(SKILL_MD_READER), *(["--install", READER["install"]] if READER["install"] else [])]
    try:
        done = subprocess.run(command, input=request, capture_output=True, text=True, timeout=120, check=False)
        response = json.loads(done.stdout)
        reader, results = response["reader"], response["results"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        raise SkillMdUnverified(f"skill_md.mjs gave no answer ({type(error).__name__})") from None
    if not isinstance(reader, dict) or reader.get("ok") is not True:
        why = reader.get("reason") if isinstance(reader, dict) else None
        READER["failure"] = (f"the yaml install skill_md.mjs verifies is {why} (skills-yaml.pin.json names the package, "
                             f"its files' sha256 and the install command; the install is read from --skills-yaml, "
                             f"{SKILLS_YAML_ENV} or the pin's default directory under HOME)")
        raise SkillMdUnverified(READER["failure"])
    READER["record"] = {key: reader.get(key) for key in ("package", "integrity", "pin_sha256")}
    result = results[0] if isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict) else {}
    if result.get("verdict") in ("take", "skip"):
        return result
    raise SkillMdUnverified(result.get("reason") or "skill_md.mjs gave no verdict")


# --------------------------------------------------------------------------- agents/openai.yaml as Codex reads it


class CodexIgnores(Exception):
    """serde_yaml cannot deserialize agents/openai.yaml into Codex's SkillMetadataFile, so Codex ignores the file."""

    def __init__(self, message: str, value: str | None = None):
        super().__init__(message)
        self.value = value


def openai_yaml_doubt(text: str) -> str | None:
    """Why neither reader answers for this agents/openai.yaml text, or None: a character libyaml refuses (outside
    LIBYAML_PRINTABLE) or a line break other than LF and CRLF (OTHER_LINE_BREAK), each at its line. Checked before
    either reader runs: libyaml's own reader refuses the first, and the subset reader splits lines only at LF and CRLF,
    so neither is decided by a reader that does not parse it as Codex does."""
    for pattern, what in ((LIBYAML_PRINTABLE, "a character libyaml refuses ({})"),
                          (OTHER_LINE_BREAK, "a line break other than LF or CRLF ({})")):
        found = pattern.search(text)
        if found:
            line = len(re.split(r"\r\n|\n", text[:found.start()]))
            return (f"line {line}: {what.format(f'U+{ord(found.group()[0]):04X}')}, so how Codex reads implicit "
                    "invocation is unverified")
    return None


def openai_yaml_policy(data) -> tuple[bool | None, str | None, str]:
    """(codex_implicit, the policy.allow_implicit_invocation value as written or None, how Codex reads it) for an
    agents/openai.yaml (bytes, or text), as Codex rust-v0.157.1 reads it with serde_yaml 0.9.34 (see SERDE_YAML_BOOL):
    false only for a plain false; true for a missing or null value, and for a file serde_yaml cannot deserialize, which
    Codex ignores; None when the reader cannot tell, with the reason in the note ("unverified"). Bytes that are not
    UTF-8 and what openai_yaml_doubt names are unverified before any reader runs. Then, with PyYAML installed its
    composer reads the file (pyyaml_policy); without it only the plain block-mapping subset is read (subset_policy).
    Type errors in the file's other fields, which also make Codex ignore it, are not checked."""
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError as error:
            return None, None, (f"byte {error.start} is not UTF-8, and how Codex reads such a file is unverified")
    doubt = openai_yaml_doubt(data)
    if doubt:
        return None, None, doubt
    return pyyaml_policy(data) if yaml is not None else subset_policy(data)


def openai_yaml_reader() -> str:
    """Which reader openai_yaml_policy uses here, as the review records it."""
    if yaml is None:
        return "subset reader (PyYAML is not installed)"
    loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
    return f"PyYAML {getattr(yaml, '__version__', '?')} compose_all with {loader.__name__}"


def pyyaml_policy(text: str) -> tuple[bool | None, str | None, str]:
    """openai_yaml_policy with PyYAML: yaml.compose_all builds the node tree (anchors and aliases resolved, every
    duplicate key and each scalar's style kept; the libyaml CSafeLoader when present, the grammar serde_yaml's
    unsafe-libyaml follows), and serde_yaml's rules are applied to it. Not safe_load: its YAML 1.1 constructor would
    read yes/no/on/off as booleans and drop the scalar's style, and serde_yaml reads neither so."""
    loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
    try:
        documents = list(yaml.compose_all(text, Loader=loader))
    except (yaml.YAMLError, ValueError) as error:  # ValueError: the pure-Python scanner's chr() beyond U+10FFFF
        first = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
        return None, None, (f"PyYAML cannot parse the file ({first}): whether serde_yaml can, and so Codex's "
                            "implicit invocation, is unverified")
    if any(SURROGATE.search(value) for value in scalar_values(documents)):  # only an escape yields one
        return None, None, ("PyYAML's pure-Python scanner took an escaped surrogate, which libyaml refuses: whether "
                            "serde_yaml can read the file, and so Codex's implicit invocation, is unverified")
    try:
        if not documents:
            raise CodexIgnores("the file holds no YAML document")  # serde_yaml: EndOfStream
        if len(documents) > 1:
            raise CodexIgnores(f"the file holds {len(documents)} YAML documents, which serde_yaml refuses")
        policy = struct_fields(documents[0], METADATA_FIELDS, "the document").get("policy")
        if policy is None:
            return True, None, "no policy mapping: Codex defaults allow_implicit_invocation to true"
        if serde_none(policy, "policy"):
            return True, None, "policy is null: Codex defaults allow_implicit_invocation to true"
        node = struct_fields(policy, POLICY_FIELDS, "policy").get("allow_implicit_invocation")
        if node is None:
            return True, None, "no policy.allow_implicit_invocation: Codex defaults it to true"
        if not isinstance(node, yaml.ScalarNode):
            raise CodexIgnores("allow_implicit_invocation holds a mapping or list")
        if serde_none(node, "allow_implicit_invocation"):
            return True, node.value or None, "policy.allow_implicit_invocation is null: Codex defaults it to true"
        value = serde_bool(node)
        if value is None:
            raise CodexIgnores(f"allow_implicit_invocation {node.value!r} is not a YAML boolean serde_yaml reads (a "
                               "plain true or false)", node.value)
        return value, node.value, f"policy.allow_implicit_invocation: {node.value}"
    except CodexIgnores as why:
        return True, why.value, f"{why}: {CODEX_IGNORES}"


def scalar_values(nodes):
    """The value of every scalar node in the composed trees, each node once (an alias repeats a node)."""
    stack, seen = list(nodes), set()
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, yaml.ScalarNode):
            yield node.value
        elif isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
        elif isinstance(node, yaml.MappingNode):
            stack.extend(item for pair in node.value for item in pair)


def plain_scalar(node) -> bool:
    """A plain (unquoted, not block) scalar node: PyYAML's pure loader gives its style as None, CSafeLoader as ""."""
    return isinstance(node, yaml.ScalarNode) and node.style in (None, "")


def struct_fields(node, fields, what: str) -> dict:
    """{field: value node} of a mapping that serde_yaml deserializes into a struct with these fields: unknown keys are
    ignored, as Codex's structs do not deny them, and an empty plain scalar is an empty map (de.rs deserialize_map,
    lines 1660-1688). Raises CodexIgnores where serde_yaml fails: not a mapping, a key that is not a scalar, a field
    given twice."""
    if plain_scalar(node) and node.value == "":
        return {}
    if not isinstance(node, yaml.MappingNode):
        raise CodexIgnores(f"{what} is not a mapping")
    out = {}
    for key, value in node.value:
        if not isinstance(key, yaml.ScalarNode):
            raise CodexIgnores(f"{what} has a key that is not a scalar")
        if key.value in fields:
            if key.value in out:
                raise CodexIgnores(f"{key.value} appears twice in {what}")
            out[key.value] = value
    return out


def serde_none(node, what: str) -> bool:
    """Whether serde_yaml's deserialize_option (de.rs lines 1517-1558) reads the node as None: a plain scalar that is
    empty or null/Null/NULL/~ and carries no other tag. A plain scalar tagged !!null that is none of those is an
    error (CodexIgnores)."""
    if not plain_scalar(node):
        return False
    if node.tag == YAML_NULL_TAG and node.value not in SERDE_YAML_NULL:
        raise CodexIgnores(f"{what} is tagged !!null but holds {node.value!r}", node.value)
    return node.tag == YAML_NULL_TAG  # an untagged empty or null-like plain scalar resolves to the null tag


def serde_bool(node) -> bool | None:
    """serde_yaml's deserialize_bool on a scalar node (de.rs lines 1266-1290 and 1149-1158): a plain scalar, whatever
    its tag, or a literal block scalar tagged !!bool, whose text is a plain true or false spelling; else None."""
    if plain_scalar(node) or (node.style == "|" and node.tag == YAML_BOOL_TAG):
        return SERDE_YAML_BOOL.get(node.value)
    return None


def quoted_end(text: str) -> int | None:
    """The index just past the quoted scalar that starts text, or None when it does not close on this line."""
    quote, index = text[0], 1
    while index < len(text):
        if quote == '"' and text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            if quote == "'" and text[index + 1:index + 2] == "'":  # '' is a quote inside a single-quoted scalar
                index += 2
                continue
            return index + 1
        index += 1
    return None


def subset_value_problem(value: str) -> str | None:
    """Why a one-line value is outside the plain block-mapping subset, or None. A quoted scalar must close on its line
    with nothing after it, and a double-quoted one must use only the escapes libyaml defines (YAML_ESCAPES, no
    surrogate): the reader does not decide how serde_yaml, which scans with libyaml's rules, reads any other."""
    if not value:
        return None
    if value[0] in "'\"":
        return quoted_scalar(value)[1]
    if value[0] in SUBSET_INDICATORS:
        return SUBSET_INDICATORS[value[0]]
    if value == "-" or value.startswith(("- ", "-\t")):
        return "a list entry after a key"
    if ": " in value or ":\t" in value or value.endswith(":"):
        return "a plain scalar holding ': '"
    return None


def subset_layout_problem(rows) -> tuple[int, str] | None:
    """(line, why) of the first line whose indentation the subset reader does not follow, else None. rows are the
    content lines as (line, indent, text stripped). Each open block sits at one indentation: a key without a value
    opens a deeper block, or a list at its own indentation; a list entry holding a key opens a mapping at its content's
    column; keys and list entries do not mix at one level except for such a list."""
    levels, last, opener = [], {}, None  # open indentations; indent -> state of its last line; what the last line opens
    for number, indent, text in rows:
        entry = text == "-" or text.startswith(("- ", "-\t"))
        if not levels:
            if indent:
                return number, "an indented first line"
            levels.append(0)
        elif indent > levels[-1]:
            if opener is None or indent <= opener:
                return number, "an indented line that no key or list entry without a value opens"
            if levels[-1] in last:
                last[levels[-1]]["open"] = False  # the deeper block is that key's value
            levels.append(indent)
        else:
            while indent < levels[-1]:
                last.pop(levels.pop(), None)
            if indent != levels[-1]:
                return number, "a line that returns to an indentation no open block uses"
        state = last.get(indent)
        if state and entry and state["kind"] == "key" and not state["open"]:
            return number, "a list entry beside mapping keys"
        if state and not entry and state["kind"] == "entry" and not state["compact"]:
            return number, "a mapping key beside list entries"
        opener = None
        if entry:
            compact = bool(state) and (state["kind"] == "key" or state["compact"])
            last[indent] = {"kind": "entry", "open": False, "compact": compact}
            content = text[1:].lstrip(" \t")
            match = YAML_KEY.fullmatch(content) if content else None
            if not content:
                opener = indent
            elif match:  # the entry's mapping continues at the column its first key starts in
                column = indent + len(text) - len(content)
                levels.append(column)
                empty = not (match.group("value") or "").strip()
                last[column] = {"kind": "key", "open": empty, "compact": False}
                opener = column if empty else None
        else:
            match = YAML_KEY.fullmatch(text)
            empty = not (match and (match.group("value") or "").strip())
            last[indent] = {"kind": "key", "open": empty, "compact": False}
            opener = indent if empty else None
    return None


def subset_policy(text: str) -> tuple[bool | None, str | None, str]:
    """openai_yaml_policy without PyYAML: the plain block-mapping subset (SUBSET_INDICATORS and subset_layout_problem)
    is read and anything else gets None with the line and construct it stopped at, so the reader never asserts a value
    for syntax it did not parse."""
    def unverified(number, what):
        return None, None, (f"line {number}: {what} is outside the plain block-mapping subset this reader parses "
                            "without PyYAML, so how Codex reads implicit invocation is unverified")

    rows, started, ended, tab = [], False, False, None
    for number, raw_line in enumerate(re.split(r"\r\n|\n", text), 1):  # openai_yaml_doubt refused any other break
        body = strip_yaml_comment(raw_line)
        stripped = body.strip()
        if not stripped:
            continue
        if ended:
            return unverified(number, "a second document after the end marker ...")
        if body.startswith(("---", "...")) and (len(body) == 3 or body[3] in " \t"):
            if body[3:].strip():
                return unverified(number, f"content after the document marker {body[:3]}")
            if body.startswith("..."):
                ended = True
            elif rows or started:
                return unverified(number, "a second document (---)")
            started = True
            continue
        indent = len(body) - len(body.lstrip(" \t"))
        if "\t" in body[:indent]:
            tab = tab or number
        item = stripped
        if item == "-" or item.startswith(("- ", "-\t")):
            item = item[1:].lstrip(" \t")
            if item == "-" or item.startswith(("- ", "-\t")):
                return unverified(number, "a list nested in a list entry")
            match = YAML_KEY.fullmatch(item) if item else None
            problem = subset_value_problem((match.group("value") or "").strip() if match else item)
        else:
            match = YAML_KEY.fullmatch(item)
            problem = (subset_value_problem((match.group("value") or "").strip()) if match
                       else "a line that is not a key: value pair or a list entry")
        if problem:
            return unverified(number, problem)
        rows.append((number, indent, stripped))
    if tab is not None:
        return unverified(tab, "a tab in the indentation")
    layout = subset_layout_problem(rows)
    if layout:
        return unverified(*layout)
    return subset_structure([(indent, stripped) for _, indent, stripped in rows])


def subset_structure(lines) -> tuple[bool, str | None, str]:
    """The policy value of a document inside the subset (lines: (indent, text)), as serde_yaml reads it."""
    def key_of(body):
        match = YAML_KEY.fullmatch(body)
        return (match.group("key").strip("'\""), (match.group("value") or "").strip()) if match else (None, "")

    top = [(position, key_of(body)[0]) for position, (indent, body) in enumerate(lines) if indent == 0]
    if top and lines[top[0][0]][1].startswith("-"):
        return True, None, f"the document is a list, not a mapping: {CODEX_IGNORES}"
    for field in METADATA_FIELDS:
        if [key for _, key in top].count(field) > 1:
            return True, None, f"{field} appears twice: {CODEX_IGNORES}"
    tops = [position for position, key in top if key == "policy"]
    if not tops:
        return True, None, "no policy mapping: Codex defaults allow_implicit_invocation to true"
    rest = key_of(lines[tops[0]][1])[1]
    if rest:
        scalar, quoted = yaml_scalar(rest)
        if not quoted and scalar in SERDE_YAML_NULL:
            return True, None, "policy is null: Codex defaults allow_implicit_invocation to true"
        return True, None, f"policy is {rest!r}, not a mapping: {CODEX_IGNORES}"
    block = []
    for indent, body in lines[tops[0] + 1:]:
        if indent == 0:
            break
        block.append((indent, body))
    if not block:
        return True, None, "policy is null: Codex defaults allow_implicit_invocation to true"
    if block[0][1].startswith("-"):
        return True, None, f"policy is a list, not a mapping: {CODEX_IGNORES}"
    child = block[0][0]
    children = [(position, *key_of(body)) for position, (indent, body) in enumerate(block) if indent == child]
    for field in POLICY_FIELDS:
        if [key for _, key, _ in children].count(field) > 1:
            return True, None, f"{field} appears twice under policy: {CODEX_IGNORES}"
    found = [(position, value) for position, key, value in children if key == "allow_implicit_invocation"]
    if not found:
        return True, None, "no policy.allow_implicit_invocation: Codex defaults it to true"
    position, value = found[0]
    if not value:
        if position + 1 < len(block) and block[position + 1][0] > child:  # a mapping or list (the subset's layout)
            return True, None, f"allow_implicit_invocation holds a mapping or list: {CODEX_IGNORES}"
        return True, None, "policy.allow_implicit_invocation is null: Codex defaults it to true"
    scalar, quoted = yaml_scalar(value)
    if not quoted and scalar in SERDE_YAML_NULL:
        return True, scalar, "policy.allow_implicit_invocation is null: Codex defaults it to true"
    if not quoted and scalar in SERDE_YAML_BOOL:
        return SERDE_YAML_BOOL[scalar], scalar, f"policy.allow_implicit_invocation: {scalar}"
    return True, value, (f"allow_implicit_invocation {value} is not a YAML boolean serde_yaml reads (a plain true or "
                         f"false): {CODEX_IGNORES}")


# --------------------------------------------------------------------------- the skills CLI's discovery order


def cli_walk(container: str, max_depth: int, skill_dirs) -> list[str]:
    """The folders skills.ts walkSkillDirs(container, max_depth) finds a SKILL.md in: 1 to max_depth levels below the
    container, never below a folder that holds a SKILL.md (a shallower SKILL.md shadows the folders below it) and never
    through a SKIP_DIRS folder. skill_dirs are the repository's folders that hold a SKILL.md."""
    prefix = f"{container}/" if container else ""
    found = []
    for folder in skill_dirs:
        if not folder or folder == container or not folder.startswith(prefix):
            continue
        parts = folder[len(prefix):].split("/")
        between = [prefix + "/".join(parts[:depth]) for depth in range(1, len(parts))]
        if len(parts) <= max_depth and not any(step in skill_dirs for step in between) \
                and not CLI_SKIP_DIRS.intersection(parts[:-1]):
            found.append(folder)
    return sorted(found)


def cli_plugin_dirs(marketplace, plugin) -> list[str]:
    """The folders plugin-manifest.ts getPluginSkillPaths adds to the search from a parsed
    .claude-plugin/marketplace.json and .claude-plugin/plugin.json (None when absent): for each local plugin, the parent
    of every skill path it declares and its skills/ folder. Paths must start with ./ and stay inside the repository."""
    dirs = []

    def inside(path):
        normal = posixpath.normpath(path)
        return "" if normal == "." else None if normal == ".." or normal.startswith(("../", "/")) else normal

    def add(base, skills):
        base = inside(base)
        if base is None:
            return
        for skill in skills if isinstance(skills, list) else []:
            if isinstance(skill, str) and skill.startswith("./"):
                # Node's path.dirname ignores a trailing slash ("./skills/" names the folder skills).
                parent = inside(posixpath.dirname(posixpath.join(base, skill).rstrip("/")))
                if parent is not None:
                    dirs.append(parent)
        dirs.append(inside(posixpath.join(base, "skills")))

    if isinstance(marketplace, dict):
        metadata = marketplace.get("metadata") if isinstance(marketplace.get("metadata"), dict) else {}
        root = metadata.get("pluginRoot", MISSING)
        if root is MISSING or (isinstance(root, str) and root.startswith("./")):
            for entry in marketplace.get("plugins") if isinstance(marketplace.get("plugins"), list) else []:
                source = entry.get("source", MISSING) if isinstance(entry, dict) else None
                if source is MISSING or (isinstance(source, str) and source.startswith("./")):
                    add(posixpath.join("" if root is MISSING else root, "" if source is MISSING else source),
                        entry.get("skills"))
    if isinstance(plugin, dict):
        add("", plugin.get("skills"))
    return dirs


def cli_locations(skill_dirs, plugin_dirs=()) -> list:
    """[(container, depth, where, folders)] of the locations discoverSkills searches without --full-depth, in its order:
    the root's child folders, each of CLI_CONTAINERS three levels deep, then each plugin folder one level deep, each
    with the folders it finds a SKILL.md in that no earlier location found (parseSkillAt skips a SKILL.md it parsed
    before)."""
    parsed, locations = set(), []
    for container, depth in [("", 1), *((container, CLI_CONTAINER_DEPTH) for container in CLI_CONTAINERS),
                             *((folder, 1) for folder in plugin_dirs)]:
        found = [folder for folder in cli_walk(container, depth, skill_dirs) if folder not in parsed]
        parsed.update(found)
        locations.append((container, depth, f"{container}/" if container else "the repository root", found))
    return locations


def symlink_at_or_above(path: str, symlinks) -> str | None:
    """The symlink (a git tree path of mode 120000) that `path` is or lies below, or None: `path` itself or one of the
    folders above it."""
    parts = path.split("/") if path else []
    return next(("/".join(parts[:depth]) for depth in range(1, len(parts) + 1) if "/".join(parts[:depth]) in symlinks),
                None)


def location_doubt(container: str, depth: int, skill_dirs, symlinks, linked_skill_md) -> str | None:
    """Why what the CLI finds in this search location cannot be read from the git tree, or None. The CLI walks a
    location with readdir, which follows a symlink at or above it (dist/cli.mjs lines 1339-1370, src/skills.ts lines
    284-298), so a symlinked location holds whatever its target holds, while the tree lists the symlink as one blob and
    nothing below it. Below the location a symlinked folder is skipped (its directory entry is not a directory), as the
    tree shows too, but a folder whose SKILL.md is a symlink is a skill folder only when the link's target is a file
    (hasSkillMd stats it, following the link): whether the walk stops there or descends to the skill folders below it
    depends on a target the tree does not resolve. `linked_skill_md` are the folders whose SKILL.md is a symlink."""
    if container:
        link = symlink_at_or_above(container, symlinks)
        if link is not None:
            return (f"the search location {container}/ is {'a symlink' if link == container else f'below the symlink {link}'}"
                    ", which the CLI walks through (readdir follows it) and the git tree does not show")
    prefix = f"{container}/" if container else ""
    for folder in cli_walk(container, depth, skill_dirs):
        if folder not in linked_skill_md or folder.rsplit("/", 1)[-1] in CLI_SKIP_DIRS:
            continue
        level = len(folder[len(prefix):].split("/"))
        for other in skill_dirs:
            below = other[len(folder) + 1:].split("/") if other.startswith(f"{folder}/") else None
            if below and level + len(below) <= depth and not CLI_SKIP_DIRS.intersection(below[:-1]):
                return (f"{folder}/SKILL.md is a symlink with the skill folder {other} below it in {prefix or 'the root'}: "
                        "whether the CLI walks below it depends on the link's target, which the git tree does not "
                        "resolve")
    return None


def cli_skill_dir(skill_dirs, name: str, plugin_dirs=(), inspect=None, skipped=None, doubt=None,
                  plugin_doubt=None) -> tuple[str | None, str]:
    """(folder, where) of the skill <name> as discoverSkills finds it without --full-depth, or (None, why not). The
    root SKILL.md is decided before this (a valid one is the repository's only skill). The CLI validates a SKILL.md
    before it takes its name (parseSkillMd returns null for one without a name or description, and tryAddSkillAt then
    adds nothing), so an invalid copy never claims <name>. inspect(folder) gives (why the CLI skips that folder's
    SKILL.md or None, the name --skill is matched against: getSkillDisplayName, the sanitized name or else the folder's
    name), or raises SkillMdUnverified when no verdict stands behind that copy, which propagates wherever that copy's
    verdict decides the result; without inspect every SKILL.md is valid and named after its folder. A copy is a folder
    named <name> whose SKILL.md is valid and whose display name is <name> in any letter case (filterSkills,
    src/skills.ts lines 331-348); a folder that fails is appended to `skipped` as (folder, reason) and passed over. The
    first location that holds a copy decides; two copies there are ambiguous (the CLI keeps whichever its directory
    listing returns first). Only when no location holds a valid skill of any name (skills.length === 0) does the CLI
    search every folder up to five levels deep, where a copy shadows the copies below it and two unnested copies are
    ambiguous. A folder anywhere else (docs/<lang>/skills/<name>, examples/) needs --full-depth and is never taken.
    doubt(container, depth) says why what the CLI finds in a location cannot be read from the git tree (location_doubt:
    a symlink at or above it, or a symlinked SKILL.md with skill folders below it), and plugin_doubt why the plugin
    folders are unknown (the manifests lie behind a symlink or their bytes are not the listed blobs): reaching such a
    location before the pick is decided raises SkillMdUnverified, since the CLI may find a copy of <name> there first, or
    a valid skill that keeps it from the recursive search. A location searched after the pick is decided cannot change
    it: the CLI keeps the first skill of a name (seenNames)."""
    inspect = inspect or (lambda folder: (None, folder.rsplit("/", 1)[-1]))
    skipped = [] if skipped is None else skipped
    named_skips, doubts = [], []

    def unknown(why):
        return LocationUnverified(f"{why}; no earlier location the CLI searches holds a valid copy of {name}, so the "
                                  "CLI may take one from there, or skip its recursive search because of what is there")

    def copies(folders):
        good = []
        for folder in folders:
            reason, declared = inspect(folder)
            if reason is None and declared and declared.lower() != name.lower():
                reason = f"its name field names the skill {declared!r}, not {name}"
            if reason is None:
                good.append(folder)
            elif (folder, reason) not in skipped:
                skipped.append((folder, reason))
                named_skips.append(folder)
        return good

    locations = cli_locations(skill_dirs, plugin_dirs)
    plugin_start = 1 + len(CLI_CONTAINERS)  # the root, then the containers, then the plugin folders
    for index, (container, depth, where, found) in enumerate(locations):
        if index == plugin_start and plugin_doubt:
            raise unknown(plugin_doubt)
        why = doubt(container, depth) if doubt else None
        if why:
            raise unknown(why)
        matches = copies([folder for folder in found if folder.rsplit("/", 1)[-1] == name])
        if len(matches) == 1:
            return matches[0], f"{where}, the first location the CLI searches that holds a valid folder named {name}"
        if matches:
            return None, (f"{len(matches)} folders named {name} in {where}, the first location the CLI searches that "
                          f"holds a valid one: {matches} (the CLI keeps whichever its directory listing returns first)")
    if plugin_doubt and len(locations) <= plugin_start:
        raise unknown(plugin_doubt)

    def takes(folder):
        try:
            return inspect(folder)[0] is None
        except SkillMdUnverified as why:
            doubts.append(why)
            return False

    # Any valid SKILL.md in the locations stops the fallback, inspected in the CLI's order up to the first valid one; a
    # SKILL.md the reader cannot tell about decides it only when none of the others is valid.
    if any(takes(folder) for *_, found in locations for folder in found):
        if named_skips:
            return None, (f"every copy of {name} in the locations the CLI searches without --full-depth is invalid, "
                          "and a valid skill there keeps the CLI from searching further")
        return None, f"no folder named {name} in the locations the CLI searches without --full-depth"
    if doubts:
        raise doubts[0]
    candidates = sorted(folder for folder in skill_dirs if folder and folder.count("/") < CLI_FALLBACK_DEPTH
                        and folder.rsplit("/", 1)[-1] == name and not CLI_SKIP_DIRS.intersection(folder.split("/")))
    good = copies(candidates)
    good = [folder for folder in good if not any(folder.startswith(f"{other}/") for other in good)]
    if len(good) == 1:
        return good[0], "the recursive search the CLI runs when no location it searches holds a valid skill"
    if good:
        return None, (f"{len(good)} unnested folders named {name} in the CLI's recursive search: {good} (the CLI keeps "
                      "whichever its directory listing returns first)")
    if skipped and any(folder.rsplit("/", 1)[-1] == name for folder, _ in skipped):
        return None, f"every copy of {name} the CLI's discovery reaches is invalid"
    return None, f"no folder named {name} holds a SKILL.md"


# --------------------------------------------------------------------------- skill reviews


def gh_file(full: str, path: str, commit: str) -> bytes:
    """The bytes the contents API returns for path at commit. GhError when it returns no base64 content: a file over
    1 MB comes back with the encoding "none", and a symlink whose target is not a file in the repository as a
    "symlink" entry without content."""
    content = gh(f"repos/{full}/contents/{urllib.parse.quote(path, safe='/')}?ref={commit}")
    if not (isinstance(content, dict) and content.get("encoding") == "base64" and isinstance(content.get("content"), str)):
        kind = content.get("type") if isinstance(content, dict) else type(content).__name__
        encoding = content.get("encoding") if isinstance(content, dict) else None
        raise GhError(f"gh api repos/{full}/contents/{path}?ref={commit} returned no base64 content (type {kind}, "
                      f"encoding {encoding})")
    return base64.b64decode(content["content"])


def git_blob_id(data: bytes) -> str:
    """git's object id of a blob (git hash-object): the sha1 of "blob <size>\\0" and the bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_file(full: str, path: str, commit: str, entry) -> bytes:
    """The bytes of the regular file the git tree at commit lists at path (entry: its tree listing record), read with
    gh and checked against the listed blob id, so no review rests on bytes that are not that blob. Raises
    SkillMdUnverified when the tree lists a symlink there (mode 120000: the CLI's clone follows it, which this review
    does not), or anything but a regular file, when gh cannot read it or returns no base64 content, and when the bytes
    are not the listed blob."""
    entry = entry if isinstance(entry, dict) else {}
    if entry.get("type") != "blob" or entry.get("mode") not in REGULAR_FILE_MODES:
        kind = "a symlink" if entry.get("mode") == "120000" else f"{entry.get('type') or 'no'} entry, mode {entry.get('mode')}"
        raise SkillMdUnverified(f"the git tree lists {kind} at {path}, not a regular file (the CLI reads its clone)")
    try:
        raw = gh_file(full, path, commit)
    except GhError as error:  # the CLI reads the blob the tree lists from its clone; this API read says nothing
        raise SkillMdUnverified(f"{path} could not be read here ({error})") from None
    # Residual: these are the blob's bytes. The CLI reads its clone's checkout, where .gitattributes can change them
    # (filter=lfs leaves a pointer or fetches the object, eol and text normalization, working-tree-encoding), and the
    # review does not read .gitattributes.
    if git_blob_id(raw) != entry.get("sha"):
        raise SkillMdUnverified(f"the {len(raw)} bytes read for {path} are not the git blob {entry.get('sha')} the tree "
                                "lists")
    return raw


def tree_json_file(full: str, path: str, commit: str, entry):
    """A plugin manifest the CLI parses (tree_file's bytes), or None when it is not JSON: the CLI skips it. Raises
    SkillMdUnverified for bytes tree_file does not verify; the caller then treats the plugin folders as unknown."""
    raw = tree_file(full, path, commit, entry)
    try:
        return json.loads(raw)
    except ValueError:
        return None


def plugin_manifests(full: str, commit: str, entries: dict, symlinks) -> tuple[list, str | None]:
    """([marketplace, plugin] as the CLI parses them from .claude-plugin (None when absent or not JSON), why the plugin
    folders they declare are unknown or None). getPluginSkillPaths reads both files with readFile, which follows a
    symlink, so a symlinked .claude-plugin or manifest, or manifest bytes that are not the listed blob, leave the
    plugin folders unknown."""
    if symlink_at_or_above(".claude-plugin", symlinks) is not None:
        return [None, None], "the plugin manifest folder .claude-plugin is a symlink, which the CLI reads through"
    parsed, doubt = [], None
    for path in PLUGIN_MANIFESTS:
        entry = entries.get(path)
        if not entry or entry.get("type") != "blob":
            parsed.append(None)
            continue
        try:
            parsed.append(tree_json_file(full, path, commit, entry))
        except SkillMdUnverified as why:
            parsed.append(None)
            doubt = doubt or f"the plugin manifest {path} has no verified bytes ({why})"
    return parsed, doubt


def git_tree_id(entries, folder: str) -> str:
    """git's object id of the tree of `folder` ("" for the root), recomputed from a recursive git-trees listing's
    direct children of it: each child as "<mode> <name>\\0" and its 20-byte id, in git's order (a folder compares as
    its name followed by "/"), under the header "tree <size>\\0". The listing's mode 040000 is git's 40000."""
    prefix, children = f"{folder}/" if folder else "", []
    for entry in entries:
        path = str(entry.get("path") or "")
        name = path[len(prefix):]
        if not path.startswith(prefix) or not name or "/" in name:
            continue
        tree = entry.get("type") == "tree"
        mode = format(int(str(entry.get("mode")), 8), "o").encode()
        children.append((name.encode() + (b"/" if tree else b""),
                         mode + b" " + name.encode() + b"\0" + bytes.fromhex(str(entry.get("sha")))))
    body = b"".join(item for _, item in sorted(children))
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def skill_folder_tree_sha(listing: dict, folder: str, read: dict) -> str:
    """The skill folder's git tree id at the reviewed commit: the id the listing gives it, and for a root SKILL.md the
    root tree's, as the pinned skills CLI records a skill's skillFolderHash (src/blob.ts getSkillFolderHashFromTree).
    Verified before it is recorded: each file read ({path: bytes}) is the blob the listing names for its path, and
    every folder from the skill folder down to those files hashes to the id the listing gives it, so the id covers the
    SKILL.md and agents/openai.yaml bytes the review read. Raises GhError on a missing id or any mismatch: a survivor's
    folder hash is never null."""
    entries = [entry for entry in listing.get("tree") or [] if isinstance(entry, dict)]
    by_path = {entry.get("path"): entry for entry in entries}
    own = by_path.get(folder) or {}
    listed = listing.get("sha") if not folder else own.get("sha") if own.get("type") == "tree" else None
    if not (isinstance(listed, str) and HEX40.fullmatch(listed)):
        raise GhError(f"the git tree lists no id for the skill folder {folder or '(the repository root)'}")
    folders = {folder}
    for path, data in read.items():
        entry = by_path.get(path) or {}
        if entry.get("type") != "blob" or entry.get("sha") != git_blob_id(data):
            raise GhError(f"{path} is not the git blob the tree lists for it ({entry.get('sha')}), so the folder's id "
                          "would not cover the bytes read")
        if folder and not path.startswith(f"{folder}/"):
            raise GhError(f"{path} is outside the skill folder {folder}")
        parent = posixpath.dirname(path)
        while parent != folder:
            folders.add(parent)
            parent = posixpath.dirname(parent)
    for each in sorted(folders):
        expected = listing.get("sha") if not each else (by_path.get(each) or {}).get("sha")
        if git_tree_id(entries, each) != expected:
            raise GhError(f"the git tree listing does not hash to the id it gives {each or 'the repository root'} "
                          f"({expected}), so the folder's id would not cover the bytes read")
    return listed


class ReviewRefused(GhError):
    """A skill survivor that gets no review. pin_lookup says how far its adjudicated pin got: "failed" (none named, not
    a 40-hex commit, unreadable, or read as another commit), "ok" (read; a later check refused the survivor), or None
    (not looked up: the survivor's skill_md_sha256 is null)."""

    def __init__(self, message: str, pin_lookup: str | None = None):
        super().__init__(message)
        self.pin_lookup = pin_lookup


def skill_review(owner_repo: str, name: str, layers: list, lane: str, fit_models: str, pin=None,
                 expected_sha256=()) -> dict:
    """The review of a skill survivor at its adjudicated pin, and at no other commit: ReviewRefused whenever the pin,
    the judged SKILL.md bytes or the skill folder's hash cannot be established (see the module docstring)."""
    label = f"{owner_repo}@{name}"
    if not pin:
        raise ReviewRefused(f"{label}: the survivor names no adjudicated pin, so no commit ties a review to the SKILL.md "
                            "the refuters judged", "failed")
    if not (isinstance(pin, str) and HEX40.fullmatch(pin)):
        raise ReviewRefused(f"{label}: the adjudicated pin {pin!r} is not a 40-hex commit", "failed")
    expected = sorted({str(value) for value in expected_sha256 if value is not None})
    if not expected_sha256 or any(value is None for value in expected_sha256):
        raise ReviewRefused(f"{label}: the survivor's skill_md_sha256 is null, so nothing ties a review to the bytes the "
                            "refuters judged")
    if len(expected) > 1 or not HEX64.fullmatch(expected[0]):
        raise ReviewRefused(f"{label}: the survivor's skill_md_sha256 at {pin} is {expected}, not one sha256")
    try:
        meta = gh(f"repos/{owner_repo}")
        full = meta["full_name"]
        commit = gh(f"repos/{full}/commits/{pin}")["sha"]
    except (GhError, KeyError, TypeError) as error:
        raise ReviewRefused(f"{label}: the adjudicated pin {pin} is unreadable ({error}); no review is written at "
                            "another commit", "failed") from None
    if commit != pin:
        raise ReviewRefused(f"{full}@{name}: GitHub reads the pin as the commit {commit}, not the adjudicated pin {pin}",
                            "failed")
    try:
        return pinned_skill_review(meta, name, pin, layers, lane, fit_models, expected[0])
    except (GhError, KeyError, ValueError, TypeError) as error:
        raise ReviewRefused(str(error), "ok") from None


def pinned_skill_review(meta: dict, name: str, pin: str, layers: list, lane: str, fit_models: str,
                        expected: str) -> dict:
    """skill_review once the pin reads as itself: the SKILL.md the CLI discovers at the pin, its bytes checked against
    the judged sha256, and the skill folder's tree id covering them."""
    full, branch = meta["full_name"], meta["default_branch"]
    tree = gh(f"repos/{full}/git/trees/{pin}?recursive=1")
    if tree.get("truncated"):
        raise GhError(f"{full}@{name}: the git tree at {pin} is truncated, so the CLI's discovery order cannot be "
                      "followed")
    entries = {entry["path"]: entry for entry in tree.get("tree") or [] if isinstance(entry, dict)
               and isinstance(entry.get("path"), str)}
    blobs = {path for path, entry in entries.items() if entry.get("type") == "blob"}
    skill_dirs = {path[:-len("/SKILL.md")] for path in blobs if path.endswith("/SKILL.md")}
    symlinks = {path for path, entry in entries.items() if entry.get("mode") == "120000"}
    linked_skill_md = {path[:-len("/SKILL.md")] for path in symlinks if path.endswith("/SKILL.md")}
    files = {}  # SKILL.md path -> (bytes, skill_md_check's result), or SkillMdUnverified

    def read(path):
        """(bytes, skill_md_check's result) of the SKILL.md at path: the regular-file blob the tree lists there
        (tree_file) as skill_md.mjs judges it, or SkillMdUnverified when either gives no verdict."""
        if path not in files:
            try:
                raw = tree_file(full, path, pin, entries.get(path))
                files[path] = (raw, skill_md_check(raw, path))
            except SkillMdUnverified as why:
                files[path] = SkillMdUnverified(str(why) if str(why).startswith(path) else f"{path}: {why}")
        if isinstance(files[path], SkillMdUnverified):
            raise files[path]
        return files[path]

    def inspect(folder):
        """(why the CLI skips the folder's SKILL.md or None, the name --skill is matched against: getSkillDisplayName,
        the name or else the folder's)."""
        result = read(f"{folder}/SKILL.md")[1]
        return (None, result.get("display_name")) if result["verdict"] == "take" else (result.get("reason"), None)

    def skipped_detail():
        detail = "; ".join(f"{f'{each}/' if each else ''}SKILL.md: {why}" for each, why in skipped)
        return f" (skipped: {detail})" if detail else ""

    skipped, skill_path, found_by = [], None, None
    try:
        if "SKILL.md" in blobs:  # a valid root SKILL.md is the only skill the CLI discovers (discoverSkills returns)
            root = read("SKILL.md")[1]
            if root["verdict"] == "take":
                if not root["name"]:
                    raise GhError(f"{full}@{name}: the root SKILL.md at {pin}, the only skill the skills CLI discovers "
                                  "in this repository without --full-depth, has a name that sanitizes to nothing, so "
                                  "the CLI names it after its clone directory")
                if root["name"].lower() != name.lower():
                    raise GhError(f"{full}@{name}: the root SKILL.md at {pin} is the skill {root['name']!r}, the only "
                                  "one the skills CLI discovers in this repository without --full-depth")
                skill_path = "SKILL.md"
                found_by = "the repository root's SKILL.md, the only skill the CLI discovers there"
            else:
                skipped.append(("", root["reason"]))  # the CLI skips it and searches on
        if skill_path is None:
            manifests, plugin_doubt = plugin_manifests(full, pin, entries, symlinks)
            folder, found_by = cli_skill_dir(
                skill_dirs, name, cli_plugin_dirs(*manifests), inspect, skipped,
                doubt=lambda container, depth: location_doubt(container, depth, skill_dirs, symlinks, linked_skill_md),
                plugin_doubt=plugin_doubt)
            if folder is None:
                raise GhError(f"{full}@{name} at {pin}: {found_by}{skipped_detail()}")
            skill_path = f"{folder}/SKILL.md"
    except LocationUnverified as why:
        raise GhError(f"{full}@{name} at {pin}: {why}; which copy the skills CLI installs is unverified"
                      f"{skipped_detail()}") from None
    except SkillMdUnverified as why:
        raise GhError(f"{full}@{name} at {pin}: {why}; whether the skills CLI takes that copy, and so which copy it "
                      f"installs, is unverified{skipped_detail()}") from None
    raw, chosen = read(skill_path)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise GhError(f"{full}@{name}: {skill_path} at {pin} has sha256 {digest}, not the survivor's skill_md_sha256 "
                      f"{expected}: the review would describe other bytes than the refuters judged")
    text = raw.decode("utf-8", "replace")
    frontmatter = SKILL_MD_FRONTMATTER.match(text)
    folder = skill_path.rsplit("/", 1)[0] if "/" in skill_path else ""
    yaml_path = f"{folder}/agents/openai.yaml" if folder else "agents/openai.yaml"
    read_bytes = {skill_path: raw}
    if yaml_path in blobs:
        read_bytes[yaml_path] = gh_file(full, yaml_path, pin)
        implicit, policy_value, policy_note = openai_yaml_policy(read_bytes[yaml_path])
    else:
        implicit, policy_value, policy_note = True, None, "no agents/openai.yaml: Codex allows implicit invocation"
    folder_sha = skill_folder_tree_sha(tree, folder, read_bytes)
    repository_license = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    declared_license = chosen.get("license")
    license_id = declared_license.strip() if isinstance(declared_license, str) and declared_license.strip() \
        else repository_license
    return {"schema_version": 1, "id": f"source-review-{review_name(f'{full}@{name}')}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"{full}@{name}", "reviewed_commit": pin,
            "readme_path": skill_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source review of the skill {name} in {full} at commit {pin} (the adjudicated pin; license "
                      f"{license_id}), read from {skill_path}" + (f" and {yaml_path}" if yaml_path in blobs else "")
                      + " at that commit, the SKILL.md the pinned skills CLI (vercel-labs/skills v1.7.0) discovers "
                      f"for {name}; its sha256 matches the survivor's skill_md_sha256, and the skill folder's git tree "
                      f"at that commit is {folder_sha}. Survived the {lane} facts refuter and both fit refuters "
                      f"({fit_models}); no install, invocation, benchmark or comparison with an installed skill."),
            "observed": {"stars": meta.get("stargazers_count"), "pushed_at": meta.get("pushed_at"),
                         "archived": meta.get("archived"), "default_branch": branch,
                         "repository_license": repository_license,
                         "adjudicated_pin": pin, "pin_lookup": "ok",
                         "skill_md_found_by": found_by,
                         "skipped_skill_md": [{"path": f"{each}/SKILL.md" if each else "SKILL.md", "reason": why}
                                              for each, why in skipped],
                         "skill_md_sha256": digest, "skill_md_bytes": len(raw), "survivor_skill_md_sha256": expected,
                         "skill_md_reader": dict(READER["record"] or {}, script="skill_md.mjs"),
                         "skill_folder_tree_sha": folder_sha,
                         "disable_model_invocation": claude_true(chosen.get("disable_model_invocation")),
                         "openai_yaml_path": yaml_path if yaml_path in blobs else None,
                         "openai_yaml_reader": openai_yaml_reader() if yaml_path in blobs else None,
                         "codex_implicit": implicit, "unverified_reason": policy_note if implicit is None else None,
                         "openai_yaml_policy_value": policy_value, "openai_yaml_policy_note": policy_note},
            "documentation_excerpts": excerpts_from(frontmatter.group(2) if frontmatter else text,
                                                    f"{skill_path}@{pin}")}


def review(repository: str, layers: list, lane: str, fit_models: str, pin=None, expected_sha256=()) -> dict:
    forgejo = codeberg_repo(repository)
    if forgejo:
        return codeberg_review(forgejo, layers, lane, fit_models)
    repo_id = hub_model(repository)
    if repo_id:
        return hub_review(repo_id, layers, lane, fit_models)
    skill = SKILL_REF.fullmatch(str(repository or "").strip())
    if skill:
        return skill_review(skill.group(1), skill.group(2), layers, lane, fit_models, pin, expected_sha256)
    owner_repo = slug(repository)
    if not OWNER_REPO.fullmatch(owner_repo):
        raise GhError(f"{repository} is not a GitHub, Codeberg or Hugging Face model repository URL")
    meta = gh(f"repos/{owner_repo}")
    full, branch = meta["full_name"], meta["default_branch"]
    commit = gh(f"repos/{full}/commits/{branch}")["sha"]
    license_id = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    excerpts, readme_path = [], None
    try:
        readme = gh(f"repos/{full}/readme?ref={commit}")
        readme_path = readme["path"]
        text = base64.b64decode(readme["content"]).decode("utf-8", "replace")
        excerpts = excerpts_from(text, f"{readme_path}@{commit}")
    except GhError:
        pass
    description = (meta.get("description") or "").strip()
    return {"schema_version": 1, "id": f"source-review-{review_name(full)}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"https://github.com/{full}", "reviewed_commit": commit,
            "readme_path": readme_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source and documentation review of {full} at commit {commit} (license {license_id}), read from "
                      f"{readme_path or 'the repository metadata'} at that commit"
                      + (f". Repository description: \"{description}\"." if description else ".")
                      + f" Survived the {lane} facts refuter and both fit refuters ({fit_models}); "
                        "no native install, run or comparison with a winner."),
            "observed": {"stars": meta.get("stargazers_count"), "pushed_at": meta.get("pushed_at"),
                         "archived": meta.get("archived"), "default_branch": branch},
            "documentation_excerpts": excerpts}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--survivors", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lane", required=True)
    parser.add_argument("--fit-models", default="Claude Opus 5.5 and GPT-6-Astra",
                        help="the two fit refuters' resolved models, as the claim names them")
    parser.add_argument("--skills-yaml", type=Path,
                        help=f"the yaml install skill_md.mjs verifies (skills-yaml.pin.json); default {SKILLS_YAML_ENV}, "
                             "then the pin's default directory under HOME")
    args = parser.parse_args(argv)
    READER.update(install=str(args.skills_yaml) if args.skills_yaml else None, failure=None, record=None)
    survivors = json.loads(args.survivors.read_text(encoding="utf-8"))
    # Review key -> the survivor URL first seen and every layer it survived in. A skill is reviewed once per adjudicated
    # pin (<skill key>#<pin>): the same skill judged at two commits in two layers gets two reviews. Each layer's
    # skill_md_sha256 is kept, a null one too, which skill_review refuses.
    by_repo: dict[str, dict] = {}
    for survivor in survivors:
        skill = bool(SKILL_REF.fullmatch(str(survivor["repository"]).strip()))
        pin = survivor.get("pin") if skill else None
        key = repository_key(survivor["repository"]) + (f"#{pin}" if pin else "")
        item = by_repo.setdefault(key, {"repository": survivor["repository"], "layers": [], "pin": pin,
                                        "skill": skill, "skill_md_sha256": []})
        item["layers"].append(survivor["layer_id"])
        if skill:
            item["skill_md_sha256"].append(survivor.get("skill_md_sha256"))
    written, failed, stopped, docs = [], [], [], {}

    def stop(item, reason, pin_lookup):
        """A skill survivor with no review: its layers are stopped (make_result.py refuses to complete them)."""
        if item["skill"]:
            stopped.append({"repository": item["repository"], "layers": sorted(set(item["layers"])),
                            "status": "stopped", "pin": item["pin"], "pin_lookup": pin_lookup, "reason": reason})

    for key, item in sorted(by_repo.items()):
        try:
            docs[key] = review(item["repository"], item["layers"], args.lane, args.fit_models, item["pin"],
                               item["skill_md_sha256"])
        except (GhError, KeyError, ValueError, TypeError) as error:
            failed.append(f"{item['repository']}: {error}")
            stop(item, str(error), getattr(error, "pin_lookup", None))
    try:
        stems = unique_stems({key: doc["id"][len("source-review-"):] for key, doc in docs.items()})
    except ValueError as error:
        print(f"source_reviews.py: {error}", file=sys.stderr)
        return 2
    args.out.mkdir(parents=True, exist_ok=True)
    for key, doc in sorted(docs.items()):
        doc["id"] = f"source-review-{stems[key]}"
        path = args.out / f"{stems[key]}.json"
        if path.is_file():
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                previous = None
            reviewed = previous.get("repository", "") if isinstance(previous, dict) else ""
            if str(reviewed).lower().rstrip("/") != doc["repository"].lower():
                reason = f"{path} already holds a review of another repository; not overwritten"
                failed.append(f"{by_repo[key]['repository']}: {reason}")
                stop(by_repo[key], reason, "ok")
                continue
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append({"repository": doc["repository"], "path": path.name, "layers": doc["layers"]})
    print(json.dumps(written + stopped, indent=1))
    for line in failed:
        print(f"source_reviews.py: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
