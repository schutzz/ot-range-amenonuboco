// 自動生成ファイル — 手で編集しないこと。
// 生成元: platform/tools/gen_gui_vocab.py
// 3分野のリファレンスマニフェストを編集モデル形式で同梱したもの。
window.AMENONUBOCO_SAMPLES = [
  {
    "group": "実演あり",
    "id": "power-grid-reference",
    "label": "電力",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "前身プロジェクト ot-ids-verum の電力網ラボの代表要素を1枚に凝縮したリファレンススライス",
        "name": "power-grid-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "http",
            "output_index": "ot-logs-http-*"
          },
          {
            "name": "dnp3",
            "output_index": "ot-logs-dnp3-*"
          },
          {
            "name": "opcua",
            "output_index": "ot-logs-opcua-*"
          },
          {
            "name": "snmp",
            "output_index": "ot-logs-snmp-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.1.10.254",
                "segment": "cc_lan"
              },
              {
                "ip": "172.18.0.254",
                "segment": "wan_link"
              },
              {
                "ip": "10.1.30.254",
                "segment": "sub_b_lan"
              },
              {
                "ip": "10.1.20.254",
                "segment": "sub_a_l2_lan"
              },
              {
                "ip": "10.1.99.254",
                "segment": "mirror_link"
              },
              {
                "ip": "10.1.40.254",
                "segment": "sub_c_lan"
              },
              {
                "ip": "10.1.50.254",
                "segment": "sub_d_l2_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "cc_scada_master",
            "networks": [
              {
                "ip": "10.1.10.10",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( MODE=outstation DEVICE_ID=10 LABEL=cc_scada_master_rx python3 /app/run.py &\n  MODE=master TARGET=10.1.40.10 DEVICE_ID=1 PEER_ID=20 INTERVAL=8 LABEL=cc_scada_master_poll python3 /app/run.py &\n  wait )\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "nodered/node-red:3.1.0",
            "name": "sub_b_rtu_hmi",
            "networks": [
              {
                "ip": "10.1.30.10",
                "segment": "sub_b_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "/usr/src/node-red/entrypoint.sh",
              "environment": [],
              "ports": [
                "18800:1880"
              ],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "sub_a_ied_02",
            "networks": [
              {
                "ip": "10.1.20.11",
                "segment": "sub_a_l2_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "tail -f /dev/null",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "attacker-insider"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "sub_c_rtu",
            "networks": [
              {
                "ip": "10.1.40.10",
                "segment": "sub_c_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=outstation",
                "LABEL=sub_c_rtu",
                "DEVICE_ID=20",
                "POINTS=4"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "nodered/node-red:3.1.0",
            "name": "sub_c_hmi",
            "networks": [
              {
                "ip": "10.1.40.11",
                "segment": "sub_c_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "/usr/src/node-red/entrypoint.sh",
              "environment": [],
              "ports": [
                "18801:1880"
              ],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "ups_attacker",
            "networks": [
              {
                "ip": "172.18.0.50",
                "segment": "wan_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq snmp >/dev/null 2>&1 &&\n( for i in 1 2 3 4 5 6; do\n    sleep 15\n    snmpset -v2c -c public -t 5 -r 2 10.1.10.95:161 1.3.6.1.2.1.1.6.0 s 'UNAUTHORIZED_SHUTDOWN_COMMAND_INJECTED' 2>&1\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "attacker-external"
          },
          {
            "image": "python:3.10-slim",
            "name": "sub_d_ied_01",
            "networks": [
              {
                "ip": "10.1.50.11",
                "segment": "sub_d_l2_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "tail -f /dev/null",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "timberio/vector:0.46.0-alpine",
            "name": "vector",
            "networks": [
              {
                "ip": "10.1.10.35",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.1.10.40",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "curlimages/curl:latest",
            "name": "es_enrich_refresher",
            "networks": [
              {
                "ip": null,
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "while true; do curl -s -X POST http://elasticsearch:9200/_enrich/policy/detection_lookup_policy/_execute; sleep 60; done",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.1.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.1.10.60",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          },
          {
            "image": "python:3.11-slim",
            "name": "killchain_detector",
            "networks": [
              {
                "ip": "10.1.10.80",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "python:3.11-slim",
            "name": "zone_detector",
            "networks": [
              {
                "ip": "10.1.10.81",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "python:3.11-slim",
            "name": "eval_harness",
            "networks": [
              {
                "ip": "10.1.10.90",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "tail -f /dev/null",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "eval-harness"
          },
          {
            "image": "python:3.11-slim",
            "name": "caldera_server",
            "networks": [
              {
                "ip": "10.1.10.70",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "ls -la /app/caldera_assets/abilities /app/caldera_assets/adversaries && tail -f /dev/null",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "attack-engine"
          },
          {
            "image": "grafana/grafana:11.1.0",
            "name": "grafana_server",
            "networks": [
              {
                "ip": "10.1.10.72",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "visualization-engine"
          },
          {
            "image": "python:3.10-slim",
            "name": "historian",
            "networks": [
              {
                "ip": "10.1.10.15",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 4840 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "cc_ups",
            "networks": [
              {
                "ip": "10.1.10.95",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq snmpd snmp >/dev/null 2>&1 &&\nprintf 'rwcommunity public\\nsysLocation Central Control Room UPS (normal)\\n' > /etc/snmp/snmpd.conf &&\n( snmpd -f -Lf /var/log/snmpd.log &\n  sleep 3\n  tail -F /var/log/snmpd.log | while read LINE; do\n    case $LINE in\n      *'Connection from UDP'*127.0.0.1*127.0.0.1*) : ;;\n      *'Connection from UDP'*)\n        echo '[cc_ups] !!! UNAUTHORIZED SNMP ACCESS FROM NON-LOCAL SOURCE DETECTED -- SIMULATING UPS SHUTDOWN (AVAILABILITY LOSS) !!!' ;;\n    esac\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.1.10.0/24",
            "kind": "it-core",
            "name": "cc_lan"
          },
          {
            "cidr": "172.18.0.0/24",
            "kind": "wan-edge",
            "name": "wan_link"
          },
          {
            "cidr": "10.1.30.0/24",
            "kind": "ot-lan",
            "name": "sub_b_lan"
          },
          {
            "cidr": "10.1.20.0/24",
            "kind": "ot-l2",
            "name": "sub_a_l2_lan"
          },
          {
            "cidr": "10.1.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          },
          {
            "cidr": "10.1.40.0/24",
            "kind": "ot-lan",
            "name": "sub_c_lan"
          },
          {
            "cidr": "10.1.50.0/24",
            "kind": "ot-l2",
            "name": "sub_d_l2_lan"
          }
        ]
      }
    }
  },
  {
    "group": "実演あり",
    "id": "water-utility-reference",
    "label": "上下水道",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "上下水道分野のリファレンススライス。Oldsmar浄水場事件型(正規リモートアクセス経路の悪用)を主軸実演とする",
        "name": "water-utility-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "vnc",
            "output_index": "ot-logs-vnc-*"
          },
          {
            "name": "modbus",
            "output_index": "ot-logs-modbus-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.2.10.254",
                "segment": "wtp_cc_lan"
              },
              {
                "ip": "172.19.0.254",
                "segment": "wan_link"
              },
              {
                "ip": "10.2.20.254",
                "segment": "pump_station_a_lan"
              },
              {
                "ip": "10.2.30.254",
                "segment": "pump_station_b_lan"
              },
              {
                "ip": "10.2.40.254",
                "segment": "remote_access_dmz"
              },
              {
                "ip": "10.2.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "python:3.10-slim",
            "name": "wtp_scada_master",
            "networks": [
              {
                "ip": "10.2.10.10",
                "segment": "wtp_cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 8080 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "pump_a_plc",
            "networks": [
              {
                "ip": "10.2.20.10",
                "segment": "pump_station_a_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 502 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "pump_b_hmi",
            "networks": [
              {
                "ip": "10.2.30.10",
                "segment": "pump_station_b_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq xvfb x11vnc xterm >/dev/null 2>&1 &&\n( Xvfb :1 -screen 0 800x600x16 &\n  sleep 2\n  DISPLAY=:1 xterm -fa Monospace -fs 16 -e sh -c 'echo NaOH_SETPOINT_PPM=100 normal; sleep 100000' &\n  sleep 1\n  x11vnc -display :1 -nopw -forever -shared -rfbport 5900 -bg -o /var/log/x11vnc.log &&\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "remote_access_gateway",
            "networks": [
              {
                "ip": "10.2.40.11",
                "segment": "remote_access_dmz"
              },
              {
                "ip": "10.2.30.11",
                "segment": "pump_station_b_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq socat >/dev/null 2>&1 &&\n( socat -d -d -lf /var/log/socat.log TCP-LISTEN:5900,fork,reuseaddr TCP:10.2.30.10:5900 &\n  sleep 2\n  tail -F /var/log/socat.log | while read LINE; do\n    case $LINE in\n      *'accepting connection'*)\n        echo '[remote_access_gateway] !!! REMOTE ACCESS SESSION VIA DMZ ESTABLISHED (OLDSMAR-TYPE CHANNEL) !!!' ;;\n    esac\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "remote-access-gateway"
          },
          {
            "image": "python:3.10-slim",
            "name": "attacker_external",
            "networks": [
              {
                "ip": "172.19.0.50",
                "segment": "wan_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq gcc python3-dev >/dev/null 2>&1 &&\npip install --quiet vncdotool >/dev/null 2>&1 &&\n( for i in 1 2 3 4 5; do\n    sleep 15\n    vncdo -s 10.2.40.11::5900 -v -t 10 type '11100' 2>&1\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "attacker-external"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.2.10.40",
                "segment": "wtp_cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.2.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.2.10.60",
                "segment": "wtp_cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.2.10.0/24",
            "kind": "it-core",
            "name": "wtp_cc_lan"
          },
          {
            "cidr": "172.19.0.0/24",
            "kind": "wan-edge",
            "name": "wan_link"
          },
          {
            "cidr": "10.2.20.0/24",
            "kind": "ot-lan",
            "name": "pump_station_a_lan"
          },
          {
            "cidr": "10.2.30.0/24",
            "kind": "ot-lan",
            "name": "pump_station_b_lan"
          },
          {
            "cidr": "10.2.40.0/24",
            "kind": "dmz",
            "name": "remote_access_dmz"
          },
          {
            "cidr": "10.2.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "実演あり",
    "id": "manufacturing-plant-reference",
    "label": "重要製造業",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "重要製造業分野のリファレンススライス。監視カメラ経由の横展開(物理セキュリティ網→OTフロア)を主軸実演とする",
        "name": "manufacturing-plant-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "enip",
            "output_index": "ot-logs-enip-*"
          },
          {
            "name": "http",
            "output_index": "ot-logs-http-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.3.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.3.15.254",
                "segment": "mes_dmz"
              },
              {
                "ip": "10.3.20.254",
                "segment": "production_line_a_lan"
              },
              {
                "ip": "10.3.30.254",
                "segment": "production_line_b_lan"
              },
              {
                "ip": "10.3.40.254",
                "segment": "physical_security_lan"
              },
              {
                "ip": "10.3.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "python:3.10-slim",
            "name": "mes_server",
            "networks": [
              {
                "ip": "10.3.15.10",
                "segment": "mes_dmz"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 8080 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "line_a_plc",
            "networks": [
              {
                "ip": "10.3.20.10",
                "segment": "production_line_a_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 44818 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "line_b_robot_controller",
            "networks": [
              {
                "ip": "10.3.30.10",
                "segment": "production_line_b_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq socat >/dev/null 2>&1 &&\n( socat -d -d -lf /var/log/socat.log TCP-LISTEN:44818,fork,reuseaddr STDOUT &\n  sleep 2\n  tail -F /var/log/socat.log | while read LINE; do\n    case $LINE in\n      *'accepting connection'*)\n        echo '[line_b_robot_controller] !!! UNEXPECTED CONNECTION FROM PHYSICAL SECURITY SEGMENT DETECTED (LATERAL MOVEMENT) !!!' ;;\n    esac\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "nvr_server",
            "networks": [
              {
                "ip": "10.3.40.10",
                "segment": "physical_security_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 80 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "security-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "access_control_panel",
            "networks": [
              {
                "ip": "10.3.40.11",
                "segment": "physical_security_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 80 & wait )",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "security-asset"
          },
          {
            "image": "python:3.10-slim",
            "name": "attacker_internal",
            "networks": [
              {
                "ip": "10.3.40.50",
                "segment": "physical_security_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq socat >/dev/null 2>&1 &&\n( for i in 1 2 3 4 5; do\n    sleep 15\n    echo BAAAAAAAAAAAAAAAUElWT1QhISEAAAAA | base64 -d | socat - TCP:10.3.30.10:44818,connect-timeout=5\n  done\n  wait\n)\n",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "attacker-internal"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.3.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.3.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.3.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.3.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.3.15.0/24",
            "kind": "dmz",
            "name": "mes_dmz"
          },
          {
            "cidr": "10.3.20.0/24",
            "kind": "ot-lan",
            "name": "production_line_a_lan"
          },
          {
            "cidr": "10.3.30.0/24",
            "kind": "ot-lan",
            "name": "production_line_b_lan"
          },
          {
            "cidr": "10.3.40.0/24",
            "kind": "security-lan",
            "name": "physical_security_lan"
          },
          {
            "cidr": "10.3.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "chemical-plant-reference",
    "label": "化学",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "化学分野の器。バッチプラント(反応器・計装ループ・DCS)をModbus/TCPとOPC UAで構成する",
        "name": "chemical-plant-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "modbus",
            "output_index": "ot-logs-modbus-*"
          },
          {
            "name": "opcua",
            "output_index": "ot-logs-opcua-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.4.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.4.15.254",
                "segment": "plant_dmz"
              },
              {
                "ip": "10.4.20.254",
                "segment": "process_control_lan"
              },
              {
                "ip": "10.4.30.254",
                "segment": "field_instrument_lan"
              },
              {
                "ip": "10.4.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "reactor_plc",
            "networks": [
              {
                "ip": "10.4.30.10",
                "segment": "field_instrument_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=reactor_plc",
                "REGISTERS=64"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/opcua",
            "name": "jacket_temp_controller",
            "networks": [
              {
                "ip": "10.4.30.11",
                "segment": "field_instrument_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=jacket_temp"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "batch_control_station",
            "networks": [
              {
                "ip": "10.4.20.10",
                "segment": "process_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=batch_control",
                "TARGET=10.4.30.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/opcua",
            "name": "dcs_operator_station",
            "networks": [
              {
                "ip": "10.4.20.11",
                "segment": "process_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=dcs_operator",
                "TARGET=10.4.30.11",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/opcua",
            "name": "plant_historian",
            "networks": [
              {
                "ip": "10.4.15.10",
                "segment": "plant_dmz"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=historian",
                "TARGET=10.4.30.11",
                "INTERVAL=10"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.4.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.4.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.4.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.4.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.4.15.0/24",
            "kind": "dmz",
            "name": "plant_dmz"
          },
          {
            "cidr": "10.4.20.0/24",
            "kind": "ot-lan",
            "name": "process_control_lan"
          },
          {
            "cidr": "10.4.30.0/24",
            "kind": "ot-lan",
            "name": "field_instrument_lan"
          },
          {
            "cidr": "10.4.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "building-automation-reference",
    "label": "商業施設",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "商業施設分野の器。商業ビルの建物管理(空調・照明・入退室)をBACnet/IPで構成する",
        "name": "building-automation-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "bacapp",
            "output_index": "ot-logs-bacnet-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.5.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.5.20.254",
                "segment": "bms_lan"
              },
              {
                "ip": "10.5.30.254",
                "segment": "floor_hvac_lan"
              },
              {
                "ip": "10.5.40.254",
                "segment": "floor_lighting_lan"
              },
              {
                "ip": "10.5.50.254",
                "segment": "access_control_lan"
              },
              {
                "ip": "10.5.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "ahu_controller",
            "networks": [
              {
                "ip": "10.5.30.10",
                "segment": "floor_hvac_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=ahu_controller",
                "DEVICE_ID=3001"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "vav_controller",
            "networks": [
              {
                "ip": "10.5.30.11",
                "segment": "floor_hvac_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=vav_controller",
                "DEVICE_ID=3002"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "lighting_gateway",
            "networks": [
              {
                "ip": "10.5.40.10",
                "segment": "floor_lighting_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=lighting_gateway",
                "DEVICE_ID=4001"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "access_control_panel",
            "networks": [
              {
                "ip": "10.5.50.10",
                "segment": "access_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=access_panel",
                "DEVICE_ID=5001"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "security-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "bms_hvac_supervisor",
            "networks": [
              {
                "ip": "10.5.20.10",
                "segment": "bms_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=bms_hvac",
                "TARGET=10.5.30.10",
                "DEVICE_ID=3001",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "bms_lighting_scheduler",
            "networks": [
              {
                "ip": "10.5.20.11",
                "segment": "bms_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=bms_lighting",
                "TARGET=10.5.40.10",
                "DEVICE_ID=4001",
                "INTERVAL=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "bms_access_monitor",
            "networks": [
              {
                "ip": "10.5.20.12",
                "segment": "bms_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=bms_access",
                "TARGET=10.5.50.10",
                "DEVICE_ID=5001",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.5.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.5.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.5.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.5.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.5.20.0/24",
            "kind": "ot-lan",
            "name": "bms_lan"
          },
          {
            "cidr": "10.5.30.0/24",
            "kind": "ot-lan",
            "name": "floor_hvac_lan"
          },
          {
            "cidr": "10.5.40.0/24",
            "kind": "ot-lan",
            "name": "floor_lighting_lan"
          },
          {
            "cidr": "10.5.50.0/24",
            "kind": "security-lan",
            "name": "access_control_lan"
          },
          {
            "cidr": "10.5.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "telecom-core-reference",
    "label": "通信",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "通信分野の器。通信事業者網(コア・アクセス・OSS/NMS)をSNMPとSIPで構成する",
        "name": "telecom-core-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "snmp",
            "output_index": "ot-logs-snmp-*"
          },
          {
            "name": "sip",
            "output_index": "ot-logs-sip-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.6.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.6.15.254",
                "segment": "oss_lan"
              },
              {
                "ip": "10.6.20.254",
                "segment": "core_transport_lan"
              },
              {
                "ip": "10.6.30.254",
                "segment": "access_edge_lan"
              },
              {
                "ip": "10.6.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "core_router_mgmt",
            "networks": [
              {
                "ip": "10.6.20.10",
                "segment": "core_transport_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=agent",
                "LABEL=core_router",
                "SYSNAME=core-router-01",
                "SYSLOCATION=Core Site A"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "edge_access_node_mgmt",
            "networks": [
              {
                "ip": "10.6.30.10",
                "segment": "access_edge_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=agent",
                "LABEL=edge_node",
                "SYSNAME=access-node-07",
                "SYSLOCATION=Edge Site B"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "nms_core_poller",
            "networks": [
              {
                "ip": "10.6.15.10",
                "segment": "oss_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=poller",
                "LABEL=nms_core",
                "TARGET=10.6.20.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "nms_edge_poller",
            "networks": [
              {
                "ip": "10.6.15.11",
                "segment": "oss_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=poller",
                "LABEL=nms_edge",
                "TARGET=10.6.30.10",
                "INTERVAL=7"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/sip",
            "name": "softswitch",
            "networks": [
              {
                "ip": "10.6.20.20",
                "segment": "core_transport_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=uas",
                "LABEL=softswitch",
                "USER=pbx"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/sip",
            "name": "subscriber_phone",
            "networks": [
              {
                "ip": "10.6.30.20",
                "segment": "access_edge_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=uac",
                "LABEL=subscriber",
                "TARGET=10.6.20.20",
                "USER=phone1",
                "INTERVAL=10"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.6.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.6.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.6.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.6.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.6.15.0/24",
            "kind": "dmz",
            "name": "oss_lan"
          },
          {
            "cidr": "10.6.20.0/24",
            "kind": "ot-lan",
            "name": "core_transport_lan"
          },
          {
            "cidr": "10.6.30.0/24",
            "kind": "ot-lan",
            "name": "access_edge_lan"
          },
          {
            "cidr": "10.6.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "dam-control-reference",
    "label": "ダム",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "ダム分野の器。治水ダム(ゲート制御・水位計・遠隔監視所)をModbus/TCPとDNP3で構成する",
        "name": "dam-control-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "modbus",
            "output_index": "ot-logs-modbus-*"
          },
          {
            "name": "dnp3",
            "output_index": "ot-logs-dnp3-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.7.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.7.20.254",
                "segment": "scada_lan"
              },
              {
                "ip": "10.7.30.254",
                "segment": "gate_control_lan"
              },
              {
                "ip": "10.7.40.254",
                "segment": "remote_site_lan"
              },
              {
                "ip": "10.7.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "spillway_gate_plc",
            "networks": [
              {
                "ip": "10.7.30.10",
                "segment": "gate_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=spillway_gate",
                "REGISTERS=16"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "gate_rtu",
            "networks": [
              {
                "ip": "10.7.30.11",
                "segment": "gate_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=outstation",
                "LABEL=gate_rtu",
                "DEVICE_ID=20",
                "POINTS=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "reservoir_level_rtu",
            "networks": [
              {
                "ip": "10.7.40.10",
                "segment": "remote_site_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=outstation",
                "LABEL=level_rtu",
                "DEVICE_ID=30",
                "POINTS=4"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "gate_control_master",
            "networks": [
              {
                "ip": "10.7.20.10",
                "segment": "scada_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=gate_master",
                "TARGET=10.7.30.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "scada_master_dnp3",
            "networks": [
              {
                "ip": "10.7.20.11",
                "segment": "scada_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=master",
                "LABEL=scada_master",
                "TARGET=10.7.30.11",
                "DEVICE_ID=1",
                "PEER_ID=20",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "remote_site_poller",
            "networks": [
              {
                "ip": "10.7.20.12",
                "segment": "scada_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=master",
                "LABEL=remote_poller",
                "TARGET=10.7.40.10",
                "DEVICE_ID=2",
                "PEER_ID=30",
                "INTERVAL=10"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.7.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.7.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.7.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.7.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.7.20.0/24",
            "kind": "ot-lan",
            "name": "scada_lan"
          },
          {
            "cidr": "10.7.30.0/24",
            "kind": "ot-lan",
            "name": "gate_control_lan"
          },
          {
            "cidr": "10.7.40.0/24",
            "kind": "ot-lan",
            "name": "remote_site_lan"
          },
          {
            "cidr": "10.7.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "food-processing-reference",
    "label": "食品・農業",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "食品・農業分野の器。食品工場(充填ライン・冷蔵倉庫・CIP洗浄)をModbus/TCPとOPC UAで構成する",
        "name": "food-processing-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "modbus",
            "output_index": "ot-logs-modbus-*"
          },
          {
            "name": "opcua",
            "output_index": "ot-logs-opcua-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.8.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.8.15.254",
                "segment": "mes_dmz"
              },
              {
                "ip": "10.8.20.254",
                "segment": "filling_line_lan"
              },
              {
                "ip": "10.8.30.254",
                "segment": "cold_storage_lan"
              },
              {
                "ip": "10.8.40.254",
                "segment": "cip_lan"
              },
              {
                "ip": "10.8.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "filler_plc",
            "networks": [
              {
                "ip": "10.8.20.10",
                "segment": "filling_line_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=filler_plc",
                "REGISTERS=32"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "cold_storage_plc",
            "networks": [
              {
                "ip": "10.8.30.10",
                "segment": "cold_storage_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=cold_storage",
                "REGISTERS=16"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/opcua",
            "name": "cip_skid",
            "networks": [
              {
                "ip": "10.8.40.10",
                "segment": "cip_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=cip_skid"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "line_supervisor",
            "networks": [
              {
                "ip": "10.8.15.10",
                "segment": "mes_dmz"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=line_supervisor",
                "TARGET=10.8.20.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "cold_chain_monitor",
            "networks": [
              {
                "ip": "10.8.15.11",
                "segment": "mes_dmz"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=cold_chain",
                "TARGET=10.8.30.10",
                "INTERVAL=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/opcua",
            "name": "mes_server",
            "networks": [
              {
                "ip": "10.8.15.12",
                "segment": "mes_dmz"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=mes_server",
                "TARGET=10.8.40.10",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.8.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.8.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.8.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.8.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.8.15.0/24",
            "kind": "dmz",
            "name": "mes_dmz"
          },
          {
            "cidr": "10.8.20.0/24",
            "kind": "ot-lan",
            "name": "filling_line_lan"
          },
          {
            "cidr": "10.8.30.0/24",
            "kind": "ot-lan",
            "name": "cold_storage_lan"
          },
          {
            "cidr": "10.8.40.0/24",
            "kind": "ot-lan",
            "name": "cip_lan"
          },
          {
            "cidr": "10.8.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ",
    "id": "hospital-network-reference",
    "label": "医療",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "医療分野の器。病院network(画像系・電子カルテ・生体モニタ)をDICOMとHL7で構成する",
        "name": "hospital-network-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "dicom",
            "output_index": "ot-logs-dicom-*"
          },
          {
            "name": "hl7",
            "output_index": "ot-logs-hl7-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.9.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.9.20.254",
                "segment": "clinical_lan"
              },
              {
                "ip": "10.9.30.254",
                "segment": "imaging_lan"
              },
              {
                "ip": "10.9.40.254",
                "segment": "biomed_lan"
              },
              {
                "ip": "10.9.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/dicom",
            "name": "pacs_server",
            "networks": [
              {
                "ip": "10.9.20.10",
                "segment": "clinical_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=scp",
                "LABEL=pacs",
                "AE_TITLE=RANGE_PACS"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/hl7",
            "name": "emr_server",
            "networks": [
              {
                "ip": "10.9.20.11",
                "segment": "clinical_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=receiver",
                "LABEL=emr",
                "APP=EMR"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dicom",
            "name": "ct_scanner",
            "networks": [
              {
                "ip": "10.9.30.10",
                "segment": "imaging_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=scu",
                "LABEL=ct",
                "TARGET=10.9.20.10",
                "AE_TITLE=RANGE_CT",
                "PEER_AE=RANGE_PACS",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dicom",
            "name": "mr_scanner",
            "networks": [
              {
                "ip": "10.9.30.11",
                "segment": "imaging_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=scu",
                "LABEL=mr",
                "TARGET=10.9.20.10",
                "AE_TITLE=RANGE_MR",
                "PEER_AE=RANGE_PACS",
                "INTERVAL=9"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/hl7",
            "name": "patient_monitor",
            "networks": [
              {
                "ip": "10.9.40.10",
                "segment": "biomed_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=sender",
                "LABEL=monitor",
                "TARGET=10.9.20.11",
                "APP=MONITOR",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/hl7",
            "name": "lab_analyzer",
            "networks": [
              {
                "ip": "10.9.40.11",
                "segment": "biomed_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=sender",
                "LABEL=lab",
                "TARGET=10.9.20.11",
                "APP=LAB",
                "INTERVAL=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.9.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.9.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.9.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.9.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.9.20.0/24",
            "kind": "ot-lan",
            "name": "clinical_lan"
          },
          {
            "cidr": "10.9.30.0/24",
            "kind": "ot-lan",
            "name": "imaging_lan"
          },
          {
            "cidr": "10.9.40.0/24",
            "kind": "ot-lan",
            "name": "biomed_lan"
          },
          {
            "cidr": "10.9.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "nuclear-plant-reference",
    "label": "原子力",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "safety_system_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "原子力分野の器。バランスオブプラント系を観測し、安全保護系を構造的な死角として描く",
        "name": "nuclear-plant-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "modbus",
            "output_index": "ot-logs-modbus-*"
          },
          {
            "name": "dnp3",
            "output_index": "ot-logs-dnp3-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.10.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.10.20.254",
                "segment": "bop_control_lan"
              },
              {
                "ip": "10.10.30.254",
                "segment": "turbine_aux_lan"
              },
              {
                "ip": "10.10.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "feedwater_pump_plc",
            "networks": [
              {
                "ip": "10.10.30.10",
                "segment": "turbine_aux_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=server",
                "LABEL=feedwater_pump",
                "REGISTERS=32"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "condenser_rtu",
            "networks": [
              {
                "ip": "10.10.30.11",
                "segment": "turbine_aux_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=outstation",
                "LABEL=condenser_rtu",
                "DEVICE_ID=40",
                "POINTS=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "bop_control_station",
            "networks": [
              {
                "ip": "10.10.20.10",
                "segment": "bop_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=bop_control",
                "TARGET=10.10.30.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/dnp3",
            "name": "bop_scada_master",
            "networks": [
              {
                "ip": "10.10.20.11",
                "segment": "bop_control_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=master",
                "LABEL=bop_scada",
                "TARGET=10.10.30.11",
                "DEVICE_ID=1",
                "PEER_ID=40",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "rps_train_a",
            "networks": [
              {
                "ip": "10.10.50.10",
                "segment": "safety_system_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=server",
                "LABEL=rps_train_a"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "rps_train_b",
            "networks": [
              {
                "ip": "10.10.50.11",
                "segment": "safety_system_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=client",
                "LABEL=rps_train_b",
                "TARGET=10.10.50.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.10.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.10.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.10.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.10.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.10.20.0/24",
            "kind": "ot-lan",
            "name": "bop_control_lan"
          },
          {
            "cidr": "10.10.30.0/24",
            "kind": "ot-lan",
            "name": "turbine_aux_lan"
          },
          {
            "cidr": "10.10.50.0/24",
            "kind": "ot-l2",
            "name": "safety_system_lan"
          },
          {
            "cidr": "10.10.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "rail-transit-reference",
    "label": "輸送",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "signalling_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "輸送分野の器。駅務・旅客設備系を観測し、信号保安系をdissector不在の死角として描く",
        "name": "rail-transit-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "bacapp",
            "output_index": "ot-logs-bacnet-*"
          },
          {
            "name": "snmp",
            "output_index": "ot-logs-snmp-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.11.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.11.20.254",
                "segment": "station_facility_lan"
              },
              {
                "ip": "10.11.30.254",
                "segment": "passenger_info_lan"
              },
              {
                "ip": "10.11.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "station_hvac_controller",
            "networks": [
              {
                "ip": "10.11.20.10",
                "segment": "station_facility_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=station_hvac",
                "DEVICE_ID=1101"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "platform_display_gateway",
            "networks": [
              {
                "ip": "10.11.30.10",
                "segment": "passenger_info_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=agent",
                "LABEL=platform_display",
                "SYSNAME=platform-display-gw",
                "SYSLOCATION=Central Station Platform 3"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "facility_management_station",
            "networks": [
              {
                "ip": "10.11.30.20",
                "segment": "passenger_info_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=facility_mgmt",
                "TARGET=10.11.20.10",
                "DEVICE_ID=1101",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "network_monitoring_station",
            "networks": [
              {
                "ip": "10.11.20.20",
                "segment": "station_facility_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=poller",
                "LABEL=nms",
                "TARGET=10.11.30.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "interlocking_controller",
            "networks": [
              {
                "ip": "10.11.50.10",
                "segment": "signalling_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=server",
                "LABEL=interlocking"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "wayside_radio_unit",
            "networks": [
              {
                "ip": "10.11.50.11",
                "segment": "signalling_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=client",
                "LABEL=wayside_radio",
                "TARGET=10.11.50.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.11.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.11.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.11.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.11.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.11.20.0/24",
            "kind": "ot-lan",
            "name": "station_facility_lan"
          },
          {
            "cidr": "10.11.30.0/24",
            "kind": "ot-lan",
            "name": "passenger_info_lan"
          },
          {
            "cidr": "10.11.50.0/24",
            "kind": "ot-l2",
            "name": "signalling_lan"
          },
          {
            "cidr": "10.11.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "emergency-dispatch-reference",
    "label": "緊急サービス",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "p25_rf_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "緊急サービス分野の器。指令システム・IP系を観測し、P25デジタル無線を伝送媒体の違いによる死角として描く",
        "name": "emergency-dispatch-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "sip",
            "output_index": "ot-logs-sip-*"
          },
          {
            "name": "snmp",
            "output_index": "ot-logs-snmp-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.12.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.12.20.254",
                "segment": "dispatch_lan"
              },
              {
                "ip": "10.12.30.254",
                "segment": "radio_gateway_lan"
              },
              {
                "ip": "10.12.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/sip",
            "name": "dispatch_telephony_switch",
            "networks": [
              {
                "ip": "10.12.20.10",
                "segment": "dispatch_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=uas",
                "LABEL=dispatch_switch",
                "USER=dispatch"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "radio_gateway_mgmt",
            "networks": [
              {
                "ip": "10.12.30.10",
                "segment": "radio_gateway_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=agent",
                "LABEL=radio_gateway",
                "SYSNAME=p25-gateway-01",
                "SYSLOCATION=Dispatch Center"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/sip",
            "name": "dispatch_console",
            "networks": [
              {
                "ip": "10.12.30.20",
                "segment": "radio_gateway_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=uac",
                "LABEL=console",
                "TARGET=10.12.20.10",
                "USER=console1",
                "PEER_USER=dispatch",
                "INTERVAL=10"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "dispatch_nms",
            "networks": [
              {
                "ip": "10.12.20.20",
                "segment": "dispatch_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=poller",
                "LABEL=dispatch_nms",
                "TARGET=10.12.30.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "p25_base_station",
            "networks": [
              {
                "ip": "10.12.50.10",
                "segment": "p25_rf_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=server",
                "LABEL=p25_base"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "field_portable_radio",
            "networks": [
              {
                "ip": "10.12.50.11",
                "segment": "p25_rf_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=client",
                "LABEL=field_radio",
                "TARGET=10.12.50.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.12.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.12.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.12.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.12.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.12.20.0/24",
            "kind": "ot-lan",
            "name": "dispatch_lan"
          },
          {
            "cidr": "10.12.30.0/24",
            "kind": "ot-lan",
            "name": "radio_gateway_lan"
          },
          {
            "cidr": "10.12.50.0/24",
            "kind": "ot-l2",
            "name": "p25_rf_lan"
          },
          {
            "cidr": "10.12.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "defense-plant-reference",
    "label": "防衛産業基盤",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "classified_enclave_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "防衛産業基盤分野の器。一般製造区画を観測し、機密区画をエアギャップ分離による死角として描く",
        "name": "defense-plant-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "enip",
            "output_index": "ot-logs-enip-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.13.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.13.20.254",
                "segment": "production_lan"
              },
              {
                "ip": "10.13.30.254",
                "segment": "quality_assurance_lan"
              },
              {
                "ip": "10.13.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/enip",
            "name": "machining_cell_plc",
            "networks": [
              {
                "ip": "10.13.20.10",
                "segment": "production_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=adapter",
                "LABEL=machining_cell",
                "PRODUCT=Machining Cell Controller"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/enip",
            "name": "assembly_robot_controller",
            "networks": [
              {
                "ip": "10.13.20.11",
                "segment": "production_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=adapter",
                "LABEL=assembly_robot",
                "PRODUCT=Assembly Robot Controller"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/enip",
            "name": "qa_inspection_station",
            "networks": [
              {
                "ip": "10.13.30.10",
                "segment": "quality_assurance_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=scanner",
                "LABEL=qa_inspection",
                "TARGET=10.13.20.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/enip",
            "name": "qa_traceability_server",
            "networks": [
              {
                "ip": "10.13.30.11",
                "segment": "quality_assurance_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=scanner",
                "LABEL=qa_trace",
                "TARGET=10.13.20.11",
                "INTERVAL=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/enip",
            "name": "classified_cell_controller",
            "networks": [
              {
                "ip": "10.13.50.10",
                "segment": "classified_enclave_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=adapter",
                "LABEL=classified_cell",
                "PRODUCT=Enclave Controller"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/enip",
            "name": "classified_supervisor",
            "networks": [
              {
                "ip": "10.13.50.11",
                "segment": "classified_enclave_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=scanner",
                "LABEL=classified_supervisor",
                "TARGET=10.13.50.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.13.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.13.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.13.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.13.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.13.20.0/24",
            "kind": "ot-lan",
            "name": "production_lan"
          },
          {
            "cidr": "10.13.30.0/24",
            "kind": "ot-lan",
            "name": "quality_assurance_lan"
          },
          {
            "cidr": "10.13.50.0/24",
            "kind": "ot-l2",
            "name": "classified_enclave_lan"
          },
          {
            "cidr": "10.13.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "government-facility-reference",
    "label": "政府施設",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "classified_area_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "政府施設分野の器。庁舎設備系・物理セキュリティを観測し、機密取扱区画をエアギャップ分離による死角として描く",
        "name": "government-facility-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "bacapp",
            "output_index": "ot-logs-bacnet-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.14.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.14.20.254",
                "segment": "facility_bms_lan"
              },
              {
                "ip": "10.14.30.254",
                "segment": "physical_security_lan"
              },
              {
                "ip": "10.14.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "building_hvac_controller",
            "networks": [
              {
                "ip": "10.14.20.10",
                "segment": "facility_bms_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=building_hvac",
                "DEVICE_ID=1401"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "badge_reader_panel",
            "networks": [
              {
                "ip": "10.14.30.10",
                "segment": "physical_security_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=badge_reader",
                "DEVICE_ID=1402"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "security-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "facility_monitoring_station",
            "networks": [
              {
                "ip": "10.14.30.20",
                "segment": "physical_security_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=facility_monitor",
                "TARGET=10.14.20.10",
                "DEVICE_ID=1401",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "security_operations_console",
            "networks": [
              {
                "ip": "10.14.20.20",
                "segment": "facility_bms_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=security_console",
                "TARGET=10.14.30.10",
                "DEVICE_ID=1402",
                "INTERVAL=8"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "security-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "classified_area_hvac",
            "networks": [
              {
                "ip": "10.14.50.10",
                "segment": "classified_area_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=device",
                "LABEL=classified_hvac",
                "DEVICE_ID=1450"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "classified_area_monitor",
            "networks": [
              {
                "ip": "10.14.50.11",
                "segment": "classified_area_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=client",
                "LABEL=classified_monitor",
                "TARGET=10.14.50.10",
                "DEVICE_ID=1450",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.14.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.14.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.14.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.14.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.14.20.0/24",
            "kind": "ot-lan",
            "name": "facility_bms_lan"
          },
          {
            "cidr": "10.14.30.0/24",
            "kind": "security-lan",
            "name": "physical_security_lan"
          },
          {
            "cidr": "10.14.50.0/24",
            "kind": "ot-l2",
            "name": "classified_area_lan"
          },
          {
            "cidr": "10.14.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  },
  {
    "group": "器のみ・観測境界あり",
    "id": "financial-datacenter-reference",
    "label": "金融",
    "model": {
      "apiVersion": "amenonuboco/v1alpha1",
      "instrumentation": {
        "exclude": [
          "payment_network_lan"
        ],
        "mirror_to": "mirror_link"
      },
      "kind": "CyberRange",
      "metadata": {
        "description": "金融分野の器。データセンターの設備系・監視を観測し、決済ネットワークを分離された死角として描く",
        "name": "financial-datacenter-reference"
      },
      "structuring": {
        "elasticsearch_url": "http://elasticsearch:9200",
        "engine": "tshark",
        "protocols": [
          {
            "name": "bacapp",
            "output_index": "ot-logs-bacnet-*"
          },
          {
            "name": "snmp",
            "output_index": "ot-logs-snmp-*"
          }
        ]
      },
      "topology": {
        "assets": [
          {
            "image": "debian:bullseye-slim",
            "name": "wan_router",
            "networks": [
              {
                "ip": "10.15.10.254",
                "segment": "corp_it_lan"
              },
              {
                "ip": "10.15.20.254",
                "segment": "dc_facility_lan"
              },
              {
                "ip": "10.15.30.254",
                "segment": "dc_network_mgmt_lan"
              },
              {
                "ip": "10.15.99.254",
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "l3-router"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "crac_controller",
            "networks": [
              {
                "ip": "10.15.20.10",
                "segment": "dc_facility_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=device",
                "LABEL=crac",
                "DEVICE_ID=1501"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "ups_power_controller",
            "networks": [
              {
                "ip": "10.15.20.11",
                "segment": "dc_facility_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=agent",
                "LABEL=dc_ups",
                "SYSNAME=dc-ups-01",
                "SYSLOCATION=Data Hall A"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/bacnet",
            "name": "bms_head_end",
            "networks": [
              {
                "ip": "10.15.30.10",
                "segment": "dc_network_mgmt_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=client",
                "LABEL=bms_head_end",
                "TARGET=10.15.20.10",
                "DEVICE_ID=1501",
                "INTERVAL=6"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/snmp",
            "name": "dc_nms",
            "networks": [
              {
                "ip": "10.15.30.11",
                "segment": "dc_network_mgmt_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "python3 /app/run.py",
              "environment": [
                "MODE=poller",
                "LABEL=dc_nms",
                "TARGET=10.15.20.11",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "payment_switch",
            "networks": [
              {
                "ip": "10.15.50.10",
                "segment": "payment_network_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=server",
                "LABEL=payment_switch"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "../protocol-images/modbus",
            "name": "settlement_node",
            "networks": [
              {
                "ip": "10.15.50.11",
                "segment": "payment_network_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "MODE=client",
                "LABEL=settlement_node",
                "TARGET=10.15.50.10",
                "INTERVAL=5"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "ot-asset"
          },
          {
            "image": "docker.elastic.co/elasticsearch/elasticsearch:8.12.0",
            "name": "elasticsearch",
            "networks": [
              {
                "ip": "10.15.10.40",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [
                "discovery.type=single-node",
                "xpack.security.enabled=false",
                "ES_JAVA_OPTS=-Xms512m -Xmx512m"
              ],
              "ports": [],
              "sysctls": null
            },
            "role": "detection-infra"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "tap_observer",
            "networks": [
              {
                "ip": null,
                "segment": "mirror_link"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "apt-get update -qq && apt-get install -y -qq tcpdump >/dev/null 2>&1 && tcpdump -i eth0 -nn",
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "observer"
          },
          {
            "image": "debian:bullseye-slim",
            "name": "log_structurer",
            "networks": [
              {
                "ip": "10.15.99.60",
                "segment": "mirror_link"
              },
              {
                "ip": "10.15.10.60",
                "segment": "corp_it_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": null,
              "environment": [],
              "ports": [],
              "sysctls": null
            },
            "role": "structurer"
          }
        ],
        "routing": {
          "gateway": "wan_router"
        },
        "segments": [
          {
            "cidr": "10.15.10.0/24",
            "kind": "it-core",
            "name": "corp_it_lan"
          },
          {
            "cidr": "10.15.20.0/24",
            "kind": "ot-lan",
            "name": "dc_facility_lan"
          },
          {
            "cidr": "10.15.30.0/24",
            "kind": "ot-lan",
            "name": "dc_network_mgmt_lan"
          },
          {
            "cidr": "10.15.50.0/24",
            "kind": "ot-l2",
            "name": "payment_network_lan"
          },
          {
            "cidr": "10.15.99.0/24",
            "kind": "observation",
            "name": "mirror_link"
          }
        ]
      }
    }
  }
];
