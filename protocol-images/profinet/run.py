import os
import time
import struct
from scapy.all import Ether, Raw, sendp, sniff

MODE = os.getenv("MODE", "client").lower()
INTERVAL = float(os.getenv("INTERVAL", "5.0"))
LABEL = os.getenv("LABEL", "profinet")
IFACE = os.getenv("IFACE", "eth0")

PROFINET_ETHERTYPE = 0x8892

def generate_profinet_rt_payload(counter):
    # PROFINET RT Cyclic Data (Frame ID: 0x8000)
    # Frame ID (2 bytes)
    frame_id = struct.pack(">H", 0x8000)
    # IO Data (Dummy 10 bytes) + Cycle Counter (2 bytes) + Data Status (1 byte) + Transfer Status (1 byte)
    io_data = b"\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"
    cycle_counter = struct.pack(">H", counter % 0xFFFF)
    data_status = b"\x35" # Good
    transfer_status = b"\x00"
    return frame_id + io_data + cycle_counter + data_status + transfer_status

def client_mode():
    print(f"[{LABEL}] Starting PROFINET RT Client (Broadcaster) on {IFACE}")
    counter = 0
    while True:
        try:
            payload = generate_profinet_rt_payload(counter)
            # Use broadcast MAC to ensure it hits the gateway's interface for tc mirred
            frame = Ether(dst="ff:ff:ff:ff:ff:ff", type=PROFINET_ETHERTYPE) / Raw(load=payload)
            sendp(frame, iface=IFACE, verbose=False)
            print(f"[{LABEL}] Sent PROFINET RT Frame (Cycle: {counter})")
            counter += 1
        except Exception as e:
            print(f"[{LABEL}] Send error: {e}")
        time.sleep(INTERVAL)

def packet_handler(pkt):
    if pkt.haslayer(Raw):
        payload = pkt[Raw].load
        if len(payload) >= 2:
            frame_id = struct.unpack(">H", payload[:2])[0]
            print(f"[{LABEL}] Received PROFINET RT Frame (ID: 0x{frame_id:04x})")

def server_mode():
    print(f"[{LABEL}] Starting PROFINET RT Server on {IFACE}")
    # filter expression for BPF: ether proto 0x8892
    sniff(iface=IFACE, filter="ether proto 0x8892", prn=packet_handler, store=0)

if __name__ == "__main__":
    if MODE == "client":
        client_mode()
    else:
        server_mode()
