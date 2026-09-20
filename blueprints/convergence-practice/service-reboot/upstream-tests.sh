#!/usr/bin/env bash
# Execute unchanged upstream Dagu tests on an owned hosted runner only.
set -euo pipefail
if [[ ${GITHUB_ACTIONS:-} != true || ${RUNNER_ENVIRONMENT:-} != github-hosted ]]; then
  echo 'Upstream execution requires the disposable hosted runner' >&2
  exit 2
fi
upstream_root="$RUNNER_TEMP/native-service-reboot-upstream"
mkdir --mode=0700 -- "$upstream_root"
mkdir --mode=0700 -- "$upstream_root/reports" "$upstream_root/home" "$upstream_root/source"
upstream_exit=0
trap 'upstream_exit=$?; printf "%s\n" "$upstream_exit" > "$upstream_root/reports/exit-code.txt"' EXIT
revision=58fed633d58c1dd1319091fdb2c2f6158ecfa053
curl --fail --silent --show-error --location --max-time 120 \
  "https://codeload.github.com/dagucloud/dagu/tar.gz/$revision" \
  --output "$upstream_root/source.tar.gz"
printf '%s  %s\n' 8f4b1095a88bb037b582f8b5e337360b1702879f1abb9cfc319643ef1a775746 "$upstream_root/source.tar.gz" \
  | sha256sum --check | tee "$upstream_root/reports/archive-verification.txt"
python3 - "$upstream_root" <<'PY'
import hashlib, json, pathlib, sys, tarfile
root = pathlib.Path(sys.argv[1])
with tarfile.open(root / 'source.tar.gz') as source:
    source.extractall(root / 'source', filter='data')
tree = next((root / 'source').iterdir())
files = {str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in tree.rglob('*') if p.is_file() and not p.is_symlink()}
(root / 'reports/source-before.json').write_text(json.dumps(files, sort_keys=True, indent=2) + '\n')
PY
cd "$upstream_root/source/dagu-$revision"
# Native Go module checksums and the upstream go.mod stay unchanged. No provider
# credentials or general runner environment are passed to the upstream process.
upstream_env=(env -i "PATH=$PATH" "HOME=$upstream_root/home" "GOPATH=$upstream_root/go"
  "GOCACHE=$upstream_root/go-cache" "GOTOOLCHAIN=local" "GOSUMDB=sum.golang.org")
"${upstream_env[@]}" go version | tee "$upstream_root/reports/go-version.txt"
printf '%s\n' "go test -count=1 -run '^TestRetryCommand($|_)' -timeout 12m -v ./internal/cmd" \
  > "$upstream_root/reports/native-command.txt"
timeout --signal=TERM --kill-after=15s 20m "${upstream_env[@]}" \
  go test -count=1 -run '^TestRetryCommand($|_)' -timeout 12m -v ./internal/cmd \
  2>&1 | tee "$upstream_root/reports/upstream-tests.txt"
python3 - "$upstream_root" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
tree = next((root / 'source').iterdir())
before = json.loads((root / 'reports/source-before.json').read_text())
after = {name: hashlib.sha256((tree / name).read_bytes()).hexdigest() for name in before}
(root / 'reports/source-after.json').write_text(json.dumps(after, sort_keys=True, indent=2) + '\n')
if after != before:
    raise SystemExit('Upstream source changed during its test execution')
PY
