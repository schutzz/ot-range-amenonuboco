"""tc-netem によるセグメント回線劣化（impairment）の tc コマンド生成器。

Phase 10 決定事項#143/#144/#145/#153:
  * `segments[].impairment` が宣言されていたら、ゲートウェイの該当セグメント向き
    IF の egress root qdisc に netem をアタッチする tc コマンドを生成する。
  * 効果は「このセグメントへの下り方向のみ」（非対称・上りは無制限のまま）。
  * 同一セグメント内の通信（ゲートウェイを経由しない）には一切効かない。
  * mirror_to セグメントへの impairment 宣言はスキーマバリデーション側で事前に
    拒否済み（決定事項#154）のため、ここでは考慮しない。

生成される tc コマンドは shell スクリプト文字列として返す。
プロビジョナ（provisioner.py）が docker exec 経由でゲートウェイコンテナ内で発行する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schema.topology import ImpairmentSpec, Manifest, Segment


def generate_impairment_commands(manifest: "Manifest") -> dict[str, list[str]]:
    """マニフェストを走査し、impairment が宣言されているセグメントについて
    tc-netem の適用コマンドを生成する。

    Returns:
        {segment_name: [tc_command, ...]} のマッピング。
        impairment が宣言されていないセグメントはキーごと省略する。

    ゲートウェイの「該当セグメント向き IF」の解決は、実際のプロビジョナ実行時に
    `ip route` + `ip link` で動的に行う。ここではシェルスニペット（変数を含む）
    として生成し、プロビジョナがゲートウェイコンテナ内で eval する方式とする。
    """
    result: dict[str, list[str]] = {}

    for seg in manifest.topology.segments:
        if seg.impairment is None:
            continue
        cmds = _build_tc_commands(seg.name, seg.impairment)
        if cmds:
            result[seg.name] = cmds

    return result


def _build_tc_commands(seg_name: str, spec: "ImpairmentSpec") -> list[str]:
    """単一セグメントの impairment spec から tc コマンドリストを生成する。

    動作:
      1. ゲートウェイの該当セグメント向き IF を「ネットワークアドレスで一意に
         特定」するシェル式（GW_IF）を組み立てる。
      2. 既存の root qdisc を del してから、netem を add する。
         (すでに netem が設定済みの場合の冪等性を確保するため del は -force で)
      3. `rate` が指定されていれば TBF（Token Bucket Filter）を netem の
         子 qdisc として追加し、帯域制限を layered に適用する。

    命名規則:
        root handle 1: netem ... (決定事項#153: egress のみ)
        child handle 2: tbf ...  (rate 指定時のみ)
    """
    # ゲートウェイ上の「このセグメント向き IF」を IP アドレスで動的解決する
    # シェルフラグメント。プロビジョナが `eval` するためバックスラッシュ不要。
    # `ip route | grep <net>` の代わりに、より堅牢な `ip -o link` を使う。
    # (決定事項#29 と同じ動的解決パターン)
    resolve_if = (
        f"GW_IF=$(ip -o addr | awk '/inet / && /{_seg_network_hint(seg_name)}/{{print $2}}' | head -1)"
    )

    # netem パラメータ組立
    netem_params = _build_netem_params(spec)
    if not netem_params:
        return []  # 全パラメータ未指定ならコマンド生成しない

    cmds = [
        resolve_if,
        # 冪等性: 既存 root qdisc を削除（存在しなくてもエラーにしない）
        "tc qdisc del dev $GW_IF root 2>/dev/null || true",
    ]

    if spec.rate:
        # rate 指定あり: root=netem → child=tbf の 2 段構成
        cmds.append(
            f"tc qdisc add dev $GW_IF root handle 1: netem {netem_params}"
        )
        cmds.append(
            f"tc qdisc add dev $GW_IF parent 1: handle 2: tbf rate {spec.rate} "
            f"burst 32kbit latency 400ms"
        )
    else:
        # rate 指定なし: root=netem のみ
        cmds.append(
            f"tc qdisc add dev $GW_IF root handle 1: netem {netem_params}"
        )

    return cmds


def _build_netem_params(spec: "ImpairmentSpec") -> str:
    """ImpairmentSpec から netem のパラメータ文字列を組み立てる。"""
    parts: list[str] = []
    if spec.delay:
        if spec.jitter:
            parts.append(f"delay {spec.delay} {spec.jitter} distribution normal")
        else:
            parts.append(f"delay {spec.delay}")
    if spec.loss:
        parts.append(f"loss {spec.loss}")
    return " ".join(parts)


def _seg_network_hint(seg_name: str) -> str:
    """セグメント名から IP アドレス範囲のヒントを返す簡易マッピング。

    実際のプロビジョナでは manifest から cidr を直接引けるが、
    このモジュールは segment_name だけを受け取る低レベル関数のため、
    生成されたシェルコマンドを実行するゲートウェイ側で `ip -o addr` から
    cidr を直接 grep するほうが確実。ここでは seg_name をそのまま渡す
    （プロビジョナ側が cidr を置換して渡す設計）。
    """
    # プロビジョナ側で {seg_name} → {actual_cidr_prefix} に置換する想定。
    # ここではプレースホルダとして seg_name を埋め込む。
    return seg_name


def generate_impairment_commands_with_cidr(manifest: "Manifest") -> dict[str, list[str]]:
    """CIDR 情報込みで tc コマンドを生成するバリアント（主な外部 API）。

    ゲートウェイコンテナ内のシェルで実行可能な、CIDR ベースの IF 解決コマンドを
    生成する。プロビジョナが exec するスクリプトとして使う。
    """
    result: dict[str, list[str]] = {}
    seg_by_name = {s.name: s for s in manifest.topology.segments}

    for seg_name, generic_cmds in generate_impairment_commands(manifest).items():
        seg = seg_by_name[seg_name]
        # CIDR の先頭オクテット群（/24 なら .0 を含む prefix）で IF を特定する
        cidr_prefix = seg.cidr.rsplit(".", 1)[0]  # "192.168.20.0/24" → "192.168.20"
        # シェルコマンド内のプレースホルダ（seg_name）を実際の cidr_prefix に置換
        resolved_cmds = [
            cmd.replace(seg_name, cidr_prefix) for cmd in generic_cmds
        ]
        result[seg_name] = resolved_cmds

    return result
