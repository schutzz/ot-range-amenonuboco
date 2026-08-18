# BACnet/IP のデバイス役と監視役を1つのイメージで兼ねる。
# MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで実装している(理由は run.py の
# docstring 参照)。そのため pip install が無く、ビルドが速い。
FROM python:3.10-slim

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
