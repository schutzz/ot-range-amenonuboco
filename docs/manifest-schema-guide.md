# マニフェスト記法ガイド（α版 / DRAFT）

> **このドキュメントについて**：Amenonuboco のサイバーレンジマニフェストを「どう書くか」の記法リファレンスです。**α版（`v1alpha1`）であり、Phase 1のプロビジョナ実装を通じて変わりうる**たたき台です。確定した仕様ではなく、設計の出発点として残しています。
>
> 対象読者：サイバーレンジを構築・運用する側（統裁側／防御側／環境構築者）。

---

## 0. 前提：マニフェストが宣言する範囲としない範囲

Amenonuboco のマニフェストは、サイバーレンジを6つの層で宣言します。設計の核は、層によって**宣言の深さを意図的に変えている**ことです。

| 層 | キー | 宣言の深さ |
|---|---|---|
| ① トポロジ | `topology` | **全面的に宣言**（環境はべき等に再現） |
| ② 計装 | `instrumentation` | **観測対象の列挙のみ**（生成の詳細はプロビジョナが担う） |
| ③ 構造化 | `structuring` | **何をどう構造化するかを宣言**（既定はtshark） |
| ④ 検知 | `detection` | **差し込み口だけ宣言**（ロジック本体はマニフェスト外） |
| ⑤ 攻撃 | `attack` | **実行環境だけ宣言**（攻撃の中身はマニフェスト外） |
| ⑥ 可視化 | `visualization` | **配線だけ宣言**（ダッシュボードの中身はマニフェスト外） |

**なぜ④⑤⑥は「口」だけなのか**：環境（①〜③）は有限の構成要素の組み合わせなので、宣言的に固めればべき等に再現できます。一方、検知ロジック・攻撃・ダッシュボードは無限に多様で、環境の細部にも依存します。これらをマニフェストに固定してしまうと、環境を変えるたびに作り直す「終わらない旅」に入ります。だから④⑤⑥は「載せる口」だけを用意し、中身はシナリオ側・実行時の自由に委ねます（⑥の詳細は§8）。

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

instrumentation:   # ② 観測（ミラーリング）
  mirror_to: ...
  exclude: [...]

structuring:       # ③ 構造化（tshark既定）
  engine: tshark
  protocols: [...]
  exceptions: [...]

detection:         # ④ 検知ロジックの差し込み口
  plugins: [...]

attack:            # ⑤ 攻撃の実行環境（攻撃者ノードは topology.assets 側に置く）
  engine: {...}
  agents: [...]

visualization:     # ⑥ 可視化エンジンへの配線（ダッシュボード本体はマニフェスト外）
  engine: grafana
  host: ...
  dashboards: [...]
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

> **重要：`networks` は必ず配列**。単一接続でも配列で書きます。前身 `ot-ids-verum` の `wan_router`（5接続）や攻撃者ノード（2接続）のようなマルチホームを、例外扱いせず一貫して表現するためです。

### 2.3 ルーティング（`routing`）

```yaml
topology:
  routing:
    gateway: wan_router      # L3ルータの役割を持つ資産名
```

セグメント間のルーティングは、`gateway` に指定した資産を経由して**プロビジョナが自動生成**します。各ノードに `ip route add ... via <gateway>` を手で書く必要はありません。

> **設計意図**：前身 `ot-ids-verum` では各コンテナの起動コマンドに `ip route add` が生のシェルで散在していました。これを接続情報から宣言的に導出することで、記述漏れ・不整合を防ぎます。

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

`environment`（コンテナ環境変数、`KEY=VALUE` 形式）も同じ `overrides` に置きます。`ports`/`command` と同様にロールプリセット側には概念を持たせず、指定した値がそのまま使われます。

```yaml
    - name: elasticsearch
      role: detection-infra
      image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
      networks:
        - { segment: cc_lan, ip: 10.1.10.40 }
      overrides:
        environment:
          - "discovery.type=single-node"
          - "xpack.security.enabled=false"     # 未設定だと既定でTLS必須起動になる(Phase3決定事項#48)
```

### 2.5 初期化処理をマニフェストに書かないこと

前身 `ot-ids-verum` では各ノードの起動コマンドに「`apt-get install ...` ＋ `ip route add ...` ＋ アプリ起動」が生のシェル文字列で埋め込まれていました。**Amenonuboco ではこれらをマニフェストに持ち込みません**。

| 前身で生シェルだったもの | Amenonuboco での扱い |
|---|---|
| `apt-get install ...`（パッケージ導入） | **ビルド済みイメージに焼く**（マニフェストで毎回宣言しない） |
| `ip route add ...`（ルーティング） | **接続情報から自動生成**（§2.3） |
| アプリ起動コマンド | **ロール定義に紐づける** |

生のシェル文字列はマニフェストの第一級市民にしません（どうしても必要なケースのエスケープハッチは別途検討中）。これによりマニフェストの宣言性を保ちます。

> **注意（`overrides.command` にバックグラウンド起動を書く場合）**：`overrides.command` はアプリ本体の起動内容としてユーザーが自由に書ける領域ですが、生成されるコンテナの起動コマンド全体は内部的に `install && routing && ... && <overrides.command>` という形で連結されます。ここに `python3 app.py & tail -f /dev/null` のように**裸の `&`（バックグラウンド起動）を書くと、この連結処理と衝突して意図と異なる解釈をされる**ことがあります（Phase5実装時に実際に遭遇。動くように見えても偶然の産物であり、資産構成によっては動かないこともあります）。バックグラウンド起動が必要な場合は、`"( app.py & wait )"` のようにサブシェルで囲んでください。これにより `overrides.command` 全体が単一の安全なブロッキングコマンドになります。

> **注意（`overrides.command` 内で二重引用符 `"` を使う場合）**：生成されるコンテナのコマンド全体は最終的に `sh -c "<すべてを連結した文字列>"` という**二重引用符でまるごと囲む**形になります（`generators/compose.py` の `_assemble_command()`）。`overrides.command` 内に `echo "hello"` のような二重引用符を（特に2箇所以上）書くと、この外側の二重引用符と衝突し、生成コマンドがシェル単語分割で意図しない位置で寸断されることがあります（Phase7実装時に実際に遭遇、罠ログ#025）。`overrides.command` 内のリテラル文字列は**単一引用符 `'...'` を使ってください**（単一引用符は変数展開されないため、変数を埋め込みたい場合は引用符自体を外すか `case` 文の glob パターンで代替してください）。この制約に反すると生成時のテストでは検出できても、実機の `docker compose up` 時点まで気づけない場合があります。

---

## 3. ② 計装層（`instrumentation`）

ミラー先の観測用セグメントを指定するだけです。**観測対象は既定で「`mirror_to` 自身を除く全セグメント」**であり、除外したいセグメントがある場合だけ `exclude` に書きます（オプトアウト方式）。

```yaml
instrumentation:
  mirror_to: mirror_link      # ミラー先の観測用セグメント
  exclude: []                 # 観測対象から除外するセグメント名（既定は空＝全セグメント観測）
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `mirror_to` | ✅ | ミラーしたトラフィックを集約する観測用セグメント |
| `exclude` | ✕ | 観測対象から除外するセグメント名の配列（既定 `[]`）。`mirror_to` 自身は指定不要（常に自動で除外される） |

> **なぜ列挙ではなく除外なのか**：観測対象をマニフェストに列挙させる方式（オプトイン）だと、`topology.segments` にセグメントを追加したときに計装層への追記を忘れる余地が残ります。前身 `ot-ids-verum` では実際にこれが起き、新セグメントのトラフィックが2日間まったく観測されないまま気づかれませんでした。`topology.segments` の全セグメントを既定で観測対象にすることで、**「追記を忘れる」という選択肢自体を無くしています**。

**プロビジョナが担うこと（マニフェストに書かないこと）**：
- IPアドレスからのインターフェース名の逆引き（コンテナ再作成での名前シャッフル対策）
- ミラーリング構文（`tc qdisc`/`tc filter`）の生成
- **冪等化**（再実行で重複が蓄積しないこと）
- 双方向カバレッジの保証（片方向欠落を作らないこと）

> **設計意図**：前身 `ot-ids-verum` が `setup_mirror.sh` の手書きで繰り返し踏んだミラーリングの非対称性・冪等化漏れ・インターフェース名シャッフルを、生成ロジック側で構造的に排除します。観測の死角が生じたかどうかは、ネットワーク図にそのまま反映されます。

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
| `protocols[].output_index` | ✅ | 出力先の Elasticsearch index の**検索パターン**（Kibana/Grafana の index pattern 相当）。命名は `ot-logs-<protocol>-*` に統一。実際の書き込み先は、末尾の `*` をUTC日付（`%Y.%m.%d`）に置き換えた具体的な日次index（例: `ot-logs-http-2026.08.16`）で、プロビジョナ側が自動導出する（Phase3決定事項#49） |
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
| `dmz` | 非武装地帯 | — |
| `security-lan` | 物理セキュリティ網（監視カメラ・入退室管理等） | Phase7決定事項#104 |

### 5.2 資産ロール（`role`）

| ロール | 意味 | 前身 `ot-ids-verum` での該当例 |
|---|---|---|
| `ot-asset` | 被害者となりうるOT資産（PLC/RTU/HMI/IED/SCADAマスター） | cc_scada_master, sub_b_rtu_hmi, sub_b_plc_01, sub_a_ied_01 |
| `l3-router` | セグメント間ルータ（`ip_forward` 有効） | wan_router |
| `detection-infra` | 検知基盤（取り込み・保存・検知 sidecar） | vector, elasticsearch, 各 sidecar |
| `observer` | 観測ノード（生パケットをそのまま確認する用途、tcpdump 等） | zeek_tap, suricata_ids |
| `structurer` | 構造化パイプライン実行ノード（tshark ＋ バルクローダー、§4） | （前身では Vector＋Zeek が担っていた役割） |
| `attack-engine` | 攻撃エミュレーションエンジン（Caldera server、§7） | （前身では常設せず Ability/Adversary 資産のみ保有） |
| `visualization-engine` | 可視化エンジン（Grafana server 等、§8） | grafana |
| `eval-harness` | 正解ラベル源（評価専用、§6参照） | oob_redis, oob_webdis |
| `attacker-external` | 境界外の攻撃者 | external_attacker |
| `attacker-internal` | 内部に置いた踏み台攻撃者 | red-team |
| `attacker-insider` | 侵害された正規資産 | sub_a_ied_02 |
| `security-asset` | 物理セキュリティ資産（NVR/IPカメラ/入退室管理パネル） | （Phase7新設、決定事項#104） |
| `remote-access-gateway` | 正規のリモート保守経路（RDP/VNC等の終端点、侵害の起点になりうる） | （Phase7新設、決定事項#105、Oldsmar型） |

各ロールには実行属性のプリセット（capability・sysctl・接続すべき既定セグメント等）が紐づく想定です。プリセットの完全な定義は Phase 1 で確定します。

---

## 6. ④ 検知層（`detection`）

検知ロジックの**本体はマニフェストに書きません**。ここで宣言するのは「どのロジックを、どの資産に、どう載せるか」という差し込み口だけです。

```yaml
detection:
  plugins:
    - name: signal-6-killchain
      type: sidecar                 # 現在は sidecar のみ
      host: killchain_detector      # topology.assets の資産を名前で指す
      source: ../scenarios/legacy-power-grid-signals/killchain_eql_poller.py
      requires: [ requests ]        # プラグインが必要とする Python パッケージ
      config:                       # プラグインへ環境変数として注入される
        ES_URL: http://elasticsearch:9200
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `plugins[].name` | ✅ | 検知プラグインの識別名（マニフェスト内で一意） |
| `plugins[].type` | ✅ | 載せ方。現在は `sidecar` のみ（後述） |
| `plugins[].host` | ✅ | プラグインを実行する資産の名前（**`topology.assets` に実在すること**）。1つのホストに複数プラグインを載せられます |
| `plugins[].source` | ✅ | ロジック本体のパス（**マニフェスト外の資産**を指す。相対パスはマニフェスト自身の位置が基点） |
| `plugins[].requires` | ✕ | プラグインが必要とする Python パッケージ。プロビジョナが導入コマンドへ合成します（生の `pip install` は書きません） |
| `plugins[].config` | ✕ | プラグインへ**環境変数として注入**される設定。接続先などをプラグイン内にハードコードさせないための仕組みです |

> **なぜ `host` で資産を指すのか**：コンテナ（資産）を宣言する場所は `topology.assets` の1箇所に統一しています。検知プラグインはコンテナを新たに作らず、既にトポロジに居る資産に「載る」だけです。「そこにどう繋がって存在するか」はトポロジ層が、「そこで何を実行するか」は検知層が担う、という責務の分け方です。

> **`type` が `sidecar` のみである理由**：sidecar 型は取り込みエンジンから完全に独立しています（Elasticsearch を読み書きするだけで、そのデータを誰が構造化したかを知りません）。この独立性こそが差し込み口の望ましい性質です。特定の処理系（例：Vector の VRL）に依存する型は、プラットフォーム本体がその処理系を背負うことになるため設けていません。

> **前身の Signal 群の流用**：`ot-ids-verum` が作り込んだ Signal 群のうち、Elasticsearch をポーリングする sidecar 型（Signal 6 など）は、`host` と `source` を指すだけでそのまま1シナリオとして差し込めます（`config` で接続先を渡せば、スクリプト側の改修は最小限で済みます）。一方、特定処理系で書かれたロジック（VRL の transform など）は、同等の判定を sidecar として書き直す必要があります。プラットフォーム本体は検知ロジックを一切持ちません。

### 評価ハーネス（正解ラベル源）について

前身 `ot-ids-verum` の `oob_redis`/`oob_webdis`（攻撃の正解ラベルをOut-of-Bandで供給する評価専用の仕組み）は、**そのままは持ち込みません**。旧実装は `io.popen` によるシェル呼び出しに依存しており、ポータビリティとセキュリティの両面で作り直しが必要なためです。

評価ハーネスに `detection` 配下の専用フィールドはありません。**`eval-harness` ロールの資産を `topology.assets` へ通常どおり宣言し、そこへ正解ラベルの記録・突き合わせを行うスクリプトを載せる**、という検知プラグインと同じ「載せる口」の形で表現します（コンテナを宣言する場所を1箇所に統一する方針。§7の攻撃者ノードと同じ考え方です）。

> **正解ラベルは、攻撃者ノード自身に記録させないこと**：正解ラベル（「いつ・どこから・何を撃ったか」）を、攻撃者役の資産自身にElasticsearch等へ書き込ませる設計は避けてください。侵害された可能性のある側が自分の行動を自己申告する構図になり、前身が明示的に排除した「OOB自己申告」と同じ問題を抱えます。正解ラベルの記録は、`eval-harness` ロールの専用資産——演習を実行する側（オペレータ）に属する、攻撃者とも検知対象とも独立したホスト——から行ってください。

---

## 7. ⑤ 攻撃層（`attack`）

攻撃の**中身（ペイロード・台本・Ability定義）はマニフェストに書きません**。宣言するのは「攻撃者がそこに立ち、OT網に手を伸ばせる実行環境」までです。

**攻撃者ノード自体は、他の資産と同じく `topology.assets` に宣言します**（攻撃者ロールを持つ、環境の一部だからです）。攻撃層が宣言するのは、資産そのものではなく「資産に何を載せるか」——攻撃エンジン（Caldera）の配線と、既存資産への agent 仕込み——だけです。

```yaml
# 攻撃者ノードは topology.assets 側に置く
topology:
  assets:
    - name: external_attacker
      role: attacker-external
      image: ./external_attacker
      networks:
        - { segment: wan_link, ip: 172.18.0.99 }
        - { segment: cc_lan,   ip: 10.1.10.98 }
    - name: caldera_server
      role: attack-engine
      image: ghcr.io/mitre/caldera:latest
      networks:
        - { segment: cc_lan, ip: 10.1.10.70 }
      overrides:
        ports: [ "8888:8888" ]

# 攻撃層は「何を載せるか」だけを宣言する
attack:
  engine:
    caldera:
      host: caldera_server          # topology.assets の attack-engine 資産を参照
      abilities_path: ../attack-assets/caldera/abilities
      adversaries_path: ../attack-assets/caldera/adversaries
  agents:
    - host: external_attacker       # 既存の攻撃者資産に agent を仕込む
      type: sandcat
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `engine.caldera.host` | ✕ | Caldera server を動かす資産の名前（`topology.assets` の `attack-engine` ロール資産を指す） |
| `engine.caldera.abilities_path` / `adversaries_path` | ✕ | Caldera が読む Ability/Adversary の**外部パス**（マニフェスト外資産を読み取り専用でマウントするだけ） |
| `agents[].host` | ✅※ | agent を仕込む資産の名前（`topology.assets` を指す）。※`agents` を書く場合は `engine.caldera` が必須 |
| `agents[].type` | ✕ | agent の種類（既定 `sandcat`） |

> **攻撃をパッケージ化しない**：攻撃者ノードは汎用の実行環境として用意します。「何を、いつ、どう撃つか」は、Caldera の UI/API や手元のスクリプトから実行時に自由に組み立てます。攻撃の追加・変更は Caldera 側（マニフェスト外）で完結し、環境定義には一切波及しません。
>
> **Caldera は既定エンジンであって強制ではありません**。`attack` 層も `engine.caldera` も任意です。宣言しなければ攻撃関連の生成は一切行われず、攻撃者ロールの資産を `topology.assets` に置いて素のスクリプトを撃つ運用が、追加の宣言なしで成立します。

---

## 8. ⑥ 可視化層（`visualization`）

ダッシュボードの**中身（パネル定義・クエリ）はマニフェストに書きません**。ここで宣言するのは「どの可視化エンジンを、どの資産に立て、どのダッシュボードJSONを載せるか」という配線だけです。ネットワーク図（構造の可視化、プラットフォーム組み込み）とは別レイヤーで、こちらは時系列データ（検知アラート・トラフィック統計）の可視化を担います。

```yaml
topology:
  assets:
    - name: grafana_server
      role: visualization-engine
      image: grafana/grafana:11.1.0
      networks:
        - { segment: cc_lan, ip: 10.0.10.72 }

visualization:
  engine: grafana                 # 現在は grafana のみ実装
  host: grafana_server            # topology.assets の visualization-engine 資産を指す
  dashboards:
    - ../scenarios/legacy-power-grid-signals/dashboards/signal1_zone.json
  # datasources は省略可能（下記参照）
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `engine` | ✕ | 可視化エンジンの種類（既定・現状唯一の実装は `grafana`） |
| `host` | ✅ | 可視化エンジンを実行する資産の名前（**`topology.assets` に実在し、`visualization-engine` ロールを持つこと**） |
| `dashboards` | ✕ | ダッシュボード定義（JSON）の**外部パス**の列挙（マニフェスト外資産を読み取り専用でマウントするだけ、`detection.plugins[].source` と同じ扱い） |
| `datasources` | ✕ | データソースの明示指定。省略時は `structuring.protocols[].output_index` と検知アラートの命名規約 `ot-signals-<signal>-*` から自動生成される（下記） |
| `elasticsearch_url` | ✕ | 投入先 Elasticsearch の URL（既定 `http://elasticsearch:9200`） |

> **なぜ `host` で資産を指すのか**：§6・§7 と同じ理由です。コンテナを宣言する場所は `topology.assets` の1箇所に統一し、可視化層は「そこに何を配線するか」だけを担います。

> **データソースは自動生成されるのが既定**：`structuring` で宣言した構造化ログの index（`ot-logs-<protocol>-*`）と、検知アラートの命名規約（`ot-signals-<signal>-*`）を束ねた1つの Elasticsearch データソースが自動生成されます。マニフェストに構造化プロトコルを1つ足すだけで、可視化側にも自動で反映されます（単一の宣言から複数の出力が生まれる、ネットワーク図と同じ思想）。細かく制御したい場合のみ `datasources` を明示してください。

> **検知プラグインは、アラートの index 名を `ot-signals-<signal>-*` に揃えること**：構造化ログの命名規約 `ot-logs-<protocol>-*` と対になる規約です。自動生成されるデータソースはこの規約に依存するため、検知プラグイン側でこの規約から外れた index 名を使うと、可視化層から見えなくなります。

> **可視化エンジンも任意です**：`visualization` 層も、宣言しなければ可視化関連の生成は一切行われません。ダッシュボードを使わない運用や、手元で別途 Grafana を立てる運用も、追加の宣言なしで成立します。

> **将来の拡張**：`engine` は現状 `grafana` のみですが、生成側は抽象化されています（`VisualizationEngine`）。将来、API 型のエンジン（Kibana 等）を追加する際も、この抽象に実装を足すだけで済み、マニフェストの語彙自体は変わりません。

---

## 9. 完全な例（前身環境のスライスを1枚で）

6層すべて、マルチホーム、IP動的割当、tshark例外、Caldera、可視化を1枚に含む最小例です。実ファイルは [`manifests/power-grid-reference.yaml`](../manifests/power-grid-reference.yaml)（Phase 6時点で全層を含む）にあります。

> 命名注記：`metadata.name` はドメイン（電力網ラボ）を表す名前とし、前身プロジェクト名を識別子として名乗りません。Amenonuboco のリポジトリ内で前身の名前がファイル名・識別子に出ると、閲覧者がどちらのプロジェクトの資産か混同しうるためです。

```yaml
apiVersion: amenonuboco/v1alpha1
kind: CyberRange
metadata:
  name: power-grid-reference
  description: 前身プロジェクト ot-ids-verum の電力網ラボの代表要素を1枚に凝縮したリファレンススライス

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
    # 検知プラグインのホスト・攻撃者・攻撃エンジンも、すべて資産として置く
    - name: killchain_detector
      role: detection-infra
      image: python:3.11-slim
      networks:
        - { segment: cc_lan, ip: 10.0.10.80 }
    # 攻撃者ノード sub_a_ied_02 は上で ot 資産群と一緒に宣言済み
    - name: caldera_server
      role: attack-engine
      image: ghcr.io/mitre/caldera:latest
      networks:
        - { segment: cc_lan, ip: 10.0.10.70 }
      overrides:
        ports: [ "8888:8888" ]
    - name: grafana_server
      role: visualization-engine
      image: grafana/grafana:11.1.0
      networks:
        - { segment: cc_lan, ip: 10.0.10.72 }

instrumentation:
  mirror_to: mirror_link
  exclude: []   # 既定で mirror_link 以外の全セグメントが観測対象になる

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
    - name: signal-6-killchain
      type: sidecar
      host: killchain_detector
      source: ../scenarios/legacy-power-grid-signals/killchain_eql_poller.py
      requires: [ requests ]
      config: { ES_URL: http://elasticsearch:9200 }

attack:
  # 攻撃者ノード(sub_a_ied_02)・Caldera server(caldera_server)は
  # 上の topology.assets 側に宣言済み。ここでは載せるものだけを書く。
  engine:
    caldera:
      host: caldera_server
      abilities_path: ../attack-assets/caldera/abilities
      adversaries_path: ../attack-assets/caldera/adversaries
  agents:
    - { host: sub_a_ied_02, type: sandcat }

visualization:
  # 可視化エンジン(grafana_server)は上の topology.assets 側に宣言済み。
  # ここでは載せるダッシュボードだけを書く。datasourcesは省略(自動生成)。
  engine: grafana
  host: grafana_server
  dashboards:
    - ../scenarios/legacy-power-grid-signals/dashboards/signal1_zone.json
```

このマニフェスト1枚から、プロビジョナが「動く環境」を、レンダラが「防御側・統裁側向けHTMLネットワーク図」を、可視化エンジンが「時系列ダッシュボード」を生成します。図・ダッシュボードのいずれもこのマニフェストから機械生成・配線されるため、定義を変えれば両方が追随し、実態との乖離が生じません。

---

## 10. まだ決まっていないこと（Phase 1以降で確定）

α版時点で未確定・要検証の項目です。

- **記述言語の最終確定**：YAML想定だが、記法の細部（例：`networks` のインライン記法の許容範囲）は Phase 1 の実装で詰める。
- **ロールプリセットの具体的な中身**：各ロールが持つ capability・sysctl・既定接続セグメント・実行属性の完全な定義。
- **初期化処理のエスケープハッチ**：どうしても宣言的に表せない起動処理を、限定的に許容する仕組みが要るか。
- **構造化の tshark 移行の互換性**：前身 `ot-ids-verum` で Zeek/ICSNPP 固有ログに依存していた検知（特に SBO バイパス検知が使う `dnp3_control.log` のオブジェクトレベル情報）を、tshark が同等に供給できるか。供給できない場合は Spicy/Zeek 例外ルートで補う。
- **検知プラグインの `type` の語彙**：現在は `sidecar` のみ。Elasticsearch 側の機構（ingest pipeline / enrich policy 等）を第2の型として追加するかは、必要になった時点で判断する。
- **ネットワーク図のビュー分岐**：防御側・統裁側向けの全開示版に加え、攻撃側・受講者向けの情報を絞ったビュー（fog of war）を出すか。α版は全開示版のみ対象。

---

## 付録：設計判断の根拠について

本ガイドの各「設計意図」は、前身プロジェクト `ot-ids-verum`（Phase 0〜11）で得た具体的な失敗と教訓に基づいています。詳細な設計判断の記録は、プロジェクトの内部計画書で管理しています。このガイドはそれを「記法」として結晶化したものです。
