"""PreToolUse secret guard: blocked and allowed Bash command strings.

Local integration class. The guard is a text heuristic; the expected
pass-through cases below record known bypasses so no reader mistakes the
hook for a security boundary.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from scripts.hooks import secret_path_guard as guard

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts/hooks/secret_path_guard.py"
HOST_HOOK = Path.home() / ".claude" / "hooks" / "secret_path_guard.py"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI", "").lower() == "true"

BLOCKED = {
    "cat ~/.config/native-agent-stack/alpaca-paper.env": "credential_store_path",
    "ls -l \"$HOME/.config/native-agent-stack\"": "credential_store_path",
    "python3 -c \"open('/home/example/.config/native-agent-stack/alpaca-paper.env').read()\"": "credential_store_path",
    "head -c 40 ~/.claude/.credentials.json": "native_store_path",
    "jq . \"${CODEX_HOME}/auth.json\"": "native_store_path",
    "grep oauth ~/.config/gh/hosts.yml": "native_store_path",
    "cat /proc/self/environ": "process_environment",
    "tr '\\0' '\\n' < /proc/1234/environ": "process_environment",
    "gh auth token": "native_token_print",
    "gh auth status --show-token": "native_token_print",
    "gh auth status -t": "native_token_print",
    # After `gh auth setup-git` a credential helper prints the same token.
    "printf 'protocol=https\\nhost=github.com\\n\\n' | git credential fill": "native_token_print",
    "git -c credential.helper= credential fill <<< 'url=https://github.com'": "native_token_print",
    "echo host=github.com | gh auth git-credential get": "native_token_print",
    "gh auth git-credential get < request.txt": "native_token_print",
    "echo host=github.com | git credential-store get": "native_token_print",
    "git credential-cache --timeout 60 get < request.txt": "native_token_print",
    "git-credential-libsecret get < request.txt": "native_token_print",
    "bash -c 'git credential fill < request.txt'": "native_token_print",
    "echo \"$OPENROUTER_API_KEY\"": "secret_variable_reference",
    "echo $MISTRAL_API_KEY": "secret_variable_reference",
    "python3 -c 'import os;print(os.environ[\"MASSIVE_API_KEY\"])'": "secret_variable_reference",
    "printf '%s' \"$TWS_USERNAME\"": "secret_variable_reference",
    "security find-generic-password -s x -w": "keychain_read",
    "echo $APCA_API_SECRET_KEY": "secret_variable_reference",
    "printf '%s' \"${DATABENTO_API_KEY}\"": "secret_variable_reference",
    "python3 -c 'import os; print(os.environ[\"APCA_API_KEY_ID\"])'": "secret_variable_reference",
    "env": "environment_dump",
    "env | sort": "environment_dump",
    "env -u HOME": "environment_dump",
    "FOO=1 printenv PATH": "environment_dump",
    "set": "environment_dump",
    "export -p": "environment_dump",
    "declare -x": "environment_dump",
    "declare -p": "environment_dump",
    "ps eww 1234": "environment_dump",
    "ps auxe": "environment_dump",
    "echo `printenv`": "environment_dump",
    "echo $(env)": "environment_dump",
    "bash -c 'printenv'": "environment_dump",
    "strace -f -e trace=read python3 runner.py": "process_trace",
    "cat \"$PAPER_ENV_FILE\"": "credential_file_read",
    "base64 < \"$SEC_CONTACT_ENV\"": "credential_file_read",
    "cp \"${ENV_FILE}\" /tmp/x": "credential_file_read",
    "cat .env": "dotenv_read",
    "cat .env.probe": "dotenv_read",
    "cp .env /tmp/backup": "dotenv_read",
    "cat .env > /tmp/copy.txt": "dotenv_read",
    "diff .env.example .env": "dotenv_read",
    "grep KEY ../other/.env.local": "dotenv_read",
    # Readers and searches on a secret variable name, a credential file or the store directory.
    "grep -n APCA_API_KEY_ID blueprints/us-equities/adaptive-paper/runner.py": "secret_name_search",
    "grep -r APCA_API_SECRET_KEY ~": "secret_name_search",
    "rg -n 'DATABENTO_API_KEY|TYPESAFE_API_KEY' /srv": "secret_name_search",
    "ag GF_SECURITY_ADMIN_PASSWORD /etc": "secret_name_search",
    "ack --hidden OPENAI_API_KEY": "secret_name_search",
    "git grep -n GH_TOKEN": "secret_name_search",
    "git -C ../other --no-pager grep HF_TOKEN": "secret_name_search",
    "find ~ -type f -exec grep -H ALPACA_SECRET_KEY {} +": "secret_name_search",
    "find ~ -name '*.env' -exec cat {} \\;": "dotenv_read",
    "find . -name .env -execdir head -n 3 {} +": "dotenv_read",
    "awk -F= '$1==\"APCA_API_SECRET_KEY\"{print $2}' paper.cfg": "secret_name_search",
    "sed -n '/TWS_PASSWORD/p' gateway.ini": "secret_name_search",
    "sed -n 1,5p alpaca-paper.env": "dotenv_read",
    "rg --hidden -g '*.env' KEY ~": "dotenv_read",
    "git log -p | grep ANTHROPIC_API_KEY": "secret_name_search",
    "ls ${XDG_CONFIG_HOME:-$HOME/.config}/native-agent-stack": "credential_store_path",
    "rg KEY \"$XDG_CONFIG_HOME/native-agent-stack/\"": "credential_store_path",
    "while read -r line; do :; done < \"$PAPER_ENV_FILE\"": "credential_file_read",
    # Shell tracing or verbose mode while sourcing a credential file prints its assignments.
    "set -x; . \"$PAPER_ENV_FILE\"": "trace_while_sourcing",
    "set -euxo pipefail; set -a; . \"$SEC_CONTACT_ENV\"; set +a": "trace_while_sourcing",
    "set -o xtrace; source \"${PAPER_ENV_FILE}\"": "trace_while_sourcing",
    "set -v; . ./alpaca-paper.env": "trace_while_sourcing",
    "bash -x -c '. \"$PAPER_ENV_FILE\"; python3 run.py'": "trace_while_sourcing",
    "sh -xc 'set -a; . \"$SEC_CONTACT_ENV\"'": "trace_while_sourcing",
    "bash -o xtrace -c 'source \"$PAPER_ENV_FILE\"'": "trace_while_sourcing",
    "SHELLOPTS=xtrace bash -c '. \"$PAPER_ENV_FILE\"'": "trace_while_sourcing",
    # Environment dumps after sourcing, including name-filtered forms.
    "set -a; . \"$PAPER_ENV_FILE\"; set +a; env": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\" && printenv APCA_API_BASE_URL": "environment_dump_after_source",
    "source \"$PAPER_ENV_FILE\"; export -p": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; declare -x": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; declare -p APCA_API_KEY_ID": "environment_dump_after_source",
    ". \"$PAPER_ENV_FILE\"; env | grep APCA": "environment_dump_after_source",
    "bash -c '. \"$PAPER_ENV_FILE\"; env'": "environment_dump_after_source",
    "( . \"$PAPER_ENV_FILE\"; python3 -c 'import os; print(dict(os.environ))' )": "environment_dump_after_source",
    "eval '. \"$PAPER_ENV_FILE\"; typeset -p'": "environment_dump_after_source",
    "bash -lc 'printenv'": "environment_dump",
    "env -u HOME env": "environment_dump",
    # /proc/<pid>/environ in any spelling.
    "grep -a -z APCA /proc/*/environ": "process_environment",
    "xargs -0 -n1 < /proc/self/task/42/environ": "process_environment",
    "cat '/proc/'\"$pid\"'/environ'": "process_environment",
    "cd /proc/1234 && tr '\\0' '\\n' < environ": "process_environment",
    "find /proc -maxdepth 2 -name environ": "process_environment",
    # Hugging Face: both token files in every spelling of their directory, `hf auth token`
    # (also inside a substitution or a pipe), HF_TOKEN_PATH as a pointer, a read or copy of
    # the whole Hugging Face home, and the legacy token variable.
    "cat ~/.cache/huggingface/token": "native_store_path",
    "head -c 8 ~/.cache/huggingface/stored_tokens": "native_store_path",
    "ls -l ~/.cache/huggingface/token": "native_store_path",
    "cat \"$HF_HOME/token\"": "native_store_path",
    "cat \"$HF_HOME\"/token": "native_store_path",
    "cat \"${HF_HOME}\"/stored_tokens": "native_store_path",
    "jq -R . ${HF_HOME:-$HOME/.cache/huggingface}/token": "native_store_path",
    "cat \"${HF_HOME:-${XDG_CACHE_HOME:-$HOME/.cache}/huggingface}/token\"": "native_store_path",
    "cat \"${XDG_CACHE_HOME:-$HOME/.cache}/huggingface/token\"": "native_store_path",
    "cp ~/.cache/huggingface/token ~/.cache/huggingface/token.bak": "native_store_path",
    "python3 -c \"print(open('/home/example/.cache/huggingface/token').read())\"": "native_store_path",
    "hf auth token": "native_token_print",
    "~/.local/bin/hf auth token": "native_token_print",
    "hf auth token | xargs curl -H 'Authorization: Bearer {}' https://huggingface.co/api/whoami-v2":
        "native_token_print",
    "curl -H \"Authorization: Bearer $(hf auth token)\" https://huggingface.co/api/whoami-v2": "native_token_print",
    "uvx hf auth token": "native_token_print",
    "huggingface-cli auth token": "native_token_print",
    "huggingface-cli token": "native_token_print",
    "cat \"$HF_TOKEN_PATH\"": "credential_file_read",
    "base64 < \"${HF_TOKEN_PATH}\"": "credential_file_read",
    "grep -r hf_ ~/.cache/huggingface": "native_store_path",
    "rg -uu . \"$HF_HOME\"": "native_store_path",
    "grep -r x \"$XDG_CACHE_HOME/huggingface/\"": "native_store_path",
    "cp -r ~/.cache/huggingface /tmp/backup": "native_store_path",
    "rsync -a ~/.cache/huggingface/ /mnt/backup/hf/": "native_store_path",
    "cat ~/.cache/huggingface/*": "native_store_path",
    "find ~/.cache/huggingface -type f -exec cat {} +": "native_store_path",
    "echo \"$HUGGING_FACE_HUB_TOKEN\"": "secret_variable_reference",
    "hf auth login --token $HF_TOKEN": "secret_variable_reference",
}

ALLOWED = [
    "python3 runner.py paper --env-file \"$PAPER_ENV_FILE\" --output out.json",
    "python3 scripts/credential_status.py --json",
    "env -u HF_TOKEN python3 run.py",
    "env -i PATH=/usr/bin python3 -V",
    "unset TYPESAFE_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY",
    "set -euo pipefail; set -a; . \"$SEC_CONTACT_ENV\"; set +a",
    "export EDGAR_IDENTITY=\"${EDGAR_IDENTITY:-$SEC_USER_AGENT}\"",
    "ps -ef | grep runner",
    "ps -o pid,command -p 123",
    "declare -a items=(a b)",
    "git status && git diff --stat",
    "cat .env.example",
    "cat docs/examples/alpaca-paper.env.example",
    "wc -c \"$PAPER_ENV_FILE\"",
    "stat -c '%a %U' \"$PAPER_ENV_FILE\"",
    "( set -a; . \"$PAPER_ENV_FILE\"; set +a; exec python3 blueprints/us-equities/alpaca-paper/paper_runner.py --once )",
    # Hugging Face: hf reads its own store, so checking the sign-in, the operator's interactive
    # login, revision-pinned downloads and checksum verification never expose the token.
    "hf auth whoami",
    "hf auth login",
    "hf auth login --force",
    "hf download nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 "
    "--local-dir /srv/models/nemotron",
    "hf cache verify nvidia/Nemotron-3-Embed-1B-BF16 --revision c0c9fea93ea424587517f2c59e20db9f1d6bf615 "
    "--local-dir /srv/models/nemotron",
    "hf cache ls",
    "hf cache ls --revisions",
    "stat -c '%a %U' \"$HF_TOKEN_PATH\"",
    "env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN python3 run.py",
]

# Negative corpus: ordinary repository and shell work that must never be blocked.
SAFE_CORPUS = [
    "ls -la",
    "pwd",
    "git status --short",
    "git log --oneline -5",
    "git diff origin/main...HEAD --stat",
    "git grep -n shell_environment_policy -- docs",
    "git -C ../other grep -n TODO",
    "git commit -m 'Tighten the secret guard'",
    "git push origin HEAD:feature",
    "gh pr view 12 --json title",
    "gh auth status",
    "gh auth setup-git",
    "git config --get credential.helper",
    "git credential-cache exit",
    "git commit -m 'Block git credential fill in the guard'",
    "grep -rn TODO docs",
    "grep -rn 'def check' scripts/hooks",
    "grep -n OTEL_LOG_TOOL_CONTENT docs/secret-storage.md",
    "grep -rn environ scripts/credential_status.py",
    "grep -c SECRET_NAMES scripts/hooks/secret_path_guard.py",
    "rg -n 'shell_environment_policy' docs adoption",
    "rg --files | wc -l",
    "ag --python parse_args tools",
    "ack -l shlex scripts",
    "sed -n '1,80p' scripts/credential_status.py",
    "sed -i 's/foo/bar/' README.md",
    "awk -F, '{print $2}' data.csv",
    "awk 'NR<=5' manifests/stack.json",
    "cat README.md | head -20",
    "head -n 40 docs/secret-storage.md",
    "tail -f logs/app.log",
    "jq '.files | length' manifests/evidence.json",
    "diff -u a.txt b.txt",
    "sort -u names.txt | uniq -c",
    "find . -name '*.py' -newer setup.cfg -print",
    "find . -name '*.py' -exec wc -l {} +",
    "find . -name '*.py' -exec grep -l shlex {} +",
    "find . -type f -name '*.md' | xargs grep -l 'secret storage'",
    "python3 -m unittest tests.test_secret_path_guard",
    "uv run -q --no-project --with pyyaml python -m unittest tests.test_credential_status",
    "python3 scripts/validate.py",
    "python3 -c 'import os; print(os.environ.get(\"HOME\"))'",
    "make -j4 test",
    "npm test",
    "set -x; make test",
    "bash -x scripts/build.sh",
    "bash -lc 'git status'",
    "sh -c 'echo hello'",
    "set -euo pipefail; python3 run.py",
    "source .venv/bin/activate && set -x && pytest -q",
    ". ~/.bashrc; env -u HF_TOKEN python3 x.py",
    "export PATH=\"$HOME/.local/bin:$PATH\"",
    "declare -a arr=(1 2 3)",
    "printf '%s\\n' \"$PATH\"",
    "echo \"$HOME\"",
    "cat /proc/cpuinfo",
    "wc -l /proc/self/status",
    "ls /proc/self/fd",
    "ps -ef | grep python",
    "docker ps --format '{{.Names}}'",
    "cp docs/examples/alpaca-paper.env.example /tmp/template.txt",
    "sed -n 1,10p docs/examples/sec-contact.env.example",
    "eval \"$(ssh-agent -s)\"",
    "timeout 30 python3 scripts/landscape.py --root .",
    "cp .env.example .env",
    "cp -n docs/examples/alpaca-paper.env.example ./local.env",
    "cat docs/examples/sec-contact.env.example > .env.local",
    "echo 'PORT=3000' | tee -a .env",
    "set -a; source .env; set +a; npm run dev",
    "ls -la .env",
    # The Hugging Face cache beside the token files stays usable.
    "ls -la ~/.cache/huggingface",
    "du -sh ~/.cache/huggingface/hub",
    "rg -n tokenizer ~/.cache/huggingface/hub/models--x/snapshots",
    "cat ~/.cache/huggingface/hub/models--x/refs/main",
    "find ~/.cache/huggingface -name '*.incomplete' -delete",
    "rsync -a /mnt/backup/hf/hub ~/.cache/huggingface/",
    "HF_HUB_OFFLINE=1 python3 serve.py",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN=1 python3 worker.py",
    "git clone https://github.com/huggingface/tokenizers",
    "hf download huggingface/token-classification-demo --local-dir demo",
    "pip download huggingface_hub",
]

# Known heuristic gaps, asserted so a change that closes one is noticed.
EXPECTED_PASS_THROUGH = [
    "python3 -c \"import runner; print(runner.credentials(__import__('os').path.expandvars('$PAPER_ENV_FILE')))\"",
    "python3 -c 'import os;print(dict(os.environ))'",
    # huggingface_hub's own loader, and an archiver on the whole Hugging Face home.
    "python3 -c 'from huggingface_hub import get_token; print(get_token())'",
    "tar czf /tmp/hf.tgz -C ~/.cache huggingface",
]


def run_hook(payload):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=30)


class SecretPathGuardTests(unittest.TestCase):
    def test_blocked_commands(self):
        for command, reason in BLOCKED.items():
            with self.subTest(command=command):
                self.assertEqual(guard.check(command), reason)

    def test_allowed_commands(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_safe_corpus_is_never_blocked(self):
        for command in SAFE_CORPUS:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_every_secret_name_is_caught_by_a_search(self):
        for name in guard.SECRET_NAMES:
            with self.subTest(name=name):
                self.assertEqual(guard.check(f"rg -n {name}"), "secret_name_search")
                self.assertIsNone(guard.check(f"rg -n MY_{name}_HINT"))

    def test_inventory_secret_names_are_all_guarded(self):
        # Contact identities (SEC_USER_AGENT) are private data that recipes pass to
        # curl by reference, and CI secrets live only in GitHub Actions; neither is
        # an agent-side authentication value, so both stay out of the hook's list.
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        names = set(inventory["must_not_be_set"])
        for entry in inventory["entries"]:
            if entry["class"] not in {"contact_identity", "ci_secret"}:
                names.update(entry.get("variables", []))
        self.assertTrue(names)
        self.assertEqual(sorted(names - set(guard.SECRET_NAMES)), [])
        self.assertEqual(len(guard.SECRET_NAMES), len(set(guard.SECRET_NAMES)))

    def test_inventory_pointer_variables_are_guarded(self):
        # A pointer variable (PAPER_ENV_FILE, or huggingface_hub's own HF_TOKEN_PATH) names a
        # credential file, so a reader on it is blocked for every inventory entry.
        inventory = json.loads((ROOT / "adoption/credential-inventory.json").read_text())
        pointers = {name for entry in inventory["entries"] for name in entry["pointer_variables"]}
        self.assertIn("HF_TOKEN_PATH", pointers)
        for name in sorted(pointers):
            with self.subTest(name=name):
                self.assertEqual(guard.check(f"cat \"${name}\""), "credential_file_read")
                self.assertEqual(guard.check(f"cat \"${{{name}}}\""), "credential_file_read")

    def test_known_bypasses_are_recorded_not_claimed(self):
        for command in EXPECTED_PASS_THROUGH:
            with self.subTest(command=command):
                self.assertIsNone(guard.check(command))

    def test_hook_protocol_exit_codes_and_no_echo(self):
        command = "cat ~/.config/native-agent-stack/alpaca-paper.env # SENTINEL-4f1d"
        blocked = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("credential_store_path", blocked.stderr)
        self.assertNotIn("SENTINEL-4f1d", blocked.stderr + blocked.stdout)
        self.assertEqual(blocked.stderr.count("\n"), 1)
        allowed = run_hook({"tool_name": "Bash", "tool_input": {"command": "git status"}})
        self.assertEqual((allowed.returncode, allowed.stdout, allowed.stderr), (0, "", ""))
        other_tool = run_hook({"tool_name": "Read", "tool_input": {"file_path": "x"}})
        self.assertEqual(other_tool.returncode, 0)
        malformed = subprocess.run([sys.executable, str(HOOK)], input="not json",
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(malformed.returncode, 1)

    def test_project_settings_register_hook_and_deny_rules(self):
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertNotIn("allow", settings["permissions"])
        deny = settings["permissions"]["deny"]
        for rule in ("Read(~/.config/native-agent-stack/**)", "Edit(~/.config/native-agent-stack/**)",
                     "Read(~/.claude/.credentials.json)", "Read(~/.codex/auth.json)",
                     "Read(~/.config/gh/hosts.yml)", "Read(//proc/*/environ)",
                     "Read(~/.cache/huggingface/token)", "Read(~/.cache/huggingface/stored_tokens)",
                     "Bash(printenv *)", "Bash(env)", "Bash(gh auth token *)",
                     "Bash(hf auth token)", "Bash(hf auth token *)",
                     "Bash(git credential fill*)", "Bash(gh auth git-credential *)"):
            self.assertIn(rule, deny)
        self.assertLess(deny.index("Read(.env.*)"), deny.index("Read(!.env.example)"))
        hooks = settings["hooks"]["PreToolUse"]
        self.assertEqual(hooks[0]["matcher"], "Bash")
        self.assertIn("scripts/hooks/secret_path_guard.py", hooks[0]["hooks"][0]["command"])
        self.assertNotIn("/home/", json.dumps(settings))


    def test_host_profile_copy_is_verbatim(self):
        if IN_CI:
            self.skipTest("running in CI: a runner has no host install of the guard to compare")
        if not HOST_HOOK.is_file():
            self.skipTest(f"no host guard at {HOST_HOOK}; "
                          "tools/adoption/install_claude_profile.py --only guard installs it")
        self.assertEqual(HOOK.read_bytes(), HOST_HOOK.read_bytes(),
                         "the installed user-scope guard must be a verbatim copy of scripts/hooks/secret_path_guard.py")


if __name__ == "__main__":
    unittest.main()
