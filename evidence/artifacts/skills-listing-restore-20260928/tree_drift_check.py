#!/usr/bin/env python3
"""Per-blob re-check of an installed skill folder against its pinned upstream git tree.

scripts/skills_status.py reports a canonical folder's on-disk tree only as a state (ok,
runtime_artifacts or drift), and a skill that re-locks its own scripts/ project reads `drift`
again after every use. This check names each differing blob, so a change outside an explicit
allowed set can be seen. For supply-chain-risk-auditor the allowed set is {scripts/uv.lock}
(docs/decisions/2026-09-25-skills-trial-and-usage.md, addendum 2026-09-28).

Usage, from the root of a checkout of this repository:
  python3 evidence/artifacts/skills-listing-restore-20260928/tree_drift_check.py \
      --checkout . --skill supply-chain-risk-auditor --allow scripts/uv.lock

Method:
  1. `gh api repos/<source>/git/trees/<ref>?recursive=1` at the manifest pin. The rows under the
     manifest path are kept, with the response's `truncated` flag.
  2. The installed folder (default ~/.agents/skills/<skill>, the canonical copy skills_status.py
     reads) is hashed per blob with skills_status.py's own `_git_blob_sha`, with the file modes its
     `git_tree_sha` assigns, and with its RUNTIME_ARTIFACT_DIRS left out at every level.
  3. Every differing, missing or extra path is compared with the --allow set.
  4. For each allowed path that differs or is missing, `gh api repos/<source>/git/blobs/<sha>`
     fetches the upstream blob. Its own git blob SHA is verified, it is written into a copy of the
     folder, and skills_status.git_tree_sha recomputes the tree. That tree must equal the
     manifest tree_sha and the upstream folder row.

Exit status: 0 when every difference is in the --allow set and the substituted tree equals the
manifest tree_sha; 1 otherwise; 2 on an input or command error, a truncated listing, no upstream
blob under the path or no local blob (a vacuous comparison is refused, never passed).

Output: one JSON object on stdout, with the home directory written as "~" and the checkout
written as "<checkout>". Read-only, except for a temporary directory that it removes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SOURCE_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
REF_RE = re.compile(r"[0-9a-f]{40}\Z")


class CheckError(Exception):
    """An input or command failure: exit 2, never a pass."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(value, replacements):
    if isinstance(value, str):
        for old, new in replacements:
            if old:
                value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [scrub(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: scrub(item, replacements) for key, item in value.items()}
    return value


def run(argv: list[str], runs: list[dict]) -> bytes:
    record = {"argv": argv, "started_utc": utc_now()}
    runs.append(record)
    try:
        done = subprocess.run(argv, capture_output=True, stdin=subprocess.DEVNULL, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        record.update({"exit": None, "error": type(error).__name__})
        raise CheckError(f"{argv[0]} could not run ({type(error).__name__})") from None
    record.update({"exit": done.returncode, "finished_utc": utc_now(), "stdout_bytes": len(done.stdout),
                   "stdout_sha256": hashlib.sha256(done.stdout).hexdigest(), "stderr_bytes": len(done.stderr)})
    if done.returncode != 0:
        record["stderr_excerpt"] = done.stderr.decode("utf-8", "replace")[:300]
        raise CheckError(f"{' '.join(argv[:3])} exited {done.returncode}")
    return done.stdout


def local_rows(folder: Path, skip: frozenset, blob_sha) -> tuple[dict, list[str]]:
    """Per-blob rows keyed by folder-relative path, classified as skills_status.git_tree_sha does."""
    rows: dict[str, dict] = {}
    left_out: list[str] = []

    def walk(directory: Path, prefix: str) -> None:
        for name in sorted(os.listdir(directory)):
            path = directory / name
            relative = prefix + name
            info = os.lstat(path)
            if name in skip:
                left_out.append(relative + ("/" if stat.S_ISDIR(info.st_mode) else ""))
            elif stat.S_ISLNK(info.st_mode):
                rows[relative] = {"mode": "120000", "blob": blob_sha(os.readlink(os.fsencode(path))).hex()}
            elif stat.S_ISDIR(info.st_mode):
                walk(path, relative + "/")
            elif stat.S_ISREG(info.st_mode):
                mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
                rows[relative] = {"mode": mode, "blob": blob_sha(path.read_bytes()).hex()}
            else:
                rows[relative] = {"mode": "not-a-file-or-link", "blob": None}

    walk(folder, "")
    return rows, left_out


def check(args: argparse.Namespace, report: dict) -> int:
    checkout = Path(args.checkout).resolve()
    sys.path.insert(0, str(checkout / "scripts"))
    import skills_status  # the checker whose folder method this reproduces

    status_file = Path(skills_status.__file__)
    report["method"] = {
        "module": "scripts/skills_status.py",
        "module_sha256": hashlib.sha256(status_file.read_bytes()).hexdigest(),
        "functions": ["git_tree_sha", "_git_blob_sha", "check_folder_tree", "check_canonical", "check_lock_entry"],
        "runtime_artifact_dirs": sorted(skills_status.RUNTIME_ARTIFACT_DIRS),
        "python": sys.version.split()[0],
    }
    manifest = skills_status.load_manifest(checkout / "adoption/skills/manifest.json")
    skill = next((entry for entry in manifest["skills"] if entry["name"] == args.skill), None)
    if skill is None:
        raise CheckError(f"no manifest skill named {args.skill}")
    source, ref, path, tree_sha = skill.get("source"), skill.get("ref"), skill.get("path"), skill["tree_sha"]
    if not (isinstance(source, str) and SOURCE_RE.match(source) and isinstance(ref, str) and REF_RE.match(ref)
            and isinstance(path, str) and path):
        raise CheckError("manifest entry lacks a source, 40-hex ref or path")
    allowed = sorted(set(args.allow))
    report["manifest"] = {"skill": args.skill, "source": source, "ref": ref, "path": path, "tree_sha": tree_sha}
    report["allowed_differences"] = allowed

    # 1. Upstream rows at the pin.
    listing = json.loads(run([args.gh, "api", f"repos/{source}/git/trees/{ref}?recursive=1"], report["runs"]))
    prefix = path + "/"
    folder_row = next((row for row in listing.get("tree", []) if row.get("path") == path), None)
    upstream = [{"path": row["path"][len(prefix):], "mode": row.get("mode"), "type": row.get("type"),
                 "sha": row.get("sha")} for row in listing.get("tree", []) if str(row.get("path", "")).startswith(prefix)]
    report["upstream"] = {"response_sha": listing.get("sha"), "truncated": listing.get("truncated"),
                          "folder_row": folder_row and {key: folder_row.get(key) for key in ("path", "mode", "type", "sha")},
                          "rows_under_path": len(upstream), "rows": upstream}
    if listing.get("truncated") is not False:
        raise CheckError("the upstream listing is truncated or does not say it is not")
    upstream_blobs = {row["path"]: row for row in upstream if row["type"] == "blob"}
    if not upstream_blobs:
        raise CheckError("no upstream blob lies under the manifest path")

    # 2. Installed folder, hashed with the checker's own functions.
    folder = Path(args.folder).expanduser() if args.folder else Path.home() / ".agents" / "skills" / args.skill
    if not folder.is_dir():
        raise CheckError("the installed folder is missing")
    skip = skills_status.RUNTIME_ARTIFACT_DIRS
    rows, left_out = local_rows(folder, skip, skills_status._git_blob_sha)
    if not rows:
        raise CheckError("the installed folder holds no blob")
    lock_path, _ = skills_status.resolve_lock_path(Path.home(), os.environ)
    lock_data, lock_state = skills_status.load_lock(lock_path)
    report["local"] = {
        "folder": str(folder),
        "tree_sha_as_on_disk": skills_status.git_tree_sha(folder),
        "tree_sha_without_runtime_artifacts": skills_status.git_tree_sha(folder, skip),
        "skills_status_folder_tree_state": skills_status.check_folder_tree(folder.parent, {**skill, "name": folder.name})["state"],
        "skill_md_sha256_state": skills_status.check_canonical(folder.parent, {**skill, "name": folder.name})["state"],
        "lock_entry_state": skills_status.check_lock_entry(lock_data, lock_state, skill)["state"],
        "left_out_runtime_artifacts": left_out,
        "blobs": len(rows),
        "rows": [{"path": key, **value} for key, value in sorted(rows.items())],
        "subtrees": {row["path"]: skills_status.git_tree_sha(folder / row["path"], skip)
                     for row in upstream if row["type"] == "tree" and (folder / row["path"]).is_dir()},
    }

    # 3. Path-by-path comparison against the allowed set.
    differing = sorted(name for name in upstream_blobs.keys() & rows.keys()
                       if (upstream_blobs[name]["sha"], upstream_blobs[name]["mode"]) != (rows[name]["blob"], rows[name]["mode"]))
    missing = sorted(upstream_blobs.keys() - rows.keys())
    extra = sorted(rows.keys() - upstream_blobs.keys())
    disallowed = sorted(set(differing + missing + extra) - set(allowed))
    report["comparison"] = {
        "upstream_blobs": len(upstream_blobs), "local_blobs": len(rows),
        "matching": len(upstream_blobs.keys() & rows.keys()) - len(differing),
        "differing": [{"path": name, "local_mode": rows[name]["mode"], "local_blob": rows[name]["blob"],
                       "upstream_mode": upstream_blobs[name]["mode"], "upstream_blob": upstream_blobs[name]["sha"]}
                      for name in differing],
        "missing": missing, "extra": extra, "outside_allowed_set": disallowed,
    }

    # 4. Substitute each allowed upstream blob into a copy and recompute the tree.
    substitution: dict = {"blobs": []}
    with tempfile.TemporaryDirectory(prefix="tree-drift-") as temporary:
        copy = Path(temporary) / folder.name
        shutil.copytree(folder, copy, symlinks=True, ignore=shutil.ignore_patterns(*skip))
        for name in sorted((set(differing) | set(missing)) & set(allowed)):
            row = upstream_blobs[name]
            blob = json.loads(run([args.gh, "api", f"repos/{source}/git/blobs/{row['sha']}"], report["runs"]))
            if blob.get("encoding") != "base64":
                raise CheckError(f"blob {row['sha']} is not base64-encoded")
            data = base64.b64decode(blob.get("content", ""))
            verified = skills_status._git_blob_sha(data).hex()
            if verified != row["sha"]:
                raise CheckError(f"fetched blob hashes to {verified}, not {row['sha']}")
            target = copy / name
            if target.is_symlink():
                target.unlink()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            mode = os.stat(target).st_mode
            os.chmod(target, (mode | stat.S_IXUSR) if row["mode"] == "100755" else (mode & ~stat.S_IXUSR))
            substitution["blobs"].append({"path": name, "upstream_blob": row["sha"], "fetched_bytes": len(data),
                                          "fetched_blob_sha_verified": True})
        for name in sorted(set(extra) & set(allowed)):
            (copy / name).unlink()
            substitution["blobs"].append({"path": name, "removed_extra": True})
        substitution["tree_sha"] = skills_status.git_tree_sha(copy, skip)
        substitution["subtrees"] = {row["path"]: skills_status.git_tree_sha(copy / row["path"], skip)
                                    for row in upstream if row["type"] == "tree" and (copy / row["path"]).is_dir()}
    substitution["equals_manifest_tree_sha"] = substitution["tree_sha"] == tree_sha
    substitution["equals_upstream_folder_row"] = bool(folder_row) and substitution["tree_sha"] == folder_row.get("sha")
    substitution["subtrees_equal_upstream_rows"] = {
        row["path"]: substitution["subtrees"].get(row["path"]) == row["sha"] for row in upstream if row["type"] == "tree"}
    report["substitution"] = substitution
    passed = not disallowed and substitution["equals_manifest_tree_sha"]
    report["result"] = "pass" if passed else "fail"
    return 0 if passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checkout", required=True, help="root of a checkout of this repository")
    parser.add_argument("--skill", required=True, help="manifest skill name")
    parser.add_argument("--allow", action="append", default=[], metavar="PATH",
                        help="folder-relative path allowed to differ (repeatable; none by default)")
    parser.add_argument("--folder", help="installed folder to check (default ~/.agents/skills/<skill>)")
    parser.add_argument("--gh", default="gh", help="GitHub CLI executable")
    args = parser.parse_args(argv)
    report: dict = {"schema": "tree_drift_check/1", "argv": sys.argv, "started_utc": utc_now(), "runs": []}
    try:
        code = check(args, report)
    except Exception as error:  # any failure is exit 2, never read as a pass or a fail
        report["result"] = "error"
        report["error"] = f"{type(error).__name__}: {error}"
        code = 2
    report["finished_utc"] = utc_now()
    report["exit"] = code
    replacements = [(str(Path(args.checkout).resolve()), "<checkout>"), (str(Path.home()), "~")]
    print(json.dumps(scrub(report, replacements), indent=1))
    return code


if __name__ == "__main__":
    sys.exit(main())
