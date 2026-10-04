#!/usr/bin/env bash
# local_integration trial (self-written; not an upstream uv test). How does the pinned uv parse the
# direct reference install_uv_tool hands it, "<package> @ <location>", when the install root holds
# characters PEP 508 or RFC 3986 treat specially? Offline (UV_OFFLINE=1), UV_NO_CONFIG=1, no Python
# download, a scratch UV_TOOL_DIR/UV_TOOL_BIN_DIR/UV_CACHE_DIR per trial, and a locally built,
# dependency-free fixture wheel "demo-tool" 1.0.0 with one console script and an empty [mcp] extra.
#   usage: uv_forms.sh UV WORK
#   forms: bare     "<package> @ /abs/path.whl"              (the first repair's form)
#          raw      "<package> @ file:///abs/path.whl"       (a file URL, path not encoded)
#          encoded  "<package> @ file://<each segment @uri>" (install_uv_tool's jq expression)
set -uo pipefail
uv="$1" work="$2"
rm -rf "$work"
mkdir -p "$work/plain"
python3 - "$work/plain" <<'EOF'
import base64, hashlib, sys, zipfile
from pathlib import Path
dist, module, version = "demo-tool", "demo_tool", "1.0.0"
info = f"{module}-{version}.dist-info"
files = {f"{module}/__init__.py": f"def main():\n    print('{dist} {version}')\n",
         f"{info}/METADATA": f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\nProvides-Extra: mcp\n",
         f"{info}/WHEEL": "Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
         f"{info}/entry_points.txt": f"[console_scripts]\n{dist} = {module}:main\n"}
record = "".join(f"{p},sha256={base64.urlsafe_b64encode(hashlib.sha256(t.encode()).digest()).rstrip(b'=').decode()},{len(t.encode())}\n"
                 for p, t in files.items()) + f"{info}/RECORD,,\n"
with zipfile.ZipFile(Path(sys.argv[1]) / f"{module}-{version}-py3-none-any.whl", "w") as archive:
    for p, t in {**files, f"{info}/RECORD": record}.items():
        archive.writestr(p, t)
EOF
wheel_src="$work/plain/demo_tool-1.0.0-py3-none-any.whl"
export UV_NO_CONFIG=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1
printf 'uv: %s\n' "$("$uv" --version)"
printf 'jq: %s\n' "$(jq --version)"
printf 'fixture wheel sha256: %s\n' "$(sha256sum <"$wheel_src" | cut -d' ' -f1)"
n=0
trial() {  # trial ROOT_NAME FORM [PACKAGE]
  local root_name="$1" form="$2" package="${3:-demo-tool[mcp]}" base spec wheel rc
  n=$((n + 1))
  base="$work/t$n"
  mkdir -p "$base/tools" "$base/bin" "$base/$root_name/downloads"
  cp "$wheel_src" "$base/$root_name/downloads/"
  wheel="$base/$root_name/downloads/demo_tool-1.0.0-py3-none-any.whl"
  case "$form" in
    bare) spec="$package @ $wheel" ;;
    raw) spec="$package @ file://$wheel" ;;
    encoded) spec="$package @ file://$(jq -rn --arg path "$wheel" '$path | split("/") | map(@uri) | join("/")')" ;;
  esac
  UV_CACHE_DIR="$base/cache" UV_TOOL_DIR="$base/tools" UV_TOOL_BIN_DIR="$base/bin" \
    "$uv" tool install --python 3.13 "$spec" </dev/null >"$base/out.log" 2>&1
  rc=$?
  printf '\n=== t%s root %q, form %s: exit %s\nspec: %s\n' "$n" "$root_name" "$form" "$rc" "${spec//$work/<work>}"
  grep -v 'is not on your PATH' "$base/out.log" | grep -E '^(error|  cause| \+ |Installed 1 executable)|already installed' \
    | sed -e "s#$work#<work>#g" | head -3
  if [[ -f "$base/tools/demo-tool/uv-receipt.toml" ]]; then
    printf 'receipt: %s\n' "$(grep '^requirements' "$base/tools/demo-tool/uv-receipt.toml" | sed -e "s#$work#<work>#g")"
    printf 'run: %s\n' "$("$base/bin/demo-tool" </dev/null 2>&1 | head -1)"
  fi
  if [[ "$form" == encoded && "$package" == "demo-tool[mcp]" && "$rc" == 0 ]]; then
    UV_CACHE_DIR="$base/cache" UV_TOOL_DIR="$base/tools" UV_TOOL_BIN_DIR="$base/bin" \
      "$uv" tool install --python 3.13 "$spec" </dev/null >"$base/again.log" 2>&1
    printf 'same spec again: exit %s: %s\n' "$?" "$(grep -c 'is already installed' "$base/again.log") 'is already installed' line(s)"
  fi
}
for root_name in plain 'eco#1' 'eco ;1' 'eco #1' 'eco 1' 'eco;1' 'eco%231' 'écho' "a!b*c'd(e)f" 'eco #1 ;%é'; do
  trial "$root_name" bare
  trial "$root_name" encoded
done
trial 'eco#1' raw
trial 'eco #1 ;%é' encoded 'demo[mcp]'
