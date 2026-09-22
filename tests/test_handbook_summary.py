"""The handbook's hand-written foundation summary table must name exactly the ledger's recorded winners.

The generated per-layer section is checked by build_verdicts.py --check; this summary table is prose, so a
re-recorded ledger can leave it naming rejected alternatives (the 2026-09-22 cross-family review found five).
"""

from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HANDBOOK = ROOT / "docs/grand-catalog-handbook.md"
LEDGER = ROOT / "catalogs/landscape/foundation.json"

# component_id -> the name the summary table uses.
DISPLAY = {
    "claude-code": "Claude Code", "codex": "Codex", "affaan-m/ECC": "ECC",
    "candidate:typesafe-ai-skills": "TypeSafe", "candidate:openai-skills": "OpenAI skills",
    "worktrunk": "Worktrunk", "sandbox-runtime": "sandbox-runtime", "serena": "Serena", "qmd": "QMD",
    "markitdown": "MarkItDown", "poppler": "Poppler", "socraticode": "SocratiCode", "qdrant": "Qdrant",
    "vllm": "vLLM", "ai-memory": "ai-memory", "tavily-cli": "Tavily CLI", "agent-browser": "agent-browser",
    "openresearch": "OpenResearch", "rtk": "RTK", "headroom": "Headroom", "ccusage": "ccusage",
    "promptfoo": "promptfoo", "playwright-test": "Playwright Test", "zizmor": "zizmor", "syft": "Syft",
    "candidate:actions-attest": "GitHub attestations", "dagu": "Dagu", "systemd": "systemd",
    "fastapi": "FastAPI", "nextjs": "Next.js", "postgresql": "PostgreSQL", "restic": "Restic",
    "candidate:astral-sh-uv": "uv", "opentelemetry-collector-contrib": "OpenTelemetry Collector",
    "prometheus": "Prometheus", "loki": "Loki", "mcporter": "MCPorter", "mcp-inspector": "MCP Inspector",
    "gitleaks": "Gitleaks", "candidate:cli-cli": "gh CLI", "difftastic": "Difftastic",
}
# Names of recorded alternatives that must never appear in a winners cell.
NON_WINNERS = ("jCodeMunch", "codebase-memory", "Grafana")


def summary_rows():
    section = HANDBOOK.read_text(encoding="utf-8").split("## Foundation selection by layer", 1)[1]
    section = section.split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ") and not line.startswith("| ---")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[1:]]


def names_in(cell):
    return {name for name in list(DISPLAY.values()) + list(NON_WINNERS)
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", cell)}


class FoundationSummaryTableTests(unittest.TestCase):
    def test_every_row_names_exactly_the_recorded_winners_and_decision(self):
        layers = json.loads(LEDGER.read_text(encoding="utf-8"))["layers"]
        rows = summary_rows()
        self.assertEqual(len(rows), len(layers), "one summary row per foundation ledger layer, in ledger order")
        for layer, (label, winners_cell, _) in zip(layers, rows):
            with self.subTest(layer=layer["layer_id"], row=label):
                self.assertEqual(layer["verdict_status"], "recorded")
                expected = {DISPLAY[winner["component_id"]] for winner in layer["winners"]}
                self.assertEqual(names_in(winners_cell), expected)
                decision = re.search(r"\(([^;)]*)", winners_cell).group(1)
                self.assertEqual(decision, layer["decision"].replace("_", " "))


if __name__ == "__main__":
    unittest.main()
