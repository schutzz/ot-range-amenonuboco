"""Phase12 Tier 1の再現可能なバッチサイズ実測を行う。

各試行の前にComposeプロジェクトを破棄し、条件順を循環させて実行する。計測
条件はrun_benchmark.pyのCLI引数で渡すため、測定中に追跡対象のソースを改変
しない。既定は50/100/200を各3回、順序を50→100→200、100→200→50、
200→50→100とするラテン方格型の最小設計である。
"""

import json
import statistics
import subprocess
import sys


COMPOSE_FILE = "manifests/stress-test-reference.docker-compose.yml"
BENCH_FILE = "platform/tools/run_benchmark.py"


def teardown() -> None:
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "-p", "amenonuboco-bench", "down", "-v"],
        capture_output=True,
        text=True,
    )


def run_benchmark(*, duration: int, batch_size: int) -> dict | None:
    command = [
        "python", BENCH_FILE, "--scenario", "B", "--duration", str(duration), "--setup",
        "--batch-size", str(batch_size), "--settle-timeout", "60",
    ]
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    last_line = result.stdout.strip().split("\n")[-1]
    try:
        payload = json.loads(last_line)
        return payload
    except (json.JSONDecodeError, KeyError):
        print("Failed to parse benchmark result:", last_line)
        print("stdout:", result.stdout[-2000:])
        print("stderr:", result.stderr[-2000:])
        return None


def test_batch_sizes(
    n_trials: int, batch_sizes: tuple[int, ...] = (50, 100, 200)
) -> dict[int, list[dict | None]]:
    results = {size: [] for size in batch_sizes}
    for trial in range(n_trials):
        # 各条件を先頭・中間・末尾に一度ずつ置く。固定順のウォームアップ等が
        # 条件差へ混入するのを防ぐ（Phase12 罠#060の再発防止）。
        offset = trial % len(batch_sizes)
        order = batch_sizes[offset:] + batch_sizes[:offset]
        for size in order:
            print(f"\n=== batch={size}, trial {trial + 1}/{n_trials} (fresh teardown) ===", flush=True)
            teardown()
            payload = run_benchmark(duration=30, batch_size=size)
            print(f"batch={size}: {payload}")
            results[size].append(payload)
    return results


def main() -> None:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    results = test_batch_sizes(n_trials)
    print("\n=== BATCH-SIZE SUMMARY ===")
    for size, payloads in results.items():
        valid = [payload for payload in payloads if payload is not None]
        throughputs = [payload["throughput_eps"] for payload in valid]
        losses = [payload["loss_pct"] for payload in valid]
        throughput_mean = statistics.mean(throughputs) if throughputs else float("nan")
        loss_mean = statistics.mean(losses) if losses else float("nan")
        print(
            f"batch={size}: throughput={throughputs} -> mean={throughput_mean:.2f} eps; "
            f"loss={losses} -> mean={loss_mean:.2f}%"
        )


if __name__ == "__main__":
    main()
