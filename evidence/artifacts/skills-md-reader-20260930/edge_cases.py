#!/usr/bin/env python3
"""SKILL.md edge cases for the reader/oracle comparison, written as a corpus-shaped JSON file
{"edge:<name>": {"blob": <git blob id>, "mode": "100644", "base64": <bytes>}}.

  edge_cases.py <out.json>

The first 102 are the round-3 cases (the frontmatter forms the earlier readers were tested on); the rest are the
round-3 review's inputs (findings 2-4), line breaks other than LF and CRLF, the name rules (sanitizeMetadata and
getSkillDisplayName), bytes that are not plain UTF-8, and probes of the yaml 2.9.0 -> 2.9.1 changes (line unfolding in
plain and single-quoted scalars; alias counting)."""

import base64
import hashlib
import json
import sys

NEL, LS, PS = chr(0x85), chr(0x2028), chr(0x2029)


def md(frontmatter: str) -> str:
    return f"---\n{frontmatter}\n---\n\nBody.\n"


N = "name: find-bugs\n"
CASES = {
    # round 3: the contract's forms
    "block-sequence description": md(N + "description:\n  - Find bugs."),
    "block-mapping description": md(N + "description:\n  summary: Find bugs."),
    "block-mapping quoted key": md(N + 'description:\n  "summary": Find bugs.'),
    "flow sequence description": md(N + "description: [Find bugs.]"),
    "flow mapping description": md(N + "description: {a: b}"),
    "empty flow mapping description": md(N + "description: {}"),
    "unclosed flow description": md(N + "description: [Find bugs."),
    "next-line flow description": md(N + "description:\n  [Find bugs.]"),
    "anchored description": md(N + "description: &d Find bugs."),
    "aliased description": md("x: &d Find bugs.\n" + N + "description: *d"),
    "undefined alias description": md(N + "description: *d"),
    "alias to a sequence": md("x: &d\n  - a\n" + N + "description: *d"),
    "tagged str description": md(N + "description: !!str 123"),
    "tagged int description": md(N + "description: !!int 1"),
    "non-specific tag name": md("name: ! 123\ndescription: Find bugs."),
    "local tag description": md(N + "description: !custom Find bugs."),
    "tag on another key": md(N + "description: Find bugs.\nx: !custom y"),
    # round 3: block scalars
    "literal block": md(N + "description: |\n  Find bugs."),
    "folded strip block": md(N + "description: >-\n  Find bugs\n  in a change."),
    "literal block no content": md(N + "description: |"),
    "folded block no content": md(N + "description: >-"),
    "keep block no content": md(N + "description: |+"),
    "keep block blank lines only": md(N + "description: |+\n\n\nlicense: MIT"),
    "clip block blank lines only": md(N + "description: |\n\n\nlicense: MIT"),
    "explicit indentation block": md(N + "description: |2\n    Find bugs."),
    "block with comment header": md(N + "description: | # note\n  Find bugs."),
    "block less-indented later line": md(N + "description: |\n    Find\n  bugs."),
    "block more-indented leading blank": md(N + "description: |\n      \n  Find bugs."),
    "block holding colon text": md(N + "description: >\n  Use when: the user asks.\n  # not a comment"),
    "block header extra text": md(N + "description: |x\n  Find bugs."),
    "block on the next line": md(N + "description:\n  |\n    Find bugs."),
    # round 3: plain scalars
    "plain one-line": md(N + "description: Find bugs."),
    "plain holding colon space": md(N + "description: Use when: the user asks."),
    "plain ending colon": md(N + "description: Find bugs:"),
    "plain holding colon no space": md(N + "description: Bash(python:*) helper"),
    "plain multi-line": md(N + "description: Find bugs\n  in a change."),
    "plain multi-line with comment between": md(N + "description: Find bugs\n  # c\n  in a change."),
    "plain continuation dash": md(N + "description: Find bugs\n  - in a change."),
    "plain continuation colon": md(N + "description: Find bugs\n  in: a change."),
    "plain next line": md(N + "description:\n  Find bugs in a change."),
    "plain next line two lines": md(N + "description:\n  Find bugs\n  in a change."),
    "plain next line colon": md(N + "description:\n  Find bugs: fast."),
    "plain comment then continuation": md(N + "description: Find bugs # c\n  in a change."),
    "plain continuation comment then more": md(N + "description: Find\n  bugs # c\n  in a change."),
    "comment line before next-line scalar": md(N + "description:\n  # note\n  Find bugs\n  in a change."),
    "key-line comment before next-line scalar": md(N + "description:  # note\n  Find bugs\n  in a change."),
    "continuation starting with a quote": md(N + 'description: Use when asked to "scan",\n  "audit a skill", or more.'),
    "continuation starting with a bracket": md(N + "description: Find\n  [bugs] now."),
    "continuation starting with an ampersand": md(N + "description: Find\n  &bugs now."),
    "continuation starting with colon space": md(N + "description: Find\n  : bugs"),
    "continuation starting with question space": md(N + "description: Find\n  ? bugs"),
    "continuation starting with a tag-like bang": md(N + "description: Find\n  !bugs now."),
    "null description": md(N + "description: ~"),
    "empty description": md(N + "description:"),
    "false description": md(N + "description: false"),
    "true description": md(N + "description: true"),
    "zero description": md(N + "description: 0"),
    "number description": md(N + "description: 1.5"),
    "negative number description": md(N + "description: -1"),
    "dash-dash description": md(N + "description: --flag"),
    "question plain": md(N + "description: ?maybe"),
    "at sign description": md(N + "description: @here"),
    "percent description": md(N + "description: %x"),
    "backtick description": md(N + "description: `x`"),
    "dash space description": md(N + "description: - x"),
    # round 3: quoted scalars
    "double-quoted": md(N + 'description: "Find bugs."'),
    "double-quoted empty": md(N + 'description: ""'),
    "single-quoted empty": md(N + "description: ''"),
    "single-quoted apostrophe": md(N + "description: 'It''s bugs.'"),
    "double-quoted bad escape": md(N + 'description: "C:\\skills"'),
    "bad escape on another key": md(N + 'description: Find bugs.\nx: "C:\\skills"'),
    "double-quoted good escapes": md(N + 'description: "Tab\\there \\"q\\" \\x41\\u00e9\\U0001F600\\/"'),
    "double-quoted surrogate": md(N + 'description: "\\uD800"'),
    "double-quoted beyond max": md(N + 'description: "\\U00110000"'),
    "double-quoted short hex": md(N + 'description: "\\x4"'),
    "double-quoted multi-line": md(N + 'description: "Find bugs\n  in a change."'),
    "single-quoted multi-line": md(N + "description: 'Find bugs\n  in a change.'"),
    "text after quoted": md(N + 'description: "Find" bugs'),
    "quoted next line": md(N + 'description:\n  "Find: bugs."'),
    "quoted name with spaces": md('name: " find-bugs "\ndescription: Find bugs.'),
    # round 3: documents and keys
    "duplicate description": md(N + "description: Find bugs.\ndescription: Again."),
    "duplicate nested key": md(N + "description: Find bugs.\nmetadata:\n  a: 1\n  a: 2"),
    "quoted duplicate key": md(N + 'description: Find bugs.\n"description": Again.'),
    "root is a list": md("- name: find-bugs"),
    "root is a scalar": md("find-bugs"),
    "empty frontmatter": "---\n\n---\n\nBody.\n",
    "comment only frontmatter": md("# nothing"),
    "document end marker inside": md(N + "description: Find bugs.\n...\nx: 1"),
    "tab after colon": md(N + "description:\tFind bugs."),
    "tab indentation": md(N + "description: Find bugs.\nmetadata:\n\ta: 1"),
    "nested metadata": md(N + "description: Find bugs.\nmetadata:\n  author: x\n  tags:\n    - a\n    - b"),
    "nested plain holding colon": md(N + "description: Find bugs.\nmetadata:\n  a: b: c"),
    "nested comment at column 0": md(N + "description: Find bugs.\nmetadata:\n  a: 1\n# c\n  b: 2"),
    "nested flow sequence": md(N + "description: Find bugs.\ntags: [a, b]"),
    "nested unclosed flow": md(N + "description: Find bugs.\ntags: [a, b"),
    "nested block scalar": md(N + "description: Find bugs.\nmetadata:\n  notes: |\n    a: b: c\n    \"unclosed"),
    "internal metadata": md(N + "description: Find bugs.\nmetadata:\n  internal: true"),
    "indented first line": md("  name: find-bugs\n  description: Find bugs."),
    "complex key": md(N + "description: Find bugs.\n? x\n: y"),
    "no frontmatter": "# Find bugs\n",
    "crlf frontmatter": "---\r\nname: find-bugs\r\ndescription: Find bugs.\r\n---\r\n\r\nBody.\r\n",
    "nel inside a plain description": md(N + "description: Find" + NEL + "bugs."),
    # round-3 review, finding 2: continuations that yaml refuses
    "under-indented double-quoted continuation": md(N + 'description: "Find bugs\nin a change."'),
    "under-indented single-quoted continuation": md(N + "description: 'Find bugs\nin a change.'"),
    "flow sequence continued at column 0": md(N + "description: Find bugs.\ntags: [a,\nb]"),
    "flow mapping continued at column 0": md(N + "description: Find bugs.\ntags: {a: 1,\nb: 2}"),
    # finding 3: line breaks other than LF and CRLF
    "lone CR between keys": md("name: find-bugs\rdescription: Find bugs."),
    "NEL between keys": md("name: find-bugs" + NEL + "description: Find bugs."),
    "LS between keys": md("name: find-bugs" + LS + "description: Find bugs."),
    "PS between keys": md("name: find-bugs" + PS + "description: Find bugs."),
    "LS inside a description": md(N + "description: Find" + LS + "bugs."),
    "lone CR before the closing marker": "---\nname: find-bugs\ndescription: Find bugs.\r---\n\nBody.\n",
    "lone CR after the opening marker": "---\rname: find-bugs\ndescription: Find bugs.\n---\n\nBody.\n",
    "CR-only line endings": "---\rname: find-bugs\rdescription: Find bugs.\r---\r\rBody.\r",
    "LS in the body only": md(N + "description: Find bugs.") + "More" + LS + "text.\n",
    "lone CR in the body only": md(N + "description: Find bugs.") + "More\rtext.\n",
    # finding 4: nested structure yaml refuses
    "nested mapping under-indented key": md(N + "description: Find bugs.\nmetadata:\n  a: 1\n b: 2"),
    "flow sequence with an empty item": md(N + "description: Find bugs.\ntags: [,]"),
    "flow collection with mismatched brackets": md(N + "description: Find bugs.\ntags: {a: [b}]"),
    "nested block scalar under-indented line": md(N + "description: Find bugs.\nmetadata:\n  notes: |\n    a\n   b"),
    # the name rules: sanitizeMetadata (terminal escapes, control characters, line breaks, trim) and getSkillDisplayName
    "name of one CSI sequence": md('name: "\\e[31m"\ndescription: Find bugs.'),
    "name with a CSI sequence inside": md('name: "find-\\e[1mbugs"\ndescription: Find bugs.'),
    "name with an OSC title sequence": md('name: "\\e]0;title\\afind-bugs"\ndescription: Find bugs.'),
    "name with a C1 control": md('name: "find-bugs\\x9b"\ndescription: Find bugs.'),
    "name with BEL and backspace": md('name: "find\\a-bugs\\b"\ndescription: Find bugs.'),
    "name with a raw ESC byte": md("name: find-\x1b[1mbugs\ndescription: Find bugs."),
    "name of spaces only (quoted)": md('name: "   "\ndescription: Find bugs.'),
    "name with a line break inside": md('name: "find-\\nbugs"\ndescription: Find bugs.'),
    "name in upper case": md("name: Find-Bugs\ndescription: Find bugs."),
    "description of control characters only": md(N + 'description: "\\a\\b"'),
    # bytes and encodings
    "UTF-8 BOM before the frontmatter": "\ufeff" + md(N + "description: Find bugs."),
    "YAML directive": "---\n%YAML 1.2\n---\n" + N + "description: Find bugs.\n---\n",
    # the yaml 2.9.0 -> 2.9.1 changes (#714 line unfolding, #685/#713 alias counting)
    "plain multi-line with trailing tabs": md("name: find\t \n  bugs\ndescription: Find\t\n \tbugs\n\n  here."),
    "single-quoted multi-line with blank lines": md(N + "description: 'Find \t\n\n  \t bugs\n \n  here'"),
    "plain multi-line name": md("name: find\n  bugs\ndescription: Find bugs."),
    "alias fan-out in metadata": md(N + "description: Find bugs.\nmetadata:\n  a: &a [x, x, x, x, x, x, x, x]\n"
                                    "  b: &b [*a, *a, *a, *a, *a, *a, *a, *a]\n  c: &c [*b, *b, *b, *b, *b, *b, *b, *b]\n"
                                    "  d: [*c, *c, *c, *c, *c, *c, *c, *c]"),
    "merge key": md("base: &base\n  description: Find bugs.\n" + N + "<<: *base"),
}
BYTES = {
    "invalid UTF-8 in the description": b"---\nname: find-bugs\ndescription: Find \xff bugs.\n---\n\nBody.\n",
    "UTF-16 LE file": md(N + "description: Find bugs.").encode("utf-16"),
}


def entry(data: bytes) -> dict:
    return {"blob": hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest(), "mode": "100644",
            "base64": base64.b64encode(data).decode()}


out = {f"edge:{name}": entry(text.encode("utf-8")) for name, text in CASES.items()}
out.update({f"edge:{name}": entry(data) for name, data in BYTES.items()})
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(out, handle, sort_keys=True)
print(len(out), "cases")
