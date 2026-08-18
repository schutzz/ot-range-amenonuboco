#!/usr/bin/env python3
"""Amenonuboco プロビジョナ CLI(Phase1最小版)。

使い方:
    python cli.py provision  <manifest.yaml> [-o <output.yml>]
    python cli.py diagram    <manifest.yaml> [-o <output.html>]
    python cli.py gui-export <manifest.yaml> [-o <output.gui.json>]

マニフェストのtopology層を読み、docker-compose.yml を生成してファイルに書き出す。
実際の `docker compose up` はここでは呼ばない(明示的にユーザーが実行する)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# platform/ 直下から実行される想定でパスを通す(パッケージ化はPhase1のスコープ外)。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generators.compose import ComposeGenerationError, dump_compose_yaml, generate_compose
from renderers.network_diagram import render_network_diagram
from schema import ManifestLoadError, PresetLoadError, load_manifest, load_role_presets
from tools.gen_gui_vocab import manifest_to_model


def cmd_provision(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    output_path = Path(args.output) if args.output else manifest_path.with_name(
        f"{manifest_path.stem}.docker-compose.yml"
    )

    try:
        manifest = load_manifest(manifest_path)
        presets = load_role_presets()
        compose = generate_compose(manifest, presets)
    except (ManifestLoadError, PresetLoadError, ComposeGenerationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(dump_compose_yaml(compose), encoding="utf-8")
    print(f"generated: {output_path}")
    print(f"  segments: {len(manifest.topology.segments)}")
    print(f"  assets:   {len(manifest.topology.assets)}")
    return 0


def cmd_diagram(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest)
    output_path = Path(args.output) if args.output else manifest_path.with_name(
        f"{manifest_path.stem}.network-diagram.html"
    )

    try:
        manifest = load_manifest(manifest_path)
        diagram_html = render_network_diagram(manifest)
    except ManifestLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output_path.write_text(diagram_html, encoding="utf-8")
    print(f"generated: {output_path}")
    return 0


def cmd_gui_export(args: argparse.Namespace) -> int:
    """マニフェストを、GUI(gui/)が読み込めるJSONへ変換する(Phase8決定事項#121)。

    GUIはクライアントサイド完結でありYAMLパーサを持たない。任意のマニフェストを
    GUIへ取り込む経路として、変換だけをCLI側(＝実際の`load_manifest()`)に担わせる。
    こうすると取り込み経路にも単一の真実が効き、JS側にYAMLパーサを持ち込まずに
    済む(YAMLの自前実装は不具合の温床、外部ライブラリは自己完結の方針と衝突する)。

    出力したJSONをGUIの画面へドラッグ&ドロップすると読み込める。GUIからの
    書き出しは常に別名(`<name>.generated.yaml`)であり、元のマニフェストを
    上書きすることはない(決定事項#120)。
    """
    manifest_path = Path(args.manifest)
    output_path = Path(args.output) if args.output else manifest_path.with_name(
        f"{manifest_path.stem}.gui.json"
    )

    try:
        manifest = load_manifest(manifest_path)
    except ManifestLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    model = manifest_to_model(manifest)
    output_path.write_text(
        json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"generated: {output_path}")
    print("  gui/index.html を開き、このファイルをドラッグ&ドロップしてください")

    dropped = [
        layer
        for layer in ("detection", "attack", "visualization")
        if getattr(manifest, layer) is not None
    ]
    if dropped:
        # GUIの編集対象は3層に限定している(決定事項#119)。黙って落とすと
        # 「書き出したら検知設定が消えた」という事故になるため明示する。
        print(
            f"  注意: GUIの編集対象外の層は含まれません: {', '.join(dropped)}"
            "（GUIから書き出したYAMLへは引き継がれません）",
            file=sys.stderr,
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="amenonuboco")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_provision = sub.add_parser(
        "provision", help="マニフェストからdocker-compose.ymlを生成する"
    )
    p_provision.add_argument("manifest", help="マニフェストファイル(YAML)のパス")
    p_provision.add_argument(
        "-o", "--output", help="出力先パス(既定: <manifest>.docker-compose.yml)"
    )
    p_provision.set_defaults(func=cmd_provision)

    p_diagram = sub.add_parser(
        "diagram", help="マニフェストからHTMLネットワーク図を生成する"
    )
    p_diagram.add_argument("manifest", help="マニフェストファイル(YAML)のパス")
    p_diagram.add_argument(
        "-o", "--output", help="出力先パス(既定: <manifest>.network-diagram.html)"
    )
    p_diagram.set_defaults(func=cmd_diagram)

    p_gui = sub.add_parser(
        "gui-export",
        help="マニフェストをGUI(gui/)へ取り込むためのJSONへ変換する",
    )
    p_gui.add_argument("manifest", help="マニフェストファイル(YAML)のパス")
    p_gui.add_argument(
        "-o", "--output", help="出力先パス(既定: <manifest>.gui.json)"
    )
    p_gui.set_defaults(func=cmd_gui_export)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
