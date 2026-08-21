FROM debian:bullseye-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends tcpreplay python3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY generate_l2_flood_pcap.py /app/generate_l2_flood_pcap.py
COPY run.sh /app/run.sh
RUN python3 /app/generate_l2_flood_pcap.py /app/l2_flood.pcap --frames 10000 && \
    chmod +x /app/run.sh

ENTRYPOINT ["/app/run.sh"]
