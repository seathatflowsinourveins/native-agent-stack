#!/usr/bin/env bash
# diegosouzapw/OmniRoute@23a11484862b3bb589a55e85b00e4ac53ffeb234:
# package.json:119,134-135,181,253; scripts/build/validate-pack-artifact.ts:215-225.
# Carries: PR13788@24bbadbad15eec0d598c908416e4b01be4e37671,
# 6c7990058c4ce9677de79452c8cefb10b4bf1b3d; PR15167@0585aba5589d5a1f49243a13a8db249558e7c9e3.
# Reproduces the wave-2 B5a source/build/pack gates in a fresh owned prefix.
# It neither starts a service nor reads provider state. Existing foreign/live
# aliases are refused. npm 3.8.51 is a separate documented rollback, not this build.
set -euo pipefail
: "${tool_root:?Run through install.sh}"
: "${config_root:?Run through install.sh}"
omniroute_unit="$HOME/.config/systemd/user/omniroute.service"
if [[ -e "$omniroute_unit" ]] && ! cmp -s -- "$config_root/omniroute.service" "$omniroute_unit"; then
  printf 'Existing OmniRoute unit differs; retained. Reconcile with its owner before proceeding.\n' >&2
  exit 1
fi
omniroute_alias="$HOME/.local/bin/omniroute"
if [[ -e "$omniroute_alias" || -L "$omniroute_alias" ]]; then
  case "$(readlink -f -- "$omniroute_alias")" in
    "$tool_root"/omniroute-canary-*/prefix/*) ;;
    *) printf 'OmniRoute alias already belongs to another installation; retain it and reconcile with its owner.\n' >&2; exit 1 ;;
  esac
  if python3 "$config_root/omniroute-canary-check.py" "$omniroute_alias" \
      "$config_root/omniroute-canary-evidence.json" "$tool_root"; then
    install -d -m 0700 "$HOME/.local/share/omniroute" "$HOME/.config/systemd/user"
    if [[ ! -e "$omniroute_unit" ]]; then
      install -m 0644 -- "$config_root/omniroute.service" "$omniroute_unit"
    fi
    systemctl --user daemon-reload
    printf 'Recorded OmniRoute canary already installed; retained without rebuilding.\n' >&2
    exit 0
  fi
  if systemctl --user is-active --quiet omniroute.service; then
    printf 'Existing owned OmniRoute service is active with a different build; retained for its owner.\n' >&2
    exit 1
  fi
fi
mkdir -p -- "$tool_root" "$HOME/.local/bin"
omniroute_build="$(mktemp -d "$tool_root/omniroute-canary-XXXXXXXX")"
omniroute_keep_build=false
trap 'if ! $omniroute_keep_build; then rm -rf -- "$omniroute_build"; fi' EXIT
git clone --quiet --filter=blob:none https://github.com/diegosouzapw/OmniRoute.git "$omniroute_build/source"
cd -- "$omniroute_build/source"
git checkout --quiet --detach 23a11484862b3bb589a55e85b00e4ac53ffeb234
git fetch --quiet origin 24bbadbad15eec0d598c908416e4b01be4e37671 6c7990058c4ce9677de79452c8cefb10b4bf1b3d 0585aba5589d5a1f49243a13a8db249558e7c9e3
git -c user.name=omniroute-build -c user.email=omniroute-build@localhost cherry-pick \
  24bbadbad15eec0d598c908416e4b01be4e37671 \
  6c7990058c4ce9677de79452c8cefb10b4bf1b3d \
  0585aba5589d5a1f49243a13a8db249558e7c9e3
# Commit timestamps vary across cherry-picks. Bind the historical marker to the
# exact reproducible source tree, without claiming the new commit is the old HEAD.
readarray -t canary_identity < <(python3 - "$config_root/omniroute-canary-evidence.json" <<'PY'
import json, sys
receipt = json.load(open(sys.argv[1]))
print(receipt["reproduction"]["source_tree"])
print(receipt["composition"]["recorded_build_sha"])
PY
)
[[ "$(git rev-parse HEAD^{tree})" == "${canary_identity[0]}" ]]
export OMNIROUTE_BUILD_SHA="${canary_identity[1]}"
npm ci --no-audit --no-fund
# Upstream Node test runner and unchanged carried tests; no local test runner.
DISABLE_SQLITE_AUTO_BACKUP=true node --max-old-space-size=8192 \
  --import tsx/esm --import ./open-sse/utils/setupPolyfill.ts \
  --import ./tests/_setup/isolateDataDir.ts --test --test-force-exit \
  tests/unit/issue-8674-alpha-search.test.ts \
  tests/unit/codex-gpt6-sol-luna.test.ts \
  tests/unit/executor-codex.test.ts \
  tests/unit/codex-fast-tier.test.ts \
  tests/unit/8951-github-gpt56-responses.test.ts
npm run typecheck:core
# Supported release steps from package.json:119. build:release itself resets the
# first build's marker to the timestamp-dependent HEAD; use its native steps so
# Next, CLI and both sentinels all receive the recorded composition marker.
# Upstream write-build-sha.mjs:27-37 explicitly supports OMNIROUTE_BUILD_SHA.
npm run build
npm run build:cli
node scripts/build/write-build-sha.mjs
OMNIROUTE_ALLOW_CANARY_BUILD=1 npm run check:pack-artifact
npm pack --pack-destination "$omniroute_build"
# Upstream npm package installation, parameterized to an owned user prefix.
npm install --global --prefix "$omniroute_build/prefix" --include=optional \
  "$omniroute_build/omniroute-3.8.52.tgz"
test -x "$omniroute_build/prefix/bin/omniroute"
python3 "$config_root/omniroute-canary-check.py" "$omniroute_build/prefix/bin/omniroute" \
  "$config_root/omniroute-canary-evidence.json" "$tool_root"
# Repository template adaptation, this PR: adoption/templates/systemd/omniroute.service:65-97.
# Native user-manager wiring; no enable/start/restart or provider-file read.
install -d -m 0700 "$HOME/.local/share/omniroute" "$HOME/.config/systemd/user"
if [[ ! -e "$omniroute_unit" ]]; then
  install -m 0644 -- "$config_root/omniroute.service" "$omniroute_unit"
fi
systemctl --user daemon-reload
ln -sfn -- "$omniroute_build/prefix/bin/omniroute" "$omniroute_alias"
omniroute_keep_build=true
printf 'OmniRoute canary installed; service startup and native account sign-in remain separate.\n' >&2
