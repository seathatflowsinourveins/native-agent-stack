"""Frozen output-contract checker; sources are native get_research_sources data.

This does not fetch missing citations or trust visited_urls/search snippets.
Oracle sources and required statements are frozen in task.json.
"""
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, urlunsplit

TASK = json.loads(Path(__file__).with_name("task.json").read_text())
URL = re.compile(r"(?:https?://|mcp://|qmd://)[^\s<>\[\]`\"\)]+")


def canonical(url):
    try:
        parts = urlsplit(url.rstrip(".,;:!"))
        if parts.scheme != "https" or parts.hostname not in TASK["allowed_domains"]:
            return None
        if parts.username or parts.password or parts.port not in (None, 443):
            return None
    except ValueError:
        return None
    return urlunsplit(("https", parts.hostname, parts.path or "/", parts.query, ""))


def check(result):
    if not isinstance(result, dict):
        result = {}
    report = result.get("report", "")
    if not isinstance(report, str):
        report = ""
    failures = []
    if not report.strip():
        failures.append("empty_report")
    # This is an explicit output contract, not a synthetic semantic grader.
    bullets = [re.sub(r"[*`]", "", line).strip() for line in report.splitlines()
               if re.match(r"^\s*[-*]\s+", line)]
    for i, fact in enumerate(TASK["required_statements"], 1):
        if not any(re.fullmatch(r"-?\s*" + re.escape(fact) + r"(?:\s+\[[^\n]+)?", line)
                   for line in bullets):
            failures.append("missing_fact_" + str(i))
    fetched = set()
    sources = result.get("sources", [])
    if not isinstance(sources, list):
        sources = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        # DuckDuckGo snippets are at most 100 chars at this upstream pin;
        # raw_content is the native scraper field, never visited_urls alone.
        content = source.get("raw_content", "")
        url = canonical(str(source.get("url", "")))
        if url and isinstance(content, str) and len(content.strip()) >= 200:
            fetched.add(url)
    cited = set()
    for raw in URL.findall(report):
        url = canonical(raw)
        if url is None:
            failures.append("citation_outside_allowed_domains")
        else:
            cited.add(url)
            if url not in fetched:
                failures.append("unfetched_citation")
    if len(cited) < TASK["min_distinct_urls"]:
        failures.append("too_few_distinct_citations")
    return {"passed": not failures, "failures": sorted(set(failures)),
            "distinct_citations": len(cited), "fetched_cited_urls": sorted(cited & fetched)}


def main():
    try:
        result = json.loads(Path(sys.argv[1]).read_text())
        verdict = check(result)
    except (OSError, ValueError, IndexError):
        verdict = {"passed": False, "failures": ["invalid_result"], "distinct_citations": 0,
                   "fetched_cited_urls": []}
    print(json.dumps(verdict, sort_keys=True))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
