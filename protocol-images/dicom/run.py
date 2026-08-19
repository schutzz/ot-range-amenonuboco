#!/usr/bin/env python3
"""DICOM の SCP（画像サーバ／PACS役）と SCU（モダリティ・ワークステーション役）。

サイバーレンジの資産として置くための最小実装。環境変数で役割と接続先を
変えられるようにしてあり、同じイメージを複数の分野・複数の資産で使い回す
(使い方は docs/protocol-assets.md)。

環境変数:
    MODE       scp | scu             （既定: scp。server/client も可）
    PORT       待ち受け/接続先ポート （既定: 104）
    TARGET     接続先IP（scu時のみ必須）
    INTERVAL   送信間隔[秒]          （既定: 5）
    AE_TITLE   自分のAEタイトル      （既定: scp=RANGE_PACS / scu=RANGE_MOD）
    PEER_AE    相手のAEタイトル      （既定: RANGE_PACS）
    LABEL      ログに出す識別名      （既定: dicom）

**ポートについて**：既定を 104（DICOMのウェルノウンポート）にしてある。
tsharkのDICOMディセクタは既定でこのポートに紐づいており、別のポート
（11112等）を使うと「TCPとしては見えるがDICOMとして構造化されない」状態に
なる。構造化まで届かせることが目的なので、既定は104を採る。

**`structuring.protocols` に書く名前は `dicom`**（`dcm` ではない）。
Wiresharkの表示フィルタ名は途中で改名されており、`dcm` と書くと
tsharkが「そんなプロトコルは無い」として起動に失敗する——マニフェストは
妥当なまま、そのプロトコルだけ構造化されない状態になる。

**扱うデータは完全な合成データである。** 患者名・患者IDは実在しないことが
一目で分かる値（`SYNTHETIC^RANGE-PATIENT` / `RANGE-nnnn`）に固定してあり、
画像データも持たない。医療分野の器は「実際の患者情報がネットワークを
平文で流れる」という構図の再現が目的であって、それらしい中身の捏造ではない。
"""

from __future__ import annotations

import logging
import os
import random
import sys
import time

logging.basicConfig(level=logging.WARNING)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


LABEL = env("LABEL", "dicom")
PORT = env_int("PORT", 104)


def log(message: str) -> None:
    print(f"[{LABEL}] {message}", flush=True)


def _build_dataset():
    """C-STORE で送る最小の合成データセット。"""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import (
        ExplicitVRLittleEndian,
        SecondaryCaptureImageStorage,
        generate_uid,
    )

    dataset = Dataset()
    dataset.PatientName = "SYNTHETIC^RANGE-PATIENT"
    dataset.PatientID = f"RANGE-{random.randint(1000, 9999)}"
    dataset.StudyDescription = "Amenonuboco cyber range synthetic study"
    dataset.Modality = "OT"  # Other（実モダリティを騙らない）
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = generate_uid()
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()

    dataset.file_meta = FileMetaDataset()
    dataset.file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    dataset.file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    dataset.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    return dataset


def run_scp() -> None:
    from pynetdicom import AE, evt
    from pynetdicom.sop_class import Verification
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

    ae_title = env("AE_TITLE", "RANGE_PACS")

    def handle_echo(event):
        log(f"C-ECHO from {event.assoc.requestor.ae_title}")
        return 0x0000

    def handle_store(event):
        dataset = event.dataset
        patient = getattr(dataset, "PatientID", "?")
        log(f"C-STORE received (PatientID={patient})")
        return 0x0000

    # SCU側が要求する2つだけを受ける。pynetdicomの
    # AllStoragePresentationContexts は単体でDICOMの上限（128個）を使い切る
    # ため、Verification を足すと関連付け要求が組めなくなる。
    ae = AE(ae_title=ae_title)
    ae.add_supported_context(Verification)
    ae.add_supported_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)

    log(f"DICOM SCP listening on 0.0.0.0:{PORT} (AE title={ae_title})")
    ae.start_server(
        ("0.0.0.0", PORT),
        evt_handlers=[(evt.EVT_C_ECHO, handle_echo), (evt.EVT_C_STORE, handle_store)],
    )


def run_scu() -> None:
    from pynetdicom import AE
    from pynetdicom.sop_class import Verification
    from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage

    target = env("TARGET")
    if not target:
        log("TARGET が未設定です（MODE=scu では接続先IPが必須）")
        sys.exit(1)

    ae_title = env("AE_TITLE", "RANGE_MOD")
    peer_ae = env("PEER_AE", "RANGE_PACS")
    interval = env_int("INTERVAL", 5)

    ae = AE(ae_title=ae_title)
    ae.add_requested_context(Verification)
    ae.add_requested_context(SecondaryCaptureImageStorage, ExplicitVRLittleEndian)

    log(f"associating with {target}:{PORT} every {interval}s ({ae_title} -> {peer_ae})")

    rounds = 0
    while True:
        rounds += 1
        try:
            assoc = ae.associate(target, PORT, ae_title=peer_ae)
            if not assoc.is_established:
                # SCP側の起動待ちで最初の数回は失敗しうる。異常終了させず、
                # 次の周期で再試行する（起動順序に依存しない器にするため）。
                log("association rejected/aborted, retrying")
            else:
                status = assoc.send_c_echo()
                log(f"C-ECHO status: 0x{status.Status:04x}" if status else "C-ECHO failed")

                # 2巡に1回は画像送信も行う。C-ECHO（疎通確認）だけでは
                # 中身のあるデータが流れないため、実際に患者情報を含む
                # データセットが平文で流れる状態を作る。
                if rounds % 2 == 0:
                    dataset = _build_dataset()
                    status = assoc.send_c_store(dataset)
                    log(
                        f"C-STORE (PatientID={dataset.PatientID}) status: "
                        f"0x{status.Status:04x}"
                        if status
                        else "C-STORE failed"
                    )
                assoc.release()
        except Exception as exc:  # noqa: BLE001 - レンジ資産は落とさず回し続ける
            log(f"unexpected error: {exc}")
        time.sleep(interval)


def main() -> None:
    mode = env("MODE", "scp").lower()
    if mode in ("scp", "server"):
        run_scp()
    elif mode in ("scu", "client"):
        run_scu()
    else:
        log(f"未知の MODE '{mode}'（scp または scu を指定してください）")
        sys.exit(1)


if __name__ == "__main__":
    main()
