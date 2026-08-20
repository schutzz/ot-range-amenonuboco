#!/usr/bin/env python3
"""MQTT / MQTTS プロトコル資産。

MODE 環境変数で役割を切り替える:
  broker  : Mosquitto ブローカーを起動する（センサーデータの中継点）
  client  : 工場センサー擬似クライアント。指定ブローカーへ周期的にパブリッシュし、
            関連トピックをサブスクライブする（両方を配置して初めて MQTT パケットが流れる）

環境変数:
    MODE        broker | client   （既定: broker）
    PORT        ブローカーポート   （既定: 1883、TLS 時は 8883）
    TARGET      ブローカー IP/ホスト（client 時のみ必須）
    INTERVAL    パブリッシュ間隔[秒]（既定: 5）
    TOPIC_ROOT  パブリッシュ先トピックのルート（既定: factory/line-a）
    TLS_ENABLE  true の場合 TLS を有効化（既定: false）
    SSLKEYLOGFILE 指定パスに TLS セッションキーを書き出す（TLS 時のみ有効）
                  演習用暗号鍵注入アーキテクチャ（Phase11 Stage1C）で使用。
    LABEL       ログに出す識別名   （既定: mqtt）

tshark の表示フィルタ: `mqtt`
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time
import threading
import signal
import json


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "mqtt")
TLS_ENABLE = env("TLS_ENABLE", "false").lower() == "true"
PORT = env_int("PORT", 8883 if TLS_ENABLE else 1883)
SSLKEYLOGFILE = env("SSLKEYLOGFILE", "")

MOSQUITTO_CONF = "/tmp/mosquitto_runtime.conf"
MOSQUITTO_CERT_DIR = "/tmp/mqtt_certs"


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


# ---------------------------------------------------------------------------
# TLS 証明書の自己署名生成（演習用）
# ---------------------------------------------------------------------------

def _generate_self_signed_cert() -> tuple[str, str, str]:
    """演習用自己署名 CA + サーバ証明書を生成して (ca_cert, srv_cert, srv_key) パスを返す。"""
    import subprocess
    os.makedirs(MOSQUITTO_CERT_DIR, exist_ok=True)
    ca_key = f"{MOSQUITTO_CERT_DIR}/ca.key"
    ca_cert = f"{MOSQUITTO_CERT_DIR}/ca.crt"
    srv_key = f"{MOSQUITTO_CERT_DIR}/server.key"
    srv_csr = f"{MOSQUITTO_CERT_DIR}/server.csr"
    srv_cert = f"{MOSQUITTO_CERT_DIR}/server.crt"

    subprocess.run(
        ["openssl", "genrsa", "-out", ca_key, "2048"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "req", "-new", "-x509", "-days", "365",
         "-key", ca_key, "-out", ca_cert,
         "-subj", "/CN=amenonuboco-mqtt-ca"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "genrsa", "-out", srv_key, "2048"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "req", "-new", "-key", srv_key, "-out", srv_csr,
         "-subj", "/CN=mqtt-broker"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "x509", "-req", "-days", "365",
         "-in", srv_csr, "-CA", ca_cert, "-CAkey", ca_key,
         "-CAcreateserial", "-out", srv_cert],
        check=True, capture_output=True,
    )
    return ca_cert, srv_cert, srv_key


# ---------------------------------------------------------------------------
# ブローカー（Mosquitto 起動）
# ---------------------------------------------------------------------------

def run_broker() -> None:
    # ランタイム用 mosquitto.conf を生成する
    conf_lines = [
        f"listener {PORT}",
        "allow_anonymous true",
        "log_dest stdout",
        "log_type all",
    ]

    if TLS_ENABLE:
        log("TLS が有効です。自己署名証明書を生成します...")
        try:
            ca_cert, srv_cert, srv_key = _generate_self_signed_cert()
            conf_lines += [
                f"cafile {ca_cert}",
                f"certfile {srv_cert}",
                f"keyfile {srv_key}",
                "tls_version tlsv1.2",
            ]
            log(f"MQTTS リスナー: port={PORT}")
        except Exception as exc:
            log(f"証明書生成失敗: {exc}。平文にフォールバックします")

    with open(MOSQUITTO_CONF, "w") as f:
        f.write("\n".join(conf_lines) + "\n")

    log(f"Mosquitto ブローカーを起動します (port={PORT}, tls={TLS_ENABLE})")
    proc = subprocess.Popen(["mosquitto", "-c", MOSQUITTO_CONF])

    def _on_signal(signum, frame):
        proc.terminate()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    ret = proc.wait()
    log(f"mosquitto exited with code {ret}")
    sys.exit(ret)


# ---------------------------------------------------------------------------
# クライアント（工場センサー役）
# ---------------------------------------------------------------------------

def run_client() -> None:
    import paho.mqtt.client as mqtt

    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=client では接続先IPが必須）")
        sys.exit(1)

    interval = env_int("INTERVAL", 5)
    topic_root = env("TOPIC_ROOT", "factory/line-a")

    log(f"connecting to {target}:{PORT} (tls={TLS_ENABLE})")

    client = mqtt.Client(client_id=f"{LABEL}-{random.randint(1000, 9999)}")

    if TLS_ENABLE:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        if SSLKEYLOGFILE:
            # Python 3.8+ で SSLKEYLOGFILE 相当を実装する
            # TLS セッションキーを書き出す（演習用鍵注入アーキテクチャ）
            orig_do_handshake = ctx.wrap_socket

            def _patched_wrap(*args, **kwargs):
                sock = orig_do_handshake(*args, **kwargs)
                try:
                    # Python 3.10+ では get_sslkeylogfile() 相当の API は無いため、
                    # SSLKEYLOGFILE 環境変数を Python プロセスレベルで設定することで
                    # OpenSSL 側に透過させる（Linux の LD_PRELOAD 不要）。
                    os.environ["SSLKEYLOGFILE"] = SSLKEYLOGFILE
                except Exception:
                    pass
                return sock
            ctx.wrap_socket = _patched_wrap  # type: ignore[method-assign]

        client.tls_set_context(ctx)

    subscribed_topics: list[str] = []

    def _on_connect(c, userdata, flags, rc):
        if rc == 0:
            log(f"connected to {target}:{PORT}")
            # センサー状態トピックをサブスクライブ（受信して流れを作る）
            topics = [
                f"{topic_root}/temperature/+",
                f"{topic_root}/pressure/+",
                f"{topic_root}/vibration/+",
            ]
            for t in topics:
                c.subscribe(t)
                subscribed_topics.append(t)
            log(f"subscribed: {topics}")
        else:
            log(f"connect failed: rc={rc}")

    def _on_message(c, userdata, msg):
        log(f"recv [{msg.topic}] {msg.payload.decode(errors='replace')}")

    client.on_connect = _on_connect
    client.on_message = _on_message

    # 最初の接続はリトライありで待つ
    while True:
        try:
            client.connect(target, PORT, keepalive=60)
            break
        except OSError as exc:
            log(f"connect failed: {exc}, retrying in {interval}s")
            time.sleep(interval)

    client.loop_start()

    # センサーデータ定期パブリッシュ（工場センサー擬似送信）
    sensors = {
        "temperature": {"unit": "C", "min": 20.0, "max": 85.0},
        "pressure": {"unit": "kPa", "min": 100.0, "max": 800.0},
        "vibration": {"unit": "mm/s", "min": 0.0, "max": 50.0},
    }
    sensor_ids = ["sensor-01", "sensor-02", "sensor-03"]

    while True:
        for stype, props in sensors.items():
            for sid in sensor_ids:
                value = round(
                    random.uniform(props["min"], props["max"]), 2
                )
                payload = json.dumps({
                    "sensor_id": sid,
                    "type": stype,
                    "value": value,
                    "unit": props["unit"],
                    "ts": int(time.time()),
                })
                topic = f"{topic_root}/{stype}/{sid}"
                client.publish(topic, payload, qos=1)
                log(f"publish [{topic}] {payload}")
        time.sleep(interval)


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> None:
    mode = env("MODE", "broker").lower()
    if mode == "broker":
        run_broker()
    elif mode == "client":
        run_client()
    else:
        log(f"未知の MODE '{mode}'（broker または client を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()
