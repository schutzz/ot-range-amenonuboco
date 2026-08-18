# 上下水道：Oldsmar型実演ウォークスルー

> [manifests/water-utility-reference.yaml](../../manifests/water-utility-reference.yaml) から生成した環境で、実際に`docker compose up`し攻撃→検知→構造化まで通した記録です。

## この実演が示すもの

2021年、米フロリダ州オールズマー浄水場で、正規のリモートアクセスソフトウェア（TeamViewer）経由で不正アクセスした攻撃者が、水酸化ナトリウム（苛性ソーダ）濃度の設定値を100 ppmから11,100 ppmへ書き換えた事件がありました。ファイアウォールを突破したのではなく、**正規のリモート保守経路そのものが、認証情報の使い回し・多要素認証の欠如によって侵害の起点になった**という点が、この事件の核心です。

この実演では、この構図をAmenonubocoのマニフェスト1枚から生成した環境で再現します。「それっぽいVNCトラフィック」ではなく、実際のVNCサーバ（x11vnc）・実際のVNCクライアント（vncdotool）による本物のRFBプロトコル通信です。

## ①一気通貫の実証ログ

```
マニフェスト（water-utility-reference.yaml）
  ↓
環境生成（docker compose up。remote_access_gateway・pump_b_hmi・attacker_external は
          すべてマニフェストの宣言から自動生成された）
  ↓
攻撃（attacker_external [172.19.0.50、wan_link] が vncdotool で
      remote_access_gateway [10.2.40.11、remote_access_dmz] 経由の
      VNCセッションを確立し、pump_b_hmi のNaOH設定値相当のフィールドへ
      "11100" を入力）
  ↓
検知（remote_access_gateway が、DMZ側の受け口(ポート5900)に確立された
      セッションをリアルタイムに検知し
      "REMOTE ACCESS SESSION VIA DMZ ESTABLISHED (OLDSMAR-TYPE CHANNEL)" を出力）
  ↓
構造化（log_structurerのtsharkが実際のRFBハンドシェイク全体
        （Server/Client protocol version → Security types → Authentication →
        Server framebuffer parameters → Client set encodings → Client key event）
        を ot-logs-vnc-* へ投入。攻撃の各ラウンドごとに vnc.key_down=true の
        キー入力イベントが記録され、入力した"11100"の文字コード
        （'1'=49, '0'=48）まで抽出できる）
```

構造化されたキーイベントの実データ（Elasticsearchから抜粋）：

```json
{
  "vnc_vnc_client_message_type": "4",
  "vnc_vnc_key_down": true,
  "vnc_vnc_key": "49"
}
```

`vnc_vnc_key`の値（49・48）は、それぞれASCIIの`'1'`・`'0'`に対応します——攻撃者が入力した"11100"という数値列の一部が、ネットワーク層の観測だけから、アプリケーションログに一切頼らずに復元できることを示しています。

## ②境界の対応表

「どこまでがAmenonubocoの自動生成で、どこからがシナリオ側が持ち込んだ中身か」の切り分けです。

| 要素 | Amenonuboco が生成 | シナリオ資産（ユーザー提供） | 結果 |
|---|---|---|---|
| ネットワーク・セグメント・ルーティング | ✅ 自動（`topology`層） | — | `remote_access_dmz`↔`pump_station_b_lan`間のルーティングが自動生成 |
| 観測カバレッジ・ミラーリング | ✅ 自動（`instrumentation`層） | — | 攻撃トラフィックがゲートウェイ経由で`mirror_link`へ届く |
| VNC構造化 | ✅ 自動（`structuring`層、tshark） | — | `ot-logs-vnc-*`へ投入 |
| リモートアクセス経路の実行環境 | ✅ 自動（`topology.assets`、`remote-access-gateway`ロール） | — | `remote_access_gateway`コンテナでリレー・検知ロジックが起動 |
| リレー・検知ロジックの中身 | 資産の`overrides.command`のみ | ポート越境セッションの検知ロジック | DMZ越しのセッション確立を検知・ログ出力 |
| 標的（VNCサーバ）の中身 | 資産の`overrides.command`のみ | Xvfb + x11vncの起動設定 | パスワード無しのVNCサーバとして動作（Oldsmar事件の認証形骸化を再現） |
| 攻撃の中身 | 攻撃者ノードの配置・実行環境（`topology.assets`） | vncdotoolによるキー入力送信 | VNCキーイベントの送信 |

**「Amenonuboco が生成」列だけを見れば、環境・配線・実行基盤はすべて宣言から自動生成され、ユーザーが持ち込むのは「リレー/検知ロジックの中身」「標的アプリの中身」「攻撃の中身」という3つの小さなスクリプトだけであることが分かります。**

## ネットワーク図

![上下水道ネットワーク図](../images/network-diagram-water.png)

## 再現方法

```bash
cd platform
python cli.py provision ../manifests/water-utility-reference.yaml
docker compose -f ../manifests/water-utility-reference.docker-compose.yml up -d \
  wan_router pump_b_hmi remote_access_gateway attacker_external log_structurer elasticsearch
```

`attacker_external`は起動15秒後から5回、15秒間隔でVNCセッションを試みます。`docker logs <remote_access_gateway のコンテナ名>`で検知ログを、Elasticsearchの`ot-logs-vnc-*`で構造化結果を確認できます。
