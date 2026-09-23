#!/usr/bin/env bash
# Setup for the local rerun of the unchanged upstream Dagu retry tests (gap 11).
# Downloads (disclosed): Go 1.27.0 linux-amd64 (~70 MB, sha256 pinned from go.dev),
# the Dagu v2.16.6 source archive (sha256 pinned in service-reboot/plan.json) and the
# Go modules named by its unchanged go.sum (via proxy.golang.org, checked by sum.golang.org).
# Everything lands under $CACHE; nothing is placed on PATH or in ~/.config.
set -euo pipefail
CACHE=${CACHE:-$HOME/.cache/gap-wave2-20260923/scheduling-supervision/go-setup}
mkdir -p "$CACHE"
cd "$CACHE"
go_sha=675c26c449cbb18fc24b74650de1eabbae6e16f64326fd85a283fb3b58280685
src_rev=58fed633d58c1dd1319091fdb2c2f6158ecfa053
src_sha=8f4b1095a88bb037b582f8b5e337360b1702879f1abb9cfc319643ef1a775746
[[ -f go1.27.0.linux-amd64.tar.gz ]] || curl --fail -sSL --max-time 300 -o go1.27.0.linux-amd64.tar.gz https://go.dev/dl/go1.27.0.linux-amd64.tar.gz
printf '%s  %s\n' "$go_sha" go1.27.0.linux-amd64.tar.gz | sha256sum --check
[[ -x go/bin/go ]] || tar -xzf go1.27.0.linux-amd64.tar.gz
[[ -f dagu-source.tar.gz ]] || curl --fail -sSL --max-time 120 -o dagu-source.tar.gz "https://codeload.github.com/dagucloud/dagu/tar.gz/$src_rev"
printf '%s  %s\n' "$src_sha" dagu-source.tar.gz | sha256sum --check
rm -rf modsrc && mkdir modsrc && tar -xzf dagu-source.tar.gz -C modsrc
cd "modsrc/dagu-$src_rev"
env -i "PATH=$CACHE/go/bin:/usr/bin:/bin" "HOME=$CACHE/home" "GOPATH=$CACHE/gopath" "GOCACHE=$CACHE/gocache" \
  "GOTOOLCHAIN=local" "GOSUMDB=sum.golang.org" go version
env -i "PATH=$CACHE/go/bin:/usr/bin:/bin" "HOME=$CACHE/home" "GOPATH=$CACHE/gopath" "GOCACHE=$CACHE/gocache" \
  "GOTOOLCHAIN=local" "GOSUMDB=sum.golang.org" go mod download
du -sh "$CACHE/gopath" "$CACHE/go"
