// ネットワーク図のプレビュー描画。
//
// platform/renderers/network_diagram.py のレイアウト計算をJSへ移植したもの
// (Phase8決定事項#117)。配色・レイアウト定数は一切ハードコードせず、
// vocab.js(Pythonスキーマからの生成物)から読む。
//
// 重要: これは**プレビュー**であり、確定版の図ではない(決定事項#118)。
// README・記事・登壇資料に載せる図は `python cli.py diagram` が生成した
// Python版を使う。JS側の役割は「編集中に形が即座に見えること」に限る。

(function (global) {
  'use strict';

  const V = global.AMENONUBOCO_VOCAB;
  const L = V.layout;
  const C = V.colors;

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  // --- 観測カバレッジ判定 ---------------------------------------------------
  // オプトアウト方式(mirror_to自身とexcludeを除く全セグメントが観測対象)。
  // Python側は Instrumentation.observed_segments に判定を委ねており、図側で
  // 再実装していない。JS側は委譲できないので同じ規則をここに置くが、
  // tests/test_gui_parity.py で Python 側との一致を確認する。
  function coverage(model) {
    const inst = model.instrumentation;
    if (!inst || !inst.mirror_to) {
      return { observed: new Set(), mirrorTo: null };
    }
    const skip = new Set([inst.mirror_to, ...(inst.exclude || [])]);
    const observed = new Set(
      (model.topology.segments || [])
        .map((s) => s.name)
        .filter((name) => !skip.has(name))
    );
    return { observed, mirrorTo: inst.mirror_to };
  }

  function assetSegmentNames(asset) {
    return (asset.networks || []).map((n) => n.segment);
  }

  // --- 箱の高さ(単一接続する資産の行数に追従させる) -------------------------
  function segmentBoxHeights(topology) {
    const counts = {};
    for (const asset of topology.assets || []) {
      const segNames = assetSegmentNames(asset);
      if (segNames.length === 1) {
        counts[segNames[0]] = (counts[segNames[0]] || 0) + 1;
      }
    }
    const heights = {};
    for (const seg of topology.segments || []) {
      const n = counts[seg.name] || 0;
      const rows = n > 0 ? Math.ceil(n / L.assetCols) : 0;
      const contentHeight = 58 + Math.max(rows - 1, 0) * L.assetRowGap + 70;
      heights[seg.name] = Math.max(L.segmentBoxH, contentHeight);
    }
    return heights;
  }

  // --- 円周半径(セグメント数・箱サイズに応じて広げる) -----------------------
  function requiredSegmentRadius(segments, boxHeights) {
    const n = segments.length;
    if (n <= 1) return L.segmentRadius;
    const maxHalfDiag = Math.max(
      ...segments.map((s) => Math.hypot(L.segmentBoxW, boxHeights[s.name]) / 2)
    );
    const margin = 30.0;
    const chordNeeded = 2 * maxHalfDiag + margin;
    const angleStep = (2 * Math.PI) / n;
    const required = chordNeeded / (2 * Math.sin(angleStep / 2));
    return Math.max(L.segmentRadius, required);
  }

  function canvasGeometry(segments, boxHeights) {
    const radius = requiredSegmentRadius(segments, boxHeights);
    const maxHalfDiag = segments.length
      ? Math.max(
          ...segments.map((s) => Math.hypot(L.segmentBoxW, boxHeights[s.name]) / 2)
        )
      : 0.0;
    const pad = 60.0;
    const needed = 2 * (radius + maxHalfDiag) + 2 * pad;
    const viewW = Math.max(L.viewW, needed);
    const viewH = Math.max(L.viewH, needed);
    return { viewW, viewH, center: [viewW / 2, viewH / 2 + 20], radius };
  }

  function segmentPositions(segments, center, radius) {
    const n = segments.length;
    const positions = {};
    segments.forEach((seg, i) => {
      const angle = n > 0 ? (2 * Math.PI * i) / n - Math.PI / 2 : 0.0;
      positions[seg.name] = [
        center[0] + radius * Math.cos(angle),
        center[1] + radius * Math.sin(angle),
      ];
    });
    return positions;
  }

  function segmentBorder(segName, observed, mirrorTo) {
    if (mirrorTo === null) return [C.segmentBorder, 1.5];
    if (segName === mirrorTo) return [C.mirrorSinkBorder, 2.0];
    if (observed.has(segName)) return [C.observedBorder, 2.0];
    return [C.blindBorder, 2.0];
  }

  function coverageBadge(segName, observed, mirrorTo) {
    if (mirrorTo === null) return '';
    if (segName === mirrorTo) return '◎ ミラー集約先';
    if (observed.has(segName)) return '◉ 観測対象';
    return '✕ 観測外（死角）';
  }

  function mirrorFlowLines(segPos, segHeights, observed, mirrorTo) {
    if (mirrorTo === null || !(mirrorTo in segPos)) return [];
    const [mx, my] = segPos[mirrorTo];
    const mHalfH = segHeights[mirrorTo] / 2 + 9;
    const lines = [];
    for (const name of [...observed].sort()) {
      if (!(name in segPos)) continue;
      const [sx, sy] = segPos[name];
      const sHalfH = segHeights[name] / 2 + 9;
      const dx = mx - sx;
      const dy = my - sy;
      const dist = Math.hypot(dx, dy) || 1.0;
      const ux = dx / dist;
      const uy = dy / dist;
      const x1 = sx + ux * 152;
      const y1 = sy + uy * sHalfH;
      const x2 = mx - ux * 152;
      const y2 = my - uy * mHalfH;
      lines.push(
        `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" ` +
          `x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" ` +
          `class="mirror-flow" marker-end="url(#mirror-arrow)">` +
          `<title>${esc(name)} のトラフィックが ${esc(mirrorTo)} へミラーされる</title>` +
          `</line>`
      );
    }
    return lines;
  }

  // --- 本体 -----------------------------------------------------------------

  function render(model) {
    const topology = model.topology || { segments: [], assets: [] };
    const segments = topology.segments || [];
    const assets = topology.assets || [];

    if (!segments.length) {
      return {
        svg: '',
        viewW: L.viewW,
        viewH: L.viewH,
        legend: '',
        empty: true,
      };
    }

    const segHeights = segmentBoxHeights(topology);
    const { viewW, viewH, center, radius } = canvasGeometry(segments, segHeights);
    const segPos = segmentPositions(segments, center, radius);
    const { observed, mirrorTo } = coverage(model);

    const parts = [];

    // ミラーフロー線は箱より先に描き、箱の下に潜らせる
    parts.push(...mirrorFlowLines(segPos, segHeights, observed, mirrorTo));

    // セグメント箱
    for (const seg of segments) {
      const [cx, cy] = segPos[seg.name];
      const boxH = segHeights[seg.name];
      const x = cx - L.segmentBoxW / 2;
      const y = cy - boxH / 2;
      const kindSpec = V.segmentKinds[seg.kind];
      const fill = kindSpec ? kindSpec.fill : 'rgba(120,120,120,0.14)';
      const [borderColor, borderW] = segmentBorder(seg.name, observed, mirrorTo);
      const badge = coverageBadge(seg.name, observed, mirrorTo);
      const badgeEl = badge
        ? `<text x="${cx.toFixed(1)}" y="${(y + boxH - 8).toFixed(1)}" class="seg-badge" ` +
          `text-anchor="middle" fill="${borderColor}">${esc(badge)}</text>`
        : '';
      let title = `${seg.name} (${seg.cidr}) — ${seg.kind}`;
      if (badge) title += `\n${badge}`;
      parts.push(
        `<g class="segment">` +
          `<rect class="seg-rect" x="${x.toFixed(1)}" y="${y.toFixed(1)}" ` +
          `width="${L.segmentBoxW}" height="${boxH.toFixed(1)}" rx="10" ` +
          `fill="${fill}" stroke="${borderColor}" stroke-width="${borderW}">` +
          `<title>${esc(title)}</title></rect>` +
          `<text x="${cx.toFixed(1)}" y="${(y + 18).toFixed(1)}" class="seg-label" ` +
          `text-anchor="middle">${esc(seg.name)}</text>` +
          `<text x="${cx.toFixed(1)}" y="${(y + 34).toFixed(1)}" class="seg-sub" ` +
          `text-anchor="middle">${esc(seg.cidr)} · ${esc(seg.kind)}</text>` +
          badgeEl +
          `</g>`
      );
    }

    // 資産の配置座標。単一接続はセグメント箱の中に左右対称で並べ、
    // マルチホームは接続する全セグメント箱の重心に置く。
    const assetPositions = {};
    const singleHomed = {};
    for (const asset of assets) {
      const segNames = assetSegmentNames(asset);
      if (segNames.length === 1 && segNames[0] in segPos) {
        (singleHomed[segNames[0]] = singleHomed[segNames[0]] || []).push(asset);
      }
    }
    for (const [segName, members] of Object.entries(singleHomed)) {
      const [cx, cy] = segPos[segName];
      const top = cy - segHeights[segName] / 2 + 58;
      for (let rowStart = 0; rowStart < members.length; rowStart += L.assetCols) {
        const rowMembers = members.slice(rowStart, rowStart + L.assetCols);
        const rowIndex = Math.floor(rowStart / L.assetCols);
        const offset = (rowMembers.length - 1) / 2;
        rowMembers.forEach((asset, i) => {
          assetPositions[asset.name] = [
            cx + (i - offset) * L.assetColGap,
            top + rowIndex * L.assetRowGap,
          ];
        });
      }
    }
    for (const asset of assets) {
      if (asset.name in assetPositions) continue;
      const segNames = assetSegmentNames(asset).filter((s) => s in segPos);
      if (segNames.length) {
        const xs = segNames.map((s) => segPos[s][0]);
        const ys = segNames.map((s) => segPos[s][1]);
        assetPositions[asset.name] = [
          xs.reduce((a, b) => a + b, 0) / xs.length,
          ys.reduce((a, b) => a + b, 0) / ys.length,
        ];
      } else {
        assetPositions[asset.name] = center;
      }
    }

    // マルチホーム資産 → 各セグメント箱へのスポーク線(資産ノードより先に描画)
    for (const asset of assets) {
      const segNames = assetSegmentNames(asset);
      if (segNames.length <= 1) continue;
      const [ax, ay] = assetPositions[asset.name];
      for (const segName of segNames) {
        if (!(segName in segPos)) continue;
        const [sx, sy] = segPos[segName];
        parts.push(
          `<line x1="${ax.toFixed(1)}" y1="${ay.toFixed(1)}" ` +
            `x2="${sx.toFixed(1)}" y2="${sy.toFixed(1)}" class="spoke" />`
        );
      }
    }

    // 資産ノード
    for (const asset of assets) {
      const [ax, ay] = assetPositions[asset.name];
      const roleSpec = V.roles[asset.role];
      const color = roleSpec ? roleSpec.color : '#888888';
      const segNames = assetSegmentNames(asset);
      const ipList = (asset.networks || [])
        .map((n) => `${n.segment}=${n.ip || '(動的割当)'}`)
        .join(', ');
      let title = `${asset.name} [${asset.role}]\n${ipList}`;
      if (asset.role === 'structurer' && model.structuring) {
        const protos = (model.structuring.protocols || [])
          .map((p) => `${p.name}→${p.output_index}`)
          .join(', ');
        if (protos) title += `\n構造化: ${protos}`;
      }
      const multihomedRing =
        segNames.length > 1
          ? `<circle class="node-ring" cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" ` +
            `r="${L.nodeR + 4}" fill="none" stroke="${color}" stroke-width="1.5" opacity="0.5" />`
          : '';
      parts.push(
        `<g class="asset-node">` +
          multihomedRing +
          `<circle class="node-dot" cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" ` +
          `r="${L.nodeR}" fill="${color}" style="color:${color}" stroke="#0d1117" stroke-width="1.5">` +
          `<title>${esc(title)}</title></circle>` +
          `<text x="${ax.toFixed(1)}" y="${(ay + L.nodeR + 13).toFixed(1)}" ` +
          `class="asset-label" text-anchor="middle">${esc(asset.name)}</text>` +
          `</g>`
      );
    }

    // 凡例は実際に登場するロールだけを出す(使われていないロールまで並べると、
    // 図から読み取れる情報と凡例が一致しなくなるため)
    const usedRoles = Object.keys(V.roles).filter((r) =>
      assets.some((a) => a.role === r)
    );
    let legend = usedRoles
      .map(
        (role) =>
          `<div class="legend-item"><span class="dot" style="background:${V.roles[role].color}"></span>${esc(role)}</div>`
      )
      .join('');
    if (mirrorTo !== null) {
      legend +=
        '<div class="legend-sep"></div>' +
        `<div class="legend-item"><span class="bar" style="background:${C.observedBorder}"></span>観測対象</div>` +
        `<div class="legend-item"><span class="bar" style="background:${C.mirrorSinkBorder}"></span>ミラー集約先</div>` +
        `<div class="legend-item"><span class="bar" style="background:${C.blindBorder}"></span>観測外（死角）</div>`;
    }

    return { svg: parts.join('\n'), viewW, viewH, legend, empty: false };
  }

  global.AmenonubocoDiagram = {
    render,
    coverage,
    segmentBoxHeights,
    requiredSegmentRadius,
    canvasGeometry,
    segmentPositions,
  };
})(typeof window !== 'undefined' ? window : globalThis);
