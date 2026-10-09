"""Exact native-reader permissions independent of the selecting JSON.

Adapter seam: repository tools/north-star/build_readiness.py Receipts.get/linked
at 0d86b53d1b8647cbf61085124403defe5b0fbc25, SHA-256 59428d63e09bab10e216e86af377891f8546aca6b3f9cc08c59d0803573b57b0.
The unchanged reader at 2ecce6ec2221704db642ddec8f70f7152ed2afb6 has the same hash.
Original native functions perform parsing, binding and rendering. This module
adds permission checks and native bounded no-symlink file handles only.
Python3.13 references: os.open(dir_fd, O_NOFOLLOW), os.fstat, os.fdopen and
contextvars.ContextVar at https://docs.python.org/3.13/library/os.html and
https://docs.python.org/3.13/library/contextvars.html.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import errno
import hashlib
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


POLICY_PATH = Path(__file__).with_name("source_policy.json")
MAX_POLICY_BYTES = 1_048_576
MAX_SOURCE_BYTES = 8 * 1024 * 1024
_BLOCKED = {"auth.json", "credentials.json", "credentials.toml", "credential.json",
            "client_secret.json", "client_secrets.json", "secrets.json", "settings.json",
            "config.toml", ".env", "environment.json", "environment.env"}


class SourcePolicyError(ValueError):
    """An input has no independent exact-role approval or violates its boundary."""


class SourceReadLimitError(SourcePolicyError):
    """An approved regular file exceeds the caller's bounded read size."""


def protected_path(relative):
    parts = PurePosixPath(relative).parts
    return any(part.lower() in _BLOCKED or part.lower().startswith(".env.")
               or part.lower().endswith(".env") or part.lower() == ".envrc"
               or re.fullmatch(r"(?:auth|credentials?|secrets?|env|environment)\.(?:json|toml|ya?ml|txt)", part.lower())
               or re.match(r"client[-_]secrets?(?:\.|$)", part.lower())
               or part.lower().startswith("e2e-truth-") for part in parts)


def _relative(value):
    if not isinstance(value, str) or not value:
        raise SourcePolicyError("source path must be a nonempty relative string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or path.as_posix() != value:
        raise SourcePolicyError("source path must be an exact normalized relative path")
    if protected_path(value):
        raise SourcePolicyError("protected source path rejected")
    return value


@contextmanager
def _directory(path):
    path = Path(path).absolute()
    descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def _check_target(path, *, allow_missing=False):
    try:
        with _directory(Path(path).parent) as directory:
            info = os.stat(Path(path).name, dir_fd=directory, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise SourcePolicyError("source must be a regular non-symlink file")
    except FileNotFoundError:
        if not allow_missing:
            raise
    except OSError as error:
        raise SourcePolicyError("source ancestor is a symlink or unavailable") from error


def _open_regular(path, *, mode="rb", buffering=-1, encoding=None, errors=None, newline=None, limit=MAX_SOURCE_BYTES):
    if mode not in {"r", "rb", "rt"}:
        raise SourcePolicyError("native source guard permits reads only")
    path = Path(path).absolute()
    if protected_path(path.as_posix()):
        raise SourcePolicyError("protected input cannot be opened as policy or source")
    with _directory(path.parent) as directory:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise SourcePolicyError("source is nonregular")
        if info.st_size > limit:
            # fstat reports this descriptor's size before fdopen or any read.
            # https://docs.python.org/3.13/library/os.html#os.fstat
            raise SourceReadLimitError("approved source exceeds the read bound")
        return os.fdopen(descriptor, mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular(path, limit):
    with _open_regular(path, limit=limit) as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise SourceReadLimitError("approved source exceeds the read bound")
    return raw


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise SourcePolicyError("duplicate JSON key")
            result[key] = value
        return result
    def constant(value):
        raise SourcePolicyError("non-JSON numeric constant")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise SourcePolicyError("policy/source index must be a JSON object")
    return value


class Policy:
    def __init__(self, document, receipt):
        if document.get("schema") != "local-pages-source-policy/1":
            raise SourcePolicyError("unsupported independent source policy")
        self.document, self.receipt = document, receipt
        self.permissions = {"source_index": document.get("source_index", [])}
        self.permissions.update({"source:" + key: paths for key, paths in document.get("sources", {}).items()})
        self.permissions.update({"linked:" + key: paths for key, paths in document.get("linked_receipts", {}).items()})
        self.permissions.update({"override:" + key: paths for key, paths in document.get("overrides", {}).items()})
        self.reader = document.get("native_reader", {})
        self.permissions["native_reader"] = [self.reader]
        self.allowed = {}
        for role, entries in self.permissions.items():
            if not isinstance(entries, list):
                raise SourcePolicyError("policy role requires an exact-path list")
            self.allowed[role] = set()
            for entry in entries:
                if not isinstance(entry, dict) or entry.get("root") not in {"repo", "state"}:
                    raise SourcePolicyError("policy entry requires a known root")
                self.allowed[role].add((entry["root"], _relative(entry.get("path"))))
        if not re.fullmatch(r"[0-9a-f]{64}", str(self.reader.get("sha256", ""))):
            raise SourcePolicyError("native reader requires an independently pinned hash")

    def validate(self, role, root, relative):
        relative = _relative(relative)
        if root not in {"repo", "state"} or (root, relative) not in self.allowed.get(role, set()):
            raise SourcePolicyError("source role/path has no independent approval: " + role)

    def validate_sources(self, spec):
        sources = spec.get("sources") if isinstance(spec, dict) else None
        if not isinstance(sources, dict):
            raise SourcePolicyError("native source index requires a sources object")
        for key, source in sources.items():
            if not isinstance(source, dict):
                raise SourcePolicyError("native source declaration must be an object")
            self.validate("source:" + key, source.get("root"), source.get("path"))

    def validate_index_path(self, root, state_root, spec_path):
        root = Path(root).absolute()
        spec_path = Path(spec_path)
        spec_path = spec_path.absolute() if spec_path.is_absolute() else root / spec_path
        try:
            relative = spec_path.relative_to(root).as_posix()
        except ValueError as error:
            raise SourcePolicyError("native source index escapes repository root") from error
        self.validate("source_index", "repo", relative)
        _check_target(spec_path)
        return spec_path

    def read_index(self, root, state_root, spec_path):
        path = self.validate_index_path(root, state_root, spec_path)
        spec = _json(_read_regular(path, MAX_SOURCE_BYTES))
        if spec.get("schema_version") != 1:
            raise SourcePolicyError("unsupported native source-index schema")
        self.validate_sources(spec)
        return path, spec

    def validate_override(self, key, path, root, state_root):
        """Bind a selected composer input to its exact independent role grant."""
        path = Path(path).absolute()
        roots = {"repo": Path(root).absolute(), "state": Path(state_root).absolute()}
        for source_root, base in roots.items():
            try:
                relative = path.relative_to(base).as_posix()
            except ValueError:
                continue
            self.validate("override:" + key, source_root, relative)
            _check_target(path)
            return path
        raise SourcePolicyError("source override escapes approved roots")


def load_policy(policy_path=POLICY_PATH):
    path = Path(policy_path).absolute()
    raw = _read_regular(path, MAX_POLICY_BYTES)
    return Policy(_json(raw), {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
                              "bytes": len(raw), "status": "independent exact native-source policy"})


def capture_policy(policy_path=POLICY_PATH):
    return load_policy(policy_path).receipt


def validate_index_path(root, state_root, spec_path, policy_path=POLICY_PATH):
    return load_policy(policy_path).validate_index_path(root, state_root, spec_path)


def validate_override(key, path, root, state_root, policy_path=POLICY_PATH):
    return load_policy(policy_path).validate_override(key, path, root, state_root)


class ArchitectureReads:
    """Authorize Architecture data roles before content or digest access.

    Exact grants come from the committed policy, never a catalog or receipt
    selecting another file. The one dynamic family has a fixed reviewed
    directory and a strict immutable-projection filename. Native permissions
    remain separately limited to repo/state; only design custody may use user.
    """

    limit_error = SourceReadLimitError

    def __init__(self, root, state_root, policy_path=POLICY_PATH, *, user_root=None):
        self.policy = load_policy(policy_path)
        self.roots = {"repo": Path(root).absolute(), "state": Path(state_root).absolute(),
                      "user": Path(user_root if user_root is not None else Path.home()).absolute()}
        self.allowed = {}
        entries = self.policy.document.get("architecture", {})
        if not isinstance(entries, dict):
            raise SourcePolicyError("Architecture permissions must be a role map")
        for role, paths in entries.items():
            if not isinstance(role, str) or not role.startswith("architecture_") or not isinstance(paths, list):
                raise SourcePolicyError("invalid Architecture exact-path role")
            self.allowed[role] = set()
            for record in paths:
                if not isinstance(record, dict) or record.get("root") not in self.roots:
                    raise SourcePolicyError("Architecture permission requires a known root")
                if record["root"] == "user" and role != "architecture_design":
                    raise SourcePolicyError("user root is permitted only for exact design custody")
                self.allowed[role].add((record["root"], _relative(record.get("path"))))
        self.families = self.policy.document.get("architecture_families", {})
        reviewed = {"architecture_adoption_snapshot": {
            "root": "state", "directory": "coordination/ns2604-coop/notes/adoption-evidence-20261008",
            "filename": "adoption-now-[a-f0-9]{16}\\.json",
        }}
        if not isinstance(self.families, dict) or any(reviewed.get(role) != record for role, record in self.families.items()):
            raise SourcePolicyError("Architecture family differs from its reviewed exact directory/form")

    def authorize(self, role, path):
        path = Path(path).absolute()
        for root, base in self.roots.items():
            try:
                relative = path.relative_to(base).as_posix()
            except ValueError:
                continue
            relative = _relative(relative)
            if (root, relative) in self.allowed.get(role, set()):
                return path
            family = self.families.get(role)
            if family and root == family["root"] and PurePosixPath(relative).parent.as_posix() == family["directory"] and re.fullmatch(family["filename"], path.name):
                return path
        raise SourcePolicyError("Architecture role/path has no independent approval: " + str(role))

    @contextmanager
    def open(self, role, path, max_bytes=MAX_SOURCE_BYTES):
        path = self.authorize(role, path)
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
            raise SourcePolicyError("Architecture read bound must be a positive integer")
        _check_target(path)
        try:
            handle = _open_regular(path, limit=max_bytes)
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise SourcePolicyError("Architecture source or ancestor is a symlink") from error
            raise
        with handle:
            yield handle

    def read(self, role, path, max_bytes=MAX_SOURCE_BYTES):
        path = self.authorize(role, path)
        with self.open(role, path, max_bytes=max_bytes) as handle:
            info = os.fstat(handle.fileno())
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise SourceReadLimitError("approved Architecture input exceeds its bounded read")
        return raw, {"path": str(path), "role": role, "sha256": hashlib.sha256(raw).hexdigest(),
                     "bytes": len(raw), "status": "independently authorized Architecture input",
                     "file_utc": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")}


@contextmanager
def guard_native(native, root, state_root, spec_path, *, policy_path=POLICY_PATH):
    """Guard every original native file read, including forced and linked inputs.

    The class and Path substitution is confined to this freshly loaded native
    module, never pathlib or a global reader. Role sites are bound by the exact
    native-reader hash, rather than values supplied by selecting JSON.
    """
    if getattr(native, "_independent_policy_active", False):
        raise SourcePolicyError("native module is already guarded")
    policy = load_policy(policy_path)
    roots = {"repo": Path(root).absolute(), "state": Path(state_root).absolute()}
    index_path, _ = policy.read_index(root, state_root, spec_path)
    reader_path = Path(native.__file__).absolute()
    try:
        reader_relative = reader_path.relative_to(roots["repo"]).as_posix()
    except ValueError as error:
        raise SourcePolicyError("native reader is outside the selected checkout") from error
    policy.validate("native_reader", "repo", reader_relative)
    if hashlib.sha256(_read_regular(reader_path, MAX_SOURCE_BYTES)).hexdigest() != policy.reader["sha256"]:
        raise SourcePolicyError("native reader differs from the approved read seam")
    original_receipts, original_path, original_build = native.Receipts, native.Path, native.build
    active_input = ContextVar("local_pages_native_input", default=None)
    base_path = type(Path())

    class BoundedPath(base_path):
        def open(self, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
            active = active_input.get()
            if active is None:
                raise SourcePolicyError("native file open has no declared input role")
            role, source_root, relative = active
            policy.validate(role, source_root, relative)
            if Path(self).absolute() != roots[source_root] / relative:
                raise SourcePolicyError("native file open differs from its approved role/path")
            return _open_regular(self, mode=mode, buffering=buffering, encoding=encoding, errors=errors, newline=newline)

    class GuardedReceipts(original_receipts):
        def __init__(self, selected_root, selected_state, sources):
            policy.validate_sources({"sources": sources})
            if Path(selected_root).absolute() != roots["repo"] or Path(selected_state).absolute() != roots["state"]:
                raise SourcePolicyError("native receipt roots differ from approved roots")
            self.direct_names = set(sources)
            self.link_roles = {}
            super().__init__(selected_root, selected_state, sources)

        def get(self, name):
            source = self.sources[name]
            role = "source:" + name if name in self.direct_names else self.link_roles.get(name)
            if role is None:
                raise SourcePolicyError("native receipt has no approved role")
            policy.validate(role, source.get("root"), source.get("path"))
            _check_target(roots[source["root"]] / source["path"], allow_missing=True)
            token = active_input.set((role, source["root"], source["path"]))
            try:
                return super().get(name)
            finally:
                active_input.reset(token)

        def linked(self, source_root, path, expected=None):
            caller = inspect.currentframe().f_back
            if caller.f_code is native.build_layers.__code__ and caller.f_lineno == 224:
                role = "linked:supporting"
            elif caller.f_code is native.build_sdks.__code__ and caller.f_lineno in {255, 271}:
                role = "linked:sdk_item" if caller.f_lineno == 255 else "linked:sdk_raw"
            else:
                raise SourcePolicyError("native linked receipt has an unapproved call role")
            policy.validate(role, source_root, path)
            name = f"{source_root}:{path}" + (f"@{expected}" if expected else "")
            self.link_roles[name] = role
            return super().linked(source_root, path, expected)

    def guarded_build(selected_root=root, selected_state=state_root, selected_spec=spec_path, **kwargs):
        # Preserve the native public keyword names used by its callers.
        selected_root = kwargs.pop("root", selected_root)
        selected_state = kwargs.pop("state_root", selected_state)
        selected_spec = kwargs.pop("spec_path", selected_spec)
        if kwargs:
            raise TypeError("unexpected native build keyword")
        approved_index = policy.validate_index_path(selected_root, selected_state, selected_spec)
        token = active_input.set(("source_index", "repo", approved_index.relative_to(roots["repo"]).as_posix()))
        try:
            return original_build(BoundedPath(selected_root), BoundedPath(selected_state), BoundedPath(approved_index))
        finally:
            active_input.reset(token)

    native._independent_policy_active = True
    native.Receipts, native.Path, native.build = GuardedReceipts, BoundedPath, guarded_build
    try:
        yield policy
    finally:
        native.Receipts, native.Path, native.build = original_receipts, original_path, original_build
        del native._independent_policy_active
