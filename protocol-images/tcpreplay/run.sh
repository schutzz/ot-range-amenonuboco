#!/bin/sh
set -eu

# --loop=0 はコンテナ停止まで連続再生する。終了時の "Actual: ... packets"
# 統計をrun_benchmark.pyが読み取り、送信確認数として使う。
exec tcpreplay \
  --intf1="${TCREPLAY_INTERFACE:-eth0}" \
  --pps="${TCREPLAY_PPS:-5000}" \
  --loop="${TCREPLAY_LOOP:-0}" \
  --stats=1 \
  /app/l2_flood.pcap
