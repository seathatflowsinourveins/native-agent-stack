#!/usr/bin/env python3
"""Generate the hosted-family catalog and check active model selectors.

Only catalog metadata is consumed; this module never starts a model or a
Claude process. Check/notice are offline and never change configuration.
Findings contain a locator and model IDs, never source lines or other values.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "catalogs/foundation/latest-models.json"
FAMILIES = ("gpt-sol", "gpt-astra", "gpt-luna", "claude-opus", "claude-sonnet", "claude-haiku", "claude-fable")
GPT = re.compile(r"gpt-(\d+(?:\.\d+)*)-(sol|astra|luna)\Z")
CLAUDE = re.compile(r"claude-([a-z][a-z0-9]*)-(\d+(?:-\d+)?)(?:-(\d{8}))?\Z")
MODEL = re.compile(r"(?<![\w.-])(?:gpt-[0-9][\w.-]*|gpt-reserve|codex-auto-review|o[134](?:-mini)?|claude-(?:[a-z][a-z0-9]*-)?[0-9][\w.-]*)(?:\[1m\])?(?![\w.-])")
EFFORT = re.compile(r"-(?:low|medium|high|xhigh|max|ultra)(?:-fast)?\Z")
CLI_ALIASES = {"opus": "claude-opus", "sonnet": "claude-sonnet", "haiku": "claude-haiku", "fable": "claude-fable", "best": "claude-fable"}
NATIVE_ROUTING_ALIASES = {"gpt-reserve", "codex-auto-review"}
SELECTOR = re.compile(r"(?:^|_)(?:model|model_id|model_name|default_model|fallback_model|review_model|agent_model)$", re.I)
KEY_EXCLUSIONS = {"supported_models", "model_catalog_json", "model_pattern", "model_regex"}
RECORD_KEYS = {"previous", "history", "historical", "examples", "landscape_check", "newer_candidates", "release_line"}
RECORD_STATUSES = {"retired", "rejected", "superseded", "historical", "not_selected", "not-selected"}
FROZEN_EXPERIMENTS = ("blueprints/convergence-practice/gpt6-family-tiering-20260926/", "blueprints/convergence-practice/native-recovery/", "blueprints/convergence-practice/native-worker/", "blueprints/convergence-practice/worker-recovery/")
RECORD_PARTS = {"tests", "fixtures", "node_modules", "vendor", ".git", ".venv", "__pycache__", "receipts", "logs", "history", "archive", "backups", "captures", "raw"}
TEXT_SUFFIXES = {"", ".py", ".js", ".cjs", ".mjs", ".ts", ".sh", ".bash", ".ps1", ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".env", ".md", ".service"}
MAX_BYTES = 2_000_000
MAX_AGE = timedelta(hours=24)
MODEL_FLAGS = {"--model", "--model-id", "-m"}
COMMAND_KEYS = {"command", "commands", "argv", "args", "command_line", "exec_start"}


class CurrencyError(ValueError):
    pass


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise CurrencyError("catalog time must be an ISO timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise CurrencyError("catalog time must include a timezone")
    return result.astimezone(timezone.utc)


def model_identity(identifier: str):
    """Stable generation identity; availability or gateway created time is not rank."""
    gpt = GPT.fullmatch(identifier)
    if gpt:
        return "gpt-" + gpt[2], tuple(int(x) for x in gpt[1].split("."))
    claude = CLAUDE.fullmatch(identifier)
    if claude and not claude[3]:
        return "claude-" + claude[1], tuple(int(x) for x in claude[2].split("-"))
    return None


def generate(codex: Path, omniroute: Path, claude: Path, recorded_at: str) -> dict:
    utc(recorded_at)
    inputs = {"codex": codex, "omniroute": omniroute, "claude": claude}
    documents = {name: json.loads(path.read_text()) for name, path in inputs.items()}
    native = documents["codex"].get("models")
    gateway = documents["omniroute"].get("data")
    anthropic = documents["claude"].get("data")
    if not all(isinstance(rows, list) and rows for rows in (native, gateway, anthropic)):
        raise CurrencyError("all three nonempty native model catalogs are required")
    if documents["claude"].get("has_more"):
        raise CurrencyError("Claude catalog pagination is incomplete")
    candidates = {}
    for row in native:
        identifier = row.get("slug", "")
        identity = model_identity(identifier)
        if identity and identity[0].startswith("gpt-"):
            candidates.setdefault(identity[0], []).append((identity[1], identifier))
    for row in anthropic:
        identifier = row.get("id", "")
        identity = model_identity(identifier)
        if identity and identity[0].startswith("claude-") and row.get("lifecycle") == "active":
            candidates.setdefault(identity[0], []).append((identity[1], identifier))
    if not set(FAMILIES) <= set(candidates):
        raise CurrencyError("the native catalogs do not cover all seven hosted families")
    latest = {family: max(candidates[family])[1] for family in sorted(candidates)}
    aliases = {identifier: identifier for identifier in latest.values()}
    gateway_ids = {row.get("id") for row in gateway if isinstance(row, dict)}
    for identifier in gateway_ids:
        if not isinstance(identifier, str):
            continue
        bare = identifier.rsplit("/", 1)[-1]
        base = EFFORT.sub("", bare)
        if base in latest.values():
            aliases[identifier] = base
            # Prefixes are transport routing; a tier is accepted only when observed.
            aliases[bare] = base
    for identifier in latest.values():
        if identifier.startswith("claude-"):
            aliases[identifier + "[1m]"] = identifier
    sources = []
    for name, path in inputs.items():
        rows = native if name == "codex" else gateway if name == "omniroute" else anthropic
        document = documents[name]
        timestamp_key = next((key for key in ("fetched_at", "captured_at", "observed_at") if key in document), None)
        observed = document[timestamp_key] if timestamp_key else None
        if observed is not None:
            utc(observed)
        sources.append({"name": name, "observed_at": observed,
                        "timestamp_origin": timestamp_key or "not_attested_in_capture",
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows)})
    routing_aliases = sorted({row["slug"] for row in native if row.get("slug") in NATIVE_ROUTING_ALIASES})
    return {"schema_version": 1, "catalog_kind": "versioned_snapshot",
            "generated_at": datetime.now(timezone.utc).isoformat(), "recorded_at": recorded_at,
            "latest": latest, "aliases": dict(sorted(aliases.items())), "native_routing_aliases": routing_aliases,
            "sources": sources, "selection": "maximum stable generation per declared hosted family; native Codex for GPT, Anthropic active lines for Claude; gateway only supplies observed routing/effort aliases",
            "limits": {"codex_network_refresh_certified": False, "gateway_created_is_release_date": False, "inference_or_route_resolution_qualified": False},
            "exempt_rule": "dated evidence/decisions/research/receipts and test/reference material are records; active agents, lanes, templates, launchers and defaults are not exempt by extension or a date in their path"}


def load_manifest(path: Path, now: datetime) -> dict:
    try:
        data = json.loads(path.read_text())
        if (not isinstance(data, dict) or data.get("schema_version") != 1
                or not isinstance(data.get("latest"), dict) or not set(FAMILIES) <= set(data["latest"])):
            raise CurrencyError("latest-models manifest has an unsupported shape")
        if any(not isinstance(identifier, str) or not model_identity(identifier)
               or model_identity(identifier)[0] != family for family, identifier in data["latest"].items()):
            raise CurrencyError("latest-models manifest has an invalid family identity")
        age = now - utc(data["generated_at"])
        snapshot = data.get("catalog_kind") == "versioned_snapshot"
        if data.get("catalog_kind") not in {None, "versioned_snapshot", "live_observation"}:
            raise CurrencyError("latest-models manifest has an unsupported catalog kind")
        if (not snapshot and age > MAX_AGE) or age < -timedelta(minutes=5):
            raise CurrencyError("latest-models manifest needs a fresh native catalog observation")
        if (not isinstance(data.get("sources"), list) or len(data["sources"]) != 3
                or not all(isinstance(row, dict) for row in data["sources"])
                or {row["name"] for row in data["sources"]} != {"codex", "omniroute", "claude"}):
            raise CurrencyError("latest-models manifest has incomplete catalog sources")
        for row in data["sources"]:
            if (type(row.get("rows")) is not int or row["rows"] <= 0
                    or not re.fullmatch(r"[a-f0-9]{64}", row.get("sha256", ""))):
                raise CurrencyError("latest-models source observation is invalid")
            if snapshot and row.get("observed_at") is None:
                continue
            source_age = now - utc(row["observed_at"])
            if (not snapshot and source_age > MAX_AGE) or source_age < -timedelta(minutes=5):
                raise CurrencyError("latest-models source observation needs refreshing")
        if not isinstance(data["aliases"], dict) or any(v not in data["latest"].values() for v in data["aliases"].values()):
            raise CurrencyError("latest-model alias target is not a current family")
        if (any(data["aliases"].get(identifier) != identifier for identifier in data["latest"].values())
                or any(EFFORT.sub("", alias.rsplit("/", 1)[-1].removesuffix("[1m]")) != target
                       for alias, target in data["aliases"].items())):
            raise CurrencyError("latest-model aliases must retain the current generation identity")
        routing = data.get("native_routing_aliases", [])
        if (not isinstance(routing, list) or any(not isinstance(alias, str) or alias not in NATIVE_ROUTING_ALIASES for alias in routing)
                or len(routing) != len(set(routing))):
            raise CurrencyError("native routing aliases must be unique observed routing identities")
        return data
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise CurrencyError(str(error) if isinstance(error, CurrencyError) else "latest-models manifest is unavailable or invalid") from None


def exempt(path: str) -> str | None:
    parts = Path(path).parts
    if {part.lower() for part in parts} & {"n2", "paper-open-e2e"} or Path(path).name == "STOP":
        return "peer-owned protected lane outside the currency scope"
    if set(parts) & RECORD_PARTS:
        return "record, fixture or dependency"
    if path.startswith("docs/decisions/"):
        return "dated decision record"
    if path in {"manifests/evidence.json", "catalogs/foundation/model-currency.json"}:
        return "file registration or dated age-review inventory; not a runtime selector"
    if path == "catalogs/landscape/grand-catalog-20261008.json":
        # Published schema-1 g5-compact-landscape on main ff69fc86 contains
        # reference rows; the full selector grammar extracts no active values.
        return "dated G5 compact landscape comparison record; model references are source metadata"
    if path.startswith(FROZEN_EXPERIMENTS):
        return "frozen completed experiment and exact replay source"
    if path == "blueprints/convergence-practice/omniroute-runtime-workers/experiment.json":
        return "September 30 frozen runtime-worker observations and replay commands; October 3 publication note preserves their historical identity"
    if path == "docs/token-efficiency-stack.json":
        return "dated 2026-09-27 token-efficiency reference edition; upstream_commands retain the observed source-host setup, not live model defaults"
    if path in {"blueprints/us-equities/convergence-review/README.md", "blueprints/us-equities/research-efficiency/README.md"}:
        return "dated review invocation or frozen comparison documentation"
    if path in {"blueprints/us-equities/research-efficiency/experiment.py",
                "blueprints/us-equities/research-efficiency/run_codex.py",
                "blueprints/us-equities/research-efficiency/review.py",
                "blueprints/us-equities/research-efficiency/plan.json",
                "blueprints/us-equities/research-efficiency/native-receipt.json"}:
        return "completed frozen research comparison and exact replay source; README documents its fixed commands"
    if re.match(r"test[-_].*\.(?:py|js|mjs|cjs|ts)$", Path(path).name):
        return "test source"
    if path.startswith("evidence/"):
        # The maintained install kit carries active instructions despite its date.
        active_kit = "evidence/artifacts/new-wsl-install-plan-20261002/"
        if not path.startswith(active_kit) or Path(path).name == "SOURCES.md":
            return "dated evidence record"
    if path.startswith("docs/research/") or (path.startswith("blueprints/") and Path(path).name in {"protocol.json", "receipt.json"}):
        return "frozen study record"
    if any(re.fullmatch(r"(?:trials|gap-wave\d*|gap-resolution|host-changes|research-cc-role)-\d{8}", part) for part in parts):
        return "dated trial/source record"
    if Path(path).suffix in {".jsonl", ".log", ".lock"}:
        return "append-only record or dependency lock"
    return None


def measurement(value: dict) -> bool:
    """A dated native observation is immutable evidence, even inside a live carrier."""
    dated = any(isinstance(item, str) and re.match(r"20\d\d-\d\d-\d\d", item)
                and re.search(r"(?:_at|date|time)(?:_utc)?$", key)
                for key, item in value.items())
    kind = value.get("kind", "")
    native = isinstance(kind, str) and kind in {"native_model_e2e", "native_cli_e2e", "execution_receipt", "observation"}
    fields = {"native_usage", "native_results", "combined_native_reported_token_counts", "exit_code"}
    return dated and (native or bool(fields & value.keys()))


def selector_key(value: str) -> bool:
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", value).lower().replace("-", "_")
    if key in KEY_EXCLUSIONS or any(word in key for word in ("secret", "password", "token", "api_key")):
        return False
    return bool(SELECTOR.search(key) or key in {"model", "modelid", "modelname", "fallback_models", "available_models"})


def command_key(value: str) -> str | None:
    key = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", value).lower().replace("-", "_")
    if key in COMMAND_KEYS or any(key.endswith("_" + suffix) for suffix in COMMAND_KEYS):
        return "argv" if key in {"argv", "args"} or key.endswith(("_argv", "_args")) else "commands"
    return None


def identifiers(value: str, allow_cli_alias: bool = False, sentence: bool = False):
    found = [match.group(0).rstrip(".") if sentence else match.group(0) for match in MODEL.finditer(value)]
    if not found and allow_cli_alias and value in CLI_ALIASES:
        found = [value]
    return found


def command_identifiers(value: str | list[str], locate: bool = False):
    """Read POSIX command strings with CPython v3.13.16 shlex; argv stays literal."""
    text = value if isinstance(value, str) else shlex.join(value)
    if not re.search(r"(?:--model(?:-id)?|-m)(?:[=\s\"',])", text):
        return []
    if not MODEL.search(text) and not any(re.search(r"\b" + alias + r"\b", text) for alias in CLI_ALIASES):
        return []
    try:
        if isinstance(value, str):
            punctuation = "\n;&|()"
            # CPython v3.13.16 shlex.py: quote/escape state is available while
            # the lexer reads its stream. Protect literal punctuation at that
            # boundary; keep upstream tokenization and decode token values later.
            protected = {}
            for character in punctuation:
                marker = chr(0xE000 + len(protected))
                while marker in value or marker in protected.values():
                    marker = chr(ord(marker) + 1)
                protected[character] = marker
            decode = str.maketrans({marker: character for character, marker in protected.items()})
            class CommandInput(io.StringIO):
                def read(self, size=-1):
                    character = super().read(size)
                    if size == 1 and self.lexer.state in ("'", '"', "\\"):
                        return protected.get(character, character)
                    return character

                def readline(self, size=-1):
                    # shlex skips comments with readline(). Keep their newline
                    # available as a command boundary, as with uncommented lines.
                    line = super().readline(size)
                    if line.endswith("\n"):
                        self.seek(self.tell() - 1)
                        return line[:-1]
                    return line
            stream = CommandInput(value)
            lexer = shlex.shlex(stream, posix=True, punctuation_chars=punctuation)
            stream.lexer = lexer
            lexer.whitespace = " \t\r"
            lexer.whitespace_split = True
            raw_tokens = list(lexer)
            boundaries = {index for index, token in enumerate(raw_tokens)
                          if token and set(token) <= set(punctuation)}
            tokens = [token.translate(decode) for token in raw_tokens]
        else:
            tokens = value
            boundaries = set()
    except ValueError:
        raise CurrencyError("active command string could not be parsed") from None
    def native_short_flag(prefix):
        # Codex rust-v0.162.0 shared_options.rs advertises -m; Claude 2.1.296
        # advertises only --model. Resolve executable positions, never operands.
        # Wrapper grammar: uutils/coreutils 0.10.0 nice/env/timeout/nohup;
        # util-linux v2.41.3 flock.c and schedutils/ionice.c:140-157
        # (+n:c:p:P:u:tVh); existing rtk proxy and shell builtins.
        values = {
            "nice": {"-n", "--adjustment"},
            "env": {"-u", "--unset", "-C", "--chdir", "-a", "--argv0", "-f", "--file"},
            "timeout": {"-k", "--kill-after", "-s", "--signal"},
            "flock": {"-w", "--timeout", "-E", "--conflict-exit-code"},
            "ionice": {"-n", "--classdata", "-c", "--class"},
            "hcom": {"--name"},
            "exec": {"-a"},
        }
        switches = {
            "nice": set(), "nohup": set(),
            "ionice": {"-t", "--ignore"},
            "hcom": {"--go"},
            "env": {"-i", "--ignore-environment", "-v", "--debug"},
            "timeout": {"-f", "--foreground", "-p", "--preserve-status", "-v", "--verbose"},
            "flock": {"-s", "--shared", "-x", "--exclusive", "-u", "--unlock", "-n", "--nonblock",
                      "-o", "--close", "-F", "--no-fork", "--fcntl", "--verbose"},
            "rtk": {"-v", "--verbose", "--ultra-compact", "--skip-env"},
            "exec": {"-c", "-l"}, "command": {"-p"},
        }
        index = 0
        while index < len(prefix):
            if re.match(r"^[A-Za-z_]\w*=", prefix[index]):
                index += 1
                continue
            program = Path(prefix[index]).name
            index += 1
            if program == "codex":
                return True
            if program not in switches:
                return False
            while index < len(prefix) and prefix[index].startswith("-"):
                token = prefix[index]
                if token == "--" or (program == "env" and token == "-"):
                    index += 1
                    break
                if program == "ionice" and not token.startswith("--"):
                    # getopt permits clustered -t and attached -c/-n values.
                    # PID/PGID/UID targeting and help/version never exec a child.
                    offset = 1
                    while offset < len(token) and token[offset] == "t":
                        offset += 1
                    if offset == len(token) and offset > 1:
                        index += 1
                    elif offset < len(token) and token[offset] in "nc":
                        attached = offset + 1 < len(token)
                        if not attached and index + 1 >= len(prefix):
                            return False
                        index += 1 if attached else 2
                    else:
                        return False
                    continue
                option = token.split("=", 1)[0]
                if option in values.get(program, set()):
                    index += 1 if "=" in token else 2
                elif token in switches[program]:
                    index += 1
                elif any(token.startswith(short) and len(token) > len(short)
                         for short in values.get(program, set()) if len(short) == 2):
                    index += 1
                elif program == "nice" and re.fullmatch(r"-\d+", token):
                    index += 1
                elif program == "rtk" and re.fullmatch(r"-v+", token):
                    index += 1
                else:
                    return False
            if program == "hcom":
                # hcom v0.7.28 commands/launch.rs: [N] tool, then strip
                # launcher flags/operands before forwarding native tool args.
                if index < len(prefix) and prefix[index].isdigit():
                    index += 1
                if index >= len(prefix) or prefix[index] != "codex":
                    return False
                index += 1
                launch_values = {"--name", "--tag", "--terminal", "--device", "--dir",
                                 "--hcom-prompt", "--hcom-system-prompt", "--batch-id"}
                while index < len(prefix):
                    token = prefix[index]
                    if token == "--":
                        break  # hcom forwards subsequent tokens unchanged
                    if token.split("=", 1)[0] in launch_values:
                        if "=" not in token and index + 1 >= len(prefix):
                            return False  # the candidate -m is a launcher value
                        index += 1 if "=" in token else 2
                    else:
                        index += 1
                return True
            if program == "env":
                while index < len(prefix) and re.match(r"^[A-Za-z_]\w*=", prefix[index]):
                    index += 1
            elif program == "timeout":
                if index >= len(prefix) or not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)[smhd]?", prefix[index]):
                    return False
                index += 1  # duration operand
            elif program == "flock":
                index += 1  # lock pathname or descriptor operand
            elif program == "rtk" and index < len(prefix) and prefix[index] == "proxy":
                index += 1
        return False
    result = []
    start = 0
    for index, token in enumerate(tokens):
        if index in boundaries:
            start = index + 1
            continue
        flag = token.rstrip(",")
        option = flag.split("=", 1)[0]
        if option == "-m" and not native_short_flag(tokens[start:index]):
            continue
        if flag in MODEL_FLAGS and index + 1 < len(tokens):
            ids = identifiers(tokens[index + 1], "claude" in tokens)
            result.extend((index + 1, item) if locate else item for item in ids)
        elif any(flag.startswith(option + "=") for option in MODEL_FLAGS):
            ids = identifiers(flag.split("=", 1)[1], "claude" in tokens)
            result.extend((index, item) if locate else item for item in ids)
    return result


def selectors(text: str, path: Path):
    """Extract selection values, not historical prose or all supported catalog IDs."""
    cli = "/claude/" in path.as_posix() or path.name == "settings.json"
    results = []
    if path.suffix == ".json":
        try:
            document = json.loads(text)
        except ValueError:
            raise CurrencyError("active JSON configuration is invalid") from None
        dated_record_name = bool(re.search(r"(?:receipt|observation)\.json$|scheduled-\d{8}\.json$", path.name))
        if dated_record_name and isinstance(document, dict) and any(
                isinstance(value, str) and re.match(r"20\d\d-\d\d-\d\d", value)
                and re.search(r"(?:_at|date|time)(?:_utc)?$", key)
                for key, value in document.items()):
            return []
        # json.loads supplies the grammar and decoded values. Retain the lexical
        # string positions in that same traversal order, including skipped records.
        tokens = iter((json.loads(match.group()), match.start())
                      for match in re.finditer(r'"(?:[^"\\]|\\.)*"', text))
        positions = {}
        def string_position(expected):
            token = next(tokens, None)
            if token is None or token[0] != expected:
                raise CurrencyError("active JSON source locations are ambiguous")
            return token[1]
        def locate(value, pointer=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    string_position(key)
                    locate(child, (*pointer, key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    locate(child, (*pointer, index))
            elif isinstance(value, str):
                positions[pointer] = string_position(value)
        locate(document)
        if next(tokens, None) is not None:
            raise CurrencyError("active JSON source locations are ambiguous")
        def emit(pointer, identifier):
            location = "".join("/" + str(key).replace("~", "~0").replace("/", "~1") for key in pointer)
            results.append((text.count("\n", 0, positions[pointer]) + 1, identifier, location))
        def walk(value, pointer=(), command=None):
            if isinstance(value, dict):
                if measurement(value):
                    return
                if isinstance(value.get("status"), str) and value["status"] in RECORD_STATUSES:
                    return
                for key, child in value.items():
                    if key in RECORD_KEYS:
                        continue
                    if selector_key(key) and isinstance(child, (str, list)):
                        for index, item in enumerate(child if isinstance(child, list) else [child]):
                            if isinstance(item, str):
                                for identifier in identifiers(item, cli):
                                    emit((*pointer, key, index) if isinstance(child, list) else (*pointer, key), identifier)
                    elif command_key(key) and isinstance(child, (str, dict, list)):
                        walk(child, (*pointer, key), command_key(key))
                    elif isinstance(child, (dict, list)):
                        walk(child, (*pointer, key), command)
            elif isinstance(value, list):
                argv = command == "argv" or any(
                    isinstance(child, str) and child.split("=", 1)[0] in MODEL_FLAGS for child in value)
                if all(isinstance(child, str) for child in value) and argv:
                    for index, identifier in command_identifiers(value, locate=True):
                        emit((*pointer, index), identifier)
                    return
                for index, child in enumerate(value):
                    walk(child, (*pointer, index), command)
            elif command and isinstance(value, str):
                for identifier in command_identifiers(value):
                    emit(pointer, identifier)
        walk(document)
        return sorted(set(results))
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            raise CurrencyError("active Python default source is invalid") from None
        def strings(node):
            return [n for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        for node in ast.walk(tree):
            values = []
            if isinstance(node, (ast.List, ast.Tuple)):
                tokens = [item.value if isinstance(item, ast.Constant) and isinstance(item.value, str) else ""
                          for item in node.elts]
                for index, identifier in command_identifiers(tokens, locate=True):
                    results.append((node.elts[index].lineno, identifier))
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                regex_value = isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "compile"
                if any(selector_key(ast.unparse(target)) for target in targets) and node.value and not regex_value:
                    values = strings(node.value)
            elif isinstance(node, ast.keyword) and node.arg and selector_key(node.arg):
                values = strings(node.value)
            elif isinstance(node, ast.Dict):
                for key, child in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and isinstance(key.value, str) and selector_key(key.value):
                        values.extend(strings(child))
            elif isinstance(node, ast.Call):
                arguments = [n.value for n in node.args if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                if any(arg in {"--model", "--model-id", "-m"} or selector_key(arg) for arg in arguments):
                    for keyword in node.keywords:
                        if keyword.arg == "default":
                            values.extend(strings(keyword.value))
                    if len(node.args) > 1 and any(selector_key(arg) for arg in arguments[:1]):
                        values.extend(strings(node.args[1]))
            for value in values:
                for identifier in identifiers(value.value, cli):
                    results.append((value.lineno, identifier))
        return sorted(set(results))
    prose = (path.suffix == ".md" and "agents" not in path.parts
             and any(part in {"docs", "blueprints", "adoption"} for part in path.parts))
    historical_setup = prose and bool(re.search(r"setup below records.*?earlier.*?historical", text[:1500], re.S | re.I))
    record_section = False
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        code_spans = []
        outside_command = None
        if path.suffix == ".md":
            # CommonMark 0.31.2 sections 4.5/6.1: fenced content is literal;
            # inline formatting must not discard surrounding command text.
            delimiter = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
            if delimiter:
                mark, tail = delimiter.groups()
                if fence is None and (mark[0] != "`" or "`" not in tail):
                    fence = (mark[0], len(mark))
                    continue
                if fence and mark[0] == fence[0] and len(mark) >= fence[1] and not tail.strip():
                    fence = None
                    continue
            if fence is None:
                spans = r"(?<!`)(`+)(?!`)(.*?)(?<!`)\1(?!`)"
                def span_content(match):
                    content = match[2]
                    if content.startswith(" ") and content.endswith(" ") and content.strip(" "):
                        content = content[1:-1]  # CommonMark 0.31.2 section 6.1
                    return content
                code_spans = [span_content(match) for match in re.finditer(spans, line)]
                # CPython v3.13.16 shlex.quote preserves each literal span as
                # one token in the surrounding command. Never delete an
                # executable or let a span's operand suffix become a command.
                # Full command spans retain their separate parse below.
                outside_command = re.sub(spans, lambda match: shlex.quote(span_content(match)), line)
                line = re.sub(spans, lambda match: " " + span_content(match) + " ", line)
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "//", "<!--", ";")):
            if prose and stripped.startswith("#"):
                record_section = bool(re.search(r"historical|dated (?:observation|measurement|receipt)|recorded (?:probe|result)", stripped, re.I))
            continue
        if historical_setup or record_section or (prose and re.search(r"source/parser checked|failed attempt|recorded provider probe", line, re.I)):
            continue
        if not MODEL.search(line) and not (cli and any(re.search(r"\b" + alias + r"\b", line) for alias in CLI_ALIASES)):
            continue
        # Model fields/frontmatter, environment defaults and native CLI arguments.
        fields = [match for match in re.finditer(
            r"(?:^|[\s{,])([\w.-]*model(?:_id|_name)?)[\s\"']*[:=]", line, re.I)
                  if selector_key(match[1])]
        argument = re.search(r"(?:--model(?:-id)?(?:[=\s])|\b(?:codex|claude)\b.*\s-m\s)", line)
        for field in fields:
            # Only a field's first value is a selector. Its explanatory tail
            # need not be valid shell syntax, including an owner's apostrophe.
            try:
                lexer = shlex.shlex(line[field.end():], posix=True)
                lexer.whitespace_split = True
                value = lexer.get_token() or ""
            except ValueError:
                raise CurrencyError("active selector value could not be parsed") from None
            for identifier in identifiers(value, cli, sentence=prose):
                results.append((number, identifier))
        if argument:
            commands = code_spans or [line]
            if code_spans:
                commands = [*commands, outside_command]
            selected = []
            try:
                for index, command in enumerate(commands):
                    # A model flag and its value may use separate adjacent spans.
                    # Do not combine independent commands or bare client mentions.
                    if (code_spans and index + 1 < len(code_spans)
                            and re.search(r"(?:--model(?:-id)?|-m)\s*$", command)):
                        command += " " + commands[index + 1]
                    selected.extend(command_identifiers(command.rstrip().removesuffix("\\")))
            except CurrencyError:
                if prose:
                    selected = identifiers(line.split("#", 1)[0], cli, sentence=True)
                else:
                    raise CurrencyError("active selector line could not be parsed") from None
            for identifier in selected:
                results.append((number, identifier))
    return sorted(set(results))


def repo_files(root: Path):
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, timeout=30)
    if result.returncode:
        raise CurrencyError("active repository inventory could not be read")
    return sorted(set(result.stdout.decode().rstrip("\0").split("\0")))


def host_files(home: Path):
    singles = [home / ".codex/config.toml", home / ".claude/settings.json"]
    folders = [home / ".claude/agents", home / ".codex/agents", home / ".local/bin", home / ".local/share/codex-ecosystem/bin",
               home / ".local/state/native-agent-stack/coordination/command-center/cc-tools",
               home / ".local/state/native-agent-stack/coordination/ns2604-coop/tools",
               home / ".local/state/native-agent-stack/coordination/api-actions-20261008"]
    return singles + [p for folder in folders if folder.is_dir() for p in folder.iterdir() if p.is_file()]


def model_candidate(path: Path) -> bool:
    """Stream a value-free candidate test before size/UTF-8 validation.

    Keep an overlap for tokens spanning read boundaries; unrelated large or
    non-UTF-8 files do not make the model report incomplete.
    """
    overlap = b""
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            text = (overlap + chunk).decode("utf-8", errors="ignore")
            if MODEL.search(text) or ("model" in text.lower() and any(
                    re.search(r"\b" + alias + r"\b", text) for alias in CLI_ALIASES)):
                return True
            overlap = chunk[-512:]
    return False


def check(manifest: dict, roots: list[Path], host: bool = False) -> dict:
    files, excluded, errors, findings = [], 0, [], []
    home = Path.home()
    for root in roots:
        try:
            names = repo_files(root)
        except CurrencyError as error:
            errors.append(str(error)); continue
        for name in names:
            if not name:
                continue
            if exempt(name):
                excluded += 1; continue
            files.append(root / name)
    if host:
        files.extend(host_files(home))
    for path in sorted(set(files)):
        if path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        display = str(path).replace(str(home), "~")
        try:
            with path.open("rb") as stream:
                prefix = stream.read(512)
            if b"\0" in prefix:
                continue
            if not model_candidate(path):
                continue
            if path.stat().st_size > MAX_BYTES:
                errors.append(display + ": active text exceeds the check bound"); continue
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            if not MODEL.search(text) and not ("model" in text.lower() and any(re.search(r"\b" + alias + r"\b", text) for alias in CLI_ALIASES)):
                continue
            selected = selectors(text, path)
        except (OSError, UnicodeError, CurrencyError):
            errors.append(display + ": active selector source could not be checked"); continue
        for number, identifier, *locator in selected:
            if identifier in manifest.get("native_routing_aliases", []):
                continue
            target = manifest["aliases"].get(identifier)
            if identifier in CLI_ALIASES:
                target = manifest["latest"][CLI_ALIASES[identifier]]
            if target is None:
                family = model_identity(EFFORT.sub("", identifier.removesuffix("[1m]")))
                expected = manifest["latest"].get(family[0]) if family else None
                finding = {"path": display, "line": number, "model": identifier, "expected": expected}
                if locator:
                    finding["json_pointer"] = locator[0]
                findings.append(finding)
    return {"schema_version": 1, "status": "unknown" if errors else "stale" if findings else "current", "stale_count": len(findings),
            "findings": findings, "errors": errors, "coverage": {"candidate_files": len(set(files)), "record_exemptions": excluded, "host": host}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("generate")
    for source in ("codex", "omniroute", "claude"):
        build.add_argument("--" + source, required=True, type=Path)
    build.add_argument("--recorded-at", "--observed-at", dest="recorded_at", required=True,
                       help="Bundle recording label; never substituted for a source capture timestamp")
    build.add_argument("--output", required=True, type=Path)
    for command in ("check", "notice"):
        run = sub.add_parser(command)
        run.add_argument("--root", type=Path, default=ROOT)
        run.add_argument("--extra-root", type=Path, action="append", default=[])
        run.add_argument("--host", action="store_true")
        run.add_argument("--manifest", type=Path)
        run.add_argument("--now")
        run.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "notice":
        try:
            event = json.load(sys.stdin)
        except (ValueError, RecursionError):
            return 0
        if not isinstance(event, dict) or event.get("hook_event_name") != "SessionStart":
            return 0
    try:
        if args.command == "generate":
            document = generate(args.codex, args.omniroute, args.claude, args.recorded_at)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(document, indent=2) + "\n")
            print(json.dumps({"manifest": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(), "latest": document["latest"]}))
            return 0
        now = utc(args.now) if args.now else datetime.now(timezone.utc)
        manifest = load_manifest(args.manifest or args.root / MANIFEST, now)
        roots = [args.root, *args.extra_root]
        trading = Path.home() / "code/us-equities-trading"
        if args.host and trading.is_dir() and trading.resolve() not in {root.resolve() for root in roots}:
            roots.append(trading)
        report = check(manifest, roots, args.host)
        report["catalog_kind"] = manifest.get("catalog_kind", "live_observation")
    except (CurrencyError, OSError, ValueError, KeyError, TypeError) as error:
        report = {"schema_version": 1, "status": "unknown", "stale_count": 0, "findings": [], "errors": [str(error) if isinstance(error, CurrencyError) else "model currency could not complete"]}
    if args.command == "generate":
        print(json.dumps(report), file=sys.stderr)
        return 2
    if args.command == "notice":
        if report["status"] != "current":
            line = f"Model currency: {report['stale_count']} stale active selectors" if report["status"] == "stale" else "Model currency: latest-model check incomplete; refresh the native catalog and run the check."
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": line}}))
        return 0
    if args.json:
        print(json.dumps(report))
    else:
        print(f"model currency: {report['status']}; {report['stale_count']} stale active selectors")
        for item in report["findings"]:
            print(f"{item['path']}:{item['line']} {item['model']} -> {item['expected'] or 'latest declared hosted family'}")
        for error in report["errors"]:
            print(error)
    return 2 if report["status"] == "unknown" else 1 if report["status"] == "stale" else 0


if __name__ == "__main__":
    raise SystemExit(main())
