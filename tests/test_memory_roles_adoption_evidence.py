"""Local source-binding regressions; no native process, network or model task.

Uses the repository's unittest receipt checks (test_ecosystem_manifest.py) and
the SHA256-pinned adoption/G5 captures selected by the #835 review. These checks
establish record consistency, never truth or upstream memory acceptance.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs/decisions/2026-10-08-memory-roles-live-host.json"
SOURCE = ROOT / "docs/decisions/memory-adoption-835"
DECISIONS = {
    "claude_native_memory", "ai_memory", "hindsight", "context_mode",
    "codebase_memory", "qmd", "graphiti",
}
HASHES = {
    "adoption-now-5de97cf238b3d28a.json":
        "5de97cf238b3d28aa9f7d5110a05857204a847b0c75cda8971de8e142e362e36",
    "adoption-now-8682d1d326f29798.json":
        "8682d1d326f2979802efa32d156d9db14dba3ce04273328b6b48a0e227533ac7",
    "INVOKE-RATES-24H-20261008T2330Z.md":
        "86e8a4e0db11846eed1c4e99d5e89321b576cab087aa07676188705de593e541",
    "g5-grand-catalog-ae6cc228.json":
        "ff3b593c34b5f27caba29a915d3ed5443cb3a3d3ebb7e46937277529f0637dc9",
    "ROLE-MCP-TRIAL-REPORT-20261009.md":
        "f0afc2c734b3ad1b70e68cd38d3c844c7f4b1338cc030c8fc40fc88db1e53989",
    "registry-role-identities.json":
        "fc6f5dd30aa8dfa78932f1cb81b11abea311beca3d306927e21cb75f54ec765e",
}
NAMESPACES = {
    "ai-memory", "hindsight", "context-mode", "plugin_context-mode_context-mode",
    "codebase-memory-mcp", "qmd", "qmdshared",
}
WINDOWS = {"baseline", "reconciled"}
REGISTRY = SOURCE / "registry-role-identities.json"
HINDSIGHT_PIN = "5fc4ce20917b916240cef27c212c387a177f115b"
HINDSIGHT_SKILL_SHA256 = "736dec06d414798f6b17dc078c5ef6204e8802f53cb3a5fb3c306ce08872f08e"
HINDSIGHT_BINARY_SHA256 = "be87c63714ff046ac8ed668465ca0c875f94e6ff0a89ed83da7eb387313197af"
TRADING_REPOSITORY = "seathatflowsinourveins/us-equities-trading"
NATIVE_REPOSITORY = "seathatflowsinourveins/native-agent-stack"
LANE_DOCUMENTS = (
    ROOT / "docs/decisions/2026-10-07-foundation-finalization.md",
    SOURCE / "README.md",
)


def markdown_rows(text, columns):
    """Parse the named table by header rather than depending on row offsets."""
    header = None
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            if header is not None:
                break
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if header is None:
            if set(columns).issubset(cells):
                header = cells
            continue
        if len(cells) == len(header) and all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        if len(cells) != len(header):
            raise ValueError("malformed table row")
        rows.append(dict(zip(header, cells)))
    if header is None:
        raise ValueError(f"missing markdown table with columns {columns}")
    return rows


def metric_value(value):
    cleaned = value.strip().replace(",", "")
    if cleaned in {"-", "—", "null", "None", "UNMEASURED"}:
        return None
    return int(cleaned)


def pointer_value(document, pointer):
    value = document
    for part in pointer.removeprefix("/").split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def bash_blocks(text):
    """Read actual Markdown Bash fences, including indented tilde fences."""
    pattern = r"^[ \t]*(?P<fence>```|~~~)bash[ \t]*\n(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$"
    return [textwrap.dedent(match["body"]).strip() for match in
            re.finditer(pattern, text, re.MULTILINE | re.DOTALL)]


def run_cli_guard_fixture(packet, case):
    """Adapt the reader's pinned reproducer to current fenced commands.

    Source: reproduce_wire_guards.py, SHA256 43e9adfe8f7477af078543bbef62aa9f170594897a07fd9ade9eba8cbdae1da8.
    Only destination prefixes and curl are substituted. The published guard,
    checksum, interpreter and binary command ordering remains intact. No
    network or vendor code is executed; HOME itself is never overridden.
    """
    block = next(block for block in bash_blocks(packet)
                 if "HINDSIGHT_CLI_VERSION=0.10.2" in block)
    with tempfile.TemporaryDirectory(prefix="memory835-wire-guard-") as directory:
        fixture = Path(directory)
        stage = fixture / "stage"
        cli_root = fixture / "cli"
        binary = cli_root / "bin/hindsight"
        marker = fixture / "curl-called"
        downloaded = fixture / "fixture-installer"
        downloaded.write_text(
            "printf 'UNVERIFIED_INSTALLER_EXECUTED\\n'\n"
            'mkdir -p "$HINDSIGHT_INSTALL_DIR"\n'
            "printf '#!/bin/sh\\necho FIXTURE_BINARY_EXECUTED\\n' "
            '> "$HINDSIGHT_INSTALL_DIR/hindsight"\n'
            'chmod +x "$HINDSIGHT_INSTALL_DIR/hindsight"\n'
        )
        block = block.replace(
            "$HOME/.local/state/native-agent-stack/coordination/ns2604-coop/"
            "memory-roles-835-fix2-20261009/cli-review", str(stage))
        block = block.replace("$HOME/.local/opt/hindsight-cli/0.10.2", str(cli_root))
        # CI runs the portable committed packet; private host files are not inputs.
        if "$HOME/.local/" in block:
            raise ValueError("unmapped host destination in offline fixture")
        prefix = ("curl() { printf 'called\\n' > " + shlex.quote(str(marker)) + "; "
                  "cp -- " + shlex.quote(str(downloaded)) + ' "${@: -1}"; }\n')
        original = b"PREEXISTING_CLI\x00preserved\n"
        if case == "failed-download":
            prefix = "curl() { return 22; }\n"
        elif case == "preexisting-binary":
            binary.parent.mkdir(parents=True)
            binary.write_bytes(original)
        elif case != "incorrect-installer-hash":
            raise ValueError(case)
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", prefix + block],
                                capture_output=True, text=True, timeout=20,
                                cwd=fixture, env=os.environ.copy())
        return {
            "rc": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "binary_bytes": binary.read_bytes() if binary.exists() else None,
            "original_bytes": original,
            "curl_called": marker.exists(),
        }


def projection(snapshot):
    """Only the exact counter and denominator fields used by this decision."""
    result = {
        "/codex_total_conversations": snapshot["codex_total_conversations"],
        "/claude_total_sessions": snapshot["claude_total_sessions"],
    }
    for group, identities in (("codex_by_lane", "conversations"),
                              ("claude_by_role", "sessions")):
        for bucket, row in snapshot[group].items():
            prefix = f"/{group}/{bucket}"
            result[f"{prefix}/{identities}"] = row[identities]
            for namespace, counter in row["servers"].items():
                if namespace in NAMESPACES:
                    for field in ("calls", identities):
                        result[f"{prefix}/servers/{namespace}/{field}"] = counter[field]
    for layer, row in snapshot["layers"].items():
        for namespace, counter in row["servers"].items():
            if namespace in NAMESPACES:
                for field, value in counter.items():
                    result[f"/layers/{layer}/servers/{namespace}/{field}"] = value
    return result


class MemoryRoleEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.record = json.loads(RECORD.read_text())
        self.evidence = self.record["adoption_evidence"]
        self.snapshots = {
            key: json.loads((ROOT / reference["source_file"]).read_text())
            for key, reference in self.evidence["snapshots"].items()
        }
        self.registry = json.loads(REGISTRY.read_text())

    def assert_role_bindings(self, evidence):
        self.assertEqual(set(evidence["snapshots"]), WINDOWS)
        self.assertEqual(set(evidence["per_decision_bindings"]), DECISIONS)
        for component, decision in evidence["per_decision_bindings"].items():
            self.assertTrue(decision["owning_lane_or_role"], component)
            self.assertTrue(decision["evidence_limit"], component)
            self.assertEqual(decision["snapshot_sources"], ["baseline", "reconciled"])
            self.assertTrue(decision["role_evidence"], component)
            seen = set()
            lane_buckets = {}
            for binding in decision["role_evidence"]:
                identity = (binding["client"], binding["snapshot_bucket"])
                self.assertNotIn(identity, seen, f"duplicate role bucket for {component}")
                seen.add(identity)
                kind = "conversations" if binding["client"] == "codex" else "sessions"
                group = "codex_by_lane" if binding["client"] == "codex" else "claude_by_role"
                self.assertEqual(binding["identity_kind"], kind)
                self.assertEqual(binding["scope_pointer"], f"/{group}/{binding['snapshot_bucket']}")
                self.assertEqual(set(binding["snapshots"]), WINDOWS,
                                 f"{component}: omitted or unknown snapshot window")
                if binding["client"] == "codex":
                    lane = binding["lane_id"]
                    self.assertIn(lane, self.registry["roles"])
                    registry_row = pointer_value(self.registry, binding["identity_registry_pointer"])
                    self.assertEqual(registry_row["alias"], binding["snapshot_bucket"])
                    self.assertIn(registry_row, self.registry["roles"][lane])
                    lane_buckets.setdefault(lane, set()).add(binding["snapshot_bucket"])
                elif binding["snapshot_bucket"] == "other Claude sessions":
                    self.assertIn("unattributed", binding["role_relation"].lower())
                    self.assertIsNone(binding.get("lane_id"), "unattributed bucket cannot own a lane")
                for window, measured in binding["snapshots"].items():
                    row = self.snapshots[window][group].get(binding["snapshot_bucket"])
                    counter = row["servers"].get(binding["server_namespace"]) if row else None
                    self.assertEqual(measured["denominator"], row[kind] if row else None)
                    self.assertEqual(measured["calls"], counter["calls"] if counter else None)
                    self.assertEqual(measured["identities"], counter[kind] if counter else None)
                    for field in ("calls", "identities", "denominator"):
                        if measured[field] is not None:
                            self.assertIs(type(measured[field]), int)
                    if counter is None:
                        self.assertTrue(measured["measurement"].startswith("UNMEASURED"))
            owner = decision["owning_lane_or_role"]
            if owner in self.registry["roles"]:
                self.assertIn(owner, lane_buckets, f"{component}: owning lane omitted")
            for lane, buckets in lane_buckets.items():
                self.assertEqual(buckets, {row["alias"] for row in self.registry["roles"][lane]},
                                 f"{component}: incomplete relaunch identity set for {lane}")
            self.assertIn(("claude", "wsl-architecture-design"), seen)
            self.assertIn(("claude", "other Claude sessions"), seen)

    def expected_lane_aggregate(self, lane, namespace, window):
        aliases = {row["alias"] for row in self.registry["roles"][lane]}
        buckets = self.snapshots[window]["codex_by_lane"]
        present = sorted(alias for alias in aliases if alias in buckets)
        absent = sorted(aliases - set(present))
        counters = [buckets[alias]["servers"][namespace] for alias in present
                    if namespace in buckets[alias]["servers"]]
        return {
            "calls": sum(row["calls"] for row in counters) if counters else None,
            "identities_sum": sum(row["conversations"] for row in counters) if counters else None,
            "denominator_sum": sum(buckets[alias]["conversations"] for alias in present)
                if present else None,
            "buckets_present": present,
            "buckets_absent": absent,
        }

    def assert_lane_aggregates(self, evidence):
        for component, decision in evidence["per_decision_bindings"].items():
            rows = [row for row in decision["role_evidence"] if row["client"] == "codex"]
            namespaces = {row["lane_id"]: row["server_namespace"] for row in rows}
            self.assertEqual(set(decision["lane_aggregates"]), set(namespaces), component)
            for lane, windows in decision["lane_aggregates"].items():
                self.assertEqual(set(windows), WINDOWS)
                for window, actual in windows.items():
                    expected = self.expected_lane_aggregate(lane, namespaces[lane], window)
                    self.assertEqual({key: actual[key] for key in expected}, expected,
                                     f"{component}/{lane}/{window}")
                    if expected["calls"] is None:
                        self.assertTrue(actual["measurement"].startswith("UNMEASURED"))
                    else:
                        self.assertIn("no cross-alias identity deduplication", actual["measurement"])

    def assert_trial_measurements(self, context):
        table = markdown_rows((ROOT / context["source_file"]).read_text(),
                              ("Arm", "Owned processes", "Owned PSS (kB)"))
        # Bind by the unchanged leading arm token (A/B/C); whole labels differ
        # in the retained producer and record, so compare the ordered rows too.
        expected = [(row["Arm"].split()[0], metric_value(row["Owned processes"]),
                     metric_value(row["Owned PSS (kB)"])) for row in table]
        actual = [(row["arm"].split()[0], row["owned_processes"], row["owned_pss_kb"])
                  for row in context["measurements"]]
        self.assertEqual(actual, expected)

    def assert_lane_summary(self, text):
        columns = ("Component", "Lane", "Baseline calls / identities sum / denominator sum",
                   "Reconciled calls / identities sum / denominator sum")
        rows = markdown_rows(text, columns)
        actual = {}
        for row in rows:
            component = row["Component"]
            self.assertNotIn(component, actual, "duplicate lane-summary component")
            self.assertIn(component, DECISIONS)
            decision = self.evidence["per_decision_bindings"][component]
            self.assertEqual(row["Lane"], decision["owning_lane_or_role"])
            actual[component] = {}
            for window, column in zip(("baseline", "reconciled"), columns[2:]):
                values = row[column].split("/")
                self.assertEqual(len(values), 3)
                actual[component][window] = tuple(metric_value(value) for value in values)
            lane = decision["owning_lane_or_role"]
            for window in WINDOWS:
                if lane in self.registry["roles"]:
                    bindings = [binding for binding in decision["role_evidence"]
                                if binding["client"] == "codex" and binding["lane_id"] == lane]
                    self.assertTrue(bindings)
                    expected = self.expected_lane_aggregate(lane, bindings[0]["server_namespace"], window)
                    metrics = tuple(expected[key] for key in ("calls", "identities_sum", "denominator_sum"))
                else:
                    metrics = (None, None, None)
                self.assertEqual(actual[component][window], metrics,
                                 f"Markdown contradicts source capture for {component}/{window}")
        self.assertEqual(set(actual), DECISIONS)

    def assert_four_stages(self, record):
        stages = record["adoption_stages"]
        self.assertEqual(set(stages), {"stage1", "stage2", "stage3", "stage4"})
        self.assertEqual(set(stages["stage1"]["role_slots"]), DECISIONS)
        for stage in ("stage2", "stage3", "stage4"):
            self.assertEqual(set(stages[stage]["tools"]), DECISIONS, stage)
        for component, decision in record["adoption_evidence"]["per_decision_bindings"].items():
            choice = stages["stage1"]["role_slots"][component]
            self.assertEqual(choice["choice_status"], "PENDING until G5")
            self.assertIn(choice["desired_disposition"], {"KEEP", "WIRE", "DEFER"})
            self.assertIs(type(choice["accepted_keep"]), bool)
            install = stages["stage2"]["tools"][component]
            self.assertEqual(install["owning_lane_or_role"], decision["owning_lane_or_role"])
            self.assertTrue(install["pin"]["repository"])
            self.assertTrue(install["pin"]["version"])
            self.assertRegex(install["pin"]["commit"], r"^[0-9a-f]{40}$")
            self.assertTrue(install["install_routing"]["inverse"])
            self.assertEqual(install["executed_host_steps"], [])
            self.assertIsNone(install["component_per_session_pss_kb"])
            self.assertEqual(install["unexecuted_steps_status"], "OUTSTANDING")
            organic = []
            for stage in ("stage3", "stage4"):
                row = stages[stage]["tools"][component]
                self.assertEqual(row["owning_lane_or_role"], decision["owning_lane_or_role"])
                self.assertIs(type(row["organic_use_established"]), bool)
                self.assertIsInstance(row["results"], list)
                if row["organic_use_established"]:
                    organic.extend(row["results"])
                else:
                    self.assertEqual(row["execution_status"], "OUTSTANDING")
                    self.assertEqual(row["results"], [])
            if decision["disposition"].startswith("KEEP") and not decision["disposition"].startswith("KEEP proposed"):
                self.assertTrue(choice["accepted_keep"])
                self.assertTrue(organic, f"{component}: KEEP lacks stage3/4 organic evidence")
                for result in organic:
                    self.assertIsInstance(result, dict)
                    provenance = result.get("provenance")
                    self.assertIsInstance(provenance, dict, "organic result lacks source provenance")
                    self.assertTrue(provenance.get("source_file"))
                    self.assertRegex(provenance.get("sha256", ""), r"^[0-9a-f]{64}$")
                    self.assertEqual(hashlib.sha256((ROOT / provenance["source_file"]).read_bytes()).hexdigest(),
                                     provenance["sha256"])
                    self.assertTrue(result.get("returned_result"), "organic result lacks returned result")
            elif choice["desired_disposition"] == "KEEP":
                self.assertEqual(decision["disposition"], "KEEP proposed")
                self.assertFalse(choice["accepted_keep"])

    def assert_hindsight_project_wiring(self, wiring):
        """Check the CC-approved scope and recorded plan, not host deployment."""
        scope = wiring["scope_decision"]
        self.assertTrue(scope["user_roots"].startswith("REJECTED"))
        self.assertEqual(scope["approved_cli_prefix"], "$HOME/.local/opt/hindsight-cli/0.10.2/bin")
        self.assertIs(scope["path_or_profile_change"], False)
        trading = scope["trading_project"]
        native = scope["native_blueprint_project"]
        self.assertEqual(trading["repository"], TRADING_REPOSITORY)
        self.assertEqual(trading["pull_request"], 15)
        self.assertEqual(trading["url"], f"https://github.com/{TRADING_REPOSITORY}/pull/15")
        self.assertRegex(trading["head"], r"^[0-9a-f]{40}$")
        self.assertEqual(native["repository"], NATIVE_REPOSITORY)
        self.assertEqual(native["pull_request"], 835)
        self.assertEqual(native["relative_project_root"], "blueprints/us-equities")
        self.assertFalse(trading["merged"])
        self.assertFalse(native["merged"])

        source = wiring["skill_source"]
        self.assertEqual(source["repository"], "vectorize-io/hindsight")
        self.assertEqual(source["commit"], HINDSIGHT_PIN)
        self.assertEqual(source["version"], "v0.10.2")
        self.assertEqual(source["file"],
                         "hindsight-integrations/agent-plugin/skills/hindsight-memory/SKILL.md")
        self.assertEqual(source["sha256"], HINDSIGHT_SKILL_SHA256)
        self.assertEqual(source["bytes"], 2758)
        self.assertIs(source["unchanged"], True)

        self.assertEqual(set(wiring["client_routes"]), {"claude", "codex"})
        local_skill_bytes = []
        for client, skill_root in (("claude", ".claude/skills/hindsight-memory"),
                                   ("codex", ".agents/skills/hindsight-memory")):
            route = wiring["client_routes"][client]
            self.assertEqual(route["skill_root"], skill_root)
            self.assertIsNone(route["install_command"])
            self.assertIs(route["user_root_rejected"], True)
            self.assertIs(route["native_repo_root_rejected"], True)
            self.assertIs(route["staged"], True)
            self.assertIs(route["applied"], False)
            self.assertEqual(route["status"], "OUTSTANDING")
            self.assertEqual(route["vendor_sha256"], source["sha256"])
            expected = {
                (TRADING_REPOSITORY, f"{skill_root}/SKILL.md", 15),
                (NATIVE_REPOSITORY, f"blueprints/us-equities/{skill_root}/SKILL.md", 835),
            }
            self.assertEqual(len(route["targets"]), 2)
            self.assertEqual({(row["repository"], row["path"], row["pull_request"])
                              for row in route["targets"]}, expected)
            for row in route["targets"]:
                if row["repository"] == TRADING_REPOSITORY:
                    self.assertEqual(row["head"], trading["head"])
                    self.assertIn(row["path"], trading["changed_files"])
                else:
                    self.assertIn(row["path"], native["changed_files"])
                    data = (ROOT / row["path"]).read_bytes()
                    self.assertEqual(len(data), source["bytes"])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), source["sha256"])
                    local_skill_bytes.append(data)
        self.assertEqual(len(local_skill_bytes), 2)
        self.assertEqual(local_skill_bytes[0], local_skill_bytes[1])

        cli = wiring["cli"]
        self.assertEqual(cli["version"], "0.10.2")
        self.assertEqual(cli["source_commit"], HINDSIGHT_PIN)
        self.assertIn("HINDSIGHT_CLI_VERSION=0.10.2", cli["install_command"])
        self.assertIn(scope["approved_cli_prefix"], cli["install_command"])
        digest = cli["binary_digest_check"]
        self.assertEqual(digest["sha256"], HINDSIGHT_BINARY_SHA256)
        self.assertEqual(digest["asset"], "hindsight-linux-amd64")
        self.assertEqual(digest["release_tag"], "v0.10.2")
        self.assertEqual(digest["source"],
                         "https://api.github.com/repos/vectorize-io/hindsight/releases/tags/v0.10.2")
        self.assertEqual(digest["release_metadata_sha256"],
                         "8ce08cd4cc97254733c4c0a61631b2bb6332594eb01f3ba12f3947c7e52bf5b7")
        self.assertIs(digest["before_first_binary_execution"], True)
        self.assertIs(digest["executed"], False)
        self.assertEqual(digest["status"], "OUTSTANDING")
        self.assertEqual(digest["operator"], "CC")
        args = shlex.split(digest["command"])
        self.assertEqual(args[0], "printf")
        self.assertIn(HINDSIGHT_BINARY_SHA256, args)
        self.assertIn("$memory835_cli_root/bin/hindsight", args)
        self.assertEqual(args[-4:], ["|", "sha256sum", "--check", "--status"])
        packet = (ROOT / wiring["packet"]["source_file"]).read_text()
        self.assertLess(packet.index(HINDSIGHT_BINARY_SHA256),
                        packet.index('"$memory835_cli_root/bin/hindsight" --version'))

        for client in ("claude", "codex"):
            smoke = wiring["smokes"][client]
            self.assertEqual(smoke["operator"], "CC")
            self.assertEqual(smoke["session_start_cwd"], "$HOME/code/us-equities-trading")
            self.assertEqual(smoke["additional_admitted_cwd"],
                             "$HOME/code/native-agent-stack/blueprints/us-equities")
            self.assertIs(smoke["resume_or_fork"], False)
            self.assertIs(smoke["executed"], False)
            self.assertEqual(smoke["status"], "OUTSTANDING")
            self.assertIsNone(smoke["result"])
            args = shlex.split(smoke["command"])
            self.assertEqual(args[:3], ["cd", smoke["session_start_cwd"], "&&"])
            self.assertEqual(args[3], client)
            self.assertIn("get_bank", args[-1])
            if client == "claude":
                self.assertIn("--allowedTools", args)
                self.assertEqual(args[args.index("--allowedTools") + 1], "mcp__hindsight__get_bank")
        harness = wiring["smokes"]["upstream_harness"]
        self.assertEqual(harness["status"], "DEFERRED")
        self.assertIsNone(harness["command"])
        self.assertIs(harness["executed"], False)
        self.assertIsNone(harness["result"])
        self.assertIn("scratch", harness["reason"])
        self.assertIn("provider", harness["reason"])

    def assert_g5_bindings(self, evidence):
        self.assertEqual(set(evidence["per_decision_bindings"]), DECISIONS)
        for component, decision in evidence["per_decision_bindings"].items():
            self.assertIn("g5_binding", decision, component)
            binding = decision["g5_binding"]
            self.assertEqual(binding["commit"], "ae6cc2286643822d3a0218136722c69d0127fcd4")
            self.assertEqual(binding["pr"], 878)
            self.assertTrue(binding["catalog_owner"])
            self.assertTrue(binding["resolution_dependency"])
            source = ROOT / binding["source_file"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), binding["source_sha256"])
            rows = json.loads(source.read_text())["rows"]
            pointer = binding["row_pointer"]
            if pointer is not None:
                self.assertEqual(binding["status"], "PENDING until G5 lands")
                self.assertEqual(rows[int(pointer.rsplit("/", 1)[1])]["repository_or_entry"].lower(),
                                 binding["component_identity"].lower())
            else:
                self.assertEqual(binding["status"], "PENDING — row absent at this G5 pin")
                identity = binding["component_identity"].removeprefix("https://github.com/").lower()
                self.assertFalse(any(identity in json.dumps(row).lower() for row in rows))

    def test_source_bytes_and_snapshot_metadata_match_exact_pins(self):
        for filename, digest in HASHES.items():
            with self.subTest(source=filename):
                self.assertEqual(hashlib.sha256((SOURCE / filename).read_bytes()).hexdigest(), digest)
        self.assertEqual(set(self.snapshots), {"baseline", "reconciled"})
        for key, source in self.evidence["snapshots"].items():
            snapshot = self.snapshots[key]
            self.assertEqual(source["sha256"], HASHES[Path(source["source_file"]).name])
            self.assertEqual(source["generated_utc"], snapshot["generated_utc"])
            self.assertEqual(source["window_hours"], snapshot["window_hours"])
            self.assertEqual(source["window_hours"], 24)
            self.assertEqual(source["codex_population"], snapshot["codex_total_conversations"])
            self.assertEqual(source["claude_population"], snapshot["claude_total_sessions"])
        self.assertNotEqual(self.snapshots["baseline"]["generated_utc"],
                            self.snapshots["reconciled"]["generated_utc"])

    def test_every_decision_binds_exact_role_calls_identities_and_denominator(self):
        self.assert_role_bindings(self.evidence)

    def test_reconciliation_covers_every_changed_relevant_scalar(self):
        before = projection(self.snapshots["baseline"])
        after = projection(self.snapshots["reconciled"])
        expected = {
            pointer: {
                "pointer": pointer, "baseline_present": pointer in before,
                "baseline": before.get(pointer), "reconciled_present": pointer in after,
                "reconciled": after.get(pointer),
            }
            for pointer in set(before) | set(after)
            if before.get(pointer) != after.get(pointer) or (pointer in before) != (pointer in after)
        }
        actual_rows = self.evidence["reconciliation"]["changed_fields"]
        actual = {row["pointer"]: row for row in actual_rows}
        self.assertEqual(len(actual), len(actual_rows), "duplicate scalar reconciliation")
        self.assertEqual(actual, expected)
        for window, snapshot in self.snapshots.items():
            rollups = {name: value for layer in snapshot["layers"].values()
                       for name, value in layer["servers"].items() if name in NAMESPACES}
            self.assertEqual(self.evidence["reconciliation"]["producer_layer_rollups"][window], rollups)

    def test_native_memory_and_graphiti_remain_unmeasured(self):
        for component in ("claude_native_memory", "graphiti"):
            decision = self.evidence["per_decision_bindings"][component]
            self.assertTrue(decision["organic_use"].startswith("UNRESOLVED"))
            for binding in decision["role_evidence"]:
                for measured in binding["snapshots"].values():
                    self.assertIsNone(measured["calls"])
                    self.assertIsNone(measured["identities"])
                    self.assertTrue(measured["measurement"].startswith("UNMEASURED"))

    def test_each_g5_binding_is_present_or_individually_pending(self):
        self.assert_g5_bindings(self.evidence)
        present = {key: value["g5_binding"]["row_pointer"]
                   for key, value in self.evidence["per_decision_bindings"].items()
                   if value["g5_binding"]["row_pointer"] is not None}
        self.assertEqual(present, {"ai_memory": "/rows/7", "codebase_memory": "/rows/32"})

    def test_old_markdown_is_history_with_reproducible_source_bytes(self):
        self.assertNotIn("invoke_rates", self.record["routing_supplement"])
        history = self.record["routing_supplement"]["historical_invoke_rates"]
        self.assertTrue(history["evidence_status"].startswith("DATED HISTORY ONLY"))
        source = ROOT / history["source_file"]
        self.assertEqual(source.stat().st_size, 2438)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), history["sha256"])

    def test_missing_role_binding_cannot_pass_as_client_total_evidence(self):
        changed = copy.deepcopy(self.evidence)
        changed["per_decision_bindings"]["ai_memory"]["role_evidence"] = []
        with self.assertRaises(AssertionError):
            self.assert_role_bindings(changed)

    def test_mixed_window_counter_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        measured = changed["per_decision_bindings"]["context_mode"]["role_evidence"][0]["snapshots"]
        measured["reconciled"]["calls"] = measured["baseline"]["calls"]
        with self.assertRaises(AssertionError):
            self.assert_role_bindings(changed)

    def test_registry_excerpt_binds_every_identity_at_a_hashed_source(self):
        registry_reference = self.evidence["identity_registry"]
        self.assertEqual(ROOT / registry_reference["source_file"], REGISTRY)
        self.assertEqual(registry_reference["sha256"], hashlib.sha256(REGISTRY.read_bytes()).hexdigest())
        self.assertEqual(set(self.registry["roles"]),
                         {"memory-h2h", "codex-token-parity", "overlap-token"})
        for lane, identities in self.registry["roles"].items():
            self.assertTrue(identities)
            self.assertEqual(len(identities), len({row["alias"] for row in identities}))
            for row in identities:
                self.assertEqual(row["name"], f"{lane}-{row['alias']}")
                self.assertRegex(row["source_sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(row["source"])
                self.assertTrue(row["field"])

    def test_relaunch_lane_aggregates_recompute_from_source_rows(self):
        self.assert_lane_aggregates(self.evidence)

    def test_missing_relaunch_identity_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        decision = changed["per_decision_bindings"]["context_mode"]
        aliases = [row for row in decision["role_evidence"]
                   if row["client"] == "codex" and row["lane_id"] == "codex-token-parity"]
        self.assertGreater(len(aliases), 1, "fixture must contain actual relaunch aliases")
        decision["role_evidence"].remove(aliases[-1])
        with self.assertRaises(AssertionError):
            self.assert_role_bindings(changed)

    def test_unmeasured_post_window_aliases_cannot_be_dropped(self):
        for component, alias in (("ai_memory", "revi"), ("context_mode", "zonu")):
            with self.subTest(component=component, alias=alias):
                decision = self.evidence["per_decision_bindings"][component]
                row = next(row for row in decision["role_evidence"]
                           if row["client"] == "codex" and row["snapshot_bucket"] == alias)
                self.assertIsNone(row["snapshots"]["baseline"]["denominator"])
                changed = copy.deepcopy(self.evidence)
                changed["per_decision_bindings"][component]["role_evidence"].remove(row)
                with self.assertRaises(AssertionError):
                    self.assert_role_bindings(changed)

    def test_binding_window_missing_extra_or_renamed_is_rejected(self):
        for mutation in ("missing", "extra", "renamed"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.evidence)
                windows = changed["per_decision_bindings"]["ai_memory"]["role_evidence"][0]["snapshots"]
                if mutation == "missing":
                    windows.pop("reconciled")
                elif mutation == "extra":
                    windows["unpublished"] = copy.deepcopy(windows["baseline"])
                else:
                    windows["new-window"] = windows.pop("reconciled")
                with self.assertRaises(AssertionError):
                    self.assert_role_bindings(changed)

    def test_snapshot_window_missing_extra_or_renamed_is_rejected(self):
        for mutation in ("missing", "extra", "renamed"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(self.evidence)
                windows = changed["snapshots"]
                if mutation == "missing":
                    windows.pop("reconciled")
                elif mutation == "extra":
                    windows["unpublished"] = copy.deepcopy(windows["baseline"])
                else:
                    windows["new-window"] = windows.pop("reconciled")
                with self.assertRaises(AssertionError):
                    self.assert_role_bindings(changed)

    def test_lane_aggregate_counter_drift_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        decision = changed["per_decision_bindings"]["context_mode"]
        decision["lane_aggregates"]["codex-token-parity"]["baseline"]["calls"] += 1
        with self.assertRaises(AssertionError):
            self.assert_lane_aggregates(changed)

    def test_lane_aggregate_window_drift_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        windows = changed["per_decision_bindings"]["context_mode"]["lane_aggregates"]["codex-token-parity"]
        windows["new-window"] = windows.pop("reconciled")
        with self.assertRaises(AssertionError):
            self.assert_lane_aggregates(changed)

    def test_each_tool_records_all_four_adoption_stages(self):
        self.assert_four_stages(self.record)

    def test_missing_stage_or_tool_is_rejected(self):
        for stage in ("stage3", "stage4"):
            with self.subTest(stage=stage, mutation="stage"):
                changed = copy.deepcopy(self.record)
                changed["adoption_stages"].pop(stage)
                with self.assertRaises(AssertionError):
                    self.assert_four_stages(changed)
            with self.subTest(stage=stage, mutation="tool"):
                changed = copy.deepcopy(self.record)
                changed["adoption_stages"][stage]["tools"].pop("hindsight")
                with self.assertRaises(AssertionError):
                    self.assert_four_stages(changed)

    def test_raw_keep_without_organic_use_is_rejected(self):
        changed = copy.deepcopy(self.record)
        changed["adoption_evidence"]["per_decision_bindings"]["context_mode"]["disposition"] = "KEEP"
        changed["adoption_stages"]["stage1"]["role_slots"]["context_mode"]["accepted_keep"] = True
        with self.assertRaises(AssertionError):
            self.assert_four_stages(changed)

    def test_organic_flag_without_returned_result_provenance_cannot_accept_keep(self):
        changed = copy.deepcopy(self.record)
        changed["adoption_evidence"]["per_decision_bindings"]["context_mode"]["disposition"] = "KEEP"
        changed["adoption_stages"]["stage1"]["role_slots"]["context_mode"]["accepted_keep"] = True
        organic = changed["adoption_stages"]["stage3"]["tools"]["context_mode"]
        organic["organic_use_established"] = True
        organic["results"] = [{"calls": 1, "note": "counter is not an organic outcome"}]
        with self.assertRaises(AssertionError):
            self.assert_four_stages(changed)

    def test_machine_checked_markdown_lane_summaries_match_source_counters(self):
        for path in LANE_DOCUMENTS:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assert_lane_summary(path.read_text())

    def test_markdown_counter_drift_is_rejected(self):
        text = LANE_DOCUMENTS[0].read_text()
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("| context_mode |"):
                cells = line.split("|")
                metrics = cells[3].split("/")
                metrics[0] = str(metric_value(metrics[0]) + 1)
                cells[3] = " / ".join(metrics)
                lines[index] = "|".join(cells)
                break
        else:
            self.fail("context_mode summary row missing")
        with self.assertRaises(AssertionError):
            self.assert_lane_summary("\n".join(lines))

    def test_invented_pending_g5_pointer_is_rejected(self):
        changed = copy.deepcopy(self.evidence)
        binding = changed["per_decision_bindings"]["graphiti"]["g5_binding"]
        binding["row_pointer"] = "/rows/7"
        binding["status"] = "PENDING until G5 lands"
        with self.assertRaises(AssertionError):
            self.assert_g5_bindings(changed)

    def test_accepted_research_job_is_preserved_by_wiring(self):
        landscape = json.loads((ROOT / "manifests/landscape.json").read_text())
        job = landscape["research_memory_jobs"][0]
        self.assertEqual(job["id"], "hindsight-research-memory")
        self.assertIn("native operation accepted", job["status"])
        decision = self.evidence["per_decision_bindings"]["hindsight"]
        self.assertEqual(decision["disposition"], "WIRE")
        self.assertEqual(decision["accepted_job_reference"],
                         "manifests/landscape.json#/research_memory_jobs/0")
        self.assertEqual(decision["wiring"]["recall_types"], ["world", "experience"])
        self.assertEqual(decision["wiring"]["tags_match"], "all_strict")
        self.assertEqual(decision["wiring"]["mcp_allowlist_tools"], 15)
        self.assertFalse(decision["wiring"]["applied"])
        self.assertEqual(self.evidence["per_decision_bindings"]["ai_memory"]["disposition"], "WIRE")
        self.assertEqual(self.evidence["per_decision_bindings"]["graphiti"]["disposition"], "DEFER")
        self.assertFalse(self.evidence["retention_policy"]["counters_gate_readiness"])

    def test_wire_packets_have_exact_hashes_and_explicit_unexecuted_steps(self):
        hindsight = self.evidence["per_decision_bindings"]["hindsight"]["wiring"]
        references = {
            "hindsight": (hindsight["packet"], {f"HW-{i:02d}" for i in range(1, 11)}),
            "ai_memory": (self.record["adoption_stages"]["stage2"]["tools"]["ai_memory"]["install_routing"]["packet"],
                          {f"AM-{i:02d}" for i in range(1, 4)} | {f"QMD-{i:02d}" for i in range(1, 4)}),
        }
        outstanding = self.record["outstanding"]
        ids = [row["id"] for row in outstanding]
        self.assertEqual(len(ids), len(set(ids)), "duplicate outstanding id")
        self.assertEqual(self.record["delta_review_correction"]["outstanding_count"], len(ids))
        for reference, expected_ids in references.values():
            source = ROOT / reference["source_file"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), reference["sha256"])
            packet = source.read_text()
            parsed = re.findall(r"^\d+\. \*\*((?:HW|AM|QMD)-\d+)\b", packet, re.MULTILINE)
            self.assertEqual(set(parsed), expected_ids)
            self.assertEqual(len(parsed), len(expected_ids))
            for step in expected_ids:
                entry = next(row for row in outstanding if row["id"] == step)
                self.assertEqual(entry["source_file"], reference["source_file"])
            self.assertIn("applied=false", packet)
            self.assertIn("OUTSTANDING", packet)
        for row in outstanding:
            self.assertEqual(row["status"], "OUTSTANDING")
            self.assertIs(row["executed"], False)
            self.assertIsNone(row["result"])
        for component in DECISIONS:
            self.assertTrue({f"MV-{stage}-{component}" for stage in ("PSS", "S3", "S4", "G5")}.issubset(ids))
        self.assert_hindsight_project_wiring(hindsight)

    def test_stage_two_hindsight_route_matches_decision_binding(self):
        wiring = self.evidence["per_decision_bindings"]["hindsight"]["wiring"]
        stage2 = self.record["adoption_stages"]["stage2"]["tools"]["hindsight"]["install_routing"]
        for field in ("packet", "cli", "client_routes", "inverse", "smokes"):
            with self.subTest(field=field):
                self.assertEqual(stage2[field], wiring[field])

    def test_hindsight_user_wide_skill_route_is_rejected(self):
        for client, root in (("claude", ".claude"), ("codex", ".agents")):
            with self.subTest(client=client):
                wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                wiring["client_routes"][client]["skill_root"] = f"$HOME/{root}/skills/hindsight-memory"
                with self.assertRaises(AssertionError):
                    self.assert_hindsight_project_wiring(wiring)

    def test_hindsight_native_repository_root_target_is_rejected(self):
        for client in ("claude", "codex"):
            with self.subTest(client=client):
                wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                target = next(row for row in wiring["client_routes"][client]["targets"]
                              if row["repository"] == NATIVE_REPOSITORY)
                target["path"] = target["path"].removeprefix("blueprints/us-equities/")
                with self.assertRaises(AssertionError):
                    self.assert_hindsight_project_wiring(wiring)

    def test_hindsight_binary_digest_and_first_execution_gate_cannot_drift(self):
        mutations = {
            "wrong_digest": ("sha256", "0" * 64),
            "unverified_source": ("source", "https://example.invalid/unverified-release"),
            "unverified_capture": ("release_metadata_sha256", "0" * 64),
            "check_after_first_run": ("before_first_binary_execution", False),
            "not_a_hash_check": ("command", '"$memory835_cli_root/bin/hindsight" --version'),
        }
        for mutation, (field, value) in mutations.items():
            with self.subTest(mutation=mutation):
                wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                wiring["cli"]["binary_digest_check"][field] = value
                with self.assertRaises(AssertionError):
                    self.assert_hindsight_project_wiring(wiring)

    def test_hindsight_smokes_require_cc_fresh_research_cwd(self):
        for client in ("claude", "codex"):
            mutations = {
                "unscoped_cwd": ("session_start_cwd", "$HOME"),
                "native_root_cwd": ("additional_admitted_cwd", "$HOME/code/native-agent-stack"),
                "wrong_operator": ("operator", "lane"),
                "resumed_session": ("resume_or_fork", True),
            }
            for mutation, (field, value) in mutations.items():
                with self.subTest(client=client, mutation=mutation):
                    wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                    wiring["smokes"][client][field] = value
                    with self.assertRaises(AssertionError):
                        self.assert_hindsight_project_wiring(wiring)
            with self.subTest(client=client, mutation="command_omits_cwd"):
                wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                wiring["smokes"][client]["command"] = wiring["smokes"][client]["command"].split(" && ", 1)[1]
                with self.assertRaises(AssertionError):
                    self.assert_hindsight_project_wiring(wiring)

    def test_hindsight_deferred_scratch_harness_cannot_be_required_or_executed(self):
        for mutation, field, value in (
                ("executed", "executed", True),
                ("required", "status", "OUTSTANDING"),
                ("executable", "command", 'bash "$memory835_stage/hindsight-cli-smoke-test.sh"')):
            with self.subTest(mutation=mutation):
                wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
                wiring["smokes"]["upstream_harness"][field] = value
                with self.assertRaises(AssertionError):
                    self.assert_hindsight_project_wiring(wiring)

    def test_every_wire_bash_block_defines_its_own_strict_guards_and_variables(self):
        for name in ("hindsight-wire.diff.md", "wire-inverses-smokes.md"):
            blocks = bash_blocks((SOURCE / name).read_text())
            self.assertTrue(blocks, name)
            for index, block in enumerate(blocks):
                with self.subTest(packet=name, block=index):
                    lines = block.splitlines()
                    self.assertEqual(lines[0], "set -euo pipefail")
                    defined = set()
                    for line in lines:
                        referenced = set(re.findall(r"\$(?:\{)?(memory835_[a-z0-9_]+)", line))
                        self.assertTrue(referenced.issubset(defined),
                                        f"task variables used before block-local definition: {line}")
                        defined.update(re.findall(r"^\s*(memory835_[a-z0-9_]+)=", line))

    def test_actual_wire_bad_installer_checksum_stops_before_fixture_execution(self):
        packet = (SOURCE / "hindsight-wire.diff.md").read_text()
        result = run_cli_guard_fixture(packet, "incorrect-installer-hash")
        self.assertNotEqual(result["rc"], 0)
        self.assertTrue(result["curl_called"])
        self.assertIsNone(result["binary_bytes"])
        self.assertNotIn("UNVERIFIED_INSTALLER_EXECUTED", result["stdout"])
        self.assertNotIn("FIXTURE_BINARY_EXECUTED", result["stdout"])

    def test_actual_wire_failed_download_stops_before_fixture_execution(self):
        packet = (SOURCE / "hindsight-wire.diff.md").read_text()
        result = run_cli_guard_fixture(packet, "failed-download")
        self.assertNotEqual(result["rc"], 0)
        self.assertIsNone(result["binary_bytes"])
        self.assertNotIn("UNVERIFIED_INSTALLER_EXECUTED", result["stdout"])
        self.assertNotIn("FIXTURE_BINARY_EXECUTED", result["stdout"])

    def test_actual_wire_preexisting_cli_is_preserved_byte_for_byte(self):
        packet = (SOURCE / "hindsight-wire.diff.md").read_text()
        result = run_cli_guard_fixture(packet, "preexisting-binary")
        self.assertNotEqual(result["rc"], 0)
        self.assertFalse(result["curl_called"])
        self.assertEqual(result["binary_bytes"], result["original_bytes"])
        self.assertNotIn("UNVERIFIED_INSTALLER_EXECUTED", result["stdout"])
        self.assertNotIn("FIXTURE_BINARY_EXECUTED", result["stdout"])

    def test_hindsight_skill_route_has_no_host_install_or_overwrite_command(self):
        packet = (SOURCE / "hindsight-wire.diff.md").read_text()
        for block in bash_blocks(packet):
            self.assertNotRegex(block, r"(?m)^\s*(?:install|mkdir)\b.*skills/hindsight-memory")
        self.assertNotIn("bash \"$memory835_stage/hindsight-cli-smoke-test.sh\"", packet)

    def test_ai_memory_primary_route_and_smoke_match_the_wire_packet(self):
        packet = (SOURCE / "wire-inverses-smokes.md").read_text()
        commands = [line for block in bash_blocks(packet) for line in block.splitlines()
                    if line.startswith("ai-memory ")]
        route = self.record["adoption_stages"]["stage2"]["tools"]["ai_memory"]["install_routing"]
        for client in ("claude_preview", "codex_preview"):
            self.assertIn(route["client_supported_commands"][client], commands)
        self.assertIn(route["vendor_command"], commands)
        self.assertIn("install-instructions", route["vendor_command"])
        for command in commands:
            args = shlex.split(command)
            self.assertEqual(args[args.index("--data-dir") + 1], "$HOME/.local/share/ai-memory")
            self.assertEqual(args[args.index("--config") + 1], "$HOME/.config/ai-memory/config.toml")
        self.assertIn("memory_query", route["smoke"])
        self.assertNotIn("ai-memory --version", route["smoke"])
        self.assertIn("AM-02", route["inverse"])
        qmd = self.record["adoption_stages"]["stage2"]["tools"]["qmd"]["install_routing"]
        self.assertIn("QMD-02", qmd["inverse"])
        self.assertIn("unselected reviewed alternative", packet)

    def test_claude_smoke_without_get_bank_allowlist_is_rejected(self):
        wiring = copy.deepcopy(self.evidence["per_decision_bindings"]["hindsight"]["wiring"])
        wiring["smokes"]["claude"]["command"] = wiring["smokes"]["claude"]["command"].replace(
            "--allowedTools mcp__hindsight__get_bank ", "")
        with self.assertRaises(AssertionError):
            self.assert_hindsight_project_wiring(wiring)

    def test_hindsight_drafts_resolve_the_approved_cli_without_path(self):
        drafts = ROOT / "adoption/drafts/memory-maintenance-20261008"
        for name in ("native-memory-hindsight-model-refresh.service",
                     "native-memory-hindsight-reflect.service"):
            with self.subTest(unit=name):
                commands = [line.removeprefix("ExecStart=") for line in (drafts / name).read_text().splitlines()
                            if line.startswith("ExecStart=")]
                self.assertEqual(len(commands), 1)
                self.assertEqual(shlex.split(commands[0])[0],
                                 "%h/.local/opt/hindsight-cli/0.10.2/bin/hindsight")

    def test_every_role_has_organic_tasks_and_unstarted_24h_followup(self):
        for component in DECISIONS:
            stage3 = self.record["adoption_stages"]["stage3"]["tools"][component]
            stage4 = self.record["adoption_stages"]["stage4"]["tools"][component]
            tasks = stage3["per_role_tasks"]
            self.assertTrue(tasks)
            for task in tasks:
                self.assertTrue(task["natural_fresh_tasks"])
                self.assertTrue(task["observables"])
                self.assertFalse(task["executed"])
                self.assertIsNone(task["session_reference"])
                self.assertIsNone(task["result"])
            plan = stage4["hourly_plan"]
            self.assertIsNone(plan["anchor_utc"])
            self.assertEqual(plan["interval_hours"], 1)
            self.assertEqual(plan["last_sample"], "T0+24h")
            self.assertFalse(plan["scheduled"])
            self.assertFalse(plan["compared"])
            self.assertEqual({(row["role"], row["client"]) for row in tasks},
                             {(row["role"], row["client"]) for row in plan["per_role_follow_up"]})
            for row in plan["per_role_follow_up"]:
                self.assertEqual(row["due"], "T0+24h")
                self.assertEqual(row["status"], "OUTSTANDING")

    def test_draft_commands_use_named_native_config_and_project(self):
        drafts = ROOT / "adoption/drafts/memory-maintenance-20261008"
        for name in ("ai-lint", "ai-retention-review"):
            lines = (drafts / f"native-memory-{name}.service").read_text().splitlines()
            command = next(line.removeprefix("ExecStart=") for line in lines
                           if line.startswith("ExecStart="))
            args = shlex.split(command)
            self.assertIn("--config", args)
            self.assertEqual(args[args.index("--config") + 1], "%h/.config/ai-memory/config.toml")
            self.assertEqual(args[args.index("--workspace") + 1], "default")
            self.assertIn("EnvironmentFile=-%h/.config/ai-memory/env", lines)
        command = next(line.removeprefix("ExecStart=") for line in
                       (drafts / "native-memory-codegraph-coverage.service").read_text().splitlines()
                       if line.startswith("ExecStart="))
        parameters = json.loads(shlex.split(command)[-1])
        self.assertEqual(parameters["project"], "home-%u-code-native-agent-stack")
        self.assertEqual(parameters["project"].replace("%u", "<user>"),
                         self.record["review_correction"]["codegraph_registered_project"])

    def test_observation_groups_and_context_sources_are_separate(self):
        self.assertNotIn("observation_window_utc", self.record)
        windows = self.record["observation_windows_utc"]
        self.assertEqual(windows["routing_supplement"]["observed_at_utc"],
                         self.record["routing_supplement"]["observed_at_utc"])
        self.assertEqual(windows["native_memory_freshness"]["observed_at_utc"],
                         self.record["routing_supplement"]["native_memory_freshness"]["observed_at_utc"])
        context = next(v for v in self.record["versions"] if v["layer"] == "context-mode")["returned"]
        self.assertNotEqual(context["claude_plugin_record_commit"], context["codex_source_checkout"])
        self.assertNotEqual(context["claude_plugin_record_commit"], context["claude_marketplace_checkout"])

    def test_stage_two_cannot_infer_component_pss_from_whole_arm_memory(self):
        stages = self.record["adoption_stages"]
        choices = stages["stage1"]["role_slots"]
        self.assertEqual(set(choices), DECISIONS)
        self.assertEqual(len({row["role_slot"] for row in choices.values()}), len(DECISIONS))
        for row in choices.values():
            self.assertTrue(row["current_choice"])
            self.assertTrue(row["overlap_disposition"])
            self.assertFalse(row["parallel_default"])
            self.assertIsNone(row["per_session_pss_kb"])
            self.assertTrue(row["stage2_admission"].startswith("BLOCKED ADOPT-NOW"))
            self.assertFalse(row["alwaysLoad"]["applied"])
        gate = stages["stage2"]
        self.assertTrue(gate["memory_cost_required_for_adopt_now"])
        context = gate["trial_context"]
        self.assertEqual(hashlib.sha256((ROOT / context["source_file"]).read_bytes()).hexdigest(),
                         context["sha256"])
        self.assert_trial_measurements(context)

    def test_pss_or_process_counter_drift_is_rejected(self):
        for field in ("owned_pss_kb", "owned_processes"):
            with self.subTest(field=field):
                context = copy.deepcopy(self.record["adoption_stages"]["stage2"]["trial_context"])
                context["measurements"][0][field] += 1
                with self.assertRaises(AssertionError):
                    self.assert_trial_measurements(context)


if __name__ == "__main__":
    unittest.main()
