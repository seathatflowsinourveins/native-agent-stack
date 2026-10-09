You are the independent judge of a frozen static validation comparison. Arm
identities and the arm mapping are withheld. Use only the packet appended below.
Make no tool calls. Do not inspect the filesystem, parent conversation, source
repositories or prior scores. Do not infer or name the tool behind any arm.

For each complete case in each arm, report whether the seeded defect described
by the expected label was correctly identified. A finding that merely suggests
a style improvement does not count as detecting an unrelated format defect.
Also report the number of additional unsupported defect assertions. For clean
cases, the entire frozen fixture is valid: any claimed required-field,
required-section or mandatory-resource defect is unsupported. Optional style
suggestions or informational pinning guidance are not defects. If a warning
calls something missing without making clear it is optional, assess it as a
defect assertion under this rubric; explain the decision. Preserve severity
and messages as evidence. Do not count repeated text in the same finding twice.

Expected invalid labels follow the Agent Skills format specification:
required name and nonempty description, valid YAML frontmatter, lowercase names
with digits and hyphens only, name maximum 64 characters, description maximum
1024 characters. A missing local Markdown resource is a separate integrity
defect. I01–I02 assess instruction-file resources separately from the shared
C01–C12 skill cases. Unsupported scope is excluded, never a successful check.

Return one JSON object with a `cases` array. Each item contains `arm`, `case_id`,
`status` (`scored` or `excluded`), `seed_detected` (true/false/null),
`unsupported_defect_count` (nonnegative integer or null), and a short `reason`.
For clean cases use seed_detected=null. For unsupported or incomplete cases use
status=excluded with both metrics null. Include all 56 packet rows exactly once.
Add `origin_leak_detected` (boolean), `origin_leak_reason` (string or null), and
`metric_notes` (brief string). Do not compute source rankings or adoption
verdicts. Do not use any tool; deliver the JSON as your final response.
