#!/usr/bin/env python3
"""Amenonuboco プロビジョナ CLI(Phase1最小版)。

使い方:
    python cli.py provision <manifest.yaml> [-o <output.yml>]

マニフェストのtopology層を読み、docker-compose.yml を生成してファイルに書き出す。
実際の `docker compose up` はここでは呼ばない(明示的にユーザーが実行する)。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# platform/ 直下から実行される想定でパスを通す(パッケージ化はPhase1のスコープ外)。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generators.compose import ComposeGenerationError, dump_compose_yaml, generate_compose
from renderers.network_diagram import render_network_diagram
from schema import ManifestLoadError, PresetLoadError, load_manifest, load_role_presets


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

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
