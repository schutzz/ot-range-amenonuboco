# プロトコル資産の使い方

`protocol-images/` には、産業用・分野特化のプロトコルを話す小さなDockerイメージが13置いてあります。マニフェストから参照するだけで、**実際にそのプロトコルの通信が発生する資産**を配置できます。

これは15分野のリファレンスを組むための内部部品ではなく、**あなたが自分のレンジを組むときに再利用する部品**です。この文書はそのための手引きです。

---

## 1. なぜ「ポートを開けるだけ」ではいけないか

最小のリスナー（`python3 -m http.server 502` のようなもの）を置いても、レンジは起動します。ネットワーク図も描かれます。テストも通ります。

しかし**そのポートには何も流れません**。`structuring` 層で `modbus` を宣言しても、Modbusのパケットが1つも存在しないため、構造化パイプラインは何も出力しません。壊れているようには見えないのに、観測すべきものが存在しない——これが最も気づきにくい失敗です。

プロトコル資産は、この失敗を避けるためにあります。

---

## 2. 最初に押さえる3つの規則

この3つを外すと、環境は立ち上がるのに何も観測されません。**順番に確認してください。**

### 規則1: サーバ役とクライアント役を対で置く

片方だけではトラフィックが流れません。各イメージは `MODE` 環境変数で役割を切り替えます。

```yaml
- name: reactor_plc          # 機器役（待ち受ける側）
  role: ot-asset
  image: ../protocol-images/modbus
  networks:
    - { segment: field_instrument_lan, ip: 10.4.30.10 }
  overrides:
    command: "python3 /app/run.py"
    environment:
      - "MODE=server"

- name: batch_control_station # ポーリング役（読みに行く側）
  role: ot-asset
  image: ../protocol-images/modbus
  networks:
    - { segment: process_control_lan, ip: 10.4.20.10 }
  overrides:
    command: "python3 /app/run.py"
    environment:
      - "MODE=client"
      - "TARGET=10.4.30.10"
      - "INTERVAL=5"
```

### 規則2: 対になる資産は**別のセグメント**に置く

ミラーリングはゲートウェイのインターフェース上で行われます。同一セグメント内で完結する通信はゲートウェイを通らないため、**ミラーに乗らず、観測されません**。

上の例で `reactor_plc` を `10.4.20.11`（クライアントと同じセグメント）に置くと、通信は成立し、両者のログにも読み書きが出ますが、`ot-logs-modbus-*` は空のままになります。

### 規則3: `overrides.command` を必ず書く

イメージには既定の `CMD` があるので、書かなくてもコンテナは動きます。しかし**書かないと、他セグメントへの経路（`ip route add`）が生成されません**。

経路が無くても、Dockerの既定ゲートウェイ経由で通信自体は成立してしまいます。つまり「通信は流れているのに、あなたのゲートウェイを通らないので観測されない」という状態になります。規則2と同じ失敗を、別の入口から踏むことになります。

書く内容はイメージ既定と同じ `"python3 /app/run.py"` で構いません。宣言することに意味があります。

> **例外**：ゲートウェイを接続していないセグメント（エアギャップの表現）に置く資産は、`overrides.command` を**書いてはいけません**。到達先が無いのに経路を生成しようとして、生成時にエラーになります。死角の資産だけ書き方が変わる——これは意図した設計で、マニフェストの構造そのものが分離を表現しています。

---

## 3. マニフェストからの参照方法

`image` に `./` または `../` で始まるパスを書くと、生成される `docker-compose.yml` では `image:` ではなく **`build:`** になります。パスは生成物（マニフェストと同じディレクトリに出力されます）からの相対パスです。

```yaml
image: ../protocol-images/modbus
```

初回の `docker compose up` でビルドが走ります。以降はレイヤキャッシュが効きます。

---

## 4. 13のイメージ

すべて「サーバ／クライアントを立てて、tsharkが実際にフィールドを抽出するところまで」を実機で確認済みです。「実測フィールド数」はその際に観測できた、そのプロトコル層の異なるフィールド名の数です。

| イメージ | プロトコル | `structuring` に書く名前 | 既定ポート | 実測フィールド数 |
|---|---|---|---|---|
| `modbus` | Modbus/TCP | `modbus` | 502/tcp | — |
| `bacnet` | BACnet/IP | **`bacapp`** | 47808/udp | — |
| `opcua` | OPC UA | `opcua` | 4840/tcp | 118 |
| `dnp3` | DNP3 (IEEE 1815) | `dnp3` | 20000/tcp | 72 |
| `snmp` | SNMP v1/v2c | `snmp` | 161/udp | 20 |
| `dicom` | DICOM | **`dicom`** | 104/tcp | 20 |
| `hl7` | HL7 v2 over MLLP | `hl7` | 2575/tcp | 2（粗い） |
| `sip` | SIP | `sip` | 5060/udp | 46 |
| `enip` | EtherNet/IP (CIP) | `enip` | 44818/tcp | 16（＋CIP層32） |
| `fins` | OMRON FINS | `omron` | 9600/tcp | — |
| `mqtt` | MQTT(S) | `mqtt` | 1883/tcp (TLS:8883) | — |
| `secsgem` | SECS/GEM (HSMS-SS) | `hsms` | 5000/tcp | — |
| `melsec` | 三菱 MCプロトコル(3E) | `tcp.port == 5007` | 5007/tcp | — (※1) |
| `profinet` | PROFINET RT | `pn_rt` | (L2 Raw) | — |
| `ethercat` | EtherCAT | `ecat` | (L2 Raw) | — |

*(※1) MELSECはtsharkネイティブディセクタがないため、`tcp.port` フィルタで捕捉後、Luaプラグインをマウントして解析する運用（詳細は後述）。*

> **`structuring.protocols[].name` はtsharkの表示フィルタ名です。** プロトコルの通称とは限りません。BACnetは `bacapp`、DICOMは `dicom`（`dcm` ではありません）。外すと、ディセクタは正常に動いているのに**そのプロトコルだけレコードが0件**になります。詳しくは第7節を参照してください。

---

## 5. 各イメージの環境変数

すべてのイメージに共通するもの:

| 変数 | 意味 |
|---|---|
| `MODE` | 役割の切り替え（イメージごとに取る値が違う。下記参照） |
| `PORT` | 待ち受け／接続先ポート |
| `TARGET` | 接続先IP（クライアント側でのみ必須） |
| `INTERVAL` | 周期[秒] |
| `LABEL` | ログに出す識別名（`docker logs` で誰の出力か見分けるため） |

### `modbus`

`MODE`: `server` / `client`。`DEVICE_ID`（既定 1）、`REGISTERS`（保持レジスタ数、既定 32）。

クライアントは保持レジスタの読み取り（ファンクションコード3）と単一レジスタの書き込み（同6）を交互に行います。

**実測で取れるもの**: `modbus.func_code`、`modbus.reference_num`、`modbus.word_cnt`、応答の `text` に `Register 0 (UINT16): 527` のような実レジスタ値。`mbtcp.trans_id` / `mbtcp.unit_id`。

### `bacnet`

`MODE`: `device` / `client`。`DEVICE_ID`（BACnetデバイスインスタンス番号）。

クライアントは Who-Is のブロードキャストと ReadProperty（present-value）を送り、デバイスは I-Am と値を返します。

**実測で取れるもの**: サービス選択（Who-Is / I-Am / ReadProperty）、BACnetオブジェクト識別子、`present_value_real`（実プロセス値）。

### `opcua`

`MODE`: `server` / `client`。

サーバは温度・圧力・流量にあたる変数ノードを公開し、周期的に値を更新します。クライアントは読み取りと書き込みを行います。**暗号化なし（SecurityPolicy None）・匿名アクセス許可**です——暗号化すると中身が構造化できなくなるため、観測対象のレンジでは平文であることが前提になります。

**実測で取れるもの**: `opcua.servicenodeid.numeric` が 631（ReadRequest）/ 634（ReadResponse）/ 673（WriteRequest）/ 676（WriteResponse）。`opcua.datavalue.SourceTimestamp`、`opcua.StatusCode`、`opcua.security.seq`。

### `dnp3`

`MODE`: `outstation` / `master`。`DEVICE_ID`（自局アドレス）、`PEER_ID`（相手局アドレス）、`POINTS`（アナログ入力の点数）。

マスタは Class 0/1/2/3 のIntegrity Pollを周期的に投げ、4回に1回は Direct Operate（CROB＝遮断器を投入する種類の制御指令）を送ります。読み取りと制御指令が別のファンクションコードとして現れます。

**実測で取れるもの**: `dnp3.al.func` が 1（READ）/ 5（DIRECT OPERATE）/ 129（RESPONSE）。`dnp3.al.ana_int` に実アナログ値の配列。制御指令では `dnp3.al.ctl.op`・`dnp3.al.ctl.trip`・`dnp3.al.on_time`。`dnp3.src` / `dnp3.dst`（IPとは別のDNP3局アドレス）。ヘッダ・データチャンクのCRCはいずれも Good で通ります。

### `snmp`

`MODE`: `agent` / `poller`。`COMMUNITY`（既定 `public`）、`VERSION`（既定 `2c`）、`SYSNAME` / `SYSLOCATION`。

本物の net-snmp（`snmpd` / `snmpget` / `snmpwalk` / `snmpset`）を使います。ポーラは system MIB の GET、インターフェース一覧の WALK、4巡に1回の SET を行います。

**認証情報は既定のまま（community `public`）**にしてあります。SNMPv1/v2c はコミュニティ文字列を平文で送るため、観測すればそのまま見えます。初期設定のまま露出した管理インターフェースという構図を再現するための設定です。

**実測で取れるもの**: `snmp.community`（平文）、`snmp.name`（OID）、`snmp.value.octets` / `value.int` / `value.timeticks`。PDU種別は `snmp.data` が 0（get）/ 1（get-next）/ 3（set）。

### `dicom`

`MODE`: `scp` / `scu`。`AE_TITLE`（自分のAEタイトル）、`PEER_AE`（相手のAEタイトル）。

SCUは C-ECHO（疎通確認）を毎回、C-STORE（画像送信）を2回に1回行います。

**扱うデータはすべて合成です。** 患者名は `SYNTHETIC^RANGE-PATIENT`、患者IDは `RANGE-nnnn` に固定され、実在しないことが一目で分かる値しか流れません。画像データも持ちません。

**ポートは104のまま使ってください。** tsharkのDICOMディセクタは既定でこのポートに紐づいており、11112等に変えると「TCPとしては見えるがDICOMとして構造化されない」状態になります。

**実測で取れるもの**: `dicom.assoc.ae.calling` / `dicom.assoc.ae.called`（AEタイトル）、`dicom.pdu_type`、`dicom.pctx.abss_syntax`。`text` に患者名・患者ID・Study Descriptionが平文で並びます。

### `hl7`

`MODE`: `receiver` / `sender`。`APP`（自システムのアプリ名）、`FACILITY`（施設名）。

送信側は ADT^A01（入院登録）と ORU^R01（検査結果・心拍・SpO2）を交互に送り、受信側は ACK を返します。データは DICOM と同じく完全な合成です。

**実測で取れるもの**: `hl7.segment`（MSH/EVN/PID/OBR/OBX等の配列）と `hl7.field`（全フィールドの平坦な配列）の**2つだけ**です。tsharkのHL7ディセクタは名前付きフィールドを持ちません。構造化はされますが、検知を書くなら文字列マッチになります——**このイメージだけ、取れる粒度が明らかに粗い**ことを承知の上で使ってください。

### `sip`

`MODE`: `uas` / `uac`。`DOMAIN`、`USER`、`PEER_USER`。

UACは REGISTER → INVITE → ACK → BYE という1本の呼を周期的に流します。UASは 100 Trying / 180 Ringing / 200 OK（SDP付き）を返します。**認証は行いません**（レジストラは REGISTER に無条件で 200 OK を返します）。

**実測で取れるもの**: `sip.Method`（REGISTER / INVITE / ACK / BYE）、`sip.Status-Code`、`sip.Call-ID`、`sip.from_user` / `sip.to_user`、`sip.Via.sent-by.address`、`sip.contact_uri`。SDPは `sdp` として入れ子で入ります。

### `enip`

`MODE`: `adapter` / `scanner`。`PRODUCT`（アダプタが名乗る製品名）、`CONTEXT`（送信者コンテキスト、8バイトまで）。
また `TLS_ENABLE=true` を指定することで、CIP Security 相当の TLS/DTLS 暗号化ラッパーを有効化できます。`SSLKEYLOGFILE` をマウントして鍵をダンプすることで、TLS暗号化された制御通信の復号・観測パリティの検証が可能です。

スキャナは RegisterSession の後、Get_Attribute_All（Identity）・Get_Attribute_Single（Assembly）・Set_Attribute_Single を巡回します。

`CONTEXT` はEtherNet/IPヘッダの8バイト任意領域にそのまま載ります。要求と応答を対応づけるための欄で**中身は検査されない**ため、攻撃シナリオで目印を仕込む場所として使えます。

**実測で取れるもの**: `enip.command`、`enip.session`、`enip.context`。加えて**CIP層が独立したレイヤ `cip` として現れます**——`cip.service` が 0x01 / 0x0E / 0x10（応答は最上位ビットが立って 0x81 / 0x8E / 0x90）、Identity応答から `cip.id.vendor_id`・`cip.id.product_name`・`cip.id.serial_number`。

### `profinet`

`MODE`: `client` / `server`。L2 Raw Socket (EtherType `0x8892`) を使用して PROFINET RT Cyclic Data フレームをブロードキャストします。
※ L2 通信のため、マニフェスト内で `cap_add: [ "NET_ADMIN", "NET_RAW" ]` が必要です。

### `ethercat`

`MODE`: `master` / `slave`。L2 Raw Socket (EtherType `0x88A4`) を使用して EtherCAT データグラムをブロードキャストします。
※ L2 通信のため、マニフェスト内で `cap_add: [ "NET_ADMIN", "NET_RAW" ]` が必要です。

### `fins`

`MODE`: `server` / `client`。`PORT`（既定 9600）。
オムロン PLC (FINS over TCP) の通信を再現します。クライアント側では `TARGET` を指定します。
内部では DM エリア（データメモリ）の読み書きコマンド（`01 01` / `01 02`）が発行されます。

**実測で取れるもの**: `omron.header.icf`、`omron.header.da1`、`omron.command_code` など FINS ヘッダ・コマンド層フィールド。

### `mqtt`

`MODE`: `broker` / `client`。`PORT`（平文1883、TLS時8883）。
Mosquitto ブローカーと paho-mqtt クライアントの組み合わせ。
`TLS_ENABLE=true` にすると MQTTS になります。`SSLKEYLOGFILE` 環境変数を設定すると、Phase11 暗号鍵注入アーキテクチャにより、マニフェストから TLS 復号（`decryption.keylog_file`）が可能になります。

**実測で取れるもの**: `mqtt.msgtype` (Connect / Publish / Subscribe 等)、`mqtt.topic`、`mqtt.msg` など。

### `secsgem`

`MODE`: `server` (Equipment役) / `client` (Host役)。`PORT`（既定 5000）。
半導体製造装置向けの SECS/GEM HSMS-SS。Select/Linktest などの HSMS 制御メッセージと、S1F1/S1F2、S6F11 (Event Report) などの SECS-II メッセージが流れます。
`TLS_ENABLE=true` で HSMS-SS over TLS になり、MQTT同等の暗号鍵注入が機能します。

**実測で取れるもの**: `hsms.length`、`hsms.session`、`hsms.stype` など。SECS-II メッセージ層（SxFy）はペイロード内に存在します。

### `melsec`

`MODE`: `server` / `client`。`PORT`（既定 5007）。
三菱 MELSEC MC プロトコル 3E フレーム（バイナリモード）の通信。クライアントは Dレジスタの読み書き（0x0401 / 0x1401 コマンド）を行います。

**実測で取れるもの**: tshark のネイティブディセクタが存在しないため、単体では `_ws.malformed` や `data` として扱われます。マニフェストの `structuring.dissector_plugins` に有志の Lua プラグイン（`slmp.lua` 等）をホストパス指定でマウントすることで、独自の解析フィールド（`slmp.command` 等）が抽出可能になります。

---

## 6. `structuring` 層への書き方

構造化は「1プロトコル＝1つのtsharkプロセス＝1つの専用index」で対応します。

```yaml
structuring:
  engine: tshark
  protocols:
    - { name: modbus, output_index: ot-logs-modbus-* }
    - { name: opcua,  output_index: ot-logs-opcua-* }
```

`output_index` の `*` は投入時に日付へ置き換わります（`ot-logs-modbus-2026.08.19` のように）。

`structuring` を宣言するには、`role: structurer` の資産が最低1つ必要です。無い場合はマニフェストの検証で弾かれます——宣言だけあってtsharkが1つも起動しない状態を作らないためです。

---

## 7. うまくいかないときに見る場所

**順番に確認してください。** 上から順に、より起きやすい原因です。

### 該当プロトコルのindexにドキュメントが1件も入らない

1. **サーバとクライアントが別セグメントにいますか**（第2節・規則2）。同一セグメントだとゲートウェイを通らず、ミラーに乗りません。
2. **両方に `overrides.command` を書きましたか**（規則3）。無いと経路が生成されず、Dockerの既定ゲートウェイ経由になってミラーを迂回します。
3. **`structurer` 資産のコンテナログを見てください。** `docker logs <structurer>` に tshark のエラーが出ていることがあります。特に：

   ```
   tshark: "dcm" is neither a field nor a protocol name.
   ```

   これは `structuring.protocols[].name` に書いた名前が、tsharkの表示フィルタ名と一致していないという意味です。第4節の表で正しい名前を確認してください。**この失敗は沈黙しません——証拠はコンテナログに出ています。**
4. **両方の資産のログを見てください。** `docker logs <asset>` に読み書きの行が出ていなければ、そもそも通信が始まっていません。起動直後は接続待ちで失敗することがありますが、各イメージは異常終了せず再試行するので、しばらく待てば繋がります。

### 起動が遅い

初回は `docker compose up` でイメージのビルドが走ります。13すべてを使う場合は数分かかります。2回目以降はレイヤキャッシュが効きます。

### コンテナがすぐ終了する

`MODE` の値が正しいか確認してください。未知の値だとログにその旨を出して終了します。クライアント側で `TARGET` を書き忘れた場合も同様です。

---

## 8. 自分のプロトコルを足す

`protocol-images/<name>/` に `Dockerfile` と起動スクリプトを置き、マニフェストから `image: ../protocol-images/<name>` で参照するだけです。既存の13に倣うなら:

- `MODE` でサーバ／クライアントを切り替える
- 接続失敗で異常終了せず、次の周期で再試行する（起動順序に依存しない器にするため）
- ログは都度フラッシュする（バッファリングされると「動いていないように見える」）
- `iproute2` を同梱する（生成される起動コマンドが `ip route add` を含むため。同梱すると起動時のパッケージ取得が省略されます）
- 外部ライブラリを使うならバージョンを固定する

**そして、器に組み込む前に単体で実機確認してください。** サーバとクライアントを立て、tsharkで該当プロトコルのフィールドが実際に抽出されるところまで見ます。「解析ツールがそのプロトコルに対応している」ことと「自分の計装・構造化パイプラインに載せた時に実際にフィールドが取れる」ことは、別の検証軸です。
