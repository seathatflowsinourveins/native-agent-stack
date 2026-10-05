#!/usr/bin/env python3
"""Derive, from rtk's own source at a pinned tag, the set of command heads rtk's hook can rewrite (rtk-rewrite-heads.json beside this file).

This is review evidence, not a gate: tools/adoption/codex_hook_trust.py parses no rule file and reads no heads (three reads found a bypass in every analysing
version). The file supports the entry of tools/adoption/exec_rules_reviewed.json, the review of #713's hcom-deny.rules (neither `hcom` nor `uvx` is a head),
and a pin move of rtk must re-derive it and re-review that entry.

    python3 derive_rtk_rewrite_heads.py --source <rtk clone> [--tag v0.51.0] --write rtk-rewrite-heads.json
    python3 derive_rtk_rewrite_heads.py --source <rtk clone> --check rtk-rewrite-heads.json

Why: `rtk hook codex` replaces a Bash call with its rewrite before Codex matches execution rules on the command words, so a rule whose
prefix can be rewritten out of it is no longer matched (docs/decisions/2026-10-04-codex-rtk-hook-qualified.md). rtk's rewrite is decided by
src/discover/registry.rs (classify_command and rewrite_segment: env prefixes, git and other global options, absolute paths and the process and
shell wrappers are peeled off, then a RULES pattern must match) and src/discover/rules.rs (the RULES table, one anchored regex per tool). Every
RULES pattern and filter pattern is `^`-anchored, so a rewrite only ever replaces the program at the start of a segment (after the peeled prefixes, which the rewrite
keeps in front of `rtk`). A rule whose first token is not one of the heads below therefore cannot have a command it matches rewritten out of it.

The heads are: the leading token(s) of every RULES pattern and of every builtin TOML filter's match_command (for a pattern that starts with an optional
wrapper group, both the wrapper's tokens and the tool's, found by walking the parsed regex, not by reading it), the names in PROCESS_WRAPPERS, SHELL_KEYWORD_PREFIXES and ROUTABLE_WRAPPER_PREFIXES,
`env` and a NAME=value token (ENV_PREFIX). A head that the pattern ends with `\\b` also accepts any continuation (`^gcc\\b` matches the word `gcc-13`, and the shell's reading of the raw
`gcc\\x`). A path-qualified head is reduced to its basename (rtk strips absolute paths, and ./ and vendor/bin/
forms, before matching). rtk's user-configured `[hooks].transparent_prefixes` are not in the file: the review reads them from `rtk config`.
The file is valid for the one rtk version it names; a pin move must re-derive it and re-review the reviewed list
(tests/test_codex_hook_trust.py compares the entries of tools/adoption/exec_rules_reviewed.json with adoption/pins-linux-x86_64.json).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import re._constants as sc
import re._parser as sre_parse
import subprocess
import sys
import tomllib
from pathlib import Path

LIMIT = 20000
SCHEMA = "rtk-rewrite-heads/1"


def show(repo: Path, tag: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"{tag}:{path}"], capture_output=True, text=True, check=True).stdout


def rule_patterns(rules_rs: str) -> list[tuple[int, str]]:
    """The RULES patterns with their line numbers (every real one is a raw string, r"..." or r#"..."#; the DEFAULT constant's is not)."""
    found = []
    for number, line in enumerate(rules_rs.splitlines(), 1):
        match = re.match(r'\s*pattern:\s*r(#*)"(.*)"\1,\s*$', line)
        if match:
            found.append((number, match.group(2)))
    return found


def toml_filter_patterns(repo: Path, tag: str) -> list[tuple[str, int, str]]:
    """The match_command of every builtin TOML filter (src/filters/*.toml, which build.rs concatenates into BUILTIN_TOML): (file, line, regex).
    rtk's hook also rewrites a command that one of them matches (registry.rs rewrite_segment_inner, `command_matches_filter`)."""
    names = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "--name-only", tag, "src/filters"], capture_output=True, text=True,
                           check=True).stdout.split()
    found = []
    for name in sorted(n for n in names if n.endswith(".toml")):
        text = show(repo, tag, name)
        parsed = tomllib.loads(text)
        lines = text.splitlines()
        for filter_name, definition in sorted((parsed.get("filters") or {}).items()):
            if "match_command" in definition:
                line = next((i for i, row in enumerate(lines, 1) if row.lstrip().startswith("match_command")), 0)
                found.append((name, line, definition["match_command"]))
    return found


CATEGORY_TEXT = {sc.CATEGORY_SPACE: r"\s", sc.CATEGORY_NOT_SPACE: r"\S", sc.CATEGORY_DIGIT: r"\d", sc.CATEGORY_NOT_DIGIT: r"\D",
                 sc.CATEGORY_WORD: r"\w", sc.CATEGORY_NOT_WORD: r"\W"}
TERMINATORS = set(";|&()<>")


def class_text(items) -> tuple[str, str | None]:
    """A parsed character class as regex text and its kind: 'ws' for the bare \\s, 'term' for a class of only the terminator
    punctuation `;|&()<>` (a token ends there), 'space' for a class that can also match whitespace (a token may end there), else None."""
    if len(items) == 1 and items[0][0] == sc.CATEGORY and items[0][1] == sc.CATEGORY_SPACE:
        return r"\s", "ws"
    body = ""
    negate = False
    spaces = False
    for op, value in items:
        if op == sc.NEGATE:
            negate = True
        elif op == sc.LITERAL:
            body += re.escape(chr(value))
        elif op == sc.RANGE:
            body += re.escape(chr(value[0])) + "-" + re.escape(chr(value[1]))
        elif op == sc.CATEGORY:
            body += CATEGORY_TEXT[value]
            spaces = spaces or value == sc.CATEGORY_SPACE
        else:
            raise ValueError(f"class item {op}")
    text = "[" + ("^" if negate else "") + body + "]"
    literals = [chr(value) for op, value in items if op == sc.LITERAL]
    if not negate and len(literals) == len(items) and set(literals) <= TERMINATORS:
        return text, "term"
    return text, "space" if spaces and not negate else None


def linearize(nodes) -> list[list[tuple[str, str]]]:
    """Every way a parsed regex can unfold into a sequence of atoms (alternations and optional groups forked), as (kind, text) pairs:
    char (regex text), ws, boundary ($ or a terminator class), wordb (\\b), start (^)."""
    results: list[list[tuple[str, str]]] = [[]]
    for op, value in nodes:
        results = [done + tail for done in results for tail in expand(op, value)]
        if len(results) > LIMIT:
            raise ValueError("too many linearizations")
    return results


def expand(op, value) -> list[list[tuple[str, str]]]:
    if op == sc.LITERAL:
        return [[("char", re.escape(chr(value)))]]
    if op == sc.NOT_LITERAL:
        return [[("char", "[^" + re.escape(chr(value)) + "]")]]
    if op == sc.ANY:
        return [[("char", ".")]]
    if op == sc.AT:
        if value == sc.AT_BEGINNING:
            return [[("start", "")]]
        if value == sc.AT_BOUNDARY:
            return [[("wordb", "")]]
        if value == sc.AT_END:
            return [[("boundary", "")]]
        raise ValueError(f"anchor {value}")
    if op == sc.IN:
        text, kind = class_text(value)
        if kind == "ws":
            return [[("ws", "")]]
        if kind == "term":
            return [[("boundary", "")]]
        if kind == "space":
            return [[("ws", "")], [("char", text)]]
        return [[("char", text)]]
    if op == sc.SUBPATTERN:
        return linearize(value[3])
    if op == sc.BRANCH:
        return [tail for alternative in value[1] for tail in linearize(alternative)]
    if op in (sc.MAX_REPEAT, sc.MIN_REPEAT):
        low, high, body = value
        alternatives = [[]] if low == 0 else []
        for tail in linearize(body):
            if high > 1 and len(tail) == 1 and tail[0][0] == "char":
                quantifier = "*" if (low, high) == (0, sc.MAXREPEAT) else "+" if (low, high) == (1, sc.MAXREPEAT) else "{%d,%d}" % (low, high)
                alternatives.append([("char", tail[0][1] + quantifier)])
            else:
                alternatives.append(tail)
        return alternatives
    raise ValueError(f"regex node {op}")


def leading_tokens(pattern: str) -> set[str]:
    """The first whitespace-delimited token of every string the pattern can match, as regex text, reduced to the basename."""
    tokens = set()
    for atoms in linearize(list(sre_parse.parse(pattern))):
        token, word_boundary = "", False
        for kind, text in atoms:
            if kind == "start":
                continue
            if kind == "wordb":
                word_boundary = True
                break
            if kind in ("ws", "boundary"):
                break
            token += text
        token = token.rsplit("/", 1)[-1]
        if token and word_boundary:
            # `\b` ends the head at a word boundary, not at whitespace: `^gcc\b` also matches the word `gcc-13` or `gcc.x`, and a shell reads a backslash
            # inside a word away (rtk sees the raw `ty\pe`, a rule sees `type`), so any continuation counts.
            token += r"\S*"
        if token:
            tokens.add(token)
    return tokens


def plain(token: str) -> str | None:
    """The literal text of a token regex that is only a literal (escaped dots and dashes allowed), else None."""
    if re.fullmatch(r"(?:[A-Za-z0-9_]|\\[.\-_])+", token):
        return re.sub(r"\\(.)", r"\1", token)
    return None


def const_block(source: str, name: str) -> tuple[int, list[str]]:
    """The line of `const NAME` and the lines up to the closing `];`."""
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf"\s*(?:pub\s+)?const {name}\b", line))
    end = next(i for i in range(start, len(lines)) if lines[i].strip().endswith("];") or lines[i].strip() == "];")
    return start + 1, lines[start:end + 1]


def derive(repo: Path, tag: str) -> dict:
    rules_rs = show(repo, tag, "src/discover/rules.rs")
    registry_rs = show(repo, tag, "src/discover/registry.rs")
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", f"{tag}^{{commit}}"], capture_output=True, text=True, check=True).stdout.strip()
    heads: dict[str, dict] = {}

    def add(token: str, source: str) -> None:
        literal = plain(token)
        key = literal if literal is not None else token
        entry = heads.setdefault(key, {"head": key, "regex": literal is None, "from": []})
        if source not in entry["from"]:
            entry["from"].append(source)

    patterns = rule_patterns(rules_rs)
    for number, pattern in patterns:
        for token in sorted(leading_tokens(pattern)):
            add(token, f"src/discover/rules.rs:L{number}")
    filters = toml_filter_patterns(repo, tag)
    for name, number, pattern in filters:
        for token in sorted(leading_tokens(pattern)):
            add(token, f"{name}:L{number}")
    line, block = const_block(registry_rs, "PROCESS_WRAPPERS")
    for offset, text in enumerate(block):
        match = re.match(r'\s*name:\s*"([^"]+)"', text)
        if match:
            add(re.escape(match.group(1)), f"src/discover/registry.rs:L{line + offset} PROCESS_WRAPPERS")
    for name in ("SHELL_KEYWORD_PREFIXES", "ROUTABLE_WRAPPER_PREFIXES"):
        line, block = const_block(registry_rs, name)
        for offset, text in enumerate(block):
            for word in re.findall(r'"([^"]+)"', text):
                add(re.escape(word.split()[0]), f"src/discover/registry.rs:L{line + offset} {name}")
    php = re.search(r"const PHP_TOOL_NAMES: \[&str; \d+\] = \[(.*?)\];", registry_rs)
    php_line = registry_rs[:php.start()].count("\n") + 1
    php_names = re.findall(r'"([^"]+)"', php.group(1))
    env_line = next(i for i, text in enumerate(registry_rs.splitlines(), 1) if "static ENV_PREFIX" in text)
    add("env", f"src/discover/registry.rs:L{env_line} ENV_PREFIX")
    add(r"[A-Z_][A-Z0-9_]*=.*", f"src/discover/registry.rs:L{env_line} ENV_PREFIX")
    version = subprocess.run(["git", "-C", str(repo), "show", f"{tag}:Cargo.toml"], capture_output=True, text=True, check=True).stdout
    number = re.search(r'^version\s*=\s*"([^"]+)"', version, re.M).group(1)
    return {
        "schema": SCHEMA,
        "rtk_version_output": f"rtk {number}",
        "source": {"repository": "rtk-ai/rtk", "tag": tag, "commit": commit,
                   "blobs_sha256": {"src/discover/rules.rs": hashlib.sha256(rules_rs.encode()).hexdigest(),
                                    "src/discover/registry.rs": hashlib.sha256(registry_rs.encode()).hexdigest()},
                   "rules_patterns": len(patterns), "toml_filters": len(filters),
                   "filters_tree_sha256": hashlib.sha256(subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", tag, "src/filters"], capture_output=True,
                                                                         text=True, check=True).stdout.encode()).hexdigest()},
        "rule": "A rule's first pattern token (every alternative, reduced to its basename) that fullmatches a head can be rewritten out of the rule's reach.",
        "not_in_file": "[hooks].transparent_prefixes of the host's rtk config: the review reads them from `rtk config`.",
        "php_tool_names": {"names": php_names, "from": f"src/discover/registry.rs:L{php_line} PHP_TOOL_NAMES",
                           "rule": "rtk normalizes a PHP tool word before it matches (normalize_php_tool_path, L364-L430: backslashes become slashes, a leading ./ goes, a "
                                   ".bat, .cmd, .exe or .ps1 extension goes), and a shell removes the backslashes of the raw word, so a rule token that ends with one of "
                                   "these names (after the same extension strip) is a head too."},
        "heads": sorted(heads.values(), key=lambda entry: (entry["regex"], entry["head"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="a clone of rtk-ai/rtk that has the tag")
    parser.add_argument("--tag", default="v0.51.0")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", metavar="FILE")
    mode.add_argument("--check", metavar="FILE")
    mode.add_argument("--list", action="store_true", help="print each RULES pattern with its leading tokens")
    args = parser.parse_args()
    repo = Path(args.source).expanduser()
    if args.list:
        for number, pattern in rule_patterns(show(repo, args.tag, "src/discover/rules.rs")):
            print(f"rules.rs L{number}: {sorted(leading_tokens(pattern))}   <- {pattern[:90]}")
        for name, number, pattern in toml_filter_patterns(repo, args.tag):
            print(f"{name} L{number}: {sorted(leading_tokens(pattern))}   <- {pattern[:90]}")
        return 0
    derived = derive(repo, args.tag)
    text = json.dumps(derived, indent=2, ensure_ascii=False) + "\n"
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8")
        print(f"wrote {args.write}: {len(derived['heads'])} heads from {derived['source']['rules_patterns']} patterns")
        return 0
    current = Path(args.check).read_text(encoding="utf-8")
    print("fixture matches the derivation" if current == text else "fixture differs from the derivation")
    return 0 if current == text else 1


if __name__ == "__main__":
    sys.exit(main())
