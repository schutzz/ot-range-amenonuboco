# EtherNet/IP (CIP) のアダプタ（PLC役）とスキャナ（上位監視役）を1つの
# イメージで兼ねる。MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで完結する。カプセル化ヘッダは
# 24バイト固定で、必要なコマンドとCIPサービスに限れば短く書けるため、
# ライブラリを挟む必然性が無い。
FROM python:3.10-slim

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
