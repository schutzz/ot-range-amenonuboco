# SIP の UAS（レジストラ／PBX役）と UAC（IP電話役）を1つのイメージで兼ねる。
# MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで完結する。SIPはHTTPに似た
# テキストプロトコルであり、登録と1本の呼に限ればヘッダを組み立てるだけで
# 表現できるため、ライブラリを挟む必然性が無い。
FROM python:3.10-slim

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
