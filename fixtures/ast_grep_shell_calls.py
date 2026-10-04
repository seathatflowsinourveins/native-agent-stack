"""Frozen ast-grep input: subprocess.run calls that pass shell=True, one of them spread over
several lines, beside calls and text that a line-based search confuses with them."""

import subprocess


def list_directory():
    return subprocess.run("ls", shell=True, check=True)


def show_status():
    return subprocess.run(
        ["git", "status"],
        check=True,
        shell=True,
    )


def safe_listing():
    return subprocess.run(["ls"], shell=False)


def quiet_listing():
    return subprocess.run(["ls"], check=True)  # never shell=True here


def other_runner(runner):
    return runner.run("ls", shell=True)


MESSAGE = "subprocess.run(command, shell=True) inside a string is not a call"
