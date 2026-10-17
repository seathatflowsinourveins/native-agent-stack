"""The install plan's memory-owner row installs the receipted ai-memory 3.1.0 run pin through the vendor's route.

The command center moved ai-memory from 2.6.6 to 3.1.0 on 2026-10-16 (its GO at 16:51Z), and condition 4 of PR (b)
retargets the plan row so the landed plan matches the host. The receipt is
evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json: the version, its commit, the release archive with
the sha256 verified against the publisher's sidecar, the binary inside it, and the vendor install.sh with its own
sidecar-verified sha256. It supersedes the F1 run pin (2.6.6) as the plan's pin source only.

The route follows the CC's rulings D1, D2 and D5 for condition 4 (RULINGS-gino-9109.md, outside the repository):
- install.sh at tag v3.1.0, fetched and verified, installs the release (akitaonrails/ai-memory@11ca7c5b install.sh:148-216);
- `ai-memory setup --yes --agent claude-code --agent codex` writes the systemd user unit, both clients' MCP entries,
  hooks and skills (setup.rs:1-31, 755-860), so the row writes no unit of its own: the stack's additions go in a
  repo-owned drop-in, ai-memory.service.d/override.conf, written before setup starts the service;
- `ai-memory install-hooks --agent claude-code --no-capture-prompts --apply` follows in the same step, because setup
  passes no capture flag (setup.rs:982-997) and a first install captures prompts (install_hooks.rs:1247-1261); it runs
  even when setup fails, and a later bare re-apply keeps the opt-out (install_hooks.rs:1263-1274, cli.rs:3262-3267).
These tests fail while the row, its install and acceptance functions, its --list line or owners.json name another
version, digest, source commit or route.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/artifacts/new-wsl-install-plan-20261002"
FIXTURE = ROOT / "tests/fixtures/ai-memory-3.1.0-claude-hooks.json"
# CLAUDE_CODE_EVENTS, the nine Claude Code events ai-memory 3.1.0's install-hooks writes (akitaonrails/ai-memory@11ca7c5b
# crates/ai-memory-cli/src/commands/render_shared.rs:37-50, read through raw.githubusercontent.com on 2026-10-17). The row's
# opt-out (--no-capture-prompts) omits UserPromptSubmit (install_hooks.rs:46 CLAUDE_PROMPT_EVENT, 1247-1274).
UPSTREAM_CLAUDE_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd",
                          "SubagentStart", "SubagentStop")
RUN_PIN = ROOT / "evidence/artifacts/memory-owner-v3.1.0-run-pin-20261017/run-pin.json"
ASSETS = RUN_PIN.parent / "outputs/github-api-release-assets.json"
# setup puts the unit under $XDG_CONFIG_HOME when that is absolute, otherwise ~/.config (akitaonrails/ai-memory@11ca7c5b
# crates/ai-memory-cli/src/commands/user_service.rs:236-249), so the drop-in goes to that directory.
DROP_DIR = '"${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/ai-memory.service.d"'
OPT_OUT = "install-hooks --agent claude-code --no-capture-prompts --apply"
# The local release tree install.sh reads through AI_MEMORY_RELEASE_BASE_URL: its url_dir is <base>/download/v<version>
# (akitaonrails/ai-memory@11ca7c5b install.sh:162-166).
TREE = "$HOME/.local/opt/ai-memory-{version}"


def function(text: str, name: str) -> str:
    return re.search(rf"(?ms)^{re.escape(name)}\(\) \{{\n.*?^\}}\n", text).group(0)


def load_checker():
    import importlib.util
    spec = importlib.util.spec_from_file_location("memory_owner_plan_check", PLAN / "check_plan.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryOwnerRunPinTests(unittest.TestCase):
    def setUp(self):
        pin = json.loads(RUN_PIN.read_text(encoding="utf-8"))["proposed_run_pin"]
        self.version, self.commit = pin["version"], pin["commit"]
        self.binary_sha = pin["release_archive"]["binary_sha256"]
        self.archive_url, self.archive_sha = pin["release_archive"]["url"], pin["release_archive"]["sha256"]
        self.script_url, self.script_sha = pin["install_script"]["url"], pin["install_script"]["sha256"]
        assets = {a["name"]: a for a in json.loads(ASSETS.read_text(encoding="utf-8"))["assets"]}
        sidecar = assets[self.archive_url.rsplit("/", 1)[1] + ".sha256"]
        self.sidecar_url, self.sidecar_sha = sidecar["browser_download_url"], sidecar["digest"].removeprefix("sha256:")
        rows = json.loads((PLAN / "install-plan.json").read_text(encoding="utf-8"))["owners"]
        self.row, = [r for r in rows if r["slot"] == "memory-owner"]
        self.install = (PLAN / "install.sh").read_text(encoding="utf-8")
        self.accept = (PLAN / "accept.sh").read_text(encoding="utf-8")

    def step(self, needle):
        found = [c for c in self.row["commands"] if needle in c]
        self.assertEqual(len(found), 1, (needle, self.row["commands"]))
        return found[0]

    def test_the_row_installs_the_receipted_release_with_the_vendor_installer(self):
        self.assertEqual((self.row["owner"], self.row["release"], self.row["route"]),
                         (f"ai-memory {self.version}", f"v{self.version}", "native-installer"))
        fetch = self.row["commands"][0]
        self.assertTrue(fetch.startswith(f"fetch_verified {self.script_url} {self.script_sha} "), fetch)
        install = self.row["commands"][1]
        self.assertIn(f"AI_MEMORY_VERSION={self.version} ", install)
        self.assertIn("install.sh", install)
        # The archive's own binary, digest from the run pin: the installer's sidecar check is the publisher's.
        self.assertIn(f"printf '%s  %s\\n' {self.binary_sha} \"$HOME/.local/lib/ai-memory/ai-memory\" "
                      "| sha256sum --check --status", install)
        for stale in ("2.5.2", "2.6.6", ".local/opt/ai-memory-" + self.version + "/ai-memory-linux"):
            self.assertNotIn(stale, json.dumps(self.row["commands"]))

    def test_install_sh_reads_only_a_release_the_row_verified_first(self):
        # On its own install.sh checks the archive only against a sidecar from the same origin, and runs the unpacked
        # binary before any check of the row's (akitaonrails/ai-memory@11ca7c5b install.sh:20-23 and 186-197). So the
        # row's first step also fetches the archive, against the run pin's digest, and its sidecar, against the asset
        # digest the release reports, into a local release tree, and install.sh reads that tree through a file://
        # AI_MEMORY_RELEASE_BASE_URL (url_dir is <base>/download/v<version>, install.sh:162-166).
        tree = TREE.format(version=self.version)
        download = f"{tree}/download/v{self.version}/{self.archive_url.rsplit('/', 1)[1]}"
        fetch, install = self.row["commands"][0], self.row["commands"][1]
        parts = fetch.split(" && ")
        self.assertEqual(parts, [f'fetch_verified {self.script_url} {self.script_sha} "{tree}/install.sh"',
                                 f'fetch_verified {self.archive_url} {self.archive_sha} "{download}"',
                                 f'fetch_verified {self.sidecar_url} {self.sidecar_sha} "{download}.sha256"'])
        self.assertIn(fetch, function(self.install, "memory-owner"))
        self.assertIn(f'AI_MEMORY_RELEASE_BASE_URL="file://{tree}" ', install)
        self.assertIn(f'sh "{tree}/install.sh"', install)
        self.assertNotIn("https://", install)
        # The sidecar install.sh's verify() reads is "<hex>  <asset>" (install.sh:114-126): the run pin's archive digest.
        self.assertEqual(hashlib.sha256(f"{self.archive_sha}  {download.rsplit('/', 1)[1]}\n".encode()).hexdigest(),
                         self.sidecar_sha)
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        helper = function(self.install, "fetch_verified")
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "bin/curl"
            stub.parent.mkdir()
            # A curl that serves $BODY for any URL: fetch_verified must keep only bytes with the pinned digest.
            stub.write_text('#!/bin/bash\nout=""\nwhile [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift 2 ;; '
                            '--proto) shift 2 ;; *) shift ;; esac; done\nprintf "%s" "$BODY" > "$out"\n')
            stub.chmod(0o755)
            for name, part, body, want_rc in (
                    ("a replaced archive", parts[1], "not the release archive\n", 1),
                    ("the sidecar", parts[2], f"{self.archive_sha}  {download.rsplit('/', 1)[1]}\n", 0)):
                with self.subTest(name):
                    env = {"PATH": f"{stub.parent}:/usr/bin:/bin", "HOME": tmp, "BODY": body}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", helper + part], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want_rc), result.stderr)
                    target = Path(tmp) / part.rsplit('"$HOME/', 1)[1].rstrip('"')
                    self.assertEqual(target.is_file(), not want_rc)

    def test_install_sh_list_and_owners_json_follow_the_row(self):
        body = function(self.install, "memory-owner")
        self.assertIn(f"fetch_verified {self.script_url} {self.script_sha} ", body)
        self.assertNotIn("2.5.2", body)
        self.assertIn(f"'memory-owner | ai-memory {self.version} | native-installer | planned'", self.install)
        owners = json.loads((PLAN / "owners.json").read_text(encoding="utf-8"))["owners"]
        self.assertEqual([o["owner"] for o in owners if o["slot"] == "memory-owner"], [f"ai-memory {self.version}"])

    def test_setup_owns_the_unit_and_the_row_adds_only_its_drop_in(self):
        joined = "\n".join(self.row["commands"])
        self.assertNotIn('> "$HOME/.config/systemd/user/ai-memory.service"', joined)
        self.assertNotIn("packaging/systemd/ai-memory-user.service", joined)
        # setup wires Codex's hooks; the row's own Codex install-hooks runs only where setup is deferred (--no-start).
        self.assertEqual([c for c in self.row["commands"] if "install-hooks --agent codex" in c],
                         [c for c in self.row["commands"] if "setup --yes" in c])
        drop = self.step(DROP_DIR)
        setup = self.step("setup --yes --agent claude-code --agent codex")
        self.assertLess(self.row["commands"].index(drop), self.row["commands"].index(setup))
        self.assertIn("systemctl --user daemon-reload", drop)
        self.assertIn('install -m 0644 "$plan_dir/config/ai-memory-override.conf" "$drop"', drop)
        self.assertIn("copy_config 'ai-memory-override.conf'", function(self.install, "memory-owner"))
        conf = (PLAN / "config/ai-memory-override.conf").read_text(encoding="utf-8")
        active = [line for line in conf.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(active[0], "[Service]")
        keys = {line.split("=", 1)[0] for line in active[1:]}
        self.assertEqual(keys, {"Environment", "CPUWeight", "MemoryHigh", "MemoryMax"})
        self.assertIn("CPUWeight=idle", active)
        self.assertTrue(any(line.startswith("Environment=PATH=%h/.local/bin:") for line in active), active)
        self.assertFalse(any(line.startswith("ExecStart") for line in active))
        # G5 (the CC's ruling for the fold): the bound is measured, not provisional. MemoryHigh=1G is the working limit and
        # MemoryMax=2G the last line, from two transient-unit MemoryPeak readings of 3.1.0 with the local embedder (the model
        # fetch and 50 embedded writes; startup, the acceptance checks and one hybrid search), cited by the private receipt's name.
        self.assertIn("MemoryHigh=1G", active)
        self.assertIn("MemoryMax=2G", active)
        self.assertNotIn("MemoryMax=4G", active)
        self.assertNotRegex(conf, r"(?i)provisional")
        self.assertRegex(conf, r"(?m)^# MEASURED \(the CC's ruling G5 ")
        peaks = [int(n) for n in re.findall(r"MemoryPeak (\d+) bytes", conf)]
        self.assertEqual(peaks, [362442752, 201592832])
        high, last = (int(value.removesuffix("G")) << 30 for value in ("1G", "2G"))
        self.assertGreater(high, max(peaks))
        self.assertGreater(last, high)
        for method in ("RECEIPT-g5-20261017.md", "cited by name only", "transient user unit", "embedding_provider = \"local\"",
                       "50 embedded writes", "hybrid search", "page\n# cache charged to the unit"):
            self.assertIn(method, conf)
        # What the readings do not cover is named, so the bound is not read as covering it.
        self.assertRegex(conf, r"NOT MEASURED: a large store's startup\n# backfill and a consolidation run")
        # The interim and the plan row say the same bound, not the provisional one.
        self.assertIn("MemoryHigh=1G as the working limit and MemoryMax=2G as the last line", json.dumps(self.row))
        self.assertNotIn("PROVISIONAL", json.dumps(self.row))
        manifest = (ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json").read_text(encoding="utf-8")
        self.assertIn("CPUWeight=idle, MemoryHigh=1G and MemoryMax=2G", manifest)
        self.assertNotIn("a provisional MemoryMax", manifest)
        # Round 2: the install plan's SOURCES.md prints the same measured bound, with the method, both readings and the
        # unmeasured residual, and no record that carries the row's bound calls it provisional or prints 4G.
        sources = (PLAN / "SOURCES.md").read_text(encoding="utf-8")
        self.assertIn("`MemoryHigh=1G` is the working limit and `MemoryMax=2G` the last line", sources)
        for reading in peaks:
            self.assertIn(f"{reading} bytes", sources)
        for part in ("RECEIPT-g5-20261017.md, cited by name only", "not measured: a large store's startup backfill and a consolidation run"):
            self.assertIn(part, sources)
        for path in (PLAN / "SOURCES.md", PLAN / "install-plan.json", PLAN / "config/ai-memory-override.conf",
                     ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json",
                     ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json", ROOT / "docs/new-wsl-handbook.json"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)MemoryMax=4G|provisional (?:bound|MemoryMax)", path.name)

    def test_the_handbook_receipt_keeps_no_state_that_only_the_prs_first_commit_held(self):
        """Round 2: a draft of this fold recorded the PR's first commit's handbook state (a regenerations entry and a
        previous_outputs entry citing that commit as source_head). The output digests of that state match no tracked
        file at the head, so the text-digest guard cannot resolve them. The receipt keeps one
        regenerations entry for this PR (one entry, found by what it records) whose digests are the tracked files' own while it
        is the current regeneration, and previous_outputs entries whose digests are the blobs at their source_head."""
        receipt_path = ROOT / "evidence/artifacts/new-wsl-handbook-20261001/receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        day = "2026-10-17"

        def sha(relative):
            return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()

        regenerations = receipt["regenerations"]
        # The PR's entry is found by what it records (the condition-4 move and the fold's B2 change), not by its date or position.
        split = [entry["source_base"] for entry in regenerations
                 if ("Condition 4" in entry.get("scope", "")) != ("finding B2" in entry.get("scope", ""))]
        self.assertEqual(split, [], "the PR's regeneration is one entry, not one per commit")
        mine = [index for index, entry in enumerate(regenerations) if "Condition 4" in entry.get("scope", "") and "finding B2" in entry.get("scope", "")]
        self.assertEqual(len(mine), 1, mine)
        entry = regenerations[mine[0]]
        previous_entries = receipt["previous_outputs"]
        if mine[0] == len(regenerations) - 1:
            # Still the current regeneration: its digests are the tracked files' own.
            self.assertEqual(entry["generator_sha256"], sha("scripts/build_new_wsl_handbook.py"))
            self.assertEqual(entry["current_outputs"], {path: sha(path) for path in entry["current_outputs"]})
            self.assertEqual(entry["current_outputs"], receipt["outputs"])
            self.assertEqual(receipt["generator_sha256"], entry["generator_sha256"])
        else:
            # A later regeneration moved the state on: this entry's outputs are then recorded as a superseded state.
            self.assertIn(entry["current_outputs"], [prev["outputs"] for prev in previous_entries])
        # A previous_outputs entry names a state its source_head held: the blobs there give its digests, wherever that
        # commit is present (a shallow checkout does not have it).
        for previous in (prev for prev in previous_entries if prev.get("superseded_at_utc") == day):
            head = previous["source_head"]
            if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{head}^{{commit}}"], capture_output=True).returncode:
                continue
            for path, digest in previous["outputs"].items():
                blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{head}:{path}"], capture_output=True, check=True).stdout
                self.assertEqual(digest, hashlib.sha256(blob).hexdigest(), (head, path))

    def test_the_drop_in_goes_to_setups_unit_directory_and_only_the_plans_bytes_stay(self):
        # setup writes the unit under $XDG_CONFIG_HOME when that is absolute (user_service.rs:236-249 at 11ca7c5b), so a
        # drop-in under ~/.config would not attach there. The step installs the plan's own bytes and, as the Dagu step
        # does, refuses any other ai-memory.service.d/*.conf and an override.conf that differs.
        drop = self.step(DROP_DIR)
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        plan_bytes = (PLAN / "config/ai-memory-override.conf").read_bytes()
        for xdg in (False, True):
            for name, seed, want_rc in (("fresh", {}, 0), ("the plan's copy", {"override.conf": plan_bytes}, 0),
                                        ("an edited copy", {"override.conf": plan_bytes + b"MemoryMax=1T\n"}, 1),
                                        ("another drop-in", {"override.conf": plan_bytes, "10-x.conf": b"[Service]\n"}, 1)):
                with self.subTest(xdg=xdg, case=name), tempfile.TemporaryDirectory() as tmp:
                    home = Path(tmp) / "home"
                    config = Path(tmp) / "xdg" if xdg else home / ".config"
                    (Path(tmp) / "bin").mkdir()
                    (Path(tmp) / "bin/systemctl").write_text("#!/bin/sh\nexit 0\n")
                    (Path(tmp) / "bin/systemctl").chmod(0o755)
                    unit_dir = config / "systemd/user/ai-memory.service.d"
                    unit_dir.mkdir(parents=True)
                    for file, data in seed.items():
                        (unit_dir / file).write_bytes(data)
                    env = {"PATH": f"{Path(tmp) / 'bin'}:/usr/bin:/bin", "HOME": str(home), "plan_dir": str(PLAN),
                           **({"XDG_CONFIG_HOME": str(config)} if xdg else {})}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", drop], env=env, capture_output=True,
                                            text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want_rc), result.stderr)
                    if not want_rc:
                        self.assertEqual((unit_dir / "override.conf").read_bytes(), plan_bytes)
                        self.assertEqual(sorted(p.name for p in unit_dir.iterdir()), ["override.conf"])
                        if xdg:
                            self.assertFalse((home / ".config/systemd").exists())
                    else:
                        self.assertIn("needs_owner", result.stderr)
                        self.assertEqual({p.name: p.read_bytes() for p in unit_dir.iterdir()}, seed)

    def test_the_config_is_setups_and_its_bind_is_set_before_setup_wires_the_clients(self):
        joined = "\n".join(self.row["commands"])
        self.assertNotIn(".config/ai-memory/config.toml", joined)
        bind = self.step("embedding_provider")
        self.assertIn('"$HOME/.local/share/ai-memory/config.toml"', bind)
        init = self.step(" init")
        setup = self.step("setup --yes")
        order = [self.row["commands"].index(c) for c in (init, bind, setup)]
        self.assertEqual(order, sorted(order))

    def test_setup_and_the_prompt_capture_opt_out_are_one_step_that_survives_a_failed_setup(self):
        setup = self.step("setup --yes --agent claude-code --agent codex")
        self.assertIn(OPT_OUT, setup)
        self.assertLess(setup.index("setup --yes"), setup.index(OPT_OUT))
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "bin/ai-memory"
            stub.parent.mkdir()
            log = Path(tmp) / "calls"
            stub.write_text('#!/bin/bash\nprintf "%s token=%s\\n" "$*" "${AI_MEMORY_AUTH_TOKEN-unset}" >> "$LOG"\n'
                            'case " $* " in *" setup "*) exit "${SETUP_RC:-0}" ;; esac\n')
            stub.chmod(0o755)
            # With --no-start setup (which starts the service) is deferred and install-hooks writes Codex's hooks, so
            # ai-memory's Codex groups precede rtk's as in a normal install; the Claude opt-out runs in every case.
            for no_start, setup_rc, want_rc, first in (("0", "0", 0, "setup --yes --agent claude-code --agent codex"),
                                                       ("0", "3", 3, "setup --yes --agent claude-code --agent codex"),
                                                       ("1", "0", 0, "install-hooks --agent codex --apply")):
                with self.subTest(no_start=no_start, setup_rc=setup_rc):
                    log.write_text("")
                    env = {"PATH": f"{stub.parent}:/usr/bin:/bin", "HOME": tmp, "LOG": str(log),
                           "SETUP_RC": setup_rc, "NS2604_NO_START": no_start,
                           "AI_MEMORY_AUTH_TOKEN": "synthetic-not-a-credential"}
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", setup], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode, want_rc, result.stderr)
                    calls = log.read_text().splitlines()
                    self.assertEqual(len(calls), 2, calls)
                    self.assertIn(first, calls[0])
                    self.assertIn(OPT_OUT, calls[1])
                    self.assertEqual(no_start == "1", not any(" setup " in f" {call} " for call in calls), calls)
                    # setup and install-mcp copy an exported token into client configs; the step unsets it.
                    self.assertTrue(all(call.endswith("token=unset") for call in calls), calls)

    def test_the_checker_holds_the_one_writer_route(self):
        checker = load_checker()
        funcs = checker.functions(self.install)
        errors = []
        checker.memory_owner_contract(funcs, lambda tag, message: errors.append((tag, message)))
        self.assertEqual(errors, [])
        body = funcs["memory-owner"]
        mutations = {
            "unit": body + "\n  run_command 'sed s/a/b/ x > \"$HOME/.config/systemd/user/ai-memory.service\"' || return \"$?\"\n",
            "opt-out": body.replace(" env -u AI_MEMORY_AUTH_TOKEN ai-memory --data-dir \"$HOME/.local/share/ai-memory\" " + OPT_OUT + ";", ""),
            "no-start": body.replace('if [[ "${NS2604_NO_START:-0}" != 1 ]]; then ', "if true; then "),
            "codex-hooks": body.replace("install-hooks --agent codex --apply || rc=$?", "true"),
            # The drop-in under ~/.config while setup's unit is under $XDG_CONFIG_HOME, and with no refusal of other drop-ins.
            "drop-in-dir": body.replace('"${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/ai-memory.service.d"',
                                        '"$HOME/.config/systemd/user/ai-memory.service.d"'),
            "unknown-drop-ins": body.replace('for f in "$dir"/*.conf;', 'for f in "$dir"/override.conf;'),
            "staged-copy": body.replace('install -m 0644 "$plan_dir/config/ai-memory-override.conf"',
                                        'install -m 0644 "$config_root/ai-memory-override.conf"'),
            # install.sh fetching the archive and its sidecar itself, from GitHub.
            "release-origin": body.replace(f'AI_MEMORY_RELEASE_BASE_URL="file://{TREE.format(version=self.version)}"',
                                           "AI_MEMORY_RELEASE_BASE_URL=https://github.com/akitaonrails/ai-memory/releases"),
            "unfetched-archive": re.sub(r' && fetch_verified \S+/ai-memory-linux-x86_64\.tar\.gz [0-9a-f]{64} "[^"]+"', "",
                                        body),
        }
        for name, changed in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(changed, body)
                errors = []
                checker.memory_owner_contract({**funcs, "memory-owner": changed},
                                              lambda tag, message: errors.append((tag, message)))
                self.assertTrue(errors and all(tag == "memory-owner" for tag, _ in errors), errors)

    def test_acceptance_reads_the_prompt_capture_opt_out_and_the_drop_in(self):
        checker = load_checker()
        checks = checker.checks_of(checker.functions(self.accept)["memory-owner"])
        program = next(command for stage, _, kind, command in checks if stage == "post_install")
        self.assertEqual(program, self.row["acceptance"]["post_install"]["command"])
        if not (shutil.which("bash") and shutil.which("jq")):
            self.skipTest("bash and jq are needed to run the check")
        events = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PreCompact", "Stop", "SessionEnd")

        def hook(event, agent):
            return [{"matcher": "", "hooks": [{"type": "command", "command":
                    f"/x/ai-memory --data-dir /x hook --event {event.lower()} --agent {agent} --server-url http://h"}]}]

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "bin").mkdir()
            (home / "bin/ai-memory").write_text("#!/bin/sh\necho 'ai-memory 3.1.0'\n")
            (home / "bin/ai-memory").chmod(0o755)
            (home / ".codex").mkdir()
            (home / ".codex/hooks.json").write_text(json.dumps({"hooks": {e: hook(e, "codex") for e in events}}))
            (home / ".claude").mkdir()
            # The acceptance compares the installed drop-in with the plan's bytes, in setup's unit directory
            # ($XDG_CONFIG_HOME here), and fails on any other drop-in there.
            unit_dir = home / "xdg/systemd/user/ai-memory.service.d"
            unit_dir.mkdir(parents=True)
            plan_bytes = (PLAN / "config/ai-memory-override.conf").read_bytes()
            env = {"PATH": f"{home / 'bin'}:/usr/bin:/bin", "HOME": tmp, "XDG_CONFIG_HOME": str(home / "xdg"),
                   "plan_dir": str(PLAN)}
            # B12: the set is the one ai-memory 3.1.0's setup installs once the opt-out ran, read from the captured fixture
            # (and, in the next test, from render_shared.rs:37-50 at the tagged commit), not typed here.
            claude = tuple(json.loads(FIXTURE.read_text(encoding="utf-8"))["settings"]["hooks"])
            self.assertEqual(len(claude), 8)
            opted_out = {e: hook(e, "claude-code") for e in claude}
            both = {"override.conf": plan_bytes}
            duplicated_in_group = {**opted_out, "Stop": [{"matcher": "", "hooks": opted_out["Stop"][0]["hooks"] * 2}]}
            for name, settings, drop_ins, want in (
                    ("opted out", opted_out, {"override.conf": plan_bytes}, 0),
                    ("captures prompts", {e: hook(e, "claude-code") for e in (*claude, "UserPromptSubmit")},
                     {"override.conf": plan_bytes}, 1),
                    ("no ai-memory hooks", {}, {"override.conf": plan_bytes}, 1),
                    # B12: a partial set (any one event missing, and a single hook), a duplicated set (an event twice, as two
                    # groups or as two hooks in one group) and a set with an extra event all fail; each passed before.
                    *((f"a partial set without {e}", {k: v for k, v in opted_out.items() if k != e}, both, 1) for e in claude),
                    ("a single hook", {"SessionStart": opted_out["SessionStart"]}, both, 1),
                    ("an event as two groups", {**opted_out, "PreToolUse": opted_out["PreToolUse"] * 2}, both, 1),
                    ("an event as two hooks in one group", duplicated_in_group, both, 1),
                    ("the whole set twice", {e: opted_out[e] * 2 for e in claude}, both, 1),
                    ("an extra event", {**opted_out, "Notification": hook("Notification", "claude-code")}, both, 1),
                    ("an edited drop-in", opted_out, {"override.conf": b"[Service]\n"}, 1),
                    ("another drop-in", opted_out, {"override.conf": plan_bytes, "10-x.conf": b"[Service]\n"}, 1),
                    ("no drop-in", opted_out, {}, 1)):
                with self.subTest(settings=name):
                    (home / ".claude/settings.json").write_text(json.dumps({"hooks": settings}))
                    for old in unit_dir.iterdir():
                        old.unlink()
                    for file, data in drop_ins.items():
                        (unit_dir / file).write_bytes(data)
                    result = subprocess.run(["bash", "-euo", "pipefail", "-c", program], env=env,
                                            capture_output=True, text=True, timeout=60)
                    self.assertEqual(result.returncode != 0, bool(want), result.stderr)

    def test_the_claude_hook_check_names_exactly_the_set_setup_installs(self):
        """B12: the smoke accepted one or more Claude ai-memory hooks. It now lists the event of every ai-memory hook and
        compares the sorted list with exactly the set that setup installs after the opt-out, each event once."""
        installed = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIn("11ca7c5b3b65e7fc216c7eae5a9aac67d38c11ea", installed["upstream"])
        fixture_events = tuple(installed["settings"]["hooks"])
        self.assertEqual(sorted(fixture_events), sorted(set(UPSTREAM_CLAUDE_EVENTS) - {"UserPromptSubmit"}))
        self.assertEqual(len(fixture_events), len(set(fixture_events)))
        for event, groups in installed["settings"]["hooks"].items():
            with self.subTest(event=event):
                self.assertEqual(len([h for g in groups for h in g["hooks"]]), 1, "setup installs each event's hook once")
        program = self.row["acceptance"]["post_install"]["command"]
        listed = re.search(r'sort == \[("[A-Za-z]+"(?:, "[A-Za-z]+")*)\]', program)
        self.assertIsNotNone(listed, "the check compares the sorted event list with a literal set")
        self.assertEqual(re.findall(r'"([A-Za-z]+)"', listed.group(1)), sorted(fixture_events))
        self.assertNotIn("length > 0", program)
        self.assertEqual(program, next(c for stage, _, kind, c in load_checker().checks_of(
            load_checker().functions(self.accept)["memory-owner"]) if stage == "post_install"))

    def test_the_row_reads_its_port_from_the_host_allocation(self):
        # The CC's ruling D3: the row reads its port from ~/.config/new-wsl-native-stack/.service-ports.json, the way
        # config/observability_config.py and NO_START_PORTS.md do, so no literal 29374 is stated where the row controls
        # the port: run_command and check render @PORT_MEMORY@ from the staged allocation (install.sh run_command,
        # accept.sh check, observability_config.py render_command).
        texts = {"commands": "\n".join(self.row["commands"]),
                 "acceptance": json.dumps(self.row["acceptance"]),
                 "install.sh": "\n".join(line for line in function(self.install, "memory-owner").splitlines()
                                         if not line.lstrip().startswith("#")),
                 "accept.sh": "\n".join(line for line in function(self.accept, "memory-owner").splitlines()
                                        if not line.lstrip().startswith("#"))}
        for where, text in texts.items():
            with self.subTest(where=where):
                self.assertNotRegex(text, r"(?<![0-9])29374(?![0-9])")
        bind = self.step("embedding_provider")
        self.assertIn('bind = "127.0.0.1:@PORT_MEMORY@"', bind)
        health = self.row["acceptance"]["service_health"]["command"]
        self.assertIn("http://127.0.0.1:@PORT_MEMORY@/healthz", health)
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
                              .read_text(encoding="utf-8"))
        interim = next(row["interim"] for row in manifest["slots"] if row["slot_id"] == "memory-owner")
        gates = "\n".join(interim["open_acceptance_gates"])
        self.assertNotRegex(gates, r"(?<![0-9])29374(?![0-9])")
        self.assertIn(".service-ports.json", gates)
        # A moved allocation reaches the config the row writes.
        import importlib.util
        spec = importlib.util.spec_from_file_location("memory_owner_ports", PLAN / "config/observability_config.py")
        renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(renderer)
        ports = renderer.service_ports({"NS_PORT_MEMORY": "23374"})
        self.assertIn("http://127.0.0.1:23374/healthz", renderer.render_command(health, ports))
        if not shutil.which("bash"):
            self.skipTest("bash is needed to run the step")
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".local/share/ai-memory/config.toml"
            config.parent.mkdir(parents=True)
            config.write_text('bind = "127.0.0.1:49374"\nlog_level = "info"\n[auth]\nsecure_cookie = false\n')
            result = subprocess.run(["bash", "-euo", "pipefail", "-c", renderer.render_command(bind, ports)],
                                    env={"PATH": "/usr/bin:/bin", "HOME": tmp}, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('bind = "127.0.0.1:23374"\nembedding_provider = "local"\n', config.read_text())

    def test_the_interim_states_the_route_the_row_runs_and_is_dated_after_its_evidence(self):
        # The wave-6 amendment corrects the interim fields the 3.1.0 route makes false (INTERIM_AMENDABLE gains
        # configuration and sources): the listen port is the host allocation's (D3), setup renders and owns the unit, and
        # setup writes Codex's tool approval unconditionally (install_mcp.rs:1923 at 11ca7c5b; the CC's ruling G1).
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
                              .read_text(encoding="utf-8"))
        row = next(row for row in manifest["slots"] if row["slot_id"] == "memory-owner")
        config = row["interim"]["configuration"]
        self.assertNotRegex(config["listen"], r"127\.0\.0\.1:29374")
        self.assertIn(".service-ports.json", config["listen"])
        self.assertIn("setup renders", config["service"])
        self.assertIn("unconditionally", config["codex_tool_approval"])
        self.assertIn("install_mcp.rs:1923", config["codex_tool_approval"])
        sources = "\n".join(row["interim"]["sources"])
        for stale in ("7580b74d", "v2.5.2"):
            self.assertNotIn(stale, sources)
        self.assertIn(f"/blob/{self.commit}/", sources)
        self.assertIn(f"/releases/tag/v{self.version}", sources)
        self.assertIn(str(RUN_PIN.relative_to(ROOT)), sources)
        amendment = row["amendments"][-1]
        self.assertEqual(set(amendment["interim_replaced"]["configuration"]), {"listen", "service", "codex_tool_approval"})
        # The batch is dated when its evidence exists: not before the run pin's capture (E-F4).
        consensus = json.loads((ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json")
                               .read_text(encoding="utf-8"))
        captured = json.loads(RUN_PIN.read_text(encoding="utf-8"))["proposed_run_pin"]["tag_resolution"]["read_at"][:10]
        self.assertGreaterEqual(consensus["wave6"]["date_utc"], captured)
        self.assertEqual(amendment["date_utc"], consensus["wave6"]["date_utc"])

    def test_the_interim_pin_string_is_the_run_pins_tag_commit_and_archive_in_every_record_that_carries_it(self):
        """N1: a draft of this fold dropped the space before '(tag object' in the interim's pin while it edited the label beside it, in
        the consensus record, the definitive manifest and the handbook JSON generated from them, and no check read the
        string. Each record carries the exact pin the run pin's tag resolution and archive give, in the form the install
        plan's SOURCES.md and the layer-consensus decision print (a space before the parenthesis)."""
        pin = json.loads(RUN_PIN.read_text(encoding="utf-8"))["proposed_run_pin"]
        expected = (f"tag v{self.version} (tag object {pin['tag_resolution']['annotated_tag_object']}) = commit {self.commit}; "
                    f"release asset ai-memory-linux-x86_64.tar.gz sha256 {self.archive_sha}")
        manifest = json.loads((ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json")
                              .read_text(encoding="utf-8"))
        consensus = json.loads((ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json")
                               .read_text(encoding="utf-8"))
        handbook_path = ROOT / "docs/new-wsl-handbook.json"
        handbook = json.loads(handbook_path.read_text(encoding="utf-8"))
        row = next(row for row in manifest["slots"] if row["slot_id"] == "memory-owner")
        self.assertEqual(row["interim"]["pin"], expected)
        amended, = [entry for entry in consensus["wave6"]["amend_rows"] if entry["slot_id"] == "memory-owner"]
        self.assertEqual(amended["interim"]["pin"], expected)

        def pins(node):
            if isinstance(node, dict):
                if node.get("default") == "ai-memory 3.1.0" and "pin" in node:
                    yield node["pin"]
                for value in node.values():
                    yield from pins(value)
            elif isinstance(node, list):
                for value in node:
                    yield from pins(value)

        self.assertEqual(set(pins(handbook)), {expected})
        # No generated or recorded text prints the tag object glued to the tag.
        for path in (ROOT / "evidence/artifacts/new-wsl-layer-consensus-20261002/consensus.json",
                     ROOT / "evidence/artifacts/new-wsl-definitive-defaults-20261001/definitive-manifest.json", handbook_path,
                     ROOT / "docs/new-wsl-handbook.md"):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"v3\.1\.0\(tag object", path.name)

    def test_every_cited_ai_memory_source_is_at_the_run_pin_commit(self):
        for where, text in (("install-plan.json", json.dumps(self.row)),
                            ("install.sh", function(self.install, "memory-owner")),
                            ("accept.sh", function(self.accept, "memory-owner"))):
            commits = set(re.findall(r"akitaonrails/ai-memory/([0-9a-f]{40})/", text))
            self.assertTrue(commits, where)
            self.assertEqual(commits, {self.commit}, where)


if __name__ == "__main__":
    unittest.main()
