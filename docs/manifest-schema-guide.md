# マニフェスト記法ガイド（α版 / DRAFT）

> **このドキュメントについて**：Amenonuboco のサイバーレンジマニフェストを「どう書くか」の記法リファレンスです。**α版（`v1alpha1`）であり、Phase 1のプロビジョナ実装を通じて変わりうる**たたき台です。確定した仕様ではなく、設計の出発点として残しています。
>
> 対象読者：サイバーレンジを構築・運用する側（統裁側／防御側／環境構築者）。

---

## 0. 前提：マニフェストが宣言する範囲としない範囲

Amenonuboco のマニフェストは、サイバーレンジを5つの層で宣言します。設計の核は、層によって**宣言の深さを意図的に変えている**ことです。

| 層 | キー | 宣言の深さ |
|---|---|---|
| ① トポロジ | `topology` | **全面的に宣言**（環境はべき等に再現） |
| ② 計装 | `instrumentation` | **観測対象の列挙のみ**（生成の詳細はプロビジョナが担う） |
| ③ 構造化 | `structuring` | **何をどう構造化するかを宣言**（既定はtshark） |
| ④ 検知 | `detection` | **差し込み口だけ宣言**（ロジック本体はマニフェスト外） |
| ⑤ 攻撃 | `attack` | **実行環境だけ宣言**（攻撃の中身はマニフェスト外） |

**なぜ④⑤は「口」だけなのか**：環境（①〜③）は有限の構成要素の組み合わせなので、宣言的に固めればべき等に再現できます。一方、検知ロジックと攻撃は無限に多様で、環境の細部にも依存します。これらをマニフェストに固定してしまうと、環境を変えるたびに検知と攻撃を作り直す「終わらない旅」に入ります。だから④⑤は「載せる口」だけを用意し、中身はシナリオ側・実行時の自由に委ねます。

---

## 1. マニフェストの全体構造

```yaml
apiVersion: amenonuboco/v1alpha1
kind: CyberRange
metadata:
  name: my-power-grid-range
  description: DNP3/Modbus/GOOSE を含む電力網ミニチュア

topology:          # ① セグメント・資産・ルーティング
  segments: [...]
  routing: {...}
  assets: [...]

instrumentation:   # ② 観測対象の列挙
  mirror_to: ...
  observe: [...]

structuring:       # ③ 構造化（tshark既定）
  engine: tshark
  protocols: [...]
  exceptions: [...]

detection:         # ④ 検知ロジックの差し込み口
  plugins: [...]
  evaluation_harness: {...}

attack:            # ⑤ 攻撃の実行環境
  nodes: [...]
  engine: {...}
```

---

## 2. ① トポロジ層（`topology`）

環境の骨格。セグメント・資産・ルーティングを全面的に宣言します。

### 2.1 セグメント（`segments`）

```yaml
topology:
  segments:
    - name: cc_lan
      cidr: 10.0.10.0/24
      kind: it-core
    - name: sub_b_lan
      cidr: 10.0.30.0/24
      kind: ot-lan
    - name: mirror_link
      cidr: 10.0.99.0/24
      kind: observation
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `name` | ✅ | セグメント名（資産の接続先として参照される） |
| `cidr` | ✅ | サブネット |
| `kind` | ✅ | セグメント種別（§5.1の語彙）。ネットワーク図の色分けと観測カバレッジ判定に使う |

### 2.2 資産（`assets`）

```yaml
topology:
  assets:
    # 単一セグメント・固定IP
    - name: cc_scada_master
      role: ot-asset
      image: ./cc_scada_master        # ローカルDockerfile。既存イメージは image: python:3.10-slim のように書く
      networks:
        - { segment: cc_lan, ip: 10.0.10.10 }

    # マルチホーム（複数セグメントに接続するL3ルータ）
    - name: wan_router
      role: l3-router
      image: debian:bullseye-slim
      networks:
        - { segment: cc_lan,       ip: 10.0.10.254 }
        - { segment: wan_link,     ip: 172.16.0.254 }
        - { segment: sub_b_lan,    ip: 10.0.30.254 }
        - { segment: mirror_link,  ip: 10.0.99.254 }

    # IP動的割当（ip を省略するとプロビジョナが割り当てる）
    - name: es_enrich_refresher
      role: detection-infra
      image: curlimages/curl:latest
      networks:
        - { segment: cc_lan }
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `name` | ✅ | 資産名 |
| `role` | ✅ | 資産ロール（§5.2の語彙）。実行属性のプリセットと図の表現を決める |
| `image` | ✅ | 既存イメージ名、または `./dir` 形式のローカルビルド元 |
| `networks` | ✅ | **接続するセグメントの配列**（マルチホーム対応）。各要素は `segment`（必須）と `ip`（任意、省略時は動的割当） |
| `overrides` | ✕ | ロールのプリセットを上書きする例外設定（§2.4） |

> **重要：`networks` は必ず配列**。単一接続でも配列で書きます。verum の `wan_router`（5接続）や攻撃者ノード（2接続）のようなマルチホームを、例外扱いせず一貫して表現するためです。

### 2.3 ルーティング（`routing`）

```yaml
topology:
  routing:
    gateway: wan_router      # L3ルータの役割を持つ資産名
```

セグメント間のルーティングは、`gateway` に指定した資産を経由して**プロビジョナが自動生成**します。各ノードに `ip route add ... via <gateway>` を手で書く必要はありません。

> **設計意図**：verum では各コンテナの起動コマンドに `ip route add` が生のシェルで散在していました。これを接続情報から宣言的に導出することで、記述漏れ・不整合を防ぎます。

### 2.4 実行属性のプリセットと上書き（`overrides`）

公開ポート・Linux capability・sysctl などの実行属性は、**ロールごとのプリセット**が既定で適用されます（プリセットの具体的な中身は §5.2、確定は Phase 1）。マニフェストでは例外だけを `overrides` に書きます。

```yaml
    - name: sub_b_rtu_hmi
      role: ot-asset
      image: nodered/node-red:3.1.0
      networks:
        - { segment: sub_b_lan, ip: 10.0.30.10 }
      overrides:
        ports: [ "1880:1880" ]     # Node-RED ダッシュボードを公開
```

> **設計意図**：`cap_add: [NET_ADMIN, NET_RAW]` のような属性を全資産に書くと冗長で誤りの温床になります。「観測ノードは NET_ADMIN を持つ」といった規則性はロールに畳み込み、マニフェストは差分だけを表現します。

### 2.5 初期化処理をマニフェストに書かないこと

verum では各ノードの起動コマンドに「`apt-get install ...` ＋ `ip route add ...` ＋ アプリ起動」が生のシェル文字列で埋め込まれていました。**Amenonuboco ではこれらをマニフェストに持ち込みません**。

| verum で生シェルだったもの | Amenonuboco での扱い |
|---|---|
| `apt-get install ...`（パッケージ導入） | **ビルド済みイメージに焼く**（マニフェストで毎回宣言しない） |
| `ip route add ...`（ルーティング） | **接続情報から自動生成**（§2.3） |
| アプリ起動コマンド | **ロール定義に紐づける** |

生のシェル文字列はマニフェストの第一級市民にしません（どうしても必要なケースのエスケープハッチは別途検討中）。これによりマニフェストの宣言性を保ちます。

---

## 3. ② 計装層（`instrumentation`）

「どのセグメントを観測するか」を列挙するだけです。

```yaml
instrumentation:
  mirror_to: mirror_link      # ミラー先の観測用セグメント
  observe:
    - cc_lan
    - wan_link
    - sub_a_l2_lan
    - sub_b_lan
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `mirror_to` | ✅ | ミラーしたトラフィックを集約する観測用セグメント |
| `observe` | ✅ | 観測対象セグメントの配列 |

**プロビジョナが担うこと（マニフェストに書かないこと）**：
- IPアドレスからのインターフェース名の逆引き（コンテナ再作成での名前シャッフル対策）
- ミラーリング構文（`tc qdisc`/`tc filter`）の生成
- **冪等化**（再実行で重複が蓄積しないこと）
- 双方向カバレッジの保証（片方向欠落を作らないこと）

> **設計意図**：verum が `setup_mirror.sh` の手書きで繰り返し踏んだミラーリングの非対称性・冪等化漏れ・インターフェース名シャッフルを、生成ロジック側で構造的に排除します。観測の死角が生じたかどうかは、ネットワーク図にそのまま反映されます。

---

## 4. ③ 構造化層（`structuring`）

観測したトラフィックを、どのプロトコルで、どう構造化するかを宣言します。既定エンジンは **tshark** です。

```yaml
structuring:
  engine: tshark
  protocols:
    - name: dnp3
      output_index: ot-logs-dnp3-*
    - name: modbus
      output_index: ot-logs-modbus-*
  exceptions:
    - protocol: goose
      engine: spicy-sidecar
      reason: 非標準ペイロード（宣言長/実長不一致）への対応と、StNum のステートフル検知のため
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `engine` | ✅ | 既定の構造化エンジン。通常 `tshark` |
| `protocols[].name` | ✅ | 構造化するプロトコル |
| `protocols[].output_index` | ✅ | 出力先の Elasticsearch index。命名は `ot-logs-<protocol>-*` に統一 |
| `exceptions[]` | ✕ | tshark では扱えない/不都合なプロトコルを、別エンジン（Spicy/Zeek 独立 sidecar）で処理する例外指定 |

> **tshark を既定にする理由**：Wireshark の広範な dissector ライブラリを、新プロトコル対応のスケールの源泉にするためです。プロトコルごとに自作パーサーを書くのは実装・デバッグコストが高く、「マニフェストで宣言したら新プロトコルに対応」という目標に向きません。
>
> **例外（Spicy/Zeek sidecar）を使う場面**：①パーサー自体にステートフルな異常検知を組み込みたい、②高負荷でtsharkのオーバーヘッドが許容できない、③非標準ペイロードにWiresharkのdissectorが対応しない。GOOSE はこの典型例です。

---

## 5. 語彙リファレンス（α版）

### 5.1 セグメント種別（`kind`）

| 種別 | 意味 | 図での扱い（想定） |
|---|---|---|
| `it-core` | IT中枢・制御センター | — |
| `wan-edge` | WAN境界・外部接続 | 境界を強調 |
| `ot-l2` | OT L2セグメント（GOOSE 等のレイヤ2通信） | — |
| `ot-lan` | OT LAN（DNP3/Modbus 等） | — |
| `observation` | 観測用ミラーネットワーク | 観測系として区別 |
| `dmz` | 非武装地帯（将来） | — |

### 5.2 資産ロール（`role`）

| ロール | 意味 | verum の該当例 |
|---|---|---|
| `ot-asset` | 被害者となりうるOT資産（PLC/RTU/HMI/IED/SCADAマスター） | cc_scada_master, sub_b_rtu_hmi, sub_b_plc_01, sub_a_ied_01 |
| `l3-router` | セグメント間ルータ（`ip_forward` 有効） | wan_router |
| `detection-infra` | 検知基盤（取り込み・保存・可視化・検知 sidecar） | vector, elasticsearch, grafana, 各 sidecar |
| `observer` | 観測ノード（tshark/Zeek/Suricata） | zeek_tap, suricata_ids |
| `eval-harness` | 正解ラベル源（評価専用、§6参照） | oob_redis, oob_webdis |
| `attacker-external` | 境界外の攻撃者 | external_attacker |
| `attacker-internal` | 内部に置いた踏み台攻撃者 | red-team |
| `attacker-insider` | 侵害された正規資産 | sub_a_ied_02 |

各ロールには実行属性のプリセット（capability・sysctl・接続すべき既定セグメント等）が紐づく想定です。プリセットの完全な定義は Phase 1 で確定します。

---

## 6. ④ 検知層（`detection`）

検知ロジックの**本体はマニフェストに書きません**。ここで宣言するのは「どのロジックを、どのコンポーネントに、どう載せるか」という差し込み口だけです。

```yaml
detection:
  plugins:
    - name: signal-1-zone-violation
      type: vector-transform
      source: ../scenarios/verum-signals/enrich_trace.vrl
    - name: signal-6-killchain
      type: sidecar
      source: ../scenarios/verum-signals/killchain_eql_poller.py
  evaluation_harness:
    enabled: false
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `plugins[].name` | ✅ | 検知プラグインの識別名 |
| `plugins[].type` | ✅ | 載せ方（`vector-transform` / `sidecar` / …） |
| `plugins[].source` | ✅ | ロジック本体のパス（**マニフェスト外の資産**を指す） |
| `evaluation_harness.enabled` | ✕ | 正解ラベル源を載せるか（既定 `false`） |

> **verum の Signal 群の流用**：verum が作り込んだ Signal 1〜8 は、`source` で指すだけの外部資産として、そのまま1シナリオとして差し込めます。プラットフォーム本体は検知ロジックを持ちません。

### 評価ハーネス（正解ラベル源）について

verum の `oob_redis`/`oob_webdis`（攻撃の正解ラベルをOut-of-Bandで供給する評価専用の仕組み）は、**そのままは持ち込みません**。旧実装は `io.popen` によるシェル呼び出しに依存しており、ポータビリティとセキュリティの両面で作り直しが必要なためです。マニフェストでは「評価ハーネスを載せる口」として抽象化し、実体は sidecar がファイル/enrichment_table へ書き出す方式に再設計します。既定は無効です。

---

## 7. ⑤ 攻撃層（`attack`）

攻撃の**中身（ペイロード・台本・Ability定義）はマニフェストに書きません**。宣言するのは「攻撃者がそこに立ち、OT網に手を伸ばせる実行環境」までです。

```yaml
attack:
  nodes:
    - name: external_attacker
      role: attacker-external
      image: ./external_attacker
      networks:
        - { segment: wan_link, ip: 172.16.0.99 }
        - { segment: cc_lan,   ip: 10.0.10.98 }
      toolchain: [ python3, scapy ]
    - name: red_team
      role: attacker-internal
      image: ./red-team
      networks:
        - { segment: cc_lan, ip: 10.0.10.99 }
      toolchain: [ python3, scapy ]
  engine:
    caldera:
      enabled: true
      server_segment: cc_lan
      abilities_path: ../attack-assets/caldera/abilities
      adversaries_path: ../attack-assets/caldera/adversaries
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `nodes[]` | ✅ | 攻撃者ノード。`networks` はトポロジ層と同じ配列記法（マルチホーム対応） |
| `nodes[].toolchain` | ✕ | ノードに用意する攻撃ツールチェーン（実行環境） |
| `engine.caldera.enabled` | ✕ | Caldera を載せるか |
| `engine.caldera.server_segment` | ✕ | Caldera server を置くセグメント |
| `engine.caldera.abilities_path` / `adversaries_path` | ✕ | Caldera が読む Ability/Adversary の**外部パス**（マニフェスト外資産をロードするだけ） |

> **攻撃をパッケージ化しない**：攻撃者ノードは汎用の実行環境（Python/scapy、必要なら Caldera agent 入り）として用意します。「何を、いつ、どう撃つか」は、Caldera の UI/API や手元のスクリプトから実行時に自由に組み立てます。攻撃の追加・変更は Caldera 側（マニフェスト外）で完結し、環境定義には一切波及しません。
>
> **Caldera は既定エンジンであって強制ではありません**。素のスクリプトを撃ちたい場合も、攻撃者ノードの実行環境でそのまま実行できます。

---

## 8. 完全な例（verum のスライスを1枚で）

5層すべて、マルチホーム、IP動的割当、tshark例外、Caldera を1枚に含む最小例です。

```yaml
apiVersion: amenonuboco/v1alpha1
kind: CyberRange
metadata:
  name: verum-slice
  description: verum の代表要素を1枚に凝縮したリファレンススライス

topology:
  segments:
    - { name: cc_lan,      cidr: 10.0.10.0/24, kind: it-core }
    - { name: wan_link,    cidr: 172.16.0.0/24, kind: wan-edge }
    - { name: sub_b_lan,   cidr: 10.0.30.0/24, kind: ot-lan }
    - { name: sub_a_l2_lan, cidr: 10.0.20.0/24, kind: ot-l2 }
    - { name: mirror_link, cidr: 10.0.99.0/24, kind: observation }
  routing:
    gateway: wan_router
  assets:
    - name: wan_router
      role: l3-router
      image: debian:bullseye-slim
      networks:
        - { segment: cc_lan,       ip: 10.0.10.254 }
        - { segment: wan_link,     ip: 172.16.0.254 }
        - { segment: sub_b_lan,    ip: 10.0.30.254 }
        - { segment: sub_a_l2_lan, ip: 10.0.20.254 }
        - { segment: mirror_link,  ip: 10.0.99.254 }
    - name: cc_scada_master
      role: ot-asset
      image: ./cc_scada_master
      networks:
        - { segment: cc_lan, ip: 10.0.10.10 }
    - name: sub_b_rtu_hmi
      role: ot-asset
      image: nodered/node-red:3.1.0
      networks:
        - { segment: sub_b_lan, ip: 10.0.30.10 }
      overrides:
        ports: [ "1880:1880" ]
    - name: sub_a_ied_02
      role: attacker-insider
      image: python:3.10-slim
      networks:
        - { segment: sub_a_l2_lan, ip: 10.0.20.11 }
    - name: vector
      role: detection-infra
      image: timberio/vector:0.46.0-alpine
      networks:
        - { segment: cc_lan, ip: 10.0.10.35 }
    - name: elasticsearch
      role: detection-infra
      image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
      networks:
        - { segment: cc_lan, ip: 10.0.10.40 }
    - name: es_enrich_refresher
      role: detection-infra
      image: curlimages/curl:latest
      networks:
        - { segment: cc_lan }        # IP動的割当

instrumentation:
  mirror_to: mirror_link
  observe: [ cc_lan, wan_link, sub_b_lan, sub_a_l2_lan ]

structuring:
  engine: tshark
  protocols:
    - { name: dnp3,   output_index: ot-logs-dnp3-* }
    - { name: modbus, output_index: ot-logs-modbus-* }
  exceptions:
    - protocol: goose
      engine: spicy-sidecar
      reason: 非標準ペイロード対応と StNum のステートフル検知

detection:
  plugins:
    - { name: signal-1-zone-violation, type: vector-transform, source: ../scenarios/verum-signals/enrich_trace.vrl }
    - { name: signal-6-killchain,      type: sidecar,          source: ../scenarios/verum-signals/killchain_eql_poller.py }
  evaluation_harness:
    enabled: false

attack:
  nodes:
    - name: external_attacker
      role: attacker-external
      image: ./external_attacker
      networks:
        - { segment: wan_link, ip: 172.16.0.99 }
        - { segment: cc_lan,   ip: 10.0.10.98 }
      toolchain: [ python3, scapy ]
    - name: red_team
      role: attacker-internal
      image: ./red-team
      networks:
        - { segment: cc_lan, ip: 10.0.10.99 }
      toolchain: [ python3, scapy ]
  engine:
    caldera:
      enabled: true
      server_segment: cc_lan
      abilities_path: ../attack-assets/caldera/abilities
      adversaries_path: ../attack-assets/caldera/adversaries
```

このマニフェスト1枚から、プロビジョナが「動く環境」を、レンダラが「防御側・統裁側向けHTMLネットワーク図」を生成します。図はこのマニフェストから機械生成されるため、定義を変えれば図も変わり、実態との乖離が生じません。

---

## 9. まだ決まっていないこと（Phase 1以降で確定）

α版時点で未確定・要検証の項目です。

- **記述言語の最終確定**：YAML想定だが、記法の細部（例：`networks` のインライン記法の許容範囲）は Phase 1 の実装で詰める。
- **ロールプリセットの具体的な中身**：各ロールが持つ capability・sysctl・既定接続セグメント・実行属性の完全な定義。
- **初期化処理のエスケープハッチ**：どうしても宣言的に表せない起動処理を、限定的に許容する仕組みが要るか。
- **構造化の tshark 移行の互換性**：verum で Zeek/ICSNPP 固有ログに依存していた検知（特に SBO バイパス検知が使う `dnp3_control.log` のオブジェクトレベル情報）を、tshark が同等に供給できるか。供給できない場合は Spicy/Zeek 例外ルートで補う。
- **検知プラグインの `type` の語彙**：`vector-transform`/`sidecar` 以外に必要な載せ方があるか。
- **ネットワーク図のビュー分岐**：防御側・統裁側向けの全開示版に加え、攻撃側・受講者向けの情報を絞ったビュー（fog of war）を出すか。α版は全開示版のみ対象。

---

## 付録：設計判断の根拠について

本ガイドの各「設計意図」は、前身プロジェクト `ot-ids-verum`（Phase 0〜11）で得た具体的な失敗と教訓に基づいています。詳細な設計判断の記録は、プロジェクトの内部計画書で管理しています。このガイドはそれを「記法」として結晶化したものです。
