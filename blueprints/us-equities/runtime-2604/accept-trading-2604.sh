#!/usr/bin/env bash
# Offline runtime acceptance only. Each check emits: name | status | exit.
# Run inside NativeStack2604 after install-trading-2604.sh. No install/sync/run
# through uv occurs here; only the existing interpreter executes examples.
# Namespace/clear-environment/read-only-mount options are upstream Bubblewrap:
# https://github.com/containers/bubblewrap/blob/v0.9.0/bubblewrap.c
# Isolation intent: native-nautilus-v2-20260920.json at native-agent-stack d323b534.
# That receipt records prose, not the exact argv/mount set used below.
set -Euo pipefail
umask 077
readonly project="$HOME/projects/us-equities-runtime"
readonly python="$project/.venv/bin/python"
readonly adapter="$project/vendor/adaptive-paper"
readonly quickstart_hash=487e6807dedd1a38062638eb671f6110799451611819542bf0f0c10646cb2c53
readonly adapter_commit=dca821cca85dce3647fa7b488d5a23fbe5b85d4a
readonly ib_image='ghcr.io/gnzsnz/ib-gateway@sha256:91165c0752ca534c0dad3c40683ae7c2745974d4d277651a90e90411ca609d8d'
readonly lean_image='docker.io/quantconnect/lean@sha256:70071d1bbb90385deb60c7d20bc3830c7f4c79f6c09c5d1ade9196c009f68861'

# Version/import probes are integration checks, not upstream test-suite passes.
specs=(
    'nautilus-trader|2.0.0rc5|nautilus_trader'
    'numpy|2.5.3|numpy'
    'pandas|3.0.6|pandas'
    'alpaca-py|0.44.0|alpaca'
    'edgartools|5.60.0|edgar'
    'exchange-calendars|4.13.2|exchange_calendars'
    'dvc|3.67.1|dvc'
    'duckdb|1.5.5|duckdb'
    'pandera|0.33.1|pandera.pandas'
    'skfolio|1.2.9|skfolio'
    'fincore|0.5.1|fincore.metrics.ratios'
    'mlflow|3.16.1|mlflow'
    'arch|8.0.0|arch'
    'purgedcv|0.1.10|purgedcv'
)
names=(offline_isolation python)
for spec in "${specs[@]}"; do
    IFS='|' read -r distribution expected module <<< "$spec"
    names+=("import_$distribution")
done
names+=(ibkr_adapter alpaca_adapter_source alpaca_adapter_import nautilus_quickstart_sha256
    nautilus_quickstart duckdb_query pandera_example skfolio_example arch_example)

blocked() {
    local code=$1 name
    printf 'BLOCKED: %s\n' "${2:-acceptance prerequisites unavailable}" >&2
    for name in "${names[@]}"; do printf '%s | BLOCKED | %s\n' "$name" "$code"; done
    exit 1
}
[[ ${WSL_DISTRO_NAME:-} == NativeStack2604 && $EUID != 0 ]] || blocked 64
for tool in bwrap timeout docker env mkdir mktemp; do command -v "$tool" >/dev/null || blocked 69 "missing $tool"; done
[[ ! -L "$HOME/projects" && ! -L "$project" && -O "$project" && -x "$python" ]] || blocked 69
[[ ! -L "$project/.trading-2604-owner" && ! -L "$project/.trading-2604-complete" ]] || blocked 73
[[ -f "$project/.trading-2604-owner" && -d "$project/.python" && -d "$project/.upstream" ]] || blocked 69
IFS= read -r recorded_owner < "$project/.trading-2604-owner" || blocked 73
[[ $recorded_owner == native-stack-trading-2604-v1 ]] || blocked 73
[[ -f "$project/.trading-2604-complete" ]] || blocked 69 'installation completion marker is missing'
IFS= read -r recorded_completion < "$project/.trading-2604-complete" || blocked 73
[[ $recorded_completion == native-stack-trading-2604-hashed-build-r3 ]] || blocked 69 'installation completion marker is stale'
[[ -d "$adapter/.git" && -f "$project/.upstream/nautilus-quickstart.py" ]] || blocked 69
for path in .python .venv .upstream .install-home .docker-config vendor vendor/adaptive-paper acceptance; do
    [[ ! -L "$project/$path" ]] || blocked 73
done
[[ -d "$project/.install-home" && -d "$project/.docker-config" ]] || blocked 69

# Read only the context endpoint, then use it explicitly with a clean config.
# No image pull or container start occurs; failed staging cannot become 25/25.
if ! docker_host=$(docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null); then
    blocked 69 'selected Docker context endpoint is unavailable'
fi
case "$docker_host" in
    ''|unix:///var/run/docker.sock|unix:///run/docker.sock)
        blocked 69 'a non-default rootless Docker endpoint is required' ;;
esac
docker_safe=(env -i PATH="$PATH" HOME="$project/.install-home" \
    DOCKER_CONFIG="$project/.docker-config" DOCKER_HOST="$docker_host")
"${docker_safe[@]}" timeout --kill-after=5s 30s docker info --format '{{.ID}}' >/dev/null 2>&1 || \
    blocked 69 'no Docker daemon answers at the captured rootless endpoint'
"${docker_safe[@]}" timeout --kill-after=5s 30s docker image inspect "$ib_image" "$lean_image" >/dev/null 2>&1 || \
    blocked 69 'both pinned images must be staged before acceptance'

mkdir -p "$project/acceptance" >/dev/null 2>&1 || blocked 73
run_directory=$(mktemp -d "$project/acceptance/run.XXXXXXXX") || blocked 73
readonly run_directory
# Keep the synthetic sandbox home explicit without spelling a home/user/cache
# path that the publication scanner would mistake for a personal home directory.
readonly sandbox_home=/tmp/home

# Fresh network/process/user namespaces per check. No host home, /mnt, Docker
# socket, SSH/authentication store or provider configuration is mounted. Only
# the interpreter, venv, public staged source and one owned output directory.
# --clearenv discards inherited credentials; do not add --share-net.
sandbox=(timeout --kill-after=5s 180s bwrap --unshare-all --die-with-parent --new-session
    --clearenv --ro-bind /usr /usr --ro-bind-try /lib /lib --ro-bind-try /lib64 /lib64
    --ro-bind "$project/.venv" "$project/.venv" --ro-bind "$project/.python" "$project/.python"
    --ro-bind "$project/.upstream" /input --ro-bind "$adapter" /source
    --bind "$run_directory" /out --proc /proc --dev /dev --tmpfs /tmp --dir "$sandbox_home"
    --setenv HOME "$sandbox_home" --setenv PATH /usr/bin:/bin
    --setenv XDG_CACHE_HOME "$sandbox_home/.cache" --setenv PYTHONDONTWRITEBYTECODE 1
    --setenv MPLBACKEND Agg --setenv OMP_NUM_THREADS 1 --setenv OPENBLAS_NUM_THREADS 1
    --setenv DVC_NO_ANALYTICS 1 --setenv UV_OFFLINE 1 --setenv GIT_OPTIONAL_LOCKS 0 --chdir /out)
failed=0
last_exit=0
check() {
    local name=$1 code status
    shift
    if "${sandbox[@]}" "$@" > "$run_directory/$name.log" 2>&1; then
        code=0; status=PASS
    else
        code=$?; status=FAIL; failed=1
    fi
    printf '%s | %s | %s\n' "$name" "$status" "$code"
    last_exit=$code
}

# A denied namespace blocks every dependent example; never silently fall back
# to an online host process. This check makes no connection attempt.
if "${sandbox[@]}" "$python" -I -c 'import socket; assert {name for _, name in socket.if_nameindex()} <= {"lo"}' \
        > "$run_directory/offline_isolation.log" 2>&1; then
    printf 'offline_isolation | PASS | 0\n'
else
    isolation_exit=$?
    printf 'offline_isolation | FAIL | %s\n' "$isolation_exit"
    for name in "${names[@]:1}"; do printf '%s | BLOCKED | 69\n' "$name"; done
    exit 1
fi

check python "$python" -I -c 'import sys; assert sys.version.split()[0] == "3.12.3"; print(sys.version)'
for spec in "${specs[@]}"; do
    IFS='|' read -r distribution expected module <<< "$spec"
    check "import_$distribution" "$python" -I -c \
        'import importlib, importlib.metadata as m, sys; importlib.import_module(sys.argv[3]); actual=m.version(sys.argv[1]); print(actual); assert actual == sys.argv[2], (actual, sys.argv[2])' \
        "$distribution" "$expected" "$module"
done

# Config-class imports only: no construction of a gateway, client or node.
# https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/integrations/interactive_brokers.md
# Public rc5 exports are checked against the pinned Python facade and Rust module.
# https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/python/nautilus_trader/adapters/interactive_brokers/__init__.py
# MarketDataType is registered by the extension and imported through the facade's
# wildcard import; omission from the facade's __all__ does not forbid named imports.
# https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/crates/adapters/interactive_brokers/src/python/mod.rs#L98
check ibkr_adapter "$python" -I -c \
    'from nautilus_trader.adapters.interactive_brokers import InteractiveBrokersDataClientConfig, InteractiveBrokersExecutionClientConfig, MarketDataType'

# The separate adapter is staged source, not an official Nautilus Alpaca plugin.
# https://github.com/seathatflowsinourveins/native-agent-stack/blob/dca821cca85dce3647fa7b488d5a23fbe5b85d4a/blueprints/us-equities/adaptive-paper/native_adapter.py
check alpaca_adapter_source "$python" -I - "$adapter_commit" <<'PY'
import hashlib
from pathlib import Path
import subprocess
import sys
assert subprocess.check_output(["/usr/bin/git", "-C", "/source", "rev-parse", "HEAD"], text=True).strip() == sys.argv[1]
assert not subprocess.check_output(["/usr/bin/git", "-C", "/source", "status", "--porcelain"], text=True).strip(), "Adapter source has local changes"
path = Path("/source/blueprints/us-equities/adaptive-paper/native_adapter.py")
assert hashlib.sha256(path.read_bytes()).hexdigest() == "fbf530884c2ad3b9e0c2b1f989eda399531647cc1db3c56dc9bcac10174fea47"
PY
if ((last_exit == 0)); then
    check alpaca_adapter_import "$python" -I -c \
        'import sys; sys.path.insert(0,"/source/blueprints/us-equities/adaptive-paper"); import native_adapter'
else
    printf 'alpaca_adapter_import | BLOCKED | 65\n'
fi

# Unchanged documented quick backtest: 10,000 generated EUR/USD bars, SIM venue.
# https://github.com/nautechsystems/nautilus_trader/blob/1b0a49d2792a9432a3aca3fcb617ce7a630d905e/docs/getting_started/quickstart.py
check nautilus_quickstart_sha256 "$python" -I -c \
    'import hashlib, pathlib, sys; assert hashlib.sha256(pathlib.Path("/input/nautilus-quickstart.py").read_bytes()).hexdigest() == sys.argv[1]' "$quickstart_hash"
# Recheck the source hash in the process that executes it. Continue collecting
# independent checks after unrelated failures; unverified source never executes.
check nautilus_quickstart "$python" -I - "$quickstart_hash" <<'PY'
import hashlib
from pathlib import Path
import runpy
import sys
path = Path("/input/nautilus-quickstart.py")
assert hashlib.sha256(path.read_bytes()).hexdigest() == sys.argv[1]
runpy.run_path(str(path), run_name="__main__")
PY

# Query copied from the pinned upstream test, using an in-memory connection.
# https://github.com/duckdb/duckdb-python/blob/b236c8194ed14c7a7c685e0534dde501cc855b3a/tests/fast/api/test_duckdb_query.py
check duckdb_query "$python" -I - <<'PY'
import duckdb
with duckdb.connect(":memory:") as con:
    con.sql("create view v1 as select 42 i")
    rel = con.sql("select * from v1")
    assert rel.fetchall()[0][0] == 42
PY

# README object-schema example. The final equality assertion is our smoke guard.
# https://github.com/unionai-oss/pandera/blob/62f55e2dccf0a199cfe4d6ce3eda0c1d29e2e4e6/README.md
check pandera_example "$python" -I - <<'PY'
import pandas as pd
import pandera.pandas as pa
df = pd.DataFrame({"column1": [1, 2, 3], "column2": [1.1, 1.2, 1.3], "column3": ["a", "b", "c"]})
schema = pa.DataFrameSchema({
    "column1": pa.Column(int, pa.Check.ge(0)),
    "column2": pa.Column(float, pa.Check.lt(10)),
    "column3": pa.Column(str, [pa.Check.isin([*"abc"]), pa.Check(lambda series: series.str.len() == 1)]),
})
validated = schema.validate(df)
assert validated.equals(df)
print(validated)
PY

# README minimum-variance example; this selected loader opens a wheel-bundled
# gzip CSV through importlib.resources, with no remote fallback.
# https://github.com/skfolio/skfolio/blob/c99fcf71349e2df4a7a1033ee85ca2e9ced9abee/README.rst
# https://github.com/skfolio/skfolio/blob/c99fcf71349e2df4a7a1033ee85ca2e9ced9abee/src/skfolio/datasets/_base.py
check skfolio_example "$python" -I - <<'PY'
import numpy as np
from sklearn.model_selection import train_test_split
from skfolio.datasets import load_sp500_dataset
from skfolio.preprocessing import prices_to_returns
from skfolio.optimization import MeanRisk
prices = load_sp500_dataset()
X = prices_to_returns(prices)
X_train, X_test = train_test_split(X, test_size=0.33, shuffle=False)
model = MeanRisk()
model.fit(X_train)
portfolio = model.predict(X_test)
assert np.isfinite(model.weights_).all()
assert np.isclose(model.weights_.sum(), 1.0, atol=1e-5)
assert np.isfinite(portfolio.annualized_sharpe_ratio)
print(model.weights_)
print(portfolio.annualized_sharpe_ratio)
PY

# Pinned notebook's bundled S&P 500 example; plotting cells are omitted.
# The README Yahoo-download example is deliberately not an acceptance input.
# https://github.com/bashtage/arch/blob/038d78b709e75f2590890757af32705817a6fad8/examples/univariate_volatility_modeling.ipynb
# https://github.com/bashtage/arch/blob/038d78b709e75f2590890757af32705817a6fad8/arch/data/sp500/__init__.py
# https://github.com/bashtage/arch/blob/038d78b709e75f2590890757af32705817a6fad8/arch/data/utility.py
check arch_example "$python" -I - <<'PY'
import numpy as np
import arch.data.sp500
from arch import arch_model
data = arch.data.sp500.load()
market = data["Adj Close"]
returns = 100 * market.pct_change().dropna()
am = arch_model(returns)
res = am.fit(update_freq=5, disp="off")
assert res.convergence_flag == 0
assert np.isfinite(res.params).all()
print(res.summary())
PY

exit "$failed"
