# Amenonuboco — Cyber Range as Code

[日本語](./README.ja.md)

![status](https://img.shields.io/badge/status-Phase%2012%20(Performance%20Evidence)-brightgreen)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](./LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22051216.svg)](https://doi.org/10.5281/zenodo.22051216)
[![CI](https://github.com/schutzz/ot-range-amenonuboco/actions/workflows/ci.yml/badge.svg)](https://github.com/schutzz/ot-range-amenonuboco/actions/workflows/ci.yml)
[![Live GUI Demo](https://img.shields.io/badge/GUI-Live%20Demo-blue)](https://schutzz.github.io/ot-range-amenonuboco/)

> A manifest-driven platform for provisioning isolated OT/ICS cyber ranges: target assets, network instrumentation, protocol structuring, and scenario assets.

![A self-contained network diagram generated from one power-grid manifest](./docs/images/network-diagram-power.png)

One manifest, such as [`power-grid-reference.yaml`](./manifests/power-grid-reference.yaml), generates a Docker Compose topology, traffic-mirroring instrumentation, and a tshark-based structuring pipeline. Amenonuboco calls this approach **Cyber Range as Code (CRaC)**: treat the range itself as declarative, reproducible infrastructure.

## Why it exists

OT/ICS exercises repeatedly require topology definitions, packet mirroring, sidecars, ingestion, and scenario wiring. Amenonuboco makes these common parts manifest-driven so a validated pattern can be reused for another protocol, topology, or exercise. It builds on [`ot-ids-verum`](https://github.com/schutzz/ot-ids-verum): the platform provides range and observability layers, while each scenario owns detection logic and assessment.

## Quick start

Prerequisites: Python 3.10–3.12, Docker Compose, and a local Docker engine. Run only in an isolated, authorized laboratory; never connect a generated range to production or unauthorized OT/ICS networks.

```bash
git clone https://github.com/schutzz/ot-range-amenonuboco.git
cd ot-range-amenonuboco
pip install -r requirements-dev.txt
cd platform
python cli.py provision ../manifests/power-grid-reference.yaml
cd ..
docker compose up -d
```

Generate the matching self-contained diagram with:

```bash
python platform/cli.py diagram manifests/power-grid-reference.yaml
```

Before a Docker Compose run, stop unrelated containers and networks. The reference environment uses fixed host ports for components such as Grafana; residual containers can cause port conflicts and invalidate end-to-end observation checks. Docker Desktop is the reference environment for the published performance evidence, not a claim about every host or production deployment.

## Try the manifest editor

The [browser-based manifest editor](https://schutzz.github.io/ot-range-amenonuboco/) works without installation. It validates CIDR membership, duplicate IP addresses, and gateway roles while rendering topology and generating YAML. It can load the 15-sector reference configurations and exports a new generated file rather than overwriting an input manifest. See the [editor guide](./docs/gui-guide.md).

## Platform capabilities

- **tshark by default for structuring**, using Wireshark dissectors for broad protocol coverage.
- **Clear responsibilities**: the platform provisions through structuring; detection logic belongs to scenario assets.
- **Optional specialist parsers**: Spicy/Zeek are plugins for stateful detection, high-load cases, or non-standard payloads.
- **Consistent outputs**: structured events use `ot-logs-<protocol>-*` indices.

## Demonstrated sectors and reusable assets

Three sectors are demonstrated end to end with real open-source protocol implementations and structured Elasticsearch output:

| Sector | Scenario focus | Protocol | Security focus |
|---|---|---|---|
| Power | Unauthorized UPS management access | SNMP | Availability |
| Water utility | Oldsmar-style process-value manipulation through remote access | VNC | Integrity |
| Critical manufacturing | Lateral movement from a camera network to an OT floor | EtherNet/IP | Confidentiality / segmentation |

Walkthroughs, observed logs, and scenario evidence are in [`docs/showcase/`](./docs/showcase/). The repository also contains 15 reference manifests derived from CISA critical-infrastructure sectors. The catalog distinguishes end-to-end demonstrations, range-only configurations, and configurations that explicitly declare unobservable boundaries; see [sector coverage](./docs/sector-coverage.md).

Reusable protocol images include Modbus/TCP, BACnet/IP, OPC UA, DNP3, SNMP, DICOM, HL7 v2, SIP, and EtherNet/IP. Server and client roles are deployed in pairs so the range produces real protocol traffic. Details: [protocol assets](./docs/protocol-assets.md).

## Repository layout

```
manifests/       Declarative range definitions and 15-sector references
protocol-images/ Reusable protocol server/client implementations
platform/        Provisioner and diagram generator
gui/             Static manifest editor
scenarios/       Detection, attack, and assessment assets
attack-assets/   Caldera abilities and adversaries
tests/           Schema, generated-artifact, and scenario tests
docs/            Public documentation and evidence
```

## Performance evidence and scope

Phase 12 recorded a Docker Desktop reference-environment test using a 10-second PROFINET RT `tcpreplay` injection. At rates up to **200,000 pps**, Elasticsearch settled within 300 seconds, final arrival was at least **99.98%**, and router qdisc drops were zero. The 200,000 pps point is a host-protection exploration cap, not an absolute platform limit. A result that has not settled within 60 seconds is treated as downstream backlog rather than immediate loss.

The complete SLO definition, raw results, environment constraints, and reproduction commands are published in [`docs/performance/phase12/`](./docs/performance/phase12/). CPU-resource experiments are internal exploratory evidence; their improvement coefficients are not external performance claims.

## Development and contributing

```bash
pip install -r requirements-dev.txt
pytest
```

Read [`CONTRIBUTING.md`](./CONTRIBUTING.md) before opening a change. It requires isolated-lab safety, focused pull requests, appropriate tests, reproducible evidence for performance claims, and synchronized English/Japanese documentation.

## Citation and license

The archived Phase 12 release is available at [Zenodo](https://doi.org/10.5281/zenodo.22051216). Citation metadata is in [`CITATION.cff`](./CITATION.cff).

The complete project and release history is in [Release Notes](./docs/releases/README.md).

[Apache License 2.0](./LICENSE). When redistributing modifications, retain required attribution in [`NOTICE`](./NOTICE) and mark modified files as required by the license.

---

🤖 This project is developed with [Claude Code](https://claude.com/claude-code) and [Codex](https://openai.com/codex/).
