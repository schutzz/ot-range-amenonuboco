#!/usr/bin/env python3
"""GUI(gui/)が読む語彙・サンプルのJSファイルを、Pythonスキーマから生成する
(Phase8決定事項#117)。

GUIはクライアントサイド完結の静的サイトであり、Pythonのモデルをそのまま
呼べない。そのためセグメント種別・資産ロール・ロールプリセット・配色・
レイアウト定数を「JS側に手書きする」と、ロールを1つ追加するたびに2箇所を
直す羽目になり、いずれ必ずズレる。これを防ぐため、これらの語彙は常に
Python側の定義から機械生成し、生成物(gui/vocab.js)はコミットするが手で
編集しない。tests/test_gui_vocab.py が「コミット済みの生成物」と「今の
スキーマから生成した結果」の一致を検証するため、再生成を忘れるとCIで落ちる
(決定事項#118の封じ込め策①)。

出力を .json ではなく .js (window へ代入するだけのスクリプト)にしているのは、
`fetch()` がfile://スキームではCORSで失敗するため。<script>タグで読める形に
しておくと、GitHub Pages公開時とローカルでのHTML直開きの両方で同じものが動く。

使い方:
    python platform/tools/gen_gui_vocab.py          # gui/ へ書き出す
    python platform/tools/gen_gui_vocab.py --check  # 差分があれば非ゼロ終了
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, get_args

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PLATFORM = _REPO_ROOT / "platform"

# platform/ はパッケージ化していない(cli.pyがsys.path.insertする運用、Phase1)。
if str(_PLATFORM) not in sys.path:
    sys.path.insert(0, str(_PLATFORM))

from renderers import network_diagram as nd  # noqa: E402
from schema import load_manifest, load_role_presets  # noqa: E402
from schema.topology import AssetRole, SegmentKind  # noqa: E402

# GUIに同梱する組み込みテンプレート(決定事項#121の経路1)。ユーザーが何も
# インストールせずに「3分野のリファレンス構成を土台に自分の環境を作る」を
# できるようにするため、load_manifest()を通したモデルをJSONとして埋め込む。
# JS側にYAMLパーサを持ち込まないための要でもある。
_SAMPLE_MANIFESTS: list[tuple[str, str]] = [
    ("power-grid-reference", "電力"),
    ("water-utility-reference", "上下水道"),
    ("manufacturing-plant-reference", "重要製造業"),
]


def build_vocab() -> dict[str, Any]:
    """GUIが必要とする語彙一式を、Python側の定義から組み立てる。"""
    presets = load_role_presets()

    roles: dict[str, Any] = {}
    for role in get_args(AssetRole):
        preset = presets.roles.get(role)
        roles[role] = {
            "color": nd._ROLE_COLORS.get(role, "#888888"),
            "cap_add": list(preset.cap_add) if preset else [],
            "sysctls": list(preset.sysctls) if preset else [],
            "default_command": preset.default_command if preset else None,
        }

    kinds: dict[str, Any] = {
        kind: {"fill": nd._SEGMENT_KIND_COLORS.get(kind, "rgba(120,120,120,0.14)")}
        for kind in get_args(SegmentKind)
    }

    return {
        "roles": roles,
        "segmentKinds": kinds,
        # レイアウト定数。JS側にハードコードすると、Python側の調整
        # (罠#015・#016・#021・#024で繰り返し効いてきた値)と乖離する。
        "layout": {
            "viewW": nd._VIEW_W,
            "viewH": nd._VIEW_H,
            "segmentRadius": nd._SEGMENT_RADIUS,
            "segmentBoxW": nd._SEGMENT_BOX_W,
            "segmentBoxH": nd._SEGMENT_BOX_H,
            "assetCols": nd._ASSET_COLS,
            "assetColGap": nd._ASSET_COL_GAP,
            "assetRowGap": nd._ASSET_ROW_GAP,
            "nodeR": nd._NODE_R,
        },
        "colors": {
            "segmentBorder": nd._SEGMENT_BORDER_COLOR,
            "observedBorder": nd._OBSERVED_BORDER_COLOR,
            "blindBorder": nd._BLIND_BORDER_COLOR,
            "mirrorSinkBorder": nd._MIRROR_SINK_BORDER_COLOR,
            "mirrorFlow": nd._MIRROR_FLOW_COLOR,
            "detectionMark": nd._DETECTION_MARK_COLOR,
        },
    }


def build_samples() -> list[dict[str, Any]]:
    """3分野のリファレンスマニフェストを、GUIの編集モデル形式で返す。"""
    samples: list[dict[str, Any]] = []
    for stem, label in _SAMPLE_MANIFESTS:
        manifest = load_manifest(_REPO_ROOT / "manifests" / f"{stem}.yaml")
        samples.append(
            {
                "id": stem,
                "label": label,
                "model": manifest_to_model(manifest),
            }
        )
    return samples


def manifest_to_model(manifest: Any) -> dict[str, Any]:
    """Manifest を GUI の編集モデル(topology/instrumentation/structuringの3層)へ落とす。

    GUIの編集対象は3層に限定している(決定事項#119)。detection/attack/
    visualization は外部シナリオ資産への参照が主であり、GUIで編集させると
    「シナリオ資産はコードで書く」という境界(Phase0決定事項#1)が濁るため、
    ここでも意図的に落とす。落としても topology 以外は全てOptionalであり、
    残る3層だけで動作する有効なマニフェストが成立する。
    """
    topo = manifest.topology
    model: dict[str, Any] = {
        "apiVersion": manifest.api_version,
        "kind": manifest.kind,
        "metadata": {
            "name": manifest.metadata.name,
            "description": manifest.metadata.description,
        },
        "topology": {
            "segments": [
                {"name": s.name, "cidr": s.cidr, "kind": s.kind} for s in topo.segments
            ],
            "assets": [
                {
                    "name": a.name,
                    "role": a.role,
                    "image": a.image,
                    "networks": [
                        {"segment": n.segment, "ip": n.ip} for n in a.networks
                    ],
                    "overrides": {
                        "ports": list(a.overrides.ports),
                        "command": a.overrides.command,
                        "cap_add": a.overrides.cap_add,
                        "sysctls": a.overrides.sysctls,
                        "environment": list(a.overrides.environment),
                    },
                }
                for a in topo.assets
            ],
            "routing": ({"gateway": topo.routing.gateway} if topo.routing else None),
        },
        "instrumentation": None,
        "structuring": None,
    }

    if manifest.instrumentation is not None:
        model["instrumentation"] = {
            "mirror_to": manifest.instrumentation.mirror_to,
            "exclude": list(manifest.instrumentation.exclude),
        }

    if manifest.structuring is not None:
        model["structuring"] = {
            "engine": manifest.structuring.engine,
            "protocols": [
                {"name": p.name, "output_index": p.output_index}
                for p in manifest.structuring.protocols
            ],
            "elasticsearch_url": manifest.structuring.elasticsearch_url,
        }

    return model


def _render_js(var_name: str, payload: Any, note: str) -> str:
    """window へ代入するだけのJSファイルを組み立てる。

    生成物であることをファイル冒頭で明示する。手で編集されると
    tests/test_gui_vocab.py が落ちるため、そこで気づける。
    """
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        "// 自動生成ファイル — 手で編集しないこと。\n"
        "// 生成元: platform/tools/gen_gui_vocab.py\n"
        f"// {note}\n"
        f"window.{var_name} = {body};\n"
    )


def generate() -> dict[Path, str]:
    """生成対象のパスと内容の対応を返す(書き出しは行わない)。"""
    gui_dir = _REPO_ROOT / "gui"
    return {
        gui_dir
        / "vocab.js": _render_js(
            "AMENONUBOCO_VOCAB",
            build_vocab(),
            "セグメント種別・資産ロール・ロールプリセット・配色・レイアウト定数。",
        ),
        gui_dir
        / "samples.js": _render_js(
            "AMENONUBOCO_SAMPLES",
            build_samples(),
            "3分野のリファレンスマニフェストを編集モデル形式で同梱したもの。",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="gen_gui_vocab")
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き出さず、既存ファイルとの差分の有無だけを終了コードで返す",
    )
    args = parser.parse_args()

    outputs = generate()

    if args.check:
        stale = [
            path
            for path, content in outputs.items()
            if not path.is_file() or path.read_text(encoding="utf-8") != content
        ]
        if stale:
            for path in stale:
                print(f"stale: {path.relative_to(_REPO_ROOT)}", file=sys.stderr)
            print(
                "再生成が必要です: python platform/tools/gen_gui_vocab.py",
                file=sys.stderr,
            )
            return 1
        print("up to date")
        return 0

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"generated: {path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
