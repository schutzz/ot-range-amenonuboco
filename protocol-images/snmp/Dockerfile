# SNMP のエージェント（機器の管理インターフェース役）とポーラ（NMS役）を1つの
# イメージで兼ねる。MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 本物の net-snmp を使う。SNMPを自作する必然性は無く、実際の運用で使われている
# 実装が生成するパケットであることに価値がある。
#
# 電力リファレンスは同じ構成を資産の overrides.command 内で apt-get していたが、
# それだと器を立ち上げるたびにネットワーク越しの取得が走り、起動が遅く外部の
# パッケージ配信状況にも依存する。イメージへ焼くことで再現性が上がる。
FROM debian:bookworm-slim

RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        snmpd snmp python3 >/dev/null 2>&1 && \
    rm -rf /var/lib/apt/lists/*

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
