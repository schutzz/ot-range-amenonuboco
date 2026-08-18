# Modbus/TCP のサーバ（機器役）とクライアント（ポーリング役）を1つのイメージで兼ねる。
# MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# ライブラリのバージョンは固定する。pymodbus は 3.x 系の中でもマイナー
# バージョンでAPI名・引数が変わっており(3.15では ModbusSlaveContext →
# ModbusDeviceContext、StartTcpServer の第1引数の解釈も変更、クライアントの
# slave → device_id キーワード化)、未固定だと「昨日まで動いていた器が今日は
# 起動しない」という、レンジの再現性そのものを損なう壊れ方をする。
# 3.6.9 はサーバ・クライアント双方の読み書きを実機で確認済み。
FROM python:3.10-slim

RUN pip install --no-cache-dir "pymodbus==3.6.9"

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
