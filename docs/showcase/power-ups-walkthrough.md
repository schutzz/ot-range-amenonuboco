# 電力：UPS可用性攻撃ウォークスルー

> [manifests/power-grid-reference.yaml](../../manifests/power-grid-reference.yaml) から生成した環境で、実際に`docker compose up`し攻撃→検知→構造化まで通した記録です。

## この実演が示すもの

2022年、CISA・FBI・DOEが共同で注意喚起を出した事案があります。攻撃者がインターネットに露出した無停電電源装置（UPS）の管理インターフェースへ、初期設定のまま変更されていない認証情報でアクセスし、UPSの設定を書き換えたり停止させたりできる状態になっていた、というものです。ランサムウェア攻撃者がこの経路を悪用する可能性も指摘されました。ここで狙われるのは「プロセス値の改竄」ではなく、電源そのものを止める——**可用性（Availability）への直接攻撃**です。

この実演では、この構図をAmenonubocoのマニフェスト1枚から生成した環境で再現します。「それっぽいSNMPトラフィック」ではなく、実際のSNMPエージェント（net-snmpの`snmpd`）・実際のSNMPクライアント（`snmpset`）による本物のSNMPv2c通信です。認証情報はcommunity文字列`public`のまま——初期設定を変更しないまま外部に露出したUPS管理インターフェースを、そのまま再現しています。

## ①一気通貫の実証ログ

```
マニフェスト（power-grid-reference.yaml）
  ↓
環境生成（docker compose up。cc_ups・ups_attacker・wan_router は
          すべてマニフェストの宣言から自動生成された）
  ↓
攻撃（ups_attacker [172.18.0.50、wan_link＝外部境界相当] が snmpset で
      cc_ups [10.1.10.95、cc_lan＝中央制御室] のSNMP管理インターフェースへ、
      community文字列 "public" のまま sysLocation(OID 1.3.6.1.2.1.1.6.0) を
      "UNAUTHORIZED_SHUTDOWN_COMMAND_INJECTED" へ書き換えようと試みる。
      15秒間隔で計6回試行）
  ↓
検知（cc_ups が、非localhost送信元からのSNMPアクセス自体をリアルタイムに検知し
      "UNAUTHORIZED SNMP ACCESS FROM NON-LOCAL SOURCE DETECTED --
       SIMULATING UPS SHUTDOWN (AVAILABILITY LOSS)" を毎回出力）
  ↓
構造化（log_structurerのtsharkが実際のSNMPパケットを捕捉し、ot-logs-snmp-* へ
        投入。community文字列・SETリクエストの対象OID・書き込もうとした値まで、
        すべてクリアテキストのまま構造化データとして抽出できる）
```

構造化されたデータの実データ（Elasticsearchから抜粋）：

```json
{
  "ip_ip_src": "172.18.0.50",
  "ip_ip_dst": "10.1.10.95",
  "udp_udp_dstport": "161",
  "snmp_snmp_version": "1",
  "snmp_snmp_community": "public",
  "snmp_snmp_name": "1.3.6.1.2.1.1.6.0",
  "text": "1.3.6.1.2.1.1.6.0: \"UNAUTHORIZED_SHUTDOWN_COMMAND_INJECTED\""
}
```

`snmp_snmp_community`の値がそのまま`"public"`——初期設定の認証情報が平文で流れていることが、パケット観測だけから直接確認できます。`snmp_snmp_name`（対象OID）・`text`（書き込もうとした値）も同様にクリアテキストで抽出されており、アプリケーションログに一切頼らずSNMP層の構造をそのまま裏付けられることを示しています。

なお実機検証では、使用したsnmpdビルドが`sysLocation.0`へのSNMP SET自体を`notWritable`として拒否することが判明しました（`ups_attacker`側のログに`Error in packet. Reason: notWritable`が記録される）。書き込みの成否に関わらず、**「非localhostからのSNMPアクセスが行われたこと自体」を送信元ベースの許可リスト方式で検知する**設計にしたことで、この実装差異に検知ロジックが影響を受けない構成になっています。

## ②境界の対応表

「どこまでがAmenonubocoの自動生成で、どこからがシナリオ側が持ち込んだ中身か」の切り分けです。

| 要素 | Amenonuboco が生成 | シナリオ資産（ユーザー提供） | 結果 |
|---|---|---|---|
| ネットワーク・セグメント・ルーティング | ✅ 自動（`topology`層） | — | `wan_link`（外部境界相当）↔`cc_lan`（中央制御室）間のルーティングが自動生成 |
| 観測カバレッジ・ミラーリング | ✅ 自動（`instrumentation`層） | — | 攻撃トラフィックがゲートウェイ経由で`mirror_link`へ届く |
| SNMP構造化 | ✅ 自動（`structuring`層、tshark） | — | `ot-logs-snmp-*`へ投入 |
| UPS管理インターフェースの実行環境 | ✅ 自動（`topology.assets`、`ot-asset`ロール） | — | `cc_ups`コンテナでsnmpd・検知ロジックが起動 |
| 検知ロジックの中身 | 資産の`overrides.command`のみ | 非localhost送信元のSNMPアクセス検知ロジック | 送信元ベースでの不正アクセス検知・ログ出力 |
| 標的（UPS管理IF）の中身 | 資産の`overrides.command`のみ | net-snmp（`snmpd`）の起動設定、community "public" | 初期設定のまま露出したSNMPエージェントとして動作（2022年CISA/FBI/DOE注意喚起の認証形骸化を再現） |
| 攻撃の中身 | 攻撃者ノードの配置・実行環境（`topology.assets`、`attacker-external`ロール） | `snmpset`によるsysLocation書き換え試行 | SNMP SETリクエストの送信 |

**「Amenonuboco が生成」列だけを見れば、環境・配線・実行基盤はすべて宣言から自動生成され、ユーザーが持ち込むのは「検知ロジックの中身」「標的アプリの中身」「攻撃の中身」という3つの小さなスクリプトだけであることが分かります。**上下水道・重要製造業の実演と全く同じ型で、電力分野に「可用性への直接攻撃」という他分野には無い攻撃パターンを持ち込んでいます。

## ネットワーク図

![電力ネットワーク図](../images/network-diagram-power.png)

## 再現方法

```bash
cd platform
python cli.py provision ../manifests/power-grid-reference.yaml
docker compose -f ../manifests/power-grid-reference.docker-compose.yml up -d \
  wan_router cc_ups ups_attacker log_structurer elasticsearch
```

`ups_attacker`は起動後から15秒間隔で6回、SNMP SETを試みます。`docker logs <cc_ups のコンテナ名>`で検知ログを、Elasticsearchの`ot-logs-snmp-*`で構造化結果を確認できます。
