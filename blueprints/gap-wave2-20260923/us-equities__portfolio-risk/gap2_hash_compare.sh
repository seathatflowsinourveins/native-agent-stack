set -u
C=$HOME/.cache/gap-wave2-20260923/portfolio-risk
F=$($C/venv-lock/bin/python -c "import skfolio.model_selection._walk_forward as m;print(m.__file__)")
echo "installed_path=${F/#$HOME/\$HOME}"
echo "installed_sha256=$(sha256sum "$F" | cut -d' ' -f1)"
echo "installed_dist=$($C/venv-lock/bin/python -c 'import importlib.metadata as m;print(m.version("skfolio"))')"
echo "receipt_walkforward_source_sha256=$(python3 -c 'import json;print(json.load(open("blueprints/us-equities/research-evaluation/receipt.json"))["runtime"]["walkforward_source_sha256"])')"
echo "upstream_repo_head_fetched=$(git -C $C/skfolio-src rev-parse HEAD)"
for rev in c99fcf71349e2df4a7a1033ee85ca2e9ced9abee v1.3.0 b500f88~1; do
  echo "git_show[$rev]_sha256=$(git -C $C/skfolio-src show $rev:src/skfolio/model_selection/_walk_forward.py | sha256sum | cut -d' ' -f1)"
done
echo "c99fcf71_is_tag=$(git -C $C/skfolio-src describe --exact-match --tags c99fcf71349e2df4a7a1033ee85ca2e9ced9abee)"
echo "diff_installed_vs_c99fcf71:"; git -C $C/skfolio-src show c99fcf71349e2df4a7a1033ee85ca2e9ced9abee:src/skfolio/model_selection/_walk_forward.py | diff -q - "$F" >/dev/null && echo identical || echo DIFFERENT
echo "diff_installed_vs_b500f88~1 (negative control):"; git -C $C/skfolio-src show b500f88~1:src/skfolio/model_selection/_walk_forward.py | diff - "$F" | wc -l
