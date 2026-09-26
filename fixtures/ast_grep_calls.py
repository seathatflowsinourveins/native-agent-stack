"""Frozen ast-grep input for scripts/native_token_ci.py: two real subprocess.run
calls, the second written with a space before its argument list, and two textual
decoys that are not calls, in a comment and in a string literal."""

import subprocess


def list_fixture_directory():
    return subprocess.run(["ls"], check=True)


def show_git_version():
    return subprocess.run (["git", "--version"], check=True)


# A comment naming subprocess.run(["decoy"]) is not a call.
DECOY = 'subprocess.run(["decoy"]) inside a string is not a call either'
