"""adoption/tools/tvly-keyring: tvly with TAVILY_API_KEY from the kernel keyring, for that command only.

Local integration class (docs/acceptance-evidence-policy.md), with a synthetic `tvly`: a fake on PATH
reports only whether TAVILY_API_KEY is set, the value's length in bytes and its own arguments, never the
value. Keyring tests store generated throwaway values under names unique to this run
(``kktvly-<pid>-<hex>-<label>``) with scripts/kernel_keyring.py and remove them with their own keyctl
calls (tests/test_kernel_keyring.py's ``Kernel``); the wrapper reaches them through TVLY_KEYRING_NAME,
so no test reads the operator's tavily_api_key. Every run's stdout and stderr are checked for each
test value. The wrapper runs from a temporary install directory laid out as adoption/tools/README.md
installs it. Checks that need no key run everywhere; the others are skipped unless Linux
x86_64/aarch64 with the keyring system calls allowed, as in tests/test_kernel_keyring.py.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest

from tests.test_kernel_keyring import SUPPORTED, Kernel

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "adoption" / "tools" / "tvly-keyring"
KEYRING = ROOT / "scripts" / "kernel_keyring.py"
SHELLCHECK = shutil.which("shellcheck")
# Built from fragments so this file never matches its own check.
PERSONAL_HOME = re.compile("/(?:" + "home" + "|" + "Users" + ")/[A-Za-z0-9_.-]+")
# Reports whether TAVILY_API_KEY is set and the value's length, never the value; touches a marker
# file when FAKE_TVLY_MARKER is set, and exits with FAKE_TVLY_EXIT.
FAKE_TVLY = (
    "import json, os, sys\n"
    "value = os.environ.get('TAVILY_API_KEY')\n"
    "marker = os.environ.get('FAKE_TVLY_MARKER')\n"
    "if marker: open(marker, 'w').close()\n"
    "json.dump({'set': value is not None, 'length': len(os.fsencode(value)) if value is not None else 0,\n"
    "           'argv': sys.argv[1:], 'inherited': os.environ.get('KK_TEST_MARKER')}, sys.stdout)\n"
    "sys.exit(int(os.environ.get('FAKE_TVLY_EXIT', '0')))\n"
)
# Arguments tvly must receive exactly: spaces, an empty string, globs, quotes, a literal $HOME, a
# separator, option-like words, a newline and non-ASCII text.
ARGUMENTS = ["research", "run", "two words", "", "*", "a'b\"c", "$HOME", "--", "-n", "--json",
             "line one\nline two", "café"]


def link(directory: Path, name: str, target: str) -> None:
    (directory / name).symlink_to(target)


class InstallLayout(unittest.TestCase):
    """A temporary install directory, a fake tvly and a minimal PATH; no tests of its own."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.install = self.base / "bin"  # the wrapper's install directory
        self.install.mkdir()
        self.tools = self.base / "tools"  # a PATH directory with the programs the wrapper runs
        self.tools.mkdir()
        for program in ("dirname", "readlink"):
            link(self.tools, program, shutil.which(program))
        link(self.tools, "python3", sys.executable)
        self.fake = self.base / "fake"  # a PATH directory holding the fake tvly
        self.fake.mkdir()
        fake = self.fake / "tvly"
        fake.write_text(f"#!{sys.executable}\n{FAKE_TVLY}", encoding="utf-8")
        fake.chmod(0o755)
        self.marker = self.base / "tvly-ran"
        self.values: list[bytes] = []

    def installed(self, with_keyring: bool = True) -> Path:
        wrapper = self.install / "tvly-keyring"
        shutil.copy2(WRAPPER, wrapper)
        if with_keyring:
            shutil.copy2(KEYRING, self.install / "kernel_keyring.py")
        return wrapper

    def run_wrapper(self, wrapper: Path, *args: str, path: list[Path] | None = None, **env: str):
        search = path if path is not None else [self.fake, self.tools]
        environment = {"PATH": os.pathsep.join(str(p) for p in search), "HOME": str(self.base),
                       "FAKE_TVLY_MARKER": str(self.marker), "KK_TEST_MARKER": "inherited", **env}
        result = subprocess.run([str(wrapper), *args], capture_output=True, env=environment, timeout=60)
        for value in self.values:
            self.assertNotIn(value, result.stdout + result.stderr, "a test value appeared in the output")
        return result


class TvlyKeyringTests(InstallLayout):
    """What needs no key: the wrapper's text, and finding kernel_keyring.py and tvly."""

    def test_file_is_an_executable_posix_sh_script(self):
        self.assertTrue(os.access(WRAPPER, os.X_OK))
        text = WRAPPER.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        for shell in ("sh", "dash", "bash"):
            path = shutil.which(shell)
            if path:
                with self.subTest(shell=shell):
                    result = subprocess.run([path, "-n", str(WRAPPER)], capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(PERSONAL_HOME.findall(text), [])

    @unittest.skipUnless(SHELLCHECK, "shellcheck is not on PATH")
    def test_shellcheck_is_clean_at_style_severity(self):
        result = subprocess.run([SHELLCHECK, "-S", "style", str(WRAPPER)], capture_output=True, text=True,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_wrapper_never_reads_the_key_itself(self):
        # Only kernel_keyring.py reads the payload: the wrapper runs no keyctl, never expands the
        # variable, and names it once, as exec's ENV_VAR argument, passing every argument on as "$@".
        code = "\n".join(line for line in WRAPPER.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertNotIn("keyctl", code)
        self.assertNotRegex(code, r"\$\{?TAVILY_API_KEY")
        self.assertEqual(code.count("TAVILY_API_KEY"), 1)
        self.assertIn('exec python3 "$keyring" exec "$name" TAVILY_API_KEY -- "$tvly" "$@"', code)

    def test_missing_kernel_keyring_script_exits_2_before_tvly(self):
        wrapper = self.installed(with_keyring=False)
        result = self.run_wrapper(wrapper, "search", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"no kernel_keyring.py beside this script", result.stderr)
        self.assertIn(b"TVLY_KEYRING_SCRIPT", result.stderr)
        self.assertFalse(self.marker.exists())
        pointed = self.run_wrapper(wrapper, "search", "x", TVLY_KEYRING_SCRIPT=str(self.base / "missing.py"))
        self.assertEqual(pointed.returncode, 2)
        self.assertIn(b"no kernel_keyring.py at TVLY_KEYRING_SCRIPT", pointed.stderr)
        self.assertFalse(self.marker.exists())

    def test_missing_tvly_exits_127(self):
        wrapper = self.installed()
        result = self.run_wrapper(wrapper, "search", "x", path=[self.tools])
        self.assertEqual(result.returncode, 127)
        self.assertIn(b"no tvly on PATH", result.stderr)

    def test_a_tvly_that_is_this_wrapper_is_refused(self):
        wrapper = self.installed()
        link(self.install, "tvly", "tvly-keyring")  # a shadowing link would otherwise recurse
        result = self.run_wrapper(wrapper, "search", "x", path=[self.install, self.fake, self.tools])
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"tvly on PATH is this wrapper", result.stderr)
        self.assertFalse(self.marker.exists())


@unittest.skipUnless(SUPPORTED, "the kernel keyring script supports Linux x86_64/aarch64 only")
class TvlyKeyringKernelTests(InstallLayout):
    """The same install layout against the real kernel user keyring, with throwaway keys."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kernel = Kernel()
        probe = cls.kernel.search(f"kktvly-probe-{secrets.token_hex(4)}")
        if probe < 0 and -probe not in {errno.ENOKEY, errno.EKEYREVOKED, errno.EKEYEXPIRED}:
            raise unittest.SkipTest(f"kernel keyring unavailable here ({errno.errorcode.get(-probe, -probe)})")
        cls.run_id = f"kktvly-{os.getpid()}-{secrets.token_hex(4)}"

    def setUp(self) -> None:
        super().setUp()
        self.names: list[str] = []

    def tearDown(self) -> None:
        for name in self.names:
            self.kernel.remove(name)
        for name in self.names:
            self.assertLessEqual(self.kernel.search(name), 0, f"{name} was left in the keyring")

    def stored(self, label: str) -> tuple[str, bytes]:
        name, value = f"{self.run_id}-{label}", f"kk-canary-{secrets.token_hex(16)}".encode()
        self.names.append(name)
        self.values.append(value)
        result = subprocess.run([sys.executable, str(KEYRING), "store", name], input=value, capture_output=True,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        return name, value

    def report(self, result) -> dict:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        return json.loads(result.stdout)

    def test_tvly_gets_the_key_and_every_argument_verbatim(self):
        name, value = self.stored("present")
        wrapper = self.installed()
        decoy = f"kk-decoy-{secrets.token_hex(4)}".encode()  # an inherited value is replaced
        self.values.append(decoy)
        report = self.report(self.run_wrapper(wrapper, *ARGUMENTS, TVLY_KEYRING_NAME=name,
                                              TAVILY_API_KEY=decoy.decode()))
        self.assertEqual(report, {"set": True, "length": len(value), "argv": ARGUMENTS, "inherited": "inherited"})
        self.assertTrue(self.marker.exists())
        self.assertNotIn("TAVILY_API_KEY", os.environ)

    def test_the_status_of_tvly_is_returned(self):
        name, _value = self.stored("status")
        result = self.run_wrapper(self.installed(), "search", "x", TVLY_KEYRING_NAME=name, FAKE_TVLY_EXIT="7")
        self.assertEqual(result.returncode, 7)

    def test_the_keyring_script_is_found_through_the_pointer_or_a_symlink(self):
        name, value = self.stored("lookup")
        alone = self.installed(with_keyring=False)
        pointed = self.report(self.run_wrapper(alone, "auth", "--json", TVLY_KEYRING_NAME=name,
                                               TVLY_KEYRING_SCRIPT=str(KEYRING)))
        self.assertEqual((pointed["set"], pointed["length"]), (True, len(value)))
        wrapper = self.installed()
        elsewhere = self.base / "linked"
        elsewhere.mkdir()
        link(elsewhere, "tvly-keyring", str(wrapper))  # as a ~/.local/bin link to the install directory
        linked = self.report(self.run_wrapper(elsewhere / "tvly-keyring", "auth", "--json",
                                              TVLY_KEYRING_NAME=name))
        self.assertEqual((linked["set"], linked["length"]), (True, len(value)))

    def test_an_absent_key_exits_2_without_running_tvly(self):
        name = f"{self.run_id}-absent"
        self.names.append(name)
        result = self.run_wrapper(self.installed(), "search", "x", TVLY_KEYRING_NAME=name)
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertIn(f"{name} is not in the kernel user keyring".encode(), result.stderr)
        self.assertFalse(self.marker.exists())

    def test_a_refused_key_name_is_not_repeated(self):
        pasted = "tvlyPastedValue" + secrets.token_hex(8)  # an uppercase letter, as in most API keys
        result = self.run_wrapper(self.installed(), "search", "x", TVLY_KEYRING_NAME=pasted)
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertIn(b"cannot check the key", result.stderr)
        self.assertNotIn(pasted.encode(), result.stderr)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
