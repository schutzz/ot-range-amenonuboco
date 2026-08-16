"""生成器が共通で使う、シェルスニペット組み立ての小さなヘルパー群。

Phase2で確立した「インターフェース名は常にIPアドレスから動的に逆引きする」
原則(決定事項#29)は、Phase3以降も同じ形で繰り返し必要になる
(ミラーリング設定を行うゲートウェイ資産、構造化を行うstructurer資産、
いずれも自分自身の接続先インターフェースを動的に特定する必要がある)。
"""

from __future__ import annotations


def resolve_interface_snippet(var_name: str, ip: str) -> str:
    """IPアドレスからインターフェース名を動的に解決する1行。
    Dockerの仮想インターフェース名(`eth3@if1462`形式)から実名だけを安全に
    切り出す`awk -F'@'`パターンは、前身ot-ids-verumが罠#003で確立した
    対策をそのまま踏襲している(Phase2決定事項#29)。
    """
    return (
        f"{var_name}=$(ip -o addr show | grep '{ip}' | "
        f"awk '{{print $2}}' | awk -F'@' '{{print $1}}')"
    )
