# User-facing local time: frozen-input preservation (2026-10-05)

The WSL image convergence experiment (`blueprints/convergence-practice/wsl-new-distro-image-20261001/experiment.json`) froze four files that the local-time change edits: the cloud-init user-data template, the new-distro decision record, the first-boot checklist and the stage-1 receipt example. The change adds an explicit `[time]` `useWindowsTimezone=true` to `/etc/wsl.conf` on both creation paths. The files under `frozen-inputs/` are exact bytes from main `e8c1edec` (`git show e8c1edec:<path>`), verified against the experiment's already-recorded SHA-256 values. Only the frozen-input paths are relocated; the existing hashes, attempts, failures, qualification and observations are unchanged. No distribution command or new acceptance ran. The current files remain at their canonical paths and are checked separately by `tests/test_wsl_new_distro_recipe.py`.

| Frozen copy | Canonical path at `e8c1edec` | SHA-256 |
| --- | --- | --- |
| `frozen-inputs/cloud-init.user-data.template.txt` | `adoption/templates/wsl/cloud-init.user-data.template` | `08e6a3f6b078dfa54d78297596d54729d10528d57147b9b9eae063c37160eeb9` |
| `frozen-inputs/2026-10-01-new-wsl-distro-recipe.md.txt` | `docs/decisions/2026-10-01-new-wsl-distro-recipe.md` | `ec03a494aa4d80ac004f74710250bf1ac7cf18e0506758d97a1cf98a0cee42a3` |
| `frozen-inputs/first-boot-checklist.md.txt` | `adoption/templates/wsl/first-boot-checklist.md` | `1a06df0e6d50b07b439317a61a450e450127052589f63254e769d99166e3603b` |
| `frozen-inputs/stage1-receipt.example.json.txt` | `adoption/templates/wsl/stage1-receipt.example.json` | `7c0811c460fe8732f413b954cd7ddadb5cc41a5300f8686b5b83aefcd80a971a` |

Decision: `docs/decisions/2026-10-05-user-facing-local-time.md`. Precedent: `evidence/artifacts/new-wsl-fix-wave-20261004/README.md`. Contract: `docs/acceptance-evidence-policy.md`; native verification: `scripts/validate_convergence.py`.
