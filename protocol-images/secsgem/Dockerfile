# SECS/GEM (HSMS-SS over TCP) の Equipment 役と Host 役を
# 1つのイメージで兼ねる。MODE 環境変数で役割を切り替える。
#
# SECS/GEM の標準 (SEMI E37): HSMS (High-Speed Message Services) は
# TCP/IP 上で動作するトランスポート層プロトコル。tshark は HSMS を
# ネイティブ dissector でサポートする（フィルタ: hsms）。
# SECS-II 上位層のメッセージ解析は限定的だが、演習用としては
# HSMS の接続確立・メッセージ交換フローが確認できれば十分。
#
# TLS_ENABLE=true でTLS上の HSMS（HSMS-SS over TLS）を有効化する。
# SSLKEYLOGFILE を設定すると演習用鍵注入アーキテクチャが機能する。
#
# ライブラリ: secspy (PyPI 上の最軽量 HSMS 実装)
# バージョン固定: 0.1.0 で HSMS Select.req/rsp と S1F1/S1F2 を確認済み。
FROM python:3.10-slim

RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 openssl >/dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

# secspy は PyPI に存在するが依存が少ない。インストールに失敗する場合は
# socket 直接実装（run.py 内蔵）にフォールバックする。
RUN pip install --no-cache-dir "secspy==0.1.0" 2>/dev/null || true

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
