# wan_router / tap_observer (l3-router / observer ロール)向けの共通base。
#
# generatorが自動付与する `_INSTALL_IPROUTE2`(platform/generators/compose.py)は
# ip/tc をruntime `apt-get install` で導入する設計であり、コンテナ起動の
# たびに外部APT repositoryへネットワーク越しに依存する。formal K8-3
# attempt `k8-repro-20260916-001` の独立post-mortemで、このAPT取得が
# transitive dependency(libcap2/libpam-cap)の404により失敗し、
# `restart: unless-stopped` による無限restart-loopへ至ったことを確認した
# (root cause: EXTERNAL RUNTIME DEPENDENCY / MUTABLE DEPENDENCY /
# REPOSITORY STATE DRIFT)。
#
# 本Dockerfileは、他のprotocol-images/*/Dockerfile(dnp3, modbus等)が
# 既に採用している「build時に同梱し、runtime apt-getを省略する」規約を
# routing/mirroring/observer用途へ適用したものである。
#
# base imageはamd64 platform-specific digestへpinする(manifest-list index
# digestは同じ名目タグでもpull側architectureにより異なる実体へ解決される
# ため、K8のimmutable identity原則とは相容れない)。

FROM debian:bullseye-slim@sha256:70509c95d1857a3704c0a5d92ee2e0adac95f612a9386889d70760bfd7c1ebba

# iproute2: wan_router/tap_observerともに`ip`/`tc`によるrouting・mirroring
# 設定を必要とする。
# tcpdump: tap_observerがmirror_link上のトラフィックを直接確認するために
# 使う(manifests/*.yamlのoverrides.commandが起動時に実行していたもの)。
#
# apt-get update/installは同一RUN内で完結させ、install成功の
# deterministic確認(`command -v`)をbuild自体の成否に結び付ける——
# インストールが実は失敗していたのにlayerだけ成立する、という取りこぼしを
# build時点で防ぐ。
RUN DEBIAN_FRONTEND=noninteractive apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2 tcpdump \
    && rm -rf /var/lib/apt/lists/* \
    && command -v ip \
    && command -v tc \
    && command -v tcpdump
