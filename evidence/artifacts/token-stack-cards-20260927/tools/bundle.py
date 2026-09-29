#!/usr/bin/env python3
"""Sanitize the 2026-09-27 token-stack cards and write their public evidence bundle.

Inputs are the private assembly outputs (cards, invoke snapshot, returned results and
GPT-6 verification receipts); nothing is fetched. Output files are deterministic for
fixed inputs. The substitution vocabulary is the one the returned-results assembly
already used ($HOME, <scratch>, $SESSION_TMP, [redacted-uuid], redacted-email,
<user>), and every output is scanned with scripts/validate.py's PRIVATE_CONTENT
patterns before it is written. A credential-shaped match stops the run instead of
being rewritten.

Usage:
  bundle.py --cards DIR --invoke FILE --returned-results FILE --verification FILE...
            --repo-root ROOT --out DIR
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

EDITION = "2026-09-27"
DROP_KEYS = {"session_id_sha", "session_id", "conversation_id", "rollout_path"}
SUMMARY_CHARS = 600


def substitutions():
    home = str(Path.home())
    user = getpass.getuser()
    rules = [
        # Session scratchpads (any dash-encoded project directory) become <scratch>.
        (re.compile(r"/tmp/claude-\d+/[^/\s\"'`]+/[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}/scratchpad"), "<scratch>"),
        (re.compile(r"/tmp/claude-\d+"), "$SESSION_TMP"),
        (re.compile(re.escape(home) + r"(?=/|\b)"), "$HOME"),
        (re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+(?=/|\b)"), "$HOME"),
        (re.compile(r"(?<![\w$.~/-])~(?=/)"), "$HOME"),
        (re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I), "[redacted-uuid]"),
        (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "redacted-email"),
    ]
    if user and len(user) > 2:
        rules.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(user) + r"(?![A-Za-z0-9])"), "<user>"))
    return rules


RULES = substitutions()


def clean_text(text: str) -> str:
    for pattern, replacement in RULES:
        text = pattern.sub(replacement, text)
    return text


def clean(value):
    if isinstance(value, dict):
        return {clean_text(key): clean(item) for key, item in value.items() if key not in DROP_KEYS}
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, str):
        return clean_text(value)
    return value


def dump(value) -> bytes:
    return (json.dumps(value, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def private_patterns(repo_root: Path):
    sys.path.insert(0, str(repo_root / "scripts"))
    import validate  # noqa: E402  (repository's own publication scanner)
    return validate.PRIVATE_CONTENT


def scan(name: str, raw: bytes, patterns) -> list[str]:
    text = raw.decode("utf-8")
    found = [f"{name}: {label}" for label, pattern in patterns if pattern.search(text)]
    for label, pattern in (("session temp path", re.compile(r"/tmp/claude-")),
                           ("e-mail address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
                           ("session id key", re.compile(r"\"session_id")),
                           ("home-relative host path", re.compile(r"(?<![\w$.~/-])~/"))):
        if pattern.search(text):
            found.append(f"{name}: {label}")
    return found


def exit_code(observation):
    parsed = observation
    if isinstance(observation, str):
        try:
            parsed = json.loads(observation)
        except ValueError:
            parsed = None
    if isinstance(parsed, dict):
        for key in ("exit", "exit_code"):
            if type(parsed.get(key)) is int:
                return parsed[key]
    text = observation if isinstance(observation, str) else ""
    match = re.search(r"\bexit(?:_code| code| status)?[\"']?\s*[=:]?\s*(-?\d+)\b", text, re.I)
    return int(match.group(1)) if match else None


def summarize(text: str) -> tuple[str, bool]:
    if len(text) <= SUMMARY_CHARS:
        return text, False
    cut = text.rfind(" ", 0, SUMMARY_CHARS)
    return text[: cut if cut > SUMMARY_CHARS // 2 else SUMMARY_CHARS].rstrip() + " [...]", True


def record_subset(record: dict, cited_by: list[str]) -> dict:
    argv = record.get("command", {}).get("argv") if isinstance(record.get("command"), dict) else None
    command = " ".join(shlex.quote(part) for part in argv) if argv else json.dumps(record.get("command"), ensure_ascii=False)
    observation = record.get("observation") or ""
    # A string observation is hashed as its UTF-8 text; an object as compact sorted JSON.
    form = "utf-8 text" if isinstance(observation, str) else "compact sorted JSON"
    text = observation if isinstance(observation, str) else json.dumps(
        observation, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    summary, omitted = summarize(text)
    body = text.encode("utf-8")
    item = {"id": record["id"], "component_ids": record.get("component_ids", []), "cited_by": cited_by,
            "runtime": record.get("runtime"), "kind": record.get("kind"), "command": command,
            "started_at": record.get("started_at"), "completed_at": record.get("completed_at"),
            "status": record.get("status"), "exit": exit_code(observation), "summary": summary,
            "observation": {"form": form, "bytes": len(body), "sha256": sha256(body),
                            "summary_truncated": omitted},
            "boundary": record.get("boundary"),
            "attachments": [{key: attachment.get(key) for key in ("label", "path", "bytes", "sha256", "mime_type")}
                            for attachment in record.get("attachments", [])]}
    if record.get("title"):
        item["title"] = record["title"]
    return clean(item)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--invoke", type=Path, required=True)
    parser.add_argument("--returned-results", type=Path, required=True)
    parser.add_argument("--verification", type=Path, action="append", default=[])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    patterns = private_patterns(args.repo_root)
    outputs: dict[str, bytes] = {}
    inputs = {}

    def source(path: Path) -> bytes:
        raw = path.read_bytes()
        inputs[clean_text(path.name)] = {"bytes": len(raw), "sha256": sha256(raw)}
        return raw

    cards = {}
    for path in sorted(args.cards.glob("*.json")):
        raw = source(path)
        value = clean(json.loads(raw))
        outputs["cards/" + path.name] = dump(value)
        if path.name != "index.json":
            cards[value["tool"]] = value

    invoke = clean(json.loads(source(args.invoke)))
    outputs["invoke-by-tool.json"] = dump(invoke)

    returned = json.loads(source(args.returned_results))
    returned_name = clean_text(args.returned_results.name)  # the key source() recorded for this input
    records = {record["id"]: record for record in returned["records"]}
    cited: dict[str, list[str]] = {}
    for tool, card in sorted(cards.items()):
        shown = [row["id"] for row in card["e2e_returned_results"]["records_shown"]]
        missing = sorted(set(shown) - set(records))
        if missing:
            raise SystemExit(f"{tool}: cited records missing from the returned results: {missing}")
        text = json.dumps(card, ensure_ascii=False)
        mentioned = [identifier for identifier in records
                     if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(identifier) + r"(?![A-Za-z0-9_-])", text)]
        for identifier in set(shown) | set(mentioned):
            cited.setdefault(identifier, []).append(tool)
    subset = [record_subset(records[identifier], sorted(tools)) for identifier, tools in sorted(cited.items())]
    outputs["returned-results-subset.json"] = dump({
        "schema_version": 1, "kind": "returned_results_cited_subset", "edition": EDITION,
        "evidence_class": "local integration (upstream commands and checks run on the source host; returned data retained)",
        "source": {"name": returned_name, "captured_at": returned.get("captured_at"),
                   **inputs[returned_name], "records": len(returned["records"])},
        "scope": clean_text(returned.get("scope", "")),
        "method": ("Every record a committed card cites (its records_shown plus any record id named in its text). "
                   "Each keeps its command, exit and a summary of at most 600 characters; the full observation "
                   "is omitted here and identified by its UTF-8 byte count and sha256, and attachment bodies by "
                   "the sha256 the source recorded."),
        "records": subset})

    reviews = []
    for tool, card in sorted(cards.items()):
        review = card["gpt6_review"]
        final = review["final_verdict"]
        runs = {name: {key: run.get(key) for key in ("model", "effort", "mcp_calls_by_server", "shell_commands",
                                                     "web_searches", "rollout_found")}
                for name, run in sorted(review.get("harness", {}).items())}
        reviews.append({"tool": tool, "card": f"cards/{tool}.json#/gpt6_review",
                        "review_verdict": review["verdict"], "final_verdict": final["verdict"],
                        "summary": final["summary"], "findings": len(review.get("findings", [])),
                        "resolutions": len(review.get("resolutions", [])),
                        "claims_verified": len(final.get("claims_verified", [])),
                        "claims_holding": sum(1 for claim in final.get("claims_verified", [])
                                              if claim.get("result") == "holds"),
                        "runs": runs})
    receipts = {}
    for path in sorted(args.verification):
        receipts[path.stem] = clean(json.loads(source(path)))
    outputs["gpt6-reviews.json"] = dump({
        "schema_version": 1, "kind": "gpt6_review_index", "edition": EDITION,
        "evidence_class": ("model review (GPT-6 astra at effort max over each card's retained sources): judgment, "
                           "not execution; findings are claims to verify, not acceptance"),
        "reviews": reviews, "verification_receipts": receipts})

    problems = [problem for name, raw in sorted(outputs.items()) for problem in scan(name, raw, patterns)]
    if problems:
        print("Sanitization scan failed:\n" + "\n".join(problems))
        return 1
    for name, raw in sorted(outputs.items()):
        target = args.out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    print(json.dumps({"written": {name: {"bytes": len(raw), "sha256": sha256(raw)}
                                  for name, raw in sorted(outputs.items())},
                      "inputs": inputs, "cited_records": len(subset)}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
