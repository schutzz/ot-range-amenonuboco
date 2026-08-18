"""Grafanaの可視化エンジン実装(Phase6決定事項#80の第1実装)。

前身`ot-ids-verum`のGrafana構成(`grafana/provisioning/`)を分析した結果、
プロビジョニング方式(datasource YAML・dashboards provider YAML・dashboard
JSONをファイルマウント)であることが分かった。この構造はPhase4の検知
プラグイン機構(マニフェスト外ファイルの読み取り専用マウント)とほぼ同型
である(Phase6-Visualization.md 2節)。

前身の実機教訓を踏襲する:
- datasourceの`index`キー(`indexPattern`ではない。前身が実機で全index横断
  検索にフォールバックする形で踏んだ罠)
- カンマ区切りワイルドカードでの複数index横断(前身決定事項#49)
- `timeField: "@timestamp"`
"""

from __future__ import annotations

import yaml

from schema import Asset, Manifest, Visualization, VisualizationDatasource

from .base import (
    ComposeServiceOverlay,
    GeneratedConfig,
    VisualizationEngine,
    VisualizationGenerationError,
)

# Grafanaコンテナ内の標準provisioningパス(前身のgrafana/provisioning/と同じ構造)。
_DATASOURCES_DIR = "/etc/grafana/provisioning/datasources"
_DASHBOARDS_PROVIDER_DIR = "/etc/grafana/provisioning/dashboards"

# 検知アラートの命名規約(Phase6決定事項#86)。構造化ログ(ot-logs-<protocol>-*、
# Phase0決定事項#5)と対になる形で、検知結果は ot-signals-<signal>-* に揃える。
_SIGNALS_INDEX_PATTERN = "ot-signals-*"


class GrafanaEngine(VisualizationEngine):
    def wire(
        self, manifest: Manifest, visualization: Visualization, host_asset: Asset
    ) -> ComposeServiceOverlay:
        datasources = (
            visualization.datasources
            if visualization.has_explicit_datasources()
            else _auto_datasources(manifest)
        )

        configs: dict[str, GeneratedConfig] = {
            "datasources": GeneratedConfig(
                content=_datasources_yaml(datasources, visualization.elasticsearch_url),
                target=f"{_DATASOURCES_DIR}/datasources.yml",
            ),
        }

        volumes: list[str] = []
        if visualization.dashboards:
            # dashboards providerは、ダッシュボードJSONを1件以上マウントする
            # 場合にのみ必要(providerだけあってもGrafana自体は問題無く起動する
            # が、意味の無い設定を生成しない)。
            configs["dashboards-provider"] = GeneratedConfig(
                content=_dashboards_provider_yaml(),
                target=f"{_DASHBOARDS_PROVIDER_DIR}/dashboards.yml",
            )
            seen_filenames: set[str] = set()
            for dashboard_path_str in visualization.dashboards:
                host_path = manifest.resolve_path(dashboard_path_str)
                if not host_path.is_file():
                    raise VisualizationGenerationError(
                        f"visualization.dashboards entry not found: {host_path} "
                        f"(declared as '{dashboard_path_str}')"
                    )
                if host_path.name in seen_filenames:
                    raise VisualizationGenerationError(
                        f"visualization.dashboards has duplicate filename "
                        f"'{host_path.name}' (mount target would collide)"
                    )
                seen_filenames.add(host_path.name)
                target = f"{_DASHBOARDS_PROVIDER_DIR}/{host_path.name}"
                volumes.append(f"{host_path.as_posix()}:{target}:ro")

        environment = [
            # スクショ/レンダリング用の匿名Viewerアクセス(決定事項#85)。ラボ
            # 限定でリスク許容する(前身も同じ設定、admin操作には別途ログイン必須)。
            "GF_AUTH_ANONYMOUS_ENABLED=true",
            "GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer",
            "GF_SECURITY_ADMIN_PASSWORD=admin",
            "GF_USERS_ALLOW_SIGN_UP=false",
        ]

        return ComposeServiceOverlay(
            environment=environment,
            ports=["3000:3000"],
            volumes=volumes,
            configs=configs,
        )


def _auto_datasources(manifest: Manifest) -> list[VisualizationDatasource]:
    """`structuring.protocols`由来の構造化ログindexと、検知アラートの命名
    規約(`ot-signals-*`、決定事項#86)から、既定datasourceを1件自動生成する
    (決定事項#81)。天沼矛は`output_index`を既に知っているため、マニフェストに
    構造化プロトコルを1つ足すだけでdatasourceにも自動で反映される
    (単一ソースから複数出力、ネットワーク図と同じ思想)。
    """
    indices: list[str] = []
    if manifest.structuring is not None:
        indices.extend(p.output_index for p in manifest.structuring.protocols)
    indices.append(_SIGNALS_INDEX_PATTERN)
    return [
        VisualizationDatasource(
            name="Elasticsearch",
            index=",".join(indices),
            time_field="@timestamp",
        )
    ]


def _datasources_yaml(datasources: list[VisualizationDatasource], es_url: str) -> str:
    """Grafana datasource provisioning YAML。前身の実機教訓(`index`キーを
    使う。`indexPattern`は無効なキーでGrafanaに認識されない)を踏まえ、
    辞書構造から`yaml.safe_dump`で組み立てる(手書き文字列によるタイポを避ける)。
    """
    doc = {
        "apiVersion": 1,
        "datasources": [
            {
                "name": ds.name,
                "type": "elasticsearch",
                "access": "proxy",
                "url": es_url,
                "isDefault": i == 0,
                "jsonData": {
                    "index": ds.index,
                    "interval": "",
                    "timeField": ds.time_field,
                    "esVersion": "8.0.0",
                },
            }
            for i, ds in enumerate(datasources)
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def _dashboards_provider_yaml() -> str:
    """Grafana dashboards provider YAML(前身の`dashboards.yml`と同じ構造、
    `path`配下のJSONファイルを自動読み込みする)。
    """
    doc = {
        "apiVersion": 1,
        "providers": [
            {
                "name": "CRaC Dashboards",
                "orgId": 1,
                "folder": "",
                "type": "file",
                "disableDeletion": False,
                "editable": True,
                "allowUiUpdates": True,
                "options": {"path": _DASHBOARDS_PROVIDER_DIR},
            }
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
