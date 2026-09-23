#!/usr/bin/env bash
# Re-run the offline observability/alerting regression suites the
# observation-inference row names (gap 6's verdict_overturn_when). This
# confirms the incumbent still passes; it does not itself close the missing
# comparison against alternative observation stacks (Phoenix, OpenLIT,
# Loki-first) named in that gap.
set -euo pipefail
cd "$(dirname "$0")/../../.."
python3 -m unittest tests.test_observability tests.test_observability_backends_alerts -v
