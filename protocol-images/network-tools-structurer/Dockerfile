# log_structurer(structurerロール)向けbase。
#
# structurerはiproute2(routing/mirroring setup用、_INSTALL_IPROUTE2経由)に
# 加えて、tshark + python3(tshark|bulk_loaderパイプライン、
# platform/generators/structuring.pyの_INSTALL_STRUCTURING_DEPS経由)を
# 必要とする。両者ともgeneratorのcommand生成ロジック側でruntime apt-get
# install(前者は`command -v`短絡あり、後者は無条件)として実装されており、
# いずれも同じ外部APT repository依存の問題を持つ(K8-3
# k8-repro-20260916-001 root-cause post-mortem参照)。
#
# tshark自体の依存footprintがwan_router/tap_observer(protocol-images/
# network-tools)より大きいため、chained FROMにせず独立したDockerfileと
# する——`docker compose up --build`はservice間のbuild順序を保証しない
# ため、他serviceのimageをFROMで参照するchainingはbuild順序の暗黙結合を
# 生み、避けるべきと判断した。iproute2のRUN行はnetwork-tools/Dockerfileと
# 重複するが、このrepositoryの既存protocol-images/*/Dockerfile群も
# それぞれ独立してiproute2導入行を持っており(dnp3, modbus等)、
# 既存規約と一致する。

FROM debian:bullseye-slim@sha256:70509c95d1857a3704c0a5d92ee2e0adac95f612a9386889d70760bfd7c1ebba

# build時sources.listをsnapshot.debian.orgの固定timestampへ差し替える。
# protocol-images/network-tools/Dockerfileと同じ理由(実際にrolling
# mirrorへのapt-get installがtransitive dependencyの404で失敗することを
# CIで確認済み)。詳細はそちらのDockerfileコメント参照。
RUN echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye main" > /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian-security/20260831T070239Z bullseye-security main" >> /etc/apt/sources.list \
    && echo "deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20260831T022607Z bullseye-updates main" >> /etc/apt/sources.list

# tsharkの非対話インストールは「非rootユーザーへcapture権限を与えるか」を
# 尋ねるprompt を持つため、DEBIAN_FRONTEND=noninteractiveが無いと
# apt-getがハングする(platform/generators/structuring.pyのPhase3決定事項
# #44と同じ制約)。
RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 tshark python3 \
    && rm -rf /var/lib/apt/lists/* \
    && command -v ip \
    && command -v tc \
    && command -v tshark \
    && command -v python3
