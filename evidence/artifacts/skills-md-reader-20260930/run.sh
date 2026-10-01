#!/usr/bin/env bash
# Reproduces this receipt: every step's command, UTC start and end and exit status go to log.txt, with the checkout
# written as <checkout> and the scratch directory as <scratch>. Network: npm (the registry) and git fetch from GitHub
# (the catalog's sources at their pins); no gh REST calls, no tokens, nothing written outside <scratch>.
#
#   bash run.sh <checkout> <scratch>
#
# <checkout> is the repository at the commit under test (skill_md.mjs, skills-yaml.pin.json, the skills catalog).
set -u
CHECKOUT=$(cd "$1" && pwd); SCRATCH=$(mkdir -p "$2" && cd "$2" && pwd); HERE=$(cd "$(dirname "$0")" && pwd)
H=$CHECKOUT/tools/sota-convergence/landscape-sweep
export HOME=$SCRATCH/home npm_config_cache=$SCRATCH/npm-cache npm_config_update_notifier=false TMPDIR=$SCRATCH/tmp
export DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 CI=1
unset GITHUB_TOKEN GH_TOKEN
mkdir -p "$HOME" "$TMPDIR" "$SCRATCH/out"
cd "$SCRATCH" || exit 2
LOG=$SCRATCH/log.txt; : > "$LOG"
step() {  # step <name> <command...>: runs it, logs it on one line sanitized and without trailing blanks, keeps going
  local name=$1; shift
  local start; start=$(date -u +%FT%TZ)
  "$@" > "out/$name.stdout" 2> "out/$name.stderr"; local status=$?
  printf '%s\t%s\t%s\texit %s\t%s\n' "$name" "$start" "$(date -u +%FT%TZ)" "$status" "$(printf '%s' "$*" | tr '\n\t' '  ')" \
    | sed -e "s#$HERE#<receipt>#g" -e "s#$CHECKOUT#<checkout>#g" -e "s#$SCRATCH#<scratch>#g" -e 's/[[:space:]]*$//' >> "$LOG"
  return 0
}
step versions sh -c 'node --version; npm --version; git --version; python3 --version'
# Inputs: the catalog's GitHub sources at their pins, and the edge cases.
step corpus python3 "$HERE/corpus.py" "$CHECKOUT/catalogs/landscape/skills-lifecycle.json" "$SCRATCH/git" "$SCRATCH/corpus.json"
step edge python3 "$HERE/edge_cases.py" "$SCRATCH/edge.json"
# What source_reviews.py's symlink rule changes on those sources' trees at their pins.
step symlinks python3 "$HERE/symlink_impact.py" "$CHECKOUT" "$SCRATCH/git"
# The pinned yaml (the pin's install command), yaml 2.9.1 for the version comparison, and the skills CLI as the
# manifest's cli.install makes it, whose own yaml npm resolves at install time.
step install-yaml-2.9.0 npm install --prefix "$SCRATCH/yaml-2.9.0" --ignore-scripts --no-audit --no-fund --save-exact yaml@2.9.0
step install-yaml-2.9.1 npm install --prefix "$SCRATCH/yaml-2.9.1" --ignore-scripts --no-audit --no-fund --save-exact yaml@2.9.1
step install-skills-cli npm install --global --prefix "$SCRATCH/skills-1.7.0" skills@1.7.0
step pack sh -c "cd '$SCRATCH/out' && npm pack skills@1.7.0 yaml@2.9.0 yaml@2.9.1 --json"
# validate.yml's provisioning step with the ubuntu-24.04 image's npm (10.9.8) and the reader under its Node.js
# (22.23.2, the nodejs.org tarball checked against its SHASUMS256.txt): see ci_step.py.
step install-npm-10 npm install --prefix "$SCRATCH/npm-10" --no-audit --no-fund npm@10.9.8
step fetch-node-22 sh -c "cd '$SCRATCH' && curl --fail --silent --show-error --location --retry 3 -o SHASUMS256.txt https://nodejs.org/dist/v22.23.2/SHASUMS256.txt && curl --fail --silent --show-error --location --retry 3 -o node-v22.23.2-linux-x64.tar.xz https://nodejs.org/dist/v22.23.2/node-v22.23.2-linux-x64.tar.xz && grep ' node-v22.23.2-linux-x64.tar.xz\$' SHASUMS256.txt | sha256sum --check && tar -xJf node-v22.23.2-linux-x64.tar.xz"
step ci-step python3 "$HERE/ci_step.py" "$CHECKOUT" "$SCRATCH/ci" "$SCRATCH/npm-10/node_modules/.bin" \
  "$SCRATCH/node-v22.23.2-linux-x64/bin/node" "$SCRATCH/out/yaml-2.9.0.tgz"
step registry sh -c 'npm view skills@1.7.0 dependencies dist.integrity gitHead --json; npm view yaml dist-tags --json; npm view yaml@2.9.0 dist.integrity gitHead --json; npm view yaml@2.9.1 dist.integrity gitHead --json'
PKG=$SCRATCH/skills-1.7.0/lib/node_modules/skills
step cli-yaml-version node -e "console.log(require('$PKG/node_modules/yaml/package.json').version)"
# The oracles: the CLI's own parseSkillMd sliced from its dist/cli.mjs, with the yaml its install resolved and with 2.9.0.
for set in corpus edge; do
  step "oracle-cli-$set" node "$HERE/cli_oracle.mjs" "$PKG" "$PKG" "$SCRATCH/$set.json" "$SCRATCH/out/oracle-cli-$set.json"
  step "oracle-290-$set" node "$HERE/cli_oracle.mjs" "$PKG" "$SCRATCH/yaml-2.9.0" "$SCRATCH/$set.json" "$SCRATCH/out/oracle-290-$set.json"
  # The reader under test, with the pinned install, against both oracles.
  step "compare-$set" python3 "$HERE/compare.py" "$H/skill_md.mjs" "$SCRATCH/yaml-2.9.0" "$SCRATCH/$set.json" \
    "$SCRATCH/out/reader-$set.json" "cli-installed-yaml=$SCRATCH/out/oracle-cli-$set.json" "yaml-2.9.0=$SCRATCH/out/oracle-290-$set.json"
  # The installed CLI end to end: every file as skills/c<NNNN>/SKILL.md plus a planted invalid and a planted valid copy.
  step "fixture-$set" python3 - "$SCRATCH/$set.json" "$SCRATCH/fixture-$set" "$SCRATCH/out/fixture-$set-index.json" <<'EOF'
import base64, json, os, shutil, sys
corpus, root, index_path = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
shutil.rmtree(root, ignore_errors=True)
index = {}
for number, key in enumerate(sorted(key for key, entry in corpus.items() if "base64" in entry)):
    os.makedirs(f"{root}/skills/c{number:04d}")
    open(f"{root}/skills/c{number:04d}/SKILL.md", "wb").write(base64.b64decode(corpus[key]["base64"]))
    index[f"c{number:04d}"] = key
for folder, text in (("zz-planted-invalid", "---\nname: zz-planted-invalid\n---\n\nNo description.\n"),
                     ("zz-planted-valid", "---\nname: zz-planted-valid-7f3a\ndescription: A planted valid copy.\n---\n")):
    os.makedirs(f"{root}/skills/{folder}")
    open(f"{root}/skills/{folder}/SKILL.md", "w").write(text)
json.dump(index, open(index_path, "w"))
print(len(index), "folders and 2 planted")
EOF
  step "e2e-$set" sh -c "cd '$SCRATCH' && timeout 600 '$SCRATCH/skills-1.7.0/bin/skills' add ./fixture-$set --list > '$SCRATCH/out/cli-$set.stdout' 2> '$SCRATCH/out/cli-$set.stderr'"
  step "e2e-compare-$set" python3 "$HERE/e2e_compare.py" "$SCRATCH/out/fixture-$set-index.json" "$SCRATCH/out/reader-$set.json" \
    "$SCRATCH/out/cli-$set.stdout" "$SCRATCH/out/cli-$set.stderr"
done
# The yaml version delta: oracle results under the two releases, and a random differential of the changed code path.
step oracle-versions python3 -c "
import json, sys
for s in ('corpus', 'edge'):
    a = json.load(open('$SCRATCH/out/oracle-290-%s.json' % s))['results']; b = json.load(open('$SCRATCH/out/oracle-cli-%s.json' % s))['results']
    print(s, len(a), 'differing', sum(a[k] != b[k] for k in a))
"
step yaml-random node "$HERE/yaml_versions.mjs" "$SCRATCH/yaml-2.9.0" "$SCRATCH/yaml-2.9.1" 200000 20260930
# Negative controls: each must fail. A reader that does not strip terminal escapes, one that skips parseSkillMd's string
# check, an end-to-end comparison fed one flipped verdict, and a tampered install.
mkdir -p "$SCRATCH/mutant-sanitize" "$SCRATCH/mutant-typeof"
cp "$H/skills-yaml.pin.json" "$SCRATCH/mutant-sanitize/"; cp "$H/skills-yaml.pin.json" "$SCRATCH/mutant-typeof/"
sed 's/return stripTerminalEscapes(str)$/return str/' "$H/skill_md.mjs" > "$SCRATCH/mutant-sanitize/skill_md.mjs"
sed "s/typeof data.name !== 'string' || typeof data.description !== 'string'/false/" "$H/skill_md.mjs" > "$SCRATCH/mutant-typeof/skill_md.mjs"
step control-mutants sh -c "cmp -s '$H/skill_md.mjs' '$SCRATCH/mutant-sanitize/skill_md.mjs' && echo 'sanitize mutant unchanged'; cmp -s '$H/skill_md.mjs' '$SCRATCH/mutant-typeof/skill_md.mjs' && echo 'typeof mutant unchanged'; echo mutants written"
step control-sanitize python3 "$HERE/compare.py" "$SCRATCH/mutant-sanitize/skill_md.mjs" "$SCRATCH/yaml-2.9.0" "$SCRATCH/edge.json" \
  "$SCRATCH/out/mutant-sanitize-edge.json" "cli-installed-yaml=$SCRATCH/out/oracle-cli-edge.json"
step control-typeof python3 "$HERE/compare.py" "$SCRATCH/mutant-typeof/skill_md.mjs" "$SCRATCH/yaml-2.9.0" "$SCRATCH/edge.json" \
  "$SCRATCH/out/mutant-typeof-edge.json" "cli-installed-yaml=$SCRATCH/out/oracle-cli-edge.json"
step control-flip python3 - "$HERE/e2e_compare.py" "$SCRATCH/out" <<'EOF'
import json, subprocess, sys
compare, out = sys.argv[1], sys.argv[2]
answer = json.load(open(f"{out}/reader-corpus.json"))
flipped = next(item for item in answer["results"] if item["verdict"] == "skip")
flipped.update(verdict="take", name="flipped", display_name="flipped", reason=None)
json.dump(answer, open(f"{out}/reader-corpus-flipped.json", "w"))
done = subprocess.run([sys.executable, compare, f"{out}/fixture-corpus-index.json", f"{out}/reader-corpus-flipped.json",
                       f"{out}/cli-corpus.stdout", f"{out}/cli-corpus.stderr"], capture_output=True, text=True)
print(done.stdout.strip())
sys.exit(done.returncode)
EOF
cp -r "$SCRATCH/yaml-2.9.0" "$SCRATCH/yaml-tampered"
printf '\n' >> "$SCRATCH/yaml-tampered/node_modules/yaml/dist/compose/composer.js"
step control-tampered sh -c "printf '{\"items\": []}' | node '$H/skill_md.mjs' --install '$SCRATCH/yaml-tampered'"
step reader-empty sh -c "printf '{\"items\": []}' | node '$H/skill_md.mjs' --install '$SCRATCH/yaml-2.9.0'"
cat "$LOG"
# The compact result, from the retained outputs (not a logged step: it reads the finished log).
python3 "$HERE/summarize.py" "$SCRATCH" "$(git -C "$CHECKOUT" rev-parse HEAD)" "$SCRATCH/counts.json" "$CHECKOUT"
