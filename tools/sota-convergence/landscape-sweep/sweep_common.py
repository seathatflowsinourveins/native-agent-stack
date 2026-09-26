"""Helpers shared by the landscape-sweep tools that run from this checkout (build_inputs, build_args, convert,
usage_record, make_result). The staged runtime (codex_call.sh, codex_job.py, make_prompt.py) does not import this
module. Standard library only."""

from __future__ import annotations

import hashlib
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


def write_json(path: Path, value, indent=1) -> None:
    Path(path).write_text(json.dumps(value, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8")


def inside_repository(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
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


def pointer_token(key) -> str:
    return str(key).replace("~", "~0").replace("/", "~1")


def private_findings(value, patterns, pointer: str = "") -> list[tuple[str, str]]:
    """(JSON pointer, kind) for every string, dict keys included, that matches a private-content pattern. The
    matched text is never returned, so a report cannot leak it."""
    found = []
    if isinstance(value, str):
        found.extend((pointer or "/", description) for description, pattern in patterns if pattern.search(value))
    elif isinstance(value, dict):
        for key, item in value.items():
            child = f"{pointer}/{pointer_token(key)}"
            if isinstance(key, str):
                found.extend((child, f"{description} (in a key)") for description, pattern in patterns
                             if pattern.search(key))
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


def sanitize(value, replacements):
    """value with every string (dict keys included) rewritten by the (prefix, token) replacements."""
    def fix(text: str) -> str:
        for prefix, token in replacements:
            text = text.replace(prefix, token)
        return text

    if isinstance(value, str):
        return fix(value)
    if isinstance(value, list):
        return [sanitize(item, replacements) for item in value]
    if isinstance(value, dict):
        return {(fix(key) if isinstance(key, str) else key): sanitize(item, replacements)
                for key, item in value.items()}
    return value
