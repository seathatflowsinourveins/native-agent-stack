"""Run only native_token_ci's rtk install (--install path) and rtk_fixture from the worktree."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, "scripts")
import native_token_ci as ci
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=False)
with tempfile.TemporaryDirectory(prefix="native-token-ci-rtk-") as d:
    run = ci.Run(out, Path(d))
    try:
        binary = run.install("rtk")
        run.tools["rtk"] = binary
        version = run.command("version-rtk", [binary, "--version"])
        print("version:", version.strip())
        ci.rtk_fixture(run)
    except Exception as e:
        print("ERROR", type(e).__name__, str(e)[:300])
    print("archive sha256:", run.report.get("rtk_archive_sha256"))
    for c in run.report["checks"]:
        print(c)
    print("failures:", run.report["failures"])
