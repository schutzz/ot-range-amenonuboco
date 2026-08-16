"""マニフェストのtopology層から、防御側・統裁側向けの自己完結HTMLネットワーク図を
生成する(Phase0決定事項#6の最小版、Phase1決定事項#25)。

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
- 観測カバレッジ・構造化・検知配置の情報は、対応する層が実装されるPhaseで
  追加する(本レンダラはPhase1時点ではトポロジ情報のみを描画する)。
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
    "eval-harness": "#8a7a4a",
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

_VIEW_W = 1100
_VIEW_H = 800
_CENTER = (_VIEW_W / 2, _VIEW_H / 2 + 20)
_SEGMENT_RADIUS = 300
_SEGMENT_BOX_W = 230
_SEGMENT_BOX_H = 140
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


def render_network_diagram(manifest: Manifest) -> str:
    topology: Topology = manifest.topology
    seg_pos = _segment_positions(topology.segments)

    svg_parts: list[str] = []

    # --- セグメント箱 ---
    for seg in topology.segments:
        cx, cy = seg_pos[seg.name]
        x, y = cx - _SEGMENT_BOX_W / 2, cy - _SEGMENT_BOX_H / 2
        fill = _SEGMENT_KIND_COLORS.get(seg.kind, "rgba(120,120,120,0.14)")
        svg_parts.append(
            f'<g class="segment">'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{_SEGMENT_BOX_W}" height="{_SEGMENT_BOX_H}" '
            f'rx="10" fill="{fill}" stroke="{_SEGMENT_BORDER_COLOR}" stroke-width="1.5">'
            f"<title>{_esc(seg.name)} ({_esc(seg.cidr)}) — {_esc(seg.kind)}</title>"
            f"</rect>"
            f'<text x="{cx:.1f}" y="{y + 18:.1f}" class="seg-label" text-anchor="middle">'
            f"{_esc(seg.name)}</text>"
            f'<text x="{cx:.1f}" y="{y + 34:.1f}" class="seg-sub" text-anchor="middle">'
            f"{_esc(seg.cidr)} · {_esc(seg.kind)}</text>"
            f"</g>"
        )

    # --- 資産の配置座標を計算 ---
    asset_positions: dict[str, tuple[float, float]] = {}
    single_homed_slot: dict[str, int] = {}  # segment名 -> 次に置くスロット番号

    for asset in topology.assets:
        seg_names = _asset_segment_names(asset)
        if len(seg_names) == 1:
            seg_name = seg_names[0]
            cx, cy = seg_pos[seg_name]
            slot = single_homed_slot.get(seg_name, 0)
            single_homed_slot[seg_name] = slot + 1
            col = slot % 3
            row = slot // 3
            ax = cx - _SEGMENT_BOX_W / 2 + 40 + col * 75
            ay = cy - _SEGMENT_BOX_H / 2 + 60 + row * 30
            asset_positions[asset.name] = (ax, ay)
        else:
            # マルチホーム資産: 接続する全セグメント箱の重心に配置
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
        multihomed_ring = (
            f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="{_NODE_R + 4}" fill="none" '
            f'stroke="{color}" stroke-width="1.5" opacity="0.5" />'
            if len(seg_names) > 1
            else ""
        )
        svg_parts.append(
            f'<g class="asset-node">'
            f"{multihomed_ring}"
            f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="{_NODE_R}" fill="{color}" '
            f'stroke="#0d1117" stroke-width="1.5">'
            f"<title>{_esc(title)}</title>"
            f"</circle>"
            f'<text x="{ax:.1f}" y="{ay + _NODE_R + 13:.1f}" class="asset-label" '
            f'text-anchor="middle">{_esc(asset.name)}</text>'
            f"</g>"
        )

    svg_body = "\n".join(svg_parts)

    legend_items = "".join(
        f'<div class="legend-item"><span class="dot" style="background:{color}"></span>{_esc(role)}</div>'
        for role, color in _ROLE_COLORS.items()
    )

    title_text = _esc(manifest.metadata.name)
    desc_text = _esc(manifest.metadata.description or "")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Amenonuboco Network Diagram — {title_text}</title>
<style>
  :root {{
    --bg: #0d1117;
    --panel: #161b22;
    --text: #c9d1d9;
    --muted: #8b949e;
    --border: #30363d;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "Segoe UI", "Hiragino Kaku Gothic ProN", sans-serif;
  }}
  header {{
    padding: 16px 24px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
  }}
  header h1 {{ margin: 0 0 4px 0; font-size: 18px; }}
  header p {{ margin: 0; color: var(--muted); font-size: 13px; }}
  #canvas-wrap {{
    width: 100%;
    height: calc(100vh - 90px);
    overflow: hidden;
    cursor: grab;
  }}
  #canvas-wrap.grabbing {{ cursor: grabbing; }}
  svg {{ display: block; }}
  .seg-label {{ fill: var(--text); font-size: 13px; font-weight: 600; }}
  .seg-sub {{ fill: var(--muted); font-size: 10px; }}
  .asset-label {{ fill: var(--text); font-size: 10px; }}
  .spoke {{ stroke: #4a5568; stroke-width: 1.2; opacity: 0.6; }}
  .legend {{
    position: fixed;
    right: 16px;
    bottom: 16px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
</style>
</head>
<body>
<header>
  <h1>Amenonuboco Network Diagram — {title_text}</h1>
  <p>{desc_text}（トポロジ層のみ・Phase 1時点。マウスホイールでズーム、ドラッグでパン。ノードにカーソルを合わせると詳細を表示）</p>
</header>
<div id="canvas-wrap">
  <svg id="diagram" viewBox="0 0 {_VIEW_W} {_VIEW_H}" xmlns="http://www.w3.org/2000/svg">
    <g id="viewport">
{svg_body}
    </g>
  </svg>
</div>
<div class="legend">{legend_items}</div>
<script>
(function () {{
  var wrap = document.getElementById('canvas-wrap');
  var svg = document.getElementById('diagram');
  var viewport = document.getElementById('viewport');
  var scale = 1, tx = 0, ty = 0;
  var dragging = false, lastX = 0, lastY = 0;

  function apply() {{
    viewport.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + scale + ')');
  }}

  wrap.addEventListener('wheel', function (e) {{
    e.preventDefault();
    var delta = e.deltaY < 0 ? 1.1 : 0.9;
    scale = Math.min(4, Math.max(0.3, scale * delta));
    apply();
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
}})();
</script>
</body>
</html>
"""
