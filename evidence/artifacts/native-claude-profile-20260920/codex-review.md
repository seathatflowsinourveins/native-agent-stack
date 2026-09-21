Two actionable findings:

- **Medium — compressed-source safeguard lost.** The [backup:9](<ECOSYSTEM_HOME>/state/foundation-practice-20260920/backups/CLAUDE.md:9) requires reading original code before editing or judging correctness because Repomix compression omits implementation details. The replacement [user instructions:7](<HOME>/.claude/CLAUDE.md:7) and [portable example:7](<STACK_CHECKOUT>/examples/claude-native/CLAUDE.md:7) preserve recovery paths but omit that requirement. Restore a short original-source verification rule.
- **Medium — scope regression check is host-bound.** [verify-native-scope.cjs:21](<ECOSYSTEM_HOME>/validation/verify-native-scope.cjs:21) hard-codes `<PROJECT>`, whereas the [launcher:11](<ECOSYSTEM_HOME>/bin/launch-linux-agent.cjs:11) derives its default from `os.homedir()`. A correct installation under another username would fail this assertion. Derive the expectation consistently; filesystem and installation dependencies also remain unmocked.

Other conclusions:

- **Launcher:** exact diff confirms only the success notice changes from stdout to stderr. Child stream inheritance and exit/signal mapping remain unchanged at [lines 28–32](<ECOSYSTEM_HOME>/bin/launch-linux-agent.cjs:28). Full stdout cleanliness remains unverified because `collect()` is outside scope and mocked in the regression.
- **Savings:** the [recipe:101](<STACK_CHECKOUT>/recipes/claude-native-profile.md:101) claims no default percentage and [line 130](<STACK_CHECKOUT>/recipes/claude-native-profile.md:130) separates native estimates from provider totals. No artifact-token measurements were supplied in the allowed files; numerical accuracy and net savings are unknown.
- **Future PC:** the recipe explicitly requires local path resolution, skill discovery setup and new-host evidence. No additional concrete defect established, but installation, CLI flags, linked source hashes and interactive behavior were not verified. Pending documents/receipts are not findings.

Checks performed: bounded line-numbered inspection of all eight allowed files and launcher backup diff. No tests, execution, network access or changes.
