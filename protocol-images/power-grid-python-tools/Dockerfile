# power-grid-reference の Python 3.10 資産向け共通image。
# iproute2とSNMP client/serverをbuild時に同梱し、container起動時の
# package-manager呼出しを不要にする。
FROM python:3.10-slim-bullseye@sha256:b3061b93c8df9809c3783a4f17bbf2520425ec6b40bd3e5e7538870e21ba7209

RUN echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye main" > /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260831T070239Z bullseye-security main" >> /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye-updates main" >> /etc/apt/sources.list \
    && DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 snmp snmpd \
    && rm -rf /var/lib/apt/lists/* \
    && command -v ip \
    && command -v tc \
    && command -v snmpset \
    && command -v snmpd

CMD ["tail", "-f", "/dev/null"]
