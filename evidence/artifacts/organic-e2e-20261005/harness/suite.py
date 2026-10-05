"""Task cards for the v1.1 pilot: suite-v1.json with the §6 amendments, the pilot cells of the pilot spec, and the R2
lint lexicon. The suite file itself stays in the coordination tree; this module reads it and freezes a derived copy
into the run root at stage 1."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from common import EXPERIMENT_WORDS, V1_ROOT, load_json, sha256_file

SUITE_PATH = V1_ROOT / "suite-v1.json"
SUITE_SHA_PREFIX = "cd26427ae9cd7c89"   # protocol header

# Aliases a prompt or launch string could use for an item (R2 (a)); the item's own name is always included.
ALIASES = {
    "ast-grep": ("sg", "ast grep", "astgrep"), "difftastic": ("difft",), "context-mode": ("context mode",),
    "codebase-memory": ("codebase memory", "codebase-memory-mcp"), "worktrunk": ("wt",),
    "chub": ("context-hub", "context hub"), "ai-memory": ("ai memory", "aimemory"), "jcodemunch": ("jcode munch",),
    "socraticode": ("socratic code",), "promptfoo": ("prompt foo",), "skill-creator": ("skill creator",),
    "search-first": ("search first",), "variant-analysis": ("variant analysis",), "diagnosing-bugs": ("diagnosing bugs",),
    "agentsview": ("agents view",),
}

# Generic MCP tool names that are not lint tokens (suite LINT note).
GENERIC_TOOL_NAMES = {"route", "menu", "order", "search", "get", "query", "status", "multi_get", "find", "list"}

# R2 (e) meta-phrases: wording that tells the model it is being tested or points it at tool choice.
META_PHRASES = ("which tool", "what tool", "use a tool", "use the tool", "using a tool", "without using", "mcp server",
                "slash command", "this experiment", "this test", "benchmark", "organic", "tool choice", "tool selection")

# §6 amendments that change prompt text.
G4_PRIME = "What is the ignore list in .grype.yaml set to?"
G6_PRIME = "What is the first heading of catalogs/README.md?"
WRITING_P2 = ("Draft a short section for catalogs/us-equities/README.md telling agents how to find catalog entries by "
              "search instead of reading whole files; put it in ./draft/.")
FP_CHECK_P1 = ("Code scanning flagged line 15 of ./alerts/pr723-promptfoo-gateway.cjs on PR #723 (head bf2c6f85) as an "
               "incomplete URL substring check. Is it a real problem or a false positive? Give your verdict with evidence.")
FP_CHECK_P2 = ("Code scanning flagged line 225 of ./alerts/pr736-drill_local_recovery.py on PR #736 (commit d109af7a) for "
               "logging a password in clear text. Is the finding real? Give your verdict with evidence.")

# Pilot cells (pilot spec, stage 4). Each entry: (item_id, instance, sandbox).
C1_TASKS = (
    ("mcp_server/both/jcodemunch", "P1", "read-only"),
    ("mcp_server/both/headroom", "P2", "read-only"),
    ("mcp_server/both/semble", "P1", "read-only"),
    ("mcp_server/both/socraticode", "P1", "read-only"),
    ("mcp_server/both/context-mode", "P1", "workspace-write"),
    ("skill/both/search-first", "P1", "read-only"),
    ("skill/codex/skill-creator", "P1", "workspace-write"),
    ("skill/both/variant-analysis", "P1", "read-only"),
    ("skill/both/diagnosing-bugs", "P1", "read-only"),
    ("cli/both/ast-grep", "P1", "read-only"),
    ("control/both/NM1", "N", "read-only"),
    ("control/both/G1", "N", "read-only"),
)
_C1 = {(item, inst): sb for item, inst, sb in C1_TASKS}
C2_TASKS = tuple((i, n, _C1[(i, n)]) for i, n in (
    ("mcp_server/both/jcodemunch", "P1"), ("mcp_server/both/headroom", "P2"), ("mcp_server/both/socraticode", "P1"),
    ("mcp_server/both/context-mode", "P1"), ("skill/both/search-first", "P1"), ("control/both/G1", "N")))
SDK_TASKS = (("mcp_server/both/jcodemunch", "P1", "read-only"), ("control/both/G1", "N", "read-only"))
A1_TASKS = (
    ("control/both/G1", "N", "n/a"), ("mcp_server/both/serena", "P1", "n/a"), ("mcp_server/both/jcodemunch", "P1", "n/a"),
    ("mcp_server/both/codebase-memory", "P1", "n/a"), ("mcp_server/both/headroom", "P2", "n/a"),
    ("mcp_server/both/semble", "P1", "n/a"), ("mcp_server/both/context-mode", "P1", "n/a"),
    ("skill/both/search-first", "P1", "n/a"), ("skill/claude/skill-creator", "P1", "n/a"),
    ("cli/both/ast-grep", "P1", "n/a"), ("control/both/NM1", "N", "n/a"),
)
A2_TASKS = (("skill/both/search-first", "P1", "n/a"),)
A3_TASKS = (("mcp_server/both/jcodemunch", "P1", "n/a"), ("control/both/G1", "N", "n/a"))

# Cells. client: claude|codex; arm: native|env; kind: the launcher (cli, sdk, app-server).
CELLS = {
    "codex-native": {"client": "codex", "arm": "native", "kind": "cli", "cl": "CL3", "effort": "max", "tasks": C1_TASKS,
                     "repeat": 3, "j": 3, "pilot_block": "C1"},
    "codex-env": {"client": "codex", "arm": "env", "kind": "cli", "cl": "CL3", "effort": "max", "tasks": C2_TASKS,
                  "repeat": 1, "j": 3, "pilot_block": "C2"},
    "codex-native-ultra": {"client": "codex", "arm": "native", "kind": "cli", "cl": "CL4", "effort": "ultra",
                           "tasks": SDK_TASKS, "repeat": 1, "j": 2, "pilot_block": "C3"},
    "codex-sdk": {"client": "codex", "arm": "native", "kind": "sdk", "cl": "CL7", "effort": "max", "tasks": SDK_TASKS,
                  "repeat": 1, "j": 2, "pilot_block": "C4"},
    "codex-app-server": {"client": "codex", "arm": "native", "kind": "app-server", "cl": "CL7b", "effort": "max",
                         "tasks": SDK_TASKS, "repeat": 1, "j": 1, "pilot_block": "C5"},
    "claude-native": {"client": "claude", "arm": "native", "kind": "cli", "cl": "CL2", "effort": "max", "tasks": A1_TASKS,
                      "repeat": 1, "j": 1, "pilot_block": "A1"},
    "claude-env": {"client": "claude", "arm": "env", "kind": "cli", "cl": "CL2", "effort": "max", "tasks": A2_TASKS,
                   "repeat": 1, "j": 1, "pilot_block": "A2"},
    "claude-sdk": {"client": "claude", "arm": "native", "kind": "sdk", "cl": "CL6", "effort": "max", "tasks": A3_TASKS,
                   "repeat": 1, "j": 1, "pilot_block": "A3"},
}
UNAVAILABLE_CELLS = {"CL5": "interactive arms: trust is the user's call (needs_user)",
                     "CL8": "OpenHands: WIRING until the wiring check passes (slots.json:241)"}

_ANNOTATION = re.compile(r"\s*\((?:NM\d+|G\d+'?(?::[^)]*)?|= [^)]+|near-miss[^)]*|documented exception[^)]*|"
                         r"A rewrite[^)]*)\)\s*$")


def item_name(item_id: str) -> str:
    return item_id.rsplit("/", 1)[-1]


def clean_prompt(text: str) -> str:
    """A negative task's trailing annotation, such as (NM1) or (= serena.P1), is suite metadata, never prompt text."""
    return _ANNOTATION.sub("", text or "").strip()


def load_suite(path: Path = SUITE_PATH) -> dict:
    suite = load_json(path)
    digest = sha256_file(path)
    return {"path": str(path), "sha256": digest, "sha_matches_protocol": digest.startswith(SUITE_SHA_PREFIX),
            "items": suite["items"], "raw": suite}


def amend(items: list[dict]) -> tuple[list[dict], list[str]]:
    """Apply the §6 prompt amendments; return the amended items and a log of what changed."""
    items, log = copy.deepcopy(items), []
    by_id = {item["item_id"]: item for item in items}

    def set_neg(item_id, text, note):
        if item_id in by_id:
            by_id[item_id]["negative_task"] = text
            log.append(note)

    set_neg("control/both/G4", G4_PRIME, "G4 -> G4'")
    set_neg("control/both/G6", G6_PRIME, "G6 -> G6'")
    for item_id in ("skill/both/iterative-retrieval", "hook/claude/context-mode", "hook/codex/context-mode"):
        set_neg(item_id, G4_PRIME + " (G4')", f"{item_id} N -> G4'")
    if "skill/both/writing-for-agents" in by_id:
        tasks = by_id["skill/both/writing-for-agents"].get("positive_tasks") or []
        if len(tasks) > 1:
            tasks[1] = WRITING_P2
            log.append("writing-for-agents P2 reworded")
    if "skill/both/fp-check" in by_id:
        tasks = by_id["skill/both/fp-check"].get("positive_tasks") or []
        if len(tasks) > 1:
            tasks[0], tasks[1] = FP_CHECK_P1, FP_CHECK_P2
            log.append("fp-check P1/P2 name ./alerts/ files")
    set_neg("skill/both/variant-analysis", FP_CHECK_P1 + " (= fp-check.P1)", "variant-analysis N = fp-check.P1 (./alerts/)")
    return items, log


def prompt_for(items_by_id: dict, item_id: str, instance: str) -> str:
    item = items_by_id[item_id]
    if instance == "N":
        return clean_prompt(item.get("negative_task") or "")
    index = int(instance[1:]) - 1
    return (item.get("positive_tasks") or [])[index]


def task_key(item_id: str, instance: str) -> str:
    return f"{item_name(item_id)}.{instance}" if instance != "N" or not item_id.startswith("control/") else item_name(item_id)


def pilot_tasks(items: list[dict]) -> list[dict]:
    """Every (item, instance) a pilot cell uses, with its frozen prompt and hash."""
    by_id = {item["item_id"]: item for item in items}
    seen, out = set(), []
    for cell in CELLS.values():
        for item_id, instance, _ in cell["tasks"]:
            if (item_id, instance) in seen:
                continue
            seen.add((item_id, instance))
            prompt = prompt_for(by_id, item_id, instance)
            out.append({"task_id": item_id, "instance": instance, "key": task_key(item_id, instance),
                        "item": item_name(item_id), "kind": by_id[item_id]["kind"], "prompt": prompt,
                        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        "source": by_id[item_id].get("source"), "expected_signal": by_id[item_id].get("expected_signal")})
    return out


def lexicon(items: list[dict], tool_functions=()) -> dict:
    """R2 lexicon: (a) item names and aliases, (b) tool function names, plus the fixed experiment words for (f)."""
    names = set()
    for item in items:
        name = item_name(item["item_id"]).lower()
        if item["kind"] == "control":
            continue
        names.add(name)
        for alias in ALIASES.get(name, ()):
            names.add(alias.lower())
    functions = sorted({f.lower() for f in tool_functions if f and f.lower() not in GENERIC_TOOL_NAMES})
    return {"names": sorted(names), "tool_functions": functions, "experiment_words": sorted(EXPERIMENT_WORDS),
            "meta_phrases": list(META_PHRASES), "skill_names": [], "task_words": []}


def _word_hit(text: str, token: str) -> bool:
    token = token.strip().lower()
    if not token:
        return False
    if re.fullmatch(r"[a-z0-9]+", token):
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None
    return token in text


def lint_text(text: str, lex: dict, descriptions: dict | None = None, *, launch_string: bool = False) -> list[dict]:
    """R2 checks over one string. launch_string=True applies (f) (experiment, client, arm and task words) too."""
    low = (text or "").lower()
    hits = []
    for name in lex["names"]:
        if _word_hit(low, name):
            hits.append({"check": "a", "token": name})
    for function in lex["tool_functions"]:
        if _word_hit(low, function):
            hits.append({"check": "b", "token": function})
    slash_names = {n.replace(" ", "-") for n in lex["names"]} | {s.lower() for s in lex.get("skill_names", [])}
    for match in re.finditer(r"(?<![\w/.~-])([$/])([a-z][a-z0-9_:-]{1,})", low):
        if match.group(1) == "$" or match.group(2) in slash_names:
            hits.append({"check": "c", "token": match.group(0)})
    if descriptions:
        words = re.findall(r"[a-z0-9']+", low)
        grams = {" ".join(words[i:i + 5]) for i in range(max(0, len(words) - 4))}
        for owner, description in descriptions.items():
            dwords = re.findall(r"[a-z0-9']+", (description or "").lower())
            dgrams = {" ".join(dwords[i:i + 5]) for i in range(max(0, len(dwords) - 4))}
            common = grams & dgrams
            if common:
                hits.append({"check": "d", "token": owner, "ngrams": sorted(common)[:3]})
    for phrase in lex["meta_phrases"]:
        if phrase in low:
            hits.append({"check": "e", "token": phrase})
    if launch_string:
        for word in lex["experiment_words"] + lex.get("task_words", []):
            if _word_hit(low, word):
                hits.append({"check": "f", "token": word})
    return hits


def skill_descriptions(roots) -> dict:
    """name -> frontmatter description of every SKILL.md under the given skill roots (R2 (d))."""
    out = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in sorted(root.glob("**/SKILL.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
            if not match:
                continue
            front = match.group(1)
            name = re.search(r"^name:\s*(.+)$", front, re.M)
            desc = re.search(r"^description:\s*(.+?)(?:\n[a-zA-Z_-]+:|\Z)", front, re.M | re.S)
            if desc:
                out[(name.group(1).strip().strip("'\"") if name else path.parent.name)] = desc.group(1).strip()
    return out
