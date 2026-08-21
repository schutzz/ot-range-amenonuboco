"""Phase12 Tier4: Scenario Cの段階的tcpreplay測定と進捗JSON。"""
from __future__ import annotations

import json
import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATUS = Path("logs/tier4-status.json")
RATES = (5000, 10000, 25000, 50000)


def write_status(**updates: object) -> None:
    current = json.loads(STATUS.read_text()) if STATUS.exists() else {}
    current.update(updates)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    temp = STATUS.with_suffix(".tmp")
    STATUS.parent.mkdir(exist_ok=True)
    temp.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
    temp.replace(STATUS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rates", nargs="+", type=int, default=list(RATES))
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--settle-timeout", type=int, default=60)
    args = parser.parse_args()
    rates = tuple(args.rates)
    schedule = tuple(rate for offset in range(args.rounds) for rate in rates[offset % len(rates):] + rates[:offset % len(rates)])
    results: list[dict] = []
    write_status(state="starting", total_trials=len(schedule), completed_trials=0, results=[])
    for number, rate in enumerate(schedule, 1):
        write_status(state="running", trial=number, pps=rate)
        subprocess.run(["docker", "compose", "-f", "manifests/stress-test-reference.docker-compose.yml", "-p", "amenonuboco-bench", "down", "-v"], check=True)
        command = [sys.executable, "platform/tools/run_benchmark.py", "--scenario", "C", "--duration", "10", "--setup", "--batch-size", "100", "--settle-timeout", str(args.settle_timeout), "--tcpreplay-pps", str(rate)]
        output = subprocess.run(command, check=True, text=True, capture_output=True)
        result = json.loads(output.stdout.strip().splitlines()[-1])
        result["requested_pps"] = rate
        results.append(result)
        write_status(state="running", completed_trials=number, last_result=result, results=results)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    write_status(state="completed", trial=None)


if __name__ == "__main__":
    main()
