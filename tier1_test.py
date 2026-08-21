"""Phase12 Tier 1の再現可能なバッチサイズ実測を行う。

各試行の前にComposeプロジェクトを破棄し、条件を交互に実行する。計測条件は
run_benchmark.pyのCLI引数で渡すため、測定中に追跡対象のソースを改変しない。
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


def run_benchmark(*, duration: int, batch_size: int) -> tuple[float | None, dict | None]:
    command = [
        "python", BENCH_FILE, "--scenario", "B", "--duration", str(duration), "--setup",
        "--batch-size", str(batch_size), "--settle-timeout", "60",
    ]
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, capture_output=True, text=True)
    last_line = result.stdout.strip().split("\n")[-1]
    try:
        payload = json.loads(last_line)
        return payload["loss_pct"], payload
    except (json.JSONDecodeError, KeyError):
        print("Failed to parse benchmark result:", last_line)
        print("stdout:", result.stdout[-2000:])
        print("stderr:", result.stderr[-2000:])
        return None, None


def test_batch_sizes(
    n_trials: int, batch_sizes: tuple[int, ...] = (50, 100, 200)
) -> dict[int, list[float | None]]:
    results = {size: [] for size in batch_sizes}
    for trial in range(n_trials):
        for size in batch_sizes:
            print(f"\n=== batch={size}, trial {trial + 1}/{n_trials} (fresh teardown) ===", flush=True)
            teardown()
            loss, payload = run_benchmark(duration=30, batch_size=size)
            print(f"batch={size}: {loss}% ({payload})")
            results[size].append(loss)
    return results


def main() -> None:
    n_trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    results = test_batch_sizes(n_trials)
    print("\n=== BATCH-SIZE SUMMARY ===")
    for size, losses in results.items():
        valid = [loss for loss in losses if loss is not None]
        mean = statistics.mean(valid) if valid else float("nan")
        print(f"batch={size}: {losses} -> mean={mean:.2f}%")


if __name__ == "__main__":
    main()
