# License scope

The root MIT license covers original publication documents, fixtures and validation glue. It does not relicense any upstream tool, model or separately attributed source.

No upstream runtime binary, model weights, authentication store or third-party skill collection is vendored here. Recipes fetch the upstream distribution, whose own license/notices must remain with it. The component and model manifests record the reviewed license of each selection; selected skill repositories can have different code/content licenses.

The public usage-report text fixture derives from the original local project adapter and replaces personal path literals. It is covered by the root license. Recorded tool output is included only as the small factual evidence needed to assess results.

SocratiCode is AGPL-3.0-only with an upstream commercial option; Nemotron weights use OpenMDW-1.1. These are not silently replaced with MIT by this repository. The original source project's full skill copies and license notices remain local and are not copied into this publication snapshot.

The native observability profile records AGPL-3.0-only for Loki and Grafana, Apache-2.0 for Prometheus/Alertmanager/Collector, and Apache-2.0 OR GPL-2.0-only for ntfy. Their official binaries remain outside this repository; pinned release provenance is in [backend pins](../observability/backends/pins.json) and the [Collector guide](../observability/collector/README.md).
