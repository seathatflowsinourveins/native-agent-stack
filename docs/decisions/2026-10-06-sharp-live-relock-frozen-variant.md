# Patch the live sharp dependency and retain captured macOS evidence

Date: 2026-10-06. Lane: foundation. Status: draft source-backed security relock.

GHSA-wq5f-xc86-pv6w affects sharp before 0.35.5 through librsvg
(CVE-2026-96889). The maintainer's first patched release 0.35.5 selects
sharp-libvips 1.3.4/librsvg 2.63.2. The maintained application recipe installs
its live pnpm-lock.yaml; its Next 16.3.8 optional range ^0.35.4 allows this fix.

Use that recipe's pnpm 12.4.2 supported targeted update. Its native CLI rejects
an exact selector for an indirect dependency, so use the documented unversioned
indirect update while independently verifying that published latest and the
exact resolved version are both the first patch 0.35.5. Only sharp's 27 required
family entries move; 67 unrelated package entries, package.json and the manager
document remain unchanged. Retain the old lock and append its prior
qualification intact in the recipe revision ledger.

The captured macOS lock remains byte-identical. One exception in its dedicated
config expires on 2026-12-24 and applies to that file alone. SVG decoding reaches
sharp's OpenInput/VipsForeignLoadSvg loaders; source review found no supported
consumer executing the retained variant. The Mac label alone is no exemption.
Remove the exception before any replay/manual install/new consumer or expiry.
A broad ordinary ignore and changing historical lock bytes were rejected.

Frozen install, peers, schema/type checks, production build and actual loaded
sharp/librsvg metadata pass. Full make verify failed on 12 database setup errors;
the separate browser attempt refused another service on port 18080. Those
failures remain distinct from the passing frontend checks. Original full-stack
receipts are not rewritten or promoted. OSV database queries find the advisory
on 0.35.4 and none on 0.35.5; native full-inventory scanner execution is unclaimed
because no executable was found in the inspected local locations.

Sources: [maintainer advisory](https://github.com/lovell/sharp/security/advisories/GHSA-wq5f-xc86-pv6w),
[Sharp 0.35.5](https://github.com/lovell/sharp/releases/tag/v0.35.5), source
51a990faa26ade5586a4934ac9673c98d8893326;
[libvips 1.3.4](https://github.com/lovell/sharp-libvips/releases/tag/v1.3.4);
lovell/sharp@7f1a0a22cc285fe180766f4935d50b55af6e8432:src/common.cc:323,506,596;
[pnpm update](https://pnpm.io/cli/update) and [frozen install](https://pnpm.io/cli/install).
Recipe/source scope: native-agent-stack@0d5e6506434fab598dee861c749a22e628beb75a:
blueprints/convergence-practice/application-delivery/Makefile:3-5,27-32,
README.md:170-180; tests/test_frozen_macos_variant_no_use.py:1-47.
Actual output and scope: evidence/receipts/sharp-0355-qualification-20261006.json.
