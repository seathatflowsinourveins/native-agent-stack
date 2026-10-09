#!/usr/bin/env bash
# Prepare the selected north-star research runtime; run only by the coordinator
# as the user inside NativeStack2604. No paper/live entrypoint is invoked.
# The target gives >=3.12,<3.15, not an exact Python patch or a full package list.
# Supplemental pins and their provenance are explicit in this recipe's README.md
# and evidence/receipts/native-trading-runtime-2604-20261004.json.
# uv project/install commands:
# https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/projects.md
# https://github.com/astral-sh/uv/blob/0.12.17/docs/guides/install-python.md
# https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/dependencies.md
# https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md
set -Eeuo pipefail
umask 077

step=preconditions
result=FAIL
status_detail=preconditions
status_fd=1
temporary=''
readonly install_pid=$BASHPID
finish_install() {
    local code=$?
    trap - EXIT ERR
    [[ $BASHPID == "$install_pid" ]] || exit "$code"
    if [[ -n $temporary ]]; then rm -f -- "$temporary" || :; fi
    if ((code == 0)) && [[ $result == PASS ]]; then
        printf 'install | PASS\n' >&"$status_fd"
    elif [[ $result == BLOCKED ]]; then
        printf 'install | BLOCKED | %s\n' "$status_detail" >&"$status_fd"
    else
        printf 'install | FAIL | %s\n' "$step" >&"$status_fd"
    fi
    exit "$code"
}
install_error() { local code=$?; result=FAIL; exit "$code"; }
trap finish_install EXIT
trap install_error ERR
die() { printf '%s\n' "$1" >&2; result=FAIL; exit "$2"; }
blocked() {
    printf '%s\n' "$1" >&2
    result=BLOCKED; status_detail=$3
    exit "$2"
}
[[ ${WSL_DISTRO_NAME:-} == NativeStack2604 ]] || blocked 'Run inside NativeStack2604.' 64 wrong-distribution
(( EUID != 0 )) || blocked 'Run as the user, without sudo.' 64 root-user
for tool in uv git curl sha256sum docker env timeout mkdir mktemp mv uname cp rm dirname bash; do
    command -v "$tool" >/dev/null || blocked "Missing prerequisite: $tool" 69 "missing-$tool"
done

# Capture only the selected public daemon endpoint before clearing context state.
# https://github.com/docker/cli/blob/v29.8.1/docs/reference/commandline/context_inspect.md
# https://github.com/docker/cli/blob/v29.8.1/cli/command/cli.go#L406-L426
step=docker-endpoint
# Drop inherited broker/provider variables, active Python settings and native
# credential-helper configuration. HOME itself is never reassigned by this script.
if [[ ${TRADING_INSTALL_CLEAN:-} != 1 ]]; then
    if ! docker_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null); then
        blocked 'BLOCKED: cannot read the selected Docker context endpoint.' 69 docker-context-unavailable
    fi
    case "$docker_host" in
        ''|unix:///var/run/docker.sock|unix:///run/docker.sock)
            blocked 'BLOCKED: a non-default rootless Docker endpoint is required.' 69 docker-endpoint-unavailable ;;
    esac
    exec env -i PATH="$PATH" HOME="$HOME" WSL_DISTRO_NAME="$WSL_DISTRO_NAME" \
        TRADING_INSTALL_CLEAN=1 TRADING_DOCKER_HOST="$docker_host" bash --noprofile --norc "$0"
fi
readonly docker_host=${TRADING_DOCKER_HOST:-}
case "$docker_host" in
    ''|unix:///var/run/docker.sock|unix:///run/docker.sock)
        blocked 'BLOCKED: the captured rootless Docker endpoint is unavailable.' 69 docker-endpoint-unavailable ;;
esac
# Reserve stdout for the single EXIT status, including unexpected command errors.
exec 3>&1 1>&2
status_fd=3

readonly project="$HOME/projects/us-equities-runtime"
# Both the pinned adapter requirements and accepted rc5 receipt use Python 3.12.
# https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/requirements.txt
# https://github.com/seathatflowsinourveins/native-agent-stack/blob/d323b53437e025be3d054b9b5e4d292fe396c75e/evidence/receipts/native-nautilus-v2-20260920.json
readonly owner='native-stack-trading-2604-v1'
readonly completion='native-stack-trading-2604-no-dvc-r4'
script_directory=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
readonly script_directory
readonly sync_vector_hash=fd150296759b07d037b1dfd65048aaf49a84306dc0488df90ec4a08da481f7f1
[[ ! -L "$script_directory/sync-trading-2604.sh" && -f "$script_directory/sync-trading-2604.sh" ]] || die 'Shared sync vector is missing or symlinked.' 65
printf '%s  %s\n' "$sync_vector_hash" "$script_directory/sync-trading-2604.sh" | sha256sum --check --status
# BEGIN shared-sync-source
source "$script_directory/sync-trading-2604.sh"
# END shared-sync-source
readonly lock_bundle="$script_directory/trading-2604-runtime"
readonly project_hash=aa370e42e29dc2419e586358254ff2e821df48a693aa9a3ee16b65d30036ee0b
readonly lock_hash=f451ef979cdb1ae3686a30df1c883c257402b32753478c1f9c686c057e9c3989
# Only exact recorded bundles may migrate toward the published final bundle.
# Prior hashes are migration inputs and inverse records, never new acceptance.
readonly accepted_project_hash=30f47dfbcb247c01e8e3ed8733fbf63bf5de6ad4ea7e4c0807e3ea484b975958
readonly accepted_lock_hash=1fb9f8ca6fef9c47a4ded826ddf20012f78d6643926cce3a36b86c674f55eb9c
readonly intermediate_project_hash=25d95481cd5cf509ffd4ce60fc8848d489b53fc402ae4dbd3cc65d528354c270
readonly intermediate_lock_hash=17221888e8f3017d61e8a96eacd87a8bd8eda60ff6b1738eb683ed52980e175a
readonly previous_project_hash=36b85fd48566fedff258ec4a8bef496cace0ea00954afd7c9255bffda0894fdb
readonly previous_lock_hash=4c98672d14147a1be712bf788b495cf318705631cbf5e04ebe230c8a13c516c2
readonly recorded_project_hash=581bbb38a265068791c1a8c92435f9859876fd613d3c2c87d618a223376b01e0
readonly recorded_lock_hash=c6b5f25cd3198c1b847c1cb602fe5441dce7e038aa16976c46ecf5f0beb7b086
readonly engine_commit=1b0a49d2792a9432a3aca3fcb617ce7a630d905e
readonly adapter_commit=dfeea13377cfb15936f856d9ed8df3c6575a7895
readonly quickstart_hash=487e6807dedd1a38062638eb671f6110799451611819542bf0f0c10646cb2c53
# Version 10.45.1j is in the pinned gnzsnz README. Its image label identifies
# build c147d206b8d5d8cd329feced09f02a9df61e84cc; e19aa0 is the documentation pin.
# https://github.com/gnzsnz/ib-gateway-docker/blob/e19aa0bebe5d0ddd55c6d0e25549380f9c7d1bf7/README.md
readonly ib_image='ghcr.io/gnzsnz/ib-gateway@sha256:91165c0752ca534c0dad3c40683ae7c2745974d4d277651a90e90411ca609d8d'
# LEAN tag 18149, source 33e3945f2faa95308d972dfd3d7b762f7743d1d5.
# https://github.com/QuantConnect/Lean/blob/33e3945f2faa95308d972dfd3d7b762f7743d1d5/Dockerfile
# Pull-only syntax: https://github.com/docker/cli/blob/v29.8.1/docs/reference/commandline/image_pull.md
readonly lean_image='docker.io/quantconnect/lean@sha256:70071d1bbb90385deb60c7d20bc3830c7f4c79f6c09c5d1ade9196c009f68861'

step=foundation
[[ $(uv --version) == "uv $uv_pin "* ]] || blocked "Requires uv $uv_pin from the foundation lane." 69 uv-version
[[ $(uname -m) == x86_64 ]] || blocked 'This recipe targets Linux x86_64.' 69 architecture
step=project-ownership
[[ ! -L "$HOME/projects" ]] || die 'The projects parent must not be a symlink.' 73
[[ ! -e "$HOME/projects" || ( -d "$HOME/projects" && -O "$HOME/projects" ) ]] || die 'The projects parent must be an owned directory.' 73
[[ ! -L "$project" ]] || die 'The runtime path must not be a symlink.' 73
[[ ! -L "$project/.trading-2604-owner" ]] || die 'The ownership marker must not be a symlink.' 73
if [[ -e "$project" ]]; then
    [[ -d "$project" && -O "$project" ]] || die 'Runtime directory must be owned by this user.' 73
    if [[ ! -f "$project/.trading-2604-owner" ]]; then
        shopt -s nullglob dotglob
        entries=("$project"/*)
        ((${#entries[@]} == 0)) || die 'Refusing to adopt a nonempty unowned runtime directory.' 73
        shopt -u nullglob dotglob
    else
        IFS= read -r recorded_owner < "$project/.trading-2604-owner"
        [[ $recorded_owner == "$owner" ]] || die 'Runtime ownership marker differs.' 73
    fi
fi
mkdir -p "$project"
rm -f -- "$project/.trading-2604-complete"
printf '%s\n' "$owner" > "$project/.trading-2604-owner"
for path in .python .venv .uv-cache .install-home .docker-config .upstream vendor; do
    [[ ! -L "$project/$path" ]] || die "Owned runtime subdirectory is a symlink: $path" 73
done
mkdir -p "$project/.python" "$project/.uv-cache" "$project/.install-home" \
    "$project/.docker-config" "$project/.upstream" "$project/vendor"

# All managed interpreter, environment, cache and installer state is project-local.
# --no-bin prevents changes to ~/.local/bin and the user's default Python.
safe=(env -i PATH="$PATH" HOME="$project/.install-home" \
    UV_CACHE_DIR="$project/.uv-cache" UV_PYTHON_INSTALL_DIR="$project/.python" \
    UV_PROJECT_ENVIRONMENT="$project/.venv" UV_PYTHON_PREFERENCE=only-managed \
    PYTHONDONTWRITEBYTECODE=1 GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
    DOCKER_CONFIG="$project/.docker-config" DOCKER_HOST="$docker_host")
step=docker-daemon
if ! "${safe[@]}" timeout --kill-after=5s 30s docker info --format '{{.ID}}' >/dev/null 2>&1; then
    blocked 'BLOCKED: no Docker daemon answers at the captured rootless endpoint.' 69 docker-daemon-unavailable
fi
step=python-install
"${safe[@]}" uv --no-config python install --no-bin "$python_pin"
# UV_PYTHON_PREFERENCE=only-managed (in safe) already restricts discovery to managed interpreters; uv rejects
# --managed-python together with a --python-preference (coordinator fix 2026-10-04 after the first 2604 run).
runtime_python=$("${safe[@]}" uv --no-config python find --system --no-project --no-python-downloads "$python_pin")
[[ $runtime_python == "$project/.python/"* ]] || die 'Interpreter resolved outside the project.' 73
printf '%s\n' "$python_pin" > "$project/.python-version"

# Exact versions implement the packages' documented PyPI install routes through
# uv's documented project interface. The bundled, verified lock retains every
# transitive version and hash, including MLflow's requested MCP extra.
requirements=(
    # https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/installation.md
    'nautilus-trader==2.0.0rc5'
    # rc5 quickstart explicitly requires NumPy and pandas; its wheel dependencies=[]:
    # https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py
    'numpy==2.5.3' 'pandas==3.0.6'
    # https://github.com/alpacahq/alpaca-py/blob/cc4cb3b7ba50ae250e621983c2779047fb16bb28/README.md
    'alpaca-py==0.44.0'
    # https://pypi.org/pypi/edgartools/5.61.1/json
    'edgartools==5.61.1'
    # https://github.com/gerrymanoim/exchange_calendars/blob/dbe38b1f6887434bbdd1a7d2df6ff8f1742a048a/README.md
    'exchange-calendars==4.13.2'
    # https://github.com/duckdb/duckdb-python/blob/b236c8194ed14c7a7c685e0534dde501cc855b3a/README.md
    'duckdb==1.5.5'
    # https://github.com/unionai-oss/pandera/blob/62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6/README.md
    'pandera[pandas]==0.33.1'
    # https://pypi.org/pypi/skfolio/1.7.0/json
    'skfolio==1.7.0'
    # https://github.com/lightgbm-org/LightGBM/blob/8f7036f03627054d5a54a6f965b13f4b9ff2cb63/README.md
    'lightgbm==4.7.0'
    # https://github.com/cloudQuant/fincore/blob/576459c495a8f7ff839f55e0d3057daa636174cc/README.md
    'fincore==0.5.1'
    # https://github.com/mlflow/mlflow/blob/32792afe5b0183fce10532d3a023f5cfa8612d09/docs/docs/classic-ml/getting-started/quickstart.mdx
    # Definitive experiment-tracking default includes MCP; only install the extra.
    # https://github.com/mlflow/mlflow/blob/32792afe5b0183fce10532d3a023f5cfa8612d09/docs/docs/genai/mcp/index.mdx
    'mlflow[mcp]==3.16.1'
    # https://github.com/bashtage/arch/blob/038d78b709e75f2590890757af32705817a6fad8/README.md
    'arch==8.0.0'
    # https://github.com/eslazarev/purged-cross-validation/blob/aee1215c58d65a60a1d6af4b483f929fecde76e2/README.md
    'purgedcv==0.1.10'
)
dev_requirements=('pytest==9.1.1') # https://pypi.org/pypi/pytest/9.1.1/json
# These public metadata bytes were copied from the measured final native bundle.
# Its locked dev sync and dependency check are imported evidence, not a new run.
# Copying the byte-verified metadata avoids another target-host resolution.
# Both files are validated before either is replaced. Only
# the exact approved metadata (including an interrupted migration) is accepted;
# arbitrary local edits are refused. Each replacement is atomic within the project.
# https://github.com/astral-sh/uv/blob/0.12.17/docs/concepts/projects/sync.md
step=locked-project
[[ ! -L "$lock_bundle" && -d "$lock_bundle" ]] || die 'Verified runtime lock bundle is missing or symlinked.' 65
for entry in "pyproject.toml|$project_hash|$previous_project_hash|$recorded_project_hash|$accepted_project_hash|$intermediate_project_hash" "uv.lock|$lock_hash|$previous_lock_hash|$recorded_lock_hash|$accepted_lock_hash|$intermediate_lock_hash"; do
    IFS='|' read -r filename expected_hash previous_hash recorded_hash accepted_hash intermediate_hash <<< "$entry"
    [[ ! -L "$lock_bundle/$filename" && -f "$lock_bundle/$filename" ]] || die "Verified bundle file is unavailable: $filename" 65
    printf '%s  %s\n' "$expected_hash" "$lock_bundle/$filename" | sha256sum --check --status
    [[ ! -L "$project/$filename" ]] || die "Owned project file is symlinked: $filename" 73
    if [[ -e "$project/$filename" ]]; then
        [[ -f "$project/$filename" && -O "$project/$filename" ]] || die "Owned project file is not an owned regular file: $filename" 73
        if ! printf '%s  %s\n' "$expected_hash" "$project/$filename" | sha256sum --check --status &&
            ! printf '%s  %s\n' "$previous_hash" "$project/$filename" | sha256sum --check --status &&
            ! printf '%s  %s\n' "$recorded_hash" "$project/$filename" | sha256sum --check --status &&
            ! printf '%s  %s\n' "$accepted_hash" "$project/$filename" | sha256sum --check --status &&
            ! printf '%s  %s\n' "$intermediate_hash" "$project/$filename" | sha256sum --check --status; then
            die "Owned project file differs from all verified bundles: $filename" 73
        fi
    fi
done
for entry in "pyproject.toml|$project_hash" "uv.lock|$lock_hash"; do
    IFS='|' read -r filename expected_hash <<< "$entry"
    if [[ ! -f "$project/$filename" ]] || ! printf '%s  %s\n' "$expected_hash" "$project/$filename" | sha256sum --check --status; then
        temporary=$(mktemp "$project/$filename.XXXXXX")
        cp -- "$lock_bundle/$filename" "$temporary"
        mv -- "$temporary" "$project/$filename"
        temporary=''
    fi
done
"${safe[@]}" "$runtime_python" -I - "$project/pyproject.toml" "$python_pin" "${dev_requirements[0]}" "${requirements[@]}" <<'PY'
import sys
import tomllib
with open(sys.argv[1], "rb") as f:
    manifest = tomllib.load(f)
project = manifest["project"]
assert project["name"] == "us-equities-runtime"
assert project["requires-python"] == "==" + sys.argv[2], "Owned project interpreter pin differs"
assert sys.version.split()[0] == sys.argv[2]
assert sorted(project["dependencies"]) == sorted(sys.argv[4:]), "Direct requirement matrix differs"
assert manifest["dependency-groups"]["dev"] == [sys.argv[3]], "Development requirement matrix differs"
PY
# Reuse the installed interpreter for the measured locked-dev sync vector.
# A fresh prefix still uses the verified managed interpreter to create its venv.
if [[ -x "$project/.venv/bin/python" ]]; then runtime_python="$project/.venv/bin/python"; fi
# BEGIN shared-sync-call
sync_trading_2604
# END shared-sync-call

# Retain unchanged upstream code now, so acceptance requires no network.
# No market dataset is fetched; this quickstart generates its own synthetic bars.
quickstart="$project/.upstream/nautilus-quickstart.py"
step=quickstart-source
if [[ ! -f "$quickstart" ]] || ! printf '%s  %s\n' "$quickstart_hash" "$quickstart" | sha256sum --check --status; then
    temporary=$(mktemp "$project/.upstream/quickstart.XXXXXX")
    "${safe[@]}" curl --fail --silent --show-error --location --proto '=https' \
        "https://raw.githubusercontent.com/nautechsystems/nautilus_trader/$engine_commit/docs/getting_started/quickstart.py" \
        --output "$temporary"
    printf '%s  %s\n' "$quickstart_hash" "$temporary" | sha256sum --check --status
    mv -- "$temporary" "$quickstart"
    temporary=''
fi

# adaptive-paper has no distributable project: preserve its selected source as
# a separate sparse checkout. Do not execute runner.py, recovery.py or LiveNode.
# https://github.com/seathatflowsinourveins/native-agent-stack/blob/dfeea13377cfb15936f856d9ed8df3c6575a7895/blueprints/us-equities/adaptive-paper/README.md
# https://github.com/git/git/blob/v2.43.0/Documentation/git-sparse-checkout.txt
# https://github.com/git/git/blob/v2.43.0/Documentation/git-fetch.txt
# https://github.com/git/git/blob/v2.43.0/Documentation/git-clone.txt
adapter="$project/vendor/adaptive-paper"
step=adapter-source
[[ ! -L "$adapter" ]] || die 'Adapter checkout must not be a symlink.' 73
if [[ ! -d "$adapter/.git" ]]; then
    [[ ! -e "$adapter" ]] || die 'Refusing to replace an existing adapter directory.' 73
    "${safe[@]}" git init "$adapter"
fi
if adapter_origin=$("${safe[@]}" git -C "$adapter" remote get-url origin 2>/dev/null); then
    [[ $adapter_origin == https://github.com/seathatflowsinourveins/native-agent-stack.git ]] || die 'Adapter origin differs from the public source.' 73
else
    "${safe[@]}" git -C "$adapter" remote add origin https://github.com/seathatflowsinourveins/native-agent-stack.git
fi
# A clean status is meaningful only after checkout has created the index.
# An interrupted initial setup can resume only if it has no worktree files.
if [[ -f "$adapter/.git/index" ]]; then
    adapter_status=$("${safe[@]}" git -C "$adapter" status --porcelain)
    [[ -z $adapter_status ]] || die 'Adapter checkout has local changes.' 73
else
    adapter_untracked=$("${safe[@]}" git -C "$adapter" ls-files --others)
    [[ -z $adapter_untracked ]] || die 'Unindexed adapter directory contains local files.' 73
fi
if [[ ! -f "$adapter/.git/index" || $("${safe[@]}" git -C "$adapter" rev-parse --verify HEAD 2>/dev/null || true) != "$adapter_commit" ]]; then
    "${safe[@]}" git -C "$adapter" fetch --depth 1 --filter=blob:none origin "$adapter_commit"
    "${safe[@]}" git -C "$adapter" sparse-checkout set --no-cone --stdin <<'PATHS'
/blueprints/us-equities/adaptive-paper/*.py
/blueprints/us-equities/adaptive-paper/requirements.txt
/blueprints/us-equities/adaptive-paper/README*.md
/blueprints/us-equities/adaptive-paper/source-hashes.json
PATHS
    "${safe[@]}" git -C "$adapter" -c advice.detachedHead=false checkout --detach FETCH_HEAD
fi
[[ $("${safe[@]}" git -C "$adapter" rev-parse HEAD) == "$adapter_commit" ]] || die 'Adapter source pin differs.' 65
[[ -f "$adapter/.git/index" ]] || die 'Adapter checkout has no index.' 65
# Check staged, unstaged and untracked files even when HEAD already matches.
# https://github.com/git/git/blob/v2.43.0/Documentation/git-status.txt
adapter_status=$("${safe[@]}" git -C "$adapter" status --porcelain)
[[ -z $adapter_status ]] || die 'Adapter checkout has local changes.' 73
"${safe[@]}" git -C "$adapter" diff --exit-code HEAD -- blueprints/us-equities/adaptive-paper
printf '%s  %s\n' 50c9cff32944b45abb4c4aff20d2235688f5240c52e892a623aa6e19ecd9b037 \
    "$adapter/blueprints/us-equities/adaptive-paper/native_adapter.py" | sha256sum --check --status

# Images are staged only. No run/create/compose-up or gateway sign-in occurs.
# An available Docker engine is a foundation prerequisite; no engine/service
# installation, privilege change, Docker login or WSL restart is attempted.
step=ib-gateway-image
"${safe[@]}" docker image pull --platform linux/amd64 "$ib_image"
step=lean-image
"${safe[@]}" docker image pull --platform linux/amd64 "$lean_image"
step=image-verification
"${safe[@]}" docker image inspect --format '{{json .RepoDigests}}' "$ib_image" > "$project/.upstream/ib-gateway-image-digests.json"
"${safe[@]}" docker image inspect --format '{{json .RepoDigests}}' "$lean_image" > "$project/.upstream/lean-image-digests.json"
step=completion-marker
temporary=$(mktemp "$project/.trading-2604-complete.XXXXXX")
printf '%s\n' "$completion" > "$temporary"
mv -- "$temporary" "$project/.trading-2604-complete"
temporary=''
result=PASS
exit 0
