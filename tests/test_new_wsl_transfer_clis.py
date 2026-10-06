"""Discriminating local contract controls for Phase1 named-only CLI transfer."""
import copy
import re
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests import test_new_wsl_definitive_defaults as plan_checks


class TransferCLIPlanChecks(unittest.TestCase):
    def run_check(self, **changes):
        existing = plan_checks.InterimPlanChecks("test_the_unchanged_copy_passes")
        return existing.run_check(**changes)

    def reject_row(self, change, text):
        def mutate(plan):
            change(plan["transfer_clis"][0], plan)
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn(text, out)

    def test_native_plan_passes_with_foundation_counts_unchanged(self):
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("84 rows: 63 installed", out)
        self.assertIn("Transfer CLIs:", out)

    def test_foundation_catalog_still_rejects_extra_default_owners(self):
        def mutate(plan):
            row = copy.deepcopy(plan["owners"][0])
            row["slot"] = "made-up-foundation-default"
            plan["owners"].append(row)
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn("no counterpart in the manifest", out)

    def test_duplicate_transfer_id_is_rejected(self):
        self.reject_row(lambda row, plan: plan["transfer_clis"].append(copy.deepcopy(row)),
                        "duplicate")

    def test_foundation_namespace_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(slot="codex"), "transfer-cli- namespace")

    def test_floating_release_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(release="latest"), "exact release pin")

    def test_unpinned_install_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(version_pinned=False), "exact release pin")

    def test_unsupported_manager_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(route="curl-pipe-shell"),
                        "mise, uv-tool or apt")

    def test_changed_native_install_command_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(commands=["echo skipped"]),
                        "install function differs from native commands")

    def test_missing_observed_or_approved_origin_is_rejected(self):
        self.reject_row(lambda row, plan: row.pop("origin"), "transfer origin")

    def test_missing_native_self_test_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(acceptance={}), "self-test is required")

    def test_scalar_native_self_test_is_rejected_without_traceback(self):
        code, out = self.run_check(change_transfer=lambda plan: plan["transfer_clis"][0].update(
            acceptance={"post_install": "not a check"}))
        self.assertEqual(code, 1, out)
        self.assertIn("self-test is required", out)
        self.assertNotIn("Traceback", out)

    def test_version_only_cannot_claim_native_self_test(self):
        self.reject_row(lambda row, plan: row["acceptance"]["post_install"].update(kind="version only"),
                        "self-test is required")

    def test_install_source_drift_is_rejected(self):
        self.reject_row(lambda row, plan: row["install_source"].update(url="https://example.invalid/no-source"),
                        "install source differs")

    def test_acceptance_source_drift_is_rejected(self):
        self.reject_row(lambda row, plan: row["acceptance"]["post_install"]["source"].update(
            url="https://example.invalid/no-source"), "self-test source differs")

    def test_manager_prerequisite_cannot_be_dropped(self):
        self.reject_row(lambda row, plan: row.update(prerequisite_tools=[]),
                        "manager prerequisite is not declared")

    def test_mise_pin_drift_is_rejected(self):
        code, out = self.run_check(change_transfer_mise=lambda text: text.replace("8.30.1", "8.30.0"))
        self.assertEqual(code, 1, out)
        self.assertIn("exactly the transfer mise pins", out)

    def test_mise_identifier_cannot_inject_shell_code(self):
        self.reject_row(lambda row, plan: row.update(mise_tool="gitleaks; echo unexpected"),
                        "invalid transfer mise_tool")

    def test_transfer_cannot_override_foundation_mise_owner(self):
        def mutate(row, plan):
            owner = next(r for r in plan["owners"] if r.get("mise_tool"))
            row.update(mise_tool=owner["mise_tool"])
        self.reject_row(mutate, "invalid transfer mise_tool")

    def test_native_install_dispatch_cannot_change_selector(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            "if named 'transfer-cli-gitleaks'; then run_slot 'transfer-cli-gitleaks'; fi",
            "if selected 'transfer-cli-gitleaks'; then run_slot 'transfer-cli-gitleaks'; fi"))
        self.assertEqual(code, 1, out)
        self.assertIn("leaked into default installation", out)

    def test_acceptance_cannot_run_during_default_plan(self):
        code, out = self.run_check(change_accept=lambda text: text.replace(
            'if [[ "$only" == transfer-cli-gitleaks ]]; then transfer-cli-gitleaks; fi',
            'if [[ -z "$only" || "$only" == transfer-cli-gitleaks ]]; then transfer-cli-gitleaks; fi'))
        self.assertEqual(code, 1, out)
        self.assertIn("leaked into default run", out)

    def test_missing_named_dispatch_is_rejected(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            "if named 'transfer-cli-gitleaks'; then run_slot 'transfer-cli-gitleaks'; fi", ""))
        self.assertEqual(code, 1, out)
        self.assertIn("install must dispatch only when named", out)

    def test_unknown_transfer_stage_is_rejected(self):
        self.reject_row(lambda row, plan: row.update(
            acceptance={"after_sign_in": row["acceptance"]["post_install"]}),
            "post_install self-test is required")

    def test_undated_not_needed_row_is_rejected(self):
        def add(plan):
            plan["transfer_clis"].append({
                "slot": "transfer-cli-retired", "cli": "retired", "owner": "Retired CLI",
                "installed": False, "route": "none", "commands": [], "acceptance": {},
                "origin": {"kind": "missing-cli", "source": "controlled inventory"},
                "reason": "Superseded by the chosen native owner"})
        code, out = self.run_check(change_transfer=add)
        self.assertEqual(code, 1, out)
        self.assertIn("not-needed row needs an ISO date", out)

    def test_unexplained_not_needed_row_is_rejected(self):
        def add(plan):
            plan["transfer_clis"].append({
                "slot": "transfer-cli-retired", "cli": "retired", "owner": "Retired CLI",
                "installed": False, "route": "none", "commands": [], "acceptance": {},
                "origin": {"kind": "missing-cli", "source": "controlled inventory"},
                "not_needed_on": "2026-10-06"})
        code, out = self.run_check(change_transfer=add)
        self.assertEqual(code, 1, out)
        self.assertIn("not-needed row needs a reason", out)


    @staticmethod
    def shell_quote(value):
        return "'" + value.replace("'", "'\\\"'\\\"'") + "'"

    def added_row_check(self, row):
        """Use the existing plan-copy checker; never run an installer."""
        if not row["installed"]:
            row.setdefault("decision_source", {
                "path": "adoption/manifest.json",
                "revision": "ecfa112764c664d35377dd66b8cfcb67e5a94d60",
            })
        slot = row["slot"]
        install = row.get("commands", [])
        if row["installed"]:
            entry = row["acceptance"]["post_install"]
            if not entry["command"].startswith("export MISE_AUTO_INSTALL=0\n"):
                entry["command"] = "export MISE_AUTO_INSTALL=0\n" + entry["command"]
            manager = row["prerequisite_tools"][0]
            install_function = (
                f"{slot}() {{\\n  command -v {manager} >/dev/null || return 69\\n"
                f"  # Source: {row['install_source']['url']}\\n"
                f"  run_command {self.shell_quote(install[0])}\\n}}\\n\\n"
            ).replace("\\n", "\n")
            entry = row["acceptance"]["post_install"]
            accept_function = (
                f'{slot}() {{\\n  case "$stage" in\\n    post_install)\\n'
                f"      # Kind: smoke; Source: {entry['source']['url']}\\n"
                f"      check {slot} smoke {self.shell_quote(entry['command'])}\\n"
                f"      ;;\\n    *) skipped {slot} ;;\\n  esac\\n}}\\n\\n"
            ).replace("\\n", "\n")
            install_dispatch = f"if named '{slot}'; then run_slot '{slot}'; fi\n"
            accept_dispatch = f'if [[ "$only" == {slot} ]]; then {slot}; fi\n'
            state = "planned-named-only"
        else:
            install_function = accept_function = ""
            install_dispatch = f"if named '{slot}'; then printf '%s | install | not-needed\\n' '{slot}'; fi\n"
            accept_dispatch = f'if [[ "$only" == {slot} ]]; then skipped {slot}; fi\n'
            state = "not-needed"

        def install_text(text):
            text = re.sub(r"(^  ''\|[^\n]+)(\) ;;)$",
                          lambda match: match[1] + f"|{slot}" + match[2], text,
                          count=1, flags=re.M)
            text = text.replace("if $list; then", install_function + "if $list; then")
            boundary = '  exit 0\nfi\ncase "$only" in'
            text = text.replace(boundary,
                                f"  printf '%s\\n' '{slot} | {row['owner']} | {row['route']} | {state}'\n" + boundary)
            return text.replace('exit "$failed"', install_dispatch + 'exit "$failed"')

        def accept_text(text):
            text = re.sub(r"(^  ''\|[^\n]+)(\) ;;)$",
                          lambda match: match[1] + f"|{slot}" + match[2], text,
                          count=1, flags=re.M)
            text = text.replace('if [[ -z "$only" || "$only" == claude-code ]]', accept_function +
                                'if [[ -z "$only" || "$only" == claude-code ]]', 1)
            return text.replace('exit "$failed"', accept_dispatch + 'exit "$failed"')

        def inventory(data):
            if row.get("origin", {}).get("kind") == "missing-cli" and row["cli"] not in data["missing_cli_names"]:
                data["missing_cli_names"].append(row["cli"])
        return self.run_check(change_transfer=lambda plan: plan["transfer_clis"].append(row),
                              change_install=install_text, change_accept=accept_text,
                              change_inventory=inventory)

    def test_dated_exclusion_is_explicit_and_has_no_executable_function(self):
        row = {"slot": "transfer-cli-retired", "cli": "retired", "owner": "Retired CLI",
               "installed": False, "route": "none", "commands": [], "acceptance": {},
               "origin": {"kind": "missing-cli", "source": "controlled inventory"},
               "reason": "Superseded by the chosen native owner", "not_needed_on": "2026-10-06"}
        code, out = self.added_row_check(row)
        self.assertEqual(code, 0, out)

    def test_excluded_install_cannot_leak_into_default_execution(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            'exit "$failed"', "if selected 'transfer-cli-dotnet'; then run_command 'false'; fi\nexit \"$failed\""))
        self.assertEqual(code, 1, out)
        self.assertIn("unapproved not-needed dispatch", out)

    def test_excluded_acceptance_cannot_run_without_its_selector(self):
        code, out = self.run_check(change_accept=lambda text: text.replace(
            'exit "$failed"', 'skipped transfer-cli-dotnet\nexit "$failed"'))
        self.assertEqual(code, 1, out)
        self.assertIn("unapproved not-needed dispatch", out)

    def rejected_exclusion_source(self, source):
        def mutate(plan):
            row = next(row for row in plan["transfer_clis"] if row["cli"] == "dotnet")
            row["decision_source"] = source
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn("not-needed decision_source", out)
        self.assertNotIn("Traceback", out)

    def test_missing_exclusion_source_is_rejected(self):
        self.rejected_exclusion_source({})

    def test_exclusion_source_cannot_escape_the_repository(self):
        self.rejected_exclusion_source({"path": "../outside.md", "revision": "ecfa112764c664d35377dd66b8cfcb67e5a94d60"})

    def test_exclusion_source_needs_an_existing_commit_object(self):
        self.rejected_exclusion_source({"path": "adoption/manifest.json", "revision": "f" * 40})

    def test_exclusion_source_cannot_float_on_main(self):
        self.rejected_exclusion_source({"path": "adoption/manifest.json", "revision": "main"})

    def test_exclusion_source_must_be_a_file_not_a_tree(self):
        self.rejected_exclusion_source({"path": "adoption", "revision": "ecfa112764c664d35377dd66b8cfcb67e5a94d60"})

    def test_secondary_apt_packages_cannot_use_floating_versions(self):
        def mutate(plan):
            row = next(row for row in plan["transfer_clis"] if row["cli"] == "pkgconf")
            row["additional_apt_packages"]["pkgconf-bin"] = "latest"
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn("additional apt packages must have exact pins", out)

    def test_secondary_apt_pin_must_match_the_native_transaction(self):
        def mutate(plan):
            row = next(row for row in plan["transfer_clis"] if row["cli"] == "pkgconf")
            row["additional_apt_packages"]["pkgconf-bin"] = "2.5.1-3"
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn("differs from its apt pin", out)

    def test_malformed_origin_kind_is_rejected_without_traceback(self):
        for kind in ([], {}):
            with self.subTest(kind=kind):
                code, out = self.run_check(change_transfer=lambda plan: plan["transfer_clis"][0]["origin"].update(kind=kind))
                self.assertEqual(code, 1, out)
                self.assertIn("transfer origin", out)
                self.assertNotIn("Traceback", out)

    def test_mise_self_test_must_disable_auto_install(self):
        self.reject_row(lambda row, plan: row["acceptance"]["post_install"].update(
            command=row["acceptance"]["post_install"]["command"].removeprefix("export MISE_AUTO_INSTALL=0\n")),
            "disable mise auto-install")

    def test_missing_mise_cli_fails_without_install_side_effect(self):
        """Synthetic shim boundary; this is not an upstream mise acceptance test."""
        plan = json.loads((plan_checks.PLAN / "install-plan.json").read_text())
        row = next(row for row in plan["transfer_clis"] if row["cli"] == "gitleaks")
        command = row["acceptance"]["post_install"]["command"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / "gitleaks"
            binary.write_text('#!/bin/sh\nif [ "${MISE_AUTO_INSTALL:-1}" = 0 ]; then exit 127; fi\n'
                              'touch "$AUTO_INSTALL_MARKER"\nprintf "8.30.1\\n"\n')
            binary.chmod(0o700)
            marker = root / "would-install"
            env = {"PATH": str(root) + ":/usr/bin:/bin", "HOME": str(root), "AUTO_INSTALL_MARKER": str(marker)}
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", command], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())
            subprocess.run(["bash", "-euo", "pipefail", "-c", command.removeprefix("export MISE_AUTO_INSTALL=0\n")],
                           env=env, capture_output=True)
            self.assertTrue(marker.exists(), "control must discriminate the missing auto-install guard")

    def test_inventory_cannot_silently_drop_a_missing_cli(self):
        code, out = self.run_check(change_inventory=lambda inventory: inventory.update(
            missing_cli_names=["unaccounted-native-cli"]))
        self.assertEqual(code, 1, out)
        self.assertIn("missing CLI decisions", out)

    def test_inventory_cannot_be_marked_complete_with_duplicate_names(self):
        code, out = self.run_check(change_inventory=lambda inventory: inventory.update(
            missing_cli_names=["gitleaks", "gitleaks"]))
        self.assertEqual(code, 1, out)
        self.assertIn("complete unique CLI roster", out)

    def test_pending_inventory_is_not_completed_coverage(self):
        code, out = self.run_check(change_inventory=lambda inventory: inventory.update(status="pending"))
        self.assertEqual(code, 1, out)
        self.assertIn("complete unique CLI roster", out)

    def test_exact_uv_slot_uses_native_command_and_only_named_dispatch(self):
        source = {"url": "https://github.com/astral-sh/uv/blob/0.12.22/docs/concepts/tools.md",
                  "pin": "0.12.22"}
        row = {"slot": "transfer-cli-ruff", "cli": "ruff", "owner": "Ruff",
               "repository": "https://github.com/astral-sh/ruff", "release": "0.13.2",
               "installed": True, "route": "uv-tool", "version_pinned": True,
               "uv_package": "ruff", "prerequisite_tools": ["uv"],
               "origin": {"kind": "missing-cli", "source": "controlled inventory"},
               "install_source": source, "upstream_source": source,
               "commands": ["uv tool install --python 3.13.16 ruff==0.13.2"],
               "acceptance": {"post_install": {"kind": "smoke", "command": "ruff --help", "source": source}}}
        code, out = self.added_row_check(row)
        self.assertEqual(code, 0, out)

    def test_exact_apt_slot_uses_native_command_and_only_named_dispatch(self):
        source = {"url": "https://manpages.debian.org/apt/apt-get.8.en.html", "reviewed_on": "2026-10-06"}
        row = {"slot": "transfer-cli-jq", "cli": "jq", "owner": "jq",
               "repository": "https://github.com/jqlang/jq", "release": "1.7.1-3build1",
               "installed": True, "route": "apt", "version_pinned": True,
               "apt_package": "jq", "prerequisite_tools": ["apt-get"],
               "origin": {"kind": "missing-cli", "source": "controlled inventory"},
               "install_source": source, "upstream_source": source,
               "commands": ["sudo apt-get install -y --no-install-recommends jq=1.7.1-3build1"],
               "acceptance": {"post_install": {"kind": "smoke", "command": "jq --help", "source": source}}}
        code, out = self.added_row_check(row)
        self.assertEqual(code, 0, out)


    def test_extra_default_install_call_cannot_hide_beside_named_dispatch(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            'exit "$failed"',
            'if [[ -z "$only" ]]; then run_slot \'transfer-cli-gitleaks\'; fi\nexit "$failed"'))
        self.assertEqual(code, 1, out)
        self.assertIn("unapproved transfer dispatch", out)

    def test_extra_default_acceptance_call_cannot_hide_beside_named_dispatch(self):
        code, out = self.run_check(change_accept=lambda text: text.replace(
            'exit "$failed"',
            'if [[ -z "$only" ]]; then transfer-cli-gitleaks; fi\nexit "$failed"'))
        self.assertEqual(code, 1, out)
        self.assertIn("unapproved transfer dispatch", out)

    def test_transfer_call_inside_foundation_helper_is_rejected(self):
        code, out = self.run_check(change_install=lambda text: text.replace(
            "run_slot() {", "run_slot() {\n  transfer-cli-gitleaks"))
        self.assertEqual(code, 1, out)
        self.assertIn("unapproved transfer dispatch", out)

    def test_container_route_is_rejected_without_traceback(self):
        for route in ([], {}):
            with self.subTest(route=route):
                code, out = self.run_check(change_transfer=lambda plan: plan["transfer_clis"][0].update(route=route))
                self.assertEqual(code, 1, out)
                self.assertIn("route must be mise", out)
                self.assertNotIn("Traceback", out)

    def test_broken_native_quote_is_a_contract_error(self):
        code, out = self.run_check(change_accept=lambda text: text.replace(
            "check transfer-cli-gitleaks smoke '", 'check transfer-cli-gitleaks smoke "', 1))
        self.assertEqual(code, 1, out)
        self.assertIn("malformed native acceptance shell quotation", out)
        self.assertNotIn("Traceback", out)

    def test_source_pin_must_be_a_string(self):
        for name in ("install_source", "upstream_source", "acceptance"):
            with self.subTest(source=name):
                def mutate(plan):
                    row = plan["transfer_clis"][0]
                    source = row["acceptance"]["post_install"]["source"] if name == "acceptance" else row[name]
                    source["pin"] = True
                    source.pop("reviewed_on", None)
                code, out = self.run_check(change_transfer=mutate)
                self.assertEqual(code, 1, out)
                self.assertIn("pin/date", out)

    def test_review_date_is_parsed(self):
        def mutate(plan):
            source = plan["transfer_clis"][0]["install_source"]
            source.pop("pin")
            source["reviewed_on"] = "not-a-date"
        code, out = self.run_check(change_transfer=mutate)
        self.assertEqual(code, 1, out)
        self.assertIn("pin/date", out)

    def test_source_comment_suffix_is_not_source_equality(self):
        url = "https://github.com/jdx/mise/blob/v2026.10.1/docs/cli/use.md"
        code, out = self.run_check(change_install=lambda text: text.replace(
            "Source: " + url, "Source: " + url + "?unreviewed"))
        self.assertEqual(code, 1, out)
        self.assertIn("install source differs", out)


if __name__ == "__main__":
    unittest.main()
