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
check refuses it (pin_lookup ok): no valid copy, an ambiguous copy, a copy whose verdict the reader cannot tell, other
SKILL.md bytes than the judged ones, or a git tree that does not cover the bytes read. make_result.py stops that
layer: its RESULT.json cannot complete.
The SKILL.md is found in the git tree at the pin in the CLI's discovery order (cli_skill_dir; vercel-labs/skills v1.7.0
discoverSkills, README "Skill Discovery"): a folder outside the CLI's locations, such as docs/<lang>/skills/<name>, is
never taken. Like the CLI (parseSkillMd), each candidate SKILL.md is validated before the order applies: its
frontmatter is typed as the CLI's yaml package types it (YAML 1.2, core schema), by PyYAML's composer when PyYAML is
installed and else by a subset reader (skill_md_check), and a copy without a name and a description that are both
non-empty strings (a list or a mapping is not one) is skipped and recorded with its reason, so a valid later copy
wins, and a skill whose every copy is invalid is refused. A copy the reader cannot type (an anchor, alias or tag, an
escape YAML does not define, a key given twice, a construct outside the subset) is not guessed at: when its verdict
decides which copy the CLI takes, no review is written and the survivor is stopped (pin_lookup ok); so is one whose
SKILL.md gh cannot read. Only two valid same-named folders in the first location that holds a valid one are
ambiguous. A folder's name stands for the skill's name (the Agent Skills specification requires them to match,
https://agentskills.io/specification), and a copy whose name, as the CLI records it (sanitizeMetadata), names another
skill is not a copy (filterSkills matches --skill against it). The review records the SKILL.md's path, sha256 and
size, the copies skipped on the way, the skill folder's git tree id at the pin (skill_folder_tree_sha: the id the
CLI's lock records as skillFolderHash, verified to cover the SKILL.md and agents/openai.yaml bytes read), its
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
# YAML 1.2's double-quoted escapes (c-ns-esc-char), the set both parsers define: unsafe-libyaml 0.2.11, the libyaml
# port serde_yaml 0.9.34 parses with (tag commit a7b8d1fbd93aefbca3003dcb5fcc6a9c2297e968, src/scanner.rs lines
# 2195-2317: any other escape is "found unknown escape character"), and the yaml package 2.9.0 (tag commit
# ddb21b04cb889722cec8f89dc1b67f19d62d7f7d, src/compose/resolve-flow-scalar.ts escapeCodes, lines 208-227: any other
# is the error BAD_DQ_ESCAPE, line 172). \x, \u and \U take exactly 2, 4 and 8 hex digits (scanner.rs line 2341;
# parseCharCode, lines 229-245), and a code point beyond U+10FFFF is refused by both; libyaml also refuses a surrogate
# (U+D800 to U+DFFF, scanner.rs lines 2355-2361), which the yaml package's String.fromCodePoint takes.
YAML_ESCAPES = {"0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r",
                "e": "\x1b", " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": chr(0x2028),
                "P": chr(0x2029)}
YAML_HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
SURROGATE = re.compile("[\ud800-\udfff]")
# What starts a YAML value other than a plain scalar (a -, ? or : does only when a space or the line end follows).
PLAIN_INDICATORS = frozenset(",[]{}#&*!|>'\"%@`")
NODE_PROPERTIES = {"&": "an anchor", "*": "an alias", "!": "a tag"}
# A block mapping's key ends at the first ':' that a space, a tab or the line end follows.
IMPLICIT_KEY_END = re.compile(r":(?=[ \t]|$)")
BLOCK_HEADER = re.compile(r"([|>])([-+]?)")  # a block scalar header without an indentation indicator
BLOCK_HEADER_ANY = re.compile(r"[|>](?:[1-9][-+]?|[-+][1-9]?)?")
# vercel-labs/skills v1.7.0 src/sanitize.ts: stripTerminalEscapes (lines 44-52, its expressions at lines 19-36, applied
# in this order) and sanitizeMetadata (lines 61-65), which records a SKILL.md's name; JavaScript's trim() removes these.
TERMINAL_ESCAPES = tuple(re.compile(pattern) for pattern in (
    r"\x1b\][\s\S]*?(?:\x07|\x1b\\)", r"\x1b[P^_][\s\S]*?(?:\x1b\\)", r"\x1b\[[\x30-\x3f]*[\x20-\x2f]*[\x40-\x7e]",
    r"\x1b[\x20-\x7e]", r"[\x80-\x9f]", r"[\x00-\x06\x07\x08\x0b\x0c\x0d-\x1a\x1c-\x1f\x7f]"))
JS_WHITESPACE = "\t\n\v\f\r \xa0" + "".join(map(chr, (0x1680, *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F,
                                                       0x3000, 0xFEFF)))
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


def double_quoted_value(body: str, surrogates: bool) -> tuple[str | None, str | None]:
    """(value, None) of the text between the quotes of a one-line double-quoted scalar, or (None, why not): an escape
    outside YAML_ESCAPES and YAML_HEX_ESCAPES, a hex escape without its digits, or a code point beyond U+10FFFF, and a
    surrogate unless `surrogates` (the yaml package takes one, libyaml does not)."""
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
            if point <= 0x10FFFF and (surrogates or not 0xD800 <= point <= 0xDFFF):
                out.append(chr(point))
                index += 2 + len(digits)
                continue
            return None, (f"a double-quoted scalar with the escape {escape}, "
                          f"{'a surrogate' if point <= 0x10FFFF else 'beyond U+10FFFF'},")
        return None, f"a double-quoted scalar with the escape {escape}, which YAML 1.2 does not define,"
    return "".join(out), None


def quoted_scalar(text: str, surrogates: bool) -> tuple[str | None, str | None]:
    """(value, None) of a quoted scalar that is the whole of text (its comment stripped), or (None, why not): it must
    close on the line with nothing after it, and a double-quoted one must use YAML's escapes (double_quoted_value)."""
    end = quoted_end(text)
    if end is None:
        return None, "a quoted scalar that continues on the next line"
    if text[end:].strip():
        return None, "text after a quoted scalar"
    if text[0] == "'":
        return text[1:end - 1].replace("''", "'"), None
    return double_quoted_value(text[1:end - 1], surrogates)


def frontmatter_values(yaml_text: str) -> dict:
    """{key: (value, quoted)} of the top-level `key: value` lines of a SKILL.md frontmatter block: a quoted value's
    content, or a plain value without its trailing comment (`name: find-bugs  # note` is find-bugs). A key whose value
    starts on the next, indented line gets that line's text. The review reads only the license and Claude Code's
    disable-model-invocation this way; whether the skills CLI takes the SKILL.md is skill_md_check's to decide."""
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


class SkillMdUnverified(GhError):
    """This reader cannot tell whether the pinned skills CLI takes a SKILL.md, so no review rests on that copy's place
    in the CLI's discovery order (skill_md_check)."""


def yaml12_value(value: str, quoted: bool) -> tuple[str, object]:
    """(JavaScript type, value) of a scalar as the yaml package's YAML 1.2 core schema reads it (YAML12_NULL,
    YAML12_BOOL, YAML12_NUMBER); a quoted or block scalar is a string."""
    if quoted:
        return "string", value
    if YAML12_NULL.fullmatch(value):
        return "null", None
    if YAML12_BOOL.fullmatch(value):
        return "boolean", value.lower() == "true"
    if YAML12_NUMBER.fullmatch(value):
        text = value.lower().replace(".inf", "inf").replace(".nan", "nan")
        return "number", int(text, 0) if text.lstrip("+-").startswith(("0x", "0o")) else float(text)
    return "string", value


def js_truthy(typed: tuple[str, object]) -> bool:
    """Whether JavaScript takes a yaml12_value as true: "", 0, -0, NaN, false, null and undefined do not, an object
    (an array or a mapping) does."""
    kind, value = typed
    if kind == "number":
        return value == value and value != 0
    return kind == "object" or (kind in ("string", "boolean") and bool(value))


def sanitize_metadata(text: str) -> str:
    """The name the skills CLI records for a SKILL.md, which --skill and filterSkills match (TERMINAL_ESCAPES: terminal
    escapes and control characters removed, line breaks folded into a space, trimmed as JavaScript trims)."""
    for pattern in TERMINAL_ESCAPES:
        text = pattern.sub("", text)
    return re.sub(r"[\r\n]+", " ", text).strip(JS_WHITESPACE)


def subset_doubt(number: int, what: str) -> SkillMdUnverified:
    return SkillMdUnverified(f"frontmatter line {number}: {what} is outside the subset this reader parses without "
                             "PyYAML")


def split_pair(text: str) -> tuple[str, bool, str] | None:
    """(key, quoted, value) of a one-line `key: value` (its comment stripped), or None: the key is a quoted scalar or
    a plain one ending at the first ': ' (IMPLICIT_KEY_END), and the value is the rest of the line, stripped."""
    if text[:1] in ("'", '"'):
        end = quoted_end(text)
        match = re.match(r"[ \t]*:(?:[ \t]+(.*)|$)", text[end:]) if end else None
        return (text[:end], True, (match.group(1) or "").strip()) if match else None
    match = IMPLICIT_KEY_END.search(text)
    key = text[:match.start()].rstrip() if match else ""
    if not key or plain_start_problem(key):
        return None
    return key, False, text[match.end():].strip()


def plain_start_problem(text: str) -> str | None:
    """Why text cannot start a plain scalar (PLAIN_INDICATORS), or None."""
    if text[0] in PLAIN_INDICATORS or (text[0] in "-?:" and text[1:2] in ("", " ", "\t")):
        return NODE_PROPERTIES.get(text[0]) or f"a value starting with the indicator {text[0]!r}"
    return None


def plain_problem(text: str) -> str | None:
    """Why a one-line value (its comment stripped) is not a plain scalar this reader takes, or None: it cannot start
    with an indicator, and a ': ' or a final ':' in it opens a mapping the yaml package refuses on that line."""
    return plain_start_problem(text) or ("a plain scalar holding ': '" if IMPLICIT_KEY_END.search(text) else None)


def flow_problem(text: str) -> str | None:
    """Why a one-line flow collection (its comment stripped) is not taken, or None: it must close on its line with
    nothing after it, hold no anchor, alias or tag, and each double-quoted scalar in it must use YAML's escapes. Its
    items are not otherwise checked."""
    depth, index, quote, start = 0, 0, None, 0
    while index < len(text):
        char = text[index]
        if quote:
            if quote == '"' and char == "\\":
                index += 2
                continue
            if char == quote:
                if quote == "'" and text[index + 1:index + 2] == "'":
                    index += 2
                    continue
                if quote == '"' and double_quoted_value(text[start + 1:index], True)[1]:
                    return double_quoted_value(text[start + 1:index], True)[1]
                quote = None
        elif index and text[index - 1] in " \t[{,:" and char in "'\"&*!":
            if char in NODE_PROPERTIES:
                return f"{NODE_PROPERTIES[char]} in a flow collection"
            quote, start = char, index
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth == 0:
                return "text after a flow collection" if text[index + 1:].strip() else None
        index += 1
    return "a flow collection that does not close on its line"


def value_problem(text: str) -> str | None:
    """Why a one-line value of a key other than name and description (its comment stripped) is not taken, or None."""
    if text[0] in NODE_PROPERTIES:
        return NODE_PROPERTIES[text[0]]
    if text[0] in "'\"":
        return quoted_scalar(text, True)[1]
    return flow_problem(text) if text[0] in "[{" else plain_problem(text)


def subset_plain(lines) -> tuple[str, object]:
    """A plain scalar over (line number, text, after a comment) lines: typed by the core schema on one line, a string
    over several. Its first line must start a plain scalar; a later line may start with any character but # (YAML 1.2
    ns-plain-char), and no line may hold ': ' or follow a comment, which ends the scalar (the yaml package then
    refuses the next line)."""
    for position, (number, text, after_comment) in enumerate(lines):
        why = ("a comment inside a multi-line plain scalar" if after_comment else plain_problem(text) if position == 0
               else "a plain scalar holding ': '" if IMPLICIT_KEY_END.search(text) else None)
        if why:
            raise subset_doubt(number, why)
    if len(lines) == 1:
        return yaml12_value(lines[0][1], False)
    return "string", " ".join(text for _, text, _ in lines)


def subset_block_scalar(number: int, header: str, block) -> tuple[str, object]:
    """A literal or folded block scalar (header |, |-, >, >- and so on) over the (line number, raw text) lines of its
    key's block: a string, "" without text. An indentation indicator, a keep-chomped scalar without text, a leading
    empty line more indented than the text and a text line less indented than the first are left unverified."""
    match = BLOCK_HEADER.fullmatch(header)
    if not match:
        raise subset_doubt(number, f"the block scalar header {header!r}")
    filled = [(line, raw) for line, raw in block if raw.strip()]
    if not filled:
        if match.group(2) == "+":
            raise subset_doubt(number, "a keep-chomped block scalar without text")
        return "string", ""
    indent = len(filled[0][1]) - len(filled[0][1].lstrip(" "))
    for line, raw in block:
        if line < filled[0][0] and len(raw) > indent:
            raise subset_doubt(line, "an empty line more indented than the block scalar's text")
        if raw.strip() and len(raw) - len(raw.lstrip(" ")) < indent:
            raise subset_doubt(line, "a line less indented than the block scalar's first line")
    return "string", "\n".join(raw[indent:] for _, raw in block).strip("\n")


def subset_nested(block) -> None:
    """Checks the block below a key other than name and description that holds a mapping or a list, line by line:
    what value_problem refuses, and a key given twice at one indentation of one mapping (the yaml package refuses it:
    uniqueKeys). A nested block scalar's text is skipped. Nested indentation is not otherwise checked."""
    deeper, keys = None, {}  # a block scalar header's indentation; column -> the keys of the mapping open there
    for number, raw in block:
        indent = len(raw) - len(raw.lstrip(" "))
        text = strip_yaml_comment(raw).strip()
        if not text or (deeper is not None and indent > deeper):
            continue
        deeper, column = None, indent
        for level in [level for level in keys if level > column]:
            del keys[level]
        while text == "-" or text.startswith(("- ", "-\t")):
            rest = text[1:].lstrip(" \t")
            column += len(text) - len(rest)
            text = rest
            keys.pop(column, None)  # an entry opens a new mapping at its content's column
        pair = split_pair(text) if text else None
        if pair:
            key, quoted, text = pair
            typed = ("string", quoted_scalar(key, True)[0]) if quoted else yaml12_value(key, False)
            if quoted and quoted_scalar(key, True)[1]:
                raise subset_doubt(number, quoted_scalar(key, True)[1])
            if typed in keys.setdefault(column, []):
                raise SkillMdUnverified(f"frontmatter line {number}: the key {key} appears twice in one mapping, which "
                                        "the yaml package refuses (uniqueKeys)")
            keys[column].append(typed)
        if text[:1] in ("|", ">"):
            if not BLOCK_HEADER_ANY.fullmatch(text):
                raise subset_doubt(number, f"the block scalar header {text!r}")
            deeper = indent
        elif text:
            why = value_problem(text)
            if why:
                raise subset_doubt(number, why)


def subset_value(number: int, value: str, block, typed: bool, commented: bool = False) -> tuple[str, object]:
    """(JavaScript type, value) of a top-level key's value: `value`, the rest of its line (which ended in a comment
    when `commented`), and `block`, the (line number, raw text) lines below it up to the next key. Raises
    SkillMdUnverified for what the subset reader does not parse. For name and description (typed) a list, a mapping or
    a flow collection is an object without further checks: the CLI skips the copy whether the yaml package reads it
    so or refuses it."""
    if value[:1] in ("|", ">"):
        if typed:
            return subset_block_scalar(number, value, block)
        if not BLOCK_HEADER_ANY.fullmatch(value):
            raise subset_doubt(number, f"the block scalar header {value!r}")
        return "string", None
    content, commented = [], commented and bool(value)  # (line number, text, after a comment) of lines with text
    for line, raw in block:
        text = strip_yaml_comment(raw).strip()
        if text:
            content.append((line, text, commented))
        if value or content:  # a comment ends a scalar that has begun; one before it is only a comment
            commented = commented or strip_yaml_comment(raw).rstrip() != raw.rstrip()
    if not value:
        if not content:
            return "null", None
        line, first, _ = content[0]
        if first[0] in NODE_PROPERTIES:
            raise subset_doubt(line, NODE_PROPERTIES[first[0]])
        if first == "-" or first.startswith(("- ", "-\t")) or first[0] in "[{" or split_pair(first):
            if not typed:
                subset_nested(block)
            return "object", None
        if first[0] in "'\"":
            scalar, why = quoted_scalar(first, True)
            if why or len(content) > 1:
                raise subset_doubt(line, why or "a quoted scalar followed by more lines")
            return "string", scalar
        if first[0] in "|>":
            raise subset_doubt(line, "a block scalar header on the line after its key")
        return subset_plain([(line, first, False), *content[1:]])
    if value[0] in NODE_PROPERTIES:
        raise subset_doubt(number, NODE_PROPERTIES[value[0]])
    if value[0] in "[{" and typed:
        return "object", None
    if value[0] in "'\"[{":
        quoted = value[0] in "'\""
        why = quoted_scalar(value, True)[1] if quoted else flow_problem(value)
        if why or content:
            raise subset_doubt(number if why else content[0][0], why or
                               f"a {'quoted scalar' if quoted else 'flow collection'} followed by more lines")
        return ("string", quoted_scalar(value, True)[0]) if quoted else ("object", None)
    why = plain_problem(value)
    if why:
        raise subset_doubt(number, why)
    return subset_plain([(number, value, False), *content])


def subset_frontmatter(text: str) -> tuple[dict, list]:
    """({"name"/"description": (JavaScript type, value), or None when this reader cannot type it}, [why it cannot
    tell]) of a SKILL.md frontmatter without PyYAML, read as the yaml package would read the subset it parses: a
    top-level block mapping of one-line keys whose values are one-line plain (core-schema typed), quoted or flow
    scalars and collections, plain scalars over several lines, literal and folded block scalars, and nested block
    mappings and lists. Anything else raises SkillMdUnverified: a top-level line that is not a key, a tab in the
    indentation; or goes into the list of doubts: anchors, aliases, tags, quoted scalars that do not close on their
    line or use other escapes than YAML's (double_quoted_value), plain scalars holding ': ', a key given twice."""
    lines = re.split(r"\r\n|\r|\n", text)  # the yaml package's line breaks (str.splitlines also splits at U+0085)
    for number, line in enumerate(lines, 1):
        if line.strip() and "\t" in line[:len(line) - len(line.lstrip(" \t"))]:
            raise subset_doubt(number, "a tab in the indentation")
    fields, doubts, keys, index = {}, [], [], 0
    while index < len(lines):
        number, body = index + 1, strip_yaml_comment(lines[index])
        index += 1
        if not body.strip():
            continue
        pair = split_pair(body) if body[0] != " " else None
        if pair is None:
            raise subset_doubt(number, "an indented line that no key opens" if body[0] == " "
                               else "a top-level line that is not a key: value pair")
        key, quoted, value = pair
        block = []  # the lines up to the next top-level key (a block scalar ends at any line at the key's column)
        while index < len(lines) and not (lines[index].strip() and lines[index][0] != " " and
                                          (value[:1] in ("|", ">") or strip_yaml_comment(lines[index]).strip())):
            block.append((index + 1, lines[index]))
            index += 1
        typed_key = ("string", quoted_scalar(key, True)[0]) if quoted else yaml12_value(key, False)
        if quoted and quoted_scalar(key, True)[1]:
            raise subset_doubt(number, quoted_scalar(key, True)[1])
        if typed_key in keys:
            doubts.append(f"frontmatter line {number}: the key {key} appears twice, which the yaml package refuses "
                          "(uniqueKeys)")
        keys.append(typed_key)
        field = typed_key[1] if typed_key in (("string", "name"), ("string", "description")) else None
        try:
            typed = subset_value(number, value, block, field is not None, body.rstrip() != lines[number - 1].rstrip())
        except SkillMdUnverified as why:
            doubts.append(str(why))
            typed = None
        if field is not None and field not in fields:
            fields[field] = typed
    return fields, doubts


def pyyaml_typed(node) -> tuple[str, object]:
    """A composed node as the yaml package's core schema types it: a plain scalar by yaml12_value, a quoted or block
    scalar as a string, a list or a mapping as an object."""
    if isinstance(node, yaml.ScalarNode):
        return yaml12_value(node.value, not plain_scalar(node))
    return "object", None


def pyyaml_frontmatter(text: str) -> tuple[dict, list]:
    """subset_frontmatter with PyYAML: an event pass refuses any explicit tag (PyYAML resolves tags by YAML 1.1 and the
    yaml package by 1.2, which only warns on a tag it does not know: src/compose/compose-scalar.ts lines 83-88), then
    yaml.compose_all builds the node tree (anchors and aliases followed, every duplicate key and each scalar's style
    kept; the libyaml CSafeLoader when present) and pyyaml_typed types the top-level name and description. Not
    safe_load: its YAML 1.1 constructor reads yes/no/on/off as booleans and 0777 as an octal, the core schema neither.
    A key given twice in any mapping, which the yaml package refuses (src/doc/Document.ts line 128: uniqueKeys), or a
    key that is not a scalar goes into the doubts. SkillMdUnverified: PyYAML cannot parse the text, or it holds more
    than one document (the yaml package's MULTIPLE_DOCS error)."""
    loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
    try:
        for event in yaml.parse(text, Loader=loader):
            if getattr(event, "tag", None) is not None:
                raise SkillMdUnverified(f"the frontmatter holds the explicit tag {event.tag}, which PyYAML and the "
                                        "yaml package resolve differently")
        documents = list(yaml.compose_all(text, Loader=loader))
    except (yaml.YAMLError, ValueError) as error:  # ValueError: the pure-Python scanner's chr() beyond U+10FFFF
        first = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
        raise SkillMdUnverified(f"PyYAML cannot parse the frontmatter ({first}), so whether the yaml package can is "
                                "unverified") from None
    if len(documents) > 1:
        raise SkillMdUnverified(f"the frontmatter holds {len(documents)} YAML documents")
    root = documents[0] if documents else None
    if not isinstance(root, yaml.MappingNode):
        return {}, []  # parse gives null (then {}), a scalar or a list: no name and no description
    fields, doubts, stack, seen = {}, [], [root], set()
    while stack:
        node = stack.pop()
        if id(node) in seen or isinstance(node, yaml.ScalarNode):
            continue
        seen.add(id(node))
        if isinstance(node, yaml.SequenceNode):
            stack.extend(node.value)
            continue
        keys = []
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode):
                doubts.append(f"frontmatter line {key.start_mark.line + 1}: a mapping key that is not a scalar")
                continue
            typed = pyyaml_typed(key)
            if typed in keys:
                doubts.append(f"frontmatter line {key.start_mark.line + 1}: the key {key.value} appears twice in one "
                              "mapping, which the yaml package refuses (uniqueKeys)")
            keys.append(typed)
            stack.append(value)
            if node is root and typed in (("string", "name"), ("string", "description")) and typed[1] not in fields:
                fields[typed[1]] = pyyaml_typed(value)
    return fields, doubts


def skill_md_check(raw: bytes) -> tuple[str | None, str | None]:
    """(why the pinned skills CLI skips this SKILL.md, or None when it takes it; the name it records for it) as
    vercel-labs/skills v1.7.0 decides (src/skills.ts parseSkillMd, lines 80-133; src/frontmatter.ts parseFrontmatter):
    the frontmatter block is parsed by the yaml package 2.9.0 (src/public-api.ts parse, lines 133-165, which throws
    its first error, and then the CLI skips the copy), a falsy name or description counts as missing, and both must be
    strings. The frontmatter is read by pyyaml_frontmatter with PyYAML, else by subset_frontmatter. A copy is skipped
    when name or description decides it whatever the rest holds (missing, or not a string); otherwise a doubt, or a
    name or description the reader cannot type, raises SkillMdUnverified: the reader never asserts a verdict for
    syntax it did not parse. The metadata.internal flag is not checked: `add --skill <name>` includes internal skills
    (src/add.ts lines 1330-1338)."""
    match = SKILL_MD_FRONTMATTER.match(raw.decode("utf-8", "replace"))
    if match:
        fields, doubts = (pyyaml_frontmatter if yaml is not None else subset_frontmatter)(match.group(1))
    else:
        fields, doubts = {}, []
    typed = {key: fields.get(key, ("undefined", None)) for key in ("name", "description")}
    missing = [key for key, value in typed.items() if value is not None and not js_truthy(value)]
    if missing:
        return f"missing required frontmatter field(s): {', '.join(missing)}", None
    if any(value is not None and value[0] != "string" for value in typed.values()):
        kinds = [value[0] if value else "unverified" for value in typed.values()]
        return f'frontmatter "name" and "description" must be strings (got {kinds[0]} and {kinds[1]})', None
    if doubts or None in typed.values():
        unknown = [key for key, value in typed.items() if value is None]
        raise SkillMdUnverified("; ".join(doubts) or f"the reader cannot type {' and '.join(unknown)}")
    return None, sanitize_metadata(typed["name"][1])


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
        return quoted_scalar(value, surrogates=False)[1]
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
    SKILL.md or None, the name the CLI records for it), or raises SkillMdUnverified when the reader cannot tell, which
    propagates wherever that copy's verdict decides the result; without inspect every SKILL.md is valid and named after
    its folder. A copy is a folder named <name> whose SKILL.md is valid and names <name> (filterSkills matches --skill
    against the name in any letter case, or against the folder's name when the name is empty: getSkillDisplayName,
    src/skills.ts lines 331-348); a folder that fails is appended to `skipped` as (folder, reason) and passed over. The
    first location that holds a copy decides; two copies there are ambiguous (the CLI keeps whichever its directory
    listing returns first). Only when no location holds a valid skill of any name (skills.length === 0) does the CLI
    search every folder up to five levels deep, where a copy shadows the copies below it and two unnested copies are
    ambiguous. A folder anywhere else (docs/<lang>/skills/<name>, examples/) needs --full-depth and is never taken."""
    inspect = inspect or (lambda folder: (None, folder.rsplit("/", 1)[-1]))
    skipped = [] if skipped is None else skipped
    named_skips, doubts = [], []

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
    for where, found in locations:
        matches = copies([folder for folder in found if folder.rsplit("/", 1)[-1] == name])
        if len(matches) == 1:
            return matches[0], f"{where}, the first location the CLI searches that holds a valid folder named {name}"
        if matches:
            return None, (f"{len(matches)} folders named {name} in {where}, the first location the CLI searches that "
                          f"holds a valid one: {matches} (the CLI keeps whichever its directory listing returns first)")
    def takes(folder):
        try:
            return inspect(folder)[0] is None
        except SkillMdUnverified as why:
            doubts.append(why)
            return False

    # Any valid SKILL.md in the locations stops the fallback, inspected in the CLI's order up to the first valid one; a
    # SKILL.md the reader cannot tell about decides it only when none of the others is valid.
    if any(takes(folder) for _, found in locations for folder in found):
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
    files = {}  # SKILL.md path -> (bytes, why the CLI skips it or None, the name it records), or SkillMdUnverified

    def read(path):
        if path not in files:
            try:
                raw = gh_file(full, path, pin)
            except GhError as error:  # the CLI reads the blob the tree lists from its clone; this API read says nothing
                files[path] = SkillMdUnverified(f"{path} could not be read here ({error})")
            else:
                try:
                    files[path] = (raw, *skill_md_check(raw))
                except SkillMdUnverified as why:
                    files[path] = SkillMdUnverified(f"{path}: {why}")
        if isinstance(files[path], SkillMdUnverified):
            raise files[path]
        return files[path]

    def inspect(folder):
        return read(f"{folder}/SKILL.md")[1:]

    def skipped_detail():
        detail = "; ".join(f"{f'{each}/' if each else ''}SKILL.md: {why}" for each, why in skipped)
        return f" (skipped: {detail})" if detail else ""

    skipped, skill_path, found_by = [], None, None
    try:
        if "SKILL.md" in blobs:  # a valid root SKILL.md is the only skill the CLI discovers (discoverSkills returns)
            _, problem, root_name = read("SKILL.md")
            if problem is None:
                if root_name.lower() != name.lower():
                    raise GhError(f"{full}@{name}: the root SKILL.md at {pin} is the skill {root_name!r}, the only one "
                                  "the skills CLI discovers in this repository without --full-depth")
                skill_path = "SKILL.md"
                found_by = "the repository root's SKILL.md, the only skill the CLI discovers there"
            else:
                skipped.append(("", problem))  # the CLI skips it and searches on
        if skill_path is None:
            plugin_dirs = cli_plugin_dirs(*(gh_json_file(full, path, pin) if path in blobs else None
                                            for path in PLUGIN_MANIFESTS))
            folder, found_by = cli_skill_dir(skill_dirs, name, plugin_dirs, inspect, skipped)
            if folder is None:
                raise GhError(f"{full}@{name} at {pin}: {found_by}{skipped_detail()}")
            skill_path = f"{folder}/SKILL.md"
    except SkillMdUnverified as why:
        raise GhError(f"{full}@{name} at {pin}: {why}; whether the skills CLI takes that copy, and so which copy it "
                      f"installs, is unverified{skipped_detail()}") from None
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
