# Phase 1 CLI transfer — 2026-10-06

The co-op applies these host steps after the PR checks pass. This PR changes
repository sources only. Run one installation at a time, at nice19, outside the
NativeStack2604 paper windows. Use the reviewed checkout and its existing plan;
never run the plan without `--only` for this transfer.

The complete `transfer-inventory.json` covers30missing legacy user-bin names
and42missing bin/sbin names from all69legacy-only package records. These72
filenames include inactive backups, versioned compiler aliases and a daemon;
they are not72distinct selected tools. The plan has10named install rows backed
by7native installations, and62dated exclusions. Foundation84owners/63selected
installations and default dispatch are unchanged.

| Native installation | Pin / route | CLI names |
| --- | --- | --- |
| Gitleaks | aqua:gitleaks/gitleaks8.30.1 / mise | gitleaks |
| Grype | aqua:anchore/grype0.119.0 / mise | grype |
| ntfy | aqua:binwiederhier/ntfy2.28.0 / mise | ntfy |
| Qdrant | aqua:qdrant/qdrant1.19.1 / mise | qdrant |
| Tavily CLI | tavily-cli0.1.8 / uv, Python3.13.16 | tvly |
| vLLM | vllm0.30.0 / uv, Python3.13.16 | vllm |
| pkgconf | Ubuntu resolute2.5.1-4 / apt; binary and library pinned too | pkgconf, pkg-config, x86_64-linux-gnu-pkgconf, x86_64-linux-gnu-pkg-config |

## Before apply

Keep manager metadata in a dated0700private receipt directory. These commands
inspect tool/package requests and versions, never authentication values. They
back up the selector state that native managers change; no authentication store
or active client configuration is copied. If a selected tool/package is already
present, confirm the exact pin and reuse acceptance rather than blindly replacing
it. A differing prior pin requires its own recorded restore command before apply.

~~~bash
set -euo pipefail
p1_cli_receipt="$HOME/.local/state/native-agent-stack/backups/p1-clis-$(rtk proxy date -u +%Y%m%dT%H%M%SZ)"
rtk proxy mkdir -m 0700 -p "$p1_cli_receipt"
rtk proxy mise ls --global --json > "$p1_cli_receipt/mise-before.json"
rtk proxy uv tool list > "$p1_cli_receipt/uv-before.txt"
rtk proxy apt-cache policy pkgconf pkgconf-bin libpkgconf7 > "$p1_cli_receipt/apt-before.txt"
~~~

## Apply and read back

All transfer installs require their native manager already supplied by the base
profile; a missing prerequisite exits69. Only the pkgconf canonical slot needs
installation: that same apt transaction supplies its other three alias rows.
The exact underlying native commands, sources and acceptance are in each plan row.

~~~bash
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-gitleaks
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-grype
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-ntfy
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-qdrant
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-tvly
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-vllm
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/install.sh --only transfer-cli-pkgconf
~~~

~~~bash
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-gitleaks --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-grype --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-ntfy --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-qdrant --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-tvly --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-vllm --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-pkgconf --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-pkg-config --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-x86_64-linux-gnu-pkgconf --stage post_install
rtk proxy nice -n 19 bash evidence/artifacts/new-wsl-install-plan-20261002/accept.sh --only transfer-cli-x86_64-linux-gnu-pkg-config --stage post_install
rtk proxy mise ls --global --json > "$p1_cli_receipt/mise-after.json"
rtk proxy uv tool list > "$p1_cli_receipt/uv-after.txt"
rtk proxy uv pip freeze --python "$(rtk proxy uv tool dir)/tavily-cli/bin/python" > "$p1_cli_receipt/tavily-dependencies.txt"
rtk proxy uv pip freeze --python "$(rtk proxy uv tool dir)/vllm/bin/python" > "$p1_cli_receipt/vllm-dependencies.txt"
rtk proxy dpkg-query -W -f='${binary:Package} ${Version}\n' pkgconf pkgconf-bin libpkgconf7 > "$p1_cli_receipt/apt-after.txt"
~~~

The native CLI parsing checks bind versions, require help to succeed, and require
an invalid option's nonzero exit plus its parser diagnostic. Gitleaks additionally
uses a synthetic owned-directory detector control with a generated nonsecret
value and redacted native findings. Transfer acceptance disables mise auto-install
in its subprocess so a missing tool stays failed. These checks install nothing,
start no service/model/REPL and exercise no provider or broker.

CLI availability is separate from native vulnerability detection, ntfy delivery,
Qdrant collection/query, vLLM model/GPU/task acceptance, or compile/link correctness.
Transitive UV dependencies resolve at apply time and are captured above; a top-
level version pin is not a dependency lock. New transfer self-tests remain UNRUN
in this repository-only PR; inventory reads and existing helper version/help
observations are retained separately.

## Rollback

The commands below apply only to newly introduced requests/packages recorded as
absent before apply and still matching the applied pins. If a prior request was
changed, restore that exact saved request instead; if another operator changed a
tool/version or installed a dependent consumer, stop rather than overwriting it.
The existing paired P1-GIT wrappers have their own rollback in that PR.

~~~bash
rtk proxy mise unuse --global aqua:gitleaks/gitleaks@8.30.1
rtk proxy mise unuse --global aqua:anchore/grype@0.119.0
rtk proxy mise unuse --global aqua:binwiederhier/ntfy@2.28.0
rtk proxy mise unuse --global aqua:qdrant/qdrant@1.19.1
rtk proxy uv tool uninstall tavily-cli
rtk proxy uv tool uninstall vllm
~~~

Mise removes only each literal request; native pruning preserves versions needed
by another tracked config. UV removal targets only the named tool environment.
For the newly introduced apt transaction, check versions and preview the removal
before authorizing the native remove command; use neither autoremove nor purge.

~~~bash
for p1_package in pkgconf pkgconf-bin libpkgconf7; do
  test "$(rtk proxy dpkg-query -W -f='${Version}' "$p1_package")" = 2.5.1-4
done
rtk proxy apt-get --simulate remove pkgconf pkgconf-bin libpkgconf7 > "$p1_cli_receipt/apt-removal-preview.txt"
rtk proxy python3 - "$p1_cli_receipt/apt-removal-preview.txt" <<'PY'
from pathlib import Path
import sys
allowed = {"pkgconf", "pkgconf-bin", "libpkgconf7"}
removed = {line.split()[1].split(":")[0] for line in Path(sys.argv[1]).read_text().splitlines()
           if line.startswith("Remv ")}
assert removed <= allowed, "rollback would remove another consumer"
PY
rtk proxy sudo apt-get remove -y pkgconf pkgconf-bin libpkgconf7
rtk proxy mise ls --global --json > "$p1_cli_receipt/mise-rollback.json"
rtk proxy uv tool list > "$p1_cli_receipt/uv-rollback.txt"
rtk proxy apt-cache policy pkgconf pkgconf-bin libpkgconf7 > "$p1_cli_receipt/apt-rollback.txt"
~~~

## Retained exclusions and gaps

`amtool`, `promtool` and `context-mode` already exist in owner bundles/scoped
prefixes; global aliases remain absent. `hf` replaces the old HF command name.
SocratiCode is intentionally invoked from its owned prefix. Required repository
containment wrappers remain a P1-GIT host step, not obsolete tools.

A9B excludes pdfinfo/pdftotext for this destination's MinerU/no-consumer scope.
Poppler26.09.0 migration remains open with foundation automation if a retained
consumer appears; apt26.01.0 is not accepted as that pin. A supported
conda:poppler26.09.0 mise route is a source-reviewed future lead, not applied here.
A10A excludes the two unowned legacy launch/sign-in wrappers while retaining
purpose/consumer questions for native-stack-migration-completion before R5.
NativeStack's original bins remain intact for retirement salvage; no universal
capability equivalence is claimed. Current rootless Docker uses gvisor-tap-vsock;
adding slirp4netns could change automatic selection and is not required here.

Sources: existing plan/catalog/credential/adoption profiles at
ecfa112764c664d35377dd66b8cfcb67e5a94d60;
[misev2026.10.1 use/unuse](https://github.com/jdx/mise/tree/v2026.10.1/docs/cli)
and [auto-install setting](https://github.com/jdx/mise/blob/v2026.10.1/settings.toml#L283);
[UV0.12.22 tools](https://github.com/astral-sh/uv/blob/0.12.22/docs/concepts/tools.md);
[APT native manual](https://manpages.ubuntu.com/manpages/resolute/man8/apt-get.8.html),
reviewed2026-10-06. Vendor/alias pins and sources are in every row, with
Ubuntu pkgconf2.5.1-4 file lists reviewed2026-10-06 and
[pkgconf2.5.1 CLI](https://github.com/pkgconf/pkgconf/blob/pkgconf-2.5.1/cli/main.c).
