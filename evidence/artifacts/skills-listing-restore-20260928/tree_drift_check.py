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

Method. The check writes nothing. It executes the checkout's scripts/skills_status.py from the
bytes it hashes (no bytecode cache is read or written) and uses that checker's functions.
  1. Scan. The installed folder (default ~/.agents/skills/<skill>, the canonical copy that
     skills_status.py reads) is walked without following a symlink, by the lstat()/open()/fstat()
     pattern of CPython 3.13's os.fwalk and shutil.rmtree (Lib/os.py _fwalk, Lib/shutil.py
     _rmtree_safe_fd). Names in RUNTIME_ARTIFACT_DIRS are left out and never entered, as in
     git_tree_sha. Any other entry that is not a directory or a regular file (a symlink, FIFO,
     socket or device), an entry named .git in any case, or a folder that is itself a symlink is
     refused before any file is read or any command runs. Git records a regular file only as mode
     100644 or 100755 (gitformat-index: "Only 0755 and 0644 are valid for regular files"), never
     records a .git path component (read-cache.c verify_dotfile), and records a directory holding
     a repository as a gitlink (builtin/add.c check_embedded_repo).
  2. Hash. A second walk opens each regular file relative to its directory with O_NOFOLLOW,
     requires its fstat to match the scanned entry, and hashes it with _git_blob_sha, at the mode
     git_tree_sha assigns (100755 when the owner-execute bit is set, else 100644).
  3. Upstream. `gh api repos/<source>/git/trees/<ref>?recursive=1` at the manifest pin must say
     truncated false. The manifest path must be a tree, and every row under it a 100644 or 100755
     blob or a 040000 tree; any other row (a 120000 symlink, a 160000 gitlink) is refused.
  4. Self-checks. tree_sha_from_rows applies git_tree_sha's entry encoding and order to a map of
     blob rows. From the local rows it must reproduce git_tree_sha of the folder with runtime
     artifacts left out; from the upstream rows, the upstream folder row and every subtree row.
  5. Compare. Every path whose blob or mode differs, or that is missing or extra, is compared with
     the --allow set. A difference outside the set is a fail, and nothing is substituted.
  6. Substitute, in memory. For each allowed path that differs or is missing,
     `gh api repos/<source>/git/blobs/<sha>` fetches the upstream blob; its content must hash to
     that SHA, and its row replaces the local row in a copy of the row map (an allowed extra row
     is dropped). The resulting tree must equal the manifest tree_sha and the upstream folder row.

Git's tree object is the reference: one "<mode> <name>\\0" plus the 20-byte object id per entry,
sorted as base_name_compare sorts (a tree's name compared as if it ended in "/"), after the header
"tree <size>\\0", hashed with SHA-1 (git v2.43.0 builtin/mktree.c write_tree, tree.c
base_name_compare, object-file.c format_object_header; Pro Git 2nd ed., "Git Internals - Git
Objects").

Exit status: 0 (pass) when nothing is refused, every difference is in the --allow set and the
substituted tree equals both the manifest tree_sha and the upstream folder row; 1 (fail)
otherwise; 2 (refused or error) on an unsupported entry on either side, a truncated listing, no
upstream or local blob, a failed self-check, or an input or command error. Exit 2 is never a pass.

Output: one JSON object on stdout, with the home directory written as "~" and the checkout as
"<checkout>". It records this script's sha256 and that of the skills_status.py it executed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

SOURCE_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
BLOB_MODES = frozenset({"100644", "100755"})
LISTED_TREE_MODE = "040000"  # as the GitHub API lists a tree; the tree object itself writes 40000
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class CheckError(Exception):
    """An input or command failure, or a failed self-check: exit 2, never a pass."""


class Refused(CheckError):
    """An entry that git's regular-file tree method cannot compare: exit 2, never a pass."""


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


def load_checker(checkout: Path) -> tuple[types.ModuleType, str]:
    """The checkout's scripts/skills_status.py, executed from the bytes whose sha256 is returned."""
    path = checkout / "scripts" / "skills_status.py"
    source = path.read_bytes()
    module = types.ModuleType("skills_status")
    module.__file__ = str(path)
    exec(compile(source, str(path), "exec"), module.__dict__)  # the same code an import runs, without a .pyc
    return module, hashlib.sha256(source).hexdigest()


def entry_type(mode: int) -> str:
    for test, name in ((stat.S_ISDIR, "directory"), (stat.S_ISREG, "file"), (stat.S_ISLNK, "symlink"),
                       (stat.S_ISFIFO, "fifo"), (stat.S_ISSOCK, "socket"), (stat.S_ISCHR, "character-device"),
                       (stat.S_ISBLK, "block-device")):
        if test(mode):
            return name
    return "unknown"


def scan_folder(folder: Path, skip: frozenset, blob_sha=None) -> dict:
    """Walk folder without following a symlink; hash each regular file when blob_sha is given.

    A directory is entered, and a file read, only through an O_NOFOLLOW descriptor whose fstat
    matches the entry's lstat, so a symlink swapped in during the walk stops it.
    """
    rows: dict[str, tuple[str, str | None]] = {}
    left_out: list[dict] = []
    refused: list[dict] = []

    def walk(dir_fd: int, prefix: str) -> None:
        for name in sorted(os.listdir(dir_fd)):
            relative = prefix + name
            info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
            kind = entry_type(info.st_mode)
            if name in skip:
                left_out.append({"path": relative, "type": kind})
            elif name.lower() == ".git":
                refused.append({"path": relative, "type": kind, "reason": "a .git entry: git records a repository as a gitlink"})
            elif stat.S_ISDIR(info.st_mode):
                fd = os.open(name, DIR_FLAGS, dir_fd=dir_fd)
                try:
                    if not os.path.samestat(info, os.fstat(fd)):
                        raise CheckError(f"{relative} changed during the scan")
                    walk(fd, relative + "/")
                finally:
                    os.close(fd)
            elif stat.S_ISREG(info.st_mode):
                blob = None
                if blob_sha is not None:
                    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
                    try:
                        if not os.path.samestat(info, os.fstat(fd)):
                            raise CheckError(f"{relative} changed during the scan")
                        with open(fd, "rb", closefd=False) as handle:
                            blob = blob_sha(handle.read()).hex()
                    finally:
                        os.close(fd)
                rows[relative] = ("100755" if info.st_mode & stat.S_IXUSR else "100644", blob)
            else:
                refused.append({"path": relative, "type": kind, "reason": "not a regular file or directory"})

    info = os.lstat(folder)
    if not stat.S_ISDIR(info.st_mode):
        refused.append({"path": ".", "type": entry_type(info.st_mode), "reason": "the folder is not a directory"})
    else:
        top = os.open(folder, DIR_FLAGS)
        try:
            if not os.path.samestat(info, os.fstat(top)):
                raise CheckError("the folder changed during the scan")
            walk(top, "")
        finally:
            os.close(top)
    return {"rows": rows, "left_out": left_out, "refused": refused}


def tree_sha_from_rows(rows: dict[str, tuple[str, str]]) -> tuple[str | None, dict[str, str]]:
    """The git tree SHA-1 of {folder-relative path: (blob mode, blob SHA-1 hex)}, and each subtree's.

    Entry encoding, order and header are skills_status.git_tree_sha's (L172-176). A subtree with no
    blob is omitted, as git omits an empty directory.
    """
    root: dict = {}
    for path, (mode, blob) in rows.items():
        *parents, leaf = path.split("/")
        node = root
        for part in parents:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise CheckError(f"{path} lies under a blob row")
        if leaf in node:
            raise CheckError(f"{path} appears twice")
        node[leaf] = (mode, blob)
    subtrees: dict[str, str] = {}

    def encode(node: dict, prefix: str) -> str | None:
        entries = []
        for name, value in node.items():
            raw_name = os.fsencode(name)
            if isinstance(value, dict):
                subtree = encode(value, prefix + name + "/")
                if subtree is not None:
                    subtrees[prefix + name] = subtree
                    entries.append((raw_name, b"40000", bytes.fromhex(subtree), True))
            else:
                entries.append((raw_name, value[0].encode("ascii"), bytes.fromhex(value[1]), False))
        if not entries:
            return None
        entries.sort(key=lambda entry: entry[0] + b"/" if entry[3] else entry[0])
        body = b"".join(mode + b" " + raw_name + b"\0" + digest for raw_name, mode, digest, _ in entries)
        return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()

    return encode(root, ""), dict(sorted(subtrees.items()))


def check(args: argparse.Namespace, report: dict) -> int:
    checkout = Path(args.checkout).resolve()
    skills_status, module_sha256 = load_checker(checkout)
    own = Path(__file__).resolve().read_bytes()
    skip = skills_status.RUNTIME_ARTIFACT_DIRS
    report["method"] = {
        "script": Path(__file__).name,
        "script_sha256": hashlib.sha256(own).hexdigest(),
        "module": "scripts/skills_status.py",
        "module_sha256": module_sha256,
        "functions": ["_git_blob_sha", "git_tree_sha", "load_manifest", "check_folder_tree", "check_canonical",
                      "check_lock_entry"],
        "runtime_artifact_dirs": sorted(skip),
        "python": sys.version.split()[0],
    }

    # 1. Scan: refuse an unsupported entry before any file is read or any command runs.
    folder = Path(args.folder).expanduser() if args.folder else Path.home() / ".agents" / "skills" / args.skill
    report["local"] = {"folder": str(folder)}
    scan = scan_folder(folder, skip)
    report["local"]["left_out_runtime_artifacts"] = scan["left_out"]
    if scan["refused"]:
        report["local"]["refused"] = scan["refused"]
        raise Refused(f"the installed folder holds {len(scan['refused'])} unsupported entry(ies)")

    allowed = sorted(set(args.allow))
    for name in allowed:
        if not name or name.startswith("/") or any(part in ("", ".", "..") for part in name.split("/")):
            raise CheckError(f"--allow {name!r} is not a normalized folder-relative path")
    manifest = skills_status.load_manifest(checkout / "adoption/skills/manifest.json")
    skill = next((entry for entry in manifest["skills"] if entry["name"] == args.skill), None)
    if skill is None:
        raise CheckError(f"no manifest skill named {args.skill}")
    source, ref, path, tree_sha = skill.get("source"), skill.get("ref"), skill.get("path"), skill["tree_sha"]
    if not (isinstance(source, str) and SOURCE_RE.match(source) and isinstance(ref, str) and SHA_RE.match(ref)
            and isinstance(path, str) and path):
        raise CheckError("manifest entry lacks a source, 40-hex ref or path")
    report["manifest"] = {"skill": args.skill, "source": source, "ref": ref, "path": path, "tree_sha": tree_sha}
    report["allowed_differences"] = allowed

    # 2. Hash the installed folder, then check the in-memory tree against the checker's own.
    scan = scan_folder(folder, skip, skills_status._git_blob_sha)
    if scan["refused"]:
        report["local"]["refused"] = scan["refused"]
        raise Refused("an unsupported entry appeared in the installed folder during the scan")
    rows = scan["rows"]
    if not rows:
        raise CheckError("the installed folder holds no blob")
    local_tree, local_subtrees = tree_sha_from_rows(rows)
    lock_path, _ = skills_status.resolve_lock_path(Path.home(), os.environ)
    lock_data, lock_state = skills_status.load_lock(lock_path)
    status_skill = {**skill, "name": folder.name}
    report["local"].update({
        "tree_sha_as_on_disk": skills_status.git_tree_sha(folder),
        "tree_sha_without_runtime_artifacts": skills_status.git_tree_sha(folder, skip),
        "tree_sha_from_rows": local_tree,
        "skills_status_folder_tree_state": skills_status.check_folder_tree(folder.parent, status_skill)["state"],
        "skill_md_sha256_state": skills_status.check_canonical(folder.parent, status_skill)["state"],
        "lock_entry_state": skills_status.check_lock_entry(lock_data, lock_state, skill)["state"],
        "blobs": len(rows),
        "rows": [{"path": name, "mode": mode, "blob": blob} for name, (mode, blob) in sorted(rows.items())],
        "subtrees": local_subtrees,
    })
    if local_tree != report["local"]["tree_sha_without_runtime_artifacts"]:
        raise CheckError("self-check: the local rows do not hash to skills_status.git_tree_sha of the folder")
    report["method"]["gh_version"] = run([args.gh, "--version"], report["runs"]).decode("utf-8", "replace").split("\n")[0]

    # 3. Upstream rows at the pin: only regular-file blobs and trees under the manifest path.
    listing = json.loads(run([args.gh, "api", f"repos/{source}/git/trees/{ref}?recursive=1"], report["runs"]))
    prefix = path + "/"
    listed = [row for row in listing.get("tree", []) if isinstance(row, dict) and isinstance(row.get("path"), str)]
    folder_row = next((row for row in listed if row["path"] == path), None)
    upstream = [{"path": row["path"][len(prefix):], "mode": row.get("mode"), "type": row.get("type"),
                 "sha": row.get("sha")} for row in listed if row["path"].startswith(prefix)]
    report["upstream"] = {"response_sha": listing.get("sha"), "truncated": listing.get("truncated"),
                          "folder_row": folder_row and {key: folder_row.get(key) for key in ("path", "mode", "type", "sha")},
                          "rows_under_path": len(upstream), "rows": upstream}
    if listing.get("truncated") is not False:
        raise CheckError("the upstream listing is truncated or does not say it is not")
    if not (folder_row and folder_row.get("type") == "tree" and folder_row.get("mode") == LISTED_TREE_MODE
            and SHA_RE.match(str(folder_row.get("sha")))):
        raise CheckError("the manifest path is not a tree in the upstream listing")
    unsupported = [row for row in upstream if not SHA_RE.match(str(row["sha"])) or not (
        (row["type"] == "blob" and row["mode"] in BLOB_MODES) or (row["type"] == "tree" and row["mode"] == LISTED_TREE_MODE))]
    if unsupported:
        report["upstream"]["refused"] = unsupported
        raise Refused(f"the upstream listing holds {len(unsupported)} row(s) other than a 100644 or 100755 blob or a tree")
    upstream_blobs = {row["path"]: (row["mode"], row["sha"]) for row in upstream if row["type"] == "blob"}
    if not upstream_blobs:
        raise CheckError("no upstream blob lies under the manifest path")
    upstream_trees = {row["path"]: row["sha"] for row in upstream if row["type"] == "tree"}
    upstream_tree, upstream_subtrees = tree_sha_from_rows(upstream_blobs)
    report["upstream"]["self_check"] = {"tree_sha_from_rows": upstream_tree,
                                        "equals_folder_row": upstream_tree == folder_row["sha"],
                                        "subtrees_equal_tree_rows": upstream_subtrees == dict(sorted(upstream_trees.items()))}
    if not all(report["upstream"]["self_check"].values()):
        raise CheckError("self-check: the upstream rows do not hash to the upstream tree rows")

    # 4. Path-by-path comparison; a difference outside the allowed set fails before any substitution.
    differing = sorted(name for name in upstream_blobs.keys() & rows.keys() if upstream_blobs[name] != rows[name])
    missing = sorted(upstream_blobs.keys() - rows.keys())
    extra = sorted(rows.keys() - upstream_blobs.keys())
    disallowed = sorted(set(differing + missing + extra) - set(allowed))
    report["comparison"] = {
        "upstream_blobs": len(upstream_blobs), "local_blobs": len(rows),
        "matching": len(upstream_blobs.keys() & rows.keys()) - len(differing),
        "differing": [{"path": name, "local_mode": rows[name][0], "local_blob": rows[name][1],
                       "upstream_mode": upstream_blobs[name][0], "upstream_blob": upstream_blobs[name][1]}
                      for name in differing],
        "missing": missing, "extra": extra, "outside_allowed_set": disallowed,
    }
    if disallowed:
        report["substitution"] = None
        report["result"] = "fail"
        return 1

    # 5. Substitute each allowed upstream blob into a copy of the row map and hash it in memory.
    substituted = dict(rows)
    blobs: list[dict] = []
    for name in sorted(set(differing) | set(missing)):
        mode, sha = upstream_blobs[name]
        blob = json.loads(run([args.gh, "api", f"repos/{source}/git/blobs/{sha}"], report["runs"]))
        if blob.get("encoding") != "base64":
            raise CheckError(f"blob {sha} is not base64-encoded")
        data = base64.b64decode(blob.get("content", ""))
        verified = skills_status._git_blob_sha(data).hex()
        if verified != sha:
            raise CheckError(f"fetched blob hashes to {verified}, not {sha}")
        substituted[name] = (mode, verified)
        blobs.append({"path": name, "upstream_blob": sha, "fetched_bytes": len(data), "fetched_blob_sha_verified": True})
    for name in extra:
        del substituted[name]
        blobs.append({"path": name, "removed_extra": True})
    tree, subtrees = tree_sha_from_rows(substituted)
    report["substitution"] = {
        "in_memory": True, "blobs": blobs, "tree_sha": tree, "subtrees": subtrees,
        "equals_manifest_tree_sha": tree == tree_sha,
        "equals_upstream_folder_row": tree == folder_row["sha"],
        "subtrees_equal_upstream_rows": {name: subtrees.get(name) == sha for name, sha in sorted(upstream_trees.items())},
    }
    passed = report["substitution"]["equals_manifest_tree_sha"] and report["substitution"]["equals_upstream_folder_row"]
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
    report: dict = {"schema": "tree_drift_check/2", "argv": sys.argv, "started_utc": utc_now(), "runs": []}
    try:
        code = check(args, report)
    except Refused as error:  # an unsupported entry on either side: exit 2, never a pass
        report["result"] = "refused"
        report["error"] = f"Refused: {error}"
        code = 2
    except Exception as error:  # any other failure is exit 2, never read as a pass or a fail
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
