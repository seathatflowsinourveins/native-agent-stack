# PR-0 read-only host recorder

This bounded foundation evidence change implements research unit A's finalized
PR-0. It serves the north-star action of qualifying the native credential guard
and agent shell before PR-1 freezes host-specific launcher reachability, so
subsequent research and historical simulation can use evidenced client settings.

## Decision and sources

Use a checkout-independent Python stdlib probe and plain `kind: host_baseline`
receipts under `evidence/receipts/`. Each `local_integration` receipt binds the
complete observation artifact and actual source file with independent SHA256s.
It carries no component install stage or pass result. Observation success does
not mean every optional binary or kernel
feature is present. Record all field exits and failures without substituting
24.04 data for either 26.04 host.

The comparison used repository source at
`3b8f9c8a1b938358d65bf422f61592dc3b89407d`, full reads of
`scripts/host_receipts.py` and `docs/contributing-evidence.md`, the finalized unit
A record and `finalize-AB.json` in the coordinator's research directory, and
installed native versions and tagged upstream source. Exact locators and
coordinator commands are in [the recorder guide](../../tools/adoption/host-baseline.md#sources).
The `search-first` skill's scoped repository and primary-source search selected
reuse of the evidence receipt style, Python's `tomllib`/`subprocess`, and the native Linux
Landlock/bubblewrap interfaces. Stdlib-only scripts and unittest follow the
task's explicit constraint and the existing repository test workflow. No new
package or runtime is installed. Registry and external MCP recorder discovery
were not used because deployment dependencies are outside this change's fixed
contract. Scoped ai-memory retrieval was unavailable: the call returned that
MCP approval is required while the session policy never allows approval. Current
canonical source was read directly instead.

Alternatives were a shell probe and a new JSON import path in the receipt CLI.
The probe requires Python 3.11+ with stdlib `tomllib` and `ctypes`; exact Python
versions are not inferred from the Ubuntu release. Its source envelope permits
the actual file SHA256 to survive stdin transport; tests independently compare
it in both invocation forms. The receipt CLI currently supports
local command execution only; adding import support would expand this bounded
change. An upstream stdin-capable recorder that preserves the exact fields,
silent privacy failure and full sanitized artifact could overturn this choice
after the same local checks. The repair uses the coordinator-selected plain
receipt format instead of introducing a new import interface or a component
anchor. No existing component acceptance index changes.

## Historical upgrade evidence

The three coordination originals `run.log`, `versions-before.txt` and
`versions-after.txt` for wave2's coreutils-2604 operation were read in full.
The sanitized upgrade receipt preserves only version maps, start/end stamps and
the logged apt exit. The originals contain no exit codes for the before/after
queries or per-utility version commands, so none are invented. It is historical
coordination evidence from NativeStack2604, not a newly executed upgrade or a
current 26.04 baseline. Package versions go from rust-coreutils
`0.8.0-0ubuntu3` to `0.10.0-1ubuntu2~26.04.1`; gnu-coreutils and
coreutils-from-uutils remain at their recorded versions.

## Local controls and corrections

The first two targeted unittest attempts each exited 1: the static scan
incorrectly classified first the literal `sudo` in the defensive deny set, then
the package-name tuple, as invocations. The scan now checks literal argv list
heads and command-shaped strings, plus the fixed
version inventory. Verification is `python3 -m unittest
tests.test_host_baseline_probe -v`; fixture execution also flags any actual
privilege-launcher execution. This was a local test defect, not a capability
finding. The planted-home-path and uppercase-login controls returned exit 3 with
both streams empty, including under optimized Python. Shape, failure retention,
configuration-value omission and file/stdin checksum controls passed on that
first attempt.

The corrected module ran four tests and exited 0. The actual stdin probe then
ran on NativeStack and exited 0, with Ubuntu `24.04` and `x86_64` observed.
Its 56 fields retain ten exit-1 observations: the three absent 26.04 coreutils
package names, rust-findutils, sudo-rs, the absent sudoers marker, and the four
optional binaries. Every other field and all 56 date queries exited 0. Landlock
reported ABI 7; bwrap exited 0; ptrace_scope reported 1. The captured user config
has no explicit Codex inherit or allow_login_shell key and no Claude
CLAUDE_CODE_SHELL key. These are recorded gaps for later qualification, not
changes made by this recorder. The original Codex version observation included
its read-only-filesystem PATH-alias warning alongside exit 0; the repair separates
stderr from the version's first stdout line. The actual source
checkout differs from the builder checkout and is recorded separately in the
artifact.

An initial scan over all eight new or changed files exited 1 because the existing
evidence manifest contains one home-path match. A full read of that manifest at
HEAD and comparison of added lines found counts `base=1`, `current=1`,
`added=0`; login counts were all zero. All seven new files had zero login and
home-path matches. Existing unrelated manifest content is preserved.

During read-only source inspection four shell launches returned exit 101 because
the sandbox reported ENOSPC. The context tool also reported ENOSPC. Only this
task's temporary downloaded source caches were deleted; subsequent native
inspection succeeded. Web page opening was unsupported by the search provider;
the named primary sources were fetched directly and tagged GitHub source was
read with `gh api` instead.

## Completeness critic

The inventory covers the requested coreutils/findutils implementations, sudo
identity without execution, other launcher version calls, optional shell
tools, native kernel checks, passwd shell, both clients and selected rendered
user settings. Extra OS-release and architecture observations attribute the
24.04 reference without publishing a machine name. The coordinator's two actual
26.04 artifacts are now retained, bound to their unchanged archived source.
The next sweep must label privileges, TTY and namespace conditions
per host; this baseline establishes neither guard reachability nor fresh-session
effective configuration. User settings alone do not resolve profile overlays,
managed settings, project settings or environment overrides. File metadata alone
does not establish passwordless operation. No extra host was queried in this
builder task.

## Repair round r1

The accepted Opus verdict has no p1 findings. Per the coordinator's receipt
decision, the component `claude-code/install/pass` receipt and its duplicate
host directory are removed. The 24.04 plain receipt uses the existing public
NativeStack identity. Three host receipts and the historical NativeStack2604
coreutils sidecar carry `kind: host_baseline`, `local_integration`, execution
context, limitations and hashes of complete artifacts. No version is typed into
an acceptance result, and the component acceptance index remains unchanged.

The coordinator supplied the unchanged 26.04 captures made with the absolute
WSL executable and `bash -lc`: NativeStack2604 at 01:02Z after F9 apply and
StackMeasure2604 around 01:03Z. Their exact timestamps remain in each field.
The guide records why bare `wsl.exe` and direct `-- python3 -` were inadequate.
The builder reruns only the local 24.04 probe. The archived r0 source's actual
SHA256 matches both supplied artifacts; it is retained as evidence rather than
presented as the repaired probe. The r1 24.04 capture uses the changed source.

The repaired Codex version value is its first stdout line; stderr stays separate.
The 24.04 execution is inside the read-only client sandbox. Codex's startup
alias write attempt is blocked there; the original native 26.04 captures do not
prove startup had no incidental effects. The probe changes no host settings.
`main()` catches every exception, including `KeyboardInterrupt`, and exits 3
without a traceback. Regression fixtures force those failures with both streams
empty under ordinary and optimized Python, and retain a failing Codex exit
without putting stderr into its version value.
The targeted module passed all seven tests with exit 0. The local r1 stdin
collection exited 0 at 2026-10-05T01:47:45Z; its independently hashed probe
source is bound by the 24.04 receipt. Gdb path lookup exited 1 and its version
command exited 127. The dpkg query retained exit 0 with an empty gdb version;
that does not establish an installed debugger. The time package is observed as
`1.9-0.2build1`, and bwrap reports `0.9.0` on this 24.04 context.

Passwordless sudo is explicitly unknown. The generic recipe link is a criterion
and establishes no per-host acceptance. Root reachability rows remain
`status-unknown` until independently evidenced. The updated probe adds gdb,
launcher-family package versions and bwrap's version. These additional fields
were not collected in the supplied r0 captures, so the 26.04 receipts state that
gap rather than fill it with 24.04 values. StackMeasure2604's retained probe is
now the source for its current rust-coreutils version.

The repair removes the unsupported claim that no privilege launcher executes:
sudo and sudo-rs never execute, other launchers run `--version`, and bwrap runs
`true`. It also removes the uncited distribution-shipping and inventory-tool
comparison claims. The prior ENOSPC report remains historical; r1 uses
`~/.cache/t-pr0-baseline-r1`, outside both the checkout and `/tmp`, for TMPDIR.
The history-squash finding belongs to the coordinator: this builder is explicitly
forbidden to commit or push. Registration is the final file mutation in r1.

The first r1 `python3 scripts/validate.py` exited 1 because the removed component
receipt remains in the coordinator-owned Git index. Its manifest entry is gone
and the worktree file is deleted. An alternate-index rerun was proposed, then
corrected after reading `scripts/validate.py:237`: publication enumeration
deliberately strips every `GIT_` override. The supported `--root` source-archive
mode instead checks an exact export of the proposed publication files, including
untracked additions and excluding the deleted receipt. The real Git index is
unchanged; the coordinator must stage the deletion for the normal worktree
command to pass. No validator code or scope is weakened.
