"""Check the recorded transport claim offline; do not run SSH or certify truth."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CHECKPOINT = "59cb2038939b9cd2840eeaed6618634cad75ffe0f9a3b689a44f420f7847a1d0"
NATIVE_CHECKS = {
    "same_native_run_id", "native_running_before_disconnect",
    "checkpoint_durable_before_disconnect", "native_succeeded",
    "checkpoint_unchanged", "exact_completed_result", "checkpoint_executed_once",
    "frozen_inputs_unchanged", "checkpoint_oracle_12", "final_oracle_12",
    "owned_processes_exited", "owned_listeners_retired",
}


def load(name):
    return json.loads((HERE / name).read_text())


def audit(receipt=None, prior=None, freeze=None, root=REPO):
    receipt = load("receipt.json") if receipt is None else receipt
    prior = load("receipt-attempt-1.json") if prior is None else prior
    freeze = load("frozen-evidence.json") if freeze is None else freeze
    errors = []

    def require(value, message):
        if not value:
            errors.append(message)

    native, transport = receipt["native"], receipt["transport"]
    require(receipt["passed"] is True and receipt["transport_survival_qualified"] is True,
            "corrected survival outcome missing")
    require(native["before_status"] == native["reconnected_status"] == "running"
            and native["final_status"] == "succeeded", "native survival sequence differs")
    require(set(native["checks"]) == NATIVE_CHECKS
            and all(v is True for v in native["checks"].values()), "native acceptance incomplete")
    require(native["checkpoint_sha256"] == CHECKPOINT
            and native["checkpoint_execution_count"] == 1
            and native["oracle_tests_before"] == native["oracle_tests_after"] == 12,
            "checkpoint or unchanged oracle differs")
    require(transport["same_native_run_id"] is True
            and transport["checkpoint_effect_count_after_reconnect"] == 1,
            "same-run reconciliation missing")
    require(transport["running_verified_before_cleanup"] is True
            and transport["native_stop_or_retry_used"] is False
            and native["native_selected_step_retry"] is False
            and receipt["diagnostic_repairs"] == 0, "stop/retry is not survival")
    require(transport["active_before_signal"] is True
            and transport["controlled_local_signal"] == "SIGTERM"
            and transport["local_ssh_exit_code"] in (-15, 255)
            and transport["separate_nonmultiplexed_sessions"] is True
            and transport["fresh_connection_after_disconnect"] is True
            and receipt["controlled_transport_interruptions"] == 1,
            "owned controlled transport protocol differs")
    require(transport["real_network_outage_or_host_restart"] is False,
            "controlled disconnect broadened to outage")
    require(receipt["local_owned_ssh_remaining"] is False
            and native["observed_owned_processes_remaining"] == 0
            and native["observed_owned_listeners_remaining"] == 0
            and native["owned_processes_observed"] >= 1, "owned cleanup incomplete")
    require(native["native_start_exit"] == {"exit_code": 0, "timeout": False}
            and all(code == 0 for code in receipt["ssh_command_exit_codes"].values()),
            "native completion command failed")
    require(receipt["model_calls"] == native["model_calls"] == 0
            and receipt["enclosing_agent_usage"] is None, "usage scope differs")
    require(prior["initial_attempt_passed"] is False
            and prior["transport_survival_qualified"] is False
            and prior["original_failure"]["message"] == "expected owned SSH client SIGTERM exit"
            and prior["native"]["reconnected_status"] == "aborted"
            and prior["native"]["native_selected_step_retry"] is True
            and prior["transport"]["explicit_native_stop_after_harness_failure"] is True,
            "original failure/repair was relabeled")
    for attempt in freeze["attempts"].values():
        for item in attempt["files"]:
            path = root / item["path"]
            require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"],
                    "frozen source changed: " + item["path"])
    for label, row in [("attempt-1", prior), ("attempt-2", receipt)]:
        for item in freeze["attempts"][label]["files"]:
            require(row["native"]["frozen_files"][item["staged_name"]] == item["sha256"],
                    "native/source freeze mismatch: " + label)
    return errors


if __name__ == "__main__":
    problems = audit()
    print(json.dumps({"valid": not problems, "errors": problems,
                      "scope": "offline evidence consistency only"}))
    raise SystemExit(bool(problems))
