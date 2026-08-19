# manifests/

サイバーレンジを宣言的に定義するマニフェストの置き場です。

1枚のマニフェストが、次の5層＋αを宣言します（記法の詳細は [`docs/manifest-schema-guide.md`](../docs/manifest-schema-guide.md)）：

| 層 | 宣言する内容 |
|---|---|
| トポロジ | ネットワークセグメント、資産（PLC/RTU/HMI/攻撃者ノード等）、接続関係 |
| 計装（観測） | どのセグメントを、どの方式（ミラーリング/タップ）で観測するか |
| 構造化 | どのプロトコルを、どう構造化するか（既定は tshark） |
| 検知 | どのシナリオ用に、どの検知ロジックを載せるか（シナリオ側の責務） |
| 攻撃 | どの攻撃シナリオを流すか（Caldera連携） |
| 可視化 | 検知結果・トラフィック統計を時系列ダッシュボード（Grafana等）へどう配線するか |

## リファレンスマニフェスト

重要インフラ15分野（CISAの16分野から Information Technology を除いたもの）を揃えていますが、**すべてが同じ深さで作られているわけではありません**。深さは3段階に分かれます。どこまでモデル化したか・何が確かで何が推定かの一覧は [分野カバレッジ](../docs/sector-coverage.md) を参照してください。

### 実演あり（3分野）

攻撃の実演・検知ロジック・正解ラベルとの照合まで含みます。

| ファイル | 分野 | 主軸実演 |
|---|---|---|
| [`power-grid-reference.yaml`](./power-grid-reference.yaml) | 電力 | UPS管理インターフェースへの不正SNMPアクセス（可視化層まで配線済み） |
| [`water-utility-reference.yaml`](./water-utility-reference.yaml) | 上下水道 | Oldsmar型（正規リモートアクセス経路の悪用によるプロセス値改竄） |
| [`manufacturing-plant-reference.yaml`](./manufacturing-plant-reference.yaml) | 重要製造業 | 監視カメラ経由の横展開（物理セキュリティ網→OTフロア） |

いずれも `docker compose up` による実機確認（攻撃者アクセス→検知ログ→tshark構造化パイプラインでの実データ抽出）まで済んでいます。

### 器のみ（6分野）

トポロジ・計装・構造化の3層のみ。攻撃・検知は含みませんが、**実際にそのプロトコルの通信が流れ、構造化されます**（中身は [`protocol-images/`](../protocol-images/) のプロトコル実装、使い方は [プロトコル資産の使い方](../docs/protocol-assets.md)）。

| ファイル | 分野 | 主要プロトコル |
|---|---|---|
| [`chemical-plant-reference.yaml`](./chemical-plant-reference.yaml) | 化学 | Modbus/TCP, OPC UA |
| [`building-automation-reference.yaml`](./building-automation-reference.yaml) | 商業施設 | BACnet/IP |
| [`telecom-core-reference.yaml`](./telecom-core-reference.yaml) | 通信 | SNMP, SIP |
| [`dam-control-reference.yaml`](./dam-control-reference.yaml) | ダム | Modbus/TCP, DNP3 |
| [`food-processing-reference.yaml`](./food-processing-reference.yaml) | 食品・農業 | Modbus/TCP, OPC UA |
| [`hospital-network-reference.yaml`](./hospital-network-reference.yaml) | 医療 | DICOM, HL7 v2 |

### 器のみ・観測境界あり（6分野）

上記に加え、**構造的に観測できない領域を死角として明示的に持ちます**。死角の理由は分野ごとに異なります。

| ファイル | 分野 | 死角にした領域 | 死角の理由 |
|---|---|---|---|
| [`nuclear-plant-reference.yaml`](./nuclear-plant-reference.yaml) | 原子力 | 安全保護系 | 物理的な分離 |
| [`rail-transit-reference.yaml`](./rail-transit-reference.yaml) | 輸送 | 信号保安系 | 取れても読めない（dissector不在） |
| [`emergency-dispatch-reference.yaml`](./emergency-dispatch-reference.yaml) | 緊急サービス | P25デジタル無線 | 伝送媒体が有線でない |
| [`defense-plant-reference.yaml`](./defense-plant-reference.yaml) | 防衛産業基盤 | 機密区画 | 制度的なエアギャップ |
| [`government-facility-reference.yaml`](./government-facility-reference.yaml) | 政府施設 | 機密取扱区画 | 同上 |
| [`financial-datacenter-reference.yaml`](./financial-datacenter-reference.yaml) | 金融 | 決済ネットワーク | 専用線・独自フレーミングで分離 |

生成方法はリポジトリルートの [README.md](../README.md) を参照してください。

`*.docker-compose.yml`・`*.network-diagram.html` はこれらのマニフェスト（ソース）から`platform/cli.py`で生成されるビルド成果物のため、`.gitignore`でリポジトリから除外しています。
