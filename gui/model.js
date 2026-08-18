// 編集モデルの生成と更新。
//
// GUIが編集するのは topology + instrumentation + structuring の3層に限る
// (Phase8決定事項#119)。detection/attack/visualization は外部シナリオ資産への
// 参照が主であり、GUIで組み立てさせると「シナリオ資産はコードで書く／
// プラットフォームは中身を一切解釈しない」という境界が濁るため含めない。
// topology 以外は全て任意宣言のため、この3層だけで動作する有効な
// マニフェストが成立する。

(function (global) {
  'use strict';

  const V = global.AMENONUBOCO_VOCAB;

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  /** 新規作成時の出発点。最小限だが、そのまま有効なマニフェストになる形。 */
  function emptyModel() {
    return {
      apiVersion: 'amenonuboco/v1alpha1',
      kind: 'CyberRange',
      metadata: { name: 'my-range', description: '' },
      topology: { segments: [], assets: [], routing: null },
      instrumentation: null,
      structuring: null,
    };
  }

  /** 読み込んだモデルの欠けている枝を埋め、GUIが前提とする形に正規化する。 */
  function normalize(raw) {
    const model = Object.assign(emptyModel(), deepClone(raw || {}));
    model.metadata = Object.assign({ name: '', description: '' }, model.metadata || {});
    model.topology = Object.assign(
      { segments: [], assets: [], routing: null },
      model.topology || {}
    );
    model.topology.segments = model.topology.segments || [];
    model.topology.assets = (model.topology.assets || []).map((a) => ({
      name: a.name || '',
      role: a.role || 'ot-asset',
      image: a.image || '',
      networks: (a.networks || []).map((n) => ({
        segment: n.segment || '',
        ip: n.ip === undefined ? null : n.ip,
      })),
      overrides: Object.assign(
        { ports: [], command: null, cap_add: null, sysctls: null, environment: [] },
        a.overrides || {}
      ),
    }));
    if (model.instrumentation) {
      model.instrumentation = {
        mirror_to: model.instrumentation.mirror_to || '',
        exclude: model.instrumentation.exclude || [],
      };
    }
    if (model.structuring) {
      model.structuring = {
        engine: model.structuring.engine || 'tshark',
        protocols: model.structuring.protocols || [],
        elasticsearch_url:
          model.structuring.elasticsearch_url || 'http://elasticsearch:9200',
      };
    }
    return model;
  }

  /** 未使用のセグメント名を作る(seg_1, seg_2, ...)。 */
  function nextSegmentName(model) {
    const used = new Set(model.topology.segments.map((s) => s.name));
    for (let i = 1; ; i += 1) {
      const name = `segment_${i}`;
      if (!used.has(name)) return name;
    }
  }

  /** 既存セグメントと重ならない 10.90.N.0/24 を割り当てる。 */
  function nextCidr(model) {
    const used = new Set(model.topology.segments.map((s) => s.cidr));
    for (let i = 10; i < 250; i += 10) {
      const cidr = `10.90.${i}.0/24`;
      if (!used.has(cidr)) return cidr;
    }
    return '10.90.250.0/24';
  }

  function nextAssetName(model) {
    const used = new Set(model.topology.assets.map((a) => a.name));
    for (let i = 1; ; i += 1) {
      const name = `asset_${i}`;
      if (!used.has(name)) return name;
    }
  }

  function addSegment(model) {
    model.topology.segments.push({
      name: nextSegmentName(model),
      cidr: nextCidr(model),
      kind: 'ot-lan',
    });
  }

  function removeSegment(model, index) {
    const removed = model.topology.segments[index];
    model.topology.segments.splice(index, 1);
    if (!removed) return;
    // 参照していた資産の接続を落とす(未定義セグメント参照エラーを残さない)
    for (const asset of model.topology.assets) {
      asset.networks = asset.networks.filter((n) => n.segment !== removed.name);
    }
    if (model.instrumentation) {
      if (model.instrumentation.mirror_to === removed.name) {
        model.instrumentation.mirror_to = '';
      }
      model.instrumentation.exclude = model.instrumentation.exclude.filter(
        (n) => n !== removed.name
      );
    }
  }

  function renameSegment(model, index, newName) {
    const old = model.topology.segments[index].name;
    model.topology.segments[index].name = newName;
    if (old === newName) return;
    for (const asset of model.topology.assets) {
      for (const net of asset.networks) {
        if (net.segment === old) net.segment = newName;
      }
    }
    if (model.instrumentation) {
      if (model.instrumentation.mirror_to === old) {
        model.instrumentation.mirror_to = newName;
      }
      model.instrumentation.exclude = model.instrumentation.exclude.map((n) =>
        n === old ? newName : n
      );
    }
  }

  function addAsset(model) {
    const firstSegment = model.topology.segments[0];
    const role = 'ot-asset';
    model.topology.assets.push({
      name: nextAssetName(model),
      role,
      image: 'python:3.10-slim',
      networks: firstSegment ? [{ segment: firstSegment.name, ip: null }] : [],
      overrides: {
        ports: [],
        command: null,
        cap_add: null,
        sysctls: null,
        environment: [],
      },
    });
  }

  function removeAsset(model, index) {
    const removed = model.topology.assets[index];
    model.topology.assets.splice(index, 1);
    if (
      removed &&
      model.topology.routing &&
      model.topology.routing.gateway === removed.name
    ) {
      model.topology.routing = null;
    }
  }

  function renameAsset(model, index, newName) {
    const old = model.topology.assets[index].name;
    model.topology.assets[index].name = newName;
    if (
      model.topology.routing &&
      model.topology.routing.gateway === old &&
      old !== newName
    ) {
      model.topology.routing.gateway = newName;
    }
  }

  /** ロールのプリセット(cap_add/sysctls)を参照用に返す。 */
  function presetFor(role) {
    return V.roles[role] || { cap_add: [], sysctls: [], default_command: null };
  }

  global.AmenonubocoModel = {
    emptyModel,
    normalize,
    deepClone,
    addSegment,
    removeSegment,
    renameSegment,
    addAsset,
    removeAsset,
    renameAsset,
    presetFor,
  };
})(typeof window !== 'undefined' ? window : globalThis);
