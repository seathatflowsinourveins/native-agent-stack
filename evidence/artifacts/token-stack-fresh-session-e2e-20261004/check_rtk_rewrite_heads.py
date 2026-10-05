#!/usr/bin/env python3
"""Check tools/adoption/rtk_rewrite_heads.json against the real rtk binary (one JSON object; exit 0 only with no gap).

    python3 check_rtk_rewrite_heads.py [OUTFILE]     # default: ~/.local/state/native-agent-stack/e2e/rtk-rewrite-heads-check.json

The fixture is derived from rtk's source (derive_rtk_rewrite_heads.py); this run asks the binary itself, with rtk's upstream defaults (a scratch
HOME with no config), `rtk hook check --agent codex` for:
  1. a positive control per RULES pattern: commands built from the pattern's own structure (every alternative of the parsed regex); at least one
     must be rewritten, and every rewritten one must start with a head;
  2. a scan: every command name this host knows (`compgen -c`, plus a few hundred common tool names) with nine argument shapes; any rewrite
     whose first word is not a head is a gap in the fixture (this can falsify the fixture, it cannot prove it);
  3. wrappers: sixty launcher and wrapper prefixes in front of `git status`; any rewrite must start with a head;
  4. the three counterexamples of the 705e read (`git -C .` is not rewritten but `git -C . push origin main` is; `uv`; `npx`) and the
     hcom rules' commands (rtk rewrites none).
Local integration evidence about one rtk binary on one host; the proof of the rule is the source reading in the fixture's provenance.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import derive_rtk_rewrite_heads as derive  # noqa: E402

FIXTURE = ROOT / "tools" / "adoption" / "rtk_rewrite_heads.json"
SHAPES = ("", "x", "status", "run", "test", "build", "install", "-C . push", "--version")
EXTRA_NAMES = """git gh docker kubectl helm terraform tofu pulumi cargo rustc go npm pnpm yarn npx bunx bun deno node python python3 pip pip3 uv uvx pipx poetry
pdm rye conda mamba make cmake ninja ctest gradle mvn ant sbt dotnet swift java javac kotlin ruby bundle rake rails gem php composer perl lua julia
ls cat head tail grep rg find tree diff curl wget aws gcloud az psql mysql sqlite3 redis-cli rsync scp ssh sftp tar zip unzip gzip bzip2 xz jq yq sed awk
sort uniq wc cut tr xargs tee echo printf test true false sleep date env sudo doas su time nice ionice nohup timeout stdbuf chroot unshare setsid
systemctl journalctl service ps top htop df du free uptime kill pkill ping traceroute dig nslookup netstat ss ip ifconfig iptables nft ufw
shellcheck hadolint yamllint markdownlint prettier eslint biome tsc jest vitest playwright prisma next vue nuxt vite webpack rollup esbuild
pytest mypy ruff black isort flake8 pylint tox nox sqlfluff ansible ansible-playbook vagrant packer sops age gpg openssl ssh-keygen
brew apt apt-get dpkg yum dnf pacman snap flatpak mix elixir erl rebar3 ghc cabal stack opam dune nim zig crystal deno
phpunit phpstan pest paratest ecs pint rspec rubocop golangci-lint golangci gradlew mvnw mvnd liquibase gt trunk pre-commit quarto shopify fail2ban-client
hcom codex claude rtk qmd serena mcporter ai-memory context-mode semble headroom""".split()
WRAPPERS = ("sudo", "doas", "xargs", "watch", "ssh host", "env", "env -i", "FOO=1", "FOO=1 BAR=2", "time", "time -p", "nice", "nice -n 5", "ionice",
            "ionice -c3", "nohup", "timeout 5", "timeout -s KILL 5", "stdbuf -oL", "chroot /x", "setsid", "unbuffer", "script -q", "strace", "ltrace",
            "gdb --args", "valgrind", "parallel", "bash -c", "sh -c", "zsh -c", "python -m", "python3 -m", "node -e", "npx", "pnpm exec", "pnpm dlx",
            "yarn", "uvx", "uv run", "pipx run", "poetry run", "pdm run", "rye run", "conda run", "direnv exec .", "dotenv run", "asdf exec", "mise exec --",
            "nix-shell --run", "command", "builtin", "exec", "noglob", "nocorrect", "eval", "bundle exec", "docker exec c", "kubectl exec p --", "hcom run",
            "uvx hcom")
COUNTEREXAMPLES = ("git -C .", "git -C . push origin main", "git -C /tmp status", "uv", "uv run harmless.py", "npx", "npx prisma migrate deploy",
                   "python3 -m pytest -q", "cat f", "yadm status", "uv pip install x")


def heads() -> list[re.Pattern]:
    return [re.compile(entry["head"] if entry["regex"] else re.escape(entry["head"])) for entry in json.loads(FIXTURE.read_text(encoding="utf-8"))["heads"]]


def first_word(command: str) -> str:
    words = shlex.split(command) if command.strip() else [""]
    return words[0].rsplit("/", 1)[-1]


def is_head(command: str, compiled: list[re.Pattern]) -> bool:
    word = first_word(command)
    return any(pattern.fullmatch(word) for pattern in compiled)


def concrete(atoms) -> str:
    text = ""
    for kind, value in atoms:
        if kind == "ws":
            text += " "
        elif kind == "char":
            if re.fullmatch(r"(?:\\.|[A-Za-z0-9_/])+", value):
                text += re.sub(r"\\(.)", r"\1", value)
            elif value.endswith(("*", "}")):
                continue
            elif value.endswith("+"):
                text += "x"
            elif re.fullmatch(r"\[[A-Za-z0-9.]+\]", value):
                text += value[1]
            elif value.startswith("[") or value in (r"\S", ".", r"\w", r"\d"):
                text += "x"
    return text.strip() + (" x" if text.endswith(" ") else "")


def main() -> int:
    target = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / ".local/state/native-agent-stack/e2e/rtk-rewrite-heads-check.json"
    compiled = heads()
    with tempfile.TemporaryDirectory(prefix="heads-check-") as scratch:
        settings = {**os.environ, "HOME": scratch, "XDG_CONFIG_HOME": str(Path(scratch) / ".config"), "RTK_TELEMETRY_DISABLED": "1"}

        def rewrite(command: str) -> str | None:
            done = subprocess.run(["rtk", "hook", "check", "--agent", "codex", command], env=settings, capture_output=True, text=True,
                                  timeout=30, check=False, stdin=subprocess.DEVNULL)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout.strip()
            if done.returncode == 1 and done.stderr.lstrip().startswith("No rewrite for"):
                return None
            raise RuntimeError(f"unexpected rtk answer for {command!r}: {done.returncode} {done.stderr[:80]}")

        def many(commands: list[str]) -> dict[str, str | None]:
            with ThreadPoolExecutor(max_workers=24) as pool:
                return dict(zip(commands, pool.map(rewrite, commands)))

        version = subprocess.run(["rtk", "--version"], env=settings, capture_output=True, text=True, check=False).stdout.strip()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        # 1. a positive control per RULES pattern
        controls = []
        rules_rs = derive.show(Path.home() / ".cache/native-agent-stack-upstream/rtk", fixture["source"]["tag"], "src/discover/rules.rs") \
            if (Path.home() / ".cache/native-agent-stack-upstream/rtk").is_dir() else None
        patterns = derive.rule_patterns(rules_rs) if rules_rs else []
        for number, pattern in patterns:
            candidates = []
            for atoms in derive.linearize(list(derive.sre_parse.parse(pattern))):
                command = concrete(atoms)
                if command and command not in candidates:
                    candidates.append(command)
            answers = many(candidates[:40])
            hits = [command for command, rewritten in answers.items() if rewritten]
            controls.append({"line": f"src/discover/rules.rs:L{number}", "tried": len(answers), "rewritten": len(hits), "example": hits[0] if hits else None,
                             "rewritten_without_head": [command for command in hits if not is_head(command, compiled)]})
        # 2. the scan
        names = set(EXTRA_NAMES)
        listing = subprocess.run(["bash", "-c", "compgen -c"], capture_output=True, text=True, check=False).stdout.split()
        names |= {name for name in listing if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,39}", name)}
        commands = [f"{name} {shape}".strip() for name in sorted(names) for shape in SHAPES]
        answers = many(commands)
        rewritten = {command: result for command, result in answers.items() if result}
        gaps = sorted(command for command in rewritten if not is_head(command, compiled))
        # 3. wrappers
        wrapper_answers = many([f"{wrapper} git status" for wrapper in WRAPPERS])
        wrapper_rewrites = {command: result for command, result in wrapper_answers.items() if result}
        wrapper_gaps = sorted(command for command in wrapper_rewrites if not is_head(command, compiled))
        # 4. counterexamples and the hcom rules' commands
        counter = {command: rewrite(command) for command in COUNTEREXAMPLES}
        hcom_commands = ["hcom term inject luna hi", "hcom relay connect", "hcom config", "hcom hooks", "hcom run onidle", "hcom kill luna", "hcom stop",
                         "hcom reset all", "hcom update", "hcom claude-pty", "hcom --name bigboss send @luna -- hi", "hcom --go send @luna -- hi",
                         "hcom send -b @luna -- hi", "hcom send --from bigboss @luna -- hi", "uvx hcom kill luna", "uvx hcom config", "uvx hcom send -b @luna -- hi"]
        hcom_answers = many(hcom_commands)
    record = {"schema": "rtk-rewrite-heads-check/1", "evidence_class": "local_integration: one run, one host, rtk upstream defaults in a scratch HOME",
              "rtk": version, "fixture_rtk": fixture["rtk_version_output"], "heads": len(fixture["heads"]),
              "positive_controls": {"patterns": len(controls), "without_a_rewrite": [c["line"] for c in controls if not c["rewritten"]],
                                    "rewritten_without_a_head": [c for c in controls if c["rewritten_without_head"]], "rows": controls},
              "scan": {"names": len(names), "shapes": list(SHAPES), "commands": len(commands), "rewritten": len(rewritten),
                       "first_words_rewritten": sorted({first_word(command) for command in rewritten}), "gaps": gaps},
              "wrappers": {"prefixes": len(WRAPPERS), "rewritten": sorted(command for command in wrapper_rewrites),
                           "not_rewritten": sorted(command for command in wrapper_answers if command not in wrapper_rewrites), "gaps": wrapper_gaps},
              "counterexamples": counter, "hcom_commands_rewritten": [command for command, result in hcom_answers.items() if result], "ok": None}
    record["ok"] = (version == fixture["rtk_version_output"] and not gaps and not wrapper_gaps and not record["positive_controls"]["without_a_rewrite"]
                    and not record["positive_controls"]["rewritten_without_a_head"] and not record["hcom_commands_rewritten"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target}: {len(controls)} patterns, {len(commands)} scanned commands ({len(rewritten)} rewritten), gaps {len(gaps)} + {len(wrapper_gaps)}, ok {record['ok']}")
    return 0 if record["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
