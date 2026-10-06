# Phase 1 Git hook acceptance

The co-op applies these host commands after this PR's own checks pass. The lane
qualified an isolated installation and scratch clone; it did not change host
mise configuration, the shared checkout or its hooksPath. The central installer
writer receives `evidence/artifacts/p1-git-hook-20261006/git-scanner-prerequisite.json`
for the existing Git row. The adjacent mise.toml is native acceptance input.

Keep Gitleaks 8.30.1 and the unchanged tracked hook command. Betterleaks 1.9.0's
default config is different, so it does not satisfy the approved equivalence
condition. Preserve the existing guarded launcher and its sibling runner.
Sources: the [decision](../docs/decisions/2026-10-06-git-hook-scanner-pin.md),
`native-agent-stack@ecfa11276:adoption/tools/README.md:135`, and
`scripts/git-hooks/pre-commit:7`.

## Host apply

Use the reviewed checkout. Before changing anything, keep a checkpoint of the
specific hooksPath value and the three public tool paths; no credential files
or complete client/Git configuration files belong in the checkpoint.
The local Git setting covers every linked worktree sharing the checkout's
Git configuration. Verify the guarded scanner before activating it.

```sh
set -eu
repo="$HOME/code/native-agent-stack"
eco="${ECO_INSTALL_ROOT:-$HOME/.local/share/codex-ecosystem}"
checkpoint="${XDG_STATE_HOME:-$HOME/.local/state}/native-agent-stack/p1-git-hook-checkpoint"
test ! -e "$checkpoint"
mkdir -p "$checkpoint"
mkdir -p "$checkpoint/tmp"
export TMPDIR="$checkpoint/tmp"
if git -C "$repo" config --local --get core.hooksPath > "$checkpoint/hooks-path"; then
  touch "$checkpoint/hooks-path-present"
fi
for item in bin/gitleaks bin/ecosystem-bounded-run tools/gitleaks-8.30.1/gitleaks; do
  if test -e "$eco/$item" || test -L "$eco/$item"; then
    mkdir -p "$checkpoint/$(dirname "$item")"
    cp -a "$eco/$item" "$checkpoint/$item"
  fi
done
if mise where aqua:gitleaks/gitleaks@8.30.1 >/dev/null 2>&1; then
  touch "$checkpoint/scanner-was-present"
fi

nice -n 19 mise install --jobs=1 aqua:gitleaks/gitleaks@8.30.1
native_dir="$(mise where aqua:gitleaks/gitleaks@8.30.1)"
install -D -m 0755 "$repo/adoption/tools/gitleaks-guarded" "$eco/bin/gitleaks"
install -D -m 0755 "$repo/adoption/tools/ecosystem-bounded-run" "$eco/bin/ecosystem-bounded-run"
mkdir -p "$eco/tools/gitleaks-8.30.1"
install -m 0755 "$native_dir/gitleaks" "$eco/tools/gitleaks-8.30.1/gitleaks"
test "$(sha256sum "$eco/tools/gitleaks-8.30.1/gitleaks" | cut -d ' ' -f 1)" = 88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509
test "$(command -v gitleaks)" = "$eco/bin/gitleaks"
test "$(gitleaks version)" = 8.30.1
command -v zizmor
git -C "$repo" config --local core.hooksPath scripts/git-hooks
```

The checkpoint directory must be new for this application. The existing harness
PATH must resolve `gitleaks` to the guarded path; the read-back below checks that
before committing. Each calling client must inherit that PATH. Enabling this
hooksPath also enables the existing pre-push gate, whose Zizmor and external
TMPDIR prerequisites are documented in `scripts/git-hooks/pre-push:49,83`.
No new profile or client configuration is part of this recipe.
The copied native binary survives pruning of the mise install; supported
`mise prune` removes unused command-line-only versions
(`jdx/mise@050ce5a20287a0aafd872b1191699a5fdafff5ac:docs/cli/prune.md:14-17`).
The vendor-archive recipe in [secret storage](../docs/secret-storage.md)
and `adoption/tools/README.md:135-140` uses the same guard and native binary.
Here `bin/gitleaks` is a copy of that guard rather than a link to
`bin/gitleaks-guarded`; its sibling runner and native target are identical.

## Read-back and scratch-clone check

These are local integration checks. They do not establish unchanged upstream
test acceptance, complete secret coverage or hosted CI acceptance.

```sh
test "$(git -C "$repo" config --local --get core.hooksPath)" = scripts/git-hooks
test "$(command -v gitleaks)" = "$eco/bin/gitleaks"
test "$(gitleaks version)" = 8.30.1
test "$(sha256sum "$eco/tools/gitleaks-8.30.1/gitleaks" | cut -d ' ' -f 1)" = 88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509
command -v zizmor
scratch="$(mktemp -d "$HOME/.cache/ns2604-github-ci-finalize/p1-git-clone.XXXXXX")"
nice -n 19 git clone --no-hardlinks --local "$repo" "$scratch/repo"
git -C "$scratch/repo" config --local core.hooksPath scripts/git-hooks
test "$(git -C "$scratch/repo" config --local --get core.hooksPath)" = scripts/git-hooks
printf '%s\n' 'P1 clean hook check' > "$scratch/repo/p1-clean.txt"
git -C "$scratch/repo" add p1-clean.txt
nice -n 19 git -C "$scratch/repo" -c user.name=P1-GIT -c user.email=p1-git@example.invalid commit -m 'test: clean hook check'
before="$(git -C "$scratch/repo" rev-parse HEAD)"
(
  cd "$repo"
  python3 -c 'from pathlib import Path; import sys; from tests.test_pre_commit_gate import synthetic_key; Path(sys.argv[1]).write_text("aws_access_key_id = " + synthetic_key() + "\n")' "$scratch/repo/p1-fake.ini"
)
git -C "$scratch/repo" add p1-fake.ini
if nice -n 19 git -C "$scratch/repo" -c user.name=P1-GIT -c user.email=p1-git@example.invalid commit -m 'test: reject fake secret' > "$scratch/blocked.log" 2>&1; then
  echo 'FAIL: planted fake secret was committed' >&2
  exit 1
else
  blocked_exit=$?
fi
test "$blocked_exit" -eq 1
rg -q 'leaks found: [1-9]' "$scratch/blocked.log"
test "$(git -C "$scratch/repo" rev-parse HEAD)" = "$before"
(
  cd "$repo"
  python3 -c 'from pathlib import Path; import sys; key=Path(sys.argv[1]).read_text().split(" = ",1)[1].strip(); assert key not in Path(sys.argv[2]).read_text()' "$scratch/repo/p1-fake.ini" "$scratch/blocked.log"
)
```

The value is generated by the existing synthetic-key fixture and has no account
behind it. Do not print it. Git returns 1 for any failing pre-commit hook,
including guard refusal (78) and lock contention (75); the positive native
`leaks found: N` line identifies a finding. A refusal, contention, timeout or
resource kill is unfinished acceptance. Retry a contended scan after the lock
holder finishes. Remove only this check's scratch directory after retaining sanitized
outputs. A pre-push/network operation is not part of the clone check.

## Rollback

For hooksPath, restore the checkpoint's single safe value if present, otherwise
unset that local key. For each replaced tool path, restore its prior public
file/link or remove only the newly introduced path. Uninstall the pinned mise
tool only if it was absent before this application.

```sh
if test -e "$checkpoint/hooks-path-present"; then
  git -C "$repo" config --local core.hooksPath "$(cat "$checkpoint/hooks-path")"
else
  if git -C "$repo" config --local --unset core.hooksPath; then
    :
  else
    hooks_rollback_exit=$?
    test "$hooks_rollback_exit" -eq 5
  fi
fi
for item in bin/gitleaks bin/ecosystem-bounded-run tools/gitleaks-8.30.1/gitleaks; do
  rm -f "$eco/$item"
  if test -e "$checkpoint/$item" || test -L "$checkpoint/$item"; then
    cp -a "$checkpoint/$item" "$eco/$item"
  fi
done
if ! test -e "$checkpoint/scanner-was-present"; then
  mise uninstall aqua:gitleaks/gitleaks@8.30.1
fi
```

The mise backend and isolated acceptance directories use upstream-supported
features: [mise aqua](https://mise.jdx.dev/dev-tools/backends/aqua.html),
`jdx/mise@050ce5a20287a0aafd872b1191699a5fdafff5ac:docs/directories.md:13`,
and `registry/gitleaks.toml:1`. Native Git's nonzero hook contract is in
[githooks](https://git-scm.com/docs/githooks#_pre_commit), read 2026-10-06.
Git's missing-key unset exit 5 is documented in
[git-config](https://git-scm.com/docs/git-config), read 2026-10-06; rollback
accepts only that absence condition so a partial apply can still restore tools.
