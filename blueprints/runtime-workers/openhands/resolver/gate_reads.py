"""The data CI-run gate code reads, for the trusted pre-push gate (resolver/push_gate.py).

Cross-family review P1 of 2026-10-04: a gate judges a change with its code and with the data
its code addresses, such as the JSON schema that scripts/validate_convergence.py reads
(`CONTRACT / "contract.schema.json"`, with `CONTRACT = REPO / "blueprints/convergence-practice"`
and `REPO = Path(__file__).resolve().parents[1]`). GateReads evaluates every expression of a
CI-run Python file to the repository locations it spells. A code-addressed read is caught
where its path is built, wherever the bytes are later read:
- builtin open(), io.open and Path.open; Path.read_text and Path.read_bytes (CPython
  Lib/pathlib);
- json.load, tomllib.load and csv.reader, which read from a handle opened on that path;
- a helper such as `read_json(path)`, whose argument is built at the call site.

So no read sink needs to be modelled, and no helper's parameter needs to be traced.

What the code spells:
- a string literal;
- a module, class or `self.X` constant;
- an f-string, `+`, `%` or `str.format` over those;
- a `Path(__file__)` chain: `.parent`, `.parents[k]`, `/`, Path(a, b, ...), os.path.join,
  joinpath, with_name, with_suffix, with_stem, os.path.dirname;
- an element of a literal tuple, list, set or dict constant, including a destructured
  `for a, (b, *c) in CONSTANT`;
- `from module import NAME` of a repository module.

A path the code receives from outside its text is the subject the gate checks: a parameter,
`self.X` not set from a constant, argparse, os.environ, sys.argv, file content, subprocess
output, or the result of any other call, received as the whole path. Where the data that
selects it is a file, the code spells that file's location, so that file is protected.
That subject rule does not apply to a computed path with a fixed directory: its fixed parts
form a glob, with `*` for each runtime segment. An environment value or an unfollowed call
used as a computed base is opaque; joining a tail to it is recorded as unclassified. The
gate reports that residual without refusing the commit; it must be classified before the
resolver's first live run (cross-family read 489b, repair exception of 2026-10-04).

Each expression evaluates to a bounded set of alternatives (Value):
- ("loc", path, exact): a repository location, "" for the root. exact False means somewhere
  under `path`; `shape` is then the glob (fnmatch, `*` also matching "/") of the whole
  location, when the computed parts sit inside a template or an enumeration pattern.
- ("str", text, exact): text; exact False means `text` is only its static prefix.
- ("seq",) and ("map",): a literal container (its AST node); ("data",): received;
  ("unknown",): not determined here; ("outside",): outside the repository.

`tail` names what a computed part came from (data, enum, literal, unknown, unclassified). `assumed` marks a
location whose base was received, read as repository-relative only where the literal tail
names a tracked path.

reads() turns the values into protection:
- an exact location is a file;
- a computed location under a non-root directory is its shape, else the directory;
- at the root, a shape with a fixed directory is protected. A received or enumerated whole
  path selects subjects. The pre-round unknown, unassumed location remains unresolved and
  fails closed. Newly unclassifiable computed reads are retained in `unclassified`.

executed() tells running from reading, so the derivation follows only code CI runs (a code
file that gate code hashes or copies is data). A file runs when its location, or text read
from it, is inside the arguments of a call that executes code: a call EXECUTING names, whatever
its receiver; a call of a function or method of this module that passes a parameter on to such
a call (by name, to a fixpoint); or a call of a function imported from outside the standard
library, whose body is not read here. An executing call whose argument is a computed location
may run any file under it. The pre-round computed-execution refusals remain fail-closed;
newly opaque constructions join the unclassified residual.

Names follow Python's scopes: module, class, function, lambda and comprehension, with a
comprehension's first iterable evaluated in the enclosing scope (Python Language Reference
6.2.4) and an assignment expression in a comprehension binding in the containing scope
(PEP 572). Within a scope the analysis is flow-insensitive: a name takes the union of all its
bindings there, including `x op= y` as `x op y`, which can only add alternatives, so only add
protection. A name defined through itself (`rel = normpath(rel)`) takes its other bindings'
values (the least fixpoint); a name with no binding at all is unknown.

Sources for the modelled behaviour, docs.python.org/3.13, read 2026-10-04: pathlib PurePath
("If a segment is an absolute path, all previous segments are ignored (like os.path.join())"),
Path.rglob ("like calling Path.glob() with "**/" added in front of the pattern") and
Path.iterdir; tomllib.load ("a readable and binary file object"), json.load (a
.read()-supporting file object) and csv.reader ("an iterable of strings ... most commonly a
file-like object"), so each is reached through a handle opened on a path the code builds;
fnmatch ("the filename separator ('/' on Unix) is not special to this module"), so a shape's
`*` also matches across directories, as Protected.rule's fnmatch.fnmatchcase applies it; the
Language Reference 6.2.4 and PEP 572 for the scopes above; ast for the node types. For
executed(), read 2026-10-04: subprocess (run, call, check_call, check_output, Popen,
getoutput, getstatusoutput), os "Process Management" (system, popen, startfile, posix_spawn,
the exec* and spawn* families), asyncio subprocesses, pty.spawn, runpy (run_path,
run_module), importlib.util.spec_from_file_location and importlib.machinery.SourceFileLoader,
the builtins exec and compile, and sys.stdlib_module_names ("New in version 3.10").
"""
from __future__ import annotations

import ast
from collections import namedtuple
import itertools
import posixpath
import re
import sys

Value = namedtuple("Value", "kind path exact tail assumed shape node")
DATA = Value("data", "", False, "data", False, None, None)
# Received whole, but not a repository-relative base: an environment value or an unfollowed call.
OPAQUE = DATA._replace(tail="unclassified")
UNKNOWN = Value("unknown", "", False, "unknown", False, None, None)
OUTSIDE = Value("outside", "", False, None, False, None, None)
MAX_ALTERNATIVES = 32
MAX_CONTAINER_DEPTH = 4  # nesting of literal containers executed() looks into (an argv list, a dict of args)
PATH_TYPES = frozenset({"Path", "PurePath", "PosixPath", "PurePosixPath"})
SAME_PATH = frozenset({"str", "fspath", "abspath", "realpath", "normpath", "expanduser", "resolve", "absolute",
                       "as_posix"})
CONTAINER_CALLS = frozenset({"sorted", "list", "tuple", "set", "frozenset", "reversed", "iter"})
ENUMERATING = frozenset({"glob", "rglob", "iglob", "iterdir", "listdir", "scandir", "walk"})
RECEIVED_ATTRIBUTES = frozenset({"stdout", "stderr", "environ", "argv"})
READ_RESULTS = frozenset({"open", "input", "read", "readline", "readlines", "read_text", "read_bytes",
                          "load", "loads", "safe_load", "parse_args", "parse_known_args"})
TEXT_DATA = frozenset({"strip", "lstrip", "rstrip", "split", "splitlines", "decode"})
WILDCARD = re.compile(r"[*?\[]")
# Calls that run the code they are given, matched by their final name whatever the receiver
# (docs.python.org/3.13): subprocess's run, call, check_call, check_output, Popen, getoutput and
# getstatusoutput; os's system, popen, startfile, posix_spawn, posix_spawnp and the exec* and
# spawn* families; asyncio's create_subprocess_exec and create_subprocess_shell; pty.spawn;
# runpy.run_path and run_module; importlib.util.spec_from_file_location and
# importlib.machinery.SourceFileLoader; the builtins exec and compile.
EXECUTING = frozenset({
    "run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput",
    "system", "popen", "startfile", "posix_spawn", "posix_spawnp",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "create_subprocess_exec", "create_subprocess_shell", "spawn",
    "run_path", "run_module", "spec_from_file_location", "SourceFileLoader", "exec", "compile",
})


def standard_library(module, level=0):
    """Whether an absolute import names a standard-library module (sys.stdlib_module_names, 3.10+)."""
    return not level and module.split(".")[0] in sys.stdlib_module_names


def loc(path, exact=True, tail=None, assumed=False, shape=None):
    return Value("loc", path, exact, None if exact else (tail or "unknown"), assumed, None if exact else shape, None)


def text(value, exact=True, tail=None, shape=None):
    return Value("str", value, exact, None if exact else (tail or "unknown"), False, None if exact else shape, None)


def container(kind, node):
    return Value(kind, "", False, None, False, None, node)


def normal(base, relative):
    """`base` joined with `relative`, normalized; None when it leaves the repository."""
    joined = posixpath.normpath(posixpath.join(base or ".", relative))
    if joined == ".":
        return ""
    if joined == ".." or joined.startswith("../") or joined.startswith("/"):
        return None
    return joined


def static_dir(pattern):
    """The directory part of a path or glob before its first wildcard."""
    found = WILDCARD.search(pattern)
    prefix = pattern[:found.start()] if found else pattern
    return prefix[:-1] if prefix.endswith("/") else posixpath.dirname(prefix)


def _shape_join(base, shape):
    """`shape` (a glob relative to base) as a repository glob."""
    if shape is None:
        return None
    if not base:
        return shape.lstrip("/")
    return f"{base}/{shape.lstrip('/')}" if shape else base


def _dedupe(values):
    """The distinct alternatives, bounded. Empty only inside a cycle (see GateReads.value)."""
    seen, result = set(), []
    for value in values:
        key = (value.kind, value.path, value.exact, value.tail, value.assumed, value.shape, id(value.node))
        if key not in seen:
            seen.add(key)
            result.append(value)
    if len(result) > MAX_ALTERNATIVES:
        return (collapse(result),)
    return tuple(result)


def collapse(values):
    """One conservative value for too many alternatives: their common directory, computed."""
    locations = [value for value in values if value.kind == "loc"]
    if locations:
        paths = [value.path for value in locations]
        common = posixpath.commonpath(paths) if all(paths) else ""
        unknown = any(value.kind == "unknown" or value.tail == "unknown" for value in values)
        residual = any(value.tail == "unclassified" for value in values)
        tail = "unknown" if unknown else "unclassified" if residual else "literal"
        return loc(common, False, tail, all(value.assumed for value in locations))
    texts = [value for value in values if value.kind == "str"]
    if texts and len(texts) == len(values):
        return text(posixpath.commonprefix([value.path for value in texts]), False, "literal")
    return UNKNOWN if any(value.kind == "unknown" for value in values) else DATA


def as_location(value):
    """A relative text used as a path: a location relative to the repository root, assumed."""
    if value.exact:
        joined = normal("", value.path)
        return OUTSIDE if joined is None else loc(joined, True, None, True)
    return loc(static_dir(value.shape or value.path), False, value.tail, True, value.shape)


def join1(left, right):
    """`left / right`, Path(left, right) or os.path.join(left, right), for single alternatives."""
    if left.kind == "outside" or (right.kind == "str" and right.exact and right.path.startswith("/")):
        return OUTSIDE
    if right.kind == "loc" and right.exact and not right.assumed:
        return right  # pathlib and os.path.join alike: an absolute path replaces the base
    if left.kind == "str":
        left = as_location(left)
        if left.kind != "loc":
            return left
    if left.kind != "loc":
        if left.kind == "unknown" or left.tail in ("unknown", "unclassified"):
            # `/` is also numeric division. Only a path component makes this a path construction.
            return loc("", False, "unclassified") if right.kind in ("str", "loc") else left
        if right.kind != "str":
            return UNKNOWN if "unknown" in (left.kind, right.kind) else DATA
        left = loc("", True, None, True)  # a received base: the literal tail is read as repository-relative
    if not left.exact:
        if left.shape is None:
            return left
        piece = right.path if right.kind == "str" and right.exact else (right.shape if right.kind == "str" else "*")
        return loc(left.path, False, left.tail, left.assumed, f"{left.shape}/{(piece or '*').lstrip('/')}")
    if right.kind == "str":
        if right.exact:
            joined = normal(left.path, right.path)
            return OUTSIDE if joined is None else loc(joined, True, None, left.assumed)
        directory = normal(left.path, static_dir(right.path) if "/" in right.path else "")
        if directory is None:
            return OUTSIDE
        return loc(directory, False, right.tail, left.assumed, _shape_join(left.path, right.shape))
    tail = "literal" if right.kind == "loc" else ("data" if right.kind in ("data", "seq", "map") else "unknown")
    return loc(left.path, False, tail, left.assumed, _shape_join(left.path, "*"))


def concat1(pieces):
    """An f-string or `+`: a template; anchored when its first piece is a location."""
    if not pieces:
        return text("")
    first, rest = pieces[0], pieces[1:]
    if first.kind == "outside":
        return OUTSIDE
    anchored = first.kind == "loc"
    if anchored and not first.exact:
        if first.shape is None:
            return first
        combined = concat1([text(first.path, False, first.tail, first.shape), *rest])
        return loc(static_dir(combined.shape or combined.path), False, combined.tail, first.assumed, combined.shape)
    static, shape, exact, tail = "", "", True, None
    for piece in (rest if anchored else pieces):
        if piece.kind == "str" and piece.exact:
            if exact:
                static += piece.path
            shape += piece.path
        else:
            if exact:
                if piece.kind == "str":
                    static += piece.path
                exact, tail = False, (piece.tail if piece.tail in ("unknown", "unclassified") else
                                      "data" if piece.kind in ("data", "seq", "map") else
                                      piece.tail if piece.kind == "str" else "unknown")
            shape += piece.shape if piece.kind == "str" and piece.shape else "*"
    if anchored:
        return join1(first, text(static.lstrip("/"), exact, tail, shape.lstrip("/")))
    if not exact and not static and first.kind in ("data", "unknown", "seq", "map") and not shape.strip("*"):
        return DATA if first.kind != "unknown" else UNKNOWN
    return text(static, exact, tail, shape)


def product(func, *operands):
    """func over every combination of alternatives, bounded (collapse beyond MAX_ALTERNATIVES)."""
    results = []
    for combination in itertools.product(*operands):
        results.append(func(*combination))
        if len(results) > MAX_ALTERNATIVES * 4:
            break
    return _dedupe(results)


def parent(value):
    if value.kind != "loc":
        return value
    if not value.exact:
        return value
    return loc(posixpath.dirname(value.path), True, None, value.assumed) if value.path else OUTSIDE


def plausible(path, blobs, dirs, top_dirs):
    """A tracked file, or a file an agent could add that reads as a repository path: under an
    existing top-level directory, with a file suffix, and not a tracked directory itself."""
    if not path or path in dirs:
        return False
    return path in blobs or ("/" in path and path.split("/", 1)[0] in top_dirs and bool(posixpath.splitext(path)[1]))


class GateReads:
    """The repository locations one CI-run Python file addresses (see the module docstring)."""

    SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
    COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)

    def __init__(self, path, source, imported=None):
        self.path = path
        self.module = ast.parse(source, filename=path)
        self.imported = imported or (lambda module, name, level: (UNKNOWN,))
        self.cache, self.bindings, self.synthetic = {}, {None: {}}, []
        self.unclassified = {}  # script:line -> computed shapes already known to the evaluator
        self.scope_of, self.parent_scope, self.class_of = {}, {}, {}
        for child in ast.iter_child_nodes(self.module):
            self._visit(child, None)

    # -- Bindings, scoped as Python scopes names

    def _visit(self, node, scope):
        own = self.bindings.setdefault(scope, {})
        if isinstance(node, self.COMPREHENSIONS):
            # A comprehension runs in its own scope, except its first iterable, which is evaluated in
            # the enclosing scope (Python Language Reference 6.2.4, "Displays for lists, sets and
            # dictionaries"), so its targets do not mix with same-named variables outside it.
            self.scope_of[node] = scope
            self._visit(node.generators[0].iter, scope)
            self.parent_scope[node] = scope
            self.class_of[node] = None
            inner = self.bindings.setdefault(node, {})
            for number, generator in enumerate(node.generators):
                self._bind(node, inner, generator.target, ("iter", generator.iter))
                for child in [*([generator.iter] if number else []), *generator.ifs, generator.target]:
                    self._visit(child, node)
            for child in ((node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,)):
                self._visit(child, node)
            return
        if isinstance(node, self.SCOPES):
            outer = [*getattr(node, "decorator_list", []), *getattr(node, "bases", []),
                     *getattr(node, "keywords", [])]
            if not isinstance(node, ast.ClassDef):
                outer += [*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)]
            for item in outer:
                self._visit(item, scope)
            if not isinstance(node, ast.Lambda):
                own.setdefault(node.name, []).append(("class" if isinstance(node, ast.ClassDef) else "function", node))
            self.parent_scope[node] = scope
            self.class_of[node] = scope if isinstance(scope, ast.ClassDef) else None
            inner = self.bindings.setdefault(node, {})
            if not isinstance(node, ast.ClassDef):
                arguments = node.args
                for argument in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                                 *(item for item in (arguments.vararg, arguments.kwarg) if item)]:
                    inner.setdefault(argument.arg, []).append(("param", None))
            for child in ([node.body] if isinstance(node, ast.Lambda) else node.body):
                self._visit(child, node)
            return
        self.scope_of[node] = scope
        if isinstance(node, ast.Assign):
            for target in node.targets:
                self._bind(scope, own, target, ("value", node.value))
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            self._bind(scope, own, node.target, ("value", node.value))
        elif isinstance(node, ast.AugAssign):
            # `x op= y` binds x to `x op y` (a synthetic BinOp; its self-reference is a cycle).
            if isinstance(node.target, (ast.Name, ast.Attribute)):
                if isinstance(node.target, ast.Name):
                    left = ast.Name(id=node.target.id, ctx=ast.Load())
                else:
                    left = ast.Attribute(value=node.target.value, attr=node.target.attr, ctx=ast.Load())
                combined = ast.BinOp(left=left, op=node.op, right=node.value)
                for synthetic in (left, combined):
                    ast.copy_location(synthetic, node)
                    self.scope_of[synthetic] = scope
                self.synthetic += [left, combined]
                self._bind(scope, own, node.target, ("value", combined))
            else:
                self._bind(scope, own, node.target, ("unknown", None))
        elif isinstance(node, ast.NamedExpr):
            # PEP 572: in a comprehension, an assignment expression binds in the containing scope.
            target_scope = scope
            while isinstance(target_scope, self.COMPREHENSIONS):
                target_scope = self.parent_scope.get(target_scope)
            self._bind(target_scope, self.bindings.setdefault(target_scope, {}), node.target, ("value", node.value))
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            self._bind(scope, own, node.target, ("iter", node.iter))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    self._bind(scope, own, item.optional_vars, ("with", item.context_expr))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                own.setdefault((alias.asname or alias.name).split(".")[0], []).append(
                    ("module", (alias.name if alias.asname else alias.name.split(".")[0], 0)))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                own.setdefault(alias.asname or alias.name, []).append(
                    ("import", (node.module or "", alias.name, node.level or 0)))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            own.setdefault(node.name, []).append(("unknown", None))
        for child in ast.iter_child_nodes(node):
            self._visit(child, scope)

    def _bind(self, scope, own, target, binding):
        if isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name) and target.value.id in ("self", "cls"):
                klass = self.class_of.get(scope)  # `self.X = value` in a method, read back as self.X
                if klass is not None:
                    self.bindings.setdefault(klass, {}).setdefault(target.attr, []).append(binding)
            return
        if isinstance(target, ast.Name):
            own.setdefault(target.id, []).append(binding)
        elif isinstance(target, ast.Starred):
            self._bind(scope, own, target.value, ("rest", binding))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for index, element in enumerate(target.elts):
                if isinstance(element, ast.Starred):
                    self._bind(scope, own, element.value, ("rest", (index, binding)))
                else:
                    self._bind(scope, own, element, ("index", (index, binding)))

    def _scope_chain(self, node):
        scope = self.scope_of.get(node)
        chain = [scope] if scope is not None else []
        while scope is not None:
            scope = self.parent_scope.get(scope)
            if scope is not None and not isinstance(scope, ast.ClassDef):
                chain.append(scope)
        return [*chain, None]

    def _entries(self, name, node):
        for scope in self._scope_chain(node):
            entries = self.bindings.get(scope, {}).get(name)
            if entries:
                return entries
        return None

    # -- Evaluation

    def value(self, node):
        """The alternatives of `node`. A cycle (`rel = normpath(rel)`) starts from no
        alternative, the least fixpoint of the union, so a name defined through itself takes the
        values of its other bindings; a value with no alternative at all is unknown."""
        key = id(node)
        if key not in self.cache:
            self.cache[key] = ()
            self.cache[key] = self._value(node) or (UNKNOWN,)
        return self.cache[key]

    def module_value(self, name):
        """A module-level name's value, for `from <this module> import name`."""
        entries = self.bindings.get(None, {}).get(name)
        if not entries:
            return (UNKNOWN,)
        return _dedupe([item for entry in entries for item in self._binding(entry)])

    def _binding(self, binding):
        kind, payload = binding
        if kind == "param" or kind == "with":
            return (DATA,)
        if kind == "value":
            return self.value(payload)
        if kind == "iter":
            return self._elements(payload)
        if kind == "index":
            index, inner = payload
            return _dedupe([item for alternative in self._binding(inner) for item in self._at(alternative, index)])
        if kind == "rest":
            index, inner = payload if isinstance(payload, tuple) and len(payload) == 2 and isinstance(payload[0], int) \
                else (0, payload)
            return _dedupe([item for alternative in self._binding(inner)
                            for item in self._at(alternative, index, rest=True)])
        if kind == "import":
            module, name, level = payload
            return self.imported(module, name, level)
        return (UNKNOWN,)

    def _at(self, alternative, index, rest=False):
        """Element `index` (or the elements from it on) of one alternative, for destructuring."""
        if alternative.kind == "seq":
            elements = alternative.node.elts
            chosen = elements[index:] if rest else elements[index:index + 1]
            return _dedupe([item for element in chosen for item in self._element_values(element)]) if chosen else \
                (UNKNOWN,)
        if alternative.kind == "loc" and alternative.exact:
            return (loc(alternative.path, False, "literal", alternative.assumed),)
        return (alternative,)

    def _element_values(self, element):
        if isinstance(element, ast.Starred):
            return self._elements(element.value)
        return self.value(element)

    def _elements(self, iterable):
        """The values one element of `iterable` can take (a for or comprehension target)."""
        if isinstance(iterable, (ast.List, ast.Tuple, ast.Set)):
            return _dedupe([item for element in iterable.elts for item in self._element_values(element)])
        if isinstance(iterable, (ast.ListComp, ast.GeneratorExp, ast.SetComp)):
            return self.value(iterable.elt)
        if isinstance(iterable, ast.DictComp):
            return self.value(iterable.key)
        if isinstance(iterable, ast.Call):
            name = self._call_name(iterable)
            if name in CONTAINER_CALLS and iterable.args:
                return self._elements(iterable.args[0])
            if name == "filter" and len(iterable.args) == 2:
                return self._elements(iterable.args[1])
            if name in ("enumerate", "zip") and iterable.args:
                return _dedupe([DATA, *(item for argument in iterable.args for item in self._elements(argument))])
            if name in ("items", "values", "keys") and isinstance(iterable.func, ast.Attribute):
                return self._mapping_elements(iterable.func.value, name)
        results = []
        for alternative in self.value(iterable):
            if alternative.kind == "seq":
                results += [item for element in alternative.node.elts for item in self._element_values(element)]
            elif alternative.kind == "map":
                results += [item for key in alternative.node.keys if key is not None for item in self.value(key)]
            elif alternative.kind == "loc":
                results.append(loc(alternative.path, False, "enum" if alternative.tail == "enum" else
                                   (alternative.tail or "literal"), alternative.assumed, alternative.shape))
            elif alternative.kind == "str":
                results.append(DATA)
            else:
                results.append(alternative)
        return _dedupe(results) or (DATA,)  # an empty literal binds nothing

    def _mapping_elements(self, receiver, method):
        results = []
        for alternative in self.value(receiver):
            if alternative.kind != "map":
                results.append(DATA if alternative.kind in ("data", "loc", "str") else alternative)
                continue
            mapping = alternative.node
            for key, item in zip(mapping.keys, mapping.values):
                if method == "keys" and key is not None:
                    results += self.value(key)
                elif method == "values":
                    results += self.value(item)
                elif method == "items" and key is not None:
                    pair = ast.Tuple(elts=[key, item], ctx=ast.Load())
                    self.synthetic.append(pair)
                    results.append(container("seq", pair))
        return _dedupe(results)

    @staticmethod
    def _call_name(call):
        func = call.func
        return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)

    def _value(self, node):
        if isinstance(node, ast.Constant):
            return (text(node.value),) if isinstance(node.value, str) else (DATA,)
        if isinstance(node, ast.Name):
            if node.id == "__file__":
                return (loc(self.path),)
            entries = self._entries(node.id, node)
            if not entries:
                return (UNKNOWN,)
            return _dedupe([item for entry in entries for item in self._binding(entry)])
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return (container("seq", node),)
        if isinstance(node, ast.Dict):
            return (container("map", node),)
        if isinstance(node, ast.JoinedStr):
            parts = [self.value(part.value) if isinstance(part, ast.FormattedValue) else self.value(part)
                     for part in node.values]
            return product(lambda *pieces: concat1(list(pieces)), *parts)
        if isinstance(node, ast.BinOp):
            left, right = self.value(node.left), self.value(node.right)
            if isinstance(node.op, ast.Div):
                joined = product(join1, left, right)
                return _dedupe([item._replace(node=node) if item.kind == "data" else item for item in joined])
            if isinstance(node.op, ast.Add):
                return product(lambda a, b: concat1([a, b]) if "seq" not in (a.kind, b.kind) else DATA, left, right)
            if isinstance(node.op, ast.Mod):
                return _dedupe([self._template(item.path, "%") if item.kind == "str" and item.exact else
                                OPAQUE._replace(node=node)
                                for item in left])
            return (DATA,)
        if isinstance(node, ast.IfExp):
            return _dedupe([*self.value(node.body), *self.value(node.orelse)])
        if isinstance(node, ast.BoolOp):
            return _dedupe([item for part in node.values for item in self.value(part)])
        if isinstance(node, ast.Attribute):
            return self._attribute(node)
        if isinstance(node, ast.Subscript):
            return self._subscript(node)
        if isinstance(node, ast.Call):
            return self._call(node)
        if isinstance(node, ast.Starred):
            return self.value(node.value)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return (DATA,)
        return (DATA,)

    @staticmethod
    def _template(pattern, marker):
        """A %-format or str.format template as text with computed parts."""
        if marker == "%":
            pieces = re.split(r"%[-#0 +]*[0-9*]*(?:\.[0-9*]+)?[a-zA-Z%]", pattern)
        else:
            pieces = re.split(r"\{[^{}]*\}", pattern)
        if len(pieces) == 1:
            return text(pattern)
        return text(pieces[0], False, "data", "*".join(pieces))

    def _attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id in ("self", "cls"):
            scope = self.scope_of.get(node)
            while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = self.parent_scope.get(scope)
            klass = self.class_of.get(scope) if scope is not None else None
            entries = self.bindings.get(klass, {}).get(node.attr) if klass is not None else None
            return _dedupe([item for entry in entries for item in self._binding(entry)]) if entries else (DATA,)
        if node.attr in RECEIVED_ATTRIBUTES:
            return (OPAQUE if node.attr == "environ" else DATA,)
        if isinstance(node.value, ast.Name):
            entries = self._entries(node.value.id, node) or []
            modules = [payload for kind, payload in entries if kind == "module"]
            if modules:
                return _dedupe([item for module, level in modules for item in self.imported(module, node.attr, level)])
        results = []
        for base in self.value(node.value):
            if node.attr == "parent":
                results.append(parent(base))
            elif node.attr in ("name", "stem", "suffix") and base.kind == "loc" and base.exact:
                name = posixpath.basename(base.path)
                results.append(text({"name": name, "stem": posixpath.splitext(name)[0],
                                     "suffix": posixpath.splitext(name)[1]}[node.attr]))
            elif base.kind == "unknown":
                results.append(UNKNOWN)
            else:
                results.append(OPAQUE if base.tail in ("unknown", "unclassified") else DATA)
        return _dedupe(results)

    def _subscript(self, node):
        if isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
            index = node.slice.value if isinstance(node.slice, ast.Constant) else None
            results = []
            for base in self.value(node.value.value):
                if not isinstance(index, int) or index < 0:
                    results.append(base if base.kind != "loc" else loc(base.path, False, "literal", base.assumed))
                    continue
                for _ in range(index + 1):
                    base = parent(base)
                results.append(base)
            return _dedupe(results)
        key = node.slice.value if isinstance(node.slice, ast.Constant) else None
        results = []
        for base in self.value(node.value):
            if base.kind == "seq":
                elements = base.node.elts
                if isinstance(key, int) and -len(elements) <= key < len(elements):
                    results += self._element_values(elements[key])
                else:
                    results += [item for element in elements for item in self._element_values(element)]
            elif base.kind == "map":
                matched = [item for name, item in zip(base.node.keys, base.node.values)
                           if isinstance(name, ast.Constant) and name.value == key]
                for item in (matched or base.node.values):
                    results += self.value(item)
            elif base.kind == "unknown":
                results.append(UNKNOWN)
            else:
                results.append(OPAQUE if base.tail in ("unknown", "unclassified") else DATA)
        return _dedupe(results)

    def _fold(self, alternatives_list):
        value = alternatives_list[0]
        for following in alternatives_list[1:]:
            value = product(join1, value, following)
        if len(alternatives_list) > 1:
            value = _dedupe([loc("", False, "unclassified") if item.kind in ("data", "unknown") else item
                             for item in value])
        return value

    def _call(self, node):
        name, func = self._call_name(node), node.func
        receiver = self.value(func.value) if isinstance(func, ast.Attribute) else None
        arguments = [self.value(argument) for argument in node.args]
        dotted = ast.unparse(func) if isinstance(func, (ast.Attribute, ast.Name)) else ""
        if name in PATH_TYPES:
            if not arguments:
                return (OUTSIDE,)  # Path() is the working directory, not a repository location
            value = self._fold(arguments)
            return _dedupe([as_location(item) if item.kind == "str" else item for item in value])
        if dotted in ("os.path.join", "path.join", "posixpath.join") and arguments:
            return self._fold(arguments)
        if name == "joinpath" and receiver is not None:
            return self._fold([receiver, *arguments])
        if dotted in ("os.path.dirname", "path.dirname", "posixpath.dirname") and arguments:
            return _dedupe([parent(item) for item in arguments[0]])
        if name in ("with_name", "with_suffix", "with_stem") and receiver is not None:
            results = []
            for base in receiver:
                if base.kind != "loc":
                    results.append(OUTSIDE if base.kind == "outside" else loc("", False, "unclassified"))
                    continue
                pattern = base.path if base.exact else base.shape
                if pattern is None:
                    results.append(base)
                    continue
                directory = posixpath.dirname(pattern)
                above = loc(directory, True, None, base.assumed) if not WILDCARD.search(directory) else \
                    loc(static_dir(directory), False, base.tail, base.assumed, directory)
                if name == "with_name" and arguments:
                    results += [join1(above, item) for item in arguments[0]]
                elif arguments:
                    stem, suffix = posixpath.splitext(posixpath.basename(pattern))
                    fixed = stem if name == "with_suffix" else (suffix if base.exact or suffix else "*")
                    fixed = text(fixed, not WILDCARD.search(fixed), base.tail, fixed)
                    for item in arguments[0]:
                        pieces = [fixed, item] if name == "with_suffix" else [item, fixed]
                        results.append(join1(above, concat1(pieces)))
            return _dedupe(results)
        if name in ENUMERATING:
            return self._enumeration(name, receiver, arguments)
        if name in SAME_PATH:
            return receiver if receiver is not None and not arguments else (arguments[0] if arguments else (DATA,))
        if name in CONTAINER_CALLS:
            return arguments[0] if arguments else (DATA,)
        if name == "format" and receiver is not None:
            return _dedupe([self._template(item.path, "{") if item.kind == "str" and item.exact else
                            OPAQUE._replace(node=node)
                            for item in receiver])
        if name in READ_RESULTS:
            return (DATA,)
        if name in TEXT_DATA and receiver is not None:
            return _dedupe([item if item.kind == "data" else OPAQUE for item in receiver])
        if receiver is not None and all(item.kind == "data" and item.tail == "data" for item in receiver):
            return (DATA,)  # selecting a field from received content keeps it a whole runtime subject
        if isinstance(func, ast.Name):
            for kind, payload in self._entries(func.id, node) or []:
                if kind == "function" and not (payload.args.args or payload.args.posonlyargs or payload.args.vararg
                                               or payload.args.kwonlyargs):
                    returns = [item.value for item in ast.walk(payload) if isinstance(item, ast.Return) and item.value]
                    return _dedupe([value for item in returns for value in self.value(item)]) if returns else (DATA,)
        # Any other call computes its result at run time: received. A helper given a code-spelled
        # location and a literal may join them; that join is a candidate, kept where it is tracked.
        candidates = [OPAQUE]
        locations = [item for alternatives in arguments for item in alternatives if item.kind == "loc" and item.exact]
        literals = [item for alternatives in arguments for item in alternatives if item.kind == "str" and item.exact]
        for base, leaf in itertools.islice(itertools.product(locations, literals), MAX_ALTERNATIVES):
            joined = join1(base, leaf)
            if joined.kind == "loc":
                candidates.append(loc(joined.path, True, None, True))
        return _dedupe(candidates)

    def _enumeration(self, name, receiver, arguments):
        if receiver is not None and name in ("glob", "rglob", "iterdir"):
            bases, patterns = receiver, (arguments[0] if arguments else (text("*"),))
        else:
            bases, patterns = (arguments[0] if arguments else (DATA,)), (text("*"),)
        results = []
        for base in bases:
            if base.kind == "str" and name in ("glob", "iglob"):
                pattern = base.path if base.exact else (base.shape or base.path + "*")
                directory = static_dir(pattern)
                results.append(loc(directory, False, "enum", True, pattern))
                continue
            if base.kind != "loc":
                results.append(base if base.kind == "unknown" else DATA)
                continue
            if not base.exact:
                results.append(loc(base.path, False, "enum", base.assumed, base.shape))
                continue
            for pattern in patterns:
                glob = pattern.path if pattern.kind == "str" and pattern.exact else "*"
                if name == "rglob":
                    glob = f"*{glob}" if not glob.startswith("*") else glob
                directory = normal(base.path, static_dir(glob)) if "/" in glob else base.path
                results.append(loc(directory if directory is not None else base.path, False, "enum", base.assumed,
                                   _shape_join(base.path, glob) if name in ("glob", "rglob") else None))
        return _dedupe(results)

    # -- Execution

    def _arguments(self, call):
        return [*call.args, *(keyword.value for keyword in call.keywords)]

    def _executes(self, call, executors):
        """Whether `call` runs code it is given: an EXECUTING call; a call, by name, of a function or
        method of this module that passes a parameter on to one (`executors`); or a call of a function
        imported from outside the standard library, whose body is not read here."""
        func = call.func
        name = self._call_name(call)
        if name in EXECUTING or (isinstance(func, ast.Attribute) and func.attr in executors):
            return True
        if isinstance(func, ast.Name):
            entries = self._entries(func.id, call) or []
            if func.id in executors and any(kind == "function" for kind, _ in entries):
                return True
            return any(kind == "import" and not standard_library(payload[0], payload[2]) for kind, payload in entries)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            entries = self._entries(func.value.id, call) or []
            return any(kind == "module" and not standard_library(payload[0], payload[1]) for kind, payload in entries)
        return False

    def _executors(self):
        """Names of this module's functions and methods that pass a parameter on to a call that
        executes code, to a fixpoint (a wrapper of a wrapper counts)."""
        if getattr(self, "_executor_names", None) is None:
            functions = [node for node in ast.walk(self.module)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            executors, changed = set(), True
            while changed:
                changed = False
                for function in functions:
                    if function.name in executors:
                        continue
                    arguments = function.args
                    parameters = {item.arg for item in [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                                                        *(extra for extra in (arguments.vararg, arguments.kwarg) if extra)]}
                    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                        if self._executes(call, executors) and any(
                                isinstance(node, ast.Name) and node.id in parameters
                                for argument in self._arguments(call) for node in ast.walk(argument)):
                            executors.add(function.name)
                            changed = True
                            break
            self._executor_names = executors
        return self._executor_names

    def _leaf_values(self, node, depth=0):
        """The alternatives of `node`, with a literal container replaced by the values of its elements
        (a list or tuple's items, a dict's keys and values), to MAX_CONTAINER_DEPTH: an argv bound to a
        name (`cmd = [sys.executable, script]`, then `subprocess.run(cmd)`) runs `script`."""
        results = []
        for value in self.value(node):
            if value.kind == "seq" and depth < MAX_CONTAINER_DEPTH:
                for element in value.node.elts:
                    results += self._leaf_values(element.value if isinstance(element, ast.Starred) else element,
                                                 depth + 1)
            elif value.kind == "map" and depth < MAX_CONTAINER_DEPTH:
                for item in [*(key for key in value.node.keys if key is not None), *value.node.values]:
                    results += self._leaf_values(item, depth + 1)
            else:
                results.append(value)
        return results

    def imported_modules(self):
        """Dotted names of this file's absolute imports at any depth, lazy imports inside functions
        included: `import X`, `from X import Y` (X and X.Y), and import_module or __import__ with a
        literal name. Relative imports are left to patch_policy.python_references."""
        names = []
        for node in ast.walk(self.module):
            if isinstance(node, ast.Import):
                names += [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                names += [node.module, *(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")]
            elif (isinstance(node, ast.Call) and self._call_name(node) in ("import_module", "__import__")
                  and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                names.append(node.args[0].value)
        return list(dict.fromkeys(names))

    def executed(self, blobs, dirs):
        """(paths, computed) that this file runs: the repository files spelled inside the arguments of a
        call that executes code (`_executes`), literal containers included (`_leaf_values`), and
        "<file>:<line>" of such calls whose argument is a computed location under the repository,
        which may run any file there."""
        executors = self._executors()
        top_dirs = {path.split("/", 1)[0] for path in blobs if "/" in path}
        paths, computed = set(), set()
        for call in (node for node in ast.walk(self.module) if isinstance(node, ast.Call)):
            if not self._executes(call, executors):
                continue
            for argument in self._arguments(call):
                for node in ast.walk(argument):
                    if not isinstance(node, ast.expr):
                        continue
                    for value in self._leaf_values(node):
                        if value.kind == "str" and value.exact:
                            candidate = value.path[2:] if value.path.startswith("./") else value.path
                            path = normal("", candidate) if candidate and not any(c.isspace() for c in candidate) else None
                            if plausible(path, blobs, dirs, top_dirs):
                                paths.add(path)
                        elif value.kind == "loc" and value.exact:
                            if value.path and value.path not in dirs and (
                                    not value.assumed or plausible(value.path, blobs, dirs, top_dirs)):
                                paths.add(value.path)
                        elif value.kind == "loc" and not value.assumed:
                            if value.tail == "unclassified":
                                self._note_unclassified(node, value)
                            else:
                                computed.add(f"{self.path}:{getattr(node, 'lineno', 0)}")
        return paths, computed

    # -- Protection

    def _note_unclassified(self, node, value):
        location = f"{self.path}:{getattr(node, 'lineno', 0)}"
        shapes = self.unclassified.setdefault(location, set())
        if value.shape:
            shapes.add(value.shape)

    def reads(self, blobs, dirs):
        """(files, prefixes, globs, unresolved) that this file's expressions address.

        - An exact location is a file read, whether or not the tree has it yet (an agent
          could add it). A tracked directory is not, by itself. An assumed location (a literal
          under a received base) counts where it is plausible (see `plausible`).
        - A computed location under a non-root directory protects its shape, else that
          directory as a prefix.
        - At the root, a shape with a fixed directory is protected. Otherwise a
          whole received or enumerated part selects subjects. The root's unknown, unassumed
          location remains unresolved as at 7c1d24cc5. New unclassifiable computed reads are
          recorded in self.unclassified with their existing shapes, without a refusal.
        - An exact string counts where it is plausible and has no whitespace. A computed
          relative string with a fixed directory uses the same glob representation as Path.
        """
        files, prefixes, globs, unresolved = set(), set(), set(), set()
        self.unclassified = {}
        top_dirs = {path.split("/", 1)[0] for path in blobs if "/" in path}
        path_inputs = set()
        for call in (node for node in ast.walk(self.module) if isinstance(node, ast.Call)):
            name = self._call_name(call)
            if name == "open" and call.args:
                path_inputs.add(call.args[0])
            if name in ("open", "read_text", "read_bytes") and isinstance(call.func, ast.Attribute):
                path_inputs.add(call.func.value)
        for node in ast.walk(self.module):
            if not isinstance(node, ast.expr):
                continue
            for value in self.value(node):
                if value.kind == "data" and value.node is not None and node in path_inputs:
                    self._note_unclassified(node, value)
                    continue
                if value.kind == "str":
                    candidate = value.path[2:] if value.path.startswith("./") else value.path
                    if value.exact and candidate and not any(char.isspace() for char in candidate):
                        path = normal("", candidate)
                        if plausible(path, blobs, dirs, top_dirs):
                            files.add(path)
                        continue
                    shape = value.shape or value.path
                    if not value.exact and ((static_dir(shape) and not any(c.isspace() for c in shape))
                                            or node in path_inputs):
                        value = as_location(value)
                    else:
                        continue
                if value.kind != "loc":
                    continue
                path = value.path
                if value.exact:
                    if path and path not in dirs and (not value.assumed or plausible(path, blobs, dirs, top_dirs)):
                        files.add(path)
                    continue
                if path in blobs:
                    path = posixpath.dirname(path)
                shape = value.shape if value.shape and static_dir(value.shape) else None
                if path:
                    if shape:
                        globs.add(shape)
                    else:
                        prefixes.add(path)
                elif shape:
                    globs.add(shape)
                elif value.tail == "unknown" and not value.assumed:
                    unresolved.add(f"{self.path}:{getattr(node, 'lineno', 0)}")
                elif value.tail in ("unknown", "unclassified") or (value.shape and value.shape.strip("*")):
                    self._note_unclassified(node, value)
        return files, prefixes, globs, unresolved
