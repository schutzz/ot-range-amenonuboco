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

| ファイル | 分野 | 主軸実演 |
|---|---|---|
| [`power-grid-reference.yaml`](./power-grid-reference.yaml) | 電力 | UPS管理インターフェースへの不正SNMPアクセス（可視化層まで配線済み） |
| [`water-utility-reference.yaml`](./water-utility-reference.yaml) | 上下水道 | Oldsmar型（正規リモートアクセス経路の悪用によるプロセス値改竄） |
| [`manufacturing-plant-reference.yaml`](./manufacturing-plant-reference.yaml) | 重要製造業 | 監視カメラ経由の横展開（物理セキュリティ網→OTフロア） |

いずれも `docker compose up` による実機確認（攻撃者アクセス→検知ログ→tshark構造化パイプラインでの実データ抽出）まで済んでいます。生成方法はリポジトリルートの [README.md](../README.md) を参照してください。

`*.docker-compose.yml`・`*.network-diagram.html` はこれらのマニフェスト（ソース）から`platform/cli.py`で生成されるビルド成果物のため、`.gitignore`でリポジトリから除外しています。
