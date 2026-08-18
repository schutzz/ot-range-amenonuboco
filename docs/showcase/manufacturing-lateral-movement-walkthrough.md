# 重要製造業：監視カメラ経由の横展開ウォークスルー

> [manifests/manufacturing-plant-reference.yaml](../../manifests/manufacturing-plant-reference.yaml) から生成した環境で、実際に`docker compose up`し攻撃→検知→構造化まで通した記録です。

## この実演が示すもの

製造業の工場ネットワークでは、監視カメラ・入退室管理といった物理セキュリティ系（警備系）が、生産ラインのOT機器と同じネットワーク基盤の上に混在していることが少なくありません。両者は本来別のリスクプロファイルを持つにもかかわらず、セグメント分離が甘いと、**監視カメラ網の侵害が、そのまま生産ラインへの横展開の踏み台になる**という構図が生まれます。これは複数のICSインシデント調査で繰り返し指摘されてきたパターンです。

この実演では、この構図をAmenonubocoのマニフェスト1枚から生成した環境で再現します。「それっぽいEtherNet/IPトラフィック」ではなく、実際のEtherNet/IPカプセル化ヘッダ（ListServicesコマンド、24byte）を使った本物のプロトコル通信です。

## ①一気通貫の実証ログ

```
マニフェスト（manufacturing-plant-reference.yaml）
  ↓
環境生成（docker compose up。attacker_internal・line_b_robot_controller・
          wan_router はすべてマニフェストの宣言から自動生成された）
  ↓
攻撃（attacker_internal [10.3.40.50、physical_security_lan＝監視カメラ網を
      侵害済みという想定の踏み台] が、line_b_robot_controller
      [10.3.30.10、production_line_b_lan＝生産ラインB] のEtherNet/IP既定
      ポート(44818)へ、本物のENIPカプセル化ヘッダ(Command=ListServices、
      Context="PIVOT!!!")を15秒間隔で計5回送信)
  ↓
検知（line_b_robot_controller が、物理セキュリティ網からの予期しない接続を
      イベント駆動でリアルタイムに検知し
      "UNEXPECTED CONNECTION FROM PHYSICAL SECURITY SEGMENT DETECTED
       (LATERAL MOVEMENT)" を出力）
  ↓
構造化（log_structurerのtsharkが実際のENIPディセクタでカプセル化ヘッダを
        解析し、ot-logs-enip-* へ投入。enip.command(0x04=ListServices)・
        enip.context(埋め込んだ"PIVOT!!!"マーカー)まで正しく抽出できる）
```

構造化されたデータの実データ（Elasticsearchから抜粋）：

```json
{
  "ip_ip_src": "10.3.40.50",
  "ip_ip_dst": "10.3.30.10",
  "tcp_tcp_dstport": "44818",
  "enip_enip_command": "0x00000004",
  "enip_enip_context": "50:49:56:4f:54:21:21:21"
}
```

`ip_ip_src`が`10.3.40.50`（物理セキュリティ網の`attacker_internal`）、`ip_ip_dst`が`10.3.30.10`（生産ラインBの`line_b_robot_controller`）——セグメントをまたいだ通信であることがIP層からそのまま裏付けられます。`enip_enip_command`の`0x00000004`はEtherNet/IPのListServicesコマンド、`enip_enip_context`の16進列`50:49:56:4f:54:21:21:21`はASCIIで`"PIVOT!!!"`（横展開を示す目印として埋め込んだ文字列）にデコードでき、tsharkの実ENIPディセクタがカプセル化ヘッダの中身まで正しく解釈できていることを示しています。

なお、当初は攻撃ペイロードを`printf`のバックスラッシュエスケープ（`\004`等）で組み立てていましたが、Docker Compose自身のcommand文字列パース層でバックスラッシュが消費され、コンテナに届く頃にはリテラルの`"004"`という数字文字列に化けてしまうという罠がありました。base64エンコードでペイロードを埋め込む方式に変更することで、この曖昧さを構造的に回避しています。

## ②境界の対応表

「どこまでがAmenonubocoの自動生成で、どこからがシナリオ側が持ち込んだ中身か」の切り分けです。

| 要素 | Amenonuboco が生成 | シナリオ資産（ユーザー提供） | 結果 |
|---|---|---|---|
| ネットワーク・セグメント・ルーティング | ✅ 自動（`topology`層） | — | `physical_security_lan`（警備系）↔`production_line_b_lan`（生産ラインB）間のルーティングが自動生成 |
| 観測カバレッジ・ミラーリング | ✅ 自動（`instrumentation`層） | — | 攻撃トラフィックがゲートウェイ経由で`mirror_link`へ届く |
| ENIP構造化 | ✅ 自動（`structuring`層、tshark） | — | `ot-logs-enip-*`へ投入 |
| 警備系セグメント・ロール | ✅ 自動（`security-lan`セグメント種別、`security-asset`ロール） | — | `physical_security_lan`・`nvr_server`・`access_control_panel`の意味付けと配線が自動生成 |
| 標的（ロボットコントローラ）の実行環境 | ✅ 自動（`topology.assets`、`ot-asset`ロール） | — | `line_b_robot_controller`コンテナでsocatリスナー・検知ロジックが起動 |
| 検知ロジックの中身 | 資産の`overrides.command`のみ | セグメント越境接続の検知ロジック | 物理セキュリティ網からの接続を検知・ログ出力 |
| 攻撃の中身 | 攻撃者ノードの配置・実行環境（`topology.assets`、`attacker-internal`ロール） | 本物のENIPカプセル化ヘッダの送信 | ListServicesリクエストの送信 |

**「Amenonuboco が生成」列だけを見れば、環境・配線・実行基盤はすべて宣言から自動生成され、ユーザーが持ち込むのは「検知ロジックの中身」「攻撃の中身」という2つの小さなスクリプトだけであることが分かります。**上下水道・電力の実演と全く同じ型で、重要製造業分野には「警備系からOTフロアへの横展開」という他分野には無いネットワーク構造（物理セキュリティ網とOTフロアの混在）を持ち込んでいます。

## ネットワーク図

![重要製造業ネットワーク図](../images/network-diagram-manufacturing.png)

## 再現方法

```bash
cd platform
python cli.py provision ../manifests/manufacturing-plant-reference.yaml
docker compose -f ../manifests/manufacturing-plant-reference.docker-compose.yml up -d \
  wan_router line_b_robot_controller attacker_internal log_structurer elasticsearch
```

`attacker_internal`は起動後から15秒間隔で5回、ENIPカプセル化ヘッダを送信します。`docker logs <line_b_robot_controller のコンテナ名>`で検知ログを、Elasticsearchの`ot-logs-enip-*`で構造化結果を確認できます。
