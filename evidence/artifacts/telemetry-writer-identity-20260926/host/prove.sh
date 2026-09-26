#!/usr/bin/env bash
# G1 E2E proof (read-only, safe to run any time; starts no model call and changes nothing).
#
# Reads the loopback Prometheus (:19090) and Loki (:13100) query APIs without credentials, the host collector
# config, one Claude settings key and the codex launcher, then checks a window that ends two minutes ago:
#   - setup: both Prometheus features and the Codex bucket drop are loaded, the native-telemetry-integrity rules
#     are loaded, the collector has the writer-identity profile, Claude sends session ids, bin/codex is the
#     identity launcher;
#   - integrity: at most one reset per Claude token/cost series (a resume), the collector self-metrics scrape up
#     for the whole window without a missed scrape, zero delta_to_cumulative errors with accepted points, no
#     unscoped token writers;
#   - Claude: per writer, Prometheus increase(... anchored) within 2 percent of the Loki api_request sums; writers
#     with requests within 30 s of either window edge are left out;
#   - Codex: every codex_exec process that started in the window, completed a turn and finished 90 s before its
#     end, turn tokens within 2 percent of its Loki response.completed sums (startup prewarm excluded); missing =
#     -100 percent; a process without a completed turn is listed, not compared;
#   - coverage: >= 2 compared Claude writers, subagent (Ultracode child) usage, >= 2 compared codex processes
#     whose activity spans (first to last Loki event) overlap;
#   - capacity (information): series, storage and delta streams against their limits.
# Run it at least end-offset + codex-settle (3.5 minutes by default) after the scenario processes finish.
# Exit 0 PASS, 1 FAIL, 2 INCONCLUSIVE (clean, but the window lacks the scenario). Extra args go to prove.py
# (--window 45m, --end-offset 120s, --tolerance 2, --out DIR, ...); the report goes to
# ${XDG_STATE_HOME:-~/.local/state}/native-agent-stack/g1-writer-identity/prove-<UTC>/ unless --out is given.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/prove.py" "$@"
