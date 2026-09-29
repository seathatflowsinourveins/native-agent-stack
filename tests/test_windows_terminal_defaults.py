"""The repository-carried Windows Terminal, notification and login-shell defaults.

These are local consistency checks over the checked-in files, not a run of Windows Terminal, Claude Code or Codex. The
policy is docs/decisions/2026-09-28-terminal-experience.md: each AI tab shows the title its client sends, the bell rings
only for a real needed action and quietly, and a profile that starts a client through a login shell reaches its PATH.
"""

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "adoption"))

import apply_claude_settings as acs  # noqa: E402

OVERLAY = ROOT / "adoption/templates/claude.settings.linux-wsl2.overlay.json"
BASE_TEMPLATE = ROOT / "adoption/templates/claude.settings.template.json"
FRAGMENT = ROOT / "examples/claude-native/windows-terminal.fragment.example.json"
RECIPE = ROOT / "recipes/claude-native-profile.md"
PLATFORM_PAGE = ROOT / "adoption/platforms/linux-wsl2.md"
# The Notification types that mean Claude Code needs the person (permission and elicitation dialogs, a teammate or an
# agent waiting, a quota event); the decision record lists where each comes from.
NEEDED_TYPES = ("permission_prompt", "elicitation_dialog", "elicitation_url_dialog", "agent_needs_input",
                "quota_auto_resume_stale", "quota_auto_resume_disabled", "worker_permission_prompt")
QUIET_TYPES = ("idle_prompt", "auth_success", "elicitation_complete", "elicitation_response")
BEL_HOOK = "jq -nc --arg s \"$(printf '\\a')\" '{terminalSequence:$s}'"
# codex-rs/tui/src/chatwidget/notifications.rs type_name() at rust-v0.157.1; async-question does not exist at
# rust-v0.155.1, where naming it is inert.
CODEX_KINDS = {"agent-turn-complete", "approval-requested", "plan-mode-prompt", "async-question"}
PLACEHOLDERS = ("<DISTRO>", "<WSL_USER>", "<PROJECT>")


def recipe_profile() -> dict:
    """The first ```json block after the recipe's "For Windows Terminal" sentence."""
    text = RECIPE.read_text(encoding="utf-8")
    start = text.index("For Windows Terminal, add a named profile")
    block = re.search(r"```json\n(.*?)\n```", text[start:], re.DOTALL)
    return json.loads(block.group(1))


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))

    def test_the_overlay_carries_only_the_terminal_alert_settings(self):
        self.assertEqual(set(self.overlay), {"$schema", "preferredNotifChannel", "hooks"})
        self.assertEqual(self.overlay["preferredNotifChannel"], "notifications_disabled")
        self.assertEqual(set(self.overlay["hooks"]), {"Notification"})

    def test_one_hook_rings_the_bell_for_a_needed_action_only(self):
        (group,) = self.overlay["hooks"]["Notification"]
        self.assertEqual(group["hooks"], [{"type": "command", "command": BEL_HOOK}])
        self.assertEqual(group["matcher"], "|".join(NEEDED_TYPES))
        for kind in NEEDED_TYPES:
            self.assertRegex(kind, f"^(?:{group['matcher']})$")
        for kind in QUIET_TYPES:
            self.assertNotRegex(kind, f"^(?:{group['matcher']})$")

    @unittest.skipUnless(shutil.which("jq") and shutil.which("sh"), "needs jq and sh")
    def test_the_hook_command_emits_exactly_one_bel_as_the_terminal_sequence(self):
        (group,) = self.overlay["hooks"]["Notification"]
        run = subprocess.run(["sh", "-c", group["hooks"][0]["command"]], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0)
        self.assertEqual(json.loads(run.stdout), {"terminalSequence": "\x07"})

    def test_merging_twice_changes_nothing_the_second_time_and_keeps_host_settings(self):
        host = {"model": "host-model", "permissions": {"deny": ["Edit(~/.profile)"]},
                "hooks": {"Notification": [{"matcher": "idle_prompt", "hooks": [{"type": "command", "command": "true"}]}],
                          "Stop": [{"hooks": [{"type": "command", "command": "host-stop"}]}]}}
        once = acs.merge_settings(host, self.overlay)
        twice = acs.merge_settings(once, self.overlay)
        self.assertEqual(once, twice)
        self.assertEqual(once["model"], "host-model")
        self.assertEqual(once["permissions"], host["permissions"])
        self.assertEqual(once["hooks"]["Stop"], host["hooks"]["Stop"])
        commands = [hook["command"] for group in once["hooks"]["Notification"] for hook in group["hooks"]]
        self.assertEqual(commands.count(BEL_HOOK), 1)
        self.assertIn("true", commands)
        self.assertEqual(once["preferredNotifChannel"], "notifications_disabled")

    def test_the_overlay_composes_with_the_base_template_in_either_order(self):
        base = json.loads(BASE_TEMPLATE.read_text(encoding="utf-8"))
        one = acs.merge_settings(acs.merge_settings({}, base), self.overlay)
        other = acs.merge_settings(acs.merge_settings({}, self.overlay), base)
        for merged in (one, other):
            self.assertEqual(merged["preferredNotifChannel"], "notifications_disabled")
            for event, groups in base.get("hooks", {}).items():
                for group in groups:
                    for hook in group["hooks"]:
                        commands = [item.get("command") for entry in merged["hooks"][event] for item in entry["hooks"]]
                        self.assertIn(hook.get("command"), commands, event)
            notify = [item["command"] for entry in merged["hooks"]["Notification"] for item in entry["hooks"]]
            self.assertEqual(notify.count(BEL_HOOK), 1)

    def test_the_base_template_does_not_already_own_these_settings(self):
        # A base-template value would win over or duplicate the overlay; the overlay is the one place they live.
        base = json.loads(BASE_TEMPLATE.read_text(encoding="utf-8"))
        self.assertNotIn("preferredNotifChannel", base)
        self.assertNotIn("Notification", base.get("hooks", {}))


class OverlayOracleTests(unittest.TestCase):
    """The acceptance script behind the receipt must tell a host that has the overlay from one that only looks merged."""

    ORACLE = ROOT / "evidence/artifacts/wsl-terminal-defaults-20260929/overlay_noop_check.py"

    def verdict(self, settings: dict) -> str:
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / ".claude").mkdir()
            (Path(home) / ".claude/settings.json").write_text(json.dumps(settings), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(self.ORACLE), str(ROOT)], capture_output=True, text=True, timeout=60,
                                 env={"HOME": home, "PATH": "/usr/bin:/bin"})
        self.assertEqual(run.returncode, 0, run.stderr[-300:])
        return run.stdout

    def bell_group(self, matcher):
        group = {"hooks": [{"type": "command", "command": BEL_HOOK}]}
        return {"hooks": {"Notification": [{**group, "matcher": matcher} if matcher is not None else group]}}

    def test_a_host_with_the_overlay_is_in_effect(self):
        overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
        out = self.verdict(acs.merge_settings({}, overlay))
        self.assertIn("overlay in effect (merge is a no-op, one group, same matcher): True", out)

    def test_a_wrong_host_that_the_merge_alone_cannot_see_is_refused(self):
        overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
        base = {"$schema": overlay["$schema"], "preferredNotifChannel": "notifications_disabled"}
        for label, hooks in {"a catch-all group": self.bell_group(None), "an older, narrower matcher": self.bell_group("permission_prompt")}.items():
            with self.subTest(label):
                settings = {**base, **hooks}
                # the merge tool de-duplicates by command, so it leaves this host as it is and the plain comparison passes
                self.assertEqual(acs.merge_settings(settings, overlay)["hooks"], settings["hooks"])
                out = self.verdict(settings)
                self.assertIn("merged equals live: True", out)
                self.assertIn("that group's matcher equals the overlay's: False", out)
                self.assertIn("overlay in effect (merge is a no-op, one group, same matcher): False", out)

    def test_a_host_without_the_overlay_is_not_in_effect(self):
        out = self.verdict({"model": "host-model"})
        self.assertIn("merged equals live: False", out)
        self.assertIn("overlay in effect (merge is a no-op, one group, same matcher): False", out)


class CodexTemplateTests(unittest.TestCase):
    def render(self, host: str) -> dict:
        with tempfile.TemporaryDirectory() as out:
            run = subprocess.run([sys.executable, "-B", str(ROOT / "tools/adoption/render_config.py"), "--host", host,
                                  "--out", out], capture_output=True, text=True, cwd=ROOT, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr[-400:])
            return tomllib.loads((Path(out) / "codex.config.toml").read_text(encoding="utf-8"))

    def test_the_rendered_template_notifies_only_for_a_needed_decision(self):
        for host in ("example", "macos-example"):
            with self.subTest(host=host):
                tui = self.render(host)["tui"]
                # Codex does not validate keys inside [tui] (an unknown key loads cleanly), so a new setting needs its own
                # upstream check before it joins this set; [tui.model_availability_nux] is a table Codex keeps for itself.
                self.assertEqual({key for key, value in tui.items() if not isinstance(value, dict)}, {"notifications"})
                kinds = tui["notifications"]
                self.assertIsInstance(kinds, list)
                self.assertTrue(all(isinstance(kind, str) for kind in kinds))
                self.assertEqual(set(kinds), CODEX_KINDS - {"agent-turn-complete"})
                self.assertEqual(len(kinds), len(set(kinds)))


class ProfilePolicyMixin:
    """The tab, bell and launch rules of the decision record for one Windows Terminal profile."""

    def check_common(self, profile: dict):
        bell = profile["bellStyle"]
        self.assertIsInstance(bell, list, "an explicit array, never the default or a bare \"all\"")
        self.assertNotIn("all", bell, "\"all\" would also raise a toast on Terminal main")
        self.assertTrue(set(bell) <= {"audible", "taskbar"})
        self.assertEqual(profile.get("closeOnExit"), "graceful")
        self.assertIn("tabTitle", profile)

    def check_ai(self, profile: dict, client: str):
        self.check_common(profile)
        self.assertNotIn("suppressApplicationTitle", profile, "it would discard the title each client sends")
        self.assertEqual(profile["bellStyle"], ["audible", "taskbar"])
        self.assertRegex(profile["bellSound"], r"\\Windows Ding\.wav$")
        self.assertRegex(profile["commandline"], rf'^wsl\.exe -d \S+ -u \S+ --cd \S+ --exec /bin/bash -lc "exec {client}"$')

    def check_shell(self, profile: dict):
        self.check_common(profile)
        self.assertIs(profile["suppressApplicationTitle"], True)
        self.assertEqual(profile["bellStyle"], ["taskbar"], "a readline completion bell stays silent")
        self.assertNotIn("bellSound", profile)


class FragmentExampleTests(ProfilePolicyMixin, unittest.TestCase):
    def setUp(self):
        self.fragment = json.loads(FRAGMENT.read_text(encoding="utf-8"))
        self.profiles = {profile["name"]: profile for profile in self.fragment["profiles"]}

    def test_a_fragment_of_three_profiles_that_declare_no_guid(self):
        # The GUID is optional in a fragment: Windows Terminal derives a stable one from the fragment folder's name and the profile
        # name (Profile::_GenerateGuidForProfile at v1.24.11911.0), and the derived value never travels in this repository.
        self.assertEqual(set(self.fragment), {"profiles"})
        self.assertEqual(list(self.profiles), ["WSL - Shell", "WSL - Codex", "WSL - Claude"])
        for name, profile in self.profiles.items():
            self.assertNotIn("guid", profile, name)

    def test_the_ai_profiles_show_their_own_titles_and_ring_quietly(self):
        self.check_ai(self.profiles["WSL - Codex"], "codex")
        self.check_ai(self.profiles["WSL - Claude"], "claude")

    def test_the_shell_profile_keeps_a_fixed_title_and_a_silent_bell(self):
        self.check_shell(self.profiles["WSL - Shell"])
        self.assertRegex(self.profiles["WSL - Shell"]["commandline"],
                         r'^wsl\.exe -d \S+ -u \S+ --cd \S+ --exec /bin/bash -lc "exec /bin/bash -l"$')

    def test_only_claude_sets_truecolor_and_only_through_the_environment_key(self):
        for name, profile in self.profiles.items():
            self.assertEqual(profile.get("environment"), {"COLORTERM": "truecolor"} if name == "WSL - Claude" else None, name)
            self.assertNotIn("COLORTERM", profile["commandline"])

    def test_only_the_three_placeholders_stand_for_host_values(self):
        text = FRAGMENT.read_text(encoding="utf-8")
        found = set(re.findall(r"<[A-Z_]+>", text))
        self.assertEqual(found, set(PLACEHOLDERS))
        self.assertNotRegex(text, r"(?i)/(?:home|users)/|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
        for profile in self.profiles.values():
            for placeholder in PLACEHOLDERS:
                self.assertIn(placeholder, profile["commandline"])

    def test_the_recipe_profile_follows_the_same_policy(self):
        profile = recipe_profile()
        self.check_ai(profile, "claude")
        self.assertEqual(profile["environment"], {"COLORTERM": "truecolor"})
        self.assertEqual(profile["tabTitle"], profile["name"])

    def test_a_policy_break_is_detected(self):
        # Negative controls: the same checks must refuse a profile that suppresses titles, rings for everything or
        # starts a client without a login shell.
        good = self.profiles["WSL - Claude"]
        for label, change in {
            "suppressed title": {"suppressApplicationTitle": True},
            "bell all": {"bellStyle": ["all"]},
            "default bell": {"bellStyle": "audible"},
            "no login shell": {"commandline": "wsl.exe -d <DISTRO> -u <WSL_USER> --cd <PROJECT> --exec claude"},
            "loud sound": {"bellSound": "C:\\Windows\\Media\\Windows Notify System Generic.wav"},
        }.items():
            with self.subTest(label), self.assertRaises(AssertionError):
                self.check_ai({**copy.deepcopy(good), **change}, "claude")


class DocumentationTests(unittest.TestCase):
    def test_the_platform_page_names_every_shipped_default_and_the_recipe_anchor_exists(self):
        page = PLATFORM_PAGE.read_text(encoding="utf-8")
        self.assertIn("\n## Windows Terminal profiles and the login shell\n", page)
        for path in ("adoption/templates/claude.settings.linux-wsl2.overlay.json",
                     "examples/claude-native/windows-terminal.fragment.example.json",
                     "adoption/templates/codex.config.template.toml", "scripts/adoption_status.py --login-shell",
                     "tools/adoption/apply_claude_settings.py"):
            self.assertIn(path, page)
        self.assertIn("(../adoption/platforms/linux-wsl2.md#windows-terminal-profiles-and-the-login-shell)",
                      RECIPE.read_text(encoding="utf-8"))
        # The hand-off line the page tells an operator to keep is the one the decision record verified.
        self.assertIn('if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi', page)
        self.assertIn('if [ -r "$HOME/.profile" ]; then . "$HOME/.profile"; fi',
                      (ROOT / "docs/decisions/2026-09-28-terminal-experience.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
