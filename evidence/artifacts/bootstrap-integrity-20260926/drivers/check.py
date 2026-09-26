"""local_integration post-run checks (self-written; not an upstream test) for e2e.sh's WORK directory.

usage: check.py CHECKOUT WORK E2E_OUT
Reads each scenario's bootstrap log, ECO_INSTALL_ROOT and npm debug log directly (not the driver's
own claims), runs native_probe.cjs (next to this file) against the pass run's socraticode install,
prints one PASS/FAIL line per check, and exits 0 only when every check holds. Every path under WORK
(the runs' scratch HOMEs included) is printed as <work>.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

checkout, work, e2e_out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3])
pins = {tool["id"]: tool for tool in json.loads((checkout / "adoption/pins-linux-x86_64.json").read_text())["tools"]}
headroom, socraticode = pins["headroom"], pins["socraticode"]
wheel_name = headroom["url"].rsplit("/", 1)[1]
exits = dict(re.findall(r"^\[([\w-]+)\] bootstrap exit (\d+)$", e2e_out.read_text(), re.M))
# npm's own debug log masks a UUID-shaped path segment as "***"; sanitize that spelling of WORK too.
masked_work = re.sub(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", "***", str(work))
failures = 0


def san(text: object) -> str:
    return str(text).replace(str(work), "<work>").replace(masked_work, "<work>")


def check(label: str, value: object, passed: bool) -> None:
    global failures
    failures += not passed
    print(f"{'PASS' if passed else 'FAIL'} {label}: {san(value)}")


def log(label: str) -> str:
    return (work / f"{label}.log").read_text()


def requirement(eco: Path) -> dict | None:
    receipt = eco / "python-tools/headroom-ai/uv-receipt.toml"
    if not receipt.is_file():
        return None
    return tomllib.loads(receipt.read_text())["tool"]["requirements"][0]


def npm_install_log(label: str) -> tuple[str, list[str]]:
    """The argv npm received for its `install` and every lifecycle script it ran ("info run" lines)."""
    for path in sorted((work / f"npm-cache-{label}/_logs").glob("*-debug-0.log")):
        text = path.read_text()
        argv = next((line.split(" verbose argv ", 1)[1] for line in text.splitlines() if " verbose argv " in line), "")
        if argv.startswith('"install"'):
            return argv, [line.split(" info run ", 1)[1] for line in text.splitlines()
                          if " info run " in line and "{ code:" not in line]
    return "", []


def uv_lines(label: str) -> list[str]:
    keep = re.compile(r"^(Resolved|Prepared|Installed|Uninstalled|Audited) \d+ package|already installed|^ [-+] headroom-ai")
    return [line for line in log(label).splitlines() if keep.search(line)]


def version_report(eco: Path, pin_id: str) -> list[str]:
    """The installed-versions.txt block of one pin: its probe line, the probe's output and its result."""
    report = (eco / "installed-versions.txt").read_text().split("\n-- ")
    return [" / ".join(block.strip().splitlines()) for block in report if block.startswith(f"{pin_id} ")]


# 1. pass: the fixed script installs both pins through their verified artifacts.
print("== pass: fixed script, the checkout's pins, profile {headroom, socraticode}")
eco = work / "eco-pass"
check("bootstrap exit", exits.get("pass"), exits.get("pass") == "0")
for line in (f"Installed headroom {headroom['version']} (uv-tool)", f"Installed socraticode {socraticode['version']} (npm)"):
    check("run log line", line, line in log("pass"))
for pin_id in ("headroom", "socraticode"):
    blocks = version_report(eco, pin_id)
    check(f"version report ({pin_id})", " | ".join(blocks),
          len(blocks) == 1 and blocks[0].endswith(f"result: verified (exact {pins[pin_id]['version']})"))
summary = [line for line in (eco / "installed-versions.txt").read_text().splitlines() if line.startswith("summary:")]
check("version report summary", summary, summary == ["summary: 5 verified, 0 failed"])
wheel = eco / "downloads" / wheel_name
digest = hashlib.sha256(wheel.read_bytes()).hexdigest() if wheel.is_file() else None
check("downloaded wheel sha256 equals the pin", f"{wheel_name} {digest}", digest == headroom["sha256"])
req = requirement(eco)
check("uv-receipt.toml requirement", req, req == {"name": "headroom-ai", "extras": ["mcp"], "path": str(wheel)})
site = next((eco / "python-tools/headroom-ai/lib").glob("python3.*/site-packages"))
direct_url = json.loads((site / f"headroom_ai-{headroom['version']}.dist-info/direct_url.json").read_text())
check("direct_url.json url is the wheel's file URL", direct_url["url"], direct_url["url"] == wheel.as_uri())
python = eco / "python-tools/headroom-ai/bin/python"
metadata = subprocess.run([str(python), "-c", "import importlib.metadata as m; print(m.version('headroom-ai'), m.version('mcp'))"],
                          capture_output=True, text=True, timeout=60)
check("tool environment metadata: headroom-ai and mcp (the [mcp] extra) versions", metadata.stdout.strip(),
      metadata.returncode == 0 and metadata.stdout.split()[0] == headroom["version"])
with zipfile.ZipFile(wheel) as archive:
    record_name = next(name for name in archive.namelist() if name.endswith(".dist-info/RECORD"))
    rows = list(csv.reader(io.StringIO(archive.read(record_name).decode())))
checked = matched = 0
for path, hash_field, _size in rows:
    if not hash_field or ".data/" in path:  # RECORD itself; .data/ files are relocated by the installer
        continue
    algorithm, expected = hash_field.split("=", 1)
    checked += 1
    target = site / path
    if target.is_file():
        actual = base64.urlsafe_b64encode(hashlib.new(algorithm, target.read_bytes()).digest()).rstrip(b"=").decode()
        matched += actual == expected
check("installed files matching the wheel's own RECORD hashes", f"{matched} of {checked}", checked > 0 and matched == checked)
env = {**os.environ, "HOME": str(work / "home-pass")}
version = subprocess.run([str(eco / "bin/headroom"), "--version"], capture_output=True, text=True, timeout=60,
                         stdin=subprocess.DEVNULL, env=env)
check("upstream `headroom --version` from the installed bin/", f"exit {version.returncode}: {version.stdout.strip()}",
      version.returncode == 0 and version.stdout.strip() == f"headroom, version {headroom['version']}")
npm_ls = subprocess.run([str(eco / "bin/npm"), "ls", "--global", "--prefix", str(eco / f"tools/socraticode-{socraticode['version']}"),
                         "--depth=0"], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                        env={**env, "PATH": f"{eco / 'bin'}{os.pathsep}{os.environ['PATH']}",
                             "npm_config_cache": str(work / "npm-cache-pass"), "NPM_CONFIG_USERCONFIG": str(work / "empty-npmrc")})
check("upstream `npm ls` of the socraticode prefix", " ".join(npm_ls.stdout.split()[-1:]),
      npm_ls.returncode == 0 and f"socraticode@{socraticode['version']}" in npm_ls.stdout)
argv, runs = npm_install_log("pass")
check("npm's own debug log: the install argv npm received", argv, '"--ignore-scripts"' in argv)
check("npm's own debug log: lifecycle scripts run (info run lines)", len(runs), not runs)
modules = eco / f"tools/socraticode-{socraticode['version']}/lib/node_modules"
manifests = [path for path in modules.rglob("package.json")
             if path.parent.parent.name == "node_modules"
             or (path.parent.parent.name.startswith("@") and path.parent.parent.parent.name == "node_modules")]
scripted = []
for manifest in manifests:
    try:
        scripts = json.loads(manifest.read_text()).get("scripts") or {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        continue
    hooks = [name for name in ("preinstall", "install", "postinstall") if name in scripts]
    if (manifest.parent / "binding.gyp").is_file() and "install" not in scripts:
        hooks.append("binding.gyp")
    if hooks:
        scripted.append(f"{manifest.parent.relative_to(modules)} ({'/'.join(hooks)})")
print(f"INFO socraticode tree: {len(manifests)} installed packages; {len(scripted)} declare install scripts, "
      f"none of which npm ran: {'; '.join(sorted(scripted))}")
# Whether those 18 packages still work natively without their install scripts, and a control that a
# broken parser is refused (native_probe.cjs, run with the pinned node this run installed).
names = sorted(json.loads((modules / entry.split(" (")[0] / "package.json").read_text())["name"] for entry in scripted)
probe_scratch = work / "probe-scratch"
if probe_scratch.exists():
    shutil.rmtree(probe_scratch)
probe_scratch.mkdir()
probed = subprocess.run([str(eco / "bin/node"), str(Path(__file__).with_name("native_probe.cjs")),
                         str(modules / "socraticode"), str(probe_scratch)],
                        capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, env=env)
lines = probed.stdout.splitlines()
for line in lines:
    print(f"INFO   {san(line)}")
working = [name for name in names if any(line.startswith(f"ok {name}:") for line in lines)]
check("each package whose install script npm skipped still works natively (parse, preflight or subscribe)",
      f"{len(working)} of {len(names)} (node exit {probed.returncode})",
      probed.returncode == 0 and len(names) == 18 and working == names)
check("control: a 64-byte copy of a grammar's parser.so is refused",
      next((line for line in lines if line.startswith(("ok control", "FAILED control"))), "no control line"),
      any(line.startswith("ok control:") for line in lines))

# 2. fixed-bad-hash: the same check with its condition absent (a wrong pinned hash) must refuse.
print("== fixed-bad-hash: fixed script, headroom sha256 set to 64 zeros, profile {headroom}")
eco = work / "eco-fixed-bad-hash"
check("bootstrap exit", exits.get("fixed-bad-hash"), exits.get("fixed-bad-hash") == "1")
refusal = f"Checksum mismatch: {headroom['url']}"
check("refusal line in the run log", refusal, refusal in log("fixed-bad-hash"))
check("no headroom tool environment", (eco / "python-tools/headroom-ai").exists(), not (eco / "python-tools/headroom-ai").exists())
check("no verified wheel left in downloads/", (eco / "downloads" / wheel_name).exists(), not (eco / "downloads" / wheel_name).exists())
check("no 'Installed headroom' line", "Installed headroom" in log("fixed-bad-hash"), "Installed headroom" not in log("fixed-bad-hash"))

# 3. head-bad-hash: HEAD's script never reads the wheel, its hash or ignore_scripts.
print("== head-bad-hash: HEAD's script, the same zeroed pins, profile {headroom, socraticode}")
eco = work / "eco-head-bad-hash"
check("bootstrap exit (installs although the pinned hash is wrong)", exits.get("head-bad-hash"), exits.get("head-bad-hash") == "0")
check("run log line", f"Installed headroom {headroom['version']} (uv-tool)",
      f"Installed headroom {headroom['version']} (uv-tool)" in log("head-bad-hash"))
check("pinned wheel never downloaded", (eco / "downloads" / wheel_name).exists(), not (eco / "downloads" / wheel_name).exists())
req = requirement(eco)
check("uv-receipt.toml requirement (resolved from the index)", req,
      req == {"name": "headroom-ai", "extras": ["mcp"], "specifier": f"=={headroom['version']}"})
argv, runs = npm_install_log("head-bad-hash")
check("npm's own debug log: the install argv npm received", argv, argv and '"--ignore-scripts"' not in argv)
check("npm's own debug log: lifecycle scripts run (info run lines)", len(runs), len(runs) > 0)
for line in runs:
    print(f"INFO   ran: {san(line)[:160]}")

# 4. transition: an index install from HEAD's script, then the fixed script twice on the same root.
print("== transition: one ECO_INSTALL_ROOT, profile {headroom}: HEAD's script, then the fixed script twice")
eco = work / "eco-transition"
for label in ("t1-head", "t2-fixed", "t3-fixed"):
    check(f"{label} bootstrap exit", exits.get(label), exits.get(label) == "0")
    for line in uv_lines(label):
        print(f"INFO   {label} uv: {san(line)}")
# t2 and t3 rewrite uv-receipt.toml, so t1's index install is read from its own uv output.
check("t1-head installs headroom-ai from the index", uv_lines("t1-head"),
      any(line.strip() == f"+ headroom-ai=={headroom['version']}" for line in uv_lines("t1-head")))
check("t2-fixed replaces it with the verified wheel", uv_lines("t2-fixed"),
      any(line.startswith(" - headroom-ai==") for line in uv_lines("t2-fixed"))
      and any(f"(from file://{eco}/downloads/{wheel_name})" in line for line in uv_lines("t2-fixed")))
check("t3-fixed finds it already installed", uv_lines("t3-fixed"), any("is already installed" in line for line in uv_lines("t3-fixed")))
req = requirement(eco)
check("final uv-receipt.toml requirement", req,
      req == {"name": "headroom-ai", "extras": ["mcp"], "path": str(eco / "downloads" / wheel_name)})

print(f"== {failures} check(s) failed")
sys.exit(1 if failures else 0)
