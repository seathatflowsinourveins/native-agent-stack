#!/usr/bin/env python3
"""Write one upstream-provenance source review per sweep survivor (network: gh api, and the public Hugging Face
Hub API for a model repository; no model calls).

  source_reviews.py --survivors OUT/survivors.json --out evidence/artifacts/<lane> --lane <lane>
                    [--fit-models "Claude Opus 5.5 and GPT-6-Astra"] > OUT/reviews.json

The shape follows evidence/artifacts/landscape-sweep-20260923/*.json: schema_version, id, kind, evidence_class,
repository, reviewed_commit, readme_path, license, layers, claim, observed, documentation_excerpts. A repository
surviving in several layers gets one review listing every layer. Prints [{repository, path, layers}] (make_result.py
--reviews reads it). A review is named <owner>-<repo>.json, lowercased with every other character run as "-", like
the 2026-09-23 reviews; when two reviews share that name (acme/a-b and acme-a/b, or one skill that survived at two
pins), each gets a suffix of 10 hex characters of the sha256 of its key, so no review overwrites another. A survivor
that cannot be reviewed (gh cannot read it, its skill cannot be resolved or its SKILL.md hash disagrees), or whose
file name already holds a review of another repository, is reported and skipped (exit 1 after the others are
written). make_result.py refuses a RESULT.json while any survivor lacks its review, so a skipped survivor blocks the
record until its cause is resolved and this script reruns, or until the run is recorded as stopped
(recipes/saturation-sweep.md section 4). `gh auth status` must already pass.
A Hugging Face model repository (https://huggingface.co/<namespace>/<name>, which a model layer can keep) is reviewed
at the commit of its default revision: the Hub's model-info endpoint /api/models/<repo_id> (the one huggingface_hub's
HfApi.model_info calls) gives the commit, the model card's license and the repository state, and the model card is
read at that commit through the documented "Resolve a file" endpoint /<repo_id>/resolve/<sha>/README.md. Both are
anonymous GETs (no token is read or sent), and the card's YAML metadata block is not excerpted. Its review is named
hf-<namespace>-<name>.json.
A skill survivor of the skills modality (owner/repo@name, a skills-* layer) is reviewed at the SKILL.md that the
manifest's pinned skills CLI installs for `npx skills@1.7.0 add owner/repo --skill <name>`, at the commit the refuters
judged: the survivor's pin, which convert.py copies with the proposal's skill_md_sha256 into survivors.json. A pin gh
cannot read falls back to the default branch's commit, and the review says so; a SKILL.md whose sha256 differs from
the survivor's skill_md_sha256 is reported and skipped. The SKILL.md is found in the git tree at that commit in the
CLI's discovery order (cli_skill_dir; vercel-labs/skills v1.7.0 discoverSkills, README "Skill Discovery"): a folder
outside the CLI's locations, such as docs/<lang>/skills/<name>, is never taken, and only two same-named folders in the
first location that holds one are ambiguous. A folder's name stands for the skill's name (the Agent Skills
specification requires them to match, https://agentskills.io/specification), and the chosen SKILL.md's name field is
checked. The review records the SKILL.md's path, sha256 and size, its disable-model-invocation flag as Claude Code
reads a boolean field (true, yes, on or 1 in any letter case, https://code.claude.com/docs/en/skills, frontmatter
reference), and the implicit-invocation policy Codex reads from the agents/openai.yaml beside it (openai_yaml_policy;
https://developers.openai.com/codex/skills), and excerpts the SKILL.md body without its frontmatter. Its repository
field is <full_name>@<name>, the survivor's identity, and it is named <owner>-<repo>-<name>.json.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import posixpath
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_common import slug  # noqa: E402

OWNER_REPO = re.compile(r"[a-z0-9-]+/[a-z0-9._-]+")
HUB = "https://huggingface.co"
HUB_MODEL = re.compile(r"https://huggingface\.co/([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)/?")
# First path segments that are Hub sections, never a model repository's namespace.
HUB_SECTIONS = {"api", "blog", "buckets", "collections", "containers", "datasets", "docs", "models", "organizations",
                "papers", "settings", "spaces"}
HUB_DEFAULT_REVISION = "main"  # huggingface_hub constants.DEFAULT_REVISION
# huggingface_hub repocard.REGEX_YAML_BLOCK: the card's metadata block, which may follow leading whitespace.
CARD_METADATA = re.compile(r"^(\s*---(?:\r\n|\r|\n))([\S\s]*?)((?:\r\n|\r|\n)---[ \t]*(\r\n|\n|$))")
HEX40 = re.compile(r"[0-9a-f]{40}")
# A skills-modality survivor: owner/repo@name (schemas/discover-skills.json skill_ref).
SKILL_REF = re.compile(r"([A-Za-z0-9-]+/[A-Za-z0-9._-]+)@([a-z0-9-]+)")
# A top-level `key: value` line of a SKILL.md frontmatter block, and a simple (optionally quoted) YAML mapping key.
FRONTMATTER_KEY = re.compile(r"([A-Za-z0-9_-]+):(?:[ \t]+(.*))?")
YAML_KEY = re.compile(r"""(?P<key>[A-Za-z_][A-Za-z0-9_-]*|"[A-Za-z_][A-Za-z0-9_-]*"|'[A-Za-z_][A-Za-z0-9_-]*')"""
                      r"[ \t]*:(?:[ \t]+(?P<value>.*))?")
# Claude Code's boolean frontmatter fields accept true, yes, on and 1 (and false, no, off, 0) in any letter case
# (https://code.claude.com/docs/en/skills, frontmatter reference: "Boolean fields accept ...", since v2.1.218).
CLAUDE_TRUE = ("true", "yes", "on", "1")
# Codex rust-v0.157.1 (commit 36650394c5b38c2990ccf2a3457165ca3e9d9726) reads agents/openai.yaml with serde_yaml into
# {interface, dependencies, policy: {allow_implicit_invocation: Option<bool>, products}} and ignores the whole file
# when it cannot (codex-rs/ext/skills/src/loader/metadata.rs lines 27-56 and 130-139: "Fail open"), so implicit
# invocation stays allowed (codex-rs/skills/src/model.rs allows_implicit_invocation: unwrap_or(true)). Its lockfile's
# serde_yaml 0.9.34 (tag commit 2009506d33767dfc88e979d6bc0d53d09f941c94, src/de.rs) reads a bool only from a plain
# true/True/TRUE or false/False/FALSE (parse_bool, lines 932-938) and None from an empty or null/Null/NULL/~ plain
# scalar (deserialize_option, lines 1517-1558; parse_null, lines 925-930); a quoted or any other scalar is a type error.
SERDE_YAML_BOOL = {"true": True, "True": True, "TRUE": True, "false": False, "False": False, "FALSE": False}
SERDE_YAML_NULL = ("", "~", "null", "Null", "NULL")
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
    for a Hugging Face model, so the same model with and without a trailing slash gets one review. A skill ref
    (owner/repo@name) is its own lowercased key: slug leaves it whole."""
    repo_id = hub_model(repository)
    return f"hf:{repo_id.lower()}" if repo_id else slug(repository)


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


# --------------------------------------------------------------------------- YAML scalars and the two flag files


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


def frontmatter_scalars(yaml_text: str) -> dict:
    """The top-level `key: value` pairs of a SKILL.md frontmatter block: a quoted value's content, or a plain value
    without its trailing comment (`name: find-bugs  # note` is find-bugs). A key whose value starts on the next,
    indented line gets that line's text, enough to tell that the key has a value."""
    out, lines = {}, yaml_text.splitlines()
    for index, line in enumerate(lines):
        match = FRONTMATTER_KEY.fullmatch(line.rstrip())
        if not match:
            continue
        value = yaml_scalar(match.group(2) or "")[0]
        if not value:
            following = next((item for item in lines[index + 1:] if item.strip()), "")
            if following[:1] in (" ", "\t"):
                value = yaml_scalar(following.strip())[0]
        out[match.group(1)] = value
    return out


def claude_true(value) -> bool:
    """A Claude Code boolean frontmatter field that is true: true, yes, on or 1 in any letter case (CLAUDE_TRUE)."""
    return str(value or "").strip().lower() in CLAUDE_TRUE


def flow_entries(flow: str) -> dict | None:
    """{key: value text} of a YAML flow mapping ("{a: b, c: [d]}"), split at its top-level commas; None when the text
    is not one flow mapping."""
    flow = flow.strip()
    if not (flow.startswith("{") and flow.endswith("}")):
        return None
    items, current, depth, quote = [], "", 0, None
    for char in flow[1:-1]:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(current)
            current = ""
            continue
        current += char
    items.append(current)
    out = {}
    for item in (item.strip() for item in items):
        if item:
            key, _, value = item.partition(":")
            out[key.strip().strip("'\"")] = value.strip()
    return out


def openai_yaml_policy(text: str) -> tuple[bool, str | None, str]:
    """(implicit invocation allowed, the policy.allow_implicit_invocation value as written or None, how Codex reads it)
    for an agents/openai.yaml, as Codex rust-v0.157.1 reads it with serde_yaml (see SERDE_YAML_BOOL). The documented
    shape is a top-level `policy:` mapping, in block form (an indented `allow_implicit_invocation: false`) or flow form
    (`policy: {allow_implicit_invocation: false}`). Only a plain true or false is a boolean; a missing or null value
    leaves the default true; any other value, or a file serde_yaml cannot read (a tab-indented line, a repeated
    policy key, a policy that is not a mapping), makes Codex ignore the whole file, which also leaves the default. Type
    errors in the file's other fields, which Codex handles the same way, are not checked here."""
    ignored = "Codex cannot deserialize the file and ignores it, so implicit invocation stays allowed"
    lines = []
    for raw_line in text.splitlines():
        body = strip_yaml_comment(raw_line)
        if not body.strip() or (body in ("---", "...")):
            continue
        indent = len(body) - len(body.lstrip(" \t"))
        if "\t" in body[:indent]:
            return True, None, f"a tab indents a line: {ignored}"
        lines.append((indent, body.strip()))

    def key_of(body):
        match = YAML_KEY.fullmatch(body)
        return (match.group("key").strip("'\""), match.group("value") or "") if match else (None, "")

    tops = [position for position, (indent, body) in enumerate(lines) if indent == 0 and key_of(body)[0] == "policy"]
    if not tops:
        return True, None, "no policy mapping: Codex defaults allow_implicit_invocation to true"
    if len(tops) > 1:
        return True, None, f"policy appears twice: {ignored}"
    rest = key_of(lines[tops[0]][1])[1]
    value = MISSING
    if rest.startswith("{"):
        flow, following = rest, tops[0] + 1
        while flow.count("{") > flow.count("}") and following < len(lines):  # a flow mapping over several lines
            flow, following = f"{flow} {lines[following][1]}", following + 1
        entries = flow_entries(flow)
        if entries is None:
            return True, None, f"policy is not a mapping serde_yaml reads: {ignored}"
        value = entries.get("allow_implicit_invocation", MISSING)
    elif rest:
        scalar, quoted = yaml_scalar(rest)
        if not quoted and scalar in SERDE_YAML_NULL:
            return True, None, "policy is null: Codex defaults allow_implicit_invocation to true"
        return True, None, f"policy is {rest!r}, not a mapping: {ignored}"
    else:
        block = []
        for indent, body in lines[tops[0] + 1:]:
            if indent == 0:
                break
            block.append((indent, body))
        if not block:
            return True, None, "policy is null: Codex defaults allow_implicit_invocation to true"
        if block[0][1].startswith("-"):
            return True, None, f"policy is a list, not a mapping: {ignored}"
        child = block[0][0]
        for position, (indent, body) in enumerate(block):
            key, raw_value = key_of(body)
            if indent != child or key != "allow_implicit_invocation":
                continue  # only a direct child of policy counts
            if value is not MISSING:
                return True, None, f"allow_implicit_invocation appears twice under policy: {ignored}"
            nested = position + 1 < len(block) and block[position + 1][0] > child
            value = "{" if not raw_value and nested else raw_value
    if value is MISSING:
        return True, None, "no policy.allow_implicit_invocation: Codex defaults it to true"
    if value.startswith(("{", "[")):
        return True, value, f"allow_implicit_invocation holds a mapping or list: {ignored}"
    scalar, quoted = yaml_scalar(value)
    if not quoted and scalar in SERDE_YAML_NULL:
        return True, scalar or None, "policy.allow_implicit_invocation is null: Codex defaults it to true"
    if not quoted and scalar in SERDE_YAML_BOOL:
        return SERDE_YAML_BOOL[scalar], scalar, f"policy.allow_implicit_invocation: {scalar}"
    return True, value, (f"allow_implicit_invocation {value} is not a YAML boolean serde_yaml reads (a plain true or "
                         f"false): {ignored}")


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


def cli_skill_dir(skill_dirs, name: str, plugin_dirs=()) -> tuple[str | None, str]:
    """(folder, where) of the skill <name> as discoverSkills finds it without --full-depth, or (None, why not). The
    root SKILL.md is decided before this (a valid one is the repository's only skill). The CLI searches the root's
    child folders, then each of CLI_CONTAINERS three levels deep, then each plugin folder one level deep, and only when
    none of them holds a SKILL.md, every folder up to five levels deep. A name found in one location is skipped in the
    later ones, so the first location that holds a folder named <name> decides; two such folders in that location are
    ambiguous (the CLI keeps whichever its directory listing returns first), as are two unnested ones in the fallback.
    A folder anywhere else (docs/<lang>/skills/<name>, examples/) needs --full-depth and is never taken."""
    parsed, found_any = set(), False
    locations = [("", 1), *((container, CLI_CONTAINER_DEPTH) for container in CLI_CONTAINERS),
                 *((folder, 1) for folder in plugin_dirs)]
    for container, depth in locations:
        found = [folder for folder in cli_walk(container, depth, skill_dirs) if folder not in parsed]
        parsed.update(found)
        found_any = found_any or bool(found)
        matches = [folder for folder in found if folder.rsplit("/", 1)[-1] == name]
        where = f"{container}/" if container else "the repository root"
        if len(matches) == 1:
            return matches[0], f"{where}, the first location the CLI searches that holds a folder named {name}"
        if matches:
            return None, (f"{len(matches)} folders named {name} in {where}, the first location the CLI searches that "
                          f"holds one: {matches} (the CLI keeps whichever its directory listing returns first)")
    if found_any:
        return None, f"no folder named {name} in the locations the CLI searches without --full-depth"
    candidates = [folder for folder in skill_dirs if folder and folder.count("/") < CLI_FALLBACK_DEPTH
                  and folder.rsplit("/", 1)[-1] == name and not CLI_SKIP_DIRS.intersection(folder.split("/"))]
    candidates = sorted(folder for folder in candidates
                        if not any(folder.startswith(f"{other}/") for other in candidates))
    if len(candidates) == 1:
        return candidates[0], "the recursive search the CLI runs when no location it searches holds a skill"
    if candidates:
        return None, (f"{len(candidates)} unnested folders named {name} in the CLI's recursive search: {candidates} "
                      "(the CLI keeps whichever its directory listing returns first)")
    return None, f"no folder named {name} holds a SKILL.md"


# --------------------------------------------------------------------------- skill reviews


def gh_file(full: str, path: str, commit: str) -> bytes:
    content = gh(f"repos/{full}/contents/{urllib.parse.quote(path, safe='/')}?ref={commit}")
    return base64.b64decode(content["content"])


def gh_json_file(full: str, path: str, commit: str):
    try:
        return json.loads(gh_file(full, path, commit))
    except ValueError:
        return None  # the CLI skips a manifest that is not JSON


def skill_review(owner_repo: str, name: str, layers: list, lane: str, fit_models: str, pin=None,
                 expected_sha256=()) -> dict:
    meta = gh(f"repos/{owner_repo}")
    full, branch = meta["full_name"], meta["default_branch"]
    commit, fallback = None, None
    if pin:
        try:
            commit = gh(f"repos/{full}/commits/{pin}")["sha"]
        except GhError as error:
            fallback = f"the adjudicated pin {pin} is unreadable ({error})"
    else:
        fallback = "the survivor names no adjudicated pin"
    if commit is None:
        commit = gh(f"repos/{full}/commits/{branch}")["sha"]
    tree = gh(f"repos/{full}/git/trees/{commit}?recursive=1")
    if tree.get("truncated"):
        raise GhError(f"{full}@{name}: the git tree at {commit} is truncated, so the CLI's discovery order cannot be "
                      "followed")
    blobs = {entry["path"] for entry in tree.get("tree") or [] if isinstance(entry, dict)
             and entry.get("type") == "blob" and isinstance(entry.get("path"), str)}
    skill_dirs = {path[:-len("/SKILL.md")] for path in blobs if path.endswith("/SKILL.md")}
    skill_path, raw, found_by = None, None, None
    if "SKILL.md" in blobs:  # a valid root SKILL.md is the only skill the CLI discovers (discoverSkills returns early)
        raw = gh_file(full, "SKILL.md", commit)
        metadata = CARD_METADATA.search(raw.decode("utf-8", "replace"))
        root = frontmatter_scalars(metadata.group(2)) if metadata else {}
        if root.get("name") and root.get("description"):
            if root["name"].lower() != name.lower():
                raise GhError(f"{full}@{name}: the root SKILL.md at {commit} is the skill {root['name']!r}, the only one "
                              "the skills CLI discovers in this repository without --full-depth")
            skill_path, found_by = "SKILL.md", "the repository root's SKILL.md, the only skill the CLI discovers there"
        else:
            raw = None  # no name or description: the CLI skips it and searches on
    if skill_path is None:
        plugin_dirs = cli_plugin_dirs(*(gh_json_file(full, path, commit) if path in blobs else None
                                        for path in PLUGIN_MANIFESTS))
        folder, found_by = cli_skill_dir(skill_dirs, name, plugin_dirs)
        if folder is None:
            raise GhError(f"{full}@{name} at {commit}: {found_by}")
        skill_path = f"{folder}/SKILL.md"
    raw = raw if raw is not None else gh_file(full, skill_path, commit)
    digest = hashlib.sha256(raw).hexdigest()
    mismatched = sorted({value for value in expected_sha256 if value and value != digest})
    if mismatched:
        raise GhError(f"{full}@{name}: {skill_path} at {commit} has sha256 {digest}, not the survivor's skill_md_sha256 "
                      f"{', '.join(mismatched)}: the review would describe other bytes than the refuters judged")
    text = raw.decode("utf-8", "replace")
    metadata = CARD_METADATA.search(text)
    fields = frontmatter_scalars(metadata.group(2)) if metadata else {}
    if fields.get("name") and fields["name"].lower() != name.lower():
        raise GhError(f"{full}@{name}: {skill_path} at {commit} declares name {fields.get('name')!r}")
    folder = skill_path.rsplit("/", 1)[0] if "/" in skill_path else ""
    yaml_path = f"{folder}/agents/openai.yaml" if folder else "agents/openai.yaml"
    if yaml_path in blobs:
        implicit, policy_value, policy_note = openai_yaml_policy(gh_file(full, yaml_path, commit).decode("utf-8",
                                                                                                          "replace"))
    else:
        implicit, policy_value, policy_note = True, None, "no agents/openai.yaml: Codex allows implicit invocation"
    repository_license = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    license_id = fields.get("license") or repository_license
    at = "the adjudicated pin" if fallback is None else f"the default branch's commit, because {fallback}"
    checked = "; its sha256 matches the survivor's skill_md_sha256" if any(expected_sha256) else ""
    return {"schema_version": 1, "id": f"source-review-{review_name(f'{full}@{name}')}", "kind": "upstream_provenance",
            "evidence_class": "source_review", "repository": f"{full}@{name}", "reviewed_commit": commit,
            "readme_path": skill_path, "license": license_id, "layers": sorted(set(layers)),
            "claim": (f"Source review of the skill {name} in {full} at commit {commit} ({at}; license {license_id}), "
                      f"read from {skill_path}" + (f" and {yaml_path}" if yaml_path in blobs else "") + " at that "
                      f"commit, the SKILL.md the pinned skills CLI (vercel-labs/skills v1.7.0) discovers for "
                      f"{name}{checked}. Survived the {lane} facts refuter and both fit refuters ({fit_models}); no "
                      "install, invocation, benchmark or comparison with an installed skill."),
            "observed": {"stars": meta.get("stargazers_count"), "pushed_at": meta.get("pushed_at"),
                         "archived": meta.get("archived"), "default_branch": branch,
                         "repository_license": repository_license,
                         "adjudicated_pin": pin, "reviewed_at_pin": fallback is None, "pin_fallback": fallback,
                         "skill_md_found_by": found_by,
                         "skill_md_sha256": digest, "skill_md_bytes": len(raw),
                         "survivor_skill_md_sha256": sorted({value for value in expected_sha256 if value}) or None,
                         "disable_model_invocation": claude_true(fields.get("disable-model-invocation")),
                         "openai_yaml_path": yaml_path if yaml_path in blobs else None,
                         "allow_implicit_invocation": implicit,
                         "openai_yaml_policy_value": policy_value, "openai_yaml_policy_note": policy_note},
            "documentation_excerpts": excerpts_from(text[metadata.end():] if metadata else text,
                                                    f"{skill_path}@{commit}")}


def review(repository: str, layers: list, lane: str, fit_models: str, pin=None, expected_sha256=()) -> dict:
    repo_id = hub_model(repository)
    if repo_id:
        return hub_review(repo_id, layers, lane, fit_models)
    skill = SKILL_REF.fullmatch(str(repository or "").strip())
    if skill:
        return skill_review(skill.group(1), skill.group(2), layers, lane, fit_models, pin, expected_sha256)
    owner_repo = slug(repository)
    if not OWNER_REPO.fullmatch(owner_repo):
        raise GhError(f"{repository} is neither a GitHub repository nor a Hugging Face model repository URL")
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
    args = parser.parse_args(argv)
    survivors = json.loads(args.survivors.read_text(encoding="utf-8"))
    # Review key -> the survivor URL first seen and every layer it survived in. A skill is reviewed once per adjudicated
    # pin (<skill key>#<pin>): the same skill judged at two commits in two layers gets two reviews.
    by_repo: dict[str, dict] = {}
    for survivor in survivors:
        pin = survivor.get("pin") if SKILL_REF.fullmatch(str(survivor["repository"]).strip()) else None
        key = repository_key(survivor["repository"]) + (f"#{pin}" if pin else "")
        item = by_repo.setdefault(key, {"repository": survivor["repository"], "layers": [], "pin": pin,
                                        "skill_md_sha256": set()})
        item["layers"].append(survivor["layer_id"])
        if survivor.get("skill_md_sha256"):
            item["skill_md_sha256"].add(survivor["skill_md_sha256"])
    written, failed, docs = [], [], {}
    for key, item in sorted(by_repo.items()):
        try:
            docs[key] = review(item["repository"], item["layers"], args.lane, args.fit_models, item["pin"],
                               sorted(item["skill_md_sha256"]))
        except (GhError, KeyError, ValueError) as error:
            failed.append(f"{item['repository']}: {error}")
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
                failed.append(f"{by_repo[key]['repository']}: {path} already holds a review of another repository; "
                              "not overwritten")
                continue
        path.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append({"repository": doc["repository"], "path": path.name, "layers": doc["layers"]})
    print(json.dumps(written, indent=1))
    for line in failed:
        print(f"source_reviews.py: {line}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
