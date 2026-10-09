# agnix source review and isolated native check

The source is [agent-sh/agnix v0.57.0](https://github.com/agent-sh/agnix/releases/tag/v0.57.0),
commit `2c0e4efede3181599eca37619e8067ae2d941c00`. The annotated tag object
`19997c99b11b74d42346615334d2150bee7e40d0` resolves to that commit. Its tag
signature is absent (`verification.reason=unsigned`); no signature claim is
made. The release was published on 2026-10-08 at 16:24:04Z.

## Maintained landscape and requirement

The bounded upstream survey covered agnix, NVIDIA/SkillEvaluator v0.5.0, the
OpenAI and Anthropic skill-creator reference validators, and the official
Agent Skills specification. agnix is the candidate for checking Codex
instruction and skill files together. NVIDIA covers deterministic skill
validation, provider-assisted overlap and live evaluations; those are separate
jobs. Reference validators are controls, not complete client configuration
linters or proof of superior skills. The routed sweep is a lead rather than
an adoption receipt. Its current FINAL.md hash and the experiment scope are
retained in PREREGISTRATION.md.

REST repository metadata reports agnix not archived with default branch
`main`; the latest main commit was `004b7ea143de549c13e89614fd73be0497abbdd0`
at 2026-10-09T00:24:56Z. These reads used `gh api --cache 120s`. Main's
maintenance fact is separate from the tested release pin.

The [README:17](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/README.md#L17)
describes configuration validation; its supported-tools table at
[README:124](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/README.md#L124)
includes Agent Skills and AGENTS instruction files. Exact Codex validation
source is [crates/agnix-core/src/rules/codex.rs](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/crates/agnix-core/src/rules/codex.rs).
The report schema is [json.rs:9](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/crates/agnix-cli/src/json.rs#L9).

## Quality at the pin

The exact tagged commit has successful upstream
[CI](https://github.com/agent-sh/agnix/actions/runs/37805349571),
[Security](https://github.com/agent-sh/agnix/actions/runs/37805349656),
[Code Quality](https://github.com/agent-sh/agnix/actions/runs/37805348154),
[Docs](https://github.com/agent-sh/agnix/actions/runs/37805349614), and
[Release](https://github.com/agent-sh/agnix/actions/runs/37807065828) runs.
The two mention-triggered Claude runs were skipped, not successful tests.

The upstream [CI workflow:67](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/.github/workflows/ci.yml#L67)
distinguishes workspace merge validation from the full workspace suite and
invokes its own rule-efficacy harness at
[line 80](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/.github/workflows/ci.yml#L80).
Locally, the installed release binary executed the same native harness,
`agnix eval tests/eval.yaml`, from an exact-tag checkout: **61/61 cases passed,
exit 0**. This verifies packaged-binary efficacy on vendor fixtures; the
source-built full preflight was not rerun locally. The full command and log
are retained with the trial receipt. This vendor-authored harness is not an
independent benchmark.

## Supported install and inverse

The vendor's [installation guide:60](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/website/docs/installation.md#L60)
supports downloading platform archives from GitHub Releases. The GNU Linux
x86_64 archive is 3,668,046 bytes, sha256
`c72bf5ff1f45900055c353cc1bd6bbea6389506a3ba3197db000340066c78098`.
Its GitHub release digest, vendor checksum sidecar and locally computed hash
agree. The extracted executable sha256 is
`a9f788f9a89c3f5e1563379de44b16c66494b49e1a780765d255f62654ba9ec7`.
This value was computed directly from the installed executable. A mistaken
unmeasured draft value was removed before publication; the archive digest
and native receipt agree with the measured files.

The trial extracted only that archive into the lane-owned
`research/api-surfaces-trials/agnix/bin` prefix. `agnix --version` returned
`agnix 0.57.0`. Nothing was installed into a user bin directory, and no shell
update, MCP registration, hook or client configuration was applied. The
recorded inverse removes only the extracted lane-owned executable and verifies
its absence; the archive, exact-tag checkout and evidence remain for review.
The inverse is an archive-install inverse, not a vendor package-manager
uninstall command.

## Native routing boundary

The vendor [skills/agnix/SKILL.md:1](https://github.com/agent-sh/agnix/blob/2c0e4efede3181599eca37619e8067ae2d941c00/skills/agnix/SKILL.md#L1)
ships an implicit validation trigger and the native command. Its install
fallback uses global package installation, so no installed skill was edited
to change that behavior. The host policy rejected a read-only probe of the
skills CLI add route with `Bash(npx *skills@* add *)`; no project skill was
installed through an alternative path to evade the denial. The native fresh
session received a request without the candidate's name and selected Codex's
built-in skill-creator validator. Reaching agnix remains unproved. Static
report quality, native discovery, memory and eventual host application are
separate gates.
