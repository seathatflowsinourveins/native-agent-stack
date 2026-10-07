# Gateway correction schema — A19 addendum (2026-10-07)

This dated addendum amends only the class list in section 1 of the reviewed readiness evidence change set (SHA256 99c42fd333feef63ad48a5a8b6ff0852540463ff98afd82551b739d37887b088). The SHA-bound original stays unchanged. The co-op's A19 option A adds exactly two truthful classes; the command center may rename their spellings before publication.

The effective class list contains the original six followed by the two additions:

- `old-gateway-inferred`
- `unknown-gateway`
- `new-gateway-recorded`
- `new-gateway-inferred`
- `dated-not-live`
- `not-audited`
- `native-no-gateway`: positive evidence proves native execution with no gateway. This covers the native execution scopes in section 2 E6 and section 4 E10.
- `not-2604`: the run did not execute on NativeStack2604, established by its own dated execution or source evidence.

The record schema stays `native-agent-stack/evidence-relabel/v1`. Its nine fields stay `schema`, `written_utc`, `item`, `item_sha256`, `class`, `label`, `basis`, `consumers`, and `requalifies_by`; the basis entries and original item scopes are unchanged. This is an additive vocabulary amendment, not a new record format, run or readiness gate.

A proven native route must not be labelled `new-gateway-recorded` or left `unknown-gateway`. A missing call-log row or an unbound profile name alone proves no route. Each emitted disposition still needs the original file's digest and the quoted, hashed basis for that particular scope. If those inputs are unavailable, retain the pending source condition rather than invent a native or foreign-host observation.

The 31 existing correction records are unchanged. This amendment emits no E6 or E10 execution record: their qualified frozen originals and bases remain pending. Any later correction extends the record with a new linked observation; it does not rewrite historical results. T10's reviewed-records-first publication order and T4's gateway prerequisites remain unchanged.

Source: the co-op's A19 option A, also preserved in the dated owner-answer record of 2026-10-07T04:30:38Z (SHA256 79dc7ef483c3ae74eb4547b8668c2ceb86d86dd79a6408df71fc5d52e6ae3991), and sections 1, 2 E6 and 4 E10 of the reviewed change set above.
