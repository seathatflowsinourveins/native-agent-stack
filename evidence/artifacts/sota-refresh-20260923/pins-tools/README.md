# SOTA refresh 2026-09-23 — unit pins-tools

Qualifies the newest upstream releases for five pinned tools against retained
receipts where one exists, run natively on this host under an isolated cache
prefix (`$HOME/.cache/sota-refresh-20260923/pins-tools/`; nothing was
installed onto PATH, `~/.config`, or any live service).

| component | from | to | published_at | verdict | evidence class | receipt |
|---|---|---|---|---|---|---|
| mcporter | 0.13.13 | v0.14.0 | 2026-09-22T09:54:57Z | qualified | native_proven | [mcporter.json](mcporter.json) |
| agentsview | v0.43.0 | v0.44.0 | 2026-09-21T13:56:12Z | qualified | native_proven | [agentsview.json](agentsview.json) |
| openresearch | v0.2.7 | v0.2.8 | 2026-09-22T03:20:42Z | qualified | native_proven | [openresearch.json](openresearch.json) |
| langgraph | 1.2.11 | 1.2.12 | 2026-09-21T14:43:28Z | qualified | local_integration | [langgraph.json](langgraph.json) |
| opensandbox | server v0.2.3 | release-1.1.0 | 2026-09-21T07:46:25Z | blocked | source_review | [opensandbox.json](opensandbox.json) |

## Notes

- **mcporter**: installed the npm package `mcporter@0.14.0` into an isolated
  prefix (no linux_x86_64 GitHub-release binary exists for this version; the
  project ships as an npm package plus darwin tarballs). Ran `list` against a
  **copy** of `$HOME/codex-ecosystem/config/mcporter.json` (never the
  live file); output is byte-identical to the retained 0.13.13 receipt aside
  from the version string. That config copy carries only a loopback baseUrl
  and local command paths, no stored secrets.
- **agentsview**: downloaded the linux_amd64 release tarball, verified its
  sha256 against the release's published `SHA256SUMS`, and compared
  `--version`/`--help` to the retained version-help receipt; matched.
- **openresearch**: downloaded the musl linux CLI tarball, verified its
  sha256 against the release's `.sha256` sidecar, and compared
  `--version`/`--help`/`discover --help` (offline, no key needed) to the
  retained pin; matched. Functional search subcommands
  (`discover keyword/embedding/openalex/biorxiv`, `paper`, `login`) need a
  stored alphaXiv/OpenAlex account or key this unit was not given, so they
  were not run and are recorded as not attempted, not as passing.
- **langgraph**: no retained repository receipt exercises langgraph's
  runtime behavior (only source_review shortlist mentions). Built two
  `uv`-managed venvs (system Python's `venv` module could not run
  `ensurepip` without `apt install python3.12-venv`, which was out of scope
  for an unprivileged unit-owned install; `uv venv` avoided that dependency)
  and ran an identical from-scratch StateGraph build/compile/invoke/stream
  smoke test on 1.2.11 and 1.2.12; both passed identically. Labeled
  `local_integration`, not `native_proven`, since there is no retained
  receipt to re-run for comparison.
- **opensandbox**: the upstream README states Docker is required for local
  execution (or Kubernetes for cluster execution); this host has neither
  Docker, Podman, nor a docker.sock, and provisioning a container runtime is
  host-level infrastructure outside a unit-owned cache-prefix install.
  Recorded `blocked` with the exact missing requirement; no credential or
  broker contact was needed to reach this determination.

## Isolation

All installs live under `$HOME/.cache/sota-refresh-20260923/pins-tools/`
(npm prefix, extracted release tarballs, two `uv` venvs). No binary on PATH
was replaced, no live config was edited, no systemd unit or shell profile was
touched, and no long-running process was left behind (no daemons/servers were
started for any of these five checks).
