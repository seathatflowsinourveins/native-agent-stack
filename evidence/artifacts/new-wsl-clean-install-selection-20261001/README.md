# New WSL clean-install selection, 2026-10-01

The per-layer selection of repositories for the clean install of the new WSL distribution, chosen blind on upstream
repository evidence by workflow run `wf_c2377ebb-65c` (11 Claude Opus judges and 3 adversarial critics, effort max).
The decision record is `docs/decisions/2026-10-01-new-wsl-clean-install-selection.md`.

| File | What it is |
| --- | --- |
| `selection.json` | Per layer: the selection after the critics' review, each pick's upstream install command and source, the deciding comparison, and the critics' failed fact checks |
| `ownership.json` | The non-overlapping form: each tool's one owning layer, what each layer uses from another, and how each overlap was resolved |
| `packets/` | The 21 blind packets the judges read: requirement, what a deciding comparison measures, candidates as name and repository in a seeded shuffle |
| `criteria.txt`, `judge-prompt.txt`, `critic-prompt.txt` | The frozen criteria and prompts, verbatim |
| `preregistration.json` | Their sha256 and the packet hashes, recorded at 2026-10-01T17:35:24Z, 35 seconds before the run started |
| `build_packets.py` | The script that built the packets from the committed catalogs |

The full judge and critic returns (`result.json`, sha256 `a9d203589059029eb8be55a7495b4d9a18e2415441925b8fe7f71328ef80f502`: every pick, not-selected reason, exclusion with
its closed criterion, source read and fact check) are kept outside the repository with the coordinator's private
records. In that file 40-hex commit ids and PGP key fingerprints share a file with the word Sourcegraph, which the
secret scanner's `sourcegraph-access-token` rule reads as tokens; `selection.json` carries every pick, install
command, deciding comparison and failed fact check from it. Packet paths inside `result.json` were rewritten from the session's scratch directory to `packets/`. In the Hindsight
install command, upstream's container volume path (the hindsight user's home, then `.pg0`) is written with `example`
as the user name in `result.json` and `selection.json`, because the publication validator refuses any home path that
names a user; use upstream's documented path when installing. Nothing else was changed. This is source review by model judges: no candidate was installed or measured by the run.
