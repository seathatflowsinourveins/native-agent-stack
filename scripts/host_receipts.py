#!/usr/bin/env python3
"""Record, validate, review and summarize per-host evidence acceptance receipts.

One receipt is one component x one host x one lifecycle stage
(``adoption/host-receipt.schema.json``). This CLI never uploads anything: it
only runs locally supplied commands, writes JSON under ``evidence/hosts/``,
and registers those files in ``manifests/evidence.json``. See
``docs/contributing-evidence.md`` for the full contribution flow.

The ``validate`` rules below are implemented directly in stdlib Python (no
external JSON Schema library) and are kept in sync with
``adoption/host-receipt.schema.json`` by ``tests/test_host_receipts.py``,
which compares this module's required-key and enum constants against the
schema file.
"""

from __future__ import annotations

import argparse
import bisect
import getpass
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    from .validate import PRIVATE_CONTENT
    from .catalog_decisions import InvalidDecisionIndex, safe_file, unique_json
except ImportError:  # running as a plain script, not a package
    from validate import PRIVATE_CONTENT
    from catalog_decisions import InvalidDecisionIndex, safe_file, unique_json


SCHEMA_RELATIVE_PATH = "adoption/host-receipt.schema.json"
STAGES = {"install", "use", "restart", "recovery", "persistence", "cleanup"}
RESULTS = {"pass", "fail", "partial", "not_runnable"}
EVIDENCE_CLASSES = {"native_proven", "local_integration", "synthetic"}
REVIEW_KINDS = {"self", "independent_session", "codex_lane", "human"}
REVIEW_VERDICTS = {"agree", "disagree", "needs_changes"}
QUALIFIED_MODEL_REQUIRED = ["model_id", "revision", "runtime", "runtime_version", "bars", "result"]
QUALIFIED_MODEL_RESULTS = {"pass", "fail"}

# Identity of whoever records or reviews a receipt, stored only as a domain-separated sha256
# (a fixed public prefix, not a secret salt: a guessable --identity can be recovered by
# dictionary, so use a random per-session token). A Claude Code session exports
# CLAUDE_CODE_SESSION_ID (observed in Claude Code 2.1.280) and is always identified by it; a
# Codex session, a human or CI has no such variable and must pass --identity. There is no
# default: an absent identity fails closed rather than making every such recorder the same
# identity.
IDENTITY_ENV = "CLAUDE_CODE_SESSION_ID"
IDENTITY_DOMAIN = "host-receipt-identity-v1:"
DISSENT_VERDICTS = {"disagree", "needs_changes"}

# A ``use`` receipt records the component doing its job. Whether it does is judged by the independent review
# (contributing-evidence.md step 8), never by the command text: no classifier of shell text is both sound and complete
# (#164 Codex re-check: ``sh -c 'rtk --version'`` and ``rtk help gain`` pass any such rule, ``du -h /dev/null`` fails
# a broad one), so status derivation never reads it. ``record`` only refuses the unambiguous case, a whole command
# that is exactly ``<program> <flag>`` with one of these, as a convenience that is knowingly incomplete. ``-h`` is
# left out: ``df -h`` and ``du -h`` are functional.
BARE_HELP_OR_VERSION = frozenset({"--help", "--version", "-V", "help", "version"})


def bare_help_or_version(cmd: str) -> bool:
    """Whether ``cmd`` is exactly one program and one help or version argument (BARE_HELP_OR_VERSION)."""
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return False
    return len(argv) == 2 and argv[1] in BARE_HELP_OR_VERSION


HOST_ID_PATTERN = re.compile(r"^[a-z0-9-]+-[0-9]{8}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ISO_UTC_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
# A generation suffix ('-2', '-3', ...) distinguishes a superseding receipt's id from the
# id it supersedes without changing host/component/stage/date; see cmd_record's --supersedes
# handling and next_free_superseding_id(). No leading zero and never '-0'/'-1': the bare id
# with no suffix is generation 1.
ID_PATTERN = re.compile(
    r"^(?P<host_id>[a-z0-9-]+-[0-9]{8})--(?P<component_id>[A-Za-z0-9][A-Za-z0-9._/:-]*)--"
    r"(?P<stage>install|use|restart|recovery|persistence|cleanup)--(?P<date>[0-9]{8})"
    r"(?:-(?P<generation>[2-9]|[1-9][0-9]+))?$"
)

TOP_LEVEL_REQUIRED = [
    "schema_version", "id", "kind", "host", "catalog_revision", "component_id",
    "stage", "commands", "tool_versions", "observed_at_utc", "result", "claim",
    "limitations", "evidence_class", "reviews",
]
HOST_REQUIRED = ["host_id", "platform_id", "os", "architecture", "second_physical_machine"]
COMMAND_REQUIRED = ["cmd", "exit", "duration_s", "output_sha256", "output_excerpt"]
REVIEW_REQUIRED = ["kind", "ref", "verdict", "at_utc"]

DEFAULT_TIMEOUT_S = 120
# How far ahead of the validating machine's clock an observation or review may be dated
# (clock skew between hosts). A later date would sort as the "latest" receipt or review and
# could not be superseded, so validate refuses it.
FUTURE_SKEW_S = 15 * 60
MAX_EXCERPT_CHARS = 400


class InvalidHostReceipt(ValueError):
    """One or more host-receipt validation failures; messages avoid echoing secrets."""


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def repo_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    return Path(__file__).resolve().parents[1]


def load_json(root: Path, relative: str) -> dict:
    path = safe_file(root, relative)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)


def identity_digest(value: str) -> str:
    return hashlib.sha256((IDENTITY_DOMAIN + value).encode("utf-8")).hexdigest()


class IdentityError(ValueError):
    """An identity that cannot be used; the message says why."""


def normalize_identity(value: str) -> str:
    """NFKC, case-folded, whitespace-collapsed, so 'Alice' and ' alice ' are one identity."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def resolve_identity(explicit: str | None) -> str | None:
    """Digest of $CLAUDE_CODE_SESSION_ID when set (a Claude Code session cannot choose another
    identity), else of the normalized --identity, else None (callers fail closed)."""
    session = os.environ.get(IDENTITY_ENV, "").strip()
    chosen = normalize_identity(explicit or "")
    if session:
        if chosen:
            raise IdentityError(
                f"--identity is for sessions without ${IDENTITY_ENV}; this Claude Code session is identified "
                "by its session id, so a review from it cannot pose as another reviewer")
        return identity_digest(session)
    return identity_digest(chosen) if chosen else None


def normalize_pin(value) -> str | None:
    """Comparable form of a pin or recorded version: lower-cased, whitespace collapsed, and a
    leading 'v' dropped from each token that continues with a digit ('v1.52.0' -> '1.52.0').
    ``None`` when the text has no digit (for example 'unpinned'): such a value cannot bind."""
    if not isinstance(value, str):
        return None
    tokens = [token[1:] if re.fullmatch(r"v[0-9].*", token) else token for token in value.lower().split()]
    text = " ".join(tokens)
    return text if re.search(r"[0-9]", text) else None


HEX_PREFIX_MIN = 7
FULL_COMMIT_LENGTHS = {40, 64}


def pin_matches(recorded, pin) -> bool:
    """True when a recorded component version is ``pin``: equal after ``normalize_pin``, or
    an abbreviation (at least 7 hex characters) of a full 40- or 64-character commit id. A
    value without a digit ('unpinned') never binds."""
    left, right = normalize_pin(recorded), normalize_pin(pin)
    if not left or not right:
        return False
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    hexy = re.compile(r"[0-9a-f]+")
    return (len(longer) in FULL_COMMIT_LENGTHS and len(shorter) >= HEX_PREFIX_MIN
            and hexy.fullmatch(longer) is not None and hexy.fullmatch(shorter) is not None
            and longer.startswith(shorter))


def identity_record(digest: str, model: str | None) -> dict:
    record = {"identity_sha256": digest}
    if model and model.strip():
        record["model"] = model.strip()
    return record


def require_git() -> None:
    if shutil.which("git") is None:
        raise InvalidHostReceipt("git is not on PATH; install git (Homebrew: brew install git) and rerun")


def git_head(root: Path) -> str:
    require_git()
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=5, check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not SHA_PATTERN.fullmatch(revision):
        raise InvalidHostReceipt("could not resolve a 40-hex catalog_revision from git rev-parse HEAD")
    return revision


def sanitize(text: str) -> str:
    """Replace $HOME with ~ and the current username with <user>; never raises."""
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    try:
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or getpass.getuser()
    except Exception:
        user = None
    if user:
        text = re.sub(re.escape(user), "<user>", text)
    for _description, pattern in PRIVATE_CONTENT:
        text = pattern.sub("[redacted]", text)
    return text


def iter_receipt_strings(value):
    """Yield every decoded string in a JSON value: dict keys, dict values and list items,
    recursively. Used by the privacy scan so a JSON escape (for example ``\\u002f`` in place
    of a literal ``/``) cannot hide prohibited content from a scan of only the serialized
    file bytes: this walks the *decoded* structure instead."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from iter_receipt_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_receipt_strings(item)


# ----------------------------------------------------------- minimal JSON Schema subset
#
# adoption/host-receipt.schema.json is the single source of truth for host-receipt
# structural validation; validate_against_schema() below implements exactly the subset of
# JSON Schema (draft 2020-12) keywords that file uses. SCHEMA_SUPPORTED_KEYWORDS and
# tests/test_host_receipts.py's schema-coverage test fail loudly if the schema is ever
# edited to use a keyword this validator does not implement, so structural drift between
# the schema and the code cannot silently pass.

SCHEMA_META_KEYWORDS = {"$schema", "$id", "title", "description"}
SCHEMA_SUPPORTED_KEYWORDS = {
    "type", "enum", "const", "required", "properties", "additionalProperties",
    "items", "minItems", "minLength", "maxLength", "minimum", "pattern",
}


def schema_nodes(schema):
    """Yield every JSON-Schema object reachable from ``schema`` (itself, each
    ``properties`` value and ``items``), without descending into arbitrary property
    *names* as if they were schema keywords."""
    if not isinstance(schema, dict):
        return
    yield schema
    for subschema in schema.get("properties", {}).values():
        yield from schema_nodes(subschema)
    items = schema.get("items")
    if isinstance(items, dict):
        yield from schema_nodes(items)


def _schema_type_ok(instance, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(instance, dict)
    if type_name == "array":
        return isinstance(instance, list)
    if type_name == "string":
        return isinstance(instance, str)
    if type_name == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if type_name == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if type_name == "boolean":
        return isinstance(instance, bool)
    return True  # pragma: no cover - every type used in the schema is listed above


def _json_equal(a, b) -> bool:
    """JSON equality: unlike Python ``==``, a boolean never equals a number (True != 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    return a == b


def validate_against_schema(instance, schema: dict, path: str, errors: list[str]) -> None:
    """Validate ``instance`` against ``schema`` (a JSON Schema object or subschema),
    appending human-readable messages to ``errors``. Supports exactly
    SCHEMA_SUPPORTED_KEYWORDS; see the module comment above."""
    if "const" in schema and not _json_equal(instance, schema["const"]):
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and not any(_json_equal(instance, v) for v in schema["enum"]):
        errors.append(f"{path}: must be one of {schema['enum']!r}")
    if "type" in schema and not _schema_type_ok(instance, schema["type"]):
        errors.append(f"{path}: must be of type {schema['type']!r}")
        return  # wrong-typed instance: do not cascade further shape-specific checks

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: must be at least {schema['minLength']} character(s)")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: must be at most {schema['maxLength']} character(s)")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: must match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: must be >= {schema['minimum']}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: must have at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                validate_against_schema(item, item_schema, f"{path}[{index}]", errors)

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: unexpected additional property {key!r}")
        for key, subschema in properties.items():
            if key in instance:
                validate_against_schema(instance[key], subschema, f"{path}.{key}", errors)


def load_receipt_schema(root: Path) -> dict:
    """Load adoption/host-receipt.schema.json fresh every call (no caching): this CLI is a
    short-lived process per invocation, and caching by root path risks stale results if a
    caller (for example a test) mutates the schema file on disk between calls."""
    return load_json(root, SCHEMA_RELATIVE_PATH)


def stack_component_ids(root: Path) -> set[str]:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return set()
    return {component.get("id") for component in stack.get("components", []) if isinstance(component, dict)}


def stack_component_version(root: Path, component_id: str) -> str | None:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return None
    for component in stack.get("components", []):
        if isinstance(component, dict) and component.get("id") == component_id:
            version = component.get("version")
            return version if isinstance(version, str) else None
    return None


def stack_component_string_commands(root: Path, component_id: str) -> list[str]:
    try:
        stack = load_json(root, "manifests/stack.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return []
    for component in stack.get("components", []):
        if isinstance(component, dict) and component.get("id") == component_id:
            return [item for item in component.get("commands", []) if isinstance(item, str)]
    return []


def landscape_component_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    landscape_dir = root / "catalogs" / "landscape"
    if not landscape_dir.is_dir():
        return ids
    for path in sorted(landscape_dir.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        for layer in document.get("layers", []) if isinstance(document, dict) else []:
            if not isinstance(layer, dict):
                continue
            for winner in layer.get("winners", []):
                if isinstance(winner, dict) and isinstance(winner.get("component_id"), str):
                    ids.add(winner["component_id"])
    return ids


def winner_pins(root: Path, component_id: str) -> set[str]:
    """Every landscape winner pin recorded for ``component_id`` (one per selecting layer)."""
    pins: set[str] = set()
    landscape_dir = root / "catalogs" / "landscape"
    for path in sorted(landscape_dir.glob("*.json")) if landscape_dir.is_dir() else []:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        for layer in document.get("layers", []) if isinstance(document, dict) else []:
            for winner in (layer.get("winners") or []) if isinstance(layer, dict) else []:
                if isinstance(winner, dict) and winner.get("component_id") == component_id \
                        and isinstance(winner.get("pin"), str) and winner["pin"].strip():
                    pins.add(winner["pin"].strip())
    return pins


def catalog_component_version(root: Path, component_id: str) -> str | None:
    """The version a receipt binds to by default: the landscape winner pin when every layer
    that selects the component agrees on it (the pin scripts/platform_status.py binds to),
    else the manifests/stack.json version."""
    pins = winner_pins(root, component_id)
    if len(pins) == 1:
        return pins.pop()
    if pins:
        return None
    return stack_component_version(root, component_id)


def platform_ids(root: Path) -> set[str]:
    try:
        manifest = load_json(root, "adoption/manifest.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return set()
    return {
        profile.get("id")
        for profile in manifest.get("platform_profiles", [])
        if isinstance(profile, dict)
    }


def platform_profile_map(root: Path) -> dict[str, dict[str, str]]:
    """Map adoption/manifest.json platform_profiles[].id to its declared os/architecture.

    Read-only: this only reads adoption/manifest.json (owned by another unit) to cross-check
    that a receipt's host.os/host.architecture are consistent with the platform_id it claims.
    """
    try:
        manifest = load_json(root, "adoption/manifest.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return {}
    result: dict[str, dict[str, str]] = {}
    for profile in manifest.get("platform_profiles", []):
        if not isinstance(profile, dict):
            continue
        profile_id, os_name, architecture = profile.get("id"), profile.get("os"), profile.get("architecture")
        if isinstance(profile_id, str) and isinstance(os_name, str) and isinstance(architecture, str):
            result[profile_id] = {"os": os_name, "architecture": architecture}
    return result


# receipt_filename_stem() escapes; '%' is escaped first so it can never collide with an
# escape token produced by escaping '/' or ':' (the id pattern never permits a literal '%',
# so this ordering is unambiguous and fully reversible).
FILENAME_ESCAPES = (("%", "%25"), ("/", "%2F"), (":", "%3A"))


def receipt_filename_stem(receipt_id: str) -> str:
    """Filesystem-safe filename stem for a receipt id.

    ``id`` may legitimately contain '/' (for example a stack component id like
    ``affaan-m/ECC``) or ':' (for example a landscape ``candidate:*`` alternative id like
    ``candidate:cli-cli``), neither of which is safe inside a single filesystem path
    segment (``safe_file`` rejects ':' outright, and '/' would create a nested directory).
    Each is percent-escaped here to a distinct, reversible token (``/`` -> ``%2F``, ``:`` ->
    ``%3A``) so every receipt is a flat file directly under ``evidence/hosts/<host_id>/``
    rather than silently creating a nested directory (or crashing register_file) that
    ``_iter_receipt_files`` would never glob. The ``id`` field itself is never escaped; only
    the filename is. '%' is not a character the id pattern permits, so this encoding cannot
    collide with a literal id.
    """
    stem = receipt_id
    for character, token in FILENAME_ESCAPES:
        stem = stem.replace(character, token)
    return stem


def evidence_files(root: Path) -> dict[str, dict]:
    try:
        evidence = load_json(root, "manifests/evidence.json")
    except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
        return {}
    result = {}
    for record in evidence.get("files", []):
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            result[record["path"]] = record
    return result


def register_file(root: Path, relative_path: str) -> None:
    """Update relative_path in manifests/evidence.json files[] with its current hash,
    or insert it at its sorted position (bisect) so files[] stays sorted by path --
    conflict-friendly inserts instead of always appending at the end."""
    evidence_path = safe_file(root, "manifests/evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    target = safe_file(root, relative_path)
    raw = target.read_bytes()
    record = {"path": relative_path, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    files = evidence.setdefault("files", [])
    for index, existing in enumerate(files):
        if isinstance(existing, dict) and existing.get("path") == relative_path:
            files[index] = record
            break
    else:
        paths = [existing.get("path", "") if isinstance(existing, dict) else "" for existing in files]
        files.insert(bisect.bisect_left(paths, relative_path), record)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- record


def run_command(cmd: str, cwd: Path, timeout: int) -> tuple[int, str, float]:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        exit_code = completed.returncode
        output = (completed.stdout or "") + (completed.stderr or "")
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        output = ((error.stdout or "") if isinstance(error.stdout, str) else "") + \
                  ((error.stderr or "") if isinstance(error.stderr, str) else "") + \
                  f"\n[host_receipts: command timed out after {timeout}s]"
    duration = time.monotonic() - start
    return exit_code, output, duration


def existing_review_summary(path: Path) -> str:
    """``kind:verdict`` for each review already in the receipt at ``path``, joined by ', ',
    so a refused overwrite names exactly what it would have erased (2026-09-25: a same-day
    rerecord silently erased an independent_session ``needs_changes`` review). Never raises:
    a receipt too damaged to parse still refuses the overwrite, it just cannot describe it."""
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return "existing receipt is unreadable"
    reviews = existing.get("reviews") if isinstance(existing, dict) and isinstance(existing.get("reviews"), list) else []
    entries = [f"{review.get('kind')}:{review.get('verdict')}" for review in reviews if isinstance(review, dict)]
    return ", ".join(entries) if entries else "no reviews"


def refuse_overwrite_message(relative_path: str, target: Path, receipt_id: str) -> str:
    return (f"error: refusing to overwrite existing receipt {relative_path!r} (existing reviews: "
            f"{existing_review_summary(target)}); receipts are never edited or overwritten once written "
            f"(docs/contributing-evidence.md) -- pass --supersedes {receipt_id!r} to record a new receipt "
            "that supersedes it without touching the original")


def next_free_superseding_id(root: Path, host_id: str, base_id: str) -> str:
    """Smallest ``<base_id>-N`` (N >= 2) with no existing receipt file under
    ``evidence/hosts/<host_id>/``, for ``record --supersedes``."""
    host_dir = root / "evidence" / "hosts" / host_id
    generation = 2
    while (host_dir / f"{receipt_filename_stem(f'{base_id}-{generation}')}.json").exists():
        generation += 1
    return f"{base_id}-{generation}"


def cmd_record(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    host_id = args.host_id
    if not HOST_ID_PATTERN.fullmatch(host_id):
        print(f"error: --host-id {host_id!r} must match ^[a-z0-9-]+-[0-9]{{8}}$")
        return 2
    if args.stage not in STAGES:
        print(f"error: --stage must be one of {sorted(STAGES)}")
        return 2
    if args.evidence_class not in EVIDENCE_CLASSES:
        print(f"error: --evidence-class must be one of {sorted(EVIDENCE_CLASSES)}")
        return 2

    known_platforms = platform_ids(root)
    if known_platforms and args.platform_id not in known_platforms:
        print(f"error: --platform-id {args.platform_id!r} is not a known adoption/manifest.json platform_profiles id")
        return 2

    try:
        recorder = resolve_identity(args.identity)
    except IdentityError as error:
        print(f"error: {error}")
        return 2
    if recorder is None:
        print(f"error: no recorder identity: pass --identity NAME (only a Claude Code session exports "
              f"{IDENTITY_ENV}; a Codex session, a human or CI must name itself)")
        return 2
    component_version = args.component_version or catalog_component_version(root, args.component_id)
    if normalize_pin(component_version) is None:
        print(f"error: no usable version for component {args.component_id!r} ({component_version!r}: its landscape "
              "pins disagree, it has none, or it has no digit such as 'unpinned'); pass --component-version with "
              "the version this host ran")
        return 2
    pins = winner_pins(root, args.component_id)
    if pins and not any(pin_matches(component_version, pin) for pin in pins) and not args.allow_unbound_version:
        print(f"error: version {component_version!r} matches no current winner pin of {args.component_id!r} "
              f"({', '.join(sorted(pins))}), so the receipt would never count toward a status; pass the pin as "
              "written, or --allow-unbound-version to record it anyway")
        return 2

    qualified_models: list[dict] = []
    for raw in args.qualified_model:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            print(f"error: --qualified-model is not valid JSON ({error})")
            return 2
        if not isinstance(parsed, dict):
            print("error: --qualified-model must be a JSON object")
            return 2
        qualified_models.append(parsed)
    if args.qualified_models_file:
        models_path = Path(args.qualified_models_file)
        if not models_path.is_absolute():
            models_path = root / models_path
        try:
            payload = json.loads(models_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"error: --qualified-models-file could not be read as JSON ({error})")
            return 2
        if not isinstance(payload, list):
            print("error: --qualified-models-file must contain a JSON array")
            return 2
        for entry in payload:
            if not isinstance(entry, dict):
                print("error: --qualified-models-file entries must be JSON objects")
                return 2
            qualified_models.append(entry)
    if qualified_models:
        # Full schema validation (every constraint: required keys, type, enum, maxLength, ...)
        # against the qualified_models[] item subschema, before anything below runs a single
        # command. A hand-rolled subset check here previously let a too-long `bars` (or any
        # other constraint this list did not name) through to run the commands and fail only
        # afterward at the pre-write validate_receipt_shape() call; validating up front with
        # the same schema-driven validator used everywhere else in this module means no
        # constraint can be missed twice, and nothing executes for a malformed entry.
        qualified_model_schema = (load_receipt_schema(root).get("properties", {})
                                  .get("qualified_models", {}).get("items", {}))
        for index, entry in enumerate(qualified_models):
            entry_errors: list[str] = []
            validate_against_schema(entry, qualified_model_schema, f"qualified_models[{index}]", entry_errors)
            if entry_errors:
                print("error: --qualified-model entry would not validate (checked before running any command): "
                      + "; ".join(entry_errors))
                return 2

    commands_to_run: list[str] = []
    if args.from_stack_commands:
        stack_commands = stack_component_string_commands(root, args.component_id)
        if not stack_commands:
            print(f"error: no plain-string commands found for component {args.component_id!r} in manifests/stack.json")
            return 2
        commands_to_run.extend(stack_commands)
    commands_to_run.extend(args.cmd or [])
    if not commands_to_run:
        print("error: no commands provided; pass --cmd and/or --from-stack-commands")
        return 2
    if args.stage == "use" and all(bare_help_or_version(cmd) for cmd in commands_to_run):
        print("error: --stage use records the component doing its job, but every command here is only a help or "
              "version call; pass a functional --cmd, or record these as --stage install")
        return 2

    catalog_revision = git_head(root)
    observed_at = utc_now()
    date_stamp = observed_at[:10].replace("-", "")

    # Compute the receipt id/path and refuse a collision *before* any command below runs, so a
    # same-day rerun can never erase an existing file's appended independent reviews (the
    # 2026-09-25 incident) -- receipts are never edited or overwritten once written. --supersedes
    # is the reviewable way to record a new receipt for the same host/component/stage/date instead.
    base_id = f"{host_id}--{args.component_id}--{args.stage}--{date_stamp}"
    if args.supersedes is None:
        receipt_id = base_id
    else:
        supersedes_match = ID_PATTERN.fullmatch(args.supersedes)
        if (supersedes_match is None or supersedes_match.group("host_id") != host_id
                or supersedes_match.group("component_id") != args.component_id
                or supersedes_match.group("stage") != args.stage
                or supersedes_match.group("date") != date_stamp):
            print(f"error: --supersedes {args.supersedes!r} must be an existing receipt id for this same "
                  f"recording's host/component/stage/date ({base_id!r}, optionally with a '-N' generation "
                  "suffix from an earlier supersede)")
            return 2
        superseded_relative = f"evidence/hosts/{host_id}/{receipt_filename_stem(args.supersedes)}.json"
        try:
            superseded_target = safe_file(root, superseded_relative)
        except InvalidDecisionIndex as error:
            print(f"error: --supersedes {args.supersedes!r} is not a valid receipt path: {error}")
            return 2
        if not superseded_target.is_file():
            print(f"error: --supersedes names {superseded_relative!r}, which does not exist; --supersedes must "
                  "name an already-recorded receipt")
            return 2
        receipt_id = next_free_superseding_id(root, host_id, base_id)

    relative_path = f"evidence/hosts/{host_id}/{receipt_filename_stem(receipt_id)}.json"
    try:
        target = safe_file(root, relative_path)
    except InvalidDecisionIndex as error:
        print(f"error: cannot record a receipt at {relative_path!r}: {error}")
        return 2
    if target.exists():
        print(refuse_overwrite_message(relative_path, target, receipt_id))
        return 2

    command_records = []
    for cmd in commands_to_run:
        exit_code, output, duration = run_command(cmd, cwd=root, timeout=args.timeout)
        sanitized = sanitize(output)
        command_records.append({
            "cmd": cmd,
            "exit": exit_code,
            "duration_s": round(duration, 3),
            "output_sha256": hashlib.sha256(output.encode("utf-8", "surrogateescape")).hexdigest(),
            "output_excerpt": sanitized[:MAX_EXCERPT_CHARS],
        })

    result = "pass" if all(record["exit"] == 0 for record in command_records) else "fail"

    limitations = args.limitation or [
        "Recorded receipt covers only the listed commands; it does not establish full "
        "component functional acceptance beyond what these commands exercise.",
    ]
    claim = args.claim or (
        f"On host {host_id} ({args.platform_id}), {len(command_records)} command(s) were run for "
        f"component {args.component_id!r} at stage {args.stage!r}; overall result {result}."
    )
    tool_versions = {args.component_id: component_version}
    recorded_by = identity_record(recorder, args.model)

    receipt = {
        "schema_version": 1,
        "id": receipt_id,
        "kind": "host_acceptance",
        "host": {
            "host_id": host_id,
            "platform_id": args.platform_id,
            "os": args.os or _default_os(),
            "architecture": args.architecture or _default_architecture(),
            "second_physical_machine": bool(args.second_physical_machine),
        },
        "catalog_revision": catalog_revision,
        "recorded_by": recorded_by,
        "component_id": args.component_id,
        "stage": args.stage,
        "commands": command_records,
        "tool_versions": tool_versions,
        "observed_at_utc": observed_at,
        "result": result,
        "claim": claim,
        "limitations": limitations,
        "evidence_class": args.evidence_class,
        "reviews": [
            {"kind": "self", "ref": "scripts/host_receipts.py record", "verdict": "agree", "at_utc": observed_at,
             "reviewer": dict(recorded_by)},
        ],
    }
    if qualified_models:
        receipt["qualified_models"] = qualified_models
    if args.hardware_profile_ref:
        receipt["host"]["hardware_profile_ref"] = args.hardware_profile_ref
    if args.supersedes:
        receipt["supersedes"] = args.supersedes

    # Check the receipt against the schema before writing anything (for example an overlong
    # --model), so a failed check never leaves a receipt that validate would reject.
    shape_errors: list[str] = []
    validate_receipt_shape(root, receipt, relative_path, shape_errors)
    if shape_errors:
        print("error: the receipt would not validate: " + "; ".join(shape_errors))
        return 2

    # Validate (and register) before/around the final write, rolling back the file on any
    # registration failure, so a crash here can never leave a written-but-unregistered
    # receipt behind (the receipt file and manifests/evidence.json stay coherent together).
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, indent=2) + "\n")
    except FileExistsError:
        # Defense in depth: the target.exists() check above already refused this exact path
        # once; this only catches a receipt another process created in the window since then.
        print(refuse_overwrite_message(relative_path, target, receipt_id))
        return 2
    try:
        register_file(root, relative_path)
    except Exception as error:
        target.unlink(missing_ok=True)
        print(f"error: could not register {relative_path!r} in manifests/evidence.json ({error}); rolled back")
        return 1
    print(relative_path)
    return 0


# adoption/manifest.json platform_profiles uses "macos" (not Python's platform.system()
# value "Darwin"/"darwin") and "linux" (which already matches); keep this normalization in
# sync with that vocabulary so a host recording with default flags produces host.os values
# consistent with the platform_profiles entry its --platform-id claims.
OS_NORMALIZATION = {"darwin": "macos", "linux": "linux"}


def _default_os() -> str:
    import platform as _platform
    raw = _platform.system().lower()
    return OS_NORMALIZATION.get(raw, raw)


def _default_architecture() -> str:
    import platform as _platform
    return _platform.machine().lower()


# ------------------------------------------------------------------------- review


def cmd_review(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    receipt_file = Path(args.receipt)
    if not receipt_file.is_absolute():
        receipt_file = root / receipt_file
    try:
        relative_path = receipt_file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        print("error: --receipt must be inside the repository root")
        return 2
    path = safe_file(root, relative_path)
    receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
    if args.kind not in REVIEW_KINDS:
        print(f"error: --kind must be one of {sorted(REVIEW_KINDS)}")
        return 2
    if args.verdict not in REVIEW_VERDICTS:
        print(f"error: --verdict must be one of {sorted(REVIEW_VERDICTS)}")
        return 2
    try:
        reviewer = resolve_identity(args.identity)
    except IdentityError as error:
        print(f"error: {error}")
        return 2
    if reviewer is None:
        print(f"error: no reviewer identity: pass --identity NAME (only a Claude Code session exports {IDENTITY_ENV})")
        return 2
    recorder = (receipt.get("recorded_by") or {}).get("identity_sha256") if isinstance(receipt.get("recorded_by"), dict) else None
    if args.kind != "self":
        if recorder is None:
            print("error: this receipt has no recorded_by identity, so an independent review cannot be checked "
                  "against its recorder; re-record it with the current scripts/host_receipts.py record")
            return 2
        if reviewer == recorder:
            print(f"error: --kind {args.kind} review from the recorder's own identity; an independent review must "
                  "come from a different session, lane or person")
            return 2
    now = utc_now()
    observed_at = receipt.get("observed_at_utc")
    if isinstance(observed_at, str) and now < observed_at:
        print(f"error: this host's clock ({now}) is behind the receipt's observed_at_utc ({observed_at}); a review "
              "dated before the observation is refused by validate, so fix the clock and rerun")
        return 2
    receipt.setdefault("reviews", []).append({
        "kind": args.kind, "ref": args.ref, "verdict": args.verdict, "at_utc": now,
        "reviewer": identity_record(reviewer, args.model),
    })
    shape_errors: list[str] = []
    validate_receipt_shape(root, receipt, relative_path, shape_errors)
    if shape_errors:
        print("error: the reviewed receipt would not validate: " + "; ".join(shape_errors))
        return 2
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    register_file(root, relative_path)
    print(relative_path)
    return 0


# ----------------------------------------------------------------------- validate


def _iter_receipt_files(root: Path):
    hosts_dir = root / "evidence" / "hosts"
    if not hosts_dir.is_dir():
        return
    for host_dir in sorted(hosts_dir.iterdir()):
        if not host_dir.is_dir():
            continue
        for path in sorted(host_dir.glob("*.json")):
            yield host_dir.name, path


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_receipt_shape(root: Path, receipt, label: str, errors: list[str]) -> None:
    """Validate ``receipt`` against every constraint in
    ``adoption/host-receipt.schema.json`` (type, enum, required, properties,
    additionalProperties, items, minItems, minLength, maxLength, minimum and pattern),
    via validate_against_schema(). This is the single source of truth: nothing here
    hand-duplicates a constraint the schema already states, so the two cannot drift."""
    schema = load_receipt_schema(root)
    validate_against_schema(receipt, schema, label, errors)


def validate_receipt_cross_references(root: Path, host_dir_name: str, path: Path, receipt: dict,
                                       errors: list[str], known_platforms: set[str],
                                       known_stack_ids: set[str], known_landscape_ids: set[str],
                                       known_files: dict[str, dict],
                                       known_platform_profiles: dict[str, dict[str, str]] | None = None) -> None:
    label = path.relative_to(root).as_posix()
    if not isinstance(receipt, dict):
        return
    if known_platform_profiles is None:
        known_platform_profiles = {}

    host = receipt.get("host") if isinstance(receipt.get("host"), dict) else {}
    platform_id = host.get("platform_id")
    if known_platforms and platform_id not in known_platforms:
        errors.append(f"{label}: host.platform_id {platform_id!r} is not a known adoption/manifest.json platform_profiles id")

    expected_profile = known_platform_profiles.get(platform_id) if isinstance(platform_id, str) else None
    if expected_profile is not None:
        actual_os, actual_architecture = host.get("os"), host.get("architecture")
        if actual_os != expected_profile.get("os") or actual_architecture != expected_profile.get("architecture"):
            errors.append(
                f"{label}: host.os={actual_os!r}/host.architecture={actual_architecture!r} is inconsistent with "
                f"adoption/manifest.json platform_profiles {platform_id!r} "
                f"(expected os={expected_profile.get('os')!r}, architecture={expected_profile.get('architecture')!r})")

    component_id = receipt.get("component_id")
    if (known_stack_ids or known_landscape_ids) and component_id not in known_stack_ids and component_id not in known_landscape_ids:
        errors.append(f"{label}: component_id {component_id!r} is not a known manifests/stack.json or landscape winners component id")

    receipt_id = receipt.get("id", "")
    host_id = host.get("host_id", "")
    _require(host_dir_name == host_id, errors, f"{label}: directory {host_dir_name!r} does not match host.host_id {host_id!r}")
    expected_stem = receipt_filename_stem(receipt_id) if isinstance(receipt_id, str) else receipt_id
    _require(path.stem == expected_stem, errors, f"{label}: filename {path.stem!r} does not match id {receipt_id!r}")
    id_match = ID_PATTERN.fullmatch(receipt_id) if isinstance(receipt_id, str) else None
    if id_match is not None:
        id_host_id = id_match.group("host_id")
        _require(id_host_id == host_id, errors, f"{label}: id host segment {id_host_id!r} does not match host.host_id {host_id!r}")
        id_component_id = id_match.group("component_id")
        _require(id_component_id == component_id, errors,
                  f"{label}: id component segment {id_component_id!r} does not match component_id {component_id!r}")
        id_stage = id_match.group("stage")
        stage_value = receipt.get("stage")
        _require(id_stage == stage_value, errors,
                  f"{label}: id stage segment {id_stage!r} does not match stage {stage_value!r}")
        observed_at = receipt.get("observed_at_utc")
        if isinstance(observed_at, str) and ISO_UTC_PATTERN.fullmatch(observed_at):
            id_date = id_match.group("date")
            expected_date = observed_at[:10].replace("-", "")
            _require(id_date == expected_date, errors,
                      f"{label}: id date segment {id_date!r} does not match observed_at_utc date {expected_date!r}")

    supersedes = receipt.get("supersedes")
    if isinstance(supersedes, str) and supersedes:
        supersedes_match = ID_PATTERN.fullmatch(supersedes)
        if supersedes_match is None:
            errors.append(f"{label}: supersedes {supersedes!r} is not a well-formed receipt id")
        else:
            _require(supersedes_match.group("host_id") == host_id, errors,
                      f"{label}: supersedes host segment {supersedes_match.group('host_id')!r} does not match "
                      f"host.host_id {host_id!r}")
            _require(supersedes_match.group("component_id") == component_id, errors,
                      f"{label}: supersedes component segment {supersedes_match.group('component_id')!r} does "
                      f"not match component_id {component_id!r}")
            _require(supersedes_match.group("stage") == receipt.get("stage"), errors,
                      f"{label}: supersedes stage segment {supersedes_match.group('stage')!r} does not match "
                      f"stage {receipt.get('stage')!r}")
            _require(supersedes != receipt_id, errors, f"{label}: supersedes must not equal this receipt's own id")
            superseded_relative = f"evidence/hosts/{host_id}/{receipt_filename_stem(supersedes)}.json"
            _require(superseded_relative in known_files, errors,
                      f"{label}: supersedes {supersedes!r} ({superseded_relative}) is not registered in "
                      "manifests/evidence.json files[]")

    commands = receipt.get("commands") if isinstance(receipt.get("commands"), list) else []
    result = receipt.get("result")
    if result == "pass":
        for index, command in enumerate(commands):
            if not isinstance(command, dict):
                continue
            exit_code = command.get("exit")
            expected = command.get("expected_exit", 0)
            if exit_code != expected:
                errors.append(f"{label}.commands[{index}]: result is 'pass' but exit {exit_code!r} != expected {expected!r}")

    recorded_by = receipt.get("recorded_by") if isinstance(receipt.get("recorded_by"), dict) else {}
    recorder = recorded_by.get("identity_sha256")
    observed_at = receipt.get("observed_at_utc")
    reviews = receipt.get("reviews") if isinstance(receipt.get("reviews"), list) else []
    for index, review in enumerate(reviews):
        if not isinstance(review, dict) or review.get("kind") == "self":
            continue
        reviewer = review.get("reviewer") if isinstance(review.get("reviewer"), dict) else {}
        where = f"{label}.reviews[{index}]"
        if recorder is None:
            errors.append(f"{where}: a {review.get('kind')!r} review needs the receipt's recorded_by identity to "
                          "check independence; re-record the receipt with the current recorder")
        elif not reviewer.get("identity_sha256"):
            errors.append(f"{where}: a {review.get('kind')!r} review must carry reviewer.identity_sha256")
        elif reviewer.get("identity_sha256") == recorder:
            errors.append(f"{where}: a {review.get('kind')!r} review comes from the recorder's own identity")
        at_utc = review.get("at_utc")
        if isinstance(at_utc, str) and isinstance(observed_at, str) and at_utc < observed_at:
            errors.append(f"{where}: review at_utc {at_utc} precedes observed_at_utc {observed_at}")

    latest_allowed = datetime.fromtimestamp(time.time() + FUTURE_SKEW_S, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dated = [("observed_at_utc", observed_at)] + [
        (f"reviews[{index}].at_utc", review.get("at_utc")) for index, review in enumerate(reviews)
        if isinstance(review, dict)]
    for field, value in dated:
        if isinstance(value, str) and ISO_UTC_PATTERN.fullmatch(value) and value > latest_allowed:
            errors.append(f"{label}.{field}: {value} is later than this machine's clock allows "
                          f"({latest_allowed}, {FUTURE_SKEW_S // 60} minutes of skew); a future date would stay "
                          "the latest receipt or review")

    catalog_revision = receipt.get("catalog_revision")
    if isinstance(catalog_revision, str) and SHA_PATTERN.fullmatch(catalog_revision):
        try:
            check = subprocess.run(
                ["git", "--no-optional-locks", "-C", str(root), "cat-file", "-e", f"{catalog_revision}^{{commit}}"],
                capture_output=True, timeout=5, check=False,
            )
            if check.returncode != 0:
                # git cat-file -e exits 1 for a missing object and 128 for a well-formed
                # SHA that git cannot resolve to a commit (for example a shallow checkout
                # or a fabricated SHA); both mean "not present", not "git unavailable".
                errors.append(f"{label}: catalog_revision {catalog_revision} is not a commit present in this checkout")
        except (OSError, subprocess.TimeoutExpired):
            pass

    relative_receipt_path = path.relative_to(root).as_posix()
    registered = known_files.get(relative_receipt_path)
    if registered is None:
        errors.append(f"{label}: receipt is not registered in manifests/evidence.json files[]")
    else:
        raw = path.read_bytes()
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        if registered.get("sha256") != actual_sha256:
            errors.append(f"{label}: manifests/evidence.json files[] sha256 does not match the receipt bytes")

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError:
        content = path.read_bytes().decode("latin-1")
    for description, pattern in PRIVATE_CONTENT:
        if pattern.search(content):
            errors.append(f"{label}: contains possible {description}")
    # The raw-text scan above misses content a JSON escape hides (for example / in
    # place of a literal '/', or \/ ): scan every decoded string value AND every key,
    # recursively, from the parsed receipt as well.
    if isinstance(receipt, dict):
        for decoded_string in iter_receipt_strings(receipt):
            for description, pattern in PRIVATE_CONTENT:
                if pattern.search(decoded_string):
                    errors.append(f"{label}: contains possible {description} (decoded JSON value or key)")


def cmd_validate(args: argparse.Namespace) -> int:
    root = repo_root(args.root)
    known_platforms = platform_ids(root)
    known_platform_profiles = platform_profile_map(root)
    known_stack_ids = stack_component_ids(root)
    known_landscape_ids = landscape_component_ids(root)
    known_files = evidence_files(root)

    errors: list[str] = []
    count = 0
    for host_dir_name, path in _iter_receipt_files(root):
        count += 1
        label = path.relative_to(root).as_posix()
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        except (OSError, UnicodeError, ValueError, InvalidDecisionIndex) as error:
            errors.append(f"{label}: invalid JSON ({type(error).__name__})")
            continue
        validate_receipt_shape(root, receipt, label, errors)
        validate_receipt_cross_references(
            root, host_dir_name, path, receipt, errors,
            known_platforms, known_stack_ids, known_landscape_ids, known_files,
            known_platform_profiles,
        )

    if errors:
        print(f"Host receipt validation failed ({len(errors)} error(s) across {count} receipt(s)):")
        for error in errors:
            print(f"- {error}")
        return 1
    print(json.dumps({"status": "passed", "receipts": count}, sort_keys=True))
    return 0


# ------------------------------------------------------------------------ summary


def review_state(receipt: dict) -> str:
    """``agree``, ``dissent`` or ``none`` over the receipt's independent reviews.

    A review is well formed when it is not ``self``, carries a reviewer identity that differs
    from ``recorded_by``, and has a valid ``at_utc`` not older than the observation. Only
    each well-formed reviewer's latest review counts, so a reviewer may withdraw their own
    dissent. Any standing ``disagree`` or ``needs_changes`` vetoes, however many reviewers
    agree, and so does a dissent in a review that is not well formed, which nobody can
    withdraw. A non-self ``agree`` that is not well formed keeps the state from being
    ``agree``. Without ``recorded_by`` no review can be checked for independence."""
    recorded_by = receipt.get("recorded_by") if isinstance(receipt.get("recorded_by"), dict) else {}
    recorder = recorded_by.get("identity_sha256")
    observed_at = receipt.get("observed_at_utc") if isinstance(receipt.get("observed_at_utc"), str) else ""
    latest: dict[str, tuple[str, int, str]] = {}
    malformed_dissent = malformed_other = False
    reviews = receipt.get("reviews") if isinstance(receipt.get("reviews"), list) else []
    for position, review in enumerate(reviews):
        if not isinstance(review, dict):
            malformed_other = True
            continue
        if review.get("kind") == "self":
            continue
        reviewer = review.get("reviewer") if isinstance(review.get("reviewer"), dict) else {}
        identity = reviewer.get("identity_sha256")
        at_utc = review.get("at_utc") if isinstance(review.get("at_utc"), str) else ""
        well_formed = bool(recorder and identity and identity != recorder
                           and ISO_UTC_PATTERN.fullmatch(at_utc) and at_utc >= observed_at)
        if not well_formed:
            if review.get("verdict") in DISSENT_VERDICTS:
                malformed_dissent = True
            else:
                malformed_other = True
            continue
        key = (at_utc, position, review.get("verdict"))
        if identity not in latest or key[:2] > latest[identity][:2]:
            latest[identity] = key
    verdicts = {entry[2] for entry in latest.values()}
    if malformed_dissent or verdicts & DISSENT_VERDICTS:
        return "dissent"
    if malformed_other or not recorder:
        return "none"
    return "agree" if "agree" in verdicts else "none"


def build_summary(root: Path) -> dict:
    """Aggregate every recorded host receipt by component x platform.

    Each platform bucket additionally reports
    ``independently_reviewed_native_proven_pass_stages``: the sorted list of
    lifecycle stages with at least one receipt that is ``result: pass``,
    ``evidence_class: native_proven``, carries a non-``self`` review with
    verdict ``agree``, declares ``host.second_physical_machine: true``, has a
    ``host.os``/``host.architecture`` consistent with the claimed
    ``platform_id`` (when ``adoption/manifest.json`` records one), and passes
    ``validate_receipt_shape`` (a fabricated or malformed receipt cannot enter
    this stricter list even though it may still appear in the looser
    per-stage pass/fail counts above). "Independently reviewed" is
    ``review_state(receipt) == "agree"``. Each per-receipt entry also carries the receipt's
    own ``qualified_models`` (empty unless the receipt both declares some and is shape-valid),
    for callers such as ``scripts/component_matrix.py`` to surface per platform; this never
    feeds review or e2e-state computation. Those counts ignore pins; the
    per-receipt ``receipts`` entries carry what ``scripts/platform_status.py``
    needs to bind a receipt to a winner's current pin, and that module is the
    one rule for platform status and the macOS flip. This function does not re-run the full
    cross-reference checks (catalog_revision presence, evidence.json
    registration, id/path coherence): CI runs ``host_receipts.py validate``
    as a separate, earlier gate for that.
    """
    platform_profiles = platform_profile_map(root)
    components: dict[str, dict] = {}
    for _host_dir_name, path in _iter_receipt_files(root):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json)
        except (OSError, UnicodeError, ValueError, InvalidDecisionIndex):
            continue
        component_id = receipt.get("component_id")
        host = receipt.get("host") if isinstance(receipt.get("host"), dict) else {}
        platform_id = host.get("platform_id")
        stage = receipt.get("stage")
        result = receipt.get("result")
        evidence_class = receipt.get("evidence_class")
        observed_at = receipt.get("observed_at_utc")
        if not isinstance(component_id, str) or not isinstance(platform_id, str):
            continue
        component_bucket = components.setdefault(component_id, {"platforms": {}})
        platform_bucket = component_bucket["platforms"].setdefault(
            platform_id, {
                "stages": {}, "latest_observed_at_utc": None, "independently_reviewed_passes": 0,
                "independently_reviewed_fails": 0, "dissented": 0,
                "independently_reviewed_native_proven_pass_stages": set(), "receipts": [],
            },
        )
        stage_counts = platform_bucket["stages"].setdefault(
            stage, {"pass": 0, "fail": 0, "partial": 0, "not_runnable": 0},
        )
        if result in stage_counts:
            stage_counts[result] += 1
        if isinstance(observed_at, str):
            current_latest = platform_bucket["latest_observed_at_utc"]
            if current_latest is None or observed_at > current_latest:
                platform_bucket["latest_observed_at_utc"] = observed_at
        state = review_state(receipt)
        independently_reviewed = state == "agree"
        second_physical_machine = host.get("second_physical_machine") is True
        expected_profile = platform_profiles.get(platform_id)
        platform_identity_ok = expected_profile is None or (
            host.get("os") == expected_profile.get("os")
            and host.get("architecture") == expected_profile.get("architecture")
        )
        relative = path.relative_to(root).as_posix()
        shape_errors: list[str] = []
        validate_receipt_shape(root, receipt, relative, shape_errors)
        tool_versions = receipt.get("tool_versions") if isinstance(receipt.get("tool_versions"), dict) else {}
        component_version = tool_versions.get(component_id)
        qualified_models = [entry for entry in (receipt.get("qualified_models") or [])
                            if isinstance(entry, dict)] if not shape_errors else []
        platform_bucket["receipts"].append({
            "path": relative,
            "host_id": host.get("host_id") if isinstance(host.get("host_id"), str) else None,
            "stage": stage,
            "result": result,
            "evidence_class": evidence_class,
            "component_version": component_version if isinstance(component_version, str) else None,
            "observed_at_utc": observed_at if isinstance(observed_at, str) else None,
            "review_state": state,
            "second_physical_machine": second_physical_machine,
            "platform_identity_ok": platform_identity_ok,
            "shape_ok": not shape_errors,
            "qualified_models": qualified_models,
        })
        if state == "dissent":
            platform_bucket["dissented"] += 1
        if result == "fail" and independently_reviewed:
            platform_bucket["independently_reviewed_fails"] += 1
        if result == "pass" and independently_reviewed:
            platform_bucket["independently_reviewed_passes"] += 1
            if evidence_class == "native_proven" and isinstance(stage, str):
                if second_physical_machine and platform_identity_ok and not shape_errors:
                    platform_bucket["independently_reviewed_native_proven_pass_stages"].add(stage)

    for component_bucket in components.values():
        for platform_bucket in component_bucket["platforms"].values():
            platform_bucket["independently_reviewed_native_proven_pass_stages"] = sorted(
                platform_bucket["independently_reviewed_native_proven_pass_stages"]
            )
            platform_bucket["receipts"].sort(key=lambda entry: entry["path"])

    return {"generated_at_utc": utc_now(), "components": components}


def receipt_age_days(observed_at: str | None, now: datetime) -> int | None:
    if not isinstance(observed_at, str) or not ISO_UTC_PATTERN.fullmatch(observed_at):
        return None
    observed = datetime.strptime(observed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (now - observed).days


def cmd_summary(args: argparse.Namespace) -> int:
    """Summaries carry the receipt age and an ``old`` flag past --max-age-days. Age is only
    reported here, never in the generated matrix, so ``component_matrix.py --check`` stays
    deterministic; the pin binding in scripts/platform_status.py is what retires a receipt."""
    root = repo_root(args.root)
    summary = build_summary(root)
    components = summary["components"]
    now = datetime.now(timezone.utc)
    for component_bucket in components.values():
        for bucket in component_bucket["platforms"].values():
            age = receipt_age_days(bucket["latest_observed_at_utc"], now)
            bucket["latest_age_days"] = age
            bucket["old"] = age is not None and age > args.max_age_days
            for entry in bucket["receipts"]:
                entry["age_days"] = receipt_age_days(entry["observed_at_utc"], now)
    summary["max_age_days"] = args.max_age_days
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for component_id in sorted(components):
            for platform_id in sorted(components[component_id]["platforms"]):
                bucket = components[component_id]["platforms"][platform_id]
                stage_text = ", ".join(
                    f"{stage}={counts}" for stage, counts in sorted(bucket["stages"].items())
                )
                print(f"{component_id} @ {platform_id}: {stage_text} "
                      f"(latest={bucket['latest_observed_at_utc']}, age_days={bucket['latest_age_days']}"
                      f"{', OLD' if bucket['old'] else ''}, "
                      f"independently_reviewed_passes={bucket['independently_reviewed_passes']}, "
                      f"independently_reviewed_fails={bucket['independently_reviewed_fails']}, "
                      f"dissented={bucket['dissented']})")
    return 0


# --------------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate every recorded host receipt")
    validate_parser.add_argument("--root", type=Path, default=None)
    validate_parser.set_defaults(func=cmd_validate)

    record_parser = subparsers.add_parser("record", help="Run commands and record a new host receipt")
    record_parser.add_argument("--root", type=Path, default=None)
    record_parser.add_argument("--host-id", required=True)
    record_parser.add_argument("--platform-id", required=True)
    record_parser.add_argument("--component-id", required=True)
    record_parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    record_parser.add_argument("--supersedes", default=None,
                               help="Existing receipt id for this same host/component/stage/date to supersede: "
                                    "writes a new receipt at the next free '-N' generation, records this in its "
                                    "'supersedes' field, and leaves the original file untouched. Without this, "
                                    "record refuses (exit 2) when today's receipt for this host/component/stage "
                                    "already exists, instead of overwriting it.")
    record_parser.add_argument("--hardware-profile-ref", default=None)
    record_parser.add_argument("--second-physical-machine", action="store_true")
    record_parser.add_argument("--cmd", action="append", default=[])
    record_parser.add_argument("--from-stack-commands", action="store_true")
    record_parser.add_argument("--claim", default=None)
    record_parser.add_argument("--limitation", action="append", default=[])
    record_parser.add_argument("--evidence-class", required=True, choices=sorted(EVIDENCE_CLASSES))
    record_parser.add_argument("--os", default=None)
    record_parser.add_argument("--architecture", default=None)
    record_parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    record_parser.add_argument("--identity", default=None,
                               help=f"Recorder identity (stored hashed); defaults to ${IDENTITY_ENV}, else required")
    record_parser.add_argument("--model", default=None, help="Model or runtime that ran the recording (optional)")
    record_parser.add_argument("--component-version", default=None,
                               help="Version this host ran; defaults to the landscape pin or the stack version")
    record_parser.add_argument("--allow-unbound-version", action="store_true",
                               help="Record a --component-version that matches no current winner pin (never counts)")
    record_parser.add_argument("--qualified-model", action="append", default=[],
                               help='JSON object {model_id, revision, runtime, runtime_version, bars, result}; '
                                    'repeatable. Local model weights qualified on this host\'s runtime.')
    record_parser.add_argument("--qualified-models-file", default=None,
                               help="Path to a JSON array of qualified-model objects, merged after --qualified-model")
    record_parser.set_defaults(func=cmd_record)

    review_parser = subparsers.add_parser("review", help="Append an independent review to an existing receipt")
    review_parser.add_argument("--root", type=Path, default=None)
    review_parser.add_argument("--receipt", required=True)
    review_parser.add_argument("--kind", required=True, choices=sorted(REVIEW_KINDS))
    review_parser.add_argument("--ref", required=True)
    review_parser.add_argument("--verdict", required=True, choices=sorted(REVIEW_VERDICTS))
    review_parser.add_argument("--identity", default=None,
                               help=f"Reviewer identity (stored hashed); defaults to ${IDENTITY_ENV}, else required")
    review_parser.add_argument("--model", default=None, help="Model or runtime of the reviewer (optional)")
    review_parser.set_defaults(func=cmd_review)

    summary_parser = subparsers.add_parser("summary", help="Summarize recorded host receipts")
    summary_parser.add_argument("--root", type=Path, default=None)
    summary_parser.add_argument("--json", action="store_true")
    summary_parser.add_argument("--max-age-days", type=int, default=180,
                                help="Flag platforms whose latest receipt is older than this (report only)")
    summary_parser.set_defaults(func=cmd_summary)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InvalidHostReceipt as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
