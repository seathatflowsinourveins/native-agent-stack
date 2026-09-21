#!/usr/bin/env python3
"""Run the diagnostic in a mandatory network namespace; keep returned output private."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Preserve the virtualenv interpreter path: resolving bin/python follows its
    # symlink to system Python and loses the installed native distribution.
    interpreter = args.python.absolute()
    runtime, source, output = interpreter.parent.parent, args.run.resolve(), args.out.resolve()
    if not (runtime / "pyvenv.cfg").is_file() or output.is_relative_to(source) or output.is_relative_to(runtime):
        raise ValueError("invalid_runtime_or_output")
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    argv = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--clearenv",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
            "--symlink", "usr/lib64", "/lib64", "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--ro-bind", str(runtime), str(runtime), "--ro-bind", str(ROOT), "/repo", "--ro-bind", str(source), "/data",
            "--bind", str(output), "/out", "--chdir", "/repo"]
    for key, value in {"LANG": "C.UTF-8", "PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}.items():
        argv.extend(["--setenv", key, value])
    argv.extend([str(interpreter), "-I", "/repo/blueprints/us-equities/engine-nautilus/equity-replay/run.py",
                 "--run", "/data", "--out", "/out/native"])
    record = {"argv": argv, "cwd": str(ROOT), "started_utc": datetime.now(timezone.utc).isoformat()}
    (output / "command.private.json").write_text(json.dumps(record, indent=2) + "\n")
    with (output / "stdout").open("wb") as stdout, (output / "stderr").open("wb") as stderr:
        try:
            p = subprocess.run(argv, cwd=ROOT, env={"PATH": "/usr/bin:/bin"}, stdout=stdout, stderr=stderr, timeout=60)
            record["exit_code"] = p.returncode
        except subprocess.TimeoutExpired:
            record["exit_code"] = 124
    record["finished_utc"] = datetime.now(timezone.utc).isoformat()
    record["returned_output"] = {name: {"bytes": (output / name).stat().st_size,
        "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()} for name in ("stdout", "stderr")}
    (output / "command.private.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: v for k, v in record.items() if k not in ("argv", "cwd")}))
    raise SystemExit(record["exit_code"])


if __name__ == "__main__":
    main()
