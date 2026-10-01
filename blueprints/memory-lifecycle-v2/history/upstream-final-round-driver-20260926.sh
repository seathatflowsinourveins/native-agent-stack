#!/usr/bin/env bash
set -u
until grep -q "end v2.4.1 doc exit" <scratch>/g4/upstream/out/run_all.log; do sleep 5; done
echo "$(date -u +%FT%TZ) round 2 start"
sha256sum <scratch>/wt-g4/blueprints/memory-lifecycle-v2/upstream-20260926/run_upstream_tests.py <scratch>/wt-g4/blueprints/memory-lifecycle-v2/upstream-20260926/control.py
for tag in v2.3.2 v2.4.0 v2.4.1; do
  <scratch>/ci-venv/bin/python <scratch>/wt-g4/blueprints/memory-lifecycle-v2/upstream-20260926/run_upstream_tests.py --scratch <scratch>/g4/upstream --tag $tag --out <scratch>/g4/upstream/out2/$tag
  echo "$(date -u +%FT%TZ) end $tag exit=$?"
done
<scratch>/ci-venv/bin/python <scratch>/wt-g4/blueprints/memory-lifecycle-v2/upstream-20260926/run_upstream_tests.py --scratch <scratch>/g4/upstream --tag v2.4.1 --out <scratch>/g4/upstream/out2/v2.4.1 --doc --label workspace-doc
echo "$(date -u +%FT%TZ) end v2.4.1 doc exit=$?"
<scratch>/ci-venv/bin/python <scratch>/wt-g4/blueprints/memory-lifecycle-v2/upstream-20260926/control.py --scratch <scratch>/g4/upstream --out <scratch>/g4/upstream/out2/control
echo "$(date -u +%FT%TZ) end control exit=$?"
git -C <scratch>/g4/upstream/tags/v2.4.1 status --porcelain
echo "$(date -u +%FT%TZ) round 2 done"
