# Phase 12 Performance Evidence

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22051216.svg)](https://doi.org/10.5281/zenodo.22051216)

Docker Desktop上のScenario C（PROFINET RT / tcpreplay）測定証跡。生の実行状態は`logs/`に置かず、このフォルダをコミット対象の根拠とする。

- 送信器: tcpreplay 4.3.3、10秒送信、PROFINET RT PCAP
- 条件: 完全再構築、tsharkの`Capturing on`待機、ES件数の連続3回不変まで待機、router qdisc差分記録
- 結論: 50,000 ppsまでqdiscドロップ0・最終到達率ほぼ100%。60秒以内に定常化しない値は損失ではなく後段滞留として扱う。

再現: `python tier4_measure.py --rates 50000 --rounds 3 --settle-timeout 300`

引用: Terayama, D. (2026). *Amenonuboco: Cyber Range as Code* (v0.12.0). Zenodo. https://doi.org/10.5281/zenodo.22051216
