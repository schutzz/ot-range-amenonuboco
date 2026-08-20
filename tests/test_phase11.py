"""Phase 11 Stage 1 向け配線テスト。

新規プロトコル資産と暗号鍵注入・Lua プラグインマウント機構が、
Compose 生成物へ正しく配線されることを保証する。
"""

from __future__ import annotations

import pytest
import yaml

from generators.compose import generate_compose
from schema.topology import Manifest



def _load_manifest_from_string(yaml_str: str) -> Manifest:
    raw = yaml.safe_load(yaml_str)
    return Manifest.model_validate(raw)


# ---------------------------------------------------------------------------
# FINS / MQTT 配線テスト (Stage 1A)
# ---------------------------------------------------------------------------

_FINS_MQTT_YAML = """
apiVersion: amenonuboco/v1alpha1
kind: CyberRange
metadata:
  name: fins-mqtt-test
topology:
  segments:
    - { name: it_lan, cidr: 10.0.10.0/24, kind: it-core }
    - { name: ot_lan, cidr: 10.0.20.0/24, kind: ot-lan }
    - { name: mirror_link, cidr: 10.0.99.0/24, kind: observation }
  routing:
    gateway: router
  assets:
    - name: router
      role: l3-router
      image: debian:bullseye-slim
      networks:
        - { segment: it_lan, ip: 10.0.10.254 }
        - { segment: ot_lan, ip: 10.0.20.254 }
        - { segment: mirror_link, ip: 10.0.99.254 }
    - name: fins_plc
      role: ot-asset
      image: ../protocol-images/fins
      networks:
        - { segment: ot_lan, ip: 10.0.20.10 }
    - name: mqtt_broker
      role: ot-asset
      image: ../protocol-images/mqtt
      networks:
        - { segment: ot_lan, ip: 10.0.20.20 }
    - name: structurer
      role: structurer
      image: debian:bullseye-slim
      networks:
        - { segment: mirror_link, ip: 10.0.99.60 }
        - { segment: it_lan, ip: 10.0.10.60 }

instrumentation:
  mirror_to: mirror_link

structuring:
  engine: tshark
  protocols:
    - { name: omron, output_index: ot-logs-fins-* }
    - { name: mqtt, output_index: ot-logs-mqtt-* }
"""


def test_compose_wiring_fins_and_mqtt(presets):
    """FINS と MQTT の tshark パイプラインが生成されること。"""
    manifest = _load_manifest_from_string(_FINS_MQTT_YAML)
    compose = generate_compose(manifest, presets)

    structurer_cmd = compose["services"]["structurer"]["command"]
    
    assert 'tshark -i $$STRUCT_IF -T ek -Y "omron"' in structurer_cmd
    assert 'tshark -i $$STRUCT_IF -T ek -Y "mqtt"' in structurer_cmd
    assert 'ot-logs-fins-*' in structurer_cmd
    assert 'ot-logs-mqtt-*' in structurer_cmd


# ---------------------------------------------------------------------------
# 暗号鍵注入 / Lua プラグイン 配線テスト (Stage 1B/1C)
# ---------------------------------------------------------------------------

_CRYPTO_LUA_YAML = """
apiVersion: amenonuboco/v1alpha1
kind: CyberRange
metadata:
  name: crypto-lua-test
topology:
  segments:
    - { name: it_lan, cidr: 10.0.10.0/24, kind: it-core }
    - { name: ot_lan, cidr: 10.0.20.0/24, kind: ot-lan }
    - { name: mirror_link, cidr: 10.0.99.0/24, kind: observation }
  routing:
    gateway: router
  assets:
    - name: router
      role: l3-router
      image: debian:bullseye-slim
      networks:
        - { segment: it_lan, ip: 10.0.10.254 }
        - { segment: ot_lan, ip: 10.0.20.254 }
        - { segment: mirror_link, ip: 10.0.99.254 }
    - name: secsgem_equip
      role: ot-asset
      image: ../protocol-images/secsgem
      networks:
        - { segment: ot_lan, ip: 10.0.20.10 }
    - name: melsec_plc
      role: ot-asset
      image: ../protocol-images/melsec
      networks:
        - { segment: ot_lan, ip: 10.0.20.20 }
    - name: structurer
      role: structurer
      image: debian:bullseye-slim
      networks:
        - { segment: mirror_link, ip: 10.0.99.60 }
        - { segment: it_lan, ip: 10.0.10.60 }

instrumentation:
  mirror_to: mirror_link

structuring:
  engine: tshark
  protocols:
    - { name: hsms, output_index: ot-logs-hsms-* }
    - { name: "tcp.port == 5007", output_index: ot-logs-melsec-* }
  decryption:
    keylog_file: /var/log/amenonuboco/sslkeylog.log
    server_key: /var/log/amenonuboco/server.key
  dissector_plugins:
    - name: slmp-melsec
      host_path: /opt/amenonuboco/dissectors/slmp.lua
"""

def test_compose_wiring_tls_decryption(presets):
    """TLS 復号設定が tshark オプションおよびボリュームマウントとして配線されること。"""
    manifest = _load_manifest_from_string(_CRYPTO_LUA_YAML)
    compose = generate_compose(manifest, presets)

    svc = compose["services"]["structurer"]
    cmd = svc["command"]
    vols = svc.get("volumes", [])

    # コマンドへの配線（-o tls.keylog_file, -o tls.rsa_keys）
    assert '-o tls.keylog_file:/var/log/amenonuboco/sslkeylog.log' in cmd
    assert '-o tls.rsa_keys:/var/log/amenonuboco/server.key' in cmd

    # ボリュームマウントへの配線
    assert '/var/log/amenonuboco/sslkeylog.log:/var/log/amenonuboco/sslkeylog.log:ro' in vols
    assert '/var/log/amenonuboco/server.key:/var/log/amenonuboco/server.key:ro' in vols


def test_compose_wiring_melsec_lua_dissector(presets):
    """Lua プラグインが structurer コンテナの Wireshark プラグインディレクトリにマウントされること。"""
    manifest = _load_manifest_from_string(_CRYPTO_LUA_YAML)
    compose = generate_compose(manifest, presets)

    svc = compose["services"]["structurer"]
    vols = svc.get("volumes", [])

    expected_mount = '/opt/amenonuboco/dissectors/slmp.lua:/usr/lib/x86_64-linux-gnu/wireshark/plugins/slmp.lua:ro'
    assert expected_mount in vols
