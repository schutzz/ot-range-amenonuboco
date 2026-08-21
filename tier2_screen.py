"""Phase12 Tier 2: structurerのCPU/メモリ制限を独立に比較する一次測定。"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import argparse
from datetime import datetime, timezone
from pathlib import Path


COMPOSE_FILE = "manifests/stress-test-reference.docker-compose.yml"
PROJECT = "amenonuboco-bench"
STRUCTURER = f"{PROJECT}-log_structurer-1"
STATUS_FILE = Path("logs/tier2-status.json")
CONDITIONS = (
    ("baseline", "1.0", "512m"),
    ("cpu_2", "2.0", "512m"),
    ("cpu_4", "4.0", "512m"),
    ("mem_1g", "1.0", "1g"),
    ("mem_2g", "1.0", "2g"),
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, text=True, capture_output=True, env=env)
    if result.returncode:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout: {result.stdout[-2000:]}\nstderr: {result.stderr[-2000:]}"
        )
    return result


def write_status(**updates: object) -> None:
    """IDEから確認できる、実行状態の単一情報源を原子的に更新する。"""
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    current = {}
    if STATUS_FILE.exists():
        current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    current.update(updates)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS_FILE)


def wait_for_es(timeout_s: int = 60) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:9200", timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("Elasticsearch did not become ready")


def run_condition(name: str, cpus: str, memory: str) -> dict:
    write_status(state="running", condition=name, cpus=cpus, memory=memory)
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", PROJECT, "down", "-v"],
        check=False, capture_output=True, text=True,
    )
    run(["python", "platform/cli.py", "provision", "manifests/stress-test-reference.yaml"])
    env = os.environ | {"BULK_LOADER_BATCH_SIZE": "100"}
    run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", PROJECT, "up", "-d",
         "wan_router", "elasticsearch", "log_structurer"],
        env=env,
    )
    wait_for_es()
    # Docker はメモリ上限を既存のmemoryswap上限より大きく更新できない。
    # 両方を同じ値にしてswapなしの明示的な制限として更新する。
    run(
        ["docker", "update", "--cpus", cpus, "--memory", memory,
         "--memory-swap", memory, STRUCTURER]
    )
    result = run(
        ["python", "platform/tools/run_benchmark.py", "--scenario", "B", "--duration", "30",
         "--batch-size", "100", "--settle-timeout", "60"],
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    payload.update({"condition": name, "cpus": cpus, "memory": memory})
    current = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    history = list(current.get("results", []))
    history.append(payload)
    write_status(
        state="running", completed_condition=name, last_result=payload,
        results=history, error=None, last_error=None,
    )
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", action="append", choices=[condition[0] for condition in CONDITIONS])
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    conditions = tuple(condition for condition in CONDITIONS if not args.only or condition[0] in args.only)
    schedule = tuple(
        condition
        for trial in range(args.repeat)
        for condition in conditions[trial % len(conditions):] + conditions[:trial % len(conditions)]
    )
    write_status(state="starting", total_conditions=len(schedule), completed_conditions=0)
    try:
        for index, condition in enumerate(schedule, start=1):
            run_condition(*condition)
            write_status(state="running", completed_conditions=index)
    except Exception as exc:
        write_status(state="failed", error=str(exc))
        raise
    write_status(state="completed", condition=None)


if __name__ == "__main__":
    main()
