# Amenonuboco — Cyber Range as Code

![status](https://img.shields.io/badge/status-Phase%207%20(3%20Sectors%20Verified)-brightgreen)

> **天沼矛（あめのぬぼこ）** — マニフェスト1枚から、OT/ICS向けサイバーレンジ（攻撃対象 + 計装 + 検知パイプライン）を動的にプロビジョニングするためのプラットフォーム。

## これは何か

Infrastructure as Code がインフラ構成をコードで宣言してべき等に再現するように、**Amenonuboco は「サイバーレンジそのもの」を宣言的なマニフェストで定義し、そこから動的に環境を立ち上げる**ことを目指すプロジェクトです。このアプローチを **Cyber Range as Code (CRaC)** と呼びます。

日本神話で、天沼矛は混沌とした海原をかき混ぜて最初の島を生み出しました。「未定義の状態を、一本の矛（マニフェスト）でかき混ぜると、そこから具体的な検証環境が立ち上がる」——この由来が、プロジェクトの本質を表しています。

## 背景

本プロジェクトは、前身プロジェクト [`ot-ids-verum`](https://github.com/schutzz/ot-ids-verum)（OOB自己申告に頼らず観測事実だけでOT攻撃を検知する固定ラボ、Phase 0〜11完了）の到達点を土台にしています。

`ot-ids-verum` では「攻撃 → 解析 → 検知ロジック追加 → 効果実証」という検証サイクルを型として確立しましたが、その型を新しいプロトコル・トポロジ・シナリオに適用するたびに、環境構築の手作業（compose定義・ミラーリング設定・各種sidecar・取り込み設定の編集）が律速になっていました。

**Amenonuboco は、この環境構築そのものをマニフェストから自動生成する**ことで、検証サイクルのスケールを狙います。`ot-ids-verum` は、本プラットフォームが生成しうる環境の「リファレンス実装・検証済みテンプレート供給源」として位置づけられます。

## 設計方針

- **構造化層は tshark を既定** とする。Wireshark の広範な dissector ライブラリを、新プロトコル対応のスケールの源泉にする（プロトコルごとに自作パーサーを書くコストを避ける）。
- **プラットフォームは「構造化まで」の共通基盤に徹する**。「何を異常とするか」という検知ロジックは各シナリオ側の責務とし、プラットフォームは載せる口だけを用意する。
- **Spicy/Zeek は例外ケースのプラグイン**。パーサー自体にステートフルな検知を組み込みたい場合、高負荷時、非標準ペイロード対応が必要な場合に限って使う。
- **出力先の命名規則は前身を踏襲**（`ot-logs-<protocol>-*`）。

## 3分野の実証（T字戦略の横棒）

「重要インフラ15種を広く浅く展開する」より「分野を絞って中身を濃く・複雑にする」方が Amenonuboco の有用性を強く示せると判断し、**電力・上下水道・重要製造業の3分野**を、それぞれ実際の脅威（社会的インパクトの大きい実インシデントをモデル化）に基づく攻撃シナリオまで実機で通しました。3分野とも同じ「型」——①weak/default な経路を用意する → ②攻撃者資産から実プロトコルで模擬アクセスする → ③イベント駆動で送信元/セッションを検知しログ出力する → ④tshark 構造化パイプラインで実データを裏付ける——で構築しています。

| 分野 | モデルにした実インシデント | 主軸実演 | 実プロトコル | CIAの観点 |
|---|---|---|---|---|
| 電力 | 2022年 CISA/FBI/DOE 共同注意喚起（インターネット露出UPSの悪用） | UPS管理インターフェースへの不正SNMPアクセス | SNMP（net-snmp） | 可用性 |
| 上下水道 | 2021年 Oldsmar浄水場事件 | 正規リモートアクセス経路を悪用したプロセス値改竄 | VNC（x11vnc + vncdotool） | 完全性 |
| 重要製造業 | 物理セキュリティ網とOTフロアの融合リスク | 監視カメラ網からOTフロアへの横展開 | EtherNet/IP | 機密性・境界防御 |

いずれも「それっぽい」トラフィックではなく、実際のOSS実装（net-snmp / x11vnc / socat）を使った本物のプロトコル交換です。tshark の構造化パイプラインが、SNMPのcommunity文字列や書き込み値、VNCのキーストローク内容（`vnc.key_down`）、EtherNet/IPのコマンド種別まで実データとして抽出できることを、Elasticsearchへの実書き込みで確認しています。

<table>
<tr>
<td width="33%">

**電力**（`power-grid-reference.yaml`）

![電力ネットワーク図](./docs/images/network-diagram-power.png)

</td>
<td width="33%">

**上下水道**（`water-utility-reference.yaml`）

![上下水道ネットワーク図](./docs/images/network-diagram-water.png)

</td>
<td width="33%">

**重要製造業**（`manufacturing-plant-reference.yaml`）

![重要製造業ネットワーク図](./docs/images/network-diagram-manufacturing.png)

</td>
</tr>
</table>

3枚とも同じマニフェスト形式・同じレンダラーから生成された自己完結HTML図です（上のPNGはそのスクリーンショット）。分野ごとに資産構成・観測カバレッジ・構造化対象プロトコルは異なりますが、図の文法（セグメント配置・色分け・観測カバレッジのバッジ）は完全に共通しています。

実際の攻撃→検知→構造化を実データ（観測されたログ・Elasticsearchの中身）で一気通貫に示すウォークスルーは [`docs/showcase/`](./docs/showcase/) にまとめています。電力（UPS可用性攻撃）・上下水道（Oldsmar型プロセス値改竄）・重要製造業（監視カメラ経由の横展開）の3分野すべてを収録済みです。

## リポジトリ構成（暫定）

```
ot-range-amenonuboco/
├── manifests/       サイバーレンジ定義マニフェスト（宣言的な入力）
├── platform/        マニフェストから環境を生成するプロビジョナ本体
├── scenarios/       検知ロジック・攻撃・評価のシナリオ資産（マニフェスト外）
├── attack-assets/   Caldera の Ability/Adversary（マニフェスト外）
├── tests/           スキーマ・生成物・シナリオ資産のユニットテスト
└── docs/            公開ドキュメント
```

## 現在のテスト品

3枚のリファレンスマニフェスト（[`manifests/power-grid-reference.yaml`](./manifests/power-grid-reference.yaml)＝前身 `ot-ids-verum` の電力網ラボを再現・濃縮したもの、[`manifests/water-utility-reference.yaml`](./manifests/water-utility-reference.yaml)、[`manifests/manufacturing-plant-reference.yaml`](./manifests/manufacturing-plant-reference.yaml)）のいずれからも、下記3つを生成・配線できます（可視化層は現時点で電力のみ配線済み）。

1. `docker-compose.yml` — 実際に `docker compose up` でコンテナ群（電力は7セグメント・20資産）が起動し、マルチホーム資産（ゲートウェイ）を経由したクロスセグメントルーティングが機能することを実機確認済みです。マニフェストに `instrumentation` 層（観測対象セグメントの宣言、既定で全セグメントが対象になるオプトアウト方式）を加えるだけで、ゲートウェイ資産が `tc` ベースのミラーリングを自動設定し、複数セグメントを跨ぐ通信が観測ノードへ実際に届くことも実機確認済みです（送出側・受信側双方のカーネルカウンタで検証）。さらに `structuring` 層を加えると、専用ロール（`structurer`）の資産が tshark ベースの構造化パイプラインを自動起動し、ミラーされたトラフィックを Elasticsearch へバルク投入します。実際にセグメントを跨ぐ HTTP/DNP3 トラフィックを捕捉し、`ot-logs-<protocol>-*` へ書き込まれ検索可能になることまで実機確認済みです。そして `detection`／`attack` 層を加えると、検知プラグイン（sidecar）を任意の資産へ載せ、Caldera エンジンを配線します。**前身 `ot-ids-verum` の検知シナリオ（Signal 1: ゾーン逸脱検知）を、環境定義に一切手を入れずに差し込み、攻撃 → 構造化 → 検知発火 → 正解ラベルとの一致まで、縦に1本通しきることを実機で確認しました**（不正セグメントからのDNP3送信 → tsharkによる構造化 → sidecarでのアラート発火 → 独立した評価ハーネスでの正解ラベル照合、一致率100%）。
2. 防御側・統裁側向けのHTMLネットワーク図（外部ライブラリ非依存の自己完結ファイル、ズーム/パン・ノードホバーでの詳細表示に対応）：

![Amenonubocoが生成したネットワーク図の例](./docs/images/network-diagram-power.png)

同じマニフェストから生成されるため、実環境の構成と図が乖離しません。図が示す情報：

- **トポロジ** — セグメントを円周上の箱として配置し、複数セグメントに接続する資産（ゲートウェイ `wan_router`、構造化ノード `log_structurer`）は接続先の重心に置いてスポーク線を伸ばします。
- **観測カバレッジ** — 各セグメントの枠色と下端バッジが「観測対象／ミラー集約先／**観測外（死角）**」を示します。破線の矢印は、実際にミラーされるトラフィックの流れです。**どこが死角かを一目で示すこと**を重視しています（演習の統裁側にとっては、見えている範囲より見えていない範囲の方が重要なため）。
- **構造化・検知・可視化** — どのプロトコルがどの Elasticsearch index へ構造化されるか、どの検知プラグイン・可視化エンジンがどの資産に載っているかを左パネルに表示します。検知プラグインを載せた資産には破線の角枠、攻撃エンジン（Caldera）・可視化エンジン（Grafana）には専用色を付けます。

観測カバレッジ・検知配置の判定は図側で再実装せず、プロビジョナと同じロジックをそのまま呼んでいます。図と実環境が別々の答えを出す余地を作らないためです。

3. Grafana ダッシュボード（時系列データの可視化。ネットワーク図が「構造」を可視化するのに対し、こちらは「検知結果・トラフィック統計」を可視化する別レイヤーです）：

![Amenonubocoが配線したGrafanaダッシュボードの例](./docs/images/grafana-dashboard-preview.png)

`visualization` 層は、Grafana server を `topology.assets` へ通常の資産として宣言し、`visualization.host` で名前参照するだけで配線が完成します。データソース（Elasticsearch）は `structuring.protocols[].output_index` と検知アラートの命名規約（`ot-signals-<signal>-*`）から**自動生成**され、ダッシュボード定義（JSON）はマニフェスト外のシナリオ資産として読み取り専用マウントされます（プラットフォームは中身を解釈しません、検知プラグインの `source` と同じ扱い）。上のスクリーンショットは、Signal 1（ゾーン逸脱検知）に対する反復攻撃（15回）で蓄積したアラートを、Grafana が実際にプロビジョニングし描画したものを headless Chrome で撮影したものです（13件のアラート発火をタイムライン上に確認できます）。

再現する場合：

```bash
cd platform
python cli.py provision ../manifests/power-grid-reference.yaml          # docker-compose.yml を生成(Grafanaの配線を含む)
python cli.py diagram   ../manifests/power-grid-reference.yaml          # ネットワーク図(HTML)を生成

# 上下水道・重要製造業も同じ2コマンドで生成できる
python cli.py provision ../manifests/water-utility-reference.yaml
python cli.py diagram   ../manifests/water-utility-reference.yaml
python cli.py provision ../manifests/manufacturing-plant-reference.yaml
python cli.py diagram   ../manifests/manufacturing-plant-reference.yaml
```

## ステータス

**Phase 7（重要インフラの器展開）進行中** — 当初「15種を広く浅く展開する」構想でしたが、分野を絞って中身を濃く・複雑にする方が有用性を強く示せると判断し、**電力・上下水道・重要製造業の3分野**へスコープを転換しました（15種という主張自体は保留、3分野の実装から判断材料を得た上で再検討）。3分野とも、実インシデントをモデルにした攻撃シナリオを実プロトコル（SNMP/VNC/EtherNet-IP）で実装し、`docker compose up` による実機確認——攻撃者資産からのアクセス→イベント駆動の検知ログ→tshark構造化パイプラインでの実データ抽出——まで完了しています（詳細は上記「3分野の実証」）。この過程でスキーマに`security-lan`セグメント種別・`security-asset`/`remote-access-gateway`ロールを追加し、生成器・レンダラーの汎用性を高める複数の修正（セグメント配置の動的レイアウト化、マルチホーム資産の実行属性周りの見直し等）も行いました。

Phase 6（可視化層）までの到達点——トポロジ層〜検知・攻撃層の差し込み口（Phase 1〜4）、前身 `ot-ids-verum` の検知シナリオ「Signal 1」の縦通し（Phase 5）、Grafanaダッシュボードへの可視化配線（Phase 6）——はそのまま電力分野に残っています。スキーマ・生成物・シナリオ資産をカバーする pytest スイート（54テスト）と GitHub Actions CI も継続して整備しています。次は3分野の成果を踏まえ、15種への横展開判断とGUI化（ノーコード/ローコードのマニフェストエディタ）の検討に進む予定です。

### 開発

```bash
pip install -r requirements-dev.txt
pytest          # スキーマ検証・生成物・記法ガイド整合・シナリオ資産のテスト
```

## ライセンス

（未定）

---

🤖 このプロジェクトは [Claude Code](https://claude.com/claude-code) を用いて開発されています。
