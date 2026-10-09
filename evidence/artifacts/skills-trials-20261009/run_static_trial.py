#!/usr/bin/env python3
"""Retain native static reports without grading; never use views as a judge packet.

Schemas: agent-sh/agnix@2c0e4efede3181599eca37619e8067ae2d941c00,
crates/agnix-cli/src/json.rs; NVIDIA/SkillEvaluator@
7304d76cde371287b67ea99653409d014b6b9c85,
src/skillevaluator/reporting/json_reporter.py. Parent must anonymize arm mapping.
"""

import argparse
import hashlib
import json
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PREREG_SHA = "6fc7045aed40d6a0d82ebc1234d2566f6ac51d0c3da7a946676eb92c0286836b"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def neutral(text, paths, rule=None):
    for path in sorted(paths, key=len, reverse=True):
        text = text.replace(path, "[path]")
    if rule:
        text = text.replace(rule, "[check]")
    text = re.sub(r"\b(?:agnix|skillevaluator|nvidia|openai|anthropics?|quick_validate)\b",
                  "validator", text, flags=re.I)
    return re.sub(r"\b[A-Z][A-Z0-9]*-\d{3,}\b", "[check]", text)


def finding(item, severity_key, paths, rule_key=None):
    severity, message = item[severity_key], item["message"]
    if not isinstance(severity, str) or not isinstance(message, str) or not message:
        raise ValueError("finding must contain severity and nonempty message strings")
    result = {"severity": severity, "message": neutral(message, paths, item.get(rule_key))}
    for field in ("suggestion", "assumption"):
        if item.get(field) is not None:
            if not isinstance(item[field], str):
                raise ValueError(f"finding {field} must be a string or null")
            result[field] = neutral(item[field], paths, item.get(rule_key))
    return result


def extract(tool, record, directory, paths):
    """Only parse structures established by the pinned native sources."""
    rc = record["rc"]
    stdout = (directory / "stdout.txt").read_text(errors="replace")
    stderr = (directory / "stderr.txt").read_text(errors="replace")
    if record["execution_error"] or rc not in (0, 1):
        return "tool_error", [], record["execution_error"] or f"unexpected exit code {rc}"
    if tool == "agnix":
        data = json.loads(stdout)
        if not isinstance(data, dict) or not isinstance(data.get("diagnostics"), list):
            raise ValueError("expected documented diagnostics array")
        if not isinstance(data.get("files_checked"), int) or data["files_checked"] < 1:
            return "incomplete", [], "no recognized files checked"
        items = [finding(d, "level", paths, "rule") for d in data["diagnostics"]]
        if rc == 1 and not items:
            return "incomplete", [], "nonzero exit without diagnostics"
        return "complete", items, None
    if tool == "skillevaluator":
        reports = list((directory / "reports").glob("*.json"))
        if len(reports) != 1:
            raise ValueError(f"expected one native JSON report, found {len(reports)}")
        data = json.loads(reports[0].read_text())
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("expected documented results array")
        if not data["results"] or data.get("overall_status") not in ("passed", "failed", "incomplete"):
            raise ValueError("missing native overall status or validators")
        incomplete = bool(data.get("incomplete_scans")) or data["overall_status"] == "incomplete"
        items = []
        record["native_validators"] = []
        for result in data["results"]:
            if not isinstance(result.get("findings"), list):
                raise ValueError("expected documented validator findings array")
            status = result.get("status")
            record["native_validators"].append({"validator": result.get("validator"), "status": status})
            incomplete |= bool(result.get("incomplete_scans")) or status not in ("passed", "failed")
            items.extend(finding(f, "severity", paths, "check_name") for f in result["findings"])
            # Native legacy errors/warnings can exist independently of structured findings.
            legacy = result.get("legacy", {})
            for field, severity in (("errors", "error"), ("warnings", "warning")):
                messages = legacy.get(field, [])
                if not isinstance(messages, list):
                    raise ValueError("invalid legacy finding array")
                for message in messages:
                    view = finding({"severity": severity, "message": message}, "severity", paths)
                    if not any(item["message"] == view["message"] for item in items):
                        items.append(view)
        return ("incomplete" if incomplete else "complete"), items, ("native report incomplete" if incomplete else None)
    # Both unmodified reference scripts print one verdict and exit 0/1.
    if stderr.strip() or not stdout.strip() or (rc == 0 and stdout.strip() != "Skill is valid!"):
        return "tool_error", [], "reference output does not match native verdict contract"
    items = [] if rc == 0 else [{"severity": "error", "message": neutral(stdout.strip(), paths)}]
    return "complete", items, None


def execute(command, directory, timeout):
    directory.mkdir(parents=True)
    record = {"command": command, "rc": None, "execution_error": None,
              "started_utc": datetime.now(timezone.utc).isoformat(),
              "pss_kib": None, "pss_samples": 0, "pss_scope": "child process only"}
    start = time.monotonic()
    with (directory / "stdout.txt").open("wb") as stdout, (directory / "stderr.txt").open("wb") as stderr:
        try:
            child = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
            record["pid"] = child.pid
            while child.poll() is None:
                try:
                    sample = Path(f"/proc/{child.pid}/smaps_rollup").read_text()
                    match = re.search(r"^Pss:\s+(\d+)\s+kB$", sample, re.M)
                    if match:
                        pss = int(match[1])
                        record["pss_samples"] += 1
                        if record["pss_kib"] is None or pss > record["pss_kib"]:
                            record["pss_kib"] = pss
                            (directory / "smaps_rollup.txt").write_text(sample)
                except OSError:
                    pass
                if time.monotonic() - start > timeout:
                    signal_name = signal.SIGKILL
                    try:
                        import os
                        os.killpg(child.pid, signal_name)
                    except ProcessLookupError:
                        pass
                    record["execution_error"] = "native command timeout"
                    break
                time.sleep(0.02)
            record["rc"] = child.wait()
        except OSError as error:
            record["execution_error"] = str(error)
    record["wall_seconds"] = round(time.monotonic() - start, 6)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("agnix", "skillevaluator", "openai-validator", "anthropic-validator", "corpus", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    prereg = Path(__file__).resolve().with_name("PREREGISTRATION.md")
    if digest(prereg) != PREREG_SHA:
        parser.error("preregistration differs from frozen bytes")
    corpus = args.corpus.resolve()
    case_file = corpus / "cases.json"
    document = json.loads(case_file.read_text())
    cases = document["cases"]
    if not isinstance(cases, list) or not cases:
        parser.error("cases.json must contain a nonempty cases array")
    tools = {name: getattr(args, name).resolve() for name in
             ("agnix", "skillevaluator", "openai_validator", "anthropic_validator")}
    if args.timeout <= 0 or any(not path.is_file() for path in tools.values()):
        parser.error("positive timeout and existing native tool files required")
    ids = set()
    for case in cases:
        ident = case["id"]
        path = (corpus / case["path"]).resolve()
        if not re.fullmatch(r"[CI]\d{2}", ident) or ident in ids:
            parser.error("case IDs must be unique C/I plus two digits")
        ids.add(ident)
        if case["scope"] not in ("skill", "instructions") or not path.is_relative_to(corpus) or not path.is_dir():
            parser.error("case scope/path is invalid or outside corpus")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)  # Reject stale reports and accidental reruns.
    results, views = [], []
    for tool, executable in tools.items():
        for case in cases:
            target = (corpus / case["path"]).resolve()
            record = {"tool": tool, "case_id": case["id"], "scope": case["scope"]}
            view = {"record_index": len(results), "case_id": case["id"], "scope": case["scope"]}
            if case["scope"] == "instructions" and tool != "agnix":
                record.update(status="unsupported_scope", command=None, rc=None, wall_seconds=None,
                              pss_kib=None, artifacts=[])
                view.update(status="unsupported_scope", findings=[], detail="instruction scope unsupported")
            else:
                directory = out / tool / case["id"]
                if tool == "agnix":
                    command = [str(executable), "--target", "codex", "--format", "json", str(target)]
                elif tool == "skillevaluator":
                    command = [str(executable), "validate", str(target), "--tiers", "1", "--checks",
                               "schema,quality", "--no-llm", "--min-score", "70", "-r", "json",
                               "-o", str(directory / "reports")]
                else:
                    command = [sys.executable, str(executable), str(target)]
                record.update(execute(command, directory, args.timeout))
                paths = [str(target), str(corpus), str(out), *(str(p) for p in tools.values())]
                try:
                    status, findings, detail = extract(tool, record, directory, paths)
                except (ValueError, KeyError, TypeError, AttributeError, OSError) as error:
                    status, findings, detail = "incomplete", [], f"native report parse failure: {error}"
                record["status"], record["detail"] = status, detail
                record["artifacts"] = [{"path": str(p.relative_to(out)), "sha256": digest(p)}
                                       for p in sorted(directory.rglob("*")) if p.is_file()]
                view.update(status=status, findings=findings, detail=neutral(detail, paths) if detail else None)
            results.append(record)
            views.append(view)
            write_json(out / "native-results.json", {"preregistration_sha256": PREREG_SHA,
                       "cases_sha256": digest(case_file), "tool_files": {
                           name: {"path": str(p), "sha256": digest(p)} for name, p in tools.items()},
                       "python": sys.version, "records": results})
            write_json(out / "finding-views.json", {"requires_parent_anonymization": True, "records": views})
    print(out / "native-results.json")
    return int(any(r["status"] in ("incomplete", "tool_error") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
