# PR-0 read-only host recorder

This bounded foundation evidence change implements research unit A's finalized
PR-0. It serves the north-star action of qualifying the native credential guard
and agent shell before PR-1 freezes host-specific launcher reachability, so
subsequent research and historical simulation can use evidenced client settings.

## Decision and sources

Use a checkout-independent Python stdlib probe, then the existing receipt
recorder's `--cmd` interface. The full JSON artifact accompanies the schema-valid
`local_integration` host receipt; its native excerpt names and hashes that
artifact. Observation success does not mean every optional binary or kernel
feature is present. Record all field exits and failures without substituting
24.04 data for either 26.04 host.

The comparison used repository source at
`3b8f9c8a1b938358d65bf422f61592dc3b89407d`, full reads of
`scripts/host_receipts.py` and `docs/contributing-evidence.md`, the finalized unit
A record and `finalize-AB.json` in the coordinator's research directory, and
installed native versions and tagged upstream source. Exact locators and
coordinator commands are in [the recorder guide](../../tools/adoption/host-baseline.md#sources).
The `search-first` skill's scoped repository and primary-source search selected
reuse of this recorder, Python's `tomllib`/`subprocess`, and the native Linux
Landlock/bubblewrap interfaces. Stdlib-only scripts and unittest follow the
task's explicit constraint and the existing repository test workflow. No new
package or runtime is installed. Registry and external MCP recorder discovery
were not used because deployment dependencies are outside this change's fixed
contract. Scoped ai-memory retrieval was unavailable: the call returned that
MCP approval is required while the session policy never allows approval. Current
canonical source was read directly instead.

Alternatives were a shell probe, a full inventory dependency, and a new JSON
import path in the receipt CLI. Python supplies the required TOML parser and
ctypes interface on both requested Ubuntu releases. Its source envelope permits
the actual file SHA256 to survive stdin transport; tests independently compare
it in both invocation forms. A full inventory dependency adds output and
installation requirements outside the task. The receipt CLI currently supports
local command execution only; adding import support would expand this bounded
change. An upstream stdin-capable recorder that preserves the exact fields,
silent privacy failure and full sanitized artifact could overturn this choice
after the same local checks. A supported receipt import interface could replace
the documented `--cmd` usage without changing the probe.

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
changes made by this recorder. The Codex version observation retains its
read-only-filesystem PATH-alias warning alongside exit 0. The actual source
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

The inventory covers the requested coreutils/findutils implementations, privilege
launcher identity without execution, runner paths and versions, optional shell
tools, native kernel checks, passwd shell, both clients and selected rendered
user settings. Extra OS-release and architecture observations attribute the
24.04 reference without publishing a machine name. The next sweep must use
actual 26.04 probe artifacts and label privileges, TTY and namespace conditions
per host; this baseline establishes neither guard reachability nor fresh-session
effective configuration. User settings alone do not resolve profile overlays,
managed settings, project settings or environment overrides. File metadata alone
does not establish passwordless operation. No extra host was queried in this
builder task.
