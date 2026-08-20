# オムロン FINS プロトコルのサーバ（機器役）とクライアント（ポーリング役）を
# 1つのイメージで兼ねる。MODE 環境変数で役割を切り替える。
#
# tshark には FINS のネイティブ dissector（フィルタ: omron）が存在するため、
# structuring.protocols に { name: omron, output_index: ... } を宣言するだけで
# 構造化パイプラインが機能する（Lua プラグイン不要、Phase11 低リスク確認済み）。
#
# fins-driver は検証時点でクライアント専用（サーバ実装を持たない）かつ
# API が 0.x 系で不安定だったため採用を見送り、FINS/TCP フレーム（ハンドシェイク
# + メモリエリア Read/Write）を run.py 内で標準ライブラリの socket 直接実装として
# 書き起こしている（melsec と同じ判断、pymodbus の教訓を踏まえ外部ライブラリの
# 未固定バージョン依存を避けた）。そのため外部ライブラリの pip install は不要。
FROM python:3.10-slim

# iproute2 を同梱する（modbus と同じ理由: ルーティング注入・起動高速化・
# パッケージ配信への依存排除）。
RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 >/dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
