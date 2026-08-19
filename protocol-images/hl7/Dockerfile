# HL7 v2 over MLLP の受信側（電子カルテ役）と送信側（モダリティ役）を1つの
# イメージで兼ねる。MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで完結する。MLLPは開始・終了
# バイトを付けるだけのフレーミングであり、HL7 v2 自体も区切り文字で並べた
# テキストなので、ライブラリを挟む必然性が無い。
FROM python:3.10-slim

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
