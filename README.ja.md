# Amenonuboco — Cyber Range as Code

[English](./README.md)

> **天沼矛（あめのぬぼこ）** — マニフェスト1枚から、OT/ICS向けサイバーレンジ（攻撃対象・計装・検知パイプライン）を動的にプロビジョニングするプラットフォームです。

![電力ネットワーク図（マニフェストから自動生成）](./docs/images/network-diagram-power.png)

`power-grid-reference.yaml`のような単一マニフェストから、Docker Composeトポロジ、トラフィックミラーリング、tsharkによる構造化パイプラインを生成します。この考え方を **Cyber Range as Code (CRaC)** と呼びます。英語版READMEが正本です。

## 目的と最短起動

OT/ICS演習で繰り返すトポロジ、ミラーリング、sidecar、データ取り込み、シナリオ配線を、再利用可能な宣言的マニフェストにします。検知ロジックと評価は各シナリオ資産の責務です。

Python 3.10–3.12、Docker Compose、ローカルDockerエンジンが必要です。隔離した許可済み検証環境だけで実行し、実稼働または無許可のOT/ICSネットワークへ接続しないでください。

```bash
git clone https://github.com/schutzz/ot-range-amenonuboco.git
cd ot-range-amenonuboco
pip install -r requirements-dev.txt
cd platform
python cli.py provision ../manifests/power-grid-reference.yaml
cd ..
docker compose up -d
```

```bash
python platform/cli.py diagram manifests/power-grid-reference.yaml
```

Compose起動前に無関係なコンテナ・ネットワークを停止してください。Grafana等が固定ホストポートを使うため、残留コンテナは競合や観測検証の不確実性を招きます。性能証跡の参照環境はDocker Desktopであり、全環境・本番環境への性能保証ではありません。

## エディタ・機能・資産

インストール不要の[ブラウザ版エディタ](https://schutzz.github.io/ot-range-amenonuboco/)はCIDR外IP、重複IP、ゲートウェイロールを検証し、トポロジとYAMLを生成します。[エディタガイド](./docs/gui-guide.md)を参照してください。

- tsharkを既定の構造化層とし、Wireshark dissectorを活用
- 検知ロジックをシナリオ資産へ分離
- Spicy/Zeekを高負荷・特殊payload・状態的検知向けの任意プラグインとして利用
- `ot-logs-<protocol>-*`による一貫した出力名

電力（SNMP/UPS不正アクセス）、上下水道（VNC経由のOldsmar型改竄）、重要製造業（EtherNet/IP・カメラ網からの横展開）の3分野で、実OSS実装・実トラフィック・Elasticsearch構造化出力までを通しで実証しています。詳細なログとウォークスルーは[`docs/showcase/`](./docs/showcase/)です。

CISAの重要インフラ分類を基にした15分野の参照マニフェストもあります。実演済み、器のみ、観測できない境界を明示する構成を区別しており、詳細は[分野カバレッジ](./docs/sector-coverage.md)。再利用可能なプロトコル資産（Modbus/TCP、BACnet/IP、OPC UA、DNP3、SNMP、DICOM、HL7 v2、SIP、EtherNet/IP）は[プロトコル資産の使い方](./docs/protocol-assets.md)を参照してください。

## 性能証跡と適用範囲

Phase 12では、Docker Desktop参照環境でPROFINET RTを`tcpreplay`で10秒注入し、最大**200,000 pps**まで、300秒以内のElasticsearch定常化、最終到達率**99.98%以上**、router qdiscドロップ0を確認しました。200,000 ppsはホスト保護のための探索上限であり、絶対上限ではありません。60秒以内に定常化していない状態は、即時の損失ではなく後段滞留として扱います。

SLO、生データ、環境制約、再現コマンドは[`docs/performance/phase12/`](./docs/performance/phase12/)に集約しています。CPU資源緩和の係数は内部探索値であり、外部性能主張には使用しません。

## 開発・貢献・引用

```bash
pip install -r requirements-dev.txt
pytest
```

変更前に[`CONTRIBUTING.md`](./CONTRIBUTING.md)を読んでください。隔離環境での安全性、焦点を絞ったPR、対応テスト、性能主張の再現可能な証跡、英日文書の同期を必須にしています。

Phase 12リリースは[Zenodo DOI](https://doi.org/10.5281/zenodo.22051216)で公開しています。引用情報は[`CITATION.cff`](./CITATION.cff)、ライセンスは[Apache License 2.0](./LICENSE)です。

全Phaseとリリースの履歴は[Release Notes](./docs/releases/README.md)にまとめています。

---

🤖 このプロジェクトは [Claude Code](https://claude.com/claude-code) と [Codex](https://openai.com/codex/) を用いて開発されています。
