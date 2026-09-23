# Workers comparison: artifact-acceptance judge prompt (pinned 2026-09-23)

You judge one stripped packet from the workers/SDK comparison. Arms appear only as
opaque labels (`arm-<8 hex>`). If a product, vendor, model-family, repository or
filesystem path name appears, return `{"leak": true, "text": "<offending text>"}` and stop.

For each submission in the packet, decide `artifact_accepted` (true/false/unknown):
true only when the returned artifact satisfies every preregistered acceptance clause
printed in the packet, using the packet's frozen outputs alone. Copy numbers exactly;
never infer a value the packet does not contain; missing evidence is `unknown`, not false.

Return only JSON:
{"leak": false, "judgments": [{"arm": "arm-xxxxxxxx", "submission": <int>,
  "artifact_accepted": true|false|"unknown", "failed_clauses": [<clause ids>],
  "evidence": "<quoted packet text, at most 200 chars>"}]}
