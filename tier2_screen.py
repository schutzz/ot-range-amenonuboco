"""Phase12 Tier 2: structurerのCPU/メモリ制限を独立に比較する一次測定。"""

import json
import os
import subprocess
import sys
import time
import urllib.request


COMPOSE_FILE = "manifests/stress-test-reference.docker-compose.yml"
PROJECT = "amenonuboco-bench"
STRUCTURER = f"{PROJECT}-log_structurer-1"
CONDITIONS = (
    ("baseline", "1.0", "512m"),
    ("cpu_2", "2.0", "512m"),
    ("cpu_4", "4.0", "512m"),
    ("mem_1g", "1.0", "1g"),
    ("mem_2g", "1.0", "2g"),
)


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(command)}", flush=True)
    return subprocess.run(command, check=True, text=True, capture_output=True, env=env)


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
    run(["docker", "update", "--cpus", cpus, "--memory", memory, STRUCTURER])
    result = run(
        ["python", "platform/tools/run_benchmark.py", "--scenario", "B", "--duration", "30",
         "--batch-size", "100", "--settle-timeout", "60"],
    )
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    payload.update({"condition": name, "cpus": cpus, "memory": memory})
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    return payload


def main() -> None:
    for condition in CONDITIONS:
        run_condition(*condition)


if __name__ == "__main__":
    main()
