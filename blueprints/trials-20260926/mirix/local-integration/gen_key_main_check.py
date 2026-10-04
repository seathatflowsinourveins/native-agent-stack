#!/usr/bin/env python3
"""Check gen_key_main.py against stub MIRIX modules (synthetic fixture; no MIRIX server, no real key).

The stub package, written into a fresh temporary directory, mimics the calls the helper makes:
its generate_api_key returns a random dummy value and records it in a side file, and its
ClientManager.create_client_api_key records each call. Cases, each expectation fixed before the run:
  fixed    exit 0; the value appears in neither output stream; the key file holds exactly
           the value and a newline with mode 0600 even under umask 000;
  exists   --key-file names an existing file: non-zero exit before any key is registered,
           the file unchanged;
  symlink  --key-file names a symlink to another file: non-zero exit, target unchanged;
  missing  no --key-file: exit 2 (usage), no key registered;
  error    upstream exception containing the dummy value: non-zero exit, neither
           output stream contains it, and the helper removes its output file.
Prints one line per observation and exits 0 only when every expectation held. Our glue.
"""

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED = HERE / "gen_key_main.py"

STUB = {
    "mirix/__init__.py": "",
    "mirix/security/__init__.py": "",
    "mirix/security/api_keys.py": (
        "import os, secrets\n"
        "def generate_api_key():\n"
        "    value = 'dummy-' + secrets.token_hex(16)\n"
        "    with open(os.environ['STUB_SIDE_DIR'] + '/generated', 'a') as side:\n"
        "        side.write(value + '\\n')\n"
        "    return value\n"
    ),
    "mirix/services/__init__.py": "",
    "mirix/services/organization_manager.py": (
        "class OrganizationManager:\n"
        "    async def get_organization_by_id(self, org_id):\n"
        "        raise LookupError(org_id)\n"
        "    async def create_organization(self, org):\n"
        "        return org\n"
    ),
    "mirix/services/client_manager.py": (
        "import os, types\n"
        "class ClientManager:\n"
        "    async def get_client_by_id(self, client_id):\n"
        "        raise LookupError(client_id)\n"
        "    async def create_client(self, client):\n"
        "        return client\n"
        "    async def create_client_api_key(self, client_id, value, name=None):\n"
        "        if os.environ.get('STUB_FAIL'):\n"
        "            raise RuntimeError(value)\n"
        "        with open(os.environ['STUB_SIDE_DIR'] + '/registered', 'a') as side:\n"
        "            side.write(client_id + '\\n')\n"
        "        return types.SimpleNamespace(id='stub-record-id', status='active')\n"
    ),
    "mirix/schemas/__init__.py": "",
    "mirix/schemas/client.py": "class Client:\n    def __init__(self, **fields):\n        self.__dict__.update(fields)\n",
    "mirix/schemas/organization.py": "class Organization:\n    def __init__(self, **fields):\n        self.__dict__.update(fields)\n",
}


def lines(path):
    return path.read_text().splitlines() if path.exists() else []


def main():
    results = []

    def expect(label, condition):
        results.append(bool(condition))
        print(f"{'PASS' if condition else 'FAIL'} {label}")

    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        source = work / "mirix-main-src"
        for name, text in STUB.items():
            (source / name).parent.mkdir(parents=True, exist_ok=True)
            (source / name).write_text(text)
        side = work / "side"
        side.mkdir()
        environment = dict(os.environ, STUB_SIDE_DIR=str(side), PYTHONDONTWRITEBYTECODE="1")

        def run(arguments, script=FIXED, umask=None):
            return subprocess.run([sys.executable, str(script), *arguments], capture_output=True, text=True,
                                  env=environment, cwd=work, timeout=60,
                                  preexec_fn=(lambda: os.umask(umask)) if umask is not None else None)

        # fixed: key goes only to the 0600 file.
        destination = work / "out" / "demo-key"
        destination.parent.mkdir()
        completed = run(["--mirix-src", str(source), "--key-file", str(destination)], umask=0)
        generated = lines(side / "generated")
        expect(f"fixed: exit {completed.returncode} == 0", completed.returncode == 0)
        expect("fixed: the generated value is in neither standard output nor standard error",
               len(generated) == 1 and generated[-1] not in completed.stdout and generated[-1] not in completed.stderr)
        mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else None
        expect(f"fixed: key file mode {oct(mode) if mode is not None else None} == 0o600 under umask 000", mode == 0o600)
        expect("fixed: key file holds exactly the generated value and a newline",
               destination.exists() and destination.read_text() == generated[-1] + "\n")
        expect("fixed: standard output names the destination",
               str(destination) in completed.stdout)
        registered_before = len(lines(side / "registered"))

        # exists: refused before any key is registered.
        before = destination.read_bytes()
        completed = run(["--mirix-src", str(source), "--key-file", str(destination)])
        expect(f"exists: exit {completed.returncode} != 0", completed.returncode != 0)
        expect("exists: failure reported without exception details", "Key creation failed" in completed.stderr)
        expect("exists: no further key generated or registered",
               len(lines(side / "generated")) == 1 and len(lines(side / "registered")) == registered_before)
        expect("exists: existing file unchanged", destination.read_bytes() == before)

        # symlink: refused, target unchanged.
        target = work / "out" / "target"
        target.write_text("unchanged\n")
        link = work / "out" / "link"
        link.symlink_to(target)
        completed = run(["--mirix-src", str(source), "--key-file", str(link)])
        expect(f"symlink: exit {completed.returncode} != 0", completed.returncode != 0)
        expect("symlink: target unchanged and link kept",
               target.read_text() == "unchanged\n" and link.is_symlink())
        expect("symlink: no further key registered", len(lines(side / "registered")) == registered_before)

        # missing: usage error.
        completed = run(["--mirix-src", str(source)])
        expect(f"missing: exit {completed.returncode} == 2", completed.returncode == 2)
        expect("missing: no further key registered", len(lines(side / "registered")) == registered_before)

        # An upstream error can include its input key in the exception message.
        environment["STUB_FAIL"] = "1"
        failed_destination = work / "out" / "failed-key"
        completed = run(["--mirix-src", str(source), "--key-file", str(failed_destination)])
        generated = lines(side / "generated")
        expect("error: non-zero exit with a value-free diagnostic",
               completed.returncode != 0 and "Key creation failed" in completed.stderr)
        expect("error: the generated value is in neither output stream",
               len(generated) == 2 and generated[-1] not in completed.stdout and generated[-1] not in completed.stderr)
        expect("error: incomplete key file removed", not failed_destination.exists())
        expect("error: no additional key registered", len(lines(side / "registered")) == registered_before)

        del environment["STUB_FAIL"]
        restricted = work / "out" / "restricted-key"
        completed = run(["--mirix-src", str(source), "--key-file", str(restricted)], umask=0o777)
        expect("restrictive umask: exit 0 and mode 0600",
               completed.returncode == 0 and restricted.exists()
               and stat.S_IMODE(restricted.stat().st_mode) == 0o600)

    print(f"{sum(results)} of {len(results)} expectations held")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
