"""Keep portable adoption references and accepted SDK dependency artifacts aligned."""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AdoptionContractTests(unittest.TestCase):
    def setUp(self):
        self.adoption = json.loads((ROOT / 'adoption/manifest.json').read_text())
        self.stack = json.loads((ROOT / 'manifests/stack.json').read_text())

    def _require_commit(self, commit_ish: str, label: str) -> None:
        """Skip (not fail) the calling test when `commit_ish` is not present
        as a commit object in this clone.

        Codex review of PR #83, round 3: CI's shallow clone does not carry
        every commit this test's `git cat-file -e <sha>:<path>` calls need --
        the path can genuinely exist on disk in the checked-out working tree
        while the COMMIT OBJECT itself (a different, non-checked-out sha, e.g.
        an older `source.release_commit`/`source.baseline_commit` pin) is
        simply absent from a shallow history. A missing commit object makes
        `git cat-file -e <sha>:<path>` fail regardless of whether the path
        would actually be present there, which either wrongly fails the
        positive assertions (release_commit contains adoption/) or wrongly
        PASSES the negative one (baseline_commit does NOT contain adoption/)
        for the wrong reason. Skip with an explicit message naming the
        missing object instead of asserting either way; the fetch depth is
        left alone (deepening it here would hide the real shallow-clone
        constraint rather than test around it)."""
        result = subprocess.run(
            ['git', 'cat-file', '-e', f'{commit_ish}^{{commit}}'],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if result.returncode != 0:
            self.skipTest(
                f'{label} ({commit_ish}) is not present as a commit object in this clone '
                f'(git cat-file -e {commit_ish}^{{commit}} failed: {result.stderr.strip()}); '
                'likely a shallow clone that does not carry this commit'
            )

    def test_every_component_has_a_confined_recipe(self):
        components = {item['id'] for item in self.stack['components']}
        self.assertEqual(set(self.adoption['recipe_map']), components)
        for reference in self.adoption['recipe_map'].values():
            path = (ROOT / reference).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertTrue(path.is_file(), reference)
        for profile in self.adoption['profiles']:
            self.assertTrue(set(profile['component_ids']) <= components)

    def test_continuation_references_resolve_without_copying_gate_states(self):
        # `sources.ecosystem_explorer` (docs/ecosystem/index.html) is generated
        # and gitignored, not committed (see
        # docs/decisions/2026-09-23-generated-explorer-sorted-manifest.md): a
        # clean checkout has no such file until `python3
        # scripts/build_ecosystem.py --write` runs. Every other source must
        # still resolve to a real, committed file.
        generated_not_committed = {'ecosystem_explorer'}
        for key, reference in self.adoption['sources'].items():
            if key in generated_not_committed:
                continue
            self.assertTrue((ROOT / reference).is_file(), reference)
        # Excluding the key above must not silently hide a typo'd path: pin
        # its exact expected value rather than skipping any string that
        # happens to match.
        self.assertEqual(self.adoption['sources']['ecosystem_explorer'], 'docs/ecosystem/index.html')
        gates = json.loads((ROOT / self.adoption['sources']['open_gates']).read_text())
        identifiers = {gate['id'] for gate in gates['open_gates']}
        self.assertTrue(set(self.adoption['continuation']['next_action_refs']) <= identifiers)
        for reference in self.adoption['continuation']['research_refs']:
            path = (ROOT / reference).resolve()
            self.assertTrue(path.is_relative_to(ROOT))
            self.assertTrue(path.is_file(), reference)
        self.assertNotIn('open_gates', self.adoption)
        self.assertFalse(self.adoption['policy']['historical_acceptance_transfers'])

    def test_foundation_and_trading_continuations_keep_separate_gates(self):
        sources = self.adoption['sources']
        self.assertEqual(sources['open_gates'], sources['foundation_catalog'])
        self.assertEqual(sources['current_convergence'], sources['foundation_catalog'])
        self.assertNotEqual(sources['open_gates'], sources['trading_open_gates'])
        trading = json.loads((ROOT / sources['trading_open_gates']).read_text())
        identifiers = {gate['id'] for gate in trading['open_gates']}
        references = set(self.adoption['continuation']['trading_next_action_refs'])
        self.assertTrue(references)
        self.assertTrue(references <= identifiers)
        self.assertFalse(references & set(self.adoption['continuation']['next_action_refs']))

    def test_lock_matches_accepted_inventory_and_all_pins_have_hashes(self):
        normal = lambda value: re.sub(r'[-_.]+', '-', value).lower()
        inventory = json.loads((ROOT / 'blueprints/us-equities/supply-chain/receipt.json').read_text())
        expected = {normal(item['name']): item['version'] for item in inventory['packages']}
        text = (ROOT / self.adoption['toolchain']['sdk_lock']).read_text()
        blocks = re.split(r'(?=^[A-Za-z0-9_.-]+==)', text, flags=re.M)
        pins = {}
        for block in blocks:
            match = re.match(r'([A-Za-z0-9_.-]+)==([^\s\\]+)', block)
            if match:
                self.assertRegex(block, r'--hash=sha256:[0-9a-f]{64}')
                self.assertNotIn(normal(match[1]), pins)
                pins[normal(match[1])] = match[2]
        self.assertEqual(pins, expected)
        for reference in ['sdk_direct_requirements', 'sdk_accepted_constraints']:
            records = (ROOT / self.adoption['toolchain'][reference]).read_text()
            required = dict((normal(name), version) for name, version in re.findall(
                r'^([A-Za-z0-9_.-]+)==([^\s]+)$', records, re.M))
            self.assertTrue(required)
            self.assertTrue(required.items() <= pins.items())
            if reference == 'sdk_accepted_constraints':
                self.assertEqual(required, expected)

    def test_platform_profiles_stay_linux_accepted_and_macos_drafted(self):
        profiles = {row['id']: row for row in self.adoption['platform_profiles']}
        self.assertEqual(profiles['linux-wsl2-x86_64']['status'], 'accepted')
        self.assertEqual(profiles['linux-wsl2-x86_64']['evidence_ref'], 'adoption/receipt.json')
        self.assertEqual(profiles['macos-arm64']['status'], 'drafted_not_accepted')
        self.assertIsNone(profiles['macos-arm64']['evidence_ref'])
        for row in profiles.values():
            self.assertTrue({'id', 'os', 'architecture', 'status', 'doc', 'evidence_ref'} <= set(row))
            self.assertTrue((ROOT / row['doc']).is_file(), row['doc'])
        # supported_platforms stays Linux-only; a drafted macOS profile does not
        # change what adoption_status.py reports as this host's supported platform.
        self.assertEqual(
            [(item['os'], item['architecture']) for item in self.adoption['supported_platforms']],
            [('linux', 'x86_64')],
        )

    def test_macos_arm64_foundation_profile_uses_plain_command_names(self):
        by_id = {row['id']: row for row in self.adoption['profiles']}
        profile = by_id['macos-arm64-foundation']
        components = {item['id'] for item in self.stack['components']}
        self.assertTrue(set(profile['component_ids']) <= components)
        for name in profile['required_commands']:
            self.assertRegex(name, r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')

    def test_host_example_claims_no_live_acceptance(self):
        host = json.loads((ROOT / 'adoption/host-state.example.json').read_text())
        self.assertEqual(host['selected_components'], [])
        self.assertEqual(host['local_receipts'], [])
        for client in host['clients'].values():
            self.assertEqual(set(client.values()), {'not_checked'})

    def test_bootstrap_step_zero_checks_out_the_attested_release_not_the_pre_adoption_baseline(self):
        """Codex cross-family review finding (codex-review-72): adoption/bootstrap.md
        step 0 used to check out `source.baseline_commit`
        (8f1da51757e925d319e2a50f080b02742e7e7168), a revision that predates
        `adoption/` and `tools/adoption/` entirely, so every later step on that page
        failed. Step 0 must check out `source.release_tag` (an attested release, at
        or after `source.release_commit`, which must actually contain both
        directories -- verified below with `git cat-file` on the named commit, not
        by trusting the manifest's own claim), and `baseline_commit` must remain
        exactly what it always meant (the pre-adoption comparison point
        `scripts/adoption_status.py` uses), never a checkout target."""
        source = self.adoption['source']
        self.assertIn('release_tag', source)
        self.assertIn('release_commit', source)
        self.assertEqual(source['baseline_commit'], '8f1da51757e925d319e2a50f080b02742e7e7168')

        bootstrap_text = (ROOT / 'adoption/bootstrap.md').read_text()
        step_zero_start = bootstrap_text.index('Step 0')
        step_zero = bootstrap_text[step_zero_start:step_zero_start + 1500]
        self.assertIn("['source']['release_tag']", step_zero)
        self.assertNotIn("['source']['baseline_commit']", step_zero)

        tag = subprocess.run(
            ['git', 'rev-parse', '--verify', '--quiet', f"{source['release_tag']}^{{commit}}"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if tag.returncode == 0:
            self.assertEqual(tag.stdout.strip(), source['release_commit'],
                             'source.release_tag must resolve to source.release_commit')

        self._require_commit(source['release_commit'], 'source.release_commit')
        for path in ('adoption/bootstrap.md', 'tools/adoption/render_config.py'):
            result = subprocess.run(
                ['git', 'cat-file', '-e', f"{source['release_commit']}:{path}"],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(
                result.returncode, 0,
                f"source.release_commit ({source['release_commit']}) must contain {path} "
                f"(git cat-file -e failed: {result.stderr.strip()})",
            )
        # The pre-adoption baseline_commit is the actual regression case: it must
        # NOT contain these paths, confirming step 0's fix was necessary in the
        # first place (this is checking real git history, not a synthetic fixture).
        self._require_commit(source['baseline_commit'], 'source.baseline_commit')
        for path in ('adoption', 'tools/adoption'):
            result = subprocess.run(
                ['git', 'cat-file', '-e', f"{source['baseline_commit']}:{path}"],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertNotEqual(
                result.returncode, 0,
                f"source.baseline_commit ({source['baseline_commit']}) unexpectedly contains "
                f"{path}; if this now passes, baseline_commit is no longer a reason to avoid "
                "checking it out in step 0 and this test (and the doc fix it guards) should be reviewed",
            )

    def test_require_commit_skips_when_the_commit_object_is_absent(self):
        """Codex review of PR #83, round 3: `_require_commit` must SKIP (not
        fail, not silently pass through to an assertion that could pass for
        the wrong reason) when a commit object is genuinely absent from this
        clone -- e.g. CI's shallow clone, where `source.release_commit` or
        `source.baseline_commit` can be older than the shallow fetch depth
        even though their paths exist fine in the checked-out working tree."""
        bogus_sha = '0000000000000000000000000000000000dead'
        verify = subprocess.run(
            ['git', 'cat-file', '-e', f'{bogus_sha}^{{commit}}'],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        self.assertNotEqual(
            verify.returncode, 0,
            'sanity check: this synthetic sha must not actually resolve in this repo, '
            'or this test is not exercising the missing-object path',
        )
        with self.assertRaises(unittest.SkipTest) as ctx:
            self._require_commit(bogus_sha, 'source.release_commit')
        self.assertIn(bogus_sha, str(ctx.exception))
        self.assertIn('source.release_commit', str(ctx.exception))

    def test_require_commit_does_not_skip_for_a_present_commit(self):
        """The positive path: a commit object this clone actually has (HEAD
        itself always qualifies) must not be skipped."""
        head = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=str(ROOT), capture_output=True, text=True, check=True,
        ).stdout.strip()
        self._require_commit(head, 'HEAD')  # must not raise/skip

    def test_baseline_commit_warning_cites_the_step_zero_finding_not_the_promotion_gate_one(self):
        """Codex review of PR #83, round 3: README.md's "Start here" step 0
        and adoption/platforms/linux-wsl2.md's baseline_commit warning cited
        `codex-review-64` for the step-0/baseline_commit checkout finding,
        but that finding is `codex-review-72` (see this file's own
        `test_bootstrap_step_zero_...` docstring above); `codex-review-64`
        is the separate promotion-gate cross-family review finding cited
        correctly elsewhere (blueprints/us-equities/data/README.md), which
        this test must not touch."""
        for doc in (ROOT / 'README.md', ROOT / 'adoption/platforms/linux-wsl2.md'):
            text = doc.read_text()
            start = text.index('baseline_commit')
            window = text[max(0, start - 200):start + 400]
            self.assertIn(
                'codex-review-72', window,
                f'{doc.relative_to(ROOT)}: the baseline_commit checkout warning must cite '
                'codex-review-72 (the step-0 finding), not codex-review-64 (the promotion-gate '
                f'finding); nearby text: {window!r}',
            )
        # Positive control: the promotion-gate doc's own codex-review-64
        # citations are a different finding and must be left alone.
        gate_readme = (ROOT / 'blueprints/us-equities/data/README.md').read_text()
        self.assertIn(
            'codex-review-64', gate_readme,
            'blueprints/us-equities/data/README.md must keep its codex-review-64 citations '
            '(the promotion-gate finding); this test asserts the fix stayed scoped to the '
            'baseline_commit/step-0 citation only',
        )

    def test_no_doc_entry_point_checks_out_the_pre_adoption_baseline(self):
        """Second-round Codex cross-family review finding (codex-review-72):
        the fix above only patched `adoption/bootstrap.md` step 0 and only
        inspected its first 1500 characters, so it missed three other
        checkout instructions using `source.baseline_commit` as the checkout
        target -- README.md's "Start here" step 0, its "Fresh WSL2 x86_64"
        and "Fresh macOS arm64" quick-start blocks, and
        `adoption/platforms/linux-wsl2.md` (which `adoption/bootstrap.md`
        tells readers to read "before starting"). Every one of those would
        fail identically to the original bootstrap.md bug: `baseline_commit`
        predates `adoption/` and `tools/adoption/`, so nothing after that
        checkout works. Scan every doc entry point, not just the first 1500
        characters of one file, for the literal checkout-target pattern."""
        # Codex review of PR #83, round 3: the original scan only covered
        # README.md + adoption/**/*.md and one EXACT command string (the
        # literal `python3 -c "import json;print(...)"` form). Broaden to
        # every doc surface a reader could actually follow (README.md,
        # adoption/**, recipes/**, docs/**/*.md) and to ANY line that pairs
        # a checkout-like verb (`git checkout`/`git switch`) with a
        # `baseline_commit` reference, regardless of whether the extraction
        # is written with `python3 -c`, `jq`, or something else -- while
        # still excluding a line that explicitly WARNS against doing this
        # (e.g. "Do **not** check out `source.baseline_commit`" describes
        # the hazard in prose, using "check out" not the literal
        # `git checkout`/`git switch` verb, so it is naturally excluded; a
        # future doc that quotes the broken command INSIDE a warning is
        # still excluded via the explicit negation-word check below).
        checkout_verb = re.compile(r'git\s+(?:checkout|switch)\b', re.IGNORECASE)
        negation = re.compile(
            r'\b(?:do\s+not|does\s+not|must\s+not|should\s+not|never|'
            r'not\s+a\s+checkout\s+target|is\s+never\s+a\s+checkout\s+target)\b',
            re.IGNORECASE,
        )
        candidate_docs = (
            [ROOT / 'README.md']
            + sorted((ROOT / 'adoption').rglob('*.md'))
            + sorted((ROOT / 'recipes').rglob('*.md'))
            + sorted((ROOT / 'docs').rglob('*.md'))
        )
        offenders = []
        for doc in candidate_docs:
            if not doc.exists():
                continue
            for lineno, line in enumerate(doc.read_text().splitlines(), start=1):
                if 'baseline_commit' not in line:
                    continue
                if not checkout_verb.search(line):
                    continue
                if negation.search(line):
                    continue
                offenders.append(f'{doc.relative_to(ROOT)}:{lineno}: {line.strip()[:200]}')
        self.assertEqual(
            offenders, [],
            f"these doc lines still tell a reader to `git checkout`/`git switch` "
            f"source.baseline_commit (a revision with no adoption/ or "
            f"tools/adoption/ directory) instead of source.release_tag: {offenders}",
        )
        # Positive controls: the scan above must actually catch the known-broken
        # form (with either extraction style) and must still exclude an explicit
        # warning that happens to use the real checkout verb, so a change to the
        # scan's own logic doesn't silently make it vacuous either way.
        broken_python_example = (
            'git checkout "$(python3 -c "import json;'
            "print(json.load(open('adoption/manifest.json'))"
            "['source']['baseline_commit'])\")\""
        )
        broken_jq_example = (
            "git checkout \"$(jq -r '.source.baseline_commit' adoption/manifest.json)\""
        )
        warning_with_real_verb_example = (
            'Do **not** run `git checkout "$(...baseline_commit...)"`: '
            'baseline_commit is never a checkout target.'
        )
        self.assertTrue(checkout_verb.search(broken_python_example) and 'baseline_commit' in broken_python_example
                         and not negation.search(broken_python_example))
        self.assertTrue(checkout_verb.search(broken_jq_example) and 'baseline_commit' in broken_jq_example
                         and not negation.search(broken_jq_example))
        self.assertTrue(checkout_verb.search(warning_with_real_verb_example)
                         and 'baseline_commit' in warning_with_real_verb_example
                         and negation.search(warning_with_real_verb_example))


if __name__ == '__main__':
    unittest.main()
