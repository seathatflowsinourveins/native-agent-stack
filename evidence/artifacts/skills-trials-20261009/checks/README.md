# Skills-trials check provenance

`landscape-skills-tests.log` is **pre-restoration** evidence from
`8bff1669bed2b69ee27615a1b34c60ef11cfc8a8`. That head rewrote the maintenance
snapshot and test literals, before their restoration in
`0a41c4ffaaa007afed36a4a35976079f13e979cc`. The historical log is retained
byte-for-byte (sha256
`160d0c41d9cd3ba1e51a94f853a71e61a22a7003852ab6c0c2cabbe9613f382a`);
its 111-test result does not validate the rebased head.

The fresh `tests.test_landscape_sweep_skills` run at the final rebased head,
validator result and designated pre-cue result are retained with their exact
commands, head and log hashes in the separate rebase publication receipt:
`<host-home>/.local/state/native-agent-stack/research/api-surfaces-trials/skills-trials-20261009/rebase-918-20261009T0911Z/rebase-publication.json`.
The trial outcomes, preregistration, blinded packet, judge and vendor checks
remain the pinned evidence recorded in this artifact tree.
