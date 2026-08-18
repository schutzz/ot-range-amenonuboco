"""マニフェストから、防御側・統裁側向けの自己完結HTMLネットワーク図を生成する
(Phase0決定事項#6、Phase1決定事項#26)。

方針:
- 外部ライブラリに依存しない(CDN読み込み無し、単一ファイルで完結)。SVGを
  Pythonの文字列テンプレートで直接組み立てる。
- セグメントを円周上に配置した箱として描画し、単一セグメントにのみ接続する
  資産はその箱の中に配置する。
- マルチホーム資産(l3-router等)は、接続する全セグメント箱の重心に配置し、
  各セグメント箱へ線を伸ばす(ハブ&スポーク配置)。
- インタラクション(ホバー詳細・ズーム/パン)は、ネイティブの<title>要素と
  最小限のvanilla JSのみで実現する(Phase0決定事項#6の「自己完結HTML」
  「インタラクティブ」要件を、外部依存無しで満たすための最小構成)。

描画する層(Phase0決定事項#6の5.2節が要求する情報、決定事項#50):
- トポロジ(Phase1): セグメント・資産・接続
- 観測カバレッジ(Phase2): どのセグメントがミラーされ、どこが死角か。統裁側の
  環境把握に不可欠な情報であり、「観測外」を明示的に描くことを重視する
- 構造化(Phase3): どのプロトコルがどのindexへ構造化されるか
- 検知配置(Phase4以降): 未実装
"""

from __future__ import annotations

import html
import math

from schema import Asset, Manifest, Segment, Topology

# ロールごとの色(ダークテーマ基調、docs/manifest-schema-guide.md §5.2の8ロールに対応)
_ROLE_COLORS: dict[str, str] = {
    "ot-asset": "#3b6ea5",
    "l3-router": "#c9782f",
    "detection-infra": "#4c8c4a",
    "observer": "#4a9c9c",
    "structurer": "#5fb3d9",  # Phase3決定事項#41で追加したロール
    "eval-harness": "#8a7a4a",
    "attack-engine": "#d94a6a",  # Phase4決定事項#58で追加したロール
    "visualization-engine": "#e0a63c",  # Phase6決定事項#83で追加したロール
    "attacker-external": "#b33f3f",
    "attacker-internal": "#b3703f",
    "attacker-insider": "#9c4a9c",
}

# セグメント種別ごとの背景色(薄いティント、docs/manifest-schema-guide.md §5.1に対応)
_SEGMENT_KIND_COLORS: dict[str, str] = {
    "it-core": "rgba(59,110,165,0.16)",
    "wan-edge": "rgba(179,63,63,0.14)",
    "ot-lan": "rgba(76,140,74,0.16)",
    "ot-l2": "rgba(74,156,156,0.16)",
    "observation": "rgba(122,90,158,0.16)",
    "dmz": "rgba(150,150,60,0.14)",
}

_SEGMENT_BORDER_COLOR = "#5a6a7a"
# 観測状態ごとの枠線色。「観測外(死角)」を最も目立つ色にする——統裁側にとって
# 死角の所在は最重要情報であり、"何も描かれていない"では伝わらないため。
_OBSERVED_BORDER_COLOR = "#4fd1c5"
_BLIND_BORDER_COLOR = "#d97757"
_MIRROR_SINK_BORDER_COLOR = "#a78bfa"
_MIRROR_FLOW_COLOR = "#4fd1c5"
# 検知プラグインが載っている資産を囲む角マーカーの色
_DETECTION_MARK_COLOR = "#e0b341"

_VIEW_W = 1240
_VIEW_H = 920
_CENTER = (_VIEW_W / 2, _VIEW_H / 2 + 20)
_SEGMENT_RADIUS = 350
_SEGMENT_BOX_W = 290
# 観測状態バッジを箱の下端に置くぶん拡げている。2列3行(検知基盤が集中する
# cc_lanは6資産に達する)でも最終行のラベルがバッジに重ならない高さにする。
_SEGMENT_BOX_H = 190
# 3列だと資産ラベル(最長19文字)が横に重なるため2列にした(罠ログ#016)。
# 列間隔はラベル幅(9px×19文字≒110px)より広く取り、隣の列と重ねない。
_ASSET_COLS = 2
_ASSET_COL_GAP = 138
# 行間はラベル(ノード中心+22px)より広く取る。Phase1の30pxでは次の行の
# ノードが前の行のラベルに重なった(罠ログ#015)。
_ASSET_ROW_GAP = 40
_NODE_R = 9


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _segment_positions(segments: list[Segment]) -> dict[str, tuple[float, float]]:
    """各セグメント箱の中心座標を円周上に配置して返す。"""
    n = len(segments)
    positions: dict[str, tuple[float, float]] = {}
    for i, seg in enumerate(segments):
        angle = (2 * math.pi * i / n) - (math.pi / 2) if n > 0 else 0.0
        cx = _CENTER[0] + _SEGMENT_RADIUS * math.cos(angle)
        cy = _CENTER[1] + _SEGMENT_RADIUS * math.sin(angle)
        positions[seg.name] = (cx, cy)
    return positions


def _asset_segment_names(asset: Asset) -> list[str]:
    return [net.segment for net in asset.networks]


def _segment_box_heights(topology: Topology) -> dict[str, float]:
    """各セグメント箱の高さを、そこに単一接続する資産の行数に応じて動的に
    算出する(罠ログ#021)。固定値だと、資産が増えて行数が増えるたびに
    最終行のラベルがバッジの位置にはみ出す不具合が繰り返し起きた(罠#015が
    縦方向、罠#016が横方向、本件は「行数そのものの増加」に対応できていな
    かった3件目)。資産数に追従させることで、この系統の不具合を構造的に
    解消する。
    """
    counts: dict[str, int] = {}
    for asset in topology.assets:
        seg_names = _asset_segment_names(asset)
        if len(seg_names) == 1:
            counts[seg_names[0]] = counts.get(seg_names[0], 0) + 1

    heights: dict[str, float] = {}
    for seg in topology.segments:
        n = counts.get(seg.name, 0)
        rows = math.ceil(n / _ASSET_COLS) if n > 0 else 0
        # ヘッダー(ラベル+CIDR、58px) + 資産の行(1行目はヘッダー直下、
        # 2行目以降は_ASSET_ROW_GAPごと) + バッジとその余白(70px)。
        content_height = 58 + max(rows - 1, 0) * _ASSET_ROW_GAP + 70
        heights[seg.name] = max(_SEGMENT_BOX_H, content_height)
    return heights


def _coverage(manifest: Manifest) -> tuple[set[str], str | None]:
    """(観測対象セグメント名の集合, ミラー集約先セグメント名)を返す。

    観測対象の判定は`Instrumentation.observed_segments`(オプトアウト方式、
    Phase2決定事項#28)にそのまま委ねる。図側で判定ロジックを再実装すると、
    生成器と図が別々の答えを出す余地が生まれ、「図と実態が乖離しない」という
    Phase0決定事項#6の前提が崩れるため。
    """
    inst = manifest.instrumentation
    if inst is None:
        return set(), None
    observed = {seg.name for seg in inst.observed_segments(manifest.topology)}
    return observed, inst.mirror_to


def _plugins_on(manifest: Manifest, asset_name: str) -> list[str]:
    """指定資産に載る検知プラグイン名の一覧(観測判定と同じく、図側で判定
    ロジックを再実装せず Detection.plugins_for_host に委ねる、決定事項#50)。
    """
    if manifest.detection is None:
        return []
    return [p.name for p in manifest.detection.plugins_for_host(asset_name)]


def _is_caldera_host(manifest: Manifest, asset_name: str) -> bool:
    if manifest.attack is None:
        return False
    return manifest.attack.caldera_host() == asset_name


def _visualization_host_label(manifest: Manifest, asset_name: str) -> str | None:
    """指定資産が可視化エンジンのhostであれば、表示用ラベル(例: "Grafana")を
    返す。判定は Visualization.host の比較のみで、図側でロジックを
    再実装しない(決定事項#50と同じ方針)。
    """
    if manifest.visualization is None:
        return None
    if manifest.visualization.host != asset_name:
        return None
    return manifest.visualization.engine.capitalize()


def _segment_border(seg_name: str, observed: set[str], mirror_to: str | None) -> tuple[str, float]:
    if mirror_to is None:
        return _SEGMENT_BORDER_COLOR, 1.5
    if seg_name == mirror_to:
        return _MIRROR_SINK_BORDER_COLOR, 2.0
    if seg_name in observed:
        return _OBSERVED_BORDER_COLOR, 2.0
    return _BLIND_BORDER_COLOR, 2.0


def _coverage_badge(seg_name: str, observed: set[str], mirror_to: str | None) -> str:
    if mirror_to is None:
        return ""
    if seg_name == mirror_to:
        return "◎ ミラー集約先"
    if seg_name in observed:
        return "◉ 観測対象"
    return "✕ 観測外（死角）"


def _mirror_flow_lines(
    seg_pos: dict[str, tuple[float, float]],
    seg_heights: dict[str, float],
    observed: set[str],
    mirror_to: str | None,
) -> list[str]:
    """観測対象セグメント → ミラー集約先セグメント へのフロー線。
    箱の中心同士を結ぶと箱の下に隠れるため、両端を箱の外側へ寄せる。
    """
    if mirror_to is None or mirror_to not in seg_pos:
        return []
    mx, my = seg_pos[mirror_to]
    m_half_h = seg_heights[mirror_to] / 2 + 9
    lines: list[str] = []
    for name in sorted(observed):
        if name not in seg_pos:
            continue
        sx, sy = seg_pos[name]
        s_half_h = seg_heights[name] / 2 + 9
        dx, dy = mx - sx, my - sy
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist
        # 箱の外側で始まり、外側で終わるよう寄せる(半幅145+7/半高は各セグメント
        # の実高さに応じて可変、罠ログ#021)。内側に入り込むと、矢印の先端が
        # 箱の中の資産ノードと重なって読めなくなる。
        x1, y1 = sx + ux * 152, sy + uy * s_half_h
        x2, y2 = mx - ux * 152, my - uy * m_half_h
        lines.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'class="mirror-flow" marker-end="url(#mirror-arrow)">'
            f"<title>{_esc(name)} のトラフィックが {_esc(mirror_to)} へミラーされる</title>"
            f"</line>"
        )
    return lines


def _layer_note(manifest: Manifest) -> str:
    """図がどの層まで描画しているかを示す注記。マニフェストに実際に宣言されて
    いる層だけを挙げる(トポロジしか無いマニフェストで「観測カバレッジ表示」と
    書くと、それこそ図と実態が食い違うため)。
    """
    layers = ["トポロジ"]
    if manifest.instrumentation is not None:
        layers.append("観測カバレッジ")
    if manifest.structuring is not None:
        layers.append("構造化")
    if manifest.detection is not None and manifest.detection.plugins:
        layers.append("検知配置")
    if manifest.attack is not None and manifest.attack.caldera_host() is not None:
        layers.append("攻撃エンジン")
    return " / ".join(layers)


def _info_panel_html(manifest: Manifest, observed: set[str], mirror_to: str | None) -> str:
    """計装・構造化の要約パネル。統裁側が「どこが見えていて、何が構造化されて
    いるか」を図から離れずに読めるようにする(Phase0決定事項#6の5.2節)。
    """
    blocks: list[str] = []

    if mirror_to is not None:
        total = len(manifest.topology.segments)
        # mirror_to自身は観測対象に含まれない(自己ミラーはしない)ため、
        # カバレッジの母数から外して数える。
        candidates = total - 1
        blind = [
            seg.name
            for seg in manifest.topology.segments
            if seg.name != mirror_to and seg.name not in observed
        ]
        blind_html = (
            f'<div class="info-blind">死角: {_esc(", ".join(blind))}</div>'
            if blind
            else '<div class="info-ok">死角なし</div>'
        )
        blocks.append(
            '<div class="info-block info-block--coverage">'
            '<div class="info-title"><span class="info-icon">◉</span>計装（観測カバレッジ）</div>'
            f'<div class="info-row"><span>ミラー集約先</span><code>{_esc(mirror_to)}</code></div>'
            f'<div class="info-row"><span>観測対象</span>'
            f"<code>{len(observed)} / {candidates} セグメント</code></div>"
            f"{blind_html}"
            "</div>"
        )

    structuring = manifest.structuring
    if structuring is not None and structuring.protocols:
        rows = "".join(
            f'<div class="info-row"><span>{_esc(p.name)}</span>'
            f"<code>{_esc(p.output_index)}</code></div>"
            for p in structuring.protocols
        )
        blocks.append(
            '<div class="info-block info-block--structuring">'
            f'<div class="info-title"><span class="info-icon">◆</span>構造化（{_esc(structuring.engine)}）</div>'
            f"{rows}"
            "</div>"
        )

    detection = manifest.detection
    if detection is not None and detection.plugins:
        rows = "".join(
            f'<div class="info-row"><span>{_esc(p.name)}</span>'
            f"<code>{_esc(p.host)}</code></div>"
            for p in detection.plugins
        )
        blocks.append(
            '<div class="info-block info-block--detection">'
            '<div class="info-title"><span class="info-icon">▲</span>検知プラグイン（→ ホスト）</div>'
            f"{rows}"
            "</div>"
        )

    visualization = manifest.visualization
    if visualization is not None:
        rows = f'<div class="info-row"><span>ホスト</span><code>{_esc(visualization.host)}</code></div>'
        if visualization.dashboards:
            rows += (
                f'<div class="info-row"><span>ダッシュボード</span>'
                f"<code>{len(visualization.dashboards)} 件</code></div>"
            )
        blocks.append(
            '<div class="info-block info-block--visualization">'
            f'<div class="info-title"><span class="info-icon">◈</span>可視化（{_esc(visualization.engine)}）</div>'
            f"{rows}"
            "</div>"
        )

    if not blocks:
        return ""
    return f'<div class="panel info-panel">{"".join(blocks)}</div>'


def render_network_diagram(manifest: Manifest) -> str:
    topology: Topology = manifest.topology
    seg_pos = _segment_positions(topology.segments)
    seg_heights = _segment_box_heights(topology)
    observed, mirror_to = _coverage(manifest)

    svg_parts: list[str] = []

    # --- ミラーフロー線(セグメント箱より先に描き、箱の下に潜らせる) ---
    svg_parts.extend(_mirror_flow_lines(seg_pos, seg_heights, observed, mirror_to))

    # --- セグメント箱 ---
    for seg in topology.segments:
        cx, cy = seg_pos[seg.name]
        box_h = seg_heights[seg.name]
        x, y = cx - _SEGMENT_BOX_W / 2, cy - box_h / 2
        fill = _SEGMENT_KIND_COLORS.get(seg.kind, "rgba(120,120,120,0.14)")
        border_color, border_w = _segment_border(seg.name, observed, mirror_to)
        badge = _coverage_badge(seg.name, observed, mirror_to)
        badge_el = (
            f'<text x="{cx:.1f}" y="{y + box_h - 8:.1f}" class="seg-badge" '
            f'text-anchor="middle" fill="{border_color}">{_esc(badge)}</text>'
            if badge
            else ""
        )
        title = f"{seg.name} ({seg.cidr}) — {seg.kind}"
        if badge:
            title += f"\n{badge}"
        svg_parts.append(
            f'<g class="segment">'
            f'<rect class="seg-rect" x="{x:.1f}" y="{y:.1f}" width="{_SEGMENT_BOX_W}" height="{box_h:.1f}" '
            f'rx="10" fill="{fill}" stroke="{border_color}" stroke-width="{border_w}">'
            f"<title>{_esc(title)}</title>"
            f"</rect>"
            f'<text x="{cx:.1f}" y="{y + 18:.1f}" class="seg-label" text-anchor="middle">'
            f"{_esc(seg.name)}</text>"
            f'<text x="{cx:.1f}" y="{y + 34:.1f}" class="seg-sub" text-anchor="middle">'
            f"{_esc(seg.cidr)} · {_esc(seg.kind)}</text>"
            f"{badge_el}"
            f"</g>"
        )

    # --- 資産の配置座標を計算 ---
    asset_positions: dict[str, tuple[float, float]] = {}

    # 単一接続資産は所属セグメント箱の中に並べる。各行は箱の中心に対して
    # 左右対称に配置する(端から詰めると、最終行が1件だけのときに大きく左へ
    # 寄り、長いラベルが箱の外へはみ出す)。
    single_homed: dict[str, list[Asset]] = {}
    for asset in topology.assets:
        seg_names = _asset_segment_names(asset)
        if len(seg_names) == 1 and seg_names[0] in seg_pos:
            single_homed.setdefault(seg_names[0], []).append(asset)

    for seg_name, members in single_homed.items():
        cx, cy = seg_pos[seg_name]
        top = cy - seg_heights[seg_name] / 2 + 58
        for row_start in range(0, len(members), _ASSET_COLS):
            row_members = members[row_start : row_start + _ASSET_COLS]
            row_index = row_start // _ASSET_COLS
            offset = (len(row_members) - 1) / 2
            for i, asset in enumerate(row_members):
                ax = cx + (i - offset) * _ASSET_COL_GAP
                ay = top + row_index * _ASSET_ROW_GAP
                asset_positions[asset.name] = (ax, ay)

    # マルチホーム資産: 接続する全セグメント箱の重心に配置
    for asset in topology.assets:
        if asset.name in asset_positions:
            continue
        seg_names = _asset_segment_names(asset)
        xs = [seg_pos[s][0] for s in seg_names if s in seg_pos]
        ys = [seg_pos[s][1] for s in seg_names if s in seg_pos]
        if xs and ys:
            asset_positions[asset.name] = (sum(xs) / len(xs), sum(ys) / len(ys))
        else:
            asset_positions[asset.name] = _CENTER

    # --- マルチホーム資産→各セグメント箱へのスポーク線(資産ノードより先に描画) ---
    for asset in topology.assets:
        seg_names = _asset_segment_names(asset)
        if len(seg_names) <= 1:
            continue
        ax, ay = asset_positions[asset.name]
        for seg_name in seg_names:
            if seg_name not in seg_pos:
                continue
            sx, sy = seg_pos[seg_name]
            svg_parts.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{sx:.1f}" y2="{sy:.1f}" '
                f'class="spoke" />'
            )

    # --- 資産ノード ---
    for asset in topology.assets:
        ax, ay = asset_positions[asset.name]
        color = _ROLE_COLORS.get(asset.role, "#888888")
        seg_names = _asset_segment_names(asset)
        ip_list = ", ".join(
            f"{net.segment}={net.ip or '(動的割当)'}" for net in asset.networks
        )
        title = f"{asset.name} [{asset.role}]\n{ip_list}"
        if asset.role == "structurer" and manifest.structuring is not None:
            protos = ", ".join(
                f"{p.name}→{p.output_index}" for p in manifest.structuring.protocols
            )
            if protos:
                title += f"\n構造化: {protos}"
        hosted_plugins = _plugins_on(manifest, asset.name)
        if hosted_plugins:
            title += "\n検知: " + ", ".join(hosted_plugins)
        if _is_caldera_host(manifest, asset.name):
            title += "\n攻撃エンジン: Caldera"
        viz_label = _visualization_host_label(manifest, asset.name)
        if viz_label is not None:
            title += f"\n可視化エンジン: {viz_label}"
        multihomed_ring = (
            f'<circle class="node-ring" cx="{ax:.1f}" cy="{ay:.1f}" r="{_NODE_R + 4}" fill="none" '
            f'stroke="{color}" stroke-width="1.5" opacity="0.5" />'
            if len(seg_names) > 1
            else ""
        )
        # 検知プラグインが載っている資産には、角ばったマーカーを重ねて
        # 「ここで検知が動いている」ことを図上で明示する(観測カバレッジの
        # バッジと同じ思想: 情報を持つノードは一目で分かるようにする)。
        detection_mark = (
            f'<rect x="{ax - _NODE_R - 5:.1f}" y="{ay - _NODE_R - 5:.1f}" '
            f'width="{2 * (_NODE_R + 5)}" height="{2 * (_NODE_R + 5)}" rx="3" '
            f'fill="none" stroke="{_DETECTION_MARK_COLOR}" stroke-width="1.5" '
            f'stroke-dasharray="3 2" />'
            if hosted_plugins
            else ""
        )
        svg_parts.append(
            f'<g class="asset-node">'
            f"{multihomed_ring}"
            f"{detection_mark}"
            f'<circle class="node-dot" cx="{ax:.1f}" cy="{ay:.1f}" r="{_NODE_R}" fill="{color}" '
            f'style="color:{color}" stroke="#0d1117" stroke-width="1.5">'
            f"<title>{_esc(title)}</title>"
            f"</circle>"
            f'<text x="{ax:.1f}" y="{ay + _NODE_R + 13:.1f}" class="asset-label" '
            f'text-anchor="middle">{_esc(asset.name)}</text>'
            f"</g>"
        )

    svg_body = "\n".join(svg_parts)

    # 凡例は、実際にこのマニフェストに登場するロールだけを出す(使われていない
    # ロールまで並べると、図から読み取れる情報と凡例が一致しなくなるため)。
    used_roles = [r for r in _ROLE_COLORS if any(a.role == r for a in topology.assets)]
    legend_items = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{_ROLE_COLORS[role]}">'
        f"</span>{_esc(role)}</div>"
        for role in used_roles
    )
    if mirror_to is not None:
        legend_items += (
            '<div class="legend-sep"></div>'
            f'<div class="legend-item"><span class="bar" style="background:{_OBSERVED_BORDER_COLOR}">'
            "</span>観測対象</div>"
            f'<div class="legend-item"><span class="bar" style="background:{_MIRROR_SINK_BORDER_COLOR}">'
            "</span>ミラー集約先</div>"
            f'<div class="legend-item"><span class="bar" style="background:{_BLIND_BORDER_COLOR}">'
            "</span>観測外（死角）</div>"
        )

    if manifest.detection is not None and manifest.detection.plugins:
        legend_items += (
            '<div class="legend-sep"></div>'
            f'<div class="legend-item"><span class="box" style="border-color:{_DETECTION_MARK_COLOR}">'
            "</span>検知プラグイン搭載</div>"
        )

    info_panel = _info_panel_html(manifest, observed, mirror_to)

    title_text = _esc(manifest.metadata.name)
    desc_text = _esc(manifest.metadata.description or "")
    layer_note = _layer_note(manifest)
    # ヘッダーのチップ表示用。_layer_note の文字列(" / "区切り)をそのまま
    # 再分割するだけで、判定ロジックは一切再実装しない(決定事項#50と同じ方針)。
    layer_chips = "".join(
        f'<span class="chip">{_esc(layer)}</span>' for layer in layer_note.split(" / ")
    )
    asset_count = len(topology.assets)
    segment_count = len(topology.segments)

    structuring_accent = _ROLE_COLORS["structurer"]
    visualization_accent = _ROLE_COLORS["visualization-engine"]

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Amenonuboco Network Diagram — {title_text}</title>
<style>
  :root {{
    --bg: #05070a;
    --panel: rgba(13, 17, 23, 0.82);
    --panel-solid: #0e1319;
    --border: rgba(90, 122, 145, 0.28);
    --border-strong: rgba(120, 156, 180, 0.45);
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: {_OBSERVED_BORDER_COLOR};
    --accent-soft: rgba(79, 209, 197, 0.14);
    --danger: {_BLIND_BORDER_COLOR};
    --mono: ui-monospace, "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    --sans: -apple-system, "Segoe UI", "Hiragino Kaku Gothic ProN", sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; margin: 0; }}
  body {{
    display: flex;
    flex-direction: column;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    overflow: hidden;
  }}
  /* うっすらとしたグリッド + ビネットで「監視卓」らしい空気を出す(CSSのみ、外部画像なし) */
  body::before {{
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background-image:
      linear-gradient(rgba(79, 209, 197, 0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(79, 209, 197, 0.05) 1px, transparent 1px),
      radial-gradient(ellipse at 50% 0%, rgba(79, 209, 197, 0.08), transparent 62%);
    background-size: 42px 42px, 42px 42px, 100% 100%;
  }}
  header {{
    position: relative;
    z-index: 2;
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    padding: 12px 22px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(16, 21, 28, 0.96), rgba(13, 17, 23, 0.9));
    backdrop-filter: blur(10px);
    flex-wrap: wrap;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; min-width: 0; }}
  .brand-glyph {{
    flex: 0 0 auto;
    width: 34px;
    height: 34px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--accent-soft);
    border: 1px solid rgba(79, 209, 197, 0.4);
    color: var(--accent);
    font-size: 16px;
  }}
  header h1 {{
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  header .subtitle {{
    margin: 2px 0 0 0;
    color: var(--muted);
    font-size: 11.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .header-meta {{ display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }}
  .status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    background: var(--accent-soft);
    border: 1px solid rgba(79, 209, 197, 0.35);
    color: var(--accent);
    font-family: var(--mono);
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.08em;
  }}
  .status-dot {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px 1px var(--accent);
    animation: pulse 1.8s ease-in-out infinite;
  }}
  @keyframes pulse {{
    0%, 100% {{ opacity: 1; transform: scale(1); }}
    50% {{ opacity: 0.45; transform: scale(0.75); }}
  }}
  .chips {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .chip {{
    padding: 3px 9px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 10.5px;
    font-family: var(--mono);
    white-space: nowrap;
  }}
  .stat-group {{ display: flex; gap: 16px; }}
  .stat {{ display: flex; flex-direction: column; align-items: flex-end; line-height: 1.1; }}
  .stat-value {{ font-family: var(--mono); font-size: 15px; font-weight: 700; color: var(--text); }}
  .stat-label {{ font-family: var(--mono); font-size: 9px; letter-spacing: 0.08em; color: var(--muted); }}
  #canvas-wrap {{
    position: relative;
    z-index: 1;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
    cursor: grab;
  }}
  #canvas-wrap.grabbing {{ cursor: grabbing; }}
  svg {{ display: block; width: 100%; height: 100%; }}
  .seg-label {{ fill: var(--text); font-size: 13px; font-weight: 600; }}
  .seg-sub {{ fill: var(--muted); font-size: 10px; }}
  .seg-badge {{ font-size: 10px; font-weight: 600; }}
  .seg-rect {{ filter: url(#segment-glow); }}
  .asset-label {{ fill: var(--text); font-size: 9px; }}
  .node-dot {{ filter: url(#node-glow); }}
  .spoke {{ stroke: #4a5568; stroke-width: 1.2; opacity: 0.6; }}
  .mirror-flow {{
    stroke: {_MIRROR_FLOW_COLOR};
    stroke-width: 1.5;
    stroke-dasharray: 6 5;
    opacity: 0.65;
    animation: flow 1.1s linear infinite;
  }}
  @keyframes flow {{ to {{ stroke-dashoffset: -22; }} }}
  .panel {{
    position: absolute;
    z-index: 3;
    background: var(--panel);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 12px;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
  }}
  .info-panel {{ left: 16px; top: 16px; min-width: 236px; max-width: 260px; }}
  .info-block {{ border-left: 2px solid transparent; padding-left: 10px; }}
  .info-block + .info-block {{
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
  }}
  .info-block--coverage {{ border-left-color: {_OBSERVED_BORDER_COLOR}; }}
  .info-block--structuring {{ border-left-color: {structuring_accent}; }}
  .info-block--detection {{ border-left-color: {_DETECTION_MARK_COLOR}; }}
  .info-block--visualization {{ border-left-color: {visualization_accent}; }}
  .info-title {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    margin-bottom: 6px;
    color: var(--text);
    font-size: 11.5px;
    letter-spacing: 0.02em;
  }}
  .info-icon {{ font-size: 10px; opacity: 0.85; }}
  .info-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    margin: 3px 0;
    color: var(--muted);
  }}
  .info-row code {{
    color: var(--text);
    font-family: var(--mono);
    font-size: 11px;
  }}
  .info-blind {{ margin-top: 5px; color: {_BLIND_BORDER_COLOR}; font-family: var(--mono); font-size: 11px; }}
  .info-ok {{ margin-top: 5px; color: {_OBSERVED_BORDER_COLOR}; font-family: var(--mono); font-size: 11px; }}
  .legend {{ right: 16px; bottom: 16px; }}
  .legend-item {{ display: flex; align-items: center; gap: 7px; margin: 4px 0; color: var(--muted); font-size: 11.5px; }}
  .dot {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; box-shadow: 0 0 5px 0 currentColor; }}
  .bar {{ width: 10px; height: 3px; border-radius: 2px; display: inline-block; }}
  .box {{ width: 9px; height: 9px; border: 1.5px dashed; border-radius: 2px; display: inline-block; }}
  .legend-sep {{ height: 1px; background: var(--border); margin: 7px 0; }}
  .zoom-toolbar {{
    position: absolute;
    z-index: 3;
    top: 16px;
    right: 16px;
    display: flex;
    align-items: center;
    gap: 2px;
    background: var(--panel);
    border: 1px solid var(--border-strong);
    border-radius: 8px;
    padding: 4px;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 28px rgba(0, 0, 0, 0.45);
  }}
  .zoom-toolbar button {{
    width: 26px;
    height: 26px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    border-radius: 6px;
    color: var(--text);
    font-size: 14px;
    cursor: pointer;
  }}
  .zoom-toolbar button:hover {{ background: var(--accent-soft); color: var(--accent); }}
  #zoom-readout {{
    min-width: 42px;
    text-align: center;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
  }}
  .hint {{
    position: absolute;
    z-index: 3;
    left: 16px;
    bottom: 16px;
    padding: 5px 10px;
    border-radius: 6px;
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--muted);
    font-family: var(--mono);
    font-size: 10px;
    backdrop-filter: blur(12px);
  }}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="brand-glyph">◈</span>
    <div>
      <h1>{title_text}</h1>
      <p class="subtitle">{desc_text}</p>
    </div>
  </div>
  <div class="header-meta">
    <span class="status-pill"><span class="status-dot"></span>LIVE</span>
    <div class="chips">{layer_chips}</div>
    <div class="stat-group">
      <div class="stat"><span class="stat-value">{asset_count}</span><span class="stat-label">ASSETS</span></div>
      <div class="stat"><span class="stat-value">{segment_count}</span><span class="stat-label">SEGMENTS</span></div>
    </div>
  </div>
</header>
<div id="canvas-wrap">
  <svg id="diagram" viewBox="0 0 {_VIEW_W} {_VIEW_H}"
       preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="mirror-arrow" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="{_MIRROR_FLOW_COLOR}" opacity="0.7" />
      </marker>
      <filter id="segment-glow" x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="0" stdDeviation="2.2" flood-color="#000000" flood-opacity="0.35" />
      </filter>
      <filter id="node-glow" x="-140%" y="-140%" width="380%" height="380%">
        <feDropShadow dx="0" dy="0" stdDeviation="2.4" flood-color="currentColor" flood-opacity="0.9" />
      </filter>
    </defs>
    <g id="viewport">
{svg_body}
    </g>
  </svg>
  {info_panel}
  <div class="panel legend">{legend_items}</div>
  <div class="zoom-toolbar">
    <button type="button" id="zoom-out" aria-label="ズームアウト">−</button>
    <span id="zoom-readout">100%</span>
    <button type="button" id="zoom-in" aria-label="ズームイン">＋</button>
    <button type="button" id="zoom-reset" aria-label="表示をリセット">⟲</button>
  </div>
  <div class="hint">SCROLL ズーム ・ DRAG パン ・ HOVER 詳細</div>
</div>
<script>
(function () {{
  var wrap = document.getElementById('canvas-wrap');
  var viewport = document.getElementById('viewport');
  var zoomReadout = document.getElementById('zoom-readout');
  var scale = 1, tx = 0, ty = 0;
  var dragging = false, lastX = 0, lastY = 0;

  function apply() {{
    viewport.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + scale + ')');
    zoomReadout.textContent = Math.round(scale * 100) + '%';
  }}

  function setScale(next) {{
    scale = Math.min(4, Math.max(0.3, next));
    apply();
  }}

  wrap.addEventListener('wheel', function (e) {{
    e.preventDefault();
    setScale(scale * (e.deltaY < 0 ? 1.1 : 0.9));
  }}, {{ passive: false }});

  wrap.addEventListener('mousedown', function (e) {{
    dragging = true;
    wrap.classList.add('grabbing');
    lastX = e.clientX; lastY = e.clientY;
  }});
  window.addEventListener('mouseup', function () {{
    dragging = false;
    wrap.classList.remove('grabbing');
  }});
  window.addEventListener('mousemove', function (e) {{
    if (!dragging) return;
    tx += (e.clientX - lastX);
    ty += (e.clientY - lastY);
    lastX = e.clientX; lastY = e.clientY;
    apply();
  }});

  document.getElementById('zoom-in').addEventListener('click', function () {{ setScale(scale * 1.2); }});
  document.getElementById('zoom-out').addEventListener('click', function () {{ setScale(scale * 0.8); }});
  document.getElementById('zoom-reset').addEventListener('click', function () {{
    scale = 1; tx = 0; ty = 0; apply();
  }});
}})();
</script>
</body>
</html>
"""
