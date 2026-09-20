# Upstream practice and acceptance evidence

The foundation uses research to select a supported upstream solution, then
qualifies its actual behavior. Repository popularity, local test totals and a
well-formed receipt are discovery or validation signals; none establishes native
end-to-end behavior by itself. This policy applies to both catalogs and to new
Codex, Claude, worker and GitHub automation work.

## Select and reuse before building

Start with the selected repository's official installation, examples, tests,
release notes and CI. Use the relevant installed upstream skill for the current
operation. Extend discovery through maintained community skills, curated lists,
research and comparable implementations when the selected solution has a real
gap. Keep the source URL, revision, applicability and decision in the affected
recipe; an impressive repository count is not a reason to install alternatives.

The selected [ECC search-first skill](https://github.com/affaan-m/ECC/blob/dd6ee538aee0f548d4a6b520118f875431fd749e/skills/search-first/SKILL.md)
provides a research-before-implementation procedure. Adopt a suitable upstream
workflow directly, compose supported integrations, and add only the glue needed
for a demonstrated gap. Explain that gap instead of presenting local orchestration
as an upstream feature. The skill is guidance, not evidence that an operation ran.

## Identify what each check proves

| Evidence class | Required provenance and observation | Claim boundary |
| --- | --- | --- |
| Upstream test | Official repository/revision, unchanged test file or suite, exact upstream command, returned result and skips | The selected upstream tests on that runtime |
| Upstream example or native operation | Pinned official example/docs, supported command and actual returned output | The operation, inputs and host that were exercised |
| Local integration check | Local source revision, upstream behaviors it combines, explicit input/oracle and actual native results | Our integration; never described as an official upstream test |
| Synthetic fixture | Who constructed it, frozen data and expected results, purpose and limitations | The fixture; never production, market, account or whole-ecosystem evidence |
| Independent observation | Direct artifact/state inspection using a separate method, native histories or platform records | The independently checked properties, not every assertion in a receipt |
| Structural validation | Schema, references, hashes, syntax or local contract tests | Artifact consistency; not execution or adoption |

Prefer unchanged relevant upstream tests and published examples as the primary
behavior checks. A focused subset must retain its selection, upstream test names
and omissions. Record upstream test unavailability or incompatibility explicitly;
do not replace it with an easier custom demo and call the original requirement
passed. Local fault injection and integration checks may cover behavior that an
upstream suite does not exercise, but remain separately labelled.

## Preserve the returned result

Freeze the chosen inputs, source/test versions, commands and required outcomes
before the trial. Retain exact argument vectors, working directory, start/end
times, exit codes, stdout/stderr and artifact hashes. Keep sensitive raw output
private and declare every public sanitization. Preserve failed attempts before
correcting their demonstrated cause; do not silently retry or regenerate a green
receipt. Source inspection, installation, native execution and measured improvement
are separate outcomes.

Confirm consequential claims through independent observations: inspect the native
tool's output and resulting files/state, corroborate execution with the CI/job or
process record, and recheck the frozen oracle independently. Parsing a wrapper's
own `passed` field is not independent confirmation. A checksum proves byte identity;
it does not prove the bytes describe a successful or adequate test.

## Apply the same standard to automation

Use official upstream automation interfaces and recipes. Pin third-party actions,
keep workflow permissions scoped, separate credentials from published fixtures,
and retain failures and cleanup evidence, following the
[GitHub Actions secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use).
Official CI examples inform the implementation; the recorded run must still prove
our integration. A scheduled task's registration does not prove it executed, and
a process restart does not prove a machine reboot.

The two catalogs retain component-specific acceptance and remaining limits. The
same rules govern future updates: use a source-backed improvement and a matching
comparison before replacing an accepted default. Keep actual upstream counters,
artifact-size comparisons and provider usage separate; never fabricate missing
session or lifetime savings.
