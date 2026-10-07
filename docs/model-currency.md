# Model currency

The model inventory is [model-currency.json](../catalogs/foundation/model-currency.json),
with its [schema](../catalogs/foundation/model-currency.schema.json). The current
partial inventory declares 20 artifact/model-consumer rows and seven package
snapshots, and remains `pending`. The [dated fill provenance](../evidence/artifacts/model-currency-enforcement-20261007/fill-source-review.json)
records eight unresolved groups and the sources for each date and exact revision.
This is not evidence that every installed or shipped model has been inventoried
or is current. The command center owns the ruled selections and any model switch.
This automation proposes reviews; it neither installs nor selects a model.

Each model row records its role, consumer, model identifier, exact revision,
release date and primary URL, check date and `in_use`, `held` or `package_bound`
status. Every shipped model needs a row, including embeddings, rerankers,
document/OCR/vision models, package-bundled weights and hosted model identities.
Publication validation checks the declared rows; it does not discover missing
models from a running host. Change `inventory_status` to `complete` only after
that inventory review, not merely because validation passes.

The partial fill keeps unknown selections outside the strict row subset, with
their known identities and remaining gate in the provenance record. In particular,
QMD's interim Q8 embedding still needs its scoped landscape exception or actual
CC cutover; planned retirement is not observed retirement. Unpinned loader defaults,
older enclosing packages, original MinerU companion checkpoints, trading/other-host
models and the critic's uncovered roles keep inventory completion open.

Each date retains its basis: vendor product announcements, selected artifact
uploads, tokenizer configuration revisions and shipping-package publication are
different observations. The original model-refresh packet is not rewritten when
a primary artifact date corrects its repository-created timestamp.

## Dates and package bindings

The existing [publication validator](../scripts/validate.py) checks currency
offline, with the current UTC date by default:

```sh
python3 scripts/validate.py
python3 scripts/validate.py --today 2026-10-07
```

A release more than 42 days old fails unless the model's `landscape_check` is
at most seven days old. A check records primary sources, the newer candidates
considered, each rejection reason, the overall hold reason and the model's
overturn trigger. An empty candidate list needs a sourced explanation that no
newer qualifying candidate was found. Exactly 42 days and exactly seven days
remain valid; future or malformed dates and missing source URLs fail.

A `package_bound` model joins `package.id` and `package.version` to a package
row's `id` and `latest_version`. The shipping package's release date supplies
the effective age. The weight identity, original release date and source remain
recorded, even if old. An old shipping package still needs the same seven-day
landscape exception. A declared latest package is a recorded claim, not proof
of upstream currency: the daily check separately compares the primary source.
Package-bound checks always follow the package's release line, even when the
model also retains its own weight line.

## Daily review proposals

The existing daily [stack-currency timer](../adoption/templates/systemd/stack-currency.timer)
starts a [service template](../adoption/templates/systemd/stack-currency.service)
whose new pre-step runs:

```sh
python3 scripts/freshness_propose.py --model-currency
```

It checks each declared release line once per run. Source failures and
unsupported sources produce `source_review` proposals, not current status.
An empty pending inventory produces `complete_inventory`, with zero source
checks. The service uses Nice 19 and idle I/O. An ordinary nonzero pre-step exit
does not prevent the separate offline `currency_due.py` notice. The unit's
900-second startup timeout and the collector's 30-second per-source bounds
still need native verification with the filled inventory: a whole-unit timeout
is not covered by that ordinary-exit recovery claim. This repository change has not
installed, started or enabled the revised unit on a host.

| Line | Supported primary check | Boundary |
| --- | --- | --- |
| `huggingface` | Installed `hf models info REPOSITORY --revision main --expand sha,createdAt,lastModified --format json` | Exact selected SHA stays in the model row. `main` is the upstream default revision; a pinned SHA or tag cannot be the currency line. Different SHA means revision review, not a proven new weight release. |
| `github_release` | `gh api --cache 120s repos/OWNER/REPOSITORY/releases/latest` | Published full-release metadata; no drafts/prereleases. Check account budget first and defer below 500 core requests. |
| `pypi` | PyPI's project JSON API | Latest version with non-yanked artifacts; earliest remaining artifact upload supplies the observed publication date. |
| `vendor_page` | Source-review proposal | No generic release parser is invented. Hosted-vendor pages and other unsupported lines remain unknown until a maintained adapter/source review is qualified. |

Hub repository creation and last modification do not date a product release;
README-only changes can alter a SHA. Moving to a new repository or another
model family requires a landscape review, which a same-line check cannot supply.
The Hub child disables implicit authentication and telemetry before invoking the
installed CLI; no token store is inspected by this collector. Public metadata
does not qualify model behavior or artifact integrity. Actual version changes
still need the lane's release, security and integrity gates, including cooldown.

The two-day advance refresh is included. The collector opens `refresh_landscape`
on day five after every declared landscape check, including before its model
crosses the 42-day bar. Days six and seven remain valid; an older release fails
on day eight. Missing checks on an older release also propose a refresh. These are review requests; they do
not renew the check date or hide an expired exception.

Dated JSON and Markdown proposals are appended under
`$XDG_STATE_HOME/native-agent-stack/model-currency`, or the native per-user state
directory when that variable is unset. Files use mode 0600 and the directory
uses mode 0700. A proposal destination inside a Git checkout is rejected.
There is no automatic GitHub PR, catalog edit or model switch. The command
center reviews and routes the private proposal through the normal owner and PR
process. An unavailable source keeps its unknown reason and child exit code;
raw command diagnostics are omitted from this private summary.

For an offline check without children, network, state writes or model calls:

```sh
python3 scripts/freshness_propose.py --model-currency --offline --dry-run \
  --checked-at-utc 2026-10-07T01:00:00Z
```

The [decision](decisions/2026-10-07-model-currency-enforcement.md) records sources,
alternatives and the missing modalities that the next landscape review must
cover. The initial pending scaffold does not establish native timer execution,
complete inventory coverage, current deployed models or upstream acceptance.

For the proposed persistent MinerU source carrier, use the [local-service recipe](../recipes/mineru-local-service.md).
The CC owns activation and fresh-shell parsing. Its source override is separate
from the still-unaccepted embedded-engine CPU guard. The revised ai-memory example
requires 2.5.2 prefix support; component/installer alignment remains with its owner.
