// GUIのUI配線。
//
// データの流れは一方向に固定する(Phase8決定事項#119の実装方針):
//     フォーム操作 → モデル更新 → 検証 → 図とYAMLを再描画
// 図は編集結果から毎回作り直す。既存のネットワーク図が円周上の自動レイアウト
// である以上、座標を保持する概念が無く、保持しない方が構造的に正しい。

(function (global) {
  'use strict';

  const V = global.AMENONUBOCO_VOCAB;
  const Samples = global.AMENONUBOCO_SAMPLES;
  const M = global.AmenonubocoModel;
  const Diagram = global.AmenonubocoDiagram;
  const Validate = global.AmenonubocoValidate;
  const Yaml = global.AmenonubocoYaml;

  const ROLES = Object.keys(V.roles).sort();
  const KINDS = Object.keys(V.segmentKinds).sort();

  let model = M.emptyModel();
  // 図のズーム・パンは再描画をまたいで保持する(編集のたびに視点が戻ると使えない)
  let view = { scale: 1, tx: 0, ty: 0 };

  const $ = (id) => document.getElementById(id);

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#x27;');
  }

  function options(values, selected) {
    return values
      .map(
        (v) =>
          `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`
      )
      .join('');
  }

  // --- フォーム描画 ---------------------------------------------------------

  function renderMetadata() {
    return `
      <div class="section">
        <div class="section-head"><span class="section-title">メタデータ</span></div>
        <div class="field">
          <label>name</label>
          <input type="text" data-bind="metadata.name" value="${esc(model.metadata.name)}">
        </div>
        <div class="field">
          <label>description</label>
          <input type="text" data-bind="metadata.description" value="${esc(model.metadata.description || '')}">
        </div>
      </div>`;
  }

  function renderSegments() {
    const cards = model.topology.segments
      .map(
        (seg, i) => {
          const imp = seg.impairment || {};
          return `
        <div class="card">
          <div class="card-head">
            <span class="card-title">${esc(seg.name)}</span>
            <button type="button" class="btn btn-sm btn-danger" data-action="remove-segment" data-index="${i}">削除</button>
          </div>
          <div class="field">
            <label>name</label>
            <input type="text" data-action="rename-segment" data-index="${i}" value="${esc(seg.name)}">
          </div>
          <div class="field-row">
            <div class="field">
              <label>cidr</label>
              <input type="text" data-bind="segment.cidr" data-index="${i}" value="${esc(seg.cidr)}">
            </div>
            <div class="field">
              <label>kind</label>
              <select data-bind="segment.kind" data-index="${i}">${options(KINDS, seg.kind)}</select>
            </div>
          </div>
          <div class="field" style="margin-top:6px;padding-top:6px;border-top:1px dashed #444">
            <label style="font-size:0.85em;color:#aaa">回線劣化エミュレーション (tc-netem: オプション)</label>
            <div class="field-row">
              <div class="field">
                <label style="font-size:0.75em">delay (例: 100ms)</label>
                <input type="text" data-bind="segment.impairment.delay" data-index="${i}" value="${esc(imp.delay || '')}">
              </div>
              <div class="field">
                <label style="font-size:0.75em">jitter (例: 20ms)</label>
                <input type="text" data-bind="segment.impairment.jitter" data-index="${i}" value="${esc(imp.jitter || '')}">
              </div>
            </div>
            <div class="field-row" style="margin-top:4px">
              <div class="field">
                <label style="font-size:0.75em">loss (例: 1.5%)</label>
                <input type="text" data-bind="segment.impairment.loss" data-index="${i}" value="${esc(imp.loss || '')}">
              </div>
              <div class="field">
                <label style="font-size:0.75em">rate (例: 9600bit)</label>
                <input type="text" data-bind="segment.impairment.rate" data-index="${i}" value="${esc(imp.rate || '')}">
              </div>
            </div>
          </div>
        </div>`;
        }
      )
      .join('');

    return `
      <div class="section">
        <div class="section-head">
          <span class="section-title">セグメント（${model.topology.segments.length}）</span>
          <button type="button" class="btn btn-sm" data-action="add-segment">＋ 追加</button>
        </div>
        ${cards || '<div class="empty-note">セグメントがまだありません。まず1つ追加してください。</div>'}
      </div>`;
  }

  function renderAssetNetworks(asset, assetIndex) {
    const segNames = model.topology.segments.map((s) => s.name);
    if (!segNames.length) {
      return '<div class="empty-note">先にセグメントを追加してください。</div>';
    }
    const rows = asset.networks
      .map(
        (net, ni) => `
        <div class="field-row" style="margin-top:5px">
          <select data-bind="network.segment" data-index="${assetIndex}" data-net="${ni}">
            ${options(segNames, net.segment)}
          </select>
          <input type="text" placeholder="IP（空欄=動的割当）" data-bind="network.ip"
                 data-index="${assetIndex}" data-net="${ni}" value="${esc(net.ip || '')}">
          <button type="button" class="btn btn-sm btn-danger" style="flex:0 0 auto"
                  data-action="remove-network" data-index="${assetIndex}" data-net="${ni}">×</button>
        </div>`
      )
      .join('');
    return (
      rows +
      `<button type="button" class="btn btn-sm" style="margin-top:6px"
               data-action="add-network" data-index="${assetIndex}">＋ 接続先を追加</button>`
    );
  }

  function renderAssets() {
    const assetNames = model.topology.assets.map((a) => a.name);
    const cards = model.topology.assets
      .map((asset, i) => {
        const preset = M.presetFor(asset.role);
        const presetBits = [];
        if (preset.cap_add.length) presetBits.push(`cap_add: ${preset.cap_add.join(', ')}`);
        if (preset.sysctls.length) presetBits.push(`sysctls: ${preset.sysctls.join(', ')}`);
        const presetHint = presetBits.length
          ? `<div class="preset-hint">ロール既定 → ${esc(presetBits.join(' / '))}</div>`
          : '<div class="preset-hint">ロール既定 → 追加権限なし</div>';

        const pp = asset.physical_process || {};
        const otherAssets = assetNames.filter((n) => n !== asset.name);

        return `
        <div class="card">
          <div class="card-head">
            <span class="card-title">${esc(asset.name)}</span>
            <button type="button" class="btn btn-sm btn-danger" data-action="remove-asset" data-index="${i}">削除</button>
          </div>
          <div class="field">
            <label>name</label>
            <input type="text" data-action="rename-asset" data-index="${i}" value="${esc(asset.name)}">
          </div>
          <div class="field">
            <label>role</label>
            <select data-bind="asset.role" data-index="${i}">${options(ROLES, asset.role)}</select>
            ${presetHint}
          </div>
          <div class="field">
            <label>image</label>
            <input type="text" data-bind="asset.image" data-index="${i}" value="${esc(asset.image)}">
          </div>
          <div class="field">
            <label>networks</label>
            ${renderAssetNetworks(asset, i)}
          </div>
          <div class="field">
            <label>overrides.command</label>
            <textarea data-bind="asset.command" data-index="${i}"
                      placeholder="未指定ならロール既定">${esc(asset.overrides.command || '')}</textarea>
          </div>
          <div class="field">
            <label>overrides.ports（カンマ区切り）</label>
            <input type="text" data-bind="asset.ports" data-index="${i}"
                   placeholder="例: 18800:1880" value="${esc((asset.overrides.ports || []).join(', '))}">
          </div>
          <div class="field" style="margin-top:6px;padding-top:6px;border-top:1px dashed #444">
            <label style="font-size:0.85em;color:#aaa">物理プロセス連動 (Digital Twin: オプション)</label>
            <div class="field-row">
              <div class="field">
                <label style="font-size:0.75em">type</label>
                <input type="text" data-bind="asset.physical_process.type" data-index="${i}"
                       placeholder="tank_level" value="${esc(pp.type || '')}">
              </div>
              <div class="field">
                <label style="font-size:0.75em">observed_by (別セグメント必須)</label>
                <select data-bind="asset.physical_process.observed_by" data-index="${i}">
                  <option value=""${!pp.observed_by ? ' selected' : ''}>（未設定）</option>
                  ${options(otherAssets, pp.observed_by || '')}
                </select>
              </div>
            </div>
            <div class="field-row" style="margin-top:4px">
              <div class="field">
                <label style="font-size:0.75em">initial_level</label>
                <input type="number" step="any" data-bind="asset.physical_process.initial_level" data-index="${i}"
                       value="${pp.initial_level !== undefined && pp.initial_level !== null ? pp.initial_level : ''}">
              </div>
              <div class="field">
                <label style="font-size:0.75em">capacity</label>
                <input type="number" step="any" data-bind="asset.physical_process.capacity" data-index="${i}"
                       value="${pp.capacity !== undefined && pp.capacity !== null ? pp.capacity : ''}">
              </div>
            </div>
          </div>
        </div>`;
      })
      .join('');

    return `
      <div class="section">
        <div class="section-head">
          <span class="section-title">資産（${model.topology.assets.length}）</span>
          <button type="button" class="btn btn-sm" data-action="add-asset">＋ 追加</button>
        </div>
        ${cards || '<div class="empty-note">資産がまだありません。</div>'}
      </div>`;
  }

  function renderRouting() {
    const routers = model.topology.assets
      .filter((a) => a.role === 'l3-router')
      .map((a) => a.name);
    const current = (model.topology.routing && model.topology.routing.gateway) || '';
    const body = routers.length
      ? `<select data-bind="routing.gateway">
           <option value=""${current ? '' : ' selected'}>（未設定）</option>
           ${options(routers, current)}
         </select>`
      : '<div class="empty-note">ロール l3-router の資産がありません。先に1つ作ってください。</div>';

    return `
      <div class="section">
        <div class="section-head"><span class="section-title">ルーティング</span></div>
        <div class="section-note">ゲートウェイは全セグメントに接続し、セグメント間の経路を担います。計装層（ミラーリング）の実行主体にもなります。</div>
        <div class="field">${body}</div>
      </div>`;
  }

  function renderInstrumentation() {
    const enabled = !!model.instrumentation;
    const segNames = model.topology.segments.map((s) => s.name);
    let body = `
      <div class="checkbox-item" style="margin-bottom:8px">
        <input type="checkbox" id="inst-enabled" data-action="toggle-instrumentation" ${enabled ? 'checked' : ''}>
        <label for="inst-enabled" style="margin:0;text-transform:none;letter-spacing:0">計装層を有効にする</label>
      </div>`;

    if (enabled) {
      const exclude = model.instrumentation.exclude || [];
      const candidates = segNames.filter((n) => n !== model.instrumentation.mirror_to);
      body += `
        <div class="field">
          <label>mirror_to（ミラー集約先）</label>
          <select data-bind="instrumentation.mirror_to">
            <option value="">（未設定）</option>
            ${options(segNames, model.instrumentation.mirror_to)}
          </select>
        </div>
        <div class="field">
          <label>exclude（観測から外すセグメント）</label>
          <div class="checkbox-grid">
            ${
              candidates.length
                ? candidates
                    .map(
                      (n) => `
              <span class="checkbox-item">
                <input type="checkbox" data-action="toggle-exclude" data-segment="${esc(n)}"
                       ${exclude.includes(n) ? 'checked' : ''}>
                ${esc(n)}
              </span>`
                    )
                    .join('')
                : '<span class="empty-note">対象がありません</span>'
            }
          </div>
        </div>`;
    }

    return `
      <div class="section">
        <div class="section-head"><span class="section-title">計装層（ミラーリング）</span></div>
        <div class="section-note">観測はオプトアウト方式です。ミラー集約先を決めれば、他の全セグメントが自動で観測対象になります。セグメントを足したときの観測漏れを構造的に防ぐための仕様です。</div>
        ${body}
      </div>`;
  }

  function renderStructuring() {
    const enabled = !!model.structuring;
    let body = `
      <div class="checkbox-item" style="margin-bottom:8px">
        <input type="checkbox" id="struct-enabled" data-action="toggle-structuring" ${enabled ? 'checked' : ''}>
        <label for="struct-enabled" style="margin:0;text-transform:none;letter-spacing:0">構造化層を有効にする</label>
      </div>`;

    if (enabled) {
      const rows = (model.structuring.protocols || [])
        .map(
          (p, i) => `
          <div class="field-row" style="margin-top:5px">
            <input type="text" placeholder="プロトコル" data-bind="protocol.name" data-index="${i}" value="${esc(p.name)}">
            <input type="text" placeholder="出力index" data-bind="protocol.index" data-index="${i}" value="${esc(p.output_index)}">
            <button type="button" class="btn btn-sm btn-danger" style="flex:0 0 auto"
                    data-action="remove-protocol" data-index="${i}">×</button>
          </div>`
        )
        .join('');
      body += `
        <div class="field">
          <label>protocols</label>
          ${rows || '<div class="empty-note">プロトコルが未登録です。</div>'}
          <button type="button" class="btn btn-sm" style="margin-top:6px" data-action="add-protocol">＋ 追加</button>
        </div>`;
    }

    return `
      <div class="section">
        <div class="section-head"><span class="section-title">構造化層（tshark）</span></div>
        <div class="section-note">1プロトコル＝1つの専用tsharkプロセス＝1つの専用indexという対応で配線されます。計装層が前提です。</div>
        ${body}
      </div>`;
  }

  function renderForm() {
    $('form-pane').innerHTML =
      renderMetadata() +
      renderSegments() +
      renderAssets() +
      renderRouting() +
      renderInstrumentation() +
      renderStructuring();
  }

  // --- 図・検証・YAML -------------------------------------------------------

  function applyView() {
    const vp = $('viewport');
    if (!vp) return;
    vp.setAttribute(
      'transform',
      `translate(${view.tx},${view.ty}) scale(${view.scale})`
    );
    $('zoom-readout').textContent = `${Math.round(view.scale * 100)}%`;
  }

  function renderDiagram() {
    const result = Diagram.render(model);
    const svg = $('diagram');
    if (result.empty) {
      svg.style.display = 'none';
      $('canvas-empty').style.display = 'flex';
      $('legend').innerHTML = '';
    } else {
      svg.style.display = 'block';
      $('canvas-empty').style.display = 'none';
      svg.setAttribute(
        'viewBox',
        `0 0 ${result.viewW.toFixed(0)} ${result.viewH.toFixed(0)}`
      );
      $('viewport').innerHTML = result.svg;
      $('legend').innerHTML = result.legend;
    }
    applyView();

    $('stat-assets').textContent = model.topology.assets.length;
    $('stat-segments').textContent = model.topology.segments.length;
  }

  function renderIssues() {
    const { errors, warnings } = Validate.validate(model);
    const parts = [];
    for (const e of errors) {
      parts.push(
        `<div class="issue issue-error"><span class="issue-mark">✕</span><span>${esc(e.message)}</span></div>`
      );
    }
    for (const w of warnings) {
      parts.push(
        `<div class="issue issue-warn"><span class="issue-mark">!</span><span>${esc(w.message)}</span></div>`
      );
    }
    if (!parts.length && model.topology.segments.length) {
      parts.push('<div class="issue-ok"><span>✓</span><span>検証エラーなし</span></div>');
    }
    $('issues').innerHTML = parts.join('');
    $('export-btn').disabled = errors.length > 0;
    return errors.length === 0;
  }

  function renderYaml() {
    $('yaml-out').textContent = Yaml.dump(model);
  }

  function refresh(rerenderForm) {
    if (rerenderForm !== false) renderForm();
    renderDiagram();
    renderIssues();
    renderYaml();
  }

  // --- イベント -------------------------------------------------------------

  function assetAt(el) {
    return model.topology.assets[Number(el.dataset.index)];
  }

  function onInput(event) {
    const el = event.target;
    const bind = el.dataset.bind;
    const action = el.dataset.action;
    const value = el.value;
    // 入力欄の再描画はカーソル位置を壊すため、値の反映だけで済むものは
    // フォームを描き直さない(rerenderForm=false)。
    let rerenderForm = false;

    if (action === 'rename-segment') {
      M.renameSegment(model, Number(el.dataset.index), value);
    } else if (action === 'rename-asset') {
      M.renameAsset(model, Number(el.dataset.index), value);
    } else if (bind === 'metadata.name') {
      model.metadata.name = value;
    } else if (bind === 'metadata.description') {
      model.metadata.description = value;
    } else if (bind === 'segment.cidr') {
      model.topology.segments[Number(el.dataset.index)].cidr = value;
    } else if (bind === 'segment.kind') {
      model.topology.segments[Number(el.dataset.index)].kind = value;
    } else if (bind === 'asset.role') {
      assetAt(el).role = value;
      rerenderForm = true; // プリセット表示とルーティング候補が変わる
    } else if (bind === 'asset.image') {
      assetAt(el).image = value;
    } else if (bind === 'asset.command') {
      assetAt(el).overrides.command = value.trim() === '' ? null : value;
    } else if (bind === 'asset.ports') {
      assetAt(el).overrides.ports = value
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    } else if (bind === 'network.segment') {
      assetAt(el).networks[Number(el.dataset.net)].segment = value;
    } else if (bind === 'network.ip') {
      assetAt(el).networks[Number(el.dataset.net)].ip =
        value.trim() === '' ? null : value.trim();
    } else if (bind === 'routing.gateway') {
      model.topology.routing = value ? { gateway: value } : null;
    } else if (bind === 'instrumentation.mirror_to') {
      model.instrumentation.mirror_to = value;
      model.instrumentation.exclude = model.instrumentation.exclude.filter(
        (n) => n !== value
      );
      rerenderForm = true; // exclude の候補から mirror_to を外す
    } else if (bind === 'segment.impairment.delay') {
      const seg = model.topology.segments[Number(el.dataset.index)];
      seg.impairment = seg.impairment || {};
      seg.impairment.delay = value.trim() || null;
    } else if (bind === 'segment.impairment.jitter') {
      const seg = model.topology.segments[Number(el.dataset.index)];
      seg.impairment = seg.impairment || {};
      seg.impairment.jitter = value.trim() || null;
    } else if (bind === 'segment.impairment.loss') {
      const seg = model.topology.segments[Number(el.dataset.index)];
      seg.impairment = seg.impairment || {};
      seg.impairment.loss = value.trim() || null;
    } else if (bind === 'segment.impairment.rate') {
      const seg = model.topology.segments[Number(el.dataset.index)];
      seg.impairment = seg.impairment || {};
      seg.impairment.rate = value.trim() || null;
    } else if (bind === 'asset.physical_process.type') {
      const a = assetAt(el);
      a.physical_process = a.physical_process || { observed_by: '' };
      a.physical_process.type = value.trim() || 'tank_level';
    } else if (bind === 'asset.physical_process.observed_by') {
      const a = assetAt(el);
      a.physical_process = a.physical_process || { type: 'tank_level' };
      a.physical_process.observed_by = value.trim();
    } else if (bind === 'asset.physical_process.initial_level') {
      const a = assetAt(el);
      a.physical_process = a.physical_process || { type: 'tank_level', observed_by: '' };
      a.physical_process.initial_level = value === '' ? 0.0 : Number(value);
    } else if (bind === 'asset.physical_process.capacity') {
      const a = assetAt(el);
      a.physical_process = a.physical_process || { type: 'tank_level', observed_by: '' };
      a.physical_process.capacity = value === '' ? 100.0 : Number(value);
    } else if (bind === 'protocol.name') {
      model.structuring.protocols[Number(el.dataset.index)].name = value;
    } else if (bind === 'protocol.index') {
      model.structuring.protocols[Number(el.dataset.index)].output_index = value;
    } else {
      return;
    }

    refresh(rerenderForm);
  }

  function onClick(event) {
    const el = event.target.closest('[data-action]');
    if (!el) return;
    const action = el.dataset.action;
    const index = Number(el.dataset.index);

    switch (action) {
      case 'add-segment':
        M.addSegment(model);
        break;
      case 'remove-segment':
        M.removeSegment(model, index);
        break;
      case 'add-asset':
        M.addAsset(model);
        break;
      case 'remove-asset':
        M.removeAsset(model, index);
        break;
      case 'add-network': {
        const asset = model.topology.assets[index];
        const used = new Set(asset.networks.map((n) => n.segment));
        const free = model.topology.segments.find((s) => !used.has(s.name));
        if (free) asset.networks.push({ segment: free.name, ip: null });
        break;
      }
      case 'remove-network':
        model.topology.assets[index].networks.splice(Number(el.dataset.net), 1);
        break;
      case 'toggle-instrumentation':
        model.instrumentation = el.checked
          ? { mirror_to: '', exclude: [] }
          : null;
        // 構造化は計装層が前提。計装を外したら構造化も落とす。
        if (!el.checked) model.structuring = null;
        break;
      case 'toggle-exclude': {
        const name = el.dataset.segment;
        const list = model.instrumentation.exclude;
        const at = list.indexOf(name);
        if (at >= 0) list.splice(at, 1);
        else list.push(name);
        break;
      }
      case 'toggle-structuring':
        model.structuring = el.checked
          ? {
              engine: 'tshark',
              protocols: [],
              elasticsearch_url: 'http://elasticsearch:9200',
            }
          : null;
        if (el.checked && !model.instrumentation) {
          model.instrumentation = { mirror_to: '', exclude: [] };
        }
        break;
      case 'add-protocol':
        model.structuring.protocols.push({ name: '', output_index: '' });
        break;
      case 'remove-protocol':
        model.structuring.protocols.splice(index, 1);
        break;
      default:
        return;
    }
    refresh();
  }

  // --- テンプレート・取り込み・書き出し -------------------------------------

  function loadModel(next) {
    model = M.normalize(next);
    view = { scale: 1, tx: 0, ty: 0 };
    refresh();
  }

  function onTemplateChange(event) {
    const id = event.target.value;
    if (!id) return;
    if (id === '__new__') {
      loadModel(M.emptyModel());
    } else {
      const sample = Samples.find((s) => s.id === id);
      if (sample) loadModel(sample.model);
    }
    event.target.value = '';
  }

  function exportYaml() {
    const name = (model.metadata.name || 'range').trim() || 'range';
    // 既定のファイル名は必ず `.generated.yaml`。リファレンスの実ファイル名と
    // 衝突させず、誤って手書きのマニフェストを潰す事故を防ぐ(決定事項#120)。
    const filename = `${name}.generated.yaml`;
    const blob = new Blob([Yaml.dump(model)], {
      type: 'text/yaml;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function copyYaml() {
    const text = Yaml.dump(model);
    const done = () => {
      const btn = $('copy-btn');
      const original = btn.textContent;
      btn.textContent = 'コピーしました';
      setTimeout(() => {
        btn.textContent = original;
      }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => {});
    }
  }

  // 使い方パネル。初見の利用者が画面だけで完結できるようにするのが主目的の
  // ため、初回訪問時は自動で開く。一度閉じたら以降は開かない(localStorageが
  // 使えない環境では毎回開くが、実害は無い)。
  const HELP_SEEN_KEY = 'amenonuboco.help.seen';

  function helpSeen() {
    try {
      return window.localStorage.getItem(HELP_SEEN_KEY) === '1';
    } catch (e) {
      return false;
    }
  }

  function markHelpSeen() {
    try {
      window.localStorage.setItem(HELP_SEEN_KEY, '1');
    } catch (e) {
      /* プライベートモード等では記憶しない */
    }
  }

  function openHelp() {
    $('help-overlay').hidden = false;
    $('help-close').focus();
  }

  function closeHelp() {
    $('help-overlay').hidden = true;
    markHelpSeen();
  }

  function setupHelp() {
    $('help-btn').addEventListener('click', openHelp);
    $('help-close').addEventListener('click', closeHelp);
    // 背景クリックで閉じる(パネル内のクリックは拾わない)
    $('help-overlay').addEventListener('click', (e) => {
      if (e.target === $('help-overlay')) closeHelp();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('help-overlay').hidden) closeHelp();
    });
    if (!helpSeen()) openHelp();
  }

  function setupDropZone() {
    let depth = 0;
    window.addEventListener('dragenter', (e) => {
      e.preventDefault();
      depth += 1;
      document.body.classList.add('dropping');
    });
    window.addEventListener('dragover', (e) => e.preventDefault());
    window.addEventListener('dragleave', (e) => {
      e.preventDefault();
      depth -= 1;
      if (depth <= 0) document.body.classList.remove('dropping');
    });
    window.addEventListener('drop', (e) => {
      e.preventDefault();
      depth = 0;
      document.body.classList.remove('dropping');
      const file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          loadModel(JSON.parse(reader.result));
        } catch (err) {
          alert(
            '読み込めませんでした。`python platform/cli.py gui-export <manifest.yaml>` ' +
              'が出力した .gui.json ファイルをドロップしてください。'
          );
        }
      };
      reader.readAsText(file);
    });
  }

  function setupPanZoom() {
    const wrap = $('canvas-wrap');
    let dragging = false;
    let lastX = 0;
    let lastY = 0;

    const setScale = (next) => {
      view.scale = Math.min(4, Math.max(0.3, next));
      applyView();
    };

    wrap.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        setScale(view.scale * (e.deltaY < 0 ? 1.1 : 0.9));
      },
      { passive: false }
    );
    wrap.addEventListener('mousedown', (e) => {
      dragging = true;
      wrap.classList.add('grabbing');
      lastX = e.clientX;
      lastY = e.clientY;
    });
    window.addEventListener('mouseup', () => {
      dragging = false;
      wrap.classList.remove('grabbing');
    });
    window.addEventListener('mousemove', (e) => {
      if (!dragging) return;
      view.tx += e.clientX - lastX;
      view.ty += e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
      applyView();
    });

    $('zoom-in').addEventListener('click', () => setScale(view.scale * 1.2));
    $('zoom-out').addEventListener('click', () => setScale(view.scale * 0.8));
    $('zoom-reset').addEventListener('click', () => {
      view = { scale: 1, tx: 0, ty: 0 };
      applyView();
    });
  }

  function init() {
    const select = $('template-select');
    // 15分野を平坦に並べると、深さの違い（実演まで作り込んだ分野／器だけの
    // 分野／観測境界を持つ分野）が選択肢の上で見えなくなる。群ごとに
    // optgroup で括り、選ぶ前に何を選ぼうとしているのかが分かるようにする。
    const groups = [];
    Samples.forEach((s) => {
      const name = s.group || 'その他';
      let group = groups.find((g) => g.name === name);
      if (!group) groups.push((group = { name, items: [] }));
      group.items.push(s);
    });
    select.innerHTML =
      '<option value="">テンプレートを選択…</option>' +
      '<option value="__new__">新規（空から作る）</option>' +
      groups
        .map(
          (g) =>
            `<optgroup label="${esc(g.name)}（${g.items.length}分野）">` +
            g.items
              .map(
                (s) =>
                  `<option value="${esc(s.id)}">${esc(s.label)}（${esc(s.id)}）</option>`
              )
              .join('') +
            '</optgroup>'
        )
        .join('');
    select.addEventListener('change', onTemplateChange);

    $('form-pane').addEventListener('input', onInput);
    $('form-pane').addEventListener('change', onInput);
    document.addEventListener('click', onClick);
    $('export-btn').addEventListener('click', exportYaml);
    $('copy-btn').addEventListener('click', copyYaml);

    setupPanZoom();
    setupDropZone();
    setupHelp();

    // 初期表示は電力リファレンス。空の画面より、動く実例が出ている方が
    // 「何ができるものか」が一目で伝わる。
    loadModel(Samples[0] ? Samples[0].model : M.emptyModel());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
