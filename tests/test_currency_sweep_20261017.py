"""The 2026-10-17 currency re-pin: the seven profile rows, the claude-hud tag and the public records agree.

docs/decisions/2026-10-17-currency-sweep-repin.md states the versions below. Every test here except test_the_held_rows_stay_where_the_record_says fails on the plan files as they stood
before that change (the old pins, rows without their receipts and blocking gaps, a SocratiCode command with a buffer of our own, a claude-hud tag that differed across the template, the
client map, bootstrap and the recipe row); the held-rows test guards the two rows that did not move. The tests of the second fold (the private-name placeholders, the claude-hud route record's settings step and its bootstrap order, the SocratiCode
no-buffer run, the left and routed items, the sdist digest) fail on 7e09d9a4 as well; the sdist digest check is a tightening that the old head's carriers already satisfied.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "adoption/new-wsl-profile.json"
RECORDS = ROOT / "evidence/artifacts/currency-sweep-20261017"
RECORDS_REL = "evidence/artifacts/currency-sweep-20261017/"
DECISION = ROOT / "docs/decisions/2026-10-17-currency-sweep-repin.md"
HUD_TAG = "v0.11.3"
HUD_COMMIT = "5621429b84ea2503185221244c43a06797bfd05e"
HUD_OLD_COMMITS = ("ad322b8d9016816a1858334ba57a085512110e83", "75683c6de1ac07f6bbef00d739001679dba0740c")   # v0.11.2 and v0.10.0

# row name -> (pin, public record tool name, values the row must no longer carry)
ROWS = {
    "RTK": ("1.0.1", "rtk", ("0.51.0",)),
    "Serena": ("2.0.0", "serena", ("c6fbd1c5", "2.0.0.dev0")),
    "Chrome DevTools MCP": ("1.11.0", "chrome-devtools-mcp", ("1.10.1", "e52c6b59")),
    "jcodemunch-mcp": ("1.108.374", "jcodemunch-mcp", ("1.108.327", "6d5ae86c")),
    "promptfoo": ("0.124.1", "promptfoo", ("0.123.1",)),
    "SocratiCode": ("1.16.1", "socraticode", ("1.15.0",)),
    "semble": ("0.7.0", "semble", ("0.6.1",)),
}
HELD = {"codebase-memory-mcp": "0.11.0", "Headroom": "0.37.0"}
# Shapes of private locators, case-insensitive. The account name and the lane builder's name are held out by the generator's own sanitization and by the repository's host-name scan
# (validate.py --scan-file, whose names live outside the repository); a token spelled here would publish it, so this checks the shapes: home, scratch, run-time and account-scratch paths,
# the private tracker's and receipt notes' file names, the numbered scripts, logs and backup directories of the lane builder's upgrade records, and a command-center message id.
PRIVATE = re.compile(r"/home/\S|/var/tmp/|/tmp/claude-\d|/run/user/\d|tracker\S{0,40}\.md|RECEIPT-[\w-]+\.md|(?<![\w.-])\d{2}-[a-z0-9][\w-]*\.(?:sh|log|py)\b|(?<![\w.-])\d{2}-[a-z]+-backup/|#\d{5}|\bGO #\d", re.I)
HEX = {"sha256": 64, "git-sha1": 40}
EQUAL_HEAD = "omission_notice_levels_equal_levels_over_omitted_lines_only"


def rows():
    return {row["name"]: row for row in json.loads(PROFILE.read_text(encoding="utf-8"))["entries"]}


def records(prefix):
    paths = sorted(RECORDS.glob(prefix + "*.json"))
    assert len(paths) == 1, (prefix, paths)
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def record(tool):
    return records("currency-%s-2026" % tool)


class CurrencySweepRepin(unittest.TestCase):
    def test_rows_carry_the_verified_pins_and_their_artifacts(self):
        by_name = rows()
        for name, (pin, _tool, _old) in ROWS.items():
            row = by_name[name]
            self.assertEqual(row["pin"], pin, name)
            self.assertIn(pin, row["release"]["tag"], name)
            self.assertIn(pin, row["artifact"]["url"], name)
            algorithm, value = row["checksum"]["algorithm"], row["checksum"]["value"]
            self.assertRegex(value, r"\A[0-9a-f]{%d}\Z" % HEX[algorithm], name)

    def test_the_old_pins_left_the_re_pinned_rows(self):
        by_name = rows()
        for name, (_pin, _tool, old) in ROWS.items():
            row = dict(by_name[name])
            row.pop("blocking_gaps")  # the gaps name the versions the plan's carriers and exec rules still hold
            text = json.dumps(row)
            for value in old:
                self.assertNotIn(value, text, "%s still carries %s" % (name, value))

    def test_the_held_rows_stay_where_the_record_says(self):
        by_name = rows()
        for name, pin in HELD.items():
            self.assertEqual(by_name[name]["pin"], pin, name)

    def test_the_rtk_row_records_the_owed_exec_rule_review(self):
        gaps = " ".join(rows()["RTK"]["blocking_gaps"])
        for needle in ("codex_hook_trust.py", "exec_rules_reviewed.json", "rtk-rewrite-heads"):
            self.assertIn(needle, gaps)

    def test_each_re_pinned_row_says_which_old_pin_the_plan_carriers_still_hold(self):
        by_name = rows()
        for name, (_pin, _tool, old) in ROWS.items():
            gaps = " ".join(by_name[name]["blocking_gaps"])
            self.assertTrue(any(value in gaps for value in old), "%s does not say what the plan's carriers still name" % name)
            self.assertIn("amended in their own change", gaps, name)

    def test_socraticode_installs_without_an_age_buffer_of_ours(self):
        command = rows()["SocratiCode"]["install"]["command"]
        self.assertNotIn("--before", command)
        self.assertIn("socraticode@1.16.1", command)
        handbook = (ROOT / "docs/new-wsl-handbook.md").read_text(encoding="utf-8") + (ROOT / "docs/new-wsl-handbook.json").read_text(encoding="utf-8")
        self.assertNotIn("--before=2026-10-16", handbook)

    def test_the_serena_row_records_the_repl_default_of_a_fresh_install(self):
        gaps = " ".join(rows()["Serena"]["blocking_gaps"])
        for needle in ("agent_interface", "REPL", "serena init", "install.sh:432"):
            self.assertIn(needle, gaps)

    def test_the_headroom_row_names_the_three_pins_and_the_recheck(self):
        row = rows()["Headroom"]
        gaps = " ".join(row["blocking_gaps"])
        for needle in ("0.37.0", "0.40.0", "0.41.0", "W1b", "pins-linux-x86_64.json:319-320", "manifests/stack.json:521-523", "omission count"):
            self.assertIn(needle, gaps)
        path, data = records("currency-headroom-recheck-")
        self.assertIn(RECORDS_REL + path.name, row["evidence_refs"])
        for label in ("0.40.0_scratch_install", "0.41.0_live_install"):
            self.assertEqual(data["rechecks"][label]["criteria_failing"], [EQUAL_HEAD], label)
        self.assertEqual(data["criteria"]["failing_on_both_versions"], [EQUAL_HEAD])
        self.assertEqual({data["rechecks"][k]["headroom_ai_version"] for k in data["rechecks"]}, {"0.40.0", "0.41.0"})

    def test_the_codebase_memory_hold_cites_the_readme_lines_and_rests_on_the_measurement(self):
        row = rows()["codebase-memory-mcp"]
        gaps = " ".join(row["blocking_gaps"])
        for needle in (":155", ":157-159", "target-entry-snapshot"):
            self.assertIn(needle, gaps)
        decision = DECISION.read_text(encoding="utf-8")
        for needle in ("`:155`", "`:157-159`", "target-entry-snapshot"):
            self.assertIn(needle, decision)
        path, data = records("currency-codebase-memory-mcp-native-route-")
        self.assertIn(RECORDS_REL + path.name, row["evidence_refs"])
        scenarios = data["measurement"]["scenarios"]
        refused = scenarios["symlink_layout_running_0_11_0_session"]
        self.assertEqual(refused["install"]["exit"], 1)
        self.assertIn("target-entry-snapshot", refused["install"]["stderr"])
        self.assertFalse(refused["after"]["standin_session"]["exited"], "the refusal must leave the running session untouched")
        drained = scenarios["regular_file_layout_running_0_11_0_session"]
        self.assertEqual(drained["install"]["exit"], 0)
        self.assertTrue(drained["after"]["standin_session"]["exited"])
        self.assertEqual(drained["after"]["version_via_entry"], "codebase-memory-mcp 0.12.1")

    def test_the_claude_hud_pin_agrees_across_the_plan(self):
        template = json.loads((ROOT / "adoption/templates/claude.settings.template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["extraKnownMarketplaces"]["claude-hud"]["source"]["ref"], HUD_TAG)
        client_map = (ROOT / "adoption/new-wsl/client-config-map.json").read_text(encoding="utf-8")
        override = re.search(r'"repo": "jarrodwatts/claude-hud",\s*"ref": "([^"]+)"', client_map)
        self.assertEqual(override.group(1), HUD_TAG)
        bootstrap = (ROOT / "adoption/bootstrap.md").read_text(encoding="utf-8")
        recipe = (ROOT / "recipes/README.md").read_text(encoding="utf-8")
        self.assertIn("claude-hud@%s --scope user" % HUD_TAG, bootstrap)
        self.assertIn("claude-hud@%s --scope user" % HUD_TAG, recipe)
        self.assertIn('"claude-hud@claude-hud": "%s",' % HUD_COMMIT, bootstrap)
        self.assertIn("`claude-hud` · `0.11.3` / `%s`" % HUD_COMMIT, recipe)
        for old_tag in ("v0.10.0", "v0.11.2"):
            self.assertNotIn("claude-hud@%s --scope user\n   claude plugin install" % old_tag, bootstrap)
            self.assertNotIn("claude-hud@%s --scope user`;" % old_tag, recipe)
        for old in HUD_OLD_COMMITS:
            self.assertNotIn('"claude-hud@claude-hud": "%s"' % old, bootstrap)
        for pins in ("adoption/pins-linux-x86_64.json", "adoption/pins-macos-arm64.json"):
            self.assertNotIn("installed from tag v0.10.0 through the settings template and recipe", (ROOT / pins).read_text(encoding="utf-8"), pins)

    def test_the_claude_hud_route_record_shows_the_pin_installed_through_the_tagged_route(self):
        path, data = records("claude-hud-0.11.3-")
        self.assertEqual(data["upstream"]["commit"], HUD_COMMIT)
        self.assertEqual(data["upstream"]["tag"], HUD_TAG)
        self.assertTrue(data["verification"]["installed_gitCommitSha_equals_the_v0_11_3_commit"])
        exits = {step["label"][:2]: step["exit"] for step in data["smoke"]["steps"]}
        for step in ("A1", "A2", "B1", "B2", "B3"):
            self.assertEqual(exits[step], 0, step)
        self.assertNotEqual(exits["B0"], 0, "B0 fails after the settings edit although the marketplace is on disk; the tagged add is the route")
        self.assertIn("settings.json", " ".join(data["live_application_for_the_command_center_not_run_here"]))
        self.assertFalse(data["link"]["changed_by_this_builder"])
        update = json.loads((RECORDS / "claude-hud-0.11.2-20261017T072723Z.json").read_text(encoding="utf-8"))
        self.assertEqual(update["upstream"]["tag"], "v0.11.2")

    def test_each_public_record_names_the_pin_its_row_carries(self):
        for name, (pin, tool, _old) in ROWS.items():
            path, data = record(tool)
            self.assertIn(pin, data["to"], name)
            self.assertIn("public_copy", data, path.name)

    def test_no_public_record_holds_a_private_locator(self):
        files = sorted(RECORDS.glob("*.json"))
        self.assertGreaterEqual(len(files), 13, "the thirteen public receipts are not all there, so there is nothing to scan")
        for path in files:
            text = path.read_text(encoding="utf-8")
            found = PRIVATE.search(text)
            self.assertIsNone(found, "%s holds a private locator: %r" % (path.name, found.group(0) if found else None))
            for key in re.findall(r'"([^"]+)":', text):
                self.assertIsNone(PRIVATE.search(key), "%s has a key that is a private locator: %r" % (path.name, key))

    def test_each_public_record_carries_the_registry_digests_and_the_local_ones_and_its_row_cites_it(self):
        by_name = rows()
        for name, (_pin, tool, _old) in ROWS.items():
            path, data = record(tool)
            block = data["digest_comparison"]
            self.assertIn(RECORDS_REL + path.name, by_name[name]["evidence_refs"], name)
            self.assertTrue(block["all_registry_comparisons_equal"], name)
            compared = [c for c in block["comparisons"] if c["equal"] is not None]
            self.assertTrue(compared, name)
            self.assertTrue(all(c["equal"] is True for c in compared), name)
            self.assertTrue(block["what_was_compared_with_what"], name)
            pinned = by_name[name]["checksum"]
            if pinned["algorithm"] == "sha256":
                self.assertTrue(block["profile_pin"]["equals_local_sha256"], name)
                self.assertIn(pinned["value"], json.dumps(block), "%s: the pinned sha256 has no trace in its receipt" % name)
            if block["registry"].get("npm_publishes_sha256") is False:   # npm: sha512 SRI and sha1 are the registry's own digests
                self.assertEqual(block["registry"]["published_digests"]["integrity_sha512_sri"], pinned.get("integrity"), name)
        _path, jcm = record("jcodemunch-mcp")
        files = jcm["digest_comparison"]["registry"]["files"]
        self.assertEqual({f["packagetype"] for f in files}, {"bdist_wheel", "sdist"})
        for f in files:
            self.assertEqual(f["registry_published_digests"]["sha256"], f["local"]["sha256"], f["filename"])
            self.assertIn(f["local"]["sha256"], DECISION.read_text(encoding="utf-8"), "%s: the digest is not in the decision (the wheel's and the sdist's both are)" % f["filename"])

    def test_each_public_record_resolves_its_source_commit(self):
        by_name = rows()
        for name, (_pin, tool, _old) in ROWS.items():
            _path, data = record(tool)
            resolution = data["source_commit_resolution"]
            commit = resolution["git_ls_remote"]["commit"]
            self.assertRegex(commit, r"\A[0-9a-f]{40}\Z", name)
            self.assertEqual(resolution["git_ls_remote"]["exit"], 0, name)
            if tool != "rtk":   # the RTK row cites the release tag in its URLs, the others cite the commit
                self.assertIn(commit, json.dumps(by_name[name]), "%s does not cite the commit its receipt resolved" % name)
            head = resolution.get("npm_gitHead")
            if head and head != commit:
                compared = resolution["compare_gitHead_to_tag_commit"]
                self.assertEqual((compared["status"], compared["behind_by"]), ("ahead", 0), name)
                self.assertNotIn("README.md", compared["files"], "%s: the README the row cites differs between gitHead and the tag commit" % name)

    def test_the_decision_table_matches_the_profile(self):
        text = DECISION.read_text(encoding="utf-8")
        by_name = rows()
        for name, (pin, _tool, _old) in ROWS.items():
            self.assertIn(by_name[name]["checksum"]["value"], text, name)
            self.assertRegex(text, r"\*\*[^|*]*%s[^|*]*\*\*" % re.escape(pin), name)
        self.assertIn(HUD_COMMIT, text)

    def test_the_rtk_record_names_no_private_script_or_log(self):
        _path, data = record("rtk")
        entries = data["switch_record"]["lane_builder_scripts_and_logs"]
        self.assertEqual(len(entries), 4)
        for entry in entries:
            self.assertIn(entry, ("<lane builder script (private)>", "<lane builder log (private)>"))
        for path in sorted(RECORDS.glob("*.json")):
            for key, value in json.loads(path.read_text(encoding="utf-8")).items():
                if key.endswith("scripts_and_logs") and isinstance(value, list):
                    for entry in value:
                        self.assertTrue(entry.startswith("<lane builder"), "%s: %s holds an unplaceholdered entry" % (path.name, key))

    def test_the_private_shape_check_sees_a_name_after_a_slash(self):
        self.assertTrue(PRIVATE.search("<lane builder upgrade records (private)>/22-example-script.sh"))
        self.assertTrue(PRIVATE.search("<lane builder upgrade records (private)>/22-example-trial-20261017T041859Z.log"))
        self.assertTrue(PRIVATE.search("<lane builder upgrade records (private)>/22-example-backup/"))
        self.assertFalse(PRIVATE.search("<lane builder script (private)>"))

    def test_the_claude_hud_route_record_has_the_settings_edit_and_the_reproduced_cause(self):
        _path, data = records("claude-hud-0.11.3-")
        labels = [step["label"] for step in data["smoke"]["steps"]]
        edit = [i for i, label in enumerate(labels) if label.startswith("S1 settings edit")]
        self.assertEqual(len(edit), 1, labels)
        self.assertEqual(edit[0], [i for i, label in enumerate(labels) if label.startswith("B0")][0] - 1, "the settings edit is the step before B0")
        note = data["smoke"]["note"]
        self.assertNotIn("not yet on disk", note)
        self.assertIn("no longer matches", note)
        repro = data["smoke"]["b0_cause_reproduction"]
        self.assertIn("exit 0", repro["run_without_S1"]["B0_marketplace_update"])
        self.assertIn("exit 1", repro["run_with_S1_between_A2_and_B0"]["B0_marketplace_update"])
        self.assertIn("Marketplace 'claude-hud' not found", repro["run_with_S1_between_A2_and_B0"]["B0_marketplace_update"])
        on_disk = data["smoke"]["state_after_phase_A_v0_11_2"]["known_marketplaces.json"]["claude-hud"]
        self.assertIn("installLocation", on_disk, "the marketplace is on disk when B0 fails")

    def test_bootstrap_puts_the_tagged_add_first_and_says_the_marketplace_update_failed(self):
        bootstrap = (ROOT / "adoption/bootstrap.md").read_text(encoding="utf-8")
        start = bootstrap.index("**Upgrade an existing claude-hud installation")
        block = bootstrap[start:bootstrap.index("Then compare the `gitCommitSha` that landed", start)]
        self.assertIn("0.11.2 on 2026-10-17)", block)
        self.assertNotIn("before 2026-10-17", block)
        add = block.index("claude plugin marketplace add jarrodwatts/claude-hud@v0.11.3 --scope user")
        update = block.index("claude plugin marketplace update claude-hud")
        self.assertLess(add, update, "the tagged add comes before any mention of the marketplace update")
        self.assertIn("Do not put `claude plugin marketplace update claude-hud` first", block)
        self.assertNotIn("host verification pending", block)
        self.assertNotIn("from the state of the host above", block)

    def test_the_socraticode_no_buffer_command_was_run_and_audited(self):
        path, data = record("socraticode")
        run = data["no_buffer_command_scratch_run"]
        self.assertEqual(run["row_command"], rows()["SocratiCode"]["install"]["command"])
        self.assertNotIn("--before", run["row_command"])
        self.assertEqual(run["install_exit"], {"without_before": 0, "with_before": 0})
        self.assertEqual(run["tree_comparison"]["differences"], 0)
        self.assertEqual(run["tree_comparison"]["package_directories"], {"without_before": 188, "with_before": 188})
        for audit in ("without_before", "with_before", "project_form_check"):
            self.assertEqual(run["npm_audit_signatures"][audit]["exit"], 0, audit)
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("no_buffer_command_scratch_run", decision)
        self.assertNotIn("1.16.1 resolves without it", decision)

    def test_the_old_socraticode_buffer_carriers_are_listed_as_left(self):
        decision = DECISION.read_text(encoding="utf-8")
        gaps = " ".join(rows()["SocratiCode"]["blocking_gaps"])
        for text in (decision, gaps):
            self.assertIn("--before=2026-09-24T12:00:00Z", text)
        self.assertIn("SocratiCode 1.15.0 in the handbook", decision)
        for carrier in ("evidence/artifacts/new-wsl-install-plan-20261002/install.sh", "evidence/artifacts/new-wsl-install-plan-20261002/install-plan.json"):
            self.assertIn("--before=2026-09-24", (ROOT / carrier).read_text(encoding="utf-8"), carrier)
        handbook = (ROOT / "docs/new-wsl-handbook.json").read_text(encoding="utf-8")
        self.assertIn("--before=2026-09-24T12:00:00Z", handbook)

    def test_the_jcodemunch_previous_pin_references_are_listed_as_left(self):
        row = rows()["jcodemunch-mcp"]
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("The jcodemunch-mcp row's two previous-pin references", decision)
        for ref in row["evidence_refs"]:
            if "1108327" in ref:
                self.assertIn(ref, decision, "a previous-pin reference the decision does not list")

    def test_the_codebase_memory_hold_states_the_older_route_and_the_remit_reading(self):
        gaps = " ".join(rows()["codebase-memory-mcp"]["blocking_gaps"])
        for needle in ("ln -s and mv -T", "switch_when_ready", "needs no layout change", "remit reading"):
            self.assertIn(needle, gaps)
        self.assertNotIn("needs a layout change and", gaps)
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("remit reading", decision)
        self.assertIn("`ln -s` and `mv -T`", decision)
        profile_page = (ROOT / "adoption/new-wsl-profile.md").read_text(encoding="utf-8")
        self.assertIn("symlink switch of the older receipt stays valid", profile_page)
        older = json.loads((RECORDS / "currency-codebase-memory-mcp-20261017T080146Z.json").read_text(encoding="utf-8"))
        self.assertIn("mv -T", " ".join(older["switch_when_ready"]["commands"]))

    def test_the_decision_separates_the_public_hook_cases_from_the_private_ones(self):
        decision = DECISION.read_text(encoding="utf-8")
        start = decision.index("1. **RTK's Codex hook trust step")
        finding = decision[start:decision.index("2. **Serena 2.0.0", start)]
        self.assertIn("Measured in the\n   public RTK receipt", finding)
        self.assertIn("not in any public receipt", finding)
        self.assertIn("private", finding)
        self.assertNotIn("`sh -c 'git log --oneline -3'` and `env FOO=1 bash -c 'git status'` to the", finding)
        _path, data = record("rtk")
        cases = {case["id"]: case for case in data["comparison"]["tables"]["targeted_gate_cases"]}
        self.assertEqual(cases["G7-inner-rewrite-feature"]["decision"]["1.0.1"], "rewrite")
        self.assertEqual(cases["G6a-wrapper-deny-bash-c"]["decision"]["1.0.1"], "silent(defer)")

    def test_the_rtk_pin_names_the_other_consumer_of_the_old_version(self):
        source = (ROOT / "tools/adoption/runtime_profiles.py").read_text(encoding="utf-8").splitlines()
        self.assertIn('rtk 0.51.0', source[561], "the line the record cites no longer holds the 0.51.0 check")
        gaps = " ".join(rows()["RTK"]["blocking_gaps"])
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("tools/adoption/runtime_profiles.py:562", gaps)
        self.assertIn("tools/adoption/runtime_profiles.py:562", decision)


if __name__ == "__main__":
    unittest.main()
