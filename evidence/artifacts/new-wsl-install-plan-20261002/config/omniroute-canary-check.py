#!/usr/bin/env python3
"""Bind the installed package to the recorded canary without reading provider state.

Upstream OmniRoute@23a11484862b3bb589a55e85b00e4ac53ffeb234:
bin/omniroute.mjs:43-56 (--version fast path), package.json:3;
scripts/build/write-build-sha.mjs:63-66; scripts/build/buildProvenance.ts:43-48 (dist/BUILD_SHA).
The expected marker comes from config/omniroute-canary-evidence.json.
"""
import json
from pathlib import Path
import subprocess
import sys


def check(binary, evidence, tool_root):
    receipt = json.loads(evidence.read_text())
    composition = receipt["composition"]
    expected_version = composition["version"].removesuffix("-canary")
    resolved = binary.resolve(strict=True)
    relative = resolved.relative_to(tool_root.resolve(strict=True))
    if (not relative.parts[0].startswith("omniroute-canary-")
            or relative.parts[1:5] != ("prefix", "lib", "node_modules", "omniroute")):
        raise ValueError("OmniRoute binary is outside the owned canary prefix")
    build = tool_root / relative.parts[0]
    tree = subprocess.run(["git", "-C", str(build / "source"), "rev-parse", "HEAD^{tree}"],
                          check=True, capture_output=True, text=True)
    if tree.stdout.strip() != receipt["reproduction"]["source_tree"]:
        raise ValueError("OmniRoute source tree differs from the exact canary composition")
    package = resolved.parent.parent
    metadata = json.loads((package / "package.json").read_text())
    if metadata.get("name") != "omniroute" or metadata.get("version") != expected_version:
        raise ValueError("installed OmniRoute package differs from the recorded canary version")
    returned = subprocess.run([str(binary), "--version"], check=True, capture_output=True, text=True)
    if returned.stdout.strip() != expected_version:
        raise ValueError("OmniRoute CLI version differs from the recorded canary")
    marker = (package / "dist/BUILD_SHA").read_text().strip()
    if marker != composition["recorded_build_sha"]:
        raise ValueError("OmniRoute BUILD_SHA differs from the recorded canary")
    print("gpt-gateway | recorded-canary-version-and-build=passed")


if __name__ == "__main__":
    try:
        check(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        # Paths and provider output are private; report only the failed binding.
        raise SystemExit("gpt-gateway: installed binary is not the recorded canary")
