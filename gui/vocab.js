// 自動生成ファイル — 手で編集しないこと。
// 生成元: platform/tools/gen_gui_vocab.py
// セグメント種別・資産ロール・ロールプリセット・配色・レイアウト定数。
window.AMENONUBOCO_VOCAB = {
  "colors": {
    "blindBorder": "#d97757",
    "detectionMark": "#e0b341",
    "mirrorFlow": "#4fd1c5",
    "mirrorSinkBorder": "#a78bfa",
    "observedBorder": "#4fd1c5",
    "segmentBorder": "#5a6a7a"
  },
  "layout": {
    "assetColGap": 138,
    "assetCols": 2,
    "assetRowGap": 40,
    "nodeR": 9,
    "segmentBoxH": 190,
    "segmentBoxW": 290,
    "segmentRadius": 350,
    "viewH": 920,
    "viewW": 1240
  },
  "roles": {
    "attack-engine": {
      "cap_add": [],
      "color": "#d94a6a",
      "default_command": null,
      "sysctls": []
    },
    "attacker-external": {
      "cap_add": [
        "NET_ADMIN",
        "NET_RAW"
      ],
      "color": "#b33f3f",
      "default_command": null,
      "sysctls": []
    },
    "attacker-insider": {
      "cap_add": [
        "NET_ADMIN",
        "NET_RAW"
      ],
      "color": "#9c4a9c",
      "default_command": null,
      "sysctls": []
    },
    "attacker-internal": {
      "cap_add": [
        "NET_ADMIN"
      ],
      "color": "#b3703f",
      "default_command": null,
      "sysctls": []
    },
    "detection-infra": {
      "cap_add": [],
      "color": "#4c8c4a",
      "default_command": null,
      "sysctls": []
    },
    "eval-harness": {
      "cap_add": [],
      "color": "#8a7a4a",
      "default_command": null,
      "sysctls": []
    },
    "l3-router": {
      "cap_add": [
        "NET_ADMIN",
        "NET_RAW"
      ],
      "color": "#c9782f",
      "default_command": "tail -f /dev/null",
      "sysctls": [
        "net.ipv4.ip_forward=1"
      ]
    },
    "observer": {
      "cap_add": [
        "NET_ADMIN",
        "NET_RAW"
      ],
      "color": "#4a9c9c",
      "default_command": null,
      "sysctls": []
    },
    "ot-asset": {
      "cap_add": [
        "NET_ADMIN"
      ],
      "color": "#3b6ea5",
      "default_command": null,
      "sysctls": []
    },
    "remote-access-gateway": {
      "cap_add": [
        "NET_ADMIN"
      ],
      "color": "#c9a13c",
      "default_command": null,
      "sysctls": []
    },
    "security-asset": {
      "cap_add": [
        "NET_ADMIN"
      ],
      "color": "#3ca6a6",
      "default_command": null,
      "sysctls": []
    },
    "structurer": {
      "cap_add": [
        "NET_ADMIN",
        "NET_RAW"
      ],
      "color": "#5fb3d9",
      "default_command": null,
      "sysctls": []
    },
    "visualization-engine": {
      "cap_add": [],
      "color": "#e0a63c",
      "default_command": null,
      "sysctls": []
    }
  },
  "segmentKinds": {
    "dmz": {
      "fill": "rgba(150,150,60,0.14)"
    },
    "it-core": {
      "fill": "rgba(59,110,165,0.16)"
    },
    "observation": {
      "fill": "rgba(122,90,158,0.16)"
    },
    "ot-l2": {
      "fill": "rgba(74,156,156,0.16)"
    },
    "ot-lan": {
      "fill": "rgba(76,140,74,0.16)"
    },
    "security-lan": {
      "fill": "rgba(60,166,166,0.16)"
    },
    "wan-edge": {
      "fill": "rgba(179,63,63,0.14)"
    }
  }
};
