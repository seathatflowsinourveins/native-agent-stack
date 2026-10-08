# Keep frozen dependency evidence out of automatic relocks

Dependabot PR #842 tried to change the captured package and lock used by frozen
evidence. Those bytes have registered hashes and a separate advisory report. The
command center closed #842 and authorized this scoped configuration follow-up
in item 091807Z. It serves foundation readiness before the north-star start.

Use Dependabot's supported npm entry for only the captured directory named in
[the config](../../.github/dependabot.yml). Set `open-pull-requests-limit: 0` to
keep version updates disabled, then ignore every dependency at `versions: ['>= 0']`
to suppress security relocks in that directory. The existing Actions entry and
security update configuration for other directories retain their scope. Advisory
reporting and the command center's per-advisory disposition remain separate.

Sources checked on 2026-10-08:

- GitHub's [security configuration example](https://docs.github.com/en/code-security/dependabot/dependabot-security-updates/configuring-dependabot-security-updates#overriding-the-default-behavior-with-a-configuration-file)
  uses an npm directory, limit zero and `ignore` for security updates.
- The official [ignore reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference#ignore--)
  covers both security and version updates. Its [exclude-paths reference](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference#exclude-paths-)
  is marked "Version updates only" in the current HTML. That option alone cannot
  suppress #842. A root-wide npm ignore would also affect other directories.
- [dependabot/dependabot-core](https://github.com/dependabot/dependabot-core/tree/89a9e441cf28ea8775a1f444125fa16bf5485d47),
  pin `89a9e441cf28ea8775a1f444125fa16bf5485d47`,
  [ignore_condition.rb:40](https://github.com/dependabot/dependabot-core/blob/89a9e441cf28ea8775a1f444125fa16bf5485d47/common/lib/dependabot/config/ignore_condition.rb#L40)
  returns explicit versions for security updates and defines `ALL_VERSIONS` as
  `>= 0`; this makes the security ignore explicit.

The existing frozen-reference tripwire gains only the digest of this directory
configuration line, which creates no installation, build or server route.

Native check: installed zizmor 1.30.1 returned 0 and "No findings to report" for
`zizmor --offline --no-config --no-ignores --persona regular --strict-collection .github/dependabot.yml`
at 2026-10-08T10:29:19Z. This is an offline analyzer result; no hosted Dependabot
job was run. That version's [cooldown audit](https://github.com/zizmorcore/zizmor/blob/99a054ed9283c90abdd2d5b9fb5101d27dde9783/crates/zizmor/src/audit/dependabot_cooldown.rs#L100)
returns after the existing first entry's sufficient cooldown, so this result is
not evidence of a limit-zero exemption or exhaustive per-entry cooldown checks.

Inverse: `git revert <this follow-up's landed squash commit>` restores the previous
configuration. If the evidence registry conflicts, take main's registry and
re-register the reverted owned files through [the hot-file protocol](../lanes.md#hot-file-protocol).
The inverse is recorded, not executed.
