# HL7 v2 over MLLP の受信側（電子カルテ役）と送信側（モダリティ役）を1つの
# イメージで兼ねる。MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで完結する。MLLPは開始・終了
# バイトを付けるだけのフレーミングであり、HL7 v2 自体も区切り文字で並べた
# テキストなので、ライブラリを挟む必然性が無い。
FROM python:3.10-slim

# iproute2 を同梱する。生成される起動コマンドは、資産が直接接続していない
# セグメントへの `ip route add` を含む(これが無いと通信はDockerの既定
# ゲートウェイを迂回し、ゲートウェイ上のミラーリングに乗らない＝観測
# されない)。同梱しておくと起動時のapt-getを丸ごと省略でき、レンジの
# 立ち上がりが速くなり、パッケージ配信への依存も無くなる。
RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 >/dev/null 2>&1 && rm -rf /var/lib/apt/lists/*

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
