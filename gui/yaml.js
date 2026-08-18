// 編集モデル → マニフェストYAML の出力。
//
// 汎用のYAMLエミッタではなく、天沼矛のマニフェスト形状(マップ・配列・文字列・
// 文字列配列のみ)に特化した実装(Phase8決定事項#121)。外部ライブラリを持ち
// 込まず「CDN不使用・自己完結」の方針を保つための割り切り。
//
// 出力の並び順はリファレンスマニフェストに合わせて固定する
// (apiVersion → kind → metadata → topology → instrumentation → structuring)。
// 空・null の項目は出力しない——宣言が無ければ対応する生成を一切行わない、
// という設計のため、`routing: null` のような空宣言を書くと意味が変わりうる。
//
// 注意: このエミッタはコメントを一切出力しない。GUIは新しいファイルへの
// エクスポートに限定し、既存の manifests/*.yaml を上書きしない(決定事項#120)。
// あれらのコメントは設計判断・実機検証の経緯を持つ資産であり、往復で
// 消し飛ばしてはならない。

(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.AmenonubocoYaml = api;
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  // YAMLの真偽値・null・数値と解釈されうる綴り。これらは引用しないと
  // 型が変わってしまう。
  const LOOKS_SCALAR = /^(true|false|yes|no|on|off|null|~|-?\d+(\.\d+)?([eE][-+]?\d+)?)$/i;

  // 先頭に置くと必ず指示子として解釈される文字。
  const LEADING_INDICATOR = /^[,[\]{}#&*!|>'"%@`]/;

  /**
   * ブロック文脈でプレーン(引用符なし)に書けるか。
   *
   * 判定を過度に厳しくすると `ot-lan` や `debian:bullseye-slim` のような
   * 何の変哲もない値まで引用されて、手書きのマニフェストと見た目が離れる。
   * YAMLの実際の規則に沿って、「指示子は先頭にあるときだけ特別」「`:` は
   * 直後に空白が続くときだけ特別」「`#` は直前に空白があるときだけ特別」
   * を区別する。
   */
  function isPlainSafe(s) {
    if (typeof s !== 'string') return false;
    if (s === '') return false;
    if (s.includes('\n')) return false;
    if (/^\s|\s$/.test(s)) return false;
    if (LEADING_INDICATOR.test(s)) return false;
    // `-` `?` `:` は、直後が空白または終端のときだけ指示子になる
    if (/^[-?:](\s|$)/.test(s)) return false;
    if (/:\s/.test(s) || /:$/.test(s)) return false;
    if (/(^|\s)#/.test(s)) return false;
    if (LOOKS_SCALAR.test(s)) return false;
    return true;
  }

  /**
   * フロー文脈(`{ ... }` の中)でプレーンに書けるか。
   * ブロック文脈の条件に加え、フロー区切り文字を含まないこと。
   */
  function isFlowSafe(s) {
    return isPlainSafe(s) && !/[,[\]{}]/.test(s);
  }

  /** 単一引用符スタイル。内部の ' は '' へ重ねる(バックスラッシュ解釈が無い)。 */
  function quote(s) {
    return `'${String(s).replace(/'/g, "''")}'`;
  }

  function scalar(value) {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'number') return String(value);
    const s = String(value);
    return isPlainSafe(s) ? s : quote(s);
  }

  /**
   * 複数行文字列をブロックスカラーで出す。command の埋め込み用。
   *
   * チョンピング指示子は末尾改行の数から決める(`|-`=無し / `|`=1つ /
   * `|+`=2つ以上)。ここを固定にすると、読み込んだマニフェストを書き出した
   * だけで command の末尾改行が増減し、往復が非可逆になる。
   */
  function blockScalar(key, text, indent) {
    const pad = ' '.repeat(indent);
    const inner = ' '.repeat(indent + 2);
    const s = String(text);
    const trailing = (s.match(/\n*$/) || [''])[0].length;

    let chomp;
    let body;
    if (trailing === 0) {
      chomp = '-';
      body = s;
    } else if (trailing === 1) {
      chomp = '';
      body = s.slice(0, -1);
    } else {
      chomp = '+';
      body = s.slice(0, -1);
    }

    // 先頭行がスペース始まりだとブロックのインデント幅が自動判定できないため、
    // 明示的な指示子(2)を添える。
    const needsIndentHint = /^[ ]/.test(body);
    const header = `${pad}${key}: |${needsIndentHint ? '2' : ''}${chomp}\n`;

    // 空行にはパディングを付けない(意味の無い行末スペースを残さない)
    const lines = body
      .split('\n')
      .map((line) => (line === '' ? '' : inner + line))
      .join('\n');

    return `${header}${lines}\n`;
  }

  function emitScalarField(key, value, indent) {
    if (value === null || value === undefined || value === '') return '';
    if (typeof value === 'string' && value.includes('\n')) {
      return blockScalar(key, value, indent);
    }
    return `${' '.repeat(indent)}${key}: ${scalar(value)}\n`;
  }

  function emitStringList(key, values, indent) {
    if (!values || !values.length) return '';
    const pad = ' '.repeat(indent);
    // 短い文字列配列はフロースタイルで1行に収める(リファレンスと同じ見た目)
    if (values.every((v) => isFlowSafe(String(v)))) {
      return `${pad}${key}: [ ${values.join(', ')} ]\n`;
    }
    return (
      `${pad}${key}:\n` +
      values.map((v) => `${pad}  - ${scalar(v)}\n`).join('')
    );
  }

  /**
   * 固定キーの短いレコードを、可能ならフロースタイル1行で出す。
   * リファレンスマニフェストの `- { name: cc_lan, cidr: ..., kind: it-core }`
   * と同じ見た目になり、「手で書いたものと同じ形が出てくる」ことが伝わる。
   */
  function emitRecordItem(fields, indent) {
    const pad = ' '.repeat(indent);
    const present = fields.filter(
      ([, v]) => v !== null && v !== undefined && v !== ''
    );
    const allPlain = present.every(([, v]) => isFlowSafe(String(v)));
    if (allPlain) {
      const body = present.map(([k, v]) => `${k}: ${v}`).join(', ');
      return `${pad}- { ${body} }\n`;
    }
    let out = '';
    present.forEach(([k, v], i) => {
      const prefix = i === 0 ? `${pad}- ` : `${pad}  `;
      out += `${prefix}${k}: ${scalar(v)}\n`;
    });
    return out;
  }

  function emitAsset(asset, indent) {
    const pad = ' '.repeat(indent);
    let out = `${pad}- name: ${scalar(asset.name)}\n`;
    const inner = indent + 2;
    out += emitScalarField('role', asset.role, inner);
    out += emitScalarField('image', asset.image, inner);

    out += `${' '.repeat(inner)}networks:\n`;
    for (const net of asset.networks || []) {
      out += emitRecordItem(
        [
          ['segment', net.segment],
          ['ip', net.ip],
        ],
        inner + 2
      );
    }

    const ov = asset.overrides || {};
    const hasOverrides =
      (ov.ports && ov.ports.length) ||
      (ov.command !== null && ov.command !== undefined && ov.command !== '') ||
      (ov.cap_add !== null && ov.cap_add !== undefined) ||
      (ov.sysctls !== null && ov.sysctls !== undefined) ||
      (ov.environment && ov.environment.length);

    if (hasOverrides) {
      out += `${' '.repeat(inner)}overrides:\n`;
      const oi = inner + 2;
      out += emitStringList('ports', ov.ports, oi);
      out += emitScalarField('command', ov.command, oi);
      // cap_add / sysctls は「空配列を明示指定する」ことに意味がある
      // (ロールプリセットを空で上書きする)ため、null でなければ出力する。
      if (ov.cap_add !== null && ov.cap_add !== undefined) {
        out += ov.cap_add.length
          ? emitStringList('cap_add', ov.cap_add, oi)
          : `${' '.repeat(oi)}cap_add: []\n`;
      }
      if (ov.sysctls !== null && ov.sysctls !== undefined) {
        out += ov.sysctls.length
          ? emitStringList('sysctls', ov.sysctls, oi)
          : `${' '.repeat(oi)}sysctls: []\n`;
      }
      out += emitStringList('environment', ov.environment, oi);
    }

    return out;
  }

  function dump(model) {
    const topology = (model && model.topology) || {};
    let out = '';

    out += `apiVersion: ${scalar(model.apiVersion || 'amenonuboco/v1alpha1')}\n`;
    out += `kind: ${scalar(model.kind || 'CyberRange')}\n`;

    out += 'metadata:\n';
    out += emitScalarField('name', (model.metadata || {}).name, 2);
    out += emitScalarField('description', (model.metadata || {}).description, 2);

    out += '\ntopology:\n';
    out += '  segments:\n';
    for (const seg of topology.segments || []) {
      out += emitRecordItem(
        [
          ['name', seg.name],
          ['cidr', seg.cidr],
          ['kind', seg.kind],
        ],
        4
      );
    }

    if (topology.routing && topology.routing.gateway) {
      out += '  routing:\n';
      out += emitScalarField('gateway', topology.routing.gateway, 4);
    }

    out += '  assets:\n';
    for (const asset of topology.assets || []) {
      out += emitAsset(asset, 4);
    }

    const inst = model.instrumentation;
    if (inst && inst.mirror_to) {
      out += '\ninstrumentation:\n';
      out += emitScalarField('mirror_to', inst.mirror_to, 2);
      // exclude はオプトアウト方式の要。空でも明示しておくと
      // 「除外なし＝全セグメントが観測対象」という意図が読み取れる。
      out += (inst.exclude && inst.exclude.length)
        ? emitStringList('exclude', inst.exclude, 2)
        : '  exclude: []\n';
    }

    const st = model.structuring;
    if (st && st.protocols && st.protocols.length) {
      out += '\nstructuring:\n';
      out += emitScalarField('engine', st.engine || 'tshark', 2);
      if (st.elasticsearch_url && st.elasticsearch_url !== 'http://elasticsearch:9200') {
        out += emitScalarField('elasticsearch_url', st.elasticsearch_url, 2);
      }
      out += '  protocols:\n';
      for (const p of st.protocols) {
        out += emitRecordItem(
          [
            ['name', p.name],
            ['output_index', p.output_index],
          ],
          4
        );
      }
    }

    return out;
  }

  return { dump, scalar, isPlainSafe, isFlowSafe };
});
