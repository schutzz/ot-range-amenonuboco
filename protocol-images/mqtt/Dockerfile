# MQTT / MQTTS のブローカー役と Publisher/Subscriber 役（クライアント）を
# 1つのイメージで兼ねる。MODE 環境変数で役割を切り替える。
#
# ブローカー役: Mosquitto (公式 eclipse-mosquitto イメージ) を使う方式と、
# paho-mqtt の内蔵ブローカーを使う方式がある。本資産では軽量化のために
# paho-mqtt のみを使った純 Python 実装（broker: python3 -m hbmqtt 相当）
# を避け、あえて mosquitto パッケージを apt でインストールする方式を採用する。
# 理由: tshark の `mqtt` dissector は CONNECT/PUBLISH 等の MQTT パケット全体を
# 解析するが、パケットが実際に TCP 上を流れることが前提であり、同一プロセス内の
# ループバック通信では tshark に捕捉されない。
#
# MQTTS (TLS 対応) は TLS_ENABLE=true 環境変数で有効化する。
# SSLKEYLOGFILE 環境変数を設定すると、TLS セッションキーを指定パスへ書き出す。
# これは演習用暗号鍵注入アーキテクチャ（Phase11 決定事項予定）の先行実装。
#
# tshark の表示フィルタ: `mqtt`（MQTT はネイティブ dissector あり）
FROM python:3.10-slim

# iproute2 + mosquitto-clients（mosquitto_pub/sub, mosquitto ブローカー）
# mosquitto は Debian パッケージで入れる。
RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
       iproute2 \
       mosquitto \
       mosquitto-clients \
       openssl \
    >/dev/null 2>&1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "paho-mqtt==1.6.1"

COPY run.py /app/run.py
COPY mosquitto.conf /etc/mosquitto/mosquitto_amenonuboco.conf

CMD ["python3", "/app/run.py"]
