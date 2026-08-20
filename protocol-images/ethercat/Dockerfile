FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    iproute2 \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir scapy==2.5.0

WORKDIR /app
COPY run.py /app/run.py

CMD ["python", "-u", "/app/run.py"]
