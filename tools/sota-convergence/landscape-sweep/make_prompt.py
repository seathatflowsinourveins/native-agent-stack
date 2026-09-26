#!/usr/bin/env python3
"""Compose one GPT-6 prompt from the run's frozen templates (the text the Claude workers get, with the layer input
embedded because Codex runs read-only in an empty directory and cannot read the work dir).

  make_prompt.py [--work-dir DIR] discover <layer-input.json> [proposals.json|-] [followup.json]
  make_prompt.py [--work-dir DIR] fit      <layer-input.json> <proposals.json>

The templates are <work-dir>/templates.json, which build_args.py wrote with the run's date, layer count and
skills-manifest date filled in; the repository copy, whose <<DATE>> is still open, is refused. Placeholders are
filled in one pass, so text inside a value (a proposal quoting "$&" or "<<LAYER_ID>>") is never expanded again.
Work dir resolution is codex_job.py's: --work-dir, else this file's directory when staged, else $SWEEP_WORK_DIR.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codex_job import UsageError, resolve_work_dir  # noqa: E402

PLACEHOLDER = re.compile(r"<<([A-Z_]+)>>")
BUILD_PLACEHOLDERS = ("DATE", "LAYER_COUNT", "SKILLS_CHECKED_AT")
RUNTIME_PLACEHOLDERS = {
    "common": set(),
    "discover": {"LAYER_INPUT", "STARS_NOTE", "LAYER_ID"},
    "facts": {"LAYER_ID", "REQUIREMENT", "PROPOSALS"},
    "fit": {"LAYER_INPUT", "PROPOSALS", "LAYER_ID"},
    "critic": {"SUMMARY"},
    "followup": {"CRITIC_REASON", "DIRECTIONS", "ALREADY"},
}
TAIL = ("\nYou have web search; you cannot run shell commands or gh here, so use the GitHub web pages and API URLs "
        "through search/fetch.")


def fill(template: str, values: dict) -> str:
    """Replace every <<NAME>> that values names, in one pass; other placeholders stay as they are."""
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), template)


def open_build_placeholders(templates: dict) -> list[str]:
    return sorted({name for text in templates.values() for name in PLACEHOLDER.findall(text)} &
                  set(BUILD_PLACEHOLDERS))


def compose(templates: dict, role: str, layer_input: dict, proposals: str = "[]", followup: dict | None = None) -> str:
    unfilled = open_build_placeholders(templates)
    if unfilled:
        raise ValueError(f"templates still hold {unfilled}; use the copy build_args.py wrote into the work dir")
    layer_id = layer_input["layer_id"]
    if role == "discover":
        body = fill(templates["discover"], {"LAYER_INPUT": json.dumps(layer_input, indent=1), "STARS_NOTE": "",
                                            "LAYER_ID": layer_id})
        if followup:
            body += "\n" + fill(templates["followup"], {
                "CRITIC_REASON": followup["reason"], "DIRECTIONS": "; ".join(followup["search_directions"]),
                "ALREADY": ", ".join(followup.get("already", []))})
    elif role == "fit":
        body = fill(templates["fit"], {"LAYER_INPUT": json.dumps(layer_input, indent=1), "PROPOSALS": proposals,
                                       "LAYER_ID": layer_id})
    else:
        raise ValueError("role must be discover or fit")
    return templates["common"] + "\n\n" + body + TAIL


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    explicit = None
    if argv[:1] == ["--work-dir"] and len(argv) > 1:
        explicit, argv = argv[1], argv[2:]
    if len(argv) < 2 or argv[0] not in ("discover", "fit") or len(argv) > 4:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        base = resolve_work_dir(explicit)
        templates = json.loads((base / "templates.json").read_text(encoding="utf-8"))
        layer_input = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        proposals = Path(argv[2]).read_text(encoding="utf-8") if len(argv) > 2 and argv[2] != "-" else "[]"
        followup = json.loads(Path(argv[3]).read_text(encoding="utf-8")) if len(argv) > 3 else None
        print(compose(templates, argv[0], layer_input, proposals, followup))
    except (UsageError, ValueError, OSError, KeyError) as error:
        print(f"make_prompt.py: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
