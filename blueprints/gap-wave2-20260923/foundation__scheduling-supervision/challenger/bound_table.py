#!/usr/bin/env python3
"""Fix round 1: score the SIGKILL case under both the preregistered 150 s bound
(preregistrations/4.json) and the post-hoc 270 s window, from committed result.json copies.

A SIGKILL case passes under a bound iff the run's own `cases.sigkill` is true AND its
recorded recovery_seconds is within the bound. The stop/retry/checkpoint_reuse cases do not
depend on the window and are copied unchanged. Writes JSON to stdout.

Usage: bound_table.py LABEL=RESULT.json [LABEL=RESULT.json ...]
"""

import json
from pathlib import Path
import sys

PREREGISTERED_BOUND_S = 150


def main():
    table = {"preregistered_bound_seconds": PREREGISTERED_BOUND_S, "runs": {}}
    for arg in sys.argv[1:]:
        label, path = arg.split("=", 1)
        result = json.loads(Path(path).read_text())
        runs = {}
        for engine, entry in result["engines"].items():
            b = entry.get("scenario_b", {})
            sigkill = b.get("cases", {}).get("sigkill")
            seconds = b.get("recovery_seconds")
            runs[engine] = {
                "stop": entry["case_table"].get("stop"), "retry": entry["case_table"].get("retry"),
                "checkpoint_reuse": entry["case_table"].get("checkpoint_reuse"),
                "sigkill_within_run_window": sigkill, "run_window_seconds": b.get("window_seconds"),
                "recovery_seconds": seconds, "final_status": b.get("final_status"),
                "sigkill_within_preregistered_150s": bool(sigkill) and seconds is not None and seconds <= PREREGISTERED_BOUND_S,
                "dagu_recovery_mode": result.get("protocol", {}).get("dagu_recovery",
                                                                      "scheduler (original run; flag did not exist yet)") if engine == "dagu" else None,
            }
        table["runs"][label] = {"source": path, "engines": runs}
    print(json.dumps(table, indent=2))


if __name__ == "__main__":
    main()
