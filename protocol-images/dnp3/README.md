# DNP3 range assets

Reusable, containerized DNP3 (IEEE 1815) assets for isolated OT/ICS cyber-range traffic. The same image runs as an **outstation** (device role) or a **master** (supervisory role).

The master sends Class 0/1/2/3 integrity polls at a configurable interval and sends a Direct Operate command every fourth cycle. The outstation returns analog-input values. Frames include valid DNP3 header and data-chunk CRCs so that tshark can dissect the exchange.

## Scope and safety

Use this asset only in an isolated, authorized laboratory. It is a training and observability component, not software for connecting to real industrial equipment or production networks.

## Build and run a minimal pair

From the repository root:

```bash
docker build -t amenonuboco-dnp3 ./protocol-images/dnp3
docker network create amenonuboco-dnp3

docker run -d --rm --name dnp3-outstation \
  --network amenonuboco-dnp3 \
  -e MODE=outstation \
  -e LABEL=dnp3-outstation \
  amenonuboco-dnp3

docker run --rm --name dnp3-master \
  --network amenonuboco-dnp3 \
  -e MODE=master \
  -e TARGET=dnp3-outstation \
  -e LABEL=dnp3-master \
  amenonuboco-dnp3
```

The master prints poll and Direct Operate activity while it runs. In another terminal, confirm the outstation is listening and responding:

```bash
docker logs dnp3-outstation
```

Stop and remove the demonstration resources when finished:

```bash
docker stop dnp3-outstation
docker network rm amenonuboco-dnp3
```

## Configuration

| Variable | Applies to | Default | Purpose |
|---|---|---:|---|
| `MODE` | both | `outstation` | `outstation` / `master`; `server` and `client` are accepted aliases. |
| `PORT` | both | `20000` | TCP listen or destination port. |
| `TARGET` | master | — | Outstation hostname or IP address; required for master mode. |
| `INTERVAL` | master | `5` | Poll interval in seconds; fractional values are accepted. |
| `DEVICE_ID` | both | outstation `10`, master `1` | Local DNP3 station address. |
| `PEER_ID` | both | outstation `1`, master `10` | Remote DNP3 station address. |
| `POINTS` | outstation | `3` | Number of analog-input points in responses. |
| `LABEL` | both | `dnp3` | Identifier included in container logs. |

## Verify protocol fields

Capture the laboratory traffic with the range instrumentation or another authorized capture method, then inspect the resulting PCAP with tshark:

```bash
tshark -r dnp3.pcapng -Y dnp3 -T fields \
  -e dnp3.al.func -e dnp3.src -e dnp3.dst -e dnp3.al.ana_int
```

The asset has been verified to produce DNP3 READ (`dnp3.al.func=1`), DIRECT OPERATE (`5`), and RESPONSE (`129`) messages, analog-input values, and DNP3 source/destination station addresses. Header and data-chunk CRCs are valid.

## Use in an Amenonuboco range

Reference manifests use this directory as an image source and configure DNP3 structuring as `dnp3`, with output indices such as `ot-logs-dnp3-*`. See the [protocol asset guide](../../docs/protocol-assets.md), the [power-grid reference](../../manifests/power-grid-reference.yaml), and the [dam-control reference](../../manifests/dam-control-reference.yaml).
