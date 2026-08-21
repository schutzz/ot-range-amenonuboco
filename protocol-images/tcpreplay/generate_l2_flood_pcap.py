#!/usr/bin/env python3
"""Scenario C用の決定的なPROFINET RT L2フラッドPCAPを生成する。"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


PCAP_GLOBAL_HEADER = struct.Struct("<IHHIIII")
PCAP_RECORD_HEADER = struct.Struct("<IIII")
ETHERTYPE_PROFINET = 0x8892


def profinet_rt_frame(sequence: int) -> bytes:
    """Frame ID 0x8000を持つ最小限のPROFINET RT cyclic-dataフレーム。"""
    destination = b"\xff\xff\xff\xff\xff\xff"
    source = b"\x02\x00\x00" + sequence.to_bytes(3, "big")
    ethernet = destination + source + struct.pack(">H", ETHERTYPE_PROFINET)
    payload = (
        struct.pack(">H", 0x8000)
        + b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
        + struct.pack(">H", sequence % 0x10000)
        + b"\x35\x00"
    )
    return ethernet + payload


def write_pcap(path: Path, frames: int) -> None:
    if frames < 1:
        raise ValueError("frames must be >= 1")
    with path.open("wb") as stream:
        stream.write(PCAP_GLOBAL_HEADER.pack(0xA1B2C3D4, 2, 4, 0, 0, 65535, 1))
        for sequence in range(frames):
            frame = profinet_rt_frame(sequence)
            stream.write(PCAP_RECORD_HEADER.pack(0, sequence, len(frame), len(frame)))
            stream.write(frame)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--frames", type=int, default=10_000)
    args = parser.parse_args()
    write_pcap(args.path, args.frames)


if __name__ == "__main__":
    main()
