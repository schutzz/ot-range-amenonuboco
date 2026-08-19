# OPC UA のサーバ（機器・ゲートウェイ役）とクライアント（監視役）を1つのイメージで兼ねる。
# MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# ライブラリのバージョンは固定する。未固定だと「昨日まで動いていた器が今日は
# 起動しない」という、レンジの再現性そのものを損なう壊れ方をする。
FROM python:3.10-slim

RUN pip install --no-cache-dir "asyncua==1.1.5"

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
