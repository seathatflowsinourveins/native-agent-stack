#!/usr/bin/env bash
# Upstream-owned operations on a fresh install (self-written driver, added after the recorded e2e runs;
# not an upstream test suite and not CI). In order:
# 1. bootstrap_once.sh installs profile {headroom, socraticode} with the checkout's
#    adoption/bootstrap-linux.sh and pins over the network, as e2e.sh's pass scenario does.
# 2. What the installed packages hold, read from their files and help texts: the headroom wheel's
#    entries and README, headroom's evals and doctor help, socraticode's package.json, README and the
#    dist/ lines behind its startup and codebase_health behaviour. These show which upstream checks
#    apply offline; nothing in this step installs, indexes or calls a model.
# 3. headroom's own evaluation `headroom evals adversarial`, which its --help documents as "Offline and
#    deterministic - no LLM, no API key, no model download", runs twice; the JSON reports are compared.
# 4. socraticode's documented launch, its installed `socraticode` bin as an MCP stdio server, is asked
#    for its identity and tool list by mcp_list_tools.mjs, with SOCRATICODE_LOG_FILE set so the
#    server's own log is kept. The same client then starts a node process that exits at once (the
#    control: no MCP server answers, so the check must fail).
# Steps 2 (the help texts), 3 and 4 run in a new network namespace (unshare --map-current-user --net:
# no interface is up, not even loopback) with HOME, the XDG directories and TMPDIR under WORK and with
# SOCRATICODE_AUTO_RESUME=off, which socraticode reads before any Docker or Qdrant access.
#   usage: upstream_checks.sh CHECKOUT WORK
set -uo pipefail
checkout="$1" work="$2"
here="$(cd "$(dirname "$0")" && pwd -P)"
# WORK must be new, an empty directory, or a directory these drivers created (work_guard.sh).
# shellcheck source-path=SCRIPTDIR source=work_guard.sh
. "$here/work_guard.sh" || exit 2
claim_work "$work" || exit 2
rm -rf "$work"
mkdir -p "$work"
mark_work "$work"
work="$(cd "$work" && pwd -P)"
# npm's debug log masks a UUID-shaped path segment as "***"; that spelling of WORK is sanitized too.
masked="$(printf '%s' "$work" | sed -E 's/[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}/***/g')"
san() { sed -e "s#$work#<work>#g" -e "s#${masked//\*/\\*}#<work>#g"; }
pins="$checkout/adoption/pins-linux-x86_64.json"
eco="$work/eco"
home="$work/home-checks"
printf 'checkout HEAD %s (working tree)\n' "$(git -C "$checkout" rev-parse HEAD)"
printf 'driver sha256: upstream_checks.sh %s, mcp_list_tools.mjs %s, bootstrap_once.sh %s, work_guard.sh %s\n' \
  "$(sha256sum <"$here/upstream_checks.sh" | cut -d' ' -f1)" "$(sha256sum <"$here/mcp_list_tools.mjs" | cut -d' ' -f1)" \
  "$(sha256sum <"$here/bootstrap_once.sh" | cut -d' ' -f1)" "$(sha256sum <"$here/work_guard.sh" | cut -d' ' -f1)"
"$here/bootstrap_once.sh" upstream "$checkout/adoption/bootstrap-linux.sh" "$pins" "$work" "$work/uv-cache" \
  '["headroom","socraticode"]' "$eco" | san
printf '\n--- the version report the run wrote (installed-versions.txt)\n'
san <"$eco/installed-versions.txt"
printf '\n--- npm'"'"'s own debug log of the socraticode install, read as check.py reads it\n'
for log in "$work"/npm-cache-upstream/_logs/*-debug-0.log; do
  argv="$(grep -m1 ' verbose argv ' "$log" | sed -e 's/^.* verbose argv //')"
  [[ "$argv" == '"install"'* ]] || continue
  printf 'argv: %s\n' "$argv" | san
  printf 'lifecycle scripts run (info run lines): %s\n' "$(grep ' info run ' "$log" | grep -vc '{ code:')"
done

mkdir -p "$home" "$work/tmp" "$work/project"
offline() {  # offline CMD...: in a new network namespace, cwd WORK/project, HOME/XDG/TMPDIR under WORK
  (cd "$work/project" && env HOME="$home" XDG_CONFIG_HOME="$home/.config" XDG_CACHE_HOME="$home/.cache" \
    XDG_DATA_HOME="$home/.local/share" XDG_STATE_HOME="$home/.local/state" TMPDIR="$work/tmp" \
    PATH="$eco/bin:$PATH" DO_NOT_TRACK=1 SOCRATICODE_AUTO_RESUME=off \
    unshare --map-current-user --net timeout 600 "$@" </dev/null)
}
printf '\n=== the namespace the checks run in\n'
offline ip -brief link 2>&1 | san
offline "$eco/bin/node" -e 'require("node:net").connect(443, "1.1.1.1")
  .on("connect", () => { console.log("TCP connect to 1.1.1.1:443 succeeded"); process.exit(1); })
  .on("error", (error) => console.log("TCP connect to 1.1.1.1:443 fails: " + error.code));' 2>&1 | san

version="$(jq -r '.tools[] | select(.id == "socraticode") | .version' "$pins")"
package="$eco/tools/socraticode-$version/lib/node_modules/socraticode"
wheel="$eco/downloads/$(jq -r '.tools[] | select(.id == "headroom") | .url | split("/") | last' "$pins")"
printf '\n=== what the installed packages hold, and which upstream checks apply offline\n'
printf -- '--- the headroom wheel (%s), its entries and its README (METADATA)\n' "${wheel##*/}"
python3 - "$wheel" <<'EOF'
import re, sys, zipfile
wheel = zipfile.ZipFile(sys.argv[1])
names = wheel.namelist()
rows = [row for row in wheel.read(next(n for n in names if n.endswith(".dist-info/RECORD"))).decode().splitlines() if row.strip()]
print(f"{len(names)} entries; RECORD: {len(rows)} rows, {sum(1 for row in rows if row.split(',')[1])} with a hash")
tests = [n for n in names if re.search(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$", n)]
print(f"entries whose path looks like a test: {len(tests)}: {' '.join(tests) or 'none'}")
for line in wheel.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode().splitlines():
    if re.search(r"uv run pytest|^headroom doctor\s+#|evals suite --tier", line):
        print(f"README: {line.strip()}")
EOF
for args in "evals adversarial --help" "evals probes --help" "doctor --help"; do
  printf -- '--- $ headroom %s\n' "$args"
  # shellcheck disable=SC2086  # the arguments are split on purpose
  offline "$eco/bin/headroom" $args 2>&1 | san
done
printf -- '--- $ python -m headroom.evals suite --help (the tool environment'"'"'s python)\n'
offline "$eco/python-tools/headroom-ai/bin/python" -m headroom.evals suite --help 2>&1 | san
printf -- '--- socraticode %s: package.json files and test scripts\n' "$version"
jq -c '{files, test_scripts: (.scripts | with_entries(select(.key | startswith("test"))))}' "$package/package.json"
printf -- '--- its README: a stdio launch as an MCP server, and the codebase_health row\n'
# shellcheck disable=SC2016  # the backticks are the README's own text
grep -n -F -e 'claude mcp add --scope user socraticode -- npx -y --prefer-online socraticode@latest' \
  -e 'Register `node /absolute/path/to/socraticode/dist/index.js`' -e '| `codebase_health` |' "$package/README.md" | cut -c1-160
printf -- '--- dist/services/startup.js: SOCRATICODE_AUTO_RESUME=off returns before the Docker and Qdrant checks\n'
grep -n -F -e 'const resumeMode = process.env.SOCRATICODE_AUTO_RESUME' -e 'Auto-resume: disabled by SOCRATICODE_AUTO_RESUME=off' \
  -e 'if (QDRANT_MODE === "managed")' -e 'await isDockerAvailable()' "$package/dist/services/startup.js"
printf -- '--- codebase_health and codebase_about: dist/index.js, dist/tools/manage-tools.js, dist/services/docker.js\n'
grep -n -F 'server.tool("codebase_health"' "$package/dist/index.js" | cut -c1-200
grep -n -F -e 'case "codebase_health"' -e 'case "codebase_about"' -e 'const infraStatus = await getInfraStatusSummary()' \
  -e 'const docker = await isDockerAvailable()' "$package/dist/tools/manage-tools.js"
grep -n -F 'await run("docker", ["info"])' "$package/dist/services/docker.js"

printf '\n=== headroom (%s)\n' "$(offline "$eco/bin/headroom" --version 2>&1)"
for n in 1 2; do
  started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  offline "$eco/bin/headroom" evals adversarial --json-output "$work/adversarial-$n.json" \
    >"$work/adversarial-$n.out" 2>"$work/adversarial-$n.err"
  rc=$?
  printf '\n--- run %s: headroom evals adversarial --json-output <work>/adversarial-%s.json\n' "$n" "$n"
  printf 'started %s, ended %s, exit %s\n' "$started" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc"
  printf -- '- stdout:\n'
  san <"$work/adversarial-$n.out"
  printf -- '- stderr:\n'
  san <"$work/adversarial-$n.err"
  if [[ -f "$work/adversarial-$n.json" ]]; then
    printf -- '- JSON report: sha256 %s, %s bytes\n' "$(sha256sum <"$work/adversarial-$n.json" | cut -d' ' -f1)" \
      "$(wc -c <"$work/adversarial-$n.json" | tr -d ' ')"
  else
    printf -- '- JSON report: not written\n'
  fi
done
if cmp -s "$work/adversarial-1.json" "$work/adversarial-2.json"; then
  printf '\nthe two JSON reports are byte-identical\n'
else
  printf '\nthe two JSON reports differ or are missing\n'
fi

printf '\n=== socraticode %s: MCP initialize and tools/list over stdio, server <work>/eco/bin/socraticode\n' "$version"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
offline env SOCRATICODE_LOG_FILE="$work/socraticode.log" "$eco/bin/node" "$here/mcp_list_tools.mjs" "$package" \
  "$eco/bin/socraticode" 2>&1 | san
rc=${PIPESTATUS[0]}
printf 'started %s, ended %s, exit %s\n' "$started" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$rc"
printf -- '- the server'"'"'s own log (SOCRATICODE_LOG_FILE=<work>/socraticode.log):\n'
if [[ -f "$work/socraticode.log" ]]; then san <"$work/socraticode.log"; else printf 'not written\n'; fi
printf '\n=== control: the same client, server a node process that exits at once\n'
offline "$eco/bin/node" "$here/mcp_list_tools.mjs" "$package" "$eco/bin/node" -e '' 2>&1 | san
rc=${PIPESTATUS[0]}
printf 'exit %s\n' "$rc"

printf '\n--- the bootstrap run'"'"'s own stdout and stderr (upstream.log)\n'
san <"$work/upstream.log"
