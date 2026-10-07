#!/usr/bin/env python3
"""Observe skill state; never install, inject context, or make a decision.

Sources: https://code.claude.com/docs/en/hooks-guide#audit-configuration-changes
https://code.claude.com/docs/en/hooks#instructionsloaded
openai/codex@a956835d020762cb2b570053af06f643a11c0ecc:
codex-rs/hooks/schema/generated/{post-tool-use,session-start}.command.input.schema.json
POSIX locking: https://docs.python.org/3/library/fcntl.html#fcntl.flock

This is local integration glue for state deduplication absent from the upstream
one-line audit example. Hook registration and Codex trust are separate proposals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from collections.abc import Mapping

try:
    import fcntl
except ImportError:  # A POSIX host is required; the hook still fails open.
    fcntl = None

ROOT = Path(__file__).resolve().parents[2]
EVENTS = {"ConfigChange", "SessionStart", "FileChanged", "PostToolUse", "CurrencyTimer"}
IGNORED_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "auth", "credentials", ".ssh"}
MAX_INPUT = 1024 * 1024
MAX_SKILL = 1024 * 1024
MAX_LOCK = 8 * 1024 * 1024
MAX_SCAN_ENTRIES = 100_000
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}\Z")
HEX = re.compile(r"[a-fA-F0-9]{40}(?:[a-fA-F0-9]{24})?\Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def excluded(name: str) -> bool:
    lower = name.lower()
    return name in IGNORED_DIRS or lower.endswith(".pyc") or lower in {"auth.json", "credentials.json"} or lower.startswith(".env") or lower.endswith((".pem", ".key", ".p12"))


def stamp(path: Path) -> list[int] | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return [info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino]


@contextmanager
def regular_stream(path: Path, flags: int, mode: str) -> Iterator[Any]:
    """Validate a nonblocking, final-component no-follow FD before any I/O.

    The directory must be trusted and writers must cooperate through flock.
    Regular-file I/O/fsync latency and power-loss durability are not guaranteed.
    """
    nofollow = getattr(os, "O_NOFOLLOW", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if not isinstance(nofollow, int) or not nofollow or not isinstance(nonblock, int) or not nonblock:
        raise NotImplementedError("required_file_flags_unavailable")
    if flags & os.O_TRUNC:
        raise ValueError("truncate_before_validation")
    fd = os.open(path, flags | nofollow | nonblock, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("not_regular_file")
        stream = os.fdopen(fd, mode)
        fd = None  # The stream now owns the descriptor.
        try:
            yield stream
        finally:
            stream.close()
    finally:
        if fd is not None:
            os.close(fd)


def bounded_read(path: Path, limit: int) -> bytes:
    with regular_stream(path, os.O_RDONLY, "rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("file_size_limit")
    return data


def private_append(path: Path, row: dict) -> None:
    with regular_stream(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, "ab") as stream:
        stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".next")
    with regular_stream(temporary, os.O_WRONLY | os.O_CREAT, "w") as stream:
        os.ftruncate(stream.fileno(), 0)
        json.dump(value, stream, sort_keys=True, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_json(path: Path, default: dict) -> dict:
    try:
        value = json.loads(bounded_read(path, 64 * 1024 * 1024))
    except FileNotFoundError:
        return default
    if not isinstance(value, dict):
        raise ValueError("object_required")
    return value


def project_root(cwd: Path) -> Path:
    current = cwd.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def native_config_root(home: Path, variable: str, default: str, environment: Mapping[str, str]) -> Path:
    """Select only a public root locator, without reading native configuration.

    CODEX_HOME: openai/codex@a956835d:codex-rs/utils/home-dir/src/lib.rs:13-49.
    CLAUDE_CONFIG_DIR: https://code.claude.com/docs/en/env-vars#environment-variables.
    Redirected or relative overrides remain unsupported observations, not a
    license to inspect their targets or silently substitute the default profile.
    """
    value = environment.get(variable)
    path = Path(value) if value else home / default
    if not path.is_absolute() or ".." in path.parts or path.resolve() != path:
        raise ValueError("unsupported_native_config_root")
    if path.exists() and not path.is_dir():
        raise ValueError("native_config_directory_required")
    if value and variable == "CODEX_HOME" and not path.is_dir():
        raise ValueError("unavailable_native_codex_home")
    return path


def roots(home: Path, project: Path, claude_root: Path, codex_root: Path) -> list[tuple[str, str, Path]]:
    entries = [
        ("global", "home_agents", home / ".agents/skills"),
        ("global", "home_claude", claude_root / "skills"),
        ("global", "home_codex", codex_root / "skills"),
        ("global", "claude_plugin", claude_root / "plugins/cache"),
        ("global", "codex_plugin", codex_root / "plugins/cache"),
        ("project", "project_agents", project / ".agents/skills"),
        ("project", "project_claude", project / ".claude/skills"),
    ]
    global_paths = {path for group, _, path in entries if group == "global"}
    return [row for row in entries if row[0] == "global" or row[2] not in global_paths]


def skill_name(content: bytes, folder: Path) -> tuple[str, str | None]:
    frontmatter = re.match(rb"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", content, re.S)
    name = folder.name
    if frontmatter:
        match = re.search(rb"(?m)^name:[ \t]*(.*?)\r?$", frontmatter[1])
        if match:
            name = match[1].decode("utf-8", errors="replace").strip().strip("\"'")
    if not NAME.fullmatch(name):
        name = "unknown-" + hashlib.sha256(name.encode()).hexdigest()[:12]
    return name, hashlib.sha256(frontmatter[1]).hexdigest() if frontmatter else None


def source_metadata(entry: Any) -> dict:
    entry = entry if isinstance(entry, dict) else {}
    repository = entry.get("source")
    ref = entry.get("ref")
    tree = entry.get("skillFolderHash", entry.get("computedHash"))
    repository = repository if isinstance(repository, str) and REPOSITORY.fullmatch(repository) else None
    ref = ref.lower() if isinstance(ref, str) and HEX.fullmatch(ref) else None
    tree = tree.lower() if isinstance(tree, str) and HEX.fullmatch(tree) else None
    return {"repository": repository, "ref": ref, "tree_sha": tree, "status": "known" if repository else "unknown"}


class Recorder:
    def __init__(self, home: Path, project: Path, state_dir: Path, *, status_timeout: float = 2.0, scan_timeout: float = 5.0,
                 environment: Mapping[str, str] | None = None):
        self.home = home.resolve()
        self.project = project_root(project)
        self.state_dir = state_dir
        self.state_file = state_dir / "state.json"
        self.ledger = state_dir / "ledger.jsonl"
        self.status_timeout = status_timeout
        self.scan_timeout = scan_timeout
        # Read only these named public path overrides; no settings/auth stores.
        self.native_roots_error = None
        try:
            selected = os.environ if environment is None else environment
            self.claude_root = native_config_root(self.home, "CLAUDE_CONFIG_DIR", ".claude", selected)
            self.codex_root = native_config_root(self.home, "CODEX_HOME", ".codex", selected)
        except (ValueError, OSError) as error:
            self.claude_root = self.codex_root = None
            self.native_roots_error = error

    def root_specs(self) -> list[tuple[str, str, Path]]:
        if self.native_roots_error is not None:
            raise ValueError("native_root_scope_unknown") from self.native_roots_error
        return roots(self.home, self.project, self.claude_root, self.codex_root)

    @contextmanager
    def locked(self) -> Iterator[None]:
        if fcntl is None:
            raise RuntimeError("posix_lock_unavailable")
        if any(path.is_symlink() for path in (self.state_dir, *self.state_dir.parents)):
            raise ValueError("state_directory_symlink")
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        with regular_stream(self.state_dir / "recorder.lock", os.O_RDWR | os.O_CREAT, "a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def error(self, stage: str, error: BaseException) -> None:
        # No exception text, hook input, command, file content, or host path.
        try:
            if any(path.is_symlink() for path in (self.state_dir, *self.state_dir.parents)):
                return
            self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            private_append(self.state_dir / "errors.jsonl", {
                "schema_version": 1, "kind": "skill_recorder_error", "occurred_at_utc": utc_now(),
                "stage": stage, "error_type": type(error).__name__,
            })
        except Exception:
            pass

    def locator(self, path: Path, scope: str | None = None) -> str:
        if scope is not None:
            for _, label, root in self.root_specs():
                if label == scope:
                    try:
                        return "<" + label + ">/" + path.relative_to(root).as_posix()
                    except ValueError:
                        pass
        for root, prefix in [(self.project, "<project>"), (self.home, "<home>")]:
            try:
                return prefix + "/" + path.relative_to(root).as_posix()
            except ValueError:
                pass
        return "<external>/" + digest(str(path))[:16]

    def snapshot(self, group: str, deadline: float | None = None) -> dict:
        deadline = deadline or time.monotonic() + self.scan_timeout
        specs = self.root_specs()
        selected = [(scope, path) for kind, scope, path in specs if kind == group]
        # Only an explicitly named, nonredirected root can allow an alias target.
        # A symlink never registers its arbitrary destination as a trusted root.
        allowed = [path for _, _, path in specs if path.is_dir() and path.resolve() == path]
        watches: dict[str, list[int] | None] = {}
        discovered: dict[Path, str] = {}
        metadata: dict[Path, list] = {}
        visited: set[Path] = set()
        entries = 0
        for scope, root in selected:
            watches[str(root)] = stamp(root)
            if not root.exists():
                continue
            if root.is_symlink():
                if root.resolve() not in allowed:
                    raise ValueError("unknown_skill_root_alias")
            elif root.resolve() != root:
                raise ValueError("redirected_skill_root_parent")
            pending = [root]
            while pending:
                folder = pending.pop()
                resolved = folder.resolve()
                if resolved in visited:
                    continue
                visited.add(resolved)
                watches[str(folder)] = stamp(folder)
                for item in sorted(folder.iterdir()):
                    if excluded(item.name):
                        continue
                    entries += 1
                    if entries > MAX_SCAN_ENTRIES or time.monotonic() > deadline:
                        raise TimeoutError("scan_limit")
                    watches[str(item)] = stamp(item)
                    if item.is_symlink():
                        target = item.resolve()
                        if target.is_dir() and any(target.is_relative_to(path) for path in allowed):
                            pending.append(target)
                        continue
                    if item.is_dir():
                        pending.append(item)
                    elif item.is_file():
                        metadata.setdefault(folder.resolve(), []).append([item.name, watches[str(item)]])
                        if item.name == "SKILL.md":
                            discovered.setdefault(item.resolve(), scope)
        lock = self.home / ".agents/.skill-lock.json" if group == "global" else self.project / "skills-lock.json"
        if lock.parent.resolve() != lock.parent:
            raise ValueError("redirected_public_lock_parent")
        watches[str(lock)] = stamp(lock)
        lock_data = json.loads(bounded_read(lock, MAX_LOCK)) if lock.exists() else {}
        lock_skills = lock_data.get("skills", {}) if isinstance(lock_data, dict) else {}
        if not isinstance(lock_skills, dict):
            raise ValueError("invalid_public_lock")
        observations = {}
        for path, nominal_scope in sorted(discovered.items(), key=lambda pair: str(pair[0])):
            if time.monotonic() > deadline:
                raise TimeoutError("scan_limit")
            # Resolve aliases to the canonical root's identity, across sessions.
            scope = next((label for _, label, root in specs if root in allowed and path.is_relative_to(root)), nominal_scope)
            if scope.startswith("project_") != (group == "project"):
                continue
            content = bounded_read(path, MAX_SKILL)
            name, header_hash = skill_name(content, path.parent)
            files = []
            for folder, rows in metadata.items():
                if folder.is_relative_to(path.parent):
                    for filename, file_stamp in rows:
                        if filename == "SKILL.md" and folder == path.parent:
                            continue  # Actual bytes below; a touch is not a body change.
                        files.append([str((folder / filename).relative_to(path.parent)), file_stamp])
            lock_owned = scope in {"home_agents", "home_claude", "project_agents", "project_claude"}
            source = source_metadata(lock_skills.get(name) if lock_owned else None)
            key = digest([str(path)])
            observations[key] = {
                "skill_name": name, "scope": scope, "state_key": key,
                "locator": self.locator(path, scope), "source": source,
                "skill_md_sha256": hashlib.sha256(content).hexdigest(), "skill_md_bytes": len(content),
                "frontmatter_sha256": header_hash, "folder_fingerprint": digest(sorted(files)),
                "folder_fingerprint_method": "supporting_file_stat_metadata_bytecode_excluded",
            }
        return {"watches": watches, "skills": observations}

    def append_missing(self, rows: list[dict]) -> None:
        ids = set()
        try:
            with regular_stream(self.ledger, os.O_RDONLY, "rb") as stream:
                for line in stream:
                    if len(line) > 2 * MAX_SKILL:
                        raise ValueError("ledger_row_limit")
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        ids.add(entry.get("id"))
        except FileNotFoundError:
            pass
        for row in rows:
            if row["id"] not in ids:
                private_append(self.ledger, row)
                ids.add(row["id"])

    def recover(self, state: dict) -> dict:
        pending = state.get("pending")
        if pending:
            self.append_missing(pending["rows"])
            state = pending["next"]
            atomic_json(self.state_file, state)
        return state

    def record(self, event: str) -> bool:
        with self.locked():
            state = read_json(self.state_file, {"schema_version": 1, "generation": 0, "groups": {}})
            recovered = bool(state.get("pending"))
            state = self.recover(state)
            groups = dict(state["groups"])
            changes = []
            rescanned = False
            deadline = time.monotonic() + self.scan_timeout
            specs = self.root_specs()
            global_identity = [[label, str(path)] for group, label, path in specs if group == "global"]
            for group, identity in [("global", global_identity), ("project", str(self.project))]:
                group_key = group + ":" + digest(identity)
                previous = groups.get(group_key)
                if previous and all(stamp(Path(path)) == value for path, value in previous["watches"].items()):
                    continue
                rescanned = True
                current = self.snapshot(group, deadline)
                current["observed_generation"] = state["generation"] + 1
                old_skills = previous["skills"] if previous else {}
                new_skills = current["skills"]
                for key in sorted(old_skills.keys() | new_skills.keys()):
                    before, after = old_skills.get(key), new_skills.get(key)
                    covered = bool(previous)
                    if group == "global":
                        visible = after or before
                        owning_root = next((path for kind, label, path in specs
                                            if kind == "global" and label == visible["scope"]), None)
                        # Other profile views may contain this same physical root.
                        # Their latest absence is a removal; an older presence must
                        # not create duplicate changes or resurrection observations.
                        views = [view for name, view in groups.items() if name.startswith("global:")
                                 and owning_root is not None and str(owning_root) in view["watches"]]
                        if views:
                            latest = max(views, key=lambda view: view.get("observed_generation", 0))
                            before, covered = latest["skills"].get(key), True
                    if before == after:
                        continue
                    action = "remove" if after is None else "change" if before else "add" if covered else "observed"
                    visible = after or before
                    changes.append({
                        "schema_version": 1, "kind": "skill_state_change",
                        "id": digest([state["generation"] + 1, key, before, after]),
                        "occurred_at_utc": utc_now(), "action": action,
                        "event": {"add": "added", "change": "changed", "remove": "removed", "observed": "observed"}[action],
                        "hook_event": event, "skill_name": visible["skill_name"], "scope": visible["scope"],
                        "state_key": key, "source": visible["source"], "before": before, "after": after,
                        "usage": "unknown", "observation_boundary": "filesystem_metadata_not_install_or_model_acceptance",
                    })
                groups[group_key] = current
            if rescanned:
                next_state = {"schema_version": 1, "generation": state["generation"] + 1, "groups": groups}
                if changes:
                    atomic_json(self.state_file, {**state, "pending": {"rows": changes, "next": next_state}})
                    self.recover(read_json(self.state_file, {}))
                else:
                    atomic_json(self.state_file, next_state)
        if changes or recovered:
            self.run_status()
        return bool(changes or recovered)

    def run_status(self) -> None:
        try:
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/skills_status.py"),
                "--metadata-only", "--ledger", str(self.ledger), "--json", "--home", str(self.home),
            ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=self.status_timeout, check=False, cwd=self.project,
                env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1",
                     "CLAUDE_CONFIG_DIR": str(self.claude_root), "CODEX_HOME": str(self.codex_root)})
            if result.returncode:
                private_append(self.state_dir / "errors.jsonl", {
                    "schema_version": 1, "kind": "skill_recorder_error", "occurred_at_utc": utc_now(),
                    "stage": "metadata_status", "exit_code": result.returncode,
                })
        except Exception as error:
            self.error("metadata_status", error)

    def audit_instructions(self, payload: dict) -> None:
        raw_path = payload.get("file_path")
        if not isinstance(raw_path, str):
            raise ValueError("instruction_path_required")
        path = Path(raw_path).absolute()
        self.root_specs()  # Unsupported native roots stay unknown rather than fall back.
        project_file = path.is_relative_to(self.project)
        if self.project == self.home and any(path.is_relative_to(self.home / name) for name in (".claude", ".codex")):
            project_file = False  # A home launch does not re-enable an inactive profile.
        claude_file = path == self.claude_root / "CLAUDE.md" or path.is_relative_to(self.claude_root / "rules")
        codex_file = path in {self.codex_root / "AGENTS.md", self.codex_root / "AGENTS.override.md"}
        permitted = project_file or claude_file or codex_file
        safe_name = path.suffix == ".md" and not any(excluded(part) for part in path.parts)
        body_hash = None
        if permitted and safe_name and not path.is_symlink() and path.resolve() == path:
            body_hash = hashlib.sha256(bounded_read(path, MAX_SKILL)).hexdigest()
        reason = payload.get("load_reason")
        memory = payload.get("memory_type")
        with self.locked():
            private_append(self.state_dir / "instructions-loaded.jsonl", {
                "schema_version": 1, "kind": "instructions_loaded_observation", "occurred_at_utc": utc_now(),
                "session_id_sha256": digest(payload.get("session_id")) if isinstance(payload.get("session_id"), str) else None,
                 "locator": self.locator(path), "instruction_sha256": body_hash,
                "load_reason": reason if reason in {"session_start", "nested_traversal", "path_glob_match", "include", "compact"} else "unknown",
                "memory_type": memory if memory in {"User", "Project", "Local", "Managed"} else "unknown",
                "scope_status": "known" if body_hash else "unknown",
                "observation_boundary": "hook_observation_not_skill_invocation",
            })


class FailOpenParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid_arguments")


def main(argv: list[str] | None = None, *, environment: Mapping[str, str] | None = None) -> int:
    recorder = None
    try:
        parser = FailOpenParser(description=__doc__)
        parser.add_argument("--mode", choices=["record", "instructions", "watch-paths"], default="record")
        parser.add_argument("--home", type=Path, default=Path.home())
        parser.add_argument("--project-dir", type=Path)
        parser.add_argument("--state-dir", type=Path)
        parser.add_argument("--status-timeout", type=float, default=2.0)
        args = parser.parse_args(argv)
        if args.mode == "watch-paths":
            # Claude-only watch registration; no state/content scan or decision.
            print(json.dumps({"watchPaths": [str(args.home / ".agents/.skill-lock.json")]}))
            return 0
        state_dir = args.state_dir or args.home / ".local/state/native-agent-stack/skills"
        recorder = Recorder(args.home, args.project_dir or Path.cwd(), state_dir, status_timeout=args.status_timeout, environment=environment)
        data = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(data) > MAX_INPUT:
            raise ValueError("input_size_limit")
        payload = json.loads(data) if data.strip() else {"hook_event_name": "CurrencyTimer"}
        if not isinstance(payload, dict):
            raise ValueError("hook_object_required")
        cwd = args.project_dir or Path(payload.get("cwd", os.getcwd()))
        recorder = Recorder(args.home, cwd, state_dir, status_timeout=args.status_timeout, environment=environment)
        event = payload.get("hook_event_name", "unknown")
        if args.mode == "instructions":
            if event == "InstructionsLoaded":
                recorder.audit_instructions(payload)
        elif event in EVENTS:
            recorder.record(event)
    except (Exception, SystemExit) as error:
        if recorder is not None:
            recorder.error("hook", error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
