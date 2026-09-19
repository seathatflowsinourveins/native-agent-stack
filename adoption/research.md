# Native portability convergence review

September 19, 2026: a fresh native GitHub CLI comparison found **337 public stars, zero added and zero removed**. Two bounded review waves inspected **six portability candidates and 41 selected primary source files**, with pinned source URLs and hashes in [the research manifest](research.json). Only mise is starred in that six-candidate set; the others were reviewed beyond the stars. This is additional source review, not six new installed runtimes.

| Repository | Latest checked release | Decision |
| --- | --- | --- |
| [jdx/mise](https://github.com/jdx/mise) | `v2026.9.11` | Optional broader native tool/artifact locking |
| [astral-sh/uv](https://github.com/astral-sh/uv) | `0.12.17` | Reuse the required existing Python dependency tool |
| [devcontainers/cli](https://github.com/devcontainers/cli) | `v0.89.0` | Defer until container hosting is selected |
| [twpayne/chezmoi](https://github.com/twpayne/chezmoi) | `v2.72.2` | Optional management of selected non-secret files |
| [jetify-com/devbox](https://github.com/jetify-com/devbox) | `0.18.3` | Defer Nix environment adoption |
| [DeterminateSystems/nix-installer](https://github.com/DeterminateSystems/nix-installer) | `v3.22.5` | Defer privileged platform installation |

The required path reuses upstream uv and the application's complete hash lock. Mise can add platform-tool artifact locks and npm/PyPI CLI dependency sidecars when managing several languages becomes necessary; it does not replace application locks. Its native locked-install commands and required sidecars are recorded in the JSON, but were not run here.

Dev Containers' stable `--frozen-lockfile` covers Features, not base-image bytes or arbitrary install scripts. Devbox can bootstrap Nix and mutate lock metadata; this review found no confirmed immutable-install flag for the selected release. Determinate's plan command itself requires root. Chezmoi is an option for explicitly owned non-secret files, not a route for distributing native client credentials.

No alternative manager was installed for this review. The selected acceptance is [native uv SDK reproduction](receipt.json), with exact dependency agreement and separately reported native account readiness. Candidate release checks, licenses and checksum metadata are not installation, vulnerability, inference or hosting acceptance.

The existing grand index remains 453 identities; this supplemental six-candidate source review has its own explicit scope and does not silently change its counts. Candidate cards retain their exact source revision so future sessions can inspect deltas rather than rereading all files. Latest observed releases remain distinct from compatible adopted pins.
