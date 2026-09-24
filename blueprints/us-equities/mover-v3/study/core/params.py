"""Every numeric and named parameter the study code uses (mover-v3-core-draft-20260924).

The protocol repeats this object at run_discipline.study_code.parameters. tests/test_params.py asserts
that the two are equal and that the protocol's structured fields (item_ids, minimum_sample,
minimum_detectable_effect, chronology, cost_model.base_table, coverage_rule) agree with it, and
core.guards.check_parameters refuses a run whose protocol object differs (review round 8, R8-2).
"""
from __future__ import annotations

PROTOCOL_PATH = "blueprints/us-equities/mover-v3/protocol-core-draft.json"
STUDY_PATH = "blueprints/us-equities/mover-v3/study"
FETCH_PATH = "blueprints/us-equities/mover-v3/study/fetch"
DATA_DIR = "blueprints/us-equities/mover-v3/data"
RUN_LOG = "blueprints/us-equities/mover-v3/run-log.jsonl"
ACCESS_LOG = "blueprints/us-equities/mover-v3/holdout-access-log.jsonl"
DEVIATIONS = "blueprints/us-equities/mover-v3/deviations.json"
# Results files have fixed paths (one per stage, count block and read), so a second results file for a stage is
# refused by the atomic write itself (run_discipline.once; review round 9, F1 and F10).
RESULTS_DIR = "blueprints/us-equities/mover-v3/results"
COUNT_ONLY_OUTPUT = "blueprints/us-equities/mover-v3/results/count-only-output.json"
DRY_RUN_OUTPUT = "blueprints/us-equities/mover-v3/results/dry-run-output.json"

PARAMETERS = {
    "item_ids": ["H1-D", "H1-D-b_lane-low", "H3-a", "H3-b", "H3-c"],
    "tradable_cells": ["H1-D-b_lane-low", "H3-a", "H3-b"],
    "alternatives": {"H1-D": "less", "H1-D-b_lane-low": "greater", "H3-a": "greater", "H3-b": "greater",
                     "H3-c": "two-sided"},
    "membership": {"gain_G": 0.20, "gain_eps": 1e-9, "min_official_close": 1.0, "min_dv_reg": 1_000_000.0,
                   "split_tolerance": 1e-2, "suspected_split_rel_tol": 0.01, "suspected_split_n_min": 2,
                   "suspected_split_n_max": 100, "max21_returns": 21, "sizing_window": 20,
                   "exclusion3_min_bar_sessions": 21, "exclusion3_window": 22},
    "timing": {"decision_hhmm": "16:15", "entry_hhmm": "09:35", "regular_open_hhmm": "09:30",
               "premarket_start_hhmm": "04:00", "min_latency_s": 60, "entry_timeout_s": 300,
               "prevailing_max_age_s": 1.0, "stamp_before_close_s": 300, "search_sessions": 5,
               "entry_bar_complete_s": 60, "holding_sessions_b_lane": 5},
    "sizing": {"notional_cap_usd": 20000.0, "med20_fraction": 0.01, "entry_bar_fraction": 0.10,
               "min_notional_usd": 1000.0},
    "costs": {"table_multiplier": 1.25, "impact_c": 1.0, "impact_c_sensitivities": [0.5, 2.0],
              "stress_multiplier": 2.0, "stress_impact_c": 2.0, "cash_band": 2e-3},
    "terciles": {"window_sessions": 252, "minimum_prior_events": 60, "quantiles": [1 / 3, 2 / 3],
                 "holdout_gap_start": "2026-01-02", "holdout_breakpoint_screen_start": "2024-11-01",
                 "holdout_breakpoint_screen_end": "2025-12-31"},
    "chronology": {"warmup": ["2016-01-04", "2016-12-30"], "development": ["2017-01-03", "2019-12-31"],
                   "validation": ["2020-01-02", "2020-12-31"], "embargo_sessions": 6,
                   "n0_offset_sessions": 40, "holdout_sessions": 252, "extension_block_sessions": 63,
                   "max_extension_blocks": 2, "read_deadline_sessions": 15, "paper_exposed_max_fraction": 0.05},
    "bootstrap": {"B": 100_000, "block_sessions": {"H1-D": 10, "H1-D-b_lane-low": 10, "H3-a": 5, "H3-b": 10,
                                                   "H3-c": 10},
                  "chunk_rows": 10_000, "stage_index": {"development": 0, "validation": 1, "holdout": 2}},
    "testing": {"alpha": 0.05, "m": 5, "development_alpha": 0.05, "lineage_trials": 1012 + 60 + 5,
                "winsor_quantiles": [0.01, 0.99], "top_sessions_dropped": 5},
    "minimum_sample": {"tradable_cell": {"development": 300, "validation": 150, "holdout": 150},
                       "difference_test_per_group": {"development": 150, "validation": 100, "holdout": 100}},
    "mde": {"z_sum_one_sided": 3.168, "z_sum_two_sided": 3.4175, "design_effect_DEFF": 1.5,
            "sigma_by_item": {"H1-D": [0.35, "difference"], "H1-D-b_lane-low": [0.35, "cell"],
                              "H3-a": [0.25, "cell"], "H3-b": [0.15, "cell"], "H3-c": [0.1, "paired"]}},
    "fetch": {"retries": 3, "retry_waits_s": [1, 4, 16], "void_incomplete_rate": 0.01, "max_refetches": 1,
              "screen_symbols_per_request": 100, "page_limit": 10000, "feed": "sip",
              "reproduction_live_sample": 200},
    "sampling": {"sample_modulus": 20, "coverage_modulus": 25, "coverage_stamps_hhmm": ["12:17", "14:43"],
                 "coverage_stamps_early_close_hhmm": ["12:17", "12:43"], "coverage_forward_s": 60,
                 "probe_rename_cap": 100, "probe_reuse_cap": 50, "probe_offset_sessions": 3,
                 "probe_quote_window_end_hhmm": "12:17", "probe_quote_window_s": 60},
    "cost_table": {"path": "blueprints/us-equities/mover-early-entry/evidence/cost-table-run-v1.json",
                   "sha256": "be50cbdfd75c5c4b0a66286bf9edb40c9ce49add719b6b5e1b0cdf93064eaa13"},
}

ITEM_IDS = tuple(PARAMETERS["item_ids"])
TRADABLE = tuple(PARAMETERS["tradable_cells"])
ALTERNATIVE = dict(PARAMETERS["alternatives"])
M = PARAMETERS["membership"]
T = PARAMETERS["timing"]
S = PARAMETERS["sizing"]
C = PARAMETERS["costs"]
TERC = PARAMETERS["terciles"]
CHRONO = PARAMETERS["chronology"]
BOOT = PARAMETERS["bootstrap"]
TEST = PARAMETERS["testing"]
MIN_SAMPLE = PARAMETERS["minimum_sample"]
MDE = PARAMETERS["mde"]
FETCH = PARAMETERS["fetch"]
SAMPLING = PARAMETERS["sampling"]
COST_TABLE = PARAMETERS["cost_table"]

# The sha256 of coverage_rule (canonical JSON) that this count-only code was written against
# (coverage_rule.decided_by_code). tests/test_params.py (test_coverage_rule_hash_is_recorded) recomputes it from
# the protocol.
COVERAGE_RULE_SHA256 = "365a6cdef21aba117d32976a96f6f03efd06b745cb4255d9ee6957842d625407"
