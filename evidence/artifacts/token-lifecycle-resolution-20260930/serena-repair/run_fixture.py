#!/usr/bin/env python3
"""Narrow diagnostic invocation of scripts.native_token_ci.serena_fixture.

Local integration evidence of oraios/serena's native MCP operation, not an
upstream test or a model run. It uses the existing scoped Run implementation.
"""

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("native_token_ci", ROOT / "scripts/native_token_ci.py")
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--install", action="store_true")
parser.add_argument("--changed-schema-context", choices=("claude-code", "codex"),
                    help="Local fault injection: change one generated native input-schema type")
args = parser.parse_args()
output = args.output.absolute()
output.mkdir(parents=True, exist_ok=False)
with tempfile.TemporaryDirectory(prefix="serena-parity-repair-") as directory:
    run = ci.Run(output, Path(directory))
    run.fresh_install = args.install
    run.report["installation"] = "fresh-upstream-prefix" if args.install else "existing-executables"
    if args.changed_schema_context:
        # Fault injection at the exact pinned source's schema-generation seam:
        # src/serena/mcp.py:281, SerenaMCPFactory.make_mcp_tool. No installed file is edited.
        tool, parameter = (("replace_content", "needle") if args.changed_schema_context == "claude-code"
                           else ("search_for_pattern", "substring_pattern"))
        control = run.work / "schema-control"
        control.mkdir()
        (control / "sitecustomize.py").write_text(
            "import sys\nfrom serena.mcp import SerenaMCPFactory\n"
            "original = SerenaMCPFactory.make_mcp_tool\n"
            "def changed(tool, *args, **kwargs):\n"
            "    generated = original(tool, *args, **kwargs)\n"
            f"    if tool.get_name() == {tool!r}:\n"
            f"        prop = generated.parameters['properties'][{parameter!r}]\n"
            "        assert prop['type'] == 'string'\n"
            "        prop['type'] = 'integer'\n"
            "        sys.stderr.write('[SCHEMA-CONTROL] changed one inputSchema type\\n')\n"
            "    return generated\n"
            "SerenaMCPFactory.make_mcp_tool = staticmethod(changed)\n"
        )
        run.env["PYTHONPATH"] = str(control)
        run.report["fault_injection"] = {"evidence_class": "local_fault_injection",
                                          "context": args.changed_schema_context, "tool": tool,
                                          "parameter": parameter, "before": "string", "after": "integer",
                                          "source": f"https://github.com/oraios/serena/blob/{ci.SERENA_COMMIT}/src/serena/mcp.py#L281"}
    completed = False
    try:
        binary = run.install("serena") if args.install else shutil.which("serena")
        ci.require(bool(binary), "Missing native executable: serena")
        run.tools["serena"] = str(binary)
        ci.verify_version(run, "serena", str(binary))
        ci.serena_fixture(run)
        completed = True
    except Exception as error:
        run.report["failures"].append({"component": "serena", "error": run.clean(str(error))})
    finally:
        shutil.rmtree(run.work)
        run.report["cleanup"] = {"owned_temporary_directory_absent": not run.work.exists(),
                                 "retained_output_exists": output.is_dir()}
        run.report["execution_completed"] = completed
        run.report["status"] = "passed" if completed and not run.report["failures"] else "failed"
        run.flush()
print(json.dumps({"status": run.report["status"], "commands": len(run.report["commands"]),
                  "checks": len(run.report["checks"]), "failures": run.report["failures"],
                  "serena_parity": run.report.get("serena_parity"), "cleanup": run.report["cleanup"]}))
raise SystemExit(0 if run.report["status"] == "passed" else 1)
