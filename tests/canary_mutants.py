#!/usr/bin/env python3
"""Mutation acceptance for the canary proof (contract draft 3, section 13.8; build amendment C3).

    python3 -I tests/canary_mutants.py --json [--jobs N] [--only ID,ID...] [--keep DIR] [--check]

The table below keeps draft 2's 65 fault classes (section 13.5), each adapted to the held-descriptor, two-process
design and mapped to the named test that must kill it, and adds one mutant per draft-3 repair (the seven G6 blockers,
as the thirteen G6 rows of section 13.8), the protocol nonce, check-completion, stderr-count, M2-branch and
optional-request mutants the contract names, and two continuation repairs (a hard type change absorbed by a retry;
cleanup's absence fact staling the final).

For every mutant: copy the pinned inputs (tools/credentials, scripts, adoption, tests/__init__.py,
tests/test_canary_proof.py and the loader files the credential inventory names, which its validation requires) into
a fresh scratch tree under /tmp that is a Git repository with one empty commit (prepare fingerprints HEAD), apply its
exact text edits (each must occur exactly
once in the unmutated file), drop any cached bytecode, and run its killing test in that tree with bytecode writing off
(`python3 -B -m unittest`). A mutant is killed only when that test fails with an AssertionError whose message ends
with the named label; an import, syntax or unrelated error is never a kill. Each killing test must first pass on an
unmutated scratch tree (the pristine run), so a kill is a passing named test followed by its actual assertion
failure. This process never writes the repository: the input files' SHA-256 values are compared before and after.

Output with --json: one JSON object per mutant, in table order,
    {"id", "target_file", "patch_sha256", "killing_test", "failing_assertion", "killed"}
(patch_sha256 is the SHA-256 of the unified diff this mutant applies). The retained artifacts (each mutant's patch
and its test's complete output, every pristine output and table.json with each fault description) go to --keep DIR or
a new /tmp/canary-mutants-* directory, named on stderr. --check only verifies that every edit applies.

Exit status: 0 every mutant killed and every pristine run passed; 1 otherwise; 2 usage.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ("tools/credentials", "scripts", "adoption", "tests/__init__.py", "tests/test_canary_proof.py")
PROOF, WORKER, PROBE = ("tools/credentials/canary_proof.py", "tools/credentials/canary_scan_worker.py",
                        "tools/credentials/canary_probe.py")
TIMEOUT = 1800
T = "tests.test_canary_proof."


def mutant(ident, fault, target, edits, test, assertion):
    return {"id": ident, "fault": fault, "target_file": target, "edits": edits, "killing_test": T + test,
            "failing_assertion": assertion}


MUTANTS = [
    # ---- Draft 2's 65 rows (section 13.5), adapted ------------------------------------------------------------------
    mutant("D2-01", "Threshold with no margin", PROOF,
           [("threshold_ns=ref.st_ctime_ns - MARGIN_NS,", "threshold_ns=ref.st_ctime_ns,")],
           "StabilityTests.test_st8_threshold_unknown_fs_unverifiable_fs_and_clock", "ST8-hour-margin"),
    mutant("D2-02", "Drift check removed", PROOF,
           [("    if drift < -DRIFT_NS:\n", "    if False:\n")],
           "StabilityTests.test_st8_threshold_unknown_fs_unverifiable_fs_and_clock", "ST8-drift"),
    mutant("D2-03", "Special files handed on like regular files", WORKER,
           [("        elif stat.S_ISREG(mode):\n            identity = (\"f\",) + tuple_of(info)",
             "        elif stat.S_ISREG(mode) or stat.S_ISFIFO(mode):\n            identity = (\"f\",) + tuple_of(info)")],
           "FifoTests.test_f_m1a_special_is_named_and_never_opened", "F-M1a-no-content-open"),
    mutant("D2-04", "No (dev, ino) and type re-check at hand-off", WORKER,
           [("            if not stat.S_ISREG(info.st_mode) or tuple_of(info) != identity:\n",
             "            if False:\n")],
           "FifoTests.test_f_m1b_c_swaps_before_and_after_handoff_raw_le_be", "F-M1b-type-check before_handoff"),
    mutant("D2-05", "rg exit 2 accepted", WORKER,
           [("        if code not in (0, 1):\n            check.fail(\"scanner_exit\")",
             "        if False:\n            check.fail(\"scanner_exit\")")],
           "UnitTests.test_scanner_settle_fails_exit_2_and_a_deadline_itself", "M1-settle exit 2"),
    mutant("D2-06", "Scanner stderr ignored", WORKER,
           [("flow.read(err, lambda data: self.stderr(check, data, \"scanner_stderr\"))",
             "flow.read(err, lambda data: None)")],
           "ModeTests.test_m1_scanner_exit_stderr_stats_and_unknown_records", "M1-invalid-output-incomplete stderr"),
    mutant("D2-07", "`files searched` not reconciled", WORKER,
           [("        if self.searched != files:\n", "        if False:\n")],
           "ModeTests.test_m1_stat_counts_control_origins_and_output_cap", "M1-reconcile files_searched_mismatch"),
    mutant("D2-08", "A control counted as found without a record", WORKER,
           [("            found = sum(count for (seen, p), count in self.per_control.items() if seen == label and p == "
             "pattern)", "            found = expected")],
           "ModeTests.test_m1_emptied_positive_control_is_incomplete", "M1-control-emptied m1/0001"),
    mutant("D2-09", "Compressed file silently plain when its decoder is unresolved", WORKER,
           [("            elif kind == \"decode\":\n                self.decode(",
             "            elif kind == \"decode\" and self.exes.get(\"xz\" if fmt == \"lzma\" else fmt):\n"
             "                self.decode(")],
           "ModeTests.test_m2_missing_decoder_spawn_failure_stderr_trailing_nested_and_odd_bom",
           "M2-failure-incomplete missing"),
    mutant("D2-10", "zip treated as plain", WORKER,
           [("CONTAINERS = ((0, b\"PK\\x03\\x04\"), (0, b\"PK\\x05\\x06\"), (0, b\"PK\\x07\\x08\"), ",
             "CONTAINERS = (")],
           "UnitTests.test_every_routing_row", "M2-route container"),
    mutant("D2-11", "Name matching off", WORKER,
           [("            for pattern in self.scan.patterns.find(data, first_end):\n",
             "            for pattern in ():\n")],
           "ModeTests.test_m6_names_targets_paths_newlines_boundary_names_and_negatives", "M6-name"),
    mutant("D2-12", "Symlink target not checked", WORKER,
           [("            self.names(target, 0)\n            if self.mode == \"pre\":\n                self.link(path)",
             "            if self.mode == \"pre\":\n                self.link(path)")],
           "ModeTests.test_m6_names_targets_paths_newlines_boundary_names_and_negatives", "M6-target"),
    mutant("D2-13", "A sink path in a child's argv (Git given the store path)", WORKER,
           [("[self.scan.exe(\"git\"), \"--git-dir=.\", *args], cwd=self.path)",
             "[self.scan.exe(\"git\"), \"--git-dir=\" + os.fsdecode(self.path), *args], cwd=self.path)")],
           "StabilityTests.test_st6_names_targets_paths_and_newlines_never_enter_argv", "ST6-no-sink-argv"),
    mutant("D2-14", "Names split on newlines before M6", WORKER,
           [("            for pattern in self.scan.patterns.find(data, first_end):\n",
             "            for pattern in self.scan.patterns.find(data.split(b\"\\n\")[0], first_end):\n")],
           "ModeTests.test_m6_names_targets_paths_newlines_boundary_names_and_negatives", "M6-newline-name"),
    mutant("D2-15", "Empty matched text accepted", WORKER,
           [("or label not in self.labels or pattern not in self.scan.patterns.classes:",
             "or label not in self.labels or (pattern and pattern not in self.scan.patterns.classes):")],
           "UnitTests.test_rg_record_grammar_rejects_empty_unknown_and_unlabelled_records", "M1-grammar empty"),
    mutant("D2-16", "Unknown matched text accepted", WORKER,
           [("or label not in self.labels or pattern not in self.scan.patterns.classes:",
             "or label not in self.labels or not pattern:")],
           "UnitTests.test_rg_record_grammar_rejects_empty_unknown_and_unlabelled_records", "M1-grammar unknown"),
    mutant("D2-17", "Any attempt's tag accepted instead of the latest", PROOF,
           [("klass == 2 and owner == code and number == attempt and count > 0",
             "klass == 2 and owner == code and count > 0")],
           "RequestRunTests.test_r4_rearm_unbaselined_home_attempt_binding_and_settle",
           "R4-attempt-1-tag-insufficient"),
    mutant("D2-18", "The scan request recorded after the work begins", PROOF,
           [("    try:\n"
             "        event = run.append(\"scan_requested\", request=secrets.token_hex(6), phase=args.phase, group=group,\n"
             "                           selection=\"all\" if args.phase == \"comparison\" else \"changed\")\n"
             "    except OSError:  # admission failed: no work starts and no pass is published (contract 5)\n"
             "        os.write(2, b\"canary_proof: scan request not recorded; nothing ran\\n\")\n"
             "        return EXIT[\"incomplete\"]\n"
             "    hook(\"after_request\")\n",
             "    event = {\"request\": secrets.token_hex(6), \"phase\": args.phase, \"group\": group,\n"
             "             \"selection\": \"all\" if args.phase == \"comparison\" else \"changed\"}\n"),
            ("        hook(\"before_plan\")\n        run.append(\"scan_planned\",",
             "        run.append(\"scan_requested\", **event)\n        hook(\"after_request\")\n"
             "        hook(\"before_plan\")\n        run.append(\"scan_planned\",")],
           "RequestTests.test_r1_a_kill_before_the_plan_supersedes_the_passing_final", "R1-before_mkdir"),
    mutant("D2-19", "Leak not sticky (only complete requests' hits count)", PROOF,
           [("    hits = sum(event[\"count\"] for event in events if event[\"event\"] == \"hit\")\n",
             "    hits = sum(event[\"count\"] for event in events if event[\"event\"] == \"hit\" and any(\n"
             "        e[\"event\"] == \"scan_finished\" and e[\"request\"] == event[\"request\"] and e[\"status\"] == "
             "\"complete\" for e in events))\n")],
           "BoundaryTests.test_b5_a_hit_is_sticky_through_kill_rotation_and_a_zero_rescan", "B5-sticky exit"),
    mutant("D2-20", "User-run hits ignored", PROOF,
           [("    hits = sum(event[\"count\"] for event in events if event[\"event\"] == \"hit\")\n",
             "    hits = sum(event[\"count\"] for event in events if event[\"event\"] == \"hit\" and not "
             "event[\"sink\"].startswith(\"U\"))\n")],
           "RequestRunTests.test_r5_r8_sticky_user_and_comparison_results", "R5-user-hit"),
    mutant("D2-21", "Baseline allowed after arm", PROOF,
           [("            codes.append(\"baseline_after_arm\")", "            pass")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code baseline_after_arm"),
    mutant("D2-22", "Settle not enforced", PROOF,
           [("if last_disarm is None or requested[\"boottime_ns\"] - last_disarm < SETTLE_SECONDS * 10**9:",
             "if last_disarm is None:")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code final_too_early"),
    mutant("D2-23", "Coordinator's own transcript accepted as the fresh session's recording", PROOF,
           [("\"fresh-claude-session\": (\"A1\", {1})", "\"fresh-claude-session\": (\"A1\", {1, 14})")],
           "RequestRunTests.test_r7_recording_classes_and_markers", "R7-class fresh-claude-session"),
    mutant("D2-24", "Subagent recording accepted from a main transcript", PROOF,
           [("\"subagent\": (\"A1\", {2})", "\"subagent\": (\"A1\", {1, 2})")],
           "RequestRunTests.test_r7_recording_classes_and_markers", "R7-class subagent"),
    mutant("D2-25", "Masking count not checked", PROOF,
           [("if sum(row[5] for row in rows if row[0] == 3) != expected or any(row[0] == 4 for row in rows):",
             "if any(row[0] == 4 for row in rows):")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code masking_markers_mismatch"),
    mutant("D2-26", "PARTIAL markers ignored", PROOF,
           [("if sum(row[5] for row in rows if row[0] == 3) != expected or any(row[0] == 4 for row in rows):",
             "if sum(row[5] for row in rows if row[0] == 3) != expected:")],
           "RequestRunTests.test_r7_marker_count_and_partial_marker", "R7-markers partial"),
    mutant("D2-27", "Attempt pattern file validation skipped", PROOF,
           [("    recorded = dict(run.events[0][\"patterns\"])\n",
             "    return []\n    recorded = dict(run.events[0][\"patterns\"])\n")],
           "BoundaryTests.test_b7_union_integrity", "B7-attempt-appended"),
    mutant("D2-28", "disarm without the (dev, ino) check", PROOF,
           [("(info.st_dev, info.st_ino, info.st_ctime_ns) != (armed[\"dev\"], armed[\"ino\"], armed[\"ctime_ns\"])",
             "False")],
           "StoreTests.test_foreign_inode_is_never_removed_and_absence_is_verified", "S-foreign"),
    mutant("D2-29", "arm overwrites instead of create-only publication", PROOF,
           [("        with _suppress(FileNotFoundError):\n            os.stat(STORE_FILE, dir_fd=fd, "
             "follow_symlinks=False)\n            raise Refused(\"store_file_exists\")\n", ""),
            ("        writer.create_exclusively(fd, STORE_FILE, writer.encode(VARIABLE, canary))\n",
             "        _out = os.open(STORE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600, "
             "dir_fd=fd)\n        os.write(_out, writer.encode(VARIABLE, canary).encode())\n        os.close(_out)\n")],
           "StoreTests.test_arm_is_create_only_and_an_existing_file_is_left_untouched", "S-create-only"),
    mutant("D2-30", "arm through the writer's open_store (creates and chmods the store)", PROOF,
           [("    root = cs.expand_template(cs.STORE_ROOT, env)\n    try:\n",
             "    root = cs.expand_template(cs.STORE_ROOT, env)\n    os.makedirs(root, mode=0o700, exist_ok=True)\n"
             "    os.chmod(root, 0o700)\n    try:\n")],
           "StoreTests.test_store_mode_0750_and_missing_store_refuse_without_change", "S-mode"),
    mutant("D2-31", "Store listed", PROOF,
           [("    root = cs.expand_template(cs.STORE_ROOT, env)\n    try:\n",
             "    root = cs.expand_template(cs.STORE_ROOT, env)\n    try:\n        os.listdir(root)\n")],
           "StoreTests.test_arm_and_disarm_never_list_the_store", "S-no-list"),
    mutant("D2-32", "Basename exclusion", WORKER,
           [("            if child == os.fsencode(rule[\"path\"]):",
             "            if os.path.basename(child) == os.path.basename(os.fsencode(rule[\"path\"])):")],
           "StabilityTests.test_st7_exact_exclusions_and_unreadable_entries", "ST7-ordinary-auth-scanned"),
    mutant("D2-33", "Key home not excluded (the Claude daemon key; Claude's credentials file is also an inventory "
           "path, so dropping it alone is caught twice)", PROOF,
           [("(f\"{h}/.claude/daemon/control.key\", \"key\"), ", "")],
           "StabilityTests.test_st7_exact_exclusions_and_unreadable_entries", "ST7-K-U-never-opened"),
    mutant("D2-34", "TTY gate removed", PROOF,
           [("    if args.user_run and not (os.isatty(0) and os.isatty(1) and not env.get(\"CLAUDECODE\")):\n",
             "    if False:\n")],
           "CommandTests.test_cli_exact_spellings_and_tty_guards", "CMD-TTY-required"),
    mutant("D2-35", "git failure treated as absent", WORKER,
           [("            check.fail(\"deadline\" if code is None else \"producer_exit\" if code else \"ok\")",
             "            check.fail(\"deadline\" if code is None else \"absent_since_prepare\" if code else \"ok\")")],
           "ModeTests.test_m4_orphan_index_corrupt_payload_alternate_and_promisor",
           "M4-unaccounted-incomplete exit128"),
    mutant("D2-36", "Producer stderr ignored", WORKER,
           [("flow.read(err, lambda data: self.stderr(producer, data, \"producer_stderr\"))",
             "flow.read(err, lambda data: None)")],
           "ModeTests.test_m2_missing_decoder_spawn_failure_stderr_trailing_nested_and_odd_bom",
           "M2-failure-incomplete stderr"),
    mutant("D2-37", "Worker output relayed to the coordinator (a parent-held stream read end)", PROOF,
           [("subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,",
             "subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,")],
           "BoundaryTests.test_b3_descriptor_ownership_in_prepare_and_scan", "B3-worker-stdio"),
    mutant("D2-38", "Dumper error ignored", WORKER,
           [("owner.fail(\"deadline\" if code is None else DUMPER_EXITS.get(code, \"producer_exit\") if code else \"ok\")",
             "owner.fail(\"deadline\" if code is None else \"ok\")")],
           "ModeTests.test_m5_replaced_main_inode_and_schema_errors_are_incomplete", "M5-inode-mismatch"),
    mutant("D2-39", "WAL-only change does not select its main database", WORKER,
           [("                        self.selected_by_time(member) for member in families.get(name, {}).values())):",
             "                        False for member in families.get(name, {}).values())):")],
           "ModeTests.test_m5_wal_only_change_selects_its_main_database", "M5-wal-only-change-selects-main"),
    mutant("D2-40", "Extensionless SQLite not dumped", WORKER,
           [("    if head.startswith(b\"SQLite format 3\\x00\"):\n",
             "    if head.startswith(b\"SQLite format 3\\x00\") and name.endswith((b\".db\", b\".sqlite\")):\n")],
           "UnitTests.test_every_routing_row", "M2-route sqlite"),
    mutant("D2-41", "Receipt value check removed", PROOF,
           [("    check_output(data, run.secrets())\n    boot.write_receipt(", "    boot.write_receipt(")],
           "BoundaryTests.test_b8_publication_refuses_a_synthetic_value_in_a_trusted_field", "B8-refused"),
    mutant("D2-42", "Core-pattern check skipped at prepare", PROOF,
           [("    platform_check()\n    runner.disable_core_dumps()\n    run = Run(env, \"cp-\"",
             "    platform_check()\n    run = Run(env, \"cp-\"")],
           "ContainmentTests.test_c8_prepare_scan_and_arm_refuse_a_core_collector", "C8-prepare-core-collector"),
    mutant("D2-43", "Upstream children started without setpriv --pdeathsig", WORKER,
           [("subprocess.Popen([scan.setpriv, \"--pdeathsig\", \"TERM\", \"--\", *argv],",
             "subprocess.Popen([*argv],")],
           "ContainmentTests.test_c3_worker_death_direct_scanner_and_decoder", "C3-direct-children-gone"),
    mutant("D2-44", "Group kill skipped when the leader has exited", WORKER,
           [("        exited = self.command.exited()\n        runner.end_group(self.command)\n",
             "        exited = self.command.exited()\n        None if exited else runner.end_group(self.command)\n")],
           "ContainmentTests.test_c6_exited_group_leader_keeps_descendant_ownership", "C6-descendant-reaped"),
    mutant("D2-45", "Lock not taken", PROOF,
           [("            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)\n", "            pass\n")],
           "StoreTests.test_concurrent_invocation_returns_75_and_admits_no_request", "C9-busy"),
    mutant("D2-46", "Tag computed without the attempt", PROBE,
           [("message = f\"canary-proof|{run}|{consumer}|{attempt}\".encode(\"ascii\")",
             "message = f\"canary-proof|{run}|{consumer}\".encode(\"ascii\")")],
           "UnitTests.test_tag_agrees_with_the_probe_and_binds_run_consumer_attempt", "U-tag binding"),
    mutant("D2-47", "User-run agentsview arrival not required", PROOF,
           [("            codes.append(\"user_arrival_missing:agentsview\")", "            pass")],
           "RequestRunTests.test_r7_unknown_session_fallback_and_user_arrival", "R7-agentsview"),
    mutant("D2-48", "ripgrep's --search-zip in place of the M2 producers", WORKER,
           [("\"--stats\", \"--no-ignore\", \"--hidden\", \"--file\", self.patterns.path,",
             "\"--stats\", \"--no-ignore\", \"--hidden\", \"--search-zip\", \"--file\", self.patterns.path,"),
            ("            elif kind == \"decode\":\n                self.decode(",
             "            elif False:\n                self.decode(")],
           "ModeTests.test_m2_missing_decoder_spawn_failure_stderr_trailing_nested_and_odd_bom",
           "M2-failure-incomplete missing"),
    mutant("D2-49", "--encoding none dropped from the raw pass", WORKER,
           [("\"--no-mmap\", \"--text\", \"--encoding\", encoding, \"--fixed-strings\",",
             "\"--no-mmap\", \"--text\", \"--fixed-strings\",")],
           "ModeTests.test_m1_nul_empty_bom_raw_and_utf16_views", "M1-raw-after-bom"),
    mutant("D2-50", "Completeness from ledger entries only (scan status ignored)", PROOF,
           [("        if finished[\"status\"] != \"complete\" or found:\n", "        if found:\n")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code final_incomplete"),
    mutant("D2-51", "Plan coverage not checked (a missing sink row)", PROOF,
           [("                found.append(f\"sink_not_scanned:{sink}\" if name == \"final\" else "
             "f\"{name}_sink_not_scanned:{sink}\")", "                pass")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code sink_not_scanned:A4"),
    mutant("D2-52", "Full-path check removed (names only)", WORKER,
           [("            self.names(path, len(path) - len(name) - 1)", "            self.names(name, 0)")],
           "ModeTests.test_m6_names_targets_paths_newlines_boundary_names_and_negatives", "M6-path-spanning"),
    mutant("D2-53", "Compressed files not given the physical raw view", WORKER,
           [("            raw = self.declare(\"M1\", \"raw\", obj, path_class, 1 + len(self.m1_controls(False)), "
             "info.st_size)\n            self.file_view(raw, fd, False, info.st_size)\n",
             "            if kind != \"decode\":\n                raw = self.declare(\"M1\", \"raw\", obj, path_class, 1 + "
             "len(self.m1_controls(False)), info.st_size)\n                self.file_view(raw, fd, False, info.st_size)\n")],
           "ModeTests.test_m2_every_compressor_endian_concat_and_physical_header", "M2-physical-additive"),
    mutant("D2-54", "Added magic rows removed (lzop, Snappy)", WORKER,
           [("(b\"LZIP\", \"lzip\"), (b\"\\x89LZO\", \"lzop\"), (b\"\\xff\\x06\\x00\\x00sNaPpY\", \"snappy\"))",
             "(b\"LZIP\", \"lzip\"))")],
           "UnitTests.test_every_routing_row", "M2-route lzop"),
    mutant("D2-55", "--after-cursor restored", WORKER,
           [("\"--no-pager\", \"--cursor=\" + cursor.decode()]", "\"--no-pager\", \"--after-cursor=\" + cursor.decode()]")],
           "ModeTests.test_m3_cursor_anchor_binary_fields_and_cmdline", "M3-vacuum-retains-first-hit"),
    mutant("D2-56", "hit events not written", PROOF,
           [("        self.hits += 1\n        self.run.append(\"hit\",",
             "        self.hits += 1\n        (lambda *_a, **_k: None)(\"hit\",")],
           "BoundaryTests.test_b5_a_hit_is_sticky_through_kill_rotation_and_a_zero_rescan", "B5-sticky exit"),
    mutant("D2-57", "vanished treated as absent", WORKER,
           [("            self.state = \"vanished\" if self.root[\"present\"] else \"absent_since_prepare\"\n"
             "            return\n        except OSError:",
             "            self.state = \"absent_since_prepare\"\n            return\n        except OSError:")],
           "RequestRunTests.test_r6_absent_vanished_and_declined_roots", "R6-vanished"),
    mutant("D2-58", "Out-of-scope links ignored", WORKER,
           [("        self.state = \"link_out\" if self.state == \"ok\" else self.state", "        pass")],
           "StabilityTests.test_st6_link_outcomes_are_distinct", "ST6-link-out"),
    mutant("D2-59", "Pointer targets not bound at prepare", PROOF,
           [("pointers=[record.seal.hex() for record in fact(session, \"pointer_binding\")],", "pointers=[],")],
           "StabilityTests.test_st9_pointer_binding_and_directory_refusal", "ST9-bound-target-excluded"),
    mutant("D2-60", "rg invoked by bare name", WORKER,
           [("        return [self.exe(\"rg\"), \"--no-config\",", "        return [\"rg\", \"--no-config\",")],
           "BoundaryTests.test_b6_worker_runs_the_bound_absolute_path_after_the_plan", "B6-bound-absolute-path"),
    mutant("D2-61", "Union file not re-hashed before each child", WORKER,
           [("        self.patterns.read()\n        labels = {b\"<stdin>\": None}",
             "        labels = {b\"<stdin>\": None}")],
           "BoundaryTests.test_b7_union_integrity", "B7-after-plan"),
    mutant("D2-62", "Object count check removed", WORKER,
           [("        if self.seen != set(self.objects) or markers != len(self.objects):", "        if False:")],
           "ModeTests.test_m4_stream_exact_framing_and_marker_reconciliation", "M4-scanner-marker-required"),
    mutant("D2-63", "A U7 location read by an agent-run scan (Claude settings.json)", PROOF,
           [("for name in (\"history.jsonl\", \"paste-cache\", \"settings.json\",\n",
             "for name in (\"history.jsonl\", \"paste-cache\",\n")],
           "StabilityTests.test_st7_exact_exclusions_and_unreadable_entries", "ST7-K-U-never-opened"),
    mutant("D2-64", "Journal anchor not required", WORKER,
           [("        self.scan.control(self.check, ident, self.check.counts.pop((CLASSES[\"anchor\"], 0, 0, ident), 0), 1, "
             "\"anchor\")",
             "        self.scan.control(self.check, ident, max(1, self.check.counts.pop((CLASSES[\"anchor\"], 0, 0, "
             "ident), 0)), 1, \"anchor\")")],
           "ModeTests.test_m3_cursor_anchor_binary_fields_and_cmdline", "M3-anchor-required"),
    mutant("D2-65", "Git stores inside A roots not found by the walk", WORKER,
           [("        if {b\"HEAD\", b\"objects\", b\"refs\"} <= stats.keys()",
             "        if False and {b\"HEAD\", b\"objects\", b\"refs\"} <= stats.keys()")],
           "ModeTests.test_m4_real_discovered_and_configured_stores_keep_and_duplicates",
           "M4-duplicates-physical-logical"),
    # ---- One per draft-3 repair (the G6 rows of section 13.8) -------------------------------------------------------
    mutant("G6-01", "Parent-side header and name read", PROOF,
           [("        sinks = sinks_for(args.phase, group)\n        roots = all_roots(run, env)\n",
             "        sinks = sinks_for(args.phase, group)\n        roots = all_roots(run, env)\n"
             "        for _root in roots.get(\"A1\", []):\n"
             "            for _name in sorted(os.listdir(_root[\"path\"])) if os.path.isdir(_root[\"path\"]) else ():\n"
             "                with _suppress(OSError), open(os.path.join(_root[\"path\"], _name), \"rb\") as _handle:\n"
             "                    _handle.read(64)\n")],
           "BoundaryTests.test_b1_sentinels_in_every_channel_never_reach_the_coordinator", "B1-sentinel-absent"),
    mutant("G6-02", "The latest finished request decides instead of the latest requested", PROOF,
           [("            requests[event[\"request\"]] = {\"requested\": event, \"planned\": None, \"finished\": None}\n"
             "            latest[(event[\"phase\"], event[\"group\"])] = event[\"request\"]\n"
             "        elif kind in (\"scan_planned\", \"scan_finished\"):\n"
             "            requests[event[\"request\"]][kind.split(\"_\")[1]] = event\n",
             "            requests[event[\"request\"]] = {\"requested\": event, \"planned\": None, \"finished\": None}\n"
             "        elif kind in (\"scan_planned\", \"scan_finished\"):\n"
             "            requests[event[\"request\"]][kind.split(\"_\")[1]] = event\n"
             "            if kind == \"scan_finished\":\n"
             "                first = requests[event[\"request\"]][\"requested\"]\n"
             "                latest[(first[\"phase\"], first[\"group\"])] = event[\"request\"]\n")],
           "RequestTests.test_r1_a_kill_before_the_plan_supersedes_the_passing_final", "R1-after_request"),
    mutant("G6-03", "Omitted final re-walk (no post-walk; the END seal from the pre-walk)", WORKER,
           [("        final = [Walk(self, root) for root in self.plan[\"roots\"]]\n"
             "        for before, after in zip(walks, final):\n"
             "            after.selected = before.selected\n"
             "            after.traverse(\"post\")\n"
             "            before.reconcile(after)\n"
             "            self.result(before.name_check, before.named, before.named)\n"
             "        self.finish(keyed(self.key, b\"inventory\", *(walk.canonical() for walk in final)))\n",
             "        for before in walks:\n"
             "            self.result(before.name_check, before.named, before.named)\n"
             "        self.finish(keyed(self.key, b\"inventory\", *(walk.canonical() for walk in walks)))\n")],
           "StabilityTests.test_st1_replacement_before_and_after_held_handoff", "ST1-retry-finds-replacement"),
    mutant("G6-04", "ctime omitted from same-inode identity checks", WORKER,
           [("    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns",
             "    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns")],
           "StabilityTests.test_st2_same_inode_overwrite_append_truncate_and_restored_mtime", "ST2-retry-finds-overwrite"),
    mutant("G6-05", "Pathname reopened after the validated handoff", WORKER,
           [("            hook(\"after_handoff\", rel)\n            head = os.pread(fd, SNIFF, 0)",
             "            hook(\"after_handoff\", rel)\n            os.close(fd)\n"
             "            fd = os.open(name, OPEN_FLAGS, dir_fd=dir_fd)\n            head = os.pread(fd, SNIFF, 0)")],
           "StabilityTests.test_st1_replacement_before_and_after_held_handoff", "ST1-held-fd-reads-original"),
    mutant("G6-06", "Route recheck omitted (after the views and in the final re-walk)", WORKER,
           [("            elif classify(os.pread(fd, SNIFF, 0), name, store) != (kind, fmt):\n",
             "            elif False:\n"),
            ("        elif any(after.routes.get(rel) != route_ for rel, route_ in self.routes.items()):\n",
             "        elif False:\n")],
           "StabilityTests.test_st9_route_recheck_under_deferred_timestamps", "ST9-route-recheck"),
    mutant("G6-07", "The whole objects/ subtree skipped", WORKER,
           [("        elif stat.S_ISDIR(mode):\n            if self.kind == \"tasks\" and depth == 2",
             "        elif stat.S_ISDIR(mode):\n            if store is not None and name == b\"objects\":\n"
             "                return\n            if self.kind == \"tasks\" and depth == 2")],
           "ModeTests.test_m4_real_discovered_and_configured_stores_keep_and_duplicates", "M4-keep-metadata-leak"),
    mutant("G6-08", "An unaccounted (index-less) pack ignored", WORKER,
           [("        if self.packs != self.indexes:  # an orphan pack or an index-only file\n",
             "        if False:  # an orphan pack or an index-only file\n"),
            ("        for name in sorted(self.packs):\n", "        for name in sorted(self.packs & self.indexes):\n")],
           "ModeTests.test_m4_orphan_index_corrupt_payload_alternate_and_promisor",
           "M4-unaccounted-incomplete orphan-extra"),
    mutant("G6-09", "Decoded BOM view omitted", WORKER,
           [("            self.encoding = bom_of(head)\n", "            self.encoding = None\n")],
           "ModeTests.test_m2_every_compressor_endian_concat_and_physical_header", "M2-decoded-bom gz"),
    mutant("G6-10", "ASCII control prepended before the decoded BOM", WORKER,
           [("self.flow.send(self.bom_fd, head[:2] + (control + b\"\\n\").decode(\"ascii\").encode(self.encoding))",
             "self.flow.send(self.bom_fd, control + b\"\\n\" + head[:2])")],
           "ModeTests.test_m2_every_compressor_endian_concat_and_physical_header", "M2-utf16-only-in-bom-view gz"),
    mutant("G6-11", "Schema SQL and names omitted from the dump", WORKER,
           [("    for row in schema:\n        for value in row:\n            if isinstance(value, bytes):\n"
             "                out.write(value + b\"\\n\")\n", "")],
           "ModeTests.test_m5_schema_utf16_overflow_and_uri_names_with_empty_tables", "M5-schema-uri-leak"),
    mutant("G6-12", "Literal (unescaped) SQLite URI", WORKER,
           [("    uri = \"file:\" + urllib.parse.quote_from_bytes(path, safe=\"/\") + \"?mode=ro\"",
             "    uri = \"file:\" + os.fsdecode(path) + \"?mode=ro\"")],
           "ModeTests.test_m5_schema_utf16_overflow_and_uri_names_with_empty_tables", "M5-uri-names-complete"),
    mutant("G6-13", "Actual main-descriptor identity skipped", WORKER,
           [("    if len(opened) != 1:\n        return 10\n", "    if False:\n        return 10\n")],
           "ModeTests.test_m5_actual_main_fd_race_with_the_name_restored", "M5-actual-main-fd-race"),
    # ---- The protocol, branch and request mutants that section 13.8 also names ---------------------------------------
    mutant("X-01", "Protocol nonce not checked", PROOF,
           [("or r.version != wire.VERSION or r.nonce != self.nonce or r.seq", "or r.version != wire.VERSION or r.seq")],
           "BoundaryTests.test_b4_every_kind_field_and_order_rule", "B4-reject replayed-nonce"),
    mutant("X-02", "Check completion: a declared check that never terminated", PROOF,
           [("        if set(self.checks) - set(self.completed):\n", "        if False:\n")],
           "BoundaryTests.test_b4_every_kind_field_and_order_rule", "B4-unterminated-check"),
    mutant("X-03", "Stderr count trusted in a complete RESULT", PROOF,
           [("result.exit not in (0, 1) or result.aux or result.reason", "result.exit not in (0, 1) or result.reason")],
           "BoundaryTests.test_b4_every_kind_field_and_order_rule", "B4-stderr-count"),
    mutant("X-04", "An M2 BOM branch's failure dropped when the raw branch passes", WORKER,
           [("        if self.encoding:\n            self.scan.result(self.bom_check, self.bom_check.observed, 1)",
             "        if self.encoding:\n            self.bom_check.reason = \"ok\"\n"
             "            self.scan.result(self.bom_check, self.bom_check.observed, 1)")],
           "ModeTests.test_m2_missing_decoder_spawn_failure_stderr_trailing_nested_and_odd_bom",
           "M2-failure-incomplete odd"),
    mutant("X-05", "A requested comparison's completeness optional after all", PROOF,
           [("    codes += final_codes + user_codes + group_codes((\"comparison\", \"user\"), \"comparison\")[0]",
             "    codes += final_codes + user_codes")],
           "RequestTests.test_r3_the_clean_record_and_every_classifier_code", "R3-code comparison_unfinished"),
    mutant("X-06", "Duplicate check completion accepted", PROOF,
           [("            if r.check not in self.checks or r.check in self.completed:",
             "            if r.check not in self.checks:")],
           "BoundaryTests.test_b4_every_kind_field_and_order_rule", "B4-duplicate"),
    mutant("X-07", "Scanner exit status trusted in a complete RESULT (the coordinator's half of D2-05)", PROOF,
           [("result.exit not in (0, 1) or result.aux or result.reason", "result.aux or result.reason")],
           "BoundaryTests.test_b4_every_kind_field_and_order_rule", "B4-exit-status"),
    # ---- Continuation repairs (this build) --------------------------------------------------------------------------
    mutant("C-01", "A regular file turned special absorbed by the stability retry", WORKER,
           [("                self.state = \"changed_type\"\n        elif any(",
             "                pass\n        elif any(")],
           "FifoTests.test_f_m1b_c_swaps_before_and_after_handoff_raw_le_be", "FIFO-incomplete-never-zero"),
    mutant("C-02", "Cleanup's absence fact stales the final (C4)", PROOF,
           [("    arm_events = [event for event in events if event[\"event\"] in (\"arming\", \"armed\", \"disarmed\")]",
             "    arm_events = [event for event in events if event[\"event\"] in (\"arming\", \"armed\", \"disarmed\", "
             "\"cleaned\")]")],
           "IntegratedTests.test_full_sequence_is_clean_and_cleanup_receipt_matches_verdict", "C4-cleanup-clean"),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory_references() -> list:
    """The loader and consumer files the inventory names: credential_status.inventory_errors requires each to exist
    in the checkout, and arm validates the inventory through the credential runner."""
    inventory = json.loads((ROOT / "adoption" / "credential-inventory.json").read_text(encoding="utf-8"))
    refs = {ref.split("#", 1)[0] for entry in inventory["entries"]
            for key in ("loaders", "environment_only_consumers") for ref in entry[key]}
    return sorted(ref for ref in refs if "/" in ref and " " not in ref and (ROOT / ref).is_file()
                  and not any(ref == item or ref.startswith(item + "/") for item in INPUTS))


def input_files() -> list:
    files = []
    for item in [*INPUTS, *inventory_references()]:
        path = ROOT / item
        files += [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file()
                                                     and "__pycache__" not in p.parts)
    return files


def copy_inputs(destination: Path) -> None:
    for item in [*INPUTS, *inventory_references()]:
        source, target = ROOT / item, destination / item
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, target)
    # prepare binds a keyed fingerprint of the checkout's HEAD (a contained `git rev-parse`), so the scratch tree is
    # a repository with one empty commit; nothing else reads its Git state.
    env = {"PATH": "/usr/bin:/bin", "HOME": str(destination), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_AUTHOR_NAME": "canary-mutants", "GIT_AUTHOR_EMAIL": "canary-mutants@invalid",
           "GIT_COMMITTER_NAME": "canary-mutants", "GIT_COMMITTER_EMAIL": "canary-mutants@invalid"}
    for argv in (["git", "init", "-q"], ["git", "commit", "-q", "--allow-empty", "-m", "scratch"]):
        subprocess.run(argv, cwd=destination, env=env, stdin=subprocess.DEVNULL, capture_output=True, check=True)


def apply(tree: Path, row: dict) -> str:
    """Apply one mutant's edits in tree; return its unified diff. Each edit must occur exactly once."""
    path = tree / row["target_file"]
    before = path.read_text(encoding="utf-8")
    after = before
    for old, new in row["edits"]:
        if after.count(old) != 1:
            raise ValueError(f"{row['id']}: edit text occurs {after.count(old)} times")
        after = after.replace(old, new)
    path.write_text(after, encoding="utf-8")
    for cache in tree.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        "a/" + row["target_file"], "b/" + row["target_file"]))


def run_test(tree: Path, test: str) -> tuple:
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PYTHON", "GIT_"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        done = subprocess.run([sys.executable, "-B", "-m", "unittest", "-v", test], cwd=tree, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as error:
        return None, (error.stdout or b"") + (error.stderr or b"") + b"\n[canary_mutants: timeout]\n"
    return done.returncode, done.stdout + done.stderr


def killed_by(code, output: bytes, label: str) -> bool:
    text = output.decode("utf-8", "replace")
    if code in (0, None) or re.search(r"^(ImportError|ModuleNotFoundError|SyntaxError|IndentationError)", text, re.M):
        return False
    return "AssertionError" in text and re.search(r" : " + re.escape(label) + r"$", text, re.M) is not None


def pristine(work: Path, test: str) -> tuple:
    tree = Path(tempfile.mkdtemp(prefix="pristine-", dir=work))
    try:
        copy_inputs(tree)
        code, output = run_test(tree, test)
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    return code == 0 and b"\nOK" in output, output


def one(work: Path, row: dict) -> tuple:
    tree = Path(tempfile.mkdtemp(prefix=row["id"] + "-", dir=work))
    try:
        copy_inputs(tree)
        patch = apply(tree, row)
        code, output = run_test(tree, row["killing_test"])
    except ValueError as error:
        return "", False, str(error).encode()
    finally:
        shutil.rmtree(tree, ignore_errors=True)
    return patch, killed_by(code, output, row["failing_assertion"]), output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="canary_mutants.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="one JSON object per mutant on stdout")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--only", default="", help="comma-separated mutant ids")
    parser.add_argument("--keep", help="artifact directory (default: a new /tmp/canary-mutants-* directory)")
    parser.add_argument("--check", action="store_true", help="only verify that every edit applies once")
    args = parser.parse_args(argv)
    wanted = [ident for ident in args.only.split(",") if ident]
    rows = [row for row in MUTANTS if not wanted or row["id"] in wanted]
    if len({row["id"] for row in MUTANTS}) != len(MUTANTS) or (wanted and len(rows) != len(set(wanted))) \
            or args.jobs < 1:
        parser.error("unknown or duplicate mutant id, or --jobs below 1")
    before = {str(path): digest(path) for path in input_files()}
    if args.check:
        bad = []
        with tempfile.TemporaryDirectory(prefix="canary-mutants-check-") as scratch:
            copy_inputs(Path(scratch))
            for row in rows:
                source = (Path(scratch) / row["target_file"]).read_text(encoding="utf-8")
                bad += [f"{row['id']}: edit {n} occurs {source.count(old)} times"
                        for n, (old, _new) in enumerate(row["edits"], 1) if source.count(old) != 1]
                for old, new in row["edits"]:
                    source = source.replace(old, new)
                try:
                    compile(source, row["target_file"], "exec")
                except SyntaxError:
                    bad.append(f"{row['id']}: the mutated file does not compile")
        print("\n".join(bad) or f"all {len(rows)} mutants apply exactly once and compile")
        return 1 if bad else 0
    keep = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="canary-mutants-"))
    keep.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="work-", dir=keep))
    tests = sorted({row["killing_test"] for row in rows})
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        baseline = dict(zip(tests, pool.map(lambda test: pristine(work, test), tests)))
        for test, (_passed, output) in baseline.items():
            (keep / f"pristine-{test.rsplit('.', 2)[-2]}.{test.rsplit('.', 1)[-1]}.log").write_bytes(output)
        outcomes = list(pool.map(lambda row: one(work, row), rows))
    shutil.rmtree(work, ignore_errors=True)
    table, failed = [], False
    for row, (patch, killed, output) in zip(rows, outcomes):
        killed = killed and baseline[row["killing_test"]][0]
        failed |= not killed
        (keep / f"{row['id']}.patch").write_text(patch, encoding="utf-8")
        (keep / f"{row['id']}.log").write_bytes(output)
        record = {"id": row["id"], "target_file": row["target_file"],
                  "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
                  "killing_test": row["killing_test"], "failing_assertion": row["failing_assertion"],
                  "killed": killed}
        table.append(dict(record, fault=row["fault"], pristine_passed=baseline[row["killing_test"]][0]))
        if args.json:
            print(json.dumps(record, sort_keys=True), flush=True)
        else:
            print(f"{row['id']:6} {'killed' if killed else 'SURVIVED'}  {row['fault']}  <- {row['killing_test']} "
                  f"[{row['failing_assertion']}]", flush=True)
    (keep / "table.json").write_text(json.dumps(table, indent=2), encoding="utf-8")
    after = {str(path): digest(path) for path in input_files()}
    unchanged = after == before
    killed_count = sum(row["killed"] for row in table)
    sys.stderr.write(f"canary_mutants: {killed_count}/{len(table)} killed; pristine runs passed "
                     f"{sum(passed for passed, _o in baseline.values())}/{len(baseline)}; repository inputs "
                     f"{'unchanged' if unchanged else 'CHANGED'}; artifacts {keep}\n")
    return 0 if not failed and unchanged else 1


if __name__ == "__main__":
    sys.exit(main())
