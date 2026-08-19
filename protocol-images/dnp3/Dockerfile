# DNP3 (IEEE 1815) のアウトステーション（機器役）とマスタ（監視役）を1つの
# イメージで兼ねる。MODE 環境変数で役割を切り替える(使い方は docs/protocol-assets.md)。
#
# 外部ライブラリを使わず標準ライブラリだけで完結する。DNP3のPython実装は
# 薄く、C++バインディングを要するものが多いため、必要なサービスに限って
# 生のバイト列でフレームを組む方が、依存も再現性も軽い。
FROM python:3.10-slim

COPY run.py /app/run.py

# 資産の起動コマンド(overrides.command)を書かない場合の既定。
CMD ["python3", "/app/run.py"]
