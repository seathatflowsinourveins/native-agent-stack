# Fix-wave frozen-input preservation (2026-10-04)

The original WSL image convergence experiment froze the recipe and its repository integration test before the current fix-wave changed F9 and its inventory assertions. These files are exact bytes from PR #684's head before integration, verified against the experiment's already-recorded SHA-256 values. Only the frozen-input paths are relocated; the existing hashes, attempts, failures, qualification and observations are unchanged. No distribution command or new acceptance ran. The current recipe/test remain at their canonical paths and are checked separately by the integration.

Source: PR #684's head, `adoption/platforms/linux-wsl2-new-distro.md` and `tests/test_wsl_new_distro_recipe.py`. Contract: `docs/acceptance-evidence-policy.md`; native verification: `scripts/validate_convergence.py`.
