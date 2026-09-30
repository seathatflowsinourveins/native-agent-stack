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
check refuses it (pin_lookup ok): no valid copy, an ambiguous copy, other SKILL.md bytes than the judged ones, or a
git tree that does not cover the bytes read. make_result.py stops that layer: its RESULT.json cannot complete.
The SKILL.md is found in the git tree at the pin in the CLI's discovery order (cli_skill_dir; vercel-labs/skills v1.7.0
discoverSkills, README "Skill Discovery"): a folder outside the CLI's locations, such as docs/<lang>/skills/<name>, is
never taken. Like the CLI (parseSkillMd), each candidate SKILL.md is validated before the order applies: without a
name and a description, both non-empty strings, it is skipped and recorded with its reason, so a valid later copy
wins, and a skill whose every copy is invalid is refused; only two valid same-named folders in the first location
that holds a valid one are ambiguous. A folder's name stands for the skill's name (the Agent Skills specification
requires them to match, https://agentskills.io/specification), and a copy whose name field names another skill is not
a copy (filterSkills matches --skill against that field). The review records the SKILL.md's path, sha256 and size, the
copies skipped on the way, the skill folder's git tree id at the pin (skill_folder_tree_sha: the id the CLI's lock
records as skillFolderHash, verified to cover the SKILL.md and agents/openai.yaml bytes read), its
disable-model-invocation flag as Claude Code reads a boolean field (true, yes, on or 1 in any letter case,
https://code.claude.com/docs/en/skills, frontmatter reference), and the implicit-invocation policy Codex reads from the
agents/openai.yaml beside it (openai_yaml_policy, https://developers.openai.com/codex/skills: codex_implicit, null with
unverified_reason when the reader cannot tell), and excerpts the SKILL.md body without its frontmatter. Its repository
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

try:  # PyYAML, when installed, reads agents/openai.yaml (openai_yaml_policy); the repository does not require it
    import yaml
except ImportError:  # the subset reader then decides, or says it cannot
    yaml = None

OWNER_REPO = re.compile(r"[a-z0-9-]+/[a-z0-9._-]+")
HUB = "https://huggingface.co"
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
# vercel-labs/skills v1.7.0 src/frontmatter.ts parseFrontmatter: the frontmatter block starts the file.
SKILL_MD_FRONTMATTER = re.compile(r"---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)\Z")
# ...parsed by the yaml package (^2.8.3, 2.9.0 in its lockfile) as YAML 1.2 with the core schema (eemeli/yaml v2.9.0
# src/options.ts: version "1.2" by default; src/doc/Document.ts setSchema: 1.2 is "core"), whose plain scalars that
# match these (src/schema/common/null.ts, core/bool.ts, core/int.ts, core/float.ts) are not strings.
YAML12_NULL = re.compile(r"(?:~|[Nn]ull|NULL)?")
YAML12_BOOL = re.compile(r"[Tt]rue|TRUE|[Ff]alse|FALSE")
YAML12_NUMBER = re.compile(r"[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+|[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
                           r"|[-+]?\.(?:inf|Inf|INF)|\.nan|\.NaN|\.NAN")
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


# --------------------------------------------------------------------------- YAML scalars and frontmatter lines


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


def frontmatter_values(yaml_text: str) -> dict:
    """{key: (value, quoted)} of the top-level `key: value` lines of a SKILL.md frontmatter block: a quoted value's
    content, or a plain value without its trailing comment (`name: find-bugs  # note` is find-bugs). A key whose value
    starts on the next, indented line gets that line's text, enough to tell that the key has a value."""
    out, lines = {}, yaml_text.splitlines()
    for index, line in enumerate(lines):
        match = FRONTMATTER_KEY.fullmatch(line.rstrip())
        if not match:
            continue
        value, quoted = yaml_scalar(match.group(2) or "")
        if not value and not quoted:
            following = next((item for item in lines[index + 1:] if item.strip()), "")
            if following[:1] in (" ", "\t"):
                value, quoted = yaml_scalar(following.strip())
        out[match.group(1)] = (value, quoted)
    return out


def frontmatter_scalars(yaml_text: str) -> dict:
    """{key: value} of frontmatter_values."""
    return {key: value for key, (value, _) in frontmatter_values(yaml_text).items()}


def claude_true(value) -> bool:
    """A Claude Code boolean frontmatter field that is true: true, yes, on or 1 in any letter case (CLAUDE_TRUE)."""
    return str(value or "").strip().lower() in CLAUDE_TRUE


# --------------------------------------------------------------------------- SKILL.md as the skills CLI parses it


def yaml12_scalar(value: str, quoted: bool) -> tuple[str, bool]:
    """(JavaScript type, truthy) of a one-line frontmatter scalar as the yaml package's YAML 1.2 core schema reads it
    (YAML12_NULL, YAML12_BOOL, YAML12_NUMBER); a quoted scalar is a string."""
    if quoted:
        return "string", bool(value)
    if YAML12_NULL.fullmatch(value):
        return "null", False
    if YAML12_BOOL.fullmatch(value):
        return "boolean", value.lower() == "true"
    if YAML12_NUMBER.fullmatch(value):
        text = value.lower().replace(".inf", "inf").replace(".nan", "nan")
        number = int(text, 0) if text.lstrip("+-").startswith(("0x", "0o")) else float(text)
        return "number", number == number and bool(number)  # 0, -0 and NaN are falsy
    if value.startswith(("[", "{")):
        return "object", True
    return "string", bool(value)


def skill_md_problem(raw: bytes) -> str | None:
    """Why the pinned skills CLI skips this SKILL.md, or None when it takes it (vercel-labs/skills v1.7.0 src/skills.ts
    parseSkillMd, lines 80-133): the frontmatter needs a name and a description (a falsy value counts as missing), and
    both must be strings."""
    match = SKILL_MD_FRONTMATTER.match(raw.decode("utf-8", "replace"))
    fields = frontmatter_values(match.group(1)) if match else {}
    typed = {key: yaml12_scalar(*fields[key]) if key in fields else ("undefined", False)
             for key in ("name", "description")}
    missing = [key for key, (_, truthy) in typed.items() if not truthy]
    if missing:
        return f"missing required frontmatter field(s): {', '.join(missing)}"
    if any(kind != "string" for kind, _ in typed.values()):
        return (f'frontmatter "name" and "description" must be strings (got {typed["name"][0]} and '
                f'{typed["description"][0]})')
    return None


def skill_md_name(raw: bytes) -> str | None:
    """The name field of a SKILL.md's frontmatter (SKILL_MD_FRONTMATTER), or None."""
    match = SKILL_MD_FRONTMATTER.match(raw.decode("utf-8", "replace"))
    return frontmatter_scalars(match.group(1)).get("name") if match else None


# --------------------------------------------------------------------------- agents/openai.yaml as Codex reads it


class CodexIgnores(Exception):
    """serde_yaml cannot deserialize agents/openai.yaml into Codex's SkillMetadataFile, so Codex ignores the file."""

    def __init__(self, message: str, value: str | None = None):
        super().__init__(message)
        self.value = value


def openai_yaml_policy(text: str) -> tuple[bool | None, str | None, str]:
    """(codex_implicit, the policy.allow_implicit_invocation value as written or None, how Codex reads it) for an
    agents/openai.yaml, as Codex rust-v0.157.1 reads it with serde_yaml 0.9.34 (see SERDE_YAML_BOOL): false only for
    a plain false; true for a missing or null value, and for a file serde_yaml cannot deserialize, which Codex
    ignores; None when the reader cannot tell, with the reason in the note ("unverified"). With PyYAML installed its
    composer reads the file (pyyaml_policy); without it only the plain block-mapping subset is read (subset_policy).
    Type errors in the file's other fields, which also make Codex ignore it, are not checked."""
    return pyyaml_policy(text) if yaml is not None else subset_policy(text)


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
    except yaml.YAMLError as error:
        first = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
        return None, None, (f"PyYAML cannot parse the file ({first}): whether serde_yaml can, and so Codex's "
                            "implicit invocation, is unverified")
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
    """Why a one-line value is outside the plain block-mapping subset, or None."""
    if not value:
        return None
    if value[0] in "'\"":
        end = quoted_end(value)
        if end is None:
            return "a quoted scalar that continues on the next line"
        return "text after a quoted scalar" if value[end:].strip() else None
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
    for number, raw_line in enumerate(text.splitlines(), 1):
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
    """[(where, folders)] of the locations discoverSkills searches without --full-depth, in its order: the root's child
    folders, each of CLI_CONTAINERS three levels deep, then each plugin folder one level deep, each with the folders
    it finds a SKILL.md in that no earlier location found (parseSkillAt skips a SKILL.md it parsed before)."""
    parsed, locations = set(), []
    for container, depth in [("", 1), *((container, CLI_CONTAINER_DEPTH) for container in CLI_CONTAINERS),
                             *((folder, 1) for folder in plugin_dirs)]:
        found = [folder for folder in cli_walk(container, depth, skill_dirs) if folder not in parsed]
        parsed.update(found)
        locations.append((f"{container}/" if container else "the repository root", found))
    return locations


def cli_skill_dir(skill_dirs, name: str, plugin_dirs=(), inspect=None, skipped=None) -> tuple[str | None, str]:
    """(folder, where) of the skill <name> as discoverSkills finds it without --full-depth, or (None, why not). The
    root SKILL.md is decided before this (a valid one is the repository's only skill). The CLI validates a SKILL.md
    before it takes its name (parseSkillMd returns null for one without a name or description, and tryAddSkillAt then
    adds nothing), so an invalid copy never claims <name>. inspect(folder) gives (why the CLI skips that folder's
    SKILL.md or None, its name field); without it every SKILL.md is valid and named after its folder. A copy is a
    folder named <name> whose SKILL.md is valid and names <name> (filterSkills matches --skill against the name field,
    in any letter case); a folder that fails is appended to `skipped` as (folder, reason) and passed over. The first
    location that holds a copy decides; two copies there are ambiguous (the CLI keeps whichever its directory listing
    returns first). Only when no location holds a valid skill of any name (skills.length === 0) does the CLI search
    every folder up to five levels deep, where a copy shadows the copies below it and two unnested copies are
    ambiguous. A folder anywhere else (docs/<lang>/skills/<name>, examples/) needs --full-depth and is never taken."""
    inspect = inspect or (lambda folder: (None, folder.rsplit("/", 1)[-1]))
    skipped = [] if skipped is None else skipped
    named_skips = []

    def copies(folders):
        good = []
        for folder in folders:
            reason, declared = inspect(folder)
            if reason is None and str(declared or "").lower() != name.lower():
                reason = f"its name field names the skill {declared!r}, not {name}"
            if reason is None:
                good.append(folder)
            elif (folder, reason) not in skipped:
                skipped.append((folder, reason))
                named_skips.append(folder)
        return good

    locations = cli_locations(skill_dirs, plugin_dirs)
    for where, found in locations:
        matches = copies([folder for folder in found if folder.rsplit("/", 1)[-1] == name])
        if len(matches) == 1:
            return matches[0], f"{where}, the first location the CLI searches that holds a valid folder named {name}"
        if matches:
            return None, (f"{len(matches)} folders named {name} in {where}, the first location the CLI searches that "
                          f"holds a valid one: {matches} (the CLI keeps whichever its directory listing returns first)")
    # Any valid SKILL.md in the locations stops the fallback; inspected in the CLI's order up to the first valid one.
    if any(inspect(folder)[0] is None for _, found in locations for folder in found):
        if named_skips:
            return None, (f"every copy of {name} in the locations the CLI searches without --full-depth is invalid, "
                          "and a valid skill there keeps the CLI from searching further")
        return None, f"no folder named {name} in the locations the CLI searches without --full-depth"
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
    content = gh(f"repos/{full}/contents/{urllib.parse.quote(path, safe='/')}?ref={commit}")
    return base64.b64decode(content["content"])


def gh_json_file(full: str, path: str, commit: str):
    try:
        return json.loads(gh_file(full, path, commit))
    except ValueError:
        return None  # the CLI skips a manifest that is not JSON


def git_blob_id(data: bytes) -> str:
    """git's object id of a blob (git hash-object): the sha1 of "blob <size>\\0" and the bytes."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


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
    blobs = {entry["path"] for entry in tree.get("tree") or [] if isinstance(entry, dict)
             and entry.get("type") == "blob" and isinstance(entry.get("path"), str)}
    skill_dirs = {path[:-len("/SKILL.md")] for path in blobs if path.endswith("/SKILL.md")}
    files = {}  # SKILL.md path -> (bytes or None, why the CLI skips it or None)

    def read(path):
        if path not in files:
            try:
                raw = gh_file(full, path, pin)
            except GhError as error:
                files[path] = (None, f"failed to read file: {error}")  # parseSkillMd skips an unreadable file
            else:
                files[path] = (raw, skill_md_problem(raw))
        return files[path]

    def inspect(folder):
        raw, problem = read(f"{folder}/SKILL.md")
        return problem, skill_md_name(raw) if raw is not None else None

    skipped, skill_path, found_by = [], None, None
    if "SKILL.md" in blobs:  # a valid root SKILL.md is the only skill the CLI discovers (discoverSkills returns early)
        raw, problem = read("SKILL.md")
        if problem is None:
            root_name = skill_md_name(raw)
            if root_name.lower() != name.lower():
                raise GhError(f"{full}@{name}: the root SKILL.md at {pin} is the skill {root_name!r}, the only one the "
                              "skills CLI discovers in this repository without --full-depth")
            skill_path, found_by = "SKILL.md", "the repository root's SKILL.md, the only skill the CLI discovers there"
        else:
            skipped.append(("", problem))  # the CLI skips it and searches on
    if skill_path is None:
        plugin_dirs = cli_plugin_dirs(*(gh_json_file(full, path, pin) if path in blobs else None
                                        for path in PLUGIN_MANIFESTS))
        folder, found_by = cli_skill_dir(skill_dirs, name, plugin_dirs, inspect, skipped)
        if folder is None:
            detail = "; ".join(f"{f'{each}/' if each else ''}SKILL.md: {why}" for each, why in skipped)
            raise GhError(f"{full}@{name} at {pin}: {found_by}" + (f" (skipped: {detail})" if detail else ""))
        skill_path = f"{folder}/SKILL.md"
    raw = read(skill_path)[0]
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise GhError(f"{full}@{name}: {skill_path} at {pin} has sha256 {digest}, not the survivor's skill_md_sha256 "
                      f"{expected}: the review would describe other bytes than the refuters judged")
    text = raw.decode("utf-8", "replace")
    frontmatter = SKILL_MD_FRONTMATTER.match(text)
    fields = frontmatter_scalars(frontmatter.group(1)) if frontmatter else {}
    folder = skill_path.rsplit("/", 1)[0] if "/" in skill_path else ""
    yaml_path = f"{folder}/agents/openai.yaml" if folder else "agents/openai.yaml"
    read_bytes = {skill_path: raw}
    if yaml_path in blobs:
        read_bytes[yaml_path] = gh_file(full, yaml_path, pin)
        implicit, policy_value, policy_note = openai_yaml_policy(read_bytes[yaml_path].decode("utf-8", "replace"))
    else:
        implicit, policy_value, policy_note = True, None, "no agents/openai.yaml: Codex allows implicit invocation"
    folder_sha = skill_folder_tree_sha(tree, folder, read_bytes)
    repository_license = (meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
    license_id = fields.get("license") or repository_license
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
                         "skill_folder_tree_sha": folder_sha,
                         "disable_model_invocation": claude_true(fields.get("disable-model-invocation")),
                         "openai_yaml_path": yaml_path if yaml_path in blobs else None,
                         "openai_yaml_reader": openai_yaml_reader() if yaml_path in blobs else None,
                         "codex_implicit": implicit, "unverified_reason": policy_note if implicit is None else None,
                         "openai_yaml_policy_value": policy_value, "openai_yaml_policy_note": policy_note},
            "documentation_excerpts": excerpts_from(frontmatter.group(2) if frontmatter else text,
                                                    f"{skill_path}@{pin}")}


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
