import os
import time
import struct
from scapy.all import Ether, Raw, sendp, sniff

MODE = os.getenv("MODE", "master").lower()
INTERVAL = float(os.getenv("INTERVAL", "5.0"))
LABEL = os.getenv("LABEL", "ethercat")
IFACE = os.getenv("IFACE", "eth0")

ETHERCAT_ETHERTYPE = 0x88A4

def generate_ethercat_payload(counter):
    # EtherCAT Header (2 bytes)
    # Length: 12 (0x0C), Type: 1 (EtherCAT Command)
    length = 12
    ecat_type = 1
    ecat_header = struct.pack("<H", (ecat_type << 12) | length)
    
    # EtherCAT Datagram (12 bytes)
    # Cmd: 1 (APRD), Index: counter % 256
    cmd = 1
    idx = counter % 256
    addr = b"\x00\x00\x00\x00"
    len_flags = struct.pack("<H", 4) # 4 bytes of data
    irq = struct.pack("<H", 0)
    data = b"\xaa\xbb\xcc\xdd"
    wkc = struct.pack("<H", 0)
    
    datagram = struct.pack("BB", cmd, idx) + addr + len_flags + irq + data + wkc
    return ecat_header + datagram

def master_mode():
    print(f"[{LABEL}] Starting EtherCAT Master (Broadcaster) on {IFACE}")
    counter = 0
    while True:
        try:
            payload = generate_ethercat_payload(counter)
            # Use broadcast MAC to ensure it hits the gateway's interface for tc mirred
            frame = Ether(dst="ff:ff:ff:ff:ff:ff", type=ETHERCAT_ETHERTYPE) / Raw(load=payload)
            sendp(frame, iface=IFACE, verbose=False)
            print(f"[{LABEL}] Sent EtherCAT Frame (Index: {counter % 256})")
            counter += 1
        except Exception as e:
            print(f"[{LABEL}] Send error: {e}")
        time.sleep(INTERVAL)

def packet_handler(pkt):
    # scapy は EtherType 0x88A4 を独自の EtherCat/EtherCatAPRD レイヤーとして
    # 解析するため、生の EtherCAT フレームには Raw レイヤーが存在しない
    # （Raw 層の有無を条件にすると、実際のフレームを一切ログできなくなる）。
    # sniff() 側の BPF フィルタで既に EtherCAT のみに絞り込まれているため、
    # 受信した時点でそのまま扱ってよい。
    if pkt.haslayer(Raw):
        payload = pkt[Raw].load
        print(f"[{LABEL}] Received EtherCAT Frame ({len(payload)} bytes, raw)")
    else:
        print(f"[{LABEL}] Received EtherCAT Frame ({len(pkt)} bytes): {pkt.summary()}")

def slave_mode():
    print(f"[{LABEL}] Starting EtherCAT Slave on {IFACE}")
    sniff(iface=IFACE, filter="ether proto 0x88A4", prn=packet_handler, store=0)

if __name__ == "__main__":
    if MODE == "master":
        master_mode()
    else:
        slave_mode()
