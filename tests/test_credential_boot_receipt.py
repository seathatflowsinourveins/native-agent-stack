"""Boot receipt: a value-free record of the credential store at each start of the user's service manager.

Local integration class. Every store is synthetic: HOME, XDG_CONFIG_HOME and XDG_STATE_HOME point into the
test's own temporary directory, the kernel's key list is a fixture file, and each store file holds a random
canary string generated per test. No real store, receipt directory or unit is read, written, loaded or started.
"""

from __future__ import annotations

import base64
import builtins
import hashlib
import io
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import credential_boot_receipt as cbr
from scripts.hooks import secret_path_guard as guard

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/credential_boot_receipt.py"
UNIT = ROOT / "adoption/templates/systemd/credential-boot-receipt.service"

# Every key a receipt may hold, as a dotted path ("rows[]" is any row). A field joins this list on purpose or not at
# all; the fixture of the allowlist test exercises every one, so the list cannot keep a key the tool dropped.
ALLOWED_KEYS = {
    "schema_version", "kind", "recorded_at",
    "boot", "boot.boot_id", "boot.uptime_seconds", "boot.systemd_version", "boot.linger",
    "checkout", "checkout.revision",
    "rows", "rows[].id", "rows[].status", "rows[].store_kind", "rows[].template", "rows[].state",
    "rows[].findings", "rows[].warnings", "rows[].fingerprint",
    "rows[].fingerprint.mode", "rows[].fingerprint.size", "rows[].fingerprint.mtime_ns",
    "coverage", "coverage.undeclared_store_files", "coverage.undeclared_keyring_keys",
    "warnings", "keyring_names", "claude_user_guard_matches_pin", "result",
}
FINGERPRINT_KEYS = {"mode", "size", "mtime_ns"}
FILE_KINDS = {"private_env_file", "private_file", "native_store"}
STATES = {"ok", "missing", "unsafe", "unchecked", "not_local", "changed_during_record"}
REASON_CODE = re.compile(r"[a-z0-9_]+")
LINE = re.compile(r"credential boot receipt: rows=\d+ ok=\d+ missing=\d+ unsafe=\d+ unchecked=\d+ not_local=\d+ "
                  r"changed_during_record=\d+ fingerprints=\d+ undeclared_store_files=(?:\d+|unknown) "
                  r"keyring_names=(?:\d+|unknown) guard_matches_pin=(?:true|false) "
                  r"result=(?:ok|unsafe|changed_during_record) "
                  r"receipt=\d{8,}-\d{8}T\d{6}\.\d{6}Z-(?:[0-9a-f]{8}|unknown)\.json")
SEQUENCE = re.compile(r"(\d{8,})-\d{8}T\d{6}\.\d{6}Z-(?:[0-9a-f]{8}|unknown)\.json")
# Two boot ids in the kernel's UUID form, joined at run time: scripts/validate.py flags a UUID written out in a
# tracked file as a possible local session identifier.
BOOT_A = "-".join(("3f2a9c1b", "5d6e", "4f70", "8a9b", "0c1d2e3f4a5b"))
BOOT_B = "-".join(("7c9d1e2f", "3a4b", "4c5d", "9e6f", "7a8b9c0d1e2f"))

# The unit template, pinned (amendments 2 and 3 of the D1 PR-3 contract). The workstation renders @REPOSITORY@ to the
# live clone, as its other installed units do; the working checkout and build worktrees are never the value.
PLACEHOLDER = re.compile(r"@([A-Z][A-Z0-9_]*)@")
LIVE_CLONE = {"REPOSITORY": "%h/code/native-agent-stack-live"}
EXEC_START = "ExecStart=/usr/bin/python3 -I @REPOSITORY@/scripts/credential_boot_receipt.py record"
UNIT_DIRECTIVES = [
    "[Unit]",
    "Description=Record a value-free receipt of the credential store at user-manager start",
    "[Service]",
    "Type=oneshot",
    "UMask=0077",
    "NoNewPrivileges=true",
    "TimeoutStartSec=120",
    EXEC_START,
    "[Install]",
    "WantedBy=default.target",
]
# Every directive that would hand the unit a variable or a credential: none belongs in this unit.
CREDENTIAL_DIRECTIVE = re.compile(
    r"(?:Environment|EnvironmentFile|PassEnvironment|LoadCredential\w*|SetCredential\w*|ImportCredential)=")
SED_RENDER = re.compile(r"^#\s+(sed '[^']*' adoption/templates/systemd/credential-boot-receipt\.service) > (\S+)$", re.M)
RENDER_COMMAND = ("sed 's#@REPOSITORY@#%h/code/native-agent-stack-live#g' "
                  "adoption/templates/systemd/credential-boot-receipt.service")


def directives(text: str) -> list[str]:
    """Non-blank, non-comment lines in order, section headers included (test_omniroute_gateway_unit.py's reading)."""
    return [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def render(text: str, values: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda match: values.get(match.group(1), match.group(0)), text)


def credential_directives(text: str) -> list[str]:
    return [line for line in directives(text) if CREDENTIAL_DIRECTIVE.match(line)]


def exec_start_problems(text: str) -> list[str]:
    """ExecStart= must be one line: /usr/bin/python3 -I, the script under @REPOSITORY@, the record command."""
    lines = [line for line in directives(text) if line.startswith("ExecStart=")]
    if len(lines) != 1:
        return [f"{len(lines)} ExecStart= lines"]
    argv = lines[0][len("ExecStart="):].split()
    problems = []
    if argv[:2] != ["/usr/bin/python3", "-I"]:
        problems.append("not /usr/bin/python3 -I")
    if len(argv) < 3 or not argv[2].startswith("@REPOSITORY@/"):
        problems.append("script not under @REPOSITORY@")
    if argv[2:] != ["@REPOSITORY@/scripts/credential_boot_receipt.py", "record"]:
        problems.append("not the record command")
    return problems


def with_exec_start(text: str, replacement: str) -> str:
    return "\n".join(replacement if line.startswith("ExecStart=") else line for line in text.splitlines()) + "\n"


def key_paths(value, prefix: str = "") -> set[str]:
    """Every dict key in value as a dotted path; the items of a list share one "[]" path segment."""
    paths = set()
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            paths.add(path)
            paths |= key_paths(item, path)
    elif isinstance(value, list):
        for item in value:
            paths |= key_paths(item, prefix + "[]")
    return paths


def encoded_forms(canary: str, content: bytes) -> dict[str, str]:
    """The canary and the forms a leak could take: base64 (standard, unpadded, URL-safe), hex in both cases,
    percent-encoding, and hashes of the canary and of the whole file, as hex and as base64."""
    raw = canary.encode()
    forms = {
        "raw": canary,
        "base64": base64.b64encode(raw).decode(),
        "base64 unpadded": base64.b64encode(raw).decode().rstrip("="),
        "base64 urlsafe": base64.urlsafe_b64encode(raw).decode().rstrip("="),
        "hex": raw.hex(),
        "HEX": raw.hex().upper(),
        "percent": urllib.parse.quote(canary, safe=""),
        "percent plus": urllib.parse.quote_plus(canary),
    }
    for name in ("md5", "sha1", "sha256", "sha512", "blake2b"):
        forms[f"{name} of the canary"] = hashlib.new(name, raw).hexdigest()
        forms[f"{name} of the file"] = hashlib.new(name, content).hexdigest()
        forms[f"{name} of the file, base64"] = base64.b64encode(hashlib.new(name, content).digest()).decode()
    return forms


def key_line(serial: int, name: str) -> str:
    """One line of /proc/keys for a live user key of this uid (the layout test_credential_status.py documents)."""
    uid = os.getuid()
    return f"{serial:08x} I--Q--- {1:5d} perm 3f0b0000 {uid:5d} {uid:5d} {'user':<9.9} native-agent-stack:{name}: 41\n"


class BootReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.home = self.base / "home"
        self.config = self.home / ".config"
        self.store = self.config / "native-agent-stack"
        self.store.mkdir(parents=True)
        self.store.chmod(0o700)
        self.state = self.home / ".local" / "state"
        self.receipts = self.state / "native-agent-stack" / "credential-boot"
        self.env = {"HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config), "XDG_STATE_HOME": str(self.state)}
        self.proc_keys = self.base / "proc-keys"  # a fixture: no test reads this host's /proc/keys
        self.proc_keys.write_text("")
        self.canaries: dict[str, tuple[str, bytes]] = {}
        self.clock = datetime(2026, 9, 29, 20, 15, 3, 123456, tzinfo=timezone.utc)

    def plant(self, path: Path | str, variable: str = "SOME_API_KEY", mode: int = 0o600) -> Path:
        """A store file of one export line whose value is a fresh canary with characters that percent-encode."""
        path = self.store / path if isinstance(path, str) else path
        canary = "CANARY" + secrets.token_hex(12) + "/+=@:%"
        content = f"export {variable}={canary}\n".encode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        path.write_bytes(content)
        path.chmod(mode)
        self.canaries[str(path)] = (canary, content)
        return path

    def install_guard(self):
        hooks = self.home / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "scripts/hooks/secret_path_guard.py", hooks / "secret_path_guard.py")

    def facts(self, boot_id: str | None = BOOT_A, uptime: float = 4.2) -> dict:
        return {"boot_id": boot_id, "uptime_seconds": uptime,
                "systemd_version": "systemd 255 (255.4-1ubuntu8.17)", "linger": True}

    def record(self, boot_id: str | None = BOOT_A, seconds: int = 0, uptime: float = 4.2):
        """An in-process record at a fixed clock with fixed boot facts."""
        return cbr.record(ROOT, self.env, proc_keys=self.proc_keys, facts=self.facts(boot_id, uptime),
                          now=self.clock + timedelta(seconds=seconds))

    def change_during_inspect(self, change, before_the_checker: bool = False):
        """Patch the checker's inspect, as the tool calls it, to run `change` just before or just after the checker's
        own observation of the store: the window between two observations of one record."""
        real = cbr.cs.inspect

        def inspect(*args, **kwargs):
            if before_the_checker:
                change()
            report = real(*args, **kwargs)
            if not before_the_checker:
                change()
            return report

        return patch.object(cbr.cs, "inspect", inspect)

    def run_cli(self, *args: str, isolated: bool = True, extra_env: dict | None = None):
        environment = {"PATH": os.environ.get("PATH", ""), **self.env, **(extra_env or {})}
        command = [sys.executable, *(["-I"] if isolated else []), str(SCRIPT), *args,
                   "--proc-keys", str(self.proc_keys)]
        return subprocess.run(command, env=environment, capture_output=True, text=True, timeout=120)

    def test_receipt_keys_are_an_explicit_allowlist_and_fingerprints_carry_no_content_hash(self):
        alpaca = self.plant("alpaca-paper.env", "APCA_API_KEY_ID")
        self.plant("tavily.env", "TAVILY_API_KEY")
        self.plant("stray.env")
        self.proc_keys.write_text(key_line(0x1a2b3c4d, "tavily_api_key"))
        path, receipt, _ = self.record()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), receipt)
        found = key_paths(receipt)
        self.assertLessEqual(found, ALLOWED_KEYS, f"keys outside the allowlist: {sorted(found - ALLOWED_KEYS)}")
        self.assertEqual(found, ALLOWED_KEYS, "the fixture no longer exercises every allowed key")
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual([row["id"] for row in receipt["rows"]], [entry["id"] for entry in inventory["entries"]])
        templates = {entry["id"]: entry["store"]["path_template"] for entry in inventory["entries"]}
        for row in receipt["rows"]:
            with self.subTest(row=row["id"]):
                self.assertEqual(row["template"], templates[row["id"]])
                self.assertIn(row["state"], STATES)
                for code in row["findings"] + row["warnings"]:
                    self.assertIsNotNone(REASON_CODE.fullmatch(code), code)
                self.assertEqual("fingerprint" in row, row["store_kind"] in FILE_KINDS)
                if row.get("fingerprint") is not None:
                    # Exactly mode, size and mtime_ns: no digest, checksum or content-derived field of any kind.
                    self.assertEqual(set(row["fingerprint"]), FINGERPRINT_KEYS)
                    self.assertIsNotNone(re.fullmatch(r"0[0-7]{3}", row["fingerprint"]["mode"]))
                    self.assertIs(type(row["fingerprint"]["size"]), int)
                    self.assertIs(type(row["fingerprint"]["mtime_ns"]), int)
        info = os.lstat(alpaca)
        row = next(row for row in receipt["rows"] if row["id"] == "alpaca-paper")
        self.assertEqual((row["state"], row["fingerprint"]),
                         ("ok", {"mode": "0600", "size": info.st_size, "mtime_ns": info.st_mtime_ns}))
        self.assertIsNone(next(row for row in receipt["rows"] if row["id"] == "sec-contact")["fingerprint"])
        self.assertEqual(receipt["coverage"]["undeclared_store_files"], ["stray.env"])
        self.assertEqual(receipt["keyring_names"], ["tavily_api_key"])  # the name; not its payload length
        self.assertEqual(receipt["boot"], self.facts())
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", receipt["checkout"]["revision"]))
        self.assertEqual((receipt["schema_version"], receipt["kind"], receipt["recorded_at"]),
                         (1, "credential_boot_receipt", "2026-09-29T20:15:03.123456Z"))
        self.assertEqual(path.name, "00000001-20260929T201503.123456Z-3f2a9c1b.json")

    def test_receipt_is_value_free(self):
        # A canary in every store file the inventory names, in a stray file, in the dot-file an interrupted writer
        # leaves, and in a native sign-in store. None of them, raw, encoded or hashed, reaches the receipt, the
        # printed line, stderr or compare's output, and neither does any host path.
        for name, variable in (("alpaca-paper.env", "APCA_API_KEY_ID"), ("alpaca-paper-2.env", "APCA_API_KEY_ID"),
                               ("sec-contact.env", "SEC_USER_AGENT"), ("tavily.env", "TAVILY_API_KEY"),
                               ("omniroute.env", "OMNIROUTE_API_KEY"), ("databento.env", "DATABENTO_API_KEY"),
                               ("stray.env", "STRAY_API_KEY"),
                               (".tavily.env.0123456789abcdef.tmp", "TAVILY_API_KEY")):
            self.plant(name, variable)
        self.plant(self.home / ".claude" / ".credentials.json", "CLAUDE_OAUTH")
        self.proc_keys.write_text(key_line(0x1a2b3c4d, "tavily_api_key"))
        result = self.run_cli("record")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)
        self.assertIsNotNone(LINE.fullmatch(result.stdout.strip()), result.stdout)
        written = sorted(self.receipts.iterdir())
        self.assertEqual(len(written), 1, [p.name for p in written])
        text = written[0].read_text(encoding="utf-8")
        receipt = json.loads(text)
        # The receipt the unit's command writes keeps to the same allowlist, with fingerprints of exactly three fields.
        found = key_paths(receipt)
        self.assertLessEqual(found, ALLOWED_KEYS, f"keys outside the allowlist: {sorted(found - ALLOWED_KEYS)}")
        fingerprints = [row["fingerprint"] for row in receipt["rows"] if row.get("fingerprint") is not None]
        self.assertGreaterEqual(len(fingerprints), 7)
        for fingerprint in fingerprints:
            self.assertEqual(set(fingerprint), FINGERPRINT_KEYS)
        compare = self.run_cli("compare")
        self.assertEqual(compare.returncode, 0, compare.stderr)
        outputs = {"receipt": text, "printed line": result.stdout, "stderr": result.stderr,
                   "compare": compare.stdout + compare.stderr}
        self.assertEqual(len(self.canaries), 9)
        for name, (canary, content) in self.canaries.items():
            for form, encoded in encoded_forms(canary, content).items():
                for label, output in outputs.items():
                    with self.subTest(file=Path(name).name, form=form, output=label):
                        self.assertNotIn(encoded, output)
        for label, output in outputs.items():
            self.assertNotIn(str(self.base), output, label)
        # The dot-file and the stray file are named, by name only, in the undeclared-file warning.
        self.assertEqual(receipt["coverage"]["undeclared_store_files"],
                         [".tavily.env.0123456789abcdef.tmp", "stray.env"])
        self.assertIn("undeclared_store_file", receipt["warnings"])
        self.assertIn(" undeclared_store_files=2 ", result.stdout)
        self.assertEqual(receipt["keyring_names"], ["tavily_api_key"])

    def test_record_opens_no_store_file(self):
        for name in ("alpaca-paper.env", ".tavily.env.0123456789abcdef.tmp"):
            self.plant(name)
        self.plant(self.home / ".claude" / ".credentials.json")
        # A store file replaced by a link: fingerprinted as the link itself (lstat), and its target never opened.
        target = self.plant(self.base / "outside" / "tavily.env", "TAVILY_API_KEY")
        (self.store / "tavily.env").symlink_to(target)
        self.install_guard()
        opened = []
        real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

        def watch(real):
            def opener(file, *args, **kwargs):
                opened.append(str(file))
                return real(file, *args, **kwargs)
            return opener

        with patch("builtins.open", watch(real_open)), patch("io.open", watch(real_io_open)), \
                patch("os.open", watch(real_os_open)):
            _, receipt, _ = self.record()
        self.assertTrue(opened)  # the watch saw the inventory, the guard and the receipt's own file
        self.assertEqual([p for p in opened if str(self.store) in p or ".credentials.json" in p
                          or str(target) in p], [])
        self.assertIs(receipt["claude_user_guard_matches_pin"], True)
        linked = next(row for row in receipt["rows"] if row["id"] == "tavily")
        self.assertEqual(linked["state"], "unsafe")
        self.assertIn("symlink_refused", linked["findings"])
        link = os.lstat(self.store / "tavily.env")
        self.assertEqual(linked["fingerprint"], {"mode": format(stat.S_IMODE(link.st_mode), "04o"),
                                                 "size": link.st_size, "mtime_ns": link.st_mtime_ns})
        self.assertNotEqual(linked["fingerprint"]["mode"], "0600")  # the target's mode would mean it was followed

    def test_receipt_mode_0600(self):
        self.plant("alpaca-paper.env")
        first, _, _ = self.record()
        self.assertEqual(first.parent, self.receipts)
        self.assertEqual(stat.S_IMODE(os.lstat(first).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.lstat(self.receipts).st_mode), 0o700)
        self.assertEqual([p.name for p in self.receipts.iterdir()], [first.name])  # no temporary file left
        # A looser directory is tightened; with no umask at all the modes are the same.
        self.receipts.chmod(0o755)
        previous = os.umask(0)
        try:
            second, _, _ = self.record(seconds=1)
        finally:
            os.umask(previous)
        self.assertEqual(stat.S_IMODE(os.lstat(self.receipts).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.lstat(second).st_mode), 0o600)
        # A receipt is never replaced: the same stamp and boot again take the next sequence number, and the earlier
        # receipt is left as it was.
        before = second.read_bytes()
        third, _, _ = self.record(seconds=1, uptime=9.9)
        self.assertEqual([p.name[:9] for p in (first, second, third)], ["00000001-", "00000002-", "00000003-"])
        self.assertEqual(second.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.receipts.iterdir()), [first.name, second.name, third.name])
        # A receipt directory that is a symbolic link is refused, and nothing is written through it.
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        shutil.rmtree(self.receipts)
        self.receipts.symlink_to(elsewhere)
        result = self.run_cli("record")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("not a real directory", result.stderr)
        self.assertNotIn(str(self.base), result.stderr)
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_compare_flags_ok_to_missing(self):
        tavily = self.plant("tavily.env", "TAVILY_API_KEY")  # optional file row
        alpaca = self.plant("alpaca-paper.env", "APCA_API_KEY_ID")  # required file row
        databento = self.plant("databento.env", "DATABENTO_API_KEY")  # user_only_paid: reported, never gated
        self.record(BOOT_A, 0)
        tavily.unlink()
        databento.unlink()
        self.record(BOOT_B, 60)
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^  tavily \(optional, private_env_file\): ok -> missing, "
                                        r"fingerprint gone  <- regression$")
        self.assertRegex(result.stdout, r"(?m)^  databento \(user_only_paid, private_env_file\): ok -> missing, "
                                        r"fingerprint gone$")
        self.assertRegex(result.stdout, r"(?m)^  alpaca-paper \(required, private_env_file\): ok -> ok, "
                                        r"fingerprint same$")
        self.assertIn("result: regression: tavily", result.stdout)
        # ok -> unsafe on a required row is a regression too; a row coming back is not.
        self.plant(tavily, "TAVILY_API_KEY")
        alpaca.chmod(0o644)
        self.record(BOOT_B, 120)
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^  alpaca-paper \(required, private_env_file\): ok -> unsafe, "
                                        r"fingerprint changed: mode  <- regression$")
        self.assertRegex(result.stdout, r"(?m)^  tavily \(optional, private_env_file\): missing -> ok, "
                                        r"fingerprint new$")
        self.assertIn("result: regression: alpaca-paper", result.stdout)
        # A gated row missing from the newer receipt cannot show that its file survived.
        alpaca.chmod(0o600)
        _, latest, _ = self.record(BOOT_B, 180)
        self.assertEqual(self.run_cli("compare").returncode, 0)
        latest["rows"] = [row for row in latest["rows"] if row["id"] != "tavily"]
        cbr.write_receipt(self.receipts, latest, cbr.receipt_label(self.clock + timedelta(seconds=240), BOOT_B))
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^  tavily \(optional, private_env_file\): ok -> \(no row\)  "
                                        r"<- regression$")

    def test_a_file_changed_during_record_is_never_ok(self):
        # The checker's observation and the fingerprint must describe one file. A file removed or replaced between
        # two observations of one record makes its row changed_during_record, which compare counts as not ok.
        tavily = self.plant("tavily.env", "TAVILY_API_KEY")
        self.plant("alpaca-paper.env", "APCA_API_KEY_ID")
        self.record(BOOT_A, 0)
        with self.change_during_inspect(tavily.unlink):  # removed right after the checker saw it
            _, receipt, line = self.record(BOOT_B, 60)
        row = next(row for row in receipt["rows"] if row["id"] == "tavily")
        self.assertEqual((row["state"], row["fingerprint"]), ("changed_during_record", None))
        self.assertEqual(next(row for row in receipt["rows"] if row["id"] == "alpaca-paper")["state"], "ok")
        self.assertEqual(receipt["result"], "changed_during_record")
        self.assertIn(" changed_during_record=1 ", line)
        self.assertIn(" result=changed_during_record ", line)
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^  tavily \(optional, private_env_file\): ok -> changed_during_record, "
                                        r"fingerprint gone  <- regression$")
        # Removed just before the checker looked: the same.
        self.plant(tavily, "TAVILY_API_KEY")
        self.record(BOOT_B, 120)
        with self.change_during_inspect(tavily.unlink, before_the_checker=True):
            _, receipt, _ = self.record(BOOT_B, 180)
        self.assertEqual(next(row for row in receipt["rows"] if row["id"] == "tavily")["state"], "changed_during_record")
        # Replaced by a file with the same bytes, mode and mtime: only its inode and ctime differ, so the three
        # recorded fields cannot tell, and the row is still not ok.
        self.plant(tavily, "TAVILY_API_KEY")
        self.record(BOOT_B, 240)
        seen = os.lstat(tavily)

        def replace():
            twin = tavily.with_name(".tavily.env.twin")
            twin.write_bytes(tavily.read_bytes())
            twin.chmod(0o600)
            os.utime(twin, ns=(seen.st_atime_ns, seen.st_mtime_ns))
            os.replace(twin, tavily)

        with self.change_during_inspect(replace):
            _, receipt, _ = self.record(BOOT_B, 300)
        row = next(row for row in receipt["rows"] if row["id"] == "tavily")
        self.assertEqual(row["state"], "changed_during_record")
        self.assertEqual(row["fingerprint"], {"mode": "0600", "size": seen.st_size, "mtime_ns": seen.st_mtime_ns})
        self.assertEqual(self.run_cli("compare").returncode, 1)
        # Nothing changes during a record: the row is ok, with no false alarm.
        with self.change_during_inspect(lambda: None):
            _, receipt, line = self.record(BOOT_B, 360)
        self.assertEqual(next(row for row in receipt["rows"] if row["id"] == "tavily")["state"], "ok")
        self.assertEqual(receipt["result"], "ok")
        self.assertIn(" changed_during_record=0 ", line)

    def test_receipts_compare_in_creation_order_when_the_clock_steps_back(self):
        # A WSL clock can step back after a Windows sleep or before its first time sync. A receipt stamped 60 s
        # before its predecessor is still the newer one, so a file lost across the restart is still a regression.
        tavily = self.plant("tavily.env", "TAVILY_API_KEY")
        self.plant("alpaca-paper.env", "APCA_API_KEY_ID")
        first, _, _ = self.record(BOOT_A, 0)
        tavily.unlink()
        second, _, _ = self.record(BOOT_B, -60)
        self.assertEqual((first.name, second.name), ("00000001-20260929T201503.123456Z-3f2a9c1b.json",
                                                     "00000002-20260929T201403.123456Z-7c9d1e2f.json"))
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], f"compare: {first.name} -> {second.name}")
        self.assertRegex(result.stdout, r"(?m)^  tavily \(optional, private_env_file\): ok -> missing, "
                                        r"fingerprint gone  <- regression$")

    def test_unsequenced_receipts_come_before_every_sequenced_one(self):
        # Receipts named before sequence numbers (<UTC stamp>-<boot id prefix>.json) never break compare: among
        # themselves they keep name order, and they come before every sequenced receipt whatever their stamps.
        self.plant("tavily.env", "TAVILY_API_KEY")
        written, kept, _ = self.record(BOOT_A, 0)
        written.unlink()
        lost = json.loads(json.dumps(kept))
        next(row for row in lost["rows"] if row["id"] == "tavily").update(state="missing", fingerprint=None)
        older, newer = "20260929T101503.123456Z-3f2a9c1b.json", "20260929T111503.123456Z-3f2a9c1b.json"
        (self.receipts / older).write_text(json.dumps(kept))
        (self.receipts / newer).write_text(json.dumps(lost))
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], f"compare: {older} -> {newer}")
        # Unsequenced names do not count toward the sequence, and a far-future one never overtakes a sequenced one.
        first, _, _ = self.record(BOOT_B, -86400)
        self.assertEqual(first.name[:9], "00000001-")
        (self.receipts / "20991231T235959.999999Z-3f2a9c1b.json").write_text(json.dumps(lost))
        second, _, _ = self.record(BOOT_B, -86399)
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], f"compare: {first.name} -> {second.name}")

    def test_concurrent_records_get_distinct_sequence_numbers(self):
        self.plant("tavily.env", "TAVILY_API_KEY")
        # Force the race: both writers leave the checker's scan together, and each holds the sequence number it chose
        # for a moment before linking. Only the directory lock keeps them from choosing the same number.
        barrier = threading.Barrier(2, timeout=60)
        real_inspect, real_next = cbr.cs.inspect, cbr.next_sequence

        def inspect(*args, **kwargs):
            report = real_inspect(*args, **kwargs)
            barrier.wait()
            return report

        def next_sequence(directory):
            sequence = real_next(directory)
            time.sleep(0.3)
            return sequence

        names, errors = [], []

        def worker(seconds):
            try:
                names.append(self.record(BOOT_A, seconds)[0].name)
            except Exception as error:  # noqa: BLE001  (reported by the assertion below)
                errors.append(repr(error))

        with patch.object(cbr.cs, "inspect", inspect), patch.object(cbr, "next_sequence", next_sequence):
            threads = [threading.Thread(target=worker, args=(seconds,)) for seconds in (0, 1)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(120)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(SEQUENCE.fullmatch(name).group(1) for name in names), ["00000001", "00000002"])
        # Two processes running the unit's own command at once: distinct numbers as well.
        environment = {"PATH": os.environ.get("PATH", ""), **self.env}
        processes = [subprocess.Popen([sys.executable, "-I", str(SCRIPT), "record", "--proc-keys", str(self.proc_keys)],
                                      env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
        outputs = [process.communicate(timeout=120) for process in processes]
        self.assertEqual([process.returncode for process in processes], [0, 0], outputs)
        numbers = sorted(int(match.group(1)) for match in (SEQUENCE.fullmatch(p.name) for p in self.receipts.iterdir())
                         if match)
        self.assertEqual(numbers, [1, 2, 3, 4])

    def test_a_taken_name_moves_the_writer_to_the_next_sequence(self):
        # Under the lock no writer of this tool takes a name another one chose. A name taken anyway (EEXIST) makes the
        # writer choose the sequence again, a bounded number of times, and never replaces the file.
        self.plant("tavily.env", "TAVILY_API_KEY")
        self.receipts.mkdir(parents=True, mode=0o700)
        label = cbr.receipt_label(self.clock, BOOT_A)
        squatter = self.receipts / f"00000001-{label}.json"
        squatter.write_text("planted\n")
        stale = iter([1])
        real_next = cbr.next_sequence
        with patch.object(cbr, "next_sequence", lambda directory: next(stale, None) or real_next(directory)):
            path, _, _ = self.record(BOOT_A, 0)
        self.assertEqual(path.name, f"00000002-{label}.json")
        self.assertEqual(squatter.read_text(), "planted\n")
        calls = []
        with patch.object(cbr, "next_sequence", lambda directory: calls.append(directory) or 1), \
                self.assertRaises(FileExistsError):
            self.record(BOOT_A, 0)
        self.assertEqual(len(calls), cbr.LINK_ATTEMPTS)
        self.assertEqual(sorted(p.name for p in self.receipts.iterdir()), sorted([squatter.name, path.name]))

    def test_compare_after_a_restart_names_changes_and_never_values(self):
        alpaca = self.plant("alpaca-paper.env", "APCA_API_KEY_ID")
        self.plant("tavily.env", "TAVILY_API_KEY")
        self.install_guard()
        self.proc_keys.write_text(key_line(0x1a2b3c4d, "tavily_api_key") + key_line(0x1a2b3c4e, "alpaca-paper-1-id"))
        self.record(BOOT_A, 0, uptime=812.4)  # R0, before the restart
        self.proc_keys.write_text("")  # the kernel restart erased the keyring
        self.record(BOOT_B, 3600, uptime=5.1)  # R1, written by the oneshot at the next start
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "compare: 00000001-20260929T201503.123456Z-3f2a9c1b.json -> "
                                   "00000002-20260929T211503.123456Z-7c9d1e2f.json")
        self.assertIn("boot_id: changed (uptime at record 812.4 s -> 5.1 s)", lines)
        self.assertIn("  alpaca-paper (required, private_env_file): ok -> ok, fingerprint same", lines)
        self.assertIn("  tavily (optional, private_env_file): ok -> ok, fingerprint same", lines)
        self.assertIn("kernel keyring names: alpaca-paper-1-id,tavily_api_key -> none "
                      "(memory only: a kernel restart erases them)", lines)
        self.assertIn("claude_user_guard_matches_pin: true -> true", lines)
        self.assertEqual(lines[-1], "result: ok (no required or optional file row left ok)")
        # A rewritten file is named by field only: its new size (its value's length) is never printed.
        self.plant(alpaca, "APCA_API_KEY_ID_LONGER")
        stamp = os.lstat(alpaca).st_mtime_ns
        os.utime(alpaca, ns=(stamp, stamp + 10**9))
        self.record(BOOT_B, 3700, uptime=105.1)
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("  alpaca-paper (required, private_env_file): ok -> ok, fingerprint changed: size, mtime_ns",
                      result.stdout.splitlines())
        self.assertIn("boot_id: unchanged (uptime at record 5.1 s -> 105.1 s)", result.stdout.splitlines())
        self.assertNotRegex(result.stdout, r"size\W{0,3}\d")
        for size in {str(os.lstat(alpaca).st_size), str(len(self.canaries[str(alpaca)][1]))}:
            self.assertNotRegex(result.stdout, rf"(?<!\d){size}(?!\d)")

    def test_compare_reports_the_baseline_and_refuses_without_a_readable_receipt(self):
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("no receipt", result.stderr)
        path, _, _ = self.record()
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0],
                         f"baseline: {path.name} (one receipt; nothing to compare yet)")
        self.assertIsNotNone(LINE.fullmatch(result.stdout.splitlines()[1]), result.stdout)
        # A leftover dot-file of a killed writer is not a receipt; an unreadable receipt stops compare.
        (self.receipts / f".{path.name}.0123abcd.tmp").write_text("{")
        self.assertEqual(self.run_cli("compare").returncode, 0)
        (self.receipts / f"00000002-{cbr.receipt_label(self.clock + timedelta(seconds=5), BOOT_B)}.json").write_text("{")
        result = self.run_cli("compare")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("cannot read", result.stderr)

    def test_a_plain_start_reruns_isolated(self):
        # Started without -I, the tool re-executes itself with -I (as tools/credentials/set_credential.py does), so a
        # module planted on PYTHONPATH is never imported by it.
        planted = self.base / "planted"
        planted.mkdir()
        marker = self.base / "planted-module-imported"
        (planted / "tempfile.py").write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('imported')\nraise ImportError('planted')\n")
        result = self.run_cli("record", isolated=False, extra_env={"PYTHONPATH": str(planted)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertIsNotNone(LINE.fullmatch(result.stdout.strip()), result.stdout)


class BootReceiptUnitTemplateTests(unittest.TestCase):
    """adoption/templates/systemd/credential-boot-receipt.service as text. Nothing here loads, enables or starts it;
    `systemd-analyze --user verify` on a rendered copy is a separate, manual acceptance check."""

    def setUp(self):
        self.text = UNIT.read_text(encoding="utf-8")

    def test_unit_text_is_pinned(self):
        self.assertEqual(directives(self.text), UNIT_DIRECTIVES)

    def test_a_oneshot_that_runs_record_isolated_at_every_user_manager_start(self):
        lines = directives(self.text)
        self.assertIn("Type=oneshot", lines)
        self.assertIn("WantedBy=default.target", lines)
        self.assertEqual(exec_start_problems(self.text), [])
        self.assertEqual(credential_directives(self.text), [])  # no Environment=, EnvironmentFile= or LoadCredential=
        self.assertTrue(SCRIPT.is_file())

    def test_the_documented_render_gives_the_live_clone_never_the_working_checkout_or_a_worktree(self):
        self.assertEqual(set(PLACEHOLDER.findall("\n".join(directives(self.text)))), {"REPOSITORY"})
        header = "\n".join(line for line in self.text.splitlines() if line.startswith("#"))
        self.assertIn("@REPOSITORY@", header)
        self.assertIn(LIVE_CLONE["REPOSITORY"], header)
        # The header's render command is pinned, then run on the template without a shell (stdout only, no install).
        match = SED_RENDER.search(self.text)
        self.assertIsNotNone(match, "the header must give the sed render command")
        self.assertEqual(match.group(1), RENDER_COMMAND)
        self.assertEqual(match.group(2), "~/.config/systemd/user/credential-boot-receipt.service")
        rendered = subprocess.run(shlex.split(RENDER_COMMAND), cwd=ROOT, capture_output=True, text=True,
                                  timeout=30, check=True).stdout
        self.assertEqual(rendered, render(self.text, LIVE_CLONE))
        self.assertNotIn("@REPOSITORY@", rendered)
        exec_start = next(line for line in directives(rendered) if line.startswith("ExecStart="))
        self.assertEqual(exec_start, "ExecStart=/usr/bin/python3 -I "
                                     "%h/code/native-agent-stack-live/scripts/credential_boot_receipt.py record")
        for wrong in ("%h/code/native-agent-stack/", "worktree", "scratchpad", "/tmp/"):
            self.assertNotIn(wrong, "\n".join(directives(rendered)))

    def test_the_checks_catch_planted_violations(self):
        for line in ("Environment=TAVILY_API_KEY=planted", "Environment=HARMLESS=1",
                     "EnvironmentFile=%h/.config/native-agent-stack/tavily.env",
                     "LoadCredential=tavily:%h/.config/native-agent-stack/tavily.env",
                     "LoadCredentialEncrypted=tavily:%h/tavily.cred", "SetCredential=tavily:planted",
                     "ImportCredential=tavily", "PassEnvironment=TAVILY_API_KEY"):
            with self.subTest(line=line):
                planted = self.text.replace("[Service]\n", f"[Service]\n{line}\n")
                self.assertEqual(credential_directives(planted), [line])
                self.assertNotEqual(directives(planted), UNIT_DIRECTIVES)
        for drifted in ("ExecStart=/usr/bin/python3 @REPOSITORY@/scripts/credential_boot_receipt.py record",
                        "ExecStart=/usr/bin/python3 -I %h/code/native-agent-stack/scripts/credential_boot_receipt.py "
                        "record",
                        "ExecStart=/usr/bin/python3 -I @REPOSITORY@/scripts/credential_boot_receipt.py compare",
                        "ExecStart=python3 -I @REPOSITORY@/scripts/credential_boot_receipt.py record"):
            with self.subTest(exec_start=drifted):
                self.assertNotEqual(exec_start_problems(with_exec_start(self.text, drifted)), [])
        self.assertEqual(exec_start_problems(with_exec_start(self.text, EXEC_START)), [])
        self.assertNotEqual(directives(self.text.replace("WantedBy=default.target", "WantedBy=timers.target")),
                            UNIT_DIRECTIVES)


class RestartCheckRunbookTests(unittest.TestCase):
    """docs/secret-storage.md, "Restart check (2026-09-29)". The coordinator runs its fenced commands under the
    secret-path guard (scripts/hooks/secret_path_guard.py), and they install exactly the pinned render of the unit."""

    def section(self) -> str:
        text = (ROOT / "docs/secret-storage.md").read_text(encoding="utf-8")
        match = re.search(r"^## Restart check \(2026-09-29\)\n(.*?)(?=^## )", text, re.M | re.S)
        self.assertIsNotNone(match, "docs/secret-storage.md has no Restart check section")
        return match.group(1)

    def commands(self) -> list[str]:
        blocks = re.findall(r"^[ \t]*```sh\n(.*?)^[ \t]*```", self.section(), re.M | re.S)
        return [line.strip() for block in blocks for line in block.splitlines() if line.strip()]

    def test_every_runbook_command_passes_the_guard(self):
        commands = self.commands()
        self.assertGreaterEqual(len(commands), 10)
        for command in commands:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_the_runbook_installs_the_pinned_render_and_leaves_the_restart_to_the_user(self):
        commands = self.commands()
        for command in (f"{RENDER_COMMAND} > ~/.config/systemd/user/credential-boot-receipt.service",
                        "systemd-analyze --user verify ~/.config/systemd/user/credential-boot-receipt.service",
                        "systemctl --user daemon-reload", "systemctl --user enable credential-boot-receipt.service",
                        "systemctl --user start credential-boot-receipt.service",
                        "python3 -I scripts/credential_boot_receipt.py compare"):
            self.assertIn(command, commands)
        section = self.section()
        self.assertIn("`wsl --shutdown`", section)  # the user's step, from Windows
        self.assertFalse([command for command in commands if "shutdown" in command or "reboot" in command])
        self.assertIn('`--env-file "$PAPER_ENV_FILE"`', section)  # the paper units are unchanged


if __name__ == "__main__":
    unittest.main()
