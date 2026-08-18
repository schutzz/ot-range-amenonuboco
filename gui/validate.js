// マニフェストの構造検証。
//
// platform/schema/ のPydantic検証をJSへ移植したもの(Phase8決定事項#117)。
// GUIはクライアントサイド完結でPython側を呼べないため、同じ規則をここに持つ。
// 移植による乖離は tests/test_gui_parity.py が「同じ不正入力をPython側と
// JS側の双方が拒否すること」を表明して封じ込める(決定事項#118・#122)。
//
// 移植元の対応:
//   Topology._validate_cross_references  (schema/topology.py)
//   Segment._validate_cidr / AssetNetwork._validate_ip
//   validate_instrumentation             (schema/instrumentation.py)
//   Structuring._validate_no_duplicates_or_conflicts (schema/structuring.py)
//   Manifest._validate_cross_layer_references の structuring→instrumentation 依存
//
// 加えて、Pydanticでは通るが `cli.py provision` で初めて落ちる
// MirroringGenerationError(ゲートウェイが観測対象セグメントに静的IPを
// 持たない)を、警告として先出しする。エラーの出る場所と原因の場所が離れて
// いて初見では解きにくい、GUIで防ぐ価値の高い落とし穴のため。
//
// IPアドレスの扱いはIPv4のみ。Python側(ipaddress)はIPv6も受けるため、
// この点だけJS側が厳しい。プロジェクトの全マニフェストがIPv4であり、
// 「GUIが通したものをPythonが弾く」という危険な向きの乖離は生まないため、
// 意図的にこの範囲へ絞っている。

(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.AmenonubocoValidate = api;
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  // --- IPv4ユーティリティ ---------------------------------------------------

  function parseIpv4(text) {
    if (typeof text !== 'string') return null;
    const parts = text.trim().split('.');
    if (parts.length !== 4) return null;
    let value = 0;
    for (const part of parts) {
      // 前ゼロ("010")はPythonのipaddressも拒否する
      if (!/^\d{1,3}$/.test(part)) return null;
      if (part.length > 1 && part[0] === '0') return null;
      const n = Number(part);
      if (n > 255) return null;
      value = value * 256 + n;
    }
    return value >>> 0;
  }

  /** CIDRを解析する。host bitsが立っていれば null(Pythonの strict=True 相当)。 */
  function parseCidr(text) {
    if (typeof text !== 'string') return null;
    const m = text.trim().match(/^(.+)\/(\d{1,2})$/);
    if (!m) return null;
    const base = parseIpv4(m[1]);
    if (base === null) return null;
    const prefix = Number(m[2]);
    if (prefix > 32) return null;
    const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
    // host bits が立っている場合、Python の ip_network(strict=True) は例外を投げる
    if ((base & ~mask & 0xffffffff) >>> 0 !== 0) return null;
    return { network: base >>> 0, mask };
  }

  function ipInCidr(ip, cidr) {
    return ((ip & cidr.mask) >>> 0) === cidr.network;
  }

  // --- 検証本体 -------------------------------------------------------------

  function validate(model) {
    const errors = [];
    const warnings = [];
    const err = (message, path) => errors.push({ message, path: path || null });
    const warn = (message, path) => warnings.push({ message, path: path || null });

    const topology = (model && model.topology) || {};
    const segments = topology.segments || [];
    const assets = topology.assets || [];

    // --- メタデータ ---
    if (!model || !model.metadata || !String(model.metadata.name || '').trim()) {
      err('metadata.name が未設定です', 'metadata.name');
    }

    // --- セグメント ---
    const segNames = segments.map((s) => s.name);
    const segByName = {};
    const dupSegs = new Set();
    segNames.forEach((name, i) => {
      if (segNames.indexOf(name) !== i) dupSegs.add(name);
    });
    for (const name of [...dupSegs].sort()) {
      err(`セグメント名が重複しています: '${name}'`, `segments.${name}`);
    }

    segments.forEach((seg, i) => {
      const label = seg.name || `#${i + 1}`;
      if (!String(seg.name || '').trim()) {
        err(`セグメント #${i + 1}: 名前が未設定です`, `segments.${i}`);
      }
      const cidr = parseCidr(seg.cidr);
      if (cidr === null) {
        err(
          `セグメント '${label}': CIDR '${seg.cidr || ''}' が不正です` +
            `（ホスト部が0でない場合も不正になります。例: 10.1.10.0/24）`,
          `segments.${i}`
        );
      } else {
        segByName[seg.name] = cidr;
      }
    });

    const segmentNameSet = new Set(segNames);

    // --- 資産 ---
    const assetNames = assets.map((a) => a.name);
    const dupAssets = new Set();
    assetNames.forEach((name, i) => {
      if (assetNames.indexOf(name) !== i) dupAssets.add(name);
    });
    for (const name of [...dupAssets].sort()) {
      err(`資産名が重複しています: '${name}'`, `assets.${name}`);
    }

    // セグメントごとのIP使用状況(重複検出用)
    const ipsPerSegment = {};

    assets.forEach((asset, i) => {
      const label = asset.name || `#${i + 1}`;
      if (!String(asset.name || '').trim()) {
        err(`資産 #${i + 1}: 名前が未設定です`, `assets.${i}`);
      }
      if (!String(asset.image || '').trim()) {
        err(`資産 '${label}': image が未設定です`, `assets.${i}`);
      }

      const networks = asset.networks || [];
      if (!networks.length) {
        err(`資産 '${label}': 接続先セグメントが1つも指定されていません`, `assets.${i}`);
      }

      const connected = new Set();
      for (const net of networks) {
        if (!segmentNameSet.has(net.segment)) {
          err(
            `資産 '${label}': 未定義のセグメント '${net.segment}' を参照しています`,
            `assets.${i}`
          );
          continue;
        }
        if (connected.has(net.segment)) {
          err(
            `資産 '${label}': セグメント '${net.segment}' へ二重に接続しています`,
            `assets.${i}`
          );
          continue;
        }
        connected.add(net.segment);

        if (net.ip === null || net.ip === undefined || net.ip === '') continue;

        const ip = parseIpv4(net.ip);
        if (ip === null) {
          err(`資産 '${label}': IP '${net.ip}' が不正です`, `assets.${i}`);
          continue;
        }
        const cidr = segByName[net.segment];
        if (cidr && !ipInCidr(ip, cidr)) {
          const seg = segments.find((s) => s.name === net.segment);
          err(
            `資産 '${label}': IP '${net.ip}' がセグメント '${net.segment}' の ` +
              `CIDR '${seg ? seg.cidr : ''}' の範囲外です`,
            `assets.${i}`
          );
          continue;
        }
        const seen = (ipsPerSegment[net.segment] = ipsPerSegment[net.segment] || {});
        if (seen[net.ip]) {
          err(
            `セグメント '${net.segment}' でIP '${net.ip}' が重複しています` +
              `（'${seen[net.ip]}' と '${label}'）`,
            `assets.${i}`
          );
        } else {
          seen[net.ip] = label;
        }
      }
    });

    // --- ルーティング ---
    const routing = topology.routing;
    const gatewayName = routing && routing.gateway;
    let gatewayAsset = null;
    if (gatewayName) {
      gatewayAsset = assets.find((a) => a.name === gatewayName) || null;
      if (!gatewayAsset) {
        err(
          `routing.gateway '${gatewayName}' に対応する資産が存在しません`,
          'routing.gateway'
        );
      } else if (gatewayAsset.role !== 'l3-router') {
        err(
          `routing.gateway '${gatewayName}' のロールは 'l3-router' である必要があります` +
            `（現在: '${gatewayAsset.role}'）`,
          'routing.gateway'
        );
      }
    }

    // --- 計装層 ---
    const inst = model && model.instrumentation;
    if (inst) {
      if (!segmentNameSet.has(inst.mirror_to)) {
        err(
          `instrumentation.mirror_to '${inst.mirror_to || ''}' に対応するセグメントが存在しません`,
          'instrumentation.mirror_to'
        );
      }
      const unknown = (inst.exclude || []).filter((n) => !segmentNameSet.has(n));
      if (unknown.length) {
        err(
          `instrumentation.exclude が未定義のセグメントを参照しています: ${unknown.sort().join(', ')}`,
          'instrumentation.exclude'
        );
      }
    }

    // --- 構造化層 ---
    const structuring = model && model.structuring;
    if (structuring) {
      const protoNames = (structuring.protocols || []).map((p) => p.name);
      const dupProtos = new Set();
      protoNames.forEach((name, i) => {
        if (protoNames.indexOf(name) !== i) dupProtos.add(name);
      });
      for (const name of [...dupProtos].sort()) {
        err(`structuring.protocols でプロトコル名が重複しています: '${name}'`, 'structuring');
      }
      (structuring.protocols || []).forEach((p, i) => {
        if (!String(p.name || '').trim()) {
          err(`structuring.protocols #${i + 1}: プロトコル名が未設定です`, 'structuring');
        }
        if (!String(p.output_index || '').trim()) {
          err(
            `structuring.protocols '${p.name || `#${i + 1}`}': output_index が未設定です`,
            'structuring'
          );
        }
      });
      // 構造化はミラーされたトラフィックを対象にするため、計装層が前提になる
      if (protoNames.length && !inst) {
        err(
          'structuring（protocols）を宣言するには instrumentation 層が必須です' +
            '（構造化はミラーされたトラフィックを対象にするため）',
          'structuring'
        );
      }
    }

    // --- 警告: ゲートウェイの静的IP不足 ---
    // Pydanticは通すが、cli.py provision の実行時に MirroringGenerationError で
    // 落ちる。エラーの出る場所と原因の場所が離れているため、ここで先出しする。
    if (inst && gatewayAsset && segmentNameSet.has(inst.mirror_to)) {
      const skip = new Set([inst.mirror_to, ...(inst.exclude || [])]);
      const needStaticIp = [
        inst.mirror_to,
        ...segNames.filter((n) => !skip.has(n)),
      ];
      const ipOn = {};
      for (const net of gatewayAsset.networks || []) {
        ipOn[net.segment] = net.ip;
      }
      const missing = needStaticIp.filter((n) => !ipOn[n]);
      if (missing.length) {
        warn(
          `ゲートウェイ '${gatewayAsset.name}' は観測対象セグメントとミラー集約先の` +
            `すべてに静的IPが必要です。未設定: ${missing.join(', ')}` +
            `（このままでは環境生成時にミラーリング設定の生成が失敗します）`,
          'routing.gateway'
        );
      }
    }

    // --- 警告: 計装層はあるがゲートウェイが無い ---
    if (inst && !gatewayName) {
      warn(
        'instrumentation 層を使うには routing.gateway（role: l3-router の資産）が必要です',
        'routing.gateway'
      );
    }

    // --- 警告: overrides.command 中の二重引用符 ---
    // 生成される docker-compose.yml では、資産の起動コマンドが最終的に
    // `sh -c "..."` の形で包まれる。その中に二重引用符があると包みが破れ、
    // コンテナ内で構文エラーになる。YAMLとしてもスキーマとしても妥当なため
    // 宣言時には弾けず、`docker compose up` して初めて壊れる類の落とし穴。
    // 単一引用符へ置き換えれば回避できる。
    assets.forEach((asset, i) => {
      const command = asset.overrides && asset.overrides.command;
      if (command && String(command).includes('"')) {
        warn(
          `資産 '${asset.name || `#${i + 1}`}': overrides.command に二重引用符（"）が` +
            `含まれています。起動コマンドは最終的に sh -c "..." で包まれるため、` +
            `二重引用符があるとコンテナ内で構文エラーになります。単一引用符（'）へ` +
            `置き換えてください`,
          `assets.${i}`
        );
      }
    });

    return { errors, warnings, ok: errors.length === 0 };
  }

  return { validate, parseIpv4, parseCidr, ipInCidr };
});
