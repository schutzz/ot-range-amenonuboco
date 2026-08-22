# Release Notes

This page is the public, human-readable history of Amenonuboco. It summarizes every completed phase and links release tags to their scope. Detailed implementation history remains available in the [Git commit log](../../commits/main).

## v0.12.0 — Verified Performance Evidence

**Tag:** [`v0.12.0`](https://github.com/schutzz/ot-range-amenonuboco/tree/v0.12.0)  
**Archive DOI:** [10.5281/zenodo.22051216](https://doi.org/10.5281/zenodo.22051216)

Phase 12 replaced unsupported benchmark claims with reproducible measurements. It added stabilized benchmark collection, batch-size counterbalancing, resource-limit screening, repeated candidate measurements, and a deterministic `tcpreplay` Scenario C. In the Docker Desktop reference environment, a 10-second PROFINET RT injection was observed up to 200,000 pps with Elasticsearch settling within 300 seconds, final arrival of at least 99.98%, and zero router qdisc drops. The 200,000 pps value is a host-protection exploration cap, not an absolute limit. Full scope, raw evidence, SLO, and reproduction commands: [`docs/performance/phase12/`](../performance/phase12/).

Follow-up documentation PRs added the Zenodo citation, finalized the performance catalog, and made English the canonical README with a Japanese companion and strict contribution policy.

## v0.11.0 — Initial tagged platform release

**Tag:** [`v0.11.0`](https://github.com/schutzz/ot-range-amenonuboco/tree/v0.11.0)

This tag captures completion of Phases 0–11: the manifest-driven range platform, topology and instrumentation generation, tshark structuring, scenario integration, visualization, sector demonstrations, reusable protocol images, GUI support, digital-twin impairment support, and smart-factory protocol/security extensions.

## Complete phase record

| Phase | Delivered capability |
|---|---|
| 0 | Project initialization and the Cyber Range as Code direction. |
| 1 | Manifest-driven topology-layer provisioner and generated network diagram. |
| 2 | Automatic instrumentation layer and `tc`-based traffic mirroring. |
| 3 | tshark structuring layer and Elasticsearch bulk-loading pipeline; subsequent plan-gap corrections. |
| 4 | Extension points for detection and attack assets. |
| 5 | End-to-end Signal 1 zone-deviation demonstration from attack through structuring, detection, and assessment. |
| 5.5 | Validation hardening, assessment-harness cleanup, and additional tests. |
| 6 | Visualization layer and Grafana dashboard wiring; SOC-style diagram refinement. |
| 7 | Deep, tested scenarios for power, water utility, and critical manufacturing; bidirectional mirroring reliability fix and walkthrough documentation. |
| 8 | Browser-based manifest editor, schema-derived vocabulary, GUI documentation, and static Pages deployment support. |
| 9 | Reusable protocol assets, 15-sector reference manifests, explicit unobservable-boundary modeling, GUI sector coverage, DNP3 power reference, startup sweep, screenshots, and OPC UA historian correction. |
| 9.5 | Hardening and polish: cgroup limits, malformed-frame handling, ONVIF, and GOOSE replay. |
| 10 | Impairment specification, physical-process specification, `tc netem` generation, digital-twin engine, water-utility physical-consequence E2E, and GUI parity verification. |
| 11 | FINS, MQTT, MELSEC, SECS/GEM, PROFINET, EtherCAT, and CIP Security assets; exercise key injection, Lua dissector wiring, and 13 real-container defects found and fixed. |
| 12 | Verified performance evidence, SLO, reproducible benchmark tools, resource experiments with documented statistical limits, deterministic Scenario C, Zenodo archive, and public performance catalog. |

## Maintenance history after v0.12.0

The default branch subsequently received these reviewed documentation changes:

1. Zenodo DOI citation metadata and badges (PR #2).
2. Phase 12 status and performance-catalog documentation (PRs #3 and #4).
3. English canonical README, Japanese companion README, and `CONTRIBUTING.md` (PR #5).

Future releases should add a dated section above this one, link the tag and DOI when archived, summarize user-visible changes, and link detailed evidence rather than duplicating measured values.
