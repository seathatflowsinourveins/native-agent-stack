"""Patch policy for the OpenHands resolver: the host-executed set and the patch validator.

Plan section 2 step 6 and open item 23. Both are local compositions of the cited
mechanisms below. tests/test_runtime_worker_openhands_resolver.py holds our
integration checks; they are not upstream acceptance.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
import os
import posixpath
import re
import subprocess
import unicodedata


def normalize_owned(paths):
    """The coordinator's --owned-path list as sorted, unique repository paths.

    Plan section 2 step 0: owned paths come from the coordinator, never from issue
    text. An entry is a relative POSIX path with no empty, "." or ".." component;
    a trailing "/" is dropped, and an entry covers itself and every path under it.
    """
    if isinstance(paths, (str, bytes)) or not paths:
        raise ValueError("owned_paths_required")
    owned = set()
    for path in paths:
        if (not isinstance(path, str) or not path or path != path.strip() or path.startswith("/")
                or any(ch in path for ch in "\\\0\n\r")):
            raise ValueError("invalid_owned_path")
        path = path.rstrip("/")
        if not path or any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError("invalid_owned_path")
        owned.add(path)
    return sorted(owned)


def is_owned(path, owned):
    return any(path == entry or path.startswith(entry + "/") for entry in owned)


# -- Tree readers

# Neutral configuration as dispatch.py:196-199 (git.txt GIT_CONFIG_GLOBAL and
# GIT_CONFIG_NOSYSTEM); GIT_NO_REPLACE_OBJECTS (git.txt) keeps replace refs out.
GIT_ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1"}


class GitTree:
    """One commit's tree, read with local git only.

    git-ls-tree(1) `-r -z --full-tree` lists every blob and gitlink with its mode
    and object id; git-cat-file(1) reads a blob by id. No network, no hooks.
    """

    def __init__(self, repo, commit, *, git="git"):
        self.repo, self.git = str(repo), git
        self.commit = self._run("rev-parse", "--verify", "--end-of-options",
                                f"{commit}^{{commit}}").decode("ascii").strip()
        self._entries = None

    def _run(self, *args):
        return subprocess.run([self.git, "-C", self.repo, *args], check=True, capture_output=True,
                              env=GIT_ENV, timeout=120).stdout

    def entries(self):
        if self._entries is None:
            entries = {}
            for record in self._run("ls-tree", "-r", "-z", "--full-tree", self.commit).split(b"\0"):
                if record:
                    meta, _, raw = record.partition(b"\t")
                    mode, kind, oid = meta.decode("ascii").split(" ")
                    entries[raw.decode("utf-8", "surrogateescape")] = (mode, kind, oid)
            self._entries = entries
        return self._entries

    def read(self, path):
        mode, kind, oid = self.entries()[path]
        if kind != "blob":
            raise KeyError(path)
        return self._run("cat-file", "blob", oid)


class MemoryTree:
    """An in-memory stand-in for GitTree: {path: bytes or str}, with optional modes."""

    def __init__(self, files, modes=None):
        self.files = {path: data.encode("utf-8") if isinstance(data, str) else data
                      for path, data in files.items()}
        self.modes = dict(modes or {})

    def entries(self):
        return {path: (self.modes.get(path, "100644"), "blob", "0" * 40) for path in self.files}

    def read(self, path):
        return self.files[path]


def parent_dirs(paths):
    dirs = set()
    for path in paths:
        parts = path.split("/")
        for end in range(1, len(parts)):
            dirs.add("/".join(parts[:end]))
    return dirs


# -- Unicode and filesystem aliases

# Code points HFS+ ignores in names: git utf8.c:701-719 (next_hfs_char) at v2.43.0.
HFS_IGNORABLE = frozenset([*range(0x200C, 0x2010), *range(0x202A, 0x202F), *range(0x206A, 0x2070), 0xFEFF])


def fold(path):
    """The key two names share when a filesystem can treat them as one.

    Unicode 16.0 section 3.13 D145 canonical caseless matching,
    NFD(toCasefold(NFD(X))); HFS+ ignorable code points dropped (git utf8.c:701-719);
    NTFS trailing spaces and periods trimmed per component (git path.c:1386-1388).
    APFS, HFS+, FAT and NTFS are case-insensitive to git (git-config core.ignoreCase).
    """
    text = unicodedata.normalize("NFD", unicodedata.normalize("NFD", path).casefold())
    text = "".join(ch for ch in text if ord(ch) not in HFS_IGNORABLE)
    return "/".join(part.rstrip(" .") for part in text.split("/"))


# -- The host-executed set (plan section 2 step 6; open item 23)

# Inputs, not outputs: Claude Code's project settings file, and the directory the
# repository's relative core.hooksPath names (scripts/git-hooks/pre-commit:2-3;
# docs/secret-storage.md:199-200). Everything else is derived from their text.
SETTINGS = ".claude/settings.json"
HOOKS_DIR = "scripts/git-hooks"
SETTINGS_RULE_KEYS = ("permissions", "$schema")
CODE_SUFFIXES = frozenset({".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl"})
# importlib and runpy entry points that run a file by path, not by module name.
# A script started through subprocess with a computed path is not traced (RESOLVER.md).
PATH_LOADERS = frozenset({"spec_from_file_location", "SourceFileLoader", "SourcelessFileLoader",
                          "run_path", "exec_module", "load_module"})
_TOKEN_SPLIT = re.compile(r"[\s;|&()<>`=,{}\[\]]+")
_VARIABLE_PREFIX = re.compile(r"^(?:\$[A-Za-z_][A-Za-z0-9_]*|\$)?/*")
_DOTTED = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
_PY_BASENAME = re.compile(r"[A-Za-z0-9_.-]+\.py")


class DerivationError(RuntimeError):
    """The host-executed set cannot be derived; the validator then refuses."""


@dataclass(frozen=True)
class HostExecuted:
    files: frozenset
    dirs: frozenset
    reasons: tuple = ()
    _folded: tuple = field(default=(), compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_folded", (frozenset(fold(p) for p in self.files),
                                             frozenset(fold(d) for d in self.dirs)))

    def covers(self, path):
        return path in self.files or any(path == d or path.startswith(d + "/") for d in self.dirs)

    def covers_folded(self, path):
        files, dirs = self._folded
        key = fold(path)
        return key in files or any(key == d or key.startswith(d + "/") for d in dirs)


def settings_strings(settings):
    """Every string in project settings except permission rules and $schema.

    Hook handlers (`hooks.<event>[].hooks[].command`), `statusLine.command` and the
    credential helpers are all strings Claude Code runs (code.claude.com/docs/en/settings,
    fetched 2026-09-28, names hooks and apiKeyHelper among live-reloaded settings);
    taking every string keeps the derivation independent of that key list.
    """
    found = []

    def walk(value):
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            found.append(value)

    for key, value in settings.items():
        if key not in SETTINGS_RULE_KEYS:
            walk(value)
    return found


def executable_lines(data):
    """A hook script without its whole-line comments (sh(1): `#` starts a comment)."""
    lines = data.decode("utf-8", "replace").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def resolve_module(parts, roots, blobs, dirs):
    """Repository files `import a.b.c` runs, searched from each root in turn.

    Python's import system: a package runs its __init__.py, a directory without one
    is a namespace package portion (docs.python.org/3/reference/import.html,
    "Regular packages" and "Namespace packages"), and a module is <name>.py.
    """
    found = set()
    for root in roots:
        prefix = root + "/" if root else ""
        for end in range(1, len(parts) + 1):
            base = prefix + "/".join(parts[:end])
            if base + "/__init__.py" in blobs:
                found.add(base + "/__init__.py")
                continue
            if base + ".py" in blobs:
                found.add(base + ".py")
                break
            if base in dirs:
                continue
            break
    return found


def names_in_text(text, blobs, dirs):
    """(kind, path) for each tracked path a hook text names.

    Local composition: quotes are dropped so `"${VAR}"/x` reads as one word, words
    split on shell metacharacters, and a leading `$VAR/`, `/` or `./` is stripped.
    A word is a tracked blob, a tracked directory (only when written with a "/"), or
    a dotted module name (`python3 -m a.b`, `unittest` ids). The miss-oracle in the
    tests is independent of this tokenizer.
    """
    found = set()
    for raw in _TOKEN_SPLIT.split(text.replace('"', "").replace("'", "")):
        token = _VARIABLE_PREFIX.sub("", raw, count=1)
        while token.startswith("./"):
            token = token[2:]
        token = token.rstrip("/")
        if not token:
            continue
        if token in blobs:
            found.add(("path", token))
        elif "/" in raw and token in dirs:
            found.add(("dir", token))
        elif _DOTTED.fullmatch(token):
            found.update(("module", path) for path in resolve_module(token.split("."), ("",), blobs, dirs))
    return found


def _literal_runs(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _literal_runs(node.left) + _literal_runs(node.right)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    return [None]


def _path_literals(node):
    """String paths a node spells: `a / "b" / "c"` runs, os.path.join literals, "x/y"."""
    found = set()
    for child in ast.walk(node):
        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.Div):
            run = []
            for piece in _literal_runs(child) + [None]:
                if piece is None:
                    if run:
                        found.add("/".join(run))
                    run = []
                else:
                    run.append(piece)
        elif (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "join"
              and child.args and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in child.args)):
            found.add("/".join(a.value for a in child.args))
        elif isinstance(child, ast.Constant) and isinstance(child.value, str) and "/" in child.value:
            found.add(child.value)
    normalized = set()
    for literal in found:
        literal = literal.strip()
        while literal.startswith("./"):
            literal = literal[2:]
        literal = literal.strip("/")
        if literal and "\n" not in literal and len(literal) < 512:
            normalized.add(literal)
    return normalized


def _is_sys_path_call(node):
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr in {"insert", "append", "extend"}
            and isinstance(func.value, ast.Attribute) and func.value.attr == "path"
            and isinstance(func.value.value, ast.Name) and func.value.value.id == "sys")


def _parent(value):
    if value is None or value[1] is None:
        return None
    kind, path = value
    if kind == "file":
        return ("dir", path)
    return ("dir", None) if path == "" else ("dir", posixpath.dirname(path))


def _file_relative(node, env, here):
    """The repository location a `Path(__file__)`-style expression names.

    ("file", dir) is the file itself; ("dir", path) a directory relative to the
    repository root, "" for the root and None above it. Covers Path/str/os.fspath,
    .resolve(), .absolute(), .parent, .parents[k], os.path.dirname/abspath/realpath,
    `/ "literal"` and names bound to such expressions; anything else is unknown.
    """
    if isinstance(node, ast.Name):
        return ("file", here) if node.id == "__file__" else env.get(node.id)
    if isinstance(node, ast.Call):
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if called in {"Path", "PurePath", "PosixPath", "str", "fspath", "abspath", "realpath", "normpath"}:
            return _file_relative(node.args[0], env, here) if len(node.args) == 1 else None
        if called in {"resolve", "absolute"} and isinstance(func, ast.Attribute) and not node.args:
            return _file_relative(func.value, env, here)
        if called == "dirname" and len(node.args) == 1:
            return _parent(_file_relative(node.args[0], env, here))
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return _parent(_file_relative(node.value, env, here))
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents"
            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int) and node.slice.value >= 0):
        value = _file_relative(node.value.value, env, here)
        for _ in range(node.slice.value + 1):
            value = _parent(value)
        return value
    if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, str)):
        base = _file_relative(node.left, env, here)
        if base and base[0] == "dir" and base[1] is not None:
            joined = posixpath.normpath(posixpath.join(base[1] or ".", node.right.value))
            return None if joined.startswith("..") else ("dir", "" if joined == "." else joined)
    return None


def python_references(path, source, blobs, dirs):
    """Repository files and directories one Python file imports or runs by path.

    Imports resolve from the repository root, where the pre-push runner puts the
    tree (scripts/git-hooks/pre-push:93-94), and from the file's own directory,
    where `python3 file.py` puts it (docs.python.org/3/library/sys.html#sys.path).
    A file loaded by path through importlib or runpy is traced as a file
    (tests/test_blind_checkout.py:22-34 loads tools/sota-convergence/blind_checkout.py).
    A directory a file puts on sys.path becomes a directory rule, because anything
    placed there can be imported lazily: blind_checkout.py:419-421,964 and
    lane_packets.py:51-54 add tools/sota-convergence, so plan open item 23 denies
    that directory rather than tracing its lazy imports.
    """
    module = ast.parse(source, filename=path)
    here = posixpath.dirname(path)
    roots = tuple(dict.fromkeys((here, "")))
    env = {}
    for node in sorted((n for n in ast.walk(module) if isinstance(n, (ast.Assign, ast.AnnAssign)) and n.value),
                       key=lambda n: (n.lineno, n.col_offset)):
        value = _file_relative(node.value, env, here)
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
            if isinstance(target, ast.Name) and value is not None:
                env[target.id] = value
    files, rule_dirs, names, basenames = set(), set(), set(), set()
    for node in ast.walk(module):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and _PY_BASENAME.fullmatch(node.value):
            basenames.add(node.value)
        if isinstance(node, ast.Import):
            for alias in node.names:
                files |= resolve_module(alias.name.split("."), roots, blobs, dirs)
        elif isinstance(node, ast.ImportFrom):
            prefix = node.module.split(".") if node.module else []
            if node.level:
                base = here.split("/") if here else []
                if node.level - 1 > len(base):
                    continue
                search = ("/".join(base[:len(base) - (node.level - 1)]),)
            else:
                search = roots
            if prefix:
                files |= resolve_module(prefix, search, blobs, dirs)
            for alias in node.names:
                files |= resolve_module(prefix + [alias.name], search, blobs, dirs)
        elif isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if (called in {"import_module", "__import__"} and node.args and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                files |= resolve_module(node.args[0].value.split("."), roots, blobs, dirs)
            if _is_sys_path_call(node):
                for arg in node.args:
                    rule_dirs |= {literal for literal in _path_literals(arg) if literal in dirs}
                    target = _file_relative(arg, env, here)
                    if target and target[0] == "dir" and target[1] and target[1] in dirs:
                        rule_dirs.add(target[1])
    if names & PATH_LOADERS:
        literals = _path_literals(module)
        files |= {literal for literal in literals if literal in blobs and literal.endswith(".py")}
        for directory in {literal for literal in literals if literal in dirs} | {here}:
            files |= {f"{directory}/{name}" if directory else name for name in basenames} & blobs
    return files, rule_dirs


def _is_code(tree, entries, path):
    if posixpath.splitext(path)[1] in CODE_SUFFIXES or entries[path][0] == "100755":
        return True
    return tree.read(path)[:2] == b"#!"


def _is_python(tree, path):
    if path.endswith(".py"):
        return True
    first = tree.read(path).split(b"\n", 1)[0]
    return first.startswith(b"#!") and b"python" in first


def derive_host_executed(tree):
    """Derive, at the tree's commit, every path the owner's host may execute.

    Plan section 2 step 6: the hook commands in .claude/settings.json and the scripts
    in scripts/git-hooks/*, plus the repository files each of them imports or runs,
    and whole directories where code is run by path (open item 23).
    """
    entries = tree.entries()
    blobs = {path for path, entry in entries.items() if entry[1] == "blob"}
    dirs = parent_dirs(entries)
    files, rule_dirs, reasons, queue = set(), set(), [], []

    def add_file(path, why, python=False):
        if path not in files:
            files.add(path)
            reasons.append((path, why))
            if python:
                queue.append(path)

    def add_dir(path, why):
        if path and path not in rule_dirs:
            rule_dirs.add(path)
            reasons.append((path + "/", why))

    texts = []
    if SETTINGS in blobs:
        add_file(SETTINGS, "Claude Code project settings")
        add_dir(posixpath.dirname(SETTINGS), "Claude Code project configuration directory")
        try:
            settings = json.loads(tree.read(SETTINGS))
        except (ValueError, UnicodeDecodeError) as error:
            raise DerivationError("settings_not_json") from error
        if not isinstance(settings, dict):
            raise DerivationError("settings_not_object")
        texts += [(SETTINGS, text) for text in settings_strings(settings)]
    hooks = sorted(path for path in blobs if path.startswith(HOOKS_DIR + "/"))
    if hooks:
        add_dir(HOOKS_DIR, "core.hooksPath directory")
    for hook in hooks:
        add_file(hook, "git hook", python=_is_python(tree, hook))
        texts.append((hook, executable_lines(tree.read(hook))))
    for source, text in texts:
        for kind, path in sorted(names_in_text(text, blobs, dirs)):
            if kind == "dir":
                add_dir(path, f"named by {source}")
            elif kind == "module":
                add_file(path, f"module named by {source}", python=True)
            else:
                add_file(path, f"named by {source}", python=_is_python(tree, path))
                if _is_code(tree, entries, path):
                    add_dir(posixpath.dirname(path), f"{source} runs {path} by path")
    parsed = set()
    while queue:
        path = queue.pop()
        if path in parsed:
            continue
        parsed.add(path)
        try:
            found, found_dirs = python_references(path, tree.read(path).decode("utf-8"), blobs, dirs)
        except (SyntaxError, UnicodeDecodeError, ValueError) as error:
            raise DerivationError(f"unparseable_python:{path}") from error
        for ref in sorted(found):
            add_file(ref, f"imported or loaded by {path}", python=ref.endswith(".py"))
        for directory in sorted(found_dirs):
            add_dir(directory, f"code run by path from {path}")
    return HostExecuted(frozenset(files), frozenset(rule_dirs), tuple(reasons))


# -- Parsing the exported patch

class PatchParseError(ValueError):
    def __init__(self, code, line=None):
        super().__init__(code if line is None else f"{code} at line {line}")
        self.code, self.line = code, line


@dataclass(frozen=True)
class FileChange:
    status: str
    old_path: str | None
    new_path: str | None
    old_mode: str | None
    new_mode: str | None
    binary: bool


# git Documentation/diff-generate-patch.txt:34-44 at v2.43.0: the extended headers.
_MODE = r"[0-7]{6}"
_EXTENDED = (
    ("old mode ", "old_mode", _MODE), ("new mode ", "new_mode", _MODE),
    ("deleted file mode ", "deleted_mode", _MODE), ("new file mode ", "new_file_mode", _MODE),
    ("copy from ", "copy_from", None), ("copy to ", "copy_to", None),
    ("rename from ", "rename_from", None), ("rename to ", "rename_to", None),
    ("similarity index ", "similarity", r"\d{1,3}%"), ("dissimilarity index ", "dissimilarity", r"\d{1,3}%"),
    ("index ", "index", r"[0-9a-f]{7,64}\.\.[0-9a-f]{7,64}(?: [0-7]{6})?"),
)
_HUNK = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*")
# git quote.c (unquote_c_style): the escapes core.quotePath output uses.
_C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, "\\": 92, '"': 34}
_MISSING = object()


def _take_quoted(text, line):
    """One C-quoted name at the start of text (diff-generate-patch.txt:62-63)."""
    out, index = bytearray(), 1
    while index < len(text):
        ch = text[index]
        if ch == '"':
            try:
                return out.decode("utf-8"), text[index + 1:]
            except UnicodeDecodeError:
                raise PatchParseError("path_not_utf8", line) from None
        if ch == "\\":
            escape = text[index + 1:index + 2]
            if escape in _C_ESCAPES:
                out.append(_C_ESCAPES[escape])
                index += 2
                continue
            octal = text[index + 1:index + 4]
            if re.fullmatch(r"[0-3][0-7]{2}", octal):
                out.append(int(octal, 8))
                index += 4
                continue
            raise PatchParseError("bad_quoting", line)
        out += ch.encode("utf-8")
        index += 1
    raise PatchParseError("bad_quoting", line)


def _name(value, line, prefix=None):
    if value.startswith('"'):
        value, rest = _take_quoted(value, line)
        if rest:
            raise PatchParseError("trailing_text", line)
    if prefix is not None:
        if not value.startswith(prefix):
            raise PatchParseError("missing_prefix", line)
        value = value[len(prefix):]
    return value


def _header_names(rest, line):
    """The names on a `diff --git` line when they read unambiguously.

    As git apply.c:1170 (git_header_name): quoted names parse directly; unquoted
    names are trusted only when both halves are the same path. Otherwise the rename,
    copy or ---/+++ lines supply the names.
    """
    if rest.startswith('"'):
        first, tail = _take_quoted(rest, line)
        if not tail.startswith(" "):
            raise PatchParseError("bad_diff_header", line)
        return _name(first, line, "a/"), _name(tail[1:], line, "b/")
    if rest.endswith('"'):
        split = rest.rfind(' "')
        if split < 0:
            raise PatchParseError("bad_diff_header", line)
        return _name(rest[:split], line, "a/"), _name(rest[split + 1:], line, "b/")
    if len(rest) >= 7 and (len(rest) - 5) % 2 == 0:
        half = (len(rest) - 5) // 2
        first, separator, second = rest[:half + 2], rest[half + 2], rest[half + 3:]
        if separator == " " and first.startswith("a/") and second.startswith("b/") and first[2:] == second[2:]:
            return first[2:], second[2:]
    return None, None


def _side(value, prefix, line):
    # git adds a trailing TAB after a ---/+++ name that contains a space (observed
    # in the export this parser is tested against).
    if value.endswith("\t"):
        value = value[:-1]
    return None if value == "/dev/null" else _name(value, line, prefix)


def _extended_header(text, line):
    for prefix, key, pattern in _EXTENDED:
        if text.startswith(prefix):
            value = text[len(prefix):]
            if pattern is None:
                return key, _name(value, line)
            if not re.fullmatch(pattern, value):
                raise PatchParseError(f"bad_{key}", line)
            return key, value
    raise PatchParseError("unexpected_line", line)


def _skip_hunk(lines, index):
    match = _HUNK.fullmatch(lines[index])
    if not match:
        raise PatchParseError("bad_hunk_header", index + 1)
    old = int(match[2]) if match[2] is not None else 1
    new = int(match[4]) if match[4] is not None else 1
    index += 1
    while old > 0 or new > 0:
        if index >= len(lines):
            raise PatchParseError("truncated_hunk", index + 1)
        line = lines[index]
        tag = line[:1]
        if tag == "\\":
            pass
        elif tag == " " or line == "":
            old, new = old - 1, new - 1
        elif tag == "-":
            old -= 1
        elif tag == "+":
            new -= 1
        else:
            raise PatchParseError("bad_hunk_line", index + 1)
        if old < 0 or new < 0:
            raise PatchParseError("hunk_overrun", index + 1)
        index += 1
    if index < len(lines) and lines[index].startswith("\\"):
        index += 1
    return index


def _agree(values, line):
    known = {value for value in values if value is not None}
    if len(known) != 1:
        raise PatchParseError("ambiguous_path" if not known else "path_mismatch", line)
    return known.pop()


def _change(header, info, old_side, new_side, binary, line):
    a_name, b_name = header
    sides = [] if old_side is _MISSING else [old_side, new_side]
    renamed = {"rename_from", "rename_to"} & set(info)
    copied = {"copy_from", "copy_to"} & set(info)
    created, deleted = "new_file_mode" in info, "deleted_mode" in info
    if ("old_mode" in info) != ("new_mode" in info) or sum(map(bool, (renamed, copied, created, deleted))) > 1:
        raise PatchParseError("inconsistent_headers", line)
    index_mode = info["index"].partition(" ")[2] or None if "index" in info else None
    if renamed or copied:
        kind = "rename" if renamed else "copy"
        if {f"{kind}_from", f"{kind}_to"} - set(info):
            raise PatchParseError("inconsistent_headers", line)
        old_path = _agree([info[f"{kind}_from"], a_name] + sides[:1], line)
        new_path = _agree([info[f"{kind}_to"], b_name] + sides[1:], line)
        status = "renamed" if renamed else "copied"
        old_mode = info.get("old_mode", index_mode)
        new_mode = info.get("new_mode", index_mode)
    elif created:
        if sides and sides[0] is not None:
            raise PatchParseError("inconsistent_headers", line)
        old_path, new_path = None, _agree([a_name, b_name] + sides[1:], line)
        status, old_mode, new_mode = "added", None, info["new_file_mode"]
    elif deleted:
        if sides and sides[1] is not None:
            raise PatchParseError("inconsistent_headers", line)
        old_path, new_path = _agree([a_name, b_name] + sides[:1], line), None
        status, old_mode, new_mode = "deleted", info["deleted_mode"], None
    else:
        if sides and None in sides:
            raise PatchParseError("inconsistent_headers", line)
        old_path = new_path = _agree([a_name, b_name] + sides, line)
        status = "modified"
        old_mode = info.get("old_mode", index_mode)
        new_mode = info.get("new_mode", index_mode)
    return FileChange(status, old_path, new_path, old_mode, new_mode, binary)


def parse_patch(text):
    """Parse `git diff` output into file changes; anything else fails closed.

    Grammar: git Documentation/diff-generate-patch.txt:34-44 (extended headers) and
    :62-63 (quoted names) at v2.43.0; "Binary files ... differ" and "GIT binary
    patch" as git apply.c:2167,2186 recognise them. Hunk lengths are counted from
    each @@ header, so no line can pass for a header it is not.
    """
    if not text:
        return []
    if not text.endswith("\n"):
        raise PatchParseError("missing_final_newline")
    lines = text[:-1].split("\n")
    changes, index = [], 0
    while index < len(lines):
        start = index + 1
        if not lines[index].startswith("diff --git "):
            raise PatchParseError("leading_text" if not changes else "expected_diff_header", start)
        header = _header_names(lines[index][len("diff --git "):], start)
        index += 1
        info = {}
        while index < len(lines) and not lines[index].startswith(
                ("diff --git ", "--- ", "+++ ", "Binary files ", "GIT binary patch", "@@")):
            key, value = _extended_header(lines[index], index + 1)
            if key in info:
                raise PatchParseError("duplicate_header", index + 1)
            info[key] = value
            index += 1
        binary, old_side, new_side = False, _MISSING, _MISSING
        if index < len(lines) and lines[index].startswith("Binary files "):
            if not lines[index].endswith(" differ"):
                raise PatchParseError("bad_binary_line", index + 1)
            binary = True
            index += 1
        elif index < len(lines) and lines[index] == "GIT binary patch":
            binary = True
            index += 1
            while index < len(lines) and not lines[index].startswith("diff --git "):
                index += 1
        elif index < len(lines) and lines[index].startswith("--- "):
            old_side = _side(lines[index][4:], "a/", index + 1)
            index += 1
            if index >= len(lines) or not lines[index].startswith("+++ "):
                raise PatchParseError("missing_new_side", index + 1)
            new_side = _side(lines[index][4:], "b/", index + 1)
            index += 1
            if index >= len(lines) or not lines[index].startswith("@@"):
                raise PatchParseError("missing_hunk", index + 1)
            while index < len(lines) and lines[index].startswith("@@"):
                index = _skip_hunk(lines, index)
        elif index < len(lines) and not lines[index].startswith("diff --git "):
            raise PatchParseError("unexpected_line", index + 1)
        changes.append(_change(header, info, old_side, new_side, binary, start))
    return changes


# -- The validator (plan section 2 step 6)

# Instruction files, case-folded, at any depth: Codex prefers AGENTS.override.md
# over AGENTS.md (developers.openai.com/codex/guides/agents-md) and Claude Code loads
# CLAUDE.local.md alongside CLAUDE.md (code.claude.com/docs/en/memory), both fetched
# 2026-09-28 per the plan.
INSTRUCTION_FILES = frozenset({"agents.md", "agents.override.md", "claude.md", "claude.local.md"})
ALLOWED_MODES = frozenset({"100644", "100755"})


def path_problems(path):
    """Refusals that depend on the name alone.

    Unsafe names end the check. NTFS alternate data streams (":"), 8.3 short names
    ("~" and a digit) and trailing spaces or periods follow git path.c:1382-1418;
    HFS+ ignorable code points follow git utf8.c:701-719.
    """
    parts = path.split("/")
    if (not path or path.startswith("/") or any(part in ("", ".", "..") for part in parts)
            or any(ord(ch) < 32 or ch in "\\\x7f" for ch in path)):
        return ["unsafe_path"]
    problems = set()
    if any(ord(ch) in HFS_IGNORABLE for ch in path):
        problems.add("hfs_ignorable_character")
    for part in parts:
        if ":" in part:
            problems.add("ntfs_stream")
        if re.search(r"~[0-9]", part):
            problems.add("ntfs_short_name")
        if part != part.rstrip(" ."):
            problems.add("ntfs_trailing_dot_or_space")
    return sorted(problems)


def _rule_reasons(path, owned, host, top_level, folded_existing):
    problems = path_problems(path)
    if problems == ["unsafe_path"]:
        return {("unsafe_path", path)}
    reasons = {(problem, path) for problem in problems}
    raw_parts, folded_parts = path.split("/"), fold(path).split("/")
    git_internal = any(part.startswith(".git") for part in raw_parts + folded_parts)
    if folded_parts[0] == ".github":
        reasons.add(("github_path", path))
    elif git_internal:
        reasons.add(("git_path", path))
    if folded_parts[-1] in INSTRUCTION_FILES:
        reasons.add(("instruction_file", path))
    host_hit = host.covers(path) or host.covers_folded(path)
    if host_hit:
        reasons.add(("host_executed", path))
    if any(part.startswith(".") for part in raw_parts + folded_parts):
        if not (path in owned and not host_hit and not git_internal):
            reasons.add(("dot_path", path))
    if not is_owned(path, owned):
        reasons.add(("not_owned", path))
    if raw_parts[0] not in top_level:
        reasons.add(("new_top_level_entry", path))
    for end in range(1, len(raw_parts) + 1):
        prefix = "/".join(raw_parts[:end])
        if folded_existing.get(fold(prefix), set()) - {prefix}:
            reasons.add(("case_or_unicode_alias", path))
            break
    return reasons


def validate_patch(patch_text, *, tree, owned):
    """Plan section 2 step 6: accept the exported patch only when every rule holds.

    V0 moved only a patch out of the sandbox and applied it on the host
    (OpenHands/OpenHands@7bc33009 issue_resolver.py:323-400; send_pull_request.py:
    139-174, per the plan). The rules are a local composition. The host-executed set
    is derived here from `tree`, the base commit, never passed in by hand.
    Status "empty" or "refused" means no GitHub write, only a receipt.
    """
    owned = normalize_owned(owned)
    digest = hashlib.sha256(patch_text.encode("utf-8", "surrogateescape")).hexdigest()
    verdict = {"status": "refused", "patch_sha256": digest, "reasons": [], "paths": [], "files": []}
    if not patch_text.strip():
        verdict["status"] = "empty"
        return verdict
    try:
        changes = parse_patch(patch_text)
    except PatchParseError as error:
        verdict["reasons"] = [{"reason": "unparseable_patch", "path": "", "detail": error.code}]
        return verdict
    try:
        host = derive_host_executed(tree)
    except DerivationError as error:
        verdict["reasons"] = [{"reason": "host_executed_derivation_failed", "path": "", "detail": str(error)}]
        return verdict
    entries = tree.entries()
    top_level = {path.split("/", 1)[0] for path in entries}
    folded_existing = {}
    for path in set(entries) | parent_dirs(entries):
        folded_existing.setdefault(fold(path), set()).add(path)
    reasons, touched = set(), set()
    for change in changes:
        label = change.new_path or change.old_path
        base = entries.get(change.old_path) if change.old_path is not None else None
        modes = [change.old_mode, change.new_mode] + ([base[0]] if base else [])
        for mode in modes:
            if mode == "120000":
                reasons.add(("symlink", label))
            elif mode == "160000":
                reasons.add(("gitlink", label))
            elif mode is not None and mode not in ALLOWED_MODES:
                reasons.add(("unsupported_mode", label))
        if change.binary:
            reasons.add(("binary_hunk", label))
        if change.old_path is not None and base is None:
            reasons.add(("unknown_base_path", change.old_path))
        if change.status in ("added", "copied", "renamed") and change.new_path in entries:
            reasons.add(("target_exists_at_base", change.new_path))
        for path in (change.old_path, change.new_path):
            if path is not None:
                touched.add(path)
                reasons |= _rule_reasons(path, owned, host, top_level, folded_existing)
    by_key = {}
    for path in touched:
        by_key.setdefault(fold(path), set()).add(path)
    for group in by_key.values():
        if len(group) > 1:
            reasons |= {("case_or_unicode_alias", path) for path in group}
    verdict["paths"] = sorted(touched)
    if reasons:
        verdict["reasons"] = [{"reason": reason, "path": path} for reason, path in sorted(reasons)]
    else:
        verdict["status"] = "accepted"
        verdict["files"] = [{"status": c.status, "old_path": c.old_path, "new_path": c.new_path} for c in changes]
    return verdict
