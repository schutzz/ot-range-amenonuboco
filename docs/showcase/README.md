# showcase/

実演のウォークスルー集です。各ドキュメントは、1つの主軸実演について「①マニフェストから攻撃→検知→構造化までを実データで示す一気通貫の記録」と「②どこまでがAmenonubocoの自動生成で、どこからがシナリオ側の持ち込みかを示す境界対応表」の2つを収録します（前身`ot-ids-verum`のPhase5で確立した様式を踏襲）。

> **想定読者・責任ある利用について**：本ウォークスルーは、既に公知の実インシデント（CISA勧告等で詳細が公開済み）を、検知ロジック・構造化パイプライン開発者向けの教材として再現したものです。手口はいずれも標準ツール（VNCクライアント・snmpset・socat等）による、弱い/デフォルト設定への一般的な悪用パターンであり、特定の脆弱性の非公開情報や新規のエクスプロイトコードは含みません。対象資産はすべて合成（synthetic）のDockerコンテナで、実在の事業者・システムとは無関係です。記述の重心は一貫して「検知ログ」「tshark構造化」「実データでの裏付け」にあり、侵入手順そのものの解説ではありません。

| ドキュメント | 分野 | 主軸実演 |
|---|---|---|
| [water-oldsmar-walkthrough.md](./water-oldsmar-walkthrough.md) | 上下水道 | Oldsmar型（正規リモートアクセス経路の悪用によるプロセス値改竄） |
| [power-ups-walkthrough.md](./power-ups-walkthrough.md) | 電力 | UPS可用性攻撃（インターネット露出SNMP管理インターフェースの悪用） |
| [manufacturing-lateral-movement-walkthrough.md](./manufacturing-lateral-movement-walkthrough.md) | 重要製造業 | 監視カメラ経由の横展開（物理セキュリティ網からOTフロアへの越境） |
