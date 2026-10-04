#!/bin/sh
# Re-verify every source and artifact pin the 2026-09-26 P1 trial batch cites.
#
# Usage: sh verify-pins.sh
#
# Git pins: shallow-clones each pinned tag into a fresh mktemp directory and compares
# `git rev-parse HEAD` and `git rev-parse <tag>^{commit}` with the pinned commit; commits cited
# from a branch are fetched by id. Registry pins: compares PyPI's JSON API sha256 for each pinned
# file with the pinned value and with the sha256 of the file downloaded here, and npm's published
# dist.integrity/dist.shasum with the pinned values. Hugging Face pins: asks the Hub API for each
# pinned revision and prints the fields of the small config files a trial claim rests on.
# Two deliberately wrong expectations must fail. Prints one line per check and exits 0 only when
# every expected pass passed and every must-fail check failed. The workspace is removed on exit.
# This script is local integration glue; the commits, digests and revisions are the upstream
# registries' own.
set -u
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
export GIT_TERMINAL_PROMPT=0 NO_UPDATE_NOTIFIER=1 npm_config_update_notifier=false
bad=0
report() {  # report <expect pass|fail> <got pass|fail> <label> <detail>
  if [ "$1" = "$2" ]; then verdict=ok; else verdict=UNEXPECTED; bad=1; fi
  printf '%s\texpected=%s\tgot=%s\t%s\t%s\n' "$verdict" "$1" "$2" "$3" "$4"
}

git_tag() {  # git_tag <expect> <label> <url> <tag> <commit>
  dir="$work/$2"
  if git clone -q --depth 1 --branch "$4" "$3" "$dir" 2>/dev/null; then
    head=$(git -C "$dir" rev-parse HEAD); peeled=$(git -C "$dir" rev-parse "$4^{commit}")
    if [ "$head" = "$5" ] && [ "$peeled" = "$5" ]; then got=pass; else got=fail; fi
    report "$1" "$got" "git $2" "$3 tag $4: HEAD=$head tag^{commit}=$peeled pinned=$5"
  else
    report "$1" fail "git $2" "$3 tag $4: clone failed"
  fi
}

git_commit() {  # git_commit <label> <url> <commit> <branch>
  dir="$work/$1"
  git init -q "$dir" && git -C "$dir" remote add origin "$2"
  if git -C "$dir" fetch -q --depth 1 origin "$3" 2>/dev/null; then
    fetched=$(git -C "$dir" rev-parse FETCH_HEAD)
    tip=$(git ls-remote "$2" "refs/heads/$4" | cut -f1)
    [ "$fetched" = "$3" ] && got=pass || got=fail
    report pass "$got" "git $1" "$2 commit $3 fetched=$fetched (current $4 tip: $tip)"
  else
    report pass fail "git $1" "$2 commit $3: fetch failed"
  fi
}

pypi() {  # pypi <expect> <package> <version> <filename> <pinned sha256>
  api=$(curl -fsS "https://pypi.org/pypi/$2/$3/json") || { report "$1" fail "pypi $4" "JSON API unreachable"; return; }
  line=$(printf '%s' "$api" | python3 -c 'import json,sys
d=json.load(sys.stdin)
for f in d["urls"]:
    if f["filename"] == sys.argv[1]:
        print(f["digests"]["sha256"], f["url"])' "$4")
  reported=${line%% *}; url=${line#* }
  if [ -z "$reported" ]; then report "$1" fail "pypi $4" "file not listed"; return; fi
  curl -fsS -o "$work/$4" "$url" || { report "$1" fail "pypi $4" "download failed"; return; }
  computed=$(sha256sum "$work/$4" | cut -d' ' -f1)
  if [ "$reported" = "$5" ] && [ "$computed" = "$5" ]; then got=pass; else got=fail; fi
  report "$1" "$got" "pypi $4" "pypi_reported=$reported computed=$computed pinned=$5"
}

npm_pin() {  # npm_pin <spec> <integrity> <shasum>
  integrity=$(npm view "$1" dist.integrity 2>/dev/null); shasum=$(npm view "$1" dist.shasum 2>/dev/null)
  if [ "$integrity" = "$2" ] && [ "$shasum" = "$3" ]; then got=pass; else got=fail; fi
  report pass "$got" "npm $1" "integrity=$integrity shasum=$shasum"
}

hf_rev() {  # hf_rev <models|datasets> <repo> <revision> [file field...]
  kind=$1; repo=$2; rev=$3; shift 3
  sha=$(curl -fsS "https://huggingface.co/api/$kind/$repo/revision/$rev" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha"))')
  main=$(curl -fsS "https://huggingface.co/api/$kind/$repo/revision/main" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha"))')
  [ "$sha" = "$rev" ] && got=pass || got=fail
  report pass "$got" "hf $repo" "revision $rev resolves to $sha (current main: $main)"
}

hf_fields() {  # hf_fields <repo> <revision> <file> <field...>: print selected JSON fields of a small file
  repo=$1; rev=$2; file=$3; shift 3
  rev=$(curl -fsS "https://huggingface.co/api/models/$repo/revision/$rev" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha"))')
  curl -fsSL "https://huggingface.co/$repo/resolve/$rev/$file" -o "$work/hf.json" || { report pass fail "hf $repo/$file" "download failed"; return; }
  if fields=$(python3 -c 'import json,sys
d=json.load(open(sys.argv[1]))
missing=[k for k in sys.argv[2:] if k not in d]
print(" ".join(f"{k}={json.dumps(d.get(k))}" for k in sys.argv[2:]))
sys.exit(1 if missing else 0)' "$work/hf.json" "$@" 2>/dev/null); then got=pass; else got=fail; fi
  report pass "$got" "hf $repo/$file" "at $rev (sha256 $(sha256sum "$work/hf.json" | cut -d' ' -f1)): $fields"
}

echo "# verify-pins.sh run at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git_tag pass byterover-cli https://github.com/campfirein/byterover-cli.git v3.16.1 1f4609c18ca735810860b3ba9178cae2dd8a67b0
git_tag pass mirix https://github.com/Mirix-AI/MIRIX.git v0.1.6 0f3fbdb5e085ccceb6254e2a4a128a8957dac55a
git_tag pass colpali-engine https://github.com/illuin-tech/colpali.git v0.3.13 174055b00d4a36f672c6f915f2bdd0002e4fc9ee
git_tag pass vidore-benchmark https://github.com/illuin-tech/vidore-benchmark.git v5.0.0 d167f9ce6be840c5d887aa5cb1c01d2060485c93
git_tag fail must-fail-wrong-commit https://github.com/illuin-tech/vidore-benchmark.git v5.0.0 174055b00d4a36f672c6f915f2bdd0002e4fc9ee
git_commit mirix-main https://github.com/Mirix-AI/MIRIX.git 8cb06a62bbb7c478beb33dd4f2815696a72df482 main
git_commit colpali-main https://github.com/illuin-tech/colpali.git 97487f8871ff4d5d2284411fe61bdcd2cfe99894 main
git_commit vidore-benchmark-main https://github.com/illuin-tech/vidore-benchmark.git a70f23af8bb3b33efe8a4a6c6c15a6e2d978035e main
pypi pass mirix 0.1.7 mirix-0.1.7-py3-none-any.whl ead9e0ecd33218164a319749281d3bb3d5de677e5ab1afad6ccaa3910139af45
pypi pass mirix 0.1.7 mirix-0.1.7.tar.gz d6650d24d28fb110244daa873b11215c480c80ae2e4e0d7c65ab9c37e227b5a5
pypi pass colpali-engine 0.3.13 colpali_engine-0.3.13-py3-none-any.whl 4f6225a4368cd17716fa8c2e0f20024490c745a1d5f84afab7e4d71790f48002
pypi pass colpali-engine 0.3.18 colpali_engine-0.3.18-py3-none-any.whl 9f04fa89d123b174a9c9e5fa31824776644e9331c37c1d79768e16e3fe5be9d4
pypi fail colpali-engine 0.3.13 colpali_engine-0.3.13-py3-none-any.whl 9f04fa89d123b174a9c9e5fa31824776644e9331c37c1d79768e16e3fe5be9d4
pypi pass vidore-benchmark 5.0.0 vidore_benchmark-5.0.0-py3-none-any.whl ad2b214127c807a9cd557ccce9c10f853e7ddbade563c95bb5b7f8735012a7b6
pypi pass vidore-benchmark 5.0.0 vidore_benchmark-5.0.0.tar.gz cb3d1a68cfc5542d3aca50b7e06ab630203c6fef0e19c18da78a10e7eeeeb80c
npm_pin byterover-cli@3.16.1 sha512-uI6zETcy5QO6H29/sdn4BKGWzJl658sjHWxcpO+LHYcmxQj1mAmmi9lluqQZYoXXrnrbp+an8NYhjd5MKmDTcw== dfb0b176dd93c0cfd2a751a233275eee51d28678
hf_rev models vidore/colpali-v1.3 b5c6dd62125326e6f0b540c1f7b36e901cdc0a11
hf_rev models vidore/colpaligemma-3b-pt-448-base 30ab955d073de4a91dc5a288e8c97226647e3e5a
hf_rev datasets vidore/tabfquad_test_subsampled 16c8e633612fbda7400bfcbbc31d61a7534f580f
hf_fields vidore/colpali-v1.3 b5c6dd62125326e6f0b540c1f7b36e901cdc0a11 adapter_config.json base_model_name_or_path
hf_fields vidore/colqwen2.5-v0.2 main adapter_config.json base_model_name_or_path
hf_fields vidore/colqwen2.5-base main config.json architectures model_type
hf_fields vidore/colqwen2-v1.0 main adapter_config.json base_model_name_or_path
echo "# every expectation met: $([ "$bad" -eq 0 ] && echo yes || echo no)"
exit "$bad"
