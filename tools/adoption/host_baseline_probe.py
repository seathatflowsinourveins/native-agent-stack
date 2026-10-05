#!/usr/bin/env python3
SOURCE = r'''
"""PR-0 observation without explicit host changes; Python 3.11+, stdlib only.

Native client startup may attempt incidental writes. The local reference runs
inside the read-only client sandbox; see the receipt's execution limitations.

The source envelope reports an unverified canonical-source digest. It cannot
attest the bytes Python consumed on stdin; the coordinator hashes those bytes.
Sources and coordinator recording commands: tools/adoption/host-baseline.md.
"""

import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import stat
import subprocess
import sys
import tomllib


TIMEOUT_S = 20
DATE_COMMAND = ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"]
BASH = ["/bin/bash", "--noprofile", "--norc", "-p", "-c"]
LAUNCHERS = (
    "systemd-run", "ionice", "/usr/bin/time", "watch", "script", "flock",
    "chrt", "taskset", "unshare", "nsenter", "runuser",
)
VERSION_COMMANDS = ("env", "timeout", "readlink", "find", "xargs", "claude", "codex", "gdb") + LAUNCHERS
HOME_PREFIX = "/" + "home" + "/"
# Standalone copies of scripts/validate.py's personal/Windows home-path patterns.
PRIVATE_PROFILE_PATHS = (
    re.compile(r"/(?:home|Users)/(?!example(?:/|\b))[A-Za-z0-9_.-]+(?:/|\b)"),
    re.compile(r"(?:[A-Za-z]:[/\\]+|/mnt/[A-Za-z]/)Users[/\\]+(?!example(?:[/\\]|\b))[A-Za-z0-9_.-]+", re.I),
)
LANDLOCK_CODE = (
    "import ctypes, json, sys; "
    "libc = ctypes.CDLL(None, use_errno=True); libc.syscall.restype = ctypes.c_long; "
    "abi = libc.syscall(ctypes.c_long(444), ctypes.c_void_p(0), ctypes.c_size_t(0), ctypes.c_uint(1)); "
    "print(json.dumps({'abi': abi if abi >= 0 else None, 'errno': ctypes.get_errno() if abi < 0 else 0})); "
    "sys.exit(0 if abi >= 0 else 1)"
)


class PrivacyFailure(Exception):
    pass


def execute(argv, *, exit_only=False):
    # Never execute sudo or sudo-rs, including for a version.
    if Path(argv[0]).name in {"sudo", "sudo-rs"}:
        raise PrivacyFailure()
    try:
        result = subprocess.run(
            argv, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL if exit_only else subprocess.PIPE,
            stderr=subprocess.DEVNULL if exit_only else subprocess.PIPE,
            encoding="utf-8", errors="replace", timeout=TIMEOUT_S, check=False,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired as error:
        def decoded(value):
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
        return 124, "" if exit_only else decoded(error.stdout), "" if exit_only else "timed out after 20 s"
    except OSError as error:
        code = 127 if error.errno == errno.ENOENT else 126
        return code, "", "" if exit_only else f"absent (errno={error.errno})" if code == 127 else f"unavailable (errno={error.errno})"


def combined(stdout, stderr):
    return "\n".join(part.rstrip("\n") for part in (stdout, stderr) if part)


def observation(command, code, output):
    date_exit, date_out, date_err = execute(DATE_COMMAND)
    return {
        "command": command, "exit": code, "output": output,
        "date_utc": {
            "command": shlex.join(DATE_COMMAND), "exit": date_exit,
            "output": combined(date_out, date_err),
        },
    }


def command_observation(argv, *, first_line=False, exit_only=False, stdout_only=False):
    code, out, err = execute(argv, exit_only=exit_only)
    if first_line:
        out = out.splitlines()[0] if out.splitlines() else ""
        err = err.splitlines()[0] if err.splitlines() else ""
    record = observation(shlex.join(argv), code, out if stdout_only else combined(out, err))
    if stdout_only and err:
        record["stderr"] = err
    return record


def package_observation(package):
    argv = ["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\t${db:Status-Status}\n", package]
    code, out, err = execute(argv)
    if code == 1 and not out:
        out = "absent"
    return observation(shlex.join(argv), code, combined(out, err))


def path_observation(name):
    code, out, err = execute(BASH + ["command -v " + shlex.quote(name)])
    return observation("command -v " + shlex.quote(name), code, combined(out or "absent", err))


def binary_observation(name):
    # Only names in this fixed tuple may be executed with --version.
    if name not in VERSION_COMMANDS:
        raise PrivacyFailure()
    return {
        "path": path_observation(name),
        "version": command_observation([name, "--version"], first_line=True, stdout_only=name == "codex"),
    }


def marker_observation():
    argv = ["stat", "-c", "%a %U %s", "/etc/sudoers.d/90-wsl-default-user"]
    code, out, err = execute(argv)
    # Discard the owner column before it can enter the observation.
    if code == 0:
        parts = out.split()
        if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
            output = {"exists": True, "mode": parts[0], "size_bytes": int(parts[2])}
        else:
            output = "unrecognized stat output; owner discarded"
    else:
        output = combined("metadata unavailable", err)
    return observation(shlex.join(argv), code, output)


def passwd_shell_observation():
    command = 'getent passwd "$(id -un)"'
    code, out, err = execute(BASH + [command])
    if code == 0:
        entries = out.splitlines()
        parts = entries[0].split(":") if len(entries) == 1 else []
        out = parts[6] if len(parts) == 7 else "unrecognized passwd record; identity discarded"
    else:
        out = ""
    return observation(command + " (field 7 only)", code, combined(out, err))


def config_observation(path, kind):
    command = f"python3 {'tomllib.load' if kind == 'codex' else 'json.load'} {kind} settings (selected key names and booleans only)"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return observation(command, 2, "refused non-regular settings file")
            document = tomllib.load(handle) if kind == "codex" else json.load(handle)
    except OSError as error:
        return observation(command, 1, f"settings unavailable (errno={error.errno})")
    except (ValueError, UnicodeError):
        # Parser exception text may contain a configuration value.
        return observation(command, 2, "settings parse failed; diagnostic values omitted")
    if not isinstance(document, dict):
        return observation(command, 2, "settings root is not an object")
    if kind == "claude":
        env = document.get("env", {})
        if not isinstance(env, dict):
            return observation(command, 2, "env is not an object")
        output = {"CLAUDE_CODE_SHELL": "CLAUDE_CODE_SHELL" in env}
    else:
        policy, features = document.get("shell_environment_policy", {}), document.get("features", {})
        if not isinstance(policy, dict) or not isinstance(features, dict):
            return observation(command, 2, "settings table is not an object")
        def boolean_key(table, key):
            value = table.get(key)
            output = {"present": key in table, "is_boolean": isinstance(value, bool)}
            if isinstance(value, bool):
                output["enabled"] = value
            return output
        output = {
            "shell_environment_policy.inherit": {
                "present": "inherit" in policy, "is_none": policy.get("inherit") == "none",
            },
            "features.shell_snapshot": boolean_key(features, "shell_snapshot"),
            "allow_login_shell": boolean_key(document, "allow_login_shell"),
        }
    return observation(command, 0, output)


def canonical_source_bytes():
    prefix = "#!/usr/bin/env python3\nSOURCE = r" + "'" * 3
    suffix = "'" * 3 + '\nexec(compile(SOURCE, "<host-baseline-probe>", "exec"))\n'
    return (prefix + SOURCE + suffix).encode("utf-8")


def normalize_home(value, home):
    if isinstance(value, str):
        home_text = str(home)
        return "~" + value[len(home_text):] if home_text != "/" and (value == home_text or value.startswith(home_text + "/")) else value
    if isinstance(value, dict):
        return {normalize_home(key, home): normalize_home(item, home) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_home(item, home) for item in value]
    return value


def assert_private_output_absent(document, login):
    # Static schema keys and command descriptions do not disclose an identity.
    # Home paths are forbidden everywhere, including in keys and descriptions.
    text = json.dumps(document, ensure_ascii=False)
    clean = HOME_PREFIX.casefold() not in text.casefold() and not any(pattern.search(text) for pattern in PRIVATE_PROFILE_PATHS)
    if not clean:  # Remains effective under python3 -O.
        raise PrivacyFailure()
    account = re.escape(login.casefold())
    token = re.compile(r"(?<![a-z0-9])" + account + r"(?![a-z0-9])")
    numeric_suffix = re.compile(r"(?<![a-z0-9])" + account + r"[0-9]+(?![a-z0-9])")
    user_option = re.compile(r"(?<![a-z0-9])-(?:[a-z]*u|g)" + account + r"(?![a-z0-9])")
    identity = re.compile(
        r"(?<![a-z0-9])(?:(?:user=|logname=|--user=|-u\s+|~)" + account + r"(?![a-z0-9])"
        r"|" + account + r"(?:@|:x:)|uid=[0-9]+\(" + account + r"\))"
    )
    release = document.get("os_release", {}).get("output", {})
    vendor_id = release.get("ID") if isinstance(release, dict) else None
    marker_path = re.compile(r"(?<![\w./\\-])/etc/sudoers\.d/90-wsl-default-user(?![\w./\\-])")

    def check_output(value, command=""):
        if isinstance(value, str):
            # Never erase account syntax while exempting a tool/vendor label.
            if value.strip().casefold() == login.casefold() or identity.search(value.casefold()) or user_option.search(value.casefold()):
                raise PrivacyFailure()
            # Only this complete, fixed marker path is a system label.
            value = marker_path.sub("", value)
            argv = shlex.split(command)
            if len(argv) == 3 and argv[:2] == ["command", "-v"]:
                # A resolved executable's declared basename is a tool identity.
                # Its parent path remains subject to the login-component check.
                if value.startswith(("/", "~/")) and "\n" not in value and value.rsplit("/", 1)[-1] == Path(argv[2]).name:
                    value = value.rsplit("/", 1)[0]
                    # The repository's exact default launcher root is a label.
                    if value == "~/.local/share/codex-ecosystem/bin":
                        value = ""
            elif len(argv) == 2 and argv[1] == "--version":
                name = Path(argv[0]).name
                names = (name, "codex-cli") if name == "codex" else (name,)
                label = r"(?:" + "|".join(map(re.escape, names)) + r")"
                if isinstance(vendor_id, str):
                    # A vendor group must immediately follow the leading label.
                    vendor_tag = r"\A((?:GNU[ \t]+)?" + label + r"[ \t]+\()" + re.escape(vendor_id) + r"(?=[ \t)])"
                    value = re.sub(vendor_tag, r"\1(", value, count=1, flags=re.I)
                # Exempt only the leading product label; keep all later text.
                prefix = r"\A(?:GNU[ \t]+)?" + label + r"(?=[ \t(]|$)(?:[ \t]+\((?:GNU[ \t]+)?" + re.escape(name) + r"\))?"
                value = re.sub(prefix, "", value, count=1, flags=re.I)
                if name == "claude":
                    value = re.sub(r"\A[0-9]+(?:\.[0-9]+)+(?:[-+][a-z0-9.-]+)?[ \t]+\(Claude[ \t]+Code\)", "", value, count=1, flags=re.I)
            elif len(argv) == 4 and argv[:2] == ["dpkg-query", "-W"] and argv[2].startswith("-f="):
                fields = value.split()
                if isinstance(vendor_id, str) and len(fields) in (2, 3) and fields[0] == argv[3] and re.fullmatch(r"[0-9][A-Za-z0-9.+:~\-]*", fields[1]):
                    # Distro suffixes inside a numeric package version are labels.
                    fields[1] = re.sub(r"(?<![a-z0-9])" + re.escape(vendor_id) + r"(?=[0-9])", "", fields[1], flags=re.I)
                    value = " ".join(fields)
            if token.search(value.casefold()) or numeric_suffix.search(value.casefold()):
                raise PrivacyFailure()
        elif isinstance(value, dict):
            for item in value.values():
                check_output(item)
        elif isinstance(value, list):
            for item in value:
                check_output(item)

    def check_records(value, path=()):
        if isinstance(value, dict):
            if "command" in value:
                output = value.get("output")
                # Selected OS identifiers are system labels, not account names.
                os_labels = path == ("os_release",) and isinstance(output, dict) and set(output) <= {"ID", "VERSION_ID"}
                if not os_labels:
                    check_output(output, value["command"])
                check_output(value.get("stderr"))
                check_records(value.get("date_utc"), path + ("date_utc",))
            else:
                for key, item in value.items():
                    check_records(item, path + (key,))
        elif isinstance(value, list):
            for item in value:
                check_records(item, path)

    check_records(document)
    assert clean


def collect(home):
    checkout = home / "code" / "native-agent-stack"
    if checkout.is_dir():
        code, out, err = execute(["git", "-C", str(checkout), "rev-parse", "HEAD"])
        head = observation("git -C ~/code/native-agent-stack rev-parse HEAD", code, combined(out, err))
    else:
        head = observation("git -C ~/code/native-agent-stack rev-parse HEAD", 1, "absent")
    try:
        release = {}
        for line in Path("/etc/os-release").read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"ID", "VERSION_ID"}:
                release[key] = value.strip('"')
        os_record = observation("read /etc/os-release (ID and VERSION_ID only)", 0, release)
    except OSError as error:
        os_record = observation("read /etc/os-release (ID and VERSION_ID only)", 1, f"unavailable (errno={error.errno})")
    return {
        "schema_version": 1,
        "probe": observation("python3 hashlib.sha256(canonical source envelope; self-reported, unverified)", 0, {
            "canonical_source_sha256": hashlib.sha256(canonical_source_bytes()).hexdigest(),
            "basis": "self_reported_canonical_source",
            "executed_input_sha256": None,
            "executed_input_verified": False,
        }),
        "host_checkout": head,
        "os_release": os_record,
        "architecture": command_observation(["uname", "-m"], first_line=True),
        "coreutils": {
            "packages": {name: package_observation(name) for name in ("rust-coreutils", "gnu-coreutils", "coreutils-from-uutils")},
            "versions": {name: command_observation([name, "--version"], first_line=True) for name in ("env", "timeout", "readlink")},
        },
        "findutils": {
            "packages": {name: package_observation(name) for name in ("findutils", "rust-findutils")},
            "commands": {name: binary_observation(name) for name in ("find", "xargs")},
        },
        "sudo": {
            "realpath": command_observation(BASH + ['readlink -f "$(command -v sudo)"']),
            "packages": {name: package_observation(name) for name in ("sudo", "sudo-rs")},
        },
        "passwordless_sudo": {
            "marker": marker_observation(),
            "status": "unknown",
            "other_source": "adoption/platforms/linux-wsl2-new-distro.md:624 (recipe criterion only; per-host acceptance not linked)",
        },
        "launchers": {name: binary_observation(name) for name in LAUNCHERS},
        "launcher_packages": {name: package_observation(name) for name in ("time", "util-linux", "procps", "systemd", "gdb")},
        "debuggers": {"gdb": binary_observation("gdb")},
        "optional_commands": {name: path_observation(name) for name in ("busybox", "toybox", "parallel", "zsh")},
        "kernel": {
            "landlock_abi": command_observation(["python3", "-c", LANDLOCK_CODE]),
            "bwrap_version": command_observation(["bwrap", "--version"], first_line=True),
            "bwrap": command_observation(["bwrap", "--unshare-user", "--unshare-pid", "--dev-bind", "/", "/", "--proc", "/proc", "true"], exit_only=True),
            "ptrace_scope": command_observation(["cat", "/proc/sys/kernel/yama/ptrace_scope"], first_line=True),
        },
        "passwd_shell": passwd_shell_observation(),
        "clients": {name: binary_observation(name) for name in ("claude", "codex")},
        "rendered_config": {
            "codex": config_observation(home / ".codex" / "config.toml", "codex"),
            "claude": config_observation(home / ".claude" / "settings.json", "claude"),
        },
    }


def main():
    try:
        home = Path.home()
        login = pwd.getpwuid(os.getuid()).pw_name
        output = normalize_home(collect(home), home)
        serialized = json.dumps(output, ensure_ascii=False, separators=(",", ":"))
        assert_private_output_absent(output, login)
        print(serialized)
    except BaseException:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''
exec(compile(SOURCE, "<host-baseline-probe>", "exec"))
