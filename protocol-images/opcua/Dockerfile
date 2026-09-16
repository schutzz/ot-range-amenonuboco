# OPC UA のサーバ（機器・ゲートウェイ役）とクライアント（監視役）を1つのイメージで兼ねる。
# MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# ライブラリのバージョンは固定する。未固定だと「昨日まで動いていた器が今日は
# 起動しない」という、レンジの再現性そのものを損なう壊れ方をする。
FROM python:3.10-slim-bullseye@sha256:b3061b93c8df9809c3783a4f17bbf2520425ec6b40bd3e5e7538870e21ba7209

# iproute2 を同梱する。生成される起動コマンドは、資産が直接接続していない
# セグメントへの `ip route add` を含む(これが無いと通信はDockerの既定
# ゲートウェイを迂回し、ゲートウェイ上のミラーリングに乗らない＝観測
# されない)。同梱しておくと起動時のapt-getを丸ごと省略でき、レンジの
# 立ち上がりが速くなり、パッケージ配信への依存も無くなる。
RUN echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye main" > /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260831T070239Z bullseye-security main" >> /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye-updates main" >> /etc/apt/sources.list \
    && DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v ip \
    && command -v tc

RUN pip install --no-cache-dir "asyncua==1.1.5"

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
