# 三菱 MELSEC (MC プロトコル / SLMP) のサーバ（PLC役）とクライアント（HMI役）を
# 1つのイメージで兼ねる。MODE 環境変数で役割を切り替える。
#
# tshark にネイティブ dissector は存在しない。対応は以下の2段階:
#   1. structuring.protocols に { name: slmp, output_index: ... } を宣言 → tshark が
#      ポートベースで捕捉し、生のバイトとして index に投入する（解析なし）。
#   2. structuring.dissector_plugins に Lua dissector を指定すると、compose.py が
#      Wireshark プラグインディレクトリへマウントし、tshark が SLMP/MC として
#      完全解析できるようになる（Phase11 Stage1C の dissector_plugins 配線機構）。
#
# pymelsec は MC プロトコル 3E/4E フレームのクライアント実装は持つがサーバ
# 実装を持たず、また PyPI 版は 0.x 系で API が不安定（pymodbus の教訓を踏まえ
# 未固定バージョン依存は避ける）。そのため server/client 双方を run.py 内で
# 標準ライブラリの socket 直接実装として書き起こしている（3E バイナリフレーム、
# TCP ポート 5007 が標準）。外部ライブラリの pip install は不要。
FROM python:3.10-slim

RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 >/dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
