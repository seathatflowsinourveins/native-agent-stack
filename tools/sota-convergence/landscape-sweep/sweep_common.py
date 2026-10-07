"""Helpers shared by the landscape-sweep tools that run from this checkout (build_inputs, build_args, convert,
usage_record, make_result). The staged runtime (codex_call.sh, codex_job.py, make_prompt.py) does not import this
module. Standard library only."""

from __future__ import annotations

import hashlib
import copy
import importlib.util
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
MANIFEST_SECTION = {"foundation": "foundation", "us-equities": "trading"}
GITHUB_SLUG = re.compile(r"github\.com/([^/#?\s]+/[^/#?\s]+)", re.IGNORECASE)
# A bare owner/repo (GitHub owners hold only letters, digits and hyphens), with an optional .git or trailing slash.
BARE_SLUG = re.compile(r"([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?", re.IGNORECASE)


def slug(url) -> str:
    """owner/repo, lowercased and without .git, for a GitHub URL or a bare owner/repo; otherwise the lowercased
    string. sweep.js slug() is the same function (a test keeps them in step)."""
    text = str(url or "").strip()
    match = GITHUB_SLUG.search(text)
    if match:
        return re.sub(r"\.git$", "", match.group(1), flags=re.IGNORECASE).lower()
    bare = BARE_SLUG.fullmatch(text)
    return bare.group(1).lower() if bare else text.lower()


def canon(url) -> str:
    """https://github.com/<owner>/<repo> for a GitHub URL (any path after the repository dropped) or a bare
    owner/repo; any other value unchanged. A URL is told from a bare slug before the slug is taken, so owners whose
    names start with "http" (httpie/cli) are canonical too."""
    text = str(url or "").strip()
    if GITHUB_SLUG.search(text) or BARE_SLUG.fullmatch(text):
        return f"https://github.com/{slug(text)}"
    return url


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def prompts_sha256(templates: dict) -> str:
    """The ledger's prompts_sha256: sha256 of json.dumps(templates, sort_keys=True, ensure_ascii=False)."""
    return sha256_bytes(json.dumps(templates, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_text(value, indent=1) -> str:
    """The JSON text emitted by write_json, including its final newline."""
    return json.dumps(value, indent=indent, ensure_ascii=False) + "\n"


def write_json(path: Path, value, indent=1) -> None:
    Path(path).write_text(json_text(value, indent), encoding="utf-8")


def inside_repository(path: Path) -> Path | None:
    """The nearest directory at or above path that holds a git repository marker: a .git directory with a HEAD entry
    (a file, or a symlink, which git allows to point at an unborn branch), or a non-empty .git file (a worktree's or
    submodule's gitdir pointer). An empty .git is not one. Codex's Linux
    sandbox creates empty .git mount targets under its writable roots, /tmp included, while a sandboxed command runs,
    and removes them afterwards (codex-rs/linux-sandbox/src/bwrap.rs at rust-v0.157.1, SyntheticMountTarget). A work
    directory under /tmp would otherwise be refused at random whenever another Codex job writes on the same host."""
    for candidate in (path, *path.parents):
        marker = candidate / ".git"
        try:
            head = marker / "HEAD"
            if head.is_file() or head.is_symlink() or (marker.is_file() and marker.stat().st_size > 0):
                return candidate
        except OSError:  # the marker vanished between the checks: a synthetic target being removed
            continue
    return None


def work_dir(value, must_exist: bool = True) -> Path:
    """The sweep's private work directory: given, absolute after resolution, outside every git repository, and free
    of control characters (its path goes into the workers' prompts; sweep.js refuses such a path too)."""
    if not value:
        raise ValueError("no work directory: pass --work-dir or set SWEEP_WORK_DIR")
    path = Path(value).expanduser().resolve()
    if re.search(r"[\x00-\x1f\x7f]", str(path)):
        raise ValueError(f"work directory {str(path)!r} holds a control character")
    if must_exist and not path.is_dir():
        raise ValueError(f"work directory {path} does not exist")
    repo = inside_repository(path)
    if repo is not None:
        raise ValueError(f"work directory {path} is inside the git repository {repo}; keep it outside every "
                         "repository (it holds prompts, host paths and raw Codex output)")
    return path


def private_content(repo_root: Path = REPO_ROOT):
    """scripts/validate.py's PRIVATE_CONTENT patterns, the ones its publication scan applies to tracked files."""
    spec = importlib.util.spec_from_file_location("landscape_sweep_validate", Path(repo_root) / "scripts" / "validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PRIVATE_CONTENT


def ledger_module(repo_root: Path = REPO_ROOT):
    """scripts/saturation_ledger.py of the checkout, for the ledger's own rules (refuted_by_absence, ref_resolver)."""
    spec = importlib.util.spec_from_file_location("landscape_sweep_ledger", Path(repo_root) / "scripts" / "saturation_ledger.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_requirement_binding(scope: dict, catalog: str, layer_id: str,
                               layer_input: dict | None = None, led=None) -> dict | None:
    """Carry the owner's frozen snapshot, never recapture text from a current catalog.

    Source: native-agent-stack@a40a083172af588f4b97646db87dfc8ef3c0b60e:
    scripts/saturation_ledger.py:540-571. Legacy records lack this additive map.
    """
    key = f"{catalog}/{layer_id}"
    if "requirement_bindings" not in scope:
        if layer_input is not None and "requirement_binding" in layer_input:
            raise ValueError(f"{key}: input declares a requirement_binding absent from the frozen scope")
        return None
    bindings = scope["requirement_bindings"]
    if not isinstance(bindings, dict) or key not in bindings:
        raise ValueError(f"{key}: frozen scope has no declared requirement_binding")
    led = ledger_module() if led is None else led
    validate = getattr(led, "validate_requirement_binding", None)
    if not callable(validate):
        raise ValueError("requirement_binding needs the owner's version-2 saturation-ledger migration; "
                         "text-bound qualification cannot use the legacy-only ledger")
    legacy_hash = (scope.get("requirement_sha256") or {}).get(key)
    try:
        validate(bindings[key], catalog, layer_id, legacy_hash)
    except Exception as error:
        raise ValueError(f"{key}: {error}") from error
    if layer_input is not None:
        if (layer_input.get("catalog"), layer_input.get("layer_id")) != (catalog, layer_id):
            raise ValueError(f"{key}: frozen input identity differs from the selected layer")
        if layer_input.get("requirement_sha256") != legacy_hash:
            raise ValueError(f"{key}: frozen input legacy hash differs from its scope")
        if layer_input.get("requirement_binding") != bindings[key]:
            raise ValueError(f"{key}: frozen input requirement_binding differs from its scope")
        # V2 has a separately neutralized presentation and remains non-launchable.
        if layer_input.get("contract_version", 1) == 1 and layer_input.get("requirement") != bindings[key]["requirement_text"]:
            raise ValueError(f"{key}: frozen input V1 requirement differs from its captured exact text")
    return copy.deepcopy(bindings[key])


def pointer_token(key) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def deviation_rounds(deviations: list, layer_ids) -> tuple[dict, list]:
    """(layer_id -> [(round, item)], unmapped items) for per-worker items (effort deviations, capped WebSearch calls):
    a worker label <role>:<layer>[:followup] belongs to that layer's round, and the completeness critic to every
    layer. convert.py records each item as a retained failure of those layers; make_result.py checks that it did."""
    by_layer, unmapped = {}, []
    for item in deviations:
        parts = str(item.get("child")).split(":")
        if parts == ["critic"]:
            for layer_id in layer_ids:
                by_layer.setdefault(layer_id, []).append(("critic", item))
        elif len(parts) >= 2 and parts[1] in layer_ids and parts[2:] in ([], ["followup"]):
            by_layer.setdefault(parts[1], []).append(("followup" if parts[2:] else "first", item))
        else:
            unmapped.append(item)
    return by_layer, unmapped


def private_findings(value, patterns, pointer: str = "") -> list[tuple[str, str]]:
    """(Locator, kind) for private strings and keys. Matching keys and their descendants use the key's
    document-order index instead of its text, so a report cannot expose that text through a pointer."""
    found = []
    if isinstance(value, str):
        found.extend((pointer or "/", description) for description, pattern in patterns if pattern.search(value))
    elif isinstance(value, dict):
        for index, (key, item) in enumerate(value.items()):
            kinds = [description for description, pattern in patterns if pattern.search(key)] \
                if isinstance(key, str) else []
            token = f"<key-{index}>" if kinds else pointer_token(key)
            child = f"{pointer}/{token}"
            found.extend((child, f"{description} (in a key)") for description in kinds)
            found.extend(private_findings(item, patterns, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(private_findings(item, patterns, f"{pointer}/{index}"))
    return found


def host_replacements(work: Path | None = None, repo_root: Path | None = REPO_ROOT) -> list[tuple[str, str]]:
    """Host path prefixes and their neutral tokens, longest first: work dir, checkout, home."""
    pairs = []
    for path, token in ((work, "<work-dir>"), (repo_root, "<repo>"), (Path.home(), "~")):
        if path is None:
            continue
        for form in {str(path), os.path.realpath(str(path))}:
            if form and form != "/":
                pairs.append((form, token))
    return sorted(dict(pairs).items(), key=lambda pair: -len(pair[0]))


class RedactionKeyCollision(ValueError):
    """Distinct keys would merge; path contains only dictionary-key and list indices, never key text."""

    def __init__(self, path):
        self.path = path
        super().__init__("redaction key collision")


def rewrite_strings(value, fix, path=()):
    """Rewrite strings and dict keys, refusing collisions instead of discarding a value."""
    if isinstance(value, str):
        return fix(value)
    if isinstance(value, list):
        return [rewrite_strings(item, fix, (*path, index)) for index, item in enumerate(value)]
    if isinstance(value, dict):
        result = {}
        for index, (key, item) in enumerate(value.items()):
            rewritten_key = fix(key) if isinstance(key, str) else key
            if rewritten_key in result:
                raise RedactionKeyCollision(path)
            result[rewritten_key] = rewrite_strings(item, fix, (*path, f"<key-{index}>"))
        return result
    return value


def sanitize(value, replacements):
    """Rewrite strings and keys with (prefix, token) replacements; fail on a key collision."""
    def fix(text: str) -> str:
        for prefix, token in replacements:
            text = text.replace(prefix, token)
        return text

    return rewrite_strings(value, fix)
